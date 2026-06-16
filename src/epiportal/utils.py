"""
Shared utilities for epiportal.
"""

from django.conf import settings


def get_client_ip(request) -> str:
    """
    Extract the real client IP from a request, respecting X-Forwarded-For when behind proxies.

    Use this everywhere you need the client IP (logging, rate limiting, etc.) to ensure
    consistent behavior. Requires PROXY_DEPTH to be set correctly for your production
    proxy chain (e.g. 2 for AWS ALB + nginx).
    """
    if not settings.REVERSE_PROXY_DEPTH:
        return request.META.get("REMOTE_ADDR", "")

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        full_proxy_chain = [s.strip() for s in x_forwarded_for.split(",")]
        depth = (
            settings.REVERSE_PROXY_DEPTH
            if settings.REVERSE_PROXY_DEPTH > 0
            else len(full_proxy_chain)
        )
        trusted = full_proxy_chain[-depth:] if depth else full_proxy_chain
        if trusted:
            return trusted[0]

    x_real_ip = request.META.get("HTTP_X_REAL_IP")
    if x_real_ip:
        return x_real_ip.strip()

    return request.META.get("REMOTE_ADDR", "")
