from django.shortcuts import render
from indicators.models import Indicator
from base.models import Pathogen


HEADER_DESCRIPTION = "Discover, display and download real-time infectious disease indicators (time series) that track a variety of pathogens, diseases and syndromes in a variety of locations (primarily within the USA). Browse the list, or filter it first by locations and pathogens of interest, by surveillance categories, and more. Expand any row to expose and select from a set of related indicators, then hit 'Show Selected Indicators' at bottom to plot or export your selected indicators, or to generate code snippets to retrieve them from the Delphi Epidata API. Most indicators are served from the Delphi Epidata real-time repository, but some may be available only from third parties or may require prior approval."


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

        # Get pathogen filter from URL parameters
        pathogen_filter = request.GET.get("pathogen", "")
        ctx["selected_pathogen"] = pathogen_filter

        # Build queryset with optional pathogen filtering
        indicators_qs = Indicator.objects.prefetch_related("pathogens").all()

        if pathogen_filter:
            indicators_qs = indicators_qs.filter(pathogens__id=pathogen_filter)

        # Convert to list of dictionaries
        ctx["indicators"] = [
            {
                "id": indicator.id,
                "name": indicator.name,
                "source": indicator.source.name if indicator.source else "Unknown",
                "geographic_scope": indicator.geographic_scope.name if indicator.geographic_scope else "Unknown",
                "temporal_scope_end": indicator.temporal_scope_end,
                "description": indicator.description,
                "pathogens": [pathogen.name for pathogen in indicator.pathogens.all()],
            }
            for indicator in indicators_qs
        ]

        return render(
            request, "alternative_interface/alter_dashboard.html", context=ctx
        )
    except Exception as e:
        from django.http import HttpResponse

        return HttpResponse(f"Error loading page: {str(e)}")
