"""Builders for the data-export commands shown to users, one per Epidata endpoint."""

from urllib.parse import urlencode

from delphi_utils import get_structured_logger
from django.conf import settings
from django.urls import reverse

from indicatorsets.utils.constants import DEFAULT_FILL_METHOD
from indicatorsets.utils.epidata import (
    epidata_auth,
    get_epidata_rows,
    get_time_values,
    get_v5_source,
    group_v5_indicators_by_source,
    has_epidata_results,
    split_geos_by_v5_values,
    split_v4_v5_indicators,
)
from indicatorsets.utils.helpers import get_epiweek, is_filled_fill_method

logger = get_structured_logger("indicatorsets.utils")


def _covidcast_v5_export_command(
    indicator, v5_source, geo_type, geo_values, time_values, data_format, api_key,
    fill_method,
):
    data_export_url = f"{settings.EPIDATA_V5_URL}viz/?source={v5_source}&signal={indicator['indicator']}&geo_type={geo_type}&geo_value={geo_values}&reference_times={time_values}&format={data_format}"
    if data_format == "csv":
        data_export_url += "&header=true"
    if api_key:
        data_export_url += f"&token={api_key}"
    if fill_method:
        data_export_url += f"&fill_method={fill_method}"
    # The v5 endpoint sends no Content-Disposition, so link at our own proxy
    # instead of the API, the same way the pophive and nwss builders do.
    filename = (
        f"{indicator['data_source']}_{indicator['indicator']}_{geo_type}.{data_format}"
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
    if fill_method:
        download_params["fill_method"] = fill_method
    download_url = f"{reverse('download_export')}?{urlencode(download_params)}"
    return f'curl -o {filename} <a href="{download_url}" download="{filename}">{data_export_url}</a>'


def _covidcast_v4_export_command(indicator, geo_type, geo_values, dates, data_format, api_key):
    data_export_url = f"{settings.EPIDATA_URL}covidcast/csv?signal={indicator['data_source']}:{indicator['indicator']}&start_day={dates[0]}&end_day={dates[1]}&geo_type={geo_type}&geo_values={geo_values}&format={data_format}"
    if data_format == "csv":
        data_export_url += "&header=true"
    if api_key:
        data_export_url += f"&api_key={api_key}"
    return f'wget --content-disposition <a href="{data_export_url}">{data_export_url}</a>'


def _covidcast_v4_export_commands(
    indicator, start_date, end_date, geo_type, geo_values, label, data_format, api_key
):
    """Probe v4 for ``geo_values`` and return its export command, or a no-data note."""
    time_values, dates = get_time_values(indicator, start_date, end_date, False)
    # v4 keys signals by data_source and has a time_type dimension
    check_params = {
        "signal": indicator["indicator"],
        "geo_type": geo_type,
        "time_values": time_values,
        "time_type": indicator["time_type"],
        "data_source": indicator["data_source"],
        "geo_values": geo_values,
    }
    if not has_epidata_results(
        f"{settings.EPIDATA_URL}covidcast", check_params, auth=epidata_auth(api_key)
    ):
        return [
            f'<span class="text-muted">No data found for {label}. Export skipped.</span>'
        ]
    return [
        _covidcast_v4_export_command(
            indicator, geo_type, geo_values, dates, data_format, api_key
        )
    ]


def generate_covidcast_indicators_export_url(
    indicators,
    start_date,
    end_date,
    covidcast_geos,
    api_key,
    data_format,
    fill_method=DEFAULT_FILL_METHOD,
):
    """Build one export command per (indicator, geo_type), split across v4 and v5.

    A migrated signal is probed on v5 first. Geos v5 has no real values for --
    only null rows, or no rows at all -- are exported from v4 instead, so one
    geo_type can yield both a v5 and a v4 command. That fallback only applies
    to the ``source`` fill_method: v4 cannot fill, so for a filled one those
    geos get a "No data found" note instead.
    """
    data_export_commands = []
    for indicator in indicators:
        if indicator["_endpoint"] != "covidcast":
            continue
        v5_source = get_v5_source(indicator)
        for geo_type, values in covidcast_geos.items():
            geo_value_list = [
                (
                    value["id"].split(":")[1].lower()
                    if value["geoType"] in ["nation", "state"]
                    else value["id"].split(":")[1]
                )
                for value in values
            ]
            name = indicator.get("display_name") or indicator["indicator"]
            label = f"{name} ({geo_type})"
            if not v5_source:
                data_export_commands.extend(
                    _covidcast_v4_export_commands(
                        indicator, start_date, end_date, geo_type,
                        ",".join(geo_value_list), label, data_format, api_key,
                    )
                )
                continue

            time_values, _ = get_time_values(indicator, start_date, end_date, True)
            check_params = {
                "source": v5_source,
                "signal": indicator["indicator"],
                "geo_type": geo_type,
                "geo_value": ",".join(geo_value_list),
                "reference_times": time_values,
            }
            if api_key:
                check_params["token"] = api_key
            if fill_method:
                check_params["fill_method"] = fill_method
            rows = get_epidata_rows(f"{settings.EPIDATA_V5_URL}viz/", check_params)
            v5_geos, v4_geos = split_geos_by_v5_values(rows, geo_value_list)
            if v5_geos:
                data_export_commands.append(
                    _covidcast_v5_export_command(
                        indicator, v5_source, geo_type, ",".join(v5_geos),
                        time_values, data_format, api_key, fill_method,
                    )
                )
            if not v4_geos:
                continue
            # Only name the geos when some of the selection did export,
            # otherwise the label alone already covers every geo.
            fallback_label = (
                f"{name} ({geo_type}: {', '.join(v4_geos)})" if v5_geos else label
            )
            if is_filled_fill_method(fill_method):
                # v4 has no fill_method, so it can only serve the unfilled
                # series -- not what the user picked.
                data_export_commands.append(
                    f'<span class="text-muted">No data found for {fallback_label}. Export skipped.</span>'
                )
                continue
            logger.warning(
                "Epidata v5 has no values for these geos, falling back to v4",
                extra={
                    "source": v5_source,
                    "signal": indicator["indicator"],
                    "geo_type": geo_type,
                    "geo_values": v4_geos,
                },
            )
            data_export_commands.extend(
                _covidcast_v4_export_commands(
                    indicator, start_date, end_date, geo_type,
                    ",".join(v4_geos), fallback_label, data_format, api_key,
                )
            )
    return data_export_commands


def generate_v5_epiweek_export_snippet(
    v5_indicators,
    v5_source,
    geo_type,
    geo_values,
    start_date,
    end_date,
    data_format,
    api_key,
    fill_method=DEFAULT_FILL_METHOD,
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
    }
    if api_key:
        check_params["token"] = api_key
    if fill_method:
        check_params["fill_method"] = fill_method
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
    if fill_method:
        data_export_url += f"&fill_method={fill_method}"

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
    if fill_method:
        download_params["fill_method"] = fill_method
    download_url = f"{reverse('download_export')}?{urlencode(download_params)}"
    data_export_commands.append(
        f'curl -o {filename} <a href="{download_url}" download="{filename}">{data_export_url}</a>'
    )
    return data_export_commands


def generate_v4_epiweek_export_snippet(
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
    source,
    geos,
    start_date,
    end_date,
    api_key,
    data_format,
    indicators,
    fill_method=DEFAULT_FILL_METHOD,
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
        for geo_type, geo_values in source.group_geos_by_v5_type(geos).items():
            geo_values_str = ",".join(geo_values)
            data_export_commands.extend(
                generate_v5_epiweek_export_snippet(
                    source_v5_indicators,
                    v5_source,
                    geo_type,
                    geo_values_str,
                    start_date,
                    end_date,
                    data_format,
                    api_key,
                    fill_method,
                )
            )
    if v4_indicators or not v5_indicators:
        v4_data_sources = sorted({i["data_source"] for i in v4_indicators}) or [
            source.key
        ]
        for data_source in v4_data_sources:
            data_export_commands.append(
                generate_v4_epiweek_export_snippet(
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
    fill_method=DEFAULT_FILL_METHOD,
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
                }
                if api_key:
                    check_params["token"] = api_key
                if fill_method:
                    check_params["fill_method"] = fill_method
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
                if fill_method:
                    data_export_url += f"&fill_method={fill_method}"
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
                if fill_method:
                    download_params["fill_method"] = fill_method
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
    fill_method,
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
                    "reference_times": f"{start_date}:{end_date}",
                    "extra_keys": f"nwss_source:{source['id']}",
                }
                if api_key:
                    check_params["token"] = api_key
                if fill_method:
                    check_params["fill_method"] = fill_method
                if not has_epidata_results(
                    f"{settings.EPIDATA_V5_URL}viz/", check_params
                ):
                    data_export_commands.append(
                        f'<span class="text-muted">No data found for {label}. Export skipped.</span>'
                    )
                    continue
                data_export_url = f"{settings.EPIDATA_V5_URL}viz/?source=nwss&signal={indicator['indicator']}&geo_type=sewershed&geo_value={geo_value}&reference_times={start_date}:{end_date}&extra_keys=nwss_source:{source['id']}&format={data_format}"
                if data_format == "csv":
                    data_export_url += "&header=true"
                if api_key:
                    data_export_url += f"&token={api_key}"
                if fill_method:
                    data_export_url += f"&fill_method={fill_method}"
                filename = (
                    f"{indicator['indicator']}_source_{source['id']}.{data_format}"
                )
                download_params = {
                    "source": "nwss",
                    "signal": indicator["indicator"],
                    "geo_type": "sewershed",
                    "geo_value": geo_value,
                    "reference_times": f"{start_date}:{end_date}",
                    "extra_keys": f"nwss_source:{source['id']}",
                    "format": data_format,
                    "header": "true" if data_format == "csv" else "false",
                    "filename": filename,
                }
                if api_key:
                    download_params["token"] = api_key
                if fill_method:
                    download_params["fill_method"] = fill_method
                download_url = (
                    f"{reverse('download_export')}?{urlencode(download_params)}"
                )
                data_export_commands.append(
                    f'curl -o {filename} <a href="{download_url}" download="{filename}">{data_export_url}</a>'
                )
    return data_export_commands
