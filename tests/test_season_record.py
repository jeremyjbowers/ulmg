# ABOUTME: Tests the ULMG season record: 6-ulmg lines and team records built from final game logs, and their rebuild.
# ABOUTME: Plays two real games against the engine, then checks the stored totals, the rebuild command and its dry run.

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from tests import game_fixtures as gf
from ulmg import box_score, models, season_record, sim_game

AWAY, HOME = sim_game.AWAY, sim_game.HOME
ULMG = models.PlayerStatSeason.ULMG

BATTING_KEYS = {
    "pa": "pa", "ab": "ab", "r": "r", "h": "h", "2b": "doubles", "3b": "triples", "hr": "hr", "rbi": "rbi",
    "bb": "bb", "so": "so", "sb": "sb", "cs": "cs", "gdp": "gidp", "sf": "sf", "hbp": "hbp", "sh": "sh",
}
PITCHING_KEYS = {"tbf": "bf", "h": "h", "r": "r", "er": "er", "bb": "bb", "so": "so", "hr": "hr", "pitches": "pitches"}


def stored_lines(season):
    rows = models.PlayerStatSeason.objects.filter(season=season, classification=ULMG)
    return {row.player_id: (row.hit_stats, row.pitch_stats) for row in rows}


def stored_records(season):
    rows = models.TeamSeasonRecord.objects.filter(season=season)
    return {row.team_id: (row.wins, row.losses, row.runs_scored, row.runs_allowed) for row in rows}


