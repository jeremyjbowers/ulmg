# ABOUTME: The Strat-style matchup card: the engine's outcome probabilities laid out as 10 columns of 10 rows, with a d20 split where two outcomes share a cell.
# ABOUTME: The engine draws the result; the card shows the dice that land on it, picked evenly from the cells that read that result, so the rolls are as fair as rolling first.

import random

# The engine reads its outcome table in this order. Strat prints hits and walks in capitals and outs in lower case.
OUTCOMES = (
    ("k", "strikeout", "K"),
    ("bb", "WALK", "BB"),
    ("hbp", "HBP", "HBP"),
    ("single", "SINGLE", "1B"),
    ("double", "DOUBLE", "2B"),
    ("triple", "TRIPLE", "3B"),
    ("hr", "HOMERUN", "HR"),
    ("bip_out", "out", "out"),
)
LABELS = {key: (label, short) for key, label, short in OUTCOMES}
GOOD = {"bb", "hbp", "single", "double", "triple", "hr"}

COLUMNS = 10
ROWS = 10
SPLIT = 20
SLOTS = COLUMNS * ROWS * SPLIT

# What the engine reports, folded onto the card's eight outcomes. Anything missing read no card:
# a bunt, an intentional walk, or a runner caught stealing to end the inning.
CARD_KEYS = {
    "strikeout": "k",
    "walk": "bb",
    "hit_by_pitch": "hbp",
    "single": "single",
    "double": "double",
    "triple": "triple",
    "home_run": "hr",
    "bip_out": "bip_out",
    "ground_out": "bip_out",
    "fly_out": "bip_out",
    "line_out": "bip_out",
    "grounded_into_double_play": "bip_out",
    "sacrifice_fly": "bip_out",
    "reached_on_error": "bip_out",
}

# The engine's hit-and-run keeps this share of the strikeouts (HIT_AND_RUN_K_KEEP in engine/src/sim.rs).
HIT_AND_RUN_K_KEEP = 0.5
HIT_AND_RUN_NOTES = ("hit_and_run_succeeded", "hit_and_run_failed", "hit_and_run")

# Mixed into the plate appearance's seed so the card's pick is not the engine's stream.
PICK_SALT = 0x5747_2D4F_2D4D_4154


def with_hit_and_run(probabilities):
    """The table after a hit-and-run, the same arithmetic as the engine's apply_hit_and_run."""
    p = dict(probabilities)
    removed = p["k"] * (1.0 - HIT_AND_RUN_K_KEEP)
    p["k"] -= removed
    hits = p["single"] + p["double"] + p["triple"]
    contact = hits + p["bip_out"]
    if contact <= 0.0:
        p["single"] += removed
        return p
    added_hits = removed * (hits / contact)
    p["bip_out"] += removed - added_hits
    if hits <= 0.0:
        p["single"] += added_hits
        return p
    p["single"] += added_hits * (p["single"] / hits)
    p["double"] += added_hits * (p["double"] / hits)
    p["triple"] += added_hits * (p["triple"] / hits)
    return p


def slot_counts(probabilities):
    """
    How many of the card's 2,000 chances (100 cells times a d20) each outcome
    gets: largest remainders, so they add to 2,000, and any outcome the engine
    can draw gets at least one, so every result has a place on the card.
    """
    keys = [key for key, _, _ in OUTCOMES]
    raw = [max(0.0, float(probabilities.get(key) or 0.0)) for key in keys]
    total = sum(raw)
    if total <= 0:
        raise ValueError("The matchup has no probabilities.")
    exact = [value / total * SLOTS for value in raw]
    counts = [int(value) for value in exact]
    by_remainder = sorted(range(len(keys)), key=lambda i: (exact[i] - counts[i], exact[i]), reverse=True)
    for i in by_remainder[: SLOTS - sum(counts)]:
        counts[i] += 1
    for i, value in enumerate(raw):
        if value > 0 and counts[i] == 0:
            counts[i] = 1
            counts[max(range(len(keys)), key=lambda j: counts[j])] -= 1
    return dict(zip(keys, counts))


def dice_for(slot):
    """The three dice that read one chance: the column (d10), the row (d10) and the split (d20)."""
    cell, split = divmod(slot, SPLIT)
    column, row = divmod(cell, ROWS)
    return {"column": column + 1, "row": row + 1, "d20": split + 1}


def pick_slot(counts, key, seed):
    """One of the chances that read this outcome, evenly, from the plate appearance's seed."""
    start = 0
    for outcome, _, _ in OUTCOMES:
        if outcome == key:
            break
        start += counts[outcome]
    if counts.get(key, 0) <= 0:
        return None
    return start + random.Random(int(seed) ^ PICK_SALT).randrange(counts[key])


def card(probabilities, key=None, seed=None, hit_and_run=False):
    """
    The card for one matchup. With a result key and a seed, the dice that
    read it and the cell they land on. Cells run down each column: column 1
    is rolls 1 to 10, column 10 is rolls 91 to 100.
    """
    counts = slot_counts(probabilities)
    layout = []
    for outcome, _, _ in OUTCOMES:
        layout.extend([outcome] * counts[outcome])
    slot = pick_slot(counts, key, seed) if key is not None and seed is not None else None
    dice = dice_for(slot) if slot is not None else None
    columns = []
    for column in range(COLUMNS):
        cells = []
        for row in range(ROWS):
            first = (column * ROWS + row) * SPLIT
            chances = layout[first : first + SPLIT]
            parts = []
            for i, outcome in enumerate(chances):
                if parts and parts[-1]["key"] == outcome:
                    parts[-1]["hi"] = i + 1
                    continue
                label, short = LABELS[outcome]
                parts.append({"key": outcome, "label": label, "short": short, "good": outcome in GOOD, "lo": i + 1, "hi": i + 1})
            hit = dice is not None and dice["column"] == column + 1 and dice["row"] == row + 1
            for part in parts:
                part["hit"] = hit and part["lo"] <= dice["d20"] <= part["hi"]
            cells.append({"row": row + 1, "parts": parts, "split": len(parts) > 1, "hit": hit})
        columns.append({"number": column + 1, "cells": cells})
    odds = [
        {
            "key": outcome,
            "label": label,
            "short": short,
            "good": outcome in GOOD,
            "chances": counts[outcome],
            "pct": counts[outcome] / SLOTS * 100,
        }
        for outcome, label, short in OUTCOMES
    ]
    result = None
    if dice is not None:
        hit_cell = columns[dice["column"] - 1]["cells"][dice["row"] - 1]
        dice["split"] = hit_cell["split"]
        result = LABELS[key][0]
    rows = [{"number": row + 1, "cells": [column["cells"][row] for column in columns]} for row in range(ROWS)]
    return {"columns": columns, "rows": rows, "odds": odds, "dice": dice, "result": result, "hit_and_run": hit_and_run}


def for_plate_appearance(payload, seed):
    """The card a logged plate appearance was read from, or None when it read none."""
    probabilities = payload.get("card")
    result = payload.get("result") or {}
    key = CARD_KEYS.get(result.get("outcome"))
    if not probabilities or key is None or seed is None or not result.get("batter_completed", True):
        return None
    hit_and_run = result.get("call_note") in HIT_AND_RUN_NOTES
    if hit_and_run:
        probabilities = with_hit_and_run(probabilities)
    return card(probabilities, key, seed, hit_and_run=hit_and_run)
