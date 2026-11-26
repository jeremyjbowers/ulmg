# ABOUTME: A manager's choice of normal or advanced stats on player cards.
# ABOUTME: Blank means the default: advanced for staff, normal for everyone else.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ulmg', '0113_gameevent_lineup_ok'),
    ]

    operations = [
        migrations.AddField(
            model_name='owner',
            name='stats_view',
            field=models.CharField(blank=True, default='', max_length=16),
        ),
    ]
