from io import BytesIO, TextIOWrapper

import requests
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django.utils.module_loading import import_string
from import_export.admin import ImportExportModelAdmin
from import_export.results import RowResult

from datasources.models import SourceSubdivision, OtherEndpointSourceSubdivision
from datasources.resources import SourceSubdivisionResource, OtherEndpointSourceSubdivisionResource


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
        resource = SourceSubdivisionResource()
        format_class = import_string("import_export.formats.base_formats.CSV")

        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1zb7ItJzY5oq1n-2xtvnPBiJu2L3AqmCKubrLkKJZVHs/export?format=csv&gid=0"

        response = requests.get(spreadsheet_url)
        response.raise_for_status()

        csvfile = TextIOWrapper(BytesIO(response.content), encoding="utf-8")

        dataset = format_class().create_dataset(csvfile.read())

        result = resource.import_data(dataset, dry_run=False, raise_errors=True)

        if result.has_errors():
            error_messages = ["Import errors!"]
            for error in result.base_errors:
                error_messages.append(repr(error.error))
            for line, errors in result.row_errors():
                for error in errors:
                    error_messages.append(f"Line number: {line} - {repr(error.error)}")
            self.message_user(request, "\n".join(error_messages), level=messages.ERROR)
        else:
            success_message = (
                "Import finished: {} new, {} updated, {} deleted and {} skipped {}."
            ).format(
                result.totals[RowResult.IMPORT_TYPE_NEW],
                result.totals[RowResult.IMPORT_TYPE_UPDATE],
                result.totals[RowResult.IMPORT_TYPE_DELETE],
                result.totals[RowResult.IMPORT_TYPE_SKIP],
                resource._meta.model._meta.verbose_name_plural,
            )
            self.message_user(request, success_message, level=messages.SUCCESS)
        return redirect(".")


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
        resource = OtherEndpointSourceSubdivisionResource()
        format_class = import_string("import_export.formats.base_formats.CSV")

        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1zb7ItJzY5oq1n-2xtvnPBiJu2L3AqmCKubrLkKJZVHs/export?format=csv&gid=214580132"

        response = requests.get(spreadsheet_url)
        response.raise_for_status()

        csvfile = TextIOWrapper(BytesIO(response.content), encoding="utf-8")

        dataset = format_class().create_dataset(csvfile.read())

        result = resource.import_data(dataset, dry_run=False, raise_errors=True)

        if result.has_errors():
            error_messages = ["Import errors!"]
            for error in result.base_errors:
                error_messages.append(repr(error.error))
            for line, errors in result.row_errors():
                for error in errors:
                    error_messages.append(f"Line number: {line} - {repr(error.error)}")
            self.message_user(request, "\n".join(error_messages), level=messages.ERROR)
        else:
            success_message = (
                "Import finished: {} new, {} updated, {} deleted and {} skipped {}."
            ).format(
                result.totals[RowResult.IMPORT_TYPE_NEW],
                result.totals[RowResult.IMPORT_TYPE_UPDATE],
                result.totals[RowResult.IMPORT_TYPE_DELETE],
                result.totals[RowResult.IMPORT_TYPE_SKIP],
                resource._meta.model._meta.verbose_name_plural,
            )
            self.message_user(request, success_message, level=messages.SUCCESS)
        return redirect(".")
