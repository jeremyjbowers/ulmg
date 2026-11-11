# ABOUTME: Replaces a half plan's setup, middle and long relief with single-inning and multi-inning relief.
# ABOUTME: Setup and middle become SIRP, in that order. Long relief becomes MIRP. The bullpen logic goes away.

import django.contrib.postgres.fields
from django.db import migrations, models


def copy_roles(apps, schema_editor):
    HalfPlan = apps.get_model("ulmg", "HalfPlan")
    for plan in HalfPlan.objects.all().iterator():
        sirp = list(plan.setup or [])
        sirp += [player_id for player_id in (plan.middle or []) if player_id not in sirp]
        plan.sirp = sirp
        plan.mirp = list(plan.long_relief or [])
        plan.save(update_fields=["sirp", "mirp"])


def restore_roles(apps, schema_editor):
    HalfPlan = apps.get_model("ulmg", "HalfPlan")
    for plan in HalfPlan.objects.all().iterator():
        plan.setup = list(plan.sirp or [])
        plan.middle = []
        plan.long_relief = list(plan.mirp or [])
        plan.save(update_fields=["setup", "middle", "long_relief"])


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0103_half_plan_bullpen"),
    ]

    operations = [
        migrations.AddField(
            model_name="halfplan",
            name="sirp",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(), blank=True, default=list
            ),
        ),
        migrations.AddField(
            model_name="halfplan",
            name="mirp",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(), blank=True, default=list
            ),
        ),
        migrations.RunPython(copy_roles, restore_roles),
        migrations.RemoveField(model_name="halfplan", name="setup"),
        migrations.RemoveField(model_name="halfplan", name="middle"),
        migrations.RemoveField(model_name="halfplan", name="long_relief"),
        migrations.RemoveField(model_name="halfplan", name="bullpen_logic"),
    ]
