# ABOUTME: Tests for the ULMG usage ledger in ulmg.usage: caps, per-game limits, rest, penalties and overrides.
# ABOUTME: Every test uses real players, card-season stats and scheduled games in the test database.

from django.contrib.auth.models import Permission, User
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from ulmg import models, usage
from tests.usage_fixtures import (
    ULMG_SEASON,
    create_hitter,
    create_pitcher,
    create_series,
    create_teams,
)


def walk(game, batter, pitcher, **kwargs):
    return usage.record_plate_appearance(game, batter, pitcher, at_bat=False, outs=0, **kwargs)


def strikeout(game, batter, pitcher, **kwargs):
    return usage.record_plate_appearance(game, batter, pitcher, at_bat=True, outs=1, **kwargs)


class InningsConversionTestCase(TestCase):
    def test_fangraphs_innings_convert_to_thirds(self):
        self.assertEqual(usage.innings_to_outs(175), 525)
        self.assertEqual(usage.innings_to_outs(174.2), 524)
        self.assertEqual(usage.innings_to_outs("60.1"), 181)
        self.assertEqual(usage.innings_to_outs(None), 0)

    def test_outs_display_as_innings(self):
        self.assertEqual(usage.outs_to_innings(524), "174.2")
        self.assertEqual(usage.outs_to_innings(3), "1.0")


class StarterTableTestCase(TestCase):
    def test_each_row_of_the_starter_table(self):
        rows = [
            (175, 0, 34),
            (174.2, 0, 30),
            (155, 0, 30),
            (154.2, 0, 26),
            (130, 0, 26),
            (129.2, 0, 23),
            (110, 0, 23),
            (109.2, 0, 19),
            (75, 0, 19),
            (74.2, 0, 14),
            (50, 0, 14),
            (49.2, 9, 9),
        ]
        for i, (ip, gs_floor, expected) in enumerate(rows):
            starts = max(gs_floor, 1)
            pitcher = create_pitcher(f"Starter {i}", ip=ip, g=starts, gs=starts, start_minusip=ip)
            caps = usage.card_caps(pitcher, ULMG_SEASON)
            self.assertEqual(caps["starts_cap"], max(expected, starts), msg=f"{ip} IP")
            self.assertIsNone(caps["innings_cap_outs"], msg="a pure starter has no innings cap")

    def test_real_starts_win_when_greater_than_the_table(self):
        pitcher = create_pitcher("Workhorse", ip=150, g=33, gs=33, start_minusip=150)
        self.assertEqual(usage.card_caps(pitcher, ULMG_SEASON)["starts_cap"], 33)

    def test_under_fifty_innings_is_real_starts_only(self):
        pitcher = create_pitcher("Spot Starter", ip=30, g=6, gs=6, start_minusip=30)
        self.assertEqual(usage.card_caps(pitcher, ULMG_SEASON)["starts_cap"], 6)


class RelieverTableTestCase(TestCase):
    def test_each_row_of_the_reliever_table(self):
        rows = [
            (70, 315),  # 210 outs at 150%
            (69.2, 261),  # 209 outs at 125%, rounded down
            (60, 225),  # 180 outs at 125%
            (59.2, 179),  # 179 outs at 100%
        ]
        for i, (ip, expected_outs) in enumerate(rows):
            pitcher = create_pitcher(f"Reliever {i}", ip=ip, g=60, gs=0, relief_minusip=ip)
            caps = usage.card_caps(pitcher, ULMG_SEASON)
            self.assertEqual(caps["innings_cap_outs"], expected_outs, msg=f"{ip} IP")
            self.assertEqual(caps["starts_cap"], 0)


