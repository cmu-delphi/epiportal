"""Fetching and shaping the preview rows shown for each Epidata endpoint."""

import csv
import io
from itertools import islice

import requests
from django.conf import settings
from delphi_utils import get_structured_logger

from indicatorsets.utils.constants import (
    DEFAULT_FILL_METHOD,
    INVALID_API_KEY_MESSAGE,
    NO_DATA_MESSAGE,
)
from indicatorsets.utils.epidata import (
    epidata_auth,
    get_time_values,
    get_v5_source,
    split_geos_by_v5_values,
    split_v4_v5_indicators,
)
from indicatorsets.utils.exceptions import InvalidApiKeyError
from indicatorsets.utils.helpers import get_epiweek, is_filled_fill_method

logger = get_structured_logger("indicatorsets.utils")


def _keeps_geo(row_geo, geo_values):
    return geo_values is None or str(row_geo).lower() in geo_values


def get_preview_data(
    response, data_format, no_data_message=NO_DATA_MESSAGE, geo_values=None
):
    """Shape the first rows of ``response`` into a preview.

    ``geo_values``, when given, limits the preview to rows for those geos, so a
    v5 response that also carries geos being previewed from v4 instead does
    not show their (null) rows.
    """
    if geo_values is not None:
        geo_values = {geo.lower() for geo in geo_values}
    if data_format == "json":
        data = response.json()
        if isinstance(data, dict) and "epidata" in data:
            rows = [
                row
                for row in data["epidata"] or []
                if _keeps_geo(row.get("geo_value"), geo_values)
            ]
            if rows:
                return {
                    "epidata": rows[0],
                    "result": data["result"],
                    "message": data["message"],
                }
            return {"message": no_data_message}
        if isinstance(data, list):
            rows = [row for row in data if _keeps_geo(row.get("geo_value"), geo_values)]
            return rows[0] if rows else {"message": no_data_message}
        return {"message": no_data_message}
    elif data_format == "csv":
        csv_reader = csv.reader(io.StringIO(response.text), delimiter=",")
        header = next(csv_reader, None)
        if header is None:
            return {"message": no_data_message}
        rows = csv_reader
        if geo_values is not None and "geo_value" in header:
            geo_index = header.index("geo_value")
            rows = (
                row
                for row in csv_reader
                if len(row) > geo_index and _keeps_geo(row[geo_index], geo_values)
            )
        data = [header, *islice(rows, 4)]
        if len(data) <= 1:
            return {"message": no_data_message}
        return data


def get_response_rows(response, data_format):
    """Return every row of an Epidata response as a list of dicts.

    CSV cells come back as strings, so a null value reads as ``""``.
    """
    if data_format == "csv":
        return list(csv.DictReader(io.StringIO(response.text)))
    data = response.json()
    if isinstance(data, dict) and "epidata" in data:
        return data["epidata"] or []
    return data if isinstance(data, list) else []


def _preview_covidcast_v4(
    indicator, start_date, end_date, geo_type, geo_values, api_key, data_format, label
):
    """Fetch a v4 covidcast preview for ``geo_values``, or ``None`` on error."""
    time_values, _ = get_time_values(indicator, start_date, end_date, False)
    # v4 keys signals by data_source and has a time_type dimension
    params = {
        "time_values": time_values,
        "signal": indicator["indicator"],
        "geo_type": geo_type,
        "time_type": indicator["time_type"],
        "data_source": indicator["data_source"],
        "geo_values": geo_values,
        "format": data_format,
        "header": "true" if data_format == "csv" else "false",
    }
    try:
        response = requests.get(
            f"{settings.EPIDATA_URL}covidcast",
            params=params,
            auth=epidata_auth(api_key),
            timeout=(5, 30),
        )
        if response.status_code == 401:
            raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception(
            "Error getting covidcast data",
            extra={"signal": indicator["indicator"], "geo_type": geo_type},
        )
        return None
    return get_preview_data(
        response, data_format, no_data_message=f"No data found for {label}."
    )


