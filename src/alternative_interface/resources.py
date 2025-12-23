from import_export import resources
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget
from indicators.models import Indicator

from alternative_interface.models import ExpressViewIndicator


def process_indicator(row):
    indicator_source = row.get("Indicator Source")
    indicator_name = row.get("Indicator Name")
    indicator = None
    if indicator_name and indicator_source:
        try:
            indicator = Indicator.objects.get(
                name=indicator_name, source__name=indicator_source
            )
        except Indicator.DoesNotExist:
            indicator = None
    if indicator:
        row["Indicator Name"] = indicator.id
    else:
        row["Indicator Name"] = None


class ExpressViewIndicatorResource(resources.ModelResource):
    menu_item = Field(attribute="menu_item", column_name="Menu Item")
    indicator = Field(
        attribute="indicator",
        column_name="Indicator Name",
        widget=ForeignKeyWidget(Indicator),
    )
    display_name = Field(
        attribute="display_name", column_name="text for display legend"
    )
    grouping_key = Field(
        attribute="grouping_key", column_name="tie together for scaling"
    )
    display_order = Field(
        attribute="display_order", column_name="Display Order"
    )

    def before_import_row(self, row, **kwargs):
        process_indicator(row)

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if not row["Indicator Name"]:
            return True

    class Meta:
        model = ExpressViewIndicator
        fields = (
            "menu_item",
            "indicator",
            "display_name",
            "grouping_key",
            "display_order",
        )
        import_id_fields = ("menu_item", "indicator")
        skip_unchanged = True
        report_skipped = True
        exclude = ("id",)
