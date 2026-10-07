import base64
import json
import os
import re
import tempfile
from io import StringIO
from pathlib import Path
from unittest import skipUnless
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import redis
import requests
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
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
    get_covidcast_geo_coverage,
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
from indicatorsets.utils.helpers import normalize_fill_method
from indicatorsets.utils.caching import safe_cache_get, safe_cache_set
from indicatorsets.utils.epidata import (
    get_v5_metadata,
    get_v5_source,
    split_geos_by_v5_values,
    map_fluview_geo_to_v5,
    map_flusurv_geo_to_v5,
)
from indicatorsets.utils.query_code import (
    generate_query_code_covidcast,
    generate_query_code_nwss,
    generate_query_code_pophive,
)
from indicatorsets.management.commands.diff_v5_indicators import (
    DEFAULT_MARKDOWN_PATH,
)
from indicatorsets.utils.sources import EPIWEEK_SOURCES
from indicatorsets.utils.v5_diff import (
    diff_catalogue,
    diff_source,
    find_unresolvable_sources,
    resolve_portal_signal,
)
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


def _json_response(payload):
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = payload
    return response


def _row(signal, value):
    return {
        "signal": signal,
        "geo_type": "county",
        "geo_value": "42003",
        "value": value,
    }


def _v4_envelope(rows):
    return {"result": 1 if rows else -2, "epidata": rows, "message": "success"}


NSSP_RSV = {
    "_endpoint": "covidcast",
    "data_source": "nssp",
    "indicator": "smoothed_pct_ed_visits_rsv",
    "time_type": "week",
}
NSSP_COVID = {
    "_endpoint": "covidcast",
    "data_source": "nssp",
    "indicator": "smoothed_pct_ed_visits_covid",
    "time_type": "week",
}
V4_ONLY = {
    "_endpoint": "covidcast",
    "data_source": "doctor-visits",
    "indicator": "smoothed_cli",
    "time_type": "day",
}


@patch(
    "indicatorsets.utils.epidata.get_v5_metadata",
    return_value={
        "nssp": {
            "signals": [
                "smoothed_pct_ed_visits_rsv",
                "smoothed_pct_ed_visits_covid",
            ]
        }
    },
)
class CovidcastGeoCoverageTests(TestCase):
    def _fake_get(self, v5_rows, v4_rows):
        """``None`` for either side makes that API's request fail."""
        calls = []

        def fake_get(url, params=None, **kwargs):
            calls.append((url, params))
            rows = v5_rows if url.endswith("viz/") else v4_rows
            if rows is None:
                raise requests.RequestException("down")
            return _json_response(rows if url.endswith("viz/") else _v4_envelope(rows))

        return fake_get, calls

    def _by_signal(self, coverage):
        return {entry["indicator"]: entry for entry in coverage}

    def _v4_calls(self, calls):
        return [params for url, params in calls if url.endswith("covidcast/")]

    @patch("indicatorsets.utils.geos.requests.get")
    def test_signal_with_v5_values_routes_to_v5_without_v4_lookup(
        self, mock_get, _mock_meta
    ):
        fake_get, calls = self._fake_get(
            [_row("smoothed_pct_ed_visits_rsv", 0.17)], []
        )
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage("county:42003", [NSSP_RSV])

        self.assertEqual(
            coverage,
            [
                {
                    "data_source": "nssp",
                    "indicator": "smoothed_pct_ed_visits_rsv",
                    "covered": True,
                    "route": "v5",
                }
            ],
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["source"], "nssp")
        self.assertNotIn("fill_method", calls[0][1])

    @patch("indicatorsets.utils.geos.requests.get")
    def test_null_only_v5_rows_fall_back_to_v4_values(self, mock_get, _mock_meta):
        # v5 nssp for Allegheny County: every row present, every value null.
        fake_get, calls = self._fake_get(
            [_row("smoothed_pct_ed_visits_rsv", None)] * 3,
            [_row("smoothed_pct_ed_visits_rsv", None), _row("smoothed_pct_ed_visits_rsv", 0.2)],
        )
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage("county:42003", [NSSP_RSV])

        self.assertEqual(coverage[0]["covered"], True)
        self.assertEqual(coverage[0]["route"], "v4")
        v4_params = self._v4_calls(calls)[0]
        self.assertEqual(v4_params["data_source"], "nssp")
        self.assertEqual(v4_params["time_type"], "week")
        self.assertEqual(v4_params["time_values"], "*")

    @patch("indicatorsets.utils.geos.requests.get")
    def test_null_only_rows_on_both_apis_are_not_covered(self, mock_get, _mock_meta):
        fake_get, _calls = self._fake_get(
            [_row("smoothed_pct_ed_visits_rsv", None)],
            [_row("smoothed_pct_ed_visits_rsv", None), _row("smoothed_pct_ed_visits_rsv", "")],
        )
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage("county:42003", [NSSP_RSV])

        self.assertEqual(coverage[0]["covered"], False)
        self.assertIsNone(coverage[0]["route"])

    @patch("indicatorsets.utils.geos.requests.get")
    def test_null_only_v4_rows_are_not_covered_for_unmigrated_source(
        self, mock_get, _mock_meta
    ):
        fake_get, calls = self._fake_get([], [_row("smoothed_cli", None)])
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage("state:pa", [V4_ONLY])

        self.assertEqual(coverage[0]["covered"], False)
        self.assertFalse(any(url.endswith("viz/") for url, _params in calls))

    @patch("indicatorsets.utils.geos.requests.get")
    def test_signal_without_rows_on_either_api_is_not_covered(
        self, mock_get, _mock_meta
    ):
        fake_get, _calls = self._fake_get([], [])
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage("county:42003", [NSSP_RSV])

        self.assertEqual(coverage[0]["covered"], False)

    @patch("indicatorsets.utils.geos.requests.get")
    def test_signals_of_one_v5_source_share_one_probe_and_route_separately(
        self, mock_get, _mock_meta
    ):
        fake_get, calls = self._fake_get(
            [
                _row("smoothed_pct_ed_visits_covid", 1.2),
                _row("smoothed_pct_ed_visits_rsv", None),
            ],
            [_row("smoothed_pct_ed_visits_rsv", 0.3)],
        )
        mock_get.side_effect = fake_get

        coverage = self._by_signal(
            get_covidcast_geo_coverage("county:42003", [NSSP_RSV, NSSP_COVID])
        )

        self.assertEqual(coverage["smoothed_pct_ed_visits_covid"]["route"], "v5")
        self.assertEqual(coverage["smoothed_pct_ed_visits_rsv"]["route"], "v4")
        viz_calls = [params for url, params in calls if url.endswith("viz/")]
        self.assertEqual(len(viz_calls), 1)
        self.assertEqual(
            set(viz_calls[0]["signal"].split(",")),
            {"smoothed_pct_ed_visits_rsv", "smoothed_pct_ed_visits_covid"},
        )
        # Only the signal v5 could not serve is asked of v4.
        self.assertEqual(
            self._v4_calls(calls)[0]["signals"], "smoothed_pct_ed_visits_rsv"
        )

    @patch("indicatorsets.utils.geos.requests.get")
    def test_v4_requests_are_split_by_data_source_and_time_type(
        self, mock_get, _mock_meta
    ):
        weekly = {**V4_ONLY, "indicator": "smoothed_cli_weekly", "time_type": "week"}
        fake_get, calls = self._fake_get(
            [], [_row("smoothed_cli", 1.0), _row("smoothed_cli_weekly", 2.0)]
        )
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage("state:PA", [V4_ONLY, weekly])

        self.assertTrue(all(entry["route"] == "v4" for entry in coverage))
        v4_calls = self._v4_calls(calls)
        self.assertEqual(
            sorted((p["time_type"], p["signals"]) for p in v4_calls),
            [("day", "smoothed_cli"), ("week", "smoothed_cli_weekly")],
        )
        self.assertTrue(all(p["geo_values"] == "pa" for p in v4_calls))

    @patch("indicatorsets.utils.geos.requests.get")
    def test_failed_v4_lookup_reports_unknown_not_uncovered(
        self, mock_get, _mock_meta
    ):
        fake_get, _calls = self._fake_get([], None)
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage("state:pa", [V4_ONLY])

        self.assertIsNone(coverage[0]["covered"])
        self.assertIsNone(coverage[0]["route"])

    @patch("indicatorsets.utils.geos.requests.get")
    def test_failed_v5_lookup_without_v4_values_reports_unknown(
        self, mock_get, _mock_meta
    ):
        fake_get, _calls = self._fake_get(None, [])
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage("county:42003", [NSSP_RSV])

        self.assertIsNone(coverage[0]["covered"])

    @patch("indicatorsets.utils.geos.requests.get")
    def test_failed_v5_lookup_still_finds_v4_values(self, mock_get, _mock_meta):
        fake_get, _calls = self._fake_get(
            None, [_row("smoothed_pct_ed_visits_rsv", 0.2)]
        )
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage("county:42003", [NSSP_RSV])

        self.assertEqual(coverage[0]["route"], "v4")

    @patch("indicatorsets.utils.geos.requests.get")
    def test_v4_error_envelope_reports_unknown(self, mock_get, _mock_meta):
        mock_get.return_value = _json_response(
            {"result": -1, "epidata": [], "message": "bad request"}
        )

        coverage = get_covidcast_geo_coverage("state:pa", [V4_ONLY])

        self.assertIsNone(coverage[0]["covered"])

    @patch("indicatorsets.utils.geos.requests.get")
    def test_missing_time_type_reports_unknown_without_v4_lookup(
        self, mock_get, _mock_meta
    ):
        indicator = {key: value for key, value in V4_ONLY.items() if key != "time_type"}

        coverage = get_covidcast_geo_coverage("state:pa", [indicator])

        self.assertIsNone(coverage[0]["covered"])
        mock_get.assert_not_called()

    @patch("indicatorsets.utils.geos.requests.get")
    def test_non_covidcast_indicators_are_ignored(self, mock_get, _mock_meta):
        coverage = get_covidcast_geo_coverage(
            "state:pa",
            [{"_endpoint": "fluview", "data_source": "fluview", "indicator": "wili"}],
        )

        self.assertEqual(coverage, [])
        mock_get.assert_not_called()


    @patch("indicatorsets.utils.geos.requests.get")
    def test_filled_fill_method_reaches_the_v5_probe(self, mock_get, _mock_meta):
        fake_get, calls = self._fake_get(
            [_row("smoothed_pct_ed_visits_rsv", 0.17)], []
        )
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage(
            "county:42003", [NSSP_RSV], fill_method="fill_ave"
        )

        self.assertEqual(coverage[0]["route"], "v5")
        self.assertEqual(calls[0][1]["fill_method"], "fill_ave")

    @patch("indicatorsets.utils.geos.requests.get")
    def test_filled_fill_method_does_not_count_v4_values_for_a_migrated_signal(
        self, mock_get, _mock_meta
    ):
        # Exports skip v4 for a filled fill_method, since v4 cannot fill, so
        # the modal must not call the geo covered on v4's strength either.
        fake_get, calls = self._fake_get(
            [], [_row("smoothed_pct_ed_visits_rsv", 0.2)]
        )
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage(
            "county:42003", [NSSP_RSV], fill_method="fill_ave"
        )

        self.assertEqual(coverage[0]["covered"], False)
        self.assertIsNone(coverage[0]["route"])
        self.assertEqual(self._v4_calls(calls), [])

    @patch("indicatorsets.utils.geos.requests.get")
    def test_filled_fill_method_with_failed_v5_lookup_reports_unknown(
        self, mock_get, _mock_meta
    ):
        fake_get, calls = self._fake_get(
            None, [_row("smoothed_pct_ed_visits_rsv", 0.2)]
        )
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage(
            "county:42003", [NSSP_RSV], fill_method="fill_zero"
        )

        self.assertIsNone(coverage[0]["covered"])
        self.assertEqual(self._v4_calls(calls), [])

    @patch("indicatorsets.utils.geos.requests.get")
    def test_filled_fill_method_still_checks_v4_only_indicators_on_v4(
        self, mock_get, _mock_meta
    ):
        # An unmigrated source exports from v4 whatever the fill_method.
        fake_get, calls = self._fake_get([], [_row("smoothed_cli", 1.0)])
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage(
            "county:42003", [V4_ONLY], fill_method="fill_ave"
        )

        self.assertEqual(coverage[0]["covered"], True)
        self.assertEqual(coverage[0]["route"], "v4")


    @patch("indicatorsets.utils.geos.requests.get")
    def test_explicit_source_still_counts_v4_values(self, mock_get, _mock_meta):
        fake_get, calls = self._fake_get(
            [], [_row("smoothed_pct_ed_visits_rsv", 0.2)]
        )
        mock_get.side_effect = fake_get

        coverage = get_covidcast_geo_coverage(
            "county:42003", [NSSP_RSV], fill_method="source"
        )

        self.assertEqual(coverage[0]["route"], "v4")
        self.assertEqual(calls[0][1]["fill_method"], "source")


