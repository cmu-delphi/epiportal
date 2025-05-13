import base64
import json
import logging
import requests
from bs4 import BeautifulSoup


from django.conf import settings
from django.http import JsonResponse
from django.views.generic import ListView

from base.models import Geography, GeographyUnit
from indicatorsets.filters import IndicatorSetFilter
from indicatorsets.forms import IndicatorSetFilterForm
from indicatorsets.models import IndicatorSet
from indicatorsets.utils import (
    generate_epivis_custom_title,
    generate_random_color,
    get_epiweek,
)

logger = logging.getLogger(__name__)

FILTERS_DESCRIPTIONS = {
    "pathogens": "List only indicators related to these pathogens, syndromes or diseases.",
    "geographic_scope": "List only indicators that cover any of the selected countries or world regions.",
    "geographic_levels": "List only indicators that are available at any of the selected geographic levels.",
    "severity_pyramid_rungs": "List only indicators that are directly related to any of the selected rungs.",
    "original_data_provider": "List only indicator that are based on data from one of the selected sources.",
    "temporal_granularity": "The temporal resolution of this indicator (not of the reporting).  Might not be the same as Reporting Cadence (e.g. a daily indicator may be reported only once a week).",
    "temporal_scope_end": "The latest date for which this indicator is available.",
    "location_search": "Enter one or more locations for which you are looking for indicator coverage, or leave empty for all locations.  Start entering a location name to see all compatible locations.  Auto-complete with [Tab] or [Enter].  Currently works only for U.S. locations.",
}

