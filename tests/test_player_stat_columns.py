# ABOUTME: Tests that list-view player stat cells match hitter/pitcher headers.
# ABOUTME: Covers template rendering, homepage/search pages, and shared layout across list views.
from html.parser import HTMLParser

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import Client, TestCase, override_settings

from ulmg import models


HITTER_STATS = {
    "pa": 51,
    "avg": 0.268,
    "obp": 0.350,
    "slg": 0.425,
    "hr": 1,
    "sb": 0,
    "k_pct": 0.078,
    "bb_pct": 0.069,
    "wrc_plus": 69,
    "xavg": 0.196,
    "xwoba": 0.300,
    "xslg": 0.381,
    "obp_plus": 120,
    "slg_plus": 130,
    "war": 0.4,
}

PITCHER_STATS = {
    "g": 45,
    "gs": 12,
    "ip": 80.1,
    "era": 3.25,
    "whip": 1.05,
    "k_9": 9.5,
    "bb_9": 2.1,
    "hr_9": 1.0,
    "fip": 3.10,
    "xfip": 3.20,
    "siera": 3.15,
    "war": 2.4,
}


class _TagCountParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ths = 0
        self.tds = 0

    def handle_starttag(self, tag, attrs):
        if tag == "th":
            self.ths += 1
        elif tag == "td":
            self.tds += 1


def count_th_td(html):
    parser = _TagCountParser()
    parser.feed(html)
    return parser.ths, parser.tds


