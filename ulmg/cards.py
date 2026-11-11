# ABOUTME: Builds engine card numbers (hitter/pitcher rates, platoon splits, running, fatigue, slotted defense) from FanGraphs stats.
# ABOUTME: Keys match the engine's HitterRates, PitcherRates and FatigueProfile; the engine reads these and computes nothing.
from django.conf import settings

# Steal success is regressed toward a league-average base stealer with this many attempts at this rate.
STEAL_PRIOR_ATTEMPTS = 10
STEAL_PRIOR_SUCCESS_RATE = 0.72

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


def speed(hit_stats):
    """FanGraphs Spd, or None when the payload has none."""
    if not hit_stats or hit_stats.get("spd") in (None, ""):
        return None
    try:
        return float(hit_stats["spd"])
    except (TypeError, ValueError):
        return None


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


def defense_ratings(fielding):
    """
    Slotted defense runs at every position, to one decimal.
    Catcher is rated only from catcher innings and is None for a player who never caught.
    Everywhere else follows the spectrum from the primary position; a primary catcher
    or a player with no fielding row is a 0 first baseman.
    """
    primary = primary_position(fielding)
    if primary is None or primary == CATCHER:
        base_position, base_rating = FIRST_BASE, 0.0
    else:
        base_position = primary
        base_rating = position_rating(fielding[primary][1], fielding[primary][0])

    ratings = {}
    for slot in DEFENSE_POSITIONS:
        if slot == CATCHER:
            if CATCHER in fielding:
                innings, runs = fielding[CATCHER]
                ratings[slot] = _one_decimal(position_rating(runs, innings))
            else:
                ratings[slot] = None
            continue

        spectrum = base_rating + SPECTRUM_GAINS[slot] - SPECTRUM_GAINS[base_position]
        if slot == primary:
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


def _one_decimal(value):
    # Adding 0.0 turns a rounded -0.0 into 0.0 so the card never prints "-0.0".
    return round(value, 1) + 0.0


def sim_defense(card_runs):
    """The engine sums nine fielders and moves 0.002 of hit probability per point, so it takes runs / 10."""
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
    return None


def eligible_positions(primary, defense):
    """Defensive positions a manager may slot him at. DH is always added by the lineup."""
    defense = defense or {}
    if primary == CATCHER:
        return [CATCHER, FIRST_BASE]
    if primary in OUTFIELD_POSITIONS:
        return [FIRST_BASE, "LF", "CF", "RF"]
    if primary in INFIELD_POSITIONS:
        positions = ["1B", "2B", "3B", "SS", "LF", "CF", "RF"]
        if defense.get(CATCHER) is not None:
            return [CATCHER, *positions]
        return positions
    rated = [position for position in DEFENSE_POSITIONS if defense.get(position) is not None]
    return rated or ["1B", "2B", "3B", "SS", "LF", "CF", "RF"]


def slotted_runs(defense, primary, position):
    """Stored spectrum runs at a position, with the infielder-to-outfield penalty applied once."""
    if not defense or defense.get(position) is None:
        return None
    penalty = INF_TO_OF_PENALTY if primary in INFIELD_POSITIONS and position in OUTFIELD_POSITIONS else 0
    return round(defense[position] - penalty, 1) + 0.0


def shown_defense(defense, primary):
    """Eligible positions that have a rating, in display order, after the outfield penalty."""
    rows = []
    for position in eligible_positions(primary, defense):
        runs = slotted_runs(defense, primary, position)
        if runs is None:
            continue
        rows.append((position, runs))
    return rows
