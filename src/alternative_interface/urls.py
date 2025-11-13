from django.urls import path
from django.urls.resolvers import URLPattern
from alternative_interface.views import alternative_interface_view

urlpatterns: list[URLPattern] = [
    path("alternative_interface", alternative_interface_view, name="alternative_interface"),
]
