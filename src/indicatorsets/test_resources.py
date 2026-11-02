from django.test import TestCase
from tablib import Dataset

from alternative_interface.models import ExpressViewIndicator
from datasources.models import SourceSubdivision
from indicators.models import Indicator
from indicatorsets.models import IndicatorSet
from indicatorsets.resources import IndicatorSetResource

SETS_HEADER = (
    "indicator_set,short_name,description,show_in_epiportal,kind,maintainer,"
    "email_of_maintainer,original_data_provider,v4_endpoint,language,"
    "source_dataset,pathogen,types_of_data,geographic_scope,geographic_levels,"
    "pre_processing,temporal_granularity,temporal_scope_start,"
    "temporal_scope_start_note,temporal_scope_end,temporal_scope_end_note,"
    "ongoing,reporting_cadence,update_day,reporting_lag,revision_cadence,"
    "population,population_stratifiers,surveillance_categories,censoring,"
    "missingness,dua_required,data_use_terms,dataset_location,data_format,"
    "documentation_link"
).split(",")

ROW_DEFAULTS = {
    "show_in_epiportal": "TRUE",
    "kind": "delphi",
    "original_data_provider": "CDC",
}


def sets_dataset(*rows: dict) -> Dataset:
    dataset = Dataset(headers=SETS_HEADER)
    for row in rows:
        values = {**ROW_DEFAULTS, **row}
        dataset.append([values.get(column, "") for column in SETS_HEADER])
    return dataset


def run_import(dataset: Dataset) -> tuple[IndicatorSetResource, object]:
    resource = IndicatorSetResource()
    result = resource.import_data(dataset, dry_run=False, raise_errors=True)
    return resource, result


