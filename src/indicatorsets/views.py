import base64
import json
import logging
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
    generate_epivis_custom_title,
    generate_random_color,
    get_epiweek,
    group_by_property,
)

logger = logging.getLogger(__name__)

HEADER_DESCRIPTION = "Discover, display and download real-time infectious disease indicators (time series) that track a variety of pathogens, diseases and syndromes in a variety of locations (primarily within the USA). Browse the list, or filter it first by locations and pathogens of interest, by surveillance categories, and more. Expand any row to expose and select from a set of related indicators, then hit 'Show Selected Indicators' at bottom to plot or export your selected indicators, or to generate code snippets to retrieve them from the Delphi Epidata API. Most indicators are served from the Delphi Epidata real-time repository, but some may be available only from third parties or may require prior approval."

FLUVIEW_INDICATORS_MAPPING = {"wili": "%wILI", "ili": "%ILI"}


class IndicatorSetListView(ListView):
    model = IndicatorSet
    template_name = "indicatorsets/indicatorSets.html"
    context_object_name = "indicatorsets"

    def get_queryset(self):
        try:
            return IndicatorSet.objects.all().prefetch_related(
                "geographic_scope",
            )
        except Exception as e:
            logger.error(f"Error fetching indicator sets: {e}")
            return IndicatorSet.objects.none()

    def get_related_indicators(self, queryset, indicator_set_ids: list):
        related_indicators = []
        for indicator in queryset.filter(
            indicator_set__id__in=indicator_set_ids
        ).prefetch_related("indicator_set", "source", "severity_pyramid_rungs"):
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
        fluview_geos = data.get("fluviewRegions", [])
        for indicator in indicators:
            if indicator["_endpoint"] == "covidcast":
                for geo in covidcast_geos:
                    geo_value = (
                        geo["id"].split(":")[1].lower()
                        if geo["geoType"] in ["nation", "state"]
                        else geo["id"].split(":")[1]
                    )
                    datasets.append(
                        {
                            "color": generate_random_color(),
                            "title": "value",
                            "params": {
                                "_endpoint": indicator["_endpoint"],
                                "data_source": indicator["data_source"],
                                "signal": indicator["indicator"],
                                "time_type": indicator["time_type"],
                                "geo_type": geo["geoType"],
                                "geo_value": geo_value,
                                "custom_title": generate_epivis_custom_title(
                                    indicator, geo["text"]
                                ),
                            },
                        }
                    )
            elif indicator["_endpoint"] == "fluview":
                for geo in fluview_geos:
                    datasets.append(
                        {
                            "color": generate_random_color(),
                            "title": FLUVIEW_INDICATORS_MAPPING.get(
                                indicator["indicator"], indicator["indicator"]
                            ),
                            "params": {
                                "_endpoint": indicator["_endpoint"] if indicator["data_source"] == "fluview" else "fluview_clinical",
                                "regions": geo["id"],
                                "custom_title": generate_epivis_custom_title(
                                    indicator, geo["text"]
                                ),
                            },
                        }
                    )
        datasets_json = json.dumps({"datasets": datasets})
        datasets_b64 = base64.b64encode(datasets_json.encode("ascii")).decode("ascii")
        response = {"epivis_url": f"{settings.EPIVIS_URL}#{datasets_b64}"}
        return JsonResponse(response)


