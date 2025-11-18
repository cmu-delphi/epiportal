import logging

from django.db.models import Max
from import_export import resources
from import_export.fields import Field
from import_export.results import RowResult
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget

from base.models import GeographicScope, Geography, Pathogen, SeverityPyramidRung
from base.resources import GEOGRAPHIC_GRANULARITY_MAPPING
from datasources.models import SourceSubdivision
from indicators.models import (
    Category,
    FormatType,
    Indicator,
    IndicatorGeography,
    IndicatorType,
    NonDelphiIndicator,
    OtherEndpointIndicator,
    USStateIndicator,
)
from indicatorsets.models import IndicatorSet, NonDelphiIndicatorSet

logger = logging.getLogger(__name__)


def fix_boolean_fields(row) -> None:
    fields = [
        "Active",
        "Is Smoothed",
        "Is Weighted",
        "Is Cumulative",
        "Has StdErr",
        "Has Sample Size",
        "Include in indicator app",
        "Include in express",
    ]

    for field in fields:
        if row.get(field, "") == "TRUE":
            row[field] = True
        elif row.get(field, "") == "FALSE":
            row[field] = False
        elif row.get(field, None) == "":
            row[field] = False
    return row


def process_pathogens(row) -> None:
    pathogen_ids = []
    if row["Pathogen/\nDisease Area"]:
        pathogens = row["Pathogen/\nDisease Area"].split(",")
        for pathogen in pathogens:
            pathogen_name = pathogen.strip()
            pathogen_obj, _ = Pathogen.objects.get_or_create(
                name=pathogen_name,
                used_in="indicators",
                defaults={
                    "display_name": pathogen_name,
                    "used_in": "indicators",
                },
            )
            pathogen_ids.append(pathogen_obj.id)
    row["Pathogen/\nDisease Area"] = ",".join(str(el) for el in pathogen_ids)


def process_indicator_set(row) -> None:
    indicator_set_id = None
    if row["Indicator Set"]:
        indicator_set_name = row["Indicator Set"].strip()
        try:
            indicator_set_obj = IndicatorSet.objects.get(name=indicator_set_name)
            indicator_set_id = indicator_set_obj.id
        except IndicatorSet.DoesNotExist:
            logger.warning(f"Indicator Set '{indicator_set_name}' not found.")
    row["Indicator Set"] = indicator_set_id


def process_indicator_type(row) -> None:
    if row["Indicator Type"]:
        indicator_type = row["Indicator Type"]
        indicator_type_obj, _ = IndicatorType.objects.get_or_create(name=indicator_type)
        row["Indicator Type"] = indicator_type_obj.id


def process_format_type(row) -> None:
    """
    Processes format type.
    """
    if row["Format"]:
        format_type = row["Format"].strip()
        format_type_obj, _ = FormatType.objects.get_or_create(name=format_type)
        row["Format"] = format_type_obj.id
    else:
        row["Format"] = None


def process_severity_pyramid_rungs(row) -> None:
    severity_pyramid_rung_ids = []
    if row["Surveillance Categories"]:
        severity_pyramid_rungs = row["Surveillance Categories"].split(",")
        for spr in severity_pyramid_rungs:
            spr_name = spr.strip()
            severity_pyramid_rung_obj, _ = SeverityPyramidRung.objects.get_or_create(
                name=spr_name,
                used_in="indicators",
                defaults={"display_name": spr_name.capitalize()},
            )
            severity_pyramid_rung_ids.append(severity_pyramid_rung_obj.id)
    else:
        severity_pyramid_rung_obj, _ = SeverityPyramidRung.objects.get_or_create(
            name="N/A",
            used_in="indicators",
            defaults={"used_in": "indicators", "display_name": "N/A"},
        )
        severity_pyramid_rung_ids.append(severity_pyramid_rung_obj.id)
    row["Surveillance Categories"] = ",".join(
        str(el) for el in severity_pyramid_rung_ids
    )


