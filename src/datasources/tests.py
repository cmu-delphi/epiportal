from django.test import TestCase
from tablib import Dataset

from datasources.models import SourceSubdivision
from datasources.resources import SourceSubdivisionResource, strip_all_string_values


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


class StripAllStringValuesTests(TestCase):
    def test_strips_whitespace_from_string_fields(self):
        row = {"name": "  hospital  ", "count": 1, "note": None}
        strip_all_string_values(row)
        self.assertEqual(row["name"], "hospital")
        self.assertEqual(row["count"], 1)
        self.assertIsNone(row["note"])


SOURCES_HEADER = (
    "db_source,source,name,external_name,kind,public,original_data_provider,"
    "description,reference_indicator,license,dua,documentation_link"
).split(",")


def sources_dataset(*rows: dict) -> Dataset:
    dataset = Dataset(headers=SOURCES_HEADER)
    for row in rows:
        dataset.append([row.get(column, "") for column in SOURCES_HEADER])
    return dataset


class SourceSubdivisionResourceTests(TestCase):
    def test_maps_columns(self):
        resource = SourceSubdivisionResource()
        dataset = sources_dataset(
            {
                "source": "chng",
                "db_source": "chng",
                "name": "Change Healthcare",
                "external_name": "Change HC",
                "description": "Claims",
                "license": "CC BY",
                "dua": "Yes",
            }
        )

        resource.import_data(dataset, dry_run=False, raise_errors=True)

        source = SourceSubdivision.objects.get(name="chng")
        self.assertEqual(source.datasource_name, "chng")
        self.assertEqual(source.display_name, "Change Healthcare")
        self.assertEqual(source.external_name, "Change HC")
        self.assertEqual(source.description, "Claims")
        self.assertEqual(source.license, "CC BY")
        self.assertEqual(source.dua, "Yes")

    def test_strips_whitespace(self):
        resource = SourceSubdivisionResource()
        resource.import_data(
            sources_dataset({"source": "  fluview  ", "name": " FluView "}),
            dry_run=False,
            raise_errors=True,
        )
        self.assertEqual(
            SourceSubdivision.objects.get(name="fluview").display_name, "FluView"
        )

    def test_empty_source_is_skipped(self):
        resource = SourceSubdivisionResource()
        resource.import_data(
            sources_dataset({"source": "", "name": "No id"}),
            dry_run=False,
            raise_errors=True,
        )
        self.assertFalse(SourceSubdivision.objects.exists())

    def test_duplicate_source_first_row_wins(self):
        resource = SourceSubdivisionResource()
        dataset = sources_dataset(
            {"source": "ght", "name": "Google Health Trends"},
            {"source": "ght", "name": ""},
        )

        resource.import_data(dataset, dry_run=False, raise_errors=True)

        self.assertEqual(SourceSubdivision.objects.filter(name="ght").count(), 1)
        self.assertEqual(
            SourceSubdivision.objects.get(name="ght").display_name,
            "Google Health Trends",
        )
        self.assertIn("ght", " ".join(resource.warnings))

    def test_source_missing_from_sheet_is_deleted(self):
        SourceSubdivision.objects.create(name="old")
        resource = SourceSubdivisionResource()

        resource.import_data(
            sources_dataset({"source": "new"}), dry_run=False, raise_errors=True
        )

        self.assertFalse(SourceSubdivision.objects.filter(name="old").exists())
        self.assertTrue(SourceSubdivision.objects.filter(name="new").exists())

    def test_resource_columns_exist_in_sheet_header(self):
        resource = SourceSubdivisionResource()
        for field in resource.get_import_fields():
            self.assertIn(field.column_name, SOURCES_HEADER)
