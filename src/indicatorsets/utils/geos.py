"""Geographic coverage lookups against the Epidata API."""

import ast

import requests
from django.conf import settings
from delphi_utils import get_structured_logger

from indicatorsets.utils.caching import safe_cache_get, safe_cache_set
from indicatorsets.utils.helpers import list_to_dict

logger = get_structured_logger("indicatorsets.utils")


def get_indicators_based_on_geo_epidata(geos):
    indicators = []
    for geo_type, geo_values in geos.items():
        url = f"{settings.EPIDATA_URL}covidcast/geo_coverage"
        params = {
            "geo": f"{geo_type}:{','.join(geo_values)}",
            "api_key": settings.EPIDATA_API_KEY,
        }
        try:
            response = requests.get(url, params=params, timeout=(5, 30))
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
