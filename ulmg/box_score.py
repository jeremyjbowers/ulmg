# ABOUTME: The box score of a sim game, computed from its log alone: line score, batting and pitching lines, LOB.
# ABOUTME: Also credits the win, loss and save under MLB rules 9.17 and 9.19, charging each run to the pitcher responsible for it.

from dataclasses import dataclass, field

from ulmg import models

Event = models.GameEvent
AWAY = Event.AWAY
HOME = Event.HOME
SIDES = (AWAY, HOME)

HITS = {"single", "double", "triple", "home_run", "bunt_single"}
WALKS = {"walk", "intentional_walk"}
NOT_AT_BATS = {"walk", "hit_by_pitch", "intentional_walk", "bunt_sacrifice", "sacrifice_fly", "caught_stealing"}
BATTER_OUTS = {
    "strikeout",
    "bip_out",
    "ground_out",
    "fly_out",
    "line_out",
    "grounded_into_double_play",
    "sacrifice_fly",
    "bunt_sacrifice",
    "bunt_out",
}
GIDP = "grounded_into_double_play"
SACRIFICE_FLY = "sacrifice_fly"

# Rule 9.17(b): a starter needs five complete innings for the win.
STARTER_WIN_OUTS = 15
# Rule 9.17(c) comment: a reliever is ineffective in a brief appearance when he
# pitches less than an inning and two or more earned runs score while he pitches.
BRIEF_OUTS = 3
INEFFECTIVE_EARNED_RUNS = 2
# Rule 9.19.
SAVE_MIN_OUTS = 1
SAVE_LEAD = 3
SAVE_INNING_OUTS = 3
SAVE_LONG_OUTS = 9


def other(side):
    return HOME if side == AWAY else AWAY


@dataclass
class BattingLine:
    player: object
    position: str
    substitute: bool = False
    pa: int = 0
    ab: int = 0
    r: int = 0
    h: int = 0
    rbi: int = 0
    bb: int = 0
    so: int = 0
    doubles: int = 0
    triples: int = 0
    hr: int = 0
    sb: int = 0
    cs: int = 0
    lob: int = 0
    gidp: int = 0
    sf: int = 0

    COUNTS = ("pa", "ab", "r", "h", "rbi", "bb", "so", "doubles", "triples", "hr", "sb", "cs", "lob", "gidp", "sf")


@dataclass
class PitchingLine:
    player: object
    outs: int = 0
    bf: int = 0
    h: int = 0
    r: int = 0
    er: int = 0
    bb: int = 0
    so: int = 0
    hr: int = 0
    pitches: int = 0
    lead_outs: int = 0

    @property
    def ip(self):
        return f"{self.outs // 3}.{self.outs % 3}"


@dataclass
class Run:
    side: str
    runner: int
    charged: int
    earned: bool
    pa: int
    pitcher: int
    score: dict


@dataclass
class PlateAppearance:
    index: int
    fielding: str
    pitcher: int
    before: dict
    after: dict
    runners: int


@dataclass
class BoxScore:
    innings: list = field(default_factory=list)
    line: dict = field(default_factory=dict)
    totals: dict = field(default_factory=dict)
    batting: dict = field(default_factory=dict)
    batting_totals: dict = field(default_factory=dict)
    team_lob: dict = field(default_factory=dict)
    pitching: dict = field(default_factory=dict)
    win: object = None
    loss: object = None
    save: object = None
    final: bool = False
    teams: dict = field(default_factory=dict)

    @property
    def sides(self):
        """(side, team, batting lines, batting totals, team LOB, pitching lines) for the visitors, then the home team."""
        return [
            (
                side,
                self.teams.get(side),
                self.batting.get(side, []),
                self.batting_totals.get(side, {}),
                self.team_lob.get(side, 0),
                self.pitching.get(side, []),
            )
            for side in SIDES
        ]


def _runner(event):
    """(kind, runner id) of an engine baserunning event such as {"Scored": {"runner": "12"}}."""
    (kind, body), = event.items()
    return kind, int(body["runner"])


def _bases(bases):
    return [int(pid) for pid in bases.values() if pid is not None]


