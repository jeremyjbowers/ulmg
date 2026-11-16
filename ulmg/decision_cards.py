# ABOUTME: The card a manager reads while setting a lineup or a starter.
# ABOUTME: A hitter is three lines: the summary, vsL and vsR slashes, and defense. A glove of -10 runs or worse is emergency only.

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ulmg import cards, models, usage

# FanGraphs Spd runs about 0 to 10. Zero on the card is an average 5.
SPD_AVERAGE = 5

# FanGraphs WAR already counts hitting, baserunning and defense. Per 600
# plate appearances, about 2 wins is an average hitter. Two wins either
# side of that is the full wash. An xFIP of 4.10 is an average arm, and
# 0.80 of xFIP reaches the full wash.
HITTER_AVERAGE = 2.0
HITTER_SPAN = 2.0
PA_PER_RATE = 600
PITCHER_AVERAGE = 4.10
PITCHER_SPAN = 0.80

# The darkest green and the reddest pink a card takes. Both stay light enough to read.
PALE_GREEN = (198, 228, 208)
LIGHT_PINK = (250, 214, 220)

# League-average OPS the platoon wash is centered on. Two tenths of OPS is the full wash.
# Fewer than six points off that average is not a wash: it would read as a white patch on the card.
OPS_AVERAGE = 0.720
OPS_SPAN = 0.200
OPS_QUIET = 0.006

# A shown defensive rating of this or worse, in runs, is not a normal button.
# -10 itself is emergency. The button stays available under Emergency only.
EMERGENCY_DEFENSE = -10


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
    """Name, hand, PA, speed, WAR, the two platoon slashes, and defense. The card wash is WAR per 600; each line has its own OPS wash."""
    hit = hit or {}
    versus_left = _platoon_side(card, card.hitter_rates_vs_lhp if card is not None else None)
    versus_right = _platoon_side(card, card.hitter_rates_vs_rhp if card is not None else None)
    rows = _defense_rows(card, player)
    return {
        "player": player,
        "kind": "h",
        "pa_label": _plate_appearances(hit),
        "war_label": _decimal(hit.get("war"), 1),
        "rate_label": _rate_label(hit),
        "wrc_label": _wrc(hit, card),
        "slash": _slash(card),
        "slash_vs_l": versus_left["slash"],
        "slash_vs_r": versus_right["slash"],
        "shade_vs_l": versus_left["shade"],
        "shade_vs_r": versus_right["shade"],
        "defense_label": _defense(card, player),
        "defense_rows": rows,
        "speed_label": speed_label(card.spd if card is not None else None),
        "positions": _lineup_positions(card, player),
        "emergency_positions": [row["position"] for row in rows if row["emergency"]],
        "shade": hitter_shade(war_per_600(hit)),
    }


def pitcher_card(player, pitch, card, designation=None):
    """
    What a pitcher's card shows. A reliever's innings max is 1.25x at 60
    innings and 1.5x at 70, the same table the usage ledger enforces.
    designation is rotation or bullpen. With none, the card season's role
    stands in until a counter exists.
    """
    pitch = pitch or {}
    if designation not in usage.DESIGNATIONS:
        designation = shown_designation(pitch, None)
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
        "shade": pitcher_shade(_stat_number(pitch.get("xfip"))),
        "designation": designation,
        "starts": usage._count(pitch, "gs"),
    }


def shown_designation(pitch, confined):
    """
    The Starter or Reliever button.
    A pitcher who never started stays a reliever: he has no starts to give.
    Anyone who did start shows as a starter until a stored bullpen
    designation names him a reliever. That is also how a swingman's cap starts.
    """
    pitch = pitch or {}
    # No starts on the card means no starts to give, so the button stays Reliever.
    if usage._count(pitch, "g") > 0 and usage._count(pitch, "gs") == 0:
        return usage.BULLPEN
    if confined is True:
        return usage.BULLPEN
    return usage.ROTATION


def shade_color(score):
    """A background for a score from -1 (below average) to 1 (above). 0 is no wash."""
    score = max(-1.0, min(1.0, float(score)))
    if score == 0:
        return None
    target = PALE_GREEN if score > 0 else LIGHT_PINK
    amount = abs(score) ** 0.5
    channels = tuple(round(255 + (channel - 255) * amount) for channel in target)
    return "#{:02x}{:02x}{:02x}".format(*channels)


