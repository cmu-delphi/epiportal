from django.urls import path
from django.urls.resolvers import URLPattern
from alternative_interface.views import (
    alternative_interface_view,
    get_available_geos_ajax,
    get_chart_data_ajax,
)

urlpatterns: list[URLPattern] = [
    path("alternative_interface", alternative_interface_view, name="alternative_interface"),
    path("api/get_available_geos", get_available_geos_ajax, name="get_available_geos_ajax"),
    path("api/get_chart_data", get_chart_data_ajax, name="get_chart_data_ajax"),
]
