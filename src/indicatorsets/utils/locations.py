"""Translate the modal's main Location(s) picks for endpoints that share it.

The main dropdown lists geography units as ``"<level>:<geo_id>"``. Covidcast
reads them as they are; fluview takes the same places as region ids, which
outside nation and HHS are just the ``geo_id``.
"""

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
    """Return a copy of a submitted form payload with both shares in place.

    Fluview's own ``fluviewLocations`` key, if a stale page still sends it, is
    replaced by the share derived from the main dropdown. Fluview only gets
    locations when a fluview indicator is selected: the epiweek builders run on
    locations alone, so a covidcast-only pick of, say, a state would otherwise
    add fluview output nobody asked for.
    """
    covidcast_share, fluview_share = split_locations(
        data.get("covidCastGeographicValues")
    )
    if not any(
        indicator.get("_endpoint") == "fluview"
        for indicator in data.get("indicators") or []
    ):
        fluview_share = []
    return {
        **data,
        "covidCastGeographicValues": covidcast_share,
        "fluviewLocations": fluview_share,
    }
