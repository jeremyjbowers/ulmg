# ABOUTME: Tests the sim game against the real engine: opening, stepping, the log, replay, usage, the computer manager and the final.
# ABOUTME: Plays real games on a generated schedule with filed half plans; seeds come from a counter so every game is repeatable.

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from tests import game_fixtures as gf
from ulmg import box_score, models, plans, sim_game, usage

Event = models.GameEvent
AWAY, HOME = sim_game.AWAY, sim_game.HOME


class SimGameTestCase(gf.EngineMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        gf.create_game_season(cls)

    def setUp(self):
        self.next_seed = gf.seeds()

    def open(self, user=None, seats=(AWAY,)):
        return sim_game.open_game(self.game, user or self.manager, seats, seeds=self.next_seed)

    def step(self, log, user=None, call=None):
        log = gf.refresh(log)
        sim_game.step(log, user or self.manager, sim_game.Play(log).sequence, call=call, seeds=self.next_seed)
        return gf.refresh(log)

    def play(self, log):
        return sim_game.Play(gf.refresh(log))

    def step_until(self, log, done, user=None, limit=200):
        """Step as the user, making his forced replacements, until done(play) is true."""
        user = user or self.manager
        for _ in range(limit):
            play = self.play(log)
            if done(play):
                return play
            need = play.need()
            if need is not None and play.fold.holds(user, need.side):
                choice = gf.first_legal(play.options_for(need))
                if need.kind == sim_game.PITCHER_NEED:
                    sim_game.change_pitcher(log, user, need.side, choice, play.sequence, seeds=self.next_seed)
                else:
                    sim_game.replace_batter(log, user, need.side, choice, play.sequence, seeds=self.next_seed)
                continue
            self.step(log, user)
        raise AssertionError("the condition never came")


class OpeningTestCase(SimGameTestCase):
    def test_each_side_starts_its_planned_starter_and_lineup(self):
        sheet = plans.game_sheet(self.game)
        log = self.open()
        state = gf.refresh(log).state
        for side, key in ((AWAY, "road"), (HOME, "home")):
            self.assertEqual(state[side]["pitcher_slot"], str(sheet[key]["starter"].id))
            self.assertEqual(
                [b["id"] for b in state[side]["lineup"]],
                [str(p.id) for p, _ in sheet[key]["lineup"]],
            )
            self.assertEqual([b["position"] for b in state[side]["lineup"]], [pos for _, pos in sheet[key]["lineup"]])

    def test_opening_copies_both_plans_into_the_log_and_seats_the_visitor(self):
        log = self.open()
        opening = gf.events(log, Event.OPEN)[0]
        self.assertEqual(opening.payload["sheet"]["road"]["starter"], self.road.starters[0].id)
        self.assertEqual(opening.payload["sheet"]["home"]["starter"], self.home.starters[0].id)
        seats = {e.side: e.user for e in gf.events(log, Event.SEAT)}
        self.assertEqual(seats, {AWAY: self.manager, HOME: None})
        self.assertEqual([e.sequence for e in gf.events(log)], list(range(1, len(gf.events(log)) + 1)))
        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.opened_at)

    def test_an_illegal_planned_home_starter_gives_way_to_the_next_legal_one_in_rotation(self):
        planned = self.home.starters[0]
        gf.counter(planned, starts=30, starts_cap=30)
        log = self.open()
        state = gf.refresh(log).state
        self.assertEqual(state[HOME]["pitcher_slot"], str(self.home.starters[1].id))
        decision = gf.events(log, Event.DECISION)[0]
        self.assertTrue(decision.computer)
        self.assertEqual(decision.side, HOME)
        self.assertIn(planned.name, decision.text)
        self.assertIn("30 of his 30 starts", decision.text)

    def test_an_illegal_planned_visiting_starter_refuses_the_opening(self):
        gf.counter(self.road.starters[0], starts=30, starts_cap=30)
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.open()
        self.assertIn("Spot-start another pitcher", str(refused.exception))
        self.assertFalse(models.GameLog.objects.exists())
        self.game.refresh_from_db()
        self.assertIsNone(self.game.opened_at)

    def test_the_visitor_spot_starts_before_the_first_pitch_through_his_plan(self):
        plan = plans.find_plan(self.road.team, gf.SEASON, 1)
        plans.save_day(plan, self.game.day, starter=self.road.swingman)
        log = self.open()
        self.assertEqual(gf.refresh(log).state[AWAY]["pitcher_slot"], str(self.road.swingman.id))

    def test_a_plan_edit_after_the_game_opened_changes_nothing(self):
        log = self.open()
        before = gf.refresh(log).state
        plan = plans.find_plan(self.home.team, gf.SEASON, 1)
        rotation = list(reversed(self.home.starters))
        lineup = [dict(entry, order=10 - entry["order"]) for entry in self.home.lineup()]
        self.home.file(half=1, rotation=rotation, lineup_vs_lhp=lineup, lineup_vs_rhp=lineup)
        with self.assertRaises(plans.PlanError):
            plans.save_day(plan, self.game.day, starter=self.home.starters[2])
        log = self.step(log)
        state = gf.refresh(log).state
        self.assertEqual(state[HOME]["pitcher_slot"], before[HOME]["pitcher_slot"])
        self.assertEqual([b["id"] for b in state[HOME]["lineup"]], [b["id"] for b in before[HOME]["lineup"]])

    def test_a_filed_player_without_a_card_refuses_the_opening_and_is_named(self):
        models.Card.objects.filter(player=self.road.bench[1]).delete()
        models.Card.objects.filter(player=self.home.relievers[0]).update(fatigue=None)
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.open()
        reasons = refused.exception.reasons
        self.assertIn(f"{self.road.bench[1].name} has no card.", reasons)
        self.assertIn(f"{self.home.relievers[0].name}'s card has no fatigue profile.", reasons)
        self.assertFalse(models.GameLog.objects.exists())

    def test_a_capped_planned_batter_is_replaced_by_the_first_legal_bench_player(self):
        capped = self.road.hitters[3]
        gf.counter(capped, plate_appearances_cap=100, plate_appearances=100)
        gf.counter(self.road.bench[0], plate_appearances_cap=50, plate_appearances=50)
        log = self.open()
        lineup = gf.refresh(log).state[AWAY]["lineup"]
        self.assertEqual(lineup[3]["id"], str(self.road.bench[1].id))
        self.assertEqual(lineup[3]["position"], "3B")
        decision = gf.events(log, Event.DECISION)[0]
        self.assertIn(capped.name, decision.text)
        self.assertIn(self.road.bench[0].name, decision.text)

    def test_the_park_is_the_home_teams_venue(self):
        models.Venue.objects.create(
            team=self.home.team, name="Home Park", mlb_team="X", mlb_venue_id="1", mlb_venue_url="u", park_factor=110
        )
        log = self.open()
        state = gf.refresh(log).state
        parks = {p["id"]: p["run_factor"] for p in state["parks"]}
        self.assertEqual(parks[state[HOME]["home_park_id"]], 1.1)
        self.assertEqual(parks[state[AWAY]["home_park_id"]], 1.0, "a team with no venue plays at 1.0")
        neutral = sim_game.matchup(self.play(log))
        models.Venue.objects.filter(team=self.home.team).update(park_factor=100)
        models.GameLog.objects.all().delete()
        models.ScheduleGame.objects.filter(pk=self.game.pk).update(opened_at=None, opening_sheet=None)
        flat = sim_game.matchup(self.play(self.open()))
        self.assertGreater(dict(neutral)["Home run"], dict(flat)["Home run"])


