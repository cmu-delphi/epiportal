"""Geographic coverage lookups against the Epidata API."""

import ast
from dataclasses import dataclass
from datetime import date

import requests
from django.conf import settings
from delphi_utils import get_structured_logger
from epiweeks import Week

from indicatorsets.utils.caching import safe_cache_get, safe_cache_set
from indicatorsets.utils.constants import DEFAULT_FILL_METHOD
from indicatorsets.utils.epidata import (
    can_fall_back_to_v4,
    epidata_auth,
    get_v5_metadata,
    get_v5_source,
    group_v5_indicators_by_source,
    is_covidcast_indicator,
)
from indicatorsets.utils.helpers import get_epiweek, list_to_dict
from indicatorsets.utils.locations import to_covidcast_geo, to_nwss_sewersheds

logger = get_structured_logger("indicatorsets.utils")

# The first epiweek fluview has, so "all time" on its v4 endpoint.
FLUVIEW_FIRST_EPIWEEK = "199740"


class InvalidDateWindowError(ValueError):
    """The Start/End dates sent with a coverage check make no window."""


@dataclass(frozen=True)
class DateWindow:
    start: date
    end: date


def parse_date_window(start_date, end_date):
    """Return the modal's Start/End dates as a ``DateWindow``, or ``None``.

    ``None`` means all time: Plot mode hides the dates and sends none, since
    EpiVis always plots the whole series. Otherwise both must be
    ``YYYY-MM-DD`` with start on or before end; anything else raises
    ``InvalidDateWindowError`` rather than guessing at a window.
    """
    start = (start_date or "").strip()
    end = (end_date or "").strip()
    if not start and not end:
        return None
    if not start or not end:
        raise InvalidDateWindowError("Both start_date and end_date are required")
    try:
        window = DateWindow(date.fromisoformat(start), date.fromisoformat(end))
    except ValueError as e:
        raise InvalidDateWindowError(f"Dates must be YYYY-MM-DD: {e}") from e
    if window.start > window.end:
        raise InvalidDateWindowError("start_date is after end_date")
    return window


def v5_reference_times(window):
    """v5 ``reference_times`` for ``window``, or ``None`` to leave it out."""
    if window is None:
        return None
    return f"{window.start.isoformat()}:{window.end.isoformat()}"


def v4_covidcast_time_values(window, time_type):
    """v4 covidcast ``time_values`` for ``window``, spelled as exports do.

    Weekly signals take an epiweek range, daily ones a date range; all time is
    ``*``.
    """
    if window is None:
        return "*"
    start, end = window.start.isoformat(), window.end.isoformat()
    if time_type == "week":
        return "-".join(get_epiweek(start, end))
    return f"{start}--{end}"


def v4_epiweeks(window):
    """v4 ``epiweeks`` for ``window``; all time runs from fluview's first week."""
    if window is None:
        now = Week.fromdate(date.today())
        return f"{FLUVIEW_FIRST_EPIWEEK}-{now.year}{now.week:02d}"
    return "-".join(get_epiweek(window.start.isoformat(), window.end.isoformat()))


def get_indicators_based_on_geo_epidata(geos):
    indicators = []
    for geo_type, geo_values in geos.items():
        url = f"{settings.EPIDATA_URL}covidcast/geo_coverage"
        params = {"geo": f"{geo_type}:{','.join(geo_values)}"}
        try:
            response = requests.get(
                url, params=params, auth=epidata_auth(), timeout=(5, 30)
            )
            response.raise_for_status()
            indicators.extend(response.json()["epidata"])
        except requests.RequestException:
            logger.exception("Error getting geo coverage", extra={"geos": geos})
            continue
    return indicators


def get_indicators_based_on_geo_epidata_v5(geos):
    indicators = []
    for geo_type, geo_values in geos.items():
        url = f"{settings.EPIDATA_V5_URL}metadata/geo_signals"
        params = {"geo_type": geo_type}
        for geo_value in geo_values:
            params["geo_value"] = geo_value.lower()
            try:
                response = requests.get(url, params=params, timeout=(5, 30))
                response.raise_for_status()
                indicators.extend(response.json()["values"])
            except requests.RequestException:
                logger.exception("Error getting geo coverage", extra={"geos": geos})
                continue
    return indicators