def process_category(row) -> None:
    """
    Processes category.
    """
    if row["Category"]:
        category = row["Category"].strip()
        category_obj, _ = Category.objects.get_or_create(name=category)
        row["Category"] = category_obj.id


def process_geographic_scope(row) -> None:
    if row["Geographic Coverage"]:
        geographic_scope_name = row["Geographic Coverage"].strip()
        geographic_scope_obj, _ = GeographicScope.objects.get_or_create(
            name=geographic_scope_name,
            used_in="indicators",
            defaults={
                "used_in": "indicators",
            },
        )
        row["Geographic Coverage"] = geographic_scope_obj.id


def process_source(row) -> None:
    """
    Processes source.
    """
    if row["Source Subdivision"]:
        source = row["Source Subdivision"]
        source_obj, _ = SourceSubdivision.objects.get_or_create(name=source)
        row["Source Subdivision"] = source_obj.id


def process_available_geographies(row) -> None:
    if row["Geographic Levels"]:
        geographic_levels = []
        available_geographies = row["Geographic Levels"].split(",")
        for geography in available_geographies:
            geography_name = geography.strip()
            default_params = {"used_in": "indicators"}
            try:
                default_params.update(GEOGRAPHIC_GRANULARITY_MAPPING[geography_name])
            except KeyError:
                max_display_order_number = Geography.objects.filter(
                    used_in="indicators"
                ).aggregate(Max("display_order_number"))["display_order_number__max"]
                default_params["display_order_number"] = max_display_order_number + 1
            geography_obj, _ = Geography.objects.get_or_create(
                name=geography_name,
                used_in="indicators",
                defaults=default_params,
            )
            geographic_levels.append(geography_obj.id)
        row["Geographic Levels"] = ",".join(str(el) for el in geographic_levels)


def process_indicator_geography(row):
    if row["Geographic Levels"]:
        available_geographies = row["Geographic Levels"].split(",")
        delphi_aggregated_geographies: str = row["Delphi-Aggregated Geography"].split(
            ","
        )
        for geography_id in available_geographies:
            geography_obj = Geography.objects.get(pk=int(geography_id))
            try:
                indicator_obj = Indicator.objects.get(
                    name=row["Indicator"], source=row["Source Subdivision"]
                )
            except KeyError:  # compitability with old indicators(signals) sheet
                indicator_obj = Indicator.objects.get(
                    name=row["Signal"], source=row["Source Subdivision"]
                )
            except Indicator.DoesNotExist:
                return
            indicator_geography_obj, _ = IndicatorGeography.objects.get_or_create(
                geography=geography_obj, indicator=indicator_obj
            )
            if geography_obj.name in delphi_aggregated_geographies:
                indicator_geography_obj.aggregated_by_delphi = True
                indicator_geography_obj.save()


def process_base(row) -> None:
    if row["Signal BaseName"]:
        source = SourceSubdivision.objects.get(name=row["Source Subdivision"])

        try:
            base_indicator_obj = Indicator.objects.get(
                name=row["Signal BaseName"], source=source
            )
        except Indicator.DoesNotExist:
            return

        row["base"] = base_indicator_obj.id


class ModelResource(resources.ModelResource):
    def get_field_names(self):
        names = []
        for field in list(self.fields.values()):
            names.append(self.get_field_name(field))
        return names

    def import_row(self, row, instance_loader, **kwargs):
        # overriding import_row to ignore errors and skip rows that fail to import
        # without failing the entire import
        import_result = super(ModelResource, self).import_row(
            row, instance_loader, **kwargs
        )

        if import_result.import_type in [
            RowResult.IMPORT_TYPE_ERROR,
            RowResult.IMPORT_TYPE_INVALID,
        ]:
            import_result.diff = [row.get(name, "") for name in self.get_field_names()]

            # Add a column with the error message
            import_result.diff.append(
                "Errors: {}\n{}".format(
                    [err.error for err in import_result.errors], row
                )
            )
            # clear errors and mark the record to skip
            import_result.errors = []
            import_result.import_type = RowResult.IMPORT_TYPE_SKIP

        return import_result


