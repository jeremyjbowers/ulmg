# Generated by Django 3.0.7 on 2021-02-15 13:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0019_player_eligible_year"),
    ]

    operations = [
        migrations.RenameField(
            model_name="player", old_name="eligible_year", new_name="class_year",
        ),
    ]