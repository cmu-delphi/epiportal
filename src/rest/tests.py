from unittest.mock import MagicMock, patch
from django.test import TestCase
from django.urls import reverse
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
            {"geo_type": "state", "geo_value": "pa", "pathogen": self.pathogen.id},
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
            {"geo_type": "state", "geo_value": "pa", "pathogen": self.pathogen.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"indicators": []})

    def test_invalid_pathogen_returns_400(self):
        response = self.client.get(
            reverse("available-indicators"),
            {"geo_type": "state", "geo_value": "pa", "pathogen": 99999},
        )
        self.assertEqual(response.status_code, 400)
