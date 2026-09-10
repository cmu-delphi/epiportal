"""Builders for the data-export commands shown to users, one per Epidata endpoint."""

from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from indicatorsets.utils.epidata import (
    get_time_values,
    get_v5_source,
    group_fluview_geos_by_v5_type,
    group_v5_indicators_by_source,
    has_epidata_results,
    split_v4_v5_indicators,
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
                if get_from_v5:
                    check_params = {
                        "source": v5_source,
                        "signal": indicator["indicator"],
                        "geo_type": geo_type,
                        "geo_value": geo_values,
                        "reference_times": time_values,
                        "token": api_key if api_key else settings.EPIDATA_API_KEY,
                    }
                    epidata_url = f"{settings.EPIDATA_V5_URL}viz/"
                else:
                    # v4 keys signals by data_source and has a time_type dimension
                    check_params = {
                        "signal": indicator["indicator"],
                        "geo_type": geo_type,
                        "time_values": time_values,
                        "time_type": indicator["time_type"],
                        "data_source": indicator["data_source"],
                        "geo_values": geo_values,
                        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
                    }
                    epidata_url = f"{settings.EPIDATA_URL}covidcast"

                if not has_epidata_results(epidata_url, check_params):
                    data_export_commands.append(
                        f'<span class="text-muted">No data found for {label}. Export skipped.</span>'
                    )
                    continue
                if get_from_v5:
                    data_export_url = f"{settings.EPIDATA_V5_URL}viz/?source={v5_source}&signal={indicator['indicator']}&geo_type={geo_type}&geo_value={geo_values}&reference_times={time_values}&format={data_format}"
                else:
                    data_export_url = f"{settings.EPIDATA_URL}covidcast/csv?signal={indicator['data_source']}:{indicator['indicator']}&start_day={dates[0]}&end_day={dates[1]}&geo_type={geo_type}&geo_values={geo_values}&format={data_format}"
                if data_format == "csv":
                    data_export_url += f"&header=true"
                if get_from_v5:
                    if api_key:
                        data_export_url += f"&token={api_key}"
                elif api_key:
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
                        "reference_times": time_values,
                        "format": data_format,
                        "header": "true" if data_format == "csv" else "false",
                        "filename": filename,
                    }
                    if api_key:
                        download_params["token"] = api_key
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


def generate_v5_fluview_export_snippet(
    v5_indicators,
    v5_source,
    geo_type,
    geo_values,
    start_date,
    end_date,
    data_format,
    api_key,
):
    """Build the export command for one v5 source's geo_type bucket.

    Mirrors the covidcast v5 branch: every migrated signal for this source is
    checked and downloaded in one batched request, keyed by
    ``reference_times``/``token`` (the real v5 param names, distinct from v4's
    ``time_values``/``api_key``).
    """
    data_export_commands = []
    label = f"{v5_source} ({geo_type})"
    reference_times = f"{start_date}:{end_date}"
    check_params = {
        "source": v5_source,
        "signal": ",".join([indicator["indicator"] for indicator in v5_indicators]),
        "geo_type": geo_type,
        "geo_value": geo_values,
        "reference_times": reference_times,
        "token": api_key if api_key else settings.EPIDATA_API_KEY,
    }
    if not has_epidata_results(f"{settings.EPIDATA_V5_URL}viz/", check_params):
        data_export_commands.append(
            f'<span class="text-muted">No data found for {label}. Export skipped.</span>'
        )
        return data_export_commands
    data_export_url = f"{settings.EPIDATA_V5_URL}viz/?source={check_params['source']}&signal={check_params['signal']}&geo_type={check_params['geo_type']}&geo_value={check_params['geo_value']}&reference_times={reference_times}&format={data_format}"
    if data_format == "csv":
        data_export_url += "&header=true"
    if api_key:
        data_export_url += f"&token={api_key}"

    filename = f"{v5_source}_{geo_type}.{data_format}"
    download_params = {
        "source": check_params["source"],
        "signal": check_params["signal"],
        "geo_type": check_params["geo_type"],
        "geo_value": check_params["geo_value"],
        "reference_times": reference_times,
        "format": data_format,
        "header": "true" if data_format == "csv" else "false",
        "filename": filename,
    }
    if api_key:
        download_params["token"] = api_key
    download_url = f"{reverse('download_export')}?{urlencode(download_params)}"
    data_export_commands.append(
        f'curl -o {filename} <a href="{download_url}" download="{filename}">{data_export_url}</a>'
    )
    return data_export_commands


def generate_v4_fluview_export_snippet(
    source, data_source, geos, start_date, end_date, data_format, api_key
):
    """Build the v4 export command for one data source on an epiweek endpoint.

    ``data_source`` is the actual v4 URL segment. It is often the same as
    ``source.key``, but not always: one :class:`EpiweekSource` (one geo
    widget, one ``_endpoint``) can cover several data sources that live at
    different v4 endpoints, so the caller passes the indicator's own
    ``data_source`` rather than letting this assume ``source.key``.
    """
    geo_values = ",".join([geo["id"] for geo in geos])
    date_from, date_to = get_epiweek(start_date, end_date)
    data_export_url = (
        f"{settings.EPIDATA_URL}{data_source}/"
        f"?{source.geo_param}={geo_values}"
        f"&epiweeks={date_from}-{date_to}"
        f"&format={data_format}"
    )
    if data_format == "csv":
        data_export_url += "&header=true"
    if api_key:
        data_export_url += f"&api_key={api_key}"
    return (
        f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'
    )


