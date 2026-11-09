# ABOUTME: Tests the computer manager in real sim games: bullpen roles, the starter hook, and steal calls, home and away.
# ABOUTME: Plays against the real engine with hitters who can only strike out, homer or single, so each situation is certain.

import random

from tests import game_fixtures as gf
from tests.test_sim_game import SimGameTestCase
from ulmg import computer_manager, models, sim_game

Event = models.GameEvent
AWAY, HOME = sim_game.AWAY, sim_game.HOME

# A fatigue profile so deep that only the per-game limit and the hook's runs can end an outing.
TIRELESS = dict(gf.STARTER_FATIGUE, season_pitches_per_appearance=400.0, career_pitches_per_appearance=400.0)
# A per-game limit no test reaches, for tests about the hook's other lines.
NO_LIMIT_OUTS = 60
SINGLE_RATES = dict(gf.STRIKEOUT_RATES, k=0.0, single=1.0)


def steal_stays(log, side):
    """
    The side's stays on first that reach a steal situation, worked out from
    the plate appearances alone: a stay is the run of the side's plate
    appearances that begin with the same runner on first.
    """
    stays = []
    runner = None
    for event in gf.events(log, Event.PLATE_APPEARANCE):
        before = event.payload["before"]
        on_first = before["bases"].get("first") if event.payload["batting"] == side else None
        if on_first != runner:
            runner = on_first
            counted = False
        if runner and not counted and computer_manager.is_steal_situation(before["bases"], before["outs"]):
            stays.append((int(runner), before["inning"]))
            counted = True
    return stays


def changes(log, side):
    return [e for e in gf.events(log, Event.PITCHING_CHANGE) if e.side == side]


def decision_before(log, event):
    return [e for e in gf.events(log, Event.DECISION) if e.sequence < event.sequence][-1]


def inning_of(log, event):
    """The inning a pitching change came in: the inning of the next plate appearance, or of the game now."""
    later = [e for e in gf.events(log, Event.PLATE_APPEARANCE) if e.sequence > event.sequence]
    if later:
        return later[0].payload["before"]["inning"]
    return gf.refresh(log).state["inning"]


class ComputerGameTestCase(SimGameTestCase):
    def setUp(self):
        super().setUp()
        everyone = self.road.hitters + self.road.bench + self.home.hitters + self.home.bench
        gf.set_rates(everyone, gf.STRIKEOUT_RATES)

    def tireless(self, *pitchers):
        for pitcher in pitchers:
            models.Card.objects.filter(player=pitcher).update(fatigue=TIRELESS)

    def until_changes(self, log, side, count, user=None):
        """Step until the side has made count pitching changes."""
        self.step_until(log, lambda p: len([e for e in p.events if e.kind == Event.PITCHING_CHANGE and e.side == side]) >= count, user=user)
        return changes(log, side)


