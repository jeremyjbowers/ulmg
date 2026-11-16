# ABOUTME: Each starter can keep his own hook on the half plan.
# ABOUTME: An empty map means every starter uses the plan's starter hook.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0107_halfplanday_blank_starter"),
    ]

    operations = [
        migrations.AddField(
            model_name="halfplan",
            name="starter_hooks",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
