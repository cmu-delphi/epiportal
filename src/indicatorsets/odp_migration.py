"""Shared idempotent DB steps for OriginalDataProvider schema migration."""

import django.db.models.deletion
from django.db import models


INDICATOR_SET_TABLE = "indicatorsets_indicatorset"
PROVIDER_TABLE = "indicatorsets_originaldataprovider"
UNIQUE_CONSTRAINT = "unique_indicator_set_name"


def infer_provider_group(name, source_type):
    if source_type == "us_state":
        return "us_states"
    if name and name.split(" ")[0] == "US":
        return "us_government"
    return "individual"


def get_column_types(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            """,
            [table_name],
        )
        return {row[0]: row[1] for row in cursor.fetchall()}


def drop_foreign_keys_to_table(schema_editor, table_name, referenced_table):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND REFERENCED_TABLE_NAME = %s
            """,
            [table_name, referenced_table],
        )
        for (constraint_name,) in cursor.fetchall():
            cursor.execute(
                f"ALTER TABLE `{table_name}` DROP FOREIGN KEY `{constraint_name}`"
            )


def drop_constraint_if_exists(schema_editor, table_name, constraint_name):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT CONSTRAINT_NAME
            FROM information_schema.TABLE_CONSTRAINTS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND CONSTRAINT_NAME = %s
            """,
            [table_name, constraint_name],
        )
        if cursor.fetchone():
            cursor.execute(
                f"ALTER TABLE `{table_name}` DROP INDEX `{constraint_name}`"
            )


def add_unique_constraint_if_missing(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT CONSTRAINT_NAME
            FROM information_schema.TABLE_CONSTRAINTS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND CONSTRAINT_NAME = %s
            """,
            [table_name, UNIQUE_CONSTRAINT],
        )
        if not cursor.fetchone():
            cursor.execute(
                f"""
                ALTER TABLE `{table_name}`
                ADD CONSTRAINT `{UNIQUE_CONSTRAINT}`
                UNIQUE (`name`, `original_data_provider_id`)
                """
            )


def is_odp_schema_applied(schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())
    if INDICATOR_SET_TABLE not in existing_tables:
        return False
    if PROVIDER_TABLE not in existing_tables:
        return False

    columns = get_column_types(schema_editor, INDICATOR_SET_TABLE)
    if "original_data_provider_id" not in columns:
        return False
    if columns.get("original_data_provider") in ("varchar", "char", "text"):
        return False

    return True


def ensure_original_data_provider_schema(apps, schema_editor):
    """
    Idempotently apply the OriginalDataProvider schema on MySQL.

    Safe to run from 0010 (first attempt) and 0011 (repair after partial/faked 0010).
    """
    if is_odp_schema_applied(schema_editor):
        return

    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())
    OriginalDataProvider = apps.get_model("indicatorsets", "OriginalDataProvider")
    IndicatorSet = apps.get_model("indicatorsets", "IndicatorSet")

    if INDICATOR_SET_TABLE not in existing_tables:
        if PROVIDER_TABLE in existing_tables:
            schema_editor.delete_model(OriginalDataProvider)
        return

    column_types = get_column_types(schema_editor, INDICATOR_SET_TABLE)
    legacy_is_text = column_types.get("original_data_provider") in (
        "varchar",
        "char",
        "text",
    )

    drop_foreign_keys_to_table(schema_editor, INDICATOR_SET_TABLE, PROVIDER_TABLE)

    for column_name in (
        "original_data_provider_id",
        "original_data_provider_fk_id",
    ):
        if column_name in column_types and legacy_is_text:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"ALTER TABLE `{INDICATOR_SET_TABLE}` DROP COLUMN `{column_name}`"
                )
            column_types.pop(column_name, None)

    if PROVIDER_TABLE in existing_tables and legacy_is_text:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS `{PROVIDER_TABLE}`")

    if PROVIDER_TABLE not in set(connection.introspection.table_names()):
        schema_editor.create_model(OriginalDataProvider)

    drop_constraint_if_exists(schema_editor, INDICATOR_SET_TABLE, UNIQUE_CONSTRAINT)

    column_types = get_column_types(schema_editor, INDICATOR_SET_TABLE)
    legacy_is_text = column_types.get("original_data_provider") in (
        "varchar",
        "char",
        "text",
    )

    if legacy_is_text:
        fk_field = models.ForeignKey(
            OriginalDataProvider,
            on_delete=django.db.models.deletion.SET_NULL,
            blank=True,
            null=True,
            related_name="indicator_sets_via_fk",
        )
        fk_field.set_attributes_from_name("original_data_provider_fk")
        schema_editor.add_field(IndicatorSet, fk_field)

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, original_data_provider, source_type
                FROM `{INDICATOR_SET_TABLE}`
                """
            )
            rows = cursor.fetchall()

        for row_id, provider_name, source_type in rows:
            provider_name = (provider_name or "").strip()
            if not provider_name:
                continue

            group = infer_provider_group(provider_name, source_type)
            provider, _ = OriginalDataProvider.objects.get_or_create(
                name=provider_name,
                defaults={"group": group},
            )
            if provider.group != group:
                provider.group = group
                provider.save(update_fields=["group"])

            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE `{INDICATOR_SET_TABLE}`
                    SET original_data_provider_fk_id = %s
                    WHERE id = %s
                    """,
                    [provider.id, row_id],
                )

        legacy_field = models.CharField(max_length=255, blank=True)
        legacy_field.set_attributes_from_name("original_data_provider")
        schema_editor.remove_field(IndicatorSet, legacy_field)

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                ALTER TABLE `{INDICATOR_SET_TABLE}`
                CHANGE `original_data_provider_fk_id` `original_data_provider_id` bigint NULL
                """
            )

    elif "original_data_provider_id" not in column_types:
        fk_field = models.ForeignKey(
            OriginalDataProvider,
            on_delete=django.db.models.deletion.SET_NULL,
            blank=True,
            null=True,
            related_name="indicator_sets",
        )
        fk_field.set_attributes_from_name("original_data_provider")
        schema_editor.add_field(IndicatorSet, fk_field)

    add_unique_constraint_if_missing(schema_editor, INDICATOR_SET_TABLE)
