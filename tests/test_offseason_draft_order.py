# ABOUTME: Locks the 2027 offseason draft order to the final 2026 standings.
# ABOUTME: Open and AA share one order. Tied teams are adjacent and swap on even rounds.

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPEN_PATH = ROOT / "data" / "ulmg" / "2027-offseason-open-order.txt"
AA_PATH = ROOT / "data" / "ulmg" / "2027-offseason-aa-order.txt"

# Inverse of the final 2026 standings (worst picks first). All 16 teams
# played 162 games, so wins are a complete ranking except for two exact ties:
# Louisville and Pittsburgh at 90-72, Peninsula and Windy City at 97-65.
# The constitution coin-flips who leads round 1. With no flip on record, the
# alphabetically later team leads odd rounds. Both drafts use that same order,
# matching the identical Open and AA files from 2023 and 2024.
ORDER = [
    "CHI",
    "ADK",
    "DET",
    "CAR",
    "KCB",
    "AKS",
    "NYH",
    "ABQ",
    "CLE",
    "CIN",
    "PIT|+",
    "LOU|-",
    "LNG",
    "WCH|+",
    "PEN|-",
    "ATL",
]


def _lines(path):
    return [line for line in path.read_text().splitlines() if line.strip()]


def _team(entry):
    return entry.split("|", 1)[0]


def _pick_number(entry, index, draft_round):
    """Same even-round shift as draft_generate_order."""
    pick_num = index + 1
    if "|" not in entry or draft_round % 2 != 0:
        return _team(entry), pick_num
    team, sign = entry.split("|", 1)
    if sign == "+":
        pick_num += 1
    elif sign == "-":
        pick_num -= 1
    return team, pick_num


class OffseasonDraftOrderTest(unittest.TestCase):
    def test_open_and_aa_share_the_worst_to_first_order(self):
        self.assertEqual(_lines(OPEN_PATH), ORDER)
        self.assertEqual(_lines(AA_PATH), ORDER)
        self.assertEqual(_lines(OPEN_PATH), _lines(AA_PATH))

    def test_tied_pairs_swap_on_even_rounds_and_only_with_each_other(self):
        for path in (OPEN_PATH, AA_PATH):
            entries = _lines(path)
            self.assertEqual(len(entries), 16)
            self.assertEqual(len({_team(entry) for entry in entries}), 16)
            for draft_round in range(1, 6):
                slots = {}
                for index, entry in enumerate(entries):
                    team, pick_num = _pick_number(entry, index, draft_round)
                    self.assertNotIn(pick_num, slots)
                    slots[pick_num] = team
                self.assertEqual(set(slots), set(range(1, 17)))

            for index, entry in enumerate(entries):
                if "|" not in entry:
                    continue
                partner = entries[index + 1] if entry.endswith("|+") else entries[index - 1]
                self.assertIn("|", partner)
                odd_team, odd_slot = _pick_number(entry, index, 1)
                even_team, even_slot = _pick_number(entry, index, 2)
                self.assertEqual(odd_team, even_team)
                self.assertEqual(abs(odd_slot - even_slot), 1)
                partner_index = index + 1 if entry.endswith("|+") else index - 1
                _, partner_even = _pick_number(partner, partner_index, 2)
                self.assertEqual(partner_even, odd_slot)
                self.assertEqual(_pick_number(partner, partner_index, 1)[1], even_slot)
