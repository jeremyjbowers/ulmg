# ABOUTME: Tests for paired call-ups and send-downs in ulmg.roster_moves: the 10-move cap, 15-road-game stays and games in progress.
# ABOUTME: Also covers the half plan's road/home eligibility rules, the half-start roster snapshot and the sim reset's restore step.

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import models, plans, roster_moves, schedule, sim_data
from tests.plan_fixtures import CARD_SEASON, SEASON, Roster, create_hitter, create_pitcher, create_season


def team(abbreviation):
    return models.Team.objects.get(abbreviation=abbreviation)


def road_games(team_obj, half=1):
    return [
        g
        for g in schedule.team_games(team_obj, SEASON)
        if g.series.road_team_id == team_obj.id and g.series.slot.half == half
    ]


def home_games(team_obj, half=1):
    return [
        g
        for g in schedule.team_games(team_obj, SEASON)
        if g.series.home_team_id == team_obj.id and g.series.slot.half == half
    ]


def finish(game):
    game.home_score, game.road_score = 3, 2
    game.save()


def create_aaa_pitcher(team_obj, name, card=True):
    player = create_pitcher(team_obj, name, roster=False, card=card)
    player.is_ulmg_aaa_roster = True
    player.save()
    return player


def flags(player):
    player.refresh_from_db()
    return (player.is_ulmg_mlb_roster, player.is_ulmg_aaa_roster)


def stat_flags(player, season=SEASON):
    row = models.PlayerStatSeason.objects.filter(player=player, season=season).first()
    return (row.is_ulmg_mlb_roster, row.is_ulmg_aaa_roster) if row else None


@override_settings(CURRENT_SEASON=SEASON, TEAM_SEASON_HALF="1h")
class RosterMoveTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_season()
        cls.atl = team("ATL")
        cls.roster = Roster(cls.atl)
        cls.call_ups = [create_aaa_pitcher(cls.atl, f"ATL Call-up {i + 1}") for i in range(11)]

    def move(self, up, down, half=1):
        return roster_moves.make_move(self.atl, up, down, season=SEASON, half=half)

    def thirty_man_count(self):
        return models.Player.objects.filter(team=self.atl, is_ulmg_mlb_roster=True).count()


class PairedMoveTestCase(RosterMoveTestCase):
    def test_a_move_calls_one_up_and_sends_one_down(self):
        up, down = self.call_ups[0], self.roster.relievers[1]
        before = self.thirty_man_count()

        move = self.move(up, down)

        self.assertEqual(flags(up), (True, False))
        self.assertEqual(flags(down), (False, True))
        self.assertEqual(self.thirty_man_count(), before)
        # The PlayerStatSeason copies follow the flags, as to_mlb and to_aaa keep them.
        self.assertEqual(stat_flags(up), (True, False))
        self.assertEqual(stat_flags(down), (False, True))

        move.refresh_from_db()
        self.assertEqual((move.season, move.half, move.team), (SEASON, 1, self.atl))
        self.assertEqual((move.player_up, move.player_down), (up, down))
        self.assertIsNotNone(move.made_at)
        self.assertEqual(move.stay_games, roster_moves.STAY_ROAD_GAMES)
        self.assertEqual(move.stay_last_day, road_games(self.atl)[14].day)
        self.assertIsNone(move.game)

    def test_the_player_up_must_be_off_the_30_man_and_on_the_team(self):
        with self.assertRaisesMessage(roster_moves.MoveError, "already on ATL's 30-man"):
            self.move(self.roster.relievers[0], self.roster.relievers[1])
        other = create_aaa_pitcher(team("CAR"), "CAR Arm")
        with self.assertRaisesMessage(roster_moves.MoveError, "not on ATL"):
            self.move(other, self.roster.relievers[1])
        self.assertFalse(models.RosterMove.objects.exists())

    def test_the_player_down_must_be_on_the_30_man(self):
        with self.assertRaisesMessage(roster_moves.MoveError, "not on ATL's 30-man"):
            self.move(self.call_ups[0], self.call_ups[1])
        self.assertEqual(flags(self.call_ups[0]), (False, True))

    def test_the_carded_last_season_gate_still_applies(self):
        uncarded = models.Player.objects.create(
            name="ATL Uncarded", position="P", level="B", team=self.atl, is_ulmg_aaa_roster=True
        )
        self.assertFalse(uncarded.is_carded_for_season(CARD_SEASON))
        with self.assertRaisesMessage(roster_moves.MoveError, "Only carded players"):
            self.move(uncarded, self.roster.relievers[1])
        self.assertEqual(flags(uncarded), (False, True))
        self.assertEqual(flags(self.roster.relievers[1]), (True, False))
        self.assertFalse(models.RosterMove.objects.exists())

    def test_a_midseason_open_pick_cannot_be_sent_down(self):
        pick = self.roster.bench[0]
        pick.is_ulmg_2h_draft = True
        pick.save()
        with self.assertRaisesMessage(roster_moves.MoveError, "Midseason Open picks"):
            self.move(self.call_ups[0], pick)


