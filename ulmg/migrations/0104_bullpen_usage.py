# ABOUTME: Renames the half plan's bullpen logic to the usage choices on the bullpen page.
# ABOUTME: quick, normal and slow become highest leverage, traditional closer and save the pen.

from django.db import migrations, models


def forwards(apps, schema_editor):
    HalfPlan = apps.get_model("ulmg", "HalfPlan")
    HalfPlan.objects.filter(bullpen_logic="quick").update(bullpen_logic="leverage")
    HalfPlan.objects.filter(bullpen_logic="normal").update(bullpen_logic="traditional")
    HalfPlan.objects.filter(bullpen_logic="slow").update(bullpen_logic="save")


def backwards(apps, schema_editor):
    HalfPlan = apps.get_model("ulmg", "HalfPlan")
    HalfPlan.objects.filter(bullpen_logic="leverage").update(bullpen_logic="quick")
    HalfPlan.objects.filter(bullpen_logic="traditional").update(bullpen_logic="normal")
    HalfPlan.objects.filter(bullpen_logic="save").update(bullpen_logic="slow")
    HalfPlan.objects.filter(bullpen_logic__in=["fireman", "protect"]).update(bullpen_logic="normal")


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0103_half_plan_bullpen"),
    ]

    operations = [
        migrations.AlterField(
            model_name="halfplan",
            name="bullpen_logic",
            field=models.CharField(
                choices=[
                    ("traditional", "Traditional closer"),
                    ("leverage", "Highest leverage"),
                    ("fireman", "Fireman"),
                    ("protect", "Protect the lead"),
                    ("save", "Save the pen"),
                ],
                default="traditional",
                max_length=12,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