class BullpenRolesTestCase(ComputerGameTestCase):
    def setUp(self):
        super().setUp()
        self.tireless(*self.home.starters, *self.home.relievers, self.home.swingman)
        # The home leadoff man homers in the 1st, 4th and 7th: 3-0 from the 7th on.
        gf.set_rates([self.home.hitters[0]], gf.HOME_RUN_RATES)

    def test_the_closer_comes_in_for_a_save_in_the_ninth(self):
        gf.counter(self.home.starters[0], start_limit_outs=24)
        log = self.open()
        change = self.until_changes(log, HOME, 1)[0]
        self.assertEqual(change.payload["pitcher"], self.home.relievers[0].id)
        self.assertEqual(inning_of(log, change), 9)
        decision = decision_before(log, change)
        self.assertTrue(decision.computer)
        self.assertEqual(decision.side, HOME)
        self.assertEqual(decision.payload["role"], computer_manager.CLOSER)
        self.assertEqual(decision.payload["group"], computer_manager.CLOSER)
        self.assertIn("save situation", decision.text)

    def test_a_capped_closer_is_skipped_for_setup(self):
        gf.counter(self.home.starters[0], start_limit_outs=24)
        closer = self.home.relievers[0]
        row = gf.counter(closer)
        gf.counter(closer, outs=row.innings_cap_outs)
        log = self.open()
        change = self.until_changes(log, HOME, 1)[0]
        self.assertEqual(change.payload["pitcher"], self.home.relievers[1].id)
        decision = decision_before(log, change)
        self.assertEqual(decision.payload["role"], computer_manager.CLOSER)
        self.assertEqual(decision.payload["group"], computer_manager.SETUP_R)
        self.assertEqual(decision.payload["skipped"][0][0], closer.id)
        self.assertIn("no innings left", decision.text)

    def test_a_tired_closer_is_skipped(self):
        gf.counter(self.home.starters[0], start_limit_outs=24)
        closer = self.home.relievers[0]
        next_game = models.ScheduleGame.objects.get(series=self.game.series, day=self.game.day + 1)
        models.UsageAppearance.objects.create(player=closer, game=next_game, batters_faced=9, pitches=40, outs=6)
        log = self.open()
        change = self.until_changes(log, HOME, 1)[0]
        self.assertEqual(change.payload["pitcher"], self.home.relievers[1].id)
        decision = decision_before(log, change)
        self.assertEqual(decision.payload["skipped"][0][0], closer.id)
        self.assertIn("40 pitches", decision.text)

    def test_short_relief_takes_the_seventh_setup_the_eighth_and_the_closer_the_ninth(self):
        short = self.home.swingman
        setup = self.home.relievers[1]
        self.home.file(sirp=[short], mirp=[], setup_r=[setup])
        gf.counter(self.home.starters[0], start_limit_outs=18)
        gf.counter(short, relief_limit_outs=9)
        gf.counter(setup, relief_limit_outs=9)
        log = self.open()
        first, second, third = self.until_changes(log, HOME, 3)
        self.assertEqual(first.payload["pitcher"], short.id)
        self.assertEqual(inning_of(log, first), 7)
        self.assertEqual(decision_before(log, first).payload["role"], computer_manager.SIRP)
        self.assertEqual(second.payload["pitcher"], setup.id)
        self.assertEqual(inning_of(log, second), 8)
        self.assertEqual(decision_before(log, second).payload["role"], computer_manager.SETUP_R)
        self.assertEqual(third.payload["pitcher"], self.home.relievers[0].id)
        self.assertEqual(inning_of(log, third), 9)
        self.assertEqual(decision_before(log, third).payload["role"], computer_manager.CLOSER)
        self.assertEqual(models.UsageAppearance.objects.get(game=self.game, player=short).outs, 3)
        self.assertEqual(models.UsageAppearance.objects.get(game=self.game, player=setup).outs, 3)

    def test_setup_comes_in_late_in_a_tie(self):
        gf.set_rates([self.home.hitters[0]], gf.STRIKEOUT_RATES)
        gf.counter(self.home.starters[0], start_limit_outs=21)
        log = self.open()
        change = self.until_changes(log, HOME, 1)[0]
        self.assertEqual(change.payload["pitcher"], self.home.relievers[1].id)
        self.assertEqual(inning_of(log, change), 8)
        self.assertEqual(self.play(log).state["score"], {"away": 0, "home": 0})

    def test_middle_and_long_after_an_early_knockout(self):
        gf.counter(self.home.starters[0], start_limit_outs=6)
        log = self.open()
        change = self.until_changes(log, HOME, 1)[0]
        self.assertEqual(change.payload["pitcher"], self.home.swingman.id)
        self.assertEqual(inning_of(log, change), 3)
        self.assertEqual(decision_before(log, change).payload["role"], computer_manager.MIRP)

    def test_middle_and_long_with_a_big_lead_in_the_seventh(self):
        gf.set_rates(self.home.hitters[:2], gf.HOME_RUN_RATES)
        gf.counter(self.home.starters[0], start_limit_outs=18)
        log = self.open()
        change = self.until_changes(log, HOME, 1)[0]
        self.assertEqual(inning_of(log, change), 7)
        self.assertGreater(self.play(log).state["score"]["home"], 3)
        self.assertEqual(change.payload["pitcher"], self.home.swingman.id)

    def test_with_middle_and_long_spent_setup_is_next_then_the_closer(self):
        gf.counter(self.home.starters[0], start_limit_outs=6)
        row = gf.counter(self.home.swingman)
        gf.counter(self.home.swingman, outs=row.innings_cap_outs)
        gf.counter(self.home.relievers[1], relief_limit_outs=3)
        log = self.open()
        first, second = self.until_changes(log, HOME, 2)
        self.assertEqual(first.payload["pitcher"], self.home.relievers[1].id)
        self.assertEqual(decision_before(log, first).payload["group"], computer_manager.SETUP_R)
        self.assertEqual(second.payload["pitcher"], self.home.relievers[0].id)
        self.assertEqual(decision_before(log, second).payload["group"], computer_manager.CLOSER)

    def test_the_visitors_computer_uses_the_visitors_roles(self):
        self.tireless(*self.road.starters, *self.road.relievers, self.road.swingman)
        gf.set_rates([self.home.hitters[0]], gf.STRIKEOUT_RATES)
        gf.counter(self.road.starters[0], start_limit_outs=18)
        log = self.open(self.tester, seats=(HOME,))
        change = self.until_changes(log, AWAY, 1, user=self.tester)[0]
        self.assertEqual(change.payload["pitcher"], self.road.swingman.id)
        self.assertTrue(change.computer)
        self.assertEqual(inning_of(log, change), 7)
        decision = decision_before(log, change)
        self.assertEqual(decision.payload["role"], computer_manager.SIRP)
        self.assertEqual(decision.payload["group"], computer_manager.MIRP)
        self.assertEqual(decision_before(log, change).side, AWAY)

    def test_the_eighth_uses_setup_against_the_batters_hand(self):
        lefty = self.home.relievers[1]
        lefty.throws = "L"
        lefty.save()
        self.home.file(setup_l=[lefty], setup_r=[])
        for hitter in self.road.hitters:
            hitter.bats = "L"
            hitter.save()
        gf.counter(self.home.starters[0], start_limit_outs=21)
        log = self.open()
        change = self.until_changes(log, HOME, 1)[0]
        self.assertEqual(inning_of(log, change), 8)
        self.assertEqual(change.payload["pitcher"], lefty.id)
        decision = decision_before(log, change)
        self.assertEqual(decision.payload["role"], computer_manager.SETUP_L)
        self.assertEqual(decision.payload["group"], computer_manager.SETUP_L)

    def test_an_eighth_closer_comes_in_for_the_eighth_of_a_tie(self):
        gf.set_rates([self.home.hitters[0]], gf.STRIKEOUT_RATES)
        self.home.file(closer_usage=models.HalfPlan.EIGHTH)
        gf.counter(self.home.starters[0], start_limit_outs=21)
        log = self.open()
        change = self.until_changes(log, HOME, 1)[0]
        self.assertEqual(change.payload["pitcher"], self.home.relievers[0].id)
        self.assertEqual(inning_of(log, change), 8)
        self.assertEqual(decision_before(log, change).payload["role"], computer_manager.CLOSER)

    def test_early_relief_brings_short_relief_in_the_sixth(self):
        gf.set_rates([self.home.hitters[0]], gf.STRIKEOUT_RATES)
        short = self.home.swingman
        self.home.file(relief_usage=models.HalfPlan.EARLY, sirp=[short], mirp=[])
        gf.counter(self.home.starters[0], start_limit_outs=15)
        log = self.open()
        change = self.until_changes(log, HOME, 1)[0]
        self.assertEqual(change.payload["pitcher"], short.id)
        self.assertEqual(inning_of(log, change), 6)
        self.assertEqual(decision_before(log, change).payload["role"], computer_manager.SIRP)

    def test_a_leverage_closer_comes_in_before_the_seventh_once_someone_reaches(self):
        gf.set_rates([self.home.hitters[0]], gf.STRIKEOUT_RATES)
        gf.set_rates([self.road.hitters[8]], SINGLE_RATES)
        self.home.file(closer_usage=models.HalfPlan.LEVERAGE)
        gf.counter(self.home.starters[0], start_limit_outs=15)
        log = self.open()
        changes = self.until_changes(log, HOME, 2)
        self.assertEqual(inning_of(log, changes[0]), 6)
        self.assertEqual(decision_before(log, changes[0]).payload["role"], computer_manager.MIRP)
        self.assertEqual(changes[1].payload["pitcher"], self.home.relievers[0].id)
        self.assertEqual(inning_of(log, changes[1]), 6)
        self.assertEqual(decision_before(log, changes[1]).payload["role"], computer_manager.CLOSER)


