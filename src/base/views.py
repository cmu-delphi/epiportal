import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from django.views.generic import TemplateView


class BadRequestErrorView(TemplateView):
    """
    Displays a custom 400 error page when a bad request is made.
    """

    template_name = "http_errors/400.html"


class ForbiddenErrorView(TemplateView):
    """
    Displays a custom 403 error page when access to a resource is forbidden.
    """

    template_name = "http_errors/403.html"


class NotFoundErrorView(TemplateView):
    """
    Displays a custom 404 error page when a page is not found.
    """

    template_name = "http_errors/404.html"


class InternalServerErrorView(TemplateView):
    """
    Displays a custom 500 error page when an internal server error occurs.
    """

    template_name = "http_errors/500.html"


ALLOWED_ENDPOINTS = {"covidcast/geo_coverage", "covidcast/meta"}


def epidata(request, endpoint=""):
    endpoint = endpoint.strip("/")
    if endpoint not in ALLOWED_ENDPOINTS:
        return HttpResponseForbidden("Endpoint not allowed")
    params = {k: v for k, v in request.GET.items() if k != "api_key"}
    params["api_key"] = settings.EPIDATA_API_KEY
    try:
        response = requests.get(
            f"{settings.EPIDATA_URL}{endpoint}", params=params, timeout=10
        )
        response.raise_for_status()
    except requests.RequestException:
        return JsonResponse({"epidata": [], "result": -1}, status=502)
    return JsonResponse(response.json(), safe=False, status=response.status_code)
