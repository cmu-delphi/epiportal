"""
Request logging middleware that captures comprehensive data from all HTTP requests.
"""

import time
import uuid
from typing import Any

from delphi_utils import get_structured_logger
from django.utils.deprecation import MiddlewareMixin

from epiportal.utils import get_client_ip

logger = get_structured_logger("epiportal.requests")

# Headers that may contain sensitive data - values will be redacted
SENSITIVE_HEADERS = frozenset(
    name.lower()
    for name in (
        "authorization",
        "cookie",
        "x-api-key",
        "x-auth-token",
        "proxy-authorization",
        "x-csrf-token",
        "x-session-id",
    )
)

# Path segments to exclude from request logging (matched anywhere in path)
LOG_EXCLUDE_PATH_PATTERNS = (
    # "get_table_stats_info",
    # "get_related_indicators",
    # "get_available_geos",
)


def _should_log_request(request) -> bool:
    """Return False if this request should be excluded from logging."""
    path = request.path
    return not any(pattern in path for pattern in LOG_EXCLUDE_PATH_PATTERNS)


def _sanitize_headers(meta: dict) -> dict[str, str]:
    """Extract HTTP headers from META, redacting sensitive ones."""
    headers = {}
    for key, value in meta.items():
        if key.startswith("HTTP_"):
            header_name = key[5:].replace("_", "-").lower()
            if header_name in SENSITIVE_HEADERS:
                headers[header_name] = "[REDACTED]"
            elif value:
                headers[header_name] = str(value)
    return headers


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware that logs every HTTP request with comprehensive request and response data.
    """

    def process_request(self, request):
        request._request_start_time = time.monotonic()
        request._request_id = (
            request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        )
        return None

    def process_response(self, request, response):
        if not _should_log_request(request):
            if hasattr(request, "_request_id"):
                response["X-Request-ID"] = request._request_id
            return response

        try:
            duration_ms = (
                (time.monotonic() - request._request_start_time) * 1000
                if hasattr(request, "_request_start_time")
                else None
            )

            # Build comprehensive log data
            log_data: dict[str, Any] = {
                "request_id": getattr(request, "_request_id", None),
                "method": request.method,
                "path": request.path,
                "full_uri": request.build_absolute_uri(),
                "query_string": request.META.get("QUERY_STRING") or "",
                "query_params": dict(request.GET) if request.GET else {},
                "client_ip": get_client_ip(request),
                "referer": request.META.get("HTTP_REFERER", ""),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "content_type": request.content_type or "",
                "content_length": request.META.get("CONTENT_LENGTH"),
                "headers": _sanitize_headers(request.META),
                "response_status": response.status_code,
                "response_content_type": response.get("Content-Type", ""),
            }

            # Authentication / user info
            if hasattr(request, "user") and request.user.is_authenticated:
                log_data["user_id"] = getattr(request.user, "pk", None)
                log_data["username"] = getattr(request.user, "username", str(request.user))
            else:
                log_data["user"] = "anonymous"

            if duration_ms is not None:
                log_data["duration_ms"] = round(duration_ms, 2)

            log_data["message"] = f"{request.method} {request.path} {response.status_code}"
            logger.info("request", **log_data)

        except Exception as e:
            logger.exception("Error in request logging middleware: %s", e)

        # Add request ID to response for client-side correlation
        if hasattr(request, "_request_id"):
            response["X-Request-ID"] = request._request_id

        return response
