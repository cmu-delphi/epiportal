from io import BytesIO, TextIOWrapper

import requests
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django.utils.module_loading import import_string
from import_export.admin import ImportExportModelAdmin
from import_export.results import RowResult

from indicators.models import (Category, FormatType, Indicator,
                               IndicatorGeography, IndicatorType,
                               NonDelphiIndicator, OtherEndpointIndicator)
from indicators.resources import (IndicatorBaseResource, IndicatorResource,
                                  NonDelphiIndicatorResource,
                                  OtherEndpointIndicatorResource)


@admin.register(IndicatorType)
class IndicatorTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name")
    search_fields = ("name", "display_name")
    ordering = ("name",)
    list_per_page = 50


@admin.register(FormatType)
class FormatTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name")
    search_fields = ("name", "display_name")
    ordering = ("name",)
    list_per_page = 50


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name")
    search_fields = ("name", "display_name")
    ordering = ("name",)
    list_per_page = 50


@admin.register(IndicatorGeography)
class IndicatorGeographyAdmin(admin.ModelAdmin):
    list_display = ("indicator", "geography", "aggregated_by_delphi")
    search_fields = ("indicator__name", "geography__name")
    list_filter = ("aggregated_by_delphi",)
    ordering = ("indicator__name",)
    list_per_page = 50
    list_select_related = True


@admin.register(Indicator)
class IndicatorAdmin(ImportExportModelAdmin):
    list_display = (
        "name",
        "description",
        "indicator_type",
        "format_type",
        "category",
        "geographic_scope",
    )
    search_fields = ("name", "description")
    list_filter = ("indicator_type", "format_type", "category", "geographic_scope")
    ordering = ("name",)
    list_per_page = 50
    list_select_related = True
    list_editable = ("indicator_type", "format_type", "category", "geographic_scope")
    list_display_links = ("name",)

    resource_classes = [IndicatorResource, IndicatorBaseResource]

    change_list_template = "admin/indicators/indicator_changelist.html"

    def get_queryset(self, request):
        # Exclude proxy model objects
        qs = super().get_queryset(request)
        return qs.filter(source_type="covidcast")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-from-spreadsheet",
                self.admin_site.admin_view(self.import_from_spreadsheet),
                name="import_indicators",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        resource = IndicatorResource()
        format_class = import_string("import_export.formats.base_formats.CSV")

        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1zb7ItJzY5oq1n-2xtvnPBiJu2L3AqmCKubrLkKJZVHs/export?format=csv&gid=329338228"

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


@admin.register(OtherEndpointIndicator)
class OtherEndpointIndicatorAdmin(ImportExportModelAdmin):
    list_display = (
        "name",
        "description",
        "indicator_type",
        "format_type",
        "category",
        "geographic_scope",
    )
    search_fields = ("name", "description")
    list_filter = ("indicator_type", "format_type", "category", "geographic_scope")
    ordering = ("name",)
    list_per_page = 50
    list_select_related = True
    list_editable = ("indicator_type", "format_type", "category", "geographic_scope")
    list_display_links = ("name",)

    resource_classes = [OtherEndpointIndicatorResource]

    def get_queryset(self, request):
        # Exclude proxy model objects
        qs = super().get_queryset(request)
        return qs.filter(source_type="other_endpoint")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-from-spreadsheet",
                self.admin_site.admin_view(self.import_from_spreadsheet),
                name="import_otherendpoint_indicators",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        resource = OtherEndpointIndicatorResource()
        format_class = import_string("import_export.formats.base_formats.CSV")

        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1zb7ItJzY5oq1n-2xtvnPBiJu2L3AqmCKubrLkKJZVHs/export?format=csv&gid=1364181703"

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


@admin.register(NonDelphiIndicator)
class NonDelphiIndicatorAdmin(ImportExportModelAdmin):
    list_display = (
        "name",
        "member_name",
        "description",
        "indicator_set",
    )
    search_fields = ("name", "description")
    ordering = ("name",)
    list_per_page = 50
    list_select_related = True
    list_editable = ("member_name", "description", "indicator_set")
    list_display_links = ("name",)

    resource_classes = [NonDelphiIndicatorResource]

    def get_queryset(self, request):
        # Exclude proxy model objects
        qs = super().get_queryset(request)
        return qs.filter(source_type="non_delphi")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-from-spreadsheet",
                self.admin_site.admin_view(self.import_from_spreadsheet),
                name="import_nondelphi_indicators",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        resource = NonDelphiIndicatorResource()
        format_class = import_string("import_export.formats.base_formats.CSV")

        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1zb7ItJzY5oq1n-2xtvnPBiJu2L3AqmCKubrLkKJZVHs/export?format=csv&gid=493612863"

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