class BatterCapTestCase(TestCase):
    def setUp(self):
        home, road = create_teams()
        self.game = create_series(home, road, length=3)[0]
        self.pitcher = create_pitcher("Mop Up", ip=80, g=60, gs=0, relief_minusip=80)

    def test_unlimited_at_five_hundred_at_bats(self):
        hitter = create_hitter("Regular", ab=500, pa=540)
        self.assertIsNone(usage.card_caps(hitter, ULMG_SEASON)["plate_appearances_cap"])

    def test_unlimited_at_five_hundred_fifty_plate_appearances(self):
        hitter = create_hitter("Walker", ab=480, pa=550)
        self.assertIsNone(usage.card_caps(hitter, ULMG_SEASON)["plate_appearances_cap"])

    def test_limited_below_both_thresholds(self):
        hitter = create_hitter("Platoon", ab=499, pa=549)
        self.assertEqual(usage.card_caps(hitter, ULMG_SEASON)["plate_appearances_cap"], 549)

    def test_plate_appearances_computed_when_payload_has_none(self):
        hitter = create_hitter("Old Payload", ab=10, bb=2, hbp=1, sf=1, sh=1)
        self.assertEqual(usage.card_caps(hitter, ULMG_SEASON)["plate_appearances_cap"], 15)

    def test_a_walk_uses_a_plate_appearance(self):
        hitter = create_hitter("Patient", ab=1, pa=2)
        walk(self.game, hitter, self.pitcher)
        check = usage.check_batter(hitter, self.game)
        self.assertTrue(check.legal)
        self.assertEqual(check.remaining["plate_appearances"], 1)
        counter = models.UsageCounter.objects.get(player=hitter, season=ULMG_SEASON)
        self.assertEqual((counter.plate_appearances, counter.at_bats), (1, 0))

    def test_at_bats_never_cap_him(self):
        hitter = create_hitter("Hacker", ab=2, pa=3)
        strikeout(self.game, hitter, self.pitcher)
        strikeout(self.game, hitter, self.pitcher)
        self.assertTrue(usage.check_batter(hitter, self.game).legal)
        strikeout(self.game, hitter, self.pitcher)
        counter = models.UsageCounter.objects.get(player=hitter, season=ULMG_SEASON)
        self.assertEqual((counter.plate_appearances, counter.at_bats), (3, 3))

    def test_batter_hits_cap_in_the_middle_of_a_game(self):
        hitter = create_hitter("Cup of Coffee", ab=2, pa=2)
        self.assertTrue(usage.check_batter(hitter, self.game).legal)
        strikeout(self.game, hitter, self.pitcher)
        strikeout(self.game, hitter, self.pitcher)
        check = usage.check_batter(hitter, self.game)
        self.assertFalse(check.legal)
        self.assertEqual(check.remaining["plate_appearances"], 0)
        self.assertIn("plate appearances", check.reason)

    def test_rejected_plate_appearance_at_the_cap(self):
        hitter = create_hitter("Done", ab=1, pa=1)
        walk(self.game, hitter, self.pitcher)
        with self.assertRaises(usage.UsageViolation) as raised:
            walk(self.game, hitter, self.pitcher)
        self.assertIn("plate appearances", str(raised.exception))
        counter = models.UsageCounter.objects.get(player=hitter, season=ULMG_SEASON)
        self.assertEqual(counter.plate_appearances, 1)


class PerGameLimitTestCase(TestCase):
    def test_start_limit_from_sample_innings(self):
        six = create_pitcher("Six a Start", ip=180, g=30, gs=30, start_minusip=180)
        five = create_pitcher("Five a Start", ip=150, g=30, gs=30, start_minusip=150)
        self.assertEqual(usage.card_caps(six, ULMG_SEASON)["start_limit_outs"], 24)
        self.assertEqual(usage.card_caps(five, ULMG_SEASON)["start_limit_outs"], 21)

    def test_relief_limit_from_sample_innings(self):
        setup_man = create_pitcher("Setup Man", ip=65, g=65, gs=0, relief_minusip=65)
        long_man = create_pitcher("Long Man", ip=90, g=45, gs=0, relief_minusip=90)
        self.assertEqual(usage.card_caps(setup_man, ULMG_SEASON)["relief_limit_outs"], 6)
        self.assertEqual(usage.card_caps(long_man, ULMG_SEASON)["relief_limit_outs"], 9)

    def test_start_limit_clamps(self):
        opener = create_pitcher("Opener", ip=20, g=20, gs=20, start_minusip=20)
        iron = create_pitcher("Iron Man", ip=80, g=8, gs=8, start_minusip=80)
        self.assertEqual(usage.card_caps(opener, ULMG_SEASON)["start_limit_outs"], 12)
        self.assertEqual(usage.card_caps(iron, ULMG_SEASON)["start_limit_outs"], 27)

    def test_relief_limit_clamps(self):
        lefty = create_pitcher("LOOGY", ip=20, g=60, gs=0, relief_minusip=20)
        mopup = create_pitcher("Mop Up", ip=40, g=10, gs=0, relief_minusip=40)
        self.assertEqual(usage.card_caps(lefty, ULMG_SEASON)["relief_limit_outs"], 3)
        self.assertEqual(usage.card_caps(mopup, ULMG_SEASON)["relief_limit_outs"], 9)

    def test_no_appearances_of_a_kind_uses_the_floor(self):
        closer = create_pitcher("Closer", ip=60, g=60, gs=0, relief_minusip=60)
        starter = create_pitcher("Starter", ip=24, g=4, gs=4, start_minusip=24)
        self.assertEqual(usage.card_caps(closer, ULMG_SEASON)["start_limit_outs"], 12)
        self.assertEqual(usage.card_caps(starter, ULMG_SEASON)["relief_limit_outs"], 3)

    def test_converted_starter_uses_start_limit_in_relief(self):
        converted = create_pitcher(
            "Converted", ip=70, g=30, gs=5, start_minusip=30, relief_minusip=40
        )
        caps = usage.card_caps(converted, ULMG_SEASON)
        self.assertEqual(caps["start_limit_outs"], 24)
        self.assertEqual(caps["relief_limit_outs"], 24)

    def test_four_starts_is_not_a_converted_starter(self):
        swing = create_pitcher("Swing", ip=60, g=30, gs=4, start_minusip=20, relief_minusip=40)
        self.assertEqual(usage.card_caps(swing, ULMG_SEASON)["relief_limit_outs"], 6)