class BenchUsageTestCase(ComputerGameTestCase):
    def _subs(self, play, role):
        return [
            event for event in play.events
            if event.kind == Event.SUBSTITUTION and event.computer and event.payload.get("role") == role
        ]

    def test_stand_leaves_a_weak_batter_in(self):
        models.Card.objects.filter(player=self.home.hitters[0]).update(wrc_plus=70)
        models.Card.objects.filter(player=self.home.bench[0]).update(wrc_plus=140)
        log = self.open()
        play = self.step_until(log, lambda p: p.state["inning"] >= 8)
        self.assertEqual(self._subs(play, sim_game.PINCH_HITTER), [])

    def test_pinch_sends_up_a_better_bat_from_the_seventh(self):
        self.home.file(bench_usage=models.HalfPlan.PINCH)
        models.Card.objects.filter(player=self.home.hitters[0]).update(wrc_plus=70)
        models.Card.objects.filter(player=self.home.bench[0]).update(wrc_plus=110)
        log = self.open()
        play = self.step_until(log, lambda p: self._subs(p, sim_game.PINCH_HITTER))
        sub = self._subs(play, sim_game.PINCH_HITTER)[0]
        self.assertEqual(sub.payload["player"], self.home.bench[0].id)
        self.assertEqual(sub.payload["replaced"], self.home.hitters[0].id)
        decision = decision_before(log, sub)
        self.assertEqual(decision.payload["need"], "pinch_hit")
        self.assertGreaterEqual(decision.payload["inning"], 7)

    def test_glove_replaces_a_fielder_once_the_side_leads_from_the_seventh(self):
        self.home.file(bench_usage=models.HalfPlan.GLOVE)
        gf.set_rates([self.home.hitters[0]], gf.HOME_RUN_RATES)
        models.Card.objects.filter(player=self.home.hitters[1]).update(defense={"1B": -8.0})
        models.Card.objects.filter(player=self.home.bench[0]).update(defense={"1B": 6.0}, wrc_plus=100)
        log = self.open()
        play = self.step_until(log, lambda p: self._subs(p, sim_game.DEFENSE))
        sub = self._subs(play, sim_game.DEFENSE)[0]
        self.assertEqual(sub.payload["player"], self.home.bench[0].id)
        self.assertEqual(sub.payload["position"], "1B")
        decision = decision_before(log, sub)
        self.assertEqual(decision.payload["need"], "glove")
        self.assertGreaterEqual(decision.payload["inning"], 7)


