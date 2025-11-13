from datetime import datetime, timedelta
from typing import Iterable, Union

import requests
from django.conf import settings
from epiweeks import Week

from base.models import GeographyUnit
from indicatorsets.utils import (
    generate_epivis_custom_title,
    generate_random_color,
    get_epiweek,
    group_by_property,
)


def epiweeks_in_date_range(start_date_str: str, end_date_str: str):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    start_week = Week.fromdate(start_date)
    end_week = Week.fromdate(end_date)

    weeks = []
    seen = set()
    d = start_week.startdate()
    while d <= end_week.enddate():
        w = Week.fromdate(d)
        key = (w.year, w.week)
        if key not in seen:
            weeks.append(w)
            seen.add(key)
        d += timedelta(days=7)
    return weeks


def _epiweek_key(w: Week) -> int:
    # Matches API time_value format YYYYWW, e.g. 202032
    return w.year * 100 + w.week


def _epiweek_label(w: Week) -> str:
    return f"{w.year}-W{w.week:02d}"


def get_available_geos(indicators):
    geo_values = []
    grouped_indicators = group_by_property(indicators, "data_source")
    for data_source, indicators in grouped_indicators.items():
        indicators_str = ",".join(indicator["name"] for indicator in indicators)
        response = requests.get(
            f"{settings.EPIDATA_URL}covidcast/geo_indicator_coverage",
            params={"data_source": data_source, "signals": indicators_str},
            auth=("epidata", settings.EPIDATA_API_KEY),
        )
        if response.status_code == 200:
            data = response.json()
            if len(data["epidata"]):
                geo_values.extend(data["epidata"])
    unique_values = set(geo_values)
    geo_levels = set([el.split(":")[0] for el in unique_values])
    geo_unit_ids = set([geo_value.split(":")[1] for geo_value in unique_values])
    geographic_granularities = [
        {
            "id": f"{geo_unit.geo_level.name}:{geo_unit.geo_id}",
            "geoType": geo_unit.geo_level.name,
            "text": geo_unit.display_name,
            "geoTypeDisplayName": geo_unit.geo_level.display_name,
        }
        for geo_unit in GeographyUnit.objects.filter(geo_level__name__in=geo_levels)
        .filter(geo_id__in=geo_unit_ids)
        .prefetch_related("geo_level")
        .order_by("level")
    ]
    grouped_geographic_granularities = group_by_property(
        geographic_granularities, "geoTypeDisplayName"
    )
    geographic_granularities = []
    for key, value in grouped_geographic_granularities.items():
        geographic_granularities.append(
            {
                "text": key,
                "children": value,
            }
        )
    return geographic_granularities


def get_covidcast_data(indicator, start_date, end_date, geo, api_key):
    if indicator["_endpoint"] == "covidcast":
        time_values = f"{start_date}--{end_date}"
        if indicator["time_type"] == "week":
            start_day, end_day = get_epiweek(start_date, end_date)
            time_values = f"{start_day}-{end_day}"
        geo_type, geo_value = geo.split(":")
        params = {
            "time_type": indicator["time_type"],
            "time_values": time_values,
            "data_source": indicator["data_source"],
            "signal": indicator["name"],
            "geo_type": geo_type,
            "geo_values": geo_value.lower(),
            "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
        }
        response = requests.get(f"{settings.EPIDATA_URL}covidcast", params=params)
        if response.status_code == 200:
            response_data = response.json()
            if len(response_data["epidata"]):
                return response_data["epidata"]
    return []