def generate_epiweek_export_url(
    source, geos, start_date, end_date, api_key, data_format, indicators
):
    """Build the export command(s) for an epiweek-based endpoint, routing per indicator.

    Migrated signals get a v5 export command, built per v5 source; anything
    still on v4 gets one command per distinct v4 ``data_source`` still
    present, since one endpoint can cover several data sources that migrate
    independently. ``get_v5_source`` fails closed to v4, so a source that has
    not migrated emits exactly the command it did before. See
    ``generate_query_code_epiweek`` for the equivalent routing in the
    query-code generator.

    Args:
        source: The :class:`EpiweekSource` describing the endpoint.
        geos: Selected geos, each a dict with an ``id`` key.
        indicators: All submitted indicators; only ones for this source are used.
    """
    data_export_commands = []
    source_indicators = [i for i in indicators if i["_endpoint"] == source.key]
    v5_indicators, v4_indicators, _ = split_v4_v5_indicators(source_indicators)
    # Per v5 source, not per endpoint: one endpoint can cover several data
    # sources mapping to different v5 sources, and batching one source's
    # signals into another's request would export the wrong data silently.
    for v5_source, source_v5_indicators in group_v5_indicators_by_source(
        v5_indicators
    ).items():
        for geo_type, geo_values in group_fluview_geos_by_v5_type(geos).items():
            geo_values_str = ",".join(geo_values)
            data_export_commands.extend(
                generate_v5_fluview_export_snippet(
                    source_v5_indicators,
                    v5_source,
                    geo_type,
                    geo_values_str,
                    start_date,
                    end_date,
                    data_format,
                    api_key,
                )
            )
    if v4_indicators or not v5_indicators:
        v4_data_sources = sorted({i["data_source"] for i in v4_indicators}) or [
            source.key
        ]
        for data_source in v4_data_sources:
            data_export_commands.append(
                generate_v4_fluview_export_snippet(
                    source,
                    data_source,
                    geos,
                    start_date,
                    end_date,
                    data_format,
                    api_key,
                )
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
                    "reference_times": f"{start_date}:{end_date}",
                    "extra_keys": f"age_group:{pophive_age_group[0]['id']}",
                    "token": api_key if api_key else settings.EPIDATA_API_KEY,
                }
                if not has_epidata_results(
                    f"{settings.EPIDATA_V5_URL}viz/", check_params
                ):
                    data_export_commands.append(
                        f'<span class="text-muted">No data found for {label}. Export skipped.</span>'
                    )
                    continue
                data_export_url = f"{settings.EPIDATA_V5_URL}viz/?source=pophive&signal={indicator['indicator']}&geo_type={geo['geo_type']}&geo_value={geo['id']}&reference_times={start_date}:{end_date}&extra_keys=age_group:{pophive_age_group[0]['id']}&format={data_format}"
                if data_format == "csv":
                    data_export_url += "&header=true"
                if api_key:
                    data_export_url += f"&token={api_key}"
                filename = f"{indicator['indicator']}_{geo['geo_type']}_{geo['id']}.{data_format}"
                download_params = {
                    "source": "pophive",
                    "signal": indicator["indicator"],
                    "geo_type": geo["geo_type"],
                    "geo_value": geo["id"],
                    "reference_times": f"{start_date}:{end_date}",
                    "extra_keys": f"age_group:{pophive_age_group[0]['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                    "filename": filename,
                }
                if api_key:
                    download_params["token"] = api_key
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
                    "reference_times": f"{start_date}:{end_date}",
                    "extra_keys": f"nwss_source:{source['id']}",
                    "token": api_key if api_key else settings.EPIDATA_API_KEY,
                }
                if not has_epidata_results(
                    f"{settings.EPIDATA_V5_URL}viz/", check_params
                ):
                    data_export_commands.append(
                        f'<span class="text-muted">No data found for {label}. Export skipped.</span>'
                    )
                    continue
                data_export_url = f"{settings.EPIDATA_V5_URL}viz/?source=nwss&signal={indicator['indicator']}&geo_type=sewershed&geo_value={geo_value}&fill_method={nwss_fill_method}&reference_times={start_date}:{end_date}&extra_keys=nwss_source:{source['id']}&format={data_format}"
                if data_format == "csv":
                    data_export_url += "&header=true"
                if api_key:
                    data_export_url += f"&token={api_key}"
                filename = (
                    f"{indicator['indicator']}_source_{source['id']}.{data_format}"
                )
                download_params = {
                    "source": "nwss",
                    "signal": indicator["indicator"],
                    "geo_type": "sewershed",
                    "geo_value": geo_value,
                    "fill_method": nwss_fill_method,
                    "reference_times": f"{start_date}:{end_date}",
                    "extra_keys": f"nwss_source:{source['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                    "filename": filename,
                }
                if api_key:
                    download_params["token"] = api_key
                download_url = (
                    f"{reverse('download_export')}?{urlencode(download_params)}"
                )
                data_export_commands.append(
                    f'curl -o {filename} <a href="{download_url}" download="{filename}">{data_export_url}</a>'
                )
    return data_export_commands
