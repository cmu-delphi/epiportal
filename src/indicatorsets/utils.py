import ast
import random
from collections import defaultdict
from datetime import datetime as dtime
from textwrap import dedent
from urllib.parse import urlencode
import csv
import io
from itertools import islice

import requests
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from epiportal.utils import get_client_ip
from epiweeks import Week
from delphi_utils import get_structured_logger

from indicatorsets.models import OriginalDataProvider

FLUVIEW_INDICATORS_MAPPING = {"wili": "%wILI", "ili": "%ILI"}

logger = get_structured_logger("indicatorsets.utils")

form_data_logger = get_structured_logger("form_data_logger")
form_stats_logger = get_structured_logger("form_stats_logger")

INVALID_API_KEY_MESSAGE = (
    "API key does not exist. Register a new key at "
    "https://api.delphi.cmu.edu/epidata/admin/registration_form or contact "
    "delphi-support+privacy@andrew.cmu.edu to troubleshoot"
)

NO_DATA_MESSAGE = (
    "No data found for the selected parameters. Try adjusting the date range, "
    "indicators, or locations."
)


class InvalidApiKeyError(Exception):
    """Raised when an Epidata request returns 401 Unauthorized."""


def list_to_dict(lst):
    result = {}
    for item in lst:
        key, value = item.split(":")
        if key in result:
            if isinstance(result[key], list):
                result[key].append(value)
            else:
                result[key] = [result[key], value]
        else:
            result[key] = [value]
    return result


def get_indicators_based_on_geo_epidata(geos):
    indicators = []
    for geo_type, geo_values in geos.items():
        url = f"{settings.EPIDATA_URL}covidcast/geo_coverage"
        params = {
            "geo": f"{geo_type}:{','.join(geo_values)}",
            "api_key": settings.EPIDATA_API_KEY,
        }
        try:
            response = requests.get(url, params=params, timeout=(5, 30))
            response.raise_for_status()
            indicators.extend(response.json()["epidata"])
        except requests.RequestException:
            logger.exception("Error getting geo coverage", extra={"geos": geos})
            continue
    return indicators


def get_indicators_based_on_geo_epidata_v5(geos):
    indicators = []
    for geo_type, geo_values in geos.items():
        url = f"{settings.EPIDATA_V5_URL}metadata/geo_signals"
        params = {"geo_type": geo_type}
        for geo_value in geo_values:
            params["geo_value"] = geo_value.lower()
            try:
                response = requests.get(url, params=params, timeout=(5, 30))
                response.raise_for_status()
                indicators.extend(response.json()["values"])
            except requests.RequestException:
                logger.exception("Error getting geo coverage", extra={"geos": geos})
                continue
    return indicators


def get_list_of_indicators_filtered_by_geo(geos):
    indicators = []
    geos = list_to_dict(ast.literal_eval(geos))
    indicators.extend(get_indicators_based_on_geo_epidata(geos))
    indicators.extend(get_indicators_based_on_geo_epidata_v5(geos))
    return indicators


def generate_epivis_custom_title(indicator, geo_value, extra_keys=None):
    title = f"{indicator['indicator_set_short_name']}:{indicator['indicator']} : {geo_value}"
    if extra_keys:
        title += f" ({extra_keys})"
    return title


def generate_random_color():
    """
    Generate a random color in hexadecimal format.
    """
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))


def get_epiweek(start_date, end_date):
    start_date = dtime.strptime(start_date, "%Y-%m-%d")
    start_date = Week.fromdate(start_date)
    start_date = f"{start_date.year}{start_date.week if start_date.week >= 10 else '0' + str(start_date.week)}"
    end_date = dtime.strptime(end_date, "%Y-%m-%d")
    end_date = Week.fromdate(end_date)
    end_date = f"{end_date.year}{end_date.week if end_date.week >= 10 else '0' + str(end_date.week)}"
    return [start_date, end_date]


def parse_original_data_provider_ids(query_dict):
    raw_values = []

    for odp_value in query_dict.getlist("odp"):
        raw_values.extend(v.strip() for v in odp_value.split(",") if v.strip())

    raw_values.extend(query_dict.getlist("original_data_provider"))

    ids = []
    names = []
    for value in raw_values:
        if str(value).isdigit():
            ids.append(int(value))
        elif value:
            names.append(value)

    if names:
        ids.extend(
            OriginalDataProvider.objects.filter(name__in=names).values_list(
                "id", flat=True
            )
        )

    # dedupe, preserve order
    seen = set()
    return [i for i in ids if not (i in seen or seen.add(i))]


