import tablib
from django.test import SimpleTestCase, TestCase

from base.models import Geography, GeographicScope, Pathogen, SeverityPyramidRung
from base.sheet_values import (
    drop_duplicate_rows,
    geographic_scope_id,
    geography_ids,
    normalize_sheet_date,
    parse_bool,
    pathogen_ids,
    severity_pyramid_rung_ids,
    split_list,
)


class ParseBoolTests(SimpleTestCase):
    def test_values(self):
        for v in ("TRUE", "True", "true", True):
            self.assertIs(parse_bool(v), True)
        for v in ("FALSE", "False", "", None, "no"):
            self.assertIs(parse_bool(v), False)


class NormalizeSheetDateTests(SimpleTestCase):
    def test_iso_and_time_suffix(self):
        self.assertEqual(normalize_sheet_date("2020-02-01"), "2020-02-01")
        self.assertEqual(normalize_sheet_date("2020-02-01 00:00:00"), "2020-02-01")

    def test_epiweeks_become_sunday_start(self):
        self.assertEqual(normalize_sheet_date("2020w05"), "2020-01-26")
        self.assertEqual(normalize_sheet_date("202340"), "2023-10-01")
        self.assertEqual(normalize_sheet_date("2023-W40"), "2023-10-01")
        self.assertEqual(normalize_sheet_date("2021w01"), "2021-01-03")

    def test_invalid_week_kept_as_text(self):
        for bad in ("202300", "202399", "2023w54", "2023w00"):
            self.assertEqual(normalize_sheet_date(bad), bad)

    def test_week_53_converts_when_year_has_it(self):
        self.assertEqual(normalize_sheet_date("2020w53"), "2020-12-27")

    def test_empty_and_other_text_kept(self):
        self.assertEqual(normalize_sheet_date(""), "")
        self.assertEqual(normalize_sheet_date(None), "")
        self.assertEqual(normalize_sheet_date(" varies "), "varies")


class SplitListTests(SimpleTestCase):
    def test_strips_and_drops_empty(self):
        self.assertEqual(split_list(" COVID-19, RSV ,,"), ["COVID-19", "RSV"])
        self.assertEqual(split_list(None), [])


class DropDuplicateRowsTests(SimpleTestCase):
    def test_first_wins_and_reports_differing(self):
        ds = tablib.Dataset(
            ["a", "x"], ["a", "x"], ["b", "1"], ["b", "2"], headers=["k", "v"]
        )
        self.assertEqual(drop_duplicate_rows(ds, "k"), ["b"])
        self.assertEqual([tuple(r) for r in ds], [("a", "x"), ("b", "1")])

    def test_empty_key_rows_left_alone(self):
        ds = tablib.Dataset(["", "x"], ["", "x"], headers=["k", "v"])
        self.assertEqual(drop_duplicate_rows(ds, "k"), [])
        self.assertEqual(len(ds), 2)


class PathogenIdsTests(TestCase):
    def test_creates_and_returns_ids(self):
        ids = pathogen_ids("COVID-19, RSV", "indicators")
        self.assertEqual(
            sorted(
                Pathogen.objects.filter(pk__in=ids.split(",")).values_list(
                    "name", flat=True
                )
            ),
            ["COVID-19", "RSV"],
        )
        self.assertEqual(pathogen_ids("", "indicators"), "")


class GeographyIdsTests(TestCase):
    def test_display_name_maps_to_key(self):
        ids = geography_ids("State/ADM 1, National", "indicators")
        self.assertEqual(
            sorted(
                Geography.objects.filter(pk__in=ids.split(",")).values_list(
                    "name", flat=True
                )
            ),
            ["nation", "state"],
        )

    def test_unknown_level_created_when_table_empty(self):
        Geography.objects.filter(used_in="indicators").delete()
        geography_ids("Sewershed", "indicators")
        self.assertEqual(
            Geography.objects.get(
                name="Sewershed", used_in="indicators"
            ).display_order_number,
            1,
        )


class SeverityPyramidRungIdsTests(TestCase):
    def test_empty_as_na(self):
        ids = severity_pyramid_rung_ids("", "indicators", empty_as_na=True)
        self.assertEqual(SeverityPyramidRung.objects.get(pk=int(ids)).name, "N/A")

    def test_empty_default(self):
        self.assertEqual(severity_pyramid_rung_ids("", "indicators"), "")


class GeographicScopeIdTests(TestCase):
    def test_get_or_create(self):
        scope_id = geographic_scope_id(" US ", "indicators")
        self.assertEqual(GeographicScope.objects.get(pk=scope_id).name, "US")
        self.assertIsNone(geographic_scope_id("", "indicators"))
