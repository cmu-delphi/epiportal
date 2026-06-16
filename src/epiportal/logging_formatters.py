"""
Logging formatters for Elasticsearch-compatible structured output.
"""

import json
import logging
from datetime import datetime, timezone


# Standard LogRecord attributes - excluded from extra when building JSON
_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "exc_info",
        "exc_text",
        "thread",
        "threadName",
        "message",
        "asctime",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """
    Format log records as single-line JSON for Elasticsearch.

    Each log line is a valid JSON object with @timestamp, level, logger, message,
    and any extra fields passed via logger.info(..., extra={...}).
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "@timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields (passed via extra= in log calls)
        for key, value in record.__dict__.items():
            if key not in _RECORD_ATTRS and value is not None:
                log_obj[key] = value

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)
