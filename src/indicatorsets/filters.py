import logging
import ast


import django_filters
from django.db.models import Q
from django_filters.widgets import QueryArrayWidget


from indicatorsets.models import IndicatorSet
from indicatorsets.utils import (
    get_list_of_indicators_filtered_by_geo,
    get_original_data_provider_choices,
)
from indicators.models import Indicator
from base.models import Pathogen, Geography, SeverityPyramidRung
from alternative_interface.helper import COVIDCAST_FLUVIEW_LOCATIONS_MAPPING


logger = logging.getLogger(__name__)


class IndicatorSetFilter(django_filters.FilterSet):

    indicators_qs = Indicator.objects.filter(indicator_set__isnull=False)

    pathogens = django_filters.ModelMultipleChoiceFilter(
        field_name="pathogens",
        queryset=Pathogen.objects.filter(
            id__in=IndicatorSet.objects.values_list("pathogens", flat=True)
        ).order_by("display_order_number"),
        widget=QueryArrayWidget,
        required=False,
    )

    geographic_levels = django_filters.ModelMultipleChoiceFilter(
        field_name="geographic_levels",
        queryset=Geography.objects.filter(
            id__in=IndicatorSet.objects.values_list("geographic_levels", flat=True)
        ).order_by("display_order_number"),
        widget=QueryArrayWidget,
        required=False,
    )

    severity_pyramid_rungs = django_filters.ModelMultipleChoiceFilter(
        field_name="severity_pyramid_rungs",
        queryset=SeverityPyramidRung.objects.filter(
            id__in=IndicatorSet.objects.values_list("severity_pyramid_rungs", flat=True)
        ).order_by("display_order_number"),
        widget=QueryArrayWidget,
        required=False,
    )

    original_data_provider = django_filters.MultipleChoiceFilter(
        field_name="original_data_provider",
        choices=get_original_data_provider_choices,
        widget=QueryArrayWidget,
        lookup_expr="exact",
        required=False,
    )

    temporal_granularity = django_filters.MultipleChoiceFilter(
        field_name="temporal_granularity",
        choices=[
            ("Annually", "Annually"),
            ("Monthly", "Monthly"),
            ("Weekly", "Weekly"),
            ("Daily", "Daily"),
            ("Hourly", "Hourly"),
            ("Other", "Other"),
        ],
        widget=QueryArrayWidget,
        lookup_expr="contains",
        required=False,
    )

    temporal_scope_end = django_filters.ChoiceFilter(
        field_name="temporal_scope_end",
        choices=[
            ("Ongoing", "Ongoing Surveillance Only"),
        ],
        lookup_expr="exact",
        required=False,
    )

    hosted_by_delphi = django_filters.CharFilter(
        method="hosted_by_delphi_filter",
        required=False,
    )

    location_search = django_filters.CharFilter(
        method="location_search_filter", required=False, widget=QueryArrayWidget
    )

    class Meta:
        model = IndicatorSet
        fields = [
            "pathogens",
            "geographic_levels",
            "severity_pyramid_rungs",
            "original_data_provider",
            "temporal_granularity",
            "temporal_scope_end",
            "hosted_by_delphi",
            "location_search",
        ]

    def hosted_by_delphi_filter(self, queryset, name, value):
        """
        Filter for IndicatorSets where source_type is 'covidcast' or 'other_endpoint'
        when hosted_by_delphi checkbox is checked.
        """
        # HTML checkboxes send "on" when checked, nothing when unchecked
        # Handle different value types that indicate checkbox is checked
        if not value:
            return queryset

        # Convert value to string for comparison
        value_str = str(value).lower().strip()
        checked_values = ["true", "on", "1", "yes"]

        if value_str in checked_values or value is True:
            logger.debug("Filtering for hosted_by_delphi=True")
            return queryset.filter(source_type__in=["covidcast", "other_endpoint"])

        return queryset

    @staticmethod
    def include_fluview(values):
        include_fluview = False
        for value in ast.literal_eval(values):
            if COVIDCAST_FLUVIEW_LOCATIONS_MAPPING.get(value):
                include_fluview = True
                break
        return include_fluview

    def location_search_filter(self, queryset, name, value):
        if not value:
            return queryset
        indicator_sets = []
        filtered_indicators = get_list_of_indicators_filtered_by_geo(value)
        include_fluview = self.include_fluview(value)
        query = Q()
        if filtered_indicators["epidata"]:
            for item in filtered_indicators["epidata"]:
                query |= Q(source__name=item["source"], name=item["signal"])
        if include_fluview:
            query |= Q(indicator_set__epidata_endpoint="fluview")
        self.indicators_qs = self.indicators_qs.filter(query)
        indicator_sets = list(self.indicators_qs.values_list("indicator_set_id", flat=True).order_by("indicator_set_id").distinct())
        return queryset.filter(id__in=indicator_sets)