def strip_all_string_values(row) -> None:
    for key, value in row.items():
        # Check if the value is a string and not None
        if isinstance(value, str):
            row[key] = value.strip()


class PermissiveForeignKeyWidget(ForeignKeyWidget):

    def clean(self, value, row=None, **kwargs):
        try:
            return super().clean(value)
        except self.model.DoesNotExist:
            logger.warning(f"instance matching '{value}' does not exist")


class IndicatorBaseResource(ModelResource):
    name = Field(attribute="name", column_name="Signal")
    display_name = Field(attribute="display_name", column_name="Name")
    base = Field(
        attribute="base",
        column_name="base",
        widget=PermissiveForeignKeyWidget(Indicator),
    )
    source = Field(
        attribute="source",
        column_name="Source Subdivision",
        widget=PermissiveForeignKeyWidget(SourceSubdivision, field="name"),
    )

    class Meta:
        model = Indicator
        fields: list[str] = ["base", "name", "source", "display_name"]
        import_id_fields: list[str] = ["name", "source"]

    def before_import_row(self, row, **kwargs) -> None:
        """Post-processes each row after importing."""
        strip_all_string_values(row)
        process_base(row)


class IndicatorResource(ModelResource):
    name = Field(attribute="name", column_name="Signal")
    display_name = Field(attribute="display_name", column_name="Name")
    short_description = Field(
        attribute="short_description", column_name="Short Description"
    )
    description = Field(attribute="description", column_name="Description")
    member_name = Field(attribute="member_name", column_name="Member API Name")
    member_short_name = Field(
        attribute="member_short_name", column_name="Member Short Name"
    )
    member_description = Field(
        attribute="member_description", column_name="Member Description"
    )
    pathogens = Field(
        attribute="pathogens",
        column_name="Pathogen/\nDisease Area",
        widget=ManyToManyWidget(Pathogen),
    )
    indicator_type = Field(
        attribute="indicator_type",
        column_name="Indicator Type",
        widget=PermissiveForeignKeyWidget(IndicatorType),
    )
    active = Field(attribute="active", column_name="Active")
    format_type = Field(
        attribute="format_type",
        column_name="Format",
        widget=PermissiveForeignKeyWidget(FormatType),
    )
    time_type = Field(attribute="time_type", column_name="Time Type")
    time_label = Field(attribute="time_label", column_name="Time Label")
    reporting_cadence = Field(
        attribute="reporting_cadence", column_name="Reporting Cadence"
    )
    typical_reporting_lag = Field(
        attribute="typical_reporting_lag", column_name="Typical Reporting Lag"
    )
    typical_revision_cadence = Field(
        attribute="typical_revision_cadence", column_name="Typical Revision Cadence"
    )
    demographic_scope = Field(attribute="demographic_scope", column_name="Population")
    severity_pyramid_rungs = Field(
        attribute="severity_pyramid_rungs",
        column_name="Surveillance Categories",
        widget=ManyToManyWidget(SeverityPyramidRung),
    )
    category = Field(
        attribute="category",
        column_name="Category",
        widget=PermissiveForeignKeyWidget(Category),
    )
    geographic_scope = Field(
        attribute="geographic_scope",
        column_name="Geographic Coverage",
        widget=PermissiveForeignKeyWidget(GeographicScope),
    )
    available_geographies = Field(
        attribute="available_geographies",
        column_name="Geographic Levels",
        widget=ManyToManyWidget(Geography),
    )
    temporal_scope_start = Field(
        attribute="temporal_scope_start", column_name="Temporal Scope Start"
    )
    temporal_scope_start_note = Field(
        attribute="temporal_scope_start_note", column_name="Temporal Scope Start Note"
    )
    temporal_scope_end = Field(
        attribute="temporal_scope_end", column_name="Temporal Scope End"
    )
    temporal_scope_end_note = Field(
        attribute="temporal_scope_end_note", column_name="Temporal Scope End Note"
    )
    is_smoothed = Field(attribute="is_smoothed", column_name="Is Smoothed")
    is_weighted = Field(attribute="is_weighted", column_name="Is Weighted")
    is_cumulative = Field(attribute="is_cumulative", column_name="Is Cumulative")
    has_stderr = Field(attribute="has_stderr", column_name="Has StdErr")
    has_sample_size = Field(attribute="has_sample_size", column_name="Has Sample Size")
    high_values_are = Field(attribute="high_values_are", column_name="High Values Are")
    source = Field(
        attribute="source",
        column_name="Source Subdivision",
        widget=PermissiveForeignKeyWidget(SourceSubdivision),
    )
    data_censoring = Field(attribute="data_censoring", column_name="Data Censoring")
    missingness = Field(attribute="missingness", column_name="Missingness")
    organization_access_list = Field(
        attribute="organization_access_list",
        column_name="Who may access this indicator?",
    )
    organization_sharing_list = Field(
        attribute="organization_sharing_list",
        column_name="Who may be told about this indicator?",
    )
    license = Field(attribute="license", column_name="Data Use Terms")
    restrictions = Field(attribute="restrictions", column_name="Use Restrictions")
    indicator_set = Field(
        attribute="indicator_set",
        column_name="Indicator Set",
        widget=PermissiveForeignKeyWidget(IndicatorSet),
    )
    use_in_express_interface = Field(
        attribute="use_in_express_interface", column_name="Include in express app"
    )

    class Meta:
        model = Indicator
        fields: list[str] = [
            "name",
            "display_name",
            "short_description",
            "description",
            "member_name",
            "member_short_name",
            "member_description",
            "pathogens",
            "indicator_type",
            "active",
            "format_type",
            "time_type",
            "time_label",
            "reporting_cadence",
            "typical_reporting_lag",
            "typical_revision_cadence",
            "demographic_scope",
            "severity_pyramid_rungs",
            "category",
            "geographic_scope",
            "available_geographies",
            "temporal_scope_start",
            "temporal_scope_start_note",
            "temporal_scope_end",
            "temporal_scope_end_note",
            "is_smoothed",
            "is_weighted",
            "is_cumulative",
            "has_stderr",
            "has_sample_size",
            "high_values_are",
            "source",
            "data_censoring",
            "missingness",
            "organization_access_list",
            "organization_sharing_list",
            "license",
            "restrictions",
            "indicator_set",
            "use_in_express_interface",
        ]
        import_id_fields: list[str] = ["name", "indicator_set", "source"]
        skip_unchanged = True

    def get_instance(self, instance_loader, row):
        name = row.get("Signal")
        source = row.get("Source Subdivision")
        indicator_set = row.get("Indicator Set")

        # Try to match by (name, source)
        if name and source:
            try:
                return self._meta.model.objects.get(name=name, source__id=source)
            except self._meta.model.DoesNotExist:
                pass

        # Try to match by (name, indicator_set)
        if name and indicator_set:
            try:
                return self._meta.model.objects.get(
                    name=name, indicator_set__id=indicator_set
                )
            except self._meta.model.DoesNotExist:
                pass

        return None

    def before_import_row(self, row, **kwargs) -> None:
        """Post-processes each row after importing."""
        strip_all_string_values(row)
        fix_boolean_fields(row)
        process_pathogens(row)
        process_indicator_type(row)
        process_format_type(row)
        process_category(row)
        process_geographic_scope(row)
        process_source(row)
        process_severity_pyramid_rungs(row)
        process_available_geographies(row)
        process_indicator_set(row)

    def after_import_row(self, row, row_result, **kwargs):
        process_indicator_geography(row)

    def after_save_instance(self, instance, row, **kwargs):
        instance.source_type = "covidcast"
        instance.save()

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if not row["Include in indicator app"]:
            return True
        if row["Indicator Set"] is None:
            return True