class IndicatorSetResourceTests(TestCase):
    def test_maps_columns(self):
        run_import(
            sets_dataset(
                {
                    "indicator_set": "COVIDcast",
                    "short_name": "CC",
                    "description": "Signals",
                    "maintainer": "Delphi",
                    "email_of_maintainer": "delphi@example.com",
                    "v4_endpoint": "covidcast",
                    "language": "English",
                    "source_dataset": "Claims",
                    "pathogen": "COVID-19, RSV",
                    "types_of_data": "Counts",
                    "geographic_scope": "USA",
                    "geographic_levels": "state, county",
                    "pre_processing": "Smoothed",
                    "temporal_granularity": "Daily",
                    "temporal_scope_start": "2020w05",
                    "temporal_scope_end": "2023-05-01",
                    "ongoing": "TRUE",
                    "reporting_cadence": "Daily",
                    "reporting_lag": "1 day",
                    "revision_cadence": "Weekly",
                    "population": "All",
                    "population_stratifiers": "Age",
                    "surveillance_categories": "public, ambulatory",
                    "censoring": "None",
                    "missingness": "Some",
                    "dua_required": "FALSE",
                    "data_use_terms": "CC BY",
                    "dataset_location": "Delphi",
                    "documentation_link": "https://example.com",
                }
            )
        )

        indicator_set = IndicatorSet.objects.get(name="COVIDcast")
        self.assertEqual(indicator_set.short_name, "CC")
        self.assertEqual(indicator_set.description, "Signals")
        self.assertEqual(indicator_set.kind, "delphi")
        self.assertEqual(indicator_set.maintainer_name, "Delphi")
        self.assertEqual(indicator_set.maintainer_email, "delphi@example.com")
        self.assertEqual(indicator_set.original_data_provider.name, "CDC")
        self.assertEqual(indicator_set.epidata_endpoint, "covidcast")
        self.assertEqual(indicator_set.language, "English")
        self.assertEqual(indicator_set.origin_datasource, "Claims")
        self.assertEqual(
            sorted(indicator_set.pathogens.values_list("name", flat=True)),
            ["COVID-19", "RSV"],
        )
        self.assertEqual(
            set(indicator_set.pathogens.values_list("used_in", flat=True)),
            {"indicatorsets"},
        )
        self.assertEqual(indicator_set.data_type, "Counts")
        self.assertEqual(indicator_set.geographic_scope.name, "USA")
        self.assertEqual(
            sorted(indicator_set.geographic_levels.values_list("name", flat=True)),
            ["county", "state"],
        )
        self.assertEqual(indicator_set.preprocessing_description, "Smoothed")
        self.assertEqual(indicator_set.temporal_granularity, "Daily")
        self.assertEqual(indicator_set.temporal_scope_start, "2020-01-26")
        self.assertEqual(indicator_set.temporal_scope_end, "2023-05-01")
        self.assertIs(indicator_set.ongoing, True)
        self.assertEqual(indicator_set.reporting_cadence, "Daily")
        self.assertEqual(indicator_set.reporting_lag, "1 day")
        self.assertEqual(indicator_set.revision_cadence, "Weekly")
        self.assertEqual(indicator_set.demographic_scope, "All")
        self.assertEqual(indicator_set.demographic_granularity, "Age")
        self.assertEqual(
            sorted(
                indicator_set.severity_pyramid_rungs.values_list("name", flat=True)
            ),
            ["ambulatory", "public"],
        )
        self.assertEqual(indicator_set.censoring, "None")
        self.assertEqual(indicator_set.missingness, "Some")
        self.assertIs(indicator_set.dua_required, False)
        self.assertEqual(indicator_set.license, "CC BY")
        self.assertEqual(indicator_set.dataset_location, "Delphi")
        self.assertEqual(indicator_set.documentation_link, "https://example.com")

    def test_dua_required_true(self):
        run_import(sets_dataset({"indicator_set": "Restricted", "dua_required": "TRUE"}))
        self.assertIs(IndicatorSet.objects.get(name="Restricted").dua_required, True)

    def test_strips_whitespace(self):
        run_import(sets_dataset({"indicator_set": "  NHSN  ", "short_name": " N "}))
        self.assertEqual(IndicatorSet.objects.get(name="NHSN").short_name, "N")

    def test_hidden_set_is_deleted_with_indicators_and_dashboard_rows(self):
        indicator_set = IndicatorSet.objects.create(name="Old set", kind="delphi")
        indicator = Indicator.objects.create(
            name="sig",
            source=SourceSubdivision.objects.create(name="src"),
            indicator_set=indicator_set,
        )
        ExpressViewIndicator.objects.create(
            menu_item="Menu", indicator=indicator, display_name="Sig"
        )

        _, result = run_import(
            sets_dataset({"indicator_set": "Old set", "show_in_epiportal": "FALSE"})
        )

        self.assertFalse(result.has_errors())
        self.assertFalse(IndicatorSet.objects.exists())
        self.assertFalse(Indicator.objects.exists())
        self.assertFalse(ExpressViewIndicator.objects.exists())

    def test_set_missing_from_sheet_is_deleted(self):
        IndicatorSet.objects.create(name="Gone", kind="us_states")
        run_import(sets_dataset({"indicator_set": "Kept"}))
        self.assertEqual(
            list(IndicatorSet.objects.values_list("name", flat=True)), ["Kept"]
        )

    def test_empty_name_is_skipped(self):
        run_import(sets_dataset({"indicator_set": "", "short_name": "No id"}))
        self.assertFalse(IndicatorSet.objects.exists())

    def test_duplicate_names_first_row_wins_with_warning(self):
        resource, _ = run_import(
            sets_dataset(
                {"indicator_set": "Hawaii RSV testing", "pathogen": "RSV"},
                {
                    "indicator_set": "Hawaii RSV testing ",
                    "pathogen": "Influenza (seasonal)",
                },
            )
        )

        indicator_set = IndicatorSet.objects.get(name="Hawaii RSV testing")
        self.assertEqual(
            list(indicator_set.pathogens.values_list("name", flat=True)), ["RSV"]
        )
        self.assertIn("Hawaii RSV testing", " ".join(resource.warnings))

    def test_identical_duplicates_do_not_warn(self):
        row = {"indicator_set": "Same", "pathogen": "RSV"}
        resource, _ = run_import(sets_dataset(row, row))
        self.assertEqual(IndicatorSet.objects.count(), 1)
        self.assertEqual(resource.warnings, [])

    def test_warnings_default_to_empty_list(self):
        self.assertEqual(IndicatorSetResource().warnings, [])

    def test_original_data_provider_group(self):
        run_import(
            sets_dataset(
                {
                    "indicator_set": "State set",
                    "kind": "us_states",
                    "original_data_provider": "PA DOH",
                },
                {
                    "indicator_set": "Other set",
                    "kind": "non_delphi",
                    "original_data_provider": "Acme Labs",
                },
                {
                    "indicator_set": "Federal set",
                    "kind": "delphi",
                    "original_data_provider": "US CDC",
                },
            )
        )

        def group(name):
            return IndicatorSet.objects.get(name=name).original_data_provider.group

        self.assertEqual(group("State set"), "us_states")
        self.assertEqual(group("Other set"), "individual")
        self.assertEqual(group("Federal set"), "us_government")

    def test_empty_data_use_terms_becomes_none_found(self):
        run_import(sets_dataset({"indicator_set": "No terms", "data_use_terms": ""}))
        self.assertEqual(IndicatorSet.objects.get(name="No terms").license, "None found")

    def test_unknown_kind_is_skipped(self):
        resource, result = run_import(
            sets_dataset({"indicator_set": "Mystery set", "kind": "other"})
        )

        self.assertFalse(result.has_errors())
        self.assertFalse(IndicatorSet.objects.exists())
        self.assertIn("Mystery set", " ".join(resource.warnings))

    def test_resource_columns_exist_in_sheet_header(self):
        resource = IndicatorSetResource()
        for field in resource.get_import_fields():
            self.assertIn(field.column_name, SETS_HEADER)
