from django.test import TestCase

from datasources.models import SourceSubdivision
from indicators.models import Category, FormatType, Indicator, IndicatorType
from indicatorsets.models import IndicatorSet


class IndicatorTaxonomyModelTests(TestCase):
    def test_indicator_type_str_uses_display_name(self):
        indicator_type = IndicatorType.objects.create(
            name="pct",
            display_name="Percent",
        )
        self.assertEqual(str(indicator_type), "Percent")

    def test_format_type_str_uses_display_name(self):
        format_type = FormatType.objects.create(name="pct", display_name="Percent")
        self.assertEqual(str(format_type), "Percent")


class IndicatorDisplayNameTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = SourceSubdivision.objects.create(name="covid_src")
        cls.indicator_set = IndicatorSet.objects.create(
            name="Covid indicators",
            kind="delphi",
        )

    def test_get_display_name_prefers_display_name(self):
        indicator = Indicator.objects.create(
            name="sig",
            display_name="Signal label",
            source=self.source,
            indicator_set=self.indicator_set,
        )
        self.assertEqual(indicator.get_display_name, "Signal label")

    def test_get_display_name_falls_back_to_name(self):
        indicator = Indicator.objects.create(
            name="raw_signal",
            source=self.source,
            indicator_set=self.indicator_set,
        )
        self.assertEqual(indicator.get_display_name, "raw_signal")


class IndicatorOngoingTests(TestCase):
    def test_ongoing_defaults_to_false(self):
        indicator = Indicator.objects.create(name="sig")
        self.assertIs(indicator.ongoing, False)


class IndicatorCategoryTests(TestCase):
    def test_category_str(self):
        category = Category.objects.create(name="hospital", display_name="Hospital")
        self.assertEqual(str(category), "Hospital")
