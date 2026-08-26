"""Thin helpers for probing the Epidata API."""

import requests
from delphi_utils import get_structured_logger

from indicatorsets.utils.constants import INVALID_API_KEY_MESSAGE
from indicatorsets.utils.exceptions import InvalidApiKeyError

logger = get_structured_logger("indicatorsets.utils")


def has_epidata_results(url, params):
    """Check whether an Epidata endpoint has any results for the given params."""
    check_params = {**params, "format": "json"}
    try:
        response = requests.get(url, params=check_params, timeout=(5, 30))
        if response.status_code == 401:
            raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Error checking data availability", extra={"url": url})
        return False
    data = response.json()
    if isinstance(data, dict) and "epidata" in data:
        return bool(data["epidata"])
    if isinstance(data, list):
        return bool(data)
    return False
