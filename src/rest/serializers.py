from rest_framework import serializers

from base.models import Pathogen
from indicators.models import Indicator
from datasources.models import SourceSubdivision


class PathogenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pathogen
        fields = ["name", "display_name"]


class SourceSubdivisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceSubdivision
        fields = ["name", "display_name"]

class IndicatorSerializer(serializers.ModelSerializer):
    pathogens = PathogenSerializer(many=True, read_only=True)
    source = SourceSubdivisionSerializer(read_only=True)
    class Meta:
        model = Indicator
        fields = "__all__"


class AvailableIndicatorsQuerySerializer(serializers.Serializer):
    geo_type = serializers.CharField()
    geo_value = serializers.CharField()
    pathogen = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Pathogen.objects.filter(used_in="indicators")
    )
