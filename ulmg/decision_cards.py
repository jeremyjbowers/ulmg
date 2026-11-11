# ABOUTME: The card a manager reads while setting a lineup or a starter.
# ABOUTME: Hitters show playing time, offense, defense and speed. Pitchers show the usage rules and their rates.

from ulmg import models, usage

# FanGraphs Spd runs roughly 0 to 10. These bands are a glance, not a grade.
SLOW = 3
AVERAGE = 5
FAST = 7


def load(players, season):
    """Card-season stats and cards for many players: ({id: (hit, pitch)}, {id: Card})."""
    players = list(players)
    stats = usage.card_stats_by_player(players, season)
    cards = {
        row.player_id: row
        for row in models.Card.objects.filter(
            player_id__in=[player.id for player in players],
            season=season - 1,
        )
    }
    return stats, cards


def hitter_card(player, hit, card):
    """What a hitter's card shows: PA, WAR, wRC+, the slash line, defense and speed."""
    hit = hit or {}
    return {
        "player": player,
        "kind": "h",
        "pa_label": _plate_appearances(hit),
        "war_label": _decimal(hit.get("war"), 1),
        "wrc_label": _wrc(hit, card),
        "slash": _slash(card),
        "defense_label": _defense(card),
        "speed_label": speed_label(card.spd if card is not None else None),
    }


def pitcher_card(player, pitch, card):
    """
    What a pitcher's card shows. A reliever's innings max is 1.25x at 60
    innings and 1.5x at 70, the same table the usage ledger enforces.
    """
    pitch = pitch or {}
    caps = usage.caps_from_stats({}, pitch)
    return {
        "player": player,
        "kind": "p",
        "starts_label": _starts(pitch, caps),
        "innings_label": _innings(pitch, caps),
        "xfip_label": _decimal(pitch.get("xfip"), 2),
        "war_label": _decimal(pitch.get("war"), 1),
        "k9_label": _decimal(pitch.get("k_9"), 1),
        "bb9_label": _decimal(pitch.get("bb_9"), 1),
    }


def speed_label(spd):
    """A rough speed word from FanGraphs Spd. None when the card has no Spd."""
    if spd is None:
        return "-"
    if spd < SLOW:
        return "slow"
    if spd < AVERAGE:
        return "average"
    if spd < FAST:
        return "fast"
    return "burner"


def _plate_appearances(hit):
    """unlimited once the usage rules drop the cap, otherwise the plate appearances."""
    if not hit:
        return "-"
    caps = usage.caps_from_stats(hit, {})
    plate_appearances = usage._count(hit, "pa")
    if caps["plate_appearances_cap"] is None and (
        plate_appearances or usage._count(hit, "ab")
    ):
        return "unlimited"
    if plate_appearances:
        return str(plate_appearances)
    return "-"


def _wrc(hit, card):
    value = card.wrc_plus if card is not None and card.wrc_plus is not None else hit.get("wrc_plus")
    if value in (None, ""):
        return "-"
    try:
        return str(int(round(float(value))))
    except (TypeError, ValueError):
        return "-"


def _slash(card):
    line = card.hitter_line() if card is not None else None
    if not line:
        return "-"

    def fmt(value):
        if value is None:
            return "-"
        text = f"{value:.3f}"
        return text[1:] if text.startswith("0") else text

    return f"{fmt(line['avg'])}/{fmt(line['obp'])}/{fmt(line['slg'])}"


def _defense(card):
    if card is None:
        return "-"
    parts = []
    for position, runs in card.defense_display():
        sign = "+" if runs > 0 else ""
        parts.append(f"{position} {sign}{runs:.1f}")
    return ", ".join(parts) if parts else "-"


def _starts(pitch, caps):
    starts = usage._count(pitch, "gs")
    cap = caps["starts_cap"] or 0
    if starts == 0 and cap == 0:
        return "0 GS"
    if cap and cap != starts:
        return f"{starts} GS (max {cap})"
    return f"{starts} GS"


def _innings(pitch, caps):
    raw = pitch.get("ip")
    if raw in (None, ""):
        return "-"
    cap = caps["innings_cap_outs"]
    confined = caps["confined_innings_cap_outs"]
    if cap is None and confined is None:
        return f"{raw} IP"
    if cap is not None and confined is not None and confined != cap:
        return (
            f"{raw} IP (max {usage.outs_to_innings(cap)}, "
            f"{usage.outs_to_innings(confined)} if he only relieves)"
        )
    shown = cap if cap is not None else confined
    return f"{raw} IP (max {usage.outs_to_innings(shown)})"


def _decimal(value, digits):
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"
