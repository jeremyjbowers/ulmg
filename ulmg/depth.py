# ABOUTME: Season depth charts: plate appearances by position, the 162 starts, and bullpen innings.
# ABOUTME: An unlimited player covers a spot that is still short. Only numbered players are added up.

from dataclasses import dataclass, field

from django.db import IntegrityError, transaction

from ulmg import cards, models, plans

# A ULMG season is 162 games, one start a game.
GAMES = 162

# Batters faced per team-game, in thousandths. Baseball-Reference league
# pitching, the universal-DH seasons 2022 through 2025: 37.46, 37.88, 37.56, 37.64.
BATTERS_FACED_THOUSANDTHS = (37460, 37880, 37560, 37640)
# Innings pitched per team-game, in thousandths, from the same seasons: 8.86, 8.87, 8.88, 8.86.
INNINGS_THOUSANDTHS = (8860, 8870, 8880, 8860)
# 2024 league-average starter length, Baseball-Reference, in tenths of an inning: 5.2.
STARTER_INNINGS_TENTHS = 52

# A major-league plate-appearance leader sits around here. Past it, one player
# is being asked to hit more than a season holds.
HEAVY_PLATE_APPEARANCES = 750

# Rotation starts, and bullpen innings. Lineup positions are the hitting spots.
STARTS = "SP"
BULLPEN = "RP"

PA = "pa"
STARTS_KIND = "starts"
INNINGS_KIND = "ip"


class DepthError(Exception):
    """A depth-chart edit that breaks a rule. errors are the messages."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__(" ".join(self.errors))


def _rounded_quotient(numerator, denominator):
    """Round a positive quotient to the nearest integer, half away from zero."""
    return (numerator + denominator // 2) // denominator


def _per_game_total(rates, scale):
    return _rounded_quotient(GAMES * sum(rates), len(rates) * scale)


def season_plate_appearances():
    """Plate appearances one team bats in a season."""
    return _per_game_total(BATTERS_FACED_THOUSANDTHS, 1000)


def season_innings():
    """Innings one team pitches in a season."""
    return _per_game_total(INNINGS_THOUSANDTHS, 1000)


def starter_innings():
    """Innings the rotation covers, at a major-league starter's length."""
    return _rounded_quotient(GAMES * STARTER_INNINGS_TENTHS, 10)


def bullpen_innings():
    """Innings left for the bullpen after those starts."""
    return season_innings() - starter_innings()


def position_plate_appearances():
    """
    Plate appearances each lineup position has to cover. The same number at
    every spot. Dividing the season by nine leaves a few plate appearances
    over, and those are not given to a spot.
    """
    return season_plate_appearances() // len(plans.LINEUP_POSITIONS)


def bucket_kind(bucket):
    """pa, starts or ip, or None when the spot is not on a depth chart."""
    if bucket in plans.LINEUP_POSITIONS:
        return PA
    if bucket == STARTS:
        return STARTS_KIND
    if bucket == BULLPEN:
        return INNINGS_KIND
    return None


def bucket_target(bucket):
    """How much of a season that spot has to cover."""
    kind = bucket_kind(bucket)
    if kind == PA:
        return position_plate_appearances()
    if kind == STARTS_KIND:
        return GAMES
    if kind == INNINGS_KIND:
        return bullpen_innings()
    raise ValueError(f"{bucket} is not a depth-chart spot.")


def _comma(number):
    return f"{number:,}"


def estimate_note():
    """Where the season totals come from, for the depth-chart page."""
    return (
        f"A season is {GAMES} games and about {_comma(season_plate_appearances())} plate appearances, "
        "from 2022–2025 major-league batters faced. "
        f"Each of the nine positions is {position_plate_appearances()} of those. "
        "The four left over from the split are not given to a spot. "
        f"Teams throw about {_comma(season_innings())} innings. "
        f"Starters, at the 2024 rate of 5.2 innings a start, cover {_comma(starter_innings())}. "
        f"The bullpen gets the other {_comma(bullpen_innings())}."
    )


def empty_note():
    """What an empty chart still has to cover."""
    return (
        f"Nothing is filed yet. Each position needs {position_plate_appearances()} plate appearances, "
        f"the rotation needs {GAMES} starts, and the bullpen needs {bullpen_innings()} innings."
    )


