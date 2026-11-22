# ABOUTME: The Strat-style matchup card: the engine's outcome table laid out as 10 columns of 10 rows, with a d20 split where two outcomes share a cell.
# ABOUTME: The dice are the engine's own roll read off that card, and chances the ballpark adds are marked with a diamond.

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
KEYS = tuple(key for key, _, _ in OUTCOMES)
LABELS = {key: (label, short) for key, label, short in OUTCOMES}
GOOD = {"bb", "hbp", "single", "double", "triple", "hr"}

COLUMNS = 10
ROWS = 10
SPLIT = 20
SLOTS = COLUMNS * ROWS * SPLIT

# The park factors the engine scales, with the run factor standing in for any it has no score for.
PARK_EVENTS = (("single", "single_factor"), ("double", "double_factor"), ("triple", "triple_factor"), ("hr", "hr_factor"))


def read(probabilities, roll):
    """The outcome a roll in [0, 1) reads on the table, summed in the engine's order (read_outcome in engine/src/sim.rs)."""
    cursor = 0.0
    for key in KEYS:
        cursor += probabilities[key]
        if roll < cursor:
            return key
    return "bip_out"


def slot_of(roll):
    """Which of the card's 2,000 chances a roll lands on."""
    return min(SLOTS - 1, max(0, int(roll * SLOTS)))


def boundaries(probabilities, roll=None):
    """
    Where each outcome's chances end on the card: the table's running total,
    rounded to the nearest chance, so every outcome is within a chance of its
    exact share. With a roll, the one boundary that splits the roll's chance
    moves to the side the engine read, so the card says what the roll drew.
    """
    total = sum(max(0.0, float(probabilities.get(key) or 0.0)) for key in KEYS)
    if total <= 0:
        raise ValueError("The matchup has no probabilities.")
    ends, cursor = [], 0.0
    for key in KEYS:
        cursor += max(0.0, float(probabilities.get(key) or 0.0))
        ends.append(round(cursor / total * SLOTS))
    ends[-1] = SLOTS
    if roll is not None:
        drawn = KEYS.index(read(probabilities, roll))
        slot = slot_of(roll)
        start = ends[drawn - 1] if drawn else 0
        if slot < start:
            for i in range(drawn):
                ends[i] = min(ends[i], slot)
        elif slot >= ends[drawn]:
            for i in range(drawn, len(KEYS)):
                ends[i] = max(ends[i], slot + 1)
    return ends


def counts_from(ends):
    starts = [0] + ends[:-1]
    return {key: end - start for key, start, end in zip(KEYS, starts, ends)}


def dice_for(slot):
    """The three dice that read one chance: the column (d10), the row (d10) and the split (d20)."""
    cell, split = divmod(slot, SPLIT)
    column, row = divmod(cell, ROWS)
    return {"column": column + 1, "row": row + 1, "d20": split + 1}


def park_factors(park):
    """Each hit's park factor as the engine applies it: its own score, or the run factor."""
    run = float(park.get("run_factor") or 1.0)
    return {key: float(park[attr]) if park.get(attr) is not None else run for key, attr in PARK_EVENTS}


def card(probabilities, roll=None, neutral=None):
    """
    The card for one matchup. With the engine's roll, the dice that read it
    and the cell they land on. With the neutral-park table, the chances the
    park adds to an outcome are marked, at the end of its run. Cells run down
    each column: column 1 is rolls 1 to 10, column 10 is rolls 91 to 100.
    """
    ends = boundaries(probabilities, roll)
    counts = counts_from(ends)
    # The park's share is measured without the roll's nudge, so a nudge never reads as the park.
    unrolled = counts_from(boundaries(probabilities))
    park_counts = counts_from(boundaries(neutral)) if neutral else unrolled
    layout, park = [], []
    for key in KEYS:
        added = min(counts[key], max(0, unrolled[key] - park_counts[key]))
        layout.extend([key] * counts[key])
        park.extend([False] * (counts[key] - added) + [True] * added)
    slot = slot_of(roll) if roll is not None else None
    dice = dice_for(slot) if slot is not None else None
    columns = []
    for column in range(COLUMNS):
        cells = []
        for row in range(ROWS):
            first = (column * ROWS + row) * SPLIT
            parts = []
            for i in range(SPLIT):
                key, marked = layout[first + i], park[first + i]
                if parts and parts[-1]["key"] == key and parts[-1]["park"] == marked:
                    parts[-1]["hi"] = i + 1
                    continue
                label, short = LABELS[key]
                parts.append({"key": key, "label": label, "short": short, "good": key in GOOD, "park": marked, "lo": i + 1, "hi": i + 1})
            hit = dice is not None and dice["column"] == column + 1 and dice["row"] == row + 1
            for part in parts:
                part["hit"] = hit and part["lo"] <= dice["d20"] <= part["hi"]
            cells.append({"row": row + 1, "parts": parts, "split": len(parts) > 1, "hit": hit})
        columns.append({"number": column + 1, "cells": cells})
    odds = [
        {
            "key": key,
            "label": label,
            "short": short,
            "good": key in GOOD,
            "chances": counts[key],
            "pct": counts[key] / SLOTS * 100,
            "park": unrolled[key] - park_counts[key],
            "park_pct": (unrolled[key] - park_counts[key]) / SLOTS * 100,
        }
        for key, label, short in OUTCOMES
    ]
    result = None
    if dice is not None:
        hit_cell = columns[dice["column"] - 1]["cells"][dice["row"] - 1]
        dice["split"] = hit_cell["split"]
        dice["park"] = park[slot]
        result = LABELS[layout[slot]][0]
    rows = [{"number": row + 1, "cells": [column["cells"][row] for column in columns]} for row in range(ROWS)]
    return {"columns": columns, "rows": rows, "odds": odds, "dice": dice, "result": result}


def for_plate_appearance(result):
    """The card a plate appearance was read from, from the engine's reported dice, or None when it read none."""
    dice = (result or {}).get("dice")
    if not dice:
        return None
    read_card = card(dice["probabilities"], dice["roll"], dice.get("neutral_park"))
    park = dice.get("park") or {}
    read_card["hit_and_run"] = result.get("call_note") in ("hit_and_run_succeeded", "hit_and_run_failed", "hit_and_run")
    read_card["park"] = {
        "factors": [
            {"short": LABELS[key][1], "factor": factor, "tone": "up" if factor > 1.0 else "down" if factor < 1.0 else ""}
            for key, factor in park_factors(park).items()
        ],
        "moved": [line for line in read_card["odds"] if line["park"]],
    }
    return read_card
