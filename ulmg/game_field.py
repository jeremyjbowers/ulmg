# ABOUTME: Live game state for the SNES field: world-space fielders, the batter's hand, the mound card and the last ball.
# ABOUTME: The SVG itself is composed in the browser from pixelkit.mjs; this module is the JSON the page feeds it.

from ulmg import cards, usage

# World feet. +x is toward first, +z toward center. Matches pixelkit POS.
POS = {
    "P": (0, 60.5),
    "C": (0, -10),
    "1B": (52, 80),
    "2B": (36, 136),
    "SS": (-36, 136),
    "3B": (-52, 80),
    "LF": (-150, 255),
    "CF": (0, 315),
    "RF": (150, 255),
}
BASE_GROUND = {
    "first": (63.6, 63.6),
    "second": (0, 127.3),
    "third": (-63.6, 63.6),
}
FIELDER_POSITIONS = ("CF", "LF", "RF", "SS", "2B", "3B", "1B", "C")
SKINS = ("light", "medium", "dark")
LOGICAL = {"width": 320, "height": 180}
MIN_SCALE = 4

LANDINGS = {
    "ground_out": [(48, 100), (-42, 105), (78, 82), (-74, 80)],
    "grounded_into_double_play": [(36, 120), (-32, 118)],
    "line_out": [(-90, 190), (0, 210), (96, 188), (-40, 160)],
    "fly_out": [(-120, 270), (0, 300), (130, 268)],
    "sacrifice_fly": [(-110, 280), (120, 276)],
    "single": [(-70, 175), (80, 170), (20, 200), (110, 145)],
    "double": [(-130, 240), (140, 236), (-60, 270), (70, 265)],
    "triple": [(-150, 300), (155, 295)],
    "home_run": [(-160, 345), (0, 350), (165, 345)],
    "bunt_single": [(-28, 36), (30, 34)],
    "bunt_out": [(-8, 28), (10, 26)],
    "bunt_sacrifice": [(-12, 30), (14, 28)],
    "bip_out": [(0, 150)],
    "reached_on_error": [(40, 95), (-36, 100), (70, 78)],
}
KINDS = {
    "ground_out": "ground",
    "grounded_into_double_play": "ground",
    "bunt_out": "bunt",
    "bunt_sacrifice": "bunt",
    "bunt_single": "bunt",
    "line_out": "line",
    "single": "line",
    "double": "line",
    "fly_out": "fly",
    "sacrifice_fly": "fly",
    "triple": "fly",
    "home_run": "fly",
    "bip_out": "line",
    "reached_on_error": "ground",
}
HEIGHT_FT = {"bunt": 4, "ground": 8, "line": 18, "fly": 40}
BANNERS = {
    "strikeout": "STRIKEOUT",
    "walk": "WALK",
    "hit_by_pitch": "HIT BY PITCH",
    "intentional_walk": "INTENTIONAL WALK",
    "single": "SINGLE",
    "double": "DOUBLE",
    "triple": "TRIPLE",
    "home_run": "HOME RUN",
    "ground_out": "GROUND OUT",
    "fly_out": "FLY OUT",
    "line_out": "LINE OUT",
    "grounded_into_double_play": "DOUBLE PLAY",
    "sacrifice_fly": "SAC FLY",
    "bunt_sacrifice": "SAC BUNT",
    "bunt_single": "BUNT HIT",
    "bunt_out": "BUNT OUT",
    "caught_stealing": "CAUGHT STEALING",
    "bip_out": "IN PLAY",
    "reached_on_error": "ERROR",
}


def skin_for(player_id):
    """A stable kit skin for one player, from his id so it does not flicker."""
    return SKINS[int(player_id or 0) % 3]


def fielding_label(rating):
    """The engine stores fielding runs divided by 10. The field shows the runs, signed."""
    runs = round(float(rating or 0) * 10, 1)
    if runs > 0:
        return f"+{runs:.1f}"
    return f"{runs:.1f}"


def fielding_runs(rating):
    return round(float(rating or 0) * 10, 1)