def box_score(log):
    """The box score of a game log, from its events."""
    events = list(log.events.order_by("sequence"))
    starts = [e for e in events if e.kind == Event.START]
    box = BoxScore(
        final=any(e.kind == Event.FINAL for e in events),
        teams={AWAY: log.game.series.road_team, HOME: log.game.series.home_team},
    )
    if not starts:
        return box

    opening = starts[-1].payload
    ids = set()
    for side in SIDES:
        ids |= {e["player"] for e in opening["lineups"][side]} | {opening["starters"][side]}
    for e in events:
        if e.kind in (Event.SUBSTITUTION, Event.PITCHING_CHANGE):
            ids.add(e.payload["player"] if e.kind == Event.SUBSTITUTION else e.payload["pitcher"])
    players = models.Player.objects.in_bulk(ids)

    # Batting order with substitutes after the player each replaced; pitchers in order of appearance.
    slots = {side: [[BattingLine(players[e["player"]], e["position"])] for e in opening["lineups"][side]] for side in SIDES}
    batting = {side: {line.player.id: line for slot in slots[side] for line in slot} for side in SIDES}
    starters = {side: opening["starters"][side] for side in SIDES}
    pitching = {side: {starters[side]: PitchingLine(players[starters[side]])} for side in SIDES}
    side_of_pitcher = {starters[side]: side for side in SIDES}
    for e in events:
        if e.kind == Event.SUBSTITUTION:
            line = BattingLine(players[e.payload["player"]], e.payload["position"], substitute=True)
            slots[e.side][e.payload["index"]].append(line)
            batting[e.side][line.player.id] = line
        elif e.kind == Event.PITCHING_CHANGE:
            pid = e.payload["pitcher"]
            pitching[e.side][pid] = PitchingLine(players[pid])
            side_of_pitcher[pid] = e.side

    score = {AWAY: 0, HOME: 0}
    hits = {AWAY: 0, HOME: 0}
    by_inning = {AWAY: {}, HOME: {}}
    team_lob = {AWAY: 0, HOME: 0}
    runs = []
    appearances = []
    half = None
    responsible = {}
    unearned = set()

    for event in (e for e in events if e.kind == Event.PLATE_APPEARANCE):
        payload = event.payload
        before, result = payload["before"], payload["result"]
        bats = payload["batting"]
        fields = other(bats)
        pitcher_id, batter_id = payload["pitcher"], payload["batter"]
        pitcher = pitching[fields][pitcher_id]
        outcome = result["outcome"]
        change = result["change"]
        completed = result["batter_completed"]
        index = len(appearances)

        key = (before["inning"], before["half"])
        if key != half:
            half = key
            responsible = {}
            unearned = set()
            ghost = before["bases"].get("second")
            if before["inning"] >= 10 and ghost is not None and before["outs"] == 0:
                # The placed extra-inning runner: he scores unearned, charged to the pitcher who starts the half.
                responsible[int(ghost)] = pitcher_id
                unearned.add(int(ghost))
        by_inning[bats].setdefault(before["inning"], 0)

        score_before = dict(score)
        if score[fields] > score[bats]:
            pitcher.lead_outs += change["outs_added"]
        pitcher.outs += change["outs_added"]
        pitcher.pitches += len(result["pitches"])

        if completed:
            line = batting[bats][batter_id]
            pitcher.bf += 1
            line.pa += 1
            if outcome not in NOT_AT_BATS:
                line.ab += 1
            if outcome in HITS:
                line.h += 1
                pitcher.h += 1
                hits[bats] += 1
            if outcome == "double":
                line.doubles += 1
            if outcome == "triple":
                line.triples += 1
            if outcome == "home_run":
                line.hr += 1
                pitcher.hr += 1
            if outcome in WALKS:
                line.bb += 1
                pitcher.bb += 1
            if outcome == "strikeout":
                line.so += 1
                pitcher.so += 1
            if outcome == GIDP:
                line.gidp += 1
            if outcome == SACRIFICE_FLY:
                line.sf += 1
            if outcome != GIDP:
                line.rbi += change["runs_scored"]
            if outcome in BATTER_OUTS:
                line.lob += len(_bases(change["bases"]))

        for running in result["baserunning"]:
            kind, runner = _runner(running)
            if kind == "Scored":
                charged = responsible.get(runner, pitcher_id)
                earned = runner not in unearned
                score[bats] += 1
                by_inning[bats][before["inning"]] += 1
                batting[bats][runner].r += 1
                pitching[fields][charged].r += 1
                if earned:
                    pitching[fields][charged].er += 1
                runs.append(Run(bats, runner, charged, earned, index, pitcher_id, dict(score)))
            elif kind == "StolenBase":
                batting[bats][runner].sb += 1
            elif kind == "CaughtStealing":
                batting[bats][runner].cs += 1

        responsible = {rid: responsible.get(rid, pitcher_id) for rid in _bases(change["bases"])}
        if before["outs"] + change["outs_added"] >= 3:
            team_lob[bats] += len(_bases(change["bases"]))
        appearances.append(
            PlateAppearance(index, fields, pitcher_id, score_before, dict(score), len(_bases(before["bases"])))
        )

    innings = max([1] + [inning for side in SIDES for inning in by_inning[side]])
    box.innings = list(range(1, innings + 1))
    box.line = {
        side: [by_inning[side].get(i, "X" if side == HOME and i == innings else 0) for i in box.innings]
        for side in SIDES
    }
    box.totals = {side: {"r": score[side], "h": hits[side], "e": 0} for side in SIDES}
    box.batting = {side: [line for slot in slots[side] for line in slot] for side in SIDES}
    box.batting_totals = {
        side: {name: sum(getattr(line, name) for line in box.batting[side]) for name in BattingLine.COUNTS}
        for side in SIDES
    }
    box.team_lob = team_lob
    box.pitching = {side: list(pitching[side].values()) for side in SIDES}

    if box.final and score[AWAY] != score[HOME]:
        box.win, box.loss, box.save = decisions(score, runs, appearances, pitching, starters)
    return box


