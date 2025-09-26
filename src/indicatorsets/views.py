import base64
import json
import requests
from textwrap import dedent


from django.conf import settings
from django.http import JsonResponse
from django.views.generic import ListView
from django.db.models import Case, When, Value, IntegerField

from base.models import Geography, GeographyUnit
from indicatorsets.filters import IndicatorSetFilter
from indicatorsets.forms import IndicatorSetFilterForm
from indicatorsets.models import IndicatorSet, FilterDescription, ColumnDescription
from indicatorsets.utils import (
    group_by_property,
    generate_covidcast_dataset_epivis,
    generate_fluview_dataset_epivis,
    generate_nidss_flu_dataset_epivis,
    generate_nidss_dengue_dataset_epivis,
    generate_flusurv_dataset_epivis,
    generate_covidcast_indicators_export_url,
    generate_fluview_indicators_export_url,
    generate_nidss_flu_export_url,
    generate_nidss_dengue_export_url,
    generate_flusurv_export_url,
    preview_covidcast_data,
    preview_fluview_data,
    preview_nidss_flu_data,
    preview_nidss_dengue_data,
    preview_flusurv_data,
    generate_query_code_covidcast,
    generate_query_code_fluview,
    generate_query_code_nidss_flu,
    generate_query_code_nidss_dengue,
    generate_query_code_flusurv,
    get_epiweek,
    get_client_ip,
)

from delphi_utils import get_structured_logger

indicatorsets_logger = get_structured_logger("indicatorsets_logger")

form_data_logger = get_structured_logger("form_data_logger")
form_stats_logger = get_structured_logger("form_stats_logger")

HEADER_DESCRIPTION = "Discover, display and download real-time infectious disease indicators (time series) that track a variety of pathogens, diseases and syndromes in a variety of locations (primarily within the USA). Browse the list, or filter it first by locations and pathogens of interest, by surveillance categories, and more. Expand any row to expose and select from a set of related indicators, then hit 'Show Selected Indicators' at bottom to plot or export your selected indicators, or to generate code snippets to retrieve them from the Delphi Epidata API. Most indicators are served from the Delphi Epidata real-time repository, but some may be available only from third parties or may require prior approval."


def log_form_stats(request, data, form_mode):
    log_data = {
        "form_mode": form_mode,
        "num_of_indicators": len(data.get("indicators", [])),
        "num_of_covidcast_geos": len(data.get("covidCastGeographicValues", [])),
        "num_of_fluview_geos": len(data.get("fluviewLocations", [])),
        "num_of_nidss_flu_geos": len(data.get("nidssFluLocations", [])),
        "num_of_nidss_dengue_geos": len(data.get("nidssDengueLocations", [])),
        "num_of_flusurv_geos": len(data.get("flusurvLocations", [])),
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "epiweeks": (
            get_epiweek(data.get("start_date"), data.get("end_date"))
            if data.get("start_date") and data.get("end_date")
            else []
        ),
        "api_key_used": bool(data.get("api_key")),
        "api_key": data.get("api_key", "")[:4] + "..." if data.get("api_key") else "",
        "user_ip": get_client_ip(request),
        "user_ga_id": data.get("clientId", "") if data.get("clientId") else "",
    }

    form_stats_logger.info(log_data)


