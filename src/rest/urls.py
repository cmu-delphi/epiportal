from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest.views import PathogenViewSet
from rest.views import IndicatorViewSet
from rest.views import AvailableIndicatorsViewSet

router = DefaultRouter()
router.register(r"rest/pathogens", PathogenViewSet)
router.register(r"rest/indicators", IndicatorViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "available-indicators/",
        AvailableIndicatorsViewSet.as_view(),
        name="available-indicators",
    ),
]
