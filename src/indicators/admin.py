from django.conf import settings
from django.contrib import admin
from django.urls import path
from import_export.admin import ImportExportModelAdmin

from base.utils import import_data
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
        return import_data(
            self, request, IndicatorResource, settings.SPREADSHEET_URLS["indicators"]
        )


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

    change_list_template = "admin/indicators/indicator_changelist.html"

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
        return import_data(
            self,
            request,
            OtherEndpointIndicatorResource,
            settings.SPREADSHEET_URLS["other_endpoint_indicators"],
        )


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

    change_list_template = "admin/indicators/indicator_changelist.html"

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
        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1zb7ItJzY5oq1n-2xtvnPBiJu2L3AqmCKubrLkKJZVHs/export?format=csv&gid=493612863"

        return import_data(self, request, NonDelphiIndicatorResource, spreadsheet_url)