class OtherEndpointIndicatorResource(ModelResource):
    name = Field(attribute="name", column_name="Indicator")
    display_name = Field(attribute="display_name", column_name="Name")
    short_description = Field(
        attribute="short_description", column_name="Short Description"
    )
    description = Field(attribute="description", column_name="Description")
    member_name = Field(attribute="member_name", column_name="Member Name")
    member_short_name = Field(
        attribute="member_short_name", column_name="Member Short Name"
    )
    member_description = Field(
        attribute="member_description", column_name="Member Description"
    )
    pathogens = Field(
        attribute="pathogens",
        column_name="Pathogen/\nDisease Area",
        widget=ManyToManyWidget(Pathogen),
    )
    indicator_type = Field(
        attribute="indicator_type",
        column_name="Indicator Type",
        widget=PermissiveForeignKeyWidget(IndicatorType),
    )
    active = Field(attribute="active", column_name="Active")
    format_type = Field(
        attribute="format_type",
        column_name="Format",
        widget=PermissiveForeignKeyWidget(FormatType),
    )
    time_type = Field(attribute="time_type", column_name="Time Type")
    time_label = Field(attribute="time_label", column_name="Time Label")
    reporting_cadence = Field(
        attribute="reporting_cadence", column_name="Reporting Cadence"
    )
    typical_reporting_lag = Field(
        attribute="typical_reporting_lag", column_name="Typical Reporting Lag"
    )
    typical_revision_cadence = Field(
        attribute="typical_revision_cadence", column_name="Typical Revision Cadence"
    )
    demographic_scope = Field(attribute="demographic_scope", column_name="Population")
    severity_pyramid_rungs = Field(
        attribute="severity_pyramid_rungs",
        column_name="Surveillance Categories",
        widget=ManyToManyWidget(SeverityPyramidRung),
    )
    category = Field(
        attribute="category",
        column_name="Category",
        widget=PermissiveForeignKeyWidget(Category),
    )
    geographic_scope = Field(
        attribute="geographic_scope",
        column_name="Geographic Coverage",
        widget=PermissiveForeignKeyWidget(GeographicScope),
    )
    available_geographies = Field(
        attribute="available_geographies",
        column_name="Geographic Levels",
        widget=ManyToManyWidget(Geography),
    )
    temporal_scope_start = Field(
        attribute="temporal_scope_start", column_name="Temporal Scope Start"
    )
    temporal_scope_start_note = Field(
        attribute="temporal_scope_start_note", column_name="Temporal Scope Start Note"
    )
    temporal_scope_end = Field(
        attribute="temporal_scope_end", column_name="Temporal Scope End"
    )
    temporal_scope_end_note = Field(
        attribute="temporal_scope_end_note", column_name="Temporal Scope End Note"
    )
    is_smoothed = Field(attribute="is_smoothed", column_name="Is Smoothed")
    is_weighted = Field(attribute="is_weighted", column_name="Is Weighted")
    is_cumulative = Field(attribute="is_cumulative", column_name="Is Cumulative")
    has_stderr = Field(attribute="has_stderr", column_name="Has StdErr")
    has_sample_size = Field(attribute="has_sample_size", column_name="Has Sample Size")
    high_values_are = Field(attribute="high_values_are", column_name="High Values Are")
    source = Field(
        attribute="source",
        column_name="Source Subdivision",
        widget=PermissiveForeignKeyWidget(SourceSubdivision),
    )
    data_censoring = Field(attribute="data_censoring", column_name="Data Censoring")
    missingness = Field(attribute="missingness", column_name="Missingness")
    organization_access_list = Field(
        attribute="organization_access_list",
        column_name="Who may access this indicator?",
    )
    organization_sharing_list = Field(
        attribute="organization_sharing_list",
        column_name="Who may be told about this indicator?",
    )
    license = Field(attribute="license", column_name="Data Use Terms")
    restrictions = Field(attribute="restrictions", column_name="Use Restrictions")
    indicator_set = Field(
        attribute="indicator_set",
        column_name="Indicator Set",
        widget=PermissiveForeignKeyWidget(IndicatorSet),
    )
    use_in_express_interface = Field(
        attribute="use_in_express_interface", column_name="Include in express app"
    )

    class Meta:
        model = OtherEndpointIndicator
        fields: list[str] = [
            "name",
            "display_name",
            "short_description",
            "description",
            "member_name",
            "member_short_name",
            "member_description",
            "pathogens",
            "indicator_type",
            "active",
            "format_type",
            "time_type",
            "time_label",
            "reporting_cadence",
            "typical_reporting_lag",
            "typical_revision_cadence",
            "demographic_scope",
            "severity_pyramid_rungs",
            "category",
            "geographic_scope",
            "available_geographies",
            "temporal_scope_start",
            "temporal_scope_start_note",
            "temporal_scope_end",
            "temporal_scope_end_note",
            "is_smoothed",
            "is_weighted",
            "is_cumulative",
            "has_stderr",
            "has_sample_size",
            "high_values_are",
            "source",
            "data_censoring",
            "missingness",
            "organization_access_list",
            "organization_sharing_list",
            "license",
            "restrictions",
            "indicator_set",
            "use_in_express_interface",
        ]
        import_id_fields: list[str] = ["name", "source"]
        skip_unchanged = True

    def before_import_row(self, row, **kwargs) -> None:
        """Post-processes each row after importing."""
        strip_all_string_values(row)
        fix_boolean_fields(row)
        process_source(row)
        process_pathogens(row)
        process_indicator_type(row)
        process_format_type(row)
        process_category(row)
        process_geographic_scope(row)
        process_severity_pyramid_rungs(row)
        process_available_geographies(row)
        process_indicator_set(row)

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if not row["Include in indicator app"]:
            return True
        if row["Indicator Set"] is None:
            return True

    def after_import_row(self, row, row_result, **kwargs):
        process_indicator_geography(row)

    def after_save_instance(self, instance, row, **kwargs):
        instance.source_type = "other_endpoint"
        instance.save()


