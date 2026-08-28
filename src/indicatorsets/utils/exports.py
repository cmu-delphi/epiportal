"""Builders for the data-export commands shown to users, one per Epidata endpoint."""

from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from indicatorsets.utils.epidata import (
    get_time_values,
    get_v5_source,
    has_epidata_results,
)
from indicatorsets.utils.helpers import get_epiweek


def generate_covidcast_indicators_export_url(
    indicators, start_date, end_date, covidcast_geos, api_key, data_format
):
    data_export_commands = []
    for indicator in indicators:
        if indicator["_endpoint"] == "covidcast":
            v5_source = get_v5_source(indicator)
            get_from_v5 = v5_source is not None
            time_values, dates = get_time_values(
                indicator, start_date, end_date, get_from_v5
            )
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
                label = f"{indicator.get('display_name') or indicator['indicator']} ({geo_type})"
                check_params = {
                    "signal": indicator["indicator"],
                    "geo_type": geo_type,
                    "time_values": time_values,
                    "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
                }
                if get_from_v5:
                    check_params["source"] = v5_source
                    check_params["geo_value"] = geo_values
                    epidata_url = f"{settings.EPIDATA_V5_URL}viz/"
                else:
                    # v5 keys signals by source and has no time_type dimension
                    check_params["time_type"] = indicator["time_type"]
                    check_params["data_source"] = indicator["data_source"]
                    check_params["geo_values"] = geo_values
                    epidata_url = f"{settings.EPIDATA_URL}covidcast"

                if not has_epidata_results(epidata_url, check_params):
                    data_export_commands.append(
                        f'<span class="text-muted">No data found for {label}. Export skipped.</span>'
                    )
                    continue
                if get_from_v5:
                    data_export_url = f"{settings.EPIDATA_V5_URL}viz/?source={v5_source}&signal={indicator['indicator']}&geo_type={geo_type}&geo_value={geo_values}&time_values={time_values}&format={data_format}"
                else:
                    data_export_url = f"{settings.EPIDATA_URL}covidcast/csv?signal={indicator['data_source']}:{indicator['indicator']}&start_day={dates[0]}&end_day={dates[1]}&geo_type={geo_type}&geo_values={geo_values}&format={data_format}"
                if data_format == "csv":
                    data_export_url += f"&header=true"
                if api_key:
                    data_export_url += f"&api_key={api_key}"
                if get_from_v5:
                    # The v5 endpoint sends no Content-Disposition, so link at our
                    # own proxy instead of the API, the same way the pophive and
                    # nwss builders do.
                    filename = (
                        f"{indicator['data_source']}_{indicator['indicator']}"
                        f"_{geo_type}.{data_format}"
                    )
                    download_params = {
                        "source": v5_source,
                        "signal": indicator["indicator"],
                        "geo_type": geo_type,
                        "geo_value": geo_values,
                        "time_values": time_values,
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
                else:
                    data_export_commands.append(
                        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
                    )
    return data_export_commands


def generate_epiweek_export_url(
    source, geos, start_date, end_date, api_key, data_format
):
    """Build the export command for an epiweek-based endpoint.

    Args:
        source: The :class:`EpiweekSource` describing the endpoint.
        geos: Selected geos, each a dict with an ``id`` key.
    """
    geo_values = ",".join([geo["id"] for geo in geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    data_export_url = (
        f"{settings.EPIDATA_URL}{source.key}/"
        f"?{source.geo_param}={geo_values}"
        f"&epiweeks={date_from}-{date_to}"
        f"&format={data_format}"
    )
    if data_format == "csv":
        data_export_url += "&header=true"
    if api_key:
        data_export_url += f"&api_key={api_key}"
    return [
        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
    ]


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
