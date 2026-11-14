# ABOUTME: What the game HUD shows: the scoreboard, the batter and pitcher cards, the calls, the last plays and the substitution panel.
# ABOUTME: Every number comes from the game's log, its cards and the usage ledger; the pinch-hit odds come from the engine's /matchup.

import copy

from ulmg import cards, computer_manager, engine_client, game_field, park as home_park, usage

# ulmg.sim_game builds the page from this module, so functions here import it where they use it.

# Outcomes of the engine's matchup in which the batter reaches base.
REACH_KEYS = ("bb", "hbp", "single", "double", "triple", "hr")
ODDS_GOOD = REACH_KEYS
HANDS = {"R": "right", "L": "left", "S": "both"}
ROLE_NAMES = {
    computer_manager.CLOSER: "Closer",
    computer_manager.SIRP: "Single-inning",
    computer_manager.MIRP: "Multi-inning",
    computer_manager.OTHER: "Other arm",
}
RECENT_PLAYS = 4
TABS = (("ph", "Pinch hit"), ("pr", "Pinch run"), ("pit", "New pitcher"), ("def", "Defense"))


def three(value):
    """A rate the baseball way: .262, 1.000, or a dash when there is none."""
    if value is None:
        return "—"
    text = f"{float(value):.3f}"
    return text[1:] if text.startswith("0.") else text


def percent(value, places=0):
    if value is None:
        return "—"
    return f"{float(value) * 100:.{places}f}%"


def tenths(value):
    return "—" if value is None else f"{float(value):.1f}"


def ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def split_rates(card, throws):
    """The hitter's card rates against a pitcher's hand, or his overall card."""
    split = {"L": card.hitter_rates_vs_lhp, "R": card.hitter_rates_vs_rhp}.get(throws)
    return split or card.hitter_rates


def slash(line):
    if not line:
        return {"avg": "—", "obp": "—", "slg": "—", "hr": "—"}
    return {
        "avg": three(line.get("avg")),
        "obp": three(line.get("obp")),
        "slg": three(line.get("slg")),
        "hr": tenths(None if line.get("hr_pct") is None else line["hr_pct"] * 100),
    }


def slash_text(line):
    return f"{line['avg']}/{line['obp']}/{line['slg']}"


def hitter_line(card, throws):
    if card is None or not card.hitter_rates:
        return slash(None)
    return slash(card._hitter_line_from(split_rates(card, throws)))


# The scoreboard


def scoreboard(play, box, teams):
    """The line score with the inning being played lit, R/H/E, the inning with its arrow, and the outs."""
    from ulmg import sim_game

    state = play.state
    inning, half = state["inning"], state["half"]
    batting = sim_game.batting_side(state)
    header = [{"number": n, "now": n == inning, "early": n < inning} for n in box.innings]
    rows = []
    for side in sim_game.SIDES:
        cells = []
        for n, value in zip(box.innings, box.line.get(side, [])):
            unplayed = value in ("-", "X")
            cells.append(
                {
                    "value": "·" if value == "-" else value,
                    "now": n == inning,
                    "dim": unplayed,
                    "early": n < inning,
                    "inning": n,
                }
            )
        totals = box.totals.get(side, {"r": 0, "h": 0, "e": 0})
        rows.append({"side": side, "team": teams[side], "cells": cells, "batting": side == batting, **totals})
    outs = state["outs"]
    arrow = "▲" if half == "top" else "▼"
    return {
        "header": header,
        "rows": rows,
        "inning": f"{arrow} {'Top' if half == 'top' else 'Bottom'} {ordinal(inning)}",
        "short": f"{'Top' if half == 'top' else 'Bot'} {inning}",
        "outs": outs,
        "outs_text": f"{outs} out{'' if outs == 1 else 's'}",
        "lights": [n <= outs for n in (1, 2, 3)],
    }


# The cards


def _batting_today(box, side, player):
    line = next((line for line in box.batting.get(side, []) if line.player.id == player.id), None)
    if line is None or line.pa == 0:
        return "first time up today"
    parts = [f"{line.h}-for-{line.ab}"]
    for count, label in ((line.hr, "HR"), (line.bb, "BB"), (line.rbi, "RBI")):
        if count:
            parts.append(label if count == 1 else f"{count} {label}")
    return "today " + ", ".join(parts)


