# ABOUTME: The ULMG usage ledger: season caps, per-game limits and series rest built from the card season.
# ABOUTME: Games call record_plate_appearance inside their log transaction; it locks, checks and counts.

import logging
import math
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from ulmg import models

logger = logging.getLogger(__name__)

CARD_CLASSIFICATION = "1-mlb"

# Starters: (minimum card-season innings, ULMG starts), highest row first.
# Under the last row a starter gets his real starts only.
STARTER_STARTS_TABLE = [(175, 34), (155, 30), (130, 26), (110, 23), (75, 19), (50, 14)]

# Relievers: (minimum card-season innings, share of those innings), highest row first.
RELIEVER_INNINGS_TABLE = [(70, Fraction(3, 2)), (60, Fraction(5, 4)), (0, Fraction(1))]

UNLIMITED_AT_BATS = 500
UNLIMITED_PLATE_APPEARANCES = 550

GAME_LIMIT_MULTIPLIER = Fraction(5, 4)
START_LIMIT_MIN_INNINGS = 4
START_LIMIT_MAX_INNINGS = 9
RELIEF_LIMIT_MIN_INNINGS = 1
RELIEF_LIMIT_MAX_INNINGS = 3
CONVERTED_STARTER_MIN_GS = 5

# A pitcher who starts game n cannot start games n - 3 through n + 3 of that series.
STARTER_REST_GAMES = 3
# A reliever cannot pitch three consecutive games of a series.
RELIEVER_CONSECUTIVE_GAMES = 3
# Nor the day before or after an outing of this many pitches in the same series.
RELIEVER_HEAVY_PITCHES = 30

# Penalty lines: share over a cap.
PLAYOFF_PENALTY_SHARE = Fraction(1, 10)
FREE_AGENT_PENALTY_SHARE = Fraction(1, 5)

# Swingman designations the half plan (#162) passes to set_swingman_designation.
ROTATION = "rotation"
BULLPEN = "bullpen"
DESIGNATIONS = (ROTATION, BULLPEN)


class UsageViolation(Exception):
    """Raised by record_plate_appearance when the action would cross a cap."""

    def __init__(self, check):
        super().__init__(check.reason)
        self.check = check


@dataclass
class UsageCheck:
    """
    Whether an action is legal, why not if it isn't, and what is left.
    remaining holds plate_appearances, starts, season_outs and game_outs as
    they apply; None means unlimited. overrides are the commissioner
    overrides this action needs.
    """

    legal: bool
    reason: str = None
    remaining: dict = field(default_factory=dict)
    overrides: list = field(default_factory=list)

    @property
    def override(self):
        return self.overrides[0] if self.overrides else None


@dataclass
class PlayRecord:
    batter_appearance: object
    pitcher_appearance: object
    allowance_outs: int = 0


# Card-season numbers


def innings_to_outs(value):
    """FanGraphs innings, written 174.2 for 174 and two thirds, as outs."""
    if value in (None, ""):
        return 0
    try:
        innings = Decimal(str(value))
    except InvalidOperation:
        return 0
    whole = int(innings)
    thirds = int(((innings - whole) * 10).to_integral_value())
    return whole * 3 + thirds


def outs_to_innings(outs):
    """Outs written as innings, 524 as 174.2."""
    if outs is None:
        return None
    return f"{outs // 3}.{outs % 3}"


