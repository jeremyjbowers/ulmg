# ABOUTME: Joins the depth chart and advanced bullpen migrations, which both numbered 0111.
# ABOUTME: A deploy migrates from one leaf, and two leaves make post_install exit.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0111_depth_chart"),
        ("ulmg", "0111_halfplan_bullpen_rules"),
    ]

    operations = []
