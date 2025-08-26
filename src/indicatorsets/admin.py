import csv
import sys
from io import BytesIO, TextIOWrapper

import requests
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django.utils.module_loading import import_string
from import_export.admin import ImportExportModelAdmin
from import_export.results import RowResult

from indicatorsets.models import (ColumnDescription, FilterDescription,
                                  IndicatorSet, NonDelphiIndicatorSet)
from indicatorsets.resources import (IndicatorSetResource,
                                     NonDelphiIndicatorSetResource)


# Register your models here.
@admin.register(IndicatorSet)
class IndicatorSetAdmin(ImportExportModelAdmin):
    """
    Admin interface for the IndicatorSet model.
    """

    resource_class = IndicatorSetResource
    list_display = (
        "name",
        "short_name",
        "description",
        "maintainer_name",
        "maintainer_email",
        "organization",
        "origin_datasource",
        "language",
        "version_number",
        "original_data_provider",
        "origin_datasource",
    )
    search_fields = ("name", "short_name", "description")
    ordering = ["name"]
    list_filter = ["original_data_provider"]

    def get_queryset(self, request):
        # Exclude proxy model objects
        qs = super().get_queryset(request)
        return qs.exclude(source_type="non_delphi")

    change_list_template = "admin/indicatorsets/indicator_set_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-from-spreadsheet",
                self.admin_site.admin_view(self.import_from_spreadsheet),
                name="import_indicatorsets",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        resource = IndicatorSetResource()
        format_class = import_string("import_export.formats.base_formats.CSV")

        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1zb7ItJzY5oq1n-2xtvnPBiJu2L3AqmCKubrLkKJZVHs/export?format=csv&gid=1266808975"

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


@admin.register(NonDelphiIndicatorSet)
class NonDelphiIndicatorSetAdmin(ImportExportModelAdmin):
    """
    Admin interface for the IndicatorSet model.
    """

    resource_class = NonDelphiIndicatorSetResource
    list_display = (
        "name",
        "short_name",
        "description",
        "maintainer_name",
        "maintainer_email",
        "organization",
        "origin_datasource",
        "language",
        "version_number",
        "original_data_provider",
        "origin_datasource",
        "source_type",
    )
    search_fields = ("name", "short_name", "description")
    ordering = ["name"]
    list_filter = ["original_data_provider", "source_type"]

    def get_queryset(self, request):
        # Exclude proxy model objects
        qs = super().get_queryset(request)
        return qs.filter(source_type="non_delphi")

    change_list_template = "admin/indicatorsets/indicator_set_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-from-spreadsheet",
                self.admin_site.admin_view(self.import_from_spreadsheet),
                name="import_nondelphi_indicatorsets",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        resource = NonDelphiIndicatorSetResource()
        format_class = import_string("import_export.formats.base_formats.CSV")

        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1zb7ItJzY5oq1n-2xtvnPBiJu2L3AqmCKubrLkKJZVHs/export?format=csv&gid=1266477926"

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


@admin.register(FilterDescription)
class FilterDescriptionAdmin(admin.ModelAdmin):
    """
    Admin interface for the FilterDescription model.
    """

    list_display = ("name", "description")
    search_fields = ("name", "description")
    ordering = ["name"]
    list_filter = ["name"]
    list_editable = ("description",)


@admin.register(ColumnDescription)
class ColumnDescriptionAdmin(admin.ModelAdmin):
    """
    Admin interface for the ColumnDescription model.
    """

    list_display = ("name", "description")
    search_fields = ("name", "description")
    ordering = ["name"]
    list_filter = ["name"]
    list_editable = ("description",)
