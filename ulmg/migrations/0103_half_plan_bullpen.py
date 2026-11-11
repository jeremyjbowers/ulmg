# ABOUTME: Splits a half plan's middle-and-long group into middle and long relief, and stores the bullpen logic.
# ABOUTME: Arms already filed in middle_long stay middle relief. Long relief starts empty for those plans.

import django.contrib.postgres.fields
from django.db import migrations, models


def copy_middle_long(apps, schema_editor):
    HalfPlan = apps.get_model("ulmg", "HalfPlan")
    for plan in HalfPlan.objects.all().iterator():
        if plan.middle_long:
            plan.middle = list(plan.middle_long)
            plan.save(update_fields=["middle"])


def restore_middle_long(apps, schema_editor):
    HalfPlan = apps.get_model("ulmg", "HalfPlan")
    for plan in HalfPlan.objects.all().iterator():
        combined = list(plan.middle)
        combined += [player_id for player_id in plan.long_relief if player_id not in combined]
        plan.middle_long = combined
        plan.save(update_fields=["middle_long"])


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0102_half_plan_starter_hook"),
    ]

    operations = [
        migrations.AddField(
            model_name="halfplan",
            name="middle",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(), blank=True, default=list
            ),
        ),
        migrations.AddField(
            model_name="halfplan",
            name="long_relief",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(), blank=True, default=list
            ),
        ),
        migrations.AddField(
            model_name="halfplan",
            name="bullpen_logic",
            field=models.CharField(
                choices=[("quick", "Quick"), ("normal", "Normal"), ("slow", "Slow")],
                default="normal",
                max_length=6,
            ),
        ),
        migrations.RunPython(copy_middle_long, restore_middle_long),
        migrations.RemoveField(model_name="halfplan", name="middle_long"),
    ]
