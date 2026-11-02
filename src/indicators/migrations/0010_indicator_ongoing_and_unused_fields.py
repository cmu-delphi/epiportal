from django.db import migrations, models

REMOVED_FIELDS = (
    "member_name",
    "member_short_name",
    "member_description",
    "use_in_express_interface",
    "last_updated",
    "from_date",
    "to_date",
    "indicator_availability_days",
    "source_type",
)


def fill_ongoing(apps, schema_editor):
    Indicator = apps.get_model("indicators", "Indicator")
    Indicator.objects.filter(temporal_scope_end="Ongoing").update(
        ongoing=True, temporal_scope_end=""
    )


class Migration(migrations.Migration):

    dependencies = [
        ("indicators", "0009_remove_indicator_base_alter_indicator_category_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="indicator",
            name="ongoing",
            field=models.BooleanField(
                default=False,
                help_text="Indicates if the indicator is still being updated",
                verbose_name="Ongoing",
            ),
        ),
        migrations.RunPython(fill_ongoing, migrations.RunPython.noop),
        *[
            migrations.RemoveField(model_name="indicator", name=name)
            for name in REMOVED_FIELDS
        ],
        migrations.DeleteModel(name="IndicatorGeography"),
        migrations.DeleteModel(name="NonDelphiIndicator"),
        migrations.DeleteModel(name="OtherEndpointIndicator"),
        migrations.DeleteModel(name="USStateIndicator"),
    ]
