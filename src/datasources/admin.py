from django.contrib import admin
from django.urls import path
from django.conf import settings
from import_export.admin import ImportExportModelAdmin

from base.utils import import_data
from datasources.models import (OtherEndpointSourceSubdivision,
                                SourceSubdivision)
from datasources.resources import (OtherEndpointSourceSubdivisionResource,
                                   SourceSubdivisionResource)


@admin.register(SourceSubdivision)
class SourceSubdivisionAdmin(ImportExportModelAdmin):
    """
    Admin interface for Source Subdivision model.
    """

    list_display = (
        "name",
        "display_name",
        "external_name",
        "description",
        "license",
        "dua",
        "datasource_name",
    )
    search_fields = ("name", "display_name", "external_name")
    ordering = ["name"]
    list_filter = ["datasource_name"]
    resource_classes = [SourceSubdivisionResource]

    change_list_template = "admin/datasources/source_subdivision_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-from-spreadsheet",
                self.admin_site.admin_view(self.import_from_spreadsheet),
                name="import_sourcesubdivisions",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        return import_data(self, request, SourceSubdivisionResource, settings.SPREADSHEET_URLS["source_subdivisions"])


@admin.register(OtherEndpointSourceSubdivision)
class OtherEndpointSourceSubdivisionAdmin(ImportExportModelAdmin):
    """
    Admin interface for Other Endpoint Source Subdivision model.
    """

    list_display = (
        "name",
        "display_name",
        "external_name",
        "description",
        "license",
        "dua",
        "datasource_name",
    )
    search_fields = ("name", "display_name", "external_name")
    ordering = ["name"]
    list_filter = ["datasource_name"]
    resource_classes = [OtherEndpointSourceSubdivisionResource]

    change_list_template = "admin/datasources/source_subdivision_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-from-spreadsheet",
                self.admin_site.admin_view(self.import_from_spreadsheet),
                name="import_other_endpoint_sourcesubdivisions",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        return import_data(
            self, request, OtherEndpointSourceSubdivisionResource, settings.SPREADSHEET_URLS["other_endpoint_source_subdivisions"]
        )
