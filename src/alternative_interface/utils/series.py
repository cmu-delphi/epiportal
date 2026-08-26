"""Aligning Epidata rows onto a unified day-based chart timeline."""

from datetime import datetime
from typing import Iterable, Union

from epiweeks import Week

from alternative_interface.utils.timeline import (
    _day_key,
    _day_label,
    _epiweek_key,
    _epiweek_label,
    days_in_date_range,
    epiweeks_in_date_range,
)


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
