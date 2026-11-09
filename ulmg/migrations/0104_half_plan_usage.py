# ABOUTME: Add closer, late-relief and bench usage styles to a half plan.
# ABOUTME: The defaults are the computer's previous behavior: ninth, standard and stand.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0103_bullpen_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="halfplan",
            name="closer_usage",
            field=models.CharField(
                choices=[("ninth", "Ninth"), ("eighth", "Eighth"), ("leverage", "Leverage")],
                default="ninth",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="halfplan",
            name="relief_usage",
            field=models.CharField(
                choices=[("standard", "Standard"), ("early", "Early"), ("tight", "Tight")],
                default="standard",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="halfplan",
            name="bench_usage",
            field=models.CharField(
                choices=[("stand", "Stand"), ("pinch", "Pinch"), ("glove", "Glove")],
                default="stand",
                max_length=8,
            ),
        ),
    ]
