# ABOUTME: Records the midseason bonus draft as its own DraftPick type.
# ABOUTME: The 2012-2018 history file has Bonus B picks beside AA, Open, and balance.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ulmg', '0115_league_settings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='draftpick',
            name='draft_type',
            field=models.CharField(choices=[('aa', 'aa'), ('open', 'open'), ('balance', 'balance'), ('bonus', 'bonus')], max_length=255, null=True),
        ),
    ]
