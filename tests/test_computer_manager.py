# ABOUTME: Tests the computer manager's ordering rules: starter fallback, bullpen order and bench replacement.
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

    def test_the_bullpen_goes_closer_setup_middle_then_the_rest(self):
        closer, setup, middle, other = players("Closer", "Setup", "Middle", "Other")
        order = computer_manager.bullpen_order(closer, [setup], [middle], [other])
        self.assertEqual(order, [closer, setup, middle, other])
        choice = computer_manager.next_arm(order, lambda p: "capped" if p in (closer, setup) else None)
        self.assertEqual(choice.player, middle)
        self.assertEqual([p for p, _ in choice.skipped], [closer, setup])

    def test_no_legal_player_returns_none_with_every_reason(self):
        a, b = players("A", "B")
        choice = computer_manager.bench_replacement([a, b], lambda p: "capped")
        self.assertIsNone(choice.player)
        self.assertEqual(choice.skipped, [(a, "capped"), (b, "capped")])


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