def load(team, season):
    """The team's chart for a season, or None when nobody has filed one."""
    return models.DepthChart.objects.filter(team=team, season=season).first()


def ensure(team, season):
    """The team's chart for a season, created empty when it does not exist."""
    chart, _ = models.DepthChart.objects.get_or_create(team=team, season=season)
    return chart


def _label(bucket):
    if bucket == STARTS:
        return "the rotation"
    if bucket == BULLPEN:
        return "the bullpen"
    return bucket


def _amount_name(kind):
    return {PA: "Plate appearances", STARTS_KIND: "Starts", INNINGS_KIND: "Innings"}[kind]


def _unique(errors):
    return list(dict.fromkeys(errors))


def _bucket_error(bucket):
    if bucket_kind(bucket) is None:
        shown = bucket or "That"
        return f"{shown} is not a depth-chart spot."
    return None


def _amount_errors(bucket, amount, unlimited):
    if bucket_kind(bucket) is None or unlimited:
        return []
    name = _amount_name(bucket_kind(bucket))
    if amount == "bad":
        return [f"{name} have to be a whole number."]
    if amount is None or amount < 1:
        return [f"Enter {name.lower()}, or mark the player unlimited."]
    return []


def _player_errors(chart, player, bucket):
    """Why this player cannot be filed at this spot, apart from the amount."""
    problem = _bucket_error(bucket)
    if problem:
        return [problem]
    errors = []
    if player.team_id != chart.team_id:
        errors.append(f"{player.name} is not on {chart.team.abbreviation}.")
    kind = bucket_kind(bucket)
    if kind == PA and plans.is_pitcher(player):
        errors.append(f"{player.name} is a pitcher and does not hit.")
    if kind != PA and not plans.can_pitch(player):
        errors.append(f"{player.name} does not pitch.")
    if player.throws == "L" and bucket in cards.LEFTY_BLOCKED_POSITIONS:
        errors.append(f"{player.name} throws left and cannot play {bucket}.")
    if models.DepthAssignment.objects.filter(chart=chart, player=player, bucket=bucket).exists():
        errors.append(f"{player.name} is already filed at {_label(bucket)}.")
    return errors


def add_player(chart, player, bucket, amount, unlimited):
    """File a player at a spot for a number, or as unlimited. Raises DepthError."""
    bucket = bucket or ""
    unlimited = bool(unlimited)
    errors = []
    if player is None:
        errors.append("Pick a player.")
        problem = _bucket_error(bucket)
        if problem:
            errors.append(problem)
    else:
        errors.extend(_player_errors(chart, player, bucket))
    errors.extend(_amount_errors(bucket, amount, unlimited))
    if errors:
        raise DepthError(_unique(errors))
    try:
        with transaction.atomic():
            return models.DepthAssignment.objects.create(
                chart=chart,
                player=player,
                bucket=bucket,
                amount=0 if unlimited else amount,
                unlimited=unlimited,
            )
    except IntegrityError:
        raise DepthError([f"{player.name} is already filed at {_label(bucket)}."])


def change_player(assignment, amount, unlimited):
    """Change the number, or mark the same player unlimited. Raises DepthError."""
    unlimited = bool(unlimited)
    errors = _amount_errors(assignment.bucket, amount, unlimited)
    if errors:
        raise DepthError(errors)
    assignment.amount = 0 if unlimited else amount
    assignment.unlimited = unlimited
    assignment.save()
    return assignment


def remove_player(assignment):
    """Take one row off the chart."""
    assignment.delete()


def _name_key(player):
    last = (player.last_name or "").strip()
    first = (player.first_name or "").strip()
    if not last and player.name:
        parts = player.name.split()
        last = parts[-1]
        first = " ".join(parts[:-1])
    return (last.casefold(), first.casefold(), (player.name or "").casefold(), player.pk or 0)


def _count_phrase(number, singular, plural):
    return f"{number} {singular if number == 1 else plural}"


def _join_names(names):
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _things(number, kind):
    if kind == PA:
        return "plate appearance" if number == 1 else "plate appearances"
    if kind == STARTS_KIND:
        return "start" if number == 1 else "starts"
    return "inning" if number == 1 else "innings"


def _unit(kind):
    return {PA: "PA", STARTS_KIND: "starts", INNINGS_KIND: "IP"}[kind]