class CheckCovidcastGeoCoverageViewTests(TestCase):
    @patch("indicatorsets.views.get_covidcast_geo_coverage")
    def test_post_returns_coverage(self, mock_coverage):
        mock_coverage.return_value = [{"indicator": "sig", "covered": True}]

        response = self.client.post(
            reverse("check_covidcast_geo_coverage"),
            data=json.dumps({"geo": "county:42003", "indicators": [NSSP_RSV]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"coverage": [{"indicator": "sig", "covered": True}]}
        )
        mock_coverage.assert_called_once_with(
            "county:42003", [NSSP_RSV], fill_method=""
        )

    @patch("indicatorsets.views.get_covidcast_geo_coverage", return_value=[])
    def test_post_passes_the_chosen_fill_method(self, mock_coverage):
        self.client.post(
            reverse("check_covidcast_geo_coverage"),
            data=json.dumps(
                {"geo": "county:42003", "indicators": [NSSP_RSV], "fill_method": "fill_ave"}
            ),
            content_type="application/json",
        )

        mock_coverage.assert_called_once_with(
            "county:42003", [NSSP_RSV], fill_method="fill_ave"
        )

    @patch("indicatorsets.views.get_covidcast_geo_coverage", return_value=[])
    def test_unrecognised_fill_method_means_none(self, mock_coverage):
        self.client.post(
            reverse("check_covidcast_geo_coverage"),
            data=json.dumps(
                {"geo": "county:42003", "indicators": [NSSP_RSV], "fill_method": "bogus"}
            ),
            content_type="application/json",
        )

        mock_coverage.assert_called_once_with(
            "county:42003", [NSSP_RSV], fill_method=""
        )

    def test_get_is_rejected(self):
        response = self.client.get(reverse("check_covidcast_geo_coverage"))
        self.assertEqual(response.status_code, 405)

    def test_invalid_body_is_rejected(self):
        url = reverse("check_covidcast_geo_coverage")
        for body in ("not json", json.dumps({"geo": "pa", "indicators": []})):
            response = self.client.post(url, data=body, content_type="application/json")
            self.assertEqual(response.status_code, 400)


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
        def fake_get(url, params=None, timeout=None, auth=None):
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


# A fluview indicator for view tests; they stub v5 routing so it stays on v4.
FLUVIEW_V4_INDICATOR = {
    "_endpoint": "fluview",
    "data_source": "fluview",
    "indicator": "wili",
    "time_type": "week",
}


class PreviewDataViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("indicatorsets.utils.epidata.get_v5_source", new=lambda indicator: None)
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
            "indicators": [FLUVIEW_V4_INDICATOR],
            # fluview takes its locations from the main Location(s) dropdown
            "covidCastGeographicValues": {
                "nation": [{"id": "nation:US", "text": "U.S. National", "geoType": "nation"}]
            },
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

    @patch("indicatorsets.utils.epidata.get_v5_source", new=lambda indicator: None)
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
            "indicators": [FLUVIEW_V4_INDICATOR],
            # fluview takes its locations from the main Location(s) dropdown
            "covidCastGeographicValues": {
                "nation": [{"id": "nation:US", "text": "U.S. National", "geoType": "nation"}]
            },
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
        def fake_get(url, params=None, timeout=None, auth=None):
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

        def fake_get(url, params=None, timeout=None, auth=None):
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
            # One row per requested geo: covidcast drops v5 geos without a
            # real value back to v4, so a row that names no geo would count
            # as "no data" for every geo.
            geos = (params or {}).get("geo_value") or (params or {}).get("geo_values")
            rows = [
                {"geo_value": geo, "value": 1} for geo in str(geos or "").split(",")
            ]
            response.json.return_value = (
                {"epidata": rows, "result": 1, "message": "success"}
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
        self.assertEqual(probe_calls[0].kwargs["auth"], ("epidata", "server-key"))
        self.assertNotIn("api_key", probe_calls[0].kwargs["params"])
        self.assertIn("wget", result[0])

    @override_settings(EPIDATA_API_KEY="server-key")
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v5_probe_sends_no_token_without_a_user_key(self, mock_get):
        mock_get.side_effect = self._fake_get(
            metadata_signals=["confirmed_admissions_covid_ew"]
        )

        self._export(self.V5_INDICATOR, None)
        probe_calls = self._probe_calls(mock_get)
        self.assertEqual(len(probe_calls), 1)
        params = probe_calls[0].kwargs["params"]
        self.assertIn("/v5/", probe_calls[0].args[0])
        self.assertNotIn("token", params)
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
                # fluview takes its locations from the main Location(s) dropdown
                "covidCastGeographicValues": {
                    "nation": [{"id": "nation:US", "text": "U.S. National", "geoType": "nation"}]
                },
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
                        "format": "csv",
                        "header": "true",
                    },
                )
                self.assertEqual(
                    mock_get.call_args.kwargs["auth"], ("epidata", "default-key")
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
                self.assertNotIn("api_key", params)
                self.assertEqual(mock_get.call_args.kwargs["auth"], ("epidata", "mine"))
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

    @patch("indicatorsets.utils.epidata.get_v5_source", new=lambda indicator: None)
    def test_snippets_appear_in_source_order(self):
        response = self._post(
            {
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
                "indicators": [FLUVIEW_V4_INDICATOR],
                # fluview takes its locations from the main Location(s) dropdown
                "covidCastGeographicValues": {
                    "nation": [{"id": "nation:US", "text": "U.S. National", "geoType": "nation"}]
                },
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

    @patch("indicatorsets.utils.epidata.get_v5_source", new=lambda indicator: None)
    def test_all_four_sources_emit_commands_in_order(self):
        response = self._post(
            {
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
                "indicators": [FLUVIEW_V4_INDICATOR],
                # fluview takes its locations from the main Location(s) dropdown
                "covidCastGeographicValues": {
                    "nation": [{"id": "nation:US", "text": "U.S. National", "geoType": "nation"}]
                },
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


class FillMethodNormalizationTests(TestCase):
    """``fill_method`` is user-supplied and lands in URLs, so it is whitelisted."""

    def test_accepts_every_supported_fill_method(self):
        for value in ("source", "fill_ave", "fill_zero"):
            self.assertEqual(normalize_fill_method(value), value)

    def test_unknown_value_means_no_fill_method(self):
        self.assertEqual(normalize_fill_method("fill_everything"), "")

    def test_missing_value_means_no_fill_method(self):
        self.assertEqual(normalize_fill_method(None), "")

    def test_rejects_value_that_would_inject_into_an_export_url(self):
        self.assertEqual(normalize_fill_method("source&token=stolen"), "")


class CovidcastFillMethodTests(V5RoutingTestMixin, TestCase):
    """The chosen fill_method reaches every v5 covidcast request."""

    INDICATOR = {
        "_endpoint": "covidcast",
        "data_source": "nssp",
        "indicator": "pct_ed_visits_covid",
        "time_type": "week",
        "display_name": "COVID ED Visits",
    }
    GEOS = {"state": [{"id": "state:pa", "geoType": "state"}]}

    def _fake_nssp_get(self):
        return self._fake_get(
            metadata_source="nssp", metadata_signals=["pct_ed_visits_covid"]
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_probe_carries_fill_method(self, mock_get):
        mock_get.side_effect = self._fake_nssp_get()

        generate_covidcast_indicators_export_url(
            [self.INDICATOR], "2024-01-01", "2024-03-01", self.GEOS, None, "csv",
            fill_method="fill_ave",
        )

        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertEqual(params["fill_method"], "fill_ave")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_url_and_download_link_carry_fill_method(self, mock_get):
        mock_get.side_effect = self._fake_nssp_get()

        result = generate_covidcast_indicators_export_url(
            [self.INDICATOR], "2024-01-01", "2024-03-01", self.GEOS, None, "csv",
            fill_method="fill_zero",
        )

        self.assertIn("fill_method=fill_zero", result[0])
        download_url = re.search(r'href="([^"]+)"', result[0]).group(1)
        query = parse_qs(urlparse(download_url).query)
        self.assertEqual(query["fill_method"], ["fill_zero"])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_v4_export_is_left_alone(self, mock_get):
        mock_get.side_effect = self._fake_get(metadata_signals=[])

        result = generate_covidcast_indicators_export_url(
            [{**self.INDICATOR, "data_source": "src"}],
            "2024-01-01", "2024-03-01", self.GEOS, None, "csv",
            fill_method="fill_ave",
        )

        self.assertNotIn("fill_method", result[0])

    @patch("indicatorsets.utils.previews.requests.get")
    def test_preview_request_carries_fill_method(self, mock_get):
        # previews and epidata share one ``requests`` module, so one patch
        # serves both the metadata lookup and the preview fetch.
        mock_get.side_effect = self._fake_nssp_get()

        preview_covidcast_data(
            [self.INDICATOR], "2024-01-01", "2024-03-01", self.GEOS, None, "json",
            fill_method="fill_ave",
        )

        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertEqual(params["fill_method"], "fill_ave")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_query_code_snippets_pin_fill_method(self, mock_get):
        mock_get.side_effect = self._fake_nssp_get()

        python_blocks, r_blocks = generate_query_code_covidcast(
            [self.INDICATOR], self.GEOS, "2024-01-01", "2024-03-01", "nssp",
            "pct_ed_visits_covid", fill_method="fill_ave",
        )

        self.assertIn('fill_method="fill_ave",', "".join(python_blocks))
        self.assertIn('fill_method = "fill_ave"', "".join(r_blocks))


class EpiweekFillMethodTests(V5RoutingTestMixin, TestCase):
    """Migrated epiweek endpoints honour the shared fill_method too."""

    INDICATOR = {
        "_endpoint": "flusurv",
        "data_source": "flusurv",
        "indicator": "rate_overall",
        "time_type": "week",
    }
    GEOS = [{"id": "CA", "text": "CA"}]

    def _fake_flusurv_get(self):
        return self._fake_get(
            metadata_source="flusurv", metadata_signals=["rate_overall"]
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_probe_and_url_carry_fill_method(self, mock_get):
        mock_get.side_effect = self._fake_flusurv_get()

        result = generate_epiweek_export_url(
            EPIWEEK_SOURCES["flusurv"], self.GEOS, "2024-01-01", "2024-03-01",
            None, "csv", [self.INDICATOR], fill_method="fill_ave",
        )

        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertEqual(params["fill_method"], "fill_ave")
        self.assertIn("fill_method=fill_ave", result[0])

    @patch("indicatorsets.utils.previews.requests.get")
    def test_preview_request_carries_fill_method(self, mock_get):
        # previews and epidata share one ``requests`` module, so one patch
        # serves both the metadata lookup and the preview fetch.
        mock_get.side_effect = self._fake_flusurv_get()

        preview_epiweek_data(
            EPIWEEK_SOURCES["flusurv"], self.GEOS, "2024-01-01", "2024-03-01",
            None, "json", [self.INDICATOR], fill_method="fill_zero",
        )

        params = self._probe_calls(mock_get)[0].kwargs["params"]
        self.assertEqual(params["fill_method"], "fill_zero")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_query_code_snippets_pin_fill_method(self, mock_get):
        mock_get.side_effect = self._fake_flusurv_get()

        python_blocks, r_blocks = generate_query_code_epiweek(
            EPIWEEK_SOURCES["flusurv"], self.GEOS, "2024-01-01", "2024-03-01",
            [self.INDICATOR], fill_method="fill_ave",
        )

        self.assertIn('fill_method="fill_ave",', "".join(python_blocks))
        self.assertIn('fill_method = "fill_ave"', "".join(r_blocks))


class PophiveFillMethodTests(TestCase):
    """pophive is v5-native, so it takes the shared fill_method as well."""

    INDICATORS = [{"_endpoint": "pophive", "indicator": "sig", "display_name": "Sig"}]
    GEOS = [{"id": "pa", "geo_type": "state", "text": "PA"}]
    AGE_GROUP = [{"id": "0-4"}]

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_url_carries_fill_method(self, mock_get):
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.json.return_value = [{"value": 1}]
        mock_get.return_value = response

        result = generate_pophive_export_url(
            self.INDICATORS, "2024-01-01", "2024-03-01", self.GEOS, self.AGE_GROUP,
            None, "csv", fill_method="fill_ave",
        )

        self.assertIn("fill_method=fill_ave", result[0])
        self.assertEqual(
            mock_get.call_args.kwargs["params"]["fill_method"], "fill_ave"
        )

    @patch("indicatorsets.utils.previews.requests.get")
    def test_preview_request_carries_fill_method(self, mock_get):
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.json.return_value = [{"value": 1}]
        mock_get.return_value = response

        preview_pophive_data(
            self.INDICATORS, "2024-01-01", "2024-03-01", self.GEOS, self.AGE_GROUP,
            None, "json", fill_method="fill_zero",
        )

        self.assertEqual(
            mock_get.call_args.kwargs["params"]["fill_method"], "fill_zero"
        )

    def test_query_code_snippets_pin_fill_method(self):
        python_blocks, r_blocks = generate_query_code_pophive(
            self.INDICATORS, "2024-01-01", "2024-03-01", self.GEOS, self.AGE_GROUP,
            fill_method="fill_ave",
        )

        self.assertIn('fill_method="fill_ave",', "".join(python_blocks))
        self.assertIn('fill_method = "fill_ave"', "".join(r_blocks))


class FillMethodViewTests(TestCase):
    """The views read one shared ``fillMethod`` key and normalize it."""

    NWSS_INDICATOR = {
        "_endpoint": "nwss",
        "data_source": "nwss",
        "indicator": "covid_avg_conc",
        "indicator_set_short_name": "NWSS",
    }

    def _nwss_epivis_params(self, payload):
        response = self.client.post(
            reverse("epivis"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        encoded = response.json()["epivis_url"].split("#", 1)[1]
        datasets = json.loads(base64.b64decode(encoded).decode("ascii"))["datasets"]
        return datasets[0]["params"]

    def test_epivis_nwss_uses_shared_fill_method_key(self):
        params = self._nwss_epivis_params(
            {
                "indicators": [self.NWSS_INDICATOR],
                "covidCastGeographicValues": {},
                "nwssGeographicValue": ["sewershed_1"],
                "nwssSource": [{"id": "CDC_Biobot"}],
                "fillMethod": "fill_ave",
            }
        )
        self.assertEqual(params["fill_method"], "fill_ave")

    def test_epivis_omits_fill_method_when_absent(self):
        params = self._nwss_epivis_params(
            {
                "indicators": [self.NWSS_INDICATOR],
                "covidCastGeographicValues": {},
                "nwssGeographicValue": ["sewershed_1"],
                "nwssSource": [{"id": "CDC_Biobot"}],
            }
        )
        self.assertNotIn("fill_method", params)

    def test_epivis_rejects_unknown_fill_method(self):
        params = self._nwss_epivis_params(
            {
                "indicators": [self.NWSS_INDICATOR],
                "covidCastGeographicValues": {},
                "nwssGeographicValue": ["sewershed_1"],
                "nwssSource": [{"id": "CDC_Biobot"}],
                "fillMethod": "fill_everything",
            }
        )
        self.assertNotIn("fill_method", params)

    @patch("indicatorsets.views.generate_query_code_nwss")
    def test_query_code_view_forwards_shared_fill_method(self, mock_nwss):
        mock_nwss.return_value = ([], [])
        self.client.post(
            reverse("create_query_code"),
            data=json.dumps(
                {
                    "indicators": [self.NWSS_INDICATOR],
                    "covidCastGeographicValues": {},
                    "nwssGeographicValue": ["sewershed_1"],
                    "nwssSource": [{"id": "CDC_Biobot"}],
                    "fillMethod": "fill_zero",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(mock_nwss.call_args.args[-1], "fill_zero")


class DownloadVizExportFillMethodTests(TestCase):
    """The download proxy only forwards fill_methods the API actually has."""

    def _upstream(self):
        response = MagicMock()
        response.status_code = 200
        response.content = b"[]"
        response.headers = {"Content-Type": "application/json"}
        response.raise_for_status = MagicMock()
        return response

    @patch("indicatorsets.proxy_views.requests.get")
    def test_forwards_supported_fill_method(self, mock_get):
        mock_get.return_value = self._upstream()
        self.client.get(
            reverse("download_export"),
            {"source": "nssp", "signal": "sig", "fill_method": "fill_ave"},
        )
        self.assertEqual(mock_get.call_args.kwargs["params"]["fill_method"], "fill_ave")

    @patch("indicatorsets.proxy_views.requests.get")
    def test_drops_unknown_fill_method(self, mock_get):
        mock_get.return_value = self._upstream()
        self.client.get(
            reverse("download_export"),
            {"source": "nssp", "signal": "sig", "fill_method": "fill_everything"},
        )
        self.assertNotIn("fill_method", mock_get.call_args.kwargs["params"])


class FillMethodPageContextTests(TestCase):
    """The page tells the browser which sources the fill_method picker applies to.

    Rendered from ``MIGRATED_DATASOURCES`` rather than hand-copied into the JS,
    so migrating a source turns the picker on for it without a second edit.
    """

    def test_page_exposes_the_migrated_data_sources(self):
        response = self.client.get(reverse("indicatorsets"))
        self.assertEqual(
            json.loads(response.context["v5_data_sources"]),
            sorted(MIGRATED_DATASOURCES),
        )

    def test_page_exposes_the_v5_native_endpoints(self):
        response = self.client.get(reverse("indicatorsets"))
        self.assertEqual(
            json.loads(response.context["v5_endpoints"]), ["nwss", "pophive"]
        )


class ResolvePortalSignalTests(TestCase):
    """Mapping one portal signal onto its v5 name, or finding it has none."""

    def test_identical_name_resolves_exactly(self):
        self.assertEqual(
            resolve_portal_signal("pct_ed_visits_covid", "nssp", {"pct_ed_visits_covid"}),
            ("pct_ed_visits_covid", "exact"),
        )

    def test_known_rename_resolves(self):
        self.assertEqual(
            resolve_portal_signal(
                "percent_positive", "fluview_resp_lab_clinical", {"pct_positive"}
            ),
            ("pct_positive", "renamed"),
        )

    def test_fill_method_suffix_collapses_onto_the_base_signal(self):
        """v4 spelled the fill method into the name; v5 made it a key column."""
        self.assertEqual(
            resolve_portal_signal("x_fa", "nssp", {"x"}), ("x", "fill_ave")
        )
        self.assertEqual(
            resolve_portal_signal("x_fz", "nssp", {"x"}), ("x", "fill_zero")
        )

    def test_fill_method_suffix_without_a_base_signal_stays_unresolved(self):
        """The suffix rule must not swallow a signal v5 genuinely lacks."""
        self.assertEqual(resolve_portal_signal("y_fa", "nssp", {"x"}), (None, None))

    def test_unknown_signal_stays_unresolved(self):
        self.assertEqual(resolve_portal_signal("nope", "nssp", {"x"}), (None, None))


class DiffSourceTests(TestCase):
    def test_separates_real_gaps_from_renames_and_fill_variants(self):
        diff = diff_source(
            "beta_nssp",
            "nssp",
            portal_signals={"pct_ed_visits_covid", "pct_ed_visits_covid_fa", "retired"},
            v5_signals={"pct_ed_visits_covid", "pct_ed_visits_ari"},
        )
        self.assertEqual(diff.matched, ["pct_ed_visits_covid"])
        self.assertEqual(
            diff.fill_variants, [("pct_ed_visits_covid_fa", "pct_ed_visits_covid", "fill_ave")]
        )
        self.assertEqual(diff.missing_from_v5, ["retired"])
        self.assertEqual(diff.missing_from_portal, ["pct_ed_visits_ari"])

    def test_a_renamed_signal_is_not_reported_missing_from_either_side(self):
        diff = diff_source(
            "fluview_clinical",
            "fluview_resp_lab_clinical",
            portal_signals={"percent_positive"},
            v5_signals={"pct_positive"},
        )
        self.assertEqual(diff.renamed, [("percent_positive", "pct_positive")])
        self.assertEqual(diff.missing_from_v5, [])
        self.assertEqual(diff.missing_from_portal, [])
        self.assertFalse(diff.has_gaps)

    def test_reports_gaps_when_either_side_has_an_extra(self):
        self.assertTrue(
            diff_source("nssp", "nssp", {"a"}, {"a", "b"}).has_gaps
        )


class DiffCatalogueTests(TestCase):
    V5 = {
        "nssp": {"signals": ["pct_ed_visits_covid"]},
        "va_respiratory": {"signals": ["something"]},
        "nwss": {"signals": ["covid_avg_conc"]},
    }

    def test_only_maps_sources_the_app_already_routes_on(self):
        diffs, _, unmapped_portal = diff_catalogue(
            {"nssp": {"pct_ed_visits_covid"}, "fb-survey": {"smoothed_cli"}}, self.V5
        )
        self.assertEqual([d.portal_source for d in diffs], ["nssp"])
        self.assertEqual(unmapped_portal, ["fb-survey"])

    def test_reports_v5_sources_the_portal_has_no_mapping_for(self):
        _, unmapped_v5, _ = diff_catalogue({"nssp": {"pct_ed_visits_covid"}}, self.V5)
        self.assertEqual(unmapped_v5, ["va_respiratory"])

    def test_v5_native_endpoints_are_not_reported_as_unmapped(self):
        """nwss and pophive are served from v5 without a v4 name to migrate."""
        _, unmapped_v5, _ = diff_catalogue({}, self.V5)
        self.assertNotIn("nwss", unmapped_v5)

    def test_sourceless_indicators_are_skipped(self):
        diffs, _, unmapped_portal = diff_catalogue({None: {"orphan"}}, self.V5)
        self.assertEqual(diffs, [])
        self.assertEqual(unmapped_portal, [])


class MigratedSourcesResolveInV5Tests(TestCase):
    """Every MIGRATED_DATASOURCES target must still exist in v5 metadata.

    If Epidata renames one, ``get_v5_source()`` quietly returns None and every
    user silently drops back to v4 -- no error is raised anywhere, so nothing
    else in the suite would notice.
    """

    def test_detects_a_target_missing_from_metadata(self):
        metadata = {v5: {"signals": []} for v5 in set(MIGRATED_DATASOURCES.values())}
        metadata.pop("nssp")
        self.assertEqual(find_unresolvable_sources(metadata), ["nssp"])

    def test_passes_when_every_target_is_present(self):
        metadata = {v5: {"signals": []} for v5 in set(MIGRATED_DATASOURCES.values())}
        self.assertEqual(find_unresolvable_sources(metadata), [])

    @skipUnless(
        os.environ.get("EPIDATA_LIVE_TESTS"),
        "live Epidata check; set EPIDATA_LIVE_TESTS=1 to run",
    )
    def test_live_v5_metadata_still_has_every_migrated_source(self):
        cache.clear()
        self.assertEqual(find_unresolvable_sources(get_v5_metadata()), [])


class DiffV5IndicatorsCommandTests(TestCase):
    COMMAND = "diff_v5_indicators"
    PATCH_TARGET = (
        "indicatorsets.management.commands.diff_v5_indicators.get_v5_metadata"
    )

    def setUp(self):
        source = SourceSubdivision.objects.create(name="nssp")
        Indicator.objects.create(name="pct_ed_visits_covid", source=source)
        Indicator.objects.create(name="pct_ed_visits_covid_fa", source=source)
        Indicator.objects.create(name="orphan", source=None)

    @staticmethod
    def _metadata(**overrides):
        """Metadata where every migrated source resolves, so nothing errors."""
        metadata = {v5: {"signals": []} for v5 in set(MIGRATED_DATASOURCES.values())}
        metadata.update(overrides)
        return metadata

    def _run(self, *args, **kwargs):
        out = StringIO()
        call_command(self.COMMAND, *args, stdout=out, stderr=StringIO(), **kwargs)
        return out.getvalue()

    @patch(PATCH_TARGET)
    def test_reports_a_signal_only_in_v5(self, mock_metadata):
        mock_metadata.return_value = self._metadata(
            nssp={"signals": ["pct_ed_visits_covid", "pct_ed_visits_ari"]}
        )
        self.assertIn("pct_ed_visits_ari", self._run())

    @patch(PATCH_TARGET)
    def test_does_not_report_a_fill_method_variant_as_a_gap(self, mock_metadata):
        mock_metadata.return_value = self._metadata(
            nssp={"signals": ["pct_ed_visits_covid"]}
        )
        output = self._run()
        self.assertIn("fill_method", output)
        self.assertNotIn("pct_ed_visits_covid_fa", output.split("fill_method")[-1])

    @patch(PATCH_TARGET)
    def test_errors_when_a_migrated_source_vanished_from_v5(self, mock_metadata):
        """The silent-fallback alarm: routing would drop to v4 with no error."""
        metadata = self._metadata()
        metadata.pop("nssp")
        mock_metadata.return_value = metadata
        with self.assertRaises(CommandError):
            self._run()

    @patch(PATCH_TARGET)
    def test_errors_when_v5_metadata_is_unreachable(self, mock_metadata):
        mock_metadata.return_value = {}
        with self.assertRaises(CommandError):
            self._run()

    @patch(PATCH_TARGET)
    def test_json_output_is_machine_readable(self, mock_metadata):
        mock_metadata.return_value = self._metadata(
            nssp={"signals": ["pct_ed_visits_covid", "pct_ed_visits_ari"]}
        )
        payload = json.loads(self._run("--json"))
        nssp = [d for d in payload["sources"] if d["portal_source"] == "nssp"][0]
        self.assertEqual(nssp["missing_from_portal"], ["pct_ed_visits_ari"])

    @patch(PATCH_TARGET)
    def test_lists_the_matched_signal_names(self, mock_metadata):
        """Matched was the one category shown only as a count."""
        mock_metadata.return_value = self._metadata(
            nssp={"signals": ["pct_ed_visits_covid"]}
        )
        self.assertIn("matched:     pct_ed_visits_covid", self._run())

    def _write_markdown(self, mock_metadata, **signals):
        """Run --markdown into a temp path and hand back what landed there."""
        mock_metadata.return_value = self._metadata(**signals)
        with tempfile.TemporaryDirectory() as tmp:
            # nested: the command has to create the directory, not assume it
            path = Path(tmp) / "generated" / "diff.md"
            output = self._run("--markdown", str(path))
            return path.read_text(), output, path

    @patch(PATCH_TARGET)
    def test_markdown_writes_a_document_to_the_given_path(self, mock_metadata):
        content, _, _ = self._write_markdown(
            mock_metadata, nssp={"signals": ["pct_ed_visits_covid", "pct_ed_visits_ari"]}
        )
        self.assertTrue(content.startswith("# Epidata v5 catalogue diff"))
        self.assertIn("| portal source | v5 source |", content)
        self.assertIn("### nssp \u2192 nssp", content)
        self.assertIn("`pct_ed_visits_ari`", content)

    @patch(PATCH_TARGET)
    def test_markdown_reports_where_it_wrote(self, mock_metadata):
        _, output, path = self._write_markdown(
            mock_metadata, nssp={"signals": ["pct_ed_visits_covid"]}
        )
        self.assertIn(str(path), output)

    @patch(PATCH_TARGET)
    def test_markdown_records_its_own_caveats(self, mock_metadata):
        """A generated report has to carry the reasons not to over-read it."""
        content, _, _ = self._write_markdown(
            mock_metadata, nssp={"signals": ["pct_ed_visits_covid"]}
        )
        self.assertIn("Known limitations", content)
        self.assertIn("sourceless", content.lower())

    def test_default_markdown_path_sits_in_the_reports_directory(self):
        """Generated output lives apart from the hand-written docs/ prose."""
        self.assertEqual(DEFAULT_MARKDOWN_PATH.name, "v4-to-v5-catalogue-diff.md")
        self.assertEqual(DEFAULT_MARKDOWN_PATH.parent.name, "reports")

    @patch(PATCH_TARGET)
    def test_markdown_and_json_are_mutually_exclusive(self, mock_metadata):
        mock_metadata.return_value = self._metadata()
        with self.assertRaises(CommandError):
            self._run("--markdown", "--json")

    @patch(PATCH_TARGET)
    def test_gaps_only_hides_sources_that_line_up(self, mock_metadata):
        mock_metadata.return_value = self._metadata(
            nssp={"signals": ["pct_ed_visits_covid"]}
        )
        self.assertNotIn("nssp ->", self._run("--gaps-only"))


class DiffCatalogueSourceMapTests(TestCase):
    """Sources reachable from v5 by endpoint rather than by data_source name.

    nwss and pophive are served from v5, but the portal keys them by
    ``_endpoint`` on the indicator set, so they never appear in
    MIGRATED_DATASOURCES. Without an override they look like v4-only sources.
    """

    V5 = {"nwss": {"signals": ["covid_avg_conc", "flu_avg_conc"]}}

    def test_override_lets_an_endpoint_native_source_be_compared(self):
        diffs, _, unmapped_portal = diff_catalogue(
            {"beta_nwss": {"covid_avg_conc"}},
            self.V5,
            source_map={"beta_nwss": "nwss"},
        )
        self.assertEqual([d.portal_source for d in diffs], ["beta_nwss"])
        self.assertEqual(diffs[0].matched, ["covid_avg_conc"])
        self.assertEqual(diffs[0].missing_from_portal, ["flu_avg_conc"])
        self.assertEqual(unmapped_portal, [])

    def test_without_the_override_it_reads_as_having_no_v5_counterpart(self):
        diffs, _, unmapped_portal = diff_catalogue(
            {"beta_nwss": {"covid_avg_conc"}}, self.V5
        )
        self.assertEqual(diffs, [])
        self.assertEqual(unmapped_portal, ["beta_nwss"])


class DiffV5IndicatorsV4OnlyReportTests(TestCase):
    """The report has to answer "what do we hold that v5 cannot serve?"."""

    PATCH_TARGET = DiffV5IndicatorsCommandTests.PATCH_TARGET

    def setUp(self):
        nssp = SourceSubdivision.objects.create(name="nssp")
        legacy = SourceSubdivision.objects.create(name="fb-survey")
        nwss = SourceSubdivision.objects.create(name="beta_nwss")
        covidcast_set = IndicatorSet.objects.create(
            name="Covidcast set", source_type="covidcast", epidata_endpoint="covidcast"
        )
        nwss_set = IndicatorSet.objects.create(
            name="NWSS set", source_type="other_endpoint", epidata_endpoint="nwss"
        )
        # migrated source: one signal v5 has, one it does not
        Indicator.objects.create(
            name="pct_ed_visits_covid", source=nssp, indicator_set=covidcast_set
        )
        Indicator.objects.create(
            name="retired_signal", source=nssp, indicator_set=covidcast_set
        )
        # a source v5 has no counterpart for at all
        Indicator.objects.create(
            name="smoothed_cli", source=legacy, indicator_set=covidcast_set
        )
        # reachable from v5 by endpoint, not by data_source name
        Indicator.objects.create(
            name="covid_avg_conc", source=nwss, indicator_set=nwss_set
        )
        # sourceless rows are excluded from the comparison entirely
        Indicator.objects.create(name="orphan", source=None)

    def _metadata(self):
        metadata = {v5: {"signals": []} for v5 in set(MIGRATED_DATASOURCES.values())}
        metadata["nssp"] = {"signals": ["pct_ed_visits_covid"]}
        metadata["nwss"] = {"signals": ["covid_avg_conc"]}
        return metadata

    def _json(self):
        out = StringIO()
        with patch(self.PATCH_TARGET, return_value=self._metadata()):
            call_command("diff_v5_indicators", "--json", stdout=out, stderr=StringIO())
        return json.loads(out.getvalue())

    def test_counts_v4_only_indicators_across_both_causes(self):
        totals = self._json()["v4_only"]
        # retired_signal (inside a migrated source) + smoothed_cli (source v5 lacks)
        self.assertEqual(totals["total"], 2)
        self.assertEqual(totals["inside_migrated_sources"], 1)
        self.assertEqual(totals["in_sources_v5_lacks"], 1)

    def test_endpoint_native_source_counts_as_reachable_not_v4_only(self):
        payload = self._json()
        self.assertIn(
            "beta_nwss", [d["portal_source"] for d in payload["sources"]]
        )
        self.assertNotIn("beta_nwss", payload["v4_only"]["sources"])

    def test_names_the_v4_only_sources(self):
        self.assertEqual(self._json()["v4_only"]["sources"], ["fb-survey"])

    def test_report_states_the_v4_only_and_reachable_totals(self):
        """Sourceless rows are already outside the comparison, not a deduction."""
        out = StringIO()
        with patch(self.PATCH_TARGET, return_value=self._metadata()):
            call_command("diff_v5_indicators", stdout=out, stderr=StringIO())
        output = out.getvalue()
        # 4 sourced indicators, 2 of them v4-only
        self.assertIn("reachable from v5: 2", output)
        self.assertIn("v4-only:           2", output)


class EpidataBaseUrlSettingsTests(TestCase):
    """Base URLs get a trailing slash, since callers append paths to them."""

    def _base_urls_for(self, **env):
        """Return ``(EPIDATA_URL, EPIDATA_V5_URL)`` as settings computes them for ``env``.

        Reloading mutates the one module object, so the values are read before
        the ``finally`` reload puts the real environment's back.
        """
        import importlib

        import epiportal.settings as settings_module

        try:
            with patch.dict(os.environ, env):
                importlib.reload(settings_module)
                return settings_module.EPIDATA_URL, settings_module.EPIDATA_V5_URL
        finally:
            importlib.reload(settings_module)

    def test_adds_a_missing_trailing_slash(self):
        self.assertEqual(
            self._base_urls_for(
                EPIDATA_URL="https://example.org/epidata",
                EPIDATA_V5_URL="https://example.org/epidata/v5",
            ),
            ("https://example.org/epidata/", "https://example.org/epidata/v5/"),
        )

    def test_keeps_an_existing_trailing_slash_single(self):
        self.assertEqual(
            self._base_urls_for(
                EPIDATA_URL="https://example.org/epidata/",
                EPIDATA_V5_URL="https://example.org/epidata/v5//",
            ),
            ("https://example.org/epidata/", "https://example.org/epidata/v5/"),
        )


class GetPreviewDataGeoFilterTests(TestCase):
    def test_filters_a_v4_envelope_to_the_given_geos(self):
        response = MagicMock()
        response.json.return_value = {
            "epidata": [{"geo_value": "42003"}, {"geo_value": "17031"}],
            "result": 1,
            "message": "success",
        }
        result = get_preview_data(response, "json", geo_values=["17031"])
        self.assertEqual(result["epidata"], {"geo_value": "17031"})

    def test_no_rows_left_after_filtering_is_no_data(self):
        response = MagicMock()
        response.json.return_value = [{"geo_value": "42003", "value": None}]
        result = get_preview_data(
            response, "json", no_data_message="none", geo_values=["17031"]
        )
        self.assertEqual(result, {"message": "none"})

    def test_csv_without_a_geo_value_column_is_left_unfiltered(self):
        response = MagicMock()
        response.text = "signal,value\nsig,1\n"
        result = get_preview_data(response, "csv", geo_values=["17031"])
        self.assertEqual(result, [["signal", "value"], ["sig", "1"]])


class SplitGeosByV5ValuesTests(TestCase):
    def test_geo_with_a_real_value_stays_on_v5(self):
        rows = [{"geo_value": "17031", "value": 1.5}]
        self.assertEqual(split_geos_by_v5_values(rows, ["17031"]), (["17031"], []))

    def test_geo_whose_every_value_is_null_moves_to_v4(self):
        rows = [
            {"geo_value": "42003", "value": None},
            {"geo_value": "42003", "value": None},
        ]
        self.assertEqual(split_geos_by_v5_values(rows, ["42003"]), ([], ["42003"]))

    def test_one_real_value_is_enough_to_stay_on_v5(self):
        rows = [
            {"geo_value": "42003", "value": None},
            {"geo_value": "42003", "value": 0.2},
        ]
        self.assertEqual(split_geos_by_v5_values(rows, ["42003"]), (["42003"], []))

    def test_geo_missing_from_the_response_moves_to_v4(self):
        rows = [{"geo_value": "17031", "value": 1.5}]
        self.assertEqual(
            split_geos_by_v5_values(rows, ["17031", "06037"]), (["17031"], ["06037"])
        )

    def test_empty_csv_cell_counts_as_null(self):
        rows = [{"geo_value": "42003", "value": ""}]
        self.assertEqual(split_geos_by_v5_values(rows, ["42003"]), ([], ["42003"]))

    def test_matches_geo_values_case_insensitively_and_keeps_request_order(self):
        rows = [{"geo_value": "pa", "value": 1}, {"geo_value": "ny", "value": 1}]
        self.assertEqual(
            split_geos_by_v5_values(rows, ["NY", "ca", "PA"]), (["NY", "PA"], ["ca"])
        )


class CovidcastV5NullFallbackTests(V5RoutingTestMixin, TestCase):
    """Geos v5 only has nulls (or nothing) for are served from v4 instead.

    Mirrors Allegheny County (42003): v5 nssp lists the signal and returns rows
    for it, but every value is null, while v4 has real values.
    """

    SIGNAL = "smoothed_pct_ed_visits_rsv"
    INDICATOR = {
        "_endpoint": "covidcast",
        "data_source": "nssp",
        "indicator": SIGNAL,
        "time_type": "week",
        "display_name": "RSV ED Visits",
    }
    ALLEGHENY_AND_COOK = {
        "county": [
            {"id": "county:42003", "geoType": "county"},
            {"id": "county:17031", "geoType": "county"},
        ]
    }

    def _fake(
        self,
        v5_values,
        v4_has_data=True,
        v5_error=None,
        v5_status=200,
        v5_fill_methods=("source",),
    ):
        """``v5_values`` maps geo -> value; geos left out get no v5 rows at all.

        ``v5_error`` is raised by the v5 data request, ``v5_status`` is its
        status code, and v5 returns rows only for ``v5_fill_methods`` -- live
        v5 nssp has none for the filled ones.
        """

        def rows_as_csv(rows, columns):
            lines = [",".join(columns)]
            for row in rows:
                lines.append(
                    ",".join("" if row[c] is None else str(row[c]) for c in columns)
                )
            return "\n".join(lines) + "\n"

        def fake_get(url, params=None, timeout=None, auth=None):
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status = MagicMock()
            if "metadata/" in url:
                response.json.return_value = {"nssp": {"signals": [self.SIGNAL]}}
            elif "/v5/" in url:
                if v5_error is not None:
                    raise v5_error
                response.status_code = v5_status
                # v5 applies "source" when no fill_method is sent
                served = (params.get("fill_method") or "source") in v5_fill_methods
                # null rows first, so a naive "first row" preview would show one
                rows = sorted(
                    (
                        {"geo_value": geo, "value": v5_values[geo]}
                        for geo in params["geo_value"].split(",")
                        if served and geo in v5_values
                    ),
                    key=lambda row: row["value"] is not None,
                )
                response.json.return_value = rows
                response.text = rows_as_csv(rows, ["geo_value", "value"])
            else:
                rows = (
                    [{"geo_value": g, "value": 1} for g in params["geo_values"].split(",")]
                    if v4_has_data
                    else []
                )
                response.json.return_value = {
                    "epidata": rows,
                    "result": 1 if rows else -2,
                    "message": "success" if rows else "no results",
                }
                response.text = rows_as_csv(rows, ["geo_value", "value"])
            return response

        return fake_get

    def _export(self, geos=None):
        return generate_covidcast_indicators_export_url(
            [self.INDICATOR],
            "2024-01-01",
            "2024-03-01",
            geos or self.ALLEGHENY_AND_COOK,
            None,
            "csv",
        )

    def _preview(self, data_format="json"):
        return preview_covidcast_data(
            [self.INDICATOR],
            "2024-01-01",
            "2024-03-01",
            self.ALLEGHENY_AND_COOK,
            None,
            data_format,
        )

    def _v4_calls(self, mock_get):
        return [c for c in self._probe_calls(mock_get) if "/v5/" not in c.args[0]]

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_serves_null_only_geo_from_v4_and_the_rest_from_v5(self, mock_get):
        mock_get.side_effect = self._fake({"42003": None, "17031": 0.4})

        result = self._export()

        self.assertEqual(len(result), 2)
        v5_command, v4_command = result
        self.assertIn("/v5/viz/", v5_command)
        self.assertIn("geo_value=17031&", v5_command)
        self.assertNotIn("42003", v5_command)
        self.assertIn("wget", v4_command)
        self.assertIn("covidcast/csv?signal=nssp:smoothed_pct_ed_visits_rsv", v4_command)
        self.assertIn("geo_values=42003&", v4_command)
        self.assertNotIn("17031", v4_command)

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_serves_geo_missing_from_v5_from_v4(self, mock_get):
        mock_get.side_effect = self._fake({"17031": 0.4})

        result = self._export()

        self.assertEqual(len(result), 2)
        self.assertIn("geo_value=17031&", result[0])
        self.assertIn("geo_values=42003&", result[1])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_stays_on_v5_without_a_v4_probe_when_every_geo_has_values(
        self, mock_get
    ):
        mock_get.side_effect = self._fake({"42003": 0.1, "17031": 0.4})

        result = self._export()

        self.assertEqual(len(result), 1)
        self.assertIn("geo_value=42003,17031&", result[0])
        self.assertEqual(self._v4_calls(mock_get), [])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_probes_v4_with_only_the_fallback_geos(self, mock_get):
        mock_get.side_effect = self._fake({"42003": None, "17031": 0.4})

        self._export()

        v4_calls = self._v4_calls(mock_get)
        self.assertEqual(len(v4_calls), 1)
        params = v4_calls[0].kwargs["params"]
        self.assertEqual(params["geo_values"], "42003")
        self.assertEqual(params["data_source"], "nssp")
        self.assertEqual(params["time_values"], "202401-202409")

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_reports_no_data_when_neither_api_has_values(self, mock_get):
        mock_get.side_effect = self._fake({"42003": None}, v4_has_data=False)

        result = self._export({"county": [{"id": "county:42003", "geoType": "county"}]})

        self.assertEqual(len(result), 1)
        self.assertIn("No data found for RSV ED Visits (county)", result[0])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_names_the_geos_neither_api_has_values_for(self, mock_get):
        mock_get.side_effect = self._fake({"42003": None, "17031": 0.4}, v4_has_data=False)

        result = self._export()

        self.assertEqual(len(result), 2)
        self.assertIn("geo_value=17031&", result[0])
        self.assertIn("No data found for RSV ED Visits (county: 42003)", result[1])

    @patch("indicatorsets.utils.exports.logger")
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_logs_a_warning_when_falling_back(self, mock_get, mock_logger):
        mock_get.side_effect = self._fake({"42003": None, "17031": 0.4})

        self._export()

        mock_logger.warning.assert_called_once()
        extra = mock_logger.warning.call_args.kwargs["extra"]
        self.assertEqual(extra["source"], "nssp")
        self.assertEqual(extra["signal"], self.SIGNAL)
        self.assertEqual(extra["geo_values"], ["42003"])

    @patch("indicatorsets.utils.exports.logger")
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_does_not_warn_when_v5_has_every_geo(self, mock_get, mock_logger):
        mock_get.side_effect = self._fake({"42003": 0.1, "17031": 0.4})

        self._export()

        mock_logger.warning.assert_not_called()

    @patch("indicatorsets.utils.previews.requests.get")
    def test_preview_serves_null_only_geo_from_v4(self, mock_get):
        mock_get.side_effect = self._fake({"42003": None, "17031": 0.4})

        result = self._preview()

        v4_calls = self._v4_calls(mock_get)
        self.assertEqual(len(v4_calls), 1)
        self.assertEqual(v4_calls[0].kwargs["params"]["geo_values"], "42003")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {"geo_value": "17031", "value": 0.4})
        self.assertEqual(result[1]["epidata"]["geo_value"], "42003")

    @patch("indicatorsets.utils.previews.requests.get")
    def test_preview_stays_on_v5_when_every_geo_has_values(self, mock_get):
        mock_get.side_effect = self._fake({"42003": 0.1, "17031": 0.4})

        result = self._preview()

        self.assertEqual(self._v4_calls(mock_get), [])
        self.assertEqual(len(result), 1)

    @patch("indicatorsets.utils.previews.requests.get")
    def test_csv_preview_serves_null_only_geo_from_v4(self, mock_get):
        mock_get.side_effect = self._fake({"42003": None, "17031": 0.4})

        result = self._preview("csv")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], [["geo_value", "value"], ["17031", "0.4"]])
        self.assertEqual(result[1], [["geo_value", "value"], ["42003", "1"]])

    @patch("indicatorsets.utils.previews.logger")
    @patch("indicatorsets.utils.previews.requests.get")
    def test_preview_logs_a_warning_when_falling_back(self, mock_get, mock_logger):
        mock_get.side_effect = self._fake({"42003": None, "17031": 0.4})

        self._preview()

        mock_logger.warning.assert_called_once()
        self.assertEqual(
            mock_logger.warning.call_args.kwargs["extra"]["geo_values"], ["42003"]
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_falls_back_to_v4_when_the_v5_request_fails(self, mock_get):
        mock_get.side_effect = self._fake(
            {}, v5_error=requests.ConnectionError("v5 down")
        )

        result = self._export()

        self.assertEqual(len(result), 1)
        self.assertIn("covidcast/csv?", result[0])
        self.assertIn("geo_values=42003,17031&", result[0])

    @patch("indicatorsets.utils.previews.requests.get")
    def test_preview_falls_back_to_v4_when_the_v5_request_fails(self, mock_get):
        mock_get.side_effect = self._fake(
            {}, v5_error=requests.ConnectionError("v5 down")
        )

        result = self._preview()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["epidata"]["geo_value"], "42003")
        self.assertEqual(
            self._v4_calls(mock_get)[0].kwargs["params"]["geo_values"], "42003,17031"
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_rejected_api_key_raises_instead_of_falling_back(self, mock_get):
        mock_get.side_effect = self._fake({"17031": 0.4}, v5_status=401)

        with self.assertRaises(InvalidApiKeyError):
            self._export()
        self.assertEqual(self._v4_calls(mock_get), [])

    @patch("indicatorsets.utils.previews.requests.get")
    def test_preview_rejected_api_key_raises_instead_of_falling_back(self, mock_get):
        mock_get.side_effect = self._fake({"17031": 0.4}, v5_status=401)

        with self.assertRaises(InvalidApiKeyError):
            self._preview()
        self.assertEqual(self._v4_calls(mock_get), [])

    @patch("indicatorsets.utils.previews.requests.get")
    def test_preview_names_the_geos_neither_api_has_values_for(self, mock_get):
        mock_get.side_effect = self._fake(
            {"42003": None, "17031": 0.4}, v4_has_data=False
        )

        result = self._preview()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {"geo_value": "17031", "value": 0.4})
        self.assertEqual(
            result[1], {"message": "No data found for RSV ED Visits (county: 42003)."}
        )

    def _export_filled(self, geos=None):
        return generate_covidcast_indicators_export_url(
            [self.INDICATOR], "2024-01-01", "2024-03-01",
            geos or self.ALLEGHENY_AND_COOK, None, "csv", fill_method="fill_ave",
        )

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_filled_fill_method_v5_lacks_reports_no_data_without_v4(self, mock_get):
        """v4 has no fill_method, so it cannot serve a filled series.

        Live v5 nssp has no fill_ave rows at all; exporting v4's unfilled
        series instead would silently hand over something the user did not ask
        for.
        """
        mock_get.side_effect = self._fake({"42003": 0.1, "17031": 0.4})

        result = self._export_filled()

        self.assertEqual(
            result,
            [
                '<span class="text-muted">No data found for RSV ED Visits '
                "(county). Export skipped.</span>"
            ],
        )
        self.assertEqual(self._v4_calls(mock_get), [])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_filled_fill_method_exports_v5_geos_and_names_the_rest(self, mock_get):
        mock_get.side_effect = self._fake(
            {"42003": None, "17031": 0.4}, v5_fill_methods=("fill_ave",)
        )

        result = self._export_filled()

        self.assertEqual(len(result), 2)
        self.assertIn("geo_value=17031&", result[0])
        self.assertIn("fill_method=fill_ave", result[0])
        self.assertIn("No data found for RSV ED Visits (county: 42003)", result[1])
        self.assertEqual(self._v4_calls(mock_get), [])

    @patch("indicatorsets.utils.exports.logger")
    @patch("indicatorsets.utils.epidata.requests.get")
    def test_filled_fill_method_does_not_log_a_v4_fallback(self, mock_get, mock_logger):
        mock_get.side_effect = self._fake({"42003": None, "17031": 0.4})

        self._export_filled()

        mock_logger.warning.assert_not_called()

    @patch("indicatorsets.utils.previews.requests.get")
    def test_filled_fill_method_preview_reports_no_data_without_v4(self, mock_get):
        mock_get.side_effect = self._fake(
            {"42003": None, "17031": 0.4}, v5_fill_methods=("fill_ave",)
        )

        result = preview_covidcast_data(
            [self.INDICATOR], "2024-01-01", "2024-03-01", self.ALLEGHENY_AND_COOK,
            None, "json", fill_method="fill_ave",
        )

        self.assertEqual(
            result,
            [
                {"geo_value": "17031", "value": 0.4},
                {"message": "No data found for RSV ED Visits (county: 42003)."},
            ],
        )
        self.assertEqual(self._v4_calls(mock_get), [])

    @patch("indicatorsets.utils.epidata.requests.get")
    def test_export_still_falls_back_to_v4_for_an_explicit_source(self, mock_get):
        mock_get.side_effect = self._fake({"42003": None, "17031": 0.4})

        result = generate_covidcast_indicators_export_url(
            [self.INDICATOR], "2024-01-01", "2024-03-01", self.ALLEGHENY_AND_COOK,
            None, "csv", fill_method="source",
        )

        self.assertEqual(len(result), 2)
        self.assertIn("fill_method=source", result[0])
        self.assertIn("geo_values=42003&", result[1])

    @patch("indicatorsets.utils.previews.requests.get")
    def test_preview_still_falls_back_to_v4_for_an_explicit_source(self, mock_get):
        mock_get.side_effect = self._fake({"42003": None, "17031": 0.4})

        result = preview_covidcast_data(
            [self.INDICATOR], "2024-01-01", "2024-03-01", self.ALLEGHENY_AND_COOK,
            None, "json", fill_method="source",
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["epidata"]["geo_value"], "42003")


class V5RequestAuthAndFillMethodTests(V5RoutingTestMixin, TestCase):
    """Every v5 request carries ``token``/``fill_method`` only when the user set them.

    No user key means no token at all -- the server's own key is not borrowed
    -- and no fill_method means none is sent, so v5 applies its default
    (``source``); v5 rejects an empty ``fill_method=`` outright.
    """

    METADATA = {
        "nhsn": {"signals": ["confirmed_admissions_covid_ew"]},
        "fluview_ilinet": {"signals": ["wili"]},
    }
    COVIDCAST = [
        {
            "_endpoint": "covidcast",
            "data_source": "nhsn",
            "indicator": "confirmed_admissions_covid_ew",
            "time_type": "week",
        }
    ]
    COVIDCAST_GEOS = {"state": [{"id": "state:pa", "geoType": "state"}]}
    FLUVIEW = [{"_endpoint": "fluview", "data_source": "fluview", "indicator": "wili"}]
    POPHIVE = [{"_endpoint": "pophive", "indicator": "sig"}]
    POPHIVE_GEOS = [{"id": "ca", "geo_type": "state", "text": "CA"}]
    NWSS = [{"_endpoint": "nwss", "indicator": "sig"}]

    def _builders(self):
        start, end = "2024-01-01", "2024-03-01"
        return {
            "covidcast preview": lambda key, fill: preview_covidcast_data(
                self.COVIDCAST, start, end, self.COVIDCAST_GEOS, key, "json", fill
            ),
            "covidcast export": lambda key, fill: generate_covidcast_indicators_export_url(
                self.COVIDCAST, start, end, self.COVIDCAST_GEOS, key, "csv", fill
            ),
            "epiweek preview": lambda key, fill: preview_epiweek_data(
                EPIWEEK_SOURCES["fluview"], [{"id": "nat"}], start, end, key,
                "json", self.FLUVIEW, fill,
            ),
            "epiweek export": lambda key, fill: generate_epiweek_export_url(
                EPIWEEK_SOURCES["fluview"], [{"id": "nat"}], start, end, key,
                "csv", self.FLUVIEW, fill,
            ),
            "pophive preview": lambda key, fill: preview_pophive_data(
                self.POPHIVE, start, end, self.POPHIVE_GEOS, [{"id": "all"}], key,
                "json", fill,
            ),
            "pophive export": lambda key, fill: generate_pophive_export_url(
                self.POPHIVE, start, end, self.POPHIVE_GEOS, [{"id": "all"}], key,
                "csv", fill,
            ),
            "nwss preview": lambda key, fill: preview_nwss_data(
                self.NWSS, start, end, ["sewershed_1"], [{"id": "CDC_Biobot"}],
                fill, key, "json",
            ),
            "nwss export": lambda key, fill: generate_nwss_export_url(
                self.NWSS, start, end, ["sewershed_1"], [{"id": "CDC_Biobot"}],
                fill, key, "csv",
            ),
        }

    def _run(self, build, api_key, fill_method):
        """Return ``(v5 request params, generated output)`` for one builder."""
        cache.clear()
        with patch("indicatorsets.utils.epidata.requests.get") as mock_get:
            mock_get.side_effect = self._fake_get(metadata=self.METADATA)
            output = build(api_key, fill_method)
        v5_params = [
            call.kwargs["params"]
            for call in self._probe_calls(mock_get)
            if "/v5/" in call.args[0]
        ]
        return v5_params, output

    @override_settings(EPIDATA_API_KEY="server-key")
    def test_sends_neither_without_a_user_key_or_fill_method(self):
        for name, build in self._builders().items():
            with self.subTest(name):
                v5_params, output = self._run(build, None, "")
                self.assertTrue(v5_params, "expected a v5 request")
                for params in v5_params:
                    self.assertNotIn("token", params)
                    self.assertNotIn("fill_method", params)
                if name.endswith("export"):
                    text = "".join(output)
                    self.assertIn("/v5/viz/", text)
                    self.assertNotIn("fill_method", text)
                    self.assertNotIn("token", text)

    def test_sends_both_when_the_user_set_them(self):
        for name, build in self._builders().items():
            with self.subTest(name):
                v5_params, output = self._run(build, "user-key", "fill_ave")
                self.assertTrue(v5_params, "expected a v5 request")
                for params in v5_params:
                    self.assertEqual(params["token"], "user-key")
                    self.assertEqual(params["fill_method"], "fill_ave")
                if name.endswith("export"):
                    text = "".join(output)
                    self.assertIn("fill_method=fill_ave", text)
                    self.assertIn("token=user-key", text)


@override_settings(EPIDATA_API_KEY="server-key")
class V4KeySentAsHeaderTests(TestCase):
    """v4 requests send the key as basic auth, never as an ``api_key`` param.

    A key in the query string ends up in the URL, and so in any ``HTTPError``
    message, log line or Sentry event about the request.
    """

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _calls(self, target, run):
        with patch(target) as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"result": 1, "epidata": [], "message": "ok"}
            response.text = "a\n"
            mock_get.return_value = response
            run()
        return [c for c in mock_get.call_args_list if "/v5/" not in c.args[0]]

    def _cases(self, api_key):
        v4_indicator = {
            "_endpoint": "covidcast",
            "data_source": "src",
            "indicator": "sig",
            "time_type": "week",
        }
        geos = {"state": [{"id": "state:pa", "geoType": "state"}]}
        start, end = "2024-01-01", "2024-03-01"
        return {
            "covidcast preview": (
                "indicatorsets.utils.previews.requests.get",
                lambda: preview_covidcast_data(
                    [v4_indicator], start, end, geos, api_key, "json"
                ),
            ),
            "covidcast export": (
                "indicatorsets.utils.epidata.requests.get",
                lambda: generate_covidcast_indicators_export_url(
                    [v4_indicator], start, end, geos, api_key, "csv"
                ),
            ),
            "epiweek preview": (
                "indicatorsets.utils.previews.requests.get",
                lambda: preview_epiweek_data(
                    EPIWEEK_SOURCES["nidss_flu"], [{"id": "nationwide"}], start,
                    end, api_key, "json", [],
                ),
            ),
        }

    def test_user_key_goes_in_the_auth_header(self):
        for name, (target, run) in self._cases("user-key").items():
            with self.subTest(name):
                calls = self._calls(target, run)
                self.assertTrue(calls)
                for call in calls:
                    self.assertNotIn("api_key", call.kwargs["params"])
                    self.assertEqual(call.kwargs["auth"], ("epidata", "user-key"))

    def test_server_key_goes_in_the_auth_header_without_a_user_key(self):
        cases = self._cases(None)
        cases.update(
            {
                "geo coverage lookup": (
                    "indicatorsets.utils.geos.requests.get",
                    lambda: get_indicators_based_on_geo_epidata({"state": ["pa"]}),
                ),
                "covidcast coverage check": (
                    "indicatorsets.utils.geos.requests.get",
                    lambda: get_covidcast_geo_coverage("state:pa", [V4_ONLY]),
                ),
                "fluview coverage view": (
                    "indicatorsets.views.requests.get",
                    lambda: self.client.get(
                        reverse("check_fluview_geo_coverage"),
                        {
                            "geo": "nation:US",  # main-dropdown id
                            "indicators": json.dumps(
                                [{"data_source": "fluview", "indicator": "wili"}]
                            ),
                        },
                    ),
                ),
            }
        )
        for name, (target, run) in cases.items():
            with self.subTest(name):
                calls = self._calls(target, run)
                self.assertTrue(calls)
                for call in calls:
                    self.assertNotIn("api_key", call.kwargs["params"])
                    self.assertEqual(call.kwargs["auth"], ("epidata", "server-key"))


from indicatorsets.utils.locations import (  # noqa: E402
    FLUVIEW_ONLY_LEVELS,
    pophive_locations,
    split_locations,
    to_fluview_region,
    to_pophive_location,
    use_main_locations,
)


def _geo(location_id, text=None):
    geo_type = location_id.split(":", 1)[0]
    return {"id": location_id, "text": text or location_id, "geoType": geo_type}


class ToFluviewRegionTests(TestCase):
    def test_every_fluview_level(self):
        cases = {
            "nation:US": "nat",
            "nation:us": "nat",
            "hhs:3": "hhs3",
            "state:PA": "PA",
            "state:pa": "pa",
            "census-region:cen1": "cen1",
            "us-city:jfk": "jfk",
            "us-territory:pr": "pr",
            "ny_minus_jfk:ny_minus_jfk": "ny_minus_jfk",
        }
        for location_id, region in cases.items():
            with self.subTest(location_id):
                self.assertEqual(to_fluview_region(location_id), region)

    def test_levels_fluview_does_not_have(self):
        for location_id in ("county:42003", "msa:38300", "hrr:357", "", "pa", None):
            with self.subTest(location_id):
                self.assertIsNone(to_fluview_region(location_id))


class SplitLocationsTests(TestCase):
    def test_covidcast_only_payload(self):
        geos = {"county": [_geo("county:42003")], "state": [_geo("state:PA")]}
        covidcast, fluview = split_locations(geos)
        self.assertEqual(covidcast, geos)
        self.assertEqual(
            fluview, [{"id": "PA", "text": "state:PA", "location_id": "state:PA"}]
        )

    def test_fluview_only_levels_leave_the_covidcast_share(self):
        geos = {
            "census-region": [_geo("census-region:cen1", "Census Region 1")],
            "us-city": [_geo("us-city:jfk", "New York City")],
            "nation": [_geo("nation:US", "United States")],
        }
        covidcast, fluview = split_locations(geos)
        self.assertEqual(covidcast, {"nation": [_geo("nation:US", "United States")]})
        self.assertEqual([geo["id"] for geo in fluview], ["cen1", "jfk", "nat"])
        self.assertFalse(FLUVIEW_ONLY_LEVELS & set(covidcast))

    def test_one_place_at_two_levels_is_one_fluview_region(self):
        geos = {
            "state": [_geo("state:PR", "Puerto Rico")],
            "us-territory": [_geo("us-territory:pr", "Puerto Rico")],
        }
        _, fluview = split_locations(geos)
        self.assertEqual(
            fluview, [{"id": "PR", "text": "Puerto Rico", "location_id": "state:PR"}]
        )

    def test_nothing_selected_in_any_spelling(self):
        for empty in ({}, [], None):
            with self.subTest(empty=empty):
                self.assertEqual(split_locations(empty), ({}, []))


class UseMainLocationsTests(TestCase):
    def test_rewrites_both_location_keys_and_ignores_a_stale_fluview_key(self):
        data = {
            "covidCastGeographicValues": {"us-city": [_geo("us-city:jfk")]},
            "fluviewLocations": [{"id": "hhs9", "text": "HHS Region 9"}],
            "indicators": [FLUVIEW_V4_INDICATOR],
        }
        rewritten = use_main_locations(data)
        self.assertEqual(rewritten["covidCastGeographicValues"], {})
        self.assertEqual(
            rewritten["fluviewLocations"],
            [{"id": "jfk", "text": "us-city:jfk", "location_id": "us-city:jfk"}],
        )
        self.assertIn("us-city", data["covidCastGeographicValues"])  # input untouched


class FormViewsUseMainLocationsTests(TestCase):
    """Fluview locations come from the main dropdown in every form view."""

    FLUVIEW = {"_endpoint": "fluview", "data_source": "fluview", "indicator": "wili", "time_type": "week"}
    PAYLOAD = {
        "indicators": [FLUVIEW],
        "covidCastGeographicValues": {
            "us-city": [{"id": "us-city:jfk", "text": "New York City", "geoType": "us-city"}],
            "county": [{"id": "county:42003", "text": "Allegheny", "geoType": "county"}],
        },
        "fluviewLocations": [{"id": "hhs9", "text": "HHS Region 9"}],  # stale page
        "start_date": "2024-01-01",
        "end_date": "2024-03-01",
    }

    def _post(self, name, patched, payload=None):
        with patch(patched, return_value=[]) as mock_fn:
            self.client.post(
                reverse(name),
                data=json.dumps(payload or self.PAYLOAD),
                content_type="application/json",
            )
        return mock_fn

    def test_export_and_preview_and_query_code_get_fluview_regions(self):
        cases = {
            "export": "indicatorsets.views.generate_epiweek_export_url",
            "preview_data": "indicatorsets.views.preview_epiweek_data",
        }
        for name, target in cases.items():
            with self.subTest(name):
                mock_fn = self._post(name, target)
                geos = mock_fn.call_args.args[1]
                self.assertEqual([g["id"] for g in geos], ["jfk"])
        with patch(
            "indicatorsets.views.generate_query_code_epiweek", return_value=([], [])
        ) as mock_code:
            self.client.post(
                reverse("create_query_code"),
                data=json.dumps(self.PAYLOAD),
                content_type="application/json",
            )
        self.assertEqual([g["id"] for g in mock_code.call_args.args[1]], ["jfk"])

    def test_plot_gets_fluview_regions(self):
        with patch(
            "indicatorsets.views.generate_fluview_dataset_epivis", return_value=[]
        ) as mock_plot:
            self.client.post(
                reverse("epivis"),
                data=json.dumps(self.PAYLOAD),
                content_type="application/json",
            )
        self.assertEqual([g["id"] for g in mock_plot.call_args.args[1]], ["jfk"])

    def test_covidcast_never_gets_fluview_only_levels(self):
        mock_fn = self._post(
            "export",
            "indicatorsets.views.generate_covidcast_indicators_export_url",
        )
        self.assertEqual(list(mock_fn.call_args.args[3]), ["county"])

    def test_no_location_means_no_fluview_output(self):
        payload = {**self.PAYLOAD, "covidCastGeographicValues": {}}
        mock_fn = self._post(
            "export",
            "indicatorsets.views.generate_epiweek_export_url",
            payload,
        )
        mock_fn.assert_not_called()

    @patch("indicatorsets.views.log_form_stats")
    def test_logging_sees_the_translated_locations(self, mock_stats):
        self._post("preview_data", "indicatorsets.views.preview_epiweek_data")
        logged = mock_stats.call_args.args[1]
        self.assertEqual([g["id"] for g in logged["fluviewLocations"]], ["jfk"])


class FluviewEpivisSkipsByMainIdTests(TestCase):
    def test_skips_a_location_the_modal_marked_uncovered(self):
        from indicatorsets.utils.epivis import generate_fluview_dataset_epivis

        indicator = {
            "_endpoint": "fluview", "data_source": "fluview", "indicator": "wili",
            "indicator_set_short_name": "ILINet",
            "notCoveredGeos": ["us-city:ord"],
        }
        geos = [
            {"id": "ord", "text": "Chicago", "location_id": "us-city:ord"},
            {"id": "jfk", "text": "New York City", "location_id": "us-city:jfk"},
        ]
        datasets = generate_fluview_dataset_epivis(indicator, geos)
        self.assertEqual([d["params"]["regions"] for d in datasets], ["jfk"])


class CoverageChecksTakeMainIdsTests(TestCase):
    FLUVIEW = {"_endpoint": "fluview", "data_source": "fluview", "indicator": "wili"}

    @patch("indicatorsets.utils.geos.requests.get")
    def test_covidcast_check_answers_fluview_only_levels_without_epidata(self, mock_get):
        coverage = get_covidcast_geo_coverage("us-territory:pr", [NSSP_RSV])
        self.assertEqual(coverage[0]["covered"], False)
        self.assertIsNone(coverage[0]["route"])
        mock_get.assert_not_called()

    @patch("indicatorsets.views.requests.get")
    def test_fluview_check_translates_the_main_id(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"epidata": [{"wili": 1.5}]}
        )
        response = self.client.get(
            reverse("check_fluview_geo_coverage"),
            {"geo": "us-city:jfk", "indicators": json.dumps([self.FLUVIEW])},
        )
        self.assertEqual(mock_get.call_args.kwargs["params"]["regions"], "jfk")
        self.assertEqual(response.json()["not_covered_indicators"], [])

    @patch("indicatorsets.views.requests.get")
    def test_fluview_check_answers_untranslatable_ids_without_epidata(self, mock_get):
        response = self.client.get(
            reverse("check_fluview_geo_coverage"),
            {"geo": "county:42003", "indicators": json.dumps([self.FLUVIEW])},
        )
        mock_get.assert_not_called()
        self.assertEqual(
            [i["indicator"] for i in response.json()["not_covered_indicators"]], ["wili"]
        )


class AvailableGeosOfferFluviewPlacesTests(TestCase):
    def setUp(self):
        from base.models import Geography, GeographyUnit

        levels = {
            name: Geography.objects.create(name=name, display_name=f"{name} level")
            for name in ("state", "us-city", "county")
        }
        GeographyUnit.objects.create(geo_id="PA", name="PA", display_name="Pennsylvania", level=3, geo_level=levels["state"])
        GeographyUnit.objects.create(geo_id="jfk", name="jfk", display_name="New York City", level=4, geo_level=levels["us-city"])
        GeographyUnit.objects.create(geo_id="42003", name="42003", display_name="Allegheny", level=5, geo_level=levels["county"])

    def _ids(self, indicators):
        with patch("indicatorsets.views.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200, json=lambda: {"epidata": ["state:PA"]}
            )
            response = self.client.post(
                reverse("get_available_geos"),
                data=json.dumps({"indicators": indicators}),
                content_type="application/json",
            )
        return sorted(
            child["id"]
            for group in response.json()["geographic_granularities"]
            for child in group["children"]
        )

    def test_fluview_indicators_add_fluview_places_once(self):
        indicators = [
            {"_endpoint": "covidcast", "data_source": "src", "indicator": "sig"},
            {"_endpoint": "fluview", "data_source": "fluview", "indicator": "wili"},
        ]
        self.assertEqual(self._ids(indicators), ["state:PA", "us-city:jfk"])

    def test_without_fluview_only_covidcast_coverage(self):
        indicators = [{"_endpoint": "covidcast", "data_source": "src", "indicator": "sig"}]
        self.assertEqual(self._ids(indicators), ["state:PA"])


class FilterPanelIncludesFluviewTests(TestCase):
    def test_census_division_and_city_include_fluview_sets(self):
        from indicatorsets.filters import IndicatorSetFilter

        for location in ("census-region:cen1", "us-city:jfk", "state:PA"):
            with self.subTest(location):
                self.assertTrue(IndicatorSetFilter.include_fluview(str([location])))
        self.assertFalse(IndicatorSetFilter.include_fluview(str(["county:42003"])))


class CovidcastOnlySelectionHasNoFluviewTests(TestCase):
    """A covidcast-only selection is unchanged by fluview sharing the dropdown."""

    PAYLOAD = {
        "indicators": [
            {"_endpoint": "covidcast", "data_source": "src", "indicator": "sig", "time_type": "day"}
        ],
        "covidCastGeographicValues": {
            "state": [{"id": "state:PA", "text": "Pennsylvania", "geoType": "state"}],
            "nation": [{"id": "nation:US", "text": "United States", "geoType": "nation"}],
        },
        "start_date": "2024-01-01",
        "end_date": "2024-03-01",
    }

    def test_use_main_locations_gives_fluview_nothing(self):
        rewritten = use_main_locations(self.PAYLOAD)
        self.assertEqual(rewritten["fluviewLocations"], [])
        self.assertEqual(
            rewritten["covidCastGeographicValues"],
            self.PAYLOAD["covidCastGeographicValues"],
        )

    @patch("indicatorsets.views.log_form_stats")
    @patch("indicatorsets.views.generate_query_code_epiweek", return_value=([], []))
    @patch("indicatorsets.views.preview_epiweek_data", return_value=[])
    @patch("indicatorsets.views.generate_epiweek_export_url", return_value=[])
    @patch("indicatorsets.views.preview_covidcast_data", return_value=[])
    @patch("indicatorsets.views.generate_covidcast_indicators_export_url", return_value=[])
    def test_views_emit_no_fluview_output(
        self, _export_cc, _preview_cc, mock_export, mock_preview, mock_code, mock_stats
    ):
        for name in ("export", "preview_data", "create_query_code"):
            self.client.post(
                reverse(name), data=json.dumps(self.PAYLOAD), content_type="application/json"
            )
        mock_export.assert_not_called()
        mock_preview.assert_not_called()
        mock_code.assert_not_called()
        for call in mock_stats.call_args_list:
            self.assertEqual(call.args[1]["fluviewLocations"], [])


class ModalScriptsAreVersionedTests(TestCase):
    """The two modal scripts call into each other, so a browser must never pair
    a fresh copy of one with a cached copy of the other."""

    def test_both_scripts_carry_the_app_version(self):
        response = self.client.get(reverse("indicatorsets"))
        for script in ("js/indicatorHandler.js", "js/selectedIndicatorsModal.js"):
            with self.subTest(script):
                self.assertContains(response, f"{script}?v={settings.APP_VERSION}")


class FluviewCheckFiltersUntranslatableAnswerTests(TestCase):
    @patch("indicatorsets.views.requests.get")
    def test_only_fluview_indicators_come_back_for_a_county(self, mock_get):
        indicators = [
            {"_endpoint": "fluview", "data_source": "fluview", "indicator": "wili"},
            {"_endpoint": "fluview", "data_source": "fluview_clinical", "indicator": "percent_positive"},
            {"_endpoint": "covidcast", "data_source": "nssp", "indicator": "smoothed_pct_ed_visits_rsv"},
        ]
        response = self.client.get(
            reverse("check_fluview_geo_coverage"),
            {"geo": "county:42003", "indicators": json.dumps(indicators)},
        )
        mock_get.assert_not_called()
        self.assertEqual(
            [i["indicator"] for i in response.json()["not_covered_indicators"]],
            ["wili", "percent_positive"],
        )



POPHIVE_INDICATOR = {"_endpoint": "pophive", "data_source": "pophive", "indicator": "covid_pct_ed"}


class ToPophiveLocationTests(TestCase):
    def test_nation_hhs_and_states(self):
        cases = {
            "nation:US": {"geo_type": "nation", "id": "us"},
            "hhs:3": {"geo_type": "hhs", "id": "3"},
            "state:PA": {"geo_type": "state", "id": "pa"},
            "state:pa": {"geo_type": "state", "id": "pa"},
            "state:DC": {"geo_type": "state", "id": "dc"},
        }
        for location_id, location in cases.items():
            with self.subTest(location_id):
                self.assertEqual(to_pophive_location(location_id), location)

    def test_places_pophive_has_no_data_for(self):
        for location_id in (
            "state:PR", "state:AS", "state:GU", "state:MP", "state:VI",
            "us-territory:pr", "county:42003", "census-region:cen1", "us-city:jfk",
            "", "pa", None,
        ):
            with self.subTest(location_id):
                self.assertIsNone(to_pophive_location(location_id))


class PophiveLocationsTests(TestCase):
    def test_translates_and_dedupes_case_variants(self):
        geos = {
            "state": [_geo("state:PA", "Pennsylvania"), _geo("state:pa", "pa")],
            "nation": [_geo("nation:US", "United States")],
            "county": [_geo("county:42003", "Allegheny")],
        }
        self.assertEqual(
            pophive_locations(geos),
            [
                {"id": "pa", "geo_type": "state", "text": "Pennsylvania", "location_id": "state:PA"},
                {"id": "us", "geo_type": "nation", "text": "United States", "location_id": "nation:US"},
            ],
        )

    def test_nothing_selected_in_any_spelling(self):
        for empty in ({}, [], None):
            with self.subTest(empty=empty):
                self.assertEqual(pophive_locations(empty), [])


class UseMainLocationsForPophiveTests(TestCase):
    GEOS = {"state": [_geo("state:PA", "Pennsylvania")]}

    def test_pophive_gets_the_main_locations_and_a_stale_key_is_replaced(self):
        rewritten = use_main_locations(
            {
                "indicators": [POPHIVE_INDICATOR],
                "covidCastGeographicValues": self.GEOS,
                "pophiveLocations": [{"id": "ca", "geo_type": "state", "text": "CA"}],
            }
        )
        self.assertEqual(
            rewritten["pophiveLocations"],
            [{"id": "pa", "geo_type": "state", "text": "Pennsylvania", "location_id": "state:PA"}],
        )

    def test_no_pophive_indicator_means_no_pophive_locations(self):
        rewritten = use_main_locations(
            {
                "indicators": [{"_endpoint": "covidcast", "data_source": "src", "indicator": "sig"}],
                "covidCastGeographicValues": self.GEOS,
            }
        )
        self.assertEqual(rewritten["pophiveLocations"], [])


class FormViewsGivePophiveMainLocationsTests(TestCase):
    PAYLOAD = {
        "indicators": [POPHIVE_INDICATOR],
        "covidCastGeographicValues": {
            "state": [{"id": "state:PA", "text": "Pennsylvania", "geoType": "state"}],
            "county": [{"id": "county:42003", "text": "Allegheny", "geoType": "county"}],
        },
        "pophiveLocations": [{"id": "ca", "geo_type": "state", "text": "CA"}],  # stale page
        "pophiveAgeGroup": [{"id": "all", "text": "all"}],
        "start_date": "2024-01-01",
        "end_date": "2024-03-01",
    }

    def _post(self, name, target, returns=None):
        with patch(target, return_value=[] if returns is None else returns) as mock_fn:
            self.client.post(
                reverse(name), data=json.dumps(self.PAYLOAD), content_type="application/json"
            )
        return mock_fn

    def test_every_view_gets_the_translated_locations(self):
        cases = {
            "export": ("indicatorsets.views.generate_pophive_export_url", 3, None),
            "preview_data": ("indicatorsets.views.preview_pophive_data", 3, None),
            "create_query_code": ("indicatorsets.views.generate_query_code_pophive", 3, ([], [])),
            "epivis": ("indicatorsets.views.generate_pophive_dataset_epivis", 1, None),
        }
        for name, (target, position, returns) in cases.items():
            with self.subTest(name):
                mock_fn = self._post(name, target, returns)
                geos = mock_fn.call_args.args[position]
                self.assertEqual([(g["geo_type"], g["id"]) for g in geos], [("state", "pa")])


class AvailableGeosOfferPophivePlacesTests(TestCase):
    def setUp(self):
        from base.models import Geography, GeographyUnit

        levels = {
            name: Geography.objects.create(name=name, display_name=f"{name} level")
            for name in ("nation", "state", "us-city", "county")
        }
        for level, geo_id in (
            ("nation", "US"), ("state", "PA"), ("state", "PR"),
            ("us-city", "jfk"), ("county", "42003"),
        ):
            GeographyUnit.objects.create(
                geo_id=geo_id, name=geo_id, display_name=geo_id, level=1, geo_level=levels[level]
            )

    def test_pophive_indicators_add_nation_hhs_and_states_without_territories(self):
        with patch("indicatorsets.views.requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=lambda: {"epidata": []})
            response = self.client.post(
                reverse("get_available_geos"),
                data=json.dumps({"indicators": [POPHIVE_INDICATOR]}),
                content_type="application/json",
            )
        ids = sorted(
            child["id"]
            for group in response.json()["geographic_granularities"]
            for child in group["children"]
        )
        self.assertEqual(ids, ["nation:US", "state:PA"])


class CheckPophiveGeoCoverageTests(TestCase):
    def _check(self, geo, indicators):
        return self.client.post(
            reverse("check_pophive_geo_coverage"),
            data=json.dumps({"geo": geo, "indicators": indicators}),
            content_type="application/json",
        )

    @patch("indicatorsets.views.requests.get")
    def test_county_and_territory_are_not_covered_without_epidata(self, mock_get):
        for geo in ("county:42003", "state:PR", "us-city:jfk"):
            with self.subTest(geo):
                response = self._check(geo, [POPHIVE_INDICATOR])
                self.assertEqual(
                    [i["indicator"] for i in response.json()["not_covered_indicators"]],
                    ["covid_pct_ed"],
                )
        mock_get.assert_not_called()

    def test_nation_hhs_and_state_are_covered(self):
        for geo in ("nation:US", "hhs:3", "state:PA"):
            with self.subTest(geo):
                response = self._check(geo, [POPHIVE_INDICATOR])
                self.assertEqual(response.json()["not_covered_indicators"], [])

    def test_only_pophive_indicators_are_answered(self):
        response = self._check(
            "county:42003",
            [POPHIVE_INDICATOR, {"_endpoint": "covidcast", "data_source": "src", "indicator": "sig"}],
        )
        self.assertEqual(
            [i["indicator"] for i in response.json()["not_covered_indicators"]],
            ["covid_pct_ed"],
        )

    def test_rejects_get_and_bad_bodies(self):
        self.assertEqual(self.client.get(reverse("check_pophive_geo_coverage")).status_code, 405)
        response = self.client.post(
            reverse("check_pophive_geo_coverage"), data="not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
