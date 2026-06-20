from delphi_utils import get_structured_logger

import requests
from django.conf import settings

logger = get_structured_logger("rest.utils")


def get_available_indicators_for_geo(
    geo_type: str, geo_value: str
) -> set[tuple[str, str]]:

    url = settings.EPIDATA_V5_URL + "metadata/geo_signals/"
    params = {
        "geo_type": geo_type,
        "geo_value": geo_value,
    }

    try:
        response = requests.get(url, params=params, timeout=(5, 30))
        response.raise_for_status()
    except requests.RequestException:
        logger.exception(
            "Error getting available indicators for geo",
            extra={"geo_type": geo_type, "geo_value": geo_value},
        )
        return set()

    values = response.json().get("values", [])
    return {(item["source"], item["signal"]) for item in values}
