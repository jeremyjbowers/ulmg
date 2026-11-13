# ABOUTME: Tests standings, games behind and the wild-card race, and the public standings, results and leaders pages.
# ABOUTME: Also checks the team and player pages' ULMG lines and that real-stat lookups never pick a 6-ulmg row.

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from tests.schedule_fixtures import create_league_teams
from ulmg import models, roster_moves, season_record

SEASON = 2026
ULMG = models.PlayerStatSeason.ULMG

# (wins, losses) by team. Rickey has a clear leader; CAR is the first wild
# card and DCM and CLE tie for the second. Ringen's lead is tied.
RECORDS = {
    "ATL": (10, 2), "CAR": (8, 4), "DCM": (7, 5), "PIT": (2, 10),
    "CLE": (7, 5), "DET": (9, 3), "KCB": (6, 6), "LOU": (3, 9),
    "ABQ": (6, 6), "ADK": (6, 6), "CHI": (5, 7), "HCH": (4, 8),
    "CIN": (9, 3), "LNG": (7, 5), "NYH": (7, 5), "PEN": (2, 10),
}


def create_records(teams, season=SEASON):
    for team in teams:
        wins, losses = RECORDS[team.abbreviation]
        models.TeamSeasonRecord.objects.create(team=team, season=season, wins=wins, losses=losses)


def by_abbreviation(rows):
    return {row.team.abbreviation: row for row in rows}


class StandingsTestCase(TestCase):
    def setUp(self):
        self.teams = create_league_teams()
        create_records(self.teams)
        self.standings = {c.name: c for c in season_record.standings(SEASON)}

    def division(self, name):
        for conference in self.standings.values():
            for division in conference.divisions:
                if division.name == name:
                    return division
        raise AssertionError(name)

    def test_conferences_come_from_the_division_map(self):
        self.assertEqual(list(self.standings), ["East", "West"])
        self.assertEqual([d.name for d in self.standings["East"].divisions], ["Rickey", "Fernandez"])
        self.assertEqual([d.name for d in self.standings["West"].divisions], ["Ringen", "Orzol"])

    def test_each_division_is_ordered_with_games_behind(self):
        rickey = self.division("Rickey")
        self.assertEqual([r.team.abbreviation for r in rickey.rows], ["ATL", "CAR", "DCM", "PIT"])
        self.assertEqual([r.games_behind for r in rickey.rows], [0, 2, 3, 8])
        self.assertEqual([r.games_behind_display for r in rickey.rows], ["-", "2", "3", "8"])
        self.assertEqual(rickey.rows[0].pct_display, ".833")
        self.assertFalse(any(r.tied_for_lead for r in rickey.rows))

    def test_half_games_behind(self):
        models.TeamSeasonRecord.objects.filter(team__abbreviation="CAR").update(losses=5)
        rows = by_abbreviation(self.division_rows("Rickey"))
        self.assertEqual(rows["CAR"].games_behind, 2.5)
        self.assertEqual(rows["CAR"].games_behind_display, "2.5")

    def division_rows(self, name):
        for conference in season_record.standings(SEASON):
            for division in conference.divisions:
                if division.name == name:
                    return division.rows
        raise AssertionError(name)

    def test_a_tied_division_lead_is_shown_as_a_tie(self):
        ringen = by_abbreviation(self.division("Ringen").rows)
        self.assertTrue(ringen["ABQ"].tied_for_lead)
        self.assertTrue(ringen["ADK"].tied_for_lead)
        self.assertFalse(ringen["CHI"].tied_for_lead)
        self.assertEqual((ringen["ABQ"].games_behind, ringen["ADK"].games_behind), (0, 0))

    def test_the_wild_card_race_is_everyone_but_the_division_winners_in_record_order(self):
        east = self.standings["East"].wild_card
        self.assertEqual([r.team.abbreviation for r in east], ["CAR", "CLE", "DCM", "KCB", "LOU", "PIT"])
        statuses = {r.team.abbreviation: r.status for r in east}
        self.assertEqual(statuses["CAR"], season_record.IN)
        self.assertEqual((statuses["CLE"], statuses["DCM"]), (season_record.TIED, season_record.TIED))
        self.assertEqual(statuses["KCB"], season_record.OUT)
        rows = by_abbreviation(east)
        self.assertEqual([rows[a].games_behind_display for a in ("CAR", "CLE", "DCM", "KCB", "PIT")], ["+1", "-", "-", "1", "5"])

    def test_with_two_clear_wild_cards_both_are_in(self):
        models.TeamSeasonRecord.objects.filter(team__abbreviation="CLE").update(wins=6, losses=6)
        east = by_abbreviation(
            next(c for c in season_record.standings(SEASON) if c.name == "East").wild_card
        )
        self.assertEqual((east["CAR"].status, east["DCM"].status), (season_record.IN, season_record.IN))
        self.assertEqual((east["CLE"].status, east["KCB"].status), (season_record.OUT, season_record.OUT))

    def test_a_tied_division_lead_leaves_both_teams_in_the_wild_card_race(self):
        west = self.standings["West"].wild_card
        self.assertEqual([r.team.abbreviation for r in west], ["LNG", "NYH", "ABQ", "ADK", "CHI", "HCH", "PEN"])
        rows = by_abbreviation(west)
        self.assertTrue(rows["ABQ"].tied_for_division_lead)
        self.assertEqual((rows["LNG"].status, rows["NYH"].status), (season_record.IN, season_record.IN))
        # Three places are open: two wild cards and Ringen's undecided title.
        self.assertEqual((rows["ABQ"].status, rows["ADK"].status), (season_record.TIED, season_record.TIED))
        self.assertEqual(rows["CHI"].status, season_record.OUT)

    def test_a_team_with_no_games_is_listed_at_0_0(self):
        models.TeamSeasonRecord.objects.filter(team__abbreviation="PIT").delete()
        rows = by_abbreviation(self.division_rows("Rickey"))
        self.assertEqual((rows["PIT"].wins, rows["PIT"].losses), (0, 0))
        self.assertEqual(rows["PIT"].games_behind, 4)

    def test_another_seasons_records_are_ignored(self):
        create_records(self.teams, season=SEASON + 1)
        models.TeamSeasonRecord.objects.filter(season=SEASON + 1, team__abbreviation="PIT").update(wins=50)
        rows = by_abbreviation(self.division_rows("Rickey"))
        self.assertEqual(rows["PIT"].wins, 2)


