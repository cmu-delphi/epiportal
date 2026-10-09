"""Translate the modal's main Location(s) picks for endpoints that share it.

The main dropdown lists geography units as ``"<level>:<geo_id>"``. Covidcast
reads them as they are; fluview takes the same places as region ids, which
outside nation and HHS are just the ``geo_id``; pophive (Cosmos) takes
``(geo_type, geo_id)`` pairs at the nation, HHS and state levels; NWSS takes
the sewersheds of the picked counties.
"""

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
        if level not in FLUVIEW_ONLY_LEVELS
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

    The ``fluviewLocations``, ``pophiveLocations`` and ``nwssGeographicValue``
    keys a stale page may still send are replaced by shares derived from the
    main dropdown. Each endpoint only gets locations when one of its
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
    return {
        **data,
        "covidCastGeographicValues": covidcast_share,
        "fluviewLocations": fluview_share,
        "pophiveLocations": pophive_share,
        "nwssGeographicValue": nwss_share,
    }
