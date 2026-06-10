from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from indicatorsets.models import (
    ColumnDescription,
    FilterDescription,
    IndicatorSet,
    NonDelphiIndicatorSet,
    USStateIndicatorSet,
)
from indicatorsets.utils import (
    dict_to_geo_string,
    generate_epivis_custom_title,
    generate_random_color,
    get_epiweek,
    get_grouped_original_data_provider_choices,
    get_list_of_indicators_filtered_by_geo,
    get_original_data_provider_choices,
    group_by_property,
    list_to_dict,
)
from indicatorsets.views import get_related_indicators
from indicatorsets.filters import IndicatorSetFilter
from base.models import Pathogen
from datasources.models import SourceSubdivision
from indicators.models import Indicator


class IndicatorsetsUtilsTests(TestCase):
    def test_list_to_dict_groups_duplicate_keys(self):
        result = list_to_dict(["state:pa", "state:ny", "county:42003"])
        self.assertEqual(result["state"], ["pa", "ny"])
        self.assertEqual(result["county"], ["42003"])

    def test_dict_to_geo_string(self):
        geo_dict = {"state": ["pa", "ny"], "county": ["42003"]}
        self.assertEqual(dict_to_geo_string(geo_dict), "state:pa,ny;county:42003")

    def test_group_by_property(self):
        items = [
            {"type": "a", "value": 1},
            {"type": "b", "value": 2},
            {"type": "a", "value": 3},
        ]
        grouped = group_by_property(items, "type")
        self.assertEqual(len(grouped["a"]), 2)
        self.assertEqual(len(grouped["b"]), 1)

    def test_get_epiweek_formats_dates(self):
        start, end = get_epiweek("2020-01-06", "2020-01-20")
        self.assertEqual(len(start), 6)
        self.assertEqual(len(end), 6)
        self.assertTrue(start.startswith("2020"))

    def test_generate_epivis_custom_title(self):
        indicator = {
            "indicator_set_short_name": "Set",
            "member_short_name": "Mem",
        }
        title = generate_epivis_custom_title(indicator, "Pennsylvania")
        self.assertIn("Set", title)
        self.assertIn("Pennsylvania", title)

    def test_generate_random_color_is_hex(self):
        color = generate_random_color()
        self.assertRegex(color, r"^#[0-9a-f]{6}$")


class IndicatorSetModelTests(TestCase):
    def test_create_and_str(self):
        indicator_set = IndicatorSet.objects.create(
            name="ILI surveillance",
            short_name="ILI",
            source_type="covidcast",
        )
        self.assertEqual(str(indicator_set), "ILI surveillance")


class DescriptionModelTests(TestCase):
    def test_filter_description_dict(self):
        FilterDescription.objects.create(
            name="pathogens",
            description="Filter by pathogen",
        )
        result = FilterDescription.get_all_descriptions_as_dict()
        self.assertEqual(result["pathogens"], "Filter by pathogen")

    def test_column_description_dict(self):
        ColumnDescription.objects.create(
            name="name",
            description="Indicator set name",
        )
        result = ColumnDescription.get_all_descriptions_as_dict()
        self.assertEqual(result["name"], "Indicator set name")


class GroupedDataProviderChoicesTests(TestCase):
    def test_groups_us_state_and_us_government_providers(self):
        IndicatorSet.objects.create(
            name="State set",
            original_data_provider="PA DOH",
            source_type="us_state",
        )
        IndicatorSet.objects.create(
            name="Federal set",
            original_data_provider="US CDC",
            source_type="covidcast",
        )
        IndicatorSet.objects.create(
            name="Other set",
            original_data_provider="Acme Corp",
            source_type="covidcast",
        )

        from indicatorsets.utils import get_grouped_original_data_provider_choices

        grouped = get_grouped_original_data_provider_choices()
        self.assertIn("PA DOH", grouped["groups"][1]["providers"])
        self.assertIn("US CDC", grouped["groups"][0]["providers"])
        self.assertIn("Acme Corp", grouped["main"])


class PophiveAgeGroupsViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def tearDown(self):
        cache.clear()

    @patch("indicatorsets.views.requests.get")
    def test_returns_empty_list_when_upstream_fails(self, mock_get):
        mock_get.side_effect = requests.RequestException("unavailable")
        response = self.client.get(reverse("get_pophive_age_groups"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"age_groups": []})

    @patch("indicatorsets.views.requests.get")
    def test_caches_successful_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"epidata": [{"id": "0-4"}]}
        mock_get.return_value = mock_response

        response = self.client.get(reverse("get_pophive_age_groups"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["age_groups"], [{"id": "0-4"}])
        self.assertIsNotNone(cache.get("pophive_age_groups"))


class TableStatsViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_table_stats_with_no_data(self):
        response = self.client.get(reverse("get_table_stats_info"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["num_of_indicator_sets"], 0)
        self.assertEqual(data["num_of_indicators"], 0)


class IndicatorSetListViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_list_page_renders(self):
        response = self.client.get(reverse("indicatorsets"))
        self.assertEqual(response.status_code, 200)

    def test_json_format_returns_datatables_shape(self):
        IndicatorSet.objects.create(
            name="JSON test set",
            source_type="covidcast",
            temporal_scope_end="Ongoing",
            dua_required="No",
        )
        response = self.client.get(reverse("indicatorsets"), {"format": "json"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("data", payload)
        self.assertIn("recordsTotal", payload)
        self.assertEqual(payload["recordsTotal"], 1)


class GetRelatedIndicatorsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = SourceSubdivision.objects.create(name="related_src")
        cls.indicator_set = IndicatorSet.objects.create(
            name="Related set",
            short_name="RS",
            epidata_endpoint="covidcast",
            source_type="covidcast",
            dua_required="No",
        )
        cls.indicator = Indicator.objects.create(
            name="sig_a",
            member_name="Member A",
            source=cls.source,
            indicator_set=cls.indicator_set,
            source_type="covidcast",
            description="Indicator description",
        )

    def test_display_name_falls_back_to_member_name(self):
        qs = Indicator.objects.all()
        result = get_related_indicators(qs, [self.indicator_set.id])
        self.assertEqual(result[0]["display_name"], "Member A")
        self.assertEqual(result[0]["member_description"], "Indicator description")

    def test_display_name_uses_explicit_display_name(self):
        self.indicator.display_name = "Custom label"
        self.indicator.save(update_fields=["display_name"])
        result = get_related_indicators(Indicator.objects.all(), [self.indicator_set.id])
        self.assertEqual(result[0]["display_name"], "Custom label")


class IndicatorSetFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.covidcast_set = IndicatorSet.objects.create(
            name="Covidcast set",
            source_type="covidcast",
            temporal_scope_end="Ongoing",
        )
        cls.non_delphi_set = IndicatorSet.objects.create(
            name="External set",
            source_type="non_delphi",
            temporal_scope_end="2020",
        )

    def test_hosted_by_delphi_filter(self):
        data = {"hosted_by_delphi": "on"}
        filtered = IndicatorSetFilter(data=data, queryset=IndicatorSet.objects.all()).qs
        self.assertIn(self.covidcast_set, filtered)
        self.assertNotIn(self.non_delphi_set, filtered)

    def test_temporal_scope_end_filter(self):
        data = {"temporal_scope_end": "Ongoing"}
        filtered = IndicatorSetFilter(data=data, queryset=IndicatorSet.objects.all()).qs
        self.assertIn(self.covidcast_set, filtered)
        self.assertNotIn(self.non_delphi_set, filtered)

    def test_include_fluview_detects_mapped_locations(self):
        self.assertTrue(
            IndicatorSetFilter.include_fluview("['state:PA']")
        )
        self.assertFalse(
            IndicatorSetFilter.include_fluview("['country:us']")
        )


class IndicatorSetProxyModelTests(TestCase):
    def test_non_delphi_proxy(self):
        indicator_set = IndicatorSet.objects.create(
            name="Non-delphi proxy set",
            source_type="non_delphi",
        )
        proxy = NonDelphiIndicatorSet.objects.get(pk=indicator_set.pk)
        self.assertIsInstance(proxy, NonDelphiIndicatorSet)

    def test_us_state_proxy(self):
        indicator_set = IndicatorSet.objects.create(
            name="US state proxy set",
            source_type="us_state",
        )
        proxy = USStateIndicatorSet.objects.get(pk=indicator_set.pk)
        self.assertIsInstance(proxy, USStateIndicatorSet)


class OriginalDataProviderUtilsTests(TestCase):
    def test_get_original_data_provider_choices(self):
        IndicatorSet.objects.create(
            name="Provider set",
            original_data_provider="Acme Labs",
            source_type="covidcast",
        )
        choices = get_original_data_provider_choices()
        self.assertIn(("Acme Labs", "Acme Labs"), choices)


class GeoCoverageUtilsTests(TestCase):
    @patch("indicatorsets.utils.requests.get")
    def test_get_list_of_indicators_filtered_by_geo_returns_epidata(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "epidata": [{"source": "src", "signal": "sig"}],
            "result": 1,
        }
        mock_get.return_value = mock_response

        result = get_list_of_indicators_filtered_by_geo("['state:pa']")
        self.assertEqual(result["epidata"][0]["signal"], "sig")

    @patch("indicatorsets.utils.requests.get", side_effect=requests.RequestException)
    def test_get_list_of_indicators_filtered_by_geo_handles_errors(self, _mock_get):
        result = get_list_of_indicators_filtered_by_geo("['state:pa']")
        self.assertEqual(result, {"epidata": [], "result": -1})
