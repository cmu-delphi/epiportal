from datetime import datetime, timedelta
from typing import Iterable, Union

import requests
from django.conf import settings
from epiweeks import Week

from base.models import GeographyUnit
from indicatorsets.utils import (
    generate_random_color,
    get_epiweek,
    group_by_property,
)
from alternative_interface.helper import (
    COVIDCAST_FLUVIEW_LOCATIONS_MAPPING,
)

from alternative_interface.models import ExpressViewIndicator


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


def _day_key(d: datetime.date) -> int:
    # Matches API time_value format YYYYMMDD, e.g. 20240115
    return d.year * 10000 + d.month * 100 + d.day


def _day_label(d: datetime.date) -> str:
    return d.strftime("%Y-%m-%d")


def days_in_date_range(start_date_str: str, end_date_str: str):
    """Generate all days in the date range."""
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    days = []
    d = start_date
    while d <= end_date:
        days.append(d)
        d += timedelta(days=1)
    return days


def get_available_geos(indicators):
    if indicators:
        geo_values = []
        grouped_indicators = group_by_property(indicators, "data_source")
        sources = grouped_indicators.keys()
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
        if "fluview" in sources:
            geographic_granularities.extend(
                [
                    {
                        "id": f"{geo_unit.geo_level.name}:{geo_unit.geo_id}",
                        "geoType": geo_unit.geo_level.name,
                        "text": geo_unit.display_name,
                        "geoTypeDisplayName": geo_unit.geo_level.display_name,
                    }
                    for geo_unit in GeographyUnit.objects.filter(
                        geo_level__name__in=[
                            "census-region",
                            "us-territory",
                            "us-city",
                            "ny_minus_jfk",
                        ]
                    )
                    .prefetch_related("geo_level")
                    .order_by("level")
                ]
            )
    else:
        geographic_granularities = [
            {
                "id": f"{geo_unit.geo_level.name}:{geo_unit.geo_id}",
                "geoType": geo_unit.geo_level.name,
                "text": geo_unit.display_name,
                "geoTypeDisplayName": geo_unit.geo_level.display_name,
            }
            for geo_unit in GeographyUnit.objects.all()
            .prefetch_related("geo_level")
            .order_by("level")
        ]
        # Group by geoTypeDisplayName to match the expected format
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


def get_fluview_data(indicator, geo, start_date, end_date, api_key):
    region = None
    try:
        region = COVIDCAST_FLUVIEW_LOCATIONS_MAPPING[geo]
    except KeyError:
        region = geo.split(":")[1]
    time_values = f"{start_date}--{end_date}"
    if indicator["time_type"] == "week":
        start_day, end_day = get_epiweek(start_date, end_date)
        time_values = f"{start_day}-{end_day}"
    params = {
        "regions": region,
        "epiweeks": time_values,
        "api_key": api_key if api_key else settings.EPIDATA_API_KEY,
    }
    response = requests.get(
        f"{settings.EPIDATA_URL}{indicator['data_source']}", params=params
    )
    if response.status_code == 200:
        data = response.json()
        if len(data["epidata"]):
            return [
                {
                    "time_value": el["epiweek"],
                    "value": el[indicator["name"]],
                    "signal": indicator["name"],
                    "time_type": indicator["time_type"],
                }
                for el in data["epidata"]
            ]
    return []