class MoveCapTestCase(RosterMoveTestCase):
    def test_the_eleventh_move_of_a_half_is_rejected(self):
        downs = self.roster.hitters + self.roster.bench
        for i in range(roster_moves.MOVES_PER_HALF):
            self.move(self.call_ups[i], downs[i])
            self.assertEqual(
                roster_moves.moves_left(self.atl, SEASON, 1), roster_moves.MOVES_PER_HALF - i - 1
            )

        with self.assertRaisesMessage(roster_moves.MoveError, "10 moves"):
            self.move(self.call_ups[10], downs[10])
        self.assertEqual(flags(self.call_ups[10]), (False, True))
        self.assertEqual(flags(downs[10]), (True, False))
        self.assertEqual(models.RosterMove.objects.filter(team=self.atl, season=SEASON, half=1).count(), 10)

    def test_the_cap_starts_again_in_the_second_half(self):
        downs = self.roster.hitters + self.roster.bench
        for i in range(roster_moves.MOVES_PER_HALF):
            models.RosterMove.objects.create(
                season=SEASON, half=1, team=self.atl, player_up=self.call_ups[i],
                player_down=downs[i], stay_games=0,
            )
        self.assertEqual(roster_moves.moves_left(self.atl, SEASON, 1), 0)
        self.assertEqual(roster_moves.moves_left(self.atl, SEASON, 2), roster_moves.MOVES_PER_HALF)
        with self.settings(TEAM_SEASON_HALF="2h"):
            self.move(self.call_ups[10], downs[10], half=2)


class StayTestCase(RosterMoveTestCase):
    def test_a_stay_cannot_be_cut_short(self):
        up = self.call_ups[0]
        self.move(up, self.roster.relievers[1])
        with self.assertRaisesMessage(roster_moves.MoveError, "15 road games"):
            self.move(self.call_ups[1], up)
        self.assertEqual(flags(up), (True, False))
        self.assertEqual(flags(self.call_ups[1]), (False, True))

    def test_a_stay_ends_after_the_fifteenth_road_game(self):
        up = self.call_ups[0]
        move = self.move(up, self.roster.relievers[1])
        road = road_games(self.atl)
        for game in road[:14]:
            finish(game)
        self.assertEqual(roster_moves.stay_games_left(move), 1)
        self.assertEqual(roster_moves.active_stay(up, SEASON), move)
        # Home games don't count toward the stay.
        for game in home_games(self.atl):
            finish(game)
        self.assertEqual(roster_moves.stay_games_left(move), 1)

        finish(road[14])
        self.assertEqual(roster_moves.stay_games_left(move), 0)
        self.assertIsNone(roster_moves.active_stay(up, SEASON))
        self.move(self.call_ups[1], up)
        self.assertEqual(flags(up), (False, True))

    def test_a_stay_expires_with_the_half(self):
        road = road_games(self.atl)
        for game in road[:-5]:
            finish(game)
        up = self.call_ups[0]
        move = self.move(up, self.roster.relievers[1])
        self.assertEqual(move.stay_games, 5)
        self.assertEqual(move.stay_last_day, road[-1].day)
        self.assertLessEqual(move.stay_last_day, 81)

        for game in road[-5:]:
            finish(game)
        self.assertIsNone(roster_moves.active_stay(up, SEASON))
        # Second-half road games are never part of a first-half stay.
        self.assertEqual(roster_moves.stay_games_left(move), 0)

    def test_the_single_to_aaa_action_also_refuses_a_cut_short_stay(self):
        user = User.objects.create_superuser("commish", "c@example.com", "password")
        client = Client()
        client.force_login(user)
        up = self.call_ups[0]
        self.move(up, self.roster.relievers[1])
        for action in ("to_aaa", "off_roster"):
            response = client.get(f"/api/v1/player/{up.id}/{action}/")
            self.assertEqual(response.status_code, 400, action)
            self.assertIn("15 road games", response.json()["error"])
        self.assertEqual(flags(up), (True, False))


