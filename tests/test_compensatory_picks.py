# ABOUTME: Tests for compensatory draft pick creation when a player is taken from another team.
# ABOUTME: Ensures picks 17, 18, etc. are created at end of round for teams that lost players.
from django.test import TestCase

from ulmg import models


class CompensatoryPickTestCase(TestCase):
    def setUp(self):
        self.lng = models.Team.objects.create(
            city="Long", abbreviation="LNG", nickname="Longs"
        )
        self.xyz = models.Team.objects.create(
            city="XYZ", abbreviation="XYZ", nickname="XYZs"
        )
        self.abc = models.Team.objects.create(
            city="ABC", abbreviation="ABC", nickname="ABCs"
        )
        self.lng_player = models.Player.objects.create(
            name="LNG Player",
            last_name="Player",
            first_name="LNG",
            level="V",
            position="OF",
            team=self.lng,
        )
        self.xyz_player = models.Player.objects.create(
            name="XYZ Player",
            last_name="Player",
            first_name="XYZ",
            level="V",
            position="IF",
            team=self.xyz,
        )

    def test_compensatory_pick_created_when_player_taken_from_another_team(self):
        pick3 = models.DraftPick.objects.create(
            year="2026",
            season="offseason",
            draft_type="open",
            draft_round=3,
            pick_number=3,
            original_team=self.abc,
            team=self.abc,
        )
        pick3.player = self.lng_player
        pick3.team = self.abc
        pick3.save()

        comp_picks = models.DraftPick.objects.filter(
            year="2026",
            season="offseason",
            draft_type="open",
            draft_round=3,
            compensatory_for__isnull=False,
        )
        self.assertEqual(comp_picks.count(), 1)
        comp = comp_picks.get()
        self.assertEqual(comp.original_team, self.lng)
        self.assertEqual(comp.team, self.lng)
        self.assertEqual(comp.pick_number, 17)
        self.assertEqual(comp.compensatory_for, pick3)

    def test_compensatory_picks_ordered_by_triggering_pick(self):
        pick3 = models.DraftPick.objects.create(
            year="2026",
            season="offseason",
            draft_type="open",
            draft_round=3,
            pick_number=3,
            original_team=self.abc,
            team=self.abc,
        )
        pick5 = models.DraftPick.objects.create(
            year="2026",
            season="offseason",
            draft_type="open",
            draft_round=3,
            pick_number=5,
            original_team=self.abc,
            team=self.abc,
        )
        pick3.player = self.lng_player
        pick3.team = self.abc
        pick3.save()

        pick5.player = self.xyz_player
        pick5.team = self.abc
        pick5.save()

        comp_picks = models.DraftPick.objects.filter(
            year="2026",
            season="offseason",
            draft_type="open",
            draft_round=3,
            compensatory_for__isnull=False,
        ).order_by("pick_number")
        self.assertEqual(comp_picks.count(), 2)
        self.assertEqual(comp_picks[0].original_team, self.lng)
        self.assertEqual(comp_picks[0].pick_number, 17)
        self.assertEqual(comp_picks[1].original_team, self.xyz)
        self.assertEqual(comp_picks[1].pick_number, 18)