class PitcherInGameTestCase(TestCase):
    def setUp(self):
        home, road = create_teams()
        self.games = create_series(home, road, length=5)
        self.hitter = create_hitter("Everyday", ab=600, pa=650)

    def test_pitcher_replaced_at_his_per_game_relief_limit(self):
        setup_man = create_pitcher("Setup Man", ip=65, g=65, gs=0, relief_minusip=65)
        fresh_arm = create_pitcher("Fresh Arm", ip=65, g=65, gs=0, relief_minusip=65)
        game = self.games[0]
        for _ in range(6):
            strikeout(game, self.hitter, setup_man)
        check = usage.check_pitcher(setup_man, game)
        self.assertFalse(check.legal)
        self.assertEqual(check.remaining["game_outs"], 0)
        self.assertIn("this outing", check.reason)
        with self.assertRaises(usage.UsageViolation):
            strikeout(game, self.hitter, setup_man)
        self.assertTrue(usage.check_pitcher(fresh_arm, game).legal)
        strikeout(game, self.hitter, fresh_arm)

    def test_pitcher_hits_season_cap_in_the_middle_of_a_game(self):
        cup = create_pitcher("Cup of Coffee", ip=1, g=3, gs=0, relief_minusip=1)
        game = self.games[0]
        self.assertTrue(usage.check_pitcher(cup, game).legal)
        for _ in range(3):
            strikeout(game, self.hitter, cup)
        check = usage.check_pitcher(cup, game)
        self.assertFalse(check.legal)
        self.assertEqual(check.remaining["season_outs"], 0)
        self.assertIn("season", check.reason)

    def test_double_play_allowance_puts_him_over_by_one_out(self):
        cup = create_pitcher("Cup of Coffee", ip=1, g=3, gs=0, relief_minusip=1)
        game = self.games[0]
        strikeout(game, self.hitter, cup)
        strikeout(game, self.hitter, cup)
        play = usage.record_plate_appearance(game, self.hitter, cup, at_bat=True, outs=2)
        self.assertEqual(play.allowance_outs, 1)
        appearance = models.UsageAppearance.objects.get(player=cup, game=game)
        self.assertEqual((appearance.outs, appearance.allowance_outs), (4, 1))
        counter = models.UsageCounter.objects.get(player=cup, season=ULMG_SEASON)
        self.assertEqual(counter.outs, 4)
        self.assertFalse(usage.check_pitcher(cup, game).legal)

    def test_outs_on_the_bases_count_for_the_pitcher_without_a_plate_appearance(self):
        setup_man = create_pitcher("Setup Man", ip=65, g=65, gs=0, relief_minusip=65)
        game = self.games[0]
        walk(game, self.hitter, setup_man)
        usage.record_plate_appearance(game, None, setup_man, at_bat=False, outs=1)
        appearance = models.UsageAppearance.objects.get(player=setup_man, game=game)
        self.assertEqual((appearance.outs, appearance.batters_faced), (1, 1))
        counter = models.UsageCounter.objects.get(player=self.hitter, season=ULMG_SEASON)
        self.assertEqual(counter.plate_appearances, 1)

    def test_a_play_records_at_most_three_outs(self):
        setup_man = create_pitcher("Setup Man", ip=65, g=65, gs=0, relief_minusip=65)
        with self.assertRaises(ValueError):
            usage.record_plate_appearance(self.games[0], self.hitter, setup_man, at_bat=True, outs=4)

    def test_rejected_start_at_the_starts_cap(self):
        spot = create_pitcher("Spot", ip=10, g=1, gs=1, start_minusip=10)
        strikeout(self.games[0], self.hitter, spot, pitcher_starting=True)
        check = usage.check_pitcher(spot, self.games[4], starting=True)
        self.assertFalse(check.legal)
        self.assertIn("starts", check.reason)
        with self.assertRaises(usage.UsageViolation):
            strikeout(self.games[4], self.hitter, spot, pitcher_starting=True)

    def test_rejected_relief_appearance_at_the_season_innings_cap(self):
        cup = create_pitcher("Cup of Coffee", ip=0.1, g=1, gs=0, relief_minusip=0.1)
        strikeout(self.games[0], self.hitter, cup)
        with self.assertRaises(usage.UsageViolation) as raised:
            strikeout(self.games[2], self.hitter, cup)
        self.assertIn("season", str(raised.exception))

    def test_a_pure_reliever_cannot_start(self):
        closer = create_pitcher("Closer", ip=60, g=60, gs=0, relief_minusip=60)
        self.assertFalse(usage.check_pitcher(closer, self.games[0], starting=True).legal)


