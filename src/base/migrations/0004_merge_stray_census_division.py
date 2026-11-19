from django.db import migrations

STRAY_NAME = "U.S. Census Division"
CENSUS_DIVISION = {
    "display_name": "U.S. Census Division",
    "short_name": "Census Division",
    "display_order_number": 4,
}


def merge_stray_census_division(apps, schema_editor):
    """Fold the rows the sheet import made for "U.S. Census Division" into
    ``census-division``.

    Before the level had a mapping, the import created it under its display
    name. Its indicators and indicator sets move to the ``census-division``
    row with the same ``used_in``, and the stray row is deleted.
    """
    Geography = apps.get_model("base", "Geography")
    for stray in Geography.objects.filter(name=STRAY_NAME):
        division, _ = Geography.objects.get_or_create(
            name="census-division", used_in=stray.used_in, defaults=CENSUS_DIVISION
        )
        for related in ("indicators", "indicator_sets"):
            division_links = getattr(division, related)
            division_links.add(*getattr(stray, related).all())
        stray.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0003_banner"),
        ("indicators", "0010_indicator_ongoing_and_unused_fields"),
        ("indicatorsets", "0012_indicatorset_external_source_link"),
    ]

    operations = [
        migrations.RunPython(merge_stray_census_division, migrations.RunPython.noop),
    ]
