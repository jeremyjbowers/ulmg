# ABOUTME: Adds ordered pinch-hitter lists and a defensive-replacement list to a half plan.
# ABOUTME: Each list is player ids and starts empty. An empty list means the bench order.

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0108_halfplan_starter_hooks"),
    ]

    operations = [
        migrations.AddField(
            model_name="halfplan",
            name="pinch_vs_rhp",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(), blank=True, default=list
            ),
        ),
        migrations.AddField(
            model_name="halfplan",
            name="pinch_vs_lhp",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(), blank=True, default=list
            ),
        ),
        migrations.AddField(
            model_name="halfplan",
            name="defensive_replacements",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(), blank=True, default=list
            ),
        ),
    ]
