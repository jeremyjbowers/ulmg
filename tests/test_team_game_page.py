# ABOUTME: Tests for the team Game tab: lineups, the schedule and call-ups live there, and the four stretches of a season.
# ABOUTME: The roster page stays the roster the half opens with. Uses real teams, players and the test client.

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ulmg import models, roster_moves
from tests.usage_fixtures import ULMG_SEASON, create_pitcher, create_series, create_teams


def create_owner(username, team):
    user = User.objects.create_user(username, f"{username}@example.com", "password")
    owner = models.Owner.objects.create(user=user, name=f"{username} owner", email=user.email)
    team.owner_obj = owner
    team.save()
    return user


@override_settings(CURRENT_SEASON=ULMG_SEASON, TEAM_SEASON_HALF="1h")
class PlayPeriodTestCase(TestCase):
    def test_before_the_first_half_the_four_stretches_are_named(self):
        periods = roster_moves.play_periods(ULMG_SEASON)
        self.assertEqual(
            [(p.half, p.side, p.label, p.status) for p in periods],
            [
                (1, "home", "First half, home", "setting the roster"),
                (1, "away", "First half, away", "setting the roster"),
                (2, "home", "Second half, home", "after the trade break"),
                (2, "away", "Second half, away", "after the trade break"),
            ],
        )

    @override_settings(TEAM_SEASON_HALF="2h")
    def test_the_break_is_the_second_half_before_it_starts(self):
        periods = roster_moves.play_periods(ULMG_SEASON)
        self.assertEqual(
            [p.status for p in periods],
            ["complete", "complete", "setting the roster", "setting the roster"],
        )


@override_settings(CURRENT_SEASON=ULMG_SEASON, TEAM_SEASON_HALF="1h", TEAM_ROSTER_TAB=True)
class GamePageTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.home, cls.atl = create_teams()
        create_series(cls.home, cls.atl, length=3)
        cls.owner = create_owner("atl", cls.atl)
        cls.starter = create_pitcher("ATL Starter", team=cls.atl, g=10, gs=10, ip="60.0")
        cls.starter.is_ulmg_mlb_roster = True
        cls.starter.save()
        cls.call_up = create_pitcher("ATL Call-up", team=cls.atl, g=20, gs=0, ip="20.0")
        cls.call_up.is_ulmg_aaa_roster = True
        cls.call_up.save()

    def setUp(self):
        self.client.force_login(self.owner)

    def test_the_game_page_lists_the_four_stretches_and_the_lineup_and_schedule_pages(self):
        page = self.client.get("/teams/atl/game/")
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        self.assertLess(body.index("Roster"), body.index(">Game</"))
        self.assertLess(body.index(">Game</"), body.index("Trades & picks"))
        for label in ("First half, home", "First half, away", "Second half, home", "Second half, away"):
            self.assertIn(label, body)
        self.assertIn('href="/teams/atl/plan/1/"', body)
        self.assertIn('href="/teams/atl/schedule/"', body)
        self.assertIn('href="/teams/atl/results/"', body)
        self.assertIn("half-not-started", body)

    def test_a_move_changes_the_away_roster_and_leaves_the_home_roster(self):
        roster_moves.make_move(self.atl, self.call_up, self.starter, season=ULMG_SEASON, half=1)
        page = self.client.get("/teams/atl/game/")
        body = page.content.decode()
        home = body.split('id="home-roster"', 1)[1].split('id="away-roster"', 1)[0]
        away = body.split('id="away-roster"', 1)[1].split('id="call-up-pool"', 1)[0]
        self.assertIn(self.starter.name, home)
        self.assertNotIn(self.call_up.name, home)
        self.assertNotIn("/moves/new/", home)
        self.assertIn(self.call_up.name, away)
        self.assertNotIn(self.starter.name, away)
        self.assertIn("in play", body)
        self.assertIn("the computer will not use a player who is out of plate appearances or innings", body)

        roster = self.client.get("/teams/atl/").content.decode()
        self.assertIn("opening-roster-note", roster)
        self.assertIn('class="opening-roster-player', roster)
        self.assertNotIn("Send down</a>", roster)
        self.assertNotIn('href="/teams/atl/plan/', roster)
        self.assertNotIn('href="/teams/atl/schedule/"', roster)
