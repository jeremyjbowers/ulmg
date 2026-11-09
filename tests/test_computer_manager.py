# ABOUTME: Tests the computer manager's rules: starter fallback, bullpen roles, the starter hook, steals and bench replacement.
# ABOUTME: Also tests utils.is_sim_tester, which decides who may take any seat in any game.

from django.contrib.auth.models import AnonymousUser, Group, User
from django.test import TestCase

from ulmg import computer_manager, models, utils


def players(*names):
    return [models.Player.objects.create(name=name, position="P", level="V") for name in names]


class ComputerManagerTestCase(TestCase):
    def test_a_legal_planned_starter_starts(self):
        one, two, three = players("One", "Two", "Three")
        choice = computer_manager.starter(two, [one, two, three], lambda p: None)
        self.assertEqual(choice.player, two)
        self.assertEqual(choice.skipped, [])

    def test_an_illegal_starter_gives_way_to_the_next_in_rotation_order_wrapping_around(self):
        one, two, three = players("One", "Two", "Three")
        illegal = {two.id: "tired", three.id: "capped"}
        choice = computer_manager.starter(two, [one, two, three], lambda p: illegal.get(p.id))
        self.assertEqual(choice.player, one)
        self.assertEqual(choice.skipped, [(two, "tired"), (three, "capped")])

    def test_a_spot_starter_outside_the_rotation_is_followed_by_the_rotation_from_the_top(self):
        spot, one, two = players("Spot", "One", "Two")
        choice = computer_manager.starter(spot, [one, two], lambda p: "no" if p == spot else None)
        self.assertEqual(choice.player, one)

    def test_the_bullpen_lists_closer_setup_short_middle_then_the_rest(self):
        closer, left, right, short, middle, other = players("Closer", "Left", "Right", "Short", "Middle", "Other")
        order = computer_manager.bullpen_order(closer, [left], [right], [short], [middle], [other])
        self.assertEqual(order, [closer, left, right, short, middle, other])

    def test_no_legal_player_returns_none_with_every_reason(self):
        a, b = players("A", "B")
        choice = computer_manager.bench_replacement([a, b], lambda p: "capped")
        self.assertIsNone(choice.player)
        self.assertEqual(choice.skipped, [(a, "capped"), (b, "capped")])