def preview_covidcast_data(
    indicators,
    start_date,
    end_date,
    covidcast_geos,
    api_key,
    data_format,
    fill_method=DEFAULT_FILL_METHOD,
):
    """Fetch preview rows per (indicator, geo_type), split across v4 and v5.

    Mirrors ``generate_covidcast_indicators_export_url``: geos v5 has no real
    values for are previewed from v4 instead, for the ``source`` fill_method
    only. The v5 response is already
    fetched in full for the preview, so the check costs no extra request.
    """
    preview_data = []
    for indicator in indicators:
        if indicator["_endpoint"] != "covidcast":
            continue
        v5_source = get_v5_source(indicator)
        for geo_type, values in covidcast_geos.items():
            geo_value_list = [
                (
                    value["id"].split(":")[1].lower()
                    if value["geoType"] in ["nation", "state"]
                    else value["id"].split(":")[1]
                )
                for value in values
            ]
            name = indicator.get("display_name") or indicator["indicator"]
            label = f"{name} ({geo_type})"
            if not v5_source:
                v4_preview = _preview_covidcast_v4(
                    indicator, start_date, end_date, geo_type,
                    ",".join(geo_value_list), api_key, data_format, label,
                )
                if v4_preview is not None:
                    preview_data.append(v4_preview)
                continue

            time_values, _ = get_time_values(indicator, start_date, end_date, True)
            # v5 uses reference_times/token and has no time_type
            params = {
                "source": v5_source,
                "signal": indicator["indicator"],
                "geo_type": geo_type,
                "geo_value": ",".join(geo_value_list),
                "reference_times": time_values,
                "format": data_format,
                "header": "true" if data_format == "csv" else "false",
            }
            if api_key:
                params["token"] = api_key
            if fill_method:
                params["fill_method"] = fill_method
            try:
                response = requests.get(
                    f"{settings.EPIDATA_V5_URL}viz/", params=params, timeout=(5, 30)
                )
                if response.status_code == 401:
                    raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
                response.raise_for_status()
                rows = get_response_rows(response, data_format)
            except requests.RequestException:
                logger.exception(
                    "Error getting covidcast data",
                    extra={"signal": indicator["indicator"], "geo_type": geo_type},
                )
                rows = []
            v5_geos, v4_geos = split_geos_by_v5_values(rows, geo_value_list)
            if v5_geos:
                preview_data.append(
                    get_preview_data(
                        response,
                        data_format,
                        no_data_message=f"No data found for {label}.",
                        geo_values=v5_geos,
                    )
                )
            if not v4_geos:
                continue
            fallback_label = (
                f"{name} ({geo_type}: {', '.join(v4_geos)})" if v5_geos else label
            )
            if is_filled_fill_method(fill_method):
                # v4 has no fill_method, so it can only serve the unfilled
                # series -- not what the user picked.
                preview_data.append({"message": f"No data found for {fallback_label}."})
                continue
            logger.warning(
                "Epidata v5 has no values for these geos, falling back to v4",
                extra={
                    "source": v5_source,
                    "signal": indicator["indicator"],
                    "geo_type": geo_type,
                    "geo_values": v4_geos,
                },
            )
            v4_preview = _preview_covidcast_v4(
                indicator, start_date, end_date, geo_type,
                ",".join(v4_geos), api_key, data_format, fallback_label,
            )
            if v4_preview is not None:
                preview_data.append(v4_preview)
    return preview_data


def preview_v5_epiweek_data(
    source,
    v5_indicators,
    geos,
    start_date,
    end_date,
    api_key,
    data_format,
    fill_method=DEFAULT_FILL_METHOD,
):
    """Fetch preview rows for epiweek signals whose source has migrated to v5.

    One request per (signal, v5 geo_type bucket), the same per-indicator shape
    ``preview_pophive_data``/``preview_nwss_data`` use, keyed by
    ``reference_times``/``token`` (the real v5 param names).

    Epiweek geo ids do not carry an explicit geo_type the way covidcast_geos
    does, and every endpoint spells them differently, so ``source`` supplies
    the bucketing.

    The v5 source is resolved per indicator rather than once for the group:
    one endpoint can cover several data sources mapping to different v5
    sources, and querying one source for another's signal returns the wrong
    data rather than an error.
    """
    preview_data = []
    for indicator in v5_indicators:
        for geo_type, geo_values in source.group_geos_by_v5_type(geos).items():
            params = {
                "source": get_v5_source(indicator),
                "signal": indicator["indicator"],
                "geo_type": geo_type,
                "geo_value": ",".join(geo_values),
                "reference_times": f"{start_date}:{end_date}",
                "format": data_format,
                "header": "true" if data_format == "csv" else "false",
            }
            if api_key:
                params["token"] = api_key
            if fill_method:
                params["fill_method"] = fill_method
            try:
                response = requests.get(
                    f"{settings.EPIDATA_V5_URL}viz/", params=params, timeout=(5, 30)
                )
                if response.status_code == 401:
                    raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
                response.raise_for_status()
            except requests.RequestException:
                logger.exception(
                    "Error getting epiweek v5 data",
                    extra={"signal": indicator["indicator"], "geo_type": geo_type},
                )
                continue
            preview_data.append(get_preview_data(response, data_format))
    return preview_data


