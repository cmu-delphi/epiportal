from datetime import datetime
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase
from django.urls import reverse

from alternative_interface.models import ExpressViewIndicator
from alternative_interface.utils import (
    _day_key,
    _day_label,
    _epiweek_key,
    _epiweek_label,
    days_in_date_range,
    epiweeks_in_date_range,
    get_available_geos,
    get_chart_data,
    normalize_dataset,
)
from alternative_interface.views import (
    _convert_indicators_to_dicts,
    _get_indicators_queryset,
)
from base.models import Geography, GeographyUnit
from datasources.models import SourceSubdivision
from indicators.models import Indicator
from indicatorsets.models import IndicatorSet


def _create_express_indicator(menu_item="COVID-19", signal_name="test_signal"):
    source = SourceSubdivision.objects.create(name=f"src_{signal_name}")
    indicator_set = IndicatorSet.objects.create(
        name=f"Set {signal_name}",
        short_name="TS",
        epidata_endpoint="covidcast",
        source_type="covidcast",
    )
    indicator = Indicator.objects.create(
        name=signal_name,
        display_name="Test signal",
        source=source,
        indicator_set=indicator_set,
        source_type="covidcast",
        time_type="week",
    )
    express = ExpressViewIndicator.objects.create(
        menu_item=menu_item,
        indicator=indicator,
        display_name="Express label",
        grouping_key="group_a",
        display_order=1,
    )
    return express


class ExpressViewIndicatorModelTests(TestCase):
    def test_str_returns_display_name(self):
        express = _create_express_indicator()
        self.assertEqual(str(express), "Express label")

    def test_unique_menu_item_and_indicator(self):
        express = _create_express_indicator(signal_name="sig_a")
        with self.assertRaises(Exception):
            ExpressViewIndicator.objects.create(
                menu_item=express.menu_item,
                indicator=express.indicator,
                display_name="Duplicate",
            )


class AlternativeInterfaceUtilsTests(TestCase):
    def test_epiweeks_in_date_range(self):
        weeks = epiweeks_in_date_range("2020-01-01", "2020-02-01")
        self.assertGreater(len(weeks), 0)

    def test_days_in_date_range(self):
        days = days_in_date_range("2020-01-01", "2020-01-05")
        self.assertEqual(len(days), 5)

    def test_normalize_dataset_scales_to_100(self):
        data = [10.0, 20.0, 30.0]
        normalized = normalize_dataset(data)
        self.assertEqual(normalized[-1], 100.0)

    def test_normalize_dataset_empty_returns_empty(self):
        self.assertEqual(normalize_dataset([]), [])

    def test_normalize_dataset_scales_using_initial_view_range(self):
        day_labels = ["2020-01-01", "2020-01-02", "2020-01-03"]
        data = [5.0, 10.0, 20.0]
        normalized = normalize_dataset(
            data,
            day_labels=day_labels,
            initial_view_start="2020-01-01",
            initial_view_end="2020-01-02",
        )
        self.assertEqual(normalized[1], 100.0)

    def test_epiweek_and_day_helpers(self):
        from datetime import date
        from epiweeks import Week

        week = Week(2020, 32)
        self.assertEqual(_epiweek_key(week), 202032)
        self.assertEqual(_epiweek_label(week), "2020-W32")
        self.assertEqual(_day_key(date(2024, 1, 15)), 20240115)
        self.assertEqual(_day_label(date(2024, 1, 15)), "2024-01-15")


class FrozenDatetime(datetime):
    """datetime with now() pinned, so get_chart_data's rolling 2y/10y windows
    are deterministic. Subclassing keeps strptime and the constructor working."""

    @classmethod
    def now(cls, tz=None):
        return datetime(2024, 6, 15, 12, 0, 0)


def _nonnull(values):
    """Compact projection of a 3651-element series: just (index, value) pairs."""
    return [(i, v) for i, v in enumerate(values) if v is not None]


