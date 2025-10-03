import ast
import random
from collections import defaultdict
from datetime import datetime as dtime
from textwrap import dedent

import requests
from django.conf import settings
from django.http import JsonResponse
from epiweeks import Week
from delphi_utils import get_structured_logger

from indicatorsets.models import IndicatorSet

FLUVIEW_INDICATORS_MAPPING = {"wili": "%wILI", "ili": "%ILI"}

form_data_logger = get_structured_logger("form_data_logger")
form_stats_logger = get_structured_logger("form_stats_logger")


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


def dict_to_geo_string(geo_dict):
    return ";".join([f"{k}:{','.join(v)}" for k, v in geo_dict.items()])


def get_list_of_indicators_filtered_by_geo(geos):
    geos = list_to_dict(ast.literal_eval(geos))
    url = f"{settings.EPIDATA_URL}covidcast/geo_coverage"
    params = {"geo": dict_to_geo_string(geos), "api_key": settings.EPIDATA_API_KEY}
    response = requests.get(url, params=params)
    return response.json()


def generate_epivis_custom_title(indicator, geo_value):
    return f"{indicator['indicator_set_short_name']}:{indicator.get('member_short_name', '')} : {geo_value}"


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


def get_original_data_provider_choices():
    return [
        (el, el)
        for el in IndicatorSet.objects.values_list("original_data_provider", flat=True)
        .order_by("original_data_provider")
        .distinct()
    ]


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


def generate_covidcast_indicators_export_url(
    indicators, start_date, end_date, covidcast_geos, api_key
):
    data_export_commands = []
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
    return data_export_commands


def generate_fluview_indicators_export_url(fluview_geos, start_date, end_date, api_key):
    data_export_commands = []
    regions = ",".join([region["id"] for region in fluview_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    data_export_url = f"{settings.EPIDATA_URL}fluview/?regions={regions}&epiweeks={date_from}-{date_to}&format=csv"
    if api_key:
        data_export_url += f"&api_key={api_key}"
    data_export_commands.append(
        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
    )
    return data_export_commands


def generate_nidss_flu_export_url(nidss_flu_geos, start_date, end_date, api_key):
    data_export_commands = []
    regions = ",".join([region["id"] for region in nidss_flu_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    data_export_url = f"{settings.EPIDATA_URL}nidss_flu/?regions={regions}&epiweeks={date_from}-{date_to}&format=csv"
    if api_key:
        data_export_url += f"&api_key={api_key}"
    data_export_commands.append(
        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
    )
    return data_export_commands


def generate_nidss_dengue_export_url(nidss_dengue_geos, start_date, end_date, api_key):
    data_export_commands = []
    regions = ",".join([region["id"] for region in nidss_dengue_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    data_export_url = f"{settings.EPIDATA_URL}nidss_dengue/?locations={regions}&epiweeks={date_from}-{date_to}&format=csv"  # fmt: skip
    if api_key:
        data_export_url += f"&api_key={api_key}"
    data_export_commands.append(
        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
    )
    return data_export_commands


def generate_flusurv_export_url(flusurv_geos, start_date, end_date, api_key):
    data_export_commands = []
    regions = ",".join([region["id"] for region in flusurv_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    data_export_url = f"{settings.EPIDATA_URL}flusurv/?locations={regions}&epiweeks={date_from}-{date_to}&format=csv"  # fmt: skip
    if api_key:
        data_export_url += f"&api_key={api_key}"
    data_export_commands.append(
        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
    )
    return data_export_commands


def preview_covidcast_data(indicators, start_date, end_date, covidcast_geos, api_key):
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
    return preview_data


def preview_fluview_data(fluview_geos, start_date, end_date, api_key):
    preview_data = []
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
    return preview_data


def preview_nidss_flu_data(nidss_flu_geos, start_date, end_date, api_key):
    preview_data = []
    regions = ",".join([region["id"] for region in nidss_flu_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    params = {
        "regions": regions,
        "epiweeks": f"{date_from}-{date_to}",
        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
    }
    response = requests.get(f"{settings.EPIDATA_URL}nidss_flu", params=params)
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
    return preview_data


def preview_nidss_dengue_data(nidss_dengue_geos, start_date, end_date, api_key):
    preview_data = []
    regions = ",".join([region["id"] for region in nidss_dengue_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    params = {
        "locations": regions,
        "epiweeks": f"{date_from}-{date_to}",
        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
    }
    response = requests.get(f"{settings.EPIDATA_URL}nidss_dengue", params=params)
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
    return preview_data


def preview_flusurv_data(flusurv_geos, start_date, end_date, api_key):
    preview_data = []
    regions = ",".join([region["id"] for region in flusurv_geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    params = {
        "locations": regions,
        "epiweeks": f"{date_from}-{date_to}",
        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
    }
    response = requests.get(f"{settings.EPIDATA_URL}flusurv", params=params)
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


def get_real_ip_addr(req):  # `req` should be a Flask.request object
    if settings.REVERSE_PROXY_DEPTH:
        # we only expect/trust (up to) "REVERSE_PROXY_DEPTH" number of proxies between this server and the outside world.
        # a REVERSE_PROXY_DEPTH of 0 means not proxied, i.e. server is globally directly reachable.
        # a negative proxy depth is a special case to trust the whole chain -- not generally recommended unless the
        # most-external proxy is configured to disregard "X-Forwarded-For" from outside.
        # really, ONLY trust the following headers if reverse proxied!!!
        x_forwarded_for = req.META.get('HTTP_X_FORWARDED_FOR')

        if x_forwarded_for:
            full_proxy_chain = x_forwarded_for.split(",")
            # eliminate any extra addresses at the front of this list, as they could be spoofed.
            if settings.REVERSE_PROXY_DEPTH > 0:
                depth = settings.REVERSE_PROXY_DEPTH
            else:
                # special case for -1/negative: setting `depth` to 0 will not strip any items from the chain
                depth = 0
            trusted_proxy_chain = full_proxy_chain[-depth:]
            # accept the first (or only) address in the remaining trusted part of the chain as the actual remote address
            return trusted_proxy_chain[0].strip()

        # fall back to "X-Real-Ip" if "X-Forwarded-For" isnt present
        x_real_ip = req.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip

    # if we are not proxied (or we are proxied but the headers werent present and we fell through to here), just use the remote ip addr as the true client address
    return req.META.get('REMOTE_ADDR')


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
        "user_ip": get_real_ip_addr(request),
        "user_ga_id": data.get("clientId", "") if data.get("clientId") else "",
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
        "api_key": data.get("apiKey", "") if data.get("apiKey") else "",
        "user_ip": get_real_ip_addr(request),
        "user_ga_id": data.get("clientId", "") if data.get("clientId") else "",
    }
    form_data_logger.info("form_data", **log_data)