def _singular_unit(unit):
    return {"PA": "PA", "starts": "start", "IP": "IP"}[unit]


def _shares(remainder, players):
    """Split a remainder across players in name order. Earlier names get the extra one."""
    ordered = sorted(players, key=_name_key)
    if not ordered or remainder <= 0:
        return {player.id: 0 for player in ordered}
    base, extra = divmod(remainder, len(ordered))
    return {player.id: base + (1 if index < extra else 0) for index, player in enumerate(ordered)}


def _headline(state, gap, unit):
    if state == "covered":
        return "Covered"
    if state == "exact":
        return "Filled"
    number = abs(gap)
    word = _singular_unit(unit) if number == 1 else unit
    direction = "short" if gap > 0 else "over"
    return f"{number} {word} {direction}"


def _gap_sentence(spot):
    number = abs(spot.gap)
    direction = "short" if spot.state == "short" else "over"
    if spot.code == STARTS:
        return f"The rotation is {_count_phrase(number, 'start', 'starts')} {direction}."
    if spot.code == BULLPEN:
        return f"The bullpen is {_count_phrase(number, 'inning', 'innings')} {direction}."
    return f"{spot.label} is {number} {_things(number, PA)} {direction}."


def _untouched_line(spots, kind):
    """One line for spots where nobody is filed, instead of a sentence per spot."""
    if not spots:
        return None
    target = spots[0].target
    if kind == PA:
        if len(spots) == len(plans.LINEUP_POSITIONS):
            return f"No one is filed at any position ({target} plate appearances each)."
        if len(spots) == 1:
            return f"{spots[0].label} has no one filed ({_count_phrase(target, 'plate appearance', 'plate appearances')})."
        names = _join_names([spot.label for spot in spots])
        return f"{names} have no one filed ({target} plate appearances each)."
    if kind == STARTS_KIND:
        return f"The rotation has no one filed ({_count_phrase(target, 'start', 'starts')})."
    return f"The bullpen has no one filed ({_count_phrase(target, 'inning', 'innings')})."


def _display_gaps(spots):
    """
    Shortfalls and overages a manager should read. A spot with no one filed
    is grouped with the others like it. A partial filing and an overage each
    get their own sentence.
    """
    lines = []
    untouched = {PA: [], STARTS_KIND: [], INNINGS_KIND: []}
    for spot in spots:
        kind = bucket_kind(spot.code)
        if spot.state == "short" and spot.counted == 0:
            untouched[kind].append(spot)
        elif spot.state in ("short", "over"):
            lines.append(_gap_sentence(spot))
    for kind in (PA, STARTS_KIND, INNINGS_KIND):
        line = _untouched_line(untouched[kind], kind)
        if line:
            lines.append(line)
    return lines


def _cover_note(names, remainder, kind, nothing_left):
    if not names:
        return ""
    who = _join_names(names)
    if nothing_left:
        verb = "is" if len(names) == 1 else "are"
        return f"{who} {verb} unlimited and {('has' if len(names) == 1 else 'have')} nothing left here."
    verb = "takes" if len(names) == 1 else "split"
    return f"{who} {verb} the other {remainder} {_things(remainder, kind)}."


def _detail_bit(spot, row):
    if spot.code in plans.LINEUP_POSITIONS:
        if row.unlimited:
            return f"unlimited at {spot.label} ({row.projected} PA)"
        return f"{row.amount} PA at {spot.label}"
    if spot.code == STARTS:
        if row.unlimited:
            return f"unlimited ({row.projected} starts)"
        return f"{row.amount} starts"
    if row.unlimited:
        return f"unlimited ({row.projected} bullpen innings)"
    return f"{row.amount} bullpen innings"


def _warning(plate_appearances, starts, innings):
    notes = []
    if plate_appearances > HEAVY_PLATE_APPEARANCES:
        notes.append(f"{plate_appearances} plate appearances is more than one player gets in a season.")
    if starts > GAMES:
        notes.append(f"{starts} starts is more than the {GAMES} in a season.")
    bullpen = bullpen_innings()
    if innings > bullpen:
        notes.append(f"{innings} bullpen innings is more than the pen throws.")
    return " ".join(notes)