class StarterHookTestCase(ComputerGameTestCase):
    def setUp(self):
        super().setUp()
        self.tireless(*self.home.relievers, self.home.swingman)

    def file_hook(self, hook):
        self.home.file(half=1, starter_hook=hook)
        gf.counter(self.home.starters[0], start_limit_outs=NO_LIMIT_OUTS)

    def test_each_hook_pulls_the_starter_at_its_runs_allowed(self):
        for hook, runs in computer_manager.HOOK_RUNS.items():
            with self.subTest(hook=hook):
                self.reset_game()
                self.file_hook(hook)
                self.tireless(self.home.starters[0])
                # One more home run hitter than the hook allows: he is pulled before the last.
                gf.set_rates(self.road.hitters, gf.STRIKEOUT_RATES)
                gf.set_rates(self.road.hitters[: runs + 1], gf.HOME_RUN_RATES)
                log = self.open()
                change = self.until_changes(log, HOME, 1)[0]
                self.assertEqual(self.play(log).state["score"]["away"], runs)
                self.assertEqual(inning_of(log, change), 1)
                decision = decision_before(log, change)
                self.assertEqual(decision.payload["need"], "hook")
                self.assertEqual(decision.payload["hook"], hook)
                self.assertIn(f"allowed {runs} runs", decision.text)

    def test_quick_and_normal_hooks_pull_at_their_share_of_the_fatigue_ceiling(self):
        for hook in ("quick", "normal"):
            with self.subTest(hook=hook):
                self.reset_game()
                self.file_hook(hook)
                share = computer_manager.HOOK_CEILING_SHARE[hook]
                starter = str(self.home.starters[0].id)
                log = self.open()
                shares = []

                def pulled(play):
                    if any(e.kind == Event.PITCHING_CHANGE and e.side == HOME for e in play.events):
                        return True
                    fatigue = play.state[HOME]["fatigue"][starter]
                    shares.append(fatigue["effort"] / fatigue["ceiling"])
                    return False

                play = self.step_until(log, pulled)
                fatigue = play.state[HOME]["fatigue"][starter]
                self.assertGreaterEqual(fatigue["effort"] / fatigue["ceiling"], share)
                self.assertLess(fatigue["effort"], fatigue["ceiling"], "pulled before the engine's line")
                self.assertTrue(all(s < share for s in shares), "not pulled any sooner")
                decision = decision_before(log, changes(log, HOME)[0])
                self.assertEqual(decision.payload["need"], "hook")
                self.assertIn("fatigue ceiling", decision.text)

    def test_a_slow_hook_leaves_the_starter_in_to_the_engines_fatigue_line(self):
        self.file_hook("slow")
        log = self.open()
        change = self.until_changes(log, HOME, 1)[0]
        fatigue = self.play(log).state[HOME]["fatigue"][str(self.home.starters[0].id)]
        self.assertGreaterEqual(fatigue["effort"], fatigue["ceiling"])
        decision = decision_before(log, change)
        self.assertEqual(decision.payload["need"], sim_game.PITCHER_NEED)
        self.assertIn("mound is empty", decision.text)

    def test_the_per_game_limit_comes_first_under_any_hook(self):
        self.file_hook("slow")
        self.tireless(self.home.starters[0])
        gf.counter(self.home.starters[0], start_limit_outs=12)
        log = self.open()
        change = self.until_changes(log, HOME, 1)[0]
        self.assertEqual(inning_of(log, change), 5)
        self.assertIn("limit", decision_before(log, change).text)

    def test_a_hook_with_no_available_arm_leaves_the_starter_in_and_says_so_once(self):
        self.file_hook("quick")
        self.tireless(self.home.starters[0])
        gf.set_rates(self.road.hitters[:6], gf.HOME_RUN_RATES)
        for pitcher in [*self.home.relievers, self.home.swingman, *self.home.starters[1:]]:
            gf.counter(pitcher, relief_limit_outs=0)
        log = self.open()
        self.step_until(log, lambda p: p.state["outs"] == 1)
        self.assertFalse(changes(log, HOME))
        self.assertEqual(self.play(log).state[HOME]["pitcher_slot"], str(self.home.starters[0].id))
        stays = [e for e in gf.events(log, Event.DECISION) if e.payload.get("need") == "hook"]
        self.assertEqual(len(stays), 1)
        self.assertIsNone(stays[0].payload["chose"])
        self.assertIn("stays in", stays[0].text)
        self.assertIsNone(self.play(log).fold.pause)

    def test_a_human_seat_is_never_hooked(self):
        self.file_hook("quick")
        self.tireless(self.home.starters[0])
        gf.set_rates(self.road.hitters[:6], gf.HOME_RUN_RATES)
        log = self.open(self.tester, seats=(AWAY, HOME))
        self.step_until(log, lambda p: p.state["outs"] == 1, user=self.tester)
        self.assertFalse(changes(log, HOME))
        self.assertFalse(gf.events(log, Event.DECISION))

    def reset_game(self):
        models.GameLog.objects.all().delete()
        models.UsageAppearance.objects.all().delete()
        models.UsageCounter.objects.all().delete()
        models.ScheduleGame.objects.filter(pk=self.game.pk).update(opened_at=None, opening_sheet=None)
        self.next_seed = gf.seeds()


