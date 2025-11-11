from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from django.db import models

from base.models import SOURCE_TYPES


# Create your models here.
class IndicatorType(models.Model):

    name: models.CharField = models.CharField(
        verbose_name="Name", max_length=255, unique=True
    )
    display_name: models.CharField = models.CharField(
        verbose_name="Display Name", max_length=255, blank=True
    )

    class Meta:
        verbose_name = "Indicator Type"
        verbose_name_plural = "Indicator Types"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="indicator_type_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="unique_indicator_type_name")
        ]

    def __str__(self):
        return self.display_name if self.display_name else self.name


class FormatType(models.Model):

    name: models.CharField = models.CharField(
        verbose_name="Name", max_length=255, unique=True
    )
    display_name: models.CharField = models.CharField(
        verbose_name="Display Name", max_length=255, blank=True
    )

    class Meta:
        verbose_name = "Format Type"
        verbose_name_plural = "Format Types"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="format_type_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="unique_format_type_name")
        ]

    def __str__(self):
        return self.display_name if self.display_name else self.name


class Category(models.Model):
    name: models.CharField = models.CharField(
        verbose_name="Name", max_length=255, unique=True
    )
    display_name: models.CharField = models.CharField(
        verbose_name="Display Name", max_length=255, blank=True
    )

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="category_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="unique_category_name")
        ]

    def __str__(self):
        return self.display_name if self.display_name else self.name


class IndicatorGeography(models.Model):

    geography: models.ForeignKey = models.ForeignKey(
        "base.Geography",
        verbose_name="Geography",
        on_delete=models.CASCADE,
        related_name="indicator_geographies",
    )

    indicator: models.ForeignKey = models.ForeignKey(
        "indicators.Indicator",
        verbose_name="Indicator",
        on_delete=models.CASCADE,
        related_name="indicator_geographies",
    )
    aggregated_by_delphi: models.BooleanField = models.BooleanField(
        verbose_name="Aggregated by Delphi",
        default=False,
        help_text="Indicates if the geography is aggregated by Delphi",
    )

    class Meta:
        verbose_name = "Indicator Geography"
        verbose_name_plural = "Indicator Geographies"
        ordering = ["geography"]
        indexes = [
            models.Index(fields=["geography"], name="indicator_geography_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["geography", "indicator"],
                name="unique_indicator_geography",
            )
        ]

    @property
    def display_name(self):
        return (
            f"{self.geography.display_name} (by Delphi)"
            if self.aggregated_by_delphi
            else self.geography.display_name
        )


