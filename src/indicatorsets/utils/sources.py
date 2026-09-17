"""Registry of Epidata endpoints that share the epiweek query shape.

These endpoints are queried by a list of geo ids plus an epiweek range, and
differ only in their path segment and the name of the geo query parameter.
Adding a new one is a registry entry, not a new function per operation.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EpiweekSource:
    """An Epidata endpoint queried by geo ids plus an epiweek range.

    Attributes:
        key: The ``_endpoint`` value used in indicator records, and the URL path
            segment for the endpoint.
        geo_param: Query-string parameter carrying the geo ids. Epidata is not
            consistent here: some endpoints call it ``regions``, others
            ``locations``. The ``epidatpy``/``epidatr`` client functions use the
            same name, so this drives generated query code too.
        form_key: Key holding this source's selected geos in a submitted form
            payload.
    """

    key: str
    geo_param: str
    form_key: str


EPIWEEK_SOURCES = {
    source.key: source
    for source in (
        EpiweekSource("fluview", "regions", "fluviewLocations"),
        EpiweekSource("nidss_flu", "regions", "nidssFluLocations"),
        EpiweekSource("nidss_dengue", "locations", "nidssDengueLocations"),
        EpiweekSource("flusurv", "locations", "flusurvLocations"),
    )
}
