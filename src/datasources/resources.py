from import_export.fields import Field

from base.resources import CustomModelResource
from base.sheet_values import drop_duplicate_rows
from datasources.models import SourceSubdivision


def strip_all_string_values(row) -> None:
    for key, value in row.items():
        # Check if the value is a string and not None
        if isinstance(value, str):
            row[key] = value.strip()


class SourceSubdivisionResource(CustomModelResource):
    name = Field(
        attribute="name",
        column_name="source",
    )
    datasource_name = Field(
        attribute="datasource_name",
        column_name="db_source",
    )
    display_name = Field(
        attribute="display_name",
        column_name="name",
    )
    external_name = Field(
        attribute="external_name",
        column_name="external_name",
    )
    description = Field(
        attribute="description",
        column_name="description",
    )
    license = Field(
        attribute="license",
        column_name="license",
    )
    dua = Field(
        attribute="dua",
        column_name="dua",
    )

    class Meta:
        model = SourceSubdivision
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = True
        fields = (
            "name",
            "datasource_name",
            "display_name",
            "external_name",
            "description",
            "license",
            "dua",
        )
        exclude = ("id",)

    def before_import(self, dataset, **kwargs):
        super().before_import(dataset, **kwargs)
        self.warnings = [
            f"Duplicate source rows differ: {key}"
            for key in drop_duplicate_rows(dataset, "source")
        ]

    def before_import_row(self, row, **kwargs):
        strip_all_string_values(row)

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if not row.get("source"):
            return True
        return super().skip_row(instance, original, row, import_validation_errors)
