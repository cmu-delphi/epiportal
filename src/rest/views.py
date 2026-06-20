from base.models import Pathogen
from rest_framework import viewsets
from rest.serializers import (
    PathogenSerializer,
    IndicatorSerializer,
    AvailableIndicatorsQuerySerializer,
)
from indicators.models import Indicator
from rest_framework.response import Response
from django.conf import settings
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
