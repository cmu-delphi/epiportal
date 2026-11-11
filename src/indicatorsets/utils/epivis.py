"""Builders for EpiVis dataset payloads, one per Epidata endpoint."""

from indicatorsets.utils.constants import FLUVIEW_INDICATORS_MAPPING
from indicatorsets.utils.epidata import get_v5_source
from indicatorsets.utils.helpers import generate_random_color
from indicatorsets.utils.locations import to_covidcast_geo


def generate_epivis_custom_title(indicator, geo_value, extra_keys=None):
    title = f"{indicator['indicator_set_short_name']}:{indicator['indicator']} : {geo_value}"
    if extra_keys:
        title += f" ({extra_keys})"
    return title


def generate_covidcast_dataset_epivis(indicator, covidcast_geos):
    """Build EpiVis datasets for a covidcast-shaped indicator.

    v5-only sources go out as ``covidcast`` too: EpiVis's covidcast importer
    reads a ``data_source`` from v5 whenever v5's metadata lists the signal.
    Census divisions only exist there, so they are sent only for such signals.
    """
    datasets = []
    on_v5 = bool(get_v5_source(indicator))
    for geos in covidcast_geos.values():
        for geo in geos:
            pair = to_covidcast_geo(geo["id"], on_v5)
            if pair and geo["id"] not in indicator.get("notCoveredGeos", []):
                geo_type, geo_value = pair
                datasets.append(
                    {
                        "color": generate_random_color(),
                        "title": "value",
                        "params": {
                            "_endpoint": "covidcast",
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
        # The modal records uncovered locations by their main-dropdown id.
        if geo.get("location_id", geo["id"]) not in indicator.get("notCoveredGeos", []):
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


def generate_epiweek_dataset_epivis(source, indicator, geos):
    """Build EpiVis datasets for an epiweek-based endpoint.

    Covers the endpoints whose payload is fully generic (nidss_flu,
    nidss_dengue, flusurv). fluview has its own builder because it maps
    indicator names to display titles, skips geos the indicator does not cover,
    and falls back to the fluview_clinical endpoint.

    Args:
        source: The :class:`EpiweekSource` supplying the geo parameter name.
        indicator: The indicator record; its ``_endpoint`` is used verbatim.
        geos: Selected geos, each a dict with ``id`` and ``text`` keys.
    """
    datasets = []
    for geo in geos:
        datasets.append(
            {
                "color": generate_random_color(),
                "title": indicator["indicator"],
                "params": {
                    "_endpoint": indicator["_endpoint"],
                    source.geo_param: geo["id"],
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
    sewersheds_with_values=None,
):
    """Build one EpiVis dataset per (sewershed, NWSS source) for ``indicator``.

    ``sewersheds_with_values`` maps a source id to ``{signal: {sewershed
    ids}}`` (see ``get_nwss_sewersheds_with_values``). EpiVis warns once per
    series it finds no data for, and most counties have sewersheds a given
    source does not report, so only the sewersheds listed there are plotted.
    A source mapped to ``None``, or no mapping at all, means unknown: every
    sewershed is kept rather than dropping data that may exist.
    """
    datasets = []
    geo_values = ",".join(geographic_value).replace(" ", "").split(",")
    for geo_value in geo_values:
        for s in source:
            if sewersheds_with_values is not None:
                with_values = sewersheds_with_values.get(s["id"])
                if with_values is not None and geo_value not in with_values.get(
                    indicator["indicator"], set()
                ):
                    continue
            params = {
                "_endpoint": indicator["_endpoint"],
                "source": "nwss",
                "signal": indicator["indicator"],
                "geo_type": geographic_type,
                "geo_value": geo_value,
                "custom_title": generate_epivis_custom_title(
                    indicator, geo_value, s["id"]
                ),
                "extra_keys": f"nwss_source:{s['id']}",
            }
            if fill_method:
                params["fill_method"] = fill_method
            datasets.append(
                {
                    "color": generate_random_color(),
                    "title": "value",
                    "params": params,
                }
            )
    return datasets