def sort_data_providers(providers):
    """Sort providers alphabetically, with names containing 'other' at the end."""
    sorted_providers = sorted(providers, key=lambda p: p.name.lower())
    tail = [
        provider for provider in sorted_providers if "other" in provider.name.lower()
    ]
    head = [
        provider
        for provider in sorted_providers
        if "other" not in provider.name.lower()
    ]
    return head + tail


def get_grouped_original_data_provider_choices():
    providers = (
        OriginalDataProvider.objects.filter(indicator_sets__isnull=False)
        .distinct()
        .order_by("display_order", "name")
    )
    provider_list = list(providers)
    return {
        "main": sort_data_providers(
            [p for p in provider_list if p.group == "individual"]
        ),
        "groups": [
            {
                "label": "U.S. Government",
                "providers": sort_data_providers(
                    [p for p in provider_list if p.group == "us_government"]
                ),
            },
            {
                "label": "U.S. States",
                "providers": sort_data_providers(
                    [p for p in provider_list if p.group == "us_states"]
                ),
            },
        ],
        "all": sort_data_providers(provider_list),
    }


def group_by_property(list_of_dicts, property):
    """Groups a list of dictionaries by a specified property.

    Args:
        list_of_dicts: A list of dictionaries.
        property: The property to group by.

    Returns:
        A dictionary where keys are the unique values of the property,
        and values are lists of dictionaries with that property value.
    """
    grouped_dict = defaultdict(list)
    for item in list_of_dicts:
        grouped_dict[item[property]].append(item)
    return dict(grouped_dict)


def generate_covidcast_dataset_epivis(indicator, covidcast_geos):
    datasets = []
    for geo_type in covidcast_geos.keys():
        for geo in covidcast_geos[geo_type]:
            if geo["id"] not in indicator.get("notCoveredGeos", []):
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
                            "geo_type": geo_type,
                            "geo_value": geo_value,
                            "custom_title": generate_epivis_custom_title(
                                indicator, geo["text"]
                            ),
                        },
                    }
                )
    return datasets


def generate_fluview_dataset_epivis(indicator, fluview_geos):
    datasets = []
    for geo in fluview_geos:
        if geo["id"] not in indicator.get("notCoveredGeos", []):
            datasets.append(
                {
                    "color": generate_random_color(),
                    "title": FLUVIEW_INDICATORS_MAPPING.get(
                        indicator["indicator"], indicator["indicator"]
                    ),
                    "params": {
                        "_endpoint": (
                            indicator["_endpoint"]
                            if indicator["data_source"] == "fluview"
                            else "fluview_clinical"
                        ),
                        "regions": geo["id"],
                        "custom_title": generate_epivis_custom_title(
                            indicator, geo["text"]
                        ),
                    },
                }
            )
    return datasets


def generate_nidss_flu_dataset_epivis(indicator, nidss_flu_geos):
    datasets = []
    for geo in nidss_flu_geos:
        datasets.append(
            {
                "color": generate_random_color(),
                "title": indicator["indicator"],
                "params": {
                    "_endpoint": indicator["_endpoint"],
                    "regions": geo["id"],
                    "custom_title": generate_epivis_custom_title(
                        indicator, geo["text"]
                    ),
                },
            }
        )
    return datasets


def generate_nidss_dengue_dataset_epivis(indicator, nidss_dengue_geos):
    datasets = []
    for geo in nidss_dengue_geos:
        datasets.append(
            {
                "color": generate_random_color(),
                "title": indicator["indicator"],
                "params": {
                    "_endpoint": indicator["_endpoint"],
                    "locations": geo["id"],
                    "custom_title": generate_epivis_custom_title(
                        indicator, geo["text"]
                    ),
                },
            }
        )
    return datasets


def generate_flusurv_dataset_epivis(indicator, flusurv_geos):
    datasets = []
    for geo in flusurv_geos:
        datasets.append(
            {
                "color": generate_random_color(),
                "title": indicator["indicator"],
                "params": {
                    "_endpoint": indicator["_endpoint"],
                    "locations": geo["id"],
                    "custom_title": generate_epivis_custom_title(
                        indicator, geo["text"]
                    ),
                },
            }
        )
    return datasets


