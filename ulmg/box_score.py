# ABOUTME: The box score of a sim game, computed from its log alone: line score, batting and pitching lines, and the notes.
# ABOUTME: The notes name the doubles, triples, homers and the rest; the win, loss and save follow rules 9.17 and 9.19.

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
DH = "DH"
UNPLAYED = "-"
SKIPPED = "X"
MIN_LINE_INNINGS = 9
# Box score notation for the substitution roles the game log records.
PINCH_RUNNER = "pinch_runner"
PINCH_NOTES = {"pinch_hitter": "ph", PINCH_RUNNER: "pr"}
SACRIFICE_FLY = "sacrifice_fly"
HIT_BY_PITCH = "hit_by_pitch"
SACRIFICE_BUNT = "bunt_sacrifice"

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
    moves: list = field(default_factory=list)
    hbp: int = 0
    sh: int = 0

    COUNTS = (
        "pa", "ab", "r", "h", "rbi", "bb", "so", "doubles", "triples", "hr", "sb", "cs", "lob", "gidp", "sf", "hbp", "sh"
    )

    @property
    def notation(self):
        """His positions in order, the standard way: "ph-1B" for a pinch hitter who stayed in at first, "SS-2B" for a move."""
        return "-".join([self.position] + self.moves)


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
class BoxNote:
    """One named line under the pitching tables: "HR" and "Juan Soto (4th inning off Sean Burke, 1 on, 2 outs)"."""

    label: str
    text: str


# Named in this order. An empty one is left out; a double play the defense turned and the two clubs' LOB follow.
PLAY_NOTES = ("2B", "3B", "HR", "SB", "CS", "SF", "SH", "GIDP", "HBP", "IBB")
INTENTIONAL_WALK = "intentional_walk"
BASE_WORDS = {
    "First": "1st", "Second": "2nd", "Third": "3rd",
    "first": "1st", "second": "2nd", "third": "3rd",
}


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
    notes: list = field(default_factory=list)

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
    """(kind, runner id, body) of an engine baserunning event such as {"Scored": {"runner": "12"}}."""
    (kind, body), = event.items()
    return kind, int(body["runner"]), body


def _ordinal(number):
    """1st, 2nd, 3rd, 4th; the teens stay "th"."""
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _on_phrase(count):
    return "1 on" if count == 1 else f"{count} on"


def _out_phrase(outs):
    if outs == 1:
        return "1 out"
    if outs == 0:
        return "0 out"
    return f"{outs} outs"


def _hit_detail(inning, pitcher, *, on=None, outs=None):
    """Where an extra-base hit came: the inning and the pitcher, and for a homer who was on and how many were out."""
    text = f"{_ordinal(inning)} inning off {pitcher.name}"
    if on is not None:
        text += f", {_on_phrase(on)}, {_out_phrase(outs)}"
    return text


def _base_word(body):
    raw = body.get("to", body.get("at", ""))
    return BASE_WORDS.get(raw, str(raw).lower())


def _format_players(occurrences):
    """"Name 2 (detail; detail); Other (detail)", grouping a player's occurrences in the order they happened."""
    groups = []
    index = {}
    for player, detail in occurrences:
        if player.id not in index:
            index[player.id] = len(groups)
            groups.append((player, []))
        groups[index[player.id]][1].append(detail)
    parts = []
    for player, details in groups:
        shown = [detail for detail in details if detail]
        count = len(details)
        if count == 1 and not shown:
            parts.append(player.name)
        elif count == 1:
            parts.append(f"{player.name} ({shown[0]})")
        elif not shown:
            parts.append(f"{player.name} {count}")
        else:
            parts.append(f"{player.name} {count} ({'; '.join(shown)})")
    return "; ".join(parts)


def _bases(bases):
    return [int(pid) for pid in bases.values() if pid is not None]


def line_score_cells(by_inning, *, inning, half, final):
    """
    One cell per inning for each side: the runs, '-' if that half has not
    been played, or 'X' if the home club did not need to bat.
    Always at least nine innings; extra innings extend the line.
    """
    last = max([inning, 1] + [i for side in SIDES for i in by_inning[side]])
    innings = list(range(1, max(MIN_LINE_INNINGS, last) + 1))
    return {
        "innings": innings,
        AWAY: [_line_cell(AWAY, i, by_inning, inning, half, final) for i in innings],
        HOME: [_line_cell(HOME, i, by_inning, inning, half, final) for i in innings],
    }


def _line_cell(side, i, by_inning, inning, half, final):
    if i in by_inning[side]:
        return by_inning[side][i]
    if i < inning:
        return 0
    if i > inning:
        return UNPLAYED
    started = side == AWAY or half == "bottom"
    if started:
        return 0
    if final and side == HOME:
        return SKIPPED
    return UNPLAYED


def substitute_line(player, payload):
    """
    The batting line of a substitute: "ph" or "pr" with no position until he
    is given one, except for the designated hitter's ("ph-DH"); otherwise
    the position he took.
    """
    note = PINCH_NOTES.get(payload.get("role"))
    if note is None:
        return BattingLine(player, payload["position"], substitute=True)
    line = BattingLine(player, note, substitute=True)
    if payload["position"] == DH:
        line.moves.append(DH)
    return line


