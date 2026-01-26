import base64
import json
import sys
from datetime import datetime
from textwrap import dedent

import requests
from delphi_utils import get_structured_logger
from django.conf import settings
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.views.generic import ListView
from epiweeks import Week
from django.core.cache import cache

from base.models import GeographyUnit
from indicatorsets.filters import IndicatorSetFilter
from indicatorsets.forms import IndicatorSetFilterForm
from indicatorsets.models import ColumnDescription, FilterDescription, IndicatorSet
from indicatorsets.utils import (
    generate_covidcast_dataset_epivis,
    generate_covidcast_indicators_export_url,
    generate_flusurv_dataset_epivis,
    generate_flusurv_export_url,
    generate_fluview_dataset_epivis,
    generate_fluview_indicators_export_url,
    generate_nidss_dengue_dataset_epivis,
    generate_nidss_dengue_export_url,
    generate_nidss_flu_dataset_epivis,
    generate_nidss_flu_export_url,
    generate_query_code_covidcast,
    generate_query_code_flusurv,
    generate_query_code_fluview,
    generate_query_code_nidss_dengue,
    generate_query_code_nidss_flu,
    get_grouped_original_data_provider_choices,
    group_by_property,
    log_form_data,
    log_form_stats,
    preview_covidcast_data,
    preview_flusurv_data,
    preview_fluview_data,
    preview_nidss_dengue_data,
    preview_nidss_flu_data,
)

indicatorsets_logger = get_structured_logger("indicatorsets_logger")


HEADER_DESCRIPTION = "Discover, display and download real-time infectious disease indicators (time series) that track a variety of pathogens, diseases and syndromes in a variety of locations (primarily within the USA). Browse the list, or filter it first by locations and pathogens of interest, by surveillance categories, and more. Expand any row to expose and select from a set of related indicators, then hit 'Show Selected Indicators' at bottom to plot or export your selected indicators, or to generate code snippets to retrieve them from the Delphi Epidata API. Most indicators are served from the Delphi Epidata real-time repository, but some may be available only from third parties or may require prior approval."


def get_related_indicators(queryset, indicator_set_ids: list):
    related_indicators = []
    indicators_data = queryset.filter(indicator_set__id__in=indicator_set_ids).values(
        "id",
        "display_name",
        "member_name",
        "member_short_name",
        "name",
        "indicator_set__id",
        "indicator_set__name",
        "indicator_set__short_name",
        "indicator_set__epidata_endpoint",
        "source__name",
        "time_type",
        "description",
        "member_description",
        "indicator_set__dua_required",
        "source_type",
    )

    for item in indicators_data:
        display_name = item["display_name"]
        if not display_name:
            if item["member_name"]:
                display_name = item["member_name"]
            else:
                display_name = item["name"]

        member_description = (
            item["member_description"]
            if item["member_description"]
            else item["description"]
        )

        related_indicators.append(
            {
                "id": item["id"],
                "display_name": display_name,
                "member_name": item["member_name"] if item["member_name"] else "",
                "member_short_name": (
                    item["member_short_name"] if item["member_short_name"] else ""
                ),
                "name": item["name"] if item["name"] else "",
                "indicator_set": item["indicator_set__id"],
                "indicator_set_name": item["indicator_set__name"],
                "indicator_set_short_name": (
                    item["indicator_set__short_name"]
                    if item["indicator_set__short_name"]
                    else ""
                ),
                "endpoint": (
                    item["indicator_set__epidata_endpoint"]
                    if item["indicator_set__epidata_endpoint"]
                    else ""
                ),
                "source": item["source__name"] if item["source__name"] else "",
                "time_type": item["time_type"] if item["time_type"] else "",
                "description": item["description"] if item["description"] else "",
                "member_description": member_description,
                "restricted": (
                    item["indicator_set__dua_required"]
                    if item["indicator_set__dua_required"]
                    else ""
                ),
                "source_type": item["source_type"],
            }
        )
    return related_indicators


