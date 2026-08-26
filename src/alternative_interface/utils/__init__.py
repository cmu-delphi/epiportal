"""Utilities for the alternative (express) interface.

Split into focused modules by responsibility; this package re-exports the
public names so existing ``from alternative_interface.utils import ...``
imports keep working. Prefer importing from the specific submodule in new code.
"""

from alternative_interface.utils.charts import get_chart_data
from alternative_interface.utils.epidata import (
    get_covidcast_data,
    get_fluview_data,
)
from alternative_interface.utils.geos import get_available_geos
from alternative_interface.utils.normalization import normalize_dataset
from alternative_interface.utils.series import prepare_chart_series_multi
from alternative_interface.utils.timeline import (
    _day_key,
    _day_label,
    _epiweek_key,
    _epiweek_label,
    days_in_date_range,
    epiweeks_in_date_range,
)

__all__ = [
    "_day_key",
    "_day_label",
    "_epiweek_key",
    "_epiweek_label",
    "days_in_date_range",
    "epiweeks_in_date_range",
    "get_available_geos",
    "get_chart_data",
    "get_covidcast_data",
    "get_fluview_data",
    "normalize_dataset",
    "prepare_chart_series_multi",
]
