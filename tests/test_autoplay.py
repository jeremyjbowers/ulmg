# ABOUTME: Tests autoplay against the real engine: a game from the first pitch and from the middle, a series, permissions and replay.
# ABOUTME: Also the game page's autoplay form and the autoplay_season command, on a generated schedule with filed half plans.

import time
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from tests import game_fixtures as gf
from ulmg import autoplay, box_score, models, plans, season_record, sim_game

Event = models.GameEvent
AWAY, HOME = sim_game.AWAY, sim_game.HOME

# A whole autoplayed game must fit comfortably inside one web request.
REQUEST_BUDGET_SECONDS = 60


def series_games(game):
    return list(models.ScheduleGame.objects.filter(series=game.series).order_by("day"))


def handed_over(log):
    """The seat events autoplay wrote, in order."""
    return [e for e in gf.events(log, Event.SEAT) if e.payload.get("autoplay")]


class AutoplayTestCase(gf.EngineMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        gf.create_game_season(cls)
        cls.commissioner = User.objects.create_superuser("commish", "commish@example.com", "password")

    def setUp(self):
        self.next_seed = gf.seeds()

    def autoplay(self, game=None, user=None, expected=None):
        return autoplay.autoplay_game(game or self.game, user or self.manager, expected=expected, seeds=self.next_seed)

    def assert_final(self, log):
        log = gf.refresh(log)
        self.assertEqual(log.state["status"], "final")
        self.assertEqual(len(gf.events(log, Event.FINAL)), 1)
        game = models.ScheduleGame.objects.get(pk=log.game_id)
        self.assertEqual((game.road_score, game.home_score), (log.state["score"]["away"], log.state["score"]["home"]))
        return log


class AutoplayFromTheFirstPitchTestCase(AutoplayTestCase):
    def test_the_visitor_autoplays_an_unopened_game_to_its_final(self):
        started = time.monotonic()
        result = self.autoplay()
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, REQUEST_BUDGET_SECONDS)

        log = self.assert_final(result.log)
        self.assertTrue(result.final)
        self.assertIsNone(result.paused)
        self.assertEqual(result.plate_appearances, len(gf.events(log, Event.PLATE_APPEARANCE)))
        self.assertGreater(result.plate_appearances, 50)

        opening = gf.events(log, Event.OPEN)[0]
        self.assertEqual(opening.user, self.manager)
        seats = gf.events(log, Event.SEAT)
        self.assertEqual([(e.side, e.user, e.computer) for e in seats], [(AWAY, None, True), (HOME, None, True)])
        self.assertTrue(all(e.payload["autoplay"] and e.payload["by"] == self.manager.id for e in seats))
        self.assertIn("road-manager", seats[0].text)

        for pa in gf.events(log, Event.PLATE_APPEARANCE):
            self.assertTrue(pa.computer)
            self.assertIsNone(pa.user)
        for event in gf.events(log, Event.DECISION) + gf.events(log, Event.PITCHING_CHANGE):
            self.assertTrue(event.computer)

    def test_both_sides_start_from_their_frozen_half_plans(self):
        sheet = plans.game_sheet(self.game)
        log = self.autoplay().log
        start = gf.events(log, Event.START)[0]
        self.assertEqual(start.payload["starters"], {AWAY: sheet["road"]["starter"].id, HOME: sheet["home"]["starter"].id})
        self.assertEqual(
            [entry["player"] for entry in start.payload["lineups"][AWAY]],
            [player.id for player, _ in sheet["road"]["lineup"]],
        )

    def test_the_final_is_recorded_in_the_season_record(self):
        log = self.autoplay().log
        state = gf.refresh(log).state
        road = models.TeamSeasonRecord.objects.get(team=self.road.team, season=gf.SEASON)
        self.assertEqual((road.runs_scored, road.runs_allowed), (state["score"]["away"], state["score"]["home"]))
        self.assertEqual(road.wins + road.losses, 1)

    def test_an_autoplayed_game_never_crosses_a_usage_cap(self):
        gf.counter(self.home.relievers[0], relief_limit_outs=0)
        log = self.autoplay().log
        pitched = {e.payload["pitcher"] for e in gf.events(log, Event.PLATE_APPEARANCE)}
        self.assertNotIn(self.home.relievers[0].id, pitched)


