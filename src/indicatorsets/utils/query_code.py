"""Generators for the Python/R snippets that reproduce a user's query."""

from textwrap import dedent

from indicatorsets.utils.epidata import get_v5_source
from indicatorsets.utils.helpers import get_epiweek


def split_v4_v5_covidcast_indicators(indicators):
    """Partition ``indicators`` by whether their source has migrated to v5.

    Returns ``(v5_indicators, v4_indicators, v5_source)``, where ``v5_source``
    is the v5 name shared by every v5 indicator (all indicators in a group
    share one data source), or ``None`` if nothing has migrated.
    """
    v5_indicators = [indicator for indicator in indicators if get_v5_source(indicator)]
    v4_indicators = [
        indicator for indicator in indicators if indicator not in v5_indicators
    ]
    v5_source = get_v5_source(v5_indicators[0]) if v5_indicators else None
    return v5_indicators, v4_indicators, v5_source


def generate_v5_covidcast_snippets(
    v5_indicators, v5_source, data_source, geo_type, geo_values, start_date, end_date
):
    """Build the v5 snippets for indicators whose source has migrated.

    Both epidatpy's and epidatr's ``epidata_snapshot()`` take a list/vector of
    signals, so each client batches every v5 indicator for this geo_type into
    a single call -- mirroring how the v4 branch batches its signals into one
    ``pub_covidcast`` call. The ``_v5`` suffix on the variable names keeps them
    from clobbering the v4 block's variables in a mixed group.
    """
    python_code_blocks = []
    r_code_blocks = []
    if v5_indicators:
        signals_list = ", ".join(
            f'"{indicator["indicator"]}"' for indicator in v5_indicators
        )
        geo_values_list = ", ".join(f'"{geo_value}"' for geo_value in geo_values)
        data_source_safe = data_source.replace("-", "_")
        python_code_blocks.append(
            dedent(
                f"""\
                {data_source_safe}_{geo_type}_v5_df = epidata.epidata_snapshot(
                    source="{v5_source}",
                    signals=[{signals_list}],
                    geo_type="{geo_type}",
                    geo_values=[{geo_values_list}],
                    reference_time=EpiRange("{start_date}", "{end_date}"),
                ).df()
            """
            )
        )
        r_code_blocks.append(
            dedent(
                f"""\
                epidata_{data_source_safe}_{geo_type}_v5 <- epidata_snapshot(
                    source = "{v5_source}",
                    signals = c({signals_list}),
                    geo_type = "{geo_type}",
                    geo_values = c({geo_values_list}),
                    reference_time = epirange("{start_date}", "{end_date}")
                )
            """
            )
        )
    return python_code_blocks, r_code_blocks


