# ABOUTME: Tests the Statcast sprint-speed loader and the hitting line it writes.
# ABOUTME: The page fixture is a real 2026 leaderboard row. The live test reads the Savant page.

import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from ulmg import cards, models
from ulmg.sprint_speed import leaderboard_url, qualified_runners, runner_speed, runners_from_html

# Andrew Pinckney and Sandy León, 2026, from the Statcast sprint-speed leaderboard.
PINCKNEY = {
    "name_display_last_first": "Pinckney, Andrew",
    "speed_order": "1",
    "runner_id": 687605,
    "n": "5",
    "n_top50percent": "5",
    "r_sprint_speed_top50percent": "30.98",
    "r_sprint_speed_top50percent_pretty": "31.0",
    "timeframe": "2026",
    "n_bolts": "8",
    "position_name": "LF",
}

LEON = {
    "name_display_last_first": "León, Sandy",
    "speed_order": "612",
    "runner_id": 506702,
    "n": "11",
    "n_top50percent": "10",
    "r_sprint_speed_top50percent": "22.14",
    "r_sprint_speed_top50percent_pretty": "22.1",
    "timeframe": "2026",
    "n_bolts": None,
    "position_name": "C",
}


def _page(rows):
    return "<html><script>var data = " + json.dumps(rows) + ";</script></html>"


class SprintSpeedParseTest(SimpleTestCase):
    def test_the_leaderboard_url_is_the_qualified_board(self):
        self.assertEqual(
            leaderboard_url(2026),
            "https://baseballsavant.mlb.com/leaderboard/sprint_speed"
            "?min_season=2026&max_season=2026&position=&team=&min=5"
            "&sort=r_sprint_speed_top50percent_pretty&sortDir=desc",
        )

    def test_the_leaderboard_script_is_the_runner_table(self):
        runners = runners_from_html(_page([PINCKNEY, LEON]))
        self.assertEqual(
            [row["name_display_last_first"] for row in runners],
            ["Pinckney, Andrew", "León, Sandy"],
        )

    def test_a_page_without_the_table_is_refused(self):
        with self.assertRaises(ValueError):
            runners_from_html("<html><script>var other = 1;</script></html>")

    def test_a_runner_row_is_his_sprint_speed(self):
        speed = runner_speed(PINCKNEY)
        self.assertEqual(speed["mlbam_id"], "687605")
        self.assertEqual(speed["sprint_speed"], float("30.98"))
        self.assertEqual(speed["sprint_runs"], 5)
        self.assertEqual(speed["sprint_bolts"], 8)
        self.assertEqual(speed["name"], "Pinckney, Andrew")

        slow = runner_speed(LEON)
        self.assertEqual(slow["sprint_speed"], float("22.14"))
        self.assertEqual(slow["sprint_runs"], 11)
        self.assertIsNone(slow["sprint_bolts"])

    def test_a_runner_without_a_sprint_speed_is_skipped(self):
        blank = {**PINCKNEY, "r_sprint_speed_top50percent": None}
        nameless = {"runner_id": None, "r_sprint_speed_top50percent": "28.0"}
        self.assertEqual(qualified_runners([blank, nameless]), {})

    def test_a_repeated_runner_keeps_the_larger_sample(self):
        thick = {**PINCKNEY, "n": "40", "r_sprint_speed_top50percent": "28.5"}
        kept = qualified_runners([PINCKNEY, thick])["687605"]
        self.assertEqual(kept["sprint_speed"], float("28.5"))
        self.assertEqual(kept["sprint_runs"], 40)