def batter_box(bats, throws):
    """
    Which side of the plate he stands on, in this view from behind home.
    Left is the third-base side, where a right-handed batter stands.
    A hand that cannot be known stands there too.
    """
    if cards.batting_side(bats, throws) == "L":
        return "right"
    return "left"


def batter_flip(box):
    """A left-handed batter is mirrored and stands on the first-base side."""
    return box == "right"


def short_name(name):
    """The last name on a jersey. Long ones keep nine letters and a dot."""
    parts = (name or "").split()
    label = parts[-1] if parts else ""
    if len(label) > 10:
        return label[:9] + "."
    return label


def jersey_name(player):
    """The name on the jersey: the stored last name, or the last word of the full name."""
    label = (getattr(player, "last_name", None) or "").strip()
    if not label:
        label = short_name(getattr(player, "name", "") or "")
    if len(label) > 10:
        return label[:9] + "."
    return label


def ball_track(result):
    """World landing of one batted ball, or None when the plate appearance was not in play."""
    if not result:
        return None
    outcome = result.get("outcome")
    spots = LANDINGS.get(outcome)
    if not spots:
        return None
    gx, gz = _pick(spots, result)
    kind = KINDS[outcome]
    return {
        "outcome": outcome,
        "kind": kind,
        "label": BANNERS.get(outcome, outcome.replace("_", " ").upper()),
        "x": gx,
        "z": gz,
        "height_ft": HEIGHT_FT[kind],
        "count": _count(result),
    }


def result_banner(result):
    """The banner for the last plate appearance. In-play results also carry their landing."""
    if not result or not result.get("outcome"):
        return None
    outcome = result["outcome"]
    banner = {
        "outcome": outcome,
        "label": BANNERS.get(outcome, outcome.replace("_", " ").upper()),
        "count": _count(result),
        "kind": None,
        "x": None,
        "z": None,
        "height_ft": None,
    }
    track = ball_track(result)
    if track:
        banner.update(track)
    return banner


def field_view(play):
    """JSON for the field composer, or None once the game is final."""
    from ulmg import sim_game
    from ulmg.models import GameEvent

    state = play.state
    if not state or sim_game.is_final(state):
        return None
    fielding = sim_game.fielding_side(state)
    batting = sim_game.batting_side(state)
    fielders = _fielders(play, state[fielding]["lineup"], fielding)
    pitcher = _pitcher(play, state, fielding)
    batter = _batter(play, state, batting, pitcher)
    runners = _runners(play, state, batting)
    bases = state.get("bases") or {}
    banner = result_banner(_recent_result(play, GameEvent.PLATE_APPEARANCE))
    return {
        "fielders": fielders,
        "pitcher": pitcher,
        "batter": batter,
        "runners": runners,
        "banner": banner,
        "bases": {
            "first": bool(bases.get("first")),
            "second": bool(bases.get("second")),
            "third": bool(bases.get("third")),
        },
        "steal_live": bool((bases.get("first") and not bases.get("second")) or (bases.get("second") and not bases.get("third"))),
        "hit_and_run_live": bool(bases.get("first")),
        "width": LOGICAL["width"],
        "height": LOGICAL["height"],
        "scale": MIN_SCALE,
    }


def _actor(player, x, z, side):
    return {
        "name": player.name,
        "short_name": jersey_name(player),
        "player_id": player.id,
        "x": x,
        "z": z,
        "team": side,
        "skin": skin_for(player.id),
    }


def _fielders(play, lineup, side):
    by_position = {}
    for entry in lineup:
        position = entry.get("position")
        if position not in FIELDER_POSITIONS:
            continue
        player = play.player(entry["id"])
        rating = (entry.get("defense") or {}).get("rating") or 0
        x, z = POS[position]
        actor = _actor(player, x, z, side)
        actor.update(
            {
                "position": position,
                "rating": fielding_runs(rating),
                "fielding": fielding_label(rating),
                "sprite": "catcher" if position == "C" else "fielder_ready",
            }
        )
        by_position[position] = actor
    return [by_position[position] for position in FIELDER_POSITIONS if position in by_position]


