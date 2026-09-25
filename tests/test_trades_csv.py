# ABOUTME: Tests for the /trades/csv/ export endpoint.
# ABOUTME: Covers formatter units, view integration, and HTTP end-to-end CSV download.
import csv
import datetime
from io import StringIO

from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase

from ulmg import models
from ulmg.views import csv as csv_views


class TradeCSVFormatterUnitTestCase(TestCase):
    """Unit tests for CSV cell formatting helpers."""

    def test_format_trade_players(self):
        players = [
            models.Player(position="P", name="Ace Pitcher"),
            models.Player(position="OF", name="Star Hitter"),
        ]
        self.assertEqual(
            csv_views._format_trade_players(players),
            "P Ace Pitcher, OF Star Hitter",
        )

    def test_format_trade_players_empty(self):
        self.assertEqual(csv_views._format_trade_players([]), "")

    def test_format_trade_pick(self):
        team = models.Team.objects.create(
            city="Boston", abbreviation="BOS", nickname="Beans"
        )
        pick = models.DraftPick.objects.create(
            year="2026",
            season="midseason",
            draft_type="open",
            draft_round=1,
            original_team=team,
        )
        self.assertEqual(
            csv_views._format_trade_pick(pick),
            "BOS 2026 Midseason OPEN1",
        )

    def test_format_trade_pick_with_player(self):
        team = models.Team.objects.create(
            city="Boston", abbreviation="BOS", nickname="Beans"
        )
        player = models.Player.objects.create(
            name="Drafted Guy", position="IF", level="B"
        )
        pick = models.DraftPick.objects.create(
            year="2025",
            season="offseason",
            draft_type="aa",
            draft_round=2,
            original_team=team,
            player=player,
        )
        self.assertEqual(
            csv_views._format_trade_pick(pick),
            "BOS 2025 Offseason AA2 (IF Drafted Guy)",
        )


