# ABOUTME: Builds engine card numbers (hitter/pitcher rates, fatigue profile, slotted defense) from FanGraphs stats.
# ABOUTME: Keys match the engine's HitterRates, PitcherRates and FatigueProfile; the engine reads these and computes nothing.
from django.conf import settings

FULL_SEASON_INNINGS = 1300
DEFENSE_REGRESSION_INNINGS = 600

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