class SprintSpeedLoadTest(TestCase):
    def test_a_saved_page_updates_the_hitting_line_and_leaves_the_rest(self):
        pinckney = models.Player.objects.create(name="Andrew Pinckney", position="OF", mlbam_id="687605")
        leon = models.Player.objects.create(name="Sandy León", position="C", mlbam_id="506702")
        pitcher = models.Player.objects.create(name="Bullpen Arm", position="P", mlbam_id="111")
        hitting = {"pa": 600, "spd": 4.2, "sb": 3}
        pinckney_line = models.PlayerStatSeason.objects.create(
            player=pinckney, season=2026, classification="1-mlb", hit_stats=dict(hitting)
        )
        leon_line = models.PlayerStatSeason.objects.create(
            player=leon, season=2026, classification="1-mlb", hit_stats={"pa": 80, "spd": 1.5}
        )
        models.PlayerStatSeason.objects.create(
            player=pitcher, season=2026, classification="1-mlb", pitch_stats={"ip": 40, "tbf": 160}
        )
        earlier = models.PlayerStatSeason.objects.create(
            player=pinckney, season=2025, classification="1-mlb", hit_stats={"pa": 100, "spd": 3.0}
        )
        minors = models.PlayerStatSeason.objects.create(
            player=pinckney, season=2026, classification="2-milb", hit_stats={"pa": 200, "spd": 5.0}
        )
        page = self._page("update", _page([
            PINCKNEY,
            LEON,
            {"runner_id": 111, "n": "6", "r_sprint_speed_top50percent": "26.0"},
            {"runner_id": 999999, "n": "9", "r_sprint_speed_top50percent": "27.0"},
        ]))

        out = StringIO()
        call_command("load_sprint_speed", file=str(page), year=2026, stdout=out)
        self.assertIn(
            "Stored sprint speed on 2 hitting lines for 2026. "
            "1 player had no 1-mlb hitting line. 1 runner was not in the league.",
            out.getvalue(),
        )

        pinckney_line.refresh_from_db()
        self.assertEqual(pinckney_line.hit_stats["sprint_speed"], float("30.98"))
        self.assertEqual(pinckney_line.hit_stats["sprint_runs"], 5)
        self.assertEqual(pinckney_line.hit_stats["sprint_bolts"], 8)
        self.assertEqual(pinckney_line.hit_stats["pa"], 600)
        self.assertEqual(pinckney_line.hit_stats["spd"], 4.2)
        self.assertEqual(cards.speed(pinckney_line.hit_stats), 9.0)

        leon_line.refresh_from_db()
        self.assertEqual(leon_line.hit_stats["sprint_speed"], float("22.14"))
        self.assertEqual(leon_line.hit_stats["sprint_runs"], 11)
        self.assertIsNone(leon_line.hit_stats["sprint_bolts"])
        self.assertEqual(cards.speed(leon_line.hit_stats), 0.1)

        earlier.refresh_from_db()
        minors.refresh_from_db()
        pitcher.refresh_from_db()
        self.assertNotIn("sprint_speed", earlier.hit_stats)
        self.assertNotIn("sprint_speed", minors.hit_stats)
        self.assertIsNone(pitcher.playerstatseason_set.get(season=2026).hit_stats)

    def test_a_dry_run_writes_nothing(self):
        player = models.Player.objects.create(name="Andrew Pinckney", position="OF", mlbam_id="687605")
        models.PlayerStatSeason.objects.create(
            player=player, season=2026, classification="1-mlb", hit_stats={"pa": 600, "spd": 4.2}
        )
        page = self._page("dry", _page([PINCKNEY]))
        out = StringIO()
        call_command("load_sprint_speed", file=str(page), year=2026, dry_run=True, stdout=out)
        self.assertIn(
            "Would store sprint speed on 1 hitting line for 2026. "
            "0 players had no 1-mlb hitting line. 0 runners were not in the league.",
            out.getvalue(),
        )
        stats = player.playerstatseason_set.get(season=2026).hit_stats
        self.assertNotIn("sprint_speed", stats)

    def test_a_json_file_loads_the_same_way(self):
        player = models.Player.objects.create(name="Andrew Pinckney", position="OF", mlbam_id="687605")
        models.PlayerStatSeason.objects.create(
            player=player, season=2026, classification="1-mlb", hit_stats={"pa": 600}
        )
        path = self._page("rows.json", json.dumps([PINCKNEY]))
        call_command("load_sprint_speed", file=str(path), year=2026, stdout=StringIO())
        stats = player.playerstatseason_set.get(season=2026).hit_stats
        self.assertEqual(stats["sprint_speed"], float("30.98"))

    def test_a_file_without_the_table_is_an_error(self):
        page = self._page("empty", "<html></html>")
        with self.assertRaises(CommandError):
            call_command("load_sprint_speed", file=str(page), year=2026)

    @override_settings(CURRENT_SEASON=2027, CURRENT_SEASON_TYPE="offseason")
    def test_the_default_season_is_the_current_mlb_season(self):
        player = models.Player.objects.create(name="Andrew Pinckney", position="OF", mlbam_id="687605")
        models.PlayerStatSeason.objects.create(
            player=player, season=2026, classification="1-mlb", hit_stats={"pa": 600}
        )
        models.PlayerStatSeason.objects.create(
            player=player, season=2027, classification="1-mlb", hit_stats={"pa": 10}
        )
        page = self._page("default", _page([PINCKNEY]))
        out = StringIO()
        call_command("load_sprint_speed", file=str(page), stdout=out)
        self.assertIn("for 2026.", out.getvalue())
        self.assertIn("sprint_speed", player.playerstatseason_set.get(season=2026).hit_stats)
        self.assertNotIn("sprint_speed", player.playerstatseason_set.get(season=2027).hit_stats)

    def _page(self, name, text):
        folder = Path(tempfile.mkdtemp())
        path = folder / name
        path.write_text(text)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path


class SprintSpeedLiveTest(SimpleTestCase):
    def test_the_2026_leaderboard_has_the_qualified_runners(self):
        from ulmg.sprint_speed import fetch_runners

        rows = fetch_runners(2026)
        speeds = [runner_speed(row)["sprint_speed"] for row in rows]
        self.assertGreaterEqual(len(rows), 500)
        self.assertGreater(max(speeds), 30)
        self.assertLess(min(speeds), 23)
        self.assertTrue(all(row.get("runner_id") for row in rows))