class PlayingTestCase(SimGameTestCase):
    def test_a_game_plays_to_a_final_with_a_box_score_and_the_schedule_marked(self):
        log = gf.play_out(self.open(), self.manager, self.next_seed)
        self.game.refresh_from_db()
        state = log.state
        self.assertEqual(state["status"], "final")
        self.assertEqual((self.game.road_score, self.game.home_score), (state["score"]["away"], state["score"]["home"]))
        self.assertTrue(self.game.is_played)

        pas = gf.events(log, Event.PLATE_APPEARANCE)
        self.assertEqual(len(pas), len(state["results"]))
        self.assertTrue(all(e.seed is not None for e in pas))
        sequences = [e.sequence for e in gf.events(log)]
        self.assertEqual(sequences, list(range(1, len(sequences) + 1)))
        self.assertEqual(gf.events(log)[-1].kind, Event.FINAL)

        box = box_score.box_score(log)
        self.assertTrue(box.final)
        for side in (AWAY, HOME):
            self.assertEqual(box.totals[side]["r"], state["score"][side])
            self.assertEqual(box.batting_totals[side]["r"], state["score"][side])
            self.assertEqual(sum(line.r for line in box.pitching[sim_game.other_side(side)]), state["score"][side])
            line_runs = sum(r for r in box.line[side] if r != "X")
            self.assertEqual(line_runs, state["score"][side])
            self.assertEqual(box.line[side][: len(state["line_score"][side])], state["line_score"][side][: len(box.line[side])])
            self.assertEqual(box.totals[side]["h"], box.batting_totals[side]["h"])
            outs = sum(line.outs for line in box.pitching[side])
            self.assertGreaterEqual(outs, 24)
        self.assertIsNotNone(box.win)
        self.assertIsNotNone(box.loss)

    def test_resuming_after_the_state_is_discarded_rebuilds_it_from_the_log(self):
        log = self.open()
        for _ in range(12):
            log = self.step(log)
        kept = log.state
        models.GameLog.objects.filter(pk=log.pk).update(state=None, state_sequence=0)
        log = gf.refresh(log)
        self.assertIsNone(log.state)
        self.assertEqual(self.play(log).state, kept)
        log = self.step(log)
        self.assertEqual(len(log.state["results"]), 13)
        self.assertEqual(log.state["results"][:12], kept["results"])

    def test_replaying_the_log_gives_the_identical_final(self):
        log = gf.play_out(self.open(), self.manager, self.next_seed)
        self.assertEqual(sim_game.replay(gf.events(log)), log.state)

    def test_a_duplicate_step_plays_nothing(self):
        log = self.open()
        position = self.play(log).sequence
        sim_game.step(log, self.manager, position, seeds=self.next_seed)
        count = models.GameEvent.objects.count()
        pa_total = sum(models.UsageCounter.objects.values_list("plate_appearances", flat=True))
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.step(log, self.manager, position, seeds=self.next_seed)
        self.assertIn("moved on", str(refused.exception))
        self.assertEqual(models.GameEvent.objects.count(), count)
        self.assertEqual(sum(models.UsageCounter.objects.values_list("plate_appearances", flat=True)), pa_total)
        self.assertEqual(len(gf.refresh(log).state["results"]), 1)

    def test_every_plate_appearance_is_counted_in_the_usage_ledger(self):
        log = self.open()
        for _ in range(6):
            log = self.step(log)
        pas = gf.events(log, Event.PLATE_APPEARANCE)
        completed = [e for e in pas if e.payload["result"]["batter_completed"]]
        self.assertEqual(
            sum(models.UsageAppearance.objects.filter(game=self.game).values_list("plate_appearances", flat=True)),
            len(completed),
        )
        starter = models.UsageAppearance.objects.get(game=self.game, player=self.home.starters[0])
        self.assertTrue(starter.started)
        self.assertEqual(starter.batters_faced, sum(1 for e in completed if e.payload["batting"] == AWAY))

    def test_a_removed_pitcher_cannot_re_enter(self):
        log = self.open()
        play = self.step_until(log, lambda p: p.fold.first_pitch and sim_game.fielding_side(p.state) == AWAY)
        starter = self.road.starters[0]
        sim_game.change_pitcher(log, self.manager, AWAY, self.road.relievers[0], play.sequence, seeds=self.next_seed)
        play = self.play(log)
        self.assertEqual(play.state[AWAY]["pitcher_slot"], str(self.road.relievers[0].id))
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.change_pitcher(log, self.manager, AWAY, starter, play.sequence, seeds=self.next_seed)
        self.assertIn("cannot re-enter", str(refused.exception))

    def test_a_human_cannot_bring_in_a_capped_pitcher(self):
        capped = self.road.relievers[0]
        row = gf.counter(capped)
        gf.counter(capped, outs=row.innings_cap_outs)
        log = self.open()
        play = self.step_until(log, lambda p: p.fold.first_pitch and sim_game.fielding_side(p.state) == AWAY)
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.change_pitcher(log, self.manager, AWAY, capped, play.sequence, seeds=self.next_seed)
        self.assertIn("no innings left", str(refused.exception))
        self.assertEqual(self.play(log).state[AWAY]["pitcher_slot"], str(self.road.starters[0].id))

    def test_a_human_cannot_put_a_capped_batter_in_his_lineup(self):
        capped = self.road.bench[0]
        gf.counter(capped, plate_appearances_cap=40, plate_appearances=40)
        log = self.open()
        entries = self.road.lineup()
        entries[3] = {"order": 4, "player": capped, "position": "3B"}
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.change_lineup(log, self.manager, AWAY, entries, self.play(log).sequence, seeds=self.next_seed)
        self.assertIn("all 40 of his plate appearances", str(refused.exception))

    def test_the_visitor_changes_his_lineup_for_this_game_only_before_the_first_pitch(self):
        log = self.open()
        entries = self.road.lineup()
        entries[3] = {"order": 4, "player": self.road.bench[1], "position": "3B"}
        sim_game.change_lineup(log, self.manager, AWAY, entries, self.play(log).sequence, seeds=self.next_seed)
        play = self.play(log)
        self.assertEqual(play.state[AWAY]["lineup"][3]["id"], str(self.road.bench[1].id))
        plan = plans.find_plan(self.road.team, gf.SEASON, 1)
        self.assertNotIn(self.road.bench[1].id, [e["player"] for e in plan.lineup_vs_rhp])
        self.step(log)
        with self.assertRaises(sim_game.GameRefused):
            sim_game.change_lineup(log, self.manager, AWAY, self.road.lineup(), self.play(log).sequence, seeds=self.next_seed)

    def test_a_batter_who_runs_out_mid_game_is_replaced_in_his_slot_before_he_bats_again(self):
        second = self.road.hitters[1]
        gf.counter(second, plate_appearances_cap=1, plate_appearances=0)
        log = self.open()
        self.step_until(log, lambda p: any(e.payload.get("batter") == second.id for e in p.events))
        play = self.step_until(log, lambda p: p.need() is not None and p.need().side == AWAY)
        need = play.need()
        self.assertEqual(need.kind, sim_game.BATTER_NEED)
        self.assertEqual(need.slot, 1)
        self.assertEqual(need.player, second)
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.step(log, self.manager, play.sequence, seeds=self.next_seed)
        self.assertIn(second.name, str(refused.exception))
        replacement = self.road.bench[0]
        sim_game.replace_batter(log, self.manager, AWAY, replacement, play.sequence, seeds=self.next_seed)
        play = self.play(log)
        slot = play.state[AWAY]["lineup"][1]
        self.assertEqual((slot["id"], slot["position"]), (str(replacement.id), "1B"))
        self.assertIn(str(second.id), play.state[AWAY]["unavailable"])
        log = self.step(log)
        self.assertEqual(gf.events(log, Event.PLATE_APPEARANCE)[-1].payload["batter"], replacement.id)

    def test_the_home_computer_replaces_a_batter_who_runs_out_from_its_bench_order(self):
        leadoff = self.home.hitters[1]
        gf.counter(leadoff, plate_appearances_cap=1, plate_appearances=0)
        gf.counter(self.home.bench[0], plate_appearances_cap=5, plate_appearances=5)
        log = self.open()
        self.step_until(log, lambda p: any(e.kind == Event.SUBSTITUTION for e in p.events))
        substitution = gf.events(log, Event.SUBSTITUTION)[0]
        self.assertTrue(substitution.computer)
        self.assertEqual(substitution.side, HOME)
        self.assertEqual(substitution.payload["player"], self.home.bench[1].id)
        self.assertEqual(substitution.payload["replaced"], leadoff.id)
        self.assertIn(self.home.bench[0].name, gf.events(log, Event.DECISION)[-1].text)

    def test_the_home_computer_passes_over_a_capped_reliever(self):
        gf.counter(self.home.starters[0], start_limit_outs=3)
        middle = self.home.swingman
        row = gf.counter(middle)
        gf.counter(middle, outs=usage.season_innings_cap(row))
        log = self.open()
        self.step_until(log, lambda p: any(e.kind == Event.PITCHING_CHANGE for e in p.events))
        change = gf.events(log, Event.PITCHING_CHANGE)[0]
        self.assertTrue(change.computer)
        self.assertEqual(
            change.payload["pitcher"], self.home.relievers[1].id, "setup is next when middle and long is spent"
        )
        decision = gf.events(log, Event.DECISION)[-1]
        self.assertIn(middle.name, decision.text)
        self.assertIn("no innings left", decision.text)

    def test_pitch_around_raises_the_walk_rate_for_that_plate_appearance(self):
        rates = dict(gf.HITTER_RATES)
        raised = sim_game.pitch_around(rates)
        self.assertAlmostEqual(raised["bb"], rates["bb"] * sim_game.PITCH_AROUND_BB_MULT)
        self.assertAlmostEqual(sum(raised.values()), 1.0)
        scale = (1 - raised["bb"]) / (1 - rates["bb"])
        self.assertAlmostEqual(raised["k"], rates["k"] * scale)

        log = self.open()
        play = self.step_until(log, lambda p: p.fold.first_pitch and sim_game.fielding_side(p.state) == AWAY)
        sim_game.step(log, self.manager, play.sequence, call=sim_game.PITCH_AROUND, seeds=self.next_seed)
        pa = gf.events(log, Event.PLATE_APPEARANCE)[-1]
        self.assertTrue(pa.payload["inputs"]["pitch_around"])
        self.assertAlmostEqual(pa.payload["inputs"]["hitter_rates"]["bb"], gf.HITTER_RATES["bb"] * 2)
        self.assertEqual(gf.events(log, Event.CALL)[-1].payload, {"call": sim_game.PITCH_AROUND})

    def test_a_call_belongs_to_the_side_that_makes_it(self):
        log = self.open()
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.step(log, self.manager, self.play(log).sequence, call=sim_game.PITCH_AROUND, seeds=self.next_seed)
        self.assertIn("call to make", str(refused.exception))
        sim_game.step(log, self.manager, self.play(log).sequence, call="bunt", seeds=self.next_seed)
        pa = gf.events(log, Event.PLATE_APPEARANCE)[-1]
        self.assertEqual(pa.payload["inputs"]["call"], "bunt")
        self.assertIn(pa.payload["result"]["outcome"], ("bunt_single", "bunt_sacrifice", "bunt_out"))

    def test_a_side_with_no_legal_pitcher_pauses_until_an_override(self):
        gf.counter(self.home.starters[0], start_limit_outs=3)
        for pitcher in self.home.starters[1:] + self.home.relievers + [self.home.swingman]:
            gf.counter(pitcher, relief_limit_outs=0)
        log = self.open()
        with self.assertLogs("ulmg.usage", level="WARNING") as logged:
            play = self.step_until(log, lambda p: p.fold.pause is not None)
        self.assertIn("has no legal pitcher", logged.output[0])
        self.assertEqual(play.fold.pause["side"], HOME)
        pause = models.UsagePause.objects.get(game=self.game)
        self.assertTrue(pause.is_open)
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.step(log, self.manager, play.sequence, seeds=self.next_seed)
        self.assertIn("paused", str(refused.exception))

        commissioner = models.User.objects.create_superuser(username="commish")
        usage.grant_override(commissioner, self.home.relievers[0], self.game, models.UsageOverride.GAME_INNINGS, "test")
        sim_game.check_pause(log, self.manager, play.sequence, seeds=self.next_seed)
        play = self.play(log)
        self.assertIsNone(play.fold.pause)
        self.assertEqual(play.state[HOME]["pitcher_slot"], str(self.home.relievers[0].id))
        pause.refresh_from_db()
        self.assertFalse(pause.is_open)

    def test_a_roster_move_during_the_game_is_logged_and_the_call_up_can_play(self):
        call_up = models.Player.objects.create(
            name="Call Up", position="P", level="V", team=self.road.team, throws="R", is_ulmg_mlb_roster=False,
            carded_seasons=[gf.CARD_SEASON],
        )
        models.PlayerStatSeason.objects.create(
            player=call_up, season=gf.CARD_SEASON, classification="1-mlb", pitch_stats=dict(gf.plan_fixtures.RELIEVER_STATS)
        )
        models.Card.objects.create(
            player=call_up, season=gf.CARD_SEASON, batters_faced=300,
            pitcher_rates={"k": 0.25, "bb": 0.07, "hbp": 0.01, "h": 0.2, "hr": 0.03}, fatigue=gf.RELIEVER_FATIGUE,
        )
        log = self.open()
        play = self.step_until(log, lambda p: p.fold.first_pitch and sim_game.fielding_side(p.state) == AWAY)
        sim_game.make_roster_move(
            log, self.manager, AWAY, call_up, self.road.starters[4], play.sequence, seeds=self.next_seed
        )
        move = gf.events(log, Event.ROSTER_MOVE)[0]
        self.assertEqual(move.payload["up"], call_up.id)
        self.assertEqual(move.user, self.manager)
        play = self.play(log)
        sim_game.change_pitcher(log, self.manager, AWAY, call_up, play.sequence, seeds=self.next_seed)
        self.assertEqual(self.play(log).state[AWAY]["pitcher_slot"], str(call_up.id))

    def test_a_stale_pitching_change_plays_nothing(self):
        log = self.open()
        play = self.step_until(log, lambda p: p.fold.first_pitch and sim_game.fielding_side(p.state) == AWAY)
        with self.assertRaises(sim_game.GameRefused):
            sim_game.change_pitcher(log, self.manager, AWAY, self.road.relievers[0], play.sequence - 1, seeds=self.next_seed)
        self.assertEqual(self.play(log).sequence, play.sequence)


