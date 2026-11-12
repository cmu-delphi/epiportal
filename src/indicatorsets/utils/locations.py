"""Translate the modal's main Location(s) picks for endpoints that share it.

The main dropdown lists geography units as ``"<level>:<geo_id>"``. Covidcast
reads them as they are; fluview takes the same places as region ids, which
outside nation and HHS are just the ``geo_id``; pophive (Cosmos) takes
``(geo_type, geo_id)`` pairs at the nation, HHS and state levels; NWSS takes
the sewersheds of the picked counties; FluSurv takes its networks, its states
and its two New York sites; NIDSS takes the Taiwan places.
"""

from indicatorsets.utils.epidata import get_v5_source, is_covidcast_indicator
from indicatorsets.utils.nwss import nwss_county_sewersheds

# Levels whose units fluview has a region for.
FLUVIEW_LOCATION_LEVELS = frozenset(
    {
        "nation",
        "hhs",
        "state",
        "census-region",
        "us-city",
        "us-territory",
        "ny_minus_jfk",
    }
)
# Of those, the levels covidcast has no data for.
FLUVIEW_ONLY_LEVELS = frozenset(
    {"census-region", "us-city", "us-territory", "ny_minus_jfk"}
)


# FluSurv-NET's networks, and the Taiwan places NIDSS reports on: flu for
# the national and regional ones, dengue for the counties and cities too.
FLUSURV_NETWORK_LEVEL = "FluSurv-Net site"
TAIWAN_REGION_LEVEL = "taiwan-region"
TAIWAN_COUNTY_LEVEL = "taiwan-county"

# Levels only some other endpoint has, never covidcast.
NON_COVIDCAST_LEVELS = FLUVIEW_ONLY_LEVELS | {
    FLUSURV_NETWORK_LEVEL,
    TAIWAN_REGION_LEVEL,
    TAIWAN_COUNTY_LEVEL,
}

# The states FluSurv-NET has catchment areas in, and its two New York sites,
# which the main dropdown has as their MSAs.
FLUSURV_STATES = frozenset(
    {
        "CA", "CO", "CT", "GA", "IA", "ID", "MD", "MI", "MN",
        "NM", "OH", "OK", "OR", "RI", "SD", "TN", "UT",
    }
)
FLUSURV_MSAS = {"10580": "NY_albany", "40380": "NY_rochester"}


# Fluview-only levels that covidcast-shaped sources have on v5. Our
# "census-region" units (cen1..cen9) are the nine census divisions, which v5
# calls census_division 1..9.
V5_COVIDCAST_EXTRA_LEVELS = frozenset({"census-region"})


# Levels pophive has data for, and the "states" among them it has none for.
POPHIVE_LOCATION_LEVELS = frozenset({"nation", "hhs", "state"})
POPHIVE_STATES_WITHOUT_DATA = frozenset({"as", "gu", "mp", "pr", "vi"})


def to_fluview_region(location_id):
    """Return fluview's region id for a main-dropdown location, or ``None``.

    ``nation:US`` -> ``nat``, ``hhs:3`` -> ``hhs3``; any other fluview level
    is its ``geo_id`` (``state:PA`` -> ``PA``, ``us-city:jfk`` -> ``jfk``).
    """
    if not location_id or ":" not in location_id:
        return None
    level, geo_id = location_id.split(":", 1)
    if level not in FLUVIEW_LOCATION_LEVELS or not geo_id:
        return None
    if level == "nation":
        return "nat"
    if level == "hhs":
        return f"hhs{geo_id}"
    return geo_id


def _split_location(location_id):
    """``"level:geo_id"`` -> ``(level, geo_id)``, or ``None`` when malformed."""
    if not location_id or ":" not in location_id:
        return None
    level, geo_id = location_id.split(":", 1)
    return (level, geo_id) if geo_id else None


def to_flusurv_location(location_id):
    """Return FluSurv's location id for a main-dropdown location, or ``None``.

    ``FluSurv-Net site:network_eip`` -> ``network_eip``, ``state:CA`` ->
    ``CA`` (only for states FluSurv-NET covers), ``msa:10580`` ->
    ``NY_albany``.
    """
    parts = _split_location(location_id)
    if parts is None:
        return None
    level, geo_id = parts
    if level == FLUSURV_NETWORK_LEVEL:
        return geo_id
    if level == "state" and geo_id.upper() in FLUSURV_STATES:
        return geo_id.upper()
    if level == "msa":
        return FLUSURV_MSAS.get(geo_id)
    return None