def final_game(slot, home, road, day, home_score, road_score):
    series, _ = models.ScheduleSeries.objects.get_or_create(slot=slot, home_team=home, road_team=road)
    game = models.ScheduleGame.objects.create(
        series=series, day=day, home_score=home_score, road_score=road_score
    )
    log = models.GameLog.objects.create(game=game, state={"status": "final"})
    models.GameEvent.objects.create(
        log=log, sequence=1, kind=models.GameEvent.FINAL, payload={"score": {"away": road_score, "home": home_score}}
    )
    return game


class PagesTestCase(TestCase):
    def setUp(self):
        self.teams = {t.abbreviation: t for t in create_league_teams()}
        create_records(self.teams.values())
        self.atl, self.car = self.teams["ATL"], self.teams["CAR"]
        slot = models.ScheduleSlot.objects.create(
            season=SEASON, half=1, number=1, slot_type=models.ScheduleSlot.DIVISION, length=4, first_day=1
        )
        self.won = final_game(slot, self.atl, self.car, 1, 5, 2)
        self.lost = final_game(slot, self.atl, self.car, 2, 1, 4)
        series = self.won.series
        self.unplayed = models.ScheduleGame.objects.create(series=series, day=3)
        self.unlogged = models.ScheduleGame.objects.create(series=series, day=4, home_score=9, road_score=0)

        self.slugger = models.Player.objects.create(name="Ulmg Slugger", position="OF", level="V", team=self.atl)
        models.PlayerStatSeason.objects.create(
            player=self.slugger, season=SEASON, classification="1-mlb", hit_stats={"pa": 300, "hr": 11, "ab": 270, "k_pct": 0.21, "bb_pct": 0.09}
        )
        models.PlayerStatSeason.objects.create(
            player=self.slugger, season=SEASON, classification=ULMG,
            hit_stats={
                "g": 2, "pa": 9, "ab": 8, "h": 4, "hr": 3, "rbi": 5, "r": 3, "sb": 0,
                "avg": 0.5, "obp": 0.555, "slg": 1.625, "ops": 2.18, "iso": 1.125,
                "k_pct": 0.222, "bb_pct": 0.111,
            },
        )
        self.other = models.Player.objects.create(name="Ulmg Contact", position="OF", level="A", team=self.car)
        models.PlayerStatSeason.objects.create(
            player=self.other, season=SEASON, classification=ULMG,
            hit_stats={
                "g": 2, "pa": 9, "ab": 9, "h": 5, "hr": 1, "rbi": 1, "r": 1, "sb": 2, "avg": 0.555,
                "k_pct": 0, "bb_pct": 0,
            },
        )
        self.ace = models.Player.objects.create(name="Ulmg Ace", position="P", level="V", team=self.atl)
        models.PlayerStatSeason.objects.create(
            player=self.ace, season=SEASON, classification=ULMG,
            pitch_stats={
                "g": 2, "gs": 2, "w": 2, "l": 0, "sv": 0, "hld": 7, "ip": 14.1, "so": 17,
                "era": 1.88, "whip": 0.91, "k_9": 10.8, "bb_9": 2.5,
            },
        )

    def test_the_standings_page_is_public(self):
        response = self.client.get(f"/standings/{SEASON}/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for name in ("Rickey", "Fernandez", "Ringen", "Orzol", "East wild card", "West wild card"):
            self.assertIn(name, content)
        self.assertLess(content.index(">ATL<"), content.index(">CAR<"))
        self.assertContains(response, "Tied")

    def test_the_results_page_lists_final_games_with_box_score_links(self):
        response = self.client.get(f"/teams/atl/results/{SEASON}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="/games/{self.won.id}/box/"')
        self.assertContains(response, f'href="/games/{self.lost.id}/box/"')
        self.assertContains(response, "W 5-2")
        self.assertContains(response, "L 1-4")
        self.assertNotContains(response, f"/games/{self.unplayed.id}/")
        self.assertNotContains(response, f"/games/{self.unlogged.id}/")
        self.assertContains(response, "10-2")

    def test_the_results_page_shows_players_over_the_usage_penalty_lines_and_overrides(self):
        over_10 = models.Player.objects.create(name="Overused Ten", position="OF", level="V", team=self.atl)
        over_20 = models.Player.objects.create(name="Overused Twenty", position="OF", level="V", team=self.atl)
        within = models.Player.objects.create(name="Within Cap", position="OF", level="V", team=self.atl)
        for player, used in ((over_10, 115), (over_20, 125), (within, 100)):
            models.UsageCounter.objects.create(
                player=player, season=SEASON, plate_appearances=used, plate_appearances_cap=100
            )
        commissioner = User.objects.create_user("commissioner", is_superuser=True)
        models.UsageOverride.objects.create(
            player=over_10, game=self.won, cap=models.UsageOverride.PLATE_APPEARANCES,
            reason="Extra innings", approved_by=commissioner, plate_appearances_used=2,
        )
        response = self.client.get(f"/teams/atl/results/{SEASON}/")
        content = response.content.decode()
        self.assertIn("More than 10% over", content)
        self.assertIn("More than 20% over", content)
        over_10_section = content[content.index("More than 10% over"):content.index("More than 20% over")]
        self.assertIn("Overused Ten", over_10_section)
        self.assertIn("Overused Twenty", over_10_section)
        over_20_section = content[content.index("More than 20% over"):]
        self.assertIn("Overused Twenty", over_20_section.split("Commissioner overrides")[0])
        self.assertNotIn("Overused Ten", over_20_section.split("Commissioner overrides")[0])
        self.assertNotIn("Within Cap", content)
        self.assertIn("115 of 100 plate appearances", content)
        self.assertIn("Extra innings", content)
        self.assertIn("2 PA", content)

    def test_the_standings_page_flags_a_team_with_a_player_over_a_penalty_line(self):
        player = models.Player.objects.create(name="Flagged", position="OF", level="V", team=self.car)
        models.UsageCounter.objects.create(player=player, season=SEASON, plate_appearances=125, plate_appearances_cap=100)
        response = self.client.get(f"/standings/{SEASON}/")
        self.assertContains(response, 'title="A player more than 20% over a usage cap"')

    def test_the_leaders_page_is_public_and_ranks_the_6_ulmg_lines(self):
        response = self.client.get(f"/leaders/{SEASON}/")
        self.assertEqual(response.status_code, 200)
        leaders = season_record.leaders(SEASON)
        home_runs = next(board for board in leaders.batting if board.key == "hr")
        self.assertEqual([row.player for row in home_runs.rows], [self.slugger, self.other])
        hits = next(board for board in leaders.batting if board.key == "h")
        self.assertEqual([row.value for row in hits.rows], [5, 4])
        wins = next(board for board in leaders.pitching if board.key == "w")
        self.assertEqual([row.player for row in wins.rows], [self.ace])
        holds = next(board for board in leaders.pitching if board.key == "hld")
        self.assertEqual([(row.player, row.value) for row in holds.rows], [(self.ace, 7)])
        self.assertContains(response, "Ulmg Slugger")
        self.assertContains(response, 'data-stat="hld"')
        self.assertContains(response, "14.1")
        self.assertNotContains(response, ">11<", msg_prefix="the MLB line is not a ULMG leader")

    def test_the_team_page_shows_the_current_ulmg_record(self):
        self.client.force_login(User.objects.create_user("viewer"))
        response = self.client.get("/teams/atl/")
        self.assertContains(response, "ULMG record")
        self.assertContains(response, "10-2")
        self.assertContains(response, f'href="/teams/atl/results/{SEASON}/"')

    def test_the_team_roster_shows_the_mlb_line_not_the_ulmg_line(self):
        self.client.force_login(User.objects.create_user("viewer"))
        response = self.client.get("/teams/atl/")
        slugger = next(p for p in response.context["hitters"] if p == self.slugger)
        self.assertEqual([row.classification for row in slugger.current_season_stats], ["1-mlb"])

    def test_the_player_page_shows_the_ulmg_line_beside_and_distinct_from_the_mlb_line(self):
        self.client.force_login(User.objects.create_user("viewer"))
        response = self.client.get(f"/players/{self.slugger.id}/")
        self.assertEqual(response.context["ulmg_line"].classification, ULMG)
        self.assertEqual([row.classification for row in response.context["hitter_stats"]], ["1-mlb"])
        content = response.content.decode()
        self.assertIn(f"{SEASON} ULMG season", content)
        ulmg_section = content[content.index(f"{SEASON} ULMG season"):content.index("Hitting Stats")]
        self.assertIn(".500", ulmg_section)
        self.assertIn("1.625", ulmg_section)
        for label in ("OPS", "ISO", "K%", "BB%"):
            self.assertIn(label, ulmg_section)
        self.assertIn("2.180", ulmg_section)
        self.assertIn("1.125", ulmg_section)
        self.assertIn("22.2", ulmg_section)
        self.assertIn("11.1", ulmg_section)

    def test_the_player_page_shows_the_ulmg_pitching_rates_and_holds(self):
        self.client.force_login(User.objects.create_user("pitching"))
        response = self.client.get(f"/players/{self.ace.id}/")
        content = response.content.decode()
        ulmg_section = content[content.index(f"{SEASON} ULMG season"):]
        for label in ("HLD", "ERA", "WHIP", "K/9", "BB/9"):
            self.assertIn(label, ulmg_section)
        self.assertIn("1.88", ulmg_section)
        self.assertIn("0.91", ulmg_section)
        self.assertIn("10.8", ulmg_section)
        self.assertIn("2.5", ulmg_section)
        self.assertIn(">7<", ulmg_section)

    def test_a_zero_rate_is_shown_and_a_line_without_rate_keys_still_renders(self):
        self.client.force_login(User.objects.create_user("partial"))
        response = self.client.get(f"/players/{self.other.id}/")
        content = response.content.decode()
        ulmg_section = content[content.index(f"{SEASON} ULMG season"):]
        self.assertIn("0.0", ulmg_section)
        bare = models.Player.objects.create(name="No Rates", position="OF", level="A", team=self.car)
        models.PlayerStatSeason.objects.create(
            player=bare, season=SEASON, classification=ULMG, hit_stats={"g": 1, "pa": 4, "ab": 4, "h": 1}
        )
        response = self.client.get(f"/players/{bare.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"{SEASON} ULMG season")

    def test_the_player_page_without_a_ulmg_line_has_no_ulmg_block(self):
        self.client.force_login(User.objects.create_user("viewer"))
        player = models.Player.objects.create(name="Never Played", position="OF", level="V")
        response = self.client.get(f"/players/{player.id}/")
        self.assertIsNone(response.context["ulmg_line"])
        self.assertNotContains(response, "ULMG season")


@override_settings(CURRENT_SEASON=SEASON, CURRENT_SEASON_TYPE="midseason", STATS_DISPLAY_SEASON_CAP=None)
class RealStatLookupsTestCase(TestCase):
    """A 6-ulmg row is a sim line; every lookup of a player's real season line passes over it."""

    def setUp(self):
        self.player = models.Player.objects.create(name="Sim Only", position="OF", level="V")
        models.PlayerStatSeason.objects.create(
            player=self.player, season=SEASON - 1, classification="1-mlb", hit_stats={"pa": 500}
        )
        self.ulmg = models.PlayerStatSeason.objects.create(
            player=self.player, season=SEASON, classification=ULMG, hit_stats={"pa": 40}
        )

    def test_the_best_stat_season_is_never_the_ulmg_line(self):
        self.assertEqual(self.player.get_best_stat_season().classification, "1-mlb")
        self.assertEqual(self.player.latest_hit_stats(), {"pa": 500})
        self.assertIsNone(self.player.stat_season_display_row)
        self.assertIsNone(self.player.current_season_status())

    def test_a_roster_flag_never_lands_on_the_ulmg_line(self):
        roster_moves.update_player_stat_season_roster(self.player, season=SEASON, is_ulmg_mlb_roster=True)
        self.ulmg.refresh_from_db()
        self.assertFalse(self.ulmg.is_ulmg_mlb_roster)
        real = models.PlayerStatSeason.objects.get(player=self.player, season=SEASON, classification="1-mlb")
        self.assertTrue(real.is_ulmg_mlb_roster)

    def test_the_player_search_lists_real_lines_only(self):
        self.client.force_login(User.objects.create_user("viewer"))
        response = self.client.get(f"/search/filter/?season={SEASON}")
        self.assertNotIn(self.ulmg, response.context["hitters"])


class UsageOverridesForTeamTestCase(TestCase):
    def test_only_the_teams_approved_overrides_in_the_season(self):
        teams = {t.abbreviation: t for t in create_league_teams()}
        slot = models.ScheduleSlot.objects.create(
            season=SEASON, half=1, number=1, slot_type=models.ScheduleSlot.DIVISION, length=1, first_day=1
        )
        game = final_game(slot, teams["ATL"], teams["CAR"], 1, 1, 0)
        mine = models.Player.objects.create(name="Mine", position="P", team=teams["ATL"])
        theirs = models.Player.objects.create(name="Theirs", position="P", team=teams["CAR"])
        approver = User.objects.create_user("approver", is_superuser=True)
        approved = models.UsageOverride.objects.create(player=mine, game=game, cap=models.UsageOverride.REST, approved_by=approver)
        models.UsageOverride.objects.create(player=mine, game=game, cap=models.UsageOverride.STARTS)
        models.UsageOverride.objects.create(player=theirs, game=game, cap=models.UsageOverride.REST, approved_by=approver)
        self.assertEqual(list(season_record.team_overrides(teams["ATL"], SEASON)), [approved])