class GameInProgressTestCase(RosterMoveTestCase):
    def setUp(self):
        self.game = road_games(self.atl)[0]
        plans.open_game(self.game)

    def test_a_move_during_a_road_game_in_progress(self):
        up, down = self.call_ups[0], self.roster.relievers[1]
        move = self.move(up, down)
        self.assertEqual(move.game, self.game)
        # The game in progress is the first of the stay's road games.
        self.assertEqual(move.stay_last_day, road_games(self.atl)[14].day)
        # From the next plate appearance the called-up player is on the game's roster and the other is off it.
        game_roster = roster_moves.game_roster_ids(self.atl, self.game)
        self.assertIn(up.id, game_roster)
        self.assertNotIn(down.id, game_roster)

    def test_a_player_who_appeared_in_the_game_cannot_be_sent_down_until_it_is_final(self):
        down = self.roster.relievers[1]
        models.UsageAppearance.objects.create(player=down, game=self.game, outs=3, pitches=15)
        with self.assertRaisesMessage(roster_moves.MoveError, "appeared in the game in progress"):
            self.move(self.call_ups[0], down)
        self.assertEqual(flags(down), (True, False))
        self.assertFalse(models.RosterMove.objects.exists())

        finish(self.game)
        self.move(self.call_ups[0], down)
        self.assertEqual(flags(down), (False, True))

    def test_a_player_who_has_not_appeared_can_be_sent_down(self):
        models.UsageAppearance.objects.create(player=self.roster.relievers[0], game=self.game, outs=3)
        self.move(self.call_ups[0], self.roster.relievers[1])
        self.assertEqual(flags(self.roster.relievers[1]), (False, True))

    def test_a_home_game_in_progress_does_not_block_a_send_down(self):
        home = home_games(self.atl)[0]
        plans.open_game(home)
        down = self.roster.relievers[1]
        models.UsageAppearance.objects.create(player=down, game=home, outs=3)
        self.move(self.call_ups[0], down)
        # The move leaves home games alone: he is still on the home game's roster.
        self.assertIn(down.id, roster_moves.game_roster_ids(self.atl, home))