class TwoFinalGamesTestCase(gf.EngineMixin, TestCase):
    """
    Day 1 and day 2 of one series, played to their finals by the visiting
    manager. Every hitter strikes out except the home leadoff man, who
    homers, so each game ends 3-0 to the home team.
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
        cls.logs = []
        for _ in range(2):
            game = gf.next_road_game(cls.road.team)
            log = sim_game.open_game(game, cls.manager, (AWAY,), seeds=next_seed)
            cls.logs.append(gf.play_out(log, cls.manager, next_seed))
        cls.games = [log.game for log in cls.logs]

    def boxes(self):
        return [box_score.box_score(log) for log in self.logs]

    def expected_lines(self):
        """Every player's line, summed here from the two box scores."""
        batting, pitching = {}, {}
        for box in self.boxes():
            for side in (AWAY, HOME):
                for line in box.batting[side]:
                    row = batting.setdefault(line.player.id, {key: 0 for key in BATTING_KEYS} | {"g": 0})
                    row["g"] += 1
                    for key, name in BATTING_KEYS.items():
                        row[key] += getattr(line, name)
                for index, line in enumerate(box.pitching[side]):
                    row = pitching.setdefault(
                        line.player.id,
                        {key: 0 for key in PITCHING_KEYS} | {"g": 0, "gs": 0, "w": 0, "l": 0, "sv": 0, "hld": 0, "outs": 0},
                    )
                    row["g"] += 1
                    row["gs"] += 1 if index == 0 else 0
                    row["outs"] += line.outs
                    for key, name in PITCHING_KEYS.items():
                        row[key] += getattr(line, name)
            for key, player in (("w", box.win), ("l", box.loss), ("sv", box.save)):
                if player is not None:
                    pitching[player.id][key] += 1
            for player in box.holds:
                pitching[player.id]["hld"] += 1
        return batting, pitching

    def test_both_games_are_final(self):
        for log, game in zip(self.logs, self.games):
            self.assertEqual(log.state["status"], "final")
            self.assertEqual((game.road_score, game.home_score), (0, 3))
        self.assertEqual([g.day for g in self.games], [1, 2])

    def test_a_final_writes_every_players_6_ulmg_line_as_the_sum_of_his_box_score_lines(self):
        batting, pitching = self.expected_lines()
        lines = stored_lines(gf.SEASON)
        self.assertEqual(set(lines), set(batting) | set(pitching))
        for pid, row in batting.items():
            hit_stats = lines[pid][0]
            for key, value in row.items():
                self.assertEqual(hit_stats[key], value, f"{key} for player {pid}")
        for pid, row in pitching.items():
            pitch_stats = lines[pid][1]
            for key, value in row.items():
                if key == "outs":
                    continue
                self.assertEqual(pitch_stats[key], value, f"{key} for player {pid}")
            self.assertEqual(pitch_stats["ip"], float(f"{row['outs'] // 3}.{row['outs'] % 3}"))

    def test_the_home_leadoff_line_and_the_rates_follow_the_sites_stat_keys(self):
        leadoff = models.PlayerStatSeason.objects.get(
            player=self.home.hitters[0], season=gf.SEASON, classification=ULMG
        )
        stats = leadoff.hit_stats
        self.assertEqual((stats["g"], stats["ab"], stats["h"], stats["hr"], stats["r"], stats["rbi"]), (2, 6, 6, 6, 6, 6))
        self.assertEqual((stats["avg"], stats["obp"], stats["slg"], stats["ops"], stats["iso"]), (1.0, 1.0, 4.0, 5.0, 3.0))
        self.assertEqual((stats["k_pct"], stats["bb_pct"]), (0.0, 0.0))
        self.assertIsNone(leadoff.pitch_stats)
        strikeout = models.PlayerStatSeason.objects.get(
            player=self.road.hitters[0], season=gf.SEASON, classification=ULMG
        ).hit_stats
        self.assertEqual((strikeout["h"], strikeout["avg"], strikeout["k_pct"]), (0, 0.0, 1.0))

    def test_pitching_decisions_and_rates_are_summed(self):
        _, pitching = self.expected_lines()
        lines = stored_lines(gf.SEASON)
        self.assertEqual(sum(lines[pid][1]["w"] for pid in pitching), 2)
        self.assertEqual(sum(lines[pid][1]["l"] for pid in pitching), 2)
        loser = lines[self.road.starters[0].id][1]
        self.assertEqual((loser["l"], loser["r"], loser["er"], loser["hr"], loser["gs"]), (1, 3, 3, 3, 1))
        outs = pitching[self.road.starters[0].id]["outs"]
        self.assertAlmostEqual(loser["era"], 27 * 3 / outs)
        self.assertAlmostEqual(loser["whip"], 3 * 3 / outs)
        self.assertAlmostEqual(loser["hr_9"], 27 * 3 / outs)
        self.assertEqual(lines[self.home.starters[0].id][1]["w"], 1)
        self.assertEqual(lines[self.home.starters[1].id][1]["w"], 1)

    def test_a_final_writes_both_team_records(self):
        records = stored_records(gf.SEASON)
        self.assertEqual(records, {self.home.team.id: (2, 0, 6, 0), self.road.team.id: (0, 2, 0, 6)})
        record = models.TeamSeasonRecord.objects.get(team=self.home.team, season=gf.SEASON)
        self.assertEqual(record.pct_display, "1.000")

    def test_rebuilding_from_the_game_logs_gives_the_same_lines_and_records(self):
        lines, records = stored_lines(gf.SEASON), stored_records(gf.SEASON)
        models.PlayerStatSeason.objects.filter(season=gf.SEASON, classification=ULMG).delete()
        models.TeamSeasonRecord.objects.filter(season=gf.SEASON).delete()
        out = StringIO()
        call_command("rebuild_season_record", "--season", str(gf.SEASON), stdout=out)
        self.assertEqual(stored_lines(gf.SEASON), lines)
        self.assertEqual(stored_records(gf.SEASON), records)
        self.assertIn("2 final games", out.getvalue())

    def test_a_rebuild_corrects_a_drifted_line_and_removes_one_with_no_games(self):
        lines, records = stored_lines(gf.SEASON), stored_records(gf.SEASON)
        drifted = models.PlayerStatSeason.objects.get(player=self.home.hitters[0], season=gf.SEASON, classification=ULMG)
        drifted.hit_stats = dict(drifted.hit_stats, hr=99)
        drifted.save()
        models.TeamSeasonRecord.objects.filter(team=self.road.team, season=gf.SEASON).update(wins=40)
        idle = self.road.bench[1]
        models.PlayerStatSeason.objects.create(player=idle, season=gf.SEASON, classification=ULMG, hit_stats={"hr": 1})
        other_team = models.Team.objects.exclude(pk__in=[self.home.team.pk, self.road.team.pk]).first()
        models.TeamSeasonRecord.objects.create(team=other_team, season=gf.SEASON, wins=1)
        season_record.rebuild_season(gf.SEASON)
        self.assertEqual(stored_lines(gf.SEASON), lines)
        self.assertEqual(stored_records(gf.SEASON), records)

    def test_a_dry_run_reports_and_changes_nothing(self):
        players = len(stored_lines(gf.SEASON))
        models.PlayerStatSeason.objects.filter(season=gf.SEASON, classification=ULMG).delete()
        models.TeamSeasonRecord.objects.filter(season=gf.SEASON).delete()
        out = StringIO()
        call_command("rebuild_season_record", "--season", str(gf.SEASON), "--dry-run", stdout=out)
        self.assertFalse(models.PlayerStatSeason.objects.filter(season=gf.SEASON, classification=ULMG).exists())
        self.assertFalse(models.TeamSeasonRecord.objects.filter(season=gf.SEASON).exists())
        self.assertIn("Dry run", out.getvalue())
        self.assertIn(f"would write {players} player lines and 2 team records", out.getvalue())

    def test_the_rebuild_never_touches_other_classifications_or_seasons(self):
        mlb = list(models.PlayerStatSeason.objects.exclude(classification=ULMG).values_list("pk", "hit_stats", "pitch_stats"))
        other = models.PlayerStatSeason.objects.create(
            player=self.home.hitters[0], season=gf.SEASON + 1, classification=ULMG, hit_stats={"hr": 3}
        )
        season_record.rebuild_season(gf.SEASON)
        self.assertEqual(
            list(models.PlayerStatSeason.objects.exclude(classification=ULMG).values_list("pk", "hit_stats", "pitch_stats")),
            mlb,
        )
        other.refresh_from_db()
        self.assertEqual(other.hit_stats, {"hr": 3})

    def test_a_game_that_is_not_final_counts_for_nothing(self):
        lines, records = stored_lines(gf.SEASON), stored_records(gf.SEASON)
        game = gf.next_road_game(self.road.team)
        next_seed = gf.seeds(5000)
        log = sim_game.open_game(game, self.manager, (AWAY,), seeds=next_seed)
        for _ in range(5):
            log = gf.refresh(log)
            sim_game.step(log, self.manager, sim_game.Play(log).sequence, seeds=next_seed)
        season_record.rebuild_season(gf.SEASON)
        self.assertEqual(stored_lines(gf.SEASON), lines)
        self.assertEqual(stored_records(gf.SEASON), records)
