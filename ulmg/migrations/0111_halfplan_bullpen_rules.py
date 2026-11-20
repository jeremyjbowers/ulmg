# ABOUTME: Advanced bullpen usage stores the rules a shortcut is filled in with.
# ABOUTME: A shortcut leaves the rules empty and keeps its name.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0110_two_way_dh"),
    ]

    operations = [
        migrations.AddField(
            model_name="halfplan",
            name="bullpen_rules",
            field=models.JSONField(blank=True, default=dict),
        ),
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
                    ("advanced", "Advanced"),
                ],
                default="traditional",
                max_length=12,
            ),
        ),
    ]
