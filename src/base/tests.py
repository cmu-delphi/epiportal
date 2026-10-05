import json
from import_export import fields
from tablib import Dataset
from unittest.mock import MagicMock, patch

import requests
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpResponseForbidden
from django.test import RequestFactory, TestCase, override_settings

from base.models import (
    GeographicScope,
    Geography,
    GeographyUnit,
    Pathogen,
    SeverityPyramidRung,
)
from base.resources import CustomModelResource, get_geographic_mapping_by_name
from base.views import NotFoundErrorView, epidata


class PathogenModelTests(TestCase):
    def test_str_uses_display_name_when_set(self):
        pathogen = Pathogen.objects.create(
            name="flu",
            display_name="Influenza",
            used_in="indicators",
        )
        self.assertEqual(str(pathogen), "Influenza")

    def test_str_falls_back_to_name(self):
        pathogen = Pathogen.objects.create(name="rsv", used_in="indicators")
        self.assertEqual(str(pathogen), "rsv")

    def test_unique_name_per_used_in(self):
        Pathogen.objects.create(name="covid", used_in="indicators")
        with self.assertRaises(Exception):
            Pathogen.objects.create(name="covid", used_in="indicators")


class GeographicMappingTests(TestCase):
    def test_get_geographic_mapping_by_key(self):
        key, mapping = get_geographic_mapping_by_name("state")
        self.assertEqual(key, "state")
        self.assertEqual(mapping["short_name"], "ADM 1")

    def test_get_geographic_mapping_by_display_name(self):
        result = get_geographic_mapping_by_name("State/ADM 1")
        self.assertEqual(result[0], "state")

    def test_get_geographic_mapping_unknown_returns_none(self):
        self.assertIsNone(get_geographic_mapping_by_name("not-a-real-granularity"))


class PathogenResource(CustomModelResource):
    name = fields.Field(attribute="name", column_name="name")
    used_in = fields.Field(attribute="used_in", column_name="used_in")

    class Meta:
        model = Pathogen
        import_id_fields = ("name",)
        fields = ("name", "used_in")


class CustomModelResourceTests(TestCase):
    def test_after_import_deletes_rows_not_in_import(self):
        Pathogen.objects.create(name="keep", used_in="indicators")
        Pathogen.objects.create(name="remove", used_in="indicators")

        resource = PathogenResource()
        dataset = Dataset(headers=["name", "used_in"])
        dataset.append(["keep", "indicators"])

        resource.import_data(dataset, dry_run=False)

        self.assertTrue(Pathogen.objects.filter(name="keep").exists())
        self.assertFalse(Pathogen.objects.filter(name="remove").exists())

    def test_imported_rows_pks_reset_per_import_instance(self):
        resource = PathogenResource()
        resource.before_import(None, dry_run=True)
        self.assertEqual(resource.imported_rows_pks, [])


class EpidataProxyViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_disallowed_endpoint_returns_403(self):
        request = self.factory.get("/epidata/forbidden/")
        response = epidata(request, endpoint="forbidden")
        self.assertEqual(response.status_code, 403)
        self.assertIsInstance(response, HttpResponseForbidden)

    @override_settings(EPIDATA_API_KEY="server-key")
    @patch("base.views.requests.get")
    def test_allowed_endpoint_forwards_to_epidata(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"epidata": [{"x": 1}], "result": 1}
        mock_get.return_value = mock_response

        request = self.factory.get("/epidata/covidcast/geo_coverage/", {"geo": "state:pa"})
        response = epidata(request, endpoint="covidcast/geo_coverage")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["result"], 1)
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        self.assertEqual(call_kwargs["timeout"], 10)
        self.assertNotIn("api_key", call_kwargs["params"])
        self.assertEqual(call_kwargs["auth"], ("epidata", "server-key"))

    @override_settings(EPIDATA_API_KEY="server-key")
    @patch("base.views.requests.get")
    def test_caller_supplied_api_key_is_not_forwarded(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"result": 1})

        request = self.factory.get(
            "/epidata/covidcast/meta/", {"api_key": "theirs", "a": "1"}
        )
        epidata(request, endpoint="covidcast/meta")

        self.assertEqual(mock_get.call_args.kwargs["params"], {"a": "1"})
        self.assertEqual(mock_get.call_args.kwargs["auth"], ("epidata", "server-key"))

    @patch("base.views.requests.get", side_effect=requests.Timeout)
    def test_upstream_failure_returns_502(self, _mock_get):
        request = self.factory.get("/epidata/covidcast/meta/")
        response = epidata(request, endpoint="covidcast/meta")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(json.loads(response.content)["result"], -1)


class ImportDataUtilityTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/admin/")
        self.request.session = "session"
        messages = FallbackStorage(self.request)
        self.request._messages = messages
        self.admin = MagicMock()

    @patch("base.utils.requests.get", side_effect=requests.Timeout)
    def test_import_data_timeout_shows_error_message(self, _mock_get):
        from base.utils import import_data

        response = import_data(
            self.admin, self.request, PathogenResource, "https://example.com/sheet.csv"
        )
        self.assertEqual(response.status_code, 302)
        self.admin.message_user.assert_called()
        self.assertIn("did not respond in time", self.admin.message_user.call_args[0][1])


class ErrorPageViewTests(TestCase):
    def test_not_found_error_view_renders_template(self):
        request = RequestFactory().get("/missing/")
        response = NotFoundErrorView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.template_name, ["http_errors/404.html"])


class GeographyModelTests(TestCase):
    def test_str_uses_display_name(self):
        geography = Geography.objects.create(
            name="state",
            display_name="State",
            used_in="indicators",
        )
        self.assertEqual(str(geography), "State")

    def test_str_falls_back_to_name(self):
        geography = Geography.objects.create(name="county", used_in="indicators")
        self.assertEqual(str(geography), "county")


class GeographicScopeModelTests(TestCase):
    def test_str_returns_name(self):
        scope = GeographicScope.objects.create(name="US National", used_in="indicators")
        self.assertEqual(str(scope), "US National")


class SeverityPyramidRungModelTests(TestCase):
    def test_str_uses_display_name(self):
        rung = SeverityPyramidRung.objects.create(
            name="hospital",
            display_name="Hospital admissions",
            used_in="indicators",
        )
        self.assertEqual(str(rung), "Hospital admissions")


class GeographyUnitModelTests(TestCase):
    def test_str_uses_display_name(self):
        geo_level = Geography.objects.create(
            name="state",
            display_name="State",
            used_in="indicators",
        )
        unit = GeographyUnit.objects.create(
            geo_id="pa",
            display_name="Pennsylvania",
            geo_level=geo_level,
        )
        self.assertEqual(str(unit), "Pennsylvania")


class TemplateTagTests(TestCase):
    def test_split_filter_splits_string(self):
        from base.templatetags.split_filter import split

        self.assertEqual(split("a,b,c"), ["a", "b", "c"])
        self.assertEqual(split("a|b", "|"), ["a", "b"])
        self.assertEqual(split(None), [])

    def test_dict_get_returns_value_or_empty_string(self):
        from base.templatetags.dict_get import dict_get

        self.assertEqual(dict_get({"key": "value"}, "key"), "value")
        self.assertEqual(dict_get({"key": "value"}, "missing"), "")
        self.assertEqual(dict_get(None, "key"), "")


class ImportDataSuccessTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/admin/")
        self.request.session = "session"
        self.request._messages = FallbackStorage(self.request)
        self.admin = MagicMock()

    @patch("base.utils.requests.get")
    def test_import_data_success_reports_counts(self, mock_get):
        from base.utils import import_data

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b"name,used_in\nkeep,indicators\n"
        mock_get.return_value = mock_response

        response = import_data(
            self.admin, self.request, PathogenResource, "https://example.com/sheet.csv"
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Pathogen.objects.filter(name="keep").exists())
        self.admin.message_user.assert_called()
        self.assertIn("Import finished", self.admin.message_user.call_args[0][1])

    @patch("base.utils.requests.get")
    def test_import_data_http_error_shows_status(self, mock_get):
        from base.utils import import_data

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError(
            response=mock_response
        )

        response = import_data(
            self.admin, self.request, PathogenResource, "https://example.com/sheet.csv"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("HTTP 404", self.admin.message_user.call_args[0][1])


class DownloadSourceFileTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/admin/")
        self.request.session = "session"
        self.request._messages = FallbackStorage(self.request)
        self.admin = MagicMock()

    @patch("base.utils.requests.get")
    def test_download_source_file_returns_attachment(self, mock_get):
        from base.utils import download_source_file

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b"csv,data\n"
        mock_get.return_value = mock_response

        response = download_source_file(
            self.admin, self.request, "https://example.com/data.csv", "data.csv"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="data.csv"')

    @patch("base.utils.requests.get", side_effect=requests.Timeout)
    def test_download_source_file_timeout_redirects(self, _mock_get):
        from base.utils import download_source_file

        response = download_source_file(
            self.admin, self.request, "https://example.com/data.csv", "data.csv"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("did not respond in time", self.admin.message_user.call_args[0][1])


class EpidataNon200ResponseTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("base.views.requests.get")
    def test_non_200_upstream_status_is_passthrough(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"result": -1, "message": "not found"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        request = self.factory.get("/epidata/covidcast/meta/")
        response = epidata(request, endpoint="covidcast/meta")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.content)["result"], -1)


class BannerTests(TestCase):
    """Site-wide banners, managed in admin, shown on every page layout."""

    def _banner(self, **fields):
        from base.models import Banner

        defaults = {"message": "Epidata v5 is here.", "is_active": True}
        return Banner.objects.create(**{**defaults, **fields})

    def _current(self):
        from base.models import Banner

        return list(Banner.objects.current())

    def test_current_includes_an_active_open_ended_banner(self):
        banner = self._banner()
        self.assertEqual(self._current(), [banner])

    def test_current_excludes_an_inactive_banner(self):
        self._banner(is_active=False)
        self.assertEqual(self._current(), [])

    def test_current_respects_the_date_window(self):
        from datetime import timedelta

        from django.utils import timezone

        now = timezone.now()
        running = self._banner(
            message="running",
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1),
        )
        self._banner(message="not yet", starts_at=now + timedelta(hours=1))
        self._banner(message="over", ends_at=now - timedelta(hours=1))
        self.assertEqual(self._current(), [running])

    def test_current_lists_the_newest_first(self):
        older = self._banner(message="older")
        newer = self._banner(message="newer")
        self.assertEqual(self._current(), [newer, older])

    def test_dismiss_key_changes_when_the_banner_is_edited(self):
        banner = self._banner()
        key = banner.dismiss_key
        self.assertIn(str(banner.pk), key)

        banner.message = "Epidata v5 is here, and v4 retires soon."
        banner.save()

        self.assertNotEqual(banner.dismiss_key, key)

    def test_indicator_sets_page_shows_the_banner(self):
        from django.urls import reverse

        banner = self._banner(message='Read the <a href="https://example.org/v5">v5 guide</a>.')
        response = self.client.get(reverse("indicatorsets"))
        # staff-written HTML is rendered as written, so links work
        self.assertContains(response, '<a href="https://example.org/v5">v5 guide</a>', html=False)
        self.assertContains(response, f'data-banner-key="{banner.dismiss_key}"')

    def test_express_view_shows_the_banner(self):
        from django.urls import reverse

        self._banner(message="Express view notice")
        response = self.client.get(reverse("alternative_interface"))
        self.assertContains(response, "Express view notice")

    def test_no_banner_markup_without_a_current_banner(self):
        from django.urls import reverse

        self._banner(is_active=False, message="switched off")
        response = self.client.get(reverse("indicatorsets"))
        self.assertNotContains(response, "switched off")
        self.assertNotContains(response, "site-banner")

    def test_banner_style_sets_its_alert_colour(self):
        from django.urls import reverse

        self._banner(style="warning")
        response = self.client.get(reverse("indicatorsets"))
        self.assertContains(response, "alert-warning")

    def test_admin_lists_and_adds_banners(self):
        from django.contrib.auth.models import User
        from django.urls import reverse

        self._banner(message="Listed in admin")
        self.client.force_login(
            User.objects.create_superuser("admin", "admin@example.org", "pw")
        )

        changelist = self.client.get(reverse("admin:base_banner_changelist"))
        add_form = self.client.get(reverse("admin:base_banner_add"))

        self.assertContains(changelist, "Listed in admin")
        self.assertEqual(add_form.status_code, 200)