class IndicatorSetListView(ListView):
    model = IndicatorSet
    template_name = "indicatorsets/indicatorSets.html"
    context_object_name = "indicatorsets"

    def get_queryset(self):
        try:
            return IndicatorSet.objects.all().prefetch_related(
                "geographic_scope",
                "pathogens",
                "severity_pyramid_rungs",
                "geographic_levels",
            )
        except Exception as e:
            indicatorsets_logger.error(f"Error fetching indicator sets: {e}")
            return IndicatorSet.objects.none()

    def get_url_params(self):
        url_params_dict = {
            "pathogens": (
                [int(el) for el in self.request.GET.getlist("pathogens")]
                if self.request.GET.get("pathogens")
                else ""
            ),
            "geographic_scope": (
                [el for el in self.request.GET.getlist("geographic_scope")]
                if self.request.GET.get("geographic_scope")
                else ""
            ),
            "severity_pyramid_rungs": (
                [el for el in self.request.GET.getlist("severity_pyramid_rungs")]
                if self.request.GET.get("severity_pyramid_rungs")
                else ""
            ),
            "original_data_provider": [
                el for el in self.request.GET.getlist("original_data_provider")
            ],
            "temporal_granularity": (
                [el for el in self.request.GET.getlist("temporal_granularity")]
                if self.request.GET.get("temporal_granularity")
                else ""
            ),
            "geographic_levels": (
                [el for el in self.request.GET.getlist("geographic_levels")]
                if self.request.GET.get("geographic_levels")
                else ""
            ),
            "temporal_scope_end": (
                self.request.GET.get("temporal_scope_end")
                if self.request.GET.get("temporal_scope_end")
                else ""
            ),
            "hosted_by_delphi": (
                str(
                    self.request.GET.get("hosted_by_delphi")
                    in ["True", "true", "on", "1"]
                ).lower()
                if self.request.GET.get("hosted_by_delphi")
                else "false"
            ),
            "location_search": (
                [el for el in self.request.GET.getlist("location_search")]
                if self.request.GET.get("location_search")
                else ""
            ),
        }
        url_params_str = ""
        for param_name, param_value in url_params_dict.items():
            if isinstance(param_value, list):
                for value in param_value:
                    url_params_str = f"{url_params_str}&{param_name}={value}"
            else:
                if param_value not in ["", None]:
                    url_params_str = f"{url_params_str}&{param_name}={param_value}"
        return url_params_dict, url_params_str

    def get_grouped_geographic_granularities(self):
        geo_units = GeographyUnit.objects.prefetch_related("geo_level").values(
            "geo_level__name", "id", "display_name", "geo_level__display_name"
        )
        geographic_granularities = [
            {
                "id": f"{geo_unit['geo_level__name']}:{geo_unit['id']}",
                "geoType": geo_unit["geo_level__name"],
                "text": geo_unit["display_name"],
                "geoTypeDisplayName": geo_unit["geo_level__display_name"],
            }
            for geo_unit in geo_units
        ]
        geographic_granularities = group_by_property(
            geographic_granularities, "geoTypeDisplayName"
        )
        grouped_geographic_granularities = []
        for key, value in geographic_granularities.items():
            grouped_geographic_granularities.append(
                {
                    "text": key,
                    "children": value,
                }
            )
        return grouped_geographic_granularities

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        url_params_dict, _ = self.get_url_params()
        filter = IndicatorSetFilter(self.request.GET, queryset=queryset)
        context["url_params_dict"] = url_params_dict
        context["epivis_url"] = settings.EPIVIS_URL
        context["epidata_url"] = settings.EPIDATA_URL
        # Convert hosted_by_delphi string back to boolean for form initialization
        form_initial = url_params_dict.copy()
        if "hosted_by_delphi" in form_initial:
            form_initial["hosted_by_delphi"] = (
                form_initial["hosted_by_delphi"] == "true"
            )
        context["form"] = IndicatorSetFilterForm(initial=form_initial)
        context["filter"] = filter
        context["APP_VERSION"] = settings.APP_VERSION
        context["indicator_sets"] = filter.qs.annotate(
            is_top_priority=Case(
                When(
                    temporal_scope_end="Ongoing",
                    dua_required__in=["No", "Unknown", "Sensor-dependent", ""],
                    source_type__in=["covidcast", "other_endpoint"],
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            ),
            beta_last=Case(
                When(name__istartswith="beta", then=Value(sys.maxsize)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            delphi_hosted=Case(
                When(source_type__in=["covidcast", "other_endpoint"], then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        ).order_by("beta_last", "-is_top_priority", "-delphi_hosted", "name")
        context["filters_descriptions"] = (
            FilterDescription.get_all_descriptions_as_dict()
        )
        context["columns_descriptions"] = (
            ColumnDescription.get_all_descriptions_as_dict()
        )
        context["header_description"] = HEADER_DESCRIPTION
        geographic_granularities = cache.get("geographic_granularities")
        if not geographic_granularities:
            geographic_granularities = self.get_grouped_geographic_granularities()
            cache.set(
                "geographic_granularities", geographic_granularities, 60 * 60 * 24
            )
        context["geographic_granularities"] = geographic_granularities
        context["grouped_data_providers"] = get_grouped_original_data_provider_choices()
        return context


def epivis(request):
    if request.method == "POST":
        datasets = []
        data = json.loads(request.body)
        indicators = data.get("indicators", [])
        covidcast_geos = data.get("covidCastGeographicValues", [])
        fluview_geos = data.get("fluviewLocations", [])
        nidss_flu_locations = data.get("nidssFluLocations", [])
        nidss_dengue_locations = data.get("nidssDengueLocations", [])
        flusurv_locations = data.get("flusurvLocations", [])
        log_form_stats(request, data, "epivis")
        log_form_data(request, data, "epivis")
        for indicator in indicators:
            if indicator["_endpoint"] == "covidcast":
                datasets.extend(
                    generate_covidcast_dataset_epivis(indicator, covidcast_geos)
                )
            elif indicator["_endpoint"] == "fluview":
                datasets.extend(
                    generate_fluview_dataset_epivis(indicator, fluview_geos)
                )
            elif indicator["_endpoint"] == "nidss_flu":
                datasets.extend(
                    generate_nidss_flu_dataset_epivis(indicator, nidss_flu_locations)
                )
            elif indicator["_endpoint"] == "nidss_dengue":
                datasets.extend(
                    generate_nidss_dengue_dataset_epivis(
                        indicator, nidss_dengue_locations
                    )
                )
            elif indicator["_endpoint"] == "flusurv":
                datasets.extend(
                    generate_flusurv_dataset_epivis(indicator, flusurv_locations)
                )
        if datasets:
            datasets_json = json.dumps({"datasets": datasets})
            datasets_b64 = base64.b64encode(datasets_json.encode("ascii")).decode(
                "ascii"
            )
            return JsonResponse({"epivis_url": f"{settings.EPIVIS_URL}#{datasets_b64}"})
        else:
            return JsonResponse({"epivis_url": settings.EPIVIS_URL})


def generate_export_data_url(request):
    if request.method == "POST":
        data_export_block = "To download data, please click on the link or copy/paste command(s) into your terminal: <br>{}"
        data_export_commands = []
        data = json.loads(request.body)
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
        indicators = data.get("indicators", [])
        covidcast_geos = data.get("covidCastGeographicValues", [])
        fluview_geos = data.get("fluviewLocations", [])
        nidss_flu_locations = data.get("nidssFluLocations", [])
        nidss_dengue_locations = data.get("nidssDengueLocations", [])
        flusurv_locations = data.get("flusurvLocations", [])
        api_key = data.get("apiKey", None)

        log_form_stats(request, data, "export")
        log_form_data(request, data, "export")
        data_export_commands.extend(
            generate_covidcast_indicators_export_url(
                indicators, start_date, end_date, covidcast_geos, api_key
            )
        )
        if fluview_geos:
            data_export_commands.extend(
                generate_fluview_indicators_export_url(
                    fluview_geos, start_date, end_date, api_key
                )
            )
        if nidss_flu_locations:
            data_export_commands.extend(
                generate_nidss_flu_export_url(
                    nidss_flu_locations, start_date, end_date, api_key
                )
            )
        if nidss_dengue_locations:
            data_export_commands.extend(
                generate_nidss_dengue_export_url(
                    nidss_dengue_locations, start_date, end_date, api_key
                )
            )
        if flusurv_locations:
            data_export_commands.extend(
                generate_flusurv_export_url(
                    flusurv_locations, start_date, end_date, api_key
                )
            )
        data_export_block = data_export_block.format("<br>".join(data_export_commands))
        response = {
            "data_export_block": data_export_block,
            "data_export_commands": data_export_commands,
        }
        return JsonResponse(response)


def preview_data(request):
    if request.method == "POST":
        data = json.loads(request.body)
        log_form_stats(request, data, "preview")
        log_form_data(request, data, "preview")
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
        indicators = data.get("indicators", [])
        covidcast_geos = data.get("covidCastGeographicValues", {})
        fluview_geos = data.get("fluviewLocations", [])
        nidss_flu_locations = data.get("nidssFluLocations", [])
        nidss_dengue_locations = data.get("nidssDengueLocations", [])
        flusurv_locations = data.get("flusurvLocations", [])
        api_key = data.get("apiKey", None)

        preview_data = []
        preview_data.extend(
            preview_covidcast_data(
                indicators, start_date, end_date, covidcast_geos, api_key
            )
        )
        if fluview_geos:
            preview_data.extend(
                preview_fluview_data(fluview_geos, start_date, end_date, api_key)
            )
        if nidss_flu_locations:
            preview_data.extend(
                preview_nidss_flu_data(
                    nidss_flu_locations, start_date, end_date, api_key
                )
            )
        if nidss_dengue_locations:
            preview_data.extend(
                preview_nidss_dengue_data(
                    nidss_dengue_locations, start_date, end_date, api_key
                )
            )
        if flusurv_locations:
            preview_data.extend(
                preview_flusurv_data(flusurv_locations, start_date, end_date, api_key)
            )
        return JsonResponse(preview_data, safe=False)


def create_query_code(request):
    if request.method == "POST":
        data = json.loads(request.body)
        log_form_stats(request, data, "code")
        log_form_data(request, data, "code")
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
        indicators = data.get("indicators", [])
        covidcast_geos = data.get("covidCastGeographicValues", {})
        fluview_geos = data.get("fluviewLocations", [])
        nidss_flu_locations = data.get("nidssFluLocations", [])
        nidss_dengue_locations = data.get("nidssDengueLocations", [])
        flusurv_locations = data.get("flusurvLocations", [])
        python_code_blocks = [
            dedent(
                """\
                <pre class="code-block">
                <code>from epidatpy import CovidcastEpidata, EpiDataContext, EpiRange

                # All calls using the `epidata` object will now be cached for 7 days
                epidata = EpiDataContext(use_cache=True, cache_max_age_days=7)
            """
            )
        ]
        r_code_blocks = [
            dedent(
                """\
                <pre class="code-block">
                <code>library(epidatr)
            """
            )
        ]
        grouped_indicators = group_by_property(indicators, "data_source")
        for data_source, indicators in grouped_indicators.items():
            indicators_str = ",".join(
                [indicator["indicator"] for indicator in indicators]
            )
            if indicators[0].get("_endpoint") == "covidcast":
                python_code_block, r_code_block = generate_query_code_covidcast(
                    indicators,
                    covidcast_geos,
                    start_date,
                    end_date,
                    data_source,
                    indicators_str,
                )
                python_code_blocks.extend(python_code_block)
                r_code_blocks.extend(r_code_block)
        if fluview_geos:
            python_code_block, r_code_block = generate_query_code_fluview(
                fluview_geos, start_date, end_date
            )
            python_code_blocks.extend(python_code_block)
            r_code_blocks.extend(r_code_block)
        if nidss_flu_locations:
            python_code_block, r_code_block = generate_query_code_nidss_flu(
                nidss_flu_locations, start_date, end_date
            )
            python_code_blocks.extend(python_code_block)
            r_code_blocks.extend(r_code_block)
        if nidss_dengue_locations:
            python_code_block, r_code_block = generate_query_code_nidss_dengue(
                nidss_dengue_locations, start_date, end_date
            )
            python_code_blocks.extend(python_code_block)
            r_code_blocks.extend(r_code_block)
        if flusurv_locations:
            python_code_block, r_code_block = generate_query_code_flusurv(
                flusurv_locations, start_date, end_date
            )
            python_code_blocks.extend(python_code_block)
            r_code_blocks.extend(r_code_block)
        python_code_blocks.append("</code></pre>")
        r_code_blocks.append("</code></pre>")
        return JsonResponse(
            {"python_code_blocks": python_code_blocks, "r_code_blocks": r_code_blocks},
            safe=False,
        )


def get_available_geos(request):
    if request.method == "POST":
        geo_values = []
        data = json.loads(request.body)
        indicators = data.get("indicators", [])
        grouped_indicators = group_by_property(indicators, "data_source")
        for data_source, indicators in grouped_indicators.items():
            indicators_str = ",".join(
                indicator["indicator"] for indicator in indicators
            )
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
        return JsonResponse(
            {"geographic_granularities": geographic_granularities}, safe=False
        )


def get_related_indicators_json(request):
    try:
        queryset = IndicatorSet.objects.all().prefetch_related(
            "geographic_scope",
            "pathogens",
            "severity_pyramid_rungs",
            "geographic_levels",
        )
    except Exception as e:
        indicatorsets_logger.error(f"Error fetching indicator sets: {e}")
        queryset = IndicatorSet.objects.none()

    filter = IndicatorSetFilter(request.GET, queryset=queryset)
    related_indicators = get_related_indicators(
        filter.indicators_qs.select_related("indicator_set", "source"),
        filter.qs.values_list("id", flat=True),
    )
    return JsonResponse({"related_indicators": related_indicators})


def check_fluview_geo_coverage(request):
    null_data_indicators = []
    if request.method == "GET":
        geo_value = request.GET.get("geo")
        indicators = request.GET.get("indicators")
        start_date = 199740
        end_date = Week.fromdate(datetime.today())
        end_date = f"{end_date.year}{end_date.week if end_date.week >= 10 else '0' + str(end_date.week)}"
        indicators = json.loads(indicators)

        fluview_indicators = {}
        fluview_clinical_indicators = {}
        for indicator in indicators:
            if indicator["data_source"] == "fluview":
                fluview_indicators[indicator["indicator"]] = 0
            elif indicator["data_source"] == "fluview_clinical":
                fluview_clinical_indicators[indicator["indicator"]] = 0

        params = {
            "regions": geo_value,
            "epiweeks": f"{start_date}-{end_date}",
            "api_key": settings.EPIDATA_API_KEY,
        }

        if fluview_indicators:
            response = requests.get(f"{settings.EPIDATA_URL}fluview", params=params)
            if response.status_code == 200:
                data = response.json()
                if len(data["epidata"]):
                    for el in data["epidata"]:
                        for indicator in fluview_indicators.keys():
                            fluview_indicators[indicator] += (
                                el[indicator] if el[indicator] else 0
                            )
        if fluview_clinical_indicators:
            response = requests.get(
                f"{settings.EPIDATA_URL}fluview_clinical", params=params
            )
            if response.status_code == 200:
                data = response.json()
                if len(data["epidata"]):
                    for el in data["epidata"]:
                        for indicator in fluview_clinical_indicators.keys():
                            fluview_clinical_indicators[indicator] += el[indicator]

        for indicator in fluview_indicators.keys():
            if fluview_indicators[indicator] == 0:
                null_data_indicators.append(indicator)
        for indicator in fluview_clinical_indicators.keys():
            if fluview_clinical_indicators[indicator] == 0:
                null_data_indicators.append(indicator)
        not_covered_indicators = [
            indicator
            for indicator in indicators
            if indicator["indicator"] in null_data_indicators
        ]
        return JsonResponse({"not_covered_indicators": not_covered_indicators})
