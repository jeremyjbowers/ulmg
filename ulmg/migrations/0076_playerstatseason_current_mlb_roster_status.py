# Generated by Django 5.2.3 on 2025-07-13 15:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ulmg', '0075_player_is_ulmg_midseason_unprotected'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerstatseason',
            name='current_mlb_roster_status',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
