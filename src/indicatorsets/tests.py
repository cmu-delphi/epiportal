import base64
import json
import re
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import redis
import requests
from django.conf import settings
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from django.http import QueryDict

from indicatorsets.models import (
    ColumnDescription,
    FilterDescription,
    IndicatorSet,
    NonDelphiIndicatorSet,
    OriginalDataProvider,
    USStateIndicatorSet,
)
from indicatorsets.utils import (
    NO_DATA_MESSAGE,
    InvalidApiKeyError,
    generate_covidcast_indicators_export_url,
    generate_epivis_custom_title,
    generate_epiweek_dataset_epivis,
    generate_epiweek_export_url,
    generate_query_code_epiweek,
    generate_nwss_export_url,
    generate_pophive_export_url,
    generate_random_color,
    get_epiweek,
    get_grouped_original_data_provider_choices,
    get_indicators_based_on_geo_epidata,
    get_indicators_based_on_geo_epidata_v5,
    get_list_of_indicators_filtered_by_geo,
    get_preview_data,
    group_by_property,
    list_to_dict,
    log_form_data,
    log_form_stats,
    parse_original_data_provider_ids,
    preview_covidcast_data,
    preview_epiweek_data,
    preview_nwss_data,
    preview_pophive_data,
)
from indicatorsets.proxy_views import VIZ_SOURCES
from indicatorsets.utils.constants import MIGRATED_DATASOURCES
from indicatorsets.utils.caching import safe_cache_get, safe_cache_set
from indicatorsets.utils.epidata import (
    get_v5_metadata,
    get_v5_source,
    map_fluview_geo_to_v5,
    map_flusurv_geo_to_v5,
)
from indicatorsets.utils.query_code import (
    generate_query_code_covidcast,
    generate_query_code_nwss,
    generate_query_code_pophive,
)
from indicatorsets.utils.sources import EPIWEEK_SOURCES
from indicatorsets.views import age_group_sort_key, get_related_indicators
from indicatorsets.filters import IndicatorSetFilter
from indicatorsets.resources import (
    IndicatorSetResource,
    NonDelphiIndicatorSetResource,
)
from base.models import Pathogen
from datasources.models import SourceSubdivision
from indicators.models import Indicator