def _pitcher(play, state, fielding):
    pitcher_id = state[fielding].get("pitcher_slot")
    if not pitcher_id:
        return None
    player = play.player(pitcher_id)
    fatigue = (state[fielding].get("fatigue") or {}).get(str(pitcher_id), {})
    effort = 0 if fatigue.get("effort") is None else fatigue.get("effort")
    ceiling = 0 if fatigue.get("ceiling") is None else fatigue.get("ceiling")
    pitches = 0 if fatigue.get("pitches") is None else fatigue.get("pitches")
    width = 0 if not ceiling else max(0, min(72, round(72 * float(pitches) / float(ceiling))))
    _hit, pitch = usage.card_stats(player, play.season)
    actor = _actor(player, POS["P"][0], POS["P"][1], fielding)
    actor.update(
        {
            "xfip": _xfip(pitch),
            "xfip_label": _xfip(pitch) or "—",
            "pitches": pitches,
            "effort": effort,
            "ceiling": ceiling,
            "fatigue_label": f"{round(float(effort))}/{round(float(ceiling))}",
            "fatigue_width": width,
            "fatigue_tone": _fatigue_tone(pitches, ceiling),
            "throws": player.throws or "?",
            "sprite": "pitch_set",
        }
    )
    return actor


def _batter(play, state, batting, pitcher):
    club = state[batting]
    batter_id = club["lineup"][club["batter_index"]]["id"]
    player = play.player(batter_id)
    throws = pitcher["throws"] if pitcher else None
    if throws == "?":
        throws = None
    box = batter_box(player.bats, throws)
    hand = cards.batting_side(player.bats, throws) or player.bats or "?"
    actor = _actor(player, 0, 0, batting)
    actor.update(
        {
            "hand": hand,
            "box": box,
            "flip": batter_flip(box),
            "slash": _slash(play, player),
            "sprite": "bat_stance",
        }
    )
    return actor


def _runners(play, state, batting):
    runners = []
    for base, ground in BASE_GROUND.items():
        runner_id = (state.get("bases") or {}).get(base)
        if not runner_id:
            continue
        player = play.player(runner_id)
        actor = _actor(player, ground[0], ground[1], batting)
        actor["base"] = base
        actor["sprite"] = "run_a"
        runners.append(actor)
    return runners


def _slash(play, player):
    card = play.card(player)
    line = card.hitter_line() if card else None
    if not line or line.get("avg") is None or line.get("slg") is None:
        return "—"
    return f"{_three(line['avg'])} {_three(line['obp'])} {_three(line['slg'])}"


def _three(n):
    return f"{float(n):.3f}".replace("0.", ".")


def _recent_result(play, plate_appearance):
    """The plate appearance just played, including one the computer followed with its own move."""
    for event in reversed(play.events):
        if event.kind == plate_appearance:
            return (play.state or {}).get("last_result")
        if not event.computer:
            return None
    return None


def _fatigue_tone(pitches, ceiling):
    if not ceiling:
        return "ok"
    share = float(pitches) / float(ceiling)
    if share > 0.9:
        return "hot"
    if share > 0.7:
        return "warm"
    return "ok"


def _xfip(pitch):
    if not pitch or pitch.get("xfip") in (None, ""):
        return None
    try:
        return f"{float(pitch['xfip']):.2f}"
    except (TypeError, ValueError):
        return None


def _count(result):
    count = result.get("count") or {}
    if "balls" not in count and "strikes" not in count:
        return ""
    return f"{count.get('balls', 0)}-{count.get('strikes', 0)}"


def _pick(options, result):
    count = result.get("count") or {}
    key = f"{result.get('batter_id')}|{result.get('outcome')}|{count.get('balls')}|{count.get('strikes')}"
    total = 0
    for char in key:
        total = (total * 33 + ord(char)) & 0xFFFFFFFF
    return options[total % len(options)]
