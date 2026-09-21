"""Fetching and shaping the preview rows shown for each Epidata endpoint."""

import csv
import io
from itertools import islice

import requests
from django.conf import settings
from delphi_utils import get_structured_logger

from indicatorsets.utils.constants import INVALID_API_KEY_MESSAGE, NO_DATA_MESSAGE
from indicatorsets.utils.epidata import (
    get_time_values,
    get_v5_source,
    split_v4_v5_indicators,
)
from indicatorsets.utils.exceptions import InvalidApiKeyError
from indicatorsets.utils.helpers import get_epiweek

logger = get_structured_logger("indicatorsets.utils")


def get_preview_data(response, data_format, no_data_message=NO_DATA_MESSAGE):
    if data_format == "json":
        data = response.json()
        if isinstance(data, dict) and "epidata" in data:
            if data["epidata"]:
                return {
                    "epidata": data["epidata"][0],
                    "result": data["result"],
                    "message": data["message"],
                }
            return {"message": no_data_message}
        if isinstance(data, list):
            return data[0] if data else {"message": no_data_message}
        return {"message": no_data_message}
    elif data_format == "csv":
        csv_file = io.StringIO(response.text)
        csv_reader = csv.reader(csv_file, delimiter=",")
        data = [row for row in islice(csv_reader, 5)]
        if len(data) <= 1:
            return {"message": no_data_message}
        return data


def preview_covidcast_data(
    indicators, start_date, end_date, covidcast_geos, api_key, data_format
):
    preview_data = []
    for indicator in indicators:
        if indicator["_endpoint"] == "covidcast":
            v5_source = get_v5_source(indicator)
            get_from_v5 = v5_source is not None
            time_values, _ = get_time_values(
                indicator, start_date, end_date, get_from_v5
            )
            for geo_type, values in covidcast_geos.items():
                geo_values = ",".join(
                    [
                        (
                            value["id"].split(":")[1].lower()
                            if value["geoType"] in ["nation", "state"]
                            else value["id"].split(":")[1]
                        )
                        for value in values
                    ]
                )
                if get_from_v5:
                    params = {
                        "source": v5_source,
                        "signal": indicator["indicator"],
                        "geo_type": geo_type,
                        "geo_value": geo_values,
                        "reference_times": time_values,
                        "token": api_key if api_key else settings.EPIDATA_API_KEY,
                        "format": data_format,
                        "header": "true" if data_format == "csv" else "false",
                    }
                    epidata_url = f"{settings.EPIDATA_V5_URL}viz/"
                else:
                    # v4 keys signals by data_source and has a time_type dimension
                    params = {
                        "time_values": time_values,
                        "signal": indicator["indicator"],
                        "geo_type": geo_type,
                        "time_type": indicator["time_type"],
                        "data_source": indicator["data_source"],
                        "geo_values": geo_values,
                        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
                        "format": data_format,
                        "header": "true" if data_format == "csv" else "false",
                    }
                    epidata_url = f"{settings.EPIDATA_URL}covidcast"
                try:
                    response = requests.get(
                        epidata_url,
                        params=params,
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
                    continue

                label = f"{indicator.get('display_name') or indicator['indicator']} ({geo_type})"
                preview_data.append(
                    get_preview_data(
                        response,
                        data_format,
                        no_data_message=f"No data found for {label}.",
                    )
                )
    return preview_data


def preview_v5_epiweek_data(
    source, v5_indicators, geos, start_date, end_date, api_key, data_format
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
                "token": api_key if api_key else settings.EPIDATA_API_KEY,
            }
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
        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
        "format": data_format,
        "header": "true" if data_format == "csv" else "false",
    }
    try:
        response = requests.get(
            f"{settings.EPIDATA_URL}{data_source}", params=params, timeout=(5, 30)
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
    source, geos, start_date, end_date, api_key, data_format, indicators
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
                    "token": api_key if api_key else settings.EPIDATA_API_KEY,
                }
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
    nwss_fill_method,
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
                    "fill_method": nwss_fill_method,
                    "reference_times": f"{start_date}:{end_date}",
                    "extra_keys": f"nwss_source:{source['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                    "token": api_key if api_key else settings.EPIDATA_API_KEY,
                }
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
