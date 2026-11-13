# ABOUTME: Tests the Baseball Savant park-factor loader: the page parser, the venue columns, and a live load.
# ABOUTME: The page fixture is a real leaderboard row. The live test reads the current Savant page.

import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from ulmg import models
from ulmg.park_factors import parks_from_html, venue_defaults

# Coors Field, 2025, from the Statcast park-factor leaderboard.
COORS = {
    "venue_id": "19",
    "venue_name": "Coors Field",
    "name_display_club": "Rockies",
    "index_woba": "115",
    "index_wobacon": "115",
    "index_xwobacon": "102",
    "index_runs": "132",
    "index_obp": "113",
    "index_hits": "120",
    "index_1b": "118",
    "index_2b": "126",
    "index_3b": "200",
    "index_hr": "110",
    "index_bb": "99",
    "index_so": "89",
    "year_range": "2025",
    "n_pa": "17969",
}


def _page(rows):
    return "<html><script>var data = " + json.dumps(rows) + ";</script></html>"


class ParkFactorParseTest(SimpleTestCase):
    def test_the_leaderboard_script_is_the_park_table(self):
        parks = parks_from_html(_page([COORS, {**COORS, "venue_id": "2", "venue_name": "Petco Park"}]))
        self.assertEqual([park["venue_name"] for park in parks], ["Coors Field", "Petco Park"])

    def test_a_page_without_the_table_is_refused(self):
        with self.assertRaises(ValueError):
            parks_from_html("<html><script>var other = 1;</script></html>")

    def test_indexes_become_the_venue_columns(self):
        defaults = venue_defaults(COORS)
        self.assertEqual(defaults["name"], "Coors Field")
        self.assertEqual(defaults["mlb_team"], "Rockies")
        self.assertEqual(defaults["park_factor"], 115)
        self.assertEqual(defaults["pf_wobacon"], 115)
        self.assertEqual(defaults["pf_runs"], 132)
        self.assertEqual(defaults["pf_1b"], 118)
        self.assertEqual(defaults["pf_2b"], 126)
        self.assertEqual(defaults["pf_3b"], 200)
        self.assertEqual(defaults["pf_hr"], 110)
        self.assertEqual(defaults["pf_bb"], 99)
        self.assertEqual(defaults["pf_so"], 89)
        self.assertEqual(defaults["pf_pa"], 17969)
        self.assertEqual(defaults["pf_years"], "2025")
        self.assertIn("venueId=19", defaults["mlb_venue_url"])

    def test_a_missing_index_stays_unscored(self):
        row = {**COORS, "index_3b": None, "index_hr": ""}
        defaults = venue_defaults(row)
        self.assertIsNone(defaults["pf_3b"])
        self.assertIsNone(defaults["pf_hr"])


class ParkFactorLoadTest(TestCase):
    def test_a_saved_page_updates_the_venue_and_leaves_the_rest(self):
        team = models.Team.objects.create(city="Denver", abbreviation="COL", nickname="Bears")
        venue = models.Venue.objects.create(
            name="Coors Field",
            mlb_team="Rockies",
            mlb_venue_id="19",
            mlb_venue_url="https://example.test/old",
            team=team,
            rules={"roof": "open"},
            sprites={"plate_svg": "<g></g>"},
            park_factor=100,
        )
        page = self._page("update", _page([{**COORS, "index_runs": "125", "year_range": "2023-2025"}]))

        out = StringIO()
        call_command("load_park_factors", file=str(page), rolling=1, year=2025, stdout=out)
        self.assertIn("Stored 1 park for 2023-2025.", out.getvalue())

        venue.refresh_from_db()
        self.assertEqual(models.Venue.objects.filter(mlb_venue_id="19").count(), 1)
        self.assertEqual(venue.park_factor, 115)
        self.assertEqual(venue.pf_runs, 125)
        self.assertEqual(venue.pf_years, "2023-2025")
        self.assertEqual(venue.team_id, team.id)
        self.assertEqual(venue.rules, {"roof": "open"})
        self.assertEqual(venue.sprites, {"plate_svg": "<g></g>"})

    def test_a_dry_run_writes_nothing(self):
        page = self._page("dry", _page([COORS]))
        out = StringIO()
        call_command("load_park_factors", file=str(page), dry_run=True, stdout=out)
        self.assertIn("Would store 1 park for 2025.", out.getvalue())
        self.assertEqual(models.Venue.objects.count(), 0)

    def test_a_file_without_the_table_is_an_error(self):
        page = self._page("empty", "<html></html>")
        with self.assertRaises(CommandError):
            call_command("load_park_factors", file=str(page))

    def _page(self, name, html):
        folder = Path(tempfile.mkdtemp())
        path = folder / f"{name}.html"
        path.write_text(html)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path


class ParkFactorLiveTest(TestCase):
    def test_the_savant_leaderboard_loads_coors(self):
        out = StringIO()
        call_command("load_park_factors", year=2025, rolling=3, stdout=out)
        self.assertIn("2023-2025", out.getvalue())
        coors = models.Venue.objects.get(mlb_venue_id="19")
        self.assertEqual(coors.name, "Coors Field")
        self.assertGreater(coors.pf_runs, 110)
        self.assertGreater(coors.pf_hr, 100)
        self.assertEqual(coors.pf_years, "2023-2025")
        self.assertGreater(models.Venue.objects.count(), 20)
