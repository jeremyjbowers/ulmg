# ABOUTME: Tests for the team Game tab: filing gaps, games played and left, and the next road series.
# ABOUTME: The roster page stays the roster the half opens with. Uses real teams, players and the test client.

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ulmg import models, plans, roster_moves, schedule, utils
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
        patcher = patch("ulmg.utils.league_season", return_value=ULMG_SEASON)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_game_page_names_filing_gaps_and_the_next_road_series(self):
        page = self.client.get("/teams/atl/game/")
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        self.assertLess(body.index("Roster"), body.index(">Game</"))
        self.assertLess(body.index(">Game</"), body.index("Trades & picks"))
        self.assertNotIn("First half, home", body)
        self.assertNotIn("This half", body)
        self.assertIn(">Up next<", body)
        year = utils.league_season()
        self.assertIn(f'href="/teams/atl/plan/1/{year}/edit/"', body)
        self.assertIn(f'href="/teams/atl/schedule/{year}/"', body)
        self.assertIn(f'href="/teams/atl/results/{year}/"', body)
        self.assertIn(">Set lineups<", body)
        self.assertIn(">Set rotation<", body)
        self.assertIn(f'href="/teams/atl/plan/1/{year}/bullpen/"', body)
        self.assertLess(body.index(">Schedule<"), body.index(">Bullpen<"))
        self.assertLess(body.index(">Bullpen<"), body.index(">Results<"))
        self.assertIn('id="plan-gaps"', body)
        for note in (
            "Lineups are not filed.",
            "No rotation is set.",
            "No closer is named.",
            "No one is in single-inning relief.",
            "No one is in multi-inning relief.",
        ):
            self.assertIn(note, body)
        self.assertNotIn('id="schedule-progress"', body)
        self.assertNotIn('id="home-roster"', body)
        self.assertNotIn('data-side="home"', body)
        series = body.split('id="away-series"', 1)[1]
        self.assertIn('data-opponent="HCH"', series)
        self.assertIn('data-day="1"', series)
        self.assertIn("No starter", series)
        game = models.ScheduleGame.objects.get(series__road_team=self.atl, day=1)
        self.assertIn(f'href="/games/{game.id}/"', series)
        self.assertEqual(series.count("schedule-play"), 1)

    def test_a_played_road_game_counts_and_drops_off_the_list(self):
        game = models.ScheduleGame.objects.get(series__road_team=self.atl, day=1)
        game.home_score = 4
        game.road_score = 2
        game.save()
        body = self.client.get("/teams/atl/game/").content.decode()
        self.assertIn("Away: 1 played, 2 left. Home: 0 played, 0 left.", body)
        listed = body.split('id="away-series"', 1)[1].split('id="away-roster"', 1)[0]
        self.assertNotIn('data-day="1"', listed)
        self.assertIn('data-day="2"', listed)
        self.assertIn("1 played, 2 left", listed)
        self.assertNotIn('data-side="home"', body)
        nxt = models.ScheduleGame.objects.get(series__road_team=self.atl, day=2)
        self.assertEqual(body.count("schedule-play"), 1)
        self.assertIn(f'href="/games/{nxt.id}/"', body)

    def test_a_home_series_stays_off_the_list(self):
        foe = models.Team.objects.create(
            abbreviation="BOS", city="Boston", nickname="Pilgrims", division="Rickey"
        )
        create_series(self.atl, foe, length=2, slot_number=8, first_day=10)
        body = self.client.get("/teams/atl/game/").content.decode()
        series = body.split('id="away-series"', 1)[1]
        self.assertIn('data-opponent="HCH"', series)
        self.assertNotIn('data-opponent="BOS"', series)

    def test_a_filed_plan_has_no_gap_notes(self):
        card = [{}] * plans.LINEUP_SIZE
        plan = models.HalfPlan.objects.create(
            team=self.atl,
            season=ULMG_SEASON,
            half=1,
            rotation=[self.starter.id],
            closer=self.starter,
            sirp=[self.starter.id],
            mirp=[self.call_up.id],
            lineup_vs_lhp=card,
            lineup_vs_rhp=card,
        )
        for game in models.ScheduleGame.objects.filter(series__slot__season=ULMG_SEASON):
            models.HalfPlanDay.objects.create(plan=plan, day=game.day, auto_starter=self.starter)
        body = self.client.get("/teams/atl/game/").content.decode()
        self.assertIn('id="plan-complete"', body)
        self.assertNotIn('id="plan-gaps"', body)
        self.assertIn(self.starter.name, body.split('id="away-series"', 1)[1])

    def test_a_move_changes_the_away_roster(self):
        roster_moves.make_move(self.atl, self.call_up, self.starter, season=ULMG_SEASON, half=1)
        page = self.client.get("/teams/atl/game/")
        body = page.content.decode()
        self.assertNotIn('id="home-roster"', body)
        away = body.split('id="away-roster"', 1)[1].split('id="call-up-pool"', 1)[0]
        self.assertIn(self.call_up.name, away)
        self.assertNotIn(self.starter.name, away)
        self.assertIn("Away: 0 played, 3 left. Home: 0 played, 0 left.", body)
        self.assertIn("the computer will not use a player who is out of plate appearances or innings", body)

        roster = self.client.get("/teams/atl/").content.decode()
        self.assertIn("opening-roster-note", roster)
        self.assertIn('class="opening-roster-player', roster)
        self.assertNotIn("Send down</a>", roster)
        self.assertNotIn('href="/teams/atl/plan/', roster)
        self.assertNotIn('href="/teams/atl/schedule/"', roster)


