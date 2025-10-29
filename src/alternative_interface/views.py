from django.shortcuts import render
from indicators.models import Indicator
from base.models import Pathogen, GeographyUnit

from indicatorsets.utils import group_by_property
import requests
from django.conf import settings

HEADER_DESCRIPTION = "Discover, display and download real-time infectious disease indicators (time series) that track a variety of pathogens, diseases and syndromes in a variety of locations (primarily within the USA). Browse the list, or filter it first by locations and pathogens of interest, by surveillance categories, and more. Expand any row to expose and select from a set of related indicators, then hit 'Show Selected Indicators' at bottom to plot or export your selected indicators, or to generate code snippets to retrieve them from the Delphi Epidata API. Most indicators are served from the Delphi Epidata real-time repository, but some may be available only from third parties or may require prior approval."


def get_available_geos(indicators):
    geo_values = []
    grouped_indicators = group_by_property(indicators, "data_source")
    for data_source, indicators in grouped_indicators.items():
        indicators_str = ",".join(indicator["name"] for indicator in indicators)
        response = requests.get(
            f"{settings.EPIDATA_URL}covidcast/geo_indicator_coverage",
            params={"data_source": data_source, "signals": indicators_str},
            auth=("epidata", settings.EPIDATA_API_KEY),
        )
        if response.status_code == 200:
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


def alternative_interface_view(request):
    try:
        ctx = {}
        ctx["header_description"] = HEADER_DESCRIPTION

        # Fetch pathogens for dropdown
        ctx["pathogens"] = list(
            Pathogen.objects.filter(used_in="indicators").order_by(
                "display_order_number"
            )
        )

        # Get filters from URL parameters
        pathogen_filter = request.GET.get("pathogen", "")
        ctx["selected_pathogen"] = pathogen_filter

        # Build queryset with optional filtering
        indicators_qs = Indicator.objects.prefetch_related(
            "pathogens", "available_geographies", "indicator_set"
        ).all()

        if pathogen_filter:
            indicators_qs = indicators_qs.filter(pathogens__id=pathogen_filter)

        # Convert to list of dictionaries
        ctx["indicators"] = [
            {
                "_endpoint": indicator.indicator_set.epidata_endpoint,
                "name": indicator.name,
                "data_source": indicator.source.name if indicator.source else "Unknown",
            }
            for indicator in indicators_qs
        ]

        ctx["available_geos"] = get_available_geos(ctx["indicators"])

        print(ctx["available_geos"])

        return render(
            request, "alternative_interface/alter_dashboard.html", context=ctx
        )
    except Exception as e:
        from django.http import HttpResponse

        return HttpResponse(f"Error loading page: {str(e)}")
