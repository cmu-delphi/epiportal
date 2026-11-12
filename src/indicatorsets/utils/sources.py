"""Registry of Epidata endpoints that share the epiweek query shape.

These endpoints are queried by a list of geo ids plus an epiweek range, and
differ only in their path segment and the name of the geo query parameter.
Adding a new one is a registry entry, not a new function per operation.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from indicatorsets.utils.epidata import (
    group_geos_by_v5_type,
    map_fluview_geo_to_v5,
    map_flusurv_geo_to_v5,
)
from indicatorsets.utils.helpers import is_filled_fill_method


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
        v5_geo_mapper: Maps one of this endpoint's geo ids to the v5
            ``(geo_type, geo_value)`` pair naming the same place, or ``None``
            for an endpoint that has not migrated. Epiweek geo ids bake the
            geo type into the id itself, and every endpoint spells that
            differently, so the mapping lives with the source rather than
            being shared.
        falls_back_to_v4: Whether a location v5 has no values for, for some
            selected migrated signal, is served from v4 instead, as covidcast
            does per geo. Only where v4 still has what v5 lacks (fluview: v5
            has no state-level wILI).
    """

    key: str
    geo_param: str
    form_key: str
    v5_geo_mapper: Optional[Callable[[str], tuple[str, str]]] = None
    falls_back_to_v4: bool = False

    def can_fall_back_to_v4(self, fill_method):
        """Whether to use the v4 fallback for ``fill_method``.

        v4 cannot fill, so a filled series stays on v5 even where it is empty.
        """
        return self.falls_back_to_v4 and not is_filled_fill_method(fill_method)

    def pair_geos_by_v5_type(self, geos):
        """Like :meth:`group_geos_by_v5_type`, but each v5 geo_value comes
        with the geo it was mapped from, so a v4 fallback can use its v4 id."""
        if self.v5_geo_mapper is None:
            return {}
        grouped = {}
        for geo in geos:
            geo_type, geo_value = self.v5_geo_mapper(geo["id"])
            grouped.setdefault(geo_type, []).append((geo_value, geo))
        return grouped

    def group_geos_by_v5_type(self, geos):
        """Bucket ``geos`` into ``{v5 geo_type: [v5 geo_values]}`` for this endpoint.

        An endpoint with no mapper has not migrated, so no v5 request can be
        built for it and no bucket is offered.
        """
        if self.v5_geo_mapper is None:
            return {}
        return group_geos_by_v5_type(geos, self.v5_geo_mapper)


EPIWEEK_SOURCES = {
    source.key: source
    for source in (
        EpiweekSource(
            "fluview",
            "regions",
            "fluviewLocations",
            map_fluview_geo_to_v5,
            falls_back_to_v4=True,
        ),
        EpiweekSource("nidss_flu", "regions", "nidssFluLocations"),
        EpiweekSource("nidss_dengue", "locations", "nidssDengueLocations"),
        EpiweekSource(
            "flusurv", "locations", "flusurvLocations", map_flusurv_geo_to_v5
        ),
    )
}
