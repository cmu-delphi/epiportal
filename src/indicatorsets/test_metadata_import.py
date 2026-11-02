from unittest.mock import MagicMock, patch

import requests
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from tablib import Dataset

from alternative_interface.models import ExpressViewIndicator
from datasources.admin import SourceSubdivisionAdmin
from datasources.models import SourceSubdivision
from datasources.tests import sources_dataset
from indicators.models import Indicator
from indicators.resources import IndicatorResource
from indicators.test_resources import indicators_dataset
from indicatorsets.metadata_import import (
    MetadataImportError,
    TabResult,
    import_metadata_from_admin,
    load_dataset,
    run_metadata_import,
)
from indicatorsets.models import IndicatorSet
from indicatorsets.test_resources import sets_dataset

URLS = settings.SPREADSHEET_URLS
DASHBOARD_HEADER = [
    "Menu Item",
    "Indicator Set",
    "Indicator Source",
    "Indicator Name",
    "Pathogen",
    "Indicator API name",
    "text for display legend",
    "tie together for scaling",
    "Display Order",
]
PREAMBLE = '"Dashboard config\nsecond line",,,,,,,,\n'


def dashboard_csv(*rows: dict) -> str:
    dataset = Dataset(headers=DASHBOARD_HEADER)
    for row in rows:
        dataset.append([row.get(column, "") for column in DASHBOARD_HEADER])
    return PREAMBLE + dataset.export("csv")


def dashboard_row(**overrides) -> dict:
    return {
        "Menu Item": "COVID-19",
        "Indicator Source": "chng",
        "Indicator Name": "smoothed_cli",
        "text for display legend": "CLI",
        "Display Order": "1",
        **overrides,
    }


def sheet_csvs(**overrides: str) -> dict[str, str]:
    csvs = {
        URLS["sources"]: sources_dataset({"source": "chng", "db_source": "chng"}).export("csv"),
        URLS["indicator_sets"]: sets_dataset({"indicator_set": "Delphi set"}).export("csv"),
        URLS["indicators"]: indicators_dataset(
            {"source": "chng", "indicator": "smoothed_cli", "indicator_set": "Delphi set"}
        ).export("csv"),
        URLS["express_view_indicators"]: dashboard_csv(dashboard_row()),
    }
    csvs.update({URLS[key]: value for key, value in overrides.items()})
    return csvs


def fake_fetch(csvs: dict[str, str]):
    fetched = []

    def fetch(url: str) -> str:
        fetched.append(url)
        value = csvs[url]
        if isinstance(value, Exception):
            raise value
        return value

    fetch.fetched = fetched
    return fetch


class MetadataImportTests(TestCase):
    def test_imports_tabs_in_order(self):
        results = run_metadata_import(fake_fetch(sheet_csvs()))

        self.assertEqual(
            [r.tab for r in results],
            ["sources", "indicator_sets", "indicators", "express_view_indicators"],
        )
        self.assertEqual([r.new for r in results], [1, 1, 1, 1])
        self.assertTrue(SourceSubdivision.objects.filter(name="chng").exists())
        self.assertTrue(IndicatorSet.objects.filter(name="Delphi set").exists())
        indicator = Indicator.objects.get(name="smoothed_cli")
        self.assertEqual(indicator.source.name, "chng")
        self.assertEqual(
            ExpressViewIndicator.objects.get().indicator_id, indicator.id
        )

    def test_download_failure_changes_nothing(self):
        existing = SourceSubdivision.objects.create(name="old_source")
        fetch = fake_fetch(sheet_csvs(indicators=requests.HTTPError("503")))

        with self.assertRaises(MetadataImportError):
            run_metadata_import(fetch)

        self.assertIn(URLS["sources"], fetch.fetched)
        self.assertEqual(list(SourceSubdivision.objects.all()), [existing])
        self.assertFalse(IndicatorSet.objects.exists())

    def test_row_error_rolls_back_everything(self):
        existing = SourceSubdivision.objects.create(name="old_source")
        failed = MagicMock()
        failed.has_errors.return_value = True
        failed.base_errors = []
        failed.row_errors.return_value = []

        with patch.object(IndicatorResource, "import_data", return_value=failed):
            with self.assertRaises(MetadataImportError):
                run_metadata_import(fake_fetch(sheet_csvs()))

        self.assertEqual(list(SourceSubdivision.objects.all()), [existing])
        self.assertFalse(IndicatorSet.objects.exists())
        self.assertFalse(Indicator.objects.exists())
        self.assertFalse(ExpressViewIndicator.objects.exists())

    def test_dashboard_preamble_skipped(self):
        dataset = load_dataset(
            '"Config text\nmore",,\nMenu Item,Indicator Set\nCOVID-19,X\n',
            "Menu Item",
        )

        self.assertEqual(dataset.headers, ["Menu Item", "Indicator Set"])
        self.assertEqual(dataset[0], ("COVID-19", "X"))

    def test_load_dataset_without_header_marker_keeps_all_rows(self):
        dataset = load_dataset("a,b\n1,2\n")

        self.assertEqual(dataset.headers, ["a", "b"])

    def test_dashboard_rows_missing_from_sheet_are_deleted(self):
        run_metadata_import(fake_fetch(sheet_csvs()))
        self.assertEqual(ExpressViewIndicator.objects.count(), 1)

        results = run_metadata_import(
            fake_fetch(sheet_csvs(express_view_indicators=dashboard_csv()))
        )

        self.assertEqual(ExpressViewIndicator.objects.count(), 0)
        self.assertEqual(results[-1].deleted, 1)

    def test_dashboard_row_for_unknown_indicator_is_dropped(self):
        results = run_metadata_import(
            fake_fetch(
                sheet_csvs(
                    express_view_indicators=dashboard_csv(
                        dashboard_row(),
                        dashboard_row(**{"Indicator Name": "missing"}),
                    )
                )
            )
        )

        self.assertEqual(ExpressViewIndicator.objects.count(), 1)
        self.assertEqual(results[-1].new, 1)


class ImportMetadataFromAdminTests(TestCase):
    def post(self):
        request = RequestFactory().post("/admin/")
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_admin_view_reports_counts_and_warnings(self):
        results = [
            TabResult("sources", new=1),
            TabResult("indicator_sets", updated=2, warnings=["set warning"]),
        ]
        request = self.post()
        model_admin = SourceSubdivisionAdmin(SourceSubdivision, admin.site)

        with patch(
            "indicatorsets.metadata_import.run_metadata_import", return_value=results
        ):
            response = import_metadata_from_admin(model_admin, request)

        self.assertEqual(response.status_code, 302)
        stored = list(request._messages)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].level, messages.INFO)
        self.assertIn("indicator_sets:", stored[0].message)
        self.assertIn("set warning", stored[0].message)

    def test_admin_view_reports_failure_as_error(self):
        request = self.post()
        model_admin = SourceSubdivisionAdmin(SourceSubdivision, admin.site)

        with patch(
            "indicatorsets.metadata_import.run_metadata_import",
            side_effect=MetadataImportError("boom"),
        ):
            import_metadata_from_admin(model_admin, request)

        stored = list(request._messages)
        self.assertEqual(stored[0].level, messages.ERROR)
        self.assertIn("boom", stored[0].message)
