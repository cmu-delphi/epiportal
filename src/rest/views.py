from collections import defaultdict

from base.models import Pathogen
from rest_framework import viewsets
from rest.serializers import (
    PathogenSerializer,
    IndicatorSerializer,
    AvailableIndicatorsQuerySerializer,
    MetaIndicatorsSerializer
)
from indicators.models import Indicator
from rest_framework.response import Response
from rest_framework.views import APIView
from rest.utils import get_available_indicators_for_geo
from django.db.models import Q


class PathogenViewSet(viewsets.ModelViewSet):
    queryset = Pathogen.objects.filter(used_in="indicators")
    serializer_class = PathogenSerializer
    http_method_names = ["get"]


class IndicatorViewSet(viewsets.ModelViewSet):
    queryset = Indicator.objects.all()
    serializer_class = IndicatorSerializer
    http_method_names = ["get"]


class AvailableIndicatorsViewSet(APIView):
    def get(self, request, *args, **kwargs):
        params = AvailableIndicatorsQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        pathogen = params.validated_data.get("pathogen")
        geo_type = params.validated_data.get("geo_type")
        geo_value = params.validated_data.get("geo_value")

        indicators = (
            Indicator.objects.filter(pathogens=pathogen)
            .select_related("source")
            .distinct()
        )

        available_indicators = get_available_indicators_for_geo(geo_type, geo_value)
        if not available_indicators:
            return Response({"indicators": []}, status=200)

        query = Q()
        for source, indicator in available_indicators:
            query |= Q(source__name=source, name=indicator)
        

        indicators = indicators.filter(query)
        return Response(
            {"indicators": IndicatorSerializer(indicators, many=True).data}, status=200
        )


# Half the indicator table has no source. They still need a group to sit in,
# and a name keeps every entry's `source` a string.
UNKNOWN_SOURCE = "unknown"


class IndicatorMetaView(APIView):
    """Indicator names grouped by the source that publishes them."""

    def get(self, request):
        grouped = defaultdict(list)
        # One flat query, grouped in Python: asking per source would be 47
        # queries, and the whole table is two short columns.
        rows = Indicator.objects.values_list("source__name", "name").order_by("name")
        for source_name, indicator_name in rows:
            grouped[source_name or UNKNOWN_SOURCE].append(indicator_name)
        groups = [
            {"source": source, "indicators": indicators}
            for source, indicators in sorted(grouped.items())
        ]
        return Response(MetaIndicatorsSerializer(groups, many=True).data, status=200)
