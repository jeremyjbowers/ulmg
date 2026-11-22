# ABOUTME: Tests the MCP game-result reads: scores, box scores, standings, sim stats, leaders, team seasons and usage.
# ABOUTME: Plays one real game against the engine, then reads it through the services, the JSON API and the MCP tools.
import json

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from httpx import ASGITransport, AsyncClient

from tests import game_fixtures as gf
from tests import sim_fixtures
from ulmg import box_score, models, sim_game, utils
from ulmg.mcp_app import games as game_reads
from ulmg.mcp_app.context import reset_current_owner, set_current_owner
from ulmg.mcp_app.http_app import create_site_asgi_application
from ulmg.mcp_app.tools import build_mcp

AWAY, HOME = sim_game.AWAY, sim_game.HOME
SEASON = gf.SEASON

GAME_TOOLS = {
    "list_games",
    "get_box_score",
    "get_standings",
    "list_sim_stats",
    "get_sim_leaders",
    "get_team_season",
    "get_usage",
}


def _tool_text(result):
    content = result[0] if isinstance(result, tuple) else result
    block = content[0] if isinstance(content, list) else content
    return json.loads(block.text)


class PlayedGameTestCase(gf.EngineMixin, TestCase):
    """
    Day 1's first game, played to its final by the visiting manager. Every
    hitter strikes out except the home leadoff man, who homers each time up.
    """

    @classmethod
    def setUpTestData(cls):
        gf.create_game_season(cls)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        everyone = cls.road.hitters + cls.road.bench + cls.home.hitters + cls.home.bench
        gf.set_rates(everyone, gf.STRIKEOUT_RATES)
        gf.set_rates([cls.home.hitters[0]], gf.HOME_RUN_RATES)
        next_seed = gf.seeds()
        game = gf.next_road_game(cls.road.team)
        log = sim_game.open_game(game, cls.manager, (AWAY,), seeds=next_seed)
        cls.log = gf.play_out(log, cls.manager, next_seed)
        cls.game = models.ScheduleGame.objects.get(pk=cls.log.game_id)
        cls.box = box_score.box_score(cls.log)

    def setUp(self):
        self.owner = models.Owner.objects.get(user=self.manager)
        self.raw, _ = models.OwnerAPIToken.create_token(self.owner, label="tests")
        self.client = Client()

    def _get(self, path, **params):
        return self.client.get(path, data=params, HTTP_AUTHORIZATION=f"Bearer {self.raw}")

    # Scores

    def test_list_games_returns_the_final_with_its_score(self):
        data = game_reads.list_games(season=SEASON, team=self.road.team.abbreviation)
        self.assertEqual(data["season"], SEASON)
        self.assertEqual(len(data["games"]), 1)
        game = data["games"][0]
        self.assertEqual(game["id"], self.game.id)
        self.assertEqual(game["status"], "final")
        self.assertEqual(game["day"], 1)
        self.assertEqual(game["road"]["abbreviation"], self.road.team.abbreviation)
        self.assertEqual(game["home"]["abbreviation"], self.home.team.abbreviation)
        self.assertEqual((game["road_score"], game["home_score"]), (self.game.road_score, self.game.home_score))
        self.assertEqual(game["winner"], self.home.team.abbreviation)

    def test_list_games_filters_by_status(self):
        scheduled = game_reads.list_games(season=SEASON, team=self.road.team.abbreviation, status="scheduled", limit=500)
        everything = game_reads.list_games(season=SEASON, team=self.road.team.abbreviation, status="all", limit=500)
        self.assertNotIn(self.game.id, [g["id"] for g in scheduled["games"]])
        self.assertTrue(all(g["status"] == "scheduled" for g in scheduled["games"]))
        self.assertEqual(len(everything["games"]), len(scheduled["games"]) + 1)

    def test_list_games_filters_by_day(self):
        later = game_reads.list_games(season=SEASON, day_from=2, status="all", limit=500)
        self.assertTrue(later["games"])
        self.assertTrue(all(g["day"] >= 2 for g in later["games"]))

    # Box score

    def test_box_score_matches_the_site_box_score(self):
        data = game_reads.get_box_score(self.game.id)
        self.assertTrue(data["final"])
        self.assertEqual(data["game"]["id"], self.game.id)
        self.assertEqual(data["totals"][HOME]["r"], self.game.home_score)
        self.assertEqual(data["totals"][AWAY]["r"], self.game.road_score)
        self.assertEqual(data["line_score"]["innings"], self.box.innings)
        self.assertEqual(data["line_score"][HOME], self.box.line[HOME])
        leadoff = data["batting"][HOME][0]
        self.assertEqual(leadoff["player"]["id"], self.home.hitters[0].id)
        self.assertEqual(leadoff["hr"], self.box.batting[HOME][0].hr)
        self.assertEqual(sum(line["so"] for line in data["batting"][AWAY]), data["batting_totals"][AWAY]["so"])
        self.assertEqual(data["pitching"][HOME][0]["player"]["id"], self.box.pitching[HOME][0].player.id)
        self.assertEqual(data["pitching"][HOME][0]["ip"], self.box.pitching[HOME][0].ip)
        self.assertEqual(data["decisions"]["win"]["id"], self.box.win.id)
        self.assertEqual(data["decisions"]["loss"]["id"], self.box.loss.id)
        self.assertIn("HR", [note["label"] for note in data["notes"]])

    def test_box_score_of_an_unopened_game_is_empty(self):
        unopened = models.ScheduleGame.objects.filter(series__slot__season=SEASON, opened_at__isnull=True).first()
        data = game_reads.get_box_score(unopened.id)
        self.assertEqual(data["game"]["status"], "scheduled")
        self.assertIsNone(data["batting"])

    # Standings and team season

    def test_standings_show_the_winner_and_the_runs(self):
        data = game_reads.get_standings(season=SEASON)
        rows = {
            row["team"]["abbreviation"]: row
            for conference in data["conferences"]
            for division in conference["divisions"]
            for row in division["teams"]
        }
        winner = rows[self.home.team.abbreviation]
        loser = rows[self.road.team.abbreviation]
        self.assertEqual((winner["wins"], winner["losses"]), (1, 0))
        self.assertEqual((loser["wins"], loser["losses"]), (0, 1))
        self.assertEqual(winner["runs_scored"], self.game.home_score)
        self.assertEqual(loser["runs_allowed"], self.game.home_score)
        self.assertEqual(winner["pct"], "1.000")
        self.assertTrue(all("wild_card" in conference for conference in data["conferences"]))

    def test_team_season_lists_results_record_and_totals(self):
        data = game_reads.get_team_season(abbreviation=self.home.team.abbreviation, season=SEASON)
        self.assertEqual(data["record"]["wins"], 1)
        self.assertEqual(data["record"]["runs_scored"], self.game.home_score)
        self.assertEqual(data["standing"]["place"], "1st")
        self.assertEqual(len(data["results"]), 1)
        result = data["results"][0]
        self.assertEqual(result["game_id"], self.game.id)
        self.assertEqual(result["outcome"], "W")
        self.assertTrue(result["home"])
        self.assertEqual(result["opponent"], self.road.team.abbreviation)
        self.assertEqual(data["totals"]["batting"]["hr"], self.box.batting_totals[HOME]["hr"])

    def test_team_season_defaults_to_the_owners_team(self):
        data = game_reads.get_team_season(season=SEASON, owner=self.owner)
        self.assertEqual(data["team"]["abbreviation"], self.road.team.abbreviation)
        self.assertEqual(data["results"][0]["outcome"], "L")

    # Sim stats, leaders and usage

    def test_sim_stats_sorted_by_homers_lead_with_the_home_leadoff_man(self):
        data = game_reads.list_sim_stats(season=SEASON, kind="batting", sort="hr")
        top = data["players"][0]
        self.assertEqual(top["player"]["id"], self.home.hitters[0].id)
        self.assertEqual(top["batting"]["hr"], self.box.batting[HOME][0].hr)
        self.assertIsNone(top["pitching"])

    def test_sim_stats_for_one_team_and_kind(self):
        data = game_reads.list_sim_stats(season=SEASON, team=self.home.team.abbreviation, kind="pitching")
        ids = {row["player"]["id"] for row in data["players"]}
        self.assertEqual(ids, {line.player.id for line in self.box.pitching[HOME]})
        self.assertTrue(all(row["pitching"]["gs"] in (0, 1) for row in data["players"]))

    def test_sim_stats_for_one_player(self):
        starter = self.box.pitching[AWAY][0].player
        data = game_reads.list_sim_stats(season=SEASON, player_id=starter.id)
        self.assertEqual(len(data["players"]), 1)
        self.assertEqual(data["players"][0]["pitching"]["gs"], 1)
        self.assertEqual(data["players"][0]["pitching"]["l"], 1)

    def test_sim_stats_ascending_and_minimums(self):
        data = game_reads.list_sim_stats(season=SEASON, kind="pitching", sort="era", order="asc", min_ip=1)
        eras = [row["pitching"]["era"] for row in data["players"]]
        self.assertEqual(eras, sorted(eras))
        self.assertTrue(all(row["pitching"]["ip"] >= 1 for row in data["players"]))

    def test_leaders(self):
        data = game_reads.get_sim_leaders(season=SEASON, limit=3)
        boards = {board["key"]: board for board in data["batting"]}
        self.assertEqual(boards["hr"]["leaders"][0]["player"]["id"], self.home.hitters[0].id)
        self.assertTrue(all(len(board["leaders"]) <= 3 for board in data["batting"] + data["pitching"]))

    def test_usage_counts_both_starters(self):
        data = game_reads.get_usage(season=SEASON, team=self.road.team.abbreviation)
        starter = self.box.pitching[AWAY][0].player.id
        rows = {row["player"]["id"]: row for row in data["players"]}
        self.assertEqual(rows[starter]["starts"], 1)
        self.assertTrue(all(row["player"]["team"] == self.road.team.abbreviation for row in data["players"]))

    # The same reads through the JSON API and the MCP tools

    def test_json_api(self):
        abbr = self.home.team.abbreviation
        paths = {
            "/api/mcp/v1/games/": dict(season=SEASON, team=abbr),
            f"/api/mcp/v1/games/{self.game.id}/box-score/": {},
            "/api/mcp/v1/standings/": dict(season=SEASON),
            "/api/mcp/v1/sim-stats/": dict(season=SEASON, sort="hr"),
            "/api/mcp/v1/sim-leaders/": dict(season=SEASON),
            f"/api/mcp/v1/teams/{abbr}/season/": dict(season=SEASON),
            "/api/mcp/v1/team-season/": dict(season=SEASON),
            "/api/mcp/v1/usage/": dict(season=SEASON, team=abbr),
        }
        for path, params in paths.items():
            resp = self._get(path, **params)
            self.assertEqual(resp.status_code, 200, path)
        self.assertEqual(self._get(f"/api/mcp/v1/games/{self.game.id}/box-score/").json()["totals"][HOME]["r"], self.game.home_score)
        self.assertEqual(self._get("/api/mcp/v1/team-season/", season=SEASON).json()["team"]["abbreviation"], self.road.team.abbreviation)
        with self.assertLogs("django.request", "WARNING"):
            self.assertEqual(self.client.get("/api/mcp/v1/standings/").status_code, 401)

    async def test_mcp_tools(self):
        mcp = build_mcp(mode="local")
        names = {tool.name for tool in await mcp.list_tools()}
        self.assertTrue(GAME_TOOLS <= names)
        owner_token = set_current_owner(self.owner)
        try:
            games = _tool_text(await mcp.call_tool("list_games", {"season": SEASON, "team": self.home.team.abbreviation}))
            box = _tool_text(await mcp.call_tool("get_box_score", {"game_id": self.game.id}))
            mine = _tool_text(await mcp.call_tool("get_team_season", {"season": SEASON}))
            stats = _tool_text(await mcp.call_tool("list_sim_stats", {"season": SEASON, "sort": "hr"}))
            standings = _tool_text(await mcp.call_tool("get_standings", {"season": SEASON}))
            leaders = _tool_text(await mcp.call_tool("get_sim_leaders", {"season": SEASON}))
            usage_rows = _tool_text(await mcp.call_tool("get_usage", {"season": SEASON}))
        finally:
            reset_current_owner(owner_token)
        self.assertEqual(games["games"][0]["id"], self.game.id)
        self.assertEqual(box["totals"][HOME]["r"], self.game.home_score)
        self.assertEqual(mine["team"]["abbreviation"], self.road.team.abbreviation)
        self.assertEqual(stats["players"][0]["player"]["id"], self.home.hitters[0].id)
        self.assertEqual(len(standings["conferences"]), 2)
        self.assertTrue(leaders["batting"])
        self.assertTrue(usage_rows["players"])


    @override_settings(ALLOWED_HOSTS=["*"])
    async def test_https_box_score(self):
        async def not_mcp(scope, receive, send):
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        app = create_site_asgi_application(not_mcp)
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.raw}",
        }
        call = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_box_score", "arguments": {"game_id": self.game.id}},
        }
        with self.assertLogs("mcp.server", "INFO"), self.assertLogs("httpx", "INFO"):
            async with app.router.lifespan_context(app):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post("/mcp", headers=headers, json=call)
        self.assertEqual(response.status_code, 200, response.text)
        payload = json.loads(response.json()["result"]["content"][0]["text"])
        self.assertEqual(payload["totals"][HOME]["r"], self.game.home_score)
        self.assertTrue(payload["final"])


