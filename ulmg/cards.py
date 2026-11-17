# ABOUTME: Builds engine card numbers (hitter/pitcher rates, platoon splits, running, fatigue, slotted defense) from FanGraphs stats.
# ABOUTME: Keys match the engine's HitterRates, PitcherRates and FatigueProfile; the engine reads these and computes nothing.
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

# Steal success is regressed toward a league-average base stealer with this many attempts at this rate.
STEAL_PRIOR_ATTEMPTS = 10
STEAL_PRIOR_SUCCESS_RATE = 0.72

# Statcast sprint speed, feet per second. 27 is an average runner.
# One foot per second is one point, so 5 matches an average FanGraphs Spd.
SPRINT_AVERAGE = 27.0

# FanGraphs BsR is a season total. This many plate appearances of league-average (0) baserunning
# are mixed in, and the result is read per the same number of plate appearances.
# Four of those runs are one point of speed. The nudge stops at a point and a half:
# BsR counts stolen bases, which the card already rates on their own.
BSR_PA = 600
BSR_RUNS_PER_POINT = 4.0
BSR_ADJUSTMENT_CAP = 1.5

FULL_SEASON_INNINGS = 1300
DEFENSE_REGRESSION_INNINGS = 600

# Plate appearances (hitters) or batters faced (pitchers) of overall card mixed into each platoon split.
PLATOON_REGRESSION_PA = 400

# Player.bats for a switch hitter, as utils.normalize_hand stores it from the FanGraphs roster.
SWITCH_HITTER = "S"

# Runs added to a shortstop's rating when he is slotted at each position.
SPECTRUM_GAINS = {
    "SS": 0,
    "2B": 12,
    "CF": 13,
    "3B": 15,
    "RF": 16,
    "LF": 17,
    "1B": 18,
}

CATCHER = "C"
FIRST_BASE = "1B"
INFIELD_POSITIONS = ("1B", "2B", "3B", "SS")
OUTFIELD_POSITIONS = ("LF", "CF", "RF")

# An outfielder is listed at 2B, 3B, or SS when his rating there is better than this.
# First base stays listed either way. A rating of -1.0 is not better than -1.
OUTFIELDER_INFIELD_CUTOFF = -1

# Range at these positions can anchor the spectrum. Scooping and catching cannot:
# a 1B or C rating qualifies him only at that position unless he also played one of these.
# An outfield anchor fills the outfield and first base. It does not fill 2B, 3B, or SS.
SPECTRUM_POSITIONS = ("2B", "3B", "SS", "LF", "CF", "RF")

# The infield spots an outfielder is rated at only when he played one of them.
INFIELD_RANGE_POSITIONS = ("2B", "3B", "SS")

# A left-handed thrower can play first base and the outfield.
LEFTY_BLOCKED_POSITIONS = ("2B", "3B", "SS", "C")

# The spectrum already treats the outfield as easier than the infield.
# An infielder gives back this many runs on top of that when he is read out there.
INF_TO_OF_PENALTY = 5

# Display and tie-break order for card defense.
DEFENSE_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]


def card_season():
    """Cards are generated from the previous MLB season."""
    return settings.CURRENT_SEASON - 1


