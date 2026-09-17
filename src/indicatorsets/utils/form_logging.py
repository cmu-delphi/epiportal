"""Structured logging of submitted form data and aggregate form stats."""

from delphi_utils import get_structured_logger

from epiportal.utils import get_client_ip
from indicatorsets.utils.helpers import get_epiweek, group_by_property

form_data_logger = get_structured_logger("form_data_logger")
form_stats_logger = get_structured_logger("form_stats_logger")


def log_form_stats(request, data, form_mode):
    log_data = {
        "form_mode": form_mode,
        "num_of_indicators": len(data.get("indicators", [])),
        "num_of_covidcast_geos": len(data.get("covidCastGeographicValues") or {}),
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
    # Mapping of geo_type -> selected geos. Falls back to an empty mapping when
    # the key is absent or null, which callers that select no covidcast geos do.
    covidcast_geographic_values = data.get("covidCastGeographicValues") or {}

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