def prepare_chart_series_multi(
    api_rows: list[dict],
    start_date: str,
    end_date: str,
    series_by: Union[str, Iterable[str]] = "signal",
):
    """
    api_rows: list of dicts with at least 'time_value' (YYYYWW) and 'value'
    series_by: a field name (e.g., 'signal' or 'geo_value') or an iterable of fields (e.g., ('signal','geo_value'))
    returns: { labels: [...], datasets: [{ label, data }, ...] }
    """
    # 1) Build aligned epiweek axis
    weeks = epiweeks_in_date_range(start_date, end_date)
    labels = [_epiweek_label(w) for w in weeks]
    keys = [_epiweek_key(w) for w in weeks]

    # 2) Group rows by series key
    if isinstance(series_by, (list, tuple)):

        def series_key_of(row):
            return tuple(row.get(k) for k in series_by)

        def series_label_of(key):
            return " - ".join(str(k) for k in key)

    else:

        def series_key_of(row):
            return row.get(series_by)

        def series_label_of(key):
            return str(key)

    series_to_values: dict[object, dict[int, float]] = {}
    for row in api_rows:
        tv = row.get("time_value")
        # If the API returned daily values (YYYYMMDD), convert to epiweek key (YYYYWW)
        if tv is not None and (row.get("time_type") == "day"):
            try:
                tv_str = str(tv)
                year = int(tv_str[0:4])
                month = int(tv_str[4:6])
                day = int(tv_str[6:8])
                d = datetime(year, month, day).date()
                w = Week.fromdate(d)
                tv = _epiweek_key(w)
            except Exception:
                # Skip malformed dates
                tv = None
        if tv is None:
            continue
        skey = series_key_of(row)
        if skey not in series_to_values:
            series_to_values[skey] = {}
        # last one wins if duplicates
        series_to_values[skey][tv] = row.get("value", None)

    # 3) Align each series to the epiweek axis, filling with None
    datasets = []
    for skey, tv_map in series_to_values.items():
        data = [tv_map.get(k, None) for k in keys]
        datasets.append({"label": series_label_of(skey), "data": data})

    return {"labels": labels, "datasets": datasets}


def normalize_dataset(data):
    """
    Normalize a dataset to 0-100% range based on its min/max.
    Preserves None values for missing data.
    """
    # Filter out None values for min/max calculation
    numeric_values = [v for v in data if v is not None and not (isinstance(v, float) and (v != v or v in (float('inf'), float('-inf'))))]
    
    if not numeric_values:
        return data  # Return as-is if no valid numeric values
    
    min_val = min(numeric_values)
    max_val = max(numeric_values)
    range_val = (max_val - min_val) or 1  # Avoid division by zero
    
    # Normalize each value
    normalized = []
    for value in data:
        if value is None:
            normalized.append(None)
        elif isinstance(value, float) and (value != value or value in (float('inf'), float('-inf'))):
            normalized.append(None)
        else:
            normalized.append(((value - min_val) / range_val) * 100)
    
    return normalized


def get_chart_data(indicators, geography):
    chart_data = {"labels": [], "datasets": []}
    geo_type, geo_value = geography.split(":")
    geo_display_name = GeographyUnit.objects.get(
        geo_level__name=geo_type, geo_id=geo_value
    ).display_name
    for indicator in indicators:
        title = generate_epivis_custom_title(indicator, geo_display_name)
        color = generate_random_color()
        data = get_covidcast_data(
            indicator, "2010-01-01", "2025-01-31", geography, settings.EPIDATA_API_KEY
        )
        if data:
            series = prepare_chart_series_multi(
                data,
                "2020-01-01",
                "2025-01-31",
                series_by="signal",  # label per indicator (adjust to ("signal","geo_value") if needed)
            )
            # Apply readable label, color, and normalize data for each dataset
            for ds in series["datasets"]:
                ds["label"] = f"{title} - {ds['label']}"
                ds["borderColor"] = color
                ds["backgroundColor"] = f"{color}33"
                # Normalize data to 0-100% range
                if ds.get("data"):
                    ds["data"] = normalize_dataset(ds["data"])
            # Initialize labels once; assume same date range for all
            if not chart_data["labels"]:
                chart_data["labels"] = series["labels"]
            chart_data["datasets"].extend(series["datasets"])
    return chart_data
