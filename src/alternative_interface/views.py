from django.shortcuts import render
from indicators.models import Indicator
from base.models import Pathogen
from epiportal.settings import ALTERNATIVE_INTERFACE_VERSION

from alternative_interface.utils import get_available_geos, get_chart_data


HEADER_DESCRIPTION = "Discover, display and download real-time infectious disease indicators (time series) that track a variety of pathogens, diseases and syndromes in a variety of locations (primarily within the USA). Browse the list, or filter it first by locations and pathogens of interest, by surveillance categories, and more. Expand any row to expose and select from a set of related indicators, then hit 'Show Selected Indicators' at bottom to plot or export your selected indicators, or to generate code snippets to retrieve them from the Delphi Epidata API. Most indicators are served from the Delphi Epidata real-time repository, but some may be available only from third parties or may require prior approval."


def alternative_interface_view(request):
    try:
        ctx = {}
        ctx["header_description"] = HEADER_DESCRIPTION
        ctx["alternative_interface_version"] = ALTERNATIVE_INTERFACE_VERSION
        # Get filters from URL parameters
        pathogen_filter = request.GET.get("pathogen", "")
        geography_filter = request.GET.get("geography", "")
        ctx["selected_pathogen"] = pathogen_filter
        ctx["selected_geography"] = geography_filter

        # Build queryset with optional filtering
        indicators_qs = Indicator.objects.filter(
            use_in_express_interface=True
        ).prefetch_related("pathogens", "available_geographies", "indicator_set")

        # Fetch pathogens for dropdown
        pathogens_qs = Pathogen.objects.filter(
            id__in=indicators_qs.values_list("pathogens", flat=True)
        ).order_by("display_order_number")
        ctx["pathogens"] = list[Pathogen](pathogens_qs)

        if pathogen_filter:
            indicators_qs = indicators_qs.filter(
                pathogens__id=pathogen_filter,
            )

        # Convert to list of dictionaries
        ctx["indicators"] = [
            {
                "_endpoint": (
                    indicator.indicator_set.epidata_endpoint
                    if indicator.indicator_set
                    else ""
                ),
                "name": indicator.name,
                "data_source": indicator.source.name if indicator.source else "Unknown",
                "time_type": indicator.time_type,
                "indicator_set_short_name": (
                    indicator.indicator_set.short_name
                    if indicator.indicator_set
                    else "Unknown"
                ),
                "member_short_name": (
                    indicator.member_short_name
                    if indicator.member_short_name
                    else "Unknown"
                ),
            }
            for indicator in indicators_qs
        ]

        ctx["available_geos"] = get_available_geos(ctx["indicators"])

        if geography_filter:
            ctx["chart_data"] = get_chart_data(ctx["indicators"], geography_filter)
        else:
            ctx["chart_data"] = []
        return render(
            request, "alternative_interface/alter_dashboard.html", context=ctx
        )
    except Exception as e:
        from django.http import HttpResponse

        return HttpResponse(f"Error loading page: {str(e)}")
