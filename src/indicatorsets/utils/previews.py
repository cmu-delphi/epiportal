"""Fetching and shaping the preview rows shown for each Epidata endpoint."""

import csv
import io
from itertools import islice

import requests
from django.conf import settings
from delphi_utils import get_structured_logger

from indicatorsets.utils.constants import INVALID_API_KEY_MESSAGE, NO_DATA_MESSAGE
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
            time_values = f"{start_date}--{end_date}"
            if indicator["time_type"] == "week":
                start_day, end_day = get_epiweek(start_date, end_date)
                time_values = f"{start_day}-{end_day}"
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
                params = {
                    "time_type": indicator["time_type"],
                    "time_values": time_values,
                    "data_source": indicator["data_source"],
                    "signal": indicator["indicator"],
                    "geo_type": geo_type,
                    "geo_values": geo_values,
                    "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                }
                try:
                    response = requests.get(
                        f"{settings.EPIDATA_URL}covidcast",
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


def preview_epiweek_data(source, geos, start_date, end_date, api_key, data_format):
    """Fetch preview rows for an epiweek-based endpoint.

    Args:
        source: The :class:`EpiweekSource` describing the endpoint.
        geos: Selected geos, each a dict with an ``id`` key.

    Raises:
        InvalidApiKeyError: If Epidata rejects the API key.
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
            f"{settings.EPIDATA_URL}{source.key}", params=params, timeout=(5, 30)
        )
        if response.status_code == 401:
            raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception(
            f"Error getting {source.key} data", extra={"regions": geo_values}
        )
        return preview_data
    preview_data.append(get_preview_data(response, data_format))
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
                    "time_values": f"{start_date}:{end_date}",
                    "extra_keys": f"age_group:{pophive_age_group[0]['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                    "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
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
                    "time_values": f"{start_date}:{end_date}",
                    "extra_keys": f"nwss_source:{source['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                    "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
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
