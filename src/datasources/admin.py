from django.contrib import admin
from django.urls import path
from django.conf import settings
from import_export.admin import ImportExportModelAdmin

from base.utils import import_data, download_source_file
from datasources.models import SourceSubdivision
from datasources.resources import SourceSubdivisionResource


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
            path(
                "download-source-file",
                self.admin_site.admin_view(self.download_source_subdivision),
                name="download_source_subdivision",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        return import_data(
            self,
            request,
            SourceSubdivisionResource,
            settings.SPREADSHEET_URLS["sources"],
        )

    def download_source_subdivision(self, request):
        return download_source_file(
            self,
            request,
            settings.SPREADSHEET_URLS["sources"],
            "Source_Subdivisions.csv",
        )

