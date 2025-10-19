from django.test import TestCase, Client
from django.urls import reverse

from ulmg import models


class PlayerBulkAddTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_bulk_add_accepts_commas_and_tabs_and_short_rows(self):
        # Row with exactly 8 comma-separated fields
        row1 = "John Doe,OF,12345,54321,,2001-01-02,Some HS,2025"
        # Row with tabs and missing several fields (should be padded)
        row2 = "Jane Pitcher\tP\t\t\t\t\t\t"
        # Row with name only (no delimiter); should be treated as name with rest blank
        row3 = "Only Name"

        payload = "\n".join([row1, row2, row3])

        resp = self.client.post("/api/v1/player/bulk/", data={"players": payload})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("players", data)
        self.assertEqual(len(data["players"]), 3)

        # All should return a ulmg_id and at least a name
        for p in data["players"]:
            self.assertIn("name", p)
            self.assertTrue(p.get("ulmg_id"))

        # Ensure that players are persisted and positions normalized
        john = models.Player.objects.get(id=data["players"][0]["ulmg_id"])
        self.assertEqual(john.name, "John Doe")
        self.assertEqual(john.position, "OF")
        self.assertEqual(john.mlbam_id, "12345")
        self.assertEqual(john.fg_id, "54321")

        jane = models.Player.objects.get(id=data["players"][1]["ulmg_id"])
        self.assertEqual(jane.position, "P")

        only = models.Player.objects.get(id=data["players"][2]["ulmg_id"])
        self.assertEqual(only.name, "Only Name")

    def test_bulk_add_parses_flexible_birthdate(self):
        row = "Kid Prospect,IF,,,,03/15/2004,Prep School,2024"
        resp = self.client.post("/api/v1/player/bulk/", data={"players": row})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        p = data["players"][0]
        obj = models.Player.objects.get(id=p["ulmg_id"])
        # Birthdate should be parsed into a date object and saved
        self.assertIsNotNone(obj.birthdate)