def _to_nidss_location(location_id, levels):
    parts = _split_location(location_id)
    if parts is None or parts[0] not in levels:
        return None
    return parts[1]


def to_nidss_flu_location(location_id):
    """Return NIDSS flu's region id for a main-dropdown location, or ``None``.

    Taiwan's national and regional places only: ``taiwan-region:central``
    -> ``central``.
    """
    return _to_nidss_location(location_id, {TAIWAN_REGION_LEVEL})


def to_nidss_dengue_location(location_id):
    """Return NIDSS dengue's location id for a main-dropdown location, or
    ``None``: the Taiwan regions and also its counties and cities."""
    return _to_nidss_location(location_id, {TAIWAN_REGION_LEVEL, TAIWAN_COUNTY_LEVEL})


# Epiweek endpoints besides fluview that take main-dropdown picks: the form
# payload key each one reads its locations from, and how to translate a pick.
EPIWEEK_MAIN_LOCATIONS = {
    "flusurv": ("flusurvLocations", to_flusurv_location),
    "nidss_flu": ("nidssFluLocations", to_nidss_flu_location),
    "nidss_dengue": ("nidssDengueLocations", to_nidss_dengue_location),
}


def epiweek_locations(covidcast_geos, translate):
    """One endpoint's share of the main dropdown's payload.

    ``[{"id": <its location id>, "text", "location_id": <main id>}]``, one
    entry per location even when it was picked under two spellings.
    """
    if not isinstance(covidcast_geos, dict):
        return []
    share = []
    seen = set()
    for geos in covidcast_geos.values():
        for geo in geos:
            location = translate(geo.get("id"))
            if location is None or location.lower() in seen:
                continue
            seen.add(location.lower())
            share.append({"id": location, "text": geo.get("text"), "location_id": geo["id"]})
    return share


def to_covidcast_geo(location_id, on_v5=False):
    """Return the ``(geo_type, geo_value)`` to query for a main-dropdown location,
    or ``None`` when a covidcast-shaped source has no such level.

    ``state:PA`` -> ``("state", "pa")``; other levels keep their ``geo_id``.
    Census divisions exist only for signals served from v5 (``on_v5``):
    ``census-region:cen3`` -> ``("census_division", "3")``.
    """
    if not location_id or ":" not in location_id:
        return None
    level, geo_id = location_id.split(":", 1)
    if not geo_id:
        return None
    if level == "census-region":
        if on_v5 and geo_id.lower().startswith("cen"):
            return "census_division", geo_id[len("cen") :]
        return None
    if level in NON_COVIDCAST_LEVELS:
        return None
    return level, geo_id.lower() if level in ("nation", "state") else geo_id


def group_covidcast_geos(covidcast_geos, on_v5=False):
    """Bucket the covidcast share into ``{geo_type: [geo_value]}`` to query.

    Levels the source does not have are dropped (see ``to_covidcast_geo``).
    """
    grouped = {}
    for geos in (covidcast_geos or {}).values():
        for geo in geos:
            pair = to_covidcast_geo(geo.get("id"), on_v5)
            if pair:
                grouped.setdefault(pair[0], []).append(pair[1])
    return grouped


def to_pophive_location(location_id):
    """Return pophive's ``{"geo_type", "id"}`` for a main-dropdown location, or ``None``.

    ``nation:US`` -> nation ``us``, ``hhs:3`` -> hhs ``3``, ``state:PA`` ->
    state ``pa``. Other levels, and the territories filed under ``state``,
    have no pophive data.
    """
    if not location_id or ":" not in location_id:
        return None
    level, geo_id = location_id.split(":", 1)
    geo_id = geo_id.lower()
    if level not in POPHIVE_LOCATION_LEVELS or not geo_id:
        return None
    if level == "state" and geo_id in POPHIVE_STATES_WITHOUT_DATA:
        return None
    return {"geo_type": level, "id": geo_id}


def pophive_locations(covidcast_geos):
    """Pophive's share of the main dropdown's payload.

    ``[{"id", "geo_type", "text", "location_id": <main id>}]``, one entry per
    place even when it was picked under two spellings.
    """
    if not isinstance(covidcast_geos, dict):
        return []
    locations = []
    seen = set()
    for geos in covidcast_geos.values():
        for geo in geos:
            location = to_pophive_location(geo.get("id"))
            if location is None:
                continue
            key = (location["geo_type"], location["id"])
            if key in seen:
                continue
            seen.add(key)
            locations.append(
                {**location, "text": geo.get("text"), "location_id": geo["id"]}
            )
    return locations