class StarterRestTestCase(TestCase):
    def setUp(self):
        home, road = create_teams()
        self.games = create_series(home, road, length=5)
        self.next_series = create_series(home, road, length=4, slot_number=2, first_day=6)
        self.hitter = create_hitter("Everyday", ab=600, pa=650)
        self.ace = create_pitcher("Ace", ip=200, g=32, gs=32, start_minusip=200)

    def test_starter_rest_inside_a_five_game_series(self):
        strikeout(self.games[0], self.hitter, self.ace, pitcher_starting=True)
        for n in (2, 3, 4):
            check = usage.check_pitcher(self.ace, self.games[n - 1], starting=True)
            self.assertFalse(check.legal, msg=f"game {n}")
            self.assertIn("rest", check.reason)
        self.assertTrue(usage.check_pitcher(self.ace, self.games[4], starting=True).legal)

    def test_starter_rest_looks_at_later_games_played_first(self):
        strikeout(self.games[4], self.hitter, self.ace, pitcher_starting=True)
        self.assertFalse(usage.check_pitcher(self.ace, self.games[1], starting=True).legal)
        self.assertTrue(usage.check_pitcher(self.ace, self.games[0], starting=True).legal)

    def test_rest_does_not_carry_across_a_series_break(self):
        strikeout(self.games[4], self.hitter, self.ace, pitcher_starting=True)
        self.assertTrue(usage.check_pitcher(self.ace, self.next_series[0], starting=True).legal)

    def test_relieving_does_not_block_a_start(self):
        strikeout(self.games[0], self.hitter, self.ace)
        self.assertTrue(usage.check_pitcher(self.ace, self.games[1], starting=True).legal)


class RelieverRestTestCase(TestCase):
    def setUp(self):
        home, road = create_teams()
        self.games = create_series(home, road, length=5)
        self.next_series = create_series(home, road, length=4, slot_number=2, first_day=6)
        self.hitter = create_hitter("Everyday", ab=600, pa=650)
        self.closer = create_pitcher("Closer", ip=70, g=70, gs=0, relief_minusip=70)

    def game(self, n):
        return self.games[n - 1]

    def test_three_consecutive_games_with_games_played_out_of_order(self):
        strikeout(self.game(4), self.hitter, self.closer)
        strikeout(self.game(2), self.hitter, self.closer)
        check = usage.check_pitcher(self.closer, self.game(3))
        self.assertFalse(check.legal)
        self.assertIn("consecutive games", check.reason)
        self.assertTrue(usage.check_pitcher(self.closer, self.game(1)).legal)
        self.assertTrue(usage.check_pitcher(self.closer, self.game(5)).legal)

    def test_three_consecutive_games_ending_in_game_n(self):
        strikeout(self.game(1), self.hitter, self.closer)
        strikeout(self.game(2), self.hitter, self.closer)
        self.assertFalse(usage.check_pitcher(self.closer, self.game(3)).legal)

    def test_heavy_outing_in_an_adjacent_game(self):
        usage.record_plate_appearance(
            self.game(4), self.hitter, self.closer, at_bat=True, outs=1, pitches=usage.RELIEVER_HEAVY_PITCHES
        )
        check = usage.check_pitcher(self.closer, self.game(3))
        self.assertFalse(check.legal)
        self.assertIn("pitches", check.reason)
        self.assertFalse(usage.check_pitcher(self.closer, self.game(5)).legal)
        self.assertTrue(usage.check_pitcher(self.closer, self.game(2)).legal)

    def test_light_outing_in_an_adjacent_game(self):
        usage.record_plate_appearance(
            self.game(4), self.hitter, self.closer, at_bat=True, outs=1, pitches=usage.RELIEVER_HEAVY_PITCHES - 1
        )
        self.assertTrue(usage.check_pitcher(self.closer, self.game(3)).legal)

    def test_a_new_series_starts_everyone_fresh(self):
        strikeout(self.game(4), self.hitter, self.closer)
        usage.record_plate_appearance(
            self.game(5), self.hitter, self.closer, at_bat=True, outs=1, pitches=40
        )
        self.assertTrue(usage.check_pitcher(self.closer, self.next_series[0]).legal)


class SwingmanTestCase(TestCase):
    def setUp(self):
        home, road = create_teams()
        self.games = create_series(home, road, length=5)
        self.hitter = create_hitter("Everyday", ab=600, pa=650)
        # 80 innings in 30 games, 6 of them starts: 240 actual outs, 360 with the reliever bonus.
        self.swingman = create_pitcher(
            "Swingman", ip=80, g=30, gs=6, start_minusip=30, relief_minusip=50
        )

    def counter(self):
        return models.UsageCounter.objects.get(player=self.swingman, season=ULMG_SEASON)

    def test_swingman_in_the_rotation_is_capped_at_actual_innings(self):
        usage.set_swingman_designation(self.swingman, ULMG_SEASON, usage.ROTATION)
        self.assertEqual(usage.season_innings_cap(self.counter()), 240)

    def test_swingman_defaults_to_the_rotation_until_the_half_plan_says_otherwise(self):
        self.assertEqual(usage.season_innings_cap(usage.counter_for(self.swingman, ULMG_SEASON)), 240)

    def test_swingman_confined_to_relief_gets_the_reliever_bonus(self):
        usage.set_swingman_designation(self.swingman, ULMG_SEASON, usage.BULLPEN)
        self.assertEqual(usage.season_innings_cap(self.counter()), 360)

    def test_a_start_ends_the_confinement(self):
        usage.set_swingman_designation(self.swingman, ULMG_SEASON, usage.BULLPEN)
        strikeout(self.games[0], self.hitter, self.swingman, pitcher_starting=True)
        self.assertEqual(usage.season_innings_cap(self.counter()), 240)
        usage.set_swingman_designation(self.swingman, ULMG_SEASON, usage.BULLPEN)
        self.assertEqual(usage.season_innings_cap(self.counter()), 240)

    def test_confined_swingman_past_actual_innings_cannot_start(self):
        usage.set_swingman_designation(self.swingman, ULMG_SEASON, usage.BULLPEN)
        models.UsageCounter.objects.filter(pk=self.counter().pk).update(outs=240)
        self.assertTrue(usage.check_pitcher(self.swingman, self.games[0]).legal)
        check = usage.check_pitcher(self.swingman, self.games[0], starting=True)
        self.assertFalse(check.legal)
        self.assertIn("confinement", check.reason)

    def test_unknown_designation_is_refused(self):
        with self.assertRaises(ValueError):
            usage.set_swingman_designation(self.swingman, ULMG_SEASON, "closer")