def generate_pophive_dataset_epivis(indicator, pophive_geos, pophive_age_group):
    datasets = []
    for geo in pophive_geos:
        datasets.append(
            {
                "color": generate_random_color(),
                "title": "value",
                "params": {
                    "_endpoint": indicator["_endpoint"],
                    "source": indicator["data_source"],
                    "signal": indicator["indicator"],
                    "geo_type": geo["geo_type"],
                    "geo_value": geo["id"],
                    "custom_title": generate_epivis_custom_title(
                        indicator,
                        geo["text"],
                        f"age_group:{pophive_age_group[0]['id']}",
                    ),
                    "extra_keys": f"age_group:{pophive_age_group[0]['id']}",
                },
            }
        )
    return datasets


def generate_nwss_dataset_epivis(
    indicator,
    geographic_type,
    geographic_value,
    source,
    fill_method,
):
    datasets = []
    geo_values = ",".join(geographic_value).replace(" ", "").split(",")
    for geo_value in geo_values:
        for s in source:
            datasets.append(
                {
                    "color": generate_random_color(),
                    "title": "value",
                    "params": {
                        "_endpoint": indicator["_endpoint"],
                        "source": "nwss",
                        "signal": indicator["indicator"],
                        "geo_type": geographic_type,
                        "geo_value": geo_value,
                        "fill_method": fill_method,
                        "custom_title": generate_epivis_custom_title(
                            indicator, geo_value, s["id"]
                        ),
                        "extra_keys": f"nwss_source:{s['id']}",
                    },
                }
            )
    return datasets


def generate_covidcast_indicators_export_url(
    indicators, start_date, end_date, covidcast_geos, api_key, data_format
):
    data_export_commands = []
    for indicator in indicators:
        if indicator["_endpoint"] == "covidcast":
            if indicator["time_type"] == "week":
                dates = get_epiweek(start_date, end_date)
                time_values = f"{dates[0]}-{dates[1]}"
            else:
                dates = [start_date, end_date]
                time_values = f"{start_date}--{end_date}"
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
                label = f"{indicator.get('display_name') or indicator['indicator']} ({type})"
                check_params = {
                    "time_type": indicator["time_type"],
                    "time_values": time_values,
                    "data_source": indicator["data_source"],
                    "signal": indicator["indicator"],
                    "geo_type": type,
                    "geo_values": geo_values,
                    "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
                }
                if not has_epidata_results(
                    f"{settings.EPIDATA_URL}covidcast", check_params
                ):
                    data_export_commands.append(
                        f'<span class="text-muted">No data found for {label}. Export skipped.</span>'
                    )
                    continue
                data_export_url = f"{settings.EPIDATA_URL}covidcast/csv?signal={indicator['data_source']}:{indicator['indicator']}&start_day={dates[0]}&end_day={dates[1]}&geo_type={type}&geo_values={geo_values}&format={data_format}"
                if data_format == "csv":
                    data_export_url += f"&header=true"
                if api_key:
                    data_export_url += f"&api_key={api_key}"
                data_export_commands.append(
                    f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
                )
    return data_export_commands


