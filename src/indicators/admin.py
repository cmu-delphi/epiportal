from django.conf import settings
from django.contrib import admin
from django.urls import path
from import_export.admin import ImportExportModelAdmin

from base.models import Pathogen, SeverityPyramidRung
from base.utils import download_source_file
from indicators.models import Category, FormatType, Indicator, IndicatorType
from indicators.resources import IndicatorResource


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


@admin.register(Indicator)
class IndicatorAdmin(ImportExportModelAdmin):
    list_display = (
        "name",
        "indicator_set",
        "description",
        "indicator_type",
        "format_type",
        "category",
    )
    search_fields = ("name", "description")
    list_filter = ("indicator_set__kind", "indicator_type", "format_type", "category")
    ordering = ("name",)
    list_per_page = 50
    list_select_related = True
    list_editable = ("indicator_type", "format_type", "category")
    list_display_links = ("name",)

    resource_classes = [IndicatorResource]

    change_list_template = "admin/indicators/indicator_changelist.html"

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """
        Filter pathogens and severity_pyramid_rungs fields to show only a subset of Pathogen and SeverityPyramidRung objects.
        Modify the filter criteria as needed.
        """
        if db_field.name == "pathogens":
            # Filter to show only pathogens used in indicators
            kwargs["queryset"] = Pathogen.objects.filter(
                used_in="indicators"
            ).order_by("display_order_number")
        if db_field.name == "severity_pyramid_rungs":
            # Filter to show only severity pyramid rungs used in indicators
            kwargs["queryset"] = SeverityPyramidRung.objects.filter(
                used_in="indicators"
            ).order_by("display_order_number")
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-from-spreadsheet",
                self.admin_site.admin_view(self.import_from_spreadsheet),
                name="import_indicators",
            ),
            path(
                "download-source-file",
                self.admin_site.admin_view(self.download_indicator),
                name="download_indicator",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        from indicatorsets.metadata_import import import_metadata_from_admin

        return import_metadata_from_admin(self, request)

    def download_indicator(self, request):
        return download_source_file(
            self, request, settings.SPREADSHEET_URLS["indicators"], "Indicators.csv"
        )