def generate_v4_covidcast_snippet(
    data_source, indicators_str, time_type, geo_type, geo_values, start_date, end_date
):
    """Build the single ``pub_covidcast`` snippet covering every v4 indicator.

    ``pub_covidcast`` takes a comma-joined ``signals`` string, so all v4
    indicators for this geo_type are fetched in one call.
    """
    if time_type == "week":
        start_week, end_week = get_epiweek(start_date, end_date)
        python_time_values = f"EpiRange({start_week}, {end_week})"
        r_time_values = f"epirange({start_week}, {end_week})"
    else:
        start_day = start_date.replace("-", "")
        end_day = end_date.replace("-", "")
        python_time_values = f"EpiRange({start_day}, {end_day})"
        r_time_values = f"epirange({start_day}, {end_day})"
    python_code_block = dedent(
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
    r_code_block = dedent(
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
    return python_code_block, r_code_block


def generate_query_code_covidcast(
    indicators,
    covidcast_geos,
    start_date,
    end_date,
    data_source,
    indicators_str,
):
    """Generate snippets for a covidcast data source, routing per indicator.

    Signals this source has migrated to Epidata v5 get an ``epidata_snapshot()``
    call; anything still on v4 keeps its ``pub_covidcast`` call. ``indicators_str``
    is only used when nothing has migrated; otherwise the v4 signal list is
    recomputed from the indicators that are actually still on v4.
    """
    python_code_blocks = []
    r_code_blocks = []
    v5_indicators, v4_indicators, v5_source = split_v4_v5_covidcast_indicators(
        indicators
    )
    if v5_indicators:
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
        v5_python_blocks, v5_r_blocks = generate_v5_covidcast_snippets(
            v5_indicators,
            v5_source,
            data_source,
            geo_type,
            geo_values,
            start_date,
            end_date,
        )
        python_code_blocks.extend(v5_python_blocks)
        r_code_blocks.extend(v5_r_blocks)
        if not v4_indicators:
            continue
        v4_python_block, v4_r_block = generate_v4_covidcast_snippet(
            data_source,
            indicators_str,
            time_type,
            geo_type,
            geo_values,
            start_date,
            end_date,
        )
        python_code_blocks.append(v4_python_block)
        r_code_blocks.append(v4_r_block)
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
    """Generate epidatpy/epidatr snippets for the pophive endpoint.

    Every pophive indicator shares one source, so all of them are batched
    into one ``epidata_snapshot()`` call per geo, the same way the covidcast
    branch batches its signals. epidatr filters ``age_group`` server-side via
    its named extra-key argument; epidatpy's client has no such argument yet,
    so the Python snippet filters the returned dataframe locally instead.
    """
    python_code_blocks = []
    r_code_blocks = []
    pophive_indicators = [i for i in indicators if i["_endpoint"] == "pophive"]
    if not pophive_indicators:
        return python_code_blocks, r_code_blocks
    signals_list = ", ".join(f'"{i["indicator"]}"' for i in pophive_indicators)
    age_group = pophive_age_group[0]["id"]
    for geo in pophive_geos:
        name = f"pophive_{geo['geo_type']}_{geo['id']}"
        python_code_blocks.append(
            dedent(
                f"""\
                {name}_df = epidata.epidata_snapshot(
                    source="pophive",
                    signals=[{signals_list}],
                    geo_type="{geo['geo_type']}",
                    geo_values="{geo['id']}",
                    reference_time=EpiRange("{start_date}", "{end_date}"),
                ).df()
                {name}_df = {name}_df[{name}_df["age_group"] == "{age_group}"]
            """
            )
        )
        r_code_blocks.append(
            dedent(
                f"""\
                epidata_{name} <- epidata_snapshot(
                    source = "pophive",
                    signals = c({signals_list}),
                    geo_type = "{geo['geo_type']}",
                    geo_values = "{geo['id']}",
                    reference_time = epirange("{start_date}", "{end_date}"),
                    age_group = "{age_group}"
                )
            """
            )
        )
    return python_code_blocks, r_code_blocks


def generate_query_code_nwss(
    indicators,
    start_date,
    end_date,
    nwss_geographic_value,
    nwss_source,
    nwss_fill_method,
):
    """Generate epidatpy/epidatr snippets for the nwss endpoint.

    Every nwss indicator shares one source, so all of them are batched into
    one ``epidata_snapshot()`` call per wastewater source, the same way the
    covidcast branch batches its signals. ``fill_method`` is a native
    parameter on both clients. epidatr filters ``nwss_source`` server-side
    via its named extra-key argument; epidatpy's client has no such argument
    yet, so the Python snippet filters the returned dataframe locally.
    """
    python_code_blocks = []
    r_code_blocks = []
    nwss_indicators = [i for i in indicators if i["_endpoint"] == "nwss"]
    if not nwss_indicators:
        return python_code_blocks, r_code_blocks
    signals_list = ", ".join(f'"{i["indicator"]}"' for i in nwss_indicators)
    geo_values_list = ", ".join(f'"{geo}"' for geo in nwss_geographic_value)
    for source in nwss_source:
        name = f"nwss_source_{source['id']}"
        python_code_blocks.append(
            dedent(
                f"""\
                {name}_df = epidata.epidata_snapshot(
                    source="nwss",
                    signals=[{signals_list}],
                    geo_type="sewershed",
                    geo_values=[{geo_values_list}],
                    reference_time=EpiRange("{start_date}", "{end_date}"),
                    fill_method="{nwss_fill_method}",
                ).df()
                {name}_df = {name}_df[{name}_df["nwss_source"] == "{source['id']}"]
            """
            )
        )
        r_code_blocks.append(
            dedent(
                f"""\
                epidata_{name} <- epidata_snapshot(
                    source = "nwss",
                    signals = c({signals_list}),
                    geo_type = "sewershed",
                    geo_values = c({geo_values_list}),
                    reference_time = epirange("{start_date}", "{end_date}"),
                    fill_method = "{nwss_fill_method}",
                    nwss_source = "{source['id']}"
                )
            """
            )
        )
    return python_code_blocks, r_code_blocks