COLUMNS_DESCRIPTIONS = {
    "name": "Hover over the indicator's name to see a brief description.",
    "geographic_coverage": "The countries or world regions covered by this indicator.  These are typically covered at finer geographic levels / jurisdictions.",
    "geographic_levels": "All the geographic levels at which this indicator is available.  Larger jurisdictions are often based on aggregation of data from constituent jurisdictions.",
    "temporal_scope_start": "The earliest date for which this indicator is available.",
    "temporal_scope_end": "The latest date for which this indicator is available.",
    "temporal_granularity": "The temporal resolution of this indicator (not of the reporting).  Might not be the same as Reporting Cadence (e.g. a daily indicator may be reported only once a week).",
    "reporting_cadence": "The frequency with which this indicator is reported.  This may be different from the temporal granularity.",
    "reporting_lag": 'The number of days from the last day of a reported period until the first reported value for that period is usually available in Delphi Epidata.  E.g. if reporting U.S. epiweeks (Sunday through Saturday), and the first report is usually available in Delphi Epidata on the following Friday, The Reporting Lag is 6. By "usually available" we mean when it\'s "supposed to be" available based on our current understanding of the data provider\'s operations and Delphi\'s ingestion pipeline.  That is the date on which we think of the data as showing up "on time", and relative to which we track unusual delays.',
    "revision_cadende": 'How frequently are revised values (e.g. "backfill") usually reported (if any)?',
    "population": 'The population or demographic group reflected by the indicator ("All" means the entire population)',
    "population_stratifiers": "What population or demographic stratifiers are available, if any?",
    "surveillance_categories": "Which surveillance categories or rungs in the Severity Pyramid does this indicator attempt to track?  Some indicators may approximately track multiple categories.",
    "original_data_provider": "The owner or supplier of the original or raw data used to create this indicator.",
    "pre_processing": "Brief description of main data processing used in creating this set of indicators, including smoothing and aggregation.  For more details, see the documentation.",
    "censoring": "Is any of the data being censored (e.g. small counts)?  If so how, and how much impact does it have (e.g. approximate fraction of values affected).",
    "dua_required": "Applicable data use terms (may apply even to publicly accessible indicators).",
}

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
        context["indicator_sets"] = filter.qs
        context["related_indicators"] = json.dumps(
            self.get_related_indicators(
                filter.indicators_qs, filter.qs.values_list("id", flat=True)
            )
        )
        context["filters_descriptions"] = FILTERS_DESCRIPTIONS
        context["columns_descriptions"] = COLUMNS_DESCRIPTIONS
        context["header_description"] = HEADER_DESCRIPTION
        context["available_geographies"] = Geography.objects.filter(
            used_in="indicators"
        )
        context["geographic_granularities"] = [
            {
                "id": str(geo_unit.geo_id),
                "geoType": geo_unit.geo_level.name,
                "text": geo_unit.display_name,
            }
            for geo_unit in GeographyUnit.objects.all().prefetch_related("geo_level")
        ]
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
                        geo["id"].lower()
                        if geo["geoType"] in ["nation", "state"]
                        else geo["id"]
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
                                "_endpoint": indicator["_endpoint"],
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

        for indicator in indicators:
            if indicator["_endpoint"] == "covidcast":
                dates = get_epiweek(start_date, end_date) if indicator["time_type"] == "week" else [start_date, end_date]  # fmt: skip
                for type, values in covidcast_geos.items():
                    geo_values = ",".join(
                        [
                            (
                                value["id"].lower()
                                if value["geoType"] in ["nation", "state"]
                                else value["id"]
                            )
                            for value in values
                        ]
                    )
                    data_export_url = f"{settings.EPIDATA_URL}covidcast/csv?signal={indicator['data_source']}:{indicator['indicator']}&start_day={dates[0]}&end_day={dates[1]}&geo_type={type}&geo_values={geo_values}"
                    data_export_commands.append(
                        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
                    )
        if fluview_geos:
            regions = ",".join([region["id"] for region in fluview_geos])
            date_from, date_to = get_epiweek(start_date, end_date)
            data_export_url = f"{settings.EPIDATA_URL}fluview/?regions={regions}&epiweeks={date_from}-{date_to}&format=csv"
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
                                value["id"].lower()
                                if value["geoType"] in ["nation", "state"]
                                else value["id"]
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
        if fluview_geos:
            regions = ",".join([region["id"] for region in fluview_geos])
            date_from, date_to = get_epiweek(start_date, end_date)
            params = {
                "regions": regions,
                "epiweeks": f"{date_from}-{date_to}",
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
        return JsonResponse(preview_data, safe=False)


def create_query_code(request):
    if request.method == "POST":
        data = json.loads(request.body)
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
        indicators = data.get("indicators", [])
        covidcast_geos = data.get("covidCastGeographicValues", {})
        python_code_blocks = []
        r_code_blocks = []
        for indicator in indicators:
            if indicator["_endpoint"] == "covidcast":
                for geo_type, values in covidcast_geos.items():
                    geo_values = [
                        (
                            value["id"].lower()
                            if value["geoType"] in ["nation", "state"]
                            else value["id"]
                        )
                        for value in values
                    ]
                    r_geos = ", ".join(f'"{str(geo)}"' for geo in geo_values)
                    if indicator["time_type"] == "week":
                        start_day, end_day = get_epiweek(start_date, end_date)
                        python_code_block = (
                            '<pre class="code-block">'
                            + "<code>from epiweeks import Week<br>"
                            + "import covidcast<br><br>"
                            + f'data = covidcast.signal("{indicator["data_source"]}", "{indicator["indicator"]}", Week({int(start_day[:4])}, {int(start_day[4:])}), Week({int(end_day[:4])}, {int(end_day[4:])}), "{geo_type}", {json.dumps([str(geo) for geo in geo_values])})'
                            + "</code>"
                            + "</pre>"
                        )
                        python_code_blocks.append(python_code_block)
                        r_code_block = (
                            '<pre class="code-block">'
                            + "<code>libary(covidcast)<br><br>"
                            + f'cc_data <- covidcast_signal(data_source = "{indicator["data_source"]}", signal = "{indicator["indicator"]}", start_day = "{start_day}", end_day = "{end_day}", geo_type = "{geo_type}", geo_values = c({r_geos}))'
                            + "</code>"
                            + "</pre>"
                        )
                        r_code_blocks.append(r_code_block)
                    else:
                        start_day = tuple(map(int, start_date.split("-")))
                        end_day = tuple(map(int, end_date.split("-")))
                        python_code_block = (
                            '<pre class="code-block">'
                            + "<code>from datetime import date<br>"
                            + "import covidcast<br><br>"
                            + f'data = covidcast.signal("{indicator["data_source"]}", "{indicator["indicator"]}", date{str(start_day)}, date{str(end_day)}, "{geo_type}", {json.dumps([str(geo) for geo in geo_values])})'
                            + "</code>"
                            + "</pre>"
                        )
                        python_code_blocks.append(python_code_block)
                        r_code_block = (
                            '<pre class="code-block">'
                            + "<code>libary(covidcast)<br><br>"
                            + f'cc_data <- covidcast_signal(data_source = "{indicator["data_source"]}", signal = "{indicator["indicator"]}", start_day = "{start_date}", end_day = "{end_date}", geo_type = "{geo_type}", geo_values = c({r_geos}))'
                            + "</code>"
                            + "</pre>"
                        )
                        r_code_blocks.append(r_code_block)
        return JsonResponse(
            {"python_code_blocks": python_code_blocks, "r_code_blocks": r_code_blocks},
            safe=False,
        )
