# ABOUTME: Tests for the league settings row that holds the season, half, and roster windows.
# ABOUTME: The admin edits that row. A Django setting of the old name still overrides it.

from django.contrib.auth.models import AnonymousUser, User
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from ulmg import league, models, plans, utils


class LeagueSettingsTestCase(TestCase):
    def test_one_row_is_seeded_with_the_season_that_used_to_live_in_settings(self):
        row = league.load()
        self.assertEqual(models.LeagueSettings.objects.count(), 1)
        self.assertEqual(row.pk, 1)
        self.assertEqual(league.current_season(), 2027)
        self.assertEqual(league.current_season_type(), "offseason")
        self.assertEqual(league.draft_prep_season_type(), "offseason")
        self.assertEqual(league.season_half(), "1h")
        self.assertIsNone(league.stats_display_season_cap())
        self.assertFalse(league.protect_tab())
        self.assertTrue(league.roster_tab())
        self.assertTrue(league.roster_staff_only())
        self.assertFalse(league.live_tab())
        self.assertFalse(league.wishlist_tab())
        self.assertEqual(league.mlb_roster_size(), 30)
        self.assertEqual(league.protect_roster_size(), 40)
        # Offseason stat pages stay on the card year, one behind the ULMG year.
        self.assertEqual(utils.get_current_season(), 2026)
        self.assertEqual(plans.current_half(), 1)

    def test_saving_another_instance_updates_the_same_row(self):
        league.load()
        models.LeagueSettings(
            current_season=2031,
            current_season_type="midseason",
            season_half="2h",
        ).save()
        self.assertEqual(models.LeagueSettings.objects.count(), 1)
        row = league.load()
        self.assertEqual(row.current_season, 2031)
        self.assertEqual(row.season_half, "2h")

    def test_the_row_cannot_be_deleted(self):
        row = league.load()
        with self.assertRaises(ValueError):
            row.delete()
        self.assertEqual(models.LeagueSettings.objects.count(), 1)
        with self.assertRaises(ValueError):
            models.LeagueSettings.objects.all().delete()
        self.assertTrue(models.LeagueSettings.objects.filter(pk=1).exists())

    def test_editing_the_row_changes_the_season_half_and_roster_windows(self):
        row = league.load()
        row.current_season = 2028
        row.current_season_type = "midseason"
        row.draft_prep_season_type = ""
        row.season_half = "2h"
        row.stats_display_season_cap = 2026
        row.protect_tab = True
        row.roster_tab = True
        row.roster_staff_only = False
        row.live_tab = True
        row.wishlist_tab = True
        row.mlb_roster_size = 28
        row.protect_roster_size = 42
        row.save()

        self.assertEqual(league.current_season(), 2028)
        self.assertEqual(league.current_season_type(), "midseason")
        self.assertEqual(utils.get_draft_prep_season_type(), "midseason")
        self.assertEqual(utils.get_current_season(), 2028)
        self.assertEqual(utils.get_stats_display_season_cap(), 2026)
        self.assertEqual(plans.current_half(), 2)
        self.assertTrue(plans.is_open(2))
        self.assertEqual(league.mlb_roster_size(), 28)
        self.assertEqual(league.protect_roster_size(), 42)

        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        context = utils.build_context(request)
        self.assertTrue(context["protect_tab"])
        self.assertTrue(context["roster_tab"])
        self.assertEqual(context["season_half"], "2h")
        self.assertTrue(context["live_tab"])
        self.assertTrue(context["wishlist_tab"])
        self.assertEqual(context["mlb_roster_size"], 28)
        self.assertEqual(context["previous_season"], 2027)

    @override_settings(
        CURRENT_SEASON=2024,
        CURRENT_SEASON_TYPE="offseason",
        DRAFT_PREP_SEASON_TYPE="midseason",
        TEAM_SEASON_HALF="2h",
        STATS_DISPLAY_SEASON_CAP=2022,
        TEAM_PROTECT_TAB=True,
        TEAM_ROSTER_TAB=False,
        TEAM_ROSTER_STAFF_ONLY=False,
        TEAM_LIVE_TAB=True,
        MLB_ROSTER_SIZE=26,
        PROTECT_ROSTER_SIZE=38,
    )
    def test_a_django_setting_of_the_old_name_still_overrides_the_row(self):
        row = league.load()
        row.current_season = 2030
        row.current_season_type = "midseason"
        row.season_half = "1h"
        row.roster_tab = True
        row.mlb_roster_size = 30
        row.save()

        self.assertEqual(league.current_season(), 2024)
        self.assertEqual(league.current_season_type(), "offseason")
        self.assertEqual(league.draft_prep_season_type(), "midseason")
        self.assertEqual(league.season_half(), "2h")
        self.assertEqual(league.stats_display_season_cap(), 2022)
        self.assertTrue(league.protect_tab())
        self.assertFalse(league.roster_tab())
        self.assertFalse(league.roster_staff_only())
        self.assertTrue(league.live_tab())
        self.assertEqual(league.mlb_roster_size(), 26)
        self.assertEqual(league.protect_roster_size(), 38)
        self.assertEqual(utils.get_current_season(), 2023)
        self.assertEqual(plans.current_half(), 2)

    @override_settings(STATS_DISPLAY_SEASON_CAP=None, CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_an_explicit_empty_stat_cap_override_means_no_cap(self):
        row = league.load()
        row.stats_display_season_cap = 2020
        row.save()
        self.assertIsNone(league.stats_display_season_cap())
        self.assertEqual(utils.get_stats_display_season_cap(), 2026)


class LeagueSettingsAdminTestCase(TestCase):
    def test_the_commissioner_changes_the_season_from_the_admin(self):
        user = User.objects.create_superuser("commish", "commish@example.com", "password")
        client = Client()
        client.force_login(user)
        url = reverse("admin:ulmg_leaguesettings_change", args=[league.load().pk])

        page = client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Set protections")
        self.assertContains(page, "Set rosters")
        self.assertContains(page, "Half")

        response = client.post(
            url,
            {
                "current_season": "2028",
                "current_season_type": "midseason",
                "draft_prep_season_type": "offseason",
                "season_half": "2h",
                "stats_display_season_cap": "",
                "protect_tab": "on",
                "roster_tab": "on",
                "roster_staff_only": "on",
                "mlb_roster_size": "30",
                "protect_roster_size": "40",
                "_save": "Save",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "errorlist")
        row = league.load()
        self.assertEqual(row.current_season, 2028)
        self.assertEqual(row.current_season_type, "midseason")
        self.assertEqual(row.season_half, "2h")
        self.assertTrue(row.protect_tab)
        self.assertTrue(row.roster_tab)
        self.assertFalse(row.live_tab)