class PlannedStartTestCase(TestCase):
    def setUp(self):
        home, road = create_teams()
        self.games = create_series(home, road, length=5)
        self.next_series = create_series(home, road, length=4, slot_number=2, first_day=6)
        self.hitter = create_hitter("Everyday", ab=600, pa=650)

    def test_planned_start_does_not_use_up_a_start(self):
        ace = create_pitcher("Ace", ip=200, g=32, gs=32, start_minusip=200)
        check = usage.check_planned_start(ace, self.games[0], planned_starts=[self.games[0]])
        self.assertTrue(check.legal)
        self.assertEqual(usage.counter_for(ace, ULMG_SEASON).starts, 0)

    def test_planned_starts_plus_starts_made_within_the_cap(self):
        spot = create_pitcher("Spot", ip=12, g=2, gs=2, start_minusip=12)
        strikeout(self.games[0], self.hitter, spot, pitcher_starting=True)
        self.assertTrue(usage.check_planned_start(spot, self.next_series[0], []).legal)
        check = usage.check_planned_start(
            spot, self.next_series[0], planned_starts=[self.games[4], self.next_series[0]]
        )
        self.assertFalse(check.legal)
        self.assertIn("starts", check.reason)

    def test_planned_start_must_be_rested_against_starts_made_and_planned(self):
        ace = create_pitcher("Ace", ip=200, g=32, gs=32, start_minusip=200)
        strikeout(self.games[0], self.hitter, ace, pitcher_starting=True)
        self.assertFalse(usage.check_planned_start(ace, self.games[2], []).legal)
        self.assertTrue(usage.check_planned_start(ace, self.games[4], []).legal)
        self.assertFalse(
            usage.check_planned_start(ace, self.next_series[3], [self.next_series[0]]).legal
        )