def to_nwss_sewersheds(location_id):
    """Return the NWSS sewershed ids of a main-dropdown county, or ``[]``.

    ``county:42003`` -> Allegheny's sewersheds. NWSS has data per sewershed
    only, and only counties are offered: a state would mean hundreds of series.
    """
    if not location_id or ":" not in location_id:
        return []
    level, geo_id = location_id.split(":", 1)
    if level != "county":
        return []
    return list(nwss_county_sewersheds().get(geo_id, []))


def nwss_counties():
    """The FIPS codes of the counties some NWSS sewershed serves."""
    return list(nwss_county_sewersheds())


def nwss_locations(covidcast_geos):
    """NWSS's share of the main dropdown's payload: sewershed ids, each once.

    A sewershed that serves two picked counties is listed once.
    """
    if not isinstance(covidcast_geos, dict):
        return []
    sewersheds = []
    for geos in covidcast_geos.values():
        for geo in geos:
            for sewershed in to_nwss_sewersheds(geo.get("id")):
                if sewershed not in sewersheds:
                    sewersheds.append(sewershed)
    return sewersheds


def split_locations(covidcast_geos):
    """Split the main dropdown's payload into ``(covidcast share, fluview share)``.

    ``covidcast_geos`` is ``{level: [{"id", "text", "geoType"}]}`` (Plot sends
    ``[]`` and some callers ``None`` when nothing is picked). The covidcast
    share drops levels covidcast has no data for; the fluview share is
    ``[{"id": <region>, "text", "location_id": <main id>}]``, one entry per
    region even when a place was picked at two levels.
    """
    if not isinstance(covidcast_geos, dict):
        return {}, []
    covidcast_share = {
        level: geos
        for level, geos in covidcast_geos.items()
        if level not in NON_COVIDCAST_LEVELS
    }
    fluview_share = []
    seen_regions = set()
    for geos in covidcast_geos.values():
        for geo in geos:
            region = to_fluview_region(geo.get("id"))
            if region is None or region.lower() in seen_regions:
                continue
            seen_regions.add(region.lower())
            fluview_share.append(
                {"id": region, "text": geo.get("text"), "location_id": geo["id"]}
            )
    return covidcast_share, fluview_share


def use_main_locations(data):
    """Return a copy of a submitted form payload with every share in place.

    The ``fluviewLocations``, ``pophiveLocations``, ``nwssGeographicValue``
    and ``EPIWEEK_MAIN_LOCATIONS`` keys a stale page may still send are
    replaced by shares derived from the main dropdown. Each endpoint only gets locations when one of its
    indicators is selected: their builders run on locations alone, so a
    covidcast-only pick of, say, a state would otherwise add output nobody
    asked for. That also keeps the NWSS crosswalk from being fetched for
    nothing.
    """
    covidcast_share, fluview_share = split_locations(
        data.get("covidCastGeographicValues")
    )
    endpoints = {
        indicator.get("_endpoint") for indicator in data.get("indicators") or []
    }
    if isinstance(data.get("covidCastGeographicValues"), dict) and any(
        is_covidcast_indicator(indicator) and get_v5_source(indicator)
        for indicator in data.get("indicators") or []
    ):
        # Signals served from v5 have census divisions; the covidcast paths
        # drop them again for every v4 one.
        for level in V5_COVIDCAST_EXTRA_LEVELS:
            geos = data["covidCastGeographicValues"].get(level)
            if geos:
                covidcast_share[level] = geos
    if "fluview" not in endpoints:
        fluview_share = []
    pophive_share = (
        pophive_locations(data.get("covidCastGeographicValues"))
        if "pophive" in endpoints
        else []
    )
    nwss_share = (
        nwss_locations(data.get("covidCastGeographicValues"))
        if "nwss" in endpoints
        else []
    )
    epiweek_shares = {
        form_key: (
            epiweek_locations(data.get("covidCastGeographicValues"), translate)
            if endpoint in endpoints
            else []
        )
        for endpoint, (form_key, translate) in EPIWEEK_MAIN_LOCATIONS.items()
    }
    return {
        **data,
        **epiweek_shares,
        "covidCastGeographicValues": covidcast_share,
        "fluviewLocations": fluview_share,
        "pophiveLocations": pophive_share,
        "nwssGeographicValue": nwss_share,
    }
