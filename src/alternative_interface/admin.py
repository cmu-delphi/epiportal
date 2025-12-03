from django.contrib import admin

from import_export.admin import ImportExportModelAdmin

from alternative_interface.models import ExpressViewIndicator
from alternative_interface.resources import ExpressViewIndicatorResource


@admin.register(ExpressViewIndicator)
class ExpressViewIndicatorAdmin(ImportExportModelAdmin):
    resource_class = ExpressViewIndicatorResource
    list_display = ["menu_item", "indicator", "display_name"]
    search_fields = ["menu_item", "indicator", "display_name"]
    list_filter = ["menu_item", "indicator"]
    ordering = ["menu_item", "indicator"]