class GetChartDataNormalizationTests(TestCase):
    """Characterization tests for get_chart_data's group normalization.

    get_chart_data scales every series in a grouping_key group by ONE shared
    max (unlike normalize_dataset, which scales each series by its own max),
    so these pin the group-wide behaviour before that logic is extracted.
    """

    def _setup_two_grouped_indicators(self):
        source = SourceSubdivision.objects.create(name="covidcast_src")
        indicator_set = IndicatorSet.objects.create(
            name="Set",
            short_name="S",
            epidata_endpoint="covidcast",
            source_type="covidcast",
        )
        indicators = []
        for name in ("sig_low", "sig_high"):
            ind = Indicator.objects.create(
                name=name,
                display_name=name,
                source=source,
                indicator_set=indicator_set,
                source_type="covidcast",
                time_type="day",
            )
            ExpressViewIndicator.objects.create(
                menu_item="COVID-19",
                indicator=ind,
                display_name=f"Label {name}",
                grouping_key="shared_group",
                display_order=1,
            )
            indicators.append(
                {
                    "_endpoint": "covidcast",
                    "name": name,
                    "data_source": "covidcast_src",
                    "time_type": "day",
                    "grouping_key": "shared_group",
                }
            )
        return indicators

    def _run(self, rows_by_signal):
        indicators = self._setup_two_grouped_indicators()

        def fake_covidcast(indicator, start, end, geo, api_key):
            return rows_by_signal[indicator["name"]]

        with patch(
            "alternative_interface.utils.charts.datetime", FrozenDatetime
        ), patch(
            "alternative_interface.utils.charts.generate_random_color",
            return_value="#abcdef",
        ), patch(
            "alternative_interface.utils.charts.get_covidcast_data",
            side_effect=fake_covidcast,
        ):
            return get_chart_data(indicators, "state:pa")

    def test_group_shares_one_scale_factor(self):
        """Two series in one group: only the group-wide peak reaches 100, and
        the weaker series stays proportionally smaller."""
        chart = self._run(
            {
                "sig_low": [
                    {
                        "time_value": 20240601,
                        "value": 10,
                        "signal": "sig_low",
                        "time_type": "day",
                    },
                    {
                        "time_value": 20240602,
                        "value": 20,
                        "signal": "sig_low",
                        "time_type": "day",
                    },
                ],
                "sig_high": [
                    {
                        "time_value": 20240601,
                        "value": 50,
                        "signal": "sig_high",
                        "time_type": "day",
                    },
                    {
                        "time_value": 20240602,
                        "value": 100,
                        "signal": "sig_high",
                        "time_type": "day",
                    },
                ],
            }
        )
        self.assertEqual(len(chart["datasets"]), 2)
        low, high = chart["datasets"]
        self.assertEqual([v for _, v in _nonnull(low["data"])], [10.0, 20.0])
        self.assertEqual([v for _, v in _nonnull(high["data"])], [50.0, 100.0])
        # group max is 100 -> scale factor 1.0; peak of the group is 100
        self.assertEqual(max(v for _, v in _nonnull(high["data"])), 100.0)

    def test_scale_factor_derived_from_group_max_not_series_max(self):
        chart = self._run(
            {
                "sig_low": [
                    {
                        "time_value": 20240601,
                        "value": 5,
                        "signal": "sig_low",
                        "time_type": "day",
                    },
                ],
                "sig_high": [
                    {
                        "time_value": 20240601,
                        "value": 20,
                        "signal": "sig_high",
                        "time_type": "day",
                    },
                ],
            }
        )
        low, high = chart["datasets"]
        # group max 20 -> factor 5.0; low scales to 25, not to 100
        self.assertEqual([v for _, v in _nonnull(low["data"])], [25.0])
        self.assertEqual([v for _, v in _nonnull(high["data"])], [100.0])

    def test_original_data_preserved_and_grouping_key_removed(self):
        chart = self._run(
            {
                "sig_low": [
                    {
                        "time_value": 20240601,
                        "value": 5,
                        "signal": "sig_low",
                        "time_type": "day",
                    },
                ],
                "sig_high": [
                    {
                        "time_value": 20240601,
                        "value": 20,
                        "signal": "sig_high",
                        "time_type": "day",
                    },
                ],
            }
        )
        for ds in chart["datasets"]:
            self.assertNotIn("groupingKey", ds)
            self.assertIn("original_data", ds)
            self.assertEqual(len(ds["original_data"]), len(ds["data"]))
        low = chart["datasets"][0]
        self.assertEqual([v for _, v in _nonnull(low["original_data"])], [5])

    def test_falls_back_to_whole_series_when_view_window_is_empty(self):
        """get_chart_data fetches 10 years but the view window is the last 2, so
        a group whose data all predates the window must still normalize, using
        the whole-series maximum."""
        chart = self._run(
            {
                "sig_low": [
                    {
                        "time_value": 20180101,
                        "value": 5,
                        "signal": "sig_low",
                        "time_type": "day",
                    },
                ],
                "sig_high": [
                    {
                        "time_value": 20180101,
                        "value": 20,
                        "signal": "sig_high",
                        "time_type": "day",
                    },
                ],
            }
        )
        low, high = chart["datasets"]
        # nothing inside initialViewStart..initialViewEnd, so the group max comes
        # from the whole series: 20 -> factor 5.0
        self.assertEqual([v for _, v in _nonnull(low["data"])], [25.0])
        self.assertEqual([v for _, v in _nonnull(high["data"])], [100.0])

    def test_series_length_matches_day_labels(self):
        chart = self._run(
            {
                "sig_low": [
                    {
                        "time_value": 20240601,
                        "value": 5,
                        "signal": "sig_low",
                        "time_type": "day",
                    }
                ],
                "sig_high": [
                    {
                        "time_value": 20240601,
                        "value": 20,
                        "signal": "sig_high",
                        "time_type": "day",
                    }
                ],
            }
        )
        for ds in chart["datasets"]:
            self.assertEqual(len(ds["data"]), len(chart["dayLabels"]))

    def test_non_finite_values_become_none(self):
        chart = self._run(
            {
                "sig_low": [
                    {
                        "time_value": 20240601,
                        "value": float("nan"),
                        "signal": "sig_low",
                        "time_type": "day",
                    },
                    {
                        "time_value": 20240602,
                        "value": float("inf"),
                        "signal": "sig_low",
                        "time_type": "day",
                    },
                    {
                        "time_value": 20240603,
                        "value": 7,
                        "signal": "sig_low",
                        "time_type": "day",
                    },
                ],
                "sig_high": [
                    {
                        "time_value": 20240601,
                        "value": 14,
                        "signal": "sig_high",
                        "time_type": "day",
                    },
                ],
            }
        )
        low, high = chart["datasets"]
        self.assertEqual([v for _, v in _nonnull(low["data"])], [50.0])
        self.assertEqual([v for _, v in _nonnull(high["data"])], [100.0])

    def test_all_non_finite_group_falls_back_to_factor_one(self):
        chart = self._run(
            {
                "sig_low": [
                    {
                        "time_value": 20240601,
                        "value": None,
                        "signal": "sig_low",
                        "time_type": "day",
                    },
                ],
                "sig_high": [
                    {
                        "time_value": 20240601,
                        "value": None,
                        "signal": "sig_high",
                        "time_type": "day",
                    },
                ],
            }
        )
        for ds in chart["datasets"]:
            self.assertEqual(_nonnull(ds["data"]), [])


class AlternativeInterfaceViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_dashboard_renders(self):
        _create_express_indicator()
        response = self.client.get(reverse("alternative_interface"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Respiratory Diseases Dashboard")

    def test_get_available_geos_ajax_without_pathogen(self):
        response = self.client.get(reverse("get_available_geos_ajax"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("available_geos", response.json())

    def test_get_chart_data_ajax_requires_filters(self):
        response = self.client.get(reverse("get_chart_data_ajax"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"chart_data": {}})

    @patch("alternative_interface.views.get_chart_data")
    def test_get_chart_data_ajax_returns_chart_payload(self, mock_chart):
        express = _create_express_indicator()
        mock_chart.return_value = {"labels": ["2020-W01"], "datasets": []}
        response = self.client.get(
            reverse("get_chart_data_ajax"),
            {"pathogen": express.menu_item, "geography": "state:pa"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("labels", response.json()["chart_data"])


class AlternativeInterfaceViewHelperTests(TestCase):
    def test_convert_indicators_to_dicts(self):
        express = _create_express_indicator(signal_name="helper_sig")
        dictionaries = _convert_indicators_to_dicts(
            ExpressViewIndicator.objects.filter(pk=express.pk)
        )
        self.assertEqual(dictionaries[0]["name"], "helper_sig")
        self.assertEqual(dictionaries[0]["data_source"], express.indicator.source.name)

    def test_get_indicators_queryset_filters_by_pathogen(self):
        flu = _create_express_indicator(menu_item="Influenza", signal_name="flu_sig")
        _create_express_indicator(menu_item="COVID-19", signal_name="covid_sig")
        queryset = _get_indicators_queryset("Influenza")
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().pk, flu.pk)


class GetAvailableGeosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.geo_level = Geography.objects.create(
            name="state",
            display_name="State",
            used_in="indicators",
        )
        GeographyUnit.objects.create(
            geo_id="pa",
            display_name="Pennsylvania",
            geo_level=cls.geo_level,
            level=1,
        )

    @patch("alternative_interface.utils.geos.requests.get")
    def test_get_available_geos_returns_grouped_children(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"epidata": ["state:pa"]}
        mock_get.return_value = mock_response

        indicators = [
            {
                "name": "sig",
                "data_source": "hospital-admissions",
            }
        ]
        geos = get_available_geos(indicators)
        self.assertTrue(any(group["children"] for group in geos))

    def test_get_available_geos_without_indicators_returns_all_units(self):
        geos = get_available_geos([])
        child_count = sum(len(group["children"]) for group in geos)
        self.assertEqual(child_count, GeographyUnit.objects.count())
