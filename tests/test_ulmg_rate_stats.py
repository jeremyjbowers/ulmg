# ABOUTME: Tests the rate stats stored on a ULMG season line, and that a hold is summed onto it.
# ABOUTME: Hitting keeps the slash, ISO, OPS, K% and BB%. Pitching keeps K/9, BB/9, decisions, ERA and WHIP.

from types import SimpleNamespace

from django.test import SimpleTestCase

from ulmg import season_record
from ulmg.box_score import AWAY, HOME


HITTING = {
    "g": 10, "pa": 40, "ab": 32, "r": 8, "h": 10, "2b": 2, "3b": 1, "hr": 2,
    "rbi": 9, "bb": 5, "so": 8, "sb": 1, "cs": 0, "gdp": 1, "sf": 1, "hbp": 2, "sh": 0,
}


def pitching_line(player, outs, **counts):
    base = dict(bf=0, h=0, r=0, er=0, bb=0, so=0, hr=0, pitches=0)
    base.update(counts)
    return SimpleNamespace(player=player, outs=outs, **base)


class RateStatsTest(SimpleTestCase):
    def test_a_hitters_line_stores_the_slash_iso_ops_and_the_strikeout_and_walk_rates(self):
        stats = season_record.hit_stats(dict(HITTING))
        self.assertEqual(stats["1b"], 5)
        self.assertEqual(stats["avg"], 10 / 32)
        self.assertEqual(stats["obp"], 17 / 40)
        self.assertEqual(stats["slg"], 20 / 32)
        self.assertEqual(stats["ops"], stats["obp"] + stats["slg"])
        self.assertEqual(stats["iso"], stats["slg"] - stats["avg"])
        self.assertEqual(stats["k_pct"], 8 / 40)
        self.assertEqual(stats["bb_pct"], 5 / 40)
        self.assertEqual(stats["hr"], 2)

    def test_a_line_with_no_at_bats_leaves_the_slash_empty_and_still_stores_the_plate_appearance_rates(self):
        stats = season_record.hit_stats({"g": 1, "pa": 2, "ab": 0, "h": 0, "2b": 0, "3b": 0, "hr": 0, "bb": 1, "so": 0, "hbp": 1, "sf": 0})
        self.assertEqual((stats["avg"], stats["slg"], stats["ops"], stats["iso"]), (None, None, None, None))
        self.assertEqual(stats["obp"], 1.0)
        self.assertEqual((stats["k_pct"], stats["bb_pct"]), (0.0, 0.5))

    def test_a_pitchers_line_stores_strikeouts_and_walks_per_nine_decisions_era_and_whip(self):
        row = {
            "g": 5, "gs": 0, "w": 1, "l": 2, "sv": 0, "hld": 3, "tbf": 40,
            "h": 12, "r": 6, "er": 5, "bb": 4, "so": 15, "hr": 2, "pitches": 200, "outs": 30,
        }
        stats = season_record.pitch_stats(dict(row))
        self.assertEqual(stats["ip"], 10.0)
        self.assertEqual(stats["era"], 4.5)
        self.assertEqual(stats["whip"], 1.6)
        self.assertEqual(stats["k_9"], 13.5)
        self.assertEqual(stats["bb_9"], 3.6)
        self.assertEqual((stats["w"], stats["l"], stats["sv"], stats["hld"]), (1, 2, 0, 3))
        self.assertNotIn("outs", stats)

    def test_no_outs_leaves_the_pitching_rates_empty_and_keeps_the_decisions(self):
        stats = season_record.pitch_stats({
            "g": 1, "w": 0, "l": 0, "sv": 0, "hld": 0, "er": 0, "bb": 0, "h": 0, "so": 0, "hr": 0, "tbf": 0, "outs": 0,
        })
        self.assertEqual((stats["era"], stats["whip"], stats["k_9"], stats["bb_9"]), (None, None, None, None))
        self.assertEqual(stats["ip"], 0.0)
        self.assertEqual(stats["hld"], 0)

    def test_a_hold_in_the_box_score_is_summed_onto_the_pitchers_season_line(self):
        winner, holder, loser = SimpleNamespace(id=1), SimpleNamespace(id=2), SimpleNamespace(id=3)
        box = SimpleNamespace(
            batting={AWAY: [], HOME: []},
            pitching={
                AWAY: [pitching_line(loser, 27, bf=30, h=8, r=4, er=4, bb=2, so=6, hr=1, pitches=90)],
                HOME: [
                    pitching_line(winner, 18, bf=22, h=5, r=1, er=1, bb=1, so=7, hr=0, pitches=80),
                    pitching_line(holder, 6, bf=8, h=2, r=0, er=0, bb=1, so=3, hr=0, pitches=25),
                ],
            },
            totals={AWAY: {"r": 1}, HOME: {"r": 4}},
            teams={AWAY: SimpleNamespace(id=10), HOME: SimpleNamespace(id=11)},
            win=winner,
            loss=loser,
            save=None,
            holds=[holder],
        )
        totals = season_record.Totals()
        totals.add(box)
        self.assertEqual(totals.pitching[holder.id]["hld"], 1)
        self.assertEqual(totals.pitching[winner.id]["hld"], 0)
        self.assertEqual(totals.pitching[winner.id]["w"], 1)
        self.assertEqual(totals.pitching[loser.id]["l"], 1)
        stats = season_record.pitch_stats(totals.pitching[holder.id])
        self.assertEqual(stats["hld"], 1)
        self.assertEqual(stats["ip"], 2.0)
        self.assertEqual(stats["k_9"], 13.5)
        self.assertEqual(stats["bb_9"], 4.5)
        self.assertEqual(stats["era"], 0.0)
        self.assertEqual(stats["whip"], 1.5)