def row_html_for_player(page_html, player_name):
    idx = page_html.find(player_name)
    if idx == -1:
        return ""
    tr_end = page_html.find("</tr>", idx)
    if tr_end == -1:
        return page_html[idx : idx + 2500]
    return page_html[idx:tr_end]


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class HitterStatCellsTemplateTestCase(TestCase):
    def setUp(self):
        self.hitter = models.Player.objects.create(
            name="Slash Line FA",
            position="C",
            level="V",
            current_mlb_org="LAA",
        )
        self.hitter_season = models.PlayerStatSeason.objects.create(
            player=self.hitter,
            season=2026,
            classification="1-mlb",
            level="MLB",
            role_type="mlb-bn",
            mlb_org="LAA",
            fg_positions=["C"],
            hit_stats=HITTER_STATS,
            is_career=False,
        )
        self.pitcher = models.Player.objects.create(
            name="Compact Ace FA",
            position="P",
            level="A",
            current_mlb_org="ARI",
        )
        self.pitcher_season = models.PlayerStatSeason.objects.create(
            player=self.pitcher,
            season=2026,
            classification="1-mlb",
            level="MLB",
            role_type="mlb-sp",
            mlb_org="ARI",
            pitch_stats=PITCHER_STATS,
            is_career=False,
        )

    def test_playerstatseason_hitter_cells_match_headers(self):
        header = render_to_string("includes/hitter_stat_headers.html")
        cells = render_to_string(
            "includes/hitter_stat_cells.html", {"p": self.hitter_season}
        )
        ths, _ = count_th_td(header)
        _, tds = count_th_td(cells)
        self.assertEqual(ths, tds)
        self.assertIn(".268/.350/.425", cells)
        self.assertIn(".196/.300/.381", cells)
        self.assertNotIn("mlb-bn", cells)
        self.assertNotIn(">LAA<", cells)
        self.assertIn(">C<", cells)

    def test_player_hitter_cells_match_headers(self):
        header = render_to_string("includes/hitter_stat_headers.html")
        cells = render_to_string("includes/hitter_stat_cells.html", {"p": self.hitter})
        ths, _ = count_th_td(header)
        _, tds = count_th_td(cells)
        self.assertEqual(ths, tds)
        self.assertIn(".268/.350/.425", cells)

    def test_playerstatseason_pitcher_cells_match_headers(self):
        header = render_to_string("includes/pitcher_stat_headers.html")
        cells = render_to_string(
            "includes/pitcher_stat_cells.html", {"p": self.pitcher_season}
        )
        ths, _ = count_th_td(header)
        _, tds = count_th_td(cells)
        self.assertEqual(ths, tds)
        self.assertIn("2.4", cells)
        self.assertNotIn("mlb-sp", cells)
        self.assertNotIn(">ARI<", cells)


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class PlayerStatColumnAlignmentTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="secret")
        self.owner = models.Owner.objects.create(user=self.user, name="Manager")
        self.team = models.Team.objects.create(
            city="Test City",
            abbreviation="TST",
            nickname="Testers",
            owner_obj=self.owner,
        )
        self.unowned_hitter = models.Player.objects.create(
            name="Travis DArnaud FA",
            position="C",
            level="V",
            current_mlb_org="LAA",
        )
        models.PlayerStatSeason.objects.create(
            player=self.unowned_hitter,
            season=2026,
            classification="1-mlb",
            level="MLB",
            role_type="mlb-bn",
            mlb_org="LAA",
            fg_positions=["C"],
            hit_stats=HITTER_STATS,
            is_career=False,
        )
        self.unowned_pitcher = models.Player.objects.create(
            name="Home Page Arm",
            position="P",
            level="A",
            current_mlb_org="ARI",
        )
        models.PlayerStatSeason.objects.create(
            player=self.unowned_pitcher,
            season=2026,
            classification="1-mlb",
            level="MLB",
            role_type="mlb-sp",
            mlb_org="ARI",
            pitch_stats=PITCHER_STATS,
            is_career=False,
        )
        self.owned_hitter = models.Player.objects.create(
            name="Roster Slash",
            position="C",
            level="A",
            team=self.team,
        )
        models.PlayerStatSeason.objects.create(
            player=self.owned_hitter,
            season=2026,
            classification="1-mlb",
            level="MLB",
            fg_positions=["C"],
            hit_stats=HITTER_STATS,
            is_career=False,
        )
        self.client.login(username="mgr", password="secret")

    def test_homepage_hitter_row_uses_actual_and_expected_slash_lines(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ">Actual<")
        self.assertContains(response, ">Expected<")
        row = row_html_for_player(response.content.decode(), "Travis DArnaud FA")
        self.assertIn(".268/.350/.425", row)
        self.assertIn(".196/.300/.381", row)
        self.assertNotIn("mlb-bn", row)
        self.assertNotIn(">LAA<", row)

    def test_homepage_pitcher_row_includes_war_not_org(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        row = row_html_for_player(response.content.decode(), "Home Page Arm")
        self.assertIn("2.4", row)
        self.assertNotIn("mlb-sp", row)
        self.assertNotIn(">ARI<", row)

    def test_filter_search_hitter_row_matches_headers(self):
        response = self.client.get("/search/filter/?season=2026&position=h")
        self.assertEqual(response.status_code, 200)
        row = row_html_for_player(response.content.decode(), "Travis DArnaud FA")
        self.assertIn(".268/.350/.425", row)
        self.assertNotIn("mlb-bn", row)
        self.assertNotIn(">LAA<", row)

    def test_name_search_hitter_row_matches_headers(self):
        response = self.client.get("/search/name/?name=Travis")
        self.assertEqual(response.status_code, 200)
        row = row_html_for_player(response.content.decode(), "Travis DArnaud FA")
        self.assertIn(".268/.350/.425", row)
        self.assertNotIn("mlb-bn", row)


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class PlayerListPagesShareStatColumnsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="secret")
        self.owner = models.Owner.objects.create(user=self.user, name="Manager")
        self.team = models.Team.objects.create(
            city="Test City",
            abbreviation="TST",
            nickname="Testers",
            owner_obj=self.owner,
        )
        self.unowned = models.Player.objects.create(
            name="Shared Slash FA",
            position="C",
            level="V",
        )
        models.PlayerStatSeason.objects.create(
            player=self.unowned,
            season=2026,
            classification="1-mlb",
            level="MLB",
            fg_positions=["C"],
            hit_stats=HITTER_STATS,
            is_career=False,
        )
        self.owned = models.Player.objects.create(
            name="Shared Slash Owned",
            position="C",
            level="A",
            team=self.team,
        )
        models.PlayerStatSeason.objects.create(
            player=self.owned,
            season=2026,
            classification="1-mlb",
            level="MLB",
            fg_positions=["C"],
            hit_stats=HITTER_STATS,
            is_career=False,
        )
        self.client.login(username="mgr", password="secret")

    def test_homepage_search_and_team_share_actual_expected_layout(self):
        homepage = self.client.get("/")
        search = self.client.get("/search/filter/?season=2026&position=h")
        team = self.client.get("/teams/tst/")
        for response, name in (
            (homepage, "Shared Slash FA"),
            (search, "Shared Slash FA"),
            (team, "Shared Slash Owned"),
        ):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, ">Actual<")
            self.assertContains(response, ">Expected<")
            self.assertContains(response, ">OPS+<")
            self.assertContains(response, ">WAR<")
            self.assertNotContains(response, ">AVG<")
            row = row_html_for_player(response.content.decode(), name)
            self.assertIn(".268/.350/.425", row)
            self.assertIn(".196/.300/.381", row)
            self.assertIn("150", row)
            self.assertIn("0.4", row)
