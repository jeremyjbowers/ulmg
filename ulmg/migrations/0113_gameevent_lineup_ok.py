# ABOUTME: Records that a held seat has accepted its lineup for this game.
# ABOUTME: The column stays a short string; lineup_ok is one more kind a log can append.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ulmg', '0112_merge_0111_depth_chart_0111_halfplan_bullpen_rules'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gameevent',
            name='kind',
            field=models.CharField(choices=[('open', 'Game opened'), ('seat', 'Seat change'), ('decision', 'Computer decision'), ('start', 'Lineups set'), ('lineup', 'Lineup change'), ('lineup_ok', 'Lineup accepted'), ('call', 'Call'), ('plate_appearance', 'Plate appearance'), ('pitching_change', 'Pitching change'), ('substitution', 'Substitution'), ('position_change', 'Position change'), ('roster_move', 'Roster move'), ('pause', 'Paused'), ('resume', 'Resumed'), ('final', 'Final')], max_length=32),
        ),
    ]
