from django.db.models import Max
from import_export import resources
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget

from base.models import GeographicScope, Geography, Pathogen, SeverityPyramidRung
from base.resources import GEOGRAPHIC_GRANULARITY_MAPPING
from indicatorsets.models import IndicatorSet


def process_geographic_scope(row) -> None:
    if row["Geographic Coverage"]:
        geographic_scope_name = row["Geographic Coverage"].strip()
        geographic_scope_obj, _ = GeographicScope.objects.get_or_create(
            name=geographic_scope_name,
            used_in="indicatorsets",
            defaults={
                "used_in": "indicatorsets",
            },
        )
        row["Geographic Coverage"] = geographic_scope_obj.id


def process_severity_pyramid_rungs(row) -> None:
    if row["Surveillance Categories"]:
        severity_pyramid_rungs = row["Surveillance Categories"].split(",")
        for spr in severity_pyramid_rungs:
            spr_name = spr.strip()
            severity_pyramid_rung_obj, _ = SeverityPyramidRung.objects.get_or_create(
                name=spr_name,
                used_in="indicatorsets",
                defaults={"display_name": spr_name.capitalize()},
            )


def process_pathogens(row) -> None:
    if row["Pathogen(s)/Syndrome(s)"]:
        pathogens = row["Pathogen(s)/Syndrome(s)"].split(",")
        for pathogen in pathogens:
            pathogen_name = pathogen.strip()
            pathogen_obj, _ = Pathogen.objects.get_or_create(
                name=pathogen_name,
                used_in="indicatorsets",
                defaults={
                    "display_name": pathogen_name.capitalize(),
                    "used_in": "indicatorsets",
                },
            )


def process_available_geographies(row) -> None:
    if row["Geographic Granularity - Delphi"]:
        available_geographies = row["Geographic Granularity - Delphi"].split(",")
        for geography in available_geographies:
            geography_name = geography.strip()
            default_params = {"used_in": "indicatorsets"}
            try:
                default_params.update(GEOGRAPHIC_GRANULARITY_MAPPING[geography_name])
            except KeyError:
                max_display_order_number = Geography.objects.filter(
                    used_in="indicatorsets"
                ).aggregate(Max("display_order_number"))["display_order_number__max"]
                default_params["display_order_number"] = max_display_order_number + 1
            geography_obj, _ = Geography.objects.get_or_create(
                name=geography_name,
                used_in="indicatorsets",
                defaults=default_params,
            )


class IndicatorSetResource(resources.ModelResource):
    name = Field(attribute="name", column_name="Indicator Set name* ")
    short_name = Field(attribute="short_name", column_name="Indicator Set Short Name")
    description = Field(
        attribute="description", column_name="Indicator Set Description*"
    )
    maintainer_name = Field(
        attribute="maintainer_name", column_name="Maintainer/\nKey Contact *"
    )
    maintainer_email = Field(
        attribute="maintainer_email", column_name="Email of maintainer/\nkey contact *"
    )
    organization = Field(attribute="organization", column_name="Organization")
    original_data_provider = Field(
        attribute="original_data_provider",
        column_name="Original Data Provider",
    )
    epidata_endpoint = Field(
        attribute="epidata_endpoint",
        column_name="Endpoint",
    )
    language = Field(attribute="language", column_name="Language (likely English) ")
    version_number = Field(
        attribute="version_number", column_name="Version Number \n(if applicable) "
    )
    origin_datasource = Field(
        attribute="origin_datasource",
        column_name="Source dataset from which data was derived (for aggregates or processed data) ",
    )
    pathogens = Field(
        attribute="pathogens",
        column_name="Pathogen(s)/Syndrome(s)",
        widget=ManyToManyWidget(Pathogen, field="name", separator=","),
    )
    data_type = Field(attribute="data_type", column_name="Type(s) of Data*")
    geographic_scope = Field(
        attribute="geographic_scope",
        column_name="Geographic Coverage",
        widget=ForeignKeyWidget(GeographicScope),
    )
    geographic_levels = Field(
        attribute="geographic_levels",
        column_name="Geographic Granularity - Delphi",
        widget=ManyToManyWidget(Geography, field="name", separator=","),
    )
    preprocessing_description = Field(
        attribute="preprocessing_description",
        column_name="Pre-processing",
    )
    temporal_scope_start = Field(
        attribute="temporal_scope_start", column_name="Temporal Scope Start"
    )
    temporal_scope_end = Field(
        attribute="temporal_scope_end", column_name="Temporal Scope End"
    )
    temporal_granularity = Field(
        attribute="temporal_granularity", column_name="Temporal Granularity"
    )
    reporting_cadence = Field(
        attribute="reporting_cadence", column_name="Reporting Cadence"
    )
    reporting_lag = Field(
        attribute="reporting_lag", column_name="Reporting Lag (nominal)"
    )
    demographic_scope = Field(attribute="demographic_scope", column_name="Population")
    revision_cadence = Field(
        attribute="revision_cadence", column_name="Revision Cadence"
    )
    demographic_granularity = Field(
        attribute="demographic_granularity", column_name="Population Stratifiers"
    )
    censoring = Field(attribute="censoring", column_name="Censoring")
    missingness = Field(attribute="missingness", column_name="Missingness")
    dua_required = Field(attribute="dua_required", column_name="DUA Required?")
    license = Field(attribute="license", column_name="Data Use Terms")
    dataset_location = Field(
        attribute="dataset_location", column_name="Dataset Location"
    )
    documentation_link = Field(
        attribute="documentation_link", column_name="Link to documentation"
    )
    severity_pyramid_rungs = Field(
        attribute="severity_pyramid_rungs",
        column_name="Surveillance Categories",
        widget=ManyToManyWidget(SeverityPyramidRung, field="name", separator=","),
    )

    class Meta:
        model = IndicatorSet
        import_id_fields = ("name", "original_data_provider")
        skip_unchanged = True
        report_skipped = False
        fields = (
            "name",
            "short_name",
            "description",
            "maintainer_name",
            "maintainer_email",
            "organization",
            "language",
            "version_number",
            "origin_datasource",
            "pathogens",
            "original_data_provider",
            "data_type",
            "geographic_scope",
            "geographic_levels",
            "preprocessing_description",
            "temporal_scope_start",
            "temporal_scope_end",
            "temporal_granularity",
            "reporting_cadence",
            "reporting_lag",
            "demographic_scope",
            "revision_cadence",
            "demographic_granularity",
            "censoring",
            "missingness",
            "dua_required",
            "license",
            "dataset_location",
            "documentation_link",
            "severity_pyramid_rungs",
            "epidata_endpoint",
        )

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if not row["Include in indicator app"]:
            return True

    def before_import_row(self, row, **kwargs):
        process_geographic_scope(row)
        process_severity_pyramid_rungs(row)
        process_pathogens(row)
        process_available_geographies(row)