class StealTestCase(ComputerGameTestCase):
    def setUp(self):
        super().setUp()
        # The home leadoff man singles; the next man up bats with him on first and nobody out.
        gf.set_rates([self.home.hitters[0]], SINGLE_RATES)

    def steal_decisions(self, log):
        return [e for e in gf.events(log, Event.DECISION) if e.payload.get("need") == "steal"]

    def bottom_of_the_first(self, log):
        return self.step_until(log, lambda p: p.state["half"] == "bottom" and p.state["outs"] == 0 and p.state["bases"].get("first"))

    def test_the_home_computer_steals_with_an_attempt_rate_of_one(self):
        models.Card.objects.filter(player=self.home.hitters[0]).update(steal_attempt_rate=1.0)
        log = self.open()
        self.bottom_of_the_first(log)
        log = self.step(log)
        decision = self.steal_decisions(log)[0]
        self.assertTrue(decision.computer)
        self.assertEqual(decision.side, HOME)
        self.assertTrue(decision.payload["called"])
        self.assertEqual(decision.payload["runner"], self.home.hitters[0].id)
        call = gf.events(log, Event.CALL)[-1]
        self.assertEqual((call.side, call.computer, call.payload["call"]), (HOME, True, "steal"))
        pa = gf.events(log, Event.PLATE_APPEARANCE)[-1]
        self.assertEqual(pa.payload["inputs"]["call"], "steal")
        self.assertGreater(pa.sequence, call.sequence)

    def test_the_home_computer_holds_the_runner_with_an_attempt_rate_of_zero(self):
        models.Card.objects.filter(player=self.home.hitters[0]).update(steal_attempt_rate=0.0)
        log = self.open()
        self.bottom_of_the_first(log)
        log = self.step(log)
        decision = self.steal_decisions(log)[0]
        self.assertFalse(decision.payload["called"])
        self.assertIn("holds", decision.text)
        self.assertFalse(gf.events(log, Event.CALL))
        self.assertIsNone(gf.events(log, Event.PLATE_APPEARANCE)[-1].payload["inputs"]["call"])

    def test_the_steal_call_is_a_logged_draw_against_the_attempt_rate(self):
        models.Card.objects.filter(player=self.home.hitters[0]).update(steal_attempt_rate=0.5)
        gf.set_rates(self.home.hitters[1:], SINGLE_RATES)
        gf.set_rates(self.home.hitters[2:], gf.STRIKEOUT_RATES)
        log = self.open()
        self.bottom_of_the_first(log)
        log = self.step(log)
        decision = self.steal_decisions(log)[0]
        self.assertEqual(decision.payload["rate"], 0.5)
        self.assertEqual(decision.payload["draw"], random.Random(decision.seed).random())
        self.assertEqual(decision.payload["called"], decision.payload["draw"] < 0.5)
        pa = gf.events(log, Event.PLATE_APPEARANCE)[-1]
        self.assertEqual(pa.payload["inputs"]["call"], "steal" if decision.payload["called"] else None)

    def test_a_runner_who_stays_on_first_is_rolled_for_once_and_again_when_he_reaches_first_later(self):
        # He singles in the 1st and holds while the next two strike out; he singles with two out in
        # the 3rd (no steal situation); he singles with one out in the 6th and holds again.
        leadoff = self.home.hitters[0]
        models.Card.objects.filter(player=leadoff).update(steal_attempt_rate=0.0)
        log = self.open()
        self.step_until(log, lambda p: p.state["inning"] == 2 and p.state["half"] == "top")
        rolls = self.steal_decisions(log)
        self.assertEqual([(e.payload["runner"], e.payload["called"]) for e in rolls], [(leadoff.id, False)])
        held = [
            e
            for e in gf.events(log, Event.PLATE_APPEARANCE)
            if e.payload["batting"] == HOME and e.payload["before"]["bases"].get("first") == str(leadoff.id)
            and computer_manager.is_steal_situation(e.payload["before"]["bases"], e.payload["before"]["outs"])
        ]
        self.assertEqual(len(held), 2, "two plate appearances in a steal situation during one stay on first")

        log = gf.refresh(self.step_until(log, lambda p: p.state["inning"] == 7).log)
        rolls = self.steal_decisions(log)
        self.assertEqual(len(rolls), 2)
        self.assertEqual([e.payload["runner"] for e in rolls], [leadoff.id, leadoff.id])
        self.assertEqual(steal_stays(log, HOME), [(leadoff.id, 1), (leadoff.id, 6)])
        self.assertEqual(sim_game.replay(gf.events(log)), gf.refresh(log).state)

    def test_the_visitors_computer_steals_too(self):
        gf.set_rates([self.road.hitters[0]], SINGLE_RATES)
        models.Card.objects.filter(player=self.road.hitters[0]).update(steal_attempt_rate=1.0)
        log = self.open(self.tester, seats=(HOME,))
        self.step(log, self.tester)
        log = self.step(log, self.tester)
        decision = self.steal_decisions(log)[0]
        self.assertEqual(decision.side, AWAY)
        self.assertEqual(gf.events(log, Event.PLATE_APPEARANCE)[-1].payload["inputs"]["call"], "steal")

    def test_a_human_batting_side_is_never_given_a_computer_steal(self):
        gf.set_rates([self.road.hitters[0]], SINGLE_RATES)
        models.Card.objects.filter(player=self.road.hitters[0]).update(steal_attempt_rate=1.0)
        log = self.open()
        self.step(log)
        log = self.step(log)
        self.assertFalse(self.steal_decisions(log))
        self.assertEqual(gf.events(log, Event.PLATE_APPEARANCE)[-1].payload["inputs"]["call"], sim_game.NO_CALL)


