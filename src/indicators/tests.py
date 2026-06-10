from django.test import TestCase

from base.models import Geography, Pathogen, SeverityPyramidRung
from datasources.models import SourceSubdivision
from indicators.models import (
    Category,
    FormatType,
    Indicator,
    IndicatorGeography,
    IndicatorType,
    NonDelphiIndicator,
    OtherEndpointIndicator,
    USStateIndicator,
)
from indicators.resources import (
    IndicatorResource,
    NonDelphiIndicatorResource,
    fix_boolean_fields,
    process_category,
    process_format_type,
    process_indicator_set,
    process_indicator_type,
    process_pathogens,
    process_severity_pyramid_rungs,
    process_source,
)
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
            source_type="covidcast",
        )

    def test_get_display_name_prefers_display_name(self):
        indicator = Indicator.objects.create(
            name="sig",
            display_name="Signal label",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="covidcast",
        )
        self.assertEqual(indicator.get_display_name, "Signal label")

    def test_get_display_name_uses_member_name_when_no_display_name(self):
        indicator = Indicator.objects.create(
            name="sig",
            member_name="Member label",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="covidcast",
        )
        self.assertEqual(indicator.get_display_name, "Member label")

    def test_get_display_name_falls_back_to_name(self):
        indicator = Indicator.objects.create(
            name="raw_signal",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="covidcast",
        )
        self.assertEqual(indicator.get_display_name, "raw_signal")


class IndicatorGeographyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = SourceSubdivision.objects.create(name="geo_src")
        cls.indicator_set = IndicatorSet.objects.create(
            name="Geo set",
            source_type="covidcast",
        )
        cls.indicator = Indicator.objects.create(
            name="geo_sig",
            source=cls.source,
            indicator_set=cls.indicator_set,
            source_type="covidcast",
        )
        cls.geography = Geography.objects.create(
            name="state",
            display_name="State",
            used_in="indicators",
        )

    def test_display_name_when_aggregated_by_delphi(self):
        link = IndicatorGeography.objects.create(
            geography=self.geography,
            indicator=self.indicator,
            aggregated_by_delphi=True,
        )
        self.assertEqual(link.display_name, "State (by Delphi)")

    def test_display_name_when_not_aggregated(self):
        link = IndicatorGeography.objects.create(
            geography=self.geography,
            indicator=self.indicator,
            aggregated_by_delphi=False,
        )
        self.assertEqual(link.display_name, "State")


class IndicatorProxyModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = SourceSubdivision.objects.create(name="proxy_src")
        cls.indicator_set = IndicatorSet.objects.create(
            name="Proxy set",
            source_type="covidcast",
        )

    def test_other_endpoint_proxy_resolves_same_row(self):
        indicator = Indicator.objects.create(
            name="oe_sig",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="other_endpoint",
        )
        proxy = OtherEndpointIndicator.objects.get(pk=indicator.pk)
        self.assertIsInstance(proxy, OtherEndpointIndicator)
        self.assertEqual(proxy.source_type, "other_endpoint")

    def test_non_delphi_proxy_resolves_same_row(self):
        indicator = Indicator.objects.create(
            name="nd_sig",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="non_delphi",
        )
        proxy = NonDelphiIndicator.objects.get(pk=indicator.pk)
        self.assertIsInstance(proxy, NonDelphiIndicator)

    def test_us_state_proxy_resolves_same_row(self):
        indicator = Indicator.objects.create(
            name="state_sig",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="us_state",
        )
        proxy = USStateIndicator.objects.get(pk=indicator.pk)
        self.assertIsInstance(proxy, USStateIndicator)
        self.assertEqual(proxy.source_type, "us_state")


class IndicatorImportResourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = SourceSubdivision.objects.create(name="import_src")
        cls.indicator_set = IndicatorSet.objects.create(
            name="Import test set",
            source_type="covidcast",
        )

    def test_non_delphi_import_only_deletes_other_non_delphi_indicators(self):
        covidcast_indicator = Indicator.objects.create(
            name="covidcast_sig",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="covidcast",
        )
        kept_non_delphi = Indicator.objects.create(
            name="kept_non_delphi",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="non_delphi",
        )
        removed_non_delphi = Indicator.objects.create(
            name="removed_non_delphi",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="non_delphi",
        )

        resource = NonDelphiIndicatorResource()
        resource.imported_rows_pks = [kept_non_delphi.pk]
        resource.after_import(None, None, dry_run=False)

        self.assertTrue(Indicator.objects.filter(pk=covidcast_indicator.pk).exists())
        self.assertTrue(Indicator.objects.filter(pk=kept_non_delphi.pk).exists())
        self.assertFalse(Indicator.objects.filter(pk=removed_non_delphi.pk).exists())

    def test_covidcast_import_only_deletes_other_covidcast_indicators(self):
        non_delphi_indicator = Indicator.objects.create(
            name="non_delphi_sig",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="non_delphi",
        )
        kept_covidcast = Indicator.objects.create(
            name="kept_covidcast",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="covidcast",
        )
        removed_covidcast = Indicator.objects.create(
            name="removed_covidcast",
            source=self.source,
            indicator_set=self.indicator_set,
            source_type="covidcast",
        )

        resource = IndicatorResource()
        resource.imported_rows_pks = [kept_covidcast.pk]
        resource.after_import(None, None, dry_run=False)

        self.assertTrue(Indicator.objects.filter(pk=non_delphi_indicator.pk).exists())
        self.assertTrue(Indicator.objects.filter(pk=kept_covidcast.pk).exists())
        self.assertFalse(Indicator.objects.filter(pk=removed_covidcast.pk).exists())


class IndicatorCategoryTests(TestCase):
    def test_category_str(self):
        category = Category.objects.create(name="hospital", display_name="Hospital")
        self.assertEqual(str(category), "Hospital")


class IndicatorResourceProcessorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.indicator_set = IndicatorSet.objects.create(
            name="Import test set",
            source_type="covidcast",
        )
        cls.source = SourceSubdivision.objects.create(name="import_src")

    def test_fix_boolean_fields_converts_strings(self):
        row = {
            "Active": "TRUE",
            "Is Smoothed": "FALSE",
            "Is Weighted": "",
        }
        fix_boolean_fields(row)
        self.assertTrue(row["Active"])
        self.assertFalse(row["Is Smoothed"])
        self.assertFalse(row["Is Weighted"])

    def test_process_pathogens_creates_pathogen_ids(self):
        row = {"Pathogen/\nDisease Area": "Flu, COVID-19"}
        process_pathogens(row)
        self.assertEqual(Pathogen.objects.filter(used_in="indicators").count(), 2)
        self.assertRegex(row["Pathogen/\nDisease Area"], r"^\d+,\d+$")

    def test_process_indicator_set_maps_existing_set(self):
        row = {"Indicator Set": "Import test set"}
        process_indicator_set(row)
        self.assertEqual(row["Indicator Set"], self.indicator_set.id)

    def test_process_indicator_type_creates_type(self):
        row = {"Indicator Type": "rate"}
        process_indicator_type(row)
        self.assertEqual(IndicatorType.objects.get(name="rate").id, row["Indicator Type"])

    def test_process_format_type_creates_format(self):
        row = {"Format": "percentage"}
        process_format_type(row)
        self.assertEqual(FormatType.objects.get(name="percentage").id, row["Format"])

    def test_process_format_type_empty_becomes_none(self):
        row = {"Format": ""}
        process_format_type(row)
        self.assertIsNone(row["Format"])

    def test_process_severity_pyramid_rungs_defaults_to_na(self):
        row = {"Surveillance Categories": ""}
        process_severity_pyramid_rungs(row)
        self.assertTrue(
            SeverityPyramidRung.objects.filter(name="N/A", used_in="indicators").exists()
        )

    def test_process_category_creates_category(self):
        row = {"Category": "syndromic"}
        process_category(row)
        self.assertEqual(Category.objects.get(name="syndromic").id, row["Category"])

    def test_process_source_links_existing_source(self):
        row = {"Source Subdivision": "import_src"}
        process_source(row)
        self.assertEqual(row["Source Subdivision"], self.source.id)
