"""Geographic coverage lookups against the Epidata API."""

import ast

import requests
from django.conf import settings
from delphi_utils import get_structured_logger

from indicatorsets.utils.caching import safe_cache_get, safe_cache_set
from indicatorsets.utils.constants import DEFAULT_FILL_METHOD
from indicatorsets.utils.epidata import epidata_auth, group_v5_indicators_by_source
from indicatorsets.utils.helpers import is_filled_fill_method, list_to_dict

logger = get_structured_logger("indicatorsets.utils")


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
    values count for it.

    ``geo`` is a ``"geo_type:geo_value"`` id. Returns one dict per covidcast
    indicator with its ``data_source`` and ``indicator`` plus ``covered``
    (``True``/``False``, or ``None`` when a lookup failed or the indicator has
    no ``time_type``, so the answer is unknown) and ``route`` (``"v5"``,
    ``"v4"`` or ``None``).
    """
    geo_type, geo_value = geo.split(":", 1)
    # Both APIs store geo values lowercase; the picker spells states upper.
    geo_value = geo_value.lower()
    covidcast_indicators = [
        indicator
        for indicator in indicators
        if indicator.get("_endpoint") == "covidcast"
    ]

    def key(indicator):
        return indicator["data_source"], indicator["indicator"]

    migrated = set()
    on_v5 = set()
    # Indicators whose v5 check failed: v5 may have values even if v4 has none.
    v5_unknown = set()
    for v5_source, source_indicators in group_v5_indicators_by_source(
        covidcast_indicators
    ).items():
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
        if key(indicator) in migrated and is_filled_fill_method(fill_method):
            continue
        if not indicator.get("time_type"):
            v4_unknown.add(key(indicator))
            continue
        v4_groups.setdefault(
            (indicator["data_source"], indicator["time_type"]), []
        ).append(indicator)
    for (data_source, time_type), group in v4_groups.items():
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
