"""Drop/recreate OriginalDataProvider table and wire IndicatorSet FK."""

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

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND COLUMN_NAME = 'original_data_provider_id'
              AND REFERENCED_TABLE_NAME = %s
            """,
            [INDICATOR_SET_TABLE, PROVIDER_TABLE],
        )
        return cursor.fetchone() is not None


def _collect_indicator_set_provider_links(connection, column_types, existing_tables):
    if INDICATOR_SET_TABLE not in existing_tables:
        return []

    legacy_is_text = column_types.get("original_data_provider") in (
        "varchar",
        "char",
        "text",
    )

    with connection.cursor() as cursor:
        if legacy_is_text:
            cursor.execute(
                f"""
                SELECT id, original_data_provider, source_type
                FROM `{INDICATOR_SET_TABLE}`
                """
            )
            return [
                (row_id, (provider_name or "").strip(), source_type)
                for row_id, provider_name, source_type in cursor.fetchall()
                if (provider_name or "").strip()
            ]

        if (
            "original_data_provider_id" in column_types
            and PROVIDER_TABLE in existing_tables
        ):
            cursor.execute(
                f"""
                SELECT s.id, p.name, s.source_type
                FROM `{INDICATOR_SET_TABLE}` s
                LEFT JOIN `{PROVIDER_TABLE}` p
                  ON s.original_data_provider_id = p.id
                WHERE p.name IS NOT NULL AND p.name <> ''
                """
            )
            return [
                (row_id, provider_name.strip(), source_type)
                for row_id, provider_name, source_type in cursor.fetchall()
                if provider_name and provider_name.strip()
            ]

    return []


def _drop_provider_table(schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())
    if PROVIDER_TABLE not in existing_tables:
        return

    drop_foreign_keys_to_table(schema_editor, INDICATOR_SET_TABLE, PROVIDER_TABLE)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS `{PROVIDER_TABLE}`")


def _create_provider_table(schema_editor, OriginalDataProvider):
    existing_tables = set(schema_editor.connection.introspection.table_names())
    if PROVIDER_TABLE not in existing_tables:
        schema_editor.create_model(OriginalDataProvider)


def _restore_provider_links(OriginalDataProvider, links):
    provider_ids_by_indicator_set = {}

    for indicator_set_id, provider_name, source_type in links:
        group = infer_provider_group(provider_name, source_type)
        provider, _ = OriginalDataProvider.objects.get_or_create(
            name=provider_name,
            defaults={"group": group},
        )
        if provider.group != group:
            provider.group = group
            provider.save(update_fields=["group"])
        provider_ids_by_indicator_set[indicator_set_id] = provider.id

    return provider_ids_by_indicator_set


def _apply_provider_ids(connection, provider_ids_by_indicator_set, fk_column):
    for indicator_set_id, provider_id in provider_ids_by_indicator_set.items():
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE `{INDICATOR_SET_TABLE}`
                SET `{fk_column}` = %s
                WHERE id = %s
                """,
                [provider_id, indicator_set_id],
            )


def _add_foreign_key_column(schema_editor, IndicatorSet, OriginalDataProvider):
    fk_field = models.ForeignKey(
        OriginalDataProvider,
        on_delete=django.db.models.deletion.SET_NULL,
        blank=True,
        null=True,
        related_name="indicator_sets",
    )
    fk_field.set_attributes_from_name("original_data_provider")
    schema_editor.add_field(IndicatorSet, fk_field)


def _convert_char_column_to_fk(
    schema_editor, connection, IndicatorSet, OriginalDataProvider, links
):
    fk_field = models.ForeignKey(
        OriginalDataProvider,
        on_delete=django.db.models.deletion.SET_NULL,
        blank=True,
        null=True,
        related_name="indicator_sets_via_fk",
    )
    fk_field.set_attributes_from_name("original_data_provider_fk")
    schema_editor.add_field(IndicatorSet, fk_field)

    provider_ids_by_indicator_set = _restore_provider_links(OriginalDataProvider, links)
    _apply_provider_ids(
        connection, provider_ids_by_indicator_set, "original_data_provider_fk_id"
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


def _add_foreign_key_constraint(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND COLUMN_NAME = 'original_data_provider_id'
              AND REFERENCED_TABLE_NAME = %s
            """,
            [INDICATOR_SET_TABLE, PROVIDER_TABLE],
        )
        if cursor.fetchone():
            return

        cursor.execute(
            f"""
            ALTER TABLE `{INDICATOR_SET_TABLE}`
            ADD CONSTRAINT `indicatorsets_indicatorset_odp_id_fk`
            FOREIGN KEY (`original_data_provider_id`)
            REFERENCES `{PROVIDER_TABLE}` (`id`)
            ON DELETE SET NULL
            """
        )


def ensure_original_data_provider_schema(apps, schema_editor):
    """
    Drop and recreate indicatorsets_originaldataprovider, then restore FK links.

    Safe to run on every deploy until the final schema is detected.
    """
    if is_odp_schema_applied(schema_editor):
        return

    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())
    OriginalDataProvider = apps.get_model("indicatorsets", "OriginalDataProvider")
    IndicatorSet = apps.get_model("indicatorsets", "IndicatorSet")

    if INDICATOR_SET_TABLE not in existing_tables:
        _drop_provider_table(schema_editor)
        return

    column_types = get_column_types(schema_editor, INDICATOR_SET_TABLE)
    links = _collect_indicator_set_provider_links(
        connection, column_types, existing_tables
    )

    drop_constraint_if_exists(schema_editor, INDICATOR_SET_TABLE, UNIQUE_CONSTRAINT)

    legacy_is_text = column_types.get("original_data_provider") in (
        "varchar",
        "char",
        "text",
    )

    for column_name in ("original_data_provider_fk_id",):
        if column_name in column_types:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"ALTER TABLE `{INDICATOR_SET_TABLE}` DROP COLUMN `{column_name}`"
                )
            column_types.pop(column_name, None)

    if legacy_is_text and "original_data_provider_id" in column_types:
        with connection.cursor() as cursor:
            cursor.execute(
                f"ALTER TABLE `{INDICATOR_SET_TABLE}` DROP COLUMN `original_data_provider_id`"
            )
        column_types.pop("original_data_provider_id", None)
    elif "original_data_provider_id" in column_types:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE `{INDICATOR_SET_TABLE}`
                SET original_data_provider_id = NULL
                """
            )

    _drop_provider_table(schema_editor)
    _create_provider_table(schema_editor, OriginalDataProvider)

    column_types = get_column_types(schema_editor, INDICATOR_SET_TABLE)
    legacy_is_text = column_types.get("original_data_provider") in (
        "varchar",
        "char",
        "text",
    )

    if legacy_is_text:
        _convert_char_column_to_fk(
            schema_editor, connection, IndicatorSet, OriginalDataProvider, links
        )
        _add_foreign_key_constraint(schema_editor)
    elif "original_data_provider_id" not in column_types:
        _add_foreign_key_column(schema_editor, IndicatorSet, OriginalDataProvider)
        provider_ids = _restore_provider_links(OriginalDataProvider, links)
        _apply_provider_ids(connection, provider_ids, "original_data_provider_id")
    else:
        provider_ids = _restore_provider_links(OriginalDataProvider, links)
        _apply_provider_ids(connection, provider_ids, "original_data_provider_id")
        _add_foreign_key_constraint(schema_editor)

    add_unique_constraint_if_missing(schema_editor, INDICATOR_SET_TABLE)
