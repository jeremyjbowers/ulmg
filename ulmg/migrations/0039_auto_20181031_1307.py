# Generated by Django 2.0.8 on 2018-10-31 13:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ulmg', '0038_auto_20181023_1815'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='draftpick',
            options={'ordering': ['year', '-season', 'draft_type', 'draft_round', 'pick_number']},
        ),
    ]