"""Fetching indicator time series from Epidata for the express view."""

import requests
from django.conf import settings
from delphi_utils import get_structured_logger

from alternative_interface.helper import COVIDCAST_FLUVIEW_LOCATIONS_MAPPING
from indicatorsets.utils import get_epiweek

logger = get_structured_logger("alternative_interface.utils")


def get_covidcast_data(indicator, start_date, end_date, geo, api_key):
    time_values = f"{start_date}--{end_date}"
    if indicator["time_type"] == "week":
        start_day, end_day = get_epiweek(start_date, end_date)
        time_values = f"{start_day}-{end_day}"
    geo_type, geo_value = geo.split(":")
    params = {
        "time_type": indicator["time_type"],
        "time_values": time_values,
        "data_source": indicator["data_source"],
        "signal": indicator["name"],
        "geo_type": geo_type,
        "geo_values": geo_value.lower(),
        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
    }
    try:
        response = requests.get(
            f"{settings.EPIDATA_URL}covidcast", params=params, timeout=(5, 30)
        )
        response.raise_for_status()
        response_data = response.json()
        if len(response_data["epidata"]):
            return response_data["epidata"]
    except requests.RequestException:
        logger.exception(
            "Error getting covidcast data",
            extra={"signal": indicator["name"], "geo": geo},
        )
    return []


def get_fluview_data(indicator, geo, start_date, end_date, api_key):
    region = None
    try:
        region = COVIDCAST_FLUVIEW_LOCATIONS_MAPPING[geo]
    except KeyError:
        region = geo.split(":")[1]
    time_values = f"{start_date}--{end_date}"
    if indicator["time_type"] == "week":
        start_day, end_day = get_epiweek(start_date, end_date)
        time_values = f"{start_day}-{end_day}"
    params = {
        "regions": region,
        "epiweeks": time_values,
        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
    }
    try:
        response = requests.get(
            f"{settings.EPIDATA_URL}{indicator['data_source']}",
            params=params,
            timeout=(5, 30),
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception(
            "Error getting fluview data",
            extra={"signal": indicator["name"], "geo": geo},
        )
        return []
    data = response.json()
    if len(data["epidata"]):
        return [
            {
                "time_value": el["epiweek"],
                "value": el[indicator["name"]],
                "signal": indicator["name"],
                "time_type": indicator["time_type"],
            }
            for el in data["epidata"]
        ]
    return []