class PlanEligibilityTestCase(RosterMoveTestCase):
    def setUp(self):
        self.plan = self.roster.file()

    def test_a_called_up_player_is_rejected_from_a_home_game_plan(self):
        up = self.call_ups[0]
        self.move(up, self.roster.relievers[1])
        self.roster.file(setup=[up])
        home_day = home_games(self.atl)[0].day
        road_day = road_games(self.atl)[0].day

        with self.assertRaisesMessage(plans.PlanError, "call-up and can be planned into road games only"):
            plans.save_day(self.plan, home_day, starter=up)
        plans.save_day(self.plan, road_day, starter=up)
        self.assertEqual(plans.starters(self.plan)[road_day], up)

    def test_a_called_up_hitter_is_rejected_from_a_home_day_lineup_and_the_lineup_cards(self):
        hitter_up = create_hitter(self.atl, "ATL Called Hitter", defense={"LF": 1.0}, roster=False)
        sent = self.roster.bench[1]
        self.move(hitter_up, sent)
        lineup = self.roster.lineup()
        lineup[5] = {"order": 6, "player": hitter_up, "position": lineup[5]["position"]}

        home_day = home_games(self.atl)[0].day
        with self.assertRaisesMessage(plans.PlanError, "call-up and can be planned into road games only"):
            plans.save_day(self.plan, home_day, lineup=lineup)
        with self.assertRaisesMessage(plans.PlanError, "lineup cards also cover home days"):
            self.roster.file(lineup_vs_rhp=lineup, bench=[self.roster.bench[0]])

        road_day = road_games(self.atl)[0].day
        plans.save_day(self.plan, road_day, lineup=lineup)
        side = plans.game_sheet(road_games(self.atl)[0])["road"]
        self.assertIn(hitter_up, [p for p, _ in side["lineup"]])

    def test_a_called_up_reliever_is_on_road_bullpens_only(self):
        up = self.call_ups[0]
        self.move(up, self.roster.relievers[1])
        self.roster.file(setup=[up])
        road = plans.game_sheet(road_games(self.atl)[0])["road"]
        home = plans.game_sheet(home_games(self.atl)[0])["home"]
        self.assertIn(up, road["setup"])
        self.assertNotIn(up, home["setup"])

    def test_a_called_up_starter_is_auto_filled_into_road_games_only(self):
        up = self.call_ups[0]
        self.move(up, self.roster.relievers[1])
        rotation = [up] + self.roster.starters[1:]
        plan = self.roster.file(rotation=rotation)
        starters = plans.starters(plan)
        home_days = {g.day for g in home_games(self.atl)}
        road_days = {g.day for g in road_games(self.atl)}
        self.assertTrue(any(starters[d] == up for d in road_days))
        self.assertFalse(any(starters[d] == up for d in home_days))

    def fill_fields(self, **kwargs):
        fields = {
            "rotation": self.roster.starters,
            "closer": self.roster.relievers[0],
            "setup": [],
            "middle_long": [self.roster.swingman],
            "bench": [self.roster.bench[0]],
            "lineup_vs_lhp": self.roster.lineup(),
            "lineup_vs_rhp": self.roster.lineup(),
        }
        fields.update(kwargs)
        return fields

    def test_fill_plan_auto_fills_a_called_up_starter_into_road_games_only(self):
        up = self.call_ups[0]
        self.move(up, self.roster.relievers[1])
        rotation = [up] + self.roster.starters[1:]
        self.assertEqual(plans.fill_plan(self.plan, **self.fill_fields(rotation=rotation)), [])
        starters = plans.starters(self.plan)
        self.assertTrue(any(starters[g.day] == up for g in road_games(self.atl)))
        self.assertFalse(any(starters[g.day] == up for g in home_games(self.atl)))

    def test_fill_plan_leaves_a_lineup_card_with_a_call_up_empty(self):
        hitter_up = create_hitter(self.atl, "ATL Called Hitter", defense={"LF": 1.0}, roster=False)
        self.move(hitter_up, self.roster.bench[1])
        lineup = self.roster.lineup()
        lineup[5] = {"order": 6, "player": hitter_up, "position": lineup[5]["position"]}

        problems = plans.fill_plan(self.plan, **self.fill_fields(lineup_vs_rhp=lineup))
        self.assertEqual(
            problems,
            [
                "Lineup vs RHP: ATL Called Hitter is a call-up and can be planned into road games only; "
                "the lineup cards also cover home days. File him into road days' lineups instead."
            ],
        )
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.lineup_vs_rhp, [])
        self.assertEqual(len(self.plan.lineup_vs_lhp), 9)
        self.assertTrue(all(plans.starters(self.plan).values()))

    def test_a_sent_down_player_still_starts_his_planned_home_game(self):
        sent = self.roster.starters[0]
        starts = plans.starters(self.plan)
        home_days = [g.day for g in home_games(self.atl) if starts[g.day] == sent]
        road_days = [g.day for g in road_games(self.atl) if starts[g.day] == sent]
        self.assertTrue(home_days and road_days)

        self.move(self.call_ups[0], sent)
        # His planned home starts stand: the move leaves the plan as it was.
        home = next(g for g in home_games(self.atl) if g.day == home_days[0])
        self.assertEqual(plans.game_sheet(home)["home"]["starter"], sent)
        self.assertNotIn(sent.id, plans.game_sheet(home)["home"]["unavailable"])
        road = next(g for g in road_games(self.atl) if g.day == road_days[0])
        self.assertIn(sent.id, plans.game_sheet(road)["road"]["unavailable"])

        # The plan saves with him still in the rotation, and auto-fill gives him home games only.
        plan = self.roster.file()
        starts = plans.starters(plan)
        self.assertTrue(any(starts[g.day] == sent for g in home_games(self.atl)))
        self.assertFalse(any(starts[g.day] == sent for g in road_games(self.atl)))

    def test_a_sent_down_swingmans_home_spot_start_stands(self):
        swingman = self.roster.swingman
        home_day = home_games(self.atl)[3].day
        plans.save_day(self.plan, home_day, starter=swingman)
        self.move(self.call_ups[0], swingman)

        plan = self.roster.file()
        self.assertEqual(plans.starters(plan)[home_day], swingman)
        home = next(g for g in home_games(self.atl) if g.day == home_day)
        self.assertEqual(plans.game_sheet(home)["home"]["starter"], swingman)
        # He stays in the home bullpen and leaves the road one.
        self.assertIn(swingman, plans.game_sheet(home)["home"]["middle_long"])
        road = road_games(self.atl)[0]
        self.assertNotIn(swingman, plans.game_sheet(road)["road"]["middle_long"])
        with self.assertRaisesMessage(plans.PlanError, "sent down and can be planned into home games only"):
            plans.save_day(self.plan, road.day, starter=swingman)

    def test_a_sent_down_hitter_keeps_his_home_lineup_spot(self):
        sent = self.roster.hitters[3]
        self.move(self.call_ups[0], sent)
        self.roster.file()
        home = plans.game_sheet(home_games(self.atl)[0])["home"]
        road = plans.game_sheet(road_games(self.atl)[0])["road"]
        self.assertIn(sent, [p for p, _ in home["lineup"]])
        # On the road he is flagged for the bench to replace when the game opens.
        self.assertIn(sent.id, road["unavailable"])
        self.assertNotIn(sent.id, home["unavailable"])
        with self.assertRaisesMessage(plans.PlanError, "sent down and can be planned into home games only"):
            plans.save_day(self.plan, road_games(self.atl)[1].day, lineup=self.roster.lineup())
        plans.save_day(self.plan, home_games(self.atl)[1].day, lineup=self.roster.lineup())


