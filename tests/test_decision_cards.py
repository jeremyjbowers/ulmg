# ABOUTME: Tests the cards a manager reads while setting lineups and starters.
# ABOUTME: Plate appearances, the reliever innings table, speed, and the pale good-to-bad wash.

from django.test import TestCase

from ulmg import decision_cards, models, usage


class DecisionCardTestCase(TestCase):
    def player(self, name, position="OF"):
        return models.Player.objects.create(name=name, position=position, level="V", bats="L", throws="R")

    def test_a_hitter_past_550_plate_appearances_is_unlimited(self):
        player = self.player("Slugger")
        card = models.Card.objects.create(
            player=player,
            season=2026,
            plate_appearances=600,
            wrc_plus=140,
            spd=6.4,
            hitter_rates={
                "k": 0.2, "bb": 0.1, "hbp": 0.01, "single": 0.15,
                "double": 0.05, "triple": 0.005, "hr": 0.04,
            },
            defense={"CF": 3.5, "LF": -1.2},
        )
        shown = decision_cards.hitter_card(player, {"pa": 600, "ab": 520, "war": 4.2}, card)
        self.assertEqual(shown["pa_label"], "unlimited")
        self.assertEqual(shown["war_label"], "4.2")
        self.assertEqual(shown["wrc_label"], "140")
        self.assertEqual(shown["shade"], decision_cards.hitter_shade(140))
        self.assertIn("/", shown["slash"])
        self.assertIn("CF +3.5", shown["defense_label"])
        self.assertIn("LF -1.2", shown["defense_label"])
        self.assertEqual(shown["speed_label"], "+1")
        self.assertEqual(shown["positions"], ["1B", "LF", "CF", "RF", "DH"])

    def test_a_hitter_under_the_cap_shows_his_plate_appearances(self):
        player = self.player("Part time")
        shown = decision_cards.hitter_card(player, {"pa": 400, "ab": 360}, None)
        self.assertEqual(shown["pa_label"], "400")
        self.assertEqual(shown["speed_label"], "-")
        self.assertIsNone(shown["shade"])

    def test_speed_is_whole_steps_from_an_average_five(self):
        self.assertEqual(decision_cards.speed_label(1.5), "-4")
        self.assertEqual(decision_cards.speed_label(4), "-1")
        self.assertEqual(decision_cards.speed_label(5), "0")
        self.assertEqual(decision_cards.speed_label(6), "+1")
        self.assertEqual(decision_cards.speed_label(8), "+3")
        self.assertEqual(decision_cards.speed_label(None), "-")

    def test_eligibility_follows_the_primary_position(self):
        infielder = self.player("Shortstop", position="SS")
        card = models.Card.objects.create(
            player=infielder, season=2026, primary_position="SS",
            defense={"SS": -12.0, "CF": 1.0, "C": 2.0},
        )
        shown = decision_cards.hitter_card(infielder, {}, card)
        self.assertIn("SS -12.0", shown["defense_label"])
        self.assertIn("CF -4.0", shown["defense_label"])
        self.assertIn("C +2.0", shown["defense_label"])
        self.assertEqual(shown["positions"], ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"])

        outfielder = self.player("Center", position="CF")
        card = models.Card.objects.create(
            player=outfielder, season=2026, primary_position="CF",
            defense={"CF": 3.0, "SS": -8.0, "1B": 6.0},
        )
        shown = decision_cards.hitter_card(outfielder, {}, card)
        self.assertIn("CF +3.0", shown["defense_label"])
        self.assertIn("1B +6.0", shown["defense_label"])
        self.assertNotIn("SS", shown["defense_label"])
        self.assertEqual(shown["positions"], ["1B", "LF", "CF", "RF", "DH"])

        catcher = self.player("Backstop", position="C")
        card = models.Card.objects.create(
            player=catcher, season=2026, primary_position="C",
            defense={"C": 4.0, "1B": 0.0, "LF": -1.0},
        )
        shown = decision_cards.hitter_card(catcher, {}, card)
        self.assertEqual(shown["defense_label"], "C +4.0, 1B 0.0")
        self.assertNotIn("LF", shown["defense_label"])
        self.assertEqual(shown["positions"], ["C", "1B", "DH"])

    def test_a_reliever_shows_the_innings_max_from_the_rules(self):
        player = self.player("Reliever", position="P")
        above_60 = {"g": 60, "gs": 0, "ip": "65.0", "relief_minusip": "65.0", "xfip": 3.21, "war": 1.25, "k_9": 9.4, "bb_9": 2.2}
        shown = decision_cards.pitcher_card(player, above_60, None)
        cap = usage.outs_to_innings(usage.reliever_innings_cap(usage.innings_to_outs("65.0")))
        self.assertEqual(shown["starts_label"], "0 GS")
        self.assertEqual(shown["innings_label"], f"65.0 IP (max {cap})")
        self.assertEqual(cap, "81.0")
        self.assertEqual(shown["xfip_label"], "3.21")
        self.assertEqual(shown["k9_label"], "9.4")
        self.assertEqual(shown["bb9_label"], "2.2")
        self.assertEqual(shown["shade"], decision_cards.pitcher_shade(3.21))
        self.assertEqual(shown["designation"], usage.BULLPEN)

        above_70 = {"g": 70, "gs": 0, "ip": "80.0", "relief_minusip": "80.0"}
        shown = decision_cards.pitcher_card(player, above_70, None)
        cap = usage.outs_to_innings(usage.reliever_innings_cap(usage.innings_to_outs("80.0")))
        self.assertEqual(shown["innings_label"], f"80.0 IP (max {cap})")
        self.assertEqual(cap, "120.0")

    def test_a_starter_shows_his_start_max_and_not_a_relief_innings_max(self):
        player = self.player("Starter", position="P")
        shown = decision_cards.pitcher_card(
            player, {"g": 32, "gs": 32, "ip": "190.0", "start_minusip": "190.0", "war": 3}, None
        )
        self.assertEqual(shown["starts_label"], "32 GS (max 34)")
        self.assertEqual(shown["innings_label"], "190.0 IP")
        self.assertEqual(shown["designation"], usage.ROTATION)

    def test_the_wash_runs_from_a_pale_green_to_a_light_pink(self):
        self.assertIsNone(decision_cards.hitter_shade(100))
        self.assertIsNone(decision_cards.pitcher_shade(4.10))
        self.assertIsNone(decision_cards.hitter_shade(None))
        self.assertIsNone(decision_cards.pitcher_shade(""))
        green = decision_cards.hitter_shade(160)
        pink = decision_cards.hitter_shade(40)
        self.assertEqual(green, decision_cards.shade_color(1))
        self.assertEqual(pink, decision_cards.shade_color(-1))
        self.assertEqual(decision_cards.pitcher_shade(2.5), green)
        self.assertEqual(decision_cards.pitcher_shade(6.0), pink)
        for color in (green, pink):
            channels = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
            self.assertTrue(all(channel >= 190 for channel in channels), color)
        modest = decision_cards.hitter_shade(112)
        red, green_channel, _ = [int(modest[i:i + 2], 16) for i in (1, 3, 5)]
        self.assertIsNotNone(modest)
        self.assertNotEqual(modest, green)
        self.assertGreater(green_channel, red)

    def test_the_starter_or_reliever_button_follows_the_stored_designation(self):
        self.assertEqual(decision_cards.shown_designation({"g": 60, "gs": 0}, None), usage.BULLPEN)
        self.assertEqual(decision_cards.shown_designation({"g": 32, "gs": 32}, None), usage.ROTATION)
        self.assertEqual(decision_cards.shown_designation({"g": 40, "gs": 8}, None), usage.ROTATION)
        self.assertEqual(decision_cards.shown_designation({"g": 60, "gs": 0}, False), usage.BULLPEN)
        self.assertEqual(decision_cards.shown_designation({"g": 32, "gs": 32}, True), usage.BULLPEN)
        self.assertEqual(decision_cards.shown_designation({}, None), usage.ROTATION)
        player = self.player("Named", position="P")
        shown = decision_cards.pitcher_card(player, {"g": 60, "gs": 0}, None, designation=usage.ROTATION)
        self.assertEqual(shown["designation"], usage.ROTATION)
