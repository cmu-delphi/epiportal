import logging
from datetime import datetime

from django.db.models import Case, When, Value, IntegerField
from django.http import JsonResponse
from django.shortcuts import render

from alternative_interface.models import ExpressViewIndicator
from alternative_interface.utils import get_available_geos, get_chart_data
from epiportal.settings import ALTERNATIVE_INTERFACE_VERSION

logger = logging.getLogger(__name__)

MENU_ITEMS_DISPLAY_ORDER_NUMBER = {
    "Influenza": 1,
    "COVID-19": 2,
    "RSV": 3,
    "Influenza-Like Illness (ILI)": 4,
}


def _convert_indicators_to_dicts(indicators_qs):
    """Convert queryset of ExpressViewIndicator to list of dictionaries."""
    return [
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


def _get_indicators_queryset(pathogen_filter):
    """Get optimized queryset for indicators filtered by pathogen."""
    return (
        ExpressViewIndicator.objects.filter(menu_item=pathogen_filter)
        .select_related("indicator__indicator_set", "indicator__source")
    )


def alternative_interface_view(request):
    """Main view for the alternative interface dashboard."""
    try:
        pathogen_filter = request.GET.get("pathogen", "")
        geography_filter = request.GET.get("geography", "")

        # Fetch pathogens for dropdown - optimized query
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

        # Get indicators with optimized query
        indicators_qs = _get_indicators_queryset(pathogen_filter)
        indicators = _convert_indicators_to_dicts(indicators_qs)

        ctx = {
            "alternative_interface_version": ALTERNATIVE_INTERFACE_VERSION,
            "selected_pathogen": pathogen_filter,
            "selected_geography": geography_filter,
            "pathogens": pathogens,
            "indicators": indicators,
            "available_geos": get_available_geos(indicators),
            "chart_data": (
                get_chart_data(indicators, geography_filter)
                if geography_filter
                else []
            ),
        }
        print(ctx["available_geos"])
        ctx["current_year"] = datetime.now().year

        return render(
            request, "alternative_interface/alter_dashboard.html", context=ctx
        )
    except Exception as e:
        logger.exception("Error loading alternative interface page")
        return JsonResponse({"error": str(e)}, status=500)


def get_available_geos_ajax(request):
    """AJAX endpoint to get available geographies for a selected pathogen."""
    try:
        pathogen_filter = request.GET.get("pathogen", "")

        if not pathogen_filter:
            # Return all available geographies when no pathogen is selected
            available_geos = get_available_geos([])
            return JsonResponse({"available_geos": available_geos})

        indicators_qs = _get_indicators_queryset(pathogen_filter)
        indicators = _convert_indicators_to_dicts(indicators_qs)
        available_geos = get_available_geos(indicators)

        return JsonResponse({"available_geos": available_geos})
    except Exception as e:
        logger.exception("Error fetching available geos")
        return JsonResponse({"error": str(e)}, status=500)


def get_chart_data_ajax(request):
    """AJAX endpoint to get chart data for selected pathogen and geography."""
    try:
        pathogen_filter = request.GET.get("pathogen", "")
        geography_filter = request.GET.get("geography", "")

        if not pathogen_filter or not geography_filter:
            return JsonResponse({"chart_data": {}})

        indicators_qs = _get_indicators_queryset(pathogen_filter)
        indicators = _convert_indicators_to_dicts(indicators_qs)
        chart_data = get_chart_data(indicators, geography_filter)

        return JsonResponse({"chart_data": chart_data})
    except Exception as e:
        logger.exception("Error fetching chart data")
        return JsonResponse({"error": str(e)}, status=500)
