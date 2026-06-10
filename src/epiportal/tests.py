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
