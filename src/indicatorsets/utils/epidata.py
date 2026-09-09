"""Thin helpers for probing the Epidata API."""

import requests
from django.conf import settings
from delphi_utils import get_structured_logger

from indicatorsets.utils.caching import safe_cache_get, safe_cache_set
from indicatorsets.utils.constants import (
    INVALID_API_KEY_MESSAGE,
    MIGRATED_DATASOURCES,
)
from indicatorsets.utils.exceptions import InvalidApiKeyError
from indicatorsets.utils.helpers import get_epiweek

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


V5_METADATA_CACHE_KEY = "epidata_v5_metadata"
# Deliberately shorter than settings.CACHE_TIME: this TTL is how long users keep
# getting v4 URLs after a signal is migrated to v5.
V5_METADATA_CACHE_TIME = 60 * 60


def get_v5_metadata():
    """Return all v5 source metadata keyed by source name, or ``{}`` if unreachable.

    The unfiltered response covers every source in a few kilobytes, so it is
    fetched whole and cached once rather than per source. Failures are not
    cached, so a transient outage does not pin exports to v4 for the full TTL.
    """
    metadata = safe_cache_get(V5_METADATA_CACHE_KEY)
    if metadata is not None:
        return metadata
    try:
        response = requests.get(f"{settings.EPIDATA_V5_URL}metadata/", timeout=(5, 30))
        response.raise_for_status()
        metadata = response.json()
        if not isinstance(metadata, dict):
            raise ValueError("Unexpected Epidata v5 metadata payload")
    except (requests.RequestException, ValueError):
        logger.exception("Error getting Epidata v5 metadata")
        return {}
    safe_cache_set(V5_METADATA_CACHE_KEY, metadata, V5_METADATA_CACHE_TIME)
    return metadata


def get_v5_source(indicator):
    """Return the v5 source name to query ``indicator`` from, or ``None`` for v4.

    ``MIGRATED_DATASOURCES`` is the rollout allowlist and the v4 -> v5 source
    name mapping; the v5 metadata confirms the signal actually exists there.
    Anything unknown falls back to v4. Returning the name rather than a boolean
    keeps callers from reaching for the v4 name when they build v5 requests.
    """
    v5_source = MIGRATED_DATASOURCES.get(indicator["data_source"])
    if not v5_source:
        return None
    signals = get_v5_metadata().get(v5_source, {}).get("signals", [])
    return v5_source if indicator["indicator"] in signals else None


def split_v4_v5_indicators(indicators):
    """Partition ``indicators`` by whether their source has migrated to v5.

    Returns ``(v5_indicators, v4_indicators, v5_source)``, where ``v5_source``
    is the v5 name shared by every v5 indicator (all indicators in a group
    share one data source), or ``None`` if nothing has migrated. Shared by the
    covidcast and epiweek query-code generators.
    """
    v5_indicators = [indicator for indicator in indicators if get_v5_source(indicator)]
    v4_indicators = [
        indicator for indicator in indicators if indicator not in v5_indicators
    ]
    v5_source = get_v5_source(v5_indicators[0]) if v5_indicators else None
    return v5_indicators, v4_indicators, v5_source


def get_time_values(indicator, start_date, end_date, get_from_v5):
    if get_from_v5:
        dates = None
        time_values = f"{start_date}:{end_date}"
    else:
        if indicator["time_type"] == "week":
            dates = get_epiweek(start_date, end_date)
            time_values = f"{dates[0]}-{dates[1]}"
        else:
            dates = [start_date, end_date]
            time_values = f"{start_date}--{end_date}"
    return time_values, dates


def map_fluview_geo_to_v5(geo_id):
    """Map one of fluview's ``regions`` ids to a v5 ``(geo_type, geo_value)`` pair.

    fluview's geo ids bake the geo type into the id itself ("nat" for the
    nation, "hhsN"/"cenN" for HHS regions and census divisions, bare two-letter
    codes for states) instead of carrying it alongside, the way covidcast_geos
    does.
    """
    if geo_id == "nat":
        return "nation", "us"
    if geo_id.startswith("hhs"):
        return "hhs", geo_id[len("hhs") :]
    if geo_id.startswith("cen"):
        return "census_division", geo_id[len("cen") :]
    return "state", geo_id.lower()


def group_fluview_geos_by_v5_type(geos):
    """Bucket fluview's flat geo id list into ``{v5 geo_type: [v5 geo_values]}``."""
    grouped = {}
    for geo in geos:
        geo_type, geo_value = map_fluview_geo_to_v5(geo["id"])
        grouped.setdefault(geo_type, []).append(geo_value)
    return grouped