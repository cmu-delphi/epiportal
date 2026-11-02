from unittest.mock import patch

from django.test import TestCase
from tablib import Dataset

from datasources.models import SourceSubdivision
from indicators.models import Indicator
from indicators.resources import IndicatorResource
from indicatorsets.models import IndicatorSet

INDICATORS_HEADER = (
    "source,indicator,indicator_set,base_is_other,base_indicator,"
    "computed_from_base,display_name,show_in_epiportal,active,short_description,"
    "description,pathogen,indicator_type,geographic_scope,geographic_levels,"
    "temporal_scope_start,temporal_scope_start_note,temporal_scope_end,"
    "temporal_scope_end_note,ongoing,time_type,time_label,reporting_cadence,"
    "typical_reporting_lag,typical_revision_cadence,population,"
    "demographic_breakdown,data_censoring,surveillance_categories,missingness,"
    "format,category,high_values_are,is_smoothed,is_weighted,is_cumulative,"
    "has_stderr,has_sample_size,who_may_access,who_may_be_told,use_restrictions,"
    "data_use_terms,dua_link,documentation_link"
).split(",")

ROW_DEFAULTS = {"show_in_epiportal": "TRUE"}


def indicators_dataset(*rows: dict) -> Dataset:
    dataset = Dataset(headers=INDICATORS_HEADER)
    for row in rows:
        values = {**ROW_DEFAULTS, **row}
        dataset.append([values.get(column, "") for column in INDICATORS_HEADER])
    return dataset


def run_import(dataset: Dataset) -> tuple[IndicatorResource, object]:
    resource = IndicatorResource()
    result = resource.import_data(dataset, dry_run=False, raise_errors=True)
    return resource, result


class IndicatorResourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.delphi_set = IndicatorSet.objects.create(name="Delphi set", kind="delphi")
        cls.other_set = IndicatorSet.objects.create(name="Other set", kind="delphi")
        cls.state_set = IndicatorSet.objects.create(name="State set", kind="us_states")
        cls.chng = SourceSubdivision.objects.create(name="chng")

    def test_maps_columns(self):
        run_import(
            indicators_dataset(
                {
                    "source": "chng",
                    "indicator": "smoothed_cli",
                    "indicator_set": "Delphi set",
                    "base_indicator": "ignored",
                    "display_name": "CLI",
                    "active": "TRUE",
                    "short_description": "Short",
                    "description": "Long",
                    "pathogen": "COVID-19, RSV",
                    "indicator_type": "Rate",
                    "geographic_scope": "USA",
                    "geographic_levels": "State/ADM 1",
                    "temporal_scope_start": "2020w05",
                    "temporal_scope_start_note": "Start note",
                    "temporal_scope_end": "2023-05-01 00:00:00",
                    "temporal_scope_end_note": "End note",
                    "ongoing": "TRUE",
                    "time_type": "day",
                    "time_label": "Date",
                    "reporting_cadence": "Daily",
                    "typical_reporting_lag": "3 days",
                    "typical_revision_cadence": "Weekly",
                    "population": "All",
                    "demographic_breakdown": "ignored",
                    "data_censoring": "Censored",
                    "surveillance_categories": "public",
                    "missingness": "Some",
                    "format": "Percent",
                    "category": "Early",
                    "high_values_are": "bad",
                    "is_smoothed": "",
                    "is_weighted": "TRUE",
                    "is_cumulative": "FALSE",
                    "has_stderr": "TRUE",
                    "has_sample_size": "TRUE",
                    "who_may_access": "Everyone",
                    "who_may_be_told": "Anyone",
                    "use_restrictions": "None",
                    "data_use_terms": "CC BY",
                    "dua_link": "https://example.com/dua",
                    "documentation_link": "https://example.com/docs",
                }
            )
        )

        indicator = Indicator.objects.get(name="smoothed_cli")
        self.assertEqual(indicator.source, self.chng)
        self.assertEqual(indicator.indicator_set, self.delphi_set)
        self.assertEqual(indicator.display_name, "CLI")
        self.assertIs(indicator.active, True)
        self.assertEqual(indicator.short_description, "Short")
        self.assertEqual(indicator.description, "Long")
        self.assertEqual(
            sorted(indicator.pathogens.values_list("name", flat=True)),
            ["COVID-19", "RSV"],
        )
        self.assertEqual(
            set(indicator.pathogens.values_list("used_in", flat=True)),
            {"indicators"},
        )
        self.assertEqual(indicator.indicator_type.name, "Rate")
        self.assertEqual(indicator.geographic_scope.name, "USA")
        self.assertEqual(indicator.geographic_scope.used_in, "indicators")
        self.assertEqual(
            list(indicator.available_geographies.values_list("name", flat=True)),
            ["state"],
        )
        self.assertEqual(indicator.temporal_scope_start, "2020-01-26")
        self.assertEqual(indicator.temporal_scope_start_note, "Start note")
        self.assertEqual(indicator.temporal_scope_end, "2023-05-01")
        self.assertEqual(indicator.temporal_scope_end_note, "End note")
        self.assertIs(indicator.ongoing, True)
        self.assertEqual(indicator.time_type, "day")
        self.assertEqual(indicator.time_label, "Date")
        self.assertEqual(indicator.reporting_cadence, "Daily")
        self.assertEqual(indicator.typical_reporting_lag, "3 days")
        self.assertEqual(indicator.typical_revision_cadence, "Weekly")
        self.assertEqual(indicator.demographic_scope, "All")
        self.assertEqual(indicator.data_censoring, "Censored")
        self.assertEqual(
            list(indicator.severity_pyramid_rungs.values_list("name", flat=True)),
            ["public"],
        )
        self.assertEqual(indicator.missingness, "Some")
        self.assertEqual(indicator.format_type.name, "Percent")
        self.assertEqual(indicator.category.name, "Early")
        self.assertEqual(indicator.high_values_are, "bad")
        self.assertIs(indicator.is_smoothed, False)
        self.assertIs(indicator.is_weighted, True)
        self.assertIs(indicator.is_cumulative, False)
        self.assertIs(indicator.has_stderr, True)
        self.assertIs(indicator.has_sample_size, True)
        self.assertEqual(indicator.organization_access_list, "Everyone")
        self.assertEqual(indicator.organization_sharing_list, "Anyone")
        self.assertEqual(indicator.restrictions, "None")
        self.assertEqual(indicator.license, "CC BY")
        self.assertEqual(indicator.dua_link, "https://example.com/dua")
        self.assertEqual(indicator.documentation_link, "https://example.com/docs")

    def test_strips_whitespace(self):
        run_import(
            indicators_dataset(
                {
                    "source": " chng ",
                    "indicator": " sig ",
                    "indicator_set": " Delphi set ",
                    "time_type": " day ",
                }
            )
        )
        indicator = Indicator.objects.get(name="sig")
        self.assertEqual(indicator.source, self.chng)
        self.assertEqual(indicator.time_type, "day")

    def test_delphi_indicator_moved_to_other_set_updates_same_row(self):
        indicator = Indicator.objects.create(
            name="sig", source=self.chng, indicator_set=self.delphi_set
        )

        _, result = run_import(
            indicators_dataset(
                {"source": "chng", "indicator": "sig", "indicator_set": "Other set"}
            )
        )

        self.assertFalse(result.has_errors())
        moved = Indicator.objects.get()
        self.assertEqual(moved.pk, indicator.pk)
        self.assertEqual(moved.indicator_set, self.other_set)

    def test_delphi_indicator_with_new_source_updates_same_row(self):
        indicator = Indicator.objects.create(
            name="sig",
            source=SourceSubdivision.objects.create(name="old_src"),
            indicator_set=self.delphi_set,
        )

        resource, _ = run_import(
            indicators_dataset(
                {"source": "chng", "indicator": "sig", "indicator_set": "Delphi set"}
            )
        )

        self.assertEqual(resource.warnings, [])
        updated = Indicator.objects.get()
        self.assertEqual(updated.pk, indicator.pk)
        self.assertEqual(updated.source, self.chng)

    def test_us_state_row_ignores_source_column(self):
        run_import(
            indicators_dataset(
                {"source": "chng", "indicator": "sig", "indicator_set": "State set"}
            )
        )
        indicator = Indicator.objects.get(name="sig")
        self.assertIsNone(indicator.source)
        self.assertEqual(indicator.indicator_set, self.state_set)

    def test_us_state_indicator_matched_by_set(self):
        indicator = Indicator.objects.create(name="sig", indicator_set=self.state_set)

        run_import(
            indicators_dataset(
                {"indicator": "sig", "indicator_set": "State set", "time_type": "week"}
            )
        )

        updated = Indicator.objects.get()
        self.assertEqual(updated.pk, indicator.pk)
        self.assertEqual(updated.time_type, "week")

    def test_unknown_set_is_skipped_with_warning(self):
        resource, result = run_import(
            indicators_dataset(
                {"source": "chng", "indicator": "sig", "indicator_set": "Nevada typo"}
            )
        )

        self.assertFalse(result.has_errors())
        self.assertFalse(Indicator.objects.exists())
        self.assertEqual(len(resource.warnings), 1)
        self.assertIn("Nevada typo", resource.warnings[0])

    def test_unknown_delphi_source_is_skipped_with_warning(self):
        resource, result = run_import(
            indicators_dataset(
                {"source": "nope", "indicator": "sig", "indicator_set": "Delphi set"}
            )
        )

        self.assertFalse(result.has_errors())
        self.assertFalse(Indicator.objects.exists())
        self.assertEqual(len(resource.warnings), 1)
        self.assertIn("nope", resource.warnings[0])
        self.assertFalse(SourceSubdivision.objects.filter(name="nope").exists())

    def test_hidden_indicator_is_deleted(self):
        Indicator.objects.create(
            name="sig", source=self.chng, indicator_set=self.delphi_set
        )

        resource, result = run_import(
            indicators_dataset(
                {
                    "source": "chng",
                    "indicator": "sig",
                    "indicator_set": "Delphi set",
                    "show_in_epiportal": "FALSE",
                }
            )
        )

        self.assertFalse(result.has_errors())
        self.assertFalse(Indicator.objects.exists())
        self.assertEqual(resource.warnings, [])

    def test_hidden_row_with_unknown_set_does_not_warn(self):
        resource, _ = run_import(
            indicators_dataset(
                {
                    "indicator": "sig",
                    "indicator_set": "Nevada typo",
                    "show_in_epiportal": "FALSE",
                }
            )
        )
        self.assertEqual(resource.warnings, [])

    def test_empty_indicator_is_skipped(self):
        resource, _ = run_import(
            indicators_dataset({"indicator": "", "indicator_set": "State set"})
        )
        self.assertFalse(Indicator.objects.exists())
        self.assertEqual(resource.warnings, [])

    def test_indicator_missing_from_sheet_is_deleted(self):
        Indicator.objects.create(name="gone", indicator_set=self.state_set)
        run_import(indicators_dataset({"indicator": "kept", "indicator_set": "State set"}))
        self.assertEqual(
            list(Indicator.objects.values_list("name", flat=True)), ["kept"]
        )

    def test_importing_twice_keeps_every_indicator(self):
        dataset = indicators_dataset(
            {
                "source": "chng",
                "indicator": "sig",
                "indicator_set": "Delphi set",
                "pathogen": "COVID-19",
                "geographic_levels": "state, county",
                "format": "Percent",
            },
            {"indicator": "sig", "indicator_set": "State set"},
        )
        run_import(dataset)
        pks = sorted(Indicator.objects.values_list("pk", flat=True))

        _, result = run_import(dataset)

        self.assertEqual(result.totals["skip"], 2)
        self.assertEqual(sorted(Indicator.objects.values_list("pk", flat=True)), pks)

    def test_empty_surveillance_categories_become_na(self):
        run_import(
            indicators_dataset(
                {"indicator": "sig", "indicator_set": "State set"},
            )
        )
        indicator = Indicator.objects.get(name="sig")
        self.assertEqual(
            list(indicator.severity_pyramid_rungs.values_list("name", flat=True)),
            ["N/A"],
        )

    def test_row_error_is_skipped_with_warning(self):
        with patch.object(
            IndicatorResource, "import_instance", side_effect=ValueError("boom")
        ):
            resource, result = run_import(
                indicators_dataset({"indicator": "sig", "indicator_set": "State set"})
            )

        self.assertFalse(result.has_errors())
        self.assertEqual(result.totals["skip"], 1)
        self.assertEqual(len(resource.warnings), 1)
        self.assertIn("boom", resource.warnings[0])

    def test_warnings_default_to_empty_list(self):
        self.assertEqual(IndicatorResource().warnings, [])

    def test_resource_columns_exist_in_sheet_header(self):
        resource = IndicatorResource()
        for field in resource.get_import_fields():
            self.assertIn(field.column_name, INDICATORS_HEADER)
