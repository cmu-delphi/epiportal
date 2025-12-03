from django.shortcuts import render
from django.db.models import Case, When, Value, IntegerField
from alternative_interface.models import ExpressViewIndicator
from epiportal.settings import ALTERNATIVE_INTERFACE_VERSION

from alternative_interface.utils import get_available_geos, get_chart_data


MENU_ITEMS_DISPLAY_ORDER_NUMBER = {
    "Influenza": 1,
    "COVID-19": 2,
    "RSV": 3,
    "Influenza-Like Illness (ILI)": 4,
}

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

        # Fetch pathogens for dropdown
        pathogens_qs = (
            ExpressViewIndicator.objects.annotate(
                order_number=Case(
                    *[
                        When(menu_item=key, then=Value(value))
                        for key, value in MENU_ITEMS_DISPLAY_ORDER_NUMBER.items()
                    ],
                    default=Value(999),
                    output_field=IntegerField(),
                )
            )
            .values("menu_item", "order_number")
            .distinct()
            .order_by("order_number")
        )
        pathogens = [item["menu_item"] for item in pathogens_qs]
        ctx["pathogens"] = pathogens

        indicators_qs = ExpressViewIndicator.objects.filter(
            menu_item=pathogen_filter
        ).prefetch_related("indicator")

        # Convert to list of dictionaries
        ctx["indicators"] = [
            {
                "_endpoint": (
                    indicator.indicator.indicator_set.epidata_endpoint
                    if indicator.indicator.indicator_set
                    else ""
                ),
                "name": indicator.indicator.name,
                "data_source": (
                    indicator.indicator.source.name
                    if indicator.indicator.source
                    else "Unknown"
                ),
                "time_type": indicator.indicator.time_type,
                "indicator_set_short_name": (
                    indicator.indicator.indicator_set.short_name
                    if indicator.indicator.indicator_set
                    else "Unknown"
                ),
                "member_short_name": (
                    indicator.indicator.member_short_name
                    if indicator.indicator.member_short_name
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
