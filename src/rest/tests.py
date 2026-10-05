from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch, get_resolver, resolve, reverse
from django.urls.exceptions import Resolver404
from base.models import Pathogen
from datasources.models import SourceSubdivision
from indicators.models import Indicator


class AvailableIndicatorsViewTests(TestCase):
    def setUp(self):
        self.pathogen = Pathogen.objects.create(name="COVID-19", used_in="indicators")
        self.source = SourceSubdivision.objects.create(name="nssp")
        self.indicator = Indicator.objects.create(
            name="pct_ed_visits_covid", source=self.source
        )
        self.indicator.pathogens.add(self.pathogen)
        # An indicator with the pathogen but NOT reported for the geo
        other = Indicator.objects.create(name="unavailable_signal", source=self.source)
        other.pathogens.add(self.pathogen)

    @patch("rest.utils.requests.get")
    def test_returns_only_available_pathogen_indicators(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "values": [{"source": "nssp", "signal": "pct_ed_visits_covid"}]
        }
        mock_get.return_value = mock_response
        response = self.client.get(
            reverse("available-indicators"),
            {"geo_type": "state", "geo_value": "pa", "pathogen": self.pathogen.name},
        )
        self.assertEqual(response.status_code, 200)
        names = [i["name"] for i in response.json()["indicators"]]
        self.assertEqual(names, ["pct_ed_visits_covid"])

    @patch("rest.utils.requests.get")
    def test_empty_when_epidata_fails(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException
        response = self.client.get(
            reverse("available-indicators"),
            {"geo_type": "state", "geo_value": "pa", "pathogen": self.pathogen.name},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"indicators": []})

    def test_invalid_pathogen_returns_400(self):
        response = self.client.get(
            reverse("available-indicators"),
            {"geo_type": "state", "geo_value": "pa", "pathogen": "no-such-pathogen"},
        )
        self.assertEqual(response.status_code, 400)


class UrlConfTests(SimpleTestCase):
    """The project URL conf has to import cleanly.

    A router registration that collides on basename, or a ViewSet routed
    without an action map, raises at import time and takes down every route in
    the project -- not just its own. Nothing else in the suite loads the URL
    conf eagerly, so without this the failure only shows at container start.
    """

    def test_project_url_conf_imports(self):
        get_resolver().url_patterns


class IndicatorMetaViewTests(TestCase):
    """The meta endpoint answers "what indicators does each source publish?"."""

    def setUp(self):
        nssp = SourceSubdivision.objects.create(name="nssp")
        chng = SourceSubdivision.objects.create(name="chng")
        Indicator.objects.create(name="pct_ed_visits_rsv", source=nssp)
        Indicator.objects.create(name="pct_ed_visits_covid", source=nssp)
        Indicator.objects.create(name="7dav_inpatient_covid", source=chng)
        Indicator.objects.create(name="orphan_signal", source=None)

    def _get(self):
        response = self.client.get(reverse("meta-indicators"))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_groups_indicator_names_under_their_source(self):
        self.assertIn(
            {
                "source": "nssp",
                "indicators": ["pct_ed_visits_covid", "pct_ed_visits_rsv"],
            },
            self._get(),
        )

    def test_returns_one_entry_per_source_ordered_by_name(self):
        self.assertEqual(
            [entry["source"] for entry in self._get()], ["chng", "nssp", "unknown"]
        )

    def test_sourceless_indicators_group_under_a_placeholder(self):
        """Half the table has no source, so they need somewhere to go."""
        self.assertIn(
            {"source": "unknown", "indicators": ["orphan_signal"]}, self._get()
        )

    def test_indicators_are_plain_names(self):
        for entry in self._get():
            for indicator in entry["indicators"]:
                self.assertIsInstance(indicator, str)

    def test_groups_the_whole_table_in_one_query(self):
        """Grouping in Python must not turn into a query per source."""
        with self.assertNumQueries(1):
            self.client.get(reverse("meta-indicators"))

    def test_rejects_writes(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(reverse("meta-indicators"))
                self.assertEqual(response.status_code, 405)