class NonDelphiIndicatorResource(resources.ModelResource):

    name = Field(attribute="name", column_name="Indicator Name")
    display_name = Field(attribute="display_name", column_name="Indicator Name")
    member_name = Field(attribute="member_name", column_name="Indicator API Name")
    description = Field(attribute="description", column_name="Indicator Description")
    indicator_set = Field(
        attribute="indicator_set",
        column_name="Indicator Set",
        widget=PermissiveForeignKeyWidget(NonDelphiIndicatorSet),
    )
    use_in_express_interface = Field(
        attribute="use_in_express_interface", column_name="Include in express app"
    )

    class Meta:
        model = NonDelphiIndicator
        fields: list[str] = [
            "name",
            "display_name",
            "member_name",
            "description",
            "indicator_set",
            "use_in_express_interface",
        ]
        import_id_fields: list[str] = ["name"]
        skip_unchanged = True

    def before_import_row(self, row, **kwargs) -> None:
        """Post-processes each row after importing."""
        strip_all_string_values(row)
        fix_boolean_fields(row)
        process_indicator_set(row)

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if not row["Include in indicator app"]:
            return True

    def after_save_instance(self, instance, row, **kwargs):
        instance.source_type = "non_delphi"
        instance.save()


class USStateIndicatorResource(ModelResource):
    name = Field(attribute="name", column_name="Indicator Name")
    indicator_set = Field(
        attribute="indicator_set",
        column_name="Indicator Set",
        widget=PermissiveForeignKeyWidget(IndicatorSet),
    )

    class Meta:
        model = USStateIndicator
        fields: list[str] = [
            "name",
            "indicator_set",
        ]
        import_id_fields: list[str] = ["name", "indicator_set"]
        skip_unchanged = True

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if not row["Include in indicator app"]:
            return True

    def before_import_row(self, row, **kwargs) -> None:
        """Post-processes each row after importing."""
        strip_all_string_values(row)
        fix_boolean_fields(row)
        process_indicator_set(row)

    def after_save_instance(self, instance, row, **kwargs):
        instance.source_type = "us_state"
        instance.save()
