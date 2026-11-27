# ABOUTME: One league-settings row for the season, the half, and the roster windows.
# ABOUTME: Seeded with the values that used to live in the settings file.

from django.db import migrations, models


def seed_league_settings(apps, schema_editor):
    LeagueSettings = apps.get_model("ulmg", "LeagueSettings")
    LeagueSettings.objects.get_or_create(pk=1)


def unseed_league_settings(apps, schema_editor):
    LeagueSettings = apps.get_model("ulmg", "LeagueSettings")
    LeagueSettings.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ulmg', '0114_owner_stats_view'),
    ]

    operations = [
        migrations.CreateModel(
            name='LeagueSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_modified', models.DateTimeField(auto_now=True, null=True)),
                ('current_season', models.PositiveIntegerField(default=2027, help_text='ULMG year. MLB and AAA rosters take a card from the previous MLB season, so 2027 uses 2026 cards.', verbose_name='Current season')),
                ('current_season_type', models.CharField(choices=[('offseason', 'Offseason'), ('midseason', 'Midseason')], default='offseason', help_text='Offseason keeps stat pages on the card year while owners set rosters. Midseason uses the ULMG year itself.', max_length=16, verbose_name='Season type')),
                ('draft_prep_season_type', models.CharField(blank=True, choices=[('offseason', 'Offseason'), ('midseason', 'Midseason')], default='offseason', help_text='Team-page Open and AA draft prep. Blank follows the season type.', max_length=16, verbose_name='Draft prep')),
                ('season_half', models.CharField(choices=[('1h', '1H'), ('2h', '2H')], default='1h', help_text='The second half of the schedule opens when this is 2H.', max_length=2, verbose_name='Half')),
                ('stats_display_season_cap', models.PositiveIntegerField(blank=True, help_text='Latest calendar year shown on stat pages. Blank uses the stat season (the ULMG year, or the year before it in the offseason).', null=True, verbose_name='Stat season cap')),
                ('protect_tab', models.BooleanField(default=False, help_text='Owners set 40-man protections from their team page.', verbose_name='Set protections')),
                ('roster_tab', models.BooleanField(default=True, help_text='Owners set MLB and AAA rosters from the buttons on their team page.', verbose_name='Set rosters')),
                ('roster_staff_only', models.BooleanField(default=True, help_text='While this is on, those roster controls are shown to staff only.', verbose_name='Rosters are staff-only')),
                ('live_tab', models.BooleanField(default=False, help_text='Show the live scoring tab on team pages.', verbose_name='Live tab')),
                ('wishlist_tab', models.BooleanField(default=False, help_text='Show the wishlist tab on team pages.', verbose_name='Wishlist tab')),
                ('mlb_roster_size', models.PositiveSmallIntegerField(default=30, help_text='Active MLB roster limit.', verbose_name='MLB roster size')),
                ('protect_roster_size', models.PositiveSmallIntegerField(default=40, help_text='Size of the protected roster (the 40-man).', verbose_name='Protected roster size')),
            ],
            options={
                'verbose_name': 'league settings',
                'verbose_name_plural': 'league settings',
            },
        ),
        migrations.RunPython(seed_league_settings, unseed_league_settings),
    ]
