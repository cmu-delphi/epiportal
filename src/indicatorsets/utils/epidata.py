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
    is the v5 name taken from the first v5 indicator, or ``None`` if nothing
    has migrated.

    ``v5_source`` is only meaningful when every indicator passed in shares one
    ``data_source``. That holds for callers that group by ``data_source``
    before calling this (covidcast), but not for callers that group by
    ``_endpoint``, since one endpoint can serve several data sources that map
    to different v5 sources. Those callers must use
    ``group_v5_indicators_by_source`` instead of this single ``v5_source``.
    """
    v5_indicators = [indicator for indicator in indicators if get_v5_source(indicator)]
    v4_indicators = [
        indicator for indicator in indicators if indicator not in v5_indicators
    ]
    v5_source = get_v5_source(v5_indicators[0]) if v5_indicators else None
    return v5_indicators, v4_indicators, v5_source


def group_v5_indicators_by_source(indicators):
    """Bucket migrated indicators into ``{v5 source name: [indicators]}``.

    One endpoint can serve several data sources, and those can map to
    different v5 sources. Asking one v5 source for another's signals returns
    the wrong data rather than an error, so every v5 request has to be built
    per v5 source rather than per endpoint.
    """
    grouped = {}
    for indicator in indicators:
        v5_source = get_v5_source(indicator)
        if v5_source:
            grouped.setdefault(v5_source, []).append(indicator)
    return grouped


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


# v4 keys ILINet's two New York City series on JFK airport; v5 keys them on
# the city. Verified as pure renames against the dev v5 API -- v4 jfk and v5
# nyc report identical values for the same week, likewise ny_minus_jfk and
# ny_minus_nyc.
FLUVIEW_V5_GEO_RENAMES = {
    "jfk": "nyc",
    "ny_minus_jfk": "ny_minus_nyc",
}


def map_fluview_geo_to_v5(geo_id):
    """Map one of fluview's ``regions`` ids to a v5 ``(geo_type, geo_value)`` pair.

    fluview's geo ids bake the geo type into the id itself ("nat" for the
    nation, "hhsN"/"cenN" for HHS regions and census divisions, bare two-letter
    codes for states) instead of carrying it alongside, the way covidcast_geos
    does.

    A handful of ids in the picker (``ord``, ``lax``, ``as``, ``mp``, ``gu``)
    have no data on either API, so they fall through to a ``state`` pair that
    returns nothing -- the same empty result they already give on v4, not a
    regression.
    """
    if geo_id == "nat":
        return "nation", "us"
    if geo_id.startswith("hhs"):
        return "hhs", geo_id[len("hhs") :]
    if geo_id.startswith("cen"):
        return "census_division", geo_id[len("cen") :]
    geo_value = geo_id.lower()
    return "state", FLUVIEW_V5_GEO_RENAMES.get(geo_value, geo_value)


def map_flusurv_geo_to_v5(geo_id):
    """Map one of flusurv's ``locations`` ids to a v5 ``(geo_type, geo_value)`` pair.

    v5 splits flusurv's flat picker list across two geo_types. The
    FluSurv-Net sites -- the three networks and the two New York catchment
    areas -- become ``flusurv_site``; the participating states stay
    ``state``. Site ids are the only ones carrying an underscore, which is
    what separates ``NY_albany`` (a site) from ``NY`` (a state, were it ever
    offered). The ids are otherwise unchanged from v4, just lowercased.
    """
    geo_value = geo_id.lower()
    if "_" in geo_value:
        return "flusurv_site", geo_value
    return "state", geo_value


def group_geos_by_v5_type(geos, mapper):
    """Bucket a flat epiweek geo id list into ``{v5 geo_type: [v5 geo_values]}``.

    ``mapper`` is the endpoint's own id -> ``(geo_type, geo_value)`` function;
    every epiweek endpoint spells its geo ids differently, so the mapping
    cannot be shared. Callers reach this through
    :meth:`EpiweekSource.group_geos_by_v5_type` rather than naming a mapper.
    """
    grouped = {}
    for geo in geos:
        geo_type, geo_value = mapper(geo["id"])
        grouped.setdefault(geo_type, []).append(geo_value)
    return grouped