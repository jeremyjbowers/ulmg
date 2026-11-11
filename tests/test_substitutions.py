# ABOUTME: Tests pinch hitters, pinch runners, defensive replacements and position changes in a sim game against the real engine.
# ABOUTME: Covers the DH and catcher rules, re-entry, usage and game-roster checks, the box score notation, the page and replay from the log.

from tests import game_fixtures as gf
from tests import plan_fixtures
from tests.test_sim_game import SimGameTestCase
from ulmg import box_score, models, sim_game

Event = models.GameEvent
AWAY, HOME = sim_game.AWAY, sim_game.HOME

CATCHER_SLOT = 0
FIRST_BASE_SLOT = 1
THIRD_BASE_SLOT = 3
DH_SLOT = 8


class SubstitutionTestCase(SimGameTestCase):
    def sequence(self, log):
        return self.play(log).sequence

    def batting_with(self, log, side, slot=None, runner=False, user=None):
        """Step until the side bats with no need open: the given slot due up, or a runner of his on base."""

        def ready(play):
            if not play.fold.first_pitch or sim_game.batting_side(play.state) != side or play.need() is not None:
                return False
            if runner:
                return any(play.state["bases"].get(base) for base in ("first", "second", "third"))
            return slot is None or play.state[side]["batter_index"] == slot

        return self.step_until(log, ready, user=user)

    def fielding(self, log, side, user=None):
        """Step until the side is in the field with no need but, perhaps, its pending positions."""

        def ready(play):
            need = play.need()
            return (
                play.fold.first_pitch
                and sim_game.fielding_side(play.state) == side
                and (need is None or need.kind == sim_game.POSITION_NEED)
            )

        return self.step_until(log, ready, user=user)

    def pinch_hit(self, log, player, side=AWAY, user=None):
        sim_game.pinch_hit(log, user or self.manager, side, player, self.sequence(log), seeds=self.next_seed)
        return self.play(log)

    def positions(self, log, positions, side=AWAY, user=None):
        sim_game.set_positions(log, user or self.manager, side, positions, self.sequence(log), seeds=self.next_seed)
        return self.play(log)

    def line_for(self, log, side, player):
        return next(line for line in box_score.box_score(gf.refresh(log)).batting[side] if line.player == player)


