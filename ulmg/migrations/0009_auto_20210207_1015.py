# Generated by Django 3.0.7 on 2021-02-07 10:15

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0008_owner"),
    ]

    operations = [
        migrations.RenameField(
            model_name="team", old_name="owner", new_name="owner_name",
        ),
    ]