"""Building the express view's multi-indicator chart payload."""

from datetime import datetime, timedelta

from django.conf import settings

from alternative_interface.models import ExpressViewIndicator
from alternative_interface.utils.epidata import (
    get_covidcast_data,
    get_fluview_data,
)
from alternative_interface.utils.normalization import (
    group_maximum,
    normalize_dataset,
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
    # Group datasets and normalize together, so series sharing a grouping key
    # stay comparable to one another rather than each peaking at 100.
    grouped_datasets = {}
    for ds in chart_data["datasets"]:
        grouped_datasets.setdefault(ds.get("groupingKey"), []).append(ds)

    for group in grouped_datasets.values():
        maximum, has_data = group_maximum(
            [ds.get("data", []) for ds in group],
            chart_data["dayLabels"],
            chart_data["initialViewStart"],
            chart_data["initialViewEnd"],
        )
        for ds in group:
            if ds.get("data"):
                # Preserve original data before normalization
                ds["original_data"] = list(ds["data"])
                ds["data"] = normalize_dataset(
                    ds["data"], max_value=maximum if has_data else 0
                )
            # Remove temporary key
            ds.pop("groupingKey", None)

    return chart_data