class BullpenRoleTestCase(TestCase):
    def test_a_save_situation_follows_rule_9_19(self):
        save = computer_manager.is_save_situation
        self.assertTrue(save(lead=3, runners_on=0, outs=0), "a lead of three with an inning to pitch")
        self.assertTrue(save(lead=1, runners_on=0, outs=2), "the tying run at bat")
        self.assertTrue(save(lead=4, runners_on=2, outs=1), "the tying run on deck")
        self.assertTrue(save(lead=5, runners_on=3, outs=2), "the tying run on deck with the bases loaded")
        self.assertFalse(save(lead=3, runners_on=0, outs=1), "a lead of three and no full inning left")
        self.assertFalse(save(lead=4, runners_on=0, outs=0), "the tying run not yet on deck")
        self.assertFalse(save(lead=6, runners_on=3, outs=0))
        self.assertFalse(save(lead=0, runners_on=2, outs=0), "a tie is not a save situation")
        self.assertFalse(save(lead=-1, runners_on=0, outs=0))

    def test_the_closer_in_the_ninth_or_later_in_a_save_situation(self):
        role = computer_manager.bullpen_role
        self.assertEqual(role(inning=9, lead=3, runners_on=0, outs=0), computer_manager.CLOSER)
        self.assertEqual(role(inning=11, lead=1, runners_on=1, outs=1), computer_manager.CLOSER)
        self.assertEqual(role(inning=8, lead=1, runners_on=0, outs=0), computer_manager.SETUP_R)
        self.assertEqual(role(inning=8, lead=1, runners_on=0, outs=0, batter_bats="L"), computer_manager.SETUP_L)
        self.assertEqual(role(inning=8, lead=1, runners_on=0, outs=0, batter_bats="S"), computer_manager.SETUP_R)
        self.assertEqual(role(inning=7, lead=1, runners_on=0, outs=0), computer_manager.SIRP)
        self.assertEqual(role(inning=9, lead=0, runners_on=0, outs=0), computer_manager.MIRP)
        self.assertEqual(role(inning=9, lead=5, runners_on=0, outs=0), computer_manager.MIRP)

    def test_short_relief_in_the_seventh_and_setup_in_the_eighth_when_the_game_is_close(self):
        role = computer_manager.bullpen_role
        for lead in (0, 1, 3):
            self.assertEqual(role(inning=7, lead=lead, runners_on=0, outs=0), computer_manager.SIRP)
            self.assertEqual(role(inning=8, lead=lead, runners_on=0, outs=0, batter_bats="R"), computer_manager.SETUP_R)
            self.assertEqual(role(inning=8, lead=lead, runners_on=0, outs=0, batter_bats="L"), computer_manager.SETUP_L)
        for inning in (7, 8):
            self.assertEqual(role(inning=inning, lead=4, runners_on=0, outs=0), computer_manager.MIRP)
            self.assertEqual(role(inning=inning, lead=-1, runners_on=0, outs=0), computer_manager.MIRP)
        self.assertEqual(role(inning=6, lead=1, runners_on=0, outs=0), computer_manager.MIRP)

    def test_middle_relief_otherwise(self):
        self.assertEqual(computer_manager.bullpen_role(inning=2, lead=-6, runners_on=2, outs=0), computer_manager.MIRP)

    def test_an_empty_group_falls_through_the_next_roles(self):
        cm = computer_manager
        self.assertEqual(cm.group_order(cm.CLOSER), [cm.CLOSER, cm.SETUP_R, cm.SETUP_L, cm.SIRP, cm.MIRP, cm.OTHER])
        self.assertEqual(cm.group_order(cm.SETUP_L), [cm.SETUP_L, cm.SETUP_R, cm.SIRP, cm.MIRP, cm.CLOSER, cm.OTHER])
        self.assertEqual(cm.group_order(cm.SETUP_R), [cm.SETUP_R, cm.SETUP_L, cm.SIRP, cm.MIRP, cm.CLOSER, cm.OTHER])
        self.assertEqual(cm.group_order(cm.SIRP), [cm.SIRP, cm.MIRP, cm.SETUP_R, cm.SETUP_L, cm.CLOSER, cm.OTHER])
        self.assertEqual(cm.group_order(cm.MIRP), [cm.MIRP, cm.SIRP, cm.SETUP_R, cm.SETUP_L, cm.CLOSER, cm.OTHER])

    def test_the_reliever_is_the_first_available_arm_of_the_first_group_with_one(self):
        cm = computer_manager
        closer, first, second, middle, other = players("Closer", "First", "Second", "Middle", "Other")
        groups = {
            cm.CLOSER: [closer],
            cm.SETUP_L: [],
            cm.SETUP_R: [first, second],
            cm.SIRP: [],
            cm.MIRP: [middle],
            cm.OTHER: [other],
        }
        choice = cm.reliever(cm.SETUP_R, groups, lambda p: None)
        self.assertEqual((choice.player, choice.group), (first, cm.SETUP_R))
        choice = cm.reliever(cm.SETUP_R, groups, lambda p: "tired" if p == first else None)
        self.assertEqual((choice.player, choice.group, choice.skipped), (second, cm.SETUP_R, [(first, "tired")]))
        choice = cm.reliever(cm.CLOSER, groups, lambda p: "capped" if p == closer else None)
        self.assertEqual((choice.player, choice.group), (first, cm.SETUP_R))
        choice = cm.reliever(cm.MIRP, groups, lambda p: None if p == other else "capped")
        self.assertEqual((choice.player, choice.group), (other, cm.OTHER))
        self.assertEqual([p for p, _ in choice.skipped], [middle, first, second, closer])
        self.assertIsNone(cm.reliever(cm.MIRP, groups, lambda p: "capped").player)

    def test_the_preferred_arm_is_only_from_the_situations_own_group(self):
        cm = computer_manager
        closer, setup = players("Closer", "Setup")
        groups = {cm.CLOSER: [closer], cm.SETUP_R: [setup], cm.SETUP_L: [], cm.SIRP: [], cm.MIRP: [], cm.OTHER: []}
        self.assertEqual(cm.preferred_arm(cm.SETUP_R, groups, lambda p: None).player, setup)
        self.assertIsNone(cm.preferred_arm(cm.MIRP, groups, lambda p: None).player)