class GameReadEdgesTestCase(TestCase):
    """A scored series with one final log, a game left open, and the reads' errors."""

    def setUp(self):
        self.season = utils.league_season()
        self.home = models.Team.objects.create(city="Boston", abbreviation="BOS", nickname="Beans", division="Rickey")
        self.road = models.Team.objects.create(city="New York", abbreviation="NYK", nickname="Knights", division="Rickey")
        self.player = models.Player.objects.create(name="Sim Starter", position="P", team=self.home)
        self.games = sim_fixtures.create_played_season(self.season, self.home, self.road, self.player)
        user = User.objects.create_user(username="edge-owner")
        self.owner = models.Owner.objects.create(user=user, name="Edge Owner")
        self.raw, _ = models.OwnerAPIToken.create_token(self.owner, label="tests")

    def test_the_season_defaults_to_the_league_season(self):
        data = game_reads.list_games()
        self.assertEqual(data["season"], self.season)
        self.assertEqual([g["id"] for g in data["games"]], [self.games[0].id])

    def test_an_opened_game_without_a_final_is_in_progress(self):
        game, unopened = self.games[1], self.games[2]
        models.ScheduleGame.objects.filter(pk=game.pk).update(home_score=None, road_score=None)
        models.ScheduleGame.objects.filter(pk=unopened.pk).update(home_score=None, road_score=None, opened_at=None)
        models.GameLog.objects.create(game=game, state={"status": "in_progress"})
        data = game_reads.list_games(status="in_progress")
        self.assertEqual([g["id"] for g in data["games"]], [game.id])
        self.assertIsNone(data["games"][0]["winner"])

    def test_an_unknown_game_or_team_is_not_found(self):
        with self.assertRaises(game_reads.NotFound):
            game_reads.get_box_score(999999)
        with self.assertRaises(game_reads.NotFound):
            game_reads.list_games(team="ZZZ")
        with self.assertRaises(game_reads.NotFound):
            game_reads.get_team_season(season=self.season, owner=self.owner)

    def test_a_bad_status_or_kind_is_refused(self):
        with self.assertRaises(ValueError):
            game_reads.list_games(status="postponed")
        with self.assertRaises(ValueError):
            game_reads.list_sim_stats(kind="fielding")

    def test_json_api_errors(self):
        client = Client()
        auth = {"HTTP_AUTHORIZATION": f"Bearer {self.raw}"}
        with self.assertLogs("django.request", "WARNING") as logged:
            self.assertEqual(client.get("/api/mcp/v1/games/999999/box-score/", **auth).status_code, 404)
            self.assertEqual(client.get("/api/mcp/v1/teams/ZZZ/season/", **auth).status_code, 404)
            self.assertEqual(client.get("/api/mcp/v1/team-season/", **auth).status_code, 404)
            resp = client.get("/api/mcp/v1/games/", data={"status": "postponed"}, **auth)
        self.assertEqual(len(logged.records), 4)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("status", resp.json()["error"])

    async def test_mcp_tool_errors_come_back_as_json(self):
        mcp = build_mcp(mode="local")
        missing = _tool_text(await mcp.call_tool("get_box_score", {"game_id": 999999}))
        bad = _tool_text(await mcp.call_tool("list_games", {"status": "postponed"}))
        self.assertEqual(missing["status"], 404)
        self.assertEqual(bad["status"], 400)

    def test_remote_tools_are_registered(self):
        import asyncio

        mcp = build_mcp(mode="remote")
        names = {tool.name for tool in asyncio.run(mcp.list_tools())}
        self.assertTrue(GAME_TOOLS <= names)
