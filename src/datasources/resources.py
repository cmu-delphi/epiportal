from import_export import resources
from import_export.fields import Field

from datasources.models import SourceSubdivision, OtherEndpointSourceSubdivision


class SourceSubdivisionResource(resources.ModelResource):
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

    def after_save_instance(self, instance, row, **kwargs):
        instance.source_type = "other_endpoint"
        instance.save()