def prepare_chart_series_multi(
    api_rows: list[dict],
    start_date: str,
    end_date: str,
    series_by: Union[str, Iterable[str]] = "signal",
    time_type: str = None,
):
    """
    api_rows: list of dicts with at least 'time_value' (YYYYWW or YYYYMMDD) and 'value'
    series_by: a field name (e.g., 'signal' or 'geo_value') or an iterable of fields (e.g., ('signal','geo_value'))
    time_type: 'week' or 'day' - determines how to interpret time_value
    returns: { labels: [...], dayLabels: [...], timePositions: [...], datasets: [{ label, data, timeType }, ...] }
    """
    # 1) Build unified timeline with both days and weeks
    days = days_in_date_range(start_date, end_date)
    weeks = epiweeks_in_date_range(start_date, end_date)

    # Create a unified timeline: each position can be either a day or a week
    # We'll use day positions as the base, and mark week positions
    day_keys = [_day_key(d) for d in days]
    week_keys = [_epiweek_key(w) for w in weeks]

    # Create mapping: week_key -> list of day_keys in that week
    week_to_days = {}
    for w in weeks:
        week_start = w.startdate()
        week_end = w.enddate()
        week_key = _epiweek_key(w)
        week_to_days[week_key] = []
        for d in days:
            if week_start <= d <= week_end:
                week_to_days[week_key].append(_day_key(d))

    # Build labels and time positions
    # timePositions will indicate: 'day' or 'week' for each position
    labels = []  # Primary labels (weeks)
    day_labels = []  # Secondary labels (days)
    time_positions = []  # 'day' or 'week' for each position

    # Use days as the base timeline
    for d in days:
        day_key = _day_key(d)
        day_labels.append(_day_label(d))

        # Check if this day is the start of a week
        w = Week.fromdate(d)
        week_key = _epiweek_key(w)
        if week_key in week_keys and d == w.startdate():
            labels.append(_epiweek_label(w))
            time_positions.append("week")
        else:
            # Check if any week contains this day
            is_in_week = any(day_key in week_to_days.get(wk, []) for wk in week_keys)
            if is_in_week:
                labels.append("")  # Empty label for days within weeks
                time_positions.append("day")
            else:
                labels.append("")
                time_positions.append("day")

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

    # 3) Process data based on time_type
    series_to_values: dict[object, dict[int, float]] = {}
    detected_time_type = time_type

    for row in api_rows:
        tv = row.get("time_value")
        row_time_type = row.get("time_type") or time_type

        if tv is None:
            continue

        # Determine time_type if not provided
        if detected_time_type is None:
            # Try to detect from time_value format
            tv_str = str(tv)
            if len(tv_str) == 8:  # YYYYMMDD format
                detected_time_type = "day"
            elif len(tv_str) == 6:  # YYYYWW format
                detected_time_type = "week"
            else:
                detected_time_type = row_time_type or "week"

        # Use row's time_type if available, otherwise use detected
        actual_time_type = row_time_type or detected_time_type

        # Convert time_value to appropriate key
        if actual_time_type == "day":
            try:
                tv_str = str(tv)
                if len(tv_str) == 8:
                    year = int(tv_str[0:4])
                    month = int(tv_str[4:6])
                    day = int(tv_str[6:8])
                    d = datetime(year, month, day).date()
                    tv = _day_key(d)
                else:
                    continue
            except Exception:
                continue
        else:  # week
            try:
                tv_str = str(tv)
                if len(tv_str) == 6:
                    year = int(tv_str[0:4])
                    week = int(tv_str[4:6])
                    w = Week(year, week)
                    tv = _epiweek_key(w)
                elif len(tv_str) == 8:
                    # Convert day to week
                    year = int(tv_str[0:4])
                    month = int(tv_str[4:6])
                    day = int(tv_str[6:8])
                    d = datetime(year, month, day).date()
                    w = Week.fromdate(d)
                    tv = _epiweek_key(w)
                else:
                    continue
            except Exception:
                continue

        skey = series_key_of(row)
        if skey not in series_to_values:
            series_to_values[skey] = {}
        # last one wins if duplicates
        series_to_values[skey][tv] = row.get("value", None)

    # 4) Align each series to the unified timeline (day-based)
    datasets = []
    for skey, tv_map in series_to_values.items():
        data = []
        # Determine if this series is weekly or daily based on its keys
        series_keys = list(tv_map.keys())
        series_time_type = detected_time_type or "week"

        if series_keys:
            # Check if keys match day format (8 digits) or week format (6 digits)
            first_key = series_keys[0]
            if first_key >= 10000000:  # Day key (YYYYMMDD >= 10000000)
                series_time_type = "day"
                # Map directly to day positions
                for day_key in day_keys:
                    data.append(tv_map.get(day_key, None))
            else:  # Week key (YYYYWW < 10000000)
                series_time_type = "week"
                # Map week values to day positions
                # For each day, check if it's the start of a week that has data
                for d in days:
                    w = Week.fromdate(d)
                    week_key = _epiweek_key(w)
                    # If this is the start of the week and we have data for this week
                    if d == w.startdate() and week_key in tv_map:
                        data.append(tv_map.get(week_key, None))
                    else:
                        # For other days in the week, use None
                        data.append(None)
        else:
            data = [None] * len(day_keys)

        datasets.append(
            {"label": series_label_of(skey), "data": data, "timeType": series_time_type}
        )

    return {
        "labels": labels,
        "dayLabels": day_labels,
        "timePositions": time_positions,
        "datasets": datasets,
    }