class LedgerReadsTestCase(TestCase):
    """One action's reads of the ledger: the same checks as reading it fresh, loaded once until forget()."""

    def setUp(self):
        home, road = create_teams()
        self.games = create_series(home, road, length=5)
        self.next_series = create_series(home, road, length=4, slot_number=2, first_day=6)
        self.hitter = create_hitter("Everyday", ab=600, pa=650)
        self.bench_bat = create_hitter("Bench Bat", ab=3, pa=3)
        self.ace = create_pitcher("Ace", ip=200, g=32, gs=32, start_minusip=200)
        self.closer = create_pitcher("Closer", ip=70, g=70, gs=0, relief_minusip=70)
        self.cup = create_pitcher("Cup of Coffee", ip=1, g=3, gs=0, relief_minusip=1)
        self.swingman = create_pitcher("Swingman", ip=80, g=30, gs=6, start_minusip=30, relief_minusip=50)
        self.unused = create_pitcher("Never Used", ip=50, g=40, gs=0, relief_minusip=50)
        commissioner = User.objects.create_superuser("commish", "c@example.com", "pw")

        strikeout(self.games[0], self.hitter, self.ace, pitcher_starting=True)
        usage.record_plate_appearance(
            self.games[3], self.hitter, self.closer, at_bat=True, outs=1, pitches=usage.RELIEVER_HEAVY_PITCHES
        )
        for _ in range(3):
            strikeout(self.games[1], self.bench_bat, self.cup)
        usage.set_swingman_designation(self.swingman, ULMG_SEASON, usage.BULLPEN)
        usage.grant_override(
            commissioner, self.cup, self.games[2], models.UsageOverride.SEASON_INNINGS, "Rainout makeup"
        )
        self.pitchers = [self.ace, self.closer, self.cup, self.swingman, self.unused]
        self.batters = [self.hitter, self.bench_bat]

    def every_game(self):
        return self.games + self.next_series

    def test_pitcher_checks_match_the_fresh_ledger(self):
        for game in self.every_game():
            reads = usage.LedgerReads(ULMG_SEASON)
            reads.preload(self.pitchers + self.batters)
            for pitcher in self.pitchers:
                for starting in (False, True):
                    self.assertEqual(
                        usage.check_pitcher(pitcher, game, starting=starting, reads=reads),
                        usage.check_pitcher(pitcher, game, starting=starting),
                        msg=f"{pitcher.name} day {game.day} starting={starting}",
                    )

    def test_batter_checks_match_the_fresh_ledger(self):
        for game in self.every_game():
            reads = usage.LedgerReads(ULMG_SEASON)
            for batter in self.batters + self.pitchers:
                self.assertEqual(
                    usage.check_batter(batter, game, reads=reads),
                    usage.check_batter(batter, game),
                    msg=f"{batter.name} day {game.day}",
                )

    def test_planned_start_checks_match_the_fresh_ledger(self):
        reads = usage.LedgerReads(ULMG_SEASON)
        reads.preload(self.pitchers)
        plans = [[], [self.games[4]], [self.games[4], self.next_series[0]], [self.next_series[3]]]
        for game in self.every_game():
            for pitcher in self.pitchers:
                for planned in plans:
                    self.assertEqual(
                        usage.check_planned_start(pitcher, game, planned, reads=reads),
                        usage.check_planned_start(pitcher, game, planned),
                        msg=f"{pitcher.name} day {game.day} planned {[g.day for g in planned]}",
                    )

    def test_preloaded_players_are_read_in_a_few_queries_and_then_from_memory(self):
        reads = usage.LedgerReads(ULMG_SEASON)
        reads.preload(self.pitchers + self.batters)
        game = self.games[2]
        # Counters, card-season stats for players without one, overrides, this game's
        # appearances and the series' other appearances: one query each.
        with self.assertNumQueries(5):
            usage.check_pitcher(self.ace, game, reads=reads)
        with self.assertNumQueries(0):
            for pitcher in self.pitchers:
                usage.check_pitcher(pitcher, game, starting=True, reads=reads)
                usage.check_pitcher(pitcher, game, reads=reads)
            for batter in self.batters:
                usage.check_batter(batter, game, reads=reads)
        with self.assertNumQueries(1):
            usage.check_planned_start(self.ace, game, [], reads=reads)
        with self.assertNumQueries(0):
            for pitcher in self.pitchers:
                usage.check_planned_start(pitcher, game, [], reads=reads)

    def test_reads_are_kept_until_forget_and_then_read_the_ledger_again(self):
        reads = usage.LedgerReads(ULMG_SEASON)
        game = self.games[4]
        self.assertTrue(usage.check_pitcher(self.unused, game, reads=reads).legal)
        # His relief limit is two innings.
        for _ in range(6):
            strikeout(game, self.hitter, self.unused)
        self.assertTrue(usage.check_pitcher(self.unused, game, reads=reads).legal)
        reads.forget()
        check = usage.check_pitcher(self.unused, game, reads=reads)
        self.assertFalse(check.legal)
        self.assertEqual(check, usage.check_pitcher(self.unused, game))

    def test_a_player_who_was_not_preloaded_is_still_read(self):
        reads = usage.LedgerReads(ULMG_SEASON)
        reads.preload([self.ace])
        self.assertEqual(
            usage.check_pitcher(self.cup, self.games[2], reads=reads), usage.check_pitcher(self.cup, self.games[2])
        )
        self.assertEqual(usage.check_batter(self.bench_bat, self.games[2], reads=reads), usage.check_batter(self.bench_bat, self.games[2]))

    def test_reads_for_another_season_are_refused(self):
        reads = usage.LedgerReads(ULMG_SEASON + 1)
        with self.assertRaises(ValueError):
            usage.check_pitcher(self.ace, self.games[0], reads=reads)

    def test_reads_never_write(self):
        reads = usage.LedgerReads(ULMG_SEASON)
        reads.preload(self.pitchers + self.batters)
        before = models.UsageCounter.objects.count()
        usage.check_pitcher(self.unused, self.games[0], reads=reads)
        usage.check_planned_start(self.unused, self.games[0], [], reads=reads)
        self.assertEqual(models.UsageCounter.objects.count(), before)
        self.assertFalse(models.UsageCounter.objects.filter(player=self.unused).exists())