class IndicatorsetsUtilsTests(TestCase):
    def test_list_to_dict_groups_duplicate_keys(self):
        result = list_to_dict(["state:pa", "state:ny", "county:42003"])
        self.assertEqual(result["state"], ["pa", "ny"])
        self.assertEqual(result["county"], ["42003"])

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
            "indicator": "sig",
        }
        title = generate_epivis_custom_title(indicator, "Pennsylvania")
        self.assertEqual(title, "Set:sig : Pennsylvania")

    def test_generate_epivis_custom_title_with_extra_keys(self):
        indicator = {
            "indicator_set_short_name": "Set",
            "indicator": "sig",
        }
        title = generate_epivis_custom_title(
            indicator, "Pennsylvania", "age_group:0-1"
        )
        self.assertEqual(title, "Set:sig : Pennsylvania (age_group:0-1)")

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
    def test_groups_providers_by_group_field(self):
        pa_provider = OriginalDataProvider.objects.create(
            name="PA DOH",
            group="us_states",
        )
        cdc_provider = OriginalDataProvider.objects.create(
            name="US CDC",
            group="us_government",
        )
        acme_provider = OriginalDataProvider.objects.create(
            name="Acme Corp",
            group="individual",
        )
        IndicatorSet.objects.create(
            name="State set",
            original_data_provider=pa_provider,
            source_type="us_state",
        )
        IndicatorSet.objects.create(
            name="Federal set",
            original_data_provider=cdc_provider,
            source_type="covidcast",
        )
        IndicatorSet.objects.create(
            name="Other set",
            original_data_provider=acme_provider,
            source_type="covidcast",
        )

        grouped = get_grouped_original_data_provider_choices()
        us_government_names = [p.name for p in grouped["groups"][0]["providers"]]
        us_state_names = [p.name for p in grouped["groups"][1]["providers"]]
        main_names = [p.name for p in grouped["main"]]

        self.assertIn("PA DOH", us_state_names)
        self.assertIn("US CDC", us_government_names)
        self.assertIn("Acme Corp", main_names)


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
        mock_response.json.return_value = {
            "extra_key_values": {
                "age_group": ["5-18", "0-1", "65+", "all", "1-5"],
            }
        }
        mock_get.return_value = mock_response

        response = self.client.get(reverse("get_pophive_age_groups"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["age_groups"],
            ["0-1", "1-5", "5-18", "65+", "all"],
        )
        self.assertEqual(
            cache.get("pophive_age_groups"),
            ["0-1", "1-5", "5-18", "65+", "all"],
        )

    def test_age_group_sort_key(self):
        age_groups = ["5-18", "<1", "18-50", "65+", "all", "1-5", "50-65"]
        self.assertEqual(
            sorted(age_groups, key=age_group_sort_key),
            ["<1", "1-5", "5-18", "18-50", "50-65", "65+", "all"],
        )


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
        provider = OriginalDataProvider.objects.create(name="Acme Labs")
        IndicatorSet.objects.create(
            name="JSON test set",
            source_type="covidcast",
            temporal_scope_end="Ongoing",
            dua_required="No",
            original_data_provider=provider,
        )
        response = self.client.get(reverse("indicatorsets"), {"format": "json"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("data", payload)
        self.assertIn("recordsTotal", payload)
        self.assertEqual(payload["recordsTotal"], 1)
        self.assertEqual(payload["data"][0]["original_data_provider"], "Acme Labs")

    def test_list_page_filters_by_odp_ids(self):
        provider = OriginalDataProvider.objects.create(name="Filtered provider")
        matched_set = IndicatorSet.objects.create(
            name="Matched set",
            source_type="covidcast",
            original_data_provider=provider,
        )
        IndicatorSet.objects.create(
            name="Other set",
            source_type="covidcast",
        )
        response = self.client.get(
            reverse("indicatorsets"),
            {"odp": str(provider.id), "format": "json"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["recordsTotal"], 1)
        self.assertEqual(payload["data"][0]["DT_RowId"], matched_set.id)


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
        cls.acme_provider = OriginalDataProvider.objects.create(
            name="Acme Labs",
            group="individual",
        )
        cls.cdc_provider = OriginalDataProvider.objects.create(
            name="US CDC",
            group="us_government",
        )
        cls.acme_set = IndicatorSet.objects.create(
            name="Acme set",
            source_type="covidcast",
            original_data_provider=cls.acme_provider,
        )
        cls.cdc_set = IndicatorSet.objects.create(
            name="CDC set",
            source_type="covidcast",
            original_data_provider=cls.cdc_provider,
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

    def test_odp_filter_by_comma_separated_ids(self):
        data = QueryDict(f"odp={self.acme_provider.id},{self.cdc_provider.id}")
        filtered = IndicatorSetFilter(data=data, queryset=IndicatorSet.objects.all()).qs
        self.assertIn(self.acme_set, filtered)
        self.assertIn(self.cdc_set, filtered)
        self.assertNotIn(self.covidcast_set, filtered)

    def test_odp_filter_by_repeated_ids(self):
        data = QueryDict(mutable=True)
        data.setlist("odp", [str(self.acme_provider.id), str(self.cdc_provider.id)])
        filtered = IndicatorSetFilter(data=data, queryset=IndicatorSet.objects.all()).qs
        self.assertIn(self.acme_set, filtered)
        self.assertIn(self.cdc_set, filtered)
        self.assertNotIn(self.covidcast_set, filtered)

    def test_original_data_provider_filter_accepts_legacy_names(self):
        data = QueryDict(mutable=True)
        data.setlist("original_data_provider", [self.acme_provider.name])
        filtered = IndicatorSetFilter(data=data, queryset=IndicatorSet.objects.all()).qs
        self.assertIn(self.acme_set, filtered)
        self.assertNotIn(self.cdc_set, filtered)


class IndicatorSetImportResourceTests(TestCase):
    def test_non_delphi_import_only_deletes_other_non_delphi_sets(self):
        delphi_set = IndicatorSet.objects.create(
            name="Delphi set",
            source_type="covidcast",
        )
        kept_non_delphi = IndicatorSet.objects.create(
            name="Kept non-delphi set",
            source_type="non_delphi",
        )
        removed_non_delphi = IndicatorSet.objects.create(
            name="Removed non-delphi set",
            source_type="non_delphi",
        )

        resource = NonDelphiIndicatorSetResource()
        resource.imported_rows_pks = [kept_non_delphi.pk]
        resource.after_import(None, None, dry_run=False)

        self.assertTrue(IndicatorSet.objects.filter(pk=delphi_set.pk).exists())
        self.assertTrue(IndicatorSet.objects.filter(pk=kept_non_delphi.pk).exists())
        self.assertFalse(IndicatorSet.objects.filter(pk=removed_non_delphi.pk).exists())

    def test_delphi_import_only_deletes_other_delphi_sets(self):
        non_delphi_set = IndicatorSet.objects.create(
            name="Non-delphi set",
            source_type="non_delphi",
        )
        kept_delphi = IndicatorSet.objects.create(
            name="Kept delphi set",
            source_type="covidcast",
        )
        removed_delphi = IndicatorSet.objects.create(
            name="Removed delphi set",
            source_type="other_endpoint",
        )

        resource = IndicatorSetResource()
        resource.imported_rows_pks = [kept_delphi.pk]
        resource.after_import(None, None, dry_run=False)

        self.assertTrue(IndicatorSet.objects.filter(pk=non_delphi_set.pk).exists())
        self.assertTrue(IndicatorSet.objects.filter(pk=kept_delphi.pk).exists())
        self.assertFalse(IndicatorSet.objects.filter(pk=removed_delphi.pk).exists())


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
    def test_parse_original_data_provider_ids_from_comma_separated_odp(self):
        provider = OriginalDataProvider.objects.create(name="Acme Labs")
        query_dict = QueryDict(f"odp={provider.id},999")
        self.assertEqual(
            parse_original_data_provider_ids(query_dict),
            [provider.id, 999],
        )

    def test_parse_original_data_provider_ids_from_repeated_odp_params(self):
        provider_one = OriginalDataProvider.objects.create(name="Provider One")
        provider_two = OriginalDataProvider.objects.create(name="Provider Two")
        query_dict = QueryDict(mutable=True)
        query_dict.setlist(
            "odp",
            [str(provider_one.id), str(provider_two.id)],
        )
        self.assertEqual(
            parse_original_data_provider_ids(query_dict),
            [provider_one.id, provider_two.id],
        )

    def test_parse_original_data_provider_ids_from_legacy_names(self):
        provider = OriginalDataProvider.objects.create(name="Acme Labs")
        query_dict = QueryDict(mutable=True)
        query_dict.setlist("original_data_provider", [provider.name])
        self.assertEqual(parse_original_data_provider_ids(query_dict), [provider.id])

    def test_parse_original_data_provider_ids_deduplicates(self):
        provider = OriginalDataProvider.objects.create(name="Acme Labs")
        query_dict = QueryDict(f"odp={provider.id},{provider.id}")
        self.assertEqual(parse_original_data_provider_ids(query_dict), [provider.id])


class GeoCoverageUtilsTests(TestCase):
    @patch("indicatorsets.utils.geos.requests.get")
    def test_get_indicators_based_on_geo_epidata_returns_epidata_items(
        self, mock_get
    ):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "epidata": [{"source": "src", "signal": "sig"}]
        }
        mock_get.return_value = mock_response

        result = get_indicators_based_on_geo_epidata({"state": ["pa"]})
        self.assertEqual(result, [{"source": "src", "signal": "sig"}])

    @patch("indicatorsets.utils.geos.requests.get", side_effect=requests.RequestException)
    def test_get_indicators_based_on_geo_epidata_handles_errors(self, _mock_get):
        result = get_indicators_based_on_geo_epidata({"state": ["pa"]})
        self.assertEqual(result, [])

    @patch("indicatorsets.utils.geos.requests.get")
    def test_get_indicators_based_on_geo_epidata_v5_returns_values_items(
        self, mock_get
    ):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "values": [{"source": "src", "signal": "sig"}]
        }
        mock_get.return_value = mock_response

        result = get_indicators_based_on_geo_epidata_v5({"state": ["PA"]})
        self.assertEqual(result, [{"source": "src", "signal": "sig"}])
        self.assertEqual(mock_get.call_args.kwargs["params"]["geo_value"], "pa")

    @patch("indicatorsets.utils.geos.requests.get", side_effect=requests.RequestException)
    def test_get_indicators_based_on_geo_epidata_v5_handles_errors(self, _mock_get):
        result = get_indicators_based_on_geo_epidata_v5({"state": ["pa"]})
        self.assertEqual(result, [])

    @patch("indicatorsets.utils.geos.requests.get")
    def test_get_list_of_indicators_filtered_by_geo_combines_both_sources(
        self, mock_get
    ):
        def fake_get(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            if "geo_coverage" in url:
                response.json.return_value = {
                    "epidata": [{"source": "epidata_src", "signal": "epidata_sig"}]
                }
            else:
                response.json.return_value = {
                    "values": [{"source": "v5_src", "signal": "v5_sig"}]
                }
            return response

        mock_get.side_effect = fake_get

        result = get_list_of_indicators_filtered_by_geo("['state:pa']")
        self.assertEqual(
            result,
            [
                {"source": "epidata_src", "signal": "epidata_sig"},
                {"source": "v5_src", "signal": "v5_sig"},
            ],
        )

    @patch("indicatorsets.utils.geos.requests.get", side_effect=requests.RequestException)
    def test_get_list_of_indicators_filtered_by_geo_handles_errors(self, _mock_get):
        result = get_list_of_indicators_filtered_by_geo("['state:pa']")
        self.assertEqual(result, [])


class GetPreviewDataTests(TestCase):
    def test_json_epidata_shape_returns_first_row(self):
        response = MagicMock()
        response.json.return_value = {
            "epidata": [{"value": 1}, {"value": 2}],
            "result": 1,
            "message": "success",
        }
        result = get_preview_data(response, "json")
        self.assertEqual(
            result, {"epidata": {"value": 1}, "result": 1, "message": "success"}
        )

    def test_json_epidata_shape_empty_returns_no_data_message(self):
        response = MagicMock()
        response.json.return_value = {"epidata": [], "result": -2, "message": "no results"}
        self.assertEqual(get_preview_data(response, "json"), {"message": NO_DATA_MESSAGE})

    def test_json_list_shape_returns_first_item(self):
        response = MagicMock()
        response.json.return_value = [{"value": 1}, {"value": 2}]
        self.assertEqual(get_preview_data(response, "json"), {"value": 1})

    def test_json_list_shape_empty_returns_no_data_message(self):
        response = MagicMock()
        response.json.return_value = []
        self.assertEqual(get_preview_data(response, "json"), {"message": NO_DATA_MESSAGE})

    def test_csv_returns_first_five_rows(self):
        response = MagicMock()
        rows = ["geo_value,value"] + [f"pa,{i}" for i in range(10)]
        response.text = "\n".join(rows)
        result = get_preview_data(response, "csv")
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], ["geo_value", "value"])
        self.assertEqual(result[1], ["pa", "0"])

    def test_csv_header_only_returns_no_data_message(self):
        response = MagicMock()
        response.text = "geo_value,value"
        self.assertEqual(get_preview_data(response, "csv"), {"message": NO_DATA_MESSAGE})

    def test_csv_empty_returns_no_data_message(self):
        response = MagicMock()
        response.text = ""
        self.assertEqual(get_preview_data(response, "csv"), {"message": NO_DATA_MESSAGE})

    def test_json_empty_uses_custom_no_data_message(self):
        response = MagicMock()
        response.json.return_value = {"epidata": [], "result": -2, "message": "no results"}
        result = get_preview_data(response, "json", no_data_message="No data for signal X.")
        self.assertEqual(result, {"message": "No data for signal X."})

    def test_csv_empty_uses_custom_no_data_message(self):
        response = MagicMock()
        response.text = "geo_value,value"
        result = get_preview_data(response, "csv", no_data_message="No data for signal X.")
        self.assertEqual(result, {"message": "No data for signal X."})


class PreviewCovidcastDataTests(TestCase):
    @patch("indicatorsets.utils.previews.requests.get")
    def test_no_data_message_names_indicator_and_geo_type(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"epidata": [], "result": -2, "message": "no results"}
        mock_get.return_value = mock_response

        result = preview_covidcast_data(
            [
                {
                    "_endpoint": "covidcast",
                    "data_source": "src",
                    "indicator": "sig",
                    "time_type": "day",
                    "display_name": "My Signal",
                }
            ],
            "2020-01-01",
            "2020-01-20",
            {"state": [{"id": "state:pa", "geoType": "state"}]},
            None,
            "json",
        )
        self.assertEqual(result, [{"message": "No data found for My Signal (state)."}])

    @patch("indicatorsets.utils.previews.requests.get")
    def test_shows_data_for_available_geo_and_message_for_unavailable_geo(self, mock_get):
        def fake_get(url, params=None, timeout=None):
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status = MagicMock()
            if params["geo_type"] == "state":
                response.json.return_value = {
                    "epidata": [{"value": 1}],
                    "result": 1,
                    "message": "success",
                }
            else:
                response.json.return_value = {"epidata": [], "result": -2, "message": "no results"}
            return response

        mock_get.side_effect = fake_get

        result = preview_covidcast_data(
            [
                {
                    "_endpoint": "covidcast",
                    "data_source": "src",
                    "indicator": "sig",
                    "time_type": "day",
                    "display_name": "My Signal",
                }
            ],
            "2020-01-01",
            "2020-01-20",
            {
                "state": [{"id": "state:pa", "geoType": "state"}],
                "county": [{"id": "county:42003", "geoType": "county"}],
            },
            None,
            "json",
        )
        self.assertIn({"epidata": {"value": 1}, "result": 1, "message": "success"}, result)
        self.assertIn({"message": "No data found for My Signal (county)."}, result)


class PreviewFluviewDataTests(TestCase):
    @patch("indicatorsets.utils.previews.requests.get")
    def test_csv_format_returns_parsed_rows(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "release_date,region,value\n2020-01-01,nat,1.5\n"
        mock_get.return_value = mock_response

        result = preview_epiweek_data(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat", "text": "U.S. National"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "csv",
            [],
        )
        self.assertEqual(
            result, [[["release_date", "region", "value"], ["2020-01-01", "nat", "1.5"]]]
        )

    @patch("indicatorsets.utils.previews.requests.get")
    def test_json_format_returns_first_epidata_row(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "epidata": [{"value": 1}],
            "result": 1,
            "message": "success",
        }
        mock_get.return_value = mock_response

        result = preview_epiweek_data(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat", "text": "U.S. National"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "json",
            [],
        )
        self.assertEqual(result[0]["epidata"], {"value": 1})


class PreviewNIDSSFluDataTests(TestCase):
    @patch("indicatorsets.utils.previews.requests.get")
    def test_csv_format_returns_parsed_rows(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "epiweek,region,ili\n202001,taipei,2\n"
        mock_get.return_value = mock_response

        result = preview_epiweek_data(
            EPIWEEK_SOURCES["nidss_flu"],
            [{"id": "taipei", "text": "Taipei"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "csv",
            [],
        )
        self.assertEqual(
            result, [[["epiweek", "region", "ili"], ["202001", "taipei", "2"]]]
        )


class PreviewNIDSSDengueDataTests(TestCase):
    @patch("indicatorsets.utils.previews.requests.get")
    def test_csv_format_returns_parsed_rows(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "epiweek,location,count\n202001,taipei,3\n"
        mock_get.return_value = mock_response

        result = preview_epiweek_data(
            EPIWEEK_SOURCES["nidss_dengue"],
            [{"id": "taipei", "text": "Taipei"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "csv",
            [],
        )
        self.assertEqual(
            result, [[["epiweek", "location", "count"], ["202001", "taipei", "3"]]]
        )


class PreviewFlusurvDataTests(TestCase):
    @patch("indicatorsets.utils.previews.requests.get")
    def test_csv_format_returns_parsed_rows(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "epiweek,location,rate\n202001,CA,1.1\n"
        mock_get.return_value = mock_response

        result = preview_epiweek_data(
            EPIWEEK_SOURCES["flusurv"],
            [{"id": "CA", "text": "CA"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "csv",
            [],
        )
        self.assertEqual(
            result, [[["epiweek", "location", "rate"], ["202001", "CA", "1.1"]]]
        )


class PreviewPophiveDataTests(TestCase):
    @patch("indicatorsets.utils.previews.requests.get")
    def test_csv_format_returns_parsed_rows(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "geo_value,value\nca,5\n"
        mock_get.return_value = mock_response

        result = preview_pophive_data(
            [{"_endpoint": "pophive", "indicator": "sig"}],
            "2020-01-01",
            "2020-01-20",
            [{"id": "ca", "geo_type": "state", "text": "CA"}],
            [{"id": "all"}],
            None,
            "csv",
        )
        self.assertEqual(result, [[["geo_value", "value"], ["ca", "5"]]])

    @patch("indicatorsets.utils.previews.requests.get")
    def test_json_format_returns_first_item(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [{"value": 5}]
        mock_get.return_value = mock_response

        result = preview_pophive_data(
            [{"_endpoint": "pophive", "indicator": "sig"}],
            "2020-01-01",
            "2020-01-20",
            [{"id": "ca", "geo_type": "state", "text": "CA"}],
            [{"id": "all"}],
            None,
            "json",
        )
        self.assertEqual(result, [{"value": 5}])

    @patch("indicatorsets.utils.previews.requests.get")
    def test_no_data_message_names_indicator_and_geo(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = preview_pophive_data(
            [{"_endpoint": "pophive", "indicator": "sig", "display_name": "My Signal"}],
            "2020-01-01",
            "2020-01-20",
            [{"id": "ca", "geo_type": "state", "text": "CA"}],
            [{"id": "all"}],
            None,
            "json",
        )
        self.assertEqual(result, [{"message": "No data found for My Signal (CA)."}])


class PreviewNwssDataTests(TestCase):
    @patch("indicatorsets.utils.previews.requests.get")
    def test_csv_format_appends_parsed_rows(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "geo_value,value\nsewershed_1,3\n"
        mock_get.return_value = mock_response

        result = preview_nwss_data(
            [{"_endpoint": "nwss", "indicator": "sig"}],
            "2020-01-01",
            "2020-01-20",
            ["sewershed_1"],
            [{"id": "CDC_Biobot"}],
            "source",
            None,
            "csv",
        )
        self.assertEqual(result, [[["geo_value", "value"], ["sewershed_1", "3"]]])

    @patch("indicatorsets.utils.previews.requests.get")
    def test_json_format_returns_first_item(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [{"value": 3}]
        mock_get.return_value = mock_response

        result = preview_nwss_data(
            [{"_endpoint": "nwss", "indicator": "sig"}],
            "2020-01-01",
            "2020-01-20",
            ["sewershed_1"],
            [{"id": "CDC_Biobot"}],
            "source",
            None,
            "json",
        )
        self.assertEqual(result, [{"value": 3}])

    @patch("indicatorsets.utils.previews.requests.get")
    def test_no_data_message_names_indicator_and_source(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = preview_nwss_data(
            [{"_endpoint": "nwss", "indicator": "sig", "display_name": "My Signal"}],
            "2020-01-01",
            "2020-01-20",
            ["sewershed_1"],
            [{"id": "CDC_Biobot"}],
            "source",
            None,
            "json",
        )
        self.assertEqual(
            result, [{"message": "No data found for My Signal (source: CDC_Biobot)."}]
        )


class PreviewDataViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("indicatorsets.utils.previews.requests.get")
    def test_csv_format_returns_json_response_with_parsed_rows(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "release_date,region,value\n2020-01-01,nat,1.5\n"
        mock_get.return_value = mock_response

        payload = {
            "start_date": "2020-01-01",
            "end_date": "2020-01-20",
            "indicators": [],
            "covidCastGeographicValues": {},
            "fluviewLocations": [{"id": "nat", "text": "U.S. National"}],
            "dataFormat": "csv",
        }
        response = self.client.post(
            reverse("preview_data"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertEqual(
            data, [[["release_date", "region", "value"], ["2020-01-01", "nat", "1.5"]]]
        )

    @patch("indicatorsets.utils.previews.requests.get")
    def test_csv_format_returns_no_data_message_when_no_rows(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "release_date,region,value"
        mock_get.return_value = mock_response

        payload = {
            "start_date": "2020-01-01",
            "end_date": "2020-01-20",
            "indicators": [],
            "covidCastGeographicValues": {},
            "fluviewLocations": [{"id": "nat", "text": "U.S. National"}],
            "dataFormat": "csv",
        }
        response = self.client.post(
            reverse("preview_data"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data, [{"message": NO_DATA_MESSAGE}])

    def test_no_sources_selected_returns_no_data_message(self):
        payload = {
            "start_date": "2020-01-01",
            "end_date": "2020-01-20",
            "indicators": [],
            "covidCastGeographicValues": {},
            "dataFormat": "json",
        }
        response = self.client.post(
            reverse("preview_data"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data, [{"message": NO_DATA_MESSAGE}])


class GenerateCovidcastIndicatorsExportUrlTests(TestCase):
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_skips_indicator_with_no_data(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"epidata": [], "result": -2, "message": "no results"}
        mock_get.return_value = mock_response

        result = generate_covidcast_indicators_export_url(
            [
                {
                    "_endpoint": "covidcast",
                    "data_source": "src",
                    "indicator": "sig",
                    "time_type": "day",
                    "display_name": "My Signal",
                }
            ],
            "2020-01-01",
            "2020-01-20",
            {"state": [{"id": "state:pa", "geoType": "state"}]},
            None,
            "csv",
        )
        self.assertEqual(len(result), 1)
        self.assertIn("No data found for My Signal (state)", result[0])
        self.assertNotIn("wget", result[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_includes_export_command_when_data_exists(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "epidata": [{"value": 1}],
            "result": 1,
            "message": "success",
        }
        mock_get.return_value = mock_response

        result = generate_covidcast_indicators_export_url(
            [
                {
                    "_endpoint": "covidcast",
                    "data_source": "src",
                    "indicator": "sig",
                    "time_type": "day",
                    "display_name": "My Signal",
                }
            ],
            "2020-01-01",
            "2020-01-20",
            {"state": [{"id": "state:pa", "geoType": "state"}]},
            None,
            "csv",
        )
        self.assertEqual(len(result), 1)
        self.assertIn("wget", result[0])
        self.assertIn("covidcast/csv", result[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_mixed_indicators_only_skips_the_one_without_data(self, mock_get):
        def fake_get(url, params=None, timeout=None):
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status = MagicMock()
            if params["signal"] == "has_data":
                response.json.return_value = {
                    "epidata": [{"value": 1}],
                    "result": 1,
                    "message": "success",
                }
            else:
                response.json.return_value = {"epidata": [], "result": -2, "message": "no results"}
            return response

        mock_get.side_effect = fake_get

        indicators = [
            {
                "_endpoint": "covidcast",
                "data_source": "src",
                "indicator": "has_data",
                "time_type": "day",
                "display_name": "Has Data",
            },
            {
                "_endpoint": "covidcast",
                "data_source": "src",
                "indicator": "no_data",
                "time_type": "day",
                "display_name": "No Data",
            },
        ]
        result = generate_covidcast_indicators_export_url(
            indicators,
            "2020-01-01",
            "2020-01-20",
            {"state": [{"id": "state:pa", "geoType": "state"}]},
            None,
            "csv",
        )
        self.assertEqual(len(result), 2)
        self.assertTrue(any("wget" in r and "has_data" in r for r in result))
        self.assertTrue(any("No data found for No Data" in r for r in result))


class V5RoutingTestMixin:
    """Helpers for tests that exercise the v4/v5 routing in the covidcast export.

    Every module imports ``requests`` as a module, so patching
    ``<module>.requests.get`` patches the one shared ``requests.get``. A single
    patch therefore has to serve both the v5 metadata call and the availability
    probe; these helpers dispatch on the requested URL.
    """

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @staticmethod
    def _fake_get(
        metadata_signals=None,
        metadata_error=None,
        has_data=True,
        metadata_source="nhsn",
        metadata=None,
    ):
        """Fake requests.get dispatching on URL.

        ``metadata`` serves the whole v5 metadata payload verbatim, for cases
        that need more than one migrated source live at once; otherwise the
        single ``metadata_source``/``metadata_signals`` pair is wrapped into
        one.
        """

        def fake_get(url, params=None, timeout=None):
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status = MagicMock()
            if "metadata/" in url:
                if metadata_error is not None:
                    raise metadata_error
                response.json.return_value = (
                    metadata
                    if metadata is not None
                    else {metadata_source: {"signals": list(metadata_signals or [])}}
                )
                return response
            response.json.return_value = (
                {"epidata": [{"value": 1}], "result": 1, "message": "success"}
                if has_data
                else {"epidata": [], "result": -2, "message": "no results"}
            )
            return response

        return fake_get

    @staticmethod
    def _probe_calls(mock_get):
        return [
            call for call in mock_get.call_args_list if "metadata/" not in call.args[0]
        ]


class FluviewGeoMappingTests(TestCase):
    """Pins fluview's geo id -> v5 (geo_type, geo_value) mapping.

    Expectations are taken from the live v5 API rather than inferred: the
    geo_type list is fluview_ilinet's ``geo_types`` from v5 metadata, and the
    state geo_values are the 55 distinct values fluview_ilinet actually
    returns. Both fluview and fluview_clinical share this geo widget and
    expose the same geo_types, so one mapping serves both.
    """

    # fluview_ilinet / fluview_resp_lab_clinical geo_types in v5 metadata.
    V5_GEO_TYPES = {"census_division", "hhs", "nation", "state"}

    def test_geo_type_buckets_match_the_v5_vocabulary(self):
        ids = (
            ["nat"]
            + [f"hhs{n}" for n in range(1, 11)]
            + [f"cen{n}" for n in range(1, 10)]
            + ["PA", "ny", "jfk", "ny_minus_jfk", "pr", "vi"]
        )
        for geo_id in ids:
            with self.subTest(geo_id=geo_id):
                geo_type, _ = map_fluview_geo_to_v5(geo_id)
                self.assertIn(geo_type, self.V5_GEO_TYPES)

    def test_nation_hhs_and_census_division_ids(self):
        self.assertEqual(map_fluview_geo_to_v5("nat"), ("nation", "us"))
        self.assertEqual(map_fluview_geo_to_v5("hhs1"), ("hhs", "1"))
        self.assertEqual(map_fluview_geo_to_v5("hhs10"), ("hhs", "10"))
        self.assertEqual(map_fluview_geo_to_v5("cen9"), ("census_division", "9"))

    def test_state_ids_are_lowercased(self):
        self.assertEqual(map_fluview_geo_to_v5("PA"), ("state", "pa"))
        self.assertEqual(map_fluview_geo_to_v5("ny"), ("state", "ny"))
        self.assertEqual(map_fluview_geo_to_v5("pr"), ("state", "pr"))

    def test_new_york_city_ids_are_renamed_to_the_v5_spelling(self):
        """v4 keys these on JFK airport, v5 on the city. Verified to be the
        same series -- identical values for the same week on both APIs."""
        self.assertEqual(map_fluview_geo_to_v5("jfk"), ("state", "nyc"))
        self.assertEqual(
            map_fluview_geo_to_v5("ny_minus_jfk"), ("state", "ny_minus_nyc")
        )

    def test_grouping_buckets_by_geo_type_preserving_order(self):
        grouped = EPIWEEK_SOURCES["fluview"].group_geos_by_v5_type(
            [
                {"id": "nat"},
                {"id": "hhs3"},
                {"id": "cen2"},
                {"id": "PA"},
                {"id": "jfk"},
                {"id": "hhs1"},
            ]
        )
        self.assertEqual(
            grouped,
            {
                "nation": ["us"],
                "hhs": ["3", "1"],
                "census_division": ["2"],
                "state": ["pa", "nyc"],
            },
        )


class FlusurvGeoMappingTests(TestCase):
    """Pins flusurv's geo id -> v5 (geo_type, geo_value) mapping.

    Expectations are taken from the live v5 API rather than inferred: the
    geo_type list is flusurv's ``geo_types`` from v5 metadata, and the
    geo_values are the distinct values v5 flusurv actually returns for each
    of them. v5 keeps every v4 id intact but lowercases it and splits the
    flat picker list across two geo_types -- the FluSurv-Net sites and the
    participating states.
    """

    # flusurv's geo_types in v5 metadata.
    V5_GEO_TYPES = {"flusurv_site", "state"}

    # Every id the flusurv geo picker offers.
    PICKER_IDS = [
        "network_all",
        "network_eip",
        "network_ihsp",
        "CA",
        "CO",
        "CT",
        "GA",
        "IA",
        "ID",
        "MD",
        "MI",
        "MN",
        "NM",
        "NY_albany",
        "NY_rochester",
        "OH",
        "OK",
        "OR",
        "RI",
        "SD",
        "TN",
        "UT",
    ]

    def test_geo_type_buckets_match_the_v5_vocabulary(self):
        for geo_id in self.PICKER_IDS:
            with self.subTest(geo_id=geo_id):
                geo_type, _ = map_flusurv_geo_to_v5(geo_id)
                self.assertIn(geo_type, self.V5_GEO_TYPES)

    def test_network_ids_map_to_the_site_geo_type_unchanged(self):
        self.assertEqual(
            map_flusurv_geo_to_v5("network_all"), ("flusurv_site", "network_all")
        )
        self.assertEqual(
            map_flusurv_geo_to_v5("network_eip"), ("flusurv_site", "network_eip")
        )
        self.assertEqual(
            map_flusurv_geo_to_v5("network_ihsp"), ("flusurv_site", "network_ihsp")
        )

    def test_new_york_site_ids_are_sites_rather_than_states(self):
        """These two are FluSurv-Net catchment areas, not the state of NY."""
        self.assertEqual(
            map_flusurv_geo_to_v5("NY_albany"), ("flusurv_site", "ny_albany")
        )
        self.assertEqual(
            map_flusurv_geo_to_v5("NY_rochester"), ("flusurv_site", "ny_rochester")
        )

    def test_state_ids_are_lowercased(self):
        self.assertEqual(map_flusurv_geo_to_v5("CA"), ("state", "ca"))
        self.assertEqual(map_flusurv_geo_to_v5("UT"), ("state", "ut"))


class EpiweekSourceGeoGroupingTests(TestCase):
    """Each epiweek endpoint carries its own v5 geo mapper in the registry.

    Epiweek geo ids bake the geo type into the id itself, and every endpoint
    spells that differently, so the mapping cannot be shared. Routing it
    through the source keeps a single call site in previews, exports and
    query code.
    """

    def test_flusurv_splits_sites_from_states_preserving_order(self):
        grouped = EPIWEEK_SOURCES["flusurv"].group_geos_by_v5_type(
            [
                {"id": "network_all"},
                {"id": "CA"},
                {"id": "NY_albany"},
                {"id": "UT"},
                {"id": "network_eip"},
            ]
        )
        self.assertEqual(
            grouped,
            {
                "flusurv_site": ["network_all", "ny_albany", "network_eip"],
                "state": ["ca", "ut"],
            },
        )

    def test_fluview_uses_its_own_mapper(self):
        grouped = EPIWEEK_SOURCES["fluview"].group_geos_by_v5_type(
            [{"id": "nat"}, {"id": "hhs3"}, {"id": "PA"}]
        )
        self.assertEqual(grouped, {"nation": ["us"], "hhs": ["3"], "state": ["pa"]})

    def test_sources_that_have_not_migrated_group_to_nothing(self):
        """No mapper means no v5 request can be built, so no bucket is offered."""
        for key in ("nidss_flu", "nidss_dengue"):
            with self.subTest(source=key):
                self.assertEqual(
                    EPIWEEK_SOURCES[key].group_geos_by_v5_type([{"id": "taipei"}]),
                    {},
                )


class SafeCacheTests(TestCase):
    """A cache failure must be indistinguishable from a cache miss."""

    @patch("indicatorsets.utils.caching.cache")
    def test_get_returns_default_when_the_backend_raises(self, mock_cache):
        mock_cache.get.side_effect = ConnectionError("Connection refused")
        self.assertIsNone(safe_cache_get("some_key"))
        self.assertEqual(safe_cache_get("some_key", []), [])

    @patch("indicatorsets.utils.caching.cache")
    def test_get_returns_default_on_a_miss(self, mock_cache):
        mock_cache.get.return_value = None
        self.assertEqual(safe_cache_get("some_key", []), [])

    @patch("indicatorsets.utils.caching.cache")
    def test_get_returns_the_cached_value(self, mock_cache):
        mock_cache.get.return_value = {"nhsn": {}}
        self.assertEqual(safe_cache_get("some_key"), {"nhsn": {}})

    @patch("indicatorsets.utils.caching.cache")
    def test_set_swallows_backend_failures(self, mock_cache):
        mock_cache.set.side_effect = ConnectionError("Connection refused")
        safe_cache_set("some_key", "value", 60)  # must not raise
        mock_cache.set.assert_called_once_with("some_key", "value", 60)


class V5MetadataWithoutCacheTests(V5RoutingTestMixin, TestCase):
    """Exports must keep working when Redis is unreachable."""

    INDICATOR = {
        "_endpoint": "covidcast",
        "data_source": "nhsn",
        "indicator": "confirmed_admissions_covid_ew",
        "time_type": "week",
        "display_name": "COVID Admissions",
    }

    @patch("indicatorsets.utils.caching.cache")
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_metadata_is_fetched_when_the_cache_is_down(self, mock_get, mock_cache):
        mock_cache.get.side_effect = redis.exceptions.ConnectionError("refused")
        mock_cache.set.side_effect = redis.exceptions.ConnectionError("refused")
        mock_get.side_effect = self._fake_get(metadata_signals=["sig"])

        self.assertEqual(get_v5_metadata(), {"nhsn": {"signals": ["sig"]}})

    @patch("indicatorsets.utils.caching.cache")
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_still_routes_to_v5_when_the_cache_is_down(
        self, mock_get, mock_cache
    ):
        mock_cache.get.side_effect = redis.exceptions.ConnectionError("refused")
        mock_cache.set.side_effect = redis.exceptions.ConnectionError("refused")
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )

        result = generate_covidcast_indicators_export_url(
            [self.INDICATOR],
            "2020-01-01",
            "2020-01-20",
            {"state": [{"id": "state:pa", "geoType": "state"}]},
            None,
            "csv",
        )
        self.assertEqual(len(result), 1)
        self.assertIn("curl -o", result[0])
        self.assertIn("/v5/", result[0])
        # no caching means the metadata is re-fetched per indicator
        self.assertTrue(
            any("metadata/" in call.args[0] for call in mock_get.call_args_list)
        )


class GetV5SourceTests(V5RoutingTestMixin, TestCase):
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_skips_metadata_lookup_for_non_migrated_source(self, mock_get):
        self.assertIsNone(get_v5_source({"data_source": "src", "indicator": "sig"}))
        mock_get.assert_not_called()

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_true_when_signal_present_in_v5(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )
        self.assertEqual(
            get_v5_source(
                {"data_source": "nhsn", "indicator": "confirmed_admissions_covid_ew"}
            ),
            "nhsn",
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_false_when_migrated_source_lacks_the_signal(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )
        self.assertIsNone(
            get_v5_source({"data_source": "nhsn", "indicator": "not_in_v5"})
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_false_when_metadata_request_fails(self, mock_get):
        mock_get.side_effect = requests.RequestException("unavailable")
        self.assertIsNone(
            get_v5_source(
                {"data_source": "nhsn", "indicator": "confirmed_admissions_covid_ew"}
            )
        )
        self.assertIsNone(cache.get("epidata_v5_metadata"))

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_false_when_metadata_payload_is_not_a_mapping(self, mock_get):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = ["unexpected"]
        mock_get.return_value = response
        self.assertIsNone(
            get_v5_source(
                {"data_source": "nhsn", "indicator": "confirmed_admissions_covid_ew"}
            )
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_metadata_is_fetched_once_and_cached(self, mock_get):
        mock_get.side_effect = self._fake_get(metadata_signals=["inpatient_beds_ew"])
        get_v5_metadata()
        get_v5_source({"data_source": "nhsn", "indicator": "inpatient_beds_ew"})
        get_v5_source({"data_source": "nssp", "indicator": "pct_ed_visits_ari"})
        self.assertEqual(mock_get.call_count, 1)
        self.assertIn("nhsn", cache.get("epidata_v5_metadata"))


class CovidcastExportAuthParamTests(V5RoutingTestMixin, TestCase):
    """Availability probes and export URLs must carry the right key, the right way."""

    V5_INDICATOR = {
        "_endpoint": "covidcast",
        "data_source": "nhsn",
        "indicator": "confirmed_admissions_covid_ew",
        "time_type": "week",
        "display_name": "COVID Admissions",
    }
    V4_INDICATOR = {
        "_endpoint": "covidcast",
        "data_source": "src",
        "indicator": "sig",
        "time_type": "day",
        "display_name": "My Signal",
    }

    def _export(self, indicator, api_key):
        return generate_covidcast_indicators_export_url(
            [indicator],
            "2020-01-01",
            "2020-01-20",
            {"state": [{"id": "state:pa", "geoType": "state"}]},
            api_key,
            "csv",
        )

    @override_settings(EPIDATA_API_KEY="server-key")
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v4_probe_falls_back_to_server_api_key(self, mock_get):
        mock_get.side_effect = self._fake_get()

        result = self._export(self.V4_INDICATOR, None)
        probe_calls = self._probe_calls(mock_get)
        self.assertEqual(len(probe_calls), 1)
        self.assertIn("covidcast", probe_calls[0].args[0])
        self.assertEqual(probe_calls[0].kwargs["params"]["api_key"], "server-key")
        self.assertIn("wget", result[0])

    @override_settings(EPIDATA_API_KEY="server-key")
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v5_probe_falls_back_to_server_api_key(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )

        self._export(self.V5_INDICATOR, None)
        probe_calls = self._probe_calls(mock_get)
        self.assertEqual(len(probe_calls), 1)
        params = probe_calls[0].kwargs["params"]
        self.assertIn("/v5/", probe_calls[0].args[0])
        self.assertEqual(params["token"], "server-key")
        self.assertNotIn("api_key", params)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v5_uses_token_not_api_key_for_user_supplied_key(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )

        result = self._export(self.V5_INDICATOR, "user-key")
        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertEqual(params["token"], "user-key")
        self.assertNotIn("api_key", params)
        self.assertEqual(len(result), 1)
        self.assertIn("/v5/", result[0])
        self.assertIn("token=user-key", result[0])
        self.assertNotIn("api_key=", result[0])

    @override_settings(EPIDATA_API_KEY="server-key")
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_url_never_leaks_the_server_api_key(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )

        result = self._export(self.V5_INDICATOR, None)
        self.assertEqual(len(result), 1)
        self.assertIn("curl -o", result[0])
        self.assertNotIn("server-key", result[0])
        self.assertNotIn("token", result[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v4_probe_params_are_scalars(self, mock_get):
        mock_get.side_effect = self._fake_get()

        self._export(self.V4_INDICATOR, "user-key")
        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertEqual(params["data_source"], "src")
        self.assertEqual(params["geo_values"], "pa")
        for key, value in params.items():
            self.assertIsInstance(value, str, msg=f"{key} should be a plain string")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v5_probe_params_are_scalars(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )

        self._export(self.V5_INDICATOR, "user-key")
        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertEqual(params["source"], "nhsn")
        self.assertEqual(params["geo_value"], "pa")
        for key, value in params.items():
            self.assertIsInstance(value, str, msg=f"{key} should be a plain string")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v5_export_routes_through_the_download_proxy(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )

        result = self._export(self.V5_INDICATOR, "user-key")
        self.assertEqual(len(result), 1)
        command = result[0]
        filename = "nhsn_confirmed_admissions_covid_ew_state.csv"
        self.assertIn(f"curl -o {filename}", command)
        self.assertIn(f'download="{filename}"', command)
        self.assertNotIn("wget", command)

        href = re.search(r'href="([^"]+)"', command).group(1)
        self.assertTrue(href.startswith(reverse("download_export")))
        params = parse_qs(urlparse(href).query)
        self.assertEqual(params["source"], ["nhsn"])
        self.assertEqual(params["signal"], ["confirmed_admissions_covid_ew"])
        self.assertEqual(params["geo_type"], ["state"])
        self.assertEqual(params["geo_value"], ["pa"])
        self.assertEqual(params["reference_times"], ["2020-01-01:2020-01-20"])
        self.assertEqual(params["format"], ["csv"])
        self.assertEqual(params["header"], ["true"])
        self.assertEqual(params["filename"], [filename])
        self.assertEqual(params["token"], ["user-key"])
        # the raw API URL stays visible as the link text
        self.assertIn(f"{settings.EPIDATA_V5_URL}viz/?source=nhsn", command)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v4_export_still_uses_wget_against_the_api(self, mock_get):
        mock_get.side_effect = self._fake_get()

        result = self._export(self.V4_INDICATOR, "user-key")
        self.assertEqual(len(result), 1)
        self.assertIn("wget --content-disposition", result[0])
        self.assertIn("covidcast/csv", result[0])
        self.assertNotIn("curl -o", result[0])
        self.assertNotIn(reverse("download_export"), result[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v5_probe_omits_time_type(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )

        self._export(self.V5_INDICATOR, None)
        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertNotIn("time_type", params)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v4_probe_still_sends_time_type(self, mock_get):
        mock_get.side_effect = self._fake_get()

        self._export(self.V4_INDICATOR, None)
        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertEqual(params["time_type"], "day")

    @override_settings(EPIDATA_API_KEY="server-key")
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_falls_back_to_v4_when_metadata_unavailable(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_error=requests.RequestException("unavailable")
        )

        result = self._export(self.V5_INDICATOR, None)
        probe_calls = self._probe_calls(mock_get)
        self.assertEqual(len(probe_calls), 1)
        self.assertIn("covidcast", probe_calls[0].args[0])
        self.assertNotIn("/v5/", probe_calls[0].args[0])
        self.assertEqual(len(result), 1)
        self.assertIn("covidcast/csv", result[0])
        self.assertNotIn("/v5/", result[0])


class GenerateQueryCodeCovidcastTests(V5RoutingTestMixin, TestCase):
    GEOS = {
        "state": [
            {"id": "state:PA", "geoType": "state"},
            {"id": "state:NY", "geoType": "state"},
        ]
    }

    def _indicators(
        self, time_type="week", data_source="my-src", signals=("sig_a", "sig_b")
    ):
        return [
            {
                "_endpoint": "covidcast",
                "data_source": data_source,
                "indicator": signal,
                "time_type": time_type,
            }
            for signal in signals
        ]

    def _generate(self, indicators, data_source="my-src"):
        return generate_query_code_covidcast(
            indicators,
            self.GEOS,
            "2024-01-01",
            "2024-03-01",
            data_source,
            ",".join(i["indicator"] for i in indicators),
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_weekly_v4_snippets_are_unchanged(self, mock_get):
        mock_get.side_effect = self._fake_get()
        python_blocks, r_blocks = self._generate(self._indicators("week"))
        self.assertEqual(
            "".join(python_blocks),
            "my_src_state_df = epidata.pub_covidcast(\n"
            '    data_source="my-src",\n'
            '    signals="sig_a,sig_b",\n'
            '    geo_type="state",\n'
            '    time_type="week",\n'
            '    geo_values="pa,ny",\n'
            "    time_values=EpiRange(202401, 202409),\n"
            ").df()\n",
        )
        self.assertEqual(
            "".join(r_blocks),
            "epidata_my_src_state <- pub_covidcast(\n"
            '    source = "my-src",\n'
            '    signals = "sig_a,sig_b",\n'
            '    geo_type = "state",\n'
            '    time_type = "week",\n'
            '    geo_values = "pa,ny",\n'
            "    time_values = epirange(202401, 202409)\n"
            ")\n",
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_migrated_signals_get_v5_client_snippets(self, mock_get):
        mock_get.side_effect = self._fake_get(metadata_signals=["sig_a", "sig_b"])

        python_blocks, r_blocks = self._generate(
            self._indicators("week", data_source="nhsn"), data_source="nhsn"
        )
        python_code = "".join(python_blocks)
        r_code = "".join(r_blocks)

        self.assertNotIn("pub_covidcast", python_code)
        self.assertNotIn("pub_covidcast", r_code)
        self.assertNotIn("requests.get(", python_code)
        self.assertNotIn("library(httr)", r_blocks)
        self.assertNotIn("library(jsonlite)", r_blocks)
        # both clients have a v5 client and batch every migrated signal into one call
        self.assertIn(
            "nhsn_state_v5_df = epidata.epidata_snapshot(\n"
            '    source="nhsn",\n'
            '    signals=["sig_a", "sig_b"],\n'
            '    geo_type="state",\n'
            '    geo_values=["pa", "ny"],\n'
            '    reference_time=EpiRange("2024-01-01", "2024-03-01"),\n'
            ").df()\n",
            python_code,
        )
        self.assertIn(
            "epidata_nhsn_state_v5 <- epidata_snapshot(\n"
            '    source = "nhsn",\n'
            '    signals = c("sig_a", "sig_b"),\n'
            '    geo_type = "state",\n'
            '    geo_values = c("pa", "ny"),\n'
            '    reference_time = epirange("2024-01-01", "2024-03-01")\n'
            ")\n",
            r_code,
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_mixed_group_splits_between_v5_and_v4(self, mock_get):
        mock_get.side_effect = self._fake_get(metadata_signals=["sig_a"])

        python_blocks, _ = self._generate(
            self._indicators("week", data_source="nhsn"), data_source="nhsn"
        )
        python_code = "".join(python_blocks)

        # sig_a is on v5, sig_b is not
        self.assertIn("epidata.epidata_snapshot(", python_code)
        self.assertIn('signals=["sig_a"],', python_code)
        self.assertIn("epidata.pub_covidcast(", python_code)
        self.assertIn('signals="sig_b",', python_code)
        self.assertNotIn("sig_a,sig_b", python_code)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_falls_back_to_v4_snippets_when_metadata_unavailable(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_error=requests.RequestException("unavailable")
        )

        python_blocks, _ = self._generate(
            self._indicators("week", data_source="nhsn"), data_source="nhsn"
        )
        python_code = "".join(python_blocks)
        self.assertIn("epidata.pub_covidcast(", python_code)
        self.assertIn('signals="sig_a,sig_b",', python_code)
        self.assertNotIn("requests.get(", python_code)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_daily_v4_snippets_are_unchanged(self, mock_get):
        mock_get.side_effect = self._fake_get()
        python_blocks, r_blocks = self._generate(self._indicators("day"))
        self.assertEqual(
            "".join(python_blocks),
            "my_src_state_df = epidata.pub_covidcast(\n"
            '    data_source="my-src",\n'
            '    signals="sig_a,sig_b",\n'
            '    geo_type="state",\n'
            '    time_type="day",\n'
            '    geo_values="pa,ny",\n'
            "    time_values=EpiRange(20240101, 20240301),\n"
            ").df()\n",
        )
        self.assertEqual(
            "".join(r_blocks),
            "epidata_my_src_state <- pub_covidcast(\n"
            '    source = "my-src",\n'
            '    signals = "sig_a,sig_b",\n'
            '    geo_type = "state",\n'
            '    time_type = "day",\n'
            '    geo_values = "pa,ny",\n'
            "    time_values = epirange(20240101, 20240301)\n"
            ")\n",
        )


class GenerateQueryCodePophiveTests(TestCase):
    GEOS = [
        {"id": "ca", "geo_type": "state", "text": "CA"},
        {"id": "06001", "geo_type": "county", "text": "Alameda"},
    ]
    AGE_GROUP = [{"id": "0-17"}]

    def _indicators(self, endpoint="pophive", signals=("sig_a", "sig_b")):
        return [{"_endpoint": endpoint, "indicator": signal} for signal in signals]

    def test_batches_every_signal_into_one_call_per_geo(self):
        python_blocks, r_blocks = generate_query_code_pophive(
            self._indicators(), "2024-01-01", "2024-03-01", self.GEOS, self.AGE_GROUP
        )
        self.assertEqual(
            "".join(python_blocks),
            "pophive_state_ca_df = epidata.epidata_snapshot(\n"
            '    source="pophive",\n'
            '    signals=["sig_a", "sig_b"],\n'
            '    geo_type="state",\n'
            '    geo_values="ca",\n'
            '    reference_time=EpiRange("2024-01-01", "2024-03-01"),\n'
            ").df()\n"
            'pophive_state_ca_df = pophive_state_ca_df[pophive_state_ca_df["age_group"] == "0-17"]\n'
            "pophive_county_06001_df = epidata.epidata_snapshot(\n"
            '    source="pophive",\n'
            '    signals=["sig_a", "sig_b"],\n'
            '    geo_type="county",\n'
            '    geo_values="06001",\n'
            '    reference_time=EpiRange("2024-01-01", "2024-03-01"),\n'
            ").df()\n"
            'pophive_county_06001_df = pophive_county_06001_df[pophive_county_06001_df["age_group"] == "0-17"]\n',
        )
        self.assertEqual(
            "".join(r_blocks),
            "epidata_pophive_state_ca <- epidata_snapshot(\n"
            '    source = "pophive",\n'
            '    signals = c("sig_a", "sig_b"),\n'
            '    geo_type = "state",\n'
            '    geo_values = "ca",\n'
            '    reference_time = epirange("2024-01-01", "2024-03-01"),\n'
            '    age_group = "0-17"\n'
            ")\n"
            "epidata_pophive_county_06001 <- epidata_snapshot(\n"
            '    source = "pophive",\n'
            '    signals = c("sig_a", "sig_b"),\n'
            '    geo_type = "county",\n'
            '    geo_values = "06001",\n'
            '    reference_time = epirange("2024-01-01", "2024-03-01"),\n'
            '    age_group = "0-17"\n'
            ")\n",
        )

    def test_ignores_non_pophive_indicators(self):
        indicators = self._indicators() + self._indicators(
            endpoint="covidcast", signals=("other",)
        )
        python_blocks, _ = generate_query_code_pophive(
            indicators, "2024-01-01", "2024-03-01", self.GEOS[:1], self.AGE_GROUP
        )
        python_code = "".join(python_blocks)
        self.assertNotIn("other", python_code)
        self.assertIn('signals=["sig_a", "sig_b"]', python_code)

    def test_returns_nothing_when_no_pophive_indicators(self):
        python_blocks, r_blocks = generate_query_code_pophive(
            self._indicators(endpoint="covidcast"),
            "2024-01-01",
            "2024-03-01",
            self.GEOS,
            self.AGE_GROUP,
        )
        self.assertEqual(python_blocks, [])
        self.assertEqual(r_blocks, [])


class GenerateQueryCodeNwssTests(TestCase):
    SOURCES = [{"id": "CDC_Biobot"}, {"id": "CDC_Verily"}]

    def _indicators(self, endpoint="nwss", signals=("sig_a", "sig_b")):
        return [{"_endpoint": endpoint, "indicator": signal} for signal in signals]

    def test_batches_every_signal_into_one_call_per_source(self):
        python_blocks, r_blocks = generate_query_code_nwss(
            self._indicators(),
            "2024-01-01",
            "2024-03-01",
            ["sewershed_1", "sewershed_2"],
            self.SOURCES,
            "fill_ave",
        )
        self.assertEqual(
            "".join(python_blocks),
            "nwss_source_CDC_Biobot_df = epidata.epidata_snapshot(\n"
            '    source="nwss",\n'
            '    signals=["sig_a", "sig_b"],\n'
            '    geo_type="sewershed",\n'
            '    geo_values=["sewershed_1", "sewershed_2"],\n'
            '    reference_time=EpiRange("2024-01-01", "2024-03-01"),\n'
            '    fill_method="fill_ave",\n'
            ").df()\n"
            'nwss_source_CDC_Biobot_df = nwss_source_CDC_Biobot_df[nwss_source_CDC_Biobot_df["nwss_source"] == "CDC_Biobot"]\n'
            "nwss_source_CDC_Verily_df = epidata.epidata_snapshot(\n"
            '    source="nwss",\n'
            '    signals=["sig_a", "sig_b"],\n'
            '    geo_type="sewershed",\n'
            '    geo_values=["sewershed_1", "sewershed_2"],\n'
            '    reference_time=EpiRange("2024-01-01", "2024-03-01"),\n'
            '    fill_method="fill_ave",\n'
            ").df()\n"
            'nwss_source_CDC_Verily_df = nwss_source_CDC_Verily_df[nwss_source_CDC_Verily_df["nwss_source"] == "CDC_Verily"]\n',
        )
        self.assertEqual(
            "".join(r_blocks),
            "epidata_nwss_source_CDC_Biobot <- epidata_snapshot(\n"
            '    source = "nwss",\n'
            '    signals = c("sig_a", "sig_b"),\n'
            '    geo_type = "sewershed",\n'
            '    geo_values = c("sewershed_1", "sewershed_2"),\n'
            '    reference_time = epirange("2024-01-01", "2024-03-01"),\n'
            '    fill_method = "fill_ave",\n'
            '    nwss_source = "CDC_Biobot"\n'
            ")\n"
            "epidata_nwss_source_CDC_Verily <- epidata_snapshot(\n"
            '    source = "nwss",\n'
            '    signals = c("sig_a", "sig_b"),\n'
            '    geo_type = "sewershed",\n'
            '    geo_values = c("sewershed_1", "sewershed_2"),\n'
            '    reference_time = epirange("2024-01-01", "2024-03-01"),\n'
            '    fill_method = "fill_ave",\n'
            '    nwss_source = "CDC_Verily"\n'
            ")\n",
        )

    def test_ignores_non_nwss_indicators(self):
        indicators = self._indicators() + self._indicators(
            endpoint="pophive", signals=("other",)
        )
        python_blocks, _ = generate_query_code_nwss(
            indicators,
            "2024-01-01",
            "2024-03-01",
            ["sewershed_1"],
            self.SOURCES[:1],
            "source",
        )
        python_code = "".join(python_blocks)
        self.assertNotIn("other", python_code)

    def test_returns_nothing_when_no_nwss_indicators(self):
        python_blocks, r_blocks = generate_query_code_nwss(
            self._indicators(endpoint="pophive"),
            "2024-01-01",
            "2024-03-01",
            ["sewershed_1"],
            self.SOURCES,
            "source",
        )
        self.assertEqual(python_blocks, [])
        self.assertEqual(r_blocks, [])


class PreviewCovidcastRoutingTests(V5RoutingTestMixin, TestCase):
    V5_INDICATOR = {
        "_endpoint": "covidcast",
        "data_source": "nhsn",
        "indicator": "confirmed_admissions_covid_ew",
        "time_type": "week",
        "display_name": "COVID Admissions",
    }
    V4_INDICATOR = {
        "_endpoint": "covidcast",
        "data_source": "src",
        "indicator": "sig",
        "time_type": "week",
        "display_name": "My Signal",
    }

    def _preview(self, indicator, api_key=None):
        return preview_covidcast_data(
            [indicator],
            "2020-01-01",
            "2020-01-20",
            {"state": [{"id": "state:pa", "geoType": "state"}]},
            api_key,
            "json",
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v4_indicator_is_previewed_from_v4(self, mock_get):
        mock_get.side_effect = self._fake_get()

        self._preview(self.V4_INDICATOR)
        calls = self._probe_calls(mock_get)
        self.assertEqual(len(calls), 1)
        params = calls[0].kwargs["params"]
        self.assertNotIn("/v5/", calls[0].args[0])
        self.assertEqual(params["data_source"], "src")
        self.assertEqual(params["geo_values"], "pa")
        # weekly v4 previews keep epiweek time values
        self.assertEqual(params["time_values"], "202001-202004")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_migrated_indicator_is_previewed_from_v5(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )

        self._preview(self.V5_INDICATOR, api_key="user-key")
        calls = self._probe_calls(mock_get)
        self.assertEqual(len(calls), 1)
        params = calls[0].kwargs["params"]
        self.assertIn("/v5/viz/", calls[0].args[0])
        self.assertEqual(params["source"], "nhsn")
        self.assertEqual(params["geo_value"], "pa")
        self.assertEqual(params["reference_times"], "2020-01-01:2020-01-20")
        self.assertEqual(params["token"], "user-key")
        self.assertNotIn("data_source", params)
        self.assertNotIn("geo_values", params)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v5_preview_omits_time_type(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )

        self._preview(self.V5_INDICATOR)
        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertNotIn("time_type", params)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v4_preview_still_sends_time_type(self, mock_get):
        mock_get.side_effect = self._fake_get()

        self._preview(self.V4_INDICATOR)
        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertEqual(params["time_type"], "week")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_preview_falls_back_to_v4_when_metadata_unavailable(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_error=requests.RequestException("unavailable")
        )

        self._preview(self.V5_INDICATOR)
        calls = self._probe_calls(mock_get)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("/v5/", calls[0].args[0])
        self.assertEqual(calls[0].kwargs["params"]["data_source"], "nhsn")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_preview_and_export_agree_on_the_endpoint(self, mock_get):
        """The point of the fix: one selection must not straddle two APIs."""
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )

        self._preview(self.V5_INDICATOR)
        preview_url = self._probe_calls(mock_get)[0].args[0]

        mock_get.reset_mock()
        cache.clear()
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )
        generate_covidcast_indicators_export_url(
            [self.V5_INDICATOR],
            "2020-01-01",
            "2020-01-20",
            {"state": [{"id": "state:pa", "geoType": "state"}]},
            None,
            "csv",
        )
        export_probe_url = self._probe_calls(mock_get)[0].args[0]

        self.assertIn("/v5/", preview_url)
        self.assertEqual(preview_url, export_probe_url)


@patch.dict(
    "indicatorsets.utils.constants.MIGRATED_DATASOURCES",
    {"nhsn": "nhsn_renamed_in_v5"},
    clear=True,
)
class RenamedV5SourceTests(V5RoutingTestMixin, TestCase):
    """A source whose v5 name differs from its v4 name must query the v5 name.

    Every real MIGRATED_DATASOURCES entry maps a name to itself, so only a
    non-identity mapping can catch a call site that reuses the v4 name.
    """

    INDICATOR = {
        "_endpoint": "covidcast",
        "data_source": "nhsn",
        "indicator": "confirmed_admissions_covid_ew",
        "time_type": "week",
        "display_name": "COVID Admissions",
    }
    GEOS = {"state": [{"id": "state:pa", "geoType": "state"}]}

    def _renamed_fake_get(self):
        return self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"],
            metadata_source="nhsn_renamed_in_v5",
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_resolver_returns_the_v5_name(self, mock_get):
        mock_get.side_effect = self._renamed_fake_get()
        self.assertEqual(get_v5_source(self.INDICATOR), "nhsn_renamed_in_v5")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_uses_the_v5_name_everywhere(self, mock_get):
        mock_get.side_effect = self._renamed_fake_get()

        result = generate_covidcast_indicators_export_url(
            [self.INDICATOR], "2020-01-01", "2020-01-20", self.GEOS, None, "csv"
        )
        probe_params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertEqual(probe_params["source"], "nhsn_renamed_in_v5")

        href = re.search(r'href="([^"]+)"', result[0]).group(1)
        self.assertEqual(
            parse_qs(urlparse(href).query)["source"], ["nhsn_renamed_in_v5"]
        )
        # the visible link text is a real v5 URL, so it carries the v5 name too
        self.assertIn("viz/?source=nhsn_renamed_in_v5", result[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_preview_uses_the_v5_name(self, mock_get):
        mock_get.side_effect = self._renamed_fake_get()

        preview_covidcast_data(
            [self.INDICATOR], "2020-01-01", "2020-01-20", self.GEOS, None, "json"
        )
        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertEqual(params["source"], "nhsn_renamed_in_v5")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_query_code_uses_the_v5_name(self, mock_get):
        mock_get.side_effect = self._renamed_fake_get()

        python_blocks, r_blocks = generate_query_code_covidcast(
            [self.INDICATOR],
            self.GEOS,
            "2020-01-01",
            "2020-01-20",
            "nhsn",
            "confirmed_admissions_covid_ew",
        )
        python_code = "".join(python_blocks)
        r_code = "".join(r_blocks)
        self.assertIn('source="nhsn_renamed_in_v5"', python_code)
        self.assertIn('source = "nhsn_renamed_in_v5"', r_code)
        self.assertNotIn('source="nhsn"', python_code)
        self.assertNotIn('source = "nhsn"', r_code)


class DownloadVizExportTests(TestCase):
    UPSTREAM_CSV = b"signal,value\nconfirmed_admissions_covid_ew,1\n"

    def test_rejects_source_outside_the_allowlist(self):
        response = self.client.get(
            reverse("download_export"), {"source": "not_a_source"}
        )
        self.assertEqual(response.status_code, 400)

    def test_migrated_covidcast_sources_are_allowed(self):
        for source in MIGRATED_DATASOURCES.values():
            self.assertIn(source, VIZ_SOURCES)

    @patch("indicatorsets.proxy_views.requests.get")
    def test_serves_migrated_covidcast_source_with_content_disposition(self, mock_get):
        upstream = MagicMock()
        upstream.status_code = 200
        upstream.raise_for_status = MagicMock()
        upstream.content = self.UPSTREAM_CSV
        upstream.headers = {"Content-Type": "text/csv; charset=utf-8"}
        mock_get.return_value = upstream

        filename = "nhsn_confirmed_admissions_covid_ew_state.csv"
        response = self.client.get(
            reverse("download_export"),
            {
                "source": "nhsn",
                "signal": "confirmed_admissions_covid_ew",
                "geo_type": "state",
                "geo_value": "pa",
                "reference_times": "2020-01-01:2020-01-20",
                "format": "csv",
                "header": "true",
                "filename": filename,
                "token": "user-key",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.UPSTREAM_CSV)
        self.assertEqual(
            response["Content-Disposition"], f'attachment; filename="{filename}"'
        )
        forwarded = mock_get.call_args.kwargs["params"]
        self.assertEqual(forwarded["source"], "nhsn")
        self.assertEqual(forwarded["signal"], "confirmed_admissions_covid_ew")
        self.assertEqual(forwarded["geo_value"], "pa")
        self.assertEqual(forwarded["reference_times"], "2020-01-01:2020-01-20")
        self.assertEqual(forwarded["token"], "user-key")


class GeneratePophiveExportUrlTests(TestCase):
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_skips_indicator_with_no_data(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = generate_pophive_export_url(
            [
                {
                    "_endpoint": "pophive",
                    "indicator": "sig",
                    "display_name": "My Signal",
                }
            ],
            "2020-01-01",
            "2020-01-20",
            [{"id": "ca", "geo_type": "state", "text": "CA"}],
            [{"id": "all"}],
            None,
            "csv",
        )
        self.assertEqual(len(result), 1)
        self.assertIn("No data found for My Signal (CA)", result[0])
        self.assertNotIn("curl", result[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_includes_export_command_when_data_exists(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [{"value": 5}]
        mock_get.return_value = mock_response

        result = generate_pophive_export_url(
            [
                {
                    "_endpoint": "pophive",
                    "indicator": "sig",
                    "display_name": "My Signal",
                }
            ],
            "2020-01-01",
            "2020-01-20",
            [{"id": "ca", "geo_type": "state", "text": "CA"}],
            [{"id": "all"}],
            None,
            "csv",
        )
        self.assertEqual(len(result), 1)
        self.assertIn("curl", result[0])


class GenerateNwssExportUrlTests(TestCase):
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_skips_indicator_with_no_data(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = generate_nwss_export_url(
            [
                {
                    "_endpoint": "nwss",
                    "indicator": "sig",
                    "display_name": "My Signal",
                }
            ],
            "2020-01-01",
            "2020-01-20",
            ["sewershed_1"],
            [{"id": "CDC_Biobot"}],
            "source",
            None,
            "csv",
        )
        self.assertEqual(len(result), 1)
        self.assertIn("No data found for My Signal (source: CDC_Biobot)", result[0])
        self.assertNotIn("curl", result[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_includes_export_command_when_data_exists(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [{"value": 3}]
        mock_get.return_value = mock_response

        result = generate_nwss_export_url(
            [
                {
                    "_endpoint": "nwss",
                    "indicator": "sig",
                    "display_name": "My Signal",
                }
            ],
            "2020-01-01",
            "2020-01-20",
            ["sewershed_1"],
            [{"id": "CDC_Biobot"}],
            "source",
            None,
            "csv",
        )
        self.assertEqual(len(result), 1)
        self.assertIn("curl", result[0])


class LogFormDataTests(TestCase):
    """log_form_data must tolerate a payload with no covidcast geos.

    Its default for covidCastGeographicValues was [], but the value is used as
    a dict, so any request omitting the key raised AttributeError and the view
    returned a 500.
    """

    def test_missing_covidcast_geos_does_not_raise(self):
        request = RequestFactory().post("/")
        log_form_data(request, {"indicators": []}, "export")

    def test_null_covidcast_geos_does_not_raise(self):
        request = RequestFactory().post("/")
        log_form_data(
            request, {"indicators": [], "covidCastGeographicValues": None}, "export"
        )

    def test_log_form_stats_tolerates_missing_and_null_covidcast_geos(self):
        """log_form_stats runs before log_form_data in every view, so it needs
        the same tolerance or the null case still 500s."""
        request = RequestFactory().post("/")
        log_form_stats(request, {"indicators": []}, "export")
        log_form_stats(
            request, {"indicators": [], "covidCastGeographicValues": None}, "export"
        )

    def test_covidcast_geos_are_still_flattened_when_present(self):
        request = RequestFactory().post("/")
        with patch("indicatorsets.utils.form_logging.form_data_logger") as mock_logger:
            log_form_data(
                request,
                {
                    "indicators": [],
                    "covidCastGeographicValues": {
                        "state": [{"id": "state:pa", "text": "Pennsylvania"}]
                    },
                },
                "export",
            )
        self.assertEqual(
            mock_logger.info.call_args.kwargs["covidcast_geos"],
            [{"geo_type": "state", "geo_value": "pa", "geo_text": "Pennsylvania"}],
        )


class ExportViewWithoutCovidcastGeosTests(TestCase):
    """Regression test: the export endpoint must not 500 when the payload omits
    covidCastGeographicValues."""

    def test_export_succeeds_without_covidcast_geos_key(self):
        response = self.client.post(
            reverse("export"),
            data=json.dumps(
                {
                    "start_date": "2024-01-01",
                    "end_date": "2024-02-01",
                    "indicators": [],
                    "flusurvLocations": [{"id": "network_all"}],
                    "dataFormat": "csv",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)


@override_settings(EPIVIS_URL="https://epivis.example.com/")
class EpivisViewEndpointRoutingTests(TestCase):
    """End-to-end check that the epivis view routes each endpoint to the right
    builder: fluview to its dedicated one, the other epiweek sources to the
    generic one.

    Registry-free and network-free so it runs identically before and after the
    generic builders were collapsed into one.
    """

    def _datasets(self, payload):
        response = self.client.post(
            reverse("epivis"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        encoded = response.json()["epivis_url"].split("#", 1)[1]
        return json.loads(base64.b64decode(encoded).decode("ascii"))["datasets"]

    def test_fluview_keeps_its_dedicated_payload(self):
        datasets = self._datasets(
            {
                "indicators": [
                    {
                        "_endpoint": "fluview",
                        "data_source": "fluview",
                        "indicator": "wili",
                        "indicator_set_short_name": "FluView",
                    }
                ],
                "covidCastGeographicValues": {},
                "fluviewLocations": [{"id": "nat", "text": "U.S. National"}],
            }
        )
        self.assertEqual(len(datasets), 1)
        # the mapped display title is fluview-specific behaviour
        self.assertEqual(datasets[0]["title"], "%wILI")
        self.assertEqual(datasets[0]["params"]["regions"], "nat")

    def test_other_epiweek_sources_use_the_generic_payload(self):
        for endpoint, form_key, geo_param in (
            ("nidss_flu", "nidssFluLocations", "regions"),
            ("nidss_dengue", "nidssDengueLocations", "locations"),
            ("flusurv", "flusurvLocations", "locations"),
        ):
            with self.subTest(endpoint=endpoint):
                datasets = self._datasets(
                    {
                        "indicators": [
                            {
                                "_endpoint": endpoint,
                                "data_source": endpoint,
                                "indicator": "ili",
                                "indicator_set_short_name": "SRC",
                            }
                        ],
                        "covidCastGeographicValues": {},
                        form_key: [{"id": "taipei", "text": "Taipei"}],
                    }
                )
                self.assertEqual(len(datasets), 1)
                self.assertEqual(datasets[0]["title"], "ili")
                self.assertEqual(datasets[0]["params"][geo_param], "taipei")
                self.assertEqual(datasets[0]["params"]["_endpoint"], endpoint)
                self.assertEqual(
                    datasets[0]["params"]["custom_title"], "SRC:ili : Taipei"
                )

    def test_no_geos_selected_yields_bare_epivis_url(self):
        response = self.client.post(
            reverse("epivis"),
            data=json.dumps(
                {
                    "indicators": [
                        {
                            "_endpoint": "flusurv",
                            "data_source": "flusurv",
                            "indicator": "ili",
                            "indicator_set_short_name": "SRC",
                        }
                    ],
                    "covidCastGeographicValues": {},
                    "flusurvLocations": [],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["epivis_url"], "https://epivis.example.com/")


class EpiweekEpivisDatasetTests(TestCase):
    """Characterization tests for the generic epiweek EpiVis dataset payload.

    fluview is deliberately excluded: it has its own title mapping, a
    notCoveredGeos filter and a fluview_clinical endpoint fallback, so it keeps
    a dedicated builder.
    """

    INDICATOR = {
        "_endpoint": "nidss_flu",
        "indicator": "ili",
        "indicator_set_short_name": "NIDSS",
    }
    GEOS = [{"id": "taipei", "text": "Taipei"}, {"id": "nat", "text": "Nationwide"}]

    def _expected(self, geo_param):
        return [
            {
                "color": "#abcdef",
                "title": "ili",
                "params": {
                    "_endpoint": "nidss_flu",
                    geo_param: geo_id,
                    "custom_title": f"NIDSS:ili : {geo_text}",
                },
            }
            for geo_id, geo_text in (("taipei", "Taipei"), ("nat", "Nationwide"))
        ]

    def test_generic_epiweek_sources_share_one_payload_shape(self):
        for endpoint, geo_param in (
            ("nidss_flu", "regions"),
            ("nidss_dengue", "locations"),
            ("flusurv", "locations"),
        ):
            with self.subTest(endpoint=endpoint):
                with patch(
                    "indicatorsets.utils.epivis.generate_random_color",
                    return_value="#abcdef",
                ):
                    datasets = generate_epiweek_dataset_epivis(
                        EPIWEEK_SOURCES[endpoint], self.INDICATOR, self.GEOS
                    )
                self.assertEqual(datasets, self._expected(geo_param))

    def test_endpoint_comes_from_the_indicator_not_the_source(self):
        """The payload's _endpoint is read off the indicator record, so a
        nidss_flu indicator keeps that endpoint even when built via another
        source's geo parameter."""
        with patch(
            "indicatorsets.utils.epivis.generate_random_color", return_value="#abcdef"
        ):
            datasets = generate_epiweek_dataset_epivis(
                EPIWEEK_SOURCES["flusurv"], self.INDICATOR, self.GEOS
            )
        self.assertEqual(
            [d["params"]["_endpoint"] for d in datasets], ["nidss_flu", "nidss_flu"]
        )

    def test_empty_geos_yields_no_datasets(self):
        self.assertEqual(
            generate_epiweek_dataset_epivis(
                EPIWEEK_SOURCES["flusurv"], self.INDICATOR, []
            ),
            [],
        )


@override_settings(
    EPIDATA_URL="https://api.example.com/epidata/", EPIDATA_API_KEY="default-key"
)
class EpiweekPreviewRequestTests(TestCase):
    """Characterization tests for the outgoing request each epiweek preview makes.

    The existing Preview*DataTests cover response parsing; these pin the request
    itself -- endpoint path (no trailing slash), geo parameter name, and the
    401/network error paths.
    """

    GEOS = [{"id": "nat", "text": "U.S. National"}]
    CASES = [
        ("fluview", "regions"),
        ("nidss_flu", "regions"),
        ("nidss_dengue", "locations"),
        ("flusurv", "locations"),
    ]

    @staticmethod
    def _preview(endpoint, *args):
        return preview_epiweek_data(EPIWEEK_SOURCES[endpoint], *args, [])

    def test_request_url_and_params(self):
        for endpoint, geo_param in self.CASES:
            with self.subTest(endpoint=endpoint):
                with patch("indicatorsets.utils.previews.requests.get") as mock_get:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.text = "a,b\n1,2\n"
                    mock_get.return_value = mock_response
                    self._preview(
                        endpoint, self.GEOS, "2020-01-01", "2020-01-20", None, "csv"
                    )
                self.assertEqual(
                    mock_get.call_args.args[0],
                    f"https://api.example.com/epidata/{endpoint}",
                )
                self.assertEqual(
                    mock_get.call_args.kwargs["params"],
                    {
                        geo_param: "nat",
                        "epiweeks": "202001-202004",
                        "api_key": "default-key",
                        "format": "csv",
                        "header": "true",
                    },
                )
                self.assertEqual(mock_get.call_args.kwargs["timeout"], (5, 30))

    def test_explicit_api_key_overrides_default_and_json_drops_header(self):
        for endpoint, geo_param in self.CASES:
            with self.subTest(endpoint=endpoint):
                with patch("indicatorsets.utils.previews.requests.get") as mock_get:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"epidata": [], "result": 1}
                    mock_get.return_value = mock_response
                    self._preview(
                        endpoint, self.GEOS, "2020-01-01", "2020-01-20", "mine", "json"
                    )
                params = mock_get.call_args.kwargs["params"]
                self.assertEqual(params["api_key"], "mine")
                self.assertEqual(params["format"], "json")
                self.assertEqual(params["header"], "false")

    def test_401_raises_invalid_api_key_error(self):
        for endpoint, _geo_param in self.CASES:
            with self.subTest(endpoint=endpoint):
                with patch("indicatorsets.utils.previews.requests.get") as mock_get:
                    mock_response = MagicMock()
                    mock_response.status_code = 401
                    mock_get.return_value = mock_response
                    with self.assertRaises(InvalidApiKeyError):
                        self._preview(
                            endpoint,
                            self.GEOS,
                            "2020-01-01",
                            "2020-01-20",
                            "bad",
                            "csv",
                        )

    def test_network_error_returns_empty_list(self):
        for endpoint, _geo_param in self.CASES:
            with self.subTest(endpoint=endpoint):
                with patch(
                    "indicatorsets.utils.previews.requests.get",
                    side_effect=requests.RequestException,
                ):
                    self.assertEqual(
                        self._preview(
                            endpoint, self.GEOS, "2020-01-01", "2020-01-20", None, "csv"
                        ),
                        [],
                    )


class EpiweekPreviewV5RoutingTests(V5RoutingTestMixin, TestCase):
    """Epiweek previews must route migrated signals to v5, using the real v5
    param names (reference_times/token), and keep the v4 fallback for anything
    else.

    One epiweek endpoint can cover several data sources, which migrate
    independently and map to different v5 sources, so routing has to be per
    data source rather than per endpoint. fluview is the case that exists
    today (ILINet plus clinical labs) and stands in for the general rule.
    """

    def _indicators(self, signals=("wili",), data_source="fluview"):
        return [
            {"_endpoint": "fluview", "data_source": data_source, "indicator": signal}
            for signal in signals
        ]

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_migrated_signal_is_previewed_from_v5(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["wili"], metadata_source="fluview_ilinet"
        )

        preview_epiweek_data(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}, {"id": "hhs3"}],
            "2020-01-01",
            "2020-01-20",
            "user-key",
            "json",
            self._indicators(),
        )
        calls = self._probe_calls(mock_get)
        self.assertEqual(len(calls), 2)
        params_by_geo_type = {
            call.kwargs["params"]["geo_type"]: call.kwargs["params"] for call in calls
        }
        self.assertIn("/v5/viz/", calls[0].args[0])
        self.assertEqual(params_by_geo_type["nation"]["source"], "fluview_ilinet")
        self.assertEqual(params_by_geo_type["nation"]["geo_value"], "us")
        self.assertEqual(params_by_geo_type["hhs"]["geo_value"], "3")
        for params in params_by_geo_type.values():
            self.assertEqual(params["reference_times"], "2020-01-01:2020-01-20")
            self.assertEqual(params["token"], "user-key")
            self.assertNotIn("api_key", params)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_partially_migrated_keeps_v4_fallback(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["wili"], metadata_source="fluview_ilinet"
        )

        preview_epiweek_data(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "json",
            self._indicators(signals=["wili", "ili"]),
        )
        calls = self._probe_calls(mock_get)
        v5_calls = [c for c in calls if "/v5/" in c.args[0]]
        v4_calls = [c for c in calls if "/v5/" not in c.args[0]]
        self.assertEqual(len(v5_calls), 1)
        self.assertEqual(len(v4_calls), 1)
        self.assertIn("fluview", v4_calls[0].args[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_unmigrated_source_only_hits_v4(self, mock_get):
        mock_get.side_effect = self._fake_get()

        preview_epiweek_data(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "json",
            self._indicators(),
        )
        calls = self._probe_calls(mock_get)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("/v5/", calls[0].args[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_unmigrated_fluview_clinical_hits_the_clinical_v4_endpoint(self, mock_get):
        """A second data source under the same _endpoint/geo widget is still
        a distinct v4 endpoint, and must not be queried as the first one."""
        mock_get.side_effect = self._fake_get()

        preview_epiweek_data(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "json",
            self._indicators(data_source="fluview_clinical"),
        )
        calls = self._probe_calls(mock_get)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].args[0].endswith("fluview_clinical"))

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_mixed_fluview_and_fluview_clinical_hit_both_v4_endpoints(self, mock_get):
        mock_get.side_effect = self._fake_get()

        preview_epiweek_data(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "json",
            self._indicators(signals=["wili"], data_source="fluview")
            + self._indicators(signals=["ili"], data_source="fluview_clinical"),
        )
        calls = self._probe_calls(mock_get)
        self.assertEqual(len(calls), 2)
        urls = {call.args[0] for call in calls}
        self.assertIn(f"{settings.EPIDATA_URL}fluview", urls)
        self.assertIn(f"{settings.EPIDATA_URL}fluview_clinical", urls)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_two_migrated_v5_sources_are_previewed_from_their_own_source(
        self, mock_get
    ):
        """Each migrated signal must be previewed from the v5 source it
        actually belongs to, not from whichever one came first in the group."""
        mock_get.side_effect = self._fake_get(
            metadata={
                "fluview_ilinet": {"signals": ["wili"]},
                "fluview_resp_lab_clinical": {"signals": ["pct_positive"]},
            }
        )

        preview_epiweek_data(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "json",
            self._indicators(signals=["wili"], data_source="fluview")
            + self._indicators(
                signals=["pct_positive"], data_source="fluview_clinical"
            ),
        )
        calls = self._probe_calls(mock_get)
        self.assertEqual(len(calls), 2)
        source_by_signal = {
            call.kwargs["params"]["signal"]: call.kwargs["params"]["source"]
            for call in calls
        }
        self.assertEqual(
            source_by_signal,
            {"wili": "fluview_ilinet", "pct_positive": "fluview_resp_lab_clinical"},
        )


class QueryCodeViewEpiweekOrderingTests(TestCase):
    """End-to-end check that create_query_code emits one snippet pair per
    selected epiweek source, in registry order, skipping unselected ones.

    Registry-free and network-free so it runs identically before and after the
    per-source generators were collapsed into one.
    """

    def _post(self, payload):
        return self.client.post(
            reverse("create_query_code"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_snippets_appear_in_source_order(self):
        response = self._post(
            {
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
                "indicators": [],
                "covidCastGeographicValues": {},
                "fluviewLocations": [{"id": "nat"}],
                "nidssFluLocations": [{"id": "taipei"}],
                "nidssDengueLocations": [{"id": "taipei"}],
                "flusurvLocations": [{"id": "network_all"}],
            }
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            [line for line in body["python_code_blocks"] if "epidata.pub_" in line],
            [
                'fluview_df = epidata.pub_fluview(\n    regions="nat",\n'
                '    epiweeks="202401-202405",\n).df()\n',
                'nidss_flu_df = epidata.pub_nidss_flu(\n    regions="taipei",\n'
                '    epiweeks="202401-202405",\n).df()\n',
                'nidss_dengue_df = epidata.pub_nidss_dengue(\n    locations="taipei",\n'
                '    epiweeks="202401-202405",\n).df()\n',
                'flusurv_df = epidata.pub_flusurv(\n    locations="network_all",\n'
                '    epiweeks="202401-202405",\n).df()\n',
            ],
        )
        self.assertEqual(
            [line for line in body["r_code_blocks"] if "<- pub_" in line],
            [
                'epidata_fluview <- pub_fluview(\n    regions = "nat",\n'
                "    epiweeks = epirange(202401, 202405)\n)\n",
                'epidata_nidss_flu <- pub_nidss_flu(\n    regions = "taipei",\n'
                "    epiweeks = epirange(202401, 202405)\n)\n",
                'epidata_nidss_dengue <- pub_nidss_dengue(\n    locations = "taipei",\n'
                "    epiweeks = epirange(202401, 202405)\n)\n",
                'epidata_flusurv <- pub_flusurv(\n    locations = "network_all",\n'
                "    epiweeks = epirange(202401, 202405)\n)\n",
            ],
        )

    def test_unselected_sources_are_skipped(self):
        response = self._post(
            {
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
                "indicators": [],
                "covidCastGeographicValues": {},
                "fluviewLocations": [],
                "flusurvLocations": [{"id": "network_all"}],
            }
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            [line for line in body["python_code_blocks"] if "epidata.pub_" in line],
            [
                'flusurv_df = epidata.pub_flusurv(\n    locations="network_all",\n'
                '    epiweeks="202401-202405",\n).df()\n'
            ],
        )


class EpiweekQueryCodeTests(V5RoutingTestMixin, TestCase):
    """Characterization tests for the epiweek query-code generators.

    Each of these endpoints emits one epidatpy snippet and one epidatr snippet,
    differing only in the client function name and the geo argument name.
    fluview is also in MIGRATED_DATASOURCES, so every case here touches
    get_v5_source and needs the v5 metadata call mocked -- even the ones
    asserting the unmigrated v4-only output.
    """

    GEOS = [{"id": "nat"}, {"id": "hhs1"}]
    START = "2024-01-01"
    END = "2024-02-01"

    def _indicators(self, endpoint, signals=("some_signal",), data_source=None):
        return [
            {
                "_endpoint": endpoint,
                "data_source": data_source or endpoint,
                "indicator": signal,
            }
            for signal in signals
        ]

    def _expected(self, endpoint, geo_param):
        python_block = (
            f"{endpoint}_df = epidata.pub_{endpoint}(\n"
            f'    {geo_param}="nat,hhs1",\n'
            f'    epiweeks="202401-202405",\n'
            ").df()\n"
        )
        r_block = (
            f"epidata_{endpoint} <- pub_{endpoint}(\n"
            f'    {geo_param} = "nat,hhs1",\n'
            "    epiweeks = epirange(202401, 202405)\n"
            ")\n"
        )
        return [python_block], [r_block]

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_fluview_query_code_exact_strings(self, mock_get):
        """One fully literal anchor, independent of the template helper above."""
        mock_get.side_effect = self._fake_get()
        python_blocks, r_blocks = generate_query_code_epiweek(
            EPIWEEK_SOURCES["fluview"],
            self.GEOS,
            self.START,
            self.END,
            self._indicators("fluview"),
        )
        self.assertEqual(
            python_blocks,
            [
                'fluview_df = epidata.pub_fluview(\n    regions="nat,hhs1",\n'
                '    epiweeks="202401-202405",\n).df()\n'
            ],
        )
        self.assertEqual(
            r_blocks,
            [
                'epidata_fluview <- pub_fluview(\n    regions = "nat,hhs1",\n'
                "    epiweeks = epirange(202401, 202405)\n)\n"
            ],
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_query_code_for_all_epiweek_sources(self, mock_get):
        mock_get.side_effect = self._fake_get()
        for endpoint, source in EPIWEEK_SOURCES.items():
            with self.subTest(endpoint=endpoint):
                self.assertEqual(
                    generate_query_code_epiweek(
                        source,
                        self.GEOS,
                        self.START,
                        self.END,
                        self._indicators(endpoint),
                    ),
                    self._expected(endpoint, source.geo_param),
                )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_migrated_fluview_signal_gets_v5_snippet_and_drops_v4(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["wili"], metadata_source="fluview_ilinet"
        )
        geos = [{"id": "nat"}, {"id": "hhs3"}, {"id": "cen2"}, {"id": "PA"}]
        python_blocks, r_blocks = generate_query_code_epiweek(
            EPIWEEK_SOURCES["fluview"],
            geos,
            self.START,
            self.END,
            self._indicators("fluview", signals=["wili"]),
        )
        python_code = "".join(python_blocks)
        r_code = "".join(r_blocks)
        self.assertNotIn("pub_fluview", python_code)
        self.assertNotIn("pub_fluview", r_code)
        self.assertIn(
            "fluview_ilinet_nation_v5_df = epidata.epidata_snapshot(\n"
            '    source="fluview_ilinet",\n'
            '    signals=["wili"],\n'
            '    geo_type="nation",\n'
            '    geo_values=["us"],\n'
            '    reference_time=EpiRange("2024-01-01", "2024-02-01"),\n'
            ").df()\n",
            python_code,
        )
        self.assertIn(
            "fluview_ilinet_hhs_v5_df = epidata.epidata_snapshot(\n"
            '    source="fluview_ilinet",\n'
            '    signals=["wili"],\n'
            '    geo_type="hhs",\n'
            '    geo_values=["3"],\n'
            '    reference_time=EpiRange("2024-01-01", "2024-02-01"),\n'
            ").df()\n",
            python_code,
        )
        self.assertIn(
            "fluview_ilinet_census_division_v5_df = epidata.epidata_snapshot(\n"
            '    source="fluview_ilinet",\n'
            '    signals=["wili"],\n'
            '    geo_type="census_division",\n'
            '    geo_values=["2"],\n'
            '    reference_time=EpiRange("2024-01-01", "2024-02-01"),\n'
            ").df()\n",
            python_code,
        )
        self.assertIn(
            "fluview_ilinet_state_v5_df = epidata.epidata_snapshot(\n"
            '    source="fluview_ilinet",\n'
            '    signals=["wili"],\n'
            '    geo_type="state",\n'
            '    geo_values=["pa"],\n'
            '    reference_time=EpiRange("2024-01-01", "2024-02-01"),\n'
            ").df()\n",
            python_code,
        )
        self.assertIn(
            "epidata_fluview_ilinet_nation_v5 <- epidata_snapshot(\n"
            '    source = "fluview_ilinet",\n'
            '    signals = c("wili"),\n'
            '    geo_type = "nation",\n'
            '    geo_values = c("us"),\n'
            '    reference_time = epirange("2024-01-01", "2024-02-01")\n'
            ")\n",
            r_code,
        )

    BOTH_FLUVIEW_SOURCES_V5 = {
        "fluview_ilinet": {"signals": ["wili"]},
        "fluview_resp_lab_clinical": {"signals": ["pct_positive"]},
    }

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_two_migrated_v5_sources_get_separate_snapshot_calls(self, mock_get):
        """Data sources sharing one _endpoint can map to different v5
        sources, so their signals must not be batched into a single call --
        that would ask one v5 source for another's signal."""
        mock_get.side_effect = self._fake_get(metadata=self.BOTH_FLUVIEW_SOURCES_V5)
        indicators = self._indicators(
            "fluview", signals=["wili"], data_source="fluview"
        ) + self._indicators(
            "fluview", signals=["pct_positive"], data_source="fluview_clinical"
        )
        python_blocks, _ = generate_query_code_epiweek(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}],
            self.START,
            self.END,
            indicators,
        )
        python_code = "".join(python_blocks)
        # Two separate snapshot calls, each asking its own source for its own
        # signal -- and no v4 fallback, since everything migrated.
        self.assertEqual(len(python_blocks), 2)
        self.assertNotIn("pub_fluview", python_code)
        self.assertIn(
            "fluview_ilinet_nation_v5_df = epidata.epidata_snapshot(\n"
            '    source="fluview_ilinet",\n'
            '    signals=["wili"],\n',
            python_code,
        )
        self.assertIn(
            "fluview_resp_lab_clinical_nation_v5_df = epidata.epidata_snapshot(\n"
            '    source="fluview_resp_lab_clinical",\n'
            '    signals=["pct_positive"],\n',
            python_code,
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_two_migrated_v5_sources_do_not_clobber_variable_names(self, mock_get):
        """Each v5 source needs its own dataframe variable; sharing one name
        would make the second assignment silently overwrite the first."""
        mock_get.side_effect = self._fake_get(metadata=self.BOTH_FLUVIEW_SOURCES_V5)
        indicators = self._indicators(
            "fluview", signals=["wili"], data_source="fluview"
        ) + self._indicators(
            "fluview", signals=["pct_positive"], data_source="fluview_clinical"
        )
        python_blocks, r_blocks = generate_query_code_epiweek(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}, {"id": "hhs3"}],
            self.START,
            self.END,
            indicators,
        )
        for blocks, sep in ((python_blocks, "_df ="), (r_blocks, " <-")):
            names = [block.split(sep)[0].strip() for block in blocks]
            self.assertEqual(len(names), 4)
            self.assertEqual(len(set(names)), len(names), names)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_partially_migrated_fluview_keeps_v4_call(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["wili"], metadata_source="fluview_ilinet"
        )
        python_blocks, _ = generate_query_code_epiweek(
            EPIWEEK_SOURCES["fluview"],
            self.GEOS,
            self.START,
            self.END,
            self._indicators("fluview", signals=["wili", "ili"]),
        )
        python_code = "".join(python_blocks)
        # wili is migrated and gets its own snapshot call...
        self.assertIn("epidata.epidata_snapshot(", python_code)
        self.assertIn('signals=["wili"],', python_code)
        # ...but ili isn't, so the old unfiltered pub_fluview call stays
        self.assertIn("epidata.pub_fluview(", python_code)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_fluview_clinical_indicators_are_not_migrated(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["wili"], metadata_source="fluview_ilinet"
        )
        python_blocks, r_blocks = generate_query_code_epiweek(
            EPIWEEK_SOURCES["fluview"],
            self.GEOS,
            self.START,
            self.END,
            self._indicators(
                "fluview", signals=["wili"], data_source="fluview_clinical"
            ),
        )
        python_code = "".join(python_blocks)
        r_code = "".join(r_blocks)
        # Shares the endpoint/geo widget, but is a distinct v4 source that
        # must not be folded into the other source's call.
        self.assertNotIn("epidata_snapshot", python_code)
        self.assertNotIn("pub_fluview(", python_code)
        self.assertIn("epidata.pub_fluview_clinical(", python_code)
        self.assertIn("pub_fluview_clinical(", r_code)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_mixed_fluview_and_fluview_clinical_emit_separate_v4_calls(self, mock_get):
        mock_get.side_effect = self._fake_get()
        indicators = self._indicators(
            "fluview", signals=["wili"], data_source="fluview"
        ) + self._indicators("fluview", signals=["ili"], data_source="fluview_clinical")
        python_blocks, r_blocks = generate_query_code_epiweek(
            EPIWEEK_SOURCES["fluview"],
            self.GEOS,
            self.START,
            self.END,
            indicators,
        )
        python_code = "".join(python_blocks)
        r_code = "".join(r_blocks)
        self.assertIn("fluview_df = epidata.pub_fluview(", python_code)
        self.assertIn(
            "fluview_clinical_df = epidata.pub_fluview_clinical(", python_code
        )
        self.assertIn("epidata_fluview <- pub_fluview(", r_code)
        self.assertIn("epidata_fluview_clinical <- pub_fluview_clinical(", r_code)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_ignores_indicators_from_other_endpoints(self, mock_get):
        mock_get.side_effect = self._fake_get()
        python_blocks, _ = generate_query_code_epiweek(
            EPIWEEK_SOURCES["fluview"],
            self.GEOS,
            self.START,
            self.END,
            self._indicators("nidss_flu"),
        )
        # source_indicators ends up empty, so this behaves exactly like the
        # v4-only case: the unfiltered pub_fluview call is still emitted.
        self.assertEqual(
            python_blocks,
            [
                'fluview_df = epidata.pub_fluview(\n    regions="nat,hhs1",\n'
                '    epiweeks="202401-202405",\n).df()\n'
            ],
        )


@override_settings(EPIDATA_URL="https://api.example.com/epidata/")
class EpiweekExportUrlTests(TestCase):
    """Characterization tests for the epiweek-based export URL builders.

    These endpoints (fluview, nidss_flu, nidss_dengue, flusurv) share one query
    shape and differ only in path segment and geo parameter name.
    """

    GEOS = [{"id": "nat"}, {"id": "hhs1"}]
    START = "2024-01-01"
    END = "2024-02-01"

    def _expected(self, endpoint, geo_param, data_format, api_key):
        url = (
            f"https://api.example.com/epidata/{endpoint}/"
            f"?{geo_param}=nat,hhs1&epiweeks=202401-202405&format={data_format}"
        )
        if data_format == "csv":
            url += "&header=true"
        if api_key:
            url += f"&api_key={api_key}"
        return [f'wget --content-disposition <a href="{url}">{url}</a>']

    def test_fluview_export_url_exact_string(self):
        """One fully literal anchor, independent of the template helper above."""
        expected = (
            "wget --content-disposition "
            '<a href="https://api.example.com/epidata/fluview/?regions=nat,hhs1'
            '&epiweeks=202401-202405&format=csv&header=true&api_key=secret-key">'
            "https://api.example.com/epidata/fluview/?regions=nat,hhs1"
            "&epiweeks=202401-202405&format=csv&header=true&api_key=secret-key</a>"
        )
        self.assertEqual(
            generate_epiweek_export_url(
                EPIWEEK_SOURCES["fluview"],
                self.GEOS,
                self.START,
                self.END,
                "secret-key",
                "csv",
                [],
            ),
            [expected],
        )

    def test_export_urls_for_all_epiweek_sources(self):
        expected_geo_params = {
            "fluview": "regions",
            "nidss_flu": "regions",
            "nidss_dengue": "locations",
            "flusurv": "locations",
        }
        self.assertEqual(set(EPIWEEK_SOURCES), set(expected_geo_params))
        for endpoint, geo_param in expected_geo_params.items():
            source = EPIWEEK_SOURCES[endpoint]
            self.assertEqual(source.geo_param, geo_param)
            for data_format in ("csv", "json"):
                for api_key in ("secret-key", None):
                    with self.subTest(
                        endpoint=endpoint,
                        data_format=data_format,
                        with_api_key=bool(api_key),
                    ):
                        self.assertEqual(
                            generate_epiweek_export_url(
                                source,
                                self.GEOS,
                                self.START,
                                self.END,
                                api_key,
                                data_format,
                                [],
                            ),
                            self._expected(endpoint, geo_param, data_format, api_key),
                        )


class EpiweekExportUrlV5RoutingTests(V5RoutingTestMixin, TestCase):
    """Epiweek exports must route migrated signals to v5, using the real v5
    param names (reference_times/token), and keep the v4 fallback for anything
    else.

    One epiweek endpoint can cover several data sources, which migrate
    independently and map to different v5 sources, so routing has to be per
    data source rather than per endpoint. fluview is the case that exists
    today (ILINet plus clinical labs) and stands in for the general rule.
    """

    def _indicators(self, signals=("wili",), data_source="fluview"):
        return [
            {"_endpoint": "fluview", "data_source": data_source, "indicator": signal}
            for signal in signals
        ]

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_migrated_signal_drops_the_v4_call(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["wili"], metadata_source="fluview_ilinet"
        )

        result = generate_epiweek_export_url(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}, {"id": "hhs3"}],
            "2020-01-01",
            "2020-01-20",
            "user-key",
            "csv",
            self._indicators(),
        )
        self.assertEqual(len(result), 2)
        for command in result:
            self.assertIn("curl -o", command)
            self.assertIn("reference_times=2020-01-01:2020-01-20", command)
            self.assertIn("token=user-key", command)
            self.assertNotIn("api_key", command)
        self.assertFalse(any("wget" in command for command in result))

        probe_params = [call.kwargs["params"] for call in self._probe_calls(mock_get)]
        geo_values = {params["geo_value"] for params in probe_params}
        self.assertEqual(geo_values, {"us", "3"})
        for params in probe_params:
            self.assertEqual(params["source"], "fluview_ilinet")
            self.assertEqual(params["token"], "user-key")
            self.assertNotIn("api_key", params)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_partially_migrated_keeps_both_calls(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["wili"], metadata_source="fluview_ilinet"
        )

        result = generate_epiweek_export_url(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "csv",
            self._indicators(signals=["wili", "ili"]),
        )
        self.assertEqual(len(result), 2)
        self.assertTrue(any("curl -o" in command for command in result))
        self.assertTrue(any("wget" in command for command in result))

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_unmigrated_source_only_emits_v4(self, mock_get):
        mock_get.side_effect = self._fake_get()

        result = generate_epiweek_export_url(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "csv",
            self._indicators(),
        )
        self.assertEqual(len(result), 1)
        self.assertIn("wget", result[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_unmigrated_fluview_clinical_hits_the_clinical_v4_endpoint(self, mock_get):
        """A second data source under the same _endpoint/geo widget is still
        a distinct v4 endpoint, and must not be exported as the first one."""
        mock_get.side_effect = self._fake_get()

        result = generate_epiweek_export_url(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "csv",
            self._indicators(data_source="fluview_clinical"),
        )
        self.assertEqual(len(result), 1)
        self.assertIn("wget", result[0])
        self.assertIn(f"{settings.EPIDATA_URL}fluview_clinical/", result[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_mixed_fluview_and_fluview_clinical_emit_two_v4_commands(self, mock_get):
        mock_get.side_effect = self._fake_get()

        result = generate_epiweek_export_url(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "csv",
            self._indicators(signals=["wili"], data_source="fluview")
            + self._indicators(signals=["ili"], data_source="fluview_clinical"),
        )
        self.assertEqual(len(result), 2)
        self.assertTrue(
            any(f"{settings.EPIDATA_URL}fluview/" in command for command in result)
        )
        self.assertTrue(
            any(
                f"{settings.EPIDATA_URL}fluview_clinical/" in command
                for command in result
            )
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_two_migrated_v5_sources_are_exported_separately(self, mock_get):
        """Each migrated signal must be exported from the v5 source it actually
        belongs to, in its own command, rather than batched into one request
        against whichever source came first in the group."""
        mock_get.side_effect = self._fake_get(
            metadata={
                "fluview_ilinet": {"signals": ["wili"]},
                "fluview_resp_lab_clinical": {"signals": ["pct_positive"]},
            }
        )

        result = generate_epiweek_export_url(
            EPIWEEK_SOURCES["fluview"],
            [{"id": "nat"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "csv",
            self._indicators(signals=["wili"], data_source="fluview")
            + self._indicators(
                signals=["pct_positive"], data_source="fluview_clinical"
            ),
        )
        # Two v5 commands, no v4 fallback since everything migrated.
        self.assertEqual(len(result), 2)
        self.assertFalse(any("wget" in command for command in result))

        probe_params = [call.kwargs["params"] for call in self._probe_calls(mock_get)]
        self.assertEqual(
            {params["signal"]: params["source"] for params in probe_params},
            {"wili": "fluview_ilinet", "pct_positive": "fluview_resp_lab_clinical"},
        )
        # Distinct filenames, so one download cannot overwrite the other.
        self.assertIn("fluview_ilinet_nation.csv", result[0] + result[1])
        self.assertIn("fluview_resp_lab_clinical_nation.csv", result[0] + result[1])


class FlusurvV5RoutingTests(V5RoutingTestMixin, TestCase):
    """flusurv previews, exports and query code must route migrated signals to v5.

    flusurv is the first epiweek endpoint whose geo ids span more than one v5
    geo_type: the FluSurv-Net sites and the participating states arrive in one
    flat picker list and have to be split into two requests. v5 keeps the v4
    source name and signal names, so the routing is exercised here rather than
    any renaming.
    """

    SIGNALS = ["rate_overall", "rate_age_0"]

    def _indicators(self, signals=("rate_overall",)):
        return [
            {"_endpoint": "flusurv", "data_source": "flusurv", "indicator": signal}
            for signal in signals
        ]

    def _fake_flusurv_get(self, signals=SIGNALS, **kwargs):
        return self._fake_get(
            metadata_signals=signals, metadata_source="flusurv", **kwargs
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_preview_splits_sites_and_states_into_two_v5_requests(self, mock_get):
        mock_get.side_effect = self._fake_flusurv_get()

        preview_epiweek_data(
            EPIWEEK_SOURCES["flusurv"],
            [{"id": "network_all"}, {"id": "CA"}, {"id": "NY_albany"}],
            "2020-01-01",
            "2020-01-20",
            "user-key",
            "json",
            self._indicators(),
        )
        calls = self._probe_calls(mock_get)
        self.assertEqual(len(calls), 2)
        params_by_geo_type = {
            call.kwargs["params"]["geo_type"]: call.kwargs["params"] for call in calls
        }
        self.assertEqual(
            params_by_geo_type["flusurv_site"]["geo_value"], "network_all,ny_albany"
        )
        self.assertEqual(params_by_geo_type["state"]["geo_value"], "ca")
        for call in calls:
            self.assertIn("/v5/viz/", call.args[0])
        for params in params_by_geo_type.values():
            self.assertEqual(params["source"], "flusurv")
            self.assertEqual(params["reference_times"], "2020-01-01:2020-01-20")
            self.assertEqual(params["token"], "user-key")
            self.assertNotIn("api_key", params)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_preview_falls_back_to_v4_when_the_signal_is_not_in_v5(self, mock_get):
        """A signal v5 does not carry keeps the v4 locations/epiweeks call."""
        mock_get.side_effect = self._fake_flusurv_get(signals=[])

        preview_epiweek_data(
            EPIWEEK_SOURCES["flusurv"],
            [{"id": "network_all"}, {"id": "CA"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "json",
            self._indicators(),
        )
        calls = self._probe_calls(mock_get)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("/v5/", calls[0].args[0])
        self.assertIn("flusurv", calls[0].args[0])
        self.assertEqual(calls[0].kwargs["params"]["locations"], "network_all,CA")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_preview_partially_migrated_keeps_the_v4_call(self, mock_get):
        mock_get.side_effect = self._fake_flusurv_get(signals=["rate_overall"])

        preview_epiweek_data(
            EPIWEEK_SOURCES["flusurv"],
            [{"id": "CA"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "json",
            self._indicators(signals=["rate_overall", "rate_age_0"]),
        )
        calls = self._probe_calls(mock_get)
        self.assertEqual(len([c for c in calls if "/v5/" in c.args[0]]), 1)
        self.assertEqual(len([c for c in calls if "/v5/" not in c.args[0]]), 1)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_batches_every_migrated_signal_per_geo_type(self, mock_get):
        mock_get.side_effect = self._fake_flusurv_get()

        result = generate_epiweek_export_url(
            EPIWEEK_SOURCES["flusurv"],
            [{"id": "network_all"}, {"id": "CA"}, {"id": "NY_albany"}],
            "2020-01-01",
            "2020-01-20",
            "user-key",
            "csv",
            self._indicators(signals=self.SIGNALS),
        )
        self.assertEqual(len(result), 2)
        for command in result:
            self.assertIn("curl -o", command)
            self.assertIn("source=flusurv", command)
            self.assertIn("signal=rate_overall,rate_age_0", command)
            self.assertIn("reference_times=2020-01-01:2020-01-20", command)
            self.assertIn("token=user-key", command)
        self.assertFalse(any("wget" in command for command in result))

        geo_by_type = {
            call.kwargs["params"]["geo_type"]: call.kwargs["params"]["geo_value"]
            for call in self._probe_calls(mock_get)
        }
        self.assertEqual(
            geo_by_type, {"flusurv_site": "network_all,ny_albany", "state": "ca"}
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_falls_back_to_v4_when_the_signal_is_not_in_v5(self, mock_get):
        mock_get.side_effect = self._fake_flusurv_get(signals=[])

        result = generate_epiweek_export_url(
            EPIWEEK_SOURCES["flusurv"],
            [{"id": "network_all"}, {"id": "CA"}],
            "2020-01-01",
            "2020-01-20",
            None,
            "csv",
            self._indicators(),
        )
        self.assertEqual(len(result), 1)
        self.assertIn("wget", result[0])
        self.assertIn("flusurv/?locations=network_all,CA", result[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_query_code_emits_one_snapshot_call_per_geo_type(self, mock_get):
        mock_get.side_effect = self._fake_flusurv_get()

        python_blocks, r_blocks = generate_query_code_epiweek(
            EPIWEEK_SOURCES["flusurv"],
            [{"id": "network_all"}, {"id": "CA"}, {"id": "NY_albany"}],
            "2020-01-01",
            "2020-01-20",
            self._indicators(signals=self.SIGNALS),
        )
        self.assertEqual(len(python_blocks), 2)
        self.assertEqual(len(r_blocks), 2)
        self.assertFalse(any("pub_flusurv" in block for block in python_blocks))
        self.assertIn(
            'flusurv_flusurv_site_v5_df = epidata.epidata_snapshot(\n'
            '    source="flusurv",\n'
            '    signals=["rate_overall", "rate_age_0"],\n'
            '    geo_type="flusurv_site",\n'
            '    geo_values=["network_all", "ny_albany"],\n'
            '    reference_time=EpiRange("2020-01-01", "2020-01-20"),\n'
            ').df()\n',
            python_blocks,
        )
        self.assertIn(
            'epidata_flusurv_state_v5 <- epidata_snapshot(\n'
            '    source = "flusurv",\n'
            '    signals = c("rate_overall", "rate_age_0"),\n'
            '    geo_type = "state",\n'
            '    geo_values = c("ca"),\n'
            '    reference_time = epirange("2020-01-01", "2020-01-20")\n'
            ')\n',
            r_blocks,
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_query_code_falls_back_to_v4_when_the_signal_is_not_in_v5(self, mock_get):
        mock_get.side_effect = self._fake_flusurv_get(signals=[])

        python_blocks, r_blocks = generate_query_code_epiweek(
            EPIWEEK_SOURCES["flusurv"],
            [{"id": "network_all"}, {"id": "CA"}],
            "2020-01-01",
            "2020-01-20",
            self._indicators(),
        )
        self.assertEqual(len(python_blocks), 1)
        self.assertIn("epidata.pub_flusurv(", python_blocks[0])
        self.assertIn('locations="network_all,CA"', python_blocks[0])
        self.assertIn("pub_flusurv(", r_blocks[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_query_code_partially_migrated_keeps_the_v4_call(self, mock_get):
        mock_get.side_effect = self._fake_flusurv_get(signals=["rate_overall"])

        python_blocks, _ = generate_query_code_epiweek(
            EPIWEEK_SOURCES["flusurv"],
            [{"id": "CA"}],
            "2020-01-01",
            "2020-01-20",
            self._indicators(signals=self.SIGNALS),
        )
        self.assertEqual(len(python_blocks), 2)
        self.assertTrue(any("epidata_snapshot(" in block for block in python_blocks))
        self.assertTrue(any("pub_flusurv(" in block for block in python_blocks))


@override_settings(EPIDATA_URL="https://api.example.com/epidata/")
class ExportViewEpiweekOrderingTests(TestCase):
    """End-to-end check that the export view emits one command per selected
    epiweek source, in registry order, and skips sources with no geos.

    Deliberately registry-free and network-free: no covidcast indicators means
    no availability probes, so this runs identically before and after the
    per-source builders were collapsed into one.
    """

    def _post(self, payload):
        return self.client.post(
            reverse("export"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    @staticmethod
    def _command(endpoint, geo_param, geo_ids):
        url = (
            f"https://api.example.com/epidata/{endpoint}/"
            f"?{geo_param}={geo_ids}&epiweeks=202401-202405&format=csv&header=true"
        )
        return f'wget --content-disposition <a href="{url}">{url}</a>'

    def test_all_four_sources_emit_commands_in_order(self):
        response = self._post(
            {
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
                "indicators": [],
                "covidCastGeographicValues": {},
                "fluviewLocations": [{"id": "nat"}],
                "nidssFluLocations": [{"id": "taipei"}],
                "nidssDengueLocations": [{"id": "taipei"}],
                "flusurvLocations": [{"id": "network_all"}],
                "dataFormat": "csv",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data_export_commands"],
            [
                self._command("fluview", "regions", "nat"),
                self._command("nidss_flu", "regions", "taipei"),
                self._command("nidss_dengue", "locations", "taipei"),
                self._command("flusurv", "locations", "network_all"),
            ],
        )

    def test_unselected_sources_are_skipped(self):
        response = self._post(
            {
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
                "indicators": [],
                "covidCastGeographicValues": {},
                "fluviewLocations": [],
                "nidssDengueLocations": [{"id": "taipei"}],
                "dataFormat": "csv",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data_export_commands"],
            [self._command("nidss_dengue", "locations", "taipei")],
        )


class ExportDataViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_returns_401_for_invalid_api_key(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        payload = {
            "start_date": "2020-01-01",
            "end_date": "2020-01-20",
            "indicators": [
                {
                    "_endpoint": "covidcast",
                    "data_source": "src",
                    "indicator": "sig",
                    "time_type": "day",
                    "display_name": "My Signal",
                }
            ],
            "covidCastGeographicValues": {"state": [{"id": "state:pa", "geoType": "state"}]},
            "dataFormat": "csv",
        }
        response = self.client.post(
            reverse("export"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