class QueryCountTestCase(SimGameTestCase):
    # Each action reads the ledger, the rosters' players and their cards once instead of once per
    # check: a plate appearance made 55-64 queries before, 44-49 after.
    STEP_QUERY_LIMIT = 50

    def test_a_plate_appearance_stays_within_its_query_budget(self):
        log = self.step(self.open())
        counts = []
        for _ in range(12):
            play = self.play(log)
            with CaptureQueriesContext(connection) as queries:
                sim_game.step(log, self.manager, play.sequence, seeds=self.next_seed)
            counts.append(len(queries))
            log = gf.refresh(log)
        self.assertEqual(len(log.state["results"]), 13)
        self.assertLessEqual(max(counts), self.STEP_QUERY_LIMIT, msg=f"queries per step: {counts}")


class DecisionsTestCase(SimGameTestCase):
    """Games whose runs are certain: every hitter strikes out except the ones given home-run rates."""

    def setUp(self):
        super().setUp()
        gf.set_rates(self.road.hitters + self.road.bench + self.home.hitters + self.home.bench, gf.STRIKEOUT_RATES)

    def test_win_loss_and_save_in_a_save_situation(self):
        # The home leadoff man homers in the 1st, 4th and 7th: 3-0, and the starter is done after eight.
        gf.set_rates([self.home.hitters[0]], gf.HOME_RUN_RATES)
        log = gf.play_out(self.open(), self.manager, self.next_seed)
        self.assertEqual(log.state["score"], {"away": 0, "home": 3})
        box = box_score.box_score(log)
        self.assertGreater(len(box.pitching[HOME]), 1)
        self.assertGreaterEqual(box.pitching[HOME][0].outs, box_score.STARTER_WIN_OUTS)
        self.assertEqual(box.win, self.home.starters[0])
        self.assertEqual(box.loss, self.road.starters[0])
        finisher = box.pitching[HOME][-1]
        self.assertGreaterEqual(finisher.outs, 3)
        self.assertEqual(box.save, finisher.player)
        self.assertEqual((box.pitching[AWAY][0].r, box.pitching[AWAY][0].er), (3, 3))
        self.assertEqual(box.line[HOME][-1], "X", "home leads after the top of the 9th and does not bat")
        leadoff = box.batting[HOME][0]
        self.assertEqual((leadoff.ab, leadoff.h, leadoff.hr, leadoff.r, leadoff.rbi), (3, 3, 3, 3, 3))

    def test_a_starter_short_of_five_innings_gives_the_win_to_the_most_effective_reliever(self):
        gf.set_rates([self.home.hitters[0]], gf.HOME_RUN_RATES)
        gf.counter(self.home.starters[0], start_limit_outs=6)
        log = gf.play_out(self.open(), self.manager, self.next_seed)
        box = box_score.box_score(log)
        starter = box.pitching[HOME][0]
        self.assertEqual(starter.outs, 6)
        relievers = box.pitching[HOME][1:]
        lead_outs = {line.player.id: 0 for line in relievers}
        for event in gf.events(log, Event.PLATE_APPEARANCE):
            before = event.payload["before"]["score"]
            pitcher = event.payload["pitcher"]
            if event.payload["batting"] == AWAY and before["home"] > before["away"] and pitcher in lead_outs:
                lead_outs[pitcher] += event.payload["result"]["change"]["outs_added"]
        best = max(lead_outs.values())
        expected = next(line.player for line in relievers if lead_outs[line.player.id] == best)
        self.assertEqual(box.win, expected)
        self.assertNotEqual(box.win, starter.player)

    def test_the_placed_extra_inning_runner_scores_an_unearned_run(self):
        gf.set_rates([self.road.bench[0]], gf.HOME_RUN_RATES)
        models.Card.objects.filter(player=self.road.bench[0]).update(defense={"C": 0.0})
        log = self.open()
        play = self.step_until(log, lambda p: p.state["inning"] == 10)
        self.assertEqual(play.state["half"], "top")
        ghost = int(play.state["bases"]["second"])
        leadoff = models.Player.objects.get(pk=int(sim_game.current_batter_id(play.state)))
        gf.counter(leadoff, plate_appearances_cap=1, plate_appearances=1)
        sim_game.replace_batter(log, self.manager, AWAY, self.road.bench[0], play.sequence, seeds=self.next_seed)
        log = gf.play_out(log, self.manager, self.next_seed)
        self.assertEqual(log.state["score"], {"away": 2, "home": 0})
        box = box_score.box_score(log)
        charged = [line for line in box.pitching[HOME] if line.r]
        self.assertEqual(len(charged), 1)
        self.assertEqual((charged[0].r, charged[0].er), (2, 1))
        self.assertEqual(box.loss, charged[0].player)
        ghost_line = next(line for line in box.batting[AWAY] if line.player.id == ghost)
        self.assertEqual(ghost_line.r, 1)
        completed = sum(
            1
            for e in gf.events(log, Event.PLATE_APPEARANCE)
            if e.payload["batter"] == ghost and e.payload["result"]["batter_completed"]
        )
        recorded = models.UsageAppearance.objects.get(game=self.game, player_id=ghost).plate_appearances
        self.assertEqual(recorded, completed, "being placed on second used no plate appearance")


