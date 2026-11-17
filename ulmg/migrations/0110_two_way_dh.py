# ABOUTME: A pitcher whose latest card has a real batting season is a two-way player.
# ABOUTME: DH-P is a designated hitter who also pitches. A short batting line stays a pitcher.

from django.db import migrations, models


def promote_two_way_players(apps, schema_editor):
    from ulmg.utils import promote_two_way_pitchers

    promote_two_way_pitchers(
        apps.get_model("ulmg", "Player"),
        apps.get_model("ulmg", "Card"),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('ulmg', '0109_halfplan_designations'),
    ]

    operations = [
        migrations.AlterField(
            model_name='player',
            name='position',
            field=models.CharField(choices=[('P', 'Pitcher'), ('C', 'Catcher'), ('IF', 'Infield'), ('OF', 'Outfield'), ('IF-OF', 'Infield/Outfield'), ('OF-P', 'Pitcher/Outfield'), ('IF-P', 'Pitcher/Infield'), ('DH-P', 'Pitcher/DH')], max_length=255, null=True),
        ),
        migrations.RunPython(promote_two_way_players, migrations.RunPython.noop),
    ]
