from import_export.fields import Field

from datasources.models import SourceSubdivision, OtherEndpointSourceSubdivision
from base.resources import CustomModelResource


def strip_all_string_values(row) -> None:
    for key, value in row.items():
        # Check if the value is a string and not None
        if isinstance(value, str):
            row[key] = value.strip()


class SourceSubdivisionResource(CustomModelResource):
    import_source_types = ("covidcast",)

    def get_import_deletion_queryset(self):
        queryset = SourceSubdivision.objects.all()
        if self.import_source_types:
            queryset = queryset.filter(source_type__in=self.import_source_types)
        return queryset

    def after_import(self, dataset, result, **kwargs):
        if not kwargs.get("dry_run", False):
            self.get_import_deletion_queryset().exclude(
                pk__in=self.imported_rows_pks
            ).delete()

    name = Field(
        attribute="name",
        column_name="Source Subdivision",
    )
    display_name = Field(
        attribute="display_name",
        column_name="External Name",
    )
    external_name = Field(
        attribute="external_name",
        column_name="Display Name",
    )
    description = Field(
        attribute="description",
        column_name="Description",
    )
    license = Field(
        attribute="license",
        column_name="License",
    )
    dua = Field(
        attribute="dua",
        column_name="DUA",
    )
    datasource_name = Field(
        attribute="datasource_name",
        column_name="DB Source",
    )

    class Meta:
        model = SourceSubdivision
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = True
        fields = (
            "name",
            "display_name",
            "external_name",
            "description",
            "license",
            "dua",
            "datasource_name",
        )
        exclude = ("id", )


class OtherEndpointSourceSubdivisionResource(SourceSubdivisionResource):
    import_source_types = ("other_endpoint",)

    class Meta:
        model = OtherEndpointSourceSubdivision
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = True
        fields = (
            "name",
            "display_name",
            "external_name",
            "description",
            "license",
            "dua",
            "datasource_name",
        )
        exclude = ("id", )

    def before_import_row(self, row, **kwargs):
        strip_all_string_values(row)

    def after_save_instance(self, instance, row, **kwargs):
        instance.source_type = "other_endpoint"
        instance.save()