class PinchHitterTestCase(SubstitutionTestCase):
    def test_a_pinch_hitter_bats_in_the_slot_and_must_be_given_a_position_in_the_field(self):
        log = self.open()
        play = self.batting_with(log, AWAY, slot=FIRST_BASE_SLOT)
        replaced = self.road.hitters[FIRST_BASE_SLOT]
        bat = self.road.bench[0]
        play = self.pinch_hit(log, bat)
        self.assertEqual(play.state[AWAY]["lineup"][FIRST_BASE_SLOT]["id"], str(bat.id))
        self.assertIn(str(replaced.id), play.state[AWAY]["unavailable"])
        event = gf.events(log, Event.SUBSTITUTION)[-1]
        self.assertEqual(event.payload["role"], "pinch_hitter")
        self.assertEqual(event.user, self.manager)
        self.assertIn("pinch hits for", event.text)
        self.assertTrue(models.UsageAppearance.objects.filter(game=self.game, player=bat).exists())

        log = self.step(log)
        self.assertEqual(gf.events(log, Event.PLATE_APPEARANCE)[-1].payload["batter"], bat.id)

        play = self.fielding(log, AWAY)
        need = play.need()
        self.assertEqual(need.kind, sim_game.POSITION_NEED)
        self.assertEqual(need.side, AWAY)
        self.assertIn(bat.name, need.reason)
        with self.assertRaises(sim_game.GameRefused):
            sim_game.step(log, self.manager, play.sequence, seeds=self.next_seed)

        play = self.positions(log, {FIRST_BASE_SLOT: "1B"})
        self.assertIsNone(play.need())
        self.assertEqual(play.state[AWAY]["pending"], [])
        self.assertEqual(gf.events(log, Event.POSITION_CHANGE)[-1].payload["changes"][0]["position"], "1B")
        log = self.step(log)
        self.assertEqual(self.line_for(log, AWAY, bat).notation, "ph-1B")

    def test_a_pinch_hitter_for_the_designated_hitter_becomes_the_designated_hitter(self):
        log = self.open()
        self.batting_with(log, AWAY, slot=DH_SLOT)
        bat = self.road.bench[0]
        play = self.pinch_hit(log, bat)
        self.assertEqual(play.state[AWAY]["lineup"][DH_SLOT]["position"], "DH")
        self.assertEqual(play.state[AWAY]["pending"], [])
        play = self.fielding(log, AWAY)
        self.assertIsNone(play.need(), "a pinch-hitting DH needs no fielding position")
        self.assertEqual(self.line_for(log, AWAY, bat).notation, "ph-DH")

        with self.assertRaises(sim_game.GameRefused) as refused:
            self.positions(log, {DH_SLOT: "1B", FIRST_BASE_SLOT: "DH"})
        self.assertIn("designated hitter", str(refused.exception))

    def test_a_pinch_hitter_without_a_catcher_rating_cannot_be_slotted_at_catcher(self):
        models.Card.objects.filter(player=self.road.bench[1]).update(defense={"C": 2.0})
        log = self.open()
        self.batting_with(log, AWAY, slot=CATCHER_SLOT)
        bat = self.road.bench[0]
        self.pinch_hit(log, bat)
        self.fielding(log, AWAY)
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.positions(log, {CATCHER_SLOT: "C"})
        self.assertIn(
            f"{bat.name} has no catcher rating for {plan_fixtures.CARD_SEASON} and cannot play C.",
            refused.exception.reasons,
        )

        catcher = self.road.bench[1]
        sim_game.defensive_substitution(log, self.manager, AWAY, CATCHER_SLOT, catcher, self.sequence(log), seeds=self.next_seed)
        play = self.play(log)
        self.assertIsNone(play.need())
        entry = play.state[AWAY]["lineup"][CATCHER_SLOT]
        self.assertEqual((entry["id"], entry["position"]), (str(catcher.id), "C"))
        self.assertEqual(entry["defense"]["rating"], 0.2)
        log = self.step(log)
        box = box_score.box_score(gf.refresh(log))
        catcher_slot = [line for line in box.batting[AWAY]][:3]
        self.assertEqual([line.player for line in catcher_slot], [self.road.hitters[0], bat, catcher])
        self.assertEqual([line.notation for line in catcher_slot], ["C", "ph", "C"])

    def test_a_pinch_hitter_must_be_legal(self):
        capped = self.road.bench[0]
        gf.counter(capped, plate_appearances_cap=40, plate_appearances=40)
        minors = plan_fixtures.create_hitter(self.road.team, "Minor Leaguer", roster=False)
        models.Card.objects.filter(player=minors).update(hitter_rates=gf.HITTER_RATES, wrc_plus=100.0)
        log = self.open()
        self.batting_with(log, AWAY, slot=FIRST_BASE_SLOT)
        for player, reason in (
            (capped, "all 40 of his plate appearances"),
            (minors, "is not on"),
            (self.road.starters[1], "pitchers do not hit"),
            (self.road.hitters[2], "already been in this game"),
        ):
            with self.subTest(player=player.name):
                with self.assertRaises(sim_game.GameRefused) as refused:
                    self.pinch_hit(log, player)
                self.assertIn(reason, str(refused.exception))

    def test_a_call_up_can_pinch_hit(self):
        call_up = plan_fixtures.create_hitter(self.road.team, "Call Up Bat", roster=False)
        models.Card.objects.filter(player=call_up).update(hitter_rates=gf.HITTER_RATES, wrc_plus=100.0)
        log = self.open()
        play = self.batting_with(log, AWAY, slot=FIRST_BASE_SLOT)
        sim_game.make_roster_move(log, self.manager, AWAY, call_up, self.road.bench[1], play.sequence, seeds=self.next_seed)
        play = self.pinch_hit(log, call_up)
        self.assertEqual(play.state[AWAY]["lineup"][FIRST_BASE_SLOT]["id"], str(call_up.id))

    def test_a_removed_player_cannot_re_enter(self):
        log = self.open()
        self.batting_with(log, AWAY, slot=FIRST_BASE_SLOT)
        replaced = self.road.hitters[FIRST_BASE_SLOT]
        self.pinch_hit(log, self.road.bench[0])
        self.fielding(log, AWAY)
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.defensive_substitution(
                log, self.manager, AWAY, FIRST_BASE_SLOT, replaced, self.sequence(log), seeds=self.next_seed
            )
        self.assertIn("cannot re-enter", str(refused.exception))

    def test_only_the_batting_side_pinch_hits_and_only_after_the_first_pitch(self):
        log = self.open()
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.pinch_hit(log, self.road.bench[0])
        self.assertIn("first pitch", str(refused.exception))
        self.fielding(log, AWAY)
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.pinch_hit(log, self.road.bench[0])
        self.assertIn("while your club bats", str(refused.exception))