def box_score(log, events=None):
    """The box score of a game log, from its events: given in sequence order, or read from the log."""
    events = list(log.events.order_by("sequence")) if events is None else list(events)
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
            line = substitute_line(players[e.payload["player"]], e.payload)
            slots[e.side][e.payload["index"]].append(line)
            batting[e.side][line.player.id] = line
        elif e.kind == Event.POSITION_CHANGE:
            for pid, change in zip(e.payload["players"], e.payload["changes"]):
                line = batting[e.side][pid]
                if line.notation.split("-")[-1] != change["position"]:
                    line.moves.append(change["position"])
        elif e.kind == Event.PITCHING_CHANGE:
            pid = e.payload["pitcher"]
            pitching[e.side][pid] = PitchingLine(players[pid])
            side_of_pitcher[pid] = e.side

    score = {AWAY: 0, HOME: 0}
    hits = {AWAY: 0, HOME: 0}
    by_inning = {AWAY: {}, HOME: {}}
    team_lob = {AWAY: 0, HOME: 0}
    occurrences = {label: [] for label in PLAY_NOTES}
    dp = {AWAY: 0, HOME: 0}
    runs = []
    appearances = []
    half = None
    responsible = {}
    unearned = set()

    for event in events:
        if event.kind == Event.SUBSTITUTION and event.payload.get("role") == PINCH_RUNNER:
            # A pinch runner inherits the runner's pitcher responsibility and, for the placed runner, his unearned run.
            replaced, runner = event.payload["replaced"], event.payload["player"]
            if replaced in responsible:
                responsible[runner] = responsible.pop(replaced)
            if replaced in unearned:
                unearned.add(runner)
            continue
        if event.kind != Event.PLATE_APPEARANCE:
            continue
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
                occurrences["2B"].append((line.player, _hit_detail(before["inning"], pitcher.player)))
            if outcome == "triple":
                line.triples += 1
                occurrences["3B"].append((line.player, _hit_detail(before["inning"], pitcher.player)))
            if outcome == "home_run":
                line.hr += 1
                pitcher.hr += 1
                on_base = len(_bases(before["bases"]))
                occurrences["HR"].append((
                    line.player,
                    _hit_detail(before["inning"], pitcher.player, on=on_base, outs=before["outs"]),
                ))
            if outcome in WALKS:
                line.bb += 1
                pitcher.bb += 1
            if outcome == INTENTIONAL_WALK:
                occurrences["IBB"].append((line.player, f"by {pitcher.player.name}"))
            if outcome == "strikeout":
                line.so += 1
                pitcher.so += 1
            if outcome == GIDP:
                line.gidp += 1
                occurrences["GIDP"].append((line.player, None))
                dp[fields] += 1
            if outcome == SACRIFICE_FLY:
                line.sf += 1
                occurrences["SF"].append((line.player, None))
            if outcome == HIT_BY_PITCH:
                line.hbp += 1
                occurrences["HBP"].append((line.player, f"by {pitcher.player.name}"))
            if outcome == SACRIFICE_BUNT:
                line.sh += 1
                occurrences["SH"].append((line.player, None))
            if outcome != GIDP:
                line.rbi += change["runs_scored"]
            if outcome in BATTER_OUTS:
                line.lob += len(_bases(change["bases"]))

        for running in result["baserunning"]:
            kind, runner, body = _runner(running)
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
                occurrences["SB"].append((
                    batting[bats][runner].player, f"{_base_word(body)} base off {pitcher.player.name}",
                ))
            elif kind == "CaughtStealing":
                batting[bats][runner].cs += 1
                occurrences["CS"].append((
                    batting[bats][runner].player, f"{_base_word(body)} base by {pitcher.player.name}",
                ))

        responsible = {rid: responsible.get(rid, pitcher_id) for rid in _bases(change["bases"])}
        if before["outs"] + change["outs_added"] >= 3:
            team_lob[bats] += len(_bases(change["bases"]))
        appearances.append(
            PlateAppearance(index, fields, pitcher_id, score_before, dict(score), len(_bases(before["bases"])))
        )

    played = max([1] + [inning for side in SIDES for inning in by_inning[side]])
    current = (log.state or {}).get("inning") or played
    half = (log.state or {}).get("half") or "top"
    cells = line_score_cells(by_inning, inning=current, half=half, final=box.final)
    box.innings = cells["innings"]
    box.line = {AWAY: cells[AWAY], HOME: cells[HOME]}
    box.totals = {side: {"r": score[side], "h": hits[side], "e": 0} for side in SIDES}
    box.batting = {side: [line for slot in slots[side] for line in slot] for side in SIDES}
    box.batting_totals = {
        side: {name: sum(getattr(line, name) for line in box.batting[side]) for name in BattingLine.COUNTS}
        for side in SIDES
    }
    box.team_lob = team_lob
    box.pitching = {side: list(pitching[side].values()) for side in SIDES}
    box.notes = [
        BoxNote(label, _format_players(occurrences[label])) for label in PLAY_NOTES if occurrences[label]
    ]
    turned = [f"{box.teams[side].abbreviation} {dp[side]}" for side in SIDES if dp[side]]
    if turned:
        box.notes.append(BoxNote("DP", ", ".join(turned)))
    box.notes.append(BoxNote("LOB", ", ".join(f"{box.teams[side].abbreviation} {team_lob[side]}" for side in SIDES)))

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
