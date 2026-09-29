from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest.views import (
    PathogenViewSet,
    IndicatorViewSet,
    AvailableIndicatorsViewSet,
    IndicatorMetaView,
)

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
    path(
        "rest/meta/indicators/",
        IndicatorMetaView.as_view(),
        name="meta-indicators",
    ),
]
