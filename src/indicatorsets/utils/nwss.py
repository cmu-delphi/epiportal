"""Which NWSS sewersheds serve each county.

v5 has NWSS data per sewershed only, and the modal lets people pick counties,
so this crosswalk turns one into the other.
"""

import csv
import io

import requests
from delphi_utils import get_structured_logger
from django.conf import settings

from indicatorsets.utils.caching import safe_cache_get, safe_cache_set

logger = get_structured_logger("indicatorsets.utils")

NWSS_CROSSWALK_CACHE_KEY = "nwss_county_sewersheds"
NWSS_CROSSWALK_CACHE_TIME = 60 * 60 * 24


def nwss_county_sewersheds():
    """Return ``{county fips: [sewershed ids]}``, or ``{}`` when v5 can't be reached.

    Rows without a county name carry placeholder ids (``00005``, ...) that
    match no county, so they are skipped. A failed fetch is not cached.
    """
    crosswalk = safe_cache_get(NWSS_CROSSWALK_CACHE_KEY)
    if crosswalk:
        return crosswalk
    try:
        response = requests.get(
            f"{settings.EPIDATA_V5_URL}geomap/nwss_sewershed_crosswalk",
            params={"other_geo_type": "county"},
            timeout=(5, 30),
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Error getting the nwss county crosswalk")
        return {}
    crosswalk = {}
    for row in csv.DictReader(io.StringIO(response.text)):
        if not (row.get("to_name") or "").strip():
            continue
        crosswalk.setdefault(row["to_val"], []).append(str(row["from_val"]))
    if crosswalk:
        safe_cache_set(NWSS_CROSSWALK_CACHE_KEY, crosswalk, NWSS_CROSSWALK_CACHE_TIME)
    return crosswalk