def _number(stats, key):
    try:
        return float(stats.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def hitter_rates(hit_stats):
    """Eight outcome rates per plate appearance, summing to 1. None without plate appearances."""
    if not hit_stats:
        return None
    pa = _number(hit_stats, "pa")
    if pa <= 0:
        return None

    rates = {
        "k": _number(hit_stats, "so") / pa,
        "bb": _number(hit_stats, "bb") / pa,
        "hbp": _number(hit_stats, "hbp") / pa,
        "single": _number(hit_stats, "1b") / pa,
        "double": _number(hit_stats, "2b") / pa,
        "triple": _number(hit_stats, "3b") / pa,
        "hr": _number(hit_stats, "hr") / pa,
    }
    rates["bip_out"] = 1 - sum(rates.values())
    return rates


def steal_success(hit_stats):
    """(SB + prior attempts * prior rate) / (SB + CS + prior attempts). The prior alone with zero attempts."""
    if not hit_stats:
        return None
    sb = _number(hit_stats, "sb")
    cs = _number(hit_stats, "cs")
    return (sb + STEAL_PRIOR_ATTEMPTS * STEAL_PRIOR_SUCCESS_RATE) / (sb + cs + STEAL_PRIOR_ATTEMPTS)


def steal_attempt_rate(hit_stats):
    """Steal attempts per time reaching first: (SB + CS) / (1B + BB + HBP). None if he never reached first."""
    if not hit_stats:
        return None
    times_on_first = _number(hit_stats, "1b") + _number(hit_stats, "bb") + _number(hit_stats, "hbp")
    if times_on_first <= 0:
        return None
    return (_number(hit_stats, "sb") + _number(hit_stats, "cs")) / times_on_first


def _optional_float(stats, key):
    """A stat as a float, or None when the key is missing or not a number."""
    if not stats or key not in stats or stats.get(key) in (None, ""):
        return None
    try:
        return float(stats[key])
    except (TypeError, ValueError):
        return None


def _tenths(value):
    """One decimal, halves away from zero. The card stores speed this way."""
    score = Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return float(score)


def fangraphs_bsr(hit_stats):
    """FanGraphs BsR. BaseRunning is the major-league column; wBsR is the column on the other leaderboards."""
    baserunning = _optional_float(hit_stats, "baserunning")
    if baserunning is not None:
        return baserunning
    return _optional_float(hit_stats, "wbsr")


def speed(hit_stats):
    """
    Speed on a 0-to-10 scale, 5 average, one decimal, never below 0.
    Sprint speed is the base: 27 ft/s is a 5, and each foot per second is one point.
    FanGraphs BsR, shrunk toward 0 with BSR_PA plate appearances, then moves it by
    up to BSR_ADJUSTMENT_CAP. Four baserunning runs per BSR_PA is one point.
    With no sprint speed, FanGraphs Spd is the whole number. None when neither is present.
    """
    sprint = _optional_float(hit_stats, "sprint_speed")
    if sprint is None or sprint <= 0:
        return _optional_float(hit_stats, "spd")

    score = Decimal(5) + (Decimal(str(sprint)) - Decimal(str(SPRINT_AVERAGE)))
    bsr = fangraphs_bsr(hit_stats)
    pa = _number(hit_stats, "pa")
    if bsr is not None and pa > 0:
        per_rate = Decimal(str(bsr)) * Decimal(BSR_PA) / (Decimal(str(pa)) + Decimal(BSR_PA))
        adjust = per_rate / Decimal(str(BSR_RUNS_PER_POINT))
        cap = Decimal(str(BSR_ADJUSTMENT_CAP))
        if adjust > cap:
            adjust = cap
        elif adjust < -cap:
            adjust = -cap
        score += adjust
    if score < 0:
        score = Decimal(0)
    return _tenths(score)


def pitcher_rates(pitch_stats):
    """Outcome rates per batter faced; h is hits that are not home runs. None without batters faced."""
    if not pitch_stats:
        return None
    tbf = _number(pitch_stats, "tbf")
    if tbf <= 0:
        return None

    hr = _number(pitch_stats, "hr")
    return {
        "k": _number(pitch_stats, "so") / tbf,
        "bb": _number(pitch_stats, "bb") / tbf,
        "hbp": _number(pitch_stats, "hbp") / tbf,
        "hr": hr / tbf,
        "h": (_number(pitch_stats, "h") - hr) / tbf,
    }


def regress_split(split_rates, overall_rates, n):
    """
    One platoon split regressed toward the overall card:
    regressed = (n * split + PLATOON_REGRESSION_PA * overall) / (n + PLATOON_REGRESSION_PA),
    then renormalized so the rates sum to 1. n is the split's PA or BF.
    Pitcher rates leave out the outs in play, so that remainder is regressed the same way
    and counts toward the sum. A split with no PA or BF is the overall card.
    """
    if overall_rates is None:
        return None
    if not split_rates or n <= 0:
        return dict(overall_rates)

    r = PLATOON_REGRESSION_PA
    regressed = {key: (n * split_rates[key] + r * overall) / (n + r) for key, overall in overall_rates.items()}
    remainder = (n * (1 - sum(split_rates.values())) + r * (1 - sum(overall_rates.values()))) / (n + r)
    total = sum(regressed.values()) + max(remainder, 0.0)
    return {key: rate / total for key, rate in regressed.items()}


def split_count(split_stats, key):
    """The split's PA or BF, 0 when the split is missing."""
    return int(_number(split_stats or {}, key))


def hitter_split_rates(split_stats, overall_rates):
    """Hitter rates versus one pitcher hand, regressed by the split's plate appearances."""
    return regress_split(hitter_rates(split_stats), overall_rates, split_count(split_stats, "pa"))


def pitcher_split_rates(split_stats, overall_rates):
    """Pitcher rates versus one batter side, regressed by the split's batters faced."""
    return regress_split(pitcher_rates(split_stats), overall_rates, split_count(split_stats, "tbf"))


def batting_side(bats, throws):
    """
    The side a batter hits from against a pitcher who throws `throws`.
    A switch hitter bats from the side opposite the pitcher's arm. None when it cannot be known.
    """
    if bats == SWITCH_HITTER:
        return {"L": "R", "R": "L"}.get(throws)
    if bats in ("L", "R"):
        return bats
    return None


def plate_appearance_rates(batter_card, pitcher_card, bats, throws):
    """
    The rates to send to the engine's /step for one plate appearance:
    {"hitter_rates": the batter's split versus the pitcher's throwing hand,
     "pitcher_rates": the pitcher's split versus the side the batter hits from}.
    `bats` is the batter's Player.bats (L, R, or S for a switch hitter) and `throws` the
    pitcher's Player.throws. When a hand is unknown, or the card has no split, the
    overall card is used. The game puts hitter_rates on the batter's lineup card and
    pitcher_rates on the pitcher's card in the state it sends.
    """
    hitter_split = {
        "L": batter_card.hitter_rates_vs_lhp,
        "R": batter_card.hitter_rates_vs_rhp,
    }.get(throws)
    pitcher_split = {
        "L": pitcher_card.pitcher_rates_vs_lhh,
        "R": pitcher_card.pitcher_rates_vs_rhh,
    }.get(batting_side(bats, throws))
    return {
        "hitter_rates": hitter_split or batter_card.hitter_rates,
        "pitcher_rates": pitcher_split or pitcher_card.pitcher_rates,
    }


def batted_ball_rates(stats):
    """
    Ground-ball, fly-ball and line-drive shares of batted balls, from FanGraphs GB/FB/LD counts.
    Works on hitting or pitching stats. None when the payload has no batted balls; the engine
    then uses league rates.
    """
    if not stats:
        return None
    counts = {key: _number(stats, key) for key in ("gb", "fb", "ld")}
    total = sum(counts.values())
    if total <= 0:
        return None
    return {key: count / total for key, count in counts.items()}


def _pitches_per_appearance(stats):
    games = _number(stats, "g")
    pitches = _number(stats, "pitches")
    if games <= 0 or pitches <= 0:
        return None
    return pitches / games


def fatigue_profile(pitch_stats, career_pitch_stats=None):
    """
    The sample the engine draws the fatigue line from.
    A pitcher who started at least half his games is a starter.
    When no career pitch count is stored, the card season stands in for career.
    """
    if not pitch_stats:
        return None

    games = int(_number(pitch_stats, "g"))
    games_started = int(_number(pitch_stats, "gs"))
    season_ppa = _pitches_per_appearance(pitch_stats) or 0.0

    career_ppa = None
    if career_pitch_stats:
        career_ppa = _pitches_per_appearance(career_pitch_stats)
    if career_ppa is None:
        career_ppa = season_ppa

    return {
        "role": "starter" if games > 0 and games_started * 2 >= games else "reliever",
        "age": int(_number(pitch_stats, "age")),
        "season_pitches_per_appearance": season_ppa,
        "career_pitches_per_appearance": career_ppa,
        "season_appearances": games,
    }


def fg_innings(value):
    """FanGraphs writes innings as whole.outs, so 300.1 is 300 and one third."""
    if value in (None, ""):
        return 0.0
    value = float(value)
    whole = int(value)
    outs = round((value - whole) * 10)
    return whole + outs / 3


def fielding_from_stats(fielding_stats):
    """Map stored FanGraphs fielding rows to {position: (innings, fielding runs)} for fielding positions."""
    fielding = {}
    for position, row in (fielding_stats or {}).items():
        if position not in DEFENSE_POSITIONS:
            continue
        innings = fg_innings(row.get("inn"))
        if innings <= 0:
            continue
        fielding[position] = (innings, _number(row, "frp"))
    return fielding


def position_rating(runs, innings):
    """Fielding runs per inning, scaled to a full season and regressed toward average."""
    return runs * FULL_SEASON_INNINGS / (innings + DEFENSE_REGRESSION_INNINGS)


def primary_position(fielding):
    """The position with the most innings, or None for a player with no fielding row."""
    if not fielding:
        return None
    return max(DEFENSE_POSITIONS, key=lambda pos: (fielding.get(pos, (0, 0))[0], -DEFENSE_POSITIONS.index(pos)))


def spectrum_anchor(fielding):
    """The spectrum position he played the most, or None when he only played 1B and/or C."""
    played = [position for position in SPECTRUM_POSITIONS if position in (fielding or {})]
    if not played:
        return None
    return max(played, key=lambda position: (fielding[position][0], -SPECTRUM_POSITIONS.index(position)))


def infield_anchor(fielding):
    """The 2B, 3B, or SS he played the most, or None when he never played them."""
    played = [position for position in INFIELD_RANGE_POSITIONS if position in (fielding or {})]
    if not played:
        return None
    return max(played, key=lambda position: (fielding[position][0], -INFIELD_RANGE_POSITIONS.index(position)))


def _spectrum_ratings(anchor, base_rating, fielding):
    """Slotted runs from one anchor. Catcher is left unset."""
    ratings = {}
    for slot in DEFENSE_POSITIONS:
        if slot == CATCHER:
            continue
        spectrum = base_rating + SPECTRUM_GAINS[slot] - SPECTRUM_GAINS[anchor]
        if slot == anchor:
            rating = base_rating
        elif slot in fielding:
            innings, runs = fielding[slot]
            rating = (runs * FULL_SEASON_INNINGS + DEFENSE_REGRESSION_INNINGS * spectrum) / (
                innings + DEFENSE_REGRESSION_INNINGS
            )
        else:
            rating = spectrum
        ratings[slot] = _one_decimal(rating)
    return ratings


def _infield_ratings_from_play(fielding):
    """2B, 3B, and SS from innings actually played there.

    The most-played of those is rated from its own innings, and the other two
    slide from that rating. All three are None when he never played them.
    An outfield rating is not mixed in.
    """
    blank = {position: None for position in INFIELD_RANGE_POSITIONS}
    anchor = infield_anchor(fielding)
    if anchor is None:
        return blank
    base = position_rating(fielding[anchor][1], fielding[anchor][0])
    rated = _spectrum_ratings(anchor, base, fielding)
    return {position: rated[position] for position in INFIELD_RANGE_POSITIONS}


def defense_ratings(fielding):
    """
    Slotted defense runs at every position, to one decimal.
    Catcher is rated only from catcher innings and is None for a player who never caught.
    First base and catcher do not anchor the spectrum. A player who only played those
    is rated only there. Innings at 2B, 3B, SS, LF, CF, or RF anchor the spectrum.
    An outfield anchor fills the outfield and first base only. 2B, 3B, and SS stay
    empty unless he played one of them; the most-played of those then anchors the
    other two. When his most-played position is 1B or C, first-base innings stay his
    scooping rating instead of being blended into the anchor.
    A player with no fielding row is a 0 first baseman.
    """
    if not fielding:
        ratings = _spectrum_ratings(FIRST_BASE, 0.0, {})
        ratings[CATCHER] = None
        return ratings

    ratings = {position: None for position in DEFENSE_POSITIONS}
    if CATCHER in fielding:
        innings, runs = fielding[CATCHER]
        ratings[CATCHER] = _one_decimal(position_rating(runs, innings))

    anchor = spectrum_anchor(fielding)
    primary = primary_position(fielding)
    if anchor is None:
        if FIRST_BASE in fielding:
            innings, runs = fielding[FIRST_BASE]
            ratings[FIRST_BASE] = _one_decimal(position_rating(runs, innings))
        return ratings

    base_rating = position_rating(fielding[anchor][1], fielding[anchor][0])
    ratings.update(_spectrum_ratings(anchor, base_rating, fielding))
    if FIRST_BASE in fielding and primary in (FIRST_BASE, CATCHER):
        innings, runs = fielding[FIRST_BASE]
        ratings[FIRST_BASE] = _one_decimal(position_rating(runs, innings))
    if anchor in OUTFIELD_POSITIONS:
        ratings.update(_infield_ratings_from_play(fielding))
    return ratings


def _one_decimal(value):
    # Adding 0.0 turns a rounded -0.0 into 0.0 so the card never prints "-0.0".
    return round(value, 1) + 0.0


def sim_defense(card_runs):
    """The engine sums nine fielders and moves 0.002 of a plate appearance per point, so it takes runs / 10."""
    return card_runs / 10


def playing_primary(card, player=None):
    """The position eligibility follows: the card's primary, else the player's listed position."""
    primary = getattr(card, "primary_position", None) if card is not None else None
    if primary:
        return primary
    raw = ""
    if player is not None and getattr(player, "position", None):
        raw = player.position.upper()
    if raw in ("C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"):
        return raw
    if raw in ("OF", "OF-P"):
        return "CF"
    if raw in ("IF", "IF-P", "IF-OF"):
        return "SS"
    if raw == "DH-P":
        return "DH"
    return None


def eligible_positions(primary, defense, throws=None):
    """
    Defensive positions a manager may slot him at. DH is always added by the lineup.
    An outfielder is always listed at first base and the outfield, and at 2B, 3B, or SS
    when his rating there is better than OUTFIELDER_INFIELD_CUTOFF.
    A primary first baseman or catcher is listed only where he has a rating, so scooping
    and catching do not qualify him elsewhere. A left-handed thrower is never listed at
    2B, 3B, SS, or C.
    """
    defense = defense or {}
    if primary in (CATCHER, FIRST_BASE):
        listed = [position for position in DEFENSE_POSITIONS if defense.get(position) is not None]
        if primary == FIRST_BASE and FIRST_BASE not in listed:
            listed = [position for position in DEFENSE_POSITIONS if position == FIRST_BASE or position in listed]
    elif primary in OUTFIELD_POSITIONS:
        listed = []
        for position in DEFENSE_POSITIONS:
            if position in OUTFIELD_POSITIONS or position == FIRST_BASE:
                listed.append(position)
                continue
            if position == CATCHER:
                continue
            runs = slotted_runs(defense, primary, position)
            if runs is not None and runs > OUTFIELDER_INFIELD_CUTOFF:
                listed.append(position)
    elif primary in INFIELD_POSITIONS:
        listed = ["1B", "2B", "3B", "SS", "LF", "CF", "RF"]
        if defense.get(CATCHER) is not None:
            listed = [CATCHER, *listed]
    else:
        listed = [position for position in DEFENSE_POSITIONS if defense.get(position) is not None]
        listed = listed or ["1B", "2B", "3B", "SS", "LF", "CF", "RF"]
    if throws == "L":
        listed = [position for position in listed if position not in LEFTY_BLOCKED_POSITIONS]
    return listed


def cannot_play(player, position, defense, primary, season):
    """Why he cannot be filed at position, or None. DH is always allowed."""
    if position in (None, "DH"):
        return None
    name = player.name
    if getattr(player, "throws", None) == "L" and position in LEFTY_BLOCKED_POSITIONS:
        return f"{name} throws left and cannot play {position}."
    if position == CATCHER and (defense or {}).get(CATCHER) is None:
        return f"{name} has no catcher rating for {season - 1} and cannot play {CATCHER}."
    if position not in eligible_positions(primary, defense, getattr(player, "throws", None)):
        return f"{name} cannot play {position}."
    return None


def slotted_runs(defense, primary, position):
    """Stored spectrum runs at a position, with the infielder-to-outfield penalty applied once."""
    if not defense or defense.get(position) is None:
        return None
    penalty = INF_TO_OF_PENALTY if primary in INFIELD_POSITIONS and position in OUTFIELD_POSITIONS else 0
    return round(defense[position] - penalty, 1) + 0.0


def shown_defense(defense, primary, throws=None):
    """Eligible positions that have a rating, in display order, after the outfield penalty."""
    rows = []
    for position in eligible_positions(primary, defense, throws):
        runs = slotted_runs(defense, primary, position)
        if runs is None:
            continue
        rows.append((position, runs))
    return rows
