# Generated by Django 3.0.7 on 2021-02-07 10:16

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0009_auto_20210207_1015"),
    ]

    operations = [
        migrations.AddField(
            model_name="team",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="ulmg.Owner",
            ),
        ),
    ]
