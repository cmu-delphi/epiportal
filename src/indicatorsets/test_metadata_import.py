from unittest.mock import MagicMock, patch

import requests
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from tablib import Dataset

from alternative_interface.models import ExpressViewIndicator
from alternative_interface.resources import ExpressViewIndicatorResource
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
from indicatorsets.metadata_import import (
    run_metadata_import as real_run_metadata_import,
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
        self.assertEqual(
            results[-1].warnings,
            ["Skipped dashboard row 'COVID-19': indicator chng/missing not found"],
        )

    def test_dashboard_placeholder_rows_are_dropped_quietly(self):
        results = run_metadata_import(
            fake_fetch(
                sheet_csvs(
                    express_view_indicators=dashboard_csv(
                        dashboard_row(),
                        dashboard_row(**{"Indicator Source": "", "Indicator Name": ""}),
                        dashboard_row(**{"Indicator Source": "", "Indicator Name": "soon"}),
                        dashboard_row(**{"Indicator Name": ""}),
                    )
                )
            )
        )

        self.assertEqual(ExpressViewIndicator.objects.count(), 1)
        self.assertEqual(results[-1].warnings, [])

    def test_missing_indicators_column_rolls_back_earlier_tabs(self):
        existing = SourceSubdivision.objects.create(name="old_source")
        indicators = indicators_dataset(
            {"source": "chng", "indicator": "smoothed_cli", "indicator_set": "Delphi set"}
        )
        del indicators["show_in_epiportal"]

        with self.assertRaises(MetadataImportError) as caught:
            run_metadata_import(
                fake_fetch(sheet_csvs(indicators=indicators.export("csv")))
            )

        self.assertIn("indicators", str(caught.exception))
        self.assertIn("show_in_epiportal", str(caught.exception))
        self.assertEqual(list(SourceSubdivision.objects.all()), [existing])
        self.assertFalse(IndicatorSet.objects.exists())
        self.assertFalse(Indicator.objects.exists())
        self.assertFalse(ExpressViewIndicator.objects.exists())

    def test_missing_dashboard_column_aborts_and_keeps_dashboard(self):
        run_metadata_import(fake_fetch(sheet_csvs()))
        csv_text = dashboard_csv(dashboard_row()).replace(
            "Indicator Source", "Source"
        )

        with self.assertRaises(MetadataImportError) as caught:
            run_metadata_import(
                fake_fetch(sheet_csvs(express_view_indicators=csv_text))
            )

        self.assertIn("Indicator Source", str(caught.exception))
        self.assertEqual(ExpressViewIndicator.objects.count(), 1)

    def test_html_instead_of_csv_changes_nothing(self):
        existing = SourceSubdivision.objects.create(name="old_source")
        # The second line is wider than the first, which tablib rejects.
        html = (
            "<!DOCTYPE html><html><head>\n"
            '<meta name="viewport" content="width=device-width, initial-scale=1, '
            'maximum-scale=1"><title>Sign in</title></head>\n'
            "<body><p>Sign in</p></body></html>\n"
        )

        with self.assertRaises(MetadataImportError) as caught:
            run_metadata_import(fake_fetch(sheet_csvs(indicator_sets=html)))

        self.assertIn("Could not read indicator_sets as CSV", str(caught.exception))
        self.assertEqual(list(SourceSubdivision.objects.all()), [existing])
        self.assertFalse(IndicatorSet.objects.exists())

    def test_undecodable_download_changes_nothing(self):
        existing = SourceSubdivision.objects.create(name="old_source")
        error = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

        with self.assertRaises(MetadataImportError) as caught:
            run_metadata_import(fake_fetch(sheet_csvs(sources=error)))

        self.assertIn("Could not read sources as CSV", str(caught.exception))
        self.assertEqual(list(SourceSubdivision.objects.all()), [existing])

    def test_validation_error_rolls_back_everything(self):
        existing = SourceSubdivision.objects.create(name="old_source")
        invalid = MagicMock()
        invalid.has_errors.return_value = False
        invalid.has_validation_errors.return_value = True
        invalid.base_errors = []
        invalid.row_errors.return_value = []
        invalid.invalid_rows = [MagicMock(number=3, error=ValidationError("bad"))]

        with patch.object(IndicatorResource, "import_data", return_value=invalid):
            with self.assertRaises(MetadataImportError) as caught:
                run_metadata_import(fake_fetch(sheet_csvs()))

        self.assertIn("Line number: 3", str(caught.exception))
        self.assertEqual(list(SourceSubdivision.objects.all()), [existing])
        self.assertFalse(IndicatorSet.objects.exists())

    def test_dashboard_validation_error_is_skipped_with_warning(self):
        with patch.object(
            ExpressViewIndicatorResource,
            "validate_instance",
            side_effect=ValidationError("bad order"),
        ):
            results = run_metadata_import(fake_fetch(sheet_csvs()))

        self.assertFalse(ExpressViewIndicator.objects.exists())
        self.assertEqual(len(results[-1].warnings), 1)
        self.assertIn("bad order", results[-1].warnings[0])

    def test_warnings_are_logged_in_full(self):
        sets = sets_dataset(
            {"indicator_set": "Delphi set"},
            *(
                row
                for i in range(25)
                for row in (
                    {"indicator_set": f"Set {i}", "pathogen": "RSV"},
                    {"indicator_set": f"Set {i}", "pathogen": "Flu"},
                )
            ),
        )

        with patch("indicatorsets.metadata_import.logger") as mock_logger:
            run_metadata_import(
                fake_fetch(sheet_csvs(indicator_sets=sets.export("csv")))
            )

        mock_logger.warning.assert_called_once()
        extra = mock_logger.warning.call_args.kwargs["extra"]
        self.assertEqual(extra["tab"], "indicator_sets")
        self.assertEqual(len(extra["warnings"]), 25)


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
        stored = [(m.level, m.message) for m in request._messages]
        self.assertEqual(
            stored,
            [
                (messages.INFO, "sources: 1 new, 0 updated, 0 skipped, 0 deleted"),
                (
                    messages.INFO,
                    "indicator_sets: 0 new, 2 updated, 0 skipped, 0 deleted",
                ),
                (messages.WARNING, "indicator_sets: set warning"),
            ],
        )

    def test_admin_view_shows_dropped_data_before_duplicates(self):
        sets = sets_dataset(
            {"indicator_set": "Delphi set"},
            *(
                row
                for i in range(25)
                for row in (
                    {"indicator_set": f"Set {i}", "pathogen": "RSV"},
                    {"indicator_set": f"Set {i}", "pathogen": "Flu"},
                )
            ),
        )
        indicators = indicators_dataset(
            {"source": "chng", "indicator": "smoothed_cli", "indicator_set": "Delphi set"},
            {"source": "chng", "indicator": "typo_sig", "indicator_set": "Delphy set"},
        )
        fetch = fake_fetch(
            sheet_csvs(
                indicator_sets=sets.export("csv"), indicators=indicators.export("csv")
            )
        )
        request = self.post()
        model_admin = SourceSubdivisionAdmin(SourceSubdivision, admin.site)

        with patch(
            "indicatorsets.metadata_import.run_metadata_import",
            side_effect=lambda: real_run_metadata_import(fetch),
        ):
            import_metadata_from_admin(model_admin, request)

        stored = list(request._messages)
        self.assertEqual(
            [m.level for m in stored], [messages.INFO] * 4 + [messages.WARNING] * 2
        )
        warnings = [m.message for m in stored if m.level == messages.WARNING]
        self.assertIn("Delphy set", warnings[0])
        self.assertIn("typo_sig", warnings[0])
        self.assertIn("indicator_sets: 25 duplicate rows", warnings[1])
        self.assertIn("Set 0, Set 1, Set 2, Set 3, Set 4, ...", warnings[1])
        self.assertNotIn("Set 5", warnings[1])

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
