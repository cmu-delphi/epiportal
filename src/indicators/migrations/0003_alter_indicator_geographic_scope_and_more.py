# Generated by Django 5.0.7 on 2025-05-01 15:04

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0001_initial'),
        ('datasources', '0001_initial'),
        ('indicators', '0002_nondelphiindicator'),
    ]

    operations = [
        migrations.AlterField(
            model_name='indicator',
            name='geographic_scope',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='indicators', to='base.geographicscope', verbose_name='Geographic Scope'),
        ),
        migrations.AlterField(
            model_name='indicator',
            name='source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='indicators', to='datasources.sourcesubdivision', verbose_name='Source Subdivision'),
        ),
    ]