def log_form_data(request, data, form_mode):
    indicators = data.get("indicators", [])
    indicators = [
        {
            "endpoint": ind.get("_endpoint"),
            "indicator": ind.get("indicator"),
            "data_source": ind.get("data_source"),
            "time_type": ind.get("time_type"),

        } for ind in indicators
    ]  # fmt: skip
    indicators = group_by_property(indicators, "endpoint")
    covidcast_geographic_values = data.get("covidCastGeographicValues", [])

    covidcast_geos = []
    for geo_type in covidcast_geographic_values.keys():
        for geo_value in covidcast_geographic_values.get(geo_type, []):
            covidcast_geos.append(
                {
                    "geo_type": geo_type,
                    "geo_value": geo_value.get("id").split(":")[1],
                    "geo_text": geo_value.get("text"),
                }
            )
    fluview_geos = [
        {
            "geo_value": geo.get("id"),
            "geo_text": geo.get("text"),
        }
        for geo in data.get("fluviewLocations", [])
    ]
    nidss_flu_geos = [
        {
            "geo_value": geo.get("id"),
            "geo_text": geo.get("text"),
        }
        for geo in data.get("nidssFluLocations", [])
    ]
    nidss_dengue_geos = [
        {
            "geo_value": geo.get("id"),
            "geo_text": geo.get("text"),
        }
        for geo in data.get("nidssDengueLocations", [])
    ]
    flusurv_geos = [
        {
            "geo_value": geo.get("id"),
            "geo_text": geo.get("text"),
        }
        for geo in data.get("flusurvLocations", [])
    ]
    log_data = {
        "mode": form_mode,
        "indicators": [
            {"endpoint": endpoint, "indicators": group}
            for endpoint, group in indicators.items()
        ],
        "covidcast_geos": covidcast_geos,
        "fluview_geos": fluview_geos,
        "nidss_flu_geos": nidss_flu_geos,
        "nidss_dengue_geos": nidss_dengue_geos,
        "flusurv_geos": flusurv_geos,
        "start_date": data.get("start_date", ""),
        "end_date": data.get("end_date", ""),
        "epiweeks": get_epiweek(data.get("start_date", ""), data.get("end_date", "")) if data.get("start_date") and data.get("end_date") else [],  # fmt: skip
        "api_key_used": bool(data.get("apiKey")),
        "api_key": data.get("apiKey", "") if data.get("apiKey") else "",
        "user_ip": get_client_ip(request),
        "user_ga_id": data.get("clientId", "") if data.get("clientId") else "",
    }
    form_data_logger.info(log_data)


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

    def get_related_indicators(self, queryset, indicator_set_ids: list):
        related_indicators = []
        for indicator in queryset.filter(indicator_set__id__in=indicator_set_ids):
            related_indicators.append(
                {
                    "id": indicator.id,
                    "display_name": (
                        indicator.get_display_name if indicator.get_display_name else ""
                    ),
                    "member_name": (
                        indicator.member_name if indicator.member_name else ""
                    ),
                    "member_short_name": (
                        indicator.member_short_name
                        if indicator.member_short_name
                        else ""
                    ),
                    "name": indicator.name if indicator.name else "",
                    "indicator_set": (
                        indicator.indicator_set.id if indicator.indicator_set else ""
                    ),
                    "indicator_set_name": (
                        indicator.indicator_set.name if indicator.indicator_set else ""
                    ),
                    "indicator_set_short_name": (
                        indicator.indicator_set.short_name
                        if indicator.indicator_set
                        else ""
                    ),
                    "endpoint": (
                        indicator.indicator_set.epidata_endpoint
                        if indicator.indicator_set
                        else ""
                    ),
                    "source": indicator.source.name if indicator.source else "",
                    "time_type": indicator.time_type if indicator.time_type else "",
                    "description": (
                        indicator.description if indicator.description else ""
                    ),
                    "member_description": (
                        indicator.member_description
                        if indicator.member_description
                        else indicator.description
                    ),
                    "restricted": (
                        indicator.indicator_set.dua_required
                        if indicator.indicator_set
                        else ""
                    ),
                    "source_type": indicator.source_type,
                }
            )
        return related_indicators

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
        geographic_granularities = [
            {
                "id": f"{geo_unit.geo_level.name}:{geo_unit.geo_id}",
                "geoType": geo_unit.geo_level.name,
                "text": geo_unit.display_name,
                "geoTypeDisplayName": geo_unit.geo_level.display_name,
            }
            for geo_unit in GeographyUnit.objects.all()
            .prefetch_related("geo_level")
            .order_by("level")
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
        context["form"] = IndicatorSetFilterForm(initial=url_params_dict)
        context["filter"] = filter
        context["APP_VERSION"] = settings.APP_VERSION
        context["indicator_sets"] = filter.qs.annotate(
            is_ongoing=Case(
                When(
                    temporal_scope_end="Ongoing",
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            ),
            is_dua_required=Case(
                When(
                    dua_required="No",
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            ),
        ).order_by("-is_ongoing", "-is_dua_required", "name")
        context["related_indicators"] = json.dumps(
            self.get_related_indicators(
                filter.indicators_qs, filter.qs.values_list("id", flat=True)
            )
        )
        context["filters_descriptions"] = (
            FilterDescription.get_all_descriptions_as_dict()
        )
        context["columns_descriptions"] = (
            ColumnDescription.get_all_descriptions_as_dict()
        )
        context["header_description"] = HEADER_DESCRIPTION
        context["available_geographies"] = Geography.objects.filter(
            used_in="indicators"
        )
        context["geographic_granularities"] = (
            self.get_grouped_geographic_granularities()
        )
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

        log_data = {
            "form_mode": "epivis",
            "num_of_indicators": len(data.get("indicators", [])),
            "num_of_covidcast_geos": len(data.get("covidCastGeographicValues", [])),
            "num_of_fluview_geos": len(data.get("fluviewLocations", [])),
            "num_of_nidss_flu_geos": len(data.get("nidssFluLocations", [])),
            "num_of_nidss_dengue_geos": len(data.get("nidssDengueLocations", [])),
            "num_of_flusurv_geos": len(data.get("flusurvLocations", [])),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "epiweeks": (
                get_epiweek(data.get("start_date"), data.get("end_date"))
                if data.get("start_date") and data.get("end_date")
                else []
            ),
            "api_key_used": bool(data.get("api_key")),
            "api_key": data.get("api_key", "")[:4] + "..." if data.get("api_key") else "",
            "user_ip": get_client_ip(request),
            "user_ga_id": data.get("clientId", "") if data.get("clientId") else "",
        }

        form_stats_logger.info(log_data)
        # log_form_stats(request, data, "export")
        # log_form_data(request, data, "export")
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
