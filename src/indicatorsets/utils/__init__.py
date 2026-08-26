"""Utilities for the indicatorsets app.

Split into focused modules by responsibility; this package re-exports the public
names so existing ``from indicatorsets.utils import ...`` imports keep working.
Prefer importing from the specific submodule in new code.
"""

from indicatorsets.utils.constants import (
    FLUVIEW_INDICATORS_MAPPING,
    INVALID_API_KEY_MESSAGE,
    NO_DATA_MESSAGE,
)
from indicatorsets.utils.data_providers import (
    get_grouped_original_data_provider_choices,
    parse_original_data_provider_ids,
    sort_data_providers,
)
from indicatorsets.utils.epidata import has_epidata_results
from indicatorsets.utils.epivis import (
    generate_covidcast_dataset_epivis,
    generate_epivis_custom_title,
    generate_epiweek_dataset_epivis,
    generate_fluview_dataset_epivis,
    generate_nwss_dataset_epivis,
    generate_pophive_dataset_epivis,
)
from indicatorsets.utils.exceptions import InvalidApiKeyError
from indicatorsets.utils.exports import (
    generate_covidcast_indicators_export_url,
    generate_epiweek_export_url,
    generate_nwss_export_url,
    generate_pophive_export_url,
)
from indicatorsets.utils.form_logging import log_form_data, log_form_stats
from indicatorsets.utils.geos import (
    get_indicators_based_on_geo_epidata,
    get_indicators_based_on_geo_epidata_v5,
    get_list_of_indicators_filtered_by_geo,
    get_num_locations_from_meta,
)
from indicatorsets.utils.helpers import (
    generate_random_color,
    get_epiweek,
    group_by_property,
    list_to_dict,
)
from indicatorsets.utils.previews import (
    get_preview_data,
    preview_covidcast_data,
    preview_epiweek_data,
    preview_nwss_data,
    preview_pophive_data,
)
from indicatorsets.utils.sources import EPIWEEK_SOURCES, EpiweekSource
from indicatorsets.utils.query_code import (
    generate_query_code_covidcast,
    generate_query_code_epiweek,
    generate_query_code_nwss,
    generate_query_code_pophive,
)

__all__ = [
    "EPIWEEK_SOURCES",
    "EpiweekSource",
    "FLUVIEW_INDICATORS_MAPPING",
    "INVALID_API_KEY_MESSAGE",
    "NO_DATA_MESSAGE",
    "InvalidApiKeyError",
    "generate_covidcast_dataset_epivis",
    "generate_covidcast_indicators_export_url",
    "generate_epivis_custom_title",
    "generate_epiweek_dataset_epivis",
    "generate_epiweek_export_url",
    "generate_fluview_dataset_epivis",
    "generate_nwss_dataset_epivis",
    "generate_nwss_export_url",
    "generate_pophive_dataset_epivis",
    "generate_pophive_export_url",
    "generate_query_code_covidcast",
    "generate_query_code_epiweek",
    "generate_query_code_nwss",
    "generate_query_code_pophive",
    "generate_random_color",
    "get_epiweek",
    "get_grouped_original_data_provider_choices",
    "get_indicators_based_on_geo_epidata",
    "get_indicators_based_on_geo_epidata_v5",
    "get_list_of_indicators_filtered_by_geo",
    "get_num_locations_from_meta",
    "get_preview_data",
    "group_by_property",
    "has_epidata_results",
    "list_to_dict",
    "log_form_data",
    "log_form_stats",
    "parse_original_data_provider_ids",
    "preview_covidcast_data",
    "preview_epiweek_data",
    "preview_nwss_data",
    "preview_pophive_data",
    "sort_data_providers",
]