def _pitching_today(box, side, player):
    line = next((line for line in box.pitching.get(side, []) if line.player.id == player.id), None)
    if line is None or line.bf == 0:
        return "first batter today"
    return f"{line.ip} IP, {line.r} R, {line.so} K today"


def batter_card(play, box, teams):
    """The man at bat: slot, position, hands, today's line, both platoon lines, speed, steals, PA left, and who follows."""
    from ulmg import sim_game

    state = play.state
    side = sim_game.batting_side(state)
    club = state[side]
    index = club["batter_index"]
    entry = club["lineup"][index]
    player = play.player(entry["id"])
    card = play.card(player)
    pitcher_id = sim_game.current_pitcher_id(state)
    throws = play.player(pitcher_id).throws if pitcher_id else None
    splits = []
    for hand, label in (("R", "vs RHP"), ("L", "vs LHP")):
        splits.append({"label": label, "hot": hand == throws, **hitter_line(card, hand)})
    summary = usage.usage_summary(player, play.season, reads=play.usage)
    left = summary["plate_appearances_left"]
    due = []
    for step, label in ((1, "On deck"), (2, "In the hole")):
        nxt = club["lineup"][(index + step) % len(club["lineup"])]
        nxt_player = play.player(nxt["id"])
        due.append(
            {
                "label": label,
                "player": nxt_player,
                "position": nxt["position"],
                "avg": hitter_line(play.card(nxt_player), throws)["avg"],
            }
        )
    return {
        "side": side,
        "team": teams[side],
        "slot": ordinal(index + 1),
        "player": player,
        "position": entry["position"],
        "bats": HANDS.get(player.bats, "?"),
        "today": _batting_today(box, side, player),
        "splits": splits,
        "speed": tenths(getattr(card, "spd", None)),
        "steals": percent(getattr(card, "steal_success", None)),
        "pa_left": "unlimited" if left is None else left,
        "due": due,
    }


def pitcher_card(play, box, teams, odds):
    """The man on the mound: role, arm, today's line, pitches against his ceiling, innings left this outing, and the odds."""
    from ulmg import sim_game

    state = play.state
    side = sim_game.fielding_side(state)
    pitcher_id = sim_game.current_pitcher_id(state)
    if not pitcher_id:
        return None
    player = play.player(pitcher_id)
    starter = play.is_starter(side, player)
    fatigue = (state[side].get("fatigue") or {}).get(str(pitcher_id)) or {}
    pitches = fatigue.get("pitches") or 0
    effort = fatigue.get("effort") or 0
    ceiling = fatigue.get("ceiling") or 0
    share = float(effort) / float(ceiling) if ceiling else 0.0
    check = usage.check_pitcher(player, play.game, starting=starter, reads=play.usage)
    return {
        "side": side,
        "team": teams[side],
        "player": player,
        "role": "Starter" if starter else ROLE_NAMES[play.group_of(side, player)],
        "throws": HANDS.get(player.throws, "?"),
        "today": _pitching_today(box, side, player),
        "pitches": pitches,
        "ceiling": round(float(ceiling)),
        "meter": max(0, min(100, round(share * 100))),
        "tone": "hot" if share > 0.9 else "warm" if share > 0.7 else "ok",
        "ip_left": usage.outs_to_innings(check.remaining.get("game_outs") or 0),
        "odds": [
            {"label": label, "pct": pct, "bar": min(100, pct * 2), "good": key in ODDS_GOOD}
            for key, label, pct in odds
        ],
    }


# The calls