def war_per_600(hit):
    """FanGraphs WAR scaled to 600 plate appearances. None without both WAR and PA."""
    hit = hit or {}
    war = _stat_number(hit.get("war"))
    pa = _stat_number(hit.get("pa"))
    if war is None or pa is None or pa <= 0:
        return None
    return war * PA_PER_RATE / pa


def hitter_shade(rate):
    """Pale green above 2 WAR per 600 PA, light pink below. None at average or with no rate."""
    value = _stat_number(rate)
    if value is None:
        return None
    return shade_color((value - HITTER_AVERAGE) / HITTER_SPAN)


def pitcher_shade(xfip):
    """Pale green below a 4.10 xFIP, light pink above. None at average or with no xFIP."""
    value = _stat_number(xfip)
    if value is None:
        return None
    return shade_color((PITCHER_AVERAGE - value) / PITCHER_SPAN)


def ops_shade(ops):
    """Pale green above a .720 OPS, light pink below. None within six points of average, or with no OPS."""
    value = _stat_number(ops)
    if value is None or abs(value - OPS_AVERAGE) < OPS_QUIET:
        return None
    return shade_color((value - OPS_AVERAGE) / OPS_SPAN)


def speed_label(spd):
    """Whole steps from an average FanGraphs Spd. 8 is +3 and 4 is -1. None when the card has no Spd."""
    if spd is None:
        return "-"
    try:
        shifted = Decimal(str(spd)) - Decimal(SPD_AVERAGE)
        score = int(shifted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return "-"
    if score > 0:
        return f"+{score}"
    return str(score)


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


def _stat_number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _wrc_value(hit, card):
    if card is not None and card.wrc_plus is not None:
        return _stat_number(card.wrc_plus)
    return _stat_number((hit or {}).get("wrc_plus"))


def _rate_label(hit):
    rate = war_per_600(hit)
    if rate is None:
        return None
    return _decimal(rate, 1)


def _wrc(hit, card):
    value = _wrc_value(hit, card)
    if value is None:
        return "-"
    return str(int(round(value)))


def _drop_zero(value):
    """Three digits, with a leading zero removed so .900 matches the slash line."""
    text = f"{value:.3f}"
    if text.startswith("0"):
        text = text[1:]
    return text


def _format_slash(line):
    if not line:
        return "-"

    def fmt(value):
        if value is None:
            return "-"
        return _drop_zero(value)

    return f"{fmt(line['avg'])}/{fmt(line['obp'])}/{fmt(line['slg'])}"


def _line_ops(line):
    if not line or line["obp"] is None or line["slg"] is None:
        return None
    return line["obp"] + line["slg"]


def _platoon_side(card, rates):
    """The slash and wash for one side. Missing split rates fall back to the overall card."""
    line = models.Card._hitter_line_from(rates) if rates else None
    if line is None and card is not None:
        line = card.hitter_line()
    return {"slash": _format_slash(line), "shade": ops_shade(_line_ops(line))}


def _slash(card):
    line = card.hitter_line() if card is not None else None
    return _format_slash(line)


def _defense_rows(card, player):
    """Eligible ratings, with a glove at EMERGENCY_DEFENSE or worse marked emergency."""
    if card is None:
        return []
    rows = []
    for position, runs in cards.shown_defense(card.defense, cards.playing_primary(card, player)):
        sign = "+" if runs > 0 else ""
        rows.append({
            "position": position,
            "text": f"{position} {sign}{runs:.1f}",
            "emergency": runs <= EMERGENCY_DEFENSE,
        })
    return rows


def _defense(card, player):
    rows = _defense_rows(card, player)
    return ", ".join(row["text"] for row in rows) if rows else "-"


def _lineup_positions(card, player):
    defense = card.defense if card is not None else None
    codes = list(cards.eligible_positions(cards.playing_primary(card, player), defense))
    if "DH" not in codes:
        codes.append("DH")
    return codes


def _starts(_pitch, caps):
    """The ULMG starts limit. Real starts are not shown: 30 real starts and a 35-start cap shows 35."""
    return f"{caps['starts_cap'] or 0} starts"


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
