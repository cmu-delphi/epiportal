"""Cache access that degrades to a miss when the cache backend is unavailable.

Django's Redis backend propagates connection errors instead of swallowing them,
so an unreachable Redis turns an ordinary cache lookup into a 500 for whatever
request made it. A cache is an optimization: losing it should cost speed, not
function. These wrappers make a cache failure indistinguishable from a miss.
"""

from delphi_utils import get_structured_logger
from django.core.cache import cache

logger = get_structured_logger("indicatorsets.utils")


def safe_cache_get(key, default=None):
    """Return the cached value for ``key``, or ``default`` on a miss or failure."""
    try:
        value = cache.get(key)
    except Exception as exc:
        # Warning, not exception: during an outage this fires on every request,
        # and a traceback per request buries the logs without adding signal.
        logger.warning(
            "Cache unavailable on read", extra={"cache_key": key, "error": str(exc)}
        )
        return default
    return default if value is None else value


def safe_cache_set(key, value, timeout):
    """Cache ``value`` under ``key``, ignoring cache failures."""
    try:
        cache.set(key, value, timeout)
    except Exception as exc:
        logger.warning(
            "Cache unavailable on write", extra={"cache_key": key, "error": str(exc)}
        )
