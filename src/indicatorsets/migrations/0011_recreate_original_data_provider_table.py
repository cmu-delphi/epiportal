# Drops and recreates indicatorsets_originaldataprovider if 0010 was recorded
# but the database schema is still broken (common after partial MySQL deploys).

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