def _go_ahead(runs, winner):
    """The run that gave the winner the lead it never gave up."""
    go_ahead = None
    led = False
    for run in runs:
        leads = run.score[winner] > run.score[other(winner)]
        if leads and not led:
            go_ahead = run
        led = leads
    return go_ahead


def _pitcher_of_record(appearances, side, before_index, starter):
    """The side's pitcher who last faced a batter before a plate appearance; its starter before anyone has."""
    record = starter
    for pa in appearances[:before_index]:
        if pa.fielding == side:
            record = pa.pitcher
    return record


def _most_effective(candidates, lines):
    """The scorer's-judgment win: the reliever who recorded the most outs while his team held the lead."""
    best = None
    for pid in candidates:
        if best is None or lines[pid].lead_outs > lines[best].lead_outs:
            best = pid
    return best


def decisions(score, runs, appearances, pitching, starters):
    """(win, loss, save) Players under rules 9.17 and 9.19. The save is None when no one earned one."""
    winner = AWAY if score[AWAY] > score[HOME] else HOME
    loser = other(winner)
    lines = pitching[winner]
    order = list(lines)
    starter = starters[winner]

    go_ahead = _go_ahead(runs, winner)
    loss = pitching[loser][go_ahead.charged]
    record = _pitcher_of_record(appearances, winner, go_ahead.pa, starter)
    relievers = [pid for pid in order if pid != starter]

    if record == starter:
        if lines[starter].outs >= STARTER_WIN_OUTS or not relievers:
            win = starter
        else:
            win = _most_effective(relievers, lines)
    else:
        earned_while_pitching = sum(1 for run in runs if run.pitcher == record and run.side == loser and run.earned)
        succeeding = order[order.index(record) + 1:]
        if lines[record].outs < BRIEF_OUTS and earned_while_pitching >= INEFFECTIVE_EARNED_RUNS and succeeding:
            win = _most_effective(succeeding, lines)
        else:
            win = record

    save = None
    finisher = order[-1]
    if finisher not in (win, starter):
        outing = [pa for pa in appearances if pa.fielding == winner and pa.pitcher == finisher]
        if outing:
            entry = outing[0]
            lead = entry.before[winner] - entry.before[loser]
            held = all(pa.after[winner] > pa.after[loser] for pa in outing)
            outs = lines[finisher].outs
            situation = (
                (lead <= SAVE_LEAD and outs >= SAVE_INNING_OUTS)
                or lead <= entry.runners + 2
                or outs >= SAVE_LONG_OUTS
            )
            if lead > 0 and held and outs >= SAVE_MIN_OUTS and situation:
                save = lines[finisher].player
    return lines[win].player, loss.player, save