class PenaltyLinesTestCase(TestCase):
    def setUp(self):
        self.home, self.road = create_teams()

    def over(self, name, cap, used):
        hitter = create_hitter(name, team=self.home, ab=cap, pa=cap)
        counter = usage.counter_for(hitter, ULMG_SEASON)
        models.UsageCounter.objects.filter(pk=counter.pk).update(plate_appearances=used)
        return hitter

    def test_no_penalty_at_ten_percent_over(self):
        self.over("Just Under", cap=100, used=110)
        lines = usage.penalty_lines(self.home, ULMG_SEASON)
        self.assertEqual(lines.players_over_10, [])
        self.assertFalse(lines.loses_first_round_aa_pick)

    def test_more_than_ten_percent_over(self):
        hitter = self.over("Over Ten", cap=100, used=111)
        lines = usage.penalty_lines(self.home, ULMG_SEASON)
        self.assertEqual([p.player for p in lines.players_over_10], [hitter])
        self.assertEqual(lines.players_playoff_ineligible, [hitter])
        self.assertTrue(lines.loses_first_round_aa_pick)
        self.assertFalse(lines.loses_both_first_round_picks)
        self.assertFalse(lines.team_playoff_ineligible)

    def test_a_second_player_more_than_ten_percent_over(self):
        self.over("Over Ten", cap=100, used=111)
        self.over("Also Over Ten", cap=100, used=115)
        lines = usage.penalty_lines(self.home, ULMG_SEASON)
        self.assertTrue(lines.loses_both_first_round_picks)
        self.assertFalse(lines.team_playoff_ineligible)

    def test_more_than_twenty_percent_over(self):
        hitter = self.over("Over Twenty", cap=100, used=121)
        lines = usage.penalty_lines(self.home, ULMG_SEASON)
        self.assertEqual([p.player for p in lines.players_over_20], [hitter])
        self.assertEqual(lines.free_agents_next_open_draft, [hitter])
        self.assertTrue(lines.team_playoff_ineligible)

    def test_other_teams_players_do_not_count(self):
        hitter = create_hitter("Visitor", team=self.road, ab=100, pa=100)
        counter = usage.counter_for(hitter, ULMG_SEASON)
        models.UsageCounter.objects.filter(pk=counter.pk).update(plate_appearances=150)
        self.assertEqual(usage.penalty_lines(self.home, ULMG_SEASON).players_over_10, [])


class CommissionerOverrideTestCase(TestCase):
    def setUp(self):
        self.home, self.road = create_teams()
        self.games = create_series(self.home, self.road, length=5)
        self.pitcher = create_pitcher("Mop Up", ip=80, g=60, gs=0, relief_minusip=80)
        self.hitter = create_hitter("Bench Bat", team=self.home, ab=10, pa=10)
        self.commissioner = User.objects.create_user("commish", is_superuser=True)
        self.owner = User.objects.create_user("owner")
        counter = usage.counter_for(self.hitter, ULMG_SEASON)
        models.UsageCounter.objects.filter(pk=counter.pk).update(plate_appearances=10)

    def test_override_lets_one_player_past_one_cap_in_one_game(self):
        game = self.games[0]
        self.assertFalse(usage.check_batter(self.hitter, game).legal)
        with self.assertLogs("ulmg.usage", level="INFO") as logs:
            override = usage.grant_override(
                self.commissioner, self.hitter, game, models.UsageOverride.PLATE_APPEARANCES, "Rainout makeup"
            )
        self.assertIn("commish", logs.output[0])
        self.assertIn("Rainout makeup", logs.output[0])
        self.assertEqual(override.approved_by, self.commissioner)
        self.assertIsNotNone(override.approved_at)

        check = usage.check_batter(self.hitter, game)
        self.assertTrue(check.legal)
        self.assertEqual(check.override, override)
        walk(game, self.hitter, self.pitcher)
        walk(game, self.hitter, self.pitcher)
        override.refresh_from_db()
        self.assertEqual(override.plate_appearances_used, 2)

        self.assertFalse(usage.check_batter(self.hitter, self.games[1]).legal)
        other = create_hitter("Other Bench Bat", ab=1, pa=1)
        walk(game, other, self.pitcher)
        self.assertFalse(usage.check_batter(other, game).legal)

    def test_override_usage_counts_toward_the_penalty_lines(self):
        game = self.games[0]
        usage.grant_override(
            self.commissioner, self.hitter, game, models.UsageOverride.PLATE_APPEARANCES, "Extra innings"
        )
        walk(game, self.hitter, self.pitcher)
        lines = usage.penalty_lines(self.home, ULMG_SEASON)
        self.assertEqual(lines.players_over_10, [])
        walk(game, self.hitter, self.pitcher)
        lines = usage.penalty_lines(self.home, ULMG_SEASON)
        self.assertEqual([p.player for p in lines.players_over_10], [self.hitter])

    def test_non_commissioner_is_refused_an_override(self):
        with self.assertRaises(PermissionDenied):
            usage.grant_override(
                self.owner, self.hitter, self.games[0], models.UsageOverride.PLATE_APPEARANCES, "Please"
            )
        self.assertFalse(models.UsageOverride.objects.filter(approved_by__isnull=False).exists())
        self.assertFalse(usage.check_batter(self.hitter, self.games[0]).legal)

    def test_owner_request_is_not_an_override_until_the_commissioner_grants_it(self):
        game = self.games[0]
        request = usage.request_override(
            self.owner, self.hitter, game, models.UsageOverride.PLATE_APPEARANCES, "Paused game"
        )
        self.assertIsNone(request.approved_by)
        self.assertFalse(usage.check_batter(self.hitter, game).legal)
        with self.assertLogs("ulmg.usage", level="INFO"):
            granted = usage.grant_override(
                self.commissioner, self.hitter, game, models.UsageOverride.PLATE_APPEARANCES, "Approved"
            )
        self.assertEqual(granted.pk, request.pk)
        self.assertEqual(granted.requested_by, self.owner)
        self.assertTrue(usage.check_batter(self.hitter, game).legal)

    def test_override_past_a_per_game_limit(self):
        setup_man = create_pitcher("Setup Man", ip=65, g=65, gs=0, relief_minusip=65)
        everyday = create_hitter("Everyday", ab=600, pa=650)
        game = self.games[0]
        for _ in range(6):
            strikeout(game, everyday, setup_man)
        self.assertFalse(usage.check_pitcher(setup_man, game).legal)
        with self.assertLogs("ulmg.usage", level="INFO"):
            usage.grant_override(
                self.commissioner, setup_man, game, models.UsageOverride.GAME_INNINGS, "No one left"
            )
        strikeout(game, everyday, setup_man)
        self.assertEqual(
            models.UsageOverride.objects.get(player=setup_man).outs_used, 1
        )