class AutoplayFromTheMiddleTestCase(AutoplayTestCase):
    def test_the_visitor_hands_the_rest_of_a_game_in_progress_to_his_computer(self):
        log = sim_game.open_game(self.game, self.manager, (AWAY,), seeds=self.next_seed)
        for _ in range(12):
            log = gf.refresh(log)
            sim_game.step(log, self.manager, sim_game.Play(log).sequence, seeds=self.next_seed)
        before = gf.events(log)
        played_by_hand = [e for e in before if e.kind == Event.PLATE_APPEARANCE]
        self.assertEqual(len(played_by_hand), 12)

        result = self.autoplay(expected=sim_game.Play(gf.refresh(log)).sequence)
        log = self.assert_final(result.log)
        after = gf.events(log)
        self.assertEqual([e.id for e in after[: len(before)]], [e.id for e in before])
        handover = after[len(before)]
        self.assertEqual((handover.kind, handover.side, handover.user, handover.computer), (Event.SEAT, AWAY, None, True))
        self.assertEqual(handover.payload, {"autoplay": True, "by": self.manager.id, "from": self.manager.id})
        self.assertEqual(len(handed_over(log)), 1)
        for pa in played_by_hand:
            self.assertEqual(pa.user, self.manager)
        for pa in [e for e in after[len(before):] if e.kind == Event.PLATE_APPEARANCE]:
            self.assertTrue(pa.computer)
            self.assertIsNone(pa.user)
        self.assertEqual(result.plate_appearances, len(gf.events(log, Event.PLATE_APPEARANCE)) - 12)

    def test_a_stale_autoplay_plays_nothing(self):
        log = sim_game.open_game(self.game, self.manager, (AWAY,), seeds=self.next_seed)
        count = len(gf.events(log))
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.autoplay(expected=count - 1)
        self.assertEqual(refused.exception.reasons, [sim_game.STALE])
        self.assertEqual(len(gf.events(log)), count)

    def test_the_commissioner_autoplays_a_game_a_tester_holds_both_seats_of(self):
        log = sim_game.open_game(self.game, self.tester, (AWAY, HOME), seeds=self.next_seed)
        for _ in range(3):
            log = gf.refresh(log)
            sim_game.step(log, self.tester, sim_game.Play(log).sequence, seeds=self.next_seed)
        result = self.autoplay(user=self.commissioner, expected=sim_game.Play(gf.refresh(log)).sequence)
        log = self.assert_final(result.log)
        self.assertEqual(
            [(e.side, e.payload["from"], e.payload["by"]) for e in handed_over(log)],
            [(AWAY, self.tester.id, self.commissioner.id), (HOME, self.tester.id, self.commissioner.id)],
        )

    def test_a_game_that_pauses_for_a_pitcher_stops_and_says_so(self):
        gf.counter(self.home.starters[0], start_limit_outs=3)
        for pitcher in self.home.starters[1:] + self.home.relievers + [self.home.swingman]:
            gf.counter(pitcher, relief_limit_outs=0)
        with self.assertLogs("ulmg.usage", level="WARNING") as logged:
            result = self.autoplay()
        self.assertIn("has no legal pitcher", logged.output[0])
        self.assertFalse(result.final)
        self.assertEqual(result.paused["side"], HOME)
        self.assertIn("no legal pitcher", result.paused["reason"])
        log = gf.refresh(result.log)
        self.assertNotEqual(log.state["status"], "final")
        self.assertEqual(sim_game.Play(log).fold.pause["side"], HOME)


class AutoplaySeriesTestCase(AutoplayTestCase):
    def test_the_visitor_autoplays_the_rest_of_a_series_in_schedule_order(self):
        games = series_games(self.game)
        self.assertGreater(len(games), 1)
        sheets = {game.id: plans.game_sheet(game) for game in games}
        started = time.monotonic()
        results = autoplay.autoplay_series(self.game, self.manager, seeds=self.next_seed)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, REQUEST_BUDGET_SECONDS * len(games))

        self.assertEqual([r.log.game_id for r in results], [g.id for g in games])
        logs = [self.assert_final(r.log) for r in results]
        opened = [models.ScheduleGame.objects.get(pk=g.id).opened_at for g in games]
        self.assertEqual(opened, sorted(opened))
        for game, log in zip(games, logs):
            start = gf.events(log, Event.START)[0]
            sheet = sheets[game.id]
            decided = {e.side for e in gf.events(log, Event.DECISION) if e.payload.get("need") == "starter"}
            for side, key in ((AWAY, "road"), (HOME, "home")):
                if side not in decided:
                    self.assertEqual(start.payload["starters"][side], sheet[key]["starter"].id)
        self.assertEqual(len({gf.events(log, Event.START)[0].payload["starters"][AWAY] for log in logs}), len(games))

    def test_the_series_continues_from_a_game_in_progress(self):
        log = sim_game.open_game(self.game, self.manager, (AWAY,), seeds=self.next_seed)
        sim_game.step(gf.refresh(log), self.manager, sim_game.Play(gf.refresh(log)).sequence, seeds=self.next_seed)
        expected = sim_game.Play(gf.refresh(log)).sequence
        results = autoplay.autoplay_series(self.game, self.manager, expected=expected, seeds=self.next_seed)
        self.assertEqual([r.log.game_id for r in results], [g.id for g in series_games(self.game)])
        self.assertTrue(all(r.final for r in results))
        self.assertEqual(results[0].log.pk, log.pk)


