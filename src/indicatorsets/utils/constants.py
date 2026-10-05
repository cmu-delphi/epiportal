"""Static messages and mappings shared across the indicatorsets utils package."""

FLUVIEW_INDICATORS_MAPPING = {"wili": "%wILI", "ili": "%ILI"}
INVALID_API_KEY_MESSAGE = (
    "API key does not exist. Register a new key at "
    "https://api.delphi.cmu.edu/epidata/admin/registration_form or contact "
    "delphi-support+privacy@andrew.cmu.edu to troubleshoot"
)

NO_DATA_MESSAGE = (
    "No data found for the selected parameters. Try adjusting the date range, "
    "indicators, or locations."
)

# Key, value pairs {"v4 name": "v5 name"}
MIGRATED_DATASOURCES = {
    "nhsn": "nhsn",
    "nssp": "nssp",
    "beta_nssp": "nssp",
    "beta_nssp_github": "nssp",
    "fluview": "fluview_ilinet",
    "fluview_clinical": "fluview_resp_lab_clinical",
    "nchs-mortality": "nchs_mortality",
    "flusurv": "flusurv",
}

# Epidata v5 keys every source on ``fill_method``, naming how gaps in the
# reported series were filled. Users pick one for the whole submission rather
# than per indicator, since a single value keeps mixed selections comparable.
FILL_METHODS = ("source", "fill_ave", "fill_zero")
DEFAULT_FILL_METHOD = ""

# Endpoints that are v5-native: they have no v4 equivalent to fall back to, so
# they are not in MIGRATED_DATASOURCES yet every request for them is a v5 one.
V5_NATIVE_ENDPOINTS = ("nwss", "pophive")