def generate_export_data_url(request):
    if request.method == "POST":
        data_export_block = "To download data, please click on the link or copy/paste command(s) into your terminal: <br>{}"
        data_export_commands = []
        data = json.loads(request.body)
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
        indicators = data.get("indicators", [])
        covidcast_geos = data.get("covidCastGeographicValues", {})
        fluview_geos = data.get("fluviewRegions", [])
        api_key = data.get("apiKey", None)

        for indicator in indicators:
            if indicator["_endpoint"] == "covidcast":
                dates = get_epiweek(start_date, end_date) if indicator["time_type"] == "week" else [start_date, end_date]  # fmt: skip
                for type, values in covidcast_geos.items():
                    geo_values = ",".join(
                        [
                            (
                                value["id"].split(":")[1].lower()
                                if value["geoType"] in ["nation", "state"]
                                else value["id"].split(":")[1]
                            )
                            for value in values
                        ]
                    )
                    data_export_url = f"{settings.EPIDATA_URL}covidcast/csv?signal={indicator['data_source']}:{indicator['indicator']}&start_day={dates[0]}&end_day={dates[1]}&geo_type={type}&geo_values={geo_values}"
                    if api_key:
                        data_export_url += f"&api_key={api_key}"
                    data_export_commands.append(
                        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
                    )
        if fluview_geos:
            regions = ",".join([region["id"] for region in fluview_geos])
            date_from, date_to = get_epiweek(start_date, end_date)
            data_export_url = f"{settings.EPIDATA_URL}fluview/?regions={regions}&epiweeks={date_from}-{date_to}&format=csv"
            if api_key:
                data_export_url += f"&api_key={api_key}"
            data_export_commands.append(
                f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
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
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
        indicators = data.get("indicators", [])
        covidcast_geos = data.get("covidCastGeographicValues", {})
        fluview_geos = data.get("fluviewRegions", [])
        api_key = data.get("apiKey", None)

        preview_data = []

        for indicator in indicators:
            if indicator["_endpoint"] == "covidcast":
                time_values = f"{start_date}--{end_date}"
                if indicator["time_type"] == "week":
                    start_day, end_day = get_epiweek(start_date, end_date)
                    time_values = f"{start_day}-{end_day}"
                for geo_type, values in covidcast_geos.items():
                    geo_values = ",".join(
                        [
                            (
                                value["id"].split(":")[1].lower()
                                if value["geoType"] in ["nation", "state"]
                                else value["id"].split(":")[1]
                            )
                            for value in values
                        ]
                    )
                    params = {
                        "time_type": indicator["time_type"],
                        "time_values": time_values,
                        "data_source": indicator["data_source"],
                        "signal": indicator["indicator"],
                        "geo_type": geo_type,
                        "geo_values": geo_values,
                        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
                    }
                    response = requests.get(
                        f"{settings.EPIDATA_URL}covidcast", params=params
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if len(data["epidata"]):
                            preview_data.append(
                                {
                                    "epidata": data["epidata"][0],
                                    "result": data["result"],
                                    "message": data["message"],
                                }
                            )
                    elif response.status_code == 401:
                        preview_data = {
                            "epidata": [],
                            "result": -2,
                            "message": "API key does not exist. Register a new key at https://api.delphi.cmu.edu/epidata/admin/registration_form or contact delphi-support+privacy@andrew.cmu.edu to troubleshoot",
                        }
                        return JsonResponse(preview_data, safe=False)
        if fluview_geos:
            regions = ",".join([region["id"] for region in fluview_geos])
            date_from, date_to = get_epiweek(start_date, end_date)
            params = {
                "regions": regions,
                "epiweeks": f"{date_from}-{date_to}",
                "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
            }
            response = requests.get(f"{settings.EPIDATA_URL}fluview", params=params)
            if response.status_code == 200:
                data = response.json()
                if len(data["epidata"]):
                    preview_data.append(
                        {
                            "epidata": data["epidata"][0],
                            "result": data["result"],
                            "message": data["message"],
                        }
                    )
            elif response.status_code == 401:
                preview_data = {
                    "epidata": [],
                    "result": -2,
                    "message": "API key does not exist. Register a new key at https://api.delphi.cmu.edu/epidata/admin/registration_form or contact delphi-support+privacy@andrew.cmu.edu to troubleshoot",
                }
                return JsonResponse(preview_data, safe=False)
        return JsonResponse(preview_data, safe=False)


def create_query_code(request):
    if request.method == "POST":
        data = json.loads(request.body)
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
        indicators = data.get("indicators", [])
        covidcast_geos = data.get("covidCastGeographicValues", {})
        fluview_geos = data.get("fluviewRegions", [])
        api_key = data.get("apiKey", None)
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
                time_type = indicators[0].get("time_type")
                for geo_type, values in covidcast_geos.items():
                    geo_values = [
                        (
                            value["id"].split(":")[1].lower()
                            if value["geoType"] in ["nation", "state"]
                            else value["id"].split(":")[1]
                        )
                        for value in values
                    ]
                    if time_type == "week":
                        start_week, end_week = get_epiweek(start_date, end_date)
                        python_code_block = dedent(
                            f"""\
                            {data_source.replace('-', '_')}_{geo_type}_df = epidata.pub_covidcast(
                                data_source="{data_source}",
                                signals="{indicators_str}",
                                geo_type="{geo_type}",
                                time_type="{time_type}",
                                geo_values="{','.join(geo_values)}",
                                time_values=EpiRange({start_week}, {end_week}),
                            ).df()
                        """
                        )
                        python_code_blocks.append(python_code_block)
                        r_code_block = dedent(
                            f"""\
                            epidata_{data_source.replace("-", "_")}_{geo_type} <- pub_covidcast(
                                source = "{data_source}",
                                signals = "{indicators_str}",
                                geo_type = "{geo_type}",
                                time_type = "{time_type}",
                                geo_values = "{','.join(geo_values)}",
                                time_values = epirange({start_week}, {end_week})
                            )
                        """
                        )
                        r_code_blocks.append(r_code_block)
                    else:
                        python_code_block = dedent(
                            f"""\
                            {data_source.replace('-', '_')}_{geo_type}_df = epidata.pub_covidcast(
                                data_source="{data_source}",
                                signals="{indicators_str}",
                                geo_type="{geo_type}",
                                time_type="{time_type}",
                                geo_values="{','.join(geo_values)}",
                                time_values=EpiRange({start_date.replace("-", "")}, {end_date.replace("-", "")}),
                            ).df()
                        """
                        )
                        python_code_blocks.append(python_code_block)
                        r_code_block = dedent(
                            f"""\
                            epidata_{data_source.replace("-", "_")}_{geo_type} <- pub_covidcast(
                                source = "{data_source}",
                                signals = "{indicators_str}",
                                geo_type = "{geo_type}",
                                time_type = "{time_type}",
                                geo_values = "{','.join(geo_values)}",
                                time_values = epirange({start_date.replace("-", "")}, {end_date.replace("-", "")})
                            )
                        """
                        )
                        r_code_blocks.append(r_code_block)
        if fluview_geos:
            regions = ",".join([region["id"] for region in fluview_geos])
            start_week, end_week = get_epiweek(start_date, end_date)
            python_code_block = dedent(
                f"""\
                fluview_df = epidata.pub_fluview(
                    regions="{regions}",
                    epiweeks="{start_week}-{end_week}",
                ).df()
            """
            )
            python_code_blocks.append(python_code_block)
            r_code_block = dedent(
                f"""\
                epidata_{data_source.replace("-", "_")} <- pub_fluview(
                    regions = "{regions}",
                    epiweeks = epirange({start_week}, {end_week})
                )
            """
            )
            r_code_blocks.append(r_code_block)
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
            indicators_str = ",".join(indicator["indicator"] for indicator in indicators)
            response = requests.get(f"{settings.EPIDATA_URL}covidcast/geo_indicator_coverage", params={"data_source": data_source, "signals": indicators_str}, auth=("epidata", settings.EPIDATA_API_KEY))
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
            for geo_unit in GeographyUnit.objects.filter(geo_level__name__in=geo_levels).filter(geo_id__in=geo_unit_ids)
            .prefetch_related("geo_level")
            .order_by("level")
        ]
        grouped_geographic_granularities = group_by_property(
            geographic_granularities, "geoTypeDisplayName"
        )
        geographic_granularities = []
        for key, value in grouped_geographic_granularities.items():
            geographic_granularities.append({
                "text": key,
                "children": value,
            })
        return JsonResponse({"geographic_granularities": geographic_granularities}, safe=False)
