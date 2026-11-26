# ABOUTME: Tests the stadium dimension file and load_park_dimensions, which writes each park's rules onto its Venue.
# ABOUTME: Uses the checked-in data file and real Venue rows matched by MLB venue id.

import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from ulmg import models, park

FENWAY = "3"
COORS = "19"


def _venue(venue_id, name, **fields):
    return models.Venue.objects.create(
        name=name,
        mlb_team=name,
        mlb_venue_id=venue_id,
        mlb_venue_url=f"https://example.test/{venue_id}",
        **fields,
    )


class DimensionFileTest(SimpleTestCase):
    def setUp(self):
        self.parks = park.dimension_file()

    def test_the_file_holds_thirty_parks_keyed_by_mlb_venue_id(self):
        self.assertEqual(len(self.parks), 30)
        for venue_id, entry in self.parks.items():
            self.assertTrue(venue_id.isdigit(), venue_id)
            self.assertTrue(entry["name"], venue_id)

    def test_every_park_has_five_distances_and_walls_inside_real_bounds(self):
        for venue_id, entry in self.parks.items():
            for key in park.DISTANCE_KEYS:
                distance = entry["distances_ft"][key]
                wall = entry["wall_ft"][key]
                if key in ("lf_line", "rf_line"):
                    self.assertTrue(300 <= distance <= 360, (entry["name"], key, distance))
                else:
                    self.assertTrue(355 <= distance <= 425, (entry["name"], key, distance))
                self.assertTrue(3 <= wall <= 40, (entry["name"], key, wall))
            self.assertIn(entry["surface"], park.SURFACES)
            self.assertIn(entry["roof"], park.ROOFS)

    def test_every_park_survives_the_rules_validation_unchanged(self):
        for venue_id, entry in self.parks.items():
            cleaned = park.clean_rules(entry)
            for key in ("distances_ft", "wall_ft", "surface", "roof", "ground_rules"):
                self.assertEqual(cleaned[key], entry.get(key, park.DEFAULT_RULES[key]), (entry["name"], key))

    def test_every_park_has_a_traced_fence_through_its_five_distances(self):
        angles = {"lf_line": -45, "left_center": -22.5, "center": 0, "right_center": 22.5, "rf_line": 45}
        for venue_id, entry in self.parks.items():
            fence = entry["fence_ft"]
            self.assertEqual(park.clean_rules(entry)["fence_ft"], fence, entry["name"])
            self.assertGreater(len(fence), 5, entry["name"])
            traced = dict((degrees, feet) for degrees, feet in fence)
            for key, degrees in angles.items():
                self.assertEqual(traced[degrees], entry["distances_ft"][key], (entry["name"], key))
            for degrees, feet in fence:
                self.assertTrue(280 <= feet <= 450, (entry["name"], degrees, feet))

    def test_fenway_s_wall_turns_sharply_out_from_the_short_right_field_pole(self):
        fence = dict((degrees, feet) for degrees, feet in self.parks[FENWAY]["fence_ft"])
        pole = fence[45]
        near = [feet for degrees, feet in fence.items() if 30 <= degrees < 45]
        self.assertTrue(near, "points between right-center and the pole")
        self.assertGreater(max(near) - pole, 60, "the bullpen corner is far deeper than the pole")

    def test_fenway_has_the_wall_in_left_and_a_note_about_it(self):
        fenway = self.parks[FENWAY]
        self.assertEqual(fenway["name"], "Fenway Park")
        self.assertEqual(fenway["wall_ft"]["lf_line"], 37)
        self.assertEqual(fenway["distances_ft"]["rf_line"], 302)
        self.assertIn("Monster", fenway["ground_rules"])


class LoadParkDimensionsTest(TestCase):
    def test_parks_are_matched_by_venue_id_and_their_rules_written(self):
        fenway = _venue(FENWAY, "Fenway Park", pf_hr=97, sprites={"plate_svg": "<g></g>"})
        coors = _venue(COORS, "Coors Field", rules={"foul_ft": 40})
        out = StringIO()
        call_command("load_park_dimensions", stdout=out)
        fenway.refresh_from_db()
        coors.refresh_from_db()
        self.assertEqual(fenway.rules["wall_ft"]["lf_line"], 37)
        self.assertEqual(fenway.rules["distances_ft"]["rf_line"], 302)
        self.assertIn("Monster", fenway.rules["ground_rules"])
        self.assertEqual(fenway.pf_hr, 97, "the park scores are left alone")
        self.assertEqual(fenway.sprites, {"plate_svg": "<g></g>"})
        self.assertEqual(coors.rules["distances_ft"]["center"], 415)
        self.assertEqual(fenway.rules["fence_ft"], park.dimension_file()[FENWAY]["fence_ft"])
        self.assertEqual(coors.rules["foul_ft"], 40, "a stored foul distance the file does not set stays")
        text = out.getvalue()
        self.assertIn("Stored dimensions for 2 parks.", text)
        self.assertIn("28 parks in the file have no venue", text)
        self.assertIn("Wrigley Field (17)", text)

    def test_a_dry_run_reports_and_writes_nothing(self):
        fenway = _venue(FENWAY, "Fenway Park")
        out = StringIO()
        call_command("load_park_dimensions", dry_run=True, stdout=out)
        fenway.refresh_from_db()
        self.assertEqual(fenway.rules, {})
        self.assertIn("Would store dimensions for 1 park.", out.getvalue())
        self.assertIn("Fenway Park", out.getvalue())

    def test_a_venue_with_a_name_in_the_file_but_another_id_is_not_guessed(self):
        _venue("9999", "Fenway Park")
        out = StringIO()
        call_command("load_park_dimensions", stdout=out)
        self.assertEqual(models.Venue.objects.get(mlb_venue_id="9999").rules, {})
        self.assertIn("Stored dimensions for 0 parks.", out.getvalue())

    def test_an_entry_the_validation_rejects_is_reported(self):
        _venue(FENWAY, "Fenway Park")
        folder = Path(tempfile.mkdtemp())
        path = folder / "bad.json"
        path.write_text(json.dumps({FENWAY: {"name": "Fenway Park", "surface": "ice", "distances_ft": {"center": 390}}}))
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        out = StringIO()
        call_command("load_park_dimensions", file=str(path), stdout=out)
        venue = models.Venue.objects.get(mlb_venue_id=FENWAY)
        self.assertEqual(venue.rules["surface"], "grass")
        self.assertEqual(venue.rules["distances_ft"]["center"], 390)
        self.assertIn("Fenway Park: surface", out.getvalue())

    def test_a_file_that_is_not_a_park_map_is_an_error(self):
        folder = Path(tempfile.mkdtemp())
        path = folder / "list.json"
        path.write_text("[]")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        with self.assertRaises(CommandError):
            call_command("load_park_dimensions", file=str(path))