class Indicator(models.Model):

    name: models.CharField = models.CharField(verbose_name="Name", max_length=255)
    display_name: models.CharField = models.CharField(
        verbose_name="Display Name", max_length=255, blank=True
    )
    description: models.TextField = models.TextField(
        verbose_name="Description", blank=True
    )
    short_description: models.TextField = models.TextField(
        verbose_name="Short Description", blank=True
    )
    member_name: models.CharField = models.CharField(
        verbose_name="Member Name", max_length=255, blank=True
    )
    member_short_name: models.CharField = models.CharField(
        verbose_name="Member Short Name", max_length=255, blank=True
    )
    member_description: models.TextField = models.TextField(
        verbose_name="Member Description", blank=True
    )
    pathogens: models.ManyToManyField = models.ManyToManyField(
        "base.Pathogen",
        verbose_name="Pathogens",
        related_name="indicators",
        blank=True,
    )
    indicator_type: models.ForeignKey = models.ForeignKey(
        "indicators.IndicatorType",
        verbose_name="Indicator Type",
        on_delete=models.CASCADE,
        related_name="indicators",
        null=True,
        blank=True,
    )
    active: models.BooleanField = models.BooleanField(
        verbose_name="Active",
        default=True,
        help_text="Indicates if the indicator is active",
    )
    format_type: models.ForeignKey = models.ForeignKey(
        "indicators.FormatType",
        verbose_name="Format Type",
        on_delete=models.PROTECT,
        related_name="indicators",
        null=True,
        blank=True,
    )
    time_type: models.CharField = models.CharField(
        verbose_name="Time Type",
        max_length=255,
        blank=True,
        help_text="Time type of the indicator",
    )
    time_label: models.CharField = models.CharField(
        verbose_name="Time Label",
        max_length=255,
        blank=True,
        help_text="Label for the time type of the indicator",
    )
    reporting_cadence: models.CharField = models.CharField(
        verbose_name="Reporting Cadence",
        max_length=255,
        blank=True,
        help_text="Reporting cadence of the indicator",
    )
    typical_reporting_lag: models.CharField = models.CharField(
        verbose_name="Typical Reporting Lag",
        max_length=255,
        blank=True,
        help_text="Typical reporting lag of the indicator",
    )
    typical_revision_cadence: models.TextField = models.TextField(
        verbose_name="Typical Revision Cadence",
        blank=True,
        help_text="Typical revision cadence of the indicator",
    )
    demographic_scope: models.CharField = models.CharField(
        verbose_name="Demographic Scope",
        max_length=255,
        blank=True,
        help_text="Demographic scope of the indicator",
    )
    severity_pyramid_rungs: models.ManyToManyField = models.ManyToManyField(
        "base.SeverityPyramidRung",
        verbose_name="Severity Pyramid Rungs",
        related_name="indicators",
        blank=True,
    )
    category: models.ForeignKey = models.ForeignKey(
        "indicators.Category",
        verbose_name="Category",
        on_delete=models.CASCADE,
        related_name="indicators",
        null=True,
        blank=True,
    )
    dua_link: models.CharField = models.CharField(
        verbose_name="DUA Link",
        max_length=255,
        blank=True,
        help_text="Link to the Data Use Agreement (DUA)",
    )
    documentation_link: models.TextField = models.TextField(
        verbose_name="Documentation Link",
        blank=True,
        help_text="Link to the documentation of the indicator",
    )
    geographic_scope: models.ForeignKey = models.ForeignKey(
        "base.GeographicScope",
        verbose_name="Geographic Scope",
        on_delete=models.PROTECT,
        related_name="indicators",
        null=True,
        blank=True,
    )
    available_geographies: models.ManyToManyField = models.ManyToManyField(
        "base.Geography",
        verbose_name="Available Geographies",
        related_name="indicators",
        blank=True,
    )
    temporal_scope_start: models.CharField = models.CharField(
        verbose_name="Temporal Scope Start",
        max_length=255,
        blank=True,
        help_text="Start date of the temporal scope of the indicator",
    )
    temporal_scope_start_note: models.TextField = models.TextField(
        verbose_name="Temporal Scope Start Note",
        blank=True,
        help_text="Note about the temporal scope start date",
    )
    temporal_scope_end: models.CharField = models.CharField(
        verbose_name="Temporal Scope End",
        max_length=255,
        blank=True,
        help_text="End date of the temporal scope of the indicator",
    )
    temporal_scope_end_note: models.TextField = models.TextField(
        verbose_name="Temporal Scope End Note",
        blank=True,
        help_text="Note about the temporal scope end date",
    )
    is_smoothed: models.BooleanField = models.BooleanField(
        verbose_name="Is Smoothed",
        default=False,
        help_text="Indicates if the indicator is smoothed",
    )
    is_weighted: models.BooleanField = models.BooleanField(
        verbose_name="Is Weighted",
        default=False,
        help_text="Indicates if the indicator is weighted",
    )
    is_cumulative: models.BooleanField = models.BooleanField(
        verbose_name="Is Cumulative",
        default=False,
        help_text="Indicates if the indicator is cumulative",
    )
    has_stderr: models.BooleanField = models.BooleanField(
        verbose_name="Has Standard Error",
        default=False,
        help_text="Indicates if the indicator has standard error",
    )
    has_sample_size: models.BooleanField = models.BooleanField(
        verbose_name="Has Sample Size",
        default=False,
        help_text="Indicates if the indicator has sample size",
    )
    high_values_are: models.CharField = models.CharField(
        verbose_name="High Values Are",
        max_length=255,
        blank=True,
        help_text="Indicates if high values are good or bad",
    )
    source: models.ForeignKey = models.ForeignKey(
        "datasources.SourceSubdivision",
        verbose_name="Source Subdivision",
        on_delete=models.PROTECT,
        related_name="indicators",
        null=True,
        blank=True,
    )
    data_censoring: models.TextField = models.TextField(
        verbose_name="Data Censoring",
        blank=True,
        help_text="Description of data censoring applied to the indicator",
    )
    missingness: models.TextField = models.TextField(
        verbose_name="Missingness",
        blank=True,
        help_text="Description of missingness in the indicator",
    )
    organization_access_list: models.CharField = models.CharField(
        verbose_name="Organization Access List",
        max_length=255,
        blank=True,
        help_text="List of organizations that have access to the indicator",
    )
    organization_sharing_list: models.CharField = models.CharField(
        verbose_name="Organization Sharing List",
        max_length=255,
        blank=True,
        help_text="List of organizations that share the indicator",
    )
    license: models.CharField = models.CharField(
        verbose_name="License",
        max_length=255,
        blank=True,
        help_text="License of the indicator",
    )
    restrictions: models.TextField = models.TextField(
        verbose_name="Restrictions",
        blank=True,
        help_text="Restrictions on the use of the indicator",
    )
    last_updated: models.DateField = models.DateField(
        verbose_name="Last Updated",
        blank=True,
        null=True,
        help_text="Date when the indicator was last updated",
    )
    from_date: models.DateField = models.DateField(
        verbose_name="From Date",
        blank=True,
        null=True,
        help_text="Date when the indicator was created",
    )
    to_date: models.DateField = models.DateField(
        verbose_name="To Date",
        blank=True,
        null=True,
        help_text="Date when the indicator was deleted",
    )
    indicator_availability_days: models.IntegerField = models.IntegerField(
        verbose_name="Indicator Availability Days",
        blank=True,
        null=True,
        help_text="Number of days the indicator is available",
    )

    base: models.ForeignKey = models.ForeignKey(
        "indicators.Indicator",
        verbose_name="Base Indicator",
        related_name="base_for",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    indicator_set: models.ForeignKey = models.ForeignKey(
        "indicatorsets.IndicatorSet",
        verbose_name="Indicator Set",
        on_delete=models.PROTECT,
        related_name="indicators",
        null=True,
        blank=True,
    )

    source_type: models.CharField = models.CharField(
        verbose_name="Source Type",
        max_length=255,
        choices=SOURCE_TYPES,
        default="covidcast",
        help_text="Type of source for the indicator",
        blank=True,
        null=True,
    )

    use_in_express_interface: models.BooleanField = models.BooleanField(
        verbose_name="Use in Express Interface",
        default=False,
        help_text="Indicates if the indicator is used in the Express Interface",
    )

    class Meta:
        verbose_name = "Indicator"
        verbose_name_plural = "Indicators"
        ordering = ["name"]
        indexes = [
            models.Index(
                fields=[
                    "name",
                ],
                name="indicator_name_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "source"], name="unique_indicator_name"
            ),
            models.UniqueConstraint(
                fields=["name", "indicator_set"],
                name="unique_indicator_indicator_set_name",
            ),
        ]

    @property
    def same_base_indicators(self):
        """
        Returns the indicators that have the same base indicator.
        """
        return self.base.base_for.exclude(id=self.id) if self.base else None

    def __str__(self) -> str:
        """
        Returns the name of the indicator as a string.

        """
        return str(self.name)

    def clean(self) -> None:
        """
        Validate that the indicator has a base if any other indicators exist.

        Raises:
            ValidationError: If there are other indicators and this indicator doesn't have a base.
        """
        if Indicator.objects.exists() and not self.base:
            raise ValidationError(_("Indicator should have base."))

    @property
    def get_display_name(self):
        if self.display_name:
            return self.display_name
        if self.member_name:
            return self.member_name
        else:
            return self.name


class OtherEndpointIndicator(Indicator):

    class Meta:
        proxy = True
        verbose_name = "Other Endpoint Indicator"
        verbose_name_plural = "Other Endpoint Indicators"


class NonDelphiIndicator(Indicator):

    class Meta:
        proxy = True
        verbose_name = "Non-Delphi Indicator"
        verbose_name_plural = "Non-Delphi Indicators"


class USStateIndicator(Indicator):

    class Meta:
        proxy = True
        verbose_name = "US State Indicator"
        verbose_name_plural = "US State Indicators"
