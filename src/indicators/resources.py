from import_export.fields import Field
from import_export.results import RowResult
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget

from base.models import GeographicScope, Geography, Pathogen, SeverityPyramidRung
from base.resources import CustomModelResource
from base.sheet_values import (
    geographic_scope_id,
    geography_ids,
    is_unrecognised_bool,
    normalize_sheet_date,
    parse_bool,
    pathogen_ids,
    severity_pyramid_rung_ids,
)
from datasources.models import SourceSubdivision
from indicators.models import Category, FormatType, Indicator, IndicatorType
from indicatorsets.models import IndicatorSet

USED_IN = "indicators"
BOOLEAN_COLUMNS = (
    "show_in_epiportal",
    "active",
    "ongoing",
    "is_smoothed",
    "is_weighted",
    "is_cumulative",
    "has_stderr",
    "has_sample_size",
)


def strip_all_string_values(row) -> None:
    for key, value in row.items():
        if isinstance(value, str):
            row[key] = value.strip()


def named_object_id(model, name: str) -> int | None:
    if not name:
        return None
    obj, _ = model.objects.get_or_create(name=name)
    return obj.id


class IndicatorResource(CustomModelResource):
    required_columns = ("show_in_epiportal",)

    source = Field(
        attribute="source",
        column_name="source",
        widget=ForeignKeyWidget(SourceSubdivision),
    )
    name = Field(attribute="name", column_name="indicator")
    indicator_set = Field(
        attribute="indicator_set",
        column_name="indicator_set",
        widget=ForeignKeyWidget(IndicatorSet),
    )
    display_name = Field(attribute="display_name", column_name="display_name")
    active = Field(attribute="active", column_name="active")
    short_description = Field(
        attribute="short_description", column_name="short_description"
    )
    description = Field(attribute="description", column_name="description")
    pathogens = Field(
        attribute="pathogens",
        column_name="pathogen",
        widget=ManyToManyWidget(Pathogen),
    )
    indicator_type = Field(
        attribute="indicator_type",
        column_name="indicator_type",
        widget=ForeignKeyWidget(IndicatorType),
    )
    geographic_scope = Field(
        attribute="geographic_scope",
        column_name="geographic_scope",
        widget=ForeignKeyWidget(GeographicScope),
    )
    available_geographies = Field(
        attribute="available_geographies",
        column_name="geographic_levels",
        widget=ManyToManyWidget(Geography),
    )
    temporal_scope_start = Field(
        attribute="temporal_scope_start", column_name="temporal_scope_start"
    )
    temporal_scope_start_note = Field(
        attribute="temporal_scope_start_note", column_name="temporal_scope_start_note"
    )
    temporal_scope_end = Field(
        attribute="temporal_scope_end", column_name="temporal_scope_end"
    )
    temporal_scope_end_note = Field(
        attribute="temporal_scope_end_note", column_name="temporal_scope_end_note"
    )
    ongoing = Field(attribute="ongoing", column_name="ongoing")
    time_type = Field(attribute="time_type", column_name="time_type")
    time_label = Field(attribute="time_label", column_name="time_label")
    reporting_cadence = Field(
        attribute="reporting_cadence", column_name="reporting_cadence"
    )
    typical_reporting_lag = Field(
        attribute="typical_reporting_lag", column_name="typical_reporting_lag"
    )
    typical_revision_cadence = Field(
        attribute="typical_revision_cadence", column_name="typical_revision_cadence"
    )
    demographic_scope = Field(attribute="demographic_scope", column_name="population")
    data_censoring = Field(attribute="data_censoring", column_name="data_censoring")
    severity_pyramid_rungs = Field(
        attribute="severity_pyramid_rungs",
        column_name="surveillance_categories",
        widget=ManyToManyWidget(SeverityPyramidRung),
    )
    missingness = Field(attribute="missingness", column_name="missingness")
    format_type = Field(
        attribute="format_type",
        column_name="format",
        widget=ForeignKeyWidget(FormatType),
    )
    category = Field(
        attribute="category",
        column_name="category",
        widget=ForeignKeyWidget(Category),
    )
    high_values_are = Field(attribute="high_values_are", column_name="high_values_are")
    is_smoothed = Field(attribute="is_smoothed", column_name="is_smoothed")
    is_weighted = Field(attribute="is_weighted", column_name="is_weighted")
    is_cumulative = Field(attribute="is_cumulative", column_name="is_cumulative")
    has_stderr = Field(attribute="has_stderr", column_name="has_stderr")
    has_sample_size = Field(attribute="has_sample_size", column_name="has_sample_size")
    organization_access_list = Field(
        attribute="organization_access_list", column_name="who_may_access"
    )
    organization_sharing_list = Field(
        attribute="organization_sharing_list", column_name="who_may_be_told"
    )
    restrictions = Field(attribute="restrictions", column_name="use_restrictions")
    license = Field(attribute="license", column_name="data_use_terms")
    dua_link = Field(attribute="dua_link", column_name="dua_link")
    documentation_link = Field(
        attribute="documentation_link", column_name="documentation_link"
    )

    class Meta:
        model = Indicator
        import_id_fields = ("name", "indicator_set", "source")
        skip_unchanged = True
        fields = (
            "source",
            "name",
            "indicator_set",
            "display_name",
            "active",
            "short_description",
            "description",
            "pathogens",
            "indicator_type",
            "geographic_scope",
            "available_geographies",
            "temporal_scope_start",
            "temporal_scope_start_note",
            "temporal_scope_end",
            "temporal_scope_end_note",
            "ongoing",
            "time_type",
            "time_label",
            "reporting_cadence",
            "typical_reporting_lag",
            "typical_revision_cadence",
            "demographic_scope",
            "data_censoring",
            "severity_pyramid_rungs",
            "missingness",
            "format_type",
            "category",
            "high_values_are",
            "is_smoothed",
            "is_weighted",
            "is_cumulative",
            "has_stderr",
            "has_sample_size",
            "organization_access_list",
            "organization_sharing_list",
            "restrictions",
            "license",
            "dua_link",
            "documentation_link",
        )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.warnings: list[str] = []

    def before_import(self, dataset, **kwargs):
        super().before_import(dataset, **kwargs)
        self.warnings = []

    def before_import_row(self, row, **kwargs):
        strip_all_string_values(row)
        set_name = row.get("indicator_set")
        indicator_set = (
            IndicatorSet.objects.filter(name=set_name).values("id", "kind").first()
        )
        row["_set_name"] = set_name
        row["_source_name"] = row.get("source")
        row["indicator_set"] = indicator_set["id"] if indicator_set else None
        row["_kind"] = indicator_set["kind"] if indicator_set else None
        source = None
        if row["_kind"] == "delphi":
            source = SourceSubdivision.objects.filter(name=row.get("source")).first()
        row["source"] = source.id if source else None
        if row.get("indicator") and is_unrecognised_bool(row.get("show_in_epiportal")):
            self.warnings.append(
                f"Unrecognised show_in_epiportal value "
                f"{row.get('show_in_epiportal')!r} (hidden) for indicator: "
                f"{row['indicator']} ({set_name})"
            )
        for column in BOOLEAN_COLUMNS:
            row[column] = parse_bool(row.get(column))
        for column in ("temporal_scope_start", "temporal_scope_end"):
            row[column] = normalize_sheet_date(row.get(column))
        row["pathogen"] = pathogen_ids(row.get("pathogen"), USED_IN)
        row["geographic_levels"] = geography_ids(row.get("geographic_levels"), USED_IN)
        row["surveillance_categories"] = severity_pyramid_rung_ids(
            row.get("surveillance_categories"), USED_IN, empty_as_na=True
        )
        row["geographic_scope"] = geographic_scope_id(
            row.get("geographic_scope"), USED_IN
        )
        row["indicator_type"] = named_object_id(
            IndicatorType, row.get("indicator_type")
        )
        row["format"] = named_object_id(FormatType, row.get("format"))
        row["category"] = named_object_id(Category, row.get("category"))

    def is_excluded(self, row) -> bool:
        if not row.get("indicator") or not row.get("show_in_epiportal"):
            return True
        if row.get("indicator_set") is None:
            self.warn_once(
                f"Unknown or hidden indicator set {row.get('_set_name')!r} "
                f"for indicator: {row['indicator']}"
            )
            return True
        if row.get("_kind") == "delphi" and row.get("source") is None:
            self.warn_once(
                f"Unknown source {row.get('_source_name')!r} for indicator: "
                f"{row['indicator']} ({row.get('_set_name')})"
            )
            return True
        return False

    def warn_once(self, warning: str) -> None:
        # is_excluded runs more than once per row.
        if warning not in self.warnings:
            self.warnings.append(warning)

    def get_instance(self, instance_loader, row):
        name = row.get("indicator")
        indicators = Indicator.objects.filter(name=name)
        # A Delphi indicator is keyed by its source but may also have moved
        # to a new source; others are keyed by their set.
        if row.get("source"):
            indicator = indicators.filter(source_id=row["source"]).first()
            if indicator:
                return indicator
        if row.get("indicator_set"):
            return indicators.filter(indicator_set_id=row["indicator_set"]).first()
        return None

    def import_row(self, row, instance_loader, **kwargs):
        # A failing row is skipped with a warning instead of failing the import.
        row_result = super().import_row(row, instance_loader, **kwargs)
        if row_result.import_type in (
            RowResult.IMPORT_TYPE_ERROR,
            RowResult.IMPORT_TYPE_INVALID,
        ):
            errors = [str(error.error) for error in row_result.errors]
            if row_result.validation_error is not None:
                errors.append(str(row_result.validation_error))
            warning = (
                f"Skipped indicator {row.get('indicator')!r} "
                f"(row {kwargs.get('row_number')}): {'; '.join(errors)}"
            )
            self.warnings.append(warning)
            # Show the row and its errors in the admin's import preview.
            row_result.diff = [
                row.get(field.column_name, "") for field in self.get_import_fields()
            ] + [warning]
            row_result.errors = []
            row_result.validation_error = None
            row_result.import_type = RowResult.IMPORT_TYPE_SKIP
        return row_result