def normalize_dataset(
    data, day_labels=None, initial_view_start=None, initial_view_end=None
):
    """
    Scale a dataset so that its highest value during the displayed 2 years is set to 100.
    Multiplies each value by a constant (100 / max_value_in_range).
    Preserves None values for missing data.
    """
    if not data:
        return data

    # If we have the initial view range, scale based on max value in that range
    if (
        day_labels
        and initial_view_start
        and initial_view_end
        and len(day_labels) == len(data)
    ):
        # Find indices that fall within the initial view range (2 years)
        view_indices = []
        for i, day_label in enumerate(day_labels):
            if initial_view_start <= day_label <= initial_view_end:
                view_indices.append(i)

        # Find max value only in the view range
        view_values = [
            data[i]
            for i in view_indices
            if i < len(data)
            and data[i] is not None
            and not (
                isinstance(data[i], float)
                and (data[i] != data[i] or data[i] in (float("inf"), float("-inf")))
            )
        ]

        if view_values:
            max_val_in_range = max(view_values)
            if max_val_in_range > 0:
                # Scale factor: multiply by (100 / max_value_in_range)
                scale_factor = 100.0 / max_val_in_range

                # Scale all values in the dataset
                normalized = []
                for value in data:
                    if value is None:
                        normalized.append(None)
                    elif isinstance(value, float) and (
                        value != value or value in (float("inf"), float("-inf"))
                    ):
                        normalized.append(None)
                    else:
                        normalized.append(value * scale_factor)
                return normalized

    # Fallback: if no view range provided, scale based on max value in entire dataset
    numeric_values = [
        v
        for v in data
        if v is not None
        and not (
            isinstance(v, float) and (v != v or v in (float("inf"), float("-inf")))
        )
    ]

    if not numeric_values:
        return data  # Return as-is if no valid numeric values

    max_val = max(numeric_values)
    if max_val <= 0:
        return data  # Return as-is if max is 0 or negative

    # Scale so max value = 100
    scale_factor = 100.0 / max_val

    # Scale each value
    normalized = []
    for value in data:
        if value is None:
            normalized.append(None)
        elif isinstance(value, float) and (
            value != value or value in (float("inf"), float("-inf"))
        ):
            normalized.append(None)
        else:
            normalized.append(value * scale_factor)

    return normalized


def get_chart_data(indicators, geography):
    chart_data = {"labels": [], "dayLabels": [], "timePositions": [], "datasets": []}

    # Calculate date range: last 2 years from today for initial view
    today = datetime.now().date()
    two_years_ago = today - timedelta(days=730)
    # Format dates as strings
    end_date = today.strftime("%Y-%m-%d")
    start_date = two_years_ago.strftime("%Y-%m-%d")

    # Store the initial view range (last 2 years)
    chart_data["initialViewStart"] = start_date
    chart_data["initialViewEnd"] = end_date

    # Fetch data from a wider range (10 years) for scrolling
    ten_years_ago = today - timedelta(days=3650)  # ~10 years
    data_start_date = ten_years_ago.strftime("%Y-%m-%d")
    data_end_date = today.strftime("%Y-%m-%d")

    express_view_indicators_qs = ExpressViewIndicator.objects.all().prefetch_related("indicator", "indicator__source")

    for indicator in indicators:
        title = express_view_indicators_qs.get(indicator__name=indicator["name"], indicator__source__name=indicator["data_source"]).display_name
        color = generate_random_color()
        indicator_time_type = indicator.get("time_type", "week")
        data = None
        if indicator["_endpoint"] == "covidcast":
            data = get_covidcast_data(
                indicator,
                data_start_date,
                data_end_date,
                geography,
                settings.EPIDATA_API_KEY,
            )
        elif indicator["data_source"] in ["fluview", "fluview_clinical"]:
            data = get_fluview_data(
                indicator,
                geography,
                data_start_date,
                data_end_date,
                settings.EPIDATA_API_KEY,
            )
        if data:
            # Prepare series with full data range for scrolling
            series = prepare_chart_series_multi(
                data,
                data_start_date,
                data_end_date,
                series_by="signal",  # label per indicator (adjust to ("signal","geo_value") if needed)
                time_type=indicator_time_type,
            )
            # Initialize labels once; assume same date range for all
            if not chart_data["labels"]:
                chart_data["labels"] = series["labels"]
                chart_data["dayLabels"] = series["dayLabels"]
                chart_data["timePositions"] = series["timePositions"]

            # Apply readable label, color, and normalize data for each dataset
            for ds in series["datasets"]:
                ds["label"] = title
                ds["borderColor"] = color
                ds["backgroundColor"] = f"{color}33"
                # Scale data so max value in displayed 2 years = 100
                if ds.get("data"):
                    ds["data"] = normalize_dataset(
                        ds["data"],
                        day_labels=chart_data["dayLabels"],
                        initial_view_start=chart_data["initialViewStart"],
                        initial_view_end=chart_data["initialViewEnd"],
                    )
            chart_data["datasets"].extend(series["datasets"])
    return chart_data
