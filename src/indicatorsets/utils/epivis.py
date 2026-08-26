"""Builders for EpiVis dataset payloads, one per Epidata endpoint."""

from indicatorsets.utils.constants import FLUVIEW_INDICATORS_MAPPING
from indicatorsets.utils.helpers import generate_random_color


def generate_epivis_custom_title(indicator, geo_value, extra_keys=None):
    title = f"{indicator['indicator_set_short_name']}:{indicator['indicator']} : {geo_value}"
    if extra_keys:
        title += f" ({extra_keys})"
    return title


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
