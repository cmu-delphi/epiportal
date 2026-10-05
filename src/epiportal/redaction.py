"""Keep Epidata keys out of logs and Sentry.

Server-side requests send the server's key as an auth header, but v5 still
takes ``token`` in the query string, and users pass their own keys to our
download proxy. A request error's message carries its full URL, so any of
these can surface wherever an exception or a request is logged. Redacting at
the edges -- every log record, every Sentry event -- covers call sites present
and future without each having to remember.
"""

import logging
import re

REDACTED = "[REDACTED]"
SECRET_NAMES = ("api_key", "token")

# ``api_key=...`` in a URL or query string, up to the next separator.
_QUERY_RE = re.compile(r"(?i)\b((?:api_key|token)=)[^&\s\"'<>\\]+")
# ``"api_key": "..."`` or ``"token": ["..."]`` in JSON-rendered log lines,
# which is how structlog writes the request middleware's query_params.
_JSON_RE = re.compile(r'(?i)("(?:api_key|token)"\s*:\s*\[?\s*")[^"]*(")')


def redact_secrets(text):
    """Return ``text`` with every Epidata key value replaced by ``[REDACTED]``."""
    text = _QUERY_RE.sub(rf"\g<1>{REDACTED}", text)
    return _JSON_RE.sub(rf"\g<1>{REDACTED}\g<2>", text)


def _redact(value):
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {
            key: (
                REDACTED
                if isinstance(key, str) and key.lower() in SECRET_NAMES
                else _redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return value


def redact_sentry_event(event, hint):
    """Sentry ``before_send``/``before_send_transaction`` hook.

    Walks the whole event -- exception messages, breadcrumbs, request data,
    span data -- since a URL can turn up in any of them.
    """
    return _redact(event)


def install_log_redaction():
    """Redact every log record as it is created, whichever handler formats it.

    Wraps the record factory rather than adding a handler filter: handlers come
    from Django's LOGGING, from ``delphi_utils``' ``basicConfig`` and from
    gunicorn, and a filter on one would miss the others. The traceback is
    formatted and redacted here too; formatters reuse a record's ``exc_text``
    rather than formatting ``exc_info`` again.
    """
    original_factory = logging.getLogRecordFactory()
    if getattr(original_factory, "redacts_secrets", False):
        return

    def factory(*args, **kwargs):
        record = original_factory(*args, **kwargs)
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            record.args = _redact(record.args)
        if record.exc_info and record.exc_info[0] is not None:
            record.exc_text = redact_secrets(
                logging.Formatter().formatException(record.exc_info)
            )
        return record

    factory.redacts_secrets = True
    logging.setLogRecordFactory(factory)
