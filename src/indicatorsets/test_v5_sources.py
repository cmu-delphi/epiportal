"""Covidcast-shaped signals served from Epidata v5.

Covers v5-only sources (sleepcycle), which v4 does not have at all, and
migrated sources (nssp), which keep their v4 fallback wherever v4 can answer:
everything but census divisions, a v5-only geo_type.
"""

import json
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from base.models import Geography, GeographyUnit
from indicatorsets.utils.epidata import can_fall_back_to_v4, get_v5_source
from indicatorsets.utils.epivis import generate_covidcast_dataset_epivis
from indicatorsets.utils.exports import generate_covidcast_indicators_export_url
from indicatorsets.utils.geos import get_covidcast_geo_coverage
from indicatorsets.utils.locations import to_covidcast_geo, use_main_locations
from indicatorsets.utils.previews import preview_covidcast_data
from indicatorsets.utils.query_code import generate_query_code_covidcast

SLEEPCYCLE = {
    "_endpoint": "sleepcycle",
    "data_source": "sleepcycle",
    "indicator": "pct_cough_2_plus_7dav",
    "time_type": "day",
    "display_name": "Cough 2+",
    "indicator_set_short_name": "sleep",
}
NSSP = {
    "_endpoint": "covidcast",
    "data_source": "nssp",
    "indicator": "pct_ed_visits_rsv",
    "time_type": "week",
    "display_name": "RSV ED visits",
    "indicator_set_short_name": "nssp",
}
NSSP_V4_ONLY_SIGNAL = {**NSSP, "indicator": "not_in_v5"}
DOCTOR_VISITS = {
    "_endpoint": "covidcast",
    "data_source": "doctor-visits",
    "indicator": "smoothed_cli",
    "time_type": "day",
    "display_name": "CLI",
    "indicator_set_short_name": "dv",
}

V5_METADATA = {
    "nssp": {"signals": ["pct_ed_visits_rsv"], "geo_types": ["nation", "state", "county"]},
    "sleepcycle": {
        "signals": ["pct_cough_2_plus_7dav"],
        "geo_types": ["census_division", "census_region", "nation", "state"],
    },
}


def _geo(location_id, text=None):
    return {"id": location_id, "text": text or location_id, "geoType": location_id.split(":")[0]}


def _response(payload):
    response = MagicMock(status_code=200, text="")
    response.raise_for_status = MagicMock()
    response.json.return_value = payload
    return response


class FakeEpidata:
    """Fake ``requests.get``: v5 ``viz`` answers ``v5_rows``, v4 ``v4_rows``.

    Records every call so tests can assert v4 was, or was not, asked.
    """

    def __init__(self, v5_rows=(), v4_rows=()):
        self.v5_rows = list(v5_rows)
        self.v4_rows = list(v4_rows)
        self.calls = []

    def __call__(self, url, params=None, **kwargs):
        self.calls.append((url, dict(params or {})))
        if "/v5/" in url:
            return _response(self.v5_rows)
        return _response({"result": 1, "epidata": self.v4_rows, "message": "ok"})

    def v4_calls(self):
        return [params for url, params in self.calls if "/v5/" not in url]

    def v5_calls(self):
        return [params for url, params in self.calls if "/v5/" in url]


