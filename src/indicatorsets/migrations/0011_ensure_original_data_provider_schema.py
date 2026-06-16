# Repair migration for staging: runs on deploy when 0010 is recorded but the DB
# schema is still partial (e.g. orphan provider table, char column not converted).

from django.db import migrations

from indicatorsets.odp_migration import ensure_original_data_provider_schema


class Migration(migrations.Migration):

    dependencies = [
        ("indicatorsets", "0010_originaldataprovider_and_more"),
    ]

    operations = [
        migrations.RunPython(
            ensure_original_data_provider_schema,
            migrations.RunPython.noop,
        ),
    ]
