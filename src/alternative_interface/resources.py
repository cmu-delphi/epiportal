from import_export.fields import Field
from import_export.results import RowResult
from import_export.widgets import ForeignKeyWidget
from base.resources import CustomModelResource
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


class ExpressViewIndicatorResource(CustomModelResource):
    required_columns = ("Menu Item", "Indicator Source", "Indicator Name")

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

    def get_field_names(self):
        return [self.get_field_name(field) for field in self.fields.values()]

    def before_import_row(self, row, **kwargs):
        if not row.get("Menu Item") or not row.get("Indicator Name"):
            return
        source_name = row.get("Indicator Source")
        indicator_name = row.get("Indicator Name")
        process_indicator(row)
        # Rows with an empty source are placeholders and stay quiet.
        if source_name and row["Indicator Name"] is None:
            self.warnings.append(
                f"Skipped dashboard row {row.get('Menu Item')!r}: indicator "
                f"{source_name}/{indicator_name} not found"
            )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.warnings: list[str] = []

    def before_import(self, dataset, **kwargs):
        super().before_import(dataset, **kwargs)
        self.warnings = []

    def is_excluded(self, row) -> bool:
        # before_import_row has swapped the indicator name for its id, or for
        # None when no such indicator exists.
        return not row.get("Menu Item") or not row.get("Indicator Name")

    def import_row(self, row, instance_loader, **kwargs):
        import_result = super().import_row(row, instance_loader, **kwargs)
        if import_result.import_type in [
            RowResult.IMPORT_TYPE_ERROR,
            RowResult.IMPORT_TYPE_INVALID,
        ]:
            import_result.diff = [row.get(name, "") for name in self.get_field_names()]
            import_result.diff.append(
                "Errors: {}\n{}".format(
                    [err.error for err in import_result.errors], row
                )
            )
            errors = [str(err.error) for err in import_result.errors]
            if import_result.validation_error is not None:
                errors.append(str(import_result.validation_error))
            self.warnings.append(
                "Skipped dashboard row {!r}: {}".format(
                    row.get("Menu Item"), "; ".join(errors)
                )
            )
            import_result.errors = []
            import_result.validation_error = None
            import_result.import_type = RowResult.IMPORT_TYPE_SKIP
        return import_result

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
