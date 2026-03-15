# ABOUTME: Tests for the owned players API endpoint.
# ABOUTME: Ensures /api/v1/players/owned/ returns name, level, position, mlbid, fg_id from Player model.
from django.test import TestCase, Client

from ulmg import models


class OwnedPlayersAPITestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.team = models.Team.objects.create(
            city="Test City",
            abbreviation="TST",
            nickname="Testers",
        )
        self.owned_player = models.Player.objects.create(
            name="Owned Player One",
            last_name="One",
            first_name="Owned Player",
            level="V",
            position="OF",
            team=self.team,
            mlbam_id="123456",
            fg_id="789",
        )
        self.unowned_player = models.Player.objects.create(
            name="Unowned Player",
            last_name="Player",
            first_name="Unowned",
            level="B",
            position="IF",
            team=None,
            mlbam_id="999",
            fg_id="888",
        )

    def test_owned_players_returns_only_owned_players(self):
        resp = self.client.get("/api/v1/players/owned/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("players", data)
        self.assertEqual(len(data["players"]), 1)
        p = data["players"][0]
        self.assertEqual(p["name"], "Owned Player One")
        self.assertEqual(p["level"], "V")
        self.assertEqual(p["position"], "OF")
        self.assertEqual(p["mlbid"], "123456")
        self.assertEqual(p["fg_id"], "789")

    def test_owned_players_has_required_fields(self):
        resp = self.client.get("/api/v1/players/owned/")
        self.assertEqual(resp.status_code, 200)
        p = resp.json()["players"][0]
        for field in ("name", "level", "position", "mlbid", "fg_id"):
            self.assertIn(field, p)

    def test_owned_players_rejects_non_get(self):
        resp = self.client.post("/api/v1/players/owned/")
        self.assertEqual(resp.status_code, 405)
