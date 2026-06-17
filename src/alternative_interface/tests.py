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

    @patch("alternative_interface.utils.requests.get")
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
