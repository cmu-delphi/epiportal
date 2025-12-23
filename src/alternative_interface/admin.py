from django.conf import settings
from django.contrib import admin
from django.urls import path
from import_export.admin import ImportExportModelAdmin

from alternative_interface.models import ExpressViewIndicator
from alternative_interface.resources import ExpressViewIndicatorResource
from base.utils import download_source_file, import_data


@admin.register(ExpressViewIndicator)
class ExpressViewIndicatorAdmin(ImportExportModelAdmin):
    resource_class = ExpressViewIndicatorResource
    list_display = ["menu_item", "indicator", "display_name"]
    search_fields = ["menu_item", "indicator", "display_name"]
    list_filter = ["menu_item", "indicator"]
    ordering = ["menu_item", "indicator"]

    change_list_template = "admin/alternative_interface/express_view_indicators_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-from-spreadsheet",
                self.admin_site.admin_view(self.import_from_spreadsheet),
                name="import_express_view_indicators",
            ),
            path(
                "download-source-file",
                self.admin_site.admin_view(self.download_express_view_indicators),
                name="download_express_view_indicators",
            ),
        ]
        return custom_urls + urls

    def import_from_spreadsheet(self, request):
        return import_data(
            self,
            request,
            ExpressViewIndicatorResource,
            settings.SPREADSHEET_URLS["express_view_indicators"],
        )

    def download_express_view_indicators(self, request):
        return download_source_file(
            settings.SPREADSHEET_URLS["express_view_indicators"],
            "Express_View_Indicators.csv",
        )
