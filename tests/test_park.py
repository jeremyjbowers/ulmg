# ABOUTME: Tests the home field: which park a team plays in, the scores the sim reads, and the rules and plate a builder stores.
# ABOUTME: Uses real venue rows for the team link, and plain objects for the score and sprite contract.

from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from ulmg import models, park


def _venue(**kwargs):
    blank = {
        "name": "",
        "rules": {},
        "sprites": {},
        "park_factor": None,
        "pf_runs": None,
        "pf_1b": None,
        "pf_2b": None,
        "pf_3b": None,
        "pf_hr": None,
    }
    blank.update(kwargs)
    return SimpleNamespace(**blank)


def _team(abbreviation, venue=None):
    return SimpleNamespace(
        abbreviation=abbreviation,
        pk=None,
        home_field_id=1 if venue is not None else None,
        home_field=venue,
    )


class FieldContractTest(SimpleTestCase):
    def test_a_field_with_no_rules_is_the_generic_park(self):
        drawn = park.rules(_venue())
        self.assertEqual(drawn["distances_ft"]["lf_line"], 330)
        self.assertEqual(drawn["distances_ft"]["left_center"], 380)
        self.assertEqual(drawn["distances_ft"]["center"], 400)
        self.assertEqual(drawn["wall_ft"]["rf_line"], 8)
        self.assertEqual(drawn["foul_ft"], 52)
        self.assertEqual(drawn["surface"], "grass")
        self.assertEqual(drawn["roof"], "open")
        self.assertEqual(drawn["ground_rules"], "")

    def test_stored_dimensions_override_the_generic_park_and_the_rest_stay(self):
        drawn = park.rules(_venue(rules={
            "distances_ft": {"center": 415, "lf_line": 347},
            "wall_ft": {"lf_line": 37},
            "foul_ft": 40,
            "surface": "turf",
            "roof": "dome",
            "ground_rules": "The catwalk is in play.",
        }))
        self.assertEqual(drawn["distances_ft"]["center"], 415)
        self.assertEqual(drawn["distances_ft"]["lf_line"], 347)
        self.assertEqual(drawn["distances_ft"]["rf_line"], 330)
        self.assertEqual(drawn["wall_ft"]["lf_line"], 37)
        self.assertEqual(drawn["wall_ft"]["center"], 8)
        self.assertEqual(drawn["foul_ft"], 40)
        self.assertEqual(drawn["surface"], "turf")
        self.assertEqual(drawn["roof"], "dome")
        self.assertEqual(drawn["ground_rules"], "The catwalk is in play.")

    def test_a_rule_that_is_not_a_park_rule_is_ignored(self):
        drawn = park.rules(_venue(rules={"surface": "ice", "roof": "tent", "foul_ft": 0, "distances_ft": {"center": -5}}))
        self.assertEqual(drawn["surface"], "grass")
        self.assertEqual(drawn["roof"], "open")
        self.assertEqual(drawn["foul_ft"], 52)
        self.assertEqual(drawn["distances_ft"]["center"], 400)

    def test_a_plate_is_inner_svg_and_a_script_is_not_a_plate(self):
        plate = park.sprites(_venue(sprites={
            "version": 2,
            "plate_svg": '<svg viewBox="0 0 320 180"><g id="coors-plate"></g></svg>',
        }))
        self.assertEqual(plate["version"], 2)
        self.assertEqual(plate["plate_svg"], '<g id="coors-plate"></g>')

        refused = park.sprites(_venue(sprites={"version": 2, "plate_svg": '<g></g><script>alert(1)</script>'}))
        self.assertEqual(refused["version"], 2)
        self.assertIsNone(refused["plate_svg"])
        self.assertIsNone(park.sprites(_venue(sprites={"plate_svg": '<g onload="alert(1)"></g>'}))["plate_svg"])
        self.assertIsNone(park.sprites(_venue())["plate_svg"])
        self.assertIsNone(park.sprites(_venue(sprites={"version": True}))["version"])

    def test_event_scores_become_the_factors_the_sim_reads(self):
        team = _team("COL", _venue(park_factor=115, pf_runs=132, pf_1b=110, pf_2b=130, pf_3b=177, pf_hr=119))
        self.assertEqual(park.engine_park(team), {
            "id": "park-col",
            "run_factor": 115 / 100,
            "single_factor": 110 / 100,
            "double_factor": 130 / 100,
            "triple_factor": 177 / 100,
            "hr_factor": 119 / 100,
        })

    def test_a_runs_index_is_the_fallback_and_a_blank_event_is_omitted(self):
        team = _team("TB", _venue(pf_runs=90, pf_hr=95))
        got = park.engine_park(team)
        self.assertEqual(got["run_factor"], 90 / 100)
        self.assertEqual(got["hr_factor"], 95 / 100)
        self.assertNotIn("single_factor", got)
        self.assertNotIn("double_factor", got)

    def test_a_team_with_no_field_plays_at_average(self):
        self.assertEqual(park.engine_park(_team("HCH")), {"id": "park-hch", "run_factor": 1.0})
        shown = park.art(_team("HCH"))
        self.assertEqual(shown["name"], "")
        self.assertEqual(shown["scores"], {})
        self.assertEqual(shown["rules"]["distances_ft"]["center"], 400)
        self.assertIsNone(shown["sprites"]["plate_svg"])


class HomeFieldTest(TestCase):
    def test_the_home_field_wins_and_a_pointed_venue_is_the_fallback(self):
        club = models.Team.objects.create(abbreviation="COL", city="Denver", nickname="Bears")
        other = models.Venue.objects.create(
            team=club, name="Old Park", mlb_team="X", mlb_venue_id="old", mlb_venue_url="u", park_factor=90,
        )
        home = models.Venue.objects.create(
            name="Coors Field", mlb_team="Rockies", mlb_venue_id="19", mlb_venue_url="u",
            park_factor=115, pf_hr=119,
        )
        self.assertEqual(park.home_venue(club).name, "Old Park")
        self.assertEqual(park.engine_park(club)["run_factor"], 90 / 100)

        club.home_field = home
        club.save()
        home.refresh_from_db()
        club.refresh_from_db()
        self.assertEqual(home.team_id, club.id)
        self.assertEqual(park.home_venue(club).name, "Coors Field")
        self.assertEqual(park.engine_park(club)["hr_factor"], 119 / 100)
        self.assertNotEqual(park.home_venue(club).id, other.id)
