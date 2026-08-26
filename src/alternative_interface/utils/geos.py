"""Geographic granularity options available for a set of indicators."""

import requests
from django.conf import settings
from delphi_utils import get_structured_logger

from base.models import GeographyUnit
from indicatorsets.utils import group_by_property

logger = get_structured_logger("alternative_interface.utils")


def get_available_geos(indicators):
    if indicators:
        geo_values = []
        grouped_indicators = group_by_property(indicators, "data_source")
        sources = grouped_indicators.keys()
        for data_source, indicators in grouped_indicators.items():
            indicators_str = ",".join(indicator["name"] for indicator in indicators)
            try:
                response = requests.get(
                    f"{settings.EPIDATA_URL}covidcast/geo_indicator_coverage",
                    params={"data_source": data_source, "signals": indicators_str},
                    auth=("epidata", settings.EPIDATA_API_KEY),
                    timeout=(5, 30),
                )
                response.raise_for_status()
            except requests.RequestException:
                logger.exception(
                    "Error getting geo indicator coverage",
                    extra={"data_source": data_source, "signals": indicators_str},
                )
                continue
            data = response.json()
            if len(data["epidata"]):
                geo_values.extend(data["epidata"])
        unique_values = set(geo_values)
        geo_levels = set([el.split(":")[0] for el in unique_values])
        geo_unit_ids = set([geo_value.split(":")[1] for geo_value in unique_values])
        geographic_granularities = [
            {
                "id": f"{geo_unit.geo_level.name}:{geo_unit.geo_id}",
                "geoType": geo_unit.geo_level.name,
                "text": geo_unit.display_name,
                "geoTypeDisplayName": geo_unit.geo_level.display_name,
            }
            for geo_unit in GeographyUnit.objects.filter(geo_level__name__in=geo_levels)
            .filter(geo_id__in=geo_unit_ids)
            .prefetch_related("geo_level")
            .order_by("level")
        ]
        if "fluview" in sources:
            geographic_granularities.extend(
                [
                    {
                        "id": f"{geo_unit.geo_level.name}:{geo_unit.geo_id}",
                        "geoType": geo_unit.geo_level.name,
                        "text": geo_unit.display_name,
                        "geoTypeDisplayName": geo_unit.geo_level.display_name,
                    }
                    for geo_unit in GeographyUnit.objects.filter(
                        geo_level__name__in=[
                            "census-region",
                            "us-territory",
                            "us-city",
                            "ny_minus_jfk",
                        ]
                    )
                    .prefetch_related("geo_level")
                    .order_by("level")
                ]
            )
    else:
        geographic_granularities = [
            {
                "id": f"{geo_unit.geo_level.name}:{geo_unit.geo_id}",
                "geoType": geo_unit.geo_level.name,
                "text": geo_unit.display_name,
                "geoTypeDisplayName": geo_unit.geo_level.display_name,
            }
            for geo_unit in GeographyUnit.objects.all()
            .prefetch_related("geo_level")
            .order_by("level")
        ]
        # Group by geoTypeDisplayName to match the expected format
    grouped_geographic_granularities = group_by_property(
        geographic_granularities, "geoTypeDisplayName"
    )
    geographic_granularities = []
    for key, value in grouped_geographic_granularities.items():
        geographic_granularities.append(
            {
                "text": key,
                "children": value,
            }
        )
    return geographic_granularities
