from django.db import models
from django.utils import timezone
from django.utils.html import strip_tags

USED_IN_CHOICES = (
    ("indicators", "Indicators"),
    ("indicatorsets", "Indicator Sets"),
)

SOURCE_TYPES = [
    ("covidcast", "Covidcast"),
    ("other_endpoint", "Other Endpoint"),
    ("non_delphi", "Non Delphi"),
    ("us_state", "US State"),
]


class Pathogen(models.Model):

    name: models.CharField = models.CharField(verbose_name="Name", max_length=255)
    display_name: models.CharField = models.CharField(
        verbose_name="Display Name", max_length=255, blank=True
    )

    used_in: models.CharField = models.CharField(
        verbose_name="Used In",
        max_length=255,
        blank=True,
        choices=USED_IN_CHOICES,
        help_text="Indicates where the pathogen is used",
    )

    display_order_number: models.IntegerField = models.IntegerField(
        verbose_name="Display Order Number", blank=True, null=True
    )

    class Meta:
        verbose_name = "Pathogen"
        verbose_name_plural = "Pathogens"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="pathogen_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "used_in"], name="unique_pathogen_name_used_in"
            )
        ]

    def __str__(self):
        return self.display_name if self.display_name else self.name


class GeographicScope(models.Model):

    name: models.CharField = models.CharField(verbose_name="Name", max_length=255)

    used_in: models.CharField = models.CharField(
        verbose_name="Used In",
        max_length=255,
        blank=True,
        choices=USED_IN_CHOICES,
        help_text="Indicates where the geographic scope is used",
    )

    display_order_number: models.IntegerField = models.IntegerField(
        verbose_name="Display Order Number", blank=True, null=True
    )

    class Meta:
        verbose_name = "Geographic Scope"
        verbose_name_plural = "Geographic Scopes"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="geographic_scope_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "used_in"],
                name="unique_geographic_scope_name_used_in",
            )
        ]

    def __str__(self):
        return self.name


class Geography(models.Model):

    name: models.CharField = models.CharField(verbose_name="Name", max_length=255)
    display_name: models.CharField = models.CharField(
        verbose_name="Display Name", max_length=255, blank=True
    )
    short_name: models.CharField = models.CharField(
        verbose_name="Short Name", max_length=255, blank=True
    )
    display_order_number: models.IntegerField = models.IntegerField(
        verbose_name="Display Order Number", blank=True, null=True
    )
    used_in: models.CharField = models.CharField(
        verbose_name="Used In",
        max_length=255,
        blank=True,
        choices=USED_IN_CHOICES,
        help_text="Indicates where the geography is used",
    )

    class Meta:
        verbose_name = "Geography"
        verbose_name_plural = "Geographies"
        ordering = ['display_order_number']
        indexes = [
            models.Index(fields=["name"], name="geography_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "used_in"], name="unique_geography_name_used_in"
            )
        ]

    def __str__(self):
        return self.display_name if self.display_name else self.name


class SeverityPyramidRung(models.Model):

    name: models.CharField = models.CharField(verbose_name="Name", max_length=255)
    display_name: models.CharField = models.CharField(
        verbose_name="Display Name", max_length=255, blank=True
    )
    display_order_number: models.IntegerField = models.IntegerField(
        verbose_name="Display Order Number", blank=True, null=True
    )
    used_in: models.CharField = models.CharField(
        verbose_name="Used In",
        max_length=255,
        blank=True,
        choices=USED_IN_CHOICES,
        help_text="Indicates where the severity pyramid rung is used",
    )

    class Meta:
        verbose_name = "Severity Pyramid Rung"
        verbose_name_plural = "Severity Pyramid Rungs"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="severity_pyramid_rung_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "used_in"],
                name="unique_severity_pyramid_rung_name_used_in",
            )
        ]

    def __str__(self):
        return self.display_name if self.display_name else self.name


class GeographyUnit(models.Model):
    geo_id: models.CharField = models.CharField(verbose_name="Geo ID", max_length=255)
    name: models.CharField = models.CharField(
        verbose_name="Name", max_length=255, blank=True
    )
    display_name: models.CharField = models.CharField(
        verbose_name="Display Name", max_length=255, blank=True
    )
    level: models.IntegerField = models.IntegerField(
        verbose_name="Level", blank=True, null=True
    )
    geo_level: models.ForeignKey = models.ForeignKey(
        Geography,
        on_delete=models.CASCADE,
        related_name="geography_units",
        verbose_name="Geography Level",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Geography Unit"
        verbose_name_plural = "Geography Units"
        ordering = ["geo_id"]
        indexes = [
            models.Index(fields=["geo_id"], name="geo_unit_geo_id_idx"),
        ]

    def __str__(self):
        return self.display_name if self.display_name else self.name


BANNER_STYLE_CHOICES = (
    ("info", "Info"),
    ("warning", "Warning"),
    ("danger", "Danger"),
)


class BannerQuerySet(models.QuerySet):
    def current(self):
        """Active banners inside their date window, newest first.

        An empty ``starts_at`` means "already started" and an empty
        ``ends_at`` means "until switched off".
        """
        now = timezone.now()
        return (
            self.filter(is_active=True)
            .filter(models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now))
            .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now))
            .order_by("-created_at", "-pk")
        )


class Banner(models.Model):
    """A site-wide notice shown above the page content, e.g. the v5 migration."""

    message: models.TextField = models.TextField(
        verbose_name="Message",
        help_text="Shown as written, HTML included, so links can be added with "
        '<code>&lt;a href="..."&gt;</code>.',
    )
    style: models.CharField = models.CharField(
        verbose_name="Style",
        max_length=16,
        choices=BANNER_STYLE_CHOICES,
        default="info",
    )
    is_active: models.BooleanField = models.BooleanField(
        verbose_name="Active", default=True
    )
    starts_at: models.DateTimeField = models.DateTimeField(
        verbose_name="Starts at",
        blank=True,
        null=True,
        help_text="Leave empty to show it straight away.",
    )
    ends_at: models.DateTimeField = models.DateTimeField(
        verbose_name="Ends at",
        blank=True,
        null=True,
        help_text="Leave empty to show it until it is switched off.",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    objects = BannerQuerySet.as_manager()

    class Meta:
        verbose_name = "Banner"
        verbose_name_plural = "Banners"
        ordering = ["-created_at"]

    def __str__(self):
        return strip_tags(self.message)[:80]

    @property
    def dismiss_key(self):
        """The key a visitor's browser stores when they close this banner.

        It includes the last edit time, so an edited banner reappears for
        everyone who closed an earlier version.
        """
        return f"banner-{self.pk}-{int(self.updated_at.timestamp() * 1_000_000)}"
