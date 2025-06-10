from django.urls import re_path
from django.urls.resolvers import URLPattern

from base.views import epidata

urlpatterns: list[URLPattern] = [
    re_path(r"^epidata/(?P<endpoint>.*)/$", epidata, name="epidata"),
]