class PinchRunnerTestCase(SubstitutionTestCase):
    def test_a_pinch_runner_takes_the_base_and_the_batting_order_slot(self):
        log = self.open()
        play = self.batting_with(log, AWAY, runner=True)
        base = next(b for b in ("first", "second", "third") if play.state["bases"].get(b))
        replaced = play.player(play.state["bases"][base])
        slot = [entry["id"] for entry in play.state[AWAY]["lineup"]].index(str(replaced.id))
        runner = self.road.bench[0]
        sim_game.pinch_run(log, self.manager, AWAY, base, runner, play.sequence, seeds=self.next_seed)
        play = self.play(log)
        self.assertEqual(play.state["bases"][base], str(runner.id))
        self.assertEqual(play.state[AWAY]["lineup"][slot]["id"], str(runner.id))
        event = gf.events(log, Event.SUBSTITUTION)[-1]
        self.assertEqual((event.payload["role"], event.payload["base"]), ("pinch_runner", base))
        self.assertIn("pinch runs for", event.text)
        notation = self.line_for(log, AWAY, runner).notation
        self.assertEqual(notation, "pr-DH" if slot == DH_SLOT else "pr")

        play = self.fielding(log, AWAY)
        if slot != DH_SLOT and slot != CATCHER_SLOT:
            position = plan_fixtures.FIELD_POSITIONS[slot]
            self.assertEqual(play.need().kind, sim_game.POSITION_NEED)
            self.positions(log, {slot: position})
            self.assertEqual(self.line_for(log, AWAY, runner).notation, f"pr-{position}")

    def test_a_pinch_runner_must_replace_a_runner_on_base(self):
        log = self.open()
        play = self.batting_with(log, AWAY)
        empty = next(b for b in ("first", "second", "third") if not play.state["bases"].get(b))
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.pinch_run(log, self.manager, AWAY, empty, self.road.bench[0], play.sequence, seeds=self.next_seed)
        self.assertIn("Nobody is on", str(refused.exception))


class DefensiveReplacementTestCase(SubstitutionTestCase):
    def test_a_defensive_replacement_takes_the_slot_and_position_and_the_defense_changes(self):
        models.Card.objects.filter(player=self.road.bench[0]).update(defense={"3B": 8.0})
        log = self.open()
        play = self.fielding(log, AWAY)
        before = play.state[AWAY]["lineup"][THIRD_BASE_SLOT]["defense"]["rating"]
        glove = self.road.bench[0]
        sim_game.defensive_substitution(log, self.manager, AWAY, THIRD_BASE_SLOT, glove, play.sequence, seeds=self.next_seed)
        play = self.play(log)
        entry = play.state[AWAY]["lineup"][THIRD_BASE_SLOT]
        self.assertEqual((entry["id"], entry["position"]), (str(glove.id), "3B"))
        self.assertEqual((before, entry["defense"]["rating"]), (0.15, 0.8))
        self.assertEqual(gf.events(log, Event.SUBSTITUTION)[-1].payload["role"], "defense")
        log = self.step(log)
        box = box_score.box_score(gf.refresh(log))
        names = [line.player for line in box.batting[AWAY]]
        self.assertEqual(names.index(glove), names.index(self.road.hitters[THIRD_BASE_SLOT]) + 1)
        self.assertEqual(self.line_for(log, AWAY, glove).notation, "3B")

    def test_a_defensive_replacement_waits_for_his_club_to_take_the_field(self):
        log = self.open()
        self.batting_with(log, AWAY)
        with self.assertRaises(sim_game.GameRefused) as refused:
            sim_game.defensive_substitution(
                log, self.manager, AWAY, THIRD_BASE_SLOT, self.road.bench[0], self.sequence(log), seeds=self.next_seed
            )
        self.assertIn("in the field", str(refused.exception))

    def test_fielders_switch_positions_and_the_defense_follows_their_cards(self):
        models.Card.objects.filter(player=self.road.hitters[1]).update(defense={"1B": 1.5, "3B": 3.0})
        models.Card.objects.filter(player=self.road.hitters[3]).update(defense={"3B": 1.5, "1B": 0.5})
        log = self.open()
        self.fielding(log, AWAY)
        play = self.positions(log, {1: "3B", 3: "1B"})
        lineup = play.state[AWAY]["lineup"]
        self.assertEqual([(lineup[1]["position"], lineup[1]["defense"]["rating"]), (lineup[3]["position"], lineup[3]["defense"]["rating"])],
                         [("3B", 0.3), ("1B", 0.05)])
        log = self.step(log)
        self.assertEqual(self.line_for(log, AWAY, self.road.hitters[1]).notation, "1B-3B")
        with self.assertRaises(sim_game.GameRefused) as refused:
            self.positions(log, {1: "1B"})
        self.assertIn("1B is played twice", str(refused.exception))