def _club(abbreviation):
    return models.Team.objects.create(
        abbreviation=abbreviation, city=abbreviation, nickname="Club", division="Rickey"
    )


def _filed(team, starter, season=ULMG_SEASON):
    card = [{}] * plans.LINEUP_SIZE
    return models.HalfPlan.objects.create(
        team=team,
        season=season,
        half=1,
        rotation=[starter.id],
        closer=starter,
        sirp=[starter.id],
        mirp=[starter.id],
        lineup_vs_lhp=card,
        lineup_vs_rhp=card,
    )


class PlanGapTestCase(TestCase):
    def test_an_empty_plan_names_every_gap(self):
        _, atl = create_teams()
        notes = [(gap["kind"], gap["text"]) for gap in plans.plan_gaps(atl, ULMG_SEASON, 1)]
        self.assertEqual(
            notes,
            [
                ("lineups", "Lineups are not filed."),
                ("rotation", "No rotation is set."),
                ("bullpen", "No closer is named."),
                ("bullpen", "No one is in single-inning relief."),
                ("bullpen", "No one is in multi-inning relief."),
            ],
        )

    def test_one_short_lineup_card_is_named(self):
        _, atl = create_teams()
        starter = create_pitcher("ATL Starter", team=atl, g=10, gs=10, ip="60.0")
        plan = _filed(atl, starter)
        plan.lineup_vs_lhp = []
        plan.save()
        self.assertEqual(
            plans.plan_gaps(atl, ULMG_SEASON, 1),
            [{"kind": "lineups", "text": "The lineup vs LHP is not filed."}],
        )

    def test_open_days_without_a_starter_are_a_rotation_gap(self):
        home, atl = create_teams()
        create_series(home, atl, length=2)
        starter = create_pitcher("ATL Starter", team=atl, g=10, gs=10, ip="60.0")
        plan = _filed(atl, starter)
        models.HalfPlanDay.objects.create(
            plan=plan,
            day=1,
            auto_starter=starter,
        )
        self.assertEqual(
            plans.plan_gaps(atl, ULMG_SEASON, 1),
            [{"kind": "rotation", "text": "1 open day has no starter."}],
        )

    def test_a_complete_plan_has_no_gaps(self):
        home, atl = create_teams()
        games = create_series(home, atl, length=2)
        starter = create_pitcher("ATL Starter", team=atl, g=10, gs=10, ip="60.0")
        plan = _filed(atl, starter)
        for game in games:
            models.HalfPlanDay.objects.create(plan=plan, day=game.day, auto_starter=starter)
        self.assertEqual(plans.plan_gaps(atl, ULMG_SEASON, 1), [])


class UpcomingRoadSeriesTestCase(TestCase):
    def test_the_next_three_road_series_skip_home_games_and_finished_series(self):
        home, atl = create_teams()
        first = create_series(home, atl, length=2, slot_number=1, first_day=1)
        first[0].home_score = 3
        first[0].road_score = 1
        first[0].save()
        extras = []
        for number, abbreviation in enumerate(["BOS", "NYK", "CHI", "DET"], start=2):
            club = _club(abbreviation)
            create_series(club, atl, length=1, slot_number=number, first_day=10 + number)
            extras.append(abbreviation)
        foe = _club("PHI")
        create_series(atl, foe, length=2, slot_number=8, first_day=30)

        rows = schedule.upcoming_road_series(atl, ULMG_SEASON, 1)
        self.assertEqual([row["opponent"].abbreviation for row in rows], ["HCH", "BOS", "NYK"])
        self.assertEqual(rows[0]["played"], 1)
        self.assertEqual(rows[0]["left"], 1)
        self.assertEqual([game.day for game in rows[0]["games"]], [2])
        self.assertNotIn("CHI", [row["opponent"].abbreviation for row in rows])
        self.assertNotIn("PHI", [row["opponent"].abbreviation for row in rows])

        counts = schedule.half_game_counts(atl, ULMG_SEASON, 1)
        self.assertEqual(counts["away"], {"played": 1, "left": 5})
        self.assertEqual(counts["home"], {"played": 0, "left": 2})