def generate_fluview_indicators_export_url(
    fluview_geos, start_date, end_date, api_key, data_format
):
    data_export_commands = []
    regions = ",".join([region["id"] for region in fluview_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    data_export_url = f"{settings.EPIDATA_URL}fluview/?regions={regions}&epiweeks={date_from}-{date_to}&format={data_format}"
    if data_format == "csv":
        data_export_url += f"&header=true"
    if api_key:
        data_export_url += f"&api_key={api_key}"
    data_export_commands.append(
        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
    )
    return data_export_commands


def generate_nidss_flu_export_url(
    nidss_flu_geos, start_date, end_date, api_key, data_format
):
    data_export_commands = []
    regions = ",".join([region["id"] for region in nidss_flu_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    data_export_url = f"{settings.EPIDATA_URL}nidss_flu/?regions={regions}&epiweeks={date_from}-{date_to}&format={data_format}"
    if data_format == "csv":
        data_export_url += f"&header=true"
    if api_key:
        data_export_url += f"&api_key={api_key}"
    data_export_commands.append(
        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
    )
    return data_export_commands


def generate_nidss_dengue_export_url(
    nidss_dengue_geos, start_date, end_date, api_key, data_format
):
    data_export_commands = []
    regions = ",".join([region["id"] for region in nidss_dengue_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    data_export_url = f"{settings.EPIDATA_URL}nidss_dengue/?locations={regions}&epiweeks={date_from}-{date_to}&format={data_format}"  # fmt: skip
    if data_format == "csv":
        data_export_url += f"&header=true"
    if api_key:
        data_export_url += f"&api_key={api_key}"
    data_export_commands.append(
        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
    )
    return data_export_commands


def generate_flusurv_export_url(
    flusurv_geos, start_date, end_date, api_key, data_format
):
    data_export_commands = []
    regions = ",".join([region["id"] for region in flusurv_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    data_export_url = f"{settings.EPIDATA_URL}flusurv/?locations={regions}&epiweeks={date_from}-{date_to}&format={data_format}"  # fmt: skip
    if data_format == "csv":
        data_export_url += "&header=true"
    if api_key:
        data_export_url += f"&api_key={api_key}"
    data_export_commands.append(
        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
    )
    return data_export_commands


def generate_pophive_export_url(
    indicators,
    start_date,
    end_date,
    pophive_geos,
    pophive_age_group,
    api_key,
    data_format,
):
    data_export_commands = []
    for indicator in indicators:
        if indicator["_endpoint"] == "pophive":
            for geo in pophive_geos:
                label = f"{indicator.get('display_name') or indicator['indicator']} ({geo['text']})"
                check_params = {
                    "source": "pophive",
                    "signal": indicator["indicator"],
                    "geo_type": geo["geo_type"],
                    "geo_value": geo["id"],
                    "time_values": f"{start_date}:{end_date}",
                    "extra_keys": f"age_group:{pophive_age_group[0]['id']}",
                    "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
                }
                if not has_epidata_results(
                    f"{settings.EPIDATA_V5_URL}viz/", check_params
                ):
                    data_export_commands.append(
                        f'<span class="text-muted">No data found for {label}. Export skipped.</span>'
                    )
                    continue
                data_export_url = f"{settings.EPIDATA_V5_URL}viz/?source=pophive&signal={indicator['indicator']}&geo_type={geo['geo_type']}&geo_value={geo['id']}&time_values={start_date}:{end_date}&extra_keys=age_group:{pophive_age_group[0]['id']}&format={data_format}"
                if data_format == "csv":
                    data_export_url += "&header=true"
                if api_key:
                    data_export_url += f"&api_key={api_key}"
                filename = f"{indicator['indicator']}_{geo['geo_type']}_{geo['id']}.{data_format}"
                download_params = {
                    "source": "pophive",
                    "signal": indicator["indicator"],
                    "geo_type": geo["geo_type"],
                    "geo_value": geo["id"],
                    "time_values": f"{start_date}:{end_date}",
                    "extra_keys": f"age_group:{pophive_age_group[0]['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                    "filename": filename,
                }
                if api_key:
                    download_params["api_key"] = api_key
                download_url = (
                    f"{reverse('download_export')}?{urlencode(download_params)}"
                )
                data_export_commands.append(
                    f'curl -o {filename} <a href="{download_url}" download="{filename}">{data_export_url}</a>'
                )
    return data_export_commands


def generate_nwss_export_url(
    indicators,
    start_date,
    end_date,
    nwss_geographic_value,
    nwss_source,
    nwss_fill_method,
    api_key,
    data_format,
):
    data_export_commands = []
    geo_value = ",".join(nwss_geographic_value)
    for indicator in indicators:
        for source in nwss_source:
            if indicator["_endpoint"] == "nwss":
                label = (
                    f"{indicator.get('display_name') or indicator['indicator']} "
                    f"(source: {source['id']})"
                )
                check_params = {
                    "source": "nwss",
                    "signal": indicator["indicator"],
                    "geo_type": "sewershed",
                    "geo_value": geo_value,
                    "fill_method": nwss_fill_method,
                    "time_values": f"{start_date}:{end_date}",
                    "extra_keys": f"nwss_source:{source['id']}",
                    "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
                }
                if not has_epidata_results(
                    f"{settings.EPIDATA_V5_URL}viz/", check_params
                ):
                    data_export_commands.append(
                        f'<span class="text-muted">No data found for {label}. Export skipped.</span>'
                    )
                    continue
                data_export_url = f"{settings.EPIDATA_V5_URL}viz/?source=nwss&signal={indicator['indicator']}&geo_type=sewershed&geo_value={geo_value}&fill_method={nwss_fill_method}&time_values={start_date}:{end_date}&extra_keys=nwss_source:{source['id']}&format={data_format}"
                if data_format == "csv":
                    data_export_url += "&header=true"
                if api_key:
                    data_export_url += f"&api_key={api_key}"
                filename = (
                    f"{indicator['indicator']}_source_{source['id']}.{data_format}"
                )
                download_params = {
                    "source": "nwss",
                    "signal": indicator["indicator"],
                    "geo_type": "sewershed",
                    "geo_value": geo_value,
                    "fill_method": nwss_fill_method,
                    "time_values": f"{start_date}:{end_date}",
                    "extra_keys": f"nwss_source:{source['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                    "filename": filename,
                }
                if api_key:
                    download_params["api_key"] = api_key
                download_url = (
                    f"{reverse('download_export')}?{urlencode(download_params)}"
                )
                data_export_commands.append(
                    f'curl -o {filename} <a href="{download_url}" download="{filename}">{data_export_url}</a>'
                )
    return data_export_commands


def get_preview_data(response, data_format, no_data_message=NO_DATA_MESSAGE):
    if data_format == "json":
        data = response.json()
        if isinstance(data, dict) and "epidata" in data:
            if data["epidata"]:
                return {
                    "epidata": data["epidata"][0],
                    "result": data["result"],
                    "message": data["message"],
                }
            return {"message": no_data_message}
        if isinstance(data, list):
            return data[0] if data else {"message": no_data_message}
        return {"message": no_data_message}
    elif data_format == "csv":
        csv_file = io.StringIO(response.text)
        csv_reader = csv.reader(csv_file, delimiter=",")
        data = [row for row in islice(csv_reader, 5)]
        if len(data) <= 1:
            return {"message": no_data_message}
        return data


def has_epidata_results(url, params):
    """Check whether an Epidata endpoint has any results for the given params."""
    check_params = {**params, "format": "json"}
    try:
        response = requests.get(url, params=check_params, timeout=(5, 30))
        if response.status_code == 401:
            raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Error checking data availability", extra={"url": url})
        return False
    data = response.json()
    if isinstance(data, dict) and "epidata" in data:
        return bool(data["epidata"])
    if isinstance(data, list):
        return bool(data)
    return False


def preview_covidcast_data(
    indicators, start_date, end_date, covidcast_geos, api_key, data_format
):
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
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                }
                try:
                    response = requests.get(
                        f"{settings.EPIDATA_URL}covidcast",
                        params=params,
                        timeout=(5, 30),
                    )
                    if response.status_code == 401:
                        raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
                    response.raise_for_status()
                except requests.RequestException:
                    logger.exception(
                        "Error getting covidcast data",
                        extra={"signal": indicator["indicator"], "geo_type": geo_type},
                    )
                    continue

                label = f"{indicator.get('display_name') or indicator['indicator']} ({geo_type})"
                preview_data.append(
                    get_preview_data(
                        response,
                        data_format,
                        no_data_message=f"No data found for {label}.",
                    )
                )
    return preview_data


def preview_fluview_data(fluview_geos, start_date, end_date, api_key, data_format):
    preview_data = []
    regions = ",".join([region["id"] for region in fluview_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    params = {
        "regions": regions,
        "epiweeks": f"{date_from}-{date_to}",
        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
        "format": data_format,
        "header": "true" if data_format == "csv" else "false",
    }
    try:
        response = requests.get(
            f"{settings.EPIDATA_URL}fluview", params=params, timeout=(5, 30)
        )
        if response.status_code == 401:
            raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Error getting fluview data", extra={"regions": regions})
        return preview_data
    preview_data.append(get_preview_data(response, data_format))
    return preview_data


def preview_nidss_flu_data(nidss_flu_geos, start_date, end_date, api_key, data_format):
    preview_data = []
    regions = ",".join([region["id"] for region in nidss_flu_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    params = {
        "regions": regions,
        "epiweeks": f"{date_from}-{date_to}",
        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
        "format": data_format,
        "header": "true" if data_format == "csv" else "false",
    }
    try:
        response = requests.get(
            f"{settings.EPIDATA_URL}nidss_flu", params=params, timeout=(5, 30)
        )
        if response.status_code == 401:
            raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Error getting nidss_flu data", extra={"regions": regions})
        return preview_data
    preview_data.append(get_preview_data(response, data_format))
    return preview_data


def preview_nidss_dengue_data(
    nidss_dengue_geos, start_date, end_date, api_key, data_format
):
    preview_data = []
    regions = ",".join([region["id"] for region in nidss_dengue_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    params = {
        "locations": regions,
        "epiweeks": f"{date_from}-{date_to}",
        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
        "format": data_format,
        "header": "true" if data_format == "csv" else "false",
    }
    try:
        response = requests.get(
            f"{settings.EPIDATA_URL}nidss_dengue", params=params, timeout=(5, 30)
        )
        if response.status_code == 401:
            raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Error getting nidss_dengue data", extra={"regions": regions})
        return preview_data
    preview_data.append(get_preview_data(response, data_format))
    return preview_data


def preview_flusurv_data(flusurv_geos, start_date, end_date, api_key, data_format):
    preview_data = []
    regions = ",".join([region["id"] for region in flusurv_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    params = {
        "locations": regions,
        "epiweeks": f"{date_from}-{date_to}",
        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
        "format": data_format,
        "header": "true" if data_format == "csv" else "false",
    }
    try:
        response = requests.get(
            f"{settings.EPIDATA_URL}flusurv", params=params, timeout=(5, 30)
        )
        if response.status_code == 401:
            raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Error getting flusurv data", extra={"regions": regions})
        return preview_data
    preview_data.append(get_preview_data(response, data_format))
    return preview_data


def preview_pophive_data(
    indicators,
    start_date,
    end_date,
    pophive_geos,
    pophive_age_group,
    api_key,
    data_format,
):
    preview_data = []
    for indicator in indicators:
        if indicator["_endpoint"] == "pophive":
            for geo in pophive_geos:
                params = {
                    "source": "pophive",
                    "signal": indicator["indicator"],
                    "geo_type": geo["geo_type"],
                    "geo_value": geo["id"],
                    "time_values": f"{start_date}:{end_date}",
                    "extra_keys": f"age_group:{pophive_age_group[0]['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                    "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
                }
                try:
                    response = requests.get(
                        f"{settings.EPIDATA_V5_URL}viz/", params=params, timeout=(5, 30)
                    )
                    if response.status_code == 401:
                        raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
                    response.raise_for_status()
                except requests.RequestException:
                    logger.exception(
                        "Error getting pophive data",
                        extra={
                            "signal": indicator["indicator"],
                            "geo_type": geo["geo_type"],
                            "geo_value": geo["id"],
                        },
                    )
                    continue
                label = f"{indicator.get('display_name') or indicator['indicator']} ({geo['text']})"
                preview_data.append(
                    get_preview_data(
                        response,
                        data_format,
                        no_data_message=f"No data found for {label}.",
                    )
                )
    return preview_data


def preview_nwss_data(
    indicators,
    start_date,
    end_date,
    nwss_geographic_value,
    nwss_source,
    nwss_fill_method,
    api_key,
    data_format,
):
    preview_data = []
    geo_value = ",".join(nwss_geographic_value)
    for indicator in indicators:
        for source in nwss_source:
            if indicator["_endpoint"] == "nwss":
                params = {
                    "source": "nwss",
                    "signal": indicator["indicator"],
                    "geo_type": "sewershed",
                    "geo_value": geo_value,
                    "fill_method": nwss_fill_method,
                    "time_values": f"{start_date}:{end_date}",
                    "extra_keys": f"nwss_source:{source['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                    "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
                }
                try:
                    response = requests.get(
                        f"{settings.EPIDATA_V5_URL}viz/", params=params, timeout=(5, 30)
                    )
                    if response.status_code == 401:
                        raise InvalidApiKeyError(INVALID_API_KEY_MESSAGE)
                    response.raise_for_status()
                except requests.RequestException:
                    logger.exception(
                        "Error getting nwss data",
                        extra={
                            "signal": indicator["indicator"],
                            "geo_value": geo_value,
                        },
                    )
                    continue
                label = (
                    f"{indicator.get('display_name') or indicator['indicator']} "
                    f"(source: {source['id']})"
                )
                preview_data.append(
                    get_preview_data(
                        response,
                        data_format,
                        no_data_message=f"No data found for {label}.",
                    )
                )
    return preview_data


def generate_query_code_covidcast(
    indicators,
    covidcast_geos,
    start_date,
    end_date,
    data_source,
    indicators_str,
):
    python_code_blocks = []
    r_code_blocks = []
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
    return python_code_blocks, r_code_blocks


def generate_query_code_fluview(fluview_geos, start_date, end_date):
    python_code_blocks = []
    r_code_blocks = []
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
        epidata_fluview <- pub_fluview(
            regions = "{regions}",
            epiweeks = epirange({start_week}, {end_week})
        )
    """
    )
    r_code_blocks.append(r_code_block)
    return python_code_blocks, r_code_blocks


def generate_query_code_nidss_flu(nidss_flu_geos, start_date, end_date):
    python_code_blocks = []
    r_code_blocks = []
    regions = ",".join([region["id"] for region in nidss_flu_geos])
    start_week, end_week = get_epiweek(start_date, end_date)
    python_code_block = dedent(
        f"""\
        nidss_flu_df = epidata.pub_nidss_flu(
            regions="{regions}",
            epiweeks="{start_week}-{end_week}",
        ).df()
    """
    )
    python_code_blocks.append(python_code_block)
    r_code_block = dedent(
        f"""\
        epidata_nidss_flu <- pub_nidss_flu(
            regions = "{regions}",
            epiweeks = epirange({start_week}, {end_week})
        )
    """
    )
    r_code_blocks.append(r_code_block)
    return python_code_blocks, r_code_blocks


def generate_query_code_nidss_dengue(nidss_dengue_geos, start_date, end_date):
    python_code_blocks = []
    r_code_blocks = []
    regions = ",".join([region["id"] for region in nidss_dengue_geos])
    start_week, end_week = get_epiweek(start_date, end_date)
    python_code_block = dedent(
        f"""\
        nidss_dengue_df = epidata.pub_nidss_dengue(
            locations="{regions}",
            epiweeks="{start_week}-{end_week}",
        ).df()
    """
    )
    python_code_blocks.append(python_code_block)
    r_code_block = dedent(
        f"""\
        epidata_nidss_dengue <- pub_nidss_dengue(
            locations = "{regions}",
            epiweeks = epirange({start_week}, {end_week})
        )
    """
    )
    r_code_blocks.append(r_code_block)

    return python_code_blocks, r_code_blocks


def generate_query_code_flusurv(flusurv_geos, start_date, end_date):
    python_code_blocks = []
    r_code_blocks = []
    regions = ",".join([region["id"] for region in flusurv_geos])
    start_week, end_week = get_epiweek(start_date, end_date)
    python_code_block = dedent(
        f"""\
        flusurv_df = epidata.pub_flusurv(
            locations="{regions}",
            epiweeks="{start_week}-{end_week}",
        ).df()
    """
    )
    python_code_blocks.append(python_code_block)
    r_code_block = dedent(
        f"""\
        epidata_flusurv <- pub_flusurv(
            locations = "{regions}",
            epiweeks = epirange({start_week}, {end_week})
        )
    """
    )
    r_code_blocks.append(r_code_block)

    return python_code_blocks, r_code_blocks


def generate_query_code_pophive(
    indicators, start_date, end_date, pophive_geos, pophive_age_group
):
    python_code_blocks = ["import requests"]
    r_code_blocks = ["library(httr)", "library(jsonlite)"]
    for indicator in indicators:
        if indicator["_endpoint"] == "pophive":
            for geo in pophive_geos:
                url = f"{settings.EPIDATA_V5_URL}viz/?source=pophive&signal={indicator['indicator']}&geo_type={geo['geo_type']}&geo_value={geo['id']}&time_values={start_date}:{end_date}&extra_keys=age_group:{pophive_age_group[0]['id']}&format=json&header=false"
                python_code_block = dedent(
                    f"""\
                    pophive_{indicator['indicator']}_{geo['geo_type']}_{geo['id']}_response = requests.get(
                        "{url}"
                    )
                    pophive_{indicator['indicator']}_{geo['geo_type']}_{geo['id']}_data = pophive_{indicator['indicator']}_{geo['geo_type']}_{geo['id']}_response.json()
                """
                )
                python_code_blocks.append(python_code_block)
                r_code_block = dedent(
                    f"""\
                    pophive_{indicator['indicator']}_{geo['geo_type']}_{geo['id']}_response <- GET(
                        "{url}"
                    )
                    pophive_{indicator['indicator']}_{geo['geo_type']}_{geo['id']}_data <- fromJSON(content(pophive_{indicator['indicator']}_{geo['geo_type']}_{geo['id']}_response, "text"))
                """
                )
                r_code_blocks.append(r_code_block)
    return python_code_blocks, r_code_blocks


def generate_query_code_nwss(
    indicators,
    start_date,
    end_date,
    nwss_geographic_value,
    nwss_source,
    nwss_fill_method,
):
    python_code_blocks = ["import requests"]
    r_code_blocks = ["library(httr)", "library(jsonlite)"]
    geo_value = ",".join(nwss_geographic_value)
    for indicator in indicators:
        for source in nwss_source:
            if indicator["_endpoint"] == "nwss":
                url = f"{settings.EPIDATA_V5_URL}viz/?source=nwss&signal={indicator['indicator']}&geo_type=sewershed&geo_value={geo_value}&fill_method={nwss_fill_method}&time_values={start_date}:{end_date}&extra_keys=nwss_source:{source['id']}&format=json&header=false"
                python_code_block = dedent(
                    f"""\

                    nwss_{indicator['indicator']}_source_{source['id']}_response = requests.get(
                        "{url}"
                    )
                    nwss_{indicator['indicator']}_source_{source['id']}_data = nwss_{indicator['indicator']}_source_{source['id']}_response.json()
                """
                )
                python_code_blocks.append(python_code_block)
                r_code_block = dedent(
                    f"""\
                    nwss_{indicator['indicator']}_source_{source['id']}_response <- GET(
                        "{url}"
                    )
                    nwss_{indicator['indicator']}_source_{source['id']}_data <- fromJSON(content(nwss_{indicator['indicator']}_source_{source['id']}_response, "text"))
                """
                )
                r_code_blocks.append(r_code_block)
    return python_code_blocks, r_code_blocks


def log_form_stats(request, data, form_mode):
    log_data = {
        "form_mode": form_mode,
        "num_of_indicators": len(data.get("indicators", [])),
        "num_of_covidcast_geos": len(data.get("covidCastGeographicValues", [])),
        "num_of_fluview_geos": len(data.get("fluviewLocations", [])),
        "num_of_nidss_flu_geos": len(data.get("nidssFluLocations", [])),
        "num_of_nidss_dengue_geos": len(data.get("nidssDengueLocations", [])),
        "num_of_flusurv_geos": len(data.get("flusurvLocations", [])),
        "num_of_pophive_geos": len(data.get("pophiveLocations", [])),
        "num_of_nwss_geos": len(data.get("nwssGeographicValue", "")),
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "epiweeks": (
            get_epiweek(data.get("start_date"), data.get("end_date"))
            if data.get("start_date") and data.get("end_date")
            else []
        ),
        "api_key_used": bool(data.get("api_key")),
        "api_key": data.get("api_key", "Not provided"),
        "user_ip": get_client_ip(request),
        "user_ga_id": data.get("clientId", "Not available"),
    }

    form_stats_logger.info("form_stats", **log_data)


def log_form_data(request, data, form_mode):
    indicators = data.get("indicators", [])
    indicators = [
        {
            "endpoint": ind.get("_endpoint"),
            "indicator": ind.get("indicator"),
            "data_source": ind.get("data_source"),
            "time_type": ind.get("time_type"),
            "indicator_set": ind.get("indicator_set")

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
        "form_mode": form_mode,
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
        "api_key": data.get("apiKey", "Not provided"),
        "user_ip": get_client_ip(request),
        "user_ga_id": data.get("clientId", "Not available"),
    }
    form_data_logger.info("form_data", **log_data)


def get_num_locations_from_meta(indicators):
    timeseries_count = 0
    indicators = set(
        (indicator["source__name"], indicator["name"]) for indicator in indicators
    )

    metadata = cache.get("covidcast_meta")
    if not metadata:
        try:
            response = requests.get(
                f"{settings.EPIDATA_URL}covidcast_meta/", timeout=(5, 30)
            )
            response.raise_for_status()
            data = response.json()
            metadata = data["epidata"]
            cache.set("covidcast_meta", metadata, 60 * 60 * 24)
        except requests.RequestException:
            logger.error("Error fetching covidcast metadata")
            return 0
        except Exception as e:
            logger.error(f"Error fetching covidcast metadata: {e}")
            return 0

    epidata = metadata["epidata"] if isinstance(metadata, dict) else metadata
    for r in epidata:
        if (r["data_source"], r["signal"]) in indicators:
            timeseries_count += r["num_locations"]
    return timeseries_count
