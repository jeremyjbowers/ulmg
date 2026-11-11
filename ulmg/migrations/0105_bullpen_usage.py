# ABOUTME: Puts the bullpen usage back on the half plan, above the closer, SIRP and MIRP columns.
# ABOUTME: The earlier quick, normal and slow values were removed with the column, so existing rows start at traditional.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0104_half_plan_sirp_mirp"),
    ]

    operations = [
        migrations.AddField(
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
    ]
