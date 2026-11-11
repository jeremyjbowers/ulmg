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

    def test_the_bullpen_lists_closer_then_single_inning_then_multi_inning(self):
        closer, sirp, mirp, other = players("Closer", "SIRP", "MIRP", "Other")
        order = computer_manager.bullpen_order(closer, [sirp], [mirp], [other])
        self.assertEqual(order, [closer, sirp, mirp, other])

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
        self.assertEqual(role(inning=8, lead=1, runners_on=0, outs=0), computer_manager.SIRP)
        self.assertEqual(role(inning=9, lead=0, runners_on=0, outs=0), computer_manager.SIRP)
        self.assertEqual(role(inning=9, lead=5, runners_on=0, outs=0), computer_manager.MIRP)

    def test_one_inning_from_the_sixth_on_when_the_game_is_within_three_runs(self):
        role = computer_manager.bullpen_role
        for inning in (6, 7, 8):
            for lead in (-3, -1, 0, 1, 3):
                self.assertEqual(role(inning=inning, lead=lead, runners_on=0, outs=0), computer_manager.SIRP)
            self.assertEqual(role(inning=inning, lead=4, runners_on=0, outs=0), computer_manager.MIRP)
            self.assertEqual(role(inning=inning, lead=-4, runners_on=0, outs=0), computer_manager.MIRP)

    def test_multi_inning_relief_before_the_sixth(self):
        role = computer_manager.bullpen_role
        self.assertEqual(role(inning=2, lead=-6, runners_on=2, outs=0), computer_manager.MIRP)
        self.assertEqual(role(inning=5, lead=1, runners_on=0, outs=2), computer_manager.MIRP)

    def test_a_quick_pen_brings_the_closer_in_an_inning_sooner(self):
        role = computer_manager.bullpen_role
        self.assertEqual(role(inning=8, lead=1, runners_on=0, outs=0, logic="quick"), computer_manager.CLOSER)
        self.assertEqual(role(inning=8, lead=0, runners_on=0, outs=0, logic="quick"), computer_manager.SIRP)
        self.assertEqual(role(inning=6, lead=2, runners_on=0, outs=1, logic="quick"), computer_manager.SIRP)
        self.assertEqual(role(inning=5, lead=-3, runners_on=0, outs=0, logic="quick"), computer_manager.MIRP)
        self.assertIn("8th", computer_manager.describe_bullpen_logic("quick"))

    def test_a_slow_pen_holds_single_inning_relief_until_the_eighth(self):
        role = computer_manager.bullpen_role
        self.assertEqual(role(inning=7, lead=1, runners_on=0, outs=0, logic="slow"), computer_manager.MIRP)
        self.assertEqual(role(inning=8, lead=1, runners_on=0, outs=0, logic="slow"), computer_manager.SIRP)
        self.assertEqual(role(inning=6, lead=-4, runners_on=0, outs=0, logic="slow"), computer_manager.MIRP)
        self.assertEqual(role(inning=9, lead=1, runners_on=0, outs=0, logic="slow"), computer_manager.CLOSER)
        self.assertIn("8th", computer_manager.describe_bullpen_logic("slow"))

    def test_each_bullpen_usage_calls_a_different_arm(self):
        role = computer_manager.bullpen_role
        choices = {value for value, _ in models.HalfPlan.BULLPEN_LOGIC_CHOICES}
        self.assertEqual(choices, set(computer_manager.BULLPEN_WINDOWS) - {"quick", "normal", "slow"})
        # Highest leverage: the closer in a one-run spot with a runner on, including the seventh.
        self.assertEqual(role(inning=7, lead=-1, runners_on=1, outs=0, logic="leverage"), computer_manager.CLOSER)
        self.assertEqual(role(inning=7, lead=0, runners_on=1, outs=1, logic="leverage"), computer_manager.CLOSER)
        self.assertEqual(role(inning=8, lead=1, runners_on=0, outs=0, logic="leverage"), computer_manager.CLOSER)
        self.assertEqual(role(inning=8, lead=0, runners_on=0, outs=0, logic="leverage"), computer_manager.SIRP)
        self.assertEqual(role(inning=7, lead=3, runners_on=0, outs=0, logic="leverage"), computer_manager.SIRP)
        self.assertEqual(role(inning=9, lead=3, runners_on=0, outs=0, logic="leverage"), computer_manager.CLOSER)
        self.assertEqual(role(inning=4, lead=-3, runners_on=0, outs=0, logic="leverage"), computer_manager.MIRP)
        self.assertIn("runner on", computer_manager.describe_bullpen_logic("leverage"))
        # Fireman: a tie or a one-run lead from the sixth, and he can stay there.
        self.assertEqual(role(inning=6, lead=1, runners_on=0, outs=0, logic="fireman"), computer_manager.CLOSER)
        self.assertEqual(role(inning=6, lead=0, runners_on=0, outs=2, logic="fireman"), computer_manager.CLOSER)
        self.assertEqual(role(inning=7, lead=1, runners_on=0, outs=0, logic="fireman"), computer_manager.CLOSER)
        self.assertEqual(role(inning=7, lead=2, runners_on=0, outs=0, logic="fireman"), computer_manager.SIRP)
        self.assertEqual(role(inning=8, lead=3, runners_on=0, outs=0, logic="fireman"), computer_manager.CLOSER)
        self.assertEqual(role(inning=6, lead=3, runners_on=0, outs=0, logic="fireman"), computer_manager.MIRP)
        self.assertEqual(role(inning=5, lead=1, runners_on=0, outs=0, logic="fireman"), computer_manager.MIRP)
        self.assertIn("multi-inning", computer_manager.describe_bullpen_logic("fireman"))
        # Protect the lead: no leverage arm when tied, and the closer for any one-to-three-run ninth.
        self.assertEqual(role(inning=8, lead=0, runners_on=2, outs=0, logic="protect"), computer_manager.MIRP)
        self.assertEqual(role(inning=8, lead=2, runners_on=0, outs=0, logic="protect"), computer_manager.SIRP)
        self.assertEqual(role(inning=9, lead=3, runners_on=0, outs=2, logic="protect"), computer_manager.CLOSER)
        self.assertEqual(role(inning=9, lead=3, runners_on=0, outs=2, logic="traditional"), computer_manager.SIRP)
        self.assertEqual(role(inning=9, lead=0, runners_on=0, outs=0, logic="protect"), computer_manager.MIRP)
        self.assertEqual(role(inning=6, lead=2, runners_on=0, outs=0, logic="protect"), computer_manager.MIRP)
        self.assertIn("A lead gets the good arms", computer_manager.describe_bullpen_logic("protect"))
        # Save the pen: the closer only for a one- or two-run save, single-inning relief only for a tie or one-run eighth.
        self.assertEqual(role(inning=9, lead=1, runners_on=0, outs=0, logic="save"), computer_manager.CLOSER)
        self.assertEqual(role(inning=9, lead=3, runners_on=0, outs=0, logic="save"), computer_manager.MIRP)
        self.assertEqual(role(inning=8, lead=1, runners_on=0, outs=0, logic="save"), computer_manager.SIRP)
        self.assertEqual(role(inning=8, lead=0, runners_on=0, outs=0, logic="save"), computer_manager.SIRP)
        self.assertEqual(role(inning=8, lead=2, runners_on=0, outs=0, logic="save"), computer_manager.MIRP)
        self.assertEqual(role(inning=7, lead=1, runners_on=0, outs=0, logic="save"), computer_manager.MIRP)
        self.assertEqual(role(inning=6, lead=-4, runners_on=0, outs=0, logic="save"), computer_manager.MIRP)
        self.assertIn("one or two runs", computer_manager.describe_bullpen_logic("save"))

    def test_an_unknown_logic_reads_as_traditional(self):
        role = computer_manager.bullpen_role
        self.assertEqual(role(inning=8, lead=1, runners_on=0, outs=0, logic="wild"), computer_manager.SIRP)
        self.assertEqual(role(inning=2, lead=0, runners_on=0, outs=0, logic=None), computer_manager.MIRP)
        self.assertIn("sixth", computer_manager.describe_bullpen_logic(None))
        self.assertIn("ninth", computer_manager.describe_bullpen_logic("normal"))

    def test_an_empty_group_falls_to_multi_inning_then_single_inning_then_the_closer(self):
        cm = computer_manager
        self.assertEqual(cm.group_order(cm.CLOSER), [cm.CLOSER, cm.MIRP, cm.SIRP, cm.OTHER])
        self.assertEqual(cm.group_order(cm.SIRP), [cm.SIRP, cm.MIRP, cm.CLOSER, cm.OTHER])
        self.assertEqual(cm.group_order(cm.MIRP), [cm.MIRP, cm.SIRP, cm.CLOSER, cm.OTHER])

    def test_the_reliever_is_the_first_available_arm_of_the_first_group_with_one(self):
        cm = computer_manager
        closer, first, second, multi, other = players("Closer", "First", "Second", "Multi", "Other")
        groups = {
            cm.CLOSER: [closer],
            cm.SIRP: [first, second],
            cm.MIRP: [multi],
            cm.OTHER: [other],
        }
        choice = cm.reliever(cm.SIRP, groups, lambda p: None)
        self.assertEqual((choice.player, choice.group), (first, cm.SIRP))
        choice = cm.reliever(cm.SIRP, groups, lambda p: "tired" if p == first else None)
        self.assertEqual((choice.player, choice.group, choice.skipped), (second, cm.SIRP, [(first, "tired")]))
        choice = cm.reliever(cm.CLOSER, groups, lambda p: "capped" if p == closer else None)
        self.assertEqual((choice.player, choice.group), (multi, cm.MIRP))
        choice = cm.reliever(cm.MIRP, groups, lambda p: None if p == other else "capped")
        self.assertEqual((choice.player, choice.group), (other, cm.OTHER))
        self.assertEqual([p for p, _ in choice.skipped], [multi, first, second, closer])
        self.assertIsNone(cm.reliever(cm.MIRP, groups, lambda p: "capped").player)

    def test_the_preferred_arm_is_only_from_the_situations_own_group(self):
        cm = computer_manager
        closer, sirp = players("Closer", "SIRP")
        groups = {cm.CLOSER: [closer], cm.SIRP: [sirp], cm.MIRP: [], cm.OTHER: []}
        self.assertEqual(cm.preferred_arm(cm.SIRP, groups, lambda p: None).player, sirp)
        self.assertIsNone(cm.preferred_arm(cm.MIRP, groups, lambda p: None).player)


class StarterHookTestCase(TestCase):
    def fatigue(self, effort=0.0, ceiling=100.0, runs=0):
        return {"effort": effort, "ceiling": ceiling, "pitches": int(effort), "outs_recorded": 0, "runs_allowed": runs}

    def test_the_hook_settings_are_the_plans_choices(self):
        hooks = {value for value, _ in models.HalfPlan.STARTER_HOOK_CHOICES}
        self.assertEqual(hooks, set(computer_manager.HOOK_CEILING_SHARE))
        self.assertEqual(hooks, set(computer_manager.HOOK_RUNS))
        self.assertEqual(models.HalfPlan().starter_hook, models.HalfPlan.NORMAL_HOOK)
        self.assertEqual(models.HalfPlan().bullpen_logic, models.HalfPlan.TRADITIONAL_PEN)

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
