# ABOUTME: A team's season depth chart: plate appearances, starts and bullpen innings by player.
# ABOUTME: An unlimited row covers a spot that is still short and is left out of that spot's total.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0110_two_way_dh"),
    ]

    operations = [
        migrations.CreateModel(
            name="DepthChart",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_modified", models.DateTimeField(auto_now=True, null=True)),
                ("season", models.IntegerField()),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="depth_charts",
                        to="ulmg.team",
                    ),
                ),
            ],
            options={
                "ordering": ["season", "team__abbreviation"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("team", "season"),
                        name="unique_depth_chart_team_season",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="DepthAssignment",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_modified", models.DateTimeField(auto_now=True, null=True)),
                ("bucket", models.CharField(max_length=8)),
                ("amount", models.IntegerField(default=0)),
                ("unlimited", models.BooleanField(default=False)),
                (
                    "chart",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="ulmg.depthchart",
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="depth_assignments",
                        to="ulmg.player",
                    ),
                ),
            ],
            options={
                "ordering": ["player__last_name", "player__first_name", "bucket"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("chart", "player", "bucket"),
                        name="unique_depth_assignment_chart_player_bucket",
                    )
                ],
            },
        ),
    ]
