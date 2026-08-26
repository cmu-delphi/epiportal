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