class SeatsTestCase(SimGameTestCase):
    def test_a_tester_plays_the_home_seat_against_the_visitors_computer(self):
        log = self.open(self.tester, seats=(HOME,))
        seats = {e.side: e.user for e in gf.events(log, Event.SEAT)}
        self.assertEqual(seats, {AWAY: None, HOME: self.tester})
        self.step(log, self.tester)
        pa = gf.events(log, Event.PLATE_APPEARANCE)[0]
        self.assertEqual(pa.user, self.tester)
        self.assertIsNone(pa.payload["inputs"]["call"], "the visitors' computer makes its own offensive call")
        sim_game.step(log, self.tester, self.play(log).sequence, call=sim_game.PITCH_AROUND, seeds=self.next_seed)
        with self.assertRaises(sim_game.GameRefused):
            sim_game.step(log, self.tester, self.play(log).sequence, call="bunt", seeds=self.next_seed)
        sim_game.change_pitcher(log, self.tester, HOME, self.home.relievers[1], self.play(log).sequence, seeds=self.next_seed)
        change = gf.events(log, Event.PITCHING_CHANGE)[-1]
        self.assertEqual((change.user, change.computer, change.side), (self.tester, False, HOME))
        with self.assertRaises(sim_game.GameRefused):
            sim_game.change_pitcher(
                log, self.manager, HOME, self.home.relievers[0], self.play(log).sequence, seeds=self.next_seed
            )

    def test_a_tester_plays_both_seats_through_a_final(self):
        log = self.open(self.tester, seats=(AWAY, HOME))
        log = gf.play_out(log, self.tester, self.next_seed)
        self.assertEqual(log.state["status"], "final")
        changes = gf.events(log, Event.PITCHING_CHANGE)
        self.assertTrue(changes)
        self.assertTrue(all(not e.computer and e.user == self.tester for e in changes))
        self.assertFalse(gf.events(log, Event.DECISION), "with both seats held the computer decides nothing")
        self.assertEqual({e.user for e in gf.events(log, Event.PLATE_APPEARANCE)}, {self.tester})
        self.game.refresh_from_db()
        self.assertTrue(self.game.is_played)

    def test_a_manager_is_refused_the_home_seat(self):
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.open(self.manager, seats=(HOME,))
        self.assertIn("visiting side", str(refused.exception))
        with self.assertRaises(sim_game.GameRefused):
            self.open(self.manager, seats=(AWAY, HOME))
        self.assertFalse(models.GameLog.objects.exists())
        log = self.open(self.manager, seats=(AWAY,))
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.take_seat(log, self.manager, HOME, self.play(log).sequence, seeds=self.next_seed)
        self.assertIn("visiting side", str(refused.exception))

    def test_a_manager_is_refused_another_teams_game(self):
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.open(self.other_manager, seats=(AWAY,))
        self.assertIn(f"Only {self.road.team.abbreviation}'s manager", str(refused.exception))
        self.assertEqual(sim_game.open_seat_choices(self.other_manager, self.game), [])

    def test_a_manager_opens_only_his_next_unplayed_road_game(self):
        later = (
            models.ScheduleGame.objects.filter(series__road_team=self.road.team, series__slot__season=gf.SEASON)
            .exclude(pk=self.game.pk)
            .order_by("day")
            .first()
        )
        self.assertEqual(sim_game.open_seat_choices(self.manager, later), [])
        self.assertEqual(sim_game.open_seat_choices(self.manager, self.game), [(AWAY,)])
        self.assertEqual(len(sim_game.open_seat_choices(self.tester, later)), 3)

    def test_the_log_names_the_user_in_each_seat_as_seats_change(self):
        log = self.open(self.tester, seats=(HOME,))
        sim_game.take_seat(log, self.manager, AWAY, self.play(log).sequence, seeds=self.next_seed)
        sim_game.leave_seat(log, self.tester, HOME, self.play(log).sequence, seeds=self.next_seed)
        sim_game.take_seat(log, self.tester, HOME, self.play(log).sequence, seeds=self.next_seed)
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.take_seat(log, self.tester, AWAY, self.play(log).sequence, seeds=self.next_seed)
        self.assertIn("Someone else holds", str(refused.exception))
        seat_events = [(e.side, e.user) for e in gf.events(log, Event.SEAT)]
        self.assertEqual(
            seat_events,
            [(AWAY, None), (HOME, self.tester), (AWAY, self.manager), (HOME, None), (HOME, self.tester)],
        )
        self.assertEqual(self.play(log).fold.seats, {AWAY: self.manager.id, HOME: self.tester.id})
        self.assertIn(self.manager.username, gf.events(log, Event.SEAT)[2].text)
