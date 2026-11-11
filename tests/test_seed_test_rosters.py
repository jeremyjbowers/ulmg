# ABOUTME: Tests for seed_test_rosters: a playable test 30-man, a dry run, and the blank.
# ABOUTME: The command is a shell tool. These tests never touch a page.

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from ulmg import models
from tests.plan_fixtures import CARD_SEASON, SEASON, create_hitter, create_pitcher


def set_wrc_plus(player, value):
    models.Card.objects.filter(player=player, season=CARD_SEASON).update(wrc_plus=value)


def run(*args):
    out = StringIO()
    call_command("seed_test_rosters", "--season", str(SEASON), *args, stdout=out)
    return out.getvalue()


def on_mlb():
    return set(models.Player.objects.filter(is_ulmg_mlb_roster=True).values_list("name", flat=True))


class SeedTestRostersTestCase(TestCase):
    def setUp(self):
        self.atl = models.Team.objects.create(abbreviation="ATL", city="Atlanta", nickname="Crackers")
        self.hch = models.Team.objects.create(abbreviation="HCH", city="Hub City", nickname="Hawks")
        self.pitchers = []
        for i in range(14):
            self.pitchers.append(create_pitcher(
                self.atl, f"Arm {i:02d}", stats={"g": 30, "gs": 30 - i, "ip": f"{200 - i * 10}.0"}
            ))
        self.hitters = []
        for i in range(18):
            hitter = create_hitter(self.atl, f"Bat {i:02d}", position="OF")
            set_wrc_plus(hitter, 100 - i)
            self.hitters.append(hitter)
        self.locked = create_hitter(self.atl, "Open Pick", position="DH")
        self.locked.is_ulmg_2h_draft = True
        self.locked.is_ulmg_1h_p = True
        self.locked.save()
        set_wrc_plus(self.locked, 1)
        self.prospect = models.Player.objects.create(
            name="Prospect", position="OF", team=self.atl, is_ulmg_mlb_roster=True
        )
        self.aaa = models.Player.objects.create(
            name="Farm Arm", position="P", team=self.atl, is_ulmg_aaa_roster=True
        )
        create_pitcher(self.hch, "HCH Ace")
        create_hitter(self.hch, "HCH Bat")

    def test_dry_run_prints_the_roster_and_writes_nothing(self):
        out = run("--dry-run")
        self.assertIn("Would file ATL 30/30 (13 pitchers, 17 hitters)", out)
        self.assertIn("Would file HCH 2/30 (1 pitcher, 1 hitter); 28 short", out)
        self.assertIn("Prospect", on_mlb())
        self.assertTrue(models.Player.objects.get(name="Farm Arm").is_ulmg_aaa_roster)

    def test_files_a_staff_and_the_best_bats_and_keeps_an_open_pick(self):
        out = run()
        self.assertIn("Filed ATL 30/30 (13 pitchers, 17 hitters)", out)
        self.assertIn("Filed HCH 2/30 (1 pitcher, 1 hitter); 28 short", out)
        roster = on_mlb()
        self.assertIn("Arm 00", roster)
        self.assertNotIn("Arm 13", roster)
        self.assertIn("Bat 00", roster)
        self.assertIn("Bat 15", roster)
        self.assertNotIn("Bat 16", roster)
        self.assertNotIn("Bat 17", roster)
        self.assertIn("Open Pick", roster)
        self.assertNotIn("Prospect", roster)
        self.assertIn("HCH Ace", roster)
        self.assertIn("HCH Bat", roster)
        self.assertEqual(models.Player.objects.filter(team=self.atl, is_ulmg_mlb_roster=True).count(), 30)
        farm = models.Player.objects.get(name="Farm Arm")
        self.assertFalse(farm.is_ulmg_mlb_roster)
        self.assertFalse(farm.is_ulmg_aaa_roster)
        ace = models.Player.objects.get(name="Arm 00")
        row = models.PlayerStatSeason.objects.get(player=ace, season=SEASON, classification="1-mlb")
        self.assertTrue(row.is_ulmg_mlb_roster)
        self.assertFalse(row.is_ulmg_aaa_roster)
        card_row = models.PlayerStatSeason.objects.get(player=ace, season=CARD_SEASON, classification="1-mlb")
        self.assertFalse(card_row.is_ulmg_mlb_roster)
        self.assertTrue(models.Player.objects.get(name="Open Pick").is_ulmg_1h_p)

        again = run()
        self.assertIn("Filed ATL 30/30", again)
        self.assertEqual(on_mlb(), roster)

    def test_reset_clears_mlb_and_aaa_and_leaves_a_protection(self):
        run()
        out = run("--reset")
        self.assertIn("Blanked MLB and AAA rosters:", out)
        self.assertFalse(models.Player.objects.filter(is_ulmg_mlb_roster=True).exists())
        self.assertFalse(models.Player.objects.filter(is_ulmg_aaa_roster=True).exists())
        self.assertFalse(
            models.PlayerStatSeason.objects.filter(season=SEASON, is_ulmg_mlb_roster=True).exists()
        )
        self.assertTrue(models.Player.objects.get(name="Open Pick").is_ulmg_1h_p)
        preview = run("--reset", "--dry-run")
        self.assertIn("Would blank 0 players and 0 stat lines.", preview)
        self.assertTrue(models.Player.objects.get(name="Open Pick").is_ulmg_1h_p)

    def test_warns_when_the_half_has_already_started(self):
        models.RosterMove.objects.create(
            season=SEASON, half=1, team=self.atl,
            player_up=self.hitters[0], player_down=self.hitters[1], stay_games=15,
        )
        out = run("--dry-run")
        self.assertIn("Half 1 of 2027 has started", out)
        self.assertIn("Would file ATL", out)