def controls(play, user, need, can_step, teams):
    """The Play button and both sides' calls, each with whether it can be used now and, if not, why."""
    from ulmg import sim_game

    state, fold = play.state, play.fold
    batting, fielding = sim_game.batting_side(state), sim_game.fielding_side(state)
    bases = state["bases"]
    batter = play.player(sim_game.current_batter_id(state))
    steal_ok = bool((bases.get("first") and not bases.get("second")) or (bases.get("second") and not bases.get("third")))
    on_base = any(bases.get(base) for base in sim_game.BASES)
    first_pitch = fold.first_pitch
    blocked = None
    if fold.pause is not None:
        blocked = f"The game is paused. {fold.pause['reason']}"
    elif need is not None:
        blocked = need.reason

    def button(label, key=None, call=None, tab=None, ok=True, live=False):
        return {"label": label, "key": key, "call": call, "tab": tab, "enabled": ok, "live": live and ok}

    offense_mine = fold.holds(user, batting)
    defense_mine = fold.holds(user, fielding)
    sub_ok = first_pitch and fold.pause is None
    offense = [
        button("Bunt", "B", call="bunt", ok=offense_mine and can_step),
        button("Steal", "S", call="steal", ok=offense_mine and can_step and steal_ok, live=steal_ok),
        button("Hit & run", "H", call="hit_and_run", ok=offense_mine and can_step and bool(bases.get("first")), live=bool(bases.get("first"))),
        button("Pinch hit", tab="ph", ok=offense_mine and sub_ok and need is None),
        button("Pinch run", tab="pr", ok=offense_mine and sub_ok and need is None and on_base),
    ]
    pitcher_need = need is not None and need.kind == sim_game.PITCHER_NEED and need.side == fielding
    position_need = need is not None and need.kind == sim_game.POSITION_NEED and need.side == fielding
    defense = [
        button("Intentional walk", "I", call="intentional_walk", ok=defense_mine and can_step),
        button("Pitch around", "P", call=sim_game.PITCH_AROUND, ok=defense_mine and can_step),
        button("New pitcher", tab="pit", ok=defense_mine and fold.pause is None and (first_pitch and need is None or pitcher_need)),
        button("Defensive sub", tab="def", ok=defense_mine and sub_ok and (need is None or position_need)),
    ]

    def reasons(mine, side, specific):
        if not mine:
            return [f"{teams[side].abbreviation} is the computer's side: it makes these calls itself."]
        if blocked:
            return [blocked]
        return specific

    offense_why = []
    if not first_pitch:
        offense_why.append("Pinch hitters and runners can go in after the first pitch; change the lineup below until then.")
    if not steal_ok:
        offense_why.append("Steal needs a runner with the next base open.")
    if not bases.get("first"):
        offense_why.append("Hit & run needs a runner on first.")
    if first_pitch and not on_base:
        offense_why.append("Pinch run needs a runner on base.")
    defense_why = []
    if not first_pitch:
        defense_why.append("Pitching changes and defensive subs open after the first pitch.")

    if can_step:
        play_why = None
    elif blocked:
        play_why = blocked
    else:
        play_why = "You don't hold a seat in this game."
    return {
        "play": {"enabled": can_step, "sub": f"{game_field.last_name(batter)} swings away", "why": play_why},
        "offense": {"team": teams[batting], "mine": offense_mine, "buttons": offense, "why": " ".join(reasons(offense_mine, batting, offense_why))},
        "defense": {"team": teams[fielding], "mine": defense_mine, "buttons": defense, "why": " ".join(reasons(defense_mine, fielding, defense_why))},
    }


def recent_plays(events, plate_appearance):
    """The last plate appearances, newest first, with the half inning each came in."""
    plays = []
    for event in reversed(events):
        if event.kind != plate_appearance or not event.text:
            continue
        before = event.payload.get("before") or {}
        half = "Top" if before.get("half") == "top" else "Bot"
        count, text = game_field.split_log_text(event.text)
        when = f"{half} {before.get('inning', '')}" + (f" · {count}" if count else "")
        plays.append({"when": when, "text": text})
        if len(plays) == RECENT_PLAYS:
            break
    return plays


# The field


def park_corner(team):
    """The park's name and the scores the sim plays there, with its surface, roof and tall walls."""
    venue = home_park.home_venue(team)
    rules = home_park.rules(venue)
    run = _index(venue, "park_factor") or _index(venue, "pf_runs") or 100
    facts = [f"HR {_index(venue, 'pf_hr') or run}", f"2B {_index(venue, 'pf_2b') or run}", rules["surface"]]
    if rules["roof"] != "open":
        facts.append(rules["roof"])
    return {
        "name": venue.name if venue is not None else "Generic park",
        "facts": " · ".join(str(fact) for fact in facts),
        "ground_rules": rules["ground_rules"],
        "rules": rules,
    }


