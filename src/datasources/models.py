from django.db import models

from base.models import SOURCE_TYPES


# Create your models here.
class SourceSubdivision(models.Model):

    name: models.CharField = models.CharField(
        verbose_name="Name", max_length=255, unique=True
    )

    display_name: models.CharField = models.CharField(
        verbose_name="Display Name", max_length=255, blank=True
    )

    external_name: models.CharField = models.CharField(
        verbose_name="External Name", max_length=255, blank=True
    )

    description: models.TextField = models.TextField(
        verbose_name="Description", blank=True
    )

    license: models.CharField = models.CharField(
        verbose_name="License", max_length=255, blank=True
    )

    dua: models.CharField = models.CharField(
        verbose_name="Data Use Agreement", max_length=255, blank=True
    )

    datasource_name: models.CharField = models.CharField(
        verbose_name="Datasource Name", max_length=255, blank=True
    )

    source_type: models.CharField = models.CharField(
        verbose_name="Source Type",
        max_length=255,
        choices=SOURCE_TYPES,
        default="covidcast",
        help_text="Type of source for the source subdivision",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Source Subdivision"
        verbose_name_plural = "Source Subdivisions"
        indexes = [
            models.Index(fields=["name"], name="source_subdivision_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name"], name="unique_source_subdivision_name"
            )
        ]

    def __str__(self):
        return self.name

    def get_display_name(self):
        return self.display_name if self.display_name else self.name


class OtherEndpointSourceSubdivision(SourceSubdivision):
    class Meta:
        proxy = True
        verbose_name = "Other Endpoint Source Subdivision"
        verbose_name_plural = "Other Endpoint Source Subdivisions"
