from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [("indicators", "0009_remove_indicator_base_alter_indicator_category_and_more")]
AFTER = [("indicators", "0010_indicator_ongoing_and_unused_fields")]


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


class IndicatorOngoingMigrationTests(TransactionTestCase):
    def setUp(self):
        old_apps = migrate(BEFORE)
        OldIndicator = old_apps.get_model("indicators", "Indicator")
        for name, end in [
            ("ongoing_sig", "Ongoing"),
            ("ended_sig", "2023-05-01"),
            ("blank_sig", ""),
        ]:
            OldIndicator.objects.create(
                name=name,
                temporal_scope_end=end,
                member_name="Member",
                source_type="non_delphi",
            )
        self.apps = migrate(AFTER)

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_ongoing_end_becomes_flag(self):
        Indicator = self.apps.get_model("indicators", "Indicator")
        rows = {
            row["name"]: (row["ongoing"], row["temporal_scope_end"])
            for row in Indicator.objects.values("name", "ongoing", "temporal_scope_end")
        }
        self.assertEqual(
            rows,
            {
                "ongoing_sig": (True, ""),
                "ended_sig": (False, "2023-05-01"),
                "blank_sig": (False, ""),
            },
        )
