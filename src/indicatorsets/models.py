from django.db import models
from base.models import SOURCE_TYPES


DUA_REQUIRED_CHOICES = (
    ("Yes", "Yes"),
    ("No", "No"),
    ("Unknown", "Unknown"),
    ("Sensor-dependent", "Sensor-dependent"),
)


class IndicatorSet(models.Model):

    name: models.CharField = models.CharField(
        verbose_name="Name", max_length=255, unique=True
    )
    short_name: models.CharField = models.CharField(
        verbose_name="Short Name", max_length=255, blank=True
    )
    description: models.TextField = models.TextField(
        verbose_name="Description", blank=True
    )
    maintainer_name: models.CharField = models.CharField(
        verbose_name="Maintainer Name", max_length=255, blank=True
    )
    maintainer_email: models.CharField = models.CharField(
        verbose_name="Maintainer Email", max_length=255, blank=True
    )
    organization: models.CharField = models.CharField(
        verbose_name="Organization", max_length=255, blank=True
    )
    original_data_provider: models.CharField = models.CharField(
        verbose_name="Original Data Provider",
        max_length=255,
        blank=True,
        help_text="Original data provider of the Indicator Set",
    )
    epidata_endpoint: models.CharField = models.CharField(
        verbose_name="Epidata Endpoint",
        max_length=255,
        blank=True,
        help_text="Epidata endpoint for the Indicator Set",
    )
    language: models.CharField = models.CharField(
        verbose_name="Language",
        max_length=255,
        blank=True,
        help_text="Language of the Indicator Set",
    )
    version_number: models.CharField = models.CharField(
        verbose_name="Version Number",
        max_length=255,
        blank=True,
        help_text="Version number of the Indicator Set",
    )
    origin_datasource: models.TextField = models.TextField(
        verbose_name="Origin Data Source",
        blank=True,
        help_text="Origin data source of the Indicator Set",
    )
    pathogens: models.ManyToManyField = models.ManyToManyField(
        "base.Pathogen",
        related_name="indicator_sets",
        verbose_name="Pathogens",
        blank=True,
        help_text="Pathogens included in the Indicator Set",
    )
    data_type: models.CharField = models.CharField(
        verbose_name="Data Type",
        max_length=255,
        blank=True,
        help_text="Type of data in the Indicator Set",
    )
    geographic_scope: models.ForeignKey = models.ForeignKey(
        "base.GeographicScope",
        related_name="indicator_sets",
        verbose_name="Geographic Scope",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        help_text="Geographic scope of the Indicator Set",
    )
    geographic_levels: models.ManyToManyField = models.ManyToManyField(
        "base.Geography",
        related_name="indicator_sets",
        verbose_name="Available Geographies",
        blank=True,
        help_text="Geographies available in the Indicator Set",
    )
    preprocessing_description: models.TextField = models.TextField(
        verbose_name="Preprocessing Description",
        blank=True,
        help_text="Description of preprocessing steps applied to the data",
    )
    temporal_scope_start: models.CharField = models.CharField(
        verbose_name="Temporal Scope Start",
        max_length=255,
        blank=True,
        help_text="Start date of the temporal scope of the Indicator Set",
    )
    temporal_scope_end: models.CharField = models.CharField(
        verbose_name="Temporal Scope End",
        max_length=255,
        blank=True,
        help_text="End date of the temporal scope of the Indicator Set",
    )
    temporal_granularity: models.CharField = models.CharField(
        verbose_name="Temporal Granularity",
        max_length=255,
        blank=True,
        help_text="Granularity of the temporal data in the Indicator Set",
    )
    reporting_cadence: models.CharField = models.CharField(
        verbose_name="Reporting Cadence",
        max_length=255,
        blank=True,
        help_text="Frequency of data reporting in the Indicator Set",
    )
    reporting_lag: models.CharField = models.CharField(
        verbose_name="Reporting Lag",
        max_length=255,
        blank=True,
        help_text="Lag time between data collection and reporting",
    )
    revision_cadence: models.CharField = models.CharField(
        verbose_name="Revision Cadence",
        max_length=255,
        blank=True,
        help_text="Frequency of data revision in the Indicator Set",
    )
    demographic_scope: models.CharField = models.CharField(
        verbose_name="Demographic Scope",
        max_length=255,
        blank=True,
        help_text="Demographic scope of the Indicator Set",
    )
    demographic_granularity: models.CharField = models.CharField(
        verbose_name="Demographic Granularity",
        max_length=255,
        blank=True,
        help_text="Granularity of the demographic data in the Indicator Set",
    )
    severity_pyramid_rungs: models.ManyToManyField = models.ManyToManyField(
        "base.SeverityPyramidRung",
        related_name="indicator_sets",
        verbose_name="Severity Pyramid Rungs",
        blank=True,
        help_text="Severity pyramid rungs of the Indicator Set",
    )
    censoring: models.CharField = models.CharField(
        verbose_name="Censoring",
        max_length=255,
        blank=True,
        help_text="Censoring information of the Indicator Set",
    )
    missingness: models.TextField = models.TextField(
        verbose_name="Missingness",
        blank=True,
        help_text="Missingness information of the Indicator Set",
    )
    dua_required: models.CharField = models.CharField(
        verbose_name="Data Use Agreement Required",
        max_length=255,
        blank=True,
        choices=DUA_REQUIRED_CHOICES,
        help_text="Indicates if a data use agreement is required for the Indicator Set",
    )
    license: models.CharField = models.CharField(
        verbose_name="License",
        max_length=255,
        blank=True,
        help_text="License information of the Indicator Set",
    )
    dataset_location: models.CharField = models.CharField(
        verbose_name="Dataset Location",
        max_length=255,
        blank=True,
        help_text="Location of the dataset for the Indicator Set",
    )
    documentation_link: models.CharField = models.CharField(
        verbose_name="Documentation Link",
        max_length=255,
        blank=True,
        help_text="Link to the documentation for the Indicator Set",
    )

    source_type: models.CharField = models.CharField(
        verbose_name="Source Type",
        max_length=255,
        choices=SOURCE_TYPES,
        default="covidcast",
        help_text="Type of source for the indicator set",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Indicator Set"
        verbose_name_plural = "Indicator Sets"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="indicator_set_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "original_data_provider"],
                name="unique_indicator_set_name",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def get_geographic_levels(self):
        return [geo.display_name for geo in self.geographic_levels.all().order_by("display_order_number")]


class NonDelphiIndicatorSet(IndicatorSet):

    class Meta:
        proxy = True
        verbose_name = "Non-Delphi Indicator Set"
        verbose_name_plural = "Non-Delphi Indicators Sets"


class FilterDescription(models.Model):

    name = models.CharField(verbose_name="Name", max_length=255, unique=True)
    description: models.TextField = models.TextField(
        verbose_name="Description", blank=True
    )

    class Meta:
        verbose_name = "Filter Description"
        verbose_name_plural = "Filter Descriptions"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="filter_description_name_idx"),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def get_all_descriptions_as_dict(cls):
        descriptions = cls.objects.values("name", "description")
        return {desc["name"]: desc["description"] for desc in descriptions}


class ColumnDescription(models.Model):

    name: models.CharField = models.CharField(
        verbose_name="Name", max_length=255, unique=True
    )
    description: models.TextField = models.TextField(
        verbose_name="Description", blank=True
    )

    class Meta:
        verbose_name = "Column Description"
        verbose_name_plural = "Column Descriptions"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="column_description_name_idx"),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def get_all_descriptions_as_dict(cls):
        descriptions = cls.objects.values("name", "description")
        return {desc["name"]: desc["description"] for desc in descriptions}