class TesterAndComputerTestCase(SubstitutionTestCase):
    def test_a_tester_substitutes_for_the_home_side(self):
        log = self.open(user=self.tester, seats=(AWAY, HOME))
        play = self.fielding(log, HOME, user=self.tester)
        glove = self.home.bench[0]
        sim_game.defensive_substitution(log, self.tester, HOME, THIRD_BASE_SLOT, glove, play.sequence, seeds=self.next_seed)
        self.assertEqual(self.play(log).state[HOME]["lineup"][THIRD_BASE_SLOT]["id"], str(glove.id))
        with self.assertRaises(sim_game.GameRefused):
            sim_game.pinch_hit(log, self.manager, AWAY, self.road.bench[0], self.sequence(log), seeds=self.next_seed)

    def test_the_computer_gives_a_pending_pinch_hitter_his_position_when_the_seat_is_left(self):
        log = self.open(user=self.tester, seats=(AWAY, HOME))
        self.batting_with(log, HOME, slot=FIRST_BASE_SLOT, user=self.tester)
        bat = self.home.bench[0]
        self.pinch_hit(log, bat, side=HOME, user=self.tester)
        sim_game.leave_seat(log, self.tester, HOME, self.sequence(log), seeds=self.next_seed)
        play = self.step_until(log, lambda p: sim_game.fielding_side(p.state) == HOME, user=self.tester)
        self.assertEqual(play.state[HOME]["pending"], [])
        self.assertEqual(play.state[HOME]["lineup"][FIRST_BASE_SLOT]["position"], "1B")
        decision = gf.events(log, Event.DECISION)[-1]
        self.assertIn(bat.name, decision.text)
        self.assertTrue(gf.events(log, Event.POSITION_CHANGE)[-1].computer)


class ReplayTestCase(SubstitutionTestCase):
    def test_a_game_with_substitutions_resumes_and_replays_from_its_log(self):
        log = self.open()
        self.batting_with(log, AWAY, slot=FIRST_BASE_SLOT)
        self.pinch_hit(log, self.road.bench[0])
        self.fielding(log, AWAY)
        self.positions(log, {FIRST_BASE_SLOT: "1B"})
        play = self.play(log)
        sim_game.defensive_substitution(log, self.manager, AWAY, THIRD_BASE_SLOT, self.road.bench[1], play.sequence, seeds=self.next_seed)
        log = self.step(log)
        kept = gf.refresh(log).state
        models.GameLog.objects.filter(pk=log.pk).update(state=None, state_sequence=0)
        self.assertEqual(self.play(log).state, kept)
        log = gf.play_out(gf.refresh(log), self.manager, self.next_seed)
        self.assertEqual(sim_game.replay(gf.events(log)), log.state)
        box = box_score.box_score(log)
        self.assertTrue(box.final)
        for side in (AWAY, HOME):
            self.assertEqual(box.batting_totals[side]["r"], log.state["score"][side])


class SubstitutionPageTestCase(SubstitutionTestCase):
    def post(self, action, user=None, **data):
        self.client.force_login(user or self.manager)
        return self.client.post(f"/games/{self.game.id}/{action}/", data, follow=True)

    def test_the_page_offers_a_pinch_hitter_and_takes_one(self):
        log = self.open()
        self.batting_with(log, AWAY, slot=FIRST_BASE_SLOT)
        self.client.force_login(self.manager)
        response = self.client.get(f"/games/{self.game.id}/")
        self.assertContains(response, 'action="/games/%d/pinch_hit/"' % self.game.id)
        self.assertContains(response, self.road.bench[0].name)
        self.assertNotContains(response, 'action="/games/%d/defense/"' % self.game.id)
        response = self.post("pinch_hit", side=AWAY, player=self.road.bench[0].id, expected=self.sequence(log))
        self.assertContains(response, "pinch hits for")
        self.assertEqual(gf.events(log, Event.SUBSTITUTION)[-1].payload["player"], self.road.bench[0].id)

    def test_the_page_asks_for_positions_and_takes_them(self):
        log = self.open()
        self.batting_with(log, AWAY, slot=FIRST_BASE_SLOT)
        self.pinch_hit(log, self.road.bench[0])
        self.fielding(log, AWAY)
        self.client.force_login(self.manager)
        response = self.client.get(f"/games/{self.game.id}/")
        self.assertContains(response, "needs a fielding position")
        self.assertContains(response, 'action="/games/%d/positions/"' % self.game.id)
        self.assertContains(response, 'action="/games/%d/defense/"' % self.game.id)
        self.assertNotContains(response, "Play the next plate appearance")
        data = {f"position-{slot + 1}": position for slot, position in enumerate(plan_fixtures.FIELD_POSITIONS + ["DH"])}
        response = self.post("positions", side=AWAY, expected=self.sequence(log), **data)
        self.assertContains(response, "Play the next plate appearance")
        self.assertIsNone(self.play(log).need())
