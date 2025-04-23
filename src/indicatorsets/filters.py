import logging


import django_filters
from django.db.models import Q
from django_filters.widgets import QueryArrayWidget


from indicatorsets.models import IndicatorSet
from indicatorsets.utils import get_list_of_indicators_filtered_by_geo
from indicators.models import Indicator
from base.models import Pathogen, GeographicScope, Geography, SeverityPyramidRung


logger = logging.getLogger(__name__)

try:
    ORIGINAL_DATA_PROVIDER_CHOICES = [
        (el, el)
        for el in set(
            IndicatorSet.objects.values_list("original_data_provider", flat=True)
        )
    ]
except Exception as e:
    ORIGINAL_DATA_PROVIDER_CHOICES = [("", "No original data provider available")]
    print(f"Error fetching original data provider choices: {e}")


class IndicatorSetFilter(django_filters.FilterSet):

    indicators_qs = Indicator.objects.filter(indicator_set__isnull=False)

    pathogens = django_filters.ModelMultipleChoiceFilter(
        field_name="pathogens",
        queryset=Pathogen.objects.filter(used_in="indicatorsets"),
        widget=QueryArrayWidget,
        required=False,
    )

    geographic_scope = django_filters.ModelMultipleChoiceFilter(
        field_name="geographic_scope",
        queryset=GeographicScope.objects.filter(used_in="indicatorsets"),
        widget=QueryArrayWidget,
        required=False,
    )

    geographic_levels = django_filters.ModelMultipleChoiceFilter(
        field_name="geographic_levels",
        queryset=Geography.objects.filter(used_in="indicatorsets"),
        widget=QueryArrayWidget,
        required=False,
    )

    severity_pyramid_rungs = django_filters.ModelMultipleChoiceFilter(
        field_name="severity_pyramid_rungs",
        queryset=SeverityPyramidRung.objects.filter(used_in="indicatorsets"),
        widget=QueryArrayWidget,
        required=False,
    )

    original_data_provider = django_filters.MultipleChoiceFilter(
        field_name="original_data_provider",
        choices=ORIGINAL_DATA_PROVIDER_CHOICES,
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
        lookup_expr="exact",
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

    location_search = django_filters.CharFilter(
        method="location_search_filter", required=False, widget=QueryArrayWidget
    )

    class Meta:
        model = IndicatorSet
        fields = [
            "pathogens",
            "geographic_scope",
            "geographic_levels",
            "severity_pyramid_rungs",
            "original_data_provider",
            "temporal_granularity",
            "temporal_scope_end",
            "location_search",
        ]

    def location_search_filter(self, queryset, name, value):
        if not value:
            return queryset
        filtered_signals = get_list_of_indicators_filtered_by_geo(value)
        query = Q()
        for item in filtered_signals["epidata"]:
            query |= Q(source__name=item["source"], name=item["signal"])
        self.indicators_qs = self.indicators_qs.filter(query)
        indicator_sets = self.indicators_qs.values_list(
            "indicator_set_id", flat=True
        ).distinct()
        return queryset.filter(id__in=indicator_sets)