def _index(venue, attr):
    value = getattr(venue, attr, None) if venue is not None else None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def field(play, teams):
    from ulmg import sim_game

    state = play.state
    fielding = sim_game.fielding_side(state)
    corner = park_corner(sim_game.team_for(play.game, sim_game.HOME))
    defense = game_field.fielders(play, state, fielding, corner["rules"]["distances_ft"])
    on_base = game_field.runners(play, state["bases"])
    return {
        "park": corner,
        "drawing": game_field.park_drawing(corner["rules"]),
        "fielders": defense,
        "runners": on_base,
        "text": game_field.describe(teams[fielding], defense, on_base),
    }


# The substitution panel


def reach_chance(play, player=None):
    """
    The engine's chance that this plate appearance reaches base, from /matchup:
    with the current batter, or with `player` batting in his slot on his platoon rates.
    """
    from ulmg import sim_game

    state = play.state
    pitcher = play.player(sim_game.current_pitcher_id(state))
    if player is None:
        _, _, inputs = sim_game.plate_appearance_inputs(play, None)
        sent = sim_game.with_rates(state, inputs["hitter_rates"], inputs["pitcher_rates"])
    else:
        state = copy.deepcopy(state)
        club = state[sim_game.batting_side(state)]
        index = club["batter_index"]
        card = play.card(player)
        club["lineup"][index] = sim_game.batter_card(player, card, club["lineup"][index]["position"])
        rates = cards.plate_appearance_rates(card, play.card(pitcher), player.bats, pitcher.throws)
        sent = sim_game.with_rates(state, rates["hitter_rates"], rates["pitcher_rates"])
    probabilities = engine_client.matchup(sent)["probabilities"]
    return sum(probabilities[key] for key in REACH_KEYS)


def _positions(card, player):
    shown = [position for position, _ in card.defense_display()] if card is not None else []
    return "/".join(shown) or (player.position or "—")


def _pa_left(play, player):
    left = usage.usage_summary(player, play.season, reads=play.usage)["plate_appearances_left"]
    return "unlimited" if left is None else left


def _hitter_rows(play, options, throws):
    rows = []
    for option in options:
        player = option.player
        card = play.card(player)
        rows.append(
            {
                "player": player,
                "legal": option.legal,
                "problem": option.problem,
                "bats": player.bats or "?",
                "positions": _positions(card, player),
                "line": hitter_line(card, throws),
                "spd": getattr(card, "spd", None),
                "speed": tenths(getattr(card, "spd", None)),
                "steals": percent(getattr(card, "steal_success", None)),
                "pa_left": _pa_left(play, player),
                "glove": ", ".join(f"{p} {game_field.rating_label(r)}" for p, r in card.defense_display()) if card is not None else "—",
            }
        )
    return rows


def pinch_hit_tab(play, options, batter, side):
    """Bench hitters against this pitcher, each legal one with his chance to reach base here and the change from the batter."""
    from ulmg import sim_game

    state = play.state
    pitcher_id = sim_game.current_pitcher_id(state)
    pitcher = play.player(pitcher_id) if pitcher_id else None
    throws = pitcher.throws if pitcher else None
    rows = _hitter_rows(play, options, throws)
    current = hitter_line(play.card(batter), throws)
    base = reach_chance(play) if pitcher else None
    for row in rows:
        row["reach"] = None
        if row["legal"] and pitcher is not None:
            chance = reach_chance(play, row["player"])
            row["reach_value"] = chance
            row["reach"] = f"{round(chance * 100)}%"
            delta = round(chance * 100) - round(base * 100)
            row["delta"] = f"+{delta}" if delta > 0 else f"−{abs(delta)}" if delta < 0 else "±0"
            row["up"] = delta > 0
            row["down"] = delta < 0
            row["compare"] = (
                f"{batter.name} {slash_text(current)} → {row['player'].name} {slash_text(row['line'])}; "
                f"chance to reach base {round(base * 100)}% → {round(chance * 100)}%"
            )
    hand = {"R": "right-handers", "L": "left-handers"}.get(throws)
    return {
        "side": side,
        "batter": batter,
        "rows": rows,
        "base_reach": None if base is None else f"{round(base * 100)}%",
        "sub": (
            f"Facing {pitcher.name} ({throws}HP). Lines shown are against {hand}."
            if pitcher is not None and hand
            else "Lines shown are each hitter's overall card."
        ),
    }


