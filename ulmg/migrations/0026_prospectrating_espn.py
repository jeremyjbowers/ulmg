# Generated by Django 3.1 on 2021-02-28 17:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0025_auto_20210228_1159"),
    ]

    operations = [
        migrations.AddField(
            model_name="prospectrating",
            name="espn",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]