# ABOUTME: Unit tests for the line score, the box score notes, and hold credits.
# ABOUTME: A played zero stays 0; X is a home club that does not bat. Notes name the extras. A hold is not a win, a loss or a save.

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase

from ulmg import models
from ulmg.box_score import (
    AWAY,
    HOME,
    SKIPPED,
    UNPLAYED,
    BoxScore,
    PitchingLine,
    PlateAppearance,
    _ordinal,
    box_score,
    holds,
    line_score_cells,
)

Event = models.GameEvent


class LineScoreCellsTest(SimpleTestCase):
    def test_a_new_game_shows_nine_innings_with_dashes_except_the_current_half(self):
        cells = line_score_cells({AWAY: {}, HOME: {}}, inning=1, half="top", final=False)
        self.assertEqual(cells["innings"], list(range(1, 10)))
        self.assertEqual(cells[AWAY], [0] + [UNPLAYED] * 8)
        self.assertEqual(cells[HOME], [UNPLAYED] * 9)

    def test_a_played_zero_stays_zero_and_future_innings_are_dashes(self):
        cells = line_score_cells({AWAY: {1: 0}, HOME: {}}, inning=1, half="bottom", final=False)
        self.assertEqual(cells[AWAY][0], 0)
        self.assertEqual(cells[HOME][0], 0)
        self.assertEqual(cells[AWAY][1], UNPLAYED)
        self.assertEqual(cells[HOME][1], UNPLAYED)

    def test_runs_in_a_played_inning_are_the_runs(self):
        cells = line_score_cells({AWAY: {1: 2}, HOME: {1: 0}}, inning=2, half="top", final=False)
        self.assertEqual(cells[AWAY][:2], [2, 0])
        self.assertEqual(cells[HOME][:2], [0, UNPLAYED])
        self.assertEqual(cells[AWAY][2], UNPLAYED)

    def test_home_does_not_bat_in_the_ninth_when_ahead(self):
        away = {i: 0 for i in range(1, 10)}
        home = {i: (1 if i in (1, 4, 7) else 0) for i in range(1, 9)}
        cells = line_score_cells({AWAY: away, HOME: home}, inning=9, half="top", final=True)
        self.assertEqual(cells[HOME][8], SKIPPED)
        self.assertEqual(len(cells["innings"]), 9)
        self.assertEqual(cells[AWAY][8], 0)

    def test_extra_innings_extend_the_line(self):
        away = {i: 0 for i in range(1, 11)}
        home = {i: 0 for i in range(1, 10)}
        cells = line_score_cells({AWAY: away, HOME: home}, inning=10, half="bottom", final=False)
        self.assertEqual(cells["innings"], list(range(1, 11)))
        self.assertEqual(cells[HOME][9], 0)
        self.assertEqual(cells[AWAY][9], 0)


class OrdinalTest(SimpleTestCase):
    def test_the_teens_stay_th_and_the_rest_follow_the_last_digit(self):
        self.assertEqual(
            [_ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23)],
            ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "23rd"],
        )


def _team(abbreviation):
    return models.Team.objects.create(city=abbreviation, abbreviation=abbreviation, nickname=abbreviation)


def _player(name):
    return models.Player.objects.create(name=name)


def _event(kind, payload):
    return SimpleNamespace(kind=kind, payload=payload)


def _start(away, home, away_pitcher, home_pitcher):
    return _event(Event.START, {
        "lineups": {
            AWAY: [{"player": player.id, "position": position} for player, position in away],
            HOME: [{"player": player.id, "position": position} for player, position in home],
        },
        "starters": {AWAY: away_pitcher.id, HOME: home_pitcher.id},
    })


def _bases(occupied=None):
    bases = {"first": None, "second": None, "third": None}
    if occupied:
        bases.update(occupied)
    return bases


def _pa(batting, batter, pitcher, outcome, *, inning=1, half="top", outs=0, bases=None, after=None, outs_added=0, runs=0, baserunning=None, completed=True):
    return _event(Event.PLATE_APPEARANCE, {
        "batting": batting,
        "batter": batter.id,
        "pitcher": pitcher.id,
        "before": {"inning": inning, "half": half, "outs": outs, "bases": _bases(bases)},
        "result": {
            "outcome": outcome,
            "batter_completed": completed,
            "change": {"outs_added": outs_added, "runs_scored": runs, "bases": _bases(after)},
            "pitches": [{}],
            "baserunning": baserunning or [],
        },
    })


def _log(road, home):
    return SimpleNamespace(game=SimpleNamespace(series=SimpleNamespace(road_team=road, home_team=home)), state={"inning": 9, "half": "bottom"})