def _eligible(player, bucket, taken):
    if player.id in taken:
        return False
    kind = bucket_kind(bucket)
    if kind == PA:
        if plans.is_pitcher(player):
            return False
        if player.throws == "L" and bucket in cards.LEFTY_BLOCKED_POSITIONS:
            return False
        return True
    return plans.can_pitch(player)


@dataclass
class Row:
    id: int
    player: object
    unlimited: bool
    amount: int
    projected: int


@dataclass
class Spot:
    code: str
    label: str
    unit: str
    target: int
    counted: int
    gap: int
    state: str
    headline: str
    note: str
    rows: list = field(default_factory=list)
    options: list = field(default_factory=list)


@dataclass
class PlayerLine:
    player: object
    plate_appearances: int
    starts: int
    innings: int
    detail: str
    warning: str


@dataclass
class ChartView:
    hitting: list
    rotation: object
    bullpen: object
    players: list
    gaps: list
    empty: bool
    empty_note: str
    estimate_note: str


def _spot(code, label, assignments, roster):
    kind = bucket_kind(code)
    target = bucket_target(code)
    filed = [row for row in assignments if row.bucket == code]
    counted = sum(row.amount for row in filed if not row.unlimited)
    shortfall = target - counted
    unlimited_players = [row.player for row in filed if row.unlimited]
    if shortfall < 0:
        state, gap = "over", shortfall
    elif shortfall == 0:
        state, gap = "exact", 0
    elif unlimited_players:
        state, gap = "covered", 0
    else:
        state, gap = "short", shortfall
    remainder = max(shortfall, 0)
    shares = _shares(remainder, unlimited_players)
    rows = []
    for assignment in sorted(filed, key=lambda row: _name_key(row.player)):
        projected = shares.get(assignment.player_id, 0) if assignment.unlimited else assignment.amount
        rows.append(
            Row(
                id=assignment.id,
                player=assignment.player,
                unlimited=assignment.unlimited,
                amount=assignment.amount,
                projected=projected,
            )
        )
    taken = {row.player_id for row in filed}
    options = sorted(
        (player for player in roster if _eligible(player, code, taken)),
        key=_name_key,
    )
    unit = _unit(kind)
    names = [row.player.name for row in rows if row.unlimited]
    note = _cover_note(names, remainder, kind, nothing_left=remainder == 0)
    return Spot(
        code=code,
        label=label,
        unit=unit,
        target=target,
        counted=counted,
        gap=gap,
        state=state,
        headline=_headline(state, gap, unit),
        note=note,
        rows=rows,
        options=options,
    )


def _player_lines(spots):
    totals = {}
    details = {}
    for spot in spots:
        for row in spot.rows:
            slot = totals.setdefault(row.player.id, {"player": row.player, "pa": 0, "starts": 0, "innings": 0})
            if spot.code in plans.LINEUP_POSITIONS:
                slot["pa"] += row.projected
            elif spot.code == STARTS:
                slot["starts"] += row.projected
            else:
                slot["innings"] += row.projected
            details.setdefault(row.player.id, []).append(_detail_bit(spot, row))
    lines = []
    for slot in totals.values():
        lines.append(
            PlayerLine(
                player=slot["player"],
                plate_appearances=slot["pa"],
                starts=slot["starts"],
                innings=slot["innings"],
                detail=", ".join(details[slot["player"].id]),
                warning=_warning(slot["pa"], slot["starts"], slot["innings"]),
            )
        )
    lines.sort(key=lambda line: _name_key(line.player))
    return lines


def describe(team, season):
    """The chart a page renders: each spot, its gap, and what each player absorbs."""
    chart = load(team, season)
    assignments = []
    if chart is not None:
        assignments = list(chart.assignments.select_related("player"))
    roster = list(models.Player.objects.filter(team=team))
    hitting = [_spot(code, code, assignments, roster) for code in plans.LINEUP_POSITIONS]
    rotation = _spot(STARTS, "Rotation", assignments, roster)
    bullpen = _spot(BULLPEN, "Bullpen", assignments, roster)
    spots = [*hitting, rotation, bullpen]
    return ChartView(
        hitting=hitting,
        rotation=rotation,
        bullpen=bullpen,
        players=_player_lines(spots),
        gaps=_display_gaps(spots),
        empty=not assignments,
        empty_note=empty_note(),
        estimate_note=estimate_note(),
    )
