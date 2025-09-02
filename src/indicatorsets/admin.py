from django.conf import settings
from django.contrib import admin
from django.urls import path
from import_export.admin import ImportExportModelAdmin

from base.utils import download_source_file, import_data
from indicatorsets.models import (
    ColumnDescription,
    FilterDescription,
    IndicatorSet,
    NonDelphiIndicatorSet,
)
from indicatorsets.resources import IndicatorSetResource, NonDelphiIndicatorSetResource


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
            path(
                "download-source-file",
                self.admin_site.admin_view(self.download_indicator_set),
                name="download_indicator_set",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        return import_data(
            self,
            request,
            IndicatorSetResource,
            settings.SPREADSHEET_URLS["indicator_sets"],
        )

    def download_indicator_set(self, request):
        return download_source_file(
            settings.SPREADSHEET_URLS["indicator_sets"], "Indicator_Sets.csv"
        )


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
            path(
                "download-source-file",
                self.admin_site.admin_view(self.download_nondelphi_indicator_set),
                name="download_nondelphi_indicator_set",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        return import_data(
            self,
            request,
            NonDelphiIndicatorSetResource,
            settings.SPREADSHEET_URLS["non_delphi_indicator_sets"],
        )

    def download_nondelphi_indicator_set(self, request):
        return download_source_file(
            settings.SPREADSHEET_URLS["non_delphi_indicator_sets"],
            "Non_Delphi_Indicator_Sets.csv",
        )


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