def _notes(box):
    return [(note.label, note.text) for note in box.notes]


class BoxScoreNotesTest(TestCase):
    def setUp(self):
        self.road = _team("ATL")
        self.home = _team("CHI")
        self.soto = _player("Juan Soto")
        self.tatis = _player("Fernando Tatis Jr")
        self.acuna = _player("Ronald Acuna Jr")
        self.olson = _player("Matt Olson")
        self.swanson = _player("Dansby Swanson")
        self.burke = _player("Sean Burke")
        self.sale = _player("Chris Sale")

    def box(self, events):
        return box_score(self.log(events), events)

    def log(self, events):
        return _log(self.road, self.home)

    def start(self):
        return _start(
            [(self.soto, "RF"), (self.tatis, "SS"), (self.acuna, "LF")],
            [(self.olson, "1B"), (self.swanson, "SS")],
            self.sale,
            self.burke,
        )

    def test_doubles_triples_and_homers_are_named_with_the_inning_and_the_pitcher(self):
        events = [
            self.start(),
            _pa(AWAY, self.tatis, self.burke, "double", inning=1),
            _pa(AWAY, self.tatis, self.burke, "double", inning=5),
            _pa(AWAY, self.acuna, self.burke, "triple", inning=3),
            _pa(
                AWAY, self.soto, self.burke, "home_run", inning=4, outs=2,
                bases={"first": self.tatis.id}, runs=2,
                baserunning=[{"Scored": {"runner": str(self.tatis.id)}}, {"Scored": {"runner": str(self.soto.id)}}],
            ),
            _pa(
                AWAY, self.acuna, self.burke, "strikeout", inning=7, outs=2,
                bases={"first": self.soto.id}, after={"first": self.soto.id}, outs_added=1,
            ),
        ]
        notes = dict(_notes(self.box(events)))
        self.assertEqual(
            notes["2B"],
            "Fernando Tatis Jr 2 (1st inning off Sean Burke; 5th inning off Sean Burke)",
        )
        self.assertEqual(notes["3B"], "Ronald Acuna Jr (3rd inning off Sean Burke)")
        self.assertEqual(notes["HR"], "Juan Soto (4th inning off Sean Burke, 1 on, 2 outs)")
        self.assertEqual(notes["LOB"], "ATL 1, CHI 0")
        self.assertEqual([label for label, _ in _notes(self.box(events))], ["2B", "3B", "HR", "LOB"])

    def test_steals_sacrifices_double_plays_hit_batsmen_and_intentional_walks_are_named(self):
        events = [
            self.start(),
            _pa(
                HOME, self.swanson, self.sale, "strikeout", inning=1, half="bottom",
                bases={"first": self.olson.id},
                baserunning=[{"StolenBase": {"runner": str(self.olson.id), "to": "Second"}}],
            ),
            _pa(
                HOME, self.swanson, self.sale, "caught_stealing", inning=2, half="bottom", completed=False,
                bases={"first": self.olson.id}, outs_added=1,
                baserunning=[{"CaughtStealing": {"runner": str(self.olson.id), "at": "Second"}}],
            ),
            _pa(HOME, self.olson, self.sale, "sacrifice_fly", inning=3, half="bottom", outs_added=1),
            _pa(HOME, self.olson, self.sale, "bunt_sacrifice", inning=4, half="bottom", outs_added=1),
            _pa(HOME, self.olson, self.sale, "grounded_into_double_play", inning=5, half="bottom", outs_added=2),
            _pa(HOME, self.olson, self.sale, "hit_by_pitch", inning=6, half="bottom"),
            _pa(HOME, self.olson, self.sale, "intentional_walk", inning=7, half="bottom"),
        ]
        notes = dict(_notes(self.box(events)))
        self.assertEqual(notes["SB"], "Matt Olson (2nd base off Chris Sale)")
        self.assertEqual(notes["CS"], "Matt Olson (2nd base by Chris Sale)")
        self.assertEqual(notes["SF"], "Matt Olson")
        self.assertEqual(notes["SH"], "Matt Olson")
        self.assertEqual(notes["GIDP"], "Matt Olson")
        self.assertEqual(notes["HBP"], "Matt Olson (by Chris Sale)")
        self.assertEqual(notes["IBB"], "Matt Olson (by Chris Sale)")
        self.assertEqual(notes["DP"], "ATL 1")
        self.assertEqual(notes["LOB"], "ATL 0, CHI 0")

    def test_a_game_with_no_extras_still_lists_runners_left_on_base(self):
        events = [self.start(), _pa(AWAY, self.soto, self.burke, "strikeout", outs_added=1)]
        self.assertEqual(_notes(self.box(events)), [("LOB", "ATL 0, CHI 0")])

    def test_the_notes_render_after_the_pitching_lines_and_before_the_footnote(self):
        events = [self.start(), _pa(AWAY, self.soto, self.burke, "home_run", inning=11, runs=1, baserunning=[{"Scored": {"runner": str(self.soto.id)}}])]
        box = self.box(events)
        html = render_to_string("includes/box_score.html", {"box": box, "game": self.log(events).game})
        self.assertLess(html.find("box-pitching"), html.find("box-notes"))
        self.assertLess(html.find("box-notes"), html.find("A run is unearned"))
        self.assertIn('<span class="font-bold">HR</span>: Juan Soto (11th inning off Sean Burke, 0 on, 0 out)', html)
        self.assertIn('<span class="font-bold">LOB</span>: ATL 0, CHI 0', html)
        self.assertLess(html.find(">HR</span>"), html.find(">LOB</span>"))


