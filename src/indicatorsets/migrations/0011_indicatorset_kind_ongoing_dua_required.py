from django.db import migrations, models


def fill_kind_ongoing_and_dua_required(apps, schema_editor):
    IndicatorSet = apps.get_model("indicatorsets", "IndicatorSet")
    # kind defaults to "delphi", which covers covidcast and other_endpoint.
    IndicatorSet.objects.filter(source_type="non_delphi").update(kind="non_delphi")
    IndicatorSet.objects.filter(source_type="us_state").update(kind="us_states")
    IndicatorSet.objects.filter(temporal_scope_end="Ongoing").update(
        ongoing=True, temporal_scope_end=""
    )
    IndicatorSet.objects.filter(
        dua_required__in=["Yes", "Sensor-dependent"]
    ).update(dua_required_bool=True)


class Migration(migrations.Migration):

    dependencies = [
        ("indicatorsets", "0010_originaldataprovider_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="indicatorset",
            name="kind",
            field=models.CharField(
                choices=[
                    ("delphi", "Delphi"),
                    ("non_delphi", "Non-Delphi"),
                    ("us_states", "US States"),
                ],
                default="delphi",
                help_text="Who hosts the Indicator Set",
                max_length=32,
                verbose_name="Kind",
            ),
        ),
        migrations.AddField(
            model_name="indicatorset",
            name="ongoing",
            field=models.BooleanField(
                default=False,
                help_text="Indicates if the Indicator Set is still being updated",
                verbose_name="Ongoing",
            ),
        ),
        migrations.AddField(
            model_name="indicatorset",
            name="dua_required_bool",
            field=models.BooleanField(
                default=False,
                help_text="Indicates if a data use agreement is required for the Indicator Set",
                verbose_name="Data Use Agreement Required",
            ),
        ),
        # The next import repopulates every set, so there is nothing to restore.
        migrations.RunPython(
            fill_kind_ongoing_and_dua_required, migrations.RunPython.noop
        ),
        migrations.DeleteModel(
            name="NonDelphiIndicatorSet",
        ),
        migrations.DeleteModel(
            name="USStateIndicatorSet",
        ),
        migrations.RemoveConstraint(
            model_name="indicatorset",
            name="unique_indicator_set_name",
        ),
        migrations.RemoveField(
            model_name="indicatorset",
            name="organization",
        ),
        migrations.RemoveField(
            model_name="indicatorset",
            name="source_type",
        ),
        migrations.RemoveField(
            model_name="indicatorset",
            name="state",
        ),
        migrations.RemoveField(
            model_name="indicatorset",
            name="version_number",
        ),
        migrations.RemoveField(
            model_name="indicatorset",
            name="dua_required",
        ),
        migrations.RenameField(
            model_name="indicatorset",
            old_name="dua_required_bool",
            new_name="dua_required",
        ),
    ]