def preview_v4_epiweek_data(
    source, data_source, geos, start_date, end_date, api_key, data_format
):
    """Fetch one preview row for an epiweek-based endpoint's v4 signals.

    ``data_source`` is the actual v4 URL segment to call. It is often the same
    as ``source.key``, but not always: one :class:`EpiweekSource` (one geo
    widget, one ``_endpoint``) can cover several data sources that live at
    different v4 endpoints, so the caller passes the indicator's own
    ``data_source`` rather than letting this assume ``source.key``.

    These endpoints return every signal unfiltered, so this always covers the
    full geo list regardless of which indicators are still on v4.
    """
    preview_data = []
    geo_values = ",".join([geo["id"] for geo in geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    params = {
        source.geo_param: geo_values,
        "epiweeks": f"{date_from}-{date_to}",
        "format": data_format,
        "header": "true" if data_format == "csv" else "false",
    }
    try:
        response = requests.get(
            f"{settings.EPIDATA_URL}{data_source}",
            params=params,
            auth=epidata_auth(api_key),
            timeout=(5, 30),
        )
        if response.status_code == 401:
            raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception(
            f"Error getting {data_source} data", extra={"regions": geo_values}
        )
        return preview_data
    preview_data.append(get_preview_data(response, data_format))
    return preview_data


def preview_epiweek_data(
    source,
    geos,
    start_date,
    end_date,
    api_key,
    data_format,
    indicators,
    fill_method=DEFAULT_FILL_METHOD,
):
    """Fetch preview rows for an epiweek-based endpoint, routing per indicator.

    Migrated signals are previewed from v5; anything still on v4 is previewed
    once per distinct v4 ``data_source`` still present, since one endpoint can
    cover several data sources that migrate independently. ``get_v5_source``
    fails closed to v4, so a source that has not migrated is previewed exactly
    as it was before. See ``generate_query_code_epiweek`` for the equivalent
    routing in the query-code generator.

    Args:
        source: The :class:`EpiweekSource` describing the endpoint.
        geos: Selected geos, each a dict with an ``id`` key.
        indicators: All submitted indicators; only ones for this source are used.

    Raises:
        InvalidApiKeyError: If Epidata rejects the API key.
    """
    preview_data = []
    source_indicators = [i for i in indicators if i["_endpoint"] == source.key]
    v5_indicators, v4_indicators, _ = split_v4_v5_indicators(source_indicators)
    if v5_indicators:
        preview_data.extend(
            preview_v5_epiweek_data(
                source,
                v5_indicators,
                geos,
                start_date,
                end_date,
                api_key,
                data_format,
                fill_method,
            )
        )
    if v4_indicators or not v5_indicators:
        v4_data_sources = sorted({i["data_source"] for i in v4_indicators}) or [
            source.key
        ]
        for data_source in v4_data_sources:
            preview_data.extend(
                preview_v4_epiweek_data(
                    source,
                    data_source,
                    geos,
                    start_date,
                    end_date,
                    api_key,
                    data_format,
                )
            )
    return preview_data


def preview_pophive_data(
    indicators,
    start_date,
    end_date,
    pophive_geos,
    pophive_age_group,
    api_key,
    data_format,
    fill_method=DEFAULT_FILL_METHOD,
):
    preview_data = []
    for indicator in indicators:
        if indicator["_endpoint"] == "pophive":
            for geo in pophive_geos:
                params = {
                    "source": "pophive",
                    "signal": indicator["indicator"],
                    "geo_type": geo["geo_type"],
                    "geo_value": geo["id"],
                    "reference_times": f"{start_date}:{end_date}",
                    "extra_keys": f"age_group:{pophive_age_group[0]['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                }
                if api_key:
                    params["token"] = api_key
                if fill_method:
                    params["fill_method"] = fill_method
                try:
                    response = requests.get(
                        f"{settings.EPIDATA_V5_URL}viz/", params=params, timeout=(5, 30)
                    )
                    if response.status_code == 401:
                        raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
                    response.raise_for_status()
                except requests.RequestException:
                    logger.exception(
                        "Error getting pophive data",
                        extra={
                            "signal": indicator["indicator"],
                            "geo_type": geo["geo_type"],
                            "geo_value": geo["id"],
                        },
                    )
                    continue
                label = f"{indicator.get('display_name') or indicator['indicator']} ({geo['text']})"
                preview_data.append(
                    get_preview_data(
                        response,
                        data_format,
                        no_data_message=f"No data found for {label}.",
                    )
                )
    return preview_data


def preview_nwss_data(
    indicators,
    start_date,
    end_date,
    nwss_geographic_value,
    nwss_source,
    fill_method,
    api_key,
    data_format,
):
    preview_data = []
    geo_value = ",".join(nwss_geographic_value)
    for indicator in indicators:
        for source in nwss_source:
            if indicator["_endpoint"] == "nwss":
                params = {
                    "source": "nwss",
                    "signal": indicator["indicator"],
                    "geo_type": "sewershed",
                    "geo_value": geo_value,
                    "reference_times": f"{start_date}:{end_date}",
                    "extra_keys": f"nwss_source:{source['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                }
                if api_key:
                    params["token"] = api_key
                if fill_method:
                    params["fill_method"] = fill_method
                try:
                    response = requests.get(
                        f"{settings.EPIDATA_V5_URL}viz/", params=params, timeout=(5, 30)
                    )
                    if response.status_code == 401:
                        raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
                    response.raise_for_status()
                except requests.RequestException:
                    logger.exception(
                        "Error getting nwss data",
                        extra={
                            "signal": indicator["indicator"],
                            "geo_value": geo_value,
                        },
                    )
                    continue
                label = (
                    f"{indicator.get('display_name') or indicator['indicator']} "
                    f"(source: {source['id']})"
                )
                preview_data.append(
                    get_preview_data(
                        response,
                        data_format,
                        no_data_message=f"No data found for {label}.",
                    )
                )
    return preview_data