def _pitcher(pid, name):
    return SimpleNamespace(id=pid, name=name)


def _hold_pa(pitcher_id, before, after, runners=0, fielding=HOME):
    """A plate appearance. before and after are (away, home) scores."""
    return PlateAppearance(
        0,
        fielding,
        pitcher_id,
        {AWAY: before[0], HOME: before[1]},
        {AWAY: after[0], HOME: after[1]},
        runners,
    )


def _credited(final, lines, appearances, starter, win, fielding=HOME):
    """Holds for one side's staff. lines is in the order they entered."""
    pitching = {AWAY: {}, HOME: {}}
    for line in lines:
        pitching[fielding][line.player.id] = line
    starters = {AWAY: None, HOME: None}
    starters[fielding] = starter.id
    return holds({AWAY: final[0], HOME: final[1]}, appearances, pitching, starters, win)


class HoldsTest(SimpleTestCase):
    def test_one_out_with_a_three_run_lead_is_a_hold_and_the_starter_and_finisher_are_not(self):
        starter, setup, closer = _pitcher(1, "Starter"), _pitcher(2, "Setup"), _pitcher(3, "Closer")
        lines = [PitchingLine(starter, outs=18), PitchingLine(setup, outs=1), PitchingLine(closer, outs=3)]
        appearances = [
            _hold_pa(setup.id, (0, 3), (0, 3)),
            _hold_pa(closer.id, (0, 3), (0, 3)),
        ]
        self.assertEqual(_credited((0, 3), lines, appearances, starter, starter), [setup])

    def test_two_setup_men_are_credited_in_the_order_they_pitched(self):
        starter, seventh, eighth, closer = (
            _pitcher(1, "Starter"), _pitcher(2, "Seventh"), _pitcher(3, "Eighth"), _pitcher(4, "Closer")
        )
        lines = [
            PitchingLine(starter, outs=18),
            PitchingLine(seventh, outs=3),
            PitchingLine(eighth, outs=3),
            PitchingLine(closer, outs=3),
        ]
        appearances = [
            _hold_pa(seventh.id, (0, 2), (0, 2)),
            _hold_pa(eighth.id, (0, 2), (1, 2)),
            _hold_pa(closer.id, (1, 2), (1, 2)),
        ]
        self.assertEqual(_credited((1, 2), lines, appearances, starter, starter), [seventh, eighth])

    def test_a_four_run_lead_with_the_bases_empty_is_not_a_hold_until_he_pitches_three_innings(self):
        starter, short, long, closer = (
            _pitcher(1, "Starter"), _pitcher(2, "Short"), _pitcher(3, "Long"), _pitcher(4, "Closer")
        )
        lines = [
            PitchingLine(starter, outs=9),
            PitchingLine(short, outs=3),
            PitchingLine(long, outs=9),
            PitchingLine(closer, outs=3),
        ]
        appearances = [
            _hold_pa(short.id, (0, 4), (0, 4), runners=0),
            _hold_pa(long.id, (0, 5), (0, 5), runners=0),
            _hold_pa(closer.id, (0, 5), (0, 5)),
        ]
        self.assertEqual(_credited((0, 5), lines, appearances, starter, starter), [long])

    def test_the_tying_run_on_base_is_a_hold_even_with_a_lead_of_more_than_three(self):
        starter, setup, closer = _pitcher(1, "Starter"), _pitcher(2, "Setup"), _pitcher(3, "Closer")
        lines = [PitchingLine(starter, outs=18), PitchingLine(setup, outs=1), PitchingLine(closer, outs=3)]
        appearances = [_hold_pa(setup.id, (0, 4), (0, 4), runners=3), _hold_pa(closer.id, (0, 4), (0, 4))]
        self.assertEqual(_credited((0, 4), lines, appearances, starter, starter), [setup])

    def test_giving_up_the_lead_or_recording_no_out_is_not_a_hold(self):
        starter, blown, quiet, closer = (
            _pitcher(1, "Starter"), _pitcher(2, "Blown"), _pitcher(3, "Quiet"), _pitcher(4, "Closer")
        )
        lines = [
            PitchingLine(starter, outs=15),
            PitchingLine(blown, outs=3),
            PitchingLine(quiet, outs=0),
            PitchingLine(closer, outs=3),
        ]
        appearances = [
            _hold_pa(blown.id, (0, 2), (2, 2)),
            _hold_pa(quiet.id, (2, 3), (2, 3)),
            _hold_pa(closer.id, (2, 3), (2, 3)),
        ]
        self.assertEqual(_credited((2, 3), lines, appearances, starter, starter), [])

    def test_a_reliever_who_is_the_winning_pitcher_does_not_also_get_a_hold(self):
        starter, winner, closer = _pitcher(1, "Starter"), _pitcher(2, "Winner"), _pitcher(3, "Closer")
        lines = [PitchingLine(starter, outs=6), PitchingLine(winner, outs=15), PitchingLine(closer, outs=3)]
        appearances = [_hold_pa(winner.id, (0, 2), (0, 2)), _hold_pa(closer.id, (0, 2), (0, 2))]
        self.assertEqual(_credited((0, 2), lines, appearances, starter, winner), [])

    def test_a_complete_game_and_a_tie_have_no_hold(self):
        starter = _pitcher(1, "Starter")
        complete = _credited((0, 1), [PitchingLine(starter, outs=27)], [], starter, starter)
        self.assertEqual(complete, [])
        tied = holds(
            {AWAY: 2, HOME: 2},
            [_hold_pa(2, (0, 2), (0, 2))],
            {HOME: {2: PitchingLine(_pitcher(2, "Setup"), outs=3)}, AWAY: {}},
            {HOME: 1, AWAY: None},
            None,
        )
        self.assertEqual(tied, [])

    def test_a_reliever_on_the_losing_side_does_not_get_a_hold(self):
        starter, setup, closer = _pitcher(1, "Starter"), _pitcher(2, "Setup"), _pitcher(3, "Closer")
        lines = [PitchingLine(starter, outs=18), PitchingLine(setup, outs=3), PitchingLine(closer, outs=3)]
        appearances = [_hold_pa(setup.id, (0, 3), (0, 3)), _hold_pa(closer.id, (0, 3), (1, 3))]
        # Home led while these relievers worked, then lost. A hold is only credited to the winning side.
        self.assertEqual(_credited((4, 3), lines, appearances, starter, starter, fielding=HOME), [])

    def test_the_box_score_names_each_hold(self):
        starter, setup, closer = _pitcher(1, "Starter"), _pitcher(2, "Setup"), _pitcher(3, "Closer")
        loser = _pitcher(4, "Loser")
        road, home = SimpleNamespace(abbreviation="CAR"), SimpleNamespace(abbreviation="ATL")
        zeros = {
            name: 0
            for name in ("ab", "r", "h", "rbi", "bb", "so", "doubles", "triples", "hr", "sb", "cs", "gidp", "sf", "lob")
        }
        box = BoxScore(
            innings=[1],
            line={AWAY: [0], HOME: [1]},
            totals={AWAY: {"r": 0, "h": 0, "e": 0}, HOME: {"r": 1, "h": 1, "e": 0}},
            batting={AWAY: [], HOME: []},
            batting_totals={AWAY: dict(zeros), HOME: dict(zeros)},
            team_lob={AWAY: 0, HOME: 0},
            pitching={
                AWAY: [PitchingLine(loser, outs=3)],
                HOME: [PitchingLine(starter, outs=18), PitchingLine(setup, outs=3), PitchingLine(closer, outs=3)],
            },
            teams={AWAY: road, HOME: home},
            win=starter,
            loss=loser,
            save=closer,
            holds=[setup],
            final=True,
        )
        game = SimpleNamespace(series=SimpleNamespace(road_team=road, home_team=home))
        html = render_to_string("includes/box_score.html", {"box": box, "game": game})
        self.assertIn(">H<", html.replace(" ", ""))
        self.assertIn("Setup", html)
        self.assertIn("(H)", html)
        self.assertIn("(S)", html)
        self.assertNotIn("Starter (H)", html)
        self.assertNotIn("Closer (H)", html)