class AutoplayPermissionsTestCase(AutoplayTestCase):
    def test_another_teams_manager_may_not_autoplay_the_game(self):
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.autoplay(user=self.other_manager)
        self.assertIn(f"Only {self.road.team.abbreviation}'s manager or the commissioner", str(refused.exception))
        self.assertFalse(models.GameLog.objects.exists())

    def test_a_sim_tester_who_is_not_the_commissioner_may_not_autoplay_another_teams_game(self):
        with self.assertRaises(sim_game.GameRefused):
            self.autoplay(user=self.tester)
        self.assertFalse(models.GameLog.objects.exists())

    def test_a_manager_may_autoplay_only_his_next_road_game(self):
        later = series_games(self.game)[1]
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.autoplay(game=later)
        self.assertIn("next unplayed road game", str(refused.exception))
        self.assertFalse(models.GameLog.objects.exists())

    def test_a_manager_may_not_hand_over_a_seat_someone_else_holds(self):
        log = sim_game.open_game(self.game, self.tester, (HOME,), seeds=self.next_seed)
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.autoplay(expected=sim_game.Play(gf.refresh(log)).sequence)
        self.assertIn("holds the", str(refused.exception))
        self.assertEqual(handed_over(log), [])

    def test_the_commissioner_may_autoplay_any_unplayed_game(self):
        later = series_games(self.game)[1]
        result = self.autoplay(game=later, user=self.commissioner)
        self.assert_final(result.log)

    def test_a_final_game_cannot_be_autoplayed_again(self):
        self.autoplay()
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.autoplay(user=self.commissioner)
        self.assertIn("final", str(refused.exception))

    def test_a_game_scored_outside_the_sim_cannot_be_autoplayed(self):
        models.ScheduleGame.objects.filter(pk=self.game.pk).update(road_score=1, home_score=2)
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.autoplay(user=self.commissioner)
        self.assertIn("already has a score", str(refused.exception))


class AutoplayReplayTestCase(AutoplayTestCase):
    def test_a_final_autoplayed_game_rebuilds_from_its_log(self):
        log = sim_game.open_game(self.game, self.manager, (AWAY,), seeds=self.next_seed)
        for _ in range(5):
            log = gf.refresh(log)
            sim_game.step(log, self.manager, sim_game.Play(log).sequence, seeds=self.next_seed)
        log = self.autoplay(expected=sim_game.Play(gf.refresh(log)).sequence).log
        log = gf.refresh(log)
        final_state = log.state
        self.assertEqual(sim_game.replay(gf.events(log)), final_state)

        box = box_score.box_score(log)
        stored = {
            (row.player_id): (row.hit_stats, row.pitch_stats)
            for row in models.PlayerStatSeason.objects.filter(season=gf.SEASON, classification=models.PlayerStatSeason.ULMG)
        }
        models.GameLog.objects.filter(pk=log.pk).update(state=None, state_sequence=0)
        log = gf.refresh(log)
        play = sim_game.Play(log)
        self.assertEqual(play.state, final_state)
        self.assertTrue(play.fold.final)
        rebuilt_box = box_score.box_score(log)
        self.assertEqual((rebuilt_box.line, rebuilt_box.totals), (box.line, box.totals))
        self.assertEqual((rebuilt_box.win, rebuilt_box.loss, rebuilt_box.save), (box.win, box.loss, box.save))

        models.PlayerStatSeason.objects.filter(season=gf.SEASON, classification=models.PlayerStatSeason.ULMG).delete()
        season_record.rebuild_season(gf.SEASON)
        rebuilt = {
            (row.player_id): (row.hit_stats, row.pitch_stats)
            for row in models.PlayerStatSeason.objects.filter(season=gf.SEASON, classification=models.PlayerStatSeason.ULMG)
        }
        self.assertEqual(rebuilt, stored)


