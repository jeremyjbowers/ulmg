# Generated by Django 3.0.7 on 2021-02-15 13:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0017_auto_20210215_1313"),
    ]

    operations = [
        migrations.AddField(
            model_name="player",
            name="fg_fv",
            field=models.DecimalField(
                blank=True, decimal_places=1, max_digits=3, null=True
            ),
        ),
    ]
