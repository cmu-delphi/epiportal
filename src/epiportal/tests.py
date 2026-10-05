from io import StringIO
import json
import logging
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from epiportal.block_middleware import BlockIPRangeMiddleware
from epiportal.logging_formatters import JsonFormatter
from epiportal.middleware import RequestLoggingMiddleware, _sanitize_headers
from epiportal.redaction import redact_secrets, redact_sentry_event
from epiportal.utils import get_client_ip


class GetClientIpTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(REVERSE_PROXY_DEPTH=0)
    def test_uses_remote_addr_when_proxy_depth_zero(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "203.0.113.10"
        request.META["HTTP_X_FORWARDED_FOR"] = "198.51.100.1, 10.0.0.1"
        self.assertEqual(get_client_ip(request), "203.0.113.10")

    @override_settings(REVERSE_PROXY_DEPTH=2)
    def test_uses_trusted_forwarded_chain(self):
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "198.51.100.1, 10.0.0.2, 10.0.0.1"
        self.assertEqual(get_client_ip(request), "10.0.0.2")

    @override_settings(REVERSE_PROXY_DEPTH=2)
    def test_falls_back_to_x_real_ip(self):
        request = self.factory.get("/")
        request.META["HTTP_X_REAL_IP"] = " 192.0.2.44 "
        self.assertEqual(get_client_ip(request), "192.0.2.44")


class InitAdminCommandTests(TestCase):
    def test_creates_superuser_when_missing(self):
        out = StringIO()
        call_command("initadmin", stdout=out)
        self.assertTrue(User.objects.filter(username="admin").exists())
        self.assertIn("Superuser created", out.getvalue())

    def test_skips_when_superuser_exists(self):
        User.objects.create_superuser("admin", "admin@test.com", "existing-pass")
        out = StringIO()
        call_command("initadmin", stdout=out)
        self.assertEqual(User.objects.filter(username="admin").count(), 1)
        self.assertIn("already exists", out.getvalue())


class SanitizeHeadersTests(TestCase):
    def test_redacts_sensitive_headers(self):
        meta = {
            "HTTP_AUTHORIZATION": "Bearer secret",
            "HTTP_COOKIE": "session=abc",
            "HTTP_X_API_KEY": "key123",
            "HTTP_USER_AGENT": "test-agent",
        }
        headers = _sanitize_headers(meta)
        self.assertEqual(headers["authorization"], "[REDACTED]")
        self.assertEqual(headers["cookie"], "[REDACTED]")
        self.assertEqual(headers["x-api-key"], "[REDACTED]")
        self.assertEqual(headers["user-agent"], "test-agent")


class BlockIPRangeMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = BlockIPRangeMiddleware(lambda request: HttpResponse("ok"))

    @override_settings(REVERSE_PROXY_DEPTH=0)
    def test_blocked_ip_returns_403(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "43.173.1.1"
        response = self.middleware(request)
        self.assertEqual(response.status_code, 403)

    @override_settings(REVERSE_PROXY_DEPTH=0)
    def test_allowed_ip_passes_through(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.0.2.1"
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")


class RequestLoggingMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RequestLoggingMiddleware(lambda request: HttpResponse("ok"))

    @patch("epiportal.middleware.logger")
    def test_adds_request_id_header(self, _mock_logger):
        request = self.factory.get("/indicatorsets/")
        self.middleware.process_request(request)
        response = self.middleware.process_response(request, HttpResponse("ok"))
        self.assertIn("X-Request-ID", response)

    @patch("epiportal.middleware.logger")
    def test_logs_anonymous_request(self, mock_logger):
        request = self.factory.get("/indicatorsets/")
        self.middleware.process_request(request)
        response = self.middleware.process_response(request, HttpResponse("ok"))
        self.assertEqual(response.status_code, 200)
        mock_logger.info.assert_called_once()
        self.assertEqual(mock_logger.info.call_args.kwargs["user"], "anonymous")


class JsonFormatterTests(TestCase):
    def test_format_outputs_json_with_extra_fields(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="epiportal.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.request_id = "abc-123"
        payload = json.loads(formatter.format(record))
        self.assertEqual(payload["message"], "hello")
        self.assertEqual(payload["request_id"], "abc-123")
        self.assertIn("@timestamp", payload)


class RedactSecretsTests(TestCase):
    def test_redacts_query_string_keys(self):
        self.assertEqual(
            redact_secrets(
                "500 Server Error for url: https://x/covidcast?a=1&api_key=SECRET&b=2"
            ),
            "500 Server Error for url: https://x/covidcast?a=1&api_key=[REDACTED]&b=2",
        )
        self.assertEqual(
            redact_secrets("https://x/v5/viz/?token=SECRET"),
            "https://x/v5/viz/?token=[REDACTED]",
        )

    def test_redacts_json_rendered_keys(self):
        # how the request middleware's query_params come out of structlog
        self.assertEqual(
            redact_secrets('{"query_params": {"token": ["SECRET"], "a": ["1"]}}'),
            '{"query_params": {"token": ["[REDACTED]"], "a": ["1"]}}',
        )
        self.assertEqual(
            redact_secrets('{"api_key": "SECRET"}'), '{"api_key": "[REDACTED]"}'
        )

    def test_is_case_insensitive(self):
        self.assertEqual(redact_secrets("?API_KEY=SECRET"), "?API_KEY=[REDACTED]")

    def test_leaves_other_text_alone(self):
        text = "geo_value=42003&signal=smoothed_pct_ed_visits_rsv"
        self.assertEqual(redact_secrets(text), text)


class LogRecordRedactionTests(TestCase):
    """Every log record is redacted at creation, whatever handler formats it."""

    def setUp(self):
        # settings disables logging under ``manage.py test``
        logging.disable(logging.NOTSET)
        self.stream = StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.logger = logging.getLogger("epiportal.tests.redaction")
        self.logger.addHandler(self.handler)
        self.logger.propagate = False

    def tearDown(self):
        self.logger.removeHandler(self.handler)
        logging.disable(logging.CRITICAL)

    def test_message_and_args_are_redacted(self):
        self.logger.error("fetching %s", "https://x/covidcast?api_key=SECRET")
        self.logger.error('{"url": "https://x/viz/?token=SECRET"}')

        output = self.stream.getvalue()
        self.assertNotIn("SECRET", output)
        self.assertIn("api_key=[REDACTED]", output)
        self.assertIn("token=[REDACTED]", output)

    def test_formatted_traceback_is_redacted(self):
        import requests

        try:
            raise requests.HTTPError(
                "500 Server Error for url: https://x/covidcast?api_key=SECRET"
            )
        except requests.HTTPError:
            self.logger.exception("Error getting covidcast data")

        output = self.stream.getvalue()
        self.assertIn("HTTPError", output)
        self.assertNotIn("SECRET", output)


class RedactSentryEventTests(TestCase):
    def test_scrubs_strings_and_secret_keys_everywhere_in_the_event(self):
        event = {
            "exception": {
                "values": [
                    {"value": "500 Server Error for url: https://x/?api_key=SECRET"}
                ]
            },
            "breadcrumbs": {
                "values": [{"data": {"url": "https://x/viz/?token=SECRET&a=1"}}]
            },
            "request": {"query_string": "token=SECRET", "data": {"api_key": "SECRET"}},
            "spans": [{"data": {"http.query": "a=1&api_key=SECRET"}}],
            "extra": {"count": 3},
        }

        scrubbed = redact_sentry_event(event, {})

        self.assertNotIn("SECRET", json.dumps(scrubbed))
        self.assertEqual(scrubbed["request"]["data"]["api_key"], "[REDACTED]")
        self.assertEqual(scrubbed["extra"]["count"], 3)
        self.assertEqual(
            scrubbed["breadcrumbs"]["values"][0]["data"]["url"],
            "https://x/viz/?token=[REDACTED]&a=1",
        )


class SettingsSecurityDefaultsTests(TestCase):
    def _reloaded_settings(self, env, attribute, unset=()):
        """Return ``attribute`` of settings reloaded under ``env`` minus ``unset``."""
        import importlib
        import os

        import epiportal.settings as settings_module

        try:
            with patch.dict(os.environ, env):
                for name in unset:
                    os.environ.pop(name, None)
                importlib.reload(settings_module)
                return getattr(settings_module, attribute)
        finally:
            importlib.reload(settings_module)

    def test_debug_is_off_unless_switched_on(self):
        self.assertFalse(self._reloaded_settings({}, "DEBUG", unset=["DEBUG"]))
        self.assertTrue(self._reloaded_settings({"DEBUG": "True"}, "DEBUG"))

    def test_sentry_gets_the_redaction_hooks(self):
        with patch("sentry_sdk.init") as mock_init:
            self._reloaded_settings({"SENTRY_DSN": "https://k@sentry.example/1"}, "DEBUG")

        kwargs = mock_init.call_args.kwargs
        self.assertIs(kwargs["before_send"], redact_sentry_event)
        self.assertIs(kwargs["before_send_transaction"], redact_sentry_event)