def pinch_run_tab(play, options, side):
    from ulmg import sim_game

    state = play.state
    on_base = [
        {"base": base, "player": play.player(state["bases"][base])}
        for base in sim_game.BASES
        if state["bases"].get(base)
    ]
    for runner in on_base:
        runner["speed"] = tenths(getattr(play.card(runner["player"]), "spd", None))
    rows = _hitter_rows(play, options, None)
    rows.sort(key=lambda row: (not row["legal"], -(row["spd"] if row["spd"] is not None else -1)))
    for row in rows:
        if row["legal"] and on_base:
            first = on_base[0]
            row["compare"] = f"{row['player'].name} (speed {row['speed']}, steals {row['steals']}) runs for {first['player'].name} (speed {first['speed']})"
    return {"side": side, "runners": on_base, "rows": rows}


def pitcher_tab(play, options, side):
    """The pen: arm, role, xFIP, K%, BB%, OBP allowed by batter hand, rest, and innings he can still go."""
    from ulmg import sim_game

    stats = usage.card_stats_by_player([option.player for option in options], play.season)
    reads = play.usage.for_game(play.game)
    current_id = sim_game.current_pitcher_id(play.state)
    current = play.player(current_id) if current_id else None
    rows = []
    for option in options:
        player = option.player
        card = play.card(player)
        overall = card.pitcher_line() if card is not None else None
        vs_left = card._pitcher_line_from(card.pitcher_rates_vs_lhh or card.pitcher_rates) if card is not None else None
        vs_right = card._pitcher_line_from(card.pitcher_rates_vs_rhh or card.pitcher_rates) if card is not None else None
        check = usage.check_pitcher(player, play.game, starting=False, reads=play.usage)
        pitch = stats.get(player.id, ({}, {}))[1]
        xfip = pitch.get("xfip")
        outings = sorted(
            (a for a in reads.series_appearances(player, play.game) if a.started or a.batters_faced > 0),
            key=lambda a: a.game.game_number,
        )
        if outings:
            last = outings[-1]
            rest = f"pitched game {last.game.game_number} ({last.pitches} pitches)"
        else:
            rest = "rested"
        role = ROLE_NAMES[play.group_of(side, player)]
        row = {
            "player": player,
            "legal": option.legal,
            "problem": option.problem,
            "throws": player.throws or "?",
            "role": role,
            "xfip": "—" if xfip in (None, "") else f"{float(xfip):.2f}",
            "k": percent(overall and overall["k_pct"]),
            "bb": percent(overall and overall["bb_pct"]),
            "obp_l": three(vs_left and vs_left["obp"]),
            "obp_r": three(vs_right and vs_right["obp"]),
            "rest": rest,
            "ip": usage.outs_to_innings(check.remaining.get("game_outs") or 0) if option.legal else "—",
        }
        if option.legal:
            replaces = f", replacing {current.name}" if current is not None else ""
            row["compare"] = f"{player.name} ({row['throws']}HP, {role.lower()}){replaces}; he can go {row['ip']} innings."
        rows.append(row)
    return {"side": side, "rows": rows}


def defense_tab(play, choices):
    """Positions and defensive replacements: the lineup at its slots with ratings, and the bench with his ratings."""
    defense = choices
    state = play.state
    lineup = state[defense["side"]]["lineup"]
    for row in defense["rows"]:
        rating = (lineup[row["slot"]].get("defense") or {}).get("rating")
        row["rating"] = None if row["position"] == "DH" else game_field.rating_label(game_field.rating_runs(rating))
    defense["bench"] = _hitter_rows(play, defense["options"], None)
    for row in defense["bench"]:
        if row["legal"]:
            row["compare"] = f"{row['player'].name} goes in at the slot you pick. Ratings: {row['glove'] or 'none'}."
    return defense