class PausedGameTestCase(TestCase):
    def setUp(self):
        self.home, self.road = create_teams()
        self.game = create_series(self.home, self.road, length=3)[0]
        self.hitter = create_hitter("Everyday", ab=600, pa=650)
        self.commissioner = User.objects.create_user("commish", is_superuser=True)
        self.tired = create_pitcher("Tired", team=self.home, ip=0.1, g=1, gs=0, relief_minusip=0.1)
        self.spent = create_pitcher("Spent", team=self.home, ip=0.1, g=1, gs=0, relief_minusip=0.1)
        strikeout(self.game, self.hitter, self.tired)
        strikeout(self.game, self.hitter, self.spent)

    def test_paused_game_with_no_legal_pitcher(self):
        pitchers = [self.tired, self.spent]
        self.assertEqual(usage.legal_pitchers(self.game, pitchers), [])
        with self.assertLogs("ulmg.usage", level="WARNING") as logs:
            pause = usage.pause_if_no_legal_pitcher(self.game, self.home, pitchers)
        self.assertIn("no legal pitcher", logs.output[0])
        self.assertTrue(pause.is_open)
        self.assertIn("Tired", pause.reason)
        self.assertEqual(models.UsagePause.objects.filter(resolved_at__isnull=True).count(), 1)

    def test_game_resumes_once_an_override_gives_the_side_a_pitcher(self):
        pitchers = [self.tired, self.spent]
        with self.assertLogs("ulmg.usage", level="WARNING"):
            pause = usage.pause_if_no_legal_pitcher(self.game, self.home, pitchers)
        self.assertFalse(usage.resume_if_legal(pause, pitchers))
        with self.assertLogs("ulmg.usage", level="INFO"):
            usage.grant_override(
                self.commissioner, self.tired, self.game, models.UsageOverride.SEASON_INNINGS, "Pause"
            )
        self.assertTrue(usage.resume_if_legal(pause, pitchers))
        pause.refresh_from_db()
        self.assertFalse(pause.is_open)

    def test_no_pause_when_a_side_has_a_legal_pitcher(self):
        fresh = create_pitcher("Fresh", team=self.home, ip=60, g=60, gs=0, relief_minusip=60)
        self.assertIsNone(
            usage.pause_if_no_legal_pitcher(self.game, self.home, [self.tired, fresh])
        )
        self.assertFalse(models.UsagePause.objects.exists())


class CapRefreshTestCase(TestCase):
    def test_a_data_fix_refreshes_caps_and_keeps_usage(self):
        hitter = create_hitter("Fixed", ab=50, pa=60)
        counter = usage.counter_for(hitter, ULMG_SEASON)
        models.UsageCounter.objects.filter(pk=counter.pk).update(plate_appearances=12)
        models.PlayerStatSeason.objects.filter(player=hitter).update(hit_stats={"ab": 5, "pa": 10})
        counter = usage.refresh_caps(hitter, ULMG_SEASON)
        self.assertEqual((counter.plate_appearances_cap, counter.plate_appearances), (10, 12))


class OverrideAdminTestCase(TestCase):
    def setUp(self):
        home, road = create_teams()
        self.game = create_series(home, road, length=3)[0]
        self.hitter = create_hitter("Bench Bat", ab=10, pa=10)

    def post_override(self, user):
        self.client.force_login(user)
        return self.client.post(
            "/admin/ulmg/usageoverride/add/",
            {
                "active": "on",
                "player": self.hitter.id,
                "game": self.game.id,
                "cap": models.UsageOverride.PLATE_APPEARANCES,
                "reason": "Doubleheader",
            },
        )

    def test_commissioner_grants_an_override_in_the_admin(self):
        commissioner = User.objects.create_user("commish", is_superuser=True, is_staff=True)
        with self.assertLogs("ulmg.usage", level="INFO") as logs:
            response = self.post_override(commissioner)
        self.assertEqual(response.status_code, 302)
        self.assertIn("Doubleheader", logs.output[0])
        override = models.UsageOverride.objects.get(player=self.hitter)
        self.assertEqual((override.approved_by, override.reason), (commissioner, "Doubleheader"))

    def test_staff_who_is_not_the_commissioner_cannot_grant_in_the_admin(self):
        staff = User.objects.create_user("staff", is_staff=True)
        staff.user_permissions.set(
            Permission.objects.filter(content_type__app_label="ulmg", codename__endswith="usageoverride")
        )
        response = self.post_override(staff)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(models.UsageOverride.objects.exists())
