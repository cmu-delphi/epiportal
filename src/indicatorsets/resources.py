from import_export import resources
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget

from base.models import GeographicScope, Geography, Pathogen, SeverityPyramidRung
from base.resources import CustomModelResource
from base.sheet_values import (
    drop_duplicate_rows,
    geographic_scope_id,
    geography_ids,
    is_unrecognised_bool,
    normalize_sheet_date,
    parse_bool,
    pathogen_ids,
    severity_pyramid_rung_ids,
    strip_column,
)
from indicatorsets.models import (
    KIND_CHOICES,
    ColumnDescription,
    FilterDescription,
    IndicatorSet,
    OriginalDataProvider,
)

USED_IN = "indicatorsets"
KINDS = {kind for kind, _ in KIND_CHOICES}
PROVIDER_GROUP_BY_KIND = {"us_states": "us_states", "non_delphi": "individual"}


def strip_all_string_values(row) -> None:
    for key, value in row.items():
        if isinstance(value, str):
            row[key] = value.strip()


def original_data_provider_id(name: str) -> int | None:
    if not name:
        return None
    provider, _ = OriginalDataProvider.objects.get_or_create(name=name)
    return provider.id


class IndicatorSetResource(CustomModelResource):
    required_columns = ("show_in_epiportal", "kind")

    name = Field(attribute="name", column_name="indicator_set")
    short_name = Field(attribute="short_name", column_name="short_name")
    description = Field(attribute="description", column_name="description")
    kind = Field(attribute="kind", column_name="kind")
    maintainer_name = Field(attribute="maintainer_name", column_name="maintainer")
    maintainer_email = Field(
        attribute="maintainer_email", column_name="email_of_maintainer"
    )
    original_data_provider = Field(
        attribute="original_data_provider",
        column_name="original_data_provider",
        widget=ForeignKeyWidget(OriginalDataProvider),
    )
    epidata_endpoint = Field(attribute="epidata_endpoint", column_name="v4_endpoint")
    language = Field(attribute="language", column_name="language")
    origin_datasource = Field(
        attribute="origin_datasource", column_name="source_dataset"
    )
    pathogens = Field(
        attribute="pathogens",
        column_name="pathogen",
        widget=ManyToManyWidget(Pathogen),
    )
    data_type = Field(attribute="data_type", column_name="types_of_data")
    geographic_scope = Field(
        attribute="geographic_scope",
        column_name="geographic_scope",
        widget=ForeignKeyWidget(GeographicScope),
    )
    geographic_levels = Field(
        attribute="geographic_levels",
        column_name="geographic_levels",
        widget=ManyToManyWidget(Geography),
    )
    preprocessing_description = Field(
        attribute="preprocessing_description", column_name="pre_processing"
    )
    temporal_granularity = Field(
        attribute="temporal_granularity", column_name="temporal_granularity"
    )
    temporal_scope_start = Field(
        attribute="temporal_scope_start", column_name="temporal_scope_start"
    )
    temporal_scope_end = Field(
        attribute="temporal_scope_end", column_name="temporal_scope_end"
    )
    ongoing = Field(attribute="ongoing", column_name="ongoing")
    reporting_cadence = Field(
        attribute="reporting_cadence", column_name="reporting_cadence"
    )
    reporting_lag = Field(attribute="reporting_lag", column_name="reporting_lag")
    revision_cadence = Field(
        attribute="revision_cadence", column_name="revision_cadence"
    )
    demographic_scope = Field(attribute="demographic_scope", column_name="population")
    demographic_granularity = Field(
        attribute="demographic_granularity", column_name="population_stratifiers"
    )
    severity_pyramid_rungs = Field(
        attribute="severity_pyramid_rungs",
        column_name="surveillance_categories",
        widget=ManyToManyWidget(SeverityPyramidRung),
    )
    censoring = Field(attribute="censoring", column_name="censoring")
    missingness = Field(attribute="missingness", column_name="missingness")
    dua_required = Field(attribute="dua_required", column_name="dua_required")
    license = Field(attribute="license", column_name="data_use_terms")
    dataset_location = Field(
        attribute="dataset_location", column_name="dataset_location"
    )
    documentation_link = Field(
        attribute="documentation_link", column_name="documentation_link"
    )

    class Meta:
        model = IndicatorSet
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = True
        fields = (
            "name",
            "short_name",
            "description",
            "kind",
            "maintainer_name",
            "maintainer_email",
            "original_data_provider",
            "epidata_endpoint",
            "language",
            "origin_datasource",
            "pathogens",
            "data_type",
            "geographic_scope",
            "geographic_levels",
            "preprocessing_description",
            "temporal_granularity",
            "temporal_scope_start",
            "temporal_scope_end",
            "ongoing",
            "reporting_cadence",
            "reporting_lag",
            "revision_cadence",
            "demographic_scope",
            "demographic_granularity",
            "severity_pyramid_rungs",
            "censoring",
            "missingness",
            "dua_required",
            "license",
            "dataset_location",
            "documentation_link",
        )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.warnings: list[str] = []

    def before_import(self, dataset, **kwargs):
        super().before_import(dataset, **kwargs)
        strip_column(dataset, "indicator_set")
        self.warnings = [
            f"Duplicate indicator set rows differ: {key}"
            for key in drop_duplicate_rows(dataset, "indicator_set")
        ]

    def before_import_row(self, row, **kwargs):
        strip_all_string_values(row)
        if row.get("indicator_set") and is_unrecognised_bool(
            row.get("show_in_epiportal")
        ):
            self.warnings.append(
                f"Unrecognised show_in_epiportal value "
                f"{row.get('show_in_epiportal')!r} (hidden) for indicator set: "
                f"{row['indicator_set']}"
            )
        for column in ("show_in_epiportal", "ongoing", "dua_required"):
            row[column] = parse_bool(row.get(column))
        for column in ("temporal_scope_start", "temporal_scope_end"):
            row[column] = normalize_sheet_date(row.get(column))
        row["pathogen"] = pathogen_ids(row.get("pathogen"), USED_IN)
        row["geographic_levels"] = geography_ids(row.get("geographic_levels"), USED_IN)
        row["surveillance_categories"] = severity_pyramid_rung_ids(
            row.get("surveillance_categories"), USED_IN
        )
        row["geographic_scope"] = geographic_scope_id(
            row.get("geographic_scope"), USED_IN
        )
        row["original_data_provider"] = original_data_provider_id(
            row.get("original_data_provider")
        )
        if not row.get("data_use_terms"):
            row["data_use_terms"] = "None found"

    def is_excluded(self, row) -> bool:
        if not row.get("indicator_set") or not row.get("show_in_epiportal"):
            return True
        if row.get("kind") not in KINDS:
            warning = (
                f"Unknown kind {row.get('kind')!r} for indicator set: "
                f"{row['indicator_set']}"
            )
            # Called more than once per row; set names are unique after dedupe.
            if warning not in self.warnings:
                self.warnings.append(warning)
            return True
        return False

    def after_save_instance(self, instance, row, **kwargs):
        provider = instance.original_data_provider
        if provider is None:
            return
        group = PROVIDER_GROUP_BY_KIND.get(instance.kind)
        if instance.kind == "delphi" and provider.name.startswith("US "):
            group = "us_government"
        if group and provider.group != group:
            provider.group = group
            provider.save(update_fields=["group"])


class ColumnDescriptionResource(resources.ModelResource):
    name = Field(attribute="name", column_name="Field Name")
    description = Field(
        attribute="description",
        column_name="Column Description",
    )

    class Meta:
        model = ColumnDescription
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = False
        fields = (
            "name",
            "description",
        )

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if not row["Field Name"]:
            return True


class FilterDescriptionResource(resources.ModelResource):
    name = Field(attribute="name", column_name="Field Name")
    description = Field(attribute="description", column_name="Tooltip Text")

    class Meta:
        model = FilterDescription
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = False
        fields = (
            "name",
            "description",
        )

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if not row["Field Name"]:
            return True
