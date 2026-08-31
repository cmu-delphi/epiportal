import re

import requests
from delphi_utils import get_structured_logger
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden

from indicatorsets.utils.constants import MIGRATED_DATASOURCES

logger = get_structured_logger("indicatorsets.proxy_views")

FILENAME_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_.-]")

# The v5-native endpoints, plus any covidcast source whose exports now route to
# v5 -- derived so migrating a source does not silently 400 its downloads.
VIZ_SOURCES = ("nwss", "pophive") + tuple(sorted(set(MIGRATED_DATASOURCES.values())))


def download_viz_export(request):
    """Fetch a viz export from the Epidata v5 API and stream it back same-origin.

    The Epidata API doesn't send a Content-Disposition header on this endpoint,
    and the anchor's `download` attribute is ignored by browsers for cross-origin
    links, so linking directly at the API never triggers a download. Proxying
    through our own domain makes the link same-origin so `download` takes effect.
    """
    source = request.GET.get("source")
    if source not in VIZ_SOURCES:
        return HttpResponseBadRequest("Invalid source")

    params = {
        "source": source,
        "signal": request.GET.get("signal", ""),
        "geo_type": request.GET.get("geo_type", ""),
        "geo_value": request.GET.get("geo_value", ""),
        "time_values": request.GET.get("time_values", ""),
        "format": request.GET.get("format", "json"),
        "header": request.GET.get("header", "false"),
    }
    extra_keys = request.GET.get("extra_keys")
    if extra_keys:
        params["extra_keys"] = extra_keys
    fill_method = request.GET.get("fill_method")
    if fill_method:
        params["fill_method"] = fill_method
    api_key = request.GET.get("api_key") or settings.EPIDATA_API_KEY
    if api_key:
        params["api_key"] = api_key

    filename = FILENAME_SANITIZE_RE.sub(
        "_", request.GET.get("filename", f"{source}_export.json")
    )

    try:
        upstream = requests.get(
            f"{settings.EPIDATA_V5_URL}viz/", params=params, timeout=(5, 30)
        )
        if upstream.status_code == 401:
            return HttpResponseForbidden("Invalid API key")
        upstream.raise_for_status()
    except requests.RequestException:
        logger.exception(
            "Error proxying viz export download",
            extra={"source": source, "signal": params["signal"]},
        )
        return HttpResponse("Error fetching export data", status=502)

    response = HttpResponse(
        upstream.content,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