class NoIntentionalWalkTestCase(ComputerGameTestCase):
    def test_the_computer_never_calls_an_intentional_walk_and_the_game_replays(self):
        everyone = self.road.hitters + self.road.bench + self.home.hitters + self.home.bench
        gf.set_rates(everyone, gf.HITTER_RATES)
        for hitter in everyone:
            models.Card.objects.filter(player=hitter).update(steal_attempt_rate=0.3)
        log = gf.play_out(self.open(), self.manager, self.next_seed)
        self.assertEqual(log.state["status"], "final")
        outcomes = {e.payload["result"]["outcome"] for e in gf.events(log, Event.PLATE_APPEARANCE)}
        self.assertNotIn("intentional_walk", outcomes)
        computer_calls = [e for e in gf.events(log, Event.CALL) if e.computer]
        self.assertTrue(all(e.payload["call"] == "steal" for e in computer_calls))
        self.assertTrue(computer_calls, "a .300 attempt rate steals at least once in a game")
        self.assertEqual(sim_game.replay(gf.events(log)), log.state)

        # One logged steal decision for each home stay on first that reaches a steal situation, and no others.
        steals = [e for e in gf.events(log, Event.DECISION) if e.payload.get("need") == "steal"]
        self.assertEqual(len(steals), len(steal_stays(log, HOME)))
        self.assertTrue(all(e.side == HOME for e in steals))
        self.assertEqual(len(computer_calls), sum(1 for e in steals if e.payload["called"]))