class AutoplayPageTestCase(AutoplayTestCase):
    def test_the_visitor_sees_and_uses_the_autoplay_form_before_the_game_opens(self):
        self.client.force_login(self.manager)
        page = self.client.get(f"/games/{self.game.id}/")
        self.assertContains(page, "game-autoplay")
        self.assertContains(page, "Autoplay the rest of the series")
        response = self.client.post(f"/games/{self.game.id}/autoplay/", {"scope": "game"}, follow=True)
        log = self.assert_final(models.GameLog.objects.get(game=self.game))
        self.assertContains(response, "game-final")
        self.assertContains(response, "Autoplayed")
        self.assertEqual(len(handed_over(log)), 2)

    def test_another_manager_sees_no_autoplay_form_and_is_refused(self):
        self.client.force_login(self.other_manager)
        page = self.client.get(f"/games/{self.game.id}/")
        self.assertNotContains(page, "game-autoplay")
        response = self.client.post(f"/games/{self.game.id}/autoplay/", {"scope": "game"}, follow=True)
        self.assertContains(response, "or the commissioner can autoplay")
        self.assertFalse(models.GameLog.objects.exists())

    def test_the_visitor_autoplays_the_series_from_the_game_page(self):
        log = sim_game.open_game(self.game, self.manager, (AWAY,), seeds=self.next_seed)
        self.client.force_login(self.manager)
        page = self.client.get(f"/games/{self.game.id}/")
        self.assertContains(page, "game-autoplay")
        expected = sim_game.Play(gf.refresh(log)).sequence
        self.client.post(f"/games/{self.game.id}/autoplay/", {"scope": "series", "expected": expected})
        for game in series_games(self.game):
            self.assert_final(models.GameLog.objects.get(game=game))

    def test_a_stale_autoplay_post_plays_nothing(self):
        log = sim_game.open_game(self.game, self.manager, (AWAY,), seeds=self.next_seed)
        count = len(gf.events(log))
        self.client.force_login(self.manager)
        response = self.client.post(f"/games/{self.game.id}/autoplay/", {"scope": "game"}, follow=True)
        self.assertContains(response, "The game has moved on")
        self.assertEqual(len(gf.events(log)), count)


class AutoplaySeasonCommandTestCase(AutoplayTestCase):
    def run_command(self, *args):
        out = StringIO()
        call_command("autoplay_season", "--season", str(gf.SEASON), *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def team_games(self):
        return [g for g in models.ScheduleGame.objects.filter(series__slot__season=gf.SEASON).order_by("day")
                if self.road.team in (g.series.road_team, g.series.home_team)]

    def test_it_autoplays_a_teams_unplayed_games_in_day_order(self):
        output = self.run_command("--team", self.road.team.abbreviation, "--games", "2")
        first, second = self.team_games()[:2]
        for game in (first, second):
            self.assert_final(models.GameLog.objects.get(game=game))
        self.assertEqual(models.GameLog.objects.count(), 2)
        lines = [line for line in output.splitlines() if line.startswith("Day")]
        self.assertEqual(len(lines), 2)
        self.assertEqual([line.split(":")[0] for line in lines], [f"Day {first.day}", f"Day {second.day}"])
        self.assertIn(first.series.road_team.abbreviation, lines[0])
        self.assertIn("final", lines[0])
        self.assertIn("Autoplayed 2 games.", output)

    def test_a_dry_run_lists_the_games_and_plays_nothing(self):
        output = self.run_command("--team", self.road.team.abbreviation, "--games", "3", "--dry-run")
        self.assertEqual(len([line for line in output.splitlines() if line.startswith("Day")]), 3)
        self.assertIn("Dry run", output)
        self.assertFalse(models.GameLog.objects.exists())

    def test_it_skips_final_games_and_finishes_one_in_progress(self):
        self.autoplay()
        log = sim_game.open_game(series_games(self.game)[1], self.manager, (AWAY,), seeds=self.next_seed)
        self.run_command("--team", self.road.team.abbreviation, "--games", "1")
        self.assert_final(log)
        self.assertEqual(models.GameLog.objects.count(), 2)

    def test_it_stops_cleanly_when_a_game_pauses_for_a_pitcher(self):
        gf.counter(self.home.starters[0], start_limit_outs=3)
        for pitcher in self.home.starters[1:] + self.home.relievers + [self.home.swingman]:
            gf.counter(pitcher, relief_limit_outs=0)
        with self.assertLogs("ulmg.usage", level="WARNING"):
            output = self.run_command("--team", self.road.team.abbreviation, "--games", "3")
        self.assertIn("paused", output)
        self.assertIn("no legal pitcher", output)
        self.assertIn("Stopped", output)
        self.assertEqual(models.GameLog.objects.count(), 1)

    def test_a_game_that_cannot_open_stops_the_command_with_its_reasons(self):
        models.Card.objects.filter(player=self.road.bench[1]).delete()
        with self.assertRaises(CommandError) as raised:
            self.run_command("--team", self.road.team.abbreviation)
        self.assertIn(f"{self.road.bench[1].name} has no card.", str(raised.exception))
        self.assertFalse(models.GameLog.objects.exists())

    def test_an_unknown_team_is_refused(self):
        with self.assertRaises(CommandError):
            self.run_command("--team", "ZZZ")