# v5 geo_types whose main-dropdown level is spelled differently.
V5_GEO_TYPE_LEVELS = {"census_division": "census-region"}


def v5_location_levels(indicators):
    """Main-dropdown levels the covidcast signals served from v5 have.

    v5 cannot list a source's geo values, only its geo_types (in the cached
    metadata), so the Location(s) list offers every unit at those levels and
    the per-location coverage check says which picks have no data.
    """
    metadata = get_v5_metadata()
    levels = set()
    for indicator in indicators:
        v5_source = is_covidcast_indicator(indicator) and get_v5_source(indicator)
        if not v5_source:
            continue
        for geo_type in metadata.get(v5_source, {}).get("geo_types", []):
            levels.add(V5_GEO_TYPE_LEVELS.get(geo_type, geo_type))
    return levels


def _fetch_rows(url, params, auth=None):
    """Return the rows an Epidata endpoint has for ``params``, or ``None`` on error.

    Unlike ``get_epidata_rows``, a failure is ``None`` rather than ``[]``, so
    the caller can tell "no data" apart from "could not check". Handles v4's
    ``{"result", "epidata"}`` envelope (``-2`` is v4's "no results") and v5's
    bare list.
    """
    try:
        response = requests.get(
            url, params={**params, "format": "json"}, auth=auth, timeout=(5, 30)
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        logger.exception("Error checking geo coverage", extra={"url": url})
        return None
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and data.get("result") in (1, 2, -2):
        return data.get("epidata") or []
    logger.error(
        "Unexpected geo coverage response",
        extra={"url": url, "message": data.get("message") if isinstance(data, dict) else None},
    )
    return None


def _signals_with_values(rows):
    """Signals with at least one real value in ``rows``.

    The same null test as ``split_geos_by_v5_values``: an empty string counts
    as null, which is how CSV spells it.
    """
    return {row.get("signal") for row in rows if row.get("value") not in (None, "")}


def _get_v5_signals_with_values(
    v5_source, indicators, geo_type, geo_value, fill_method
):
    """Return the signals of ``indicators`` v5 has a real value for, or ``None``.

    v5's ``metadata/geo_signals`` cannot answer this: it lists a signal for a
    geo whenever rows exist, even when every value is null (nssp for Allegheny
    County). So this reads ``/viz/`` the way exports do, with the same
    ``fill_method``, since v5 may hold rows for one fill_method and not another.
    """
    params = {
        "source": v5_source,
        "signal": ",".join(indicator["indicator"] for indicator in indicators),
        "geo_type": geo_type,
        "geo_value": geo_value,
        "token": settings.EPIDATA_API_KEY,
    }
    if fill_method:
        params["fill_method"] = fill_method
    rows = _fetch_rows(f"{settings.EPIDATA_V5_URL}viz/", params)
    return None if rows is None else _signals_with_values(rows)


def _get_v4_signals_with_values(data_source, time_type, indicators, geo_type, geo_value):
    """Return the signals of ``indicators`` v4 has a real value for, or ``None``.

    Reads the series itself rather than ``covidcast/geo_coverage``, which, like
    v5's ``geo_signals``, reports a signal for a geo whenever rows exist, even
    null-only ones. One v4 request covers one data source and time type, so
    callers group by both.
    """
    rows = _fetch_rows(
        f"{settings.EPIDATA_URL}covidcast/",
        {
            "data_source": data_source,
            "signals": ",".join(indicator["indicator"] for indicator in indicators),
            "time_type": time_type,
            "geo_type": geo_type,
            "geo_values": geo_value,
            "time_values": "*",
        },
        auth=epidata_auth(),
    )
    return None if rows is None else _signals_with_values(rows)


def get_covidcast_geo_coverage(geo, indicators, fill_method=DEFAULT_FILL_METHOD):
    """Report, per covidcast indicator, whether ``geo`` has data and from where.

    Mirrors the routing exports use, so the modal's warning agrees with what a
    submission will actually do: a migrated signal is served from v5 when v5
    has real values for the geo, and from v4 otherwise. "Has data" means at
    least one non-null value on either API -- a signal that exists for the geo
    with only null values is not covered. For a filled ``fill_method`` a
    migrated signal never falls back to v4, which cannot fill, so only v5's
    values count for it; nor does a v5-only source, which v4 does not have.

    ``geo`` is a ``"geo_type:geo_value"`` id. Returns one dict per covidcast
    indicator with its ``data_source`` and ``indicator`` plus ``covered``
    (``True``/``False``, or ``None`` when a lookup failed or the indicator has
    no ``time_type``, so the answer is unknown) and ``route`` (``"v5"``,
    ``"v4"`` or ``None``).
    """
    covidcast_indicators = [
        indicator for indicator in indicators if is_covidcast_indicator(indicator)
    ]

    def key(indicator):
        return indicator["data_source"], indicator["indicator"]

    def api_geo(indicator, on_v5):
        # Both APIs store geo values lowercase; the picker spells states upper.
        # ``None`` for a level the API has no data at (cities, territories,
        # and census divisions on v4): no data, no request.
        pair = to_covidcast_geo(geo, on_v5)
        return (pair[0], pair[1].lower()) if pair else None

    migrated = set()
    on_v5 = set()
    # Indicators whose v5 check failed: v5 may have values even if v4 has none.
    v5_unknown = set()
    for v5_source, source_indicators in group_v5_indicators_by_source(
        covidcast_indicators
    ).items():
        v5_geo = api_geo(source_indicators[0], on_v5=True)
        if v5_geo is None:
            continue
        geo_type, geo_value = v5_geo
        signals = _get_v5_signals_with_values(
            v5_source, source_indicators, geo_type, geo_value, fill_method
        )
        for indicator in source_indicators:
            migrated.add(key(indicator))
            if signals is None:
                v5_unknown.add(key(indicator))
            elif indicator["indicator"] in signals:
                on_v5.add(key(indicator))

    on_v4 = set()
    v4_unknown = set()
    v4_groups = {}
    for indicator in covidcast_indicators:
        if key(indicator) in on_v5:
            continue
        v5_geo = api_geo(indicator, on_v5=True) if key(indicator) in migrated else None
        if v5_geo and not can_fall_back_to_v4(indicator, v5_geo[0], fill_method):
            continue
        if api_geo(indicator, on_v5=False) is None:
            continue
        if not indicator.get("time_type"):
            v4_unknown.add(key(indicator))
            continue
        v4_groups.setdefault(
            (indicator["data_source"], indicator["time_type"]), []
        ).append(indicator)
    for (data_source, time_type), group in v4_groups.items():
        geo_type, geo_value = api_geo(group[0], on_v5=False)
        signals = _get_v4_signals_with_values(
            data_source, time_type, group, geo_type, geo_value
        )
        for indicator in group:
            if signals is None:
                v4_unknown.add(key(indicator))
            elif indicator["indicator"] in signals:
                on_v4.add(key(indicator))

    coverage = []
    for indicator in covidcast_indicators:
        if key(indicator) in on_v5:
            covered, route = True, "v5"
        elif key(indicator) in on_v4:
            covered, route = True, "v4"
        elif key(indicator) in v5_unknown or key(indicator) in v4_unknown:
            covered, route = None, None
        else:
            covered, route = False, None
        coverage.append(
            {
                "data_source": indicator["data_source"],
                "indicator": indicator["indicator"],
                "covered": covered,
                "route": route,
            }
        )
    return coverage


def get_nwss_sewersheds_with_values(
    nwss_source, signals, sewersheds, fill_method=DEFAULT_FILL_METHOD, window=None
):
    """Return ``{signal: {sewershed ids with a real value}}`` for one NWSS source.

    Asks ``/viz/`` the way exports do: every signal in one request, with the
    same ``fill_method`` and dates. A signal with no values anywhere is
    missing from the result. ``None`` when the lookup failed, so the caller
    can tell "no data" apart from "could not check".
    """
    params = {
        "source": "nwss",
        "signal": ",".join(signals),
        "geo_type": "sewershed",
        "geo_value": ",".join(sewersheds),
        "extra_keys": f"nwss_source:{nwss_source}",
        "token": settings.EPIDATA_API_KEY,
    }
    if fill_method:
        params["fill_method"] = fill_method
    reference_times = v5_reference_times(window)
    if reference_times:
        params["reference_times"] = reference_times
    rows = _fetch_rows(f"{settings.EPIDATA_V5_URL}viz/", params)
    if rows is None:
        return None
    with_values = {}
    for row in rows:
        if row.get("value") not in (None, ""):
            with_values.setdefault(row.get("signal"), set()).add(
                str(row.get("geo_value"))
            )
    return with_values


def get_nwss_geo_coverage(
    geo, indicators, nwss_sources, fill_method=DEFAULT_FILL_METHOD, window=None
):
    """Report, per NWSS indicator and selected NWSS source, whether ``geo`` has data.

    NWSS is offered at counties as the sewersheds that serve them, so this
    asks ``/viz/`` for those sewersheds the way exports do: one request per
    source (``extra_keys=nwss_source:<id>``), every selected signal at once,
    with the same ``fill_method`` and dates. Only real values count, so a
    signal a source reports for the county with nothing but nulls is not
    covered. Nothing is selected until a source is, so no source means no
    answer.

    ``geo`` is a ``"geo_type:geo_value"`` id. Returns one dict per (indicator,
    source) with ``data_source``, ``indicator`` and ``nwss_source``, plus
    ``covered`` (``True``/``False``, or ``None`` when the lookup failed) and
    ``not_covered_sewersheds``: the county's sewersheds with no value for it,
    which Plot leaves out (``None`` when unknown).
    """
    nwss_indicators = [
        indicator for indicator in indicators if indicator.get("_endpoint") == "nwss"
    ]
    if not nwss_indicators or not nwss_sources:
        return []
    sewersheds = to_nwss_sewersheds(geo)
    signals = [indicator["indicator"] for indicator in nwss_indicators]
    coverage = []
    for nwss_source in nwss_sources:
        # sewershed ids with a value, per signal; None when unknown.
        with_values = (
            get_nwss_sewersheds_with_values(
                nwss_source, signals, sewersheds, fill_method, window
            )
            if sewersheds
            else {}
        )
        for indicator in nwss_indicators:
            if with_values is None:
                covered, not_covered = None, None
            else:
                found = with_values.get(indicator["indicator"], set())
                covered = bool(found)
                not_covered = [s for s in sewersheds if s not in found]
            coverage.append(
                {
                    "data_source": indicator["data_source"],
                    "indicator": indicator["indicator"],
                    "nwss_source": nwss_source,
                    "covered": covered,
                    "not_covered_sewersheds": not_covered,
                }
            )
    return coverage


def get_list_of_indicators_filtered_by_geo(geos):
    indicators = []
    geos = list_to_dict(ast.literal_eval(geos))
    indicators.extend(get_indicators_based_on_geo_epidata(geos))
    indicators.extend(get_indicators_based_on_geo_epidata_v5(geos))
    return indicators


def get_num_locations_from_meta(indicators):
    timeseries_count = 0
    indicators = set(
        (indicator["source__name"], indicator["name"]) for indicator in indicators
    )

    metadata = safe_cache_get("covidcast_meta")
    if not metadata:
        try:
            response = requests.get(
                f"{settings.EPIDATA_URL}covidcast_meta/", timeout=(5, 30)
            )
            response.raise_for_status()
            data = response.json()
            metadata = data["epidata"]
            safe_cache_set("covidcast_meta", metadata, 60 * 60 * 24)
        except requests.RequestException:
            logger.error("Error fetching covidcast metadata")
            return 0
        except Exception as e:
            logger.error(f"Error fetching covidcast metadata: {e}")
            return 0

    epidata = metadata["epidata"] if isinstance(metadata, dict) else metadata
    for r in epidata:
        if (r["data_source"], r["signal"]) in indicators:
            timeseries_count += r["num_locations"]
    return timeseries_count