class V5MetadataMixin:
    def setUp(self):
        cache.clear()
        patcher = patch(
            "indicatorsets.utils.epidata.get_v5_metadata", return_value=V5_METADATA
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch(
            "indicatorsets.utils.geos.get_v5_metadata", return_value=V5_METADATA
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_epidata(self, **kwargs):
        fake = FakeEpidata(**kwargs)
        patcher = patch("requests.get", side_effect=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake


class RoutingTests(V5MetadataMixin, TestCase):
    def test_v5_only_source_routes_to_v5_without_metadata(self):
        with patch("indicatorsets.utils.epidata.get_v5_metadata", return_value={}):
            self.assertEqual(get_v5_source(SLEEPCYCLE), "sleepcycle")

    def test_migrated_signal_v5_lacks_stays_on_v4(self):
        self.assertEqual(get_v5_source(NSSP), "nssp")
        self.assertIsNone(get_v5_source(NSSP_V4_ONLY_SIGNAL))

    def test_v4_fallback_only_where_v4_can_answer(self):
        self.assertTrue(can_fall_back_to_v4(NSSP, "county", ""))
        self.assertTrue(can_fall_back_to_v4(NSSP, "county", "source"))
        self.assertFalse(can_fall_back_to_v4(NSSP, "county", "ave"))
        self.assertFalse(can_fall_back_to_v4(NSSP, "census_division", ""))
        self.assertFalse(can_fall_back_to_v4(SLEEPCYCLE, "state", ""))


class CovidcastGeoMappingTests(TestCase):
    def test_census_divisions_only_on_v5(self):
        self.assertEqual(
            to_covidcast_geo("census-region:cen3", on_v5=True), ("census_division", "3")
        )
        self.assertIsNone(to_covidcast_geo("census-region:cen3"))

    def test_other_levels(self):
        self.assertEqual(to_covidcast_geo("state:PA", on_v5=True), ("state", "pa"))
        self.assertEqual(to_covidcast_geo("county:42003"), ("county", "42003"))
        self.assertIsNone(to_covidcast_geo("us-city:jfk", on_v5=True))
        self.assertIsNone(to_covidcast_geo(""))


class UseMainLocationsCensusTests(V5MetadataMixin, TestCase):
    payload = {
        "census-region": [_geo("census-region:cen1")],
        "state": [_geo("state:PA")],
    }

    def test_kept_for_signals_served_from_v5(self):
        for indicator in (SLEEPCYCLE, NSSP):
            with self.subTest(indicator["data_source"]):
                data = use_main_locations(
                    {"indicators": [indicator], "covidCastGeographicValues": self.payload}
                )
                self.assertIn("census-region", data["covidCastGeographicValues"])

    def test_dropped_for_v4_signals(self):
        data = use_main_locations(
            {"indicators": [DOCTOR_VISITS], "covidCastGeographicValues": self.payload}
        )
        self.assertEqual(list(data["covidCastGeographicValues"]), ["state"])


class AvailableGeosFromV5Tests(V5MetadataMixin, TestCase):
    def setUp(self):
        super().setUp()
        levels = {
            name: Geography.objects.create(name=name, display_name=f"{name} level")
            for name in ("nation", "state", "county", "census-region", "us-city")
        }
        for level, geo_id in (
            ("nation", "US"),
            ("state", "PA"),
            ("county", "42003"),
            ("census-region", "cen1"),
            ("us-city", "jfk"),
        ):
            GeographyUnit.objects.create(
                geo_id=geo_id, name=geo_id, display_name=geo_id, level=1,
                geo_level=levels[level],
            )

    def _ids(self, indicators, v4_geos=()):
        fake = FakeEpidata()
        fake.v4_rows = list(v4_geos)
        with patch("requests.get", side_effect=fake):
            response = self.client.post(
                reverse("get_available_geos"),
                data=json.dumps({"indicators": indicators}),
                content_type="application/json",
            )
        ids = sorted(
            child["id"]
            for group in response.json()["geographic_granularities"]
            for child in group["children"]
        )
        return ids, fake

    def test_v5_only_source_lists_units_at_its_v5_levels(self):
        ids, fake = self._ids([SLEEPCYCLE])
        self.assertEqual(ids, ["census-region:cen1", "nation:US", "state:PA"])
        self.assertEqual(fake.calls, [])

    def test_migrated_signal_lists_from_v5_not_v4(self):
        ids, fake = self._ids([NSSP])
        self.assertEqual(ids, ["county:42003", "nation:US", "state:PA"])
        self.assertEqual(fake.calls, [])

    def test_v4_signals_still_ask_v4(self):
        ids, fake = self._ids([NSSP_V4_ONLY_SIGNAL], v4_geos=["county:42003"])
        self.assertEqual(ids, ["county:42003"])
        self.assertEqual(len(fake.v4_calls()), 1)


class CoverageTests(V5MetadataMixin, TestCase):
    def test_v5_only_source_without_v5_values_never_asks_v4(self):
        fake = self.fake_epidata(v5_rows=[], v4_rows=[{"signal": SLEEPCYCLE["indicator"], "value": 1}])
        coverage = get_covidcast_geo_coverage("state:PA", [SLEEPCYCLE])
        self.assertEqual(coverage[0]["covered"], False)
        self.assertEqual(fake.v4_calls(), [])

    def test_census_division_asks_v5_with_its_spelling(self):
        fake = self.fake_epidata(v5_rows=[{"signal": SLEEPCYCLE["indicator"], "value": 3}])
        coverage = get_covidcast_geo_coverage("census-region:cen3", [SLEEPCYCLE])
        self.assertEqual((coverage[0]["covered"], coverage[0]["route"]), (True, "v5"))
        self.assertEqual(fake.v5_calls()[0]["geo_type"], "census_division")
        self.assertEqual(fake.v5_calls()[0]["geo_value"], "3")

    def test_migrated_signal_keeps_v4_fallback(self):
        fake = self.fake_epidata(v5_rows=[], v4_rows=[{"signal": NSSP["indicator"], "value": 1}])
        coverage = get_covidcast_geo_coverage("county:42003", [NSSP])
        self.assertEqual((coverage[0]["covered"], coverage[0]["route"]), (True, "v4"))

    def test_migrated_signal_no_v4_fallback_for_census_division(self):
        fake = self.fake_epidata(v5_rows=[], v4_rows=[{"signal": NSSP["indicator"], "value": 1}])
        coverage = get_covidcast_geo_coverage("census-region:cen3", [NSSP])
        self.assertEqual(coverage[0]["covered"], False)
        self.assertEqual(fake.v4_calls(), [])

    def test_v4_signal_has_no_census_divisions(self):
        fake = self.fake_epidata()
        coverage = get_covidcast_geo_coverage("census-region:cen3", [DOCTOR_VISITS])
        self.assertEqual(coverage[0]["covered"], False)
        self.assertEqual(fake.calls, [])


class PreviewAndExportTests(V5MetadataMixin, TestCase):
    geos = {"state": [_geo("state:PA")]}

    def test_preview_v5_only_without_values_reports_no_data(self):
        fake = self.fake_epidata(v5_rows=[])
        preview = preview_covidcast_data(
            [SLEEPCYCLE], "2026-01-01", "2026-02-01", self.geos, "", "json"
        )
        self.assertEqual(preview, [{"message": "No data found for Cough 2+ (state)."}])
        self.assertEqual(fake.v4_calls(), [])

    def test_preview_migrated_signal_still_falls_back_to_v4(self):
        fake = self.fake_epidata(v5_rows=[], v4_rows=[{"geo_value": "pa", "value": 1}])
        preview_covidcast_data([NSSP], "2026-01-01", "2026-02-01", self.geos, "", "json")
        self.assertEqual(len(fake.v4_calls()), 1)

    def test_export_v5_only_without_values_skips_v4(self):
        fake = self.fake_epidata(v5_rows=[])
        commands = generate_covidcast_indicators_export_url(
            [SLEEPCYCLE], "2026-01-01", "2026-02-01", self.geos, "", "csv"
        )
        self.assertEqual(len(commands), 1)
        self.assertIn("No data found", commands[0])
        self.assertEqual(fake.v4_calls(), [])

    def test_export_census_division_goes_to_v5(self):
        self.fake_epidata(v5_rows=[{"geo_value": "1", "value": 1}])
        commands = generate_covidcast_indicators_export_url(
            [SLEEPCYCLE], "2026-01-01", "2026-02-01",
            {"census-region": [_geo("census-region:cen1")]}, "", "csv",
        )
        self.assertEqual(len(commands), 1)
        self.assertIn("geo_type=census_division", commands[0])
        self.assertIn("source=sleepcycle", commands[0])


class EpivisTests(V5MetadataMixin, TestCase):
    geos = {
        "census-region": [_geo("census-region:cen2", "Division 2")],
        "state": [_geo("state:PA", "Pennsylvania")],
    }

    def test_v5_only_source_goes_to_epivis_as_covidcast(self):
        datasets = generate_covidcast_dataset_epivis(SLEEPCYCLE, self.geos)
        params = [d["params"] for d in datasets]
        self.assertEqual({p["_endpoint"] for p in params}, {"covidcast"})
        self.assertEqual(
            [(p["geo_type"], p["geo_value"]) for p in params],
            [("census_division", "2"), ("state", "pa")],
        )

    def test_v4_signal_skips_census_divisions(self):
        datasets = generate_covidcast_dataset_epivis(DOCTOR_VISITS, self.geos)
        self.assertEqual([d["params"]["geo_type"] for d in datasets], ["state"])


class QueryCodeTests(V5MetadataMixin, TestCase):
    def test_census_division_only_in_the_v5_snippet(self):
        geos = {
            "census-region": [_geo("census-region:cen1")],
            "state": [_geo("state:PA")],
        }
        python_blocks, _ = generate_query_code_covidcast(
            [NSSP, NSSP_V4_ONLY_SIGNAL], geos, "2026-01-01", "2026-02-01",
            "nssp", "pct_ed_visits_rsv,not_in_v5",
        )
        code = "".join(python_blocks)
        self.assertIn('geo_type="census_division"', code)
        self.assertEqual(code.count("pub_covidcast("), 1)
        self.assertIn('geo_type="state"', code)
