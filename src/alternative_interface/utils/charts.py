"""Building the express view's multi-indicator chart payload."""

from datetime import datetime, timedelta

from django.conf import settings

from alternative_interface.models import ExpressViewIndicator
from alternative_interface.utils.epidata import (
    get_covidcast_data,
    get_fluview_data,
)
from alternative_interface.utils.series import prepare_chart_series_multi
from indicatorsets.utils import generate_random_color


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

    title_by_key = {
        (e.indicator.name, e.indicator.source.name): e.display_name
        for e in ExpressViewIndicator.objects.select_related(
            "indicator", "indicator__source"
        )
    }
    for indicator in indicators:
        title = title_by_key[(indicator["name"], indicator["data_source"])]
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
                grouping_key = indicator.get("grouping_key")
                if grouping_key:
                    ds["groupingKey"] = grouping_key
                else:
                    # Assign a unique key to ensure individual normalization
                    ds["groupingKey"] = f"individual_{id(ds)}"
            chart_data["datasets"].extend(series["datasets"])

    # Group datasets and normalize together
    grouped_datasets = {}
    for ds in chart_data["datasets"]:
        key = ds.get("groupingKey")
        if key not in grouped_datasets:
            grouped_datasets[key] = []
        grouped_datasets[key].append(ds)

    for key, group in grouped_datasets.items():
        # Calculate global max for the group in the initial view range
        global_max = 0
        has_data = False

        # Helper to get numeric values in view range
        for ds in group:
            data = ds.get("data", [])
            day_labels = chart_data["dayLabels"]
            initial_view_start = chart_data["initialViewStart"]
            initial_view_end = chart_data["initialViewEnd"]

            if not data or not day_labels or len(data) != len(day_labels):
                continue

            view_indices = []
            for i, day_label in enumerate(day_labels):
                if initial_view_start <= day_label <= initial_view_end:
                    view_indices.append(i)

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
                current_max = max(view_values)
                if current_max > global_max:
                    global_max = current_max
                    has_data = True

        # If no data in view range, try overall max
        if not has_data:
            for ds in group:
                data = ds.get("data", [])
                numeric_values = [
                    v
                    for v in data
                    if v is not None
                    and not (
                        isinstance(v, float)
                        and (v != v or v in (float("inf"), float("-inf")))
                    )
                ]
                if numeric_values:
                    current_max = max(numeric_values)
                    if current_max > global_max:
                        global_max = current_max
                        has_data = True

        # Apply normalization
        scale_factor = 100.0 / global_max if has_data and global_max > 0 else 1.0

        for ds in group:
            if ds.get("data"):
                # Preserve original data before normalization
                ds["original_data"] = list(ds["data"])

                normalized = []
                for value in ds["data"]:
                    if value is None:
                        normalized.append(None)
                    elif isinstance(value, float) and (
                        value != value or value in (float("inf"), float("-inf"))
                    ):
                        normalized.append(None)
                    else:
                        normalized.append(value * scale_factor)
                ds["data"] = normalized
            # Remove temporary key
            if "groupingKey" in ds:
                del ds["groupingKey"]

    return chart_data