class StarterHookTestCase(TestCase):
    def fatigue(self, effort=0.0, ceiling=100.0, runs=0):
        return {"effort": effort, "ceiling": ceiling, "pitches": int(effort), "outs_recorded": 0, "runs_allowed": runs}

    def test_the_hook_settings_are_the_plans_choices(self):
        hooks = {value for value, _ in models.HalfPlan.STARTER_HOOK_CHOICES}
        self.assertEqual(hooks, set(computer_manager.HOOK_CEILING_SHARE))
        self.assertEqual(hooks, set(computer_manager.HOOK_RUNS))
        self.assertEqual(models.HalfPlan().starter_hook, models.HalfPlan.NORMAL_HOOK)

    def test_each_hook_pulls_at_its_share_of_the_fatigue_ceiling(self):
        reason = computer_manager.hook_reason
        for hook, share in (("quick", 0.85), ("normal", 0.95), ("slow", 1.00)):
            self.assertEqual(computer_manager.HOOK_CEILING_SHARE[hook], share)
            self.assertIsNone(reason(hook, self.fatigue(effort=share * 100 - 0.5)), hook)
            self.assertIn("fatigue ceiling", reason(hook, self.fatigue(effort=share * 100)), hook)

    def test_each_hook_pulls_at_its_runs_allowed(self):
        reason = computer_manager.hook_reason
        for hook, runs in (("quick", 4), ("normal", 5), ("slow", 6)):
            self.assertEqual(computer_manager.HOOK_RUNS[hook], runs)
            self.assertIsNone(reason(hook, self.fatigue(runs=runs - 1)), hook)
            self.assertIn(f"{runs} runs", reason(hook, self.fatigue(runs=runs)), hook)

    def test_an_unknown_hook_reads_as_normal(self):
        self.assertIsNone(computer_manager.hook_reason(None, self.fatigue(effort=94)))
        self.assertIsNotNone(computer_manager.hook_reason(None, self.fatigue(effort=95)))


class StealTestCase(TestCase):
    def test_a_steal_situation_is_a_runner_on_first_second_open_and_fewer_than_two_outs(self):
        situation = computer_manager.is_steal_situation
        self.assertTrue(situation({"first": "1", "second": None, "third": None}, outs=0))
        self.assertTrue(situation({"first": "1", "second": None, "third": "3"}, outs=1))
        self.assertFalse(situation({"first": "1", "second": None, "third": None}, outs=2))
        self.assertFalse(situation({"first": "1", "second": "2", "third": None}, outs=0))
        self.assertFalse(situation({"first": None, "second": None, "third": None}, outs=0))

    def test_the_steal_is_called_with_probability_equal_to_the_attempt_rate(self):
        self.assertTrue(computer_manager.calls_steal(0.25, draw=0.2))
        self.assertFalse(computer_manager.calls_steal(0.25, draw=0.25))
        self.assertFalse(computer_manager.calls_steal(None, draw=0.0), "no attempt rate never steals")
        self.assertFalse(computer_manager.calls_steal(0.0, draw=0.0))
        calls = sum(computer_manager.calls_steal(0.3, draw=i / 1000) for i in range(1000))
        self.assertEqual(calls, 300)


class SimTesterTestCase(TestCase):
    def test_superusers_and_sim_testers_group_members_are_testers(self):
        superuser = User.objects.create_superuser(username="boss")
        member = User.objects.create_user(username="member")
        member.groups.add(Group.objects.create(name=utils.SIM_TESTERS_GROUP))
        plain = User.objects.create_user(username="plain")
        staff = User.objects.create_user(username="staff", is_staff=True)
        self.assertTrue(utils.is_sim_tester(superuser))
        self.assertTrue(utils.is_sim_tester(member))
        self.assertFalse(utils.is_sim_tester(plain))
        self.assertFalse(utils.is_sim_tester(staff))
        self.assertFalse(utils.is_sim_tester(AnonymousUser()))
