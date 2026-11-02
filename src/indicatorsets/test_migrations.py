from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [("indicatorsets", "0010_originaldataprovider_and_more")]
AFTER = [("indicatorsets", "0011_indicatorset_kind_ongoing_dua_required")]


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


class IndicatorSetKindMigrationTests(TransactionTestCase):
    def setUp(self):
        old_apps = migrate(BEFORE)
        OldIndicatorSet = old_apps.get_model("indicatorsets", "IndicatorSet")
        for name, source_type, end, dua in [
            ("Covidcast", "covidcast", "Ongoing", "No"),
            ("Other endpoint", "other_endpoint", "2023-05-01", "Yes"),
            ("Non-Delphi", "non_delphi", "Ongoing", "Sensor-dependent"),
            ("US state", "us_state", "", "Unknown"),
            ("No type", None, "", ""),
        ]:
            OldIndicatorSet.objects.create(
                name=name,
                source_type=source_type,
                temporal_scope_end=end,
                dua_required=dua,
            )
        self.apps = migrate(AFTER)

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_existing_sets_are_mapped(self):
        IndicatorSet = self.apps.get_model("indicatorsets", "IndicatorSet")
        rows = {
            row["name"]: row
            for row in IndicatorSet.objects.values(
                "name", "kind", "ongoing", "temporal_scope_end", "dua_required"
            )
        }

        def summary(name):
            row = rows[name]
            return (
                row["kind"],
                row["ongoing"],
                row["temporal_scope_end"],
                row["dua_required"],
            )

        self.assertEqual(summary("Covidcast"), ("delphi", True, "", False))
        self.assertEqual(
            summary("Other endpoint"), ("delphi", False, "2023-05-01", True)
        )
        self.assertEqual(summary("Non-Delphi"), ("non_delphi", True, "", True))
        self.assertEqual(summary("US state"), ("us_states", False, "", False))
        self.assertEqual(summary("No type"), ("delphi", False, "", False))