class TradesCSVIntegrationTestCase(TestCase):
    """Integration: trades_csv builds rows from TradeReceipt data."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="trade_csv_int", password="secret"
        )
        self.team_a = models.Team.objects.create(
            city="Boston", abbreviation="BOS", nickname="Beans"
        )
        self.team_b = models.Team.objects.create(
            city="New York", abbreviation="NYK", nickname="Knights"
        )
        self.player_a = models.Player.objects.create(
            name="Ace Pitcher", position="P", level="V", team=self.team_a
        )
        self.player_b = models.Player.objects.create(
            name="Star Hitter", position="OF", level="A", team=self.team_b
        )
        self.trade = models.Trade.objects.create(date=datetime.date(2025, 7, 15))
        receipt_a = models.TradeReceipt.objects.create(
            trade=self.trade, team=self.team_a
        )
        receipt_a.players.add(self.player_b)
        receipt_b = models.TradeReceipt.objects.create(
            trade=self.trade, team=self.team_b
        )
        receipt_b.players.add(self.player_a)

    def test_trades_csv_view_writes_receipt_contents(self):
        request = self.factory.get("/trades/csv/")
        request.user = self.user
        response = csv_views.trades_csv(request)
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(StringIO(response.content.decode("utf-8"))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["team_1"], "BOS")
        self.assertEqual(rows[0]["team_1_receives_players"], "OF Star Hitter")
        self.assertEqual(rows[0]["team_2_receives_players"], "P Ace Pitcher")

    def test_trades_csv_view_skips_single_receipt_trades(self):
        bad = models.Trade.objects.create(date=datetime.date(2024, 1, 1))
        models.TradeReceipt.objects.create(trade=bad, team=self.team_a)
        request = self.factory.get("/trades/csv/")
        request.user = self.user
        response = csv_views.trades_csv(request)
        rows = list(csv.DictReader(StringIO(response.content.decode("utf-8"))))
        self.assertEqual([r["trade_id"] for r in rows], [str(self.trade.id)])


class TradesCSVE2ETestCase(TestCase):
    """End-to-end HTTP tests through URL routing and auth middleware."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="trade_csv_user", password="secret"
        )
        self.client.login(username="trade_csv_user", password="secret")
        self.team_a = models.Team.objects.create(
            city="Boston",
            abbreviation="BOS",
            nickname="Beans",
        )
        self.team_b = models.Team.objects.create(
            city="New York",
            abbreviation="NYK",
            nickname="Knights",
        )
        self.player_a = models.Player.objects.create(
            name="Ace Pitcher",
            last_name="Pitcher",
            first_name="Ace",
            position="P",
            level="V",
            team=self.team_a,
        )
        self.player_b = models.Player.objects.create(
            name="Star Hitter",
            last_name="Hitter",
            first_name="Star",
            position="OF",
            level="A",
            team=self.team_b,
        )
        self.pick = models.DraftPick.objects.create(
            year="2026",
            season="midseason",
            draft_type="open",
            draft_round=1,
            pick_number=1,
            team=self.team_a,
            original_team=self.team_a,
        )

        self.trade = models.Trade.objects.create(
            date=datetime.date(2025, 7, 15),
        )
        receipt_a = models.TradeReceipt.objects.create(
            trade=self.trade, team=self.team_a
        )
        receipt_a.players.add(self.player_b)
        receipt_a.picks.add(self.pick)

        receipt_b = models.TradeReceipt.objects.create(
            trade=self.trade, team=self.team_b
        )
        receipt_b.players.add(self.player_a)

        self.trade.set_trade_summary()
        self.trade.set_teams()
        self.trade.save()

    def test_trades_csv_returns_csv_content_type(self):
        resp = self.client.get("/trades/csv/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("attachment", resp["Content-Disposition"])
        self.assertIn("trades-", resp["Content-Disposition"])

    def test_trades_csv_has_expected_headers(self):
        resp = self.client.get("/trades/csv/")
        self.assertEqual(resp.status_code, 200)
        reader = csv.DictReader(StringIO(resp.content.decode("utf-8")))
        self.assertEqual(
            reader.fieldnames,
            [
                "trade_id",
                "date",
                "season",
                "team_1",
                "team_1_receives_players",
                "team_1_receives_picks",
                "team_2",
                "team_2_receives_players",
                "team_2_receives_picks",
            ],
        )

    def test_trades_csv_includes_trade_row(self):
        resp = self.client.get("/trades/csv/")
        self.assertEqual(resp.status_code, 200)
        rows = list(csv.DictReader(StringIO(resp.content.decode("utf-8"))))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["trade_id"], str(self.trade.id))
        self.assertEqual(row["date"], "2025-07-15")
        self.assertEqual(row["season"], "2025")
        self.assertEqual(row["team_1"], "BOS")
        self.assertEqual(row["team_2"], "NYK")
        self.assertIn("OF Star Hitter", row["team_1_receives_players"])
        self.assertIn("BOS 2026 Midseason OPEN1", row["team_1_receives_picks"])
        self.assertIn("P Ace Pitcher", row["team_2_receives_players"])
        self.assertEqual(row["team_2_receives_picks"], "")

    def test_trades_csv_skips_malformed_trades(self):
        bad = models.Trade.objects.create(date=datetime.date(2024, 1, 1))
        models.TradeReceipt.objects.create(trade=bad, team=self.team_a)

        resp = self.client.get("/trades/csv/")
        self.assertEqual(resp.status_code, 200)
        rows = list(csv.DictReader(StringIO(resp.content.decode("utf-8"))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["trade_id"], str(self.trade.id))

    def test_trades_csv_orders_newest_first(self):
        older = models.Trade.objects.create(date=datetime.date(2024, 3, 1))
        r1 = models.TradeReceipt.objects.create(trade=older, team=self.team_a)
        r2 = models.TradeReceipt.objects.create(trade=older, team=self.team_b)
        r1.players.add(self.player_a)
        r2.players.add(self.player_b)

        resp = self.client.get("/trades/csv/")
        rows = list(csv.DictReader(StringIO(resp.content.decode("utf-8"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["date"], "2025-07-15")
        self.assertEqual(rows[1]["date"], "2024-03-01")

    def test_trades_csv_requires_login(self):
        self.client.logout()
        resp = self.client.get("/trades/csv/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp["Location"])
