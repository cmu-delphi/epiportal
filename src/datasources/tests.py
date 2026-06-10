from django.test import TestCase
from tablib import Dataset

from datasources.models import OtherEndpointSourceSubdivision, SourceSubdivision
from datasources.resources import (
    OtherEndpointSourceSubdivisionResource,
    SourceSubdivisionResource,
    strip_all_string_values,
)


class SourceSubdivisionModelTests(TestCase):
    def test_str_returns_name(self):
        source = SourceSubdivision.objects.create(name="hospital")
        self.assertEqual(str(source), "hospital")

    def test_get_display_name_prefers_display_name(self):
        source = SourceSubdivision.objects.create(
            name="hosp_api",
            display_name="Hospital admissions",
        )
        self.assertEqual(source.get_display_name(), "Hospital admissions")

    def test_get_display_name_falls_back_to_name(self):
        source = SourceSubdivision.objects.create(name="claims")
        self.assertEqual(source.get_display_name(), "claims")

    def test_name_must_be_unique(self):
        SourceSubdivision.objects.create(name="duplicate")
        with self.assertRaises(Exception):
            SourceSubdivision.objects.create(name="duplicate")


class OtherEndpointSourceSubdivisionTests(TestCase):
    def test_proxy_uses_same_table(self):
        SourceSubdivision.objects.create(
            name="other_src",
            source_type="other_endpoint",
        )
        proxy = OtherEndpointSourceSubdivision.objects.get(name="other_src")
        self.assertEqual(proxy.source_type, "other_endpoint")
        self.assertIsInstance(proxy, OtherEndpointSourceSubdivision)


class StripAllStringValuesTests(TestCase):
    def test_strips_whitespace_from_string_fields(self):
        row = {"name": "  hospital  ", "count": 1, "note": None}
        strip_all_string_values(row)
        self.assertEqual(row["name"], "hospital")
        self.assertEqual(row["count"], 1)
        self.assertIsNone(row["note"])


class SourceSubdivisionResourceTests(TestCase):
    def test_import_creates_and_updates_source(self):
        resource = SourceSubdivisionResource()
        dataset = Dataset(headers=["Source Subdivision", "External Name", "Display Name"])
        dataset.append(["hospital", "Hospital API", "Hospital admissions"])

        resource.import_data(dataset, dry_run=False)

        source = SourceSubdivision.objects.get(name="hospital")
        self.assertEqual(source.display_name, "Hospital API")
        self.assertEqual(source.external_name, "Hospital admissions")

    def test_after_import_deletes_rows_not_in_spreadsheet(self):
        SourceSubdivision.objects.create(name="keep")
        SourceSubdivision.objects.create(name="remove")

        resource = SourceSubdivisionResource()
        dataset = Dataset(headers=["Source Subdivision"])
        dataset.append(["keep"])

        resource.import_data(dataset, dry_run=False)

        self.assertTrue(SourceSubdivision.objects.filter(name="keep").exists())
        self.assertFalse(SourceSubdivision.objects.filter(name="remove").exists())


class OtherEndpointSourceSubdivisionResourceTests(TestCase):
    def test_import_sets_other_endpoint_source_type(self):
        resource = OtherEndpointSourceSubdivisionResource()
        dataset = Dataset(headers=["Source Subdivision", "External Name"])
        dataset.append(["  fluview_src  ", "FluView"])

        resource.import_data(dataset, dry_run=False)

        source = OtherEndpointSourceSubdivision.objects.get(name="fluview_src")
        self.assertEqual(source.source_type, "other_endpoint")
        self.assertEqual(source.display_name, "FluView")
