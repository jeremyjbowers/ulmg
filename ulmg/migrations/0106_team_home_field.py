# ABOUTME: Gives each team a home field, and gives that field a place for its dimensions and its plate.
# ABOUTME: A venue that already points at a team becomes that team's home field. The one with a park score wins ties.

from django.db import migrations, models


def point_teams_at_their_venues(apps, schema_editor):
    Team = apps.get_model("ulmg", "Team")
    Venue = apps.get_model("ulmg", "Venue")
    for team in Team.objects.all():
        venues = list(Venue.objects.filter(team_id=team.id).order_by("id"))
        if not venues:
            continue
        chosen = next((venue for venue in venues if venue.park_factor is not None), venues[0])
        Team.objects.filter(pk=team.pk).update(home_field_id=chosen.id)


def clear_home_fields(apps, schema_editor):
    Team = apps.get_model("ulmg", "Team")
    Team.objects.update(home_field_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0105_bullpen_usage"),
    ]

    operations = [
        migrations.AddField(
            model_name="venue",
            name="rules",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Dimensions and ground rules the field-art builder reads. "
                    "distances_ft and wall_ft use lf_line, left_center, center, right_center and rf_line, in feet. "
                    "Also foul_ft, surface (grass or turf), roof (open, retractable or dome) and ground_rules. "
                    "Missing keys use a 330/380/400 park."
                ),
            ),
        ),
        migrations.AddField(
            model_name="venue",
            name="sprites",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Art the field builder writes. version is an integer. "
                    "plate_svg is the inner SVG of the 320 by 180 field plate, with no player sprites. "
                    "Leave plate_svg empty and the game draws the generic plate."
                ),
            ),
        ),
        migrations.AddField(
            model_name="team",
            name="home_field",
            field=models.OneToOneField(
                blank=True,
                help_text="The park this club plays in. Scores, dimensions and the field plate live on that park.",
                null=True,
                on_delete=models.SET_NULL,
                related_name="home_club",
                to="ulmg.venue",
            ),
        ),
        migrations.RunPython(point_teams_at_their_venues, clear_home_fields),
    ]