def panel(play, user, need, choices, pitcher_options, teams):
    """The four tabs of the substitution panel, which one opens by itself for a forced change, and the forms behind them."""
    from ulmg import sim_game

    state, fold = play.state, play.fold
    batting, fielding = sim_game.batting_side(state), sim_game.fielding_side(state)
    tabs = {}
    opened = None
    batter = play.player(sim_game.current_batter_id(state))

    if need is not None and fold.holds(user, need.side) and need.kind == sim_game.BATTER_NEED:
        tabs["ph"] = {
            "action": "replace",
            "title": f"Replace {need.player.name}",
            "confirm": "Put him in",
            **pinch_hit_tab(play, play.options_for(need), need.player, need.side),
        }
        opened = "ph"
    elif "pinch" in choices:
        tabs["ph"] = {
            "action": "pinch_hit",
            "title": f"Pinch hit for {batter.name}",
            "confirm": "Send him up",
            **pinch_hit_tab(play, choices["pinch"]["options"], batter, batting),
        }
        if choices["pinch"]["runners"]:
            tabs["pr"] = {
                "action": "pinch_run",
                "title": "Pinch run",
                "confirm": "Put him on base",
                "sub": "Sorted by speed. Steal success is from each man's card.",
                **pinch_run_tab(play, choices["pinch"]["options"], batting),
            }
    if pitcher_options:
        pitcher_need = need is not None and need.kind == sim_game.PITCHER_NEED
        if pitcher_need or need is None:
            current_id = sim_game.current_pitcher_id(state)
            current = play.player(current_id) if current_id else None
            upcoming = [play.player(entry["id"]) for entry in _next_hitters(state)]
            tabs["pit"] = {
                "action": "pitcher",
                "title": "Bring in a new pitcher",
                "confirm": "Bring him in",
                "sub": "Next three hitters: "
                + ", ".join(f"{p.name} ({p.bats or '?'})" for p in upcoming)
                + (f". {current.name} has thrown {_pitches(state, fielding, current)} pitches." if current else "."),
                **pitcher_tab(play, pitcher_options, fielding),
            }
            if pitcher_need and fold.holds(user, need.side):
                opened = "pit"
                tabs["pit"]["title"] = need.reason
    if "defense" in choices:
        tabs["def"] = {
            "action": "defense",
            "title": "Defensive replacement",
            "confirm": "Put him in",
            "sub": "Ratings are slotted card runs, as the engine plays them. Below zero is below average.",
            **defense_tab(play, choices["defense"]),
        }
        if need is not None and need.kind == sim_game.POSITION_NEED and fold.holds(user, need.side):
            opened = "def"
            tabs["def"]["title"] = need.reason

    shown = []
    for key, label in TABS:
        tab = tabs.get(key)
        if tab is None:
            tab = {"title": label, "missing": _missing(key, play, user, need, teams)}
        tab["key"] = key
        tab["label"] = label
        shown.append(tab)
    return {"tabs": shown, "open": opened}


def _missing(key, play, user, need, teams):
    from ulmg import sim_game

    state, fold = play.state, play.fold
    side = sim_game.batting_side(state) if key in ("ph", "pr") else sim_game.fielding_side(state)
    if not fold.holds(user, side):
        return f"{teams[side].abbreviation} is the computer's side."
    if fold.pause is not None:
        return f"The game is paused. {fold.pause['reason']}"
    if not fold.first_pitch:
        return "Substitutions open after the first pitch. Until then, set the lineup below."
    if need is not None:
        return need.reason
    if key == "pr":
        return "Nobody is on base."
    return "Nothing to choose here now."


def _next_hitters(state):
    from ulmg import sim_game

    club = state[sim_game.batting_side(state)]
    index = club["batter_index"]
    return [club["lineup"][(index + step) % len(club["lineup"])] for step in range(3)]


def _pitches(state, side, pitcher):
    return ((state[side].get("fatigue") or {}).get(str(pitcher.id)) or {}).get("pitches") or 0