@override_settings(CURRENT_SEASON=SEASON, TEAM_SEASON_HALF="1h")
class SnapshotTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_season()
        cls.atl = team("ATL")
        cls.car = team("CAR")
        cls.roster = Roster(cls.atl)
        cls.car_roster = Roster(cls.car)
        cls.call_ups = [create_aaa_pitcher(cls.atl, f"ATL Call-up {i + 1}") for i in range(3)]
        cls.car_up = create_aaa_pitcher(cls.car, "CAR Call-up")

    def snapshot_rows(self, half=1):
        return {
            row.player_id: (row.team_id, row.is_ulmg_mlb_roster, row.is_ulmg_aaa_roster)
            for row in models.HalfRosterSnapshotPlayer.objects.filter(snapshot__season=SEASON, snapshot__half=half)
        }

    def current_rows(self):
        return {
            p.id: (p.team_id, p.is_ulmg_mlb_roster, p.is_ulmg_aaa_roster)
            for p in models.Player.objects.filter(team__isnull=False)
        }

    def test_the_first_move_of_a_half_takes_the_snapshot_before_it(self):
        before = self.current_rows()
        roster_moves.make_move(self.atl, self.call_ups[0], self.roster.relievers[1], season=SEASON, half=1)
        self.assertEqual(self.snapshot_rows(), before)
        thirty = {pid for pid, (_, mlb, _) in self.snapshot_rows().items() if mlb}
        self.assertIn(self.roster.relievers[1].id, thirty)
        self.assertNotIn(self.call_ups[0].id, thirty)

        # Once the half has started, later moves leave the snapshot alone.
        roster_moves.make_move(self.atl, self.call_ups[1], self.roster.relievers[0], season=SEASON, half=1)
        self.assertEqual(self.snapshot_rows(), before)
        self.assertEqual(models.HalfRosterSnapshot.objects.filter(season=SEASON).count(), 1)

    def test_opening_the_halfs_first_game_takes_the_snapshot(self):
        before = self.current_rows()
        game = road_games(self.atl)[0]
        plans.open_game(game)
        self.assertEqual(self.snapshot_rows(), before)

    def test_the_snapshot_is_retaken_until_the_half_starts(self):
        roster_moves.ensure_snapshot(SEASON, 1)
        bench = self.roster.bench[0]
        bench.is_ulmg_mlb_roster = False
        bench.save()
        roster_moves.ensure_snapshot(SEASON, 1)
        self.assertEqual(self.snapshot_rows()[bench.id], (self.atl.id, False, False))

        plans.open_game(road_games(self.atl)[0])
        bench.is_ulmg_mlb_roster = True
        bench.save()
        roster_moves.ensure_snapshot(SEASON, 1)
        self.assertEqual(self.snapshot_rows()[bench.id], (self.atl.id, False, False))

    def test_a_reset_restores_the_seasons_earliest_snapshot_exactly(self):
        before = self.current_rows()
        before_stats = {pid: stat_flags(models.Player.objects.get(pk=pid)) for pid in before}
        first = roster_moves.make_move(self.atl, self.call_ups[0], self.roster.relievers[1], season=SEASON, half=1)
        roster_moves.make_move(self.car, self.car_up, self.car_roster.bench[0], season=SEASON, half=1)
        for game in road_games(self.atl)[:15]:
            finish(game)
        roster_moves.make_move(self.atl, self.call_ups[1], self.call_ups[0], season=SEASON, half=1)
        roster_moves.make_move(self.atl, self.call_ups[2], self.roster.hitters[0], season=SEASON, half=1)
        # A second-half snapshot is not where a reset goes back to.
        with self.settings(TEAM_SEASON_HALF="2h"):
            roster_moves.ensure_snapshot(SEASON, 2)
        self.assertNotEqual(self.current_rows(), before)

        lines = []
        sim_data.reset_season(SEASON, progress=lines.append)

        self.assertEqual(self.current_rows(), before)
        after_stats = {pid: stat_flags(models.Player.objects.get(pk=pid)) for pid in before}
        for pid, stats in after_stats.items():
            if before_stats[pid] is None:
                self.assertIn(stats, (None, before[pid][1:]))
            else:
                self.assertEqual(stats, before[pid][1:], pid)
        self.assertEqual(stat_flags(self.call_ups[0]), (False, True))
        self.assertEqual(stat_flags(self.roster.relievers[1]), (True, False))
        self.assertFalse(models.RosterMove.objects.filter(season=SEASON).exists())
        self.assertFalse(models.RosterMove.objects.filter(pk=first.pk).exists())
        # The snapshots are kept, so a later reset goes back to the same roster.
        self.assertTrue(models.HalfRosterSnapshot.objects.filter(season=SEASON, half=1).exists())
        self.assertTrue(any("half 1 roster snapshot" in line for line in lines))

    def test_a_reset_with_no_snapshot_leaves_the_flags_alone(self):
        before = self.current_rows()
        lines = []
        sim_data.reset_season(SEASON, progress=lines.append)
        self.assertEqual(self.current_rows(), before)
        self.assertTrue(any("no roster snapshot" in line for line in lines))


