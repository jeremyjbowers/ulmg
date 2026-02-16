# ABOUTME: Tests for duplicate player detection and merge.
# ABOUTME: Covers find_duplicate_players command and merge logic.
from django.test import TestCase
from django.contrib.auth.models import User

from ulmg import models
from ulmg.duplicate_merge import (
    merge_delete_stub,
    mark_not_duplicate,
    player_info_dict,
)


class PlayerInfoDictTestCase(TestCase):
    def test_player_info_dict(self):
        p = models.Player.objects.create(
            name="Test Player",
            position="IF",
            level="B",
            fg_id="123",
            mlbam_id="456",
        )
        info = player_info_dict(p)
        self.assertEqual(info["name"], "Test Player")
        self.assertIn("FG:123", info["ids"])
        self.assertIn("MLB:456", info["ids"])

    def test_player_info_dict_none(self):
        self.assertEqual(player_info_dict(None), {})


class MergeDeleteStubTestCase(TestCase):
    def setUp(self):
        self.keeper = models.Player.objects.create(
            name="Keeper Player",
            position="IF",
            level="B",
            fg_id="111",
            mlbam_id="222",
        )
        self.stub = models.Player.objects.create(
            name="Stub Player",
            position="IF",
            level="B",
        )

    def test_merge_transfers_playerstatseason(self):
        models.PlayerStatSeason.objects.create(
            player=self.stub,
            season=2025,
            classification="1-mlb",
        )
        ok, _ = merge_delete_stub(self.keeper, self.stub)
        self.assertTrue(ok)
        self.assertEqual(
            models.PlayerStatSeason.objects.filter(player=self.keeper).count(),
            1
        )
        self.assertFalse(models.Player.objects.filter(id=self.stub.id).exists())

    def test_merge_transfers_draftpicks(self):
        team = models.Team.objects.first()
        if not team:
            team = models.Team.objects.create(
                city="Test", abbreviation="TST", nickname="Testers"
            )
        models.DraftPick.objects.create(
            player=self.stub,
            team=team,
            year=2025,
            season="midseason",
            draft_type="open",
            draft_round=1,
            pick_number=1,
        )
        ok, _ = merge_delete_stub(self.keeper, self.stub)
        self.assertTrue(ok)
        self.assertEqual(
            models.DraftPick.objects.filter(player=self.keeper).count(),
            1
        )

    def test_merge_rejects_same_player(self):
        ok, msg = merge_delete_stub(self.keeper, self.keeper)
        self.assertFalse(ok)
        self.assertIn("themselves", msg)


class MarkNotDuplicateTestCase(TestCase):
    def setUp(self):
        self.p1 = models.Player.objects.create(name="Player One", position="IF", level="B")
        self.p2 = models.Player.objects.create(name="Player Two", position="OF", level="B")
        self.candidate = models.DuplicatePlayerCandidate.objects.create(
            player1=self.p1,
            player2=self.p2,
            status=models.DuplicatePlayerCandidate.PENDING,
        )

    def test_mark_not_duplicate(self):
        user = User.objects.create_user("staff", "staff@test.com", "pass", is_staff=True)
        ok, msg = mark_not_duplicate(self.candidate, user=user)
        self.assertTrue(ok)
        self.candidate.refresh_from_db()
        self.assertEqual(
            self.candidate.status,
            models.DuplicatePlayerCandidate.NOT_DUPLICATE
        )
        self.assertIsNotNone(self.candidate.resolved_at)
        self.assertEqual(self.candidate.resolved_by, user)
