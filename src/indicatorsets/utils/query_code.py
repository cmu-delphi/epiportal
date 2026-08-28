"""Generators for the Python/R snippets that reproduce a user's query."""

from textwrap import dedent

from django.conf import settings

from indicatorsets.utils.epidata import get_v5_source
from indicatorsets.utils.helpers import get_epiweek


def generate_query_code_covidcast(
    indicators,
    covidcast_geos,
    start_date,
    end_date,
    data_source,
    indicators_str,
):
    """Generate snippets for a covidcast data source, routing per indicator.

    Signals this source has migrated to Epidata v5 get plain ``requests``/``httr``
    snippets against the v5 endpoint, the way the pophive and nwss builders do,
    because epidatpy/epidatr have no v5 equivalent of ``pub_covidcast``. Anything
    still on v4 keeps its ``pub_covidcast`` call. ``indicators_str`` is only used
    when nothing has migrated; otherwise the v4 signal list is recomputed from
    the indicators that are actually still on v4.
    """
    python_code_blocks = []
    r_code_blocks = []
    v5_indicators = [indicator for indicator in indicators if get_v5_source(indicator)]
    v4_indicators = [
        indicator for indicator in indicators if indicator not in v5_indicators
    ]
    # every indicator in this group shares one data source, so one v5 name
    v5_source = get_v5_source(v5_indicators[0]) if v5_indicators else None
    if v5_indicators:
        python_code_blocks.append("import requests")
        r_code_blocks.extend(["library(httr)", "library(jsonlite)"])
        indicators_str = ",".join(
            [indicator["indicator"] for indicator in v4_indicators]
        )
    time_type = v4_indicators[0].get("time_type") if v4_indicators else None
    for geo_type, values in covidcast_geos.items():
        geo_values = [
            (
                value["id"].split(":")[1].lower()
                if value["geoType"] in ["nation", "state"]
                else value["id"].split(":")[1]
            )
            for value in values
        ]
        for indicator in v5_indicators:
            url = (
                f"{settings.EPIDATA_V5_URL}viz/?source={v5_source}"
                f"&signal={indicator['indicator']}&geo_type={geo_type}"
                f"&geo_value={','.join(geo_values)}"
                f"&time_values={start_date}:{end_date}&format=json&header=false"
            )
            name = (
                f"{data_source.replace('-', '_')}_{indicator['indicator']}_{geo_type}"
            )
            python_code_blocks.append(
                dedent(
                    f"""\
                    {name}_response = requests.get(
                        "{url}"
                    )
                    {name}_data = {name}_response.json()
                """
                )
            )
            r_code_blocks.append(
                dedent(
                    f"""\
                    {name}_response <- GET(
                        "{url}"
                    )
                    {name}_data <- fromJSON(content({name}_response, "text"))
                """
                )
            )
        if not v4_indicators:
            continue
        if time_type == "week":
            start_week, end_week = get_epiweek(start_date, end_date)
            python_time_values = f"EpiRange({start_week}, {end_week})"
            r_time_values = f"epirange({start_week}, {end_week})"
        else:
            start_day = start_date.replace("-", "")
            end_day = end_date.replace("-", "")
            python_time_values = f"EpiRange({start_day}, {end_day})"
            r_time_values = f"epirange({start_day}, {end_day})"
        python_code_blocks.append(
            dedent(
                f"""\
                {data_source.replace('-', '_')}_{geo_type}_df = epidata.pub_covidcast(
                    data_source="{data_source}",
                    signals="{indicators_str}",
                    geo_type="{geo_type}",
                    time_type="{time_type}",
                    geo_values="{','.join(geo_values)}",
                    time_values={python_time_values},
                ).df()
            """
            )
        )
        r_code_blocks.append(
            dedent(
                f"""\
                epidata_{data_source.replace("-", "_")}_{geo_type} <- pub_covidcast(
                    source = "{data_source}",
                    signals = "{indicators_str}",
                    geo_type = "{geo_type}",
                    time_type = "{time_type}",
                    geo_values = "{','.join(geo_values)}",
                    time_values = {r_time_values}
                )
            """
            )
        )
    return python_code_blocks, r_code_blocks


def generate_query_code_epiweek(source, geos, start_date, end_date):
    """Generate epidatpy/epidatr snippets for an epiweek-based endpoint.

    Args:
        source: The :class:`EpiweekSource` describing the endpoint.
        geos: Selected geos, each a dict with an ``id`` key.

    Returns:
        A ``(python_code_blocks, r_code_blocks)`` pair, one block each.
    """
    geo_values = ",".join([geo["id"] for geo in geos])
    start_week, end_week = get_epiweek(start_date, end_date)
    python_code_block = dedent(
        f"""\
        {source.key}_df = epidata.pub_{source.key}(
            {source.geo_param}="{geo_values}",
            epiweeks="{start_week}-{end_week}",
        ).df()
    """
    )
    r_code_block = dedent(
        f"""\
        epidata_{source.key} <- pub_{source.key}(
            {source.geo_param} = "{geo_values}",
            epiweeks = epirange({start_week}, {end_week})
        )
    """
    )
    return [python_code_block], [r_code_block]


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