def _count(stats, key):
    try:
        return int(stats.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def card_stats(player, season):
    """The (hit_stats, pitch_stats) of a ULMG season's card: the previous MLB season's 1-mlb row."""
    row = models.PlayerStatSeason.objects.filter(
        player=player,
        season=season - 1,
        classification=CARD_CLASSIFICATION,
        is_career=False,
    ).first()
    if not row:
        return {}, {}
    return row.hit_stats or {}, row.pitch_stats or {}


def starter_starts_cap(outs, real_starts):
    for min_innings, starts in STARTER_STARTS_TABLE:
        if outs >= min_innings * 3:
            return max(real_starts, starts)
    return real_starts


def reliever_innings_cap(outs):
    """A reliever's season cap in outs, rounded down to a whole out."""
    for min_innings, share in RELIEVER_INNINGS_TABLE:
        if outs >= min_innings * 3:
            return math.floor(share * outs)
    return outs


def game_limit_outs(innings_outs, appearances, min_innings, max_innings):
    """ceil(1.25 x innings per appearance), clamped, in outs. No appearances gets the floor."""
    if appearances <= 0:
        return min_innings * 3
    innings = math.ceil(GAME_LIMIT_MULTIPLIER * Fraction(innings_outs, 3) / appearances)
    return max(min_innings, min(max_innings, innings)) * 3


def card_caps(player, season):
    """The UsageCounter cap fields for a player's ULMG season, from his card season."""
    hit, pitch = card_stats(player, season)

    outs = innings_to_outs(pitch.get("ip"))
    starts = _count(pitch, "gs")
    relief_appearances = max(_count(pitch, "g") - starts, 0)

    start_limit = game_limit_outs(
        innings_to_outs(pitch.get("start_minusip")),
        starts,
        START_LIMIT_MIN_INNINGS,
        START_LIMIT_MAX_INNINGS,
    )
    if starts >= CONVERTED_STARTER_MIN_GS:
        relief_limit = start_limit
    else:
        relief_limit = game_limit_outs(
            innings_to_outs(pitch.get("relief_minusip")),
            relief_appearances,
            RELIEF_LIMIT_MIN_INNINGS,
            RELIEF_LIMIT_MAX_INNINGS,
        )

    confined_cap = None
    if starts and not relief_appearances:
        innings_cap = None
    elif starts:
        innings_cap = outs
        confined_cap = reliever_innings_cap(outs)
    else:
        innings_cap = reliever_innings_cap(outs)

    at_bats = _count(hit, "ab")
    if hit.get("pa") is not None:
        plate_appearances = _count(hit, "pa")
    else:
        plate_appearances = at_bats + sum(_count(hit, k) for k in ("bb", "hbp", "sf", "sh"))
    if at_bats >= UNLIMITED_AT_BATS or plate_appearances >= UNLIMITED_PLATE_APPEARANCES:
        plate_appearances_cap = None
    else:
        plate_appearances_cap = plate_appearances

    return {
        "starts_cap": starter_starts_cap(outs, starts) if starts else 0,
        "innings_cap_outs": innings_cap,
        "confined_innings_cap_outs": confined_cap,
        "plate_appearances_cap": plate_appearances_cap,
        "start_limit_outs": start_limit,
        "relief_limit_outs": relief_limit,
    }


# Counters


def counter_for(player, season):
    """The player's counter for a ULMG season, created with his caps if it doesn't exist."""
    counter, _ = models.UsageCounter.objects.get_or_create(
        player=player, season=season, defaults=card_caps(player, season)
    )
    return counter


def _locked_counter(player, season):
    counter_for(player, season)
    return models.UsageCounter.objects.select_for_update().get(player=player, season=season)


def _current_counter(player, season):
    """The live counter, or an unsaved one at zero usage, so reads never write."""
    counter = models.UsageCounter.objects.filter(player=player, season=season).first()
    if counter:
        return counter
    return models.UsageCounter(player=player, season=season, **card_caps(player, season))


def refresh_caps(player, season):
    """Recompute a counter's caps from the card season after a data fix. Usage is kept."""
    with transaction.atomic():
        counter = _locked_counter(player, season)
        for name, value in card_caps(player, season).items():
            setattr(counter, name, value)
        counter.save()
    return counter


def season_innings_cap(counter):
    """
    The season innings cap in outs, None for a pure starter. A swingman gets
    the reliever bonus only while confined to relief and before any start.
    """
    if (
        counter.confined_innings_cap_outs is not None
        and counter.confined_to_relief
        and counter.starts == 0
    ):
        return counter.confined_innings_cap_outs
    return counter.innings_cap_outs


def set_swingman_designation(player, season, designation):
    """
    The half plan (#162) calls this for a swingman: ROTATION when he is
    listed in the half's rotation, BULLPEN when he is listed only in the
    bullpen. A counter starts in the rotation until told otherwise.
    """
    if designation not in DESIGNATIONS:
        raise ValueError(f"Designation must be one of {DESIGNATIONS}, not {designation!r}.")
    with transaction.atomic():
        counter = _locked_counter(player, season)
        counter.confined_to_relief = designation == BULLPEN
        counter.save(update_fields=["confined_to_relief", "last_modified"])
    return counter


def _remaining(cap, used):
    if cap is None:
        return None
    return max(cap - used, 0)


def _season(game):
    return game.series.slot.season


def _approved_overrides(player, game):
    return {
        o.cap: o
        for o in models.UsageOverride.objects.filter(
            player=player, game=game, approved_by__isnull=False
        )
    }


def _series_appearances(player, game):
    """The player's appearances in the other games of this game's series, played in any order."""
    return list(
        models.UsageAppearance.objects.filter(player=player, game__series_id=game.series_id)
        .exclude(game_id=game.id)
        .select_related("game__series__slot")
    )


def _pitched(appearance):
    return appearance.started or appearance.batters_faced > 0


# Rest


def starter_rest_problem(player, game, other_start_games):
    """Why he can't start this game given his starts in other games of the series, or None."""
    n = game.game_number
    for other in sorted(other_start_games, key=lambda g: g.day):
        if other.series_id == game.series_id and abs(other.game_number - n) <= STARTER_REST_GAMES:
            return (
                f"{player.name} has not had rest to start game {n}: "
                f"he starts game {other.game_number} of this series."
            )
    return None


def reliever_rest_problem(player, game, series_appearances):
    """Why he can't pitch in relief in this game given his outings in the series, or None."""
    n = game.game_number
    outings = {a.game.game_number: a for a in series_appearances if _pitched(a)}
    games_pitched = set(outings) | {n}
    for first in range(n - RELIEVER_CONSECUTIVE_GAMES + 1, n + 1):
        run = range(first, first + RELIEVER_CONSECUTIVE_GAMES)
        if all(g in games_pitched for g in run):
            return (
                f"{player.name} cannot pitch game {n}: games {run[0]}-{run[-1]} of this series "
                f"would be {RELIEVER_CONSECUTIVE_GAMES} consecutive games for him."
            )
    for adjacent in (n - 1, n + 1):
        outing = outings.get(adjacent)
        if outing and outing.pitches >= RELIEVER_HEAVY_PITCHES:
            return (
                f"{player.name} cannot pitch game {n}: he threw {outing.pitches} pitches "
                f"in game {adjacent} of this series."
            )
    return None


# Checks


def _batter_check(counter, overrides):
    cap = counter.plate_appearances_cap
    remaining = {"plate_appearances": _remaining(cap, counter.plate_appearances)}
    if cap is not None and counter.plate_appearances >= cap:
        override = overrides.get(models.UsageOverride.PLATE_APPEARANCES)
        if not override:
            return UsageCheck(
                False,
                f"{counter.player.name} has used all {cap} of his plate appearances for {counter.season}.",
                remaining,
            )
        return UsageCheck(True, None, remaining, [override])
    return UsageCheck(True, None, remaining)


def _pitcher_check(counter, game, starting, overrides, appearance, series_appearances):
    name = counter.player.name
    if appearance is not None and _pitched(appearance):
        starting = appearance.started
    new_start = starting and not (appearance is not None and appearance.started)
    confined = season_innings_cap(counter) != counter.innings_cap_outs

    season_cap = season_innings_cap(counter)
    game_limit = counter.start_limit_outs if starting else counter.relief_limit_outs
    game_outs = appearance.outs if appearance else 0
    remaining = {
        "starts": _remaining(counter.starts_cap, counter.starts),
        "season_outs": _remaining(season_cap, counter.outs),
        "game_outs": max(game_limit - game_outs, 0),
    }

    problems = []
    if new_start:
        if counter.starts >= counter.starts_cap:
            problems.append(
                (
                    models.UsageOverride.STARTS,
                    f"{name} has made {counter.starts} of his {counter.starts_cap} starts for {counter.season}.",
                )
            )
        other_starts = [a.game for a in series_appearances if a.started]
        rest = starter_rest_problem(counter.player, game, other_starts)
        if rest:
            problems.append((models.UsageOverride.REST, rest))
        if confined and counter.outs >= counter.innings_cap_outs:
            problems.append(
                (
                    models.UsageOverride.SEASON_INNINGS,
                    f"A start would end {name}'s relief confinement, and he has already pitched "
                    f"{outs_to_innings(counter.outs)} of his {outs_to_innings(counter.innings_cap_outs)} actual innings.",
                )
            )
    elif not starting:
        rest = reliever_rest_problem(counter.player, game, series_appearances)
        if rest:
            problems.append((models.UsageOverride.REST, rest))

    if season_cap is not None and counter.outs >= season_cap:
        problems.append(
            (
                models.UsageOverride.SEASON_INNINGS,
                f"{name} has no innings left this season: he has pitched "
                f"{outs_to_innings(counter.outs)} of {outs_to_innings(season_cap)}.",
            )
        )
    if game_outs >= game_limit:
        problems.append(
            (
                models.UsageOverride.GAME_INNINGS,
                f"{name} has reached his limit of {outs_to_innings(game_limit)} innings for this outing.",
            )
        )

    unresolved = [reason for cap, reason in problems if cap not in overrides]
    if unresolved:
        return UsageCheck(False, " ".join(unresolved), remaining)
    needed = []
    for cap, _ in problems:
        if overrides[cap] not in needed:
            needed.append(overrides[cap])
    return UsageCheck(True, None, remaining, needed)


def _appearance(player, game):
    return models.UsageAppearance.objects.filter(player=player, game=game).first()


def check_batter(player, game):
    """Before seating a batter and before each of his plate appearances: remaining, legal, and why not."""
    counter = _current_counter(player, _season(game))
    return _batter_check(counter, _approved_overrides(player, game))


def check_pitcher(player, game, starting=False):
    """
    Before seating a pitcher and before each batter he faces. starting says
    he would be this game's starting pitcher; once he has pitched in the
    game his appearance decides. Covers starts, season innings, this
    outing's limit and series rest.
    """
    counter = _current_counter(player, _season(game))
    return _pitcher_check(
        counter,
        game,
        starting,
        _approved_overrides(player, game),
        _appearance(player, game),
        _series_appearances(player, game),
    )


def check_planned_start(player, game, planned_starts):
    """
    Check a start the half plan (#162) wants without using it up.
    planned_starts are the plan's unplayed starts for him this season; this
    game is counted once whether or not it is among them. Legal when he is
    rested against his starts made and planned in this game's series, and
    starts made plus starts planned fit his cap.
    """
    counter = _current_counter(player, _season(game))
    made = [a.game for a in models.UsageAppearance.objects.filter(
        player=player, game__series__slot__season=counter.season, started=True
    ).select_related("game__series__slot")]
    made_ids = {g.id for g in made}
    planned = {g.id: g for g in planned_starts if g.id not in made_ids}
    planned[game.id] = game

    remaining = {"starts": _remaining(counter.starts_cap, counter.starts)}
    problems = []
    if counter.starts + len(planned) > counter.starts_cap:
        problems.append(
            f"{player.name} has made {counter.starts} starts and has {len(planned)} planned; "
            f"his cap is {counter.starts_cap} starts."
        )
    others = [g for g in made + list(planned.values()) if g.id != game.id]
    rest = starter_rest_problem(player, game, others)
    if rest:
        problems.append(rest)
    if problems:
        return UsageCheck(False, " ".join(problems), remaining)
    return UsageCheck(True, None, remaining)


# Recording


def record_plate_appearance(game, batter, pitcher, *, at_bat, outs, pitches=0, pitcher_starting=False):
    """
    The one entry point a game calls as it appends to its log, inside the
    log's transaction. Locks both players' counters, checks the batter and
    the pitcher, and counts one plate appearance and the outs it recorded.
    Raises UsageViolation, with nothing counted, when either player is past
    a cap. A play that starts with an out left may record more outs than
    remain; the extra outs are kept as allowance_outs.

    Pass batter=None for outs recorded on the bases during a plate
    appearance (a caught stealing): those count for the pitcher with no
    check, since he was legal when the plate appearance began.
    """
    if outs < 0 or outs > 3:
        raise ValueError(f"A play records 0 to 3 outs, not {outs}.")
    if batter is None and at_bat:
        raise ValueError("Outs on the bases have no batter and no at-bat.")
    season = _season(game)

    with transaction.atomic():
        players = sorted([p for p in (batter, pitcher) if p is not None], key=lambda p: p.id)
        counters = {p.id: _locked_counter(p, season) for p in players}
        pitcher_counter = counters[pitcher.id]
        pitcher_overrides = _approved_overrides(pitcher, game)
        pitcher_appearance = _appearance(pitcher, game)

        batter_record = None
        if batter is not None:
            batter_counter = counters[batter.id]
            batter_check = _batter_check(batter_counter, _approved_overrides(batter, game))
            if not batter_check.legal:
                raise UsageViolation(batter_check)
            pitcher_check = _pitcher_check(
                pitcher_counter,
                game,
                pitcher_starting,
                pitcher_overrides,
                pitcher_appearance,
                _series_appearances(pitcher, game),
            )
            if not pitcher_check.legal:
                raise UsageViolation(pitcher_check)

            batter_counter.plate_appearances += 1
            batter_counter.at_bats += 1 if at_bat else 0
            batter_counter.save()
            batter_record, _ = models.UsageAppearance.objects.get_or_create(player=batter, game=game)
            batter_record.plate_appearances += 1
            batter_record.at_bats += 1 if at_bat else 0
            batter_record.save()
            for override in batter_check.overrides:
                override.plate_appearances_used += 1
                override.save()
            used_overrides = pitcher_check.overrides
        else:
            used_overrides = []

        if pitcher_appearance is None:
            pitcher_appearance = models.UsageAppearance.objects.create(player=pitcher, game=game)
        if pitcher_starting and not _pitched(pitcher_appearance):
            pitcher_appearance.started = True
            pitcher_counter.starts += 1

        rooms = []
        season_cap = season_innings_cap(pitcher_counter)
        if season_cap is not None and models.UsageOverride.SEASON_INNINGS not in pitcher_overrides:
            rooms.append(season_cap - pitcher_counter.outs)
        game_limit = (
            pitcher_counter.start_limit_outs
            if pitcher_appearance.started
            else pitcher_counter.relief_limit_outs
        )
        if models.UsageOverride.GAME_INNINGS not in pitcher_overrides:
            rooms.append(game_limit - pitcher_appearance.outs)
        allowance = max(outs - max(min(rooms), 0), 0) if rooms else 0

        pitcher_counter.outs += outs
        pitcher_counter.save()
        pitcher_appearance.outs += outs
        pitcher_appearance.pitches += pitches
        pitcher_appearance.allowance_outs += allowance
        if batter is not None:
            pitcher_appearance.batters_faced += 1
        pitcher_appearance.save()

        for override in used_overrides:
            if override.cap in (models.UsageOverride.SEASON_INNINGS, models.UsageOverride.GAME_INNINGS):
                override.outs_used += outs
            if override.cap == models.UsageOverride.STARTS and pitcher_starting:
                override.starts_used += 1
            override.save()

    return PlayRecord(batter_record, pitcher_appearance, allowance)


# Commissioner overrides and paused games


def _validate_cap(cap):
    if cap not in dict(models.UsageOverride.CAP_CHOICES):
        raise ValueError(f"Unknown usage cap {cap!r}.")


def request_override(user, player, game, cap, reason):
    """An owner asks, from a paused game, for one player past one cap in that game."""
    _validate_cap(cap)
    override, created = models.UsageOverride.objects.get_or_create(
        player=player,
        game=game,
        cap=cap,
        defaults={"requested_by": user, "request_reason": reason},
    )
    return override


def grant_override(user, player, game, cap, reason):
    """
    The commissioner (a superuser) approves one player past one cap or
    per-game limit in one game. Anyone else is refused.
    """
    if not user.is_superuser:
        raise PermissionDenied("Only the commissioner can grant a usage override.")
    _validate_cap(cap)
    with transaction.atomic():
        override, _ = models.UsageOverride.objects.select_for_update().get_or_create(
            player=player, game=game, cap=cap
        )
        override.approved_by = user
        override.approved_at = timezone.now()
        override.reason = reason
        override.save()
    logger.info(
        "Usage override approved by %s: %s past %s in %s. Reason: %s",
        user.username,
        player.name,
        override.get_cap_display(),
        game,
        reason,
    )
    return override


def legal_pitchers(game, pitchers):
    """The pitchers who could face the next batter in this game."""
    return [p for p in pitchers if check_pitcher(p, game).legal]


def pause_if_no_legal_pitcher(game, team, pitchers):
    """
    Pause the game for the commissioner when none of a side's pitchers is
    legal. Returns the open pause, or None when the side has a pitcher.
    """
    if legal_pitchers(game, pitchers):
        return None
    reason = " ".join(check_pitcher(p, game).reason for p in pitchers)
    pause, _ = models.UsagePause.objects.get_or_create(
        game=game, team=team, resolved_at=None, defaults={"reason": reason}
    )
    logger.warning(
        "%s has no legal pitcher in %s; the game is paused for the commissioner. %s",
        team.abbreviation,
        game,
        reason,
    )
    return pause


def resume_if_legal(pause, pitchers):
    """Close the pause once a roster move or an override gives the side a legal pitcher."""
    if not legal_pitchers(pause.game, pitchers):
        return False
    pause.resolved_at = timezone.now()
    pause.save(update_fields=["resolved_at", "last_modified"])
    return True


# Penalties and display


@dataclass
class Overage:
    player: object
    measure: str
    used: int
    cap: int
    share_over: object


@dataclass
class PenaltyLines:
    players_over_10: list
    players_over_20: list

    @property
    def players_playoff_ineligible(self):
        return [o.player for o in self.players_over_10]

    @property
    def free_agents_next_open_draft(self):
        return [o.player for o in self.players_over_20]

    @property
    def loses_first_round_aa_pick(self):
        return len(self.players_over_10) >= 1

    @property
    def loses_both_first_round_picks(self):
        return len(self.players_over_10) >= 2

    @property
    def team_playoff_ineligible(self):
        return bool(self.players_over_20)


def worst_overage(counter):
    """The cap this counter is furthest over, or None when he is within every cap."""
    measures = [
        ("plate appearances", counter.plate_appearances, counter.plate_appearances_cap),
        ("starts", counter.starts, counter.starts_cap),
        ("innings", counter.outs, season_innings_cap(counter)),
    ]
    worst = None
    for measure, used, cap in measures:
        if cap is None or used <= cap:
            continue
        share = Fraction(used - cap, cap) if cap else math.inf
        if worst is None or share > worst.share_over:
            worst = Overage(counter.player, measure, used, cap, share)
    return worst


def penalty_lines(team, season):
    """The constitution's penalty lines for a club's players, from live counters."""
    over_10 = []
    over_20 = []
    counters = models.UsageCounter.objects.filter(player__team=team, season=season).select_related("player")
    for counter in counters:
        overage = worst_overage(counter)
        if overage and overage.share_over > PLAYOFF_PENALTY_SHARE:
            over_10.append(overage)
            if overage.share_over > FREE_AGENT_PENALTY_SHARE:
                over_20.append(overage)
    return PenaltyLines(over_10, over_20)


def usage_summary(player, season):
    """Live remaining usage for display beside a player's card. Never writes."""
    counter = _current_counter(player, season)
    season_cap = season_innings_cap(counter)
    return {
        "season": season,
        "counter": counter,
        "plate_appearances_left": _remaining(counter.plate_appearances_cap, counter.plate_appearances),
        "starts_left": _remaining(counter.starts_cap, counter.starts),
        "innings_cap": outs_to_innings(season_cap),
        "innings_left": outs_to_innings(_remaining(season_cap, counter.outs)),
        "innings_used": outs_to_innings(counter.outs),
        "start_limit": outs_to_innings(counter.start_limit_outs),
        "relief_limit": outs_to_innings(counter.relief_limit_outs),
    }