class SingleActionTestCase(RosterMoveTestCase):
    """The to_mlb and to_aaa actions run on the same flag updates as a move."""

    def setUp(self):
        user = User.objects.create_superuser("commish", "c@example.com", "password")
        self.client = Client()
        self.client.force_login(user)

    def test_to_mlb_and_to_aaa_still_move_one_player(self):
        player = self.call_ups[0]
        self.assertEqual(self.client.get(f"/api/v1/player/{player.id}/to_mlb/").content, b"ok")
        self.assertEqual(flags(player), (True, False))
        self.assertEqual(stat_flags(player), (True, False))
        self.assertEqual(self.client.get(f"/api/v1/player/{player.id}/to_aaa/").content, b"ok")
        self.assertEqual(flags(player), (False, True))
        self.assertEqual(stat_flags(player), (False, True))
        self.assertFalse(models.RosterMove.objects.exists())

    def test_to_mlb_keeps_the_carded_last_season_gate(self):
        uncarded = models.Player.objects.create(
            name="ATL Uncarded", position="P", level="B", team=self.atl, is_ulmg_aaa_roster=True
        )
        response = self.client.get(f"/api/v1/player/{uncarded.id}/to_mlb/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only carded players", response.json()["error"])
        self.assertEqual(flags(uncarded), (False, True))


class SingleActionDuringAHalfTestCase(RosterMoveTestCase):
    """Once a half has started, one-player call-ups and send-downs would dodge the 10-move cap."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from tests.test_half_plan_views import create_owner

        cls.owner = create_owner("atl", cls.atl)
        cls.commissioner = User.objects.create_superuser("commish", "c@example.com", "password")

    def start_half(self):
        plans.open_game(road_games(self.atl)[0])

    def action(self, user, player, action):
        client = Client()
        client.force_login(user)
        return client.get(f"/api/v1/player/{player.id}/{action}/")

    def test_before_the_half_starts_an_owner_can_still_move_one_player(self):
        response = self.action(self.owner, self.call_ups[0], "to_mlb")
        self.assertEqual(response.content, b"ok")
        self.assertEqual(flags(self.call_ups[0]), (True, False))

    def test_once_the_half_starts_an_owner_must_use_a_paired_move(self):
        self.start_half()
        for player, action in ((self.call_ups[0], "to_mlb"), (self.roster.relievers[1], "to_aaa")):
            with self.subTest(action=action):
                before = flags(player)
                response = self.action(self.owner, player, action)
                self.assertEqual(response.status_code, 400)
                self.assertIn("roster move", response.json()["error"])
                self.assertEqual(flags(player), before)

    def test_once_the_half_starts_the_commissioner_can_still_move_one_player(self):
        self.start_half()
        response = self.action(self.commissioner, self.call_ups[0], "to_mlb")
        self.assertEqual(response.content, b"ok")
        self.assertEqual(flags(self.call_ups[0]), (True, False))
