# ABOUTME: Split the half-plan bullpen into setup vs L, setup vs R, short relief and middle relief.
# ABOUTME: Existing setup arms move by the hand they throw, and middle-and-long arms become middle relief.

import django.contrib.postgres.fields
from django.db import migrations, models


def split_bullpen(apps, schema_editor):
    HalfPlan = apps.get_model("ulmg", "HalfPlan")
    Player = apps.get_model("ulmg", "Player")
    for plan in HalfPlan.objects.all():
        throws = dict(Player.objects.filter(id__in=plan.setup).values_list("id", "throws"))
        plan.setup_l = [pid for pid in plan.setup if throws.get(pid) == "L"]
        plan.setup_r = [pid for pid in plan.setup if throws.get(pid) != "L"]
        plan.sirp = []
        plan.mirp = list(plan.middle_long)
        plan.save(update_fields=["setup_l", "setup_r", "sirp", "mirp"])


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0102_half_plan_starter_hook"),
    ]

    operations = [
        migrations.AddField(
            model_name="halfplan",
            name="setup_l",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(), blank=True, default=list
            ),
        ),
        migrations.AddField(
            model_name="halfplan",
            name="setup_r",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(), blank=True, default=list
            ),
        ),
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
        migrations.RunPython(split_bullpen, migrations.RunPython.noop),
        migrations.RemoveField(model_name="halfplan", name="setup"),
        migrations.RemoveField(model_name="halfplan", name="middle_long"),
    ]
