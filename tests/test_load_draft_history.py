# ABOUTME: Tests the one-time load of the 2012-2018 draft history file.
# ABOUTME: Picks land on the current club, and a player is linked only when the name matches one person.

import csv
from io import StringIO
from pathlib import Path

from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ulmg import draft_history, models


ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "ulmg" / "draft-history.csv"

FIELDS = [
    "year",
    "draft_season",
    "draft_type",
    "round",
    "pick_in_round",
    "player_name",
    "position",
    "pro_amateur",
    "drafting_team",
    "original_pick_owner",
    "via_chain",
    "mlb_org_or_school",
    "notes",
    "source_url",
    "27_club_abbrev",
]


def write_history(path, rows):
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row(**overrides):
    base = {
        "year": "2012",
        "draft_season": "offseason",
        "draft_type": "AA",
        "round": "1",
        "pick_in_round": "1",
        "player_name": "Salvador Perez",
        "position": "C",
        "pro_amateur": "pro",
        "drafting_team": "Anaheim",
        "original_pick_owner": "Heartland via Peninsula",
        "via_chain": "Heartland via Peninsula",
        "mlb_org_or_school": "Kansas City",
        "notes": "",
        "source_url": "https://ulmg.wordpress.com/2012/03/18/2012-draft-results/",
        "27_club_abbrev": "ABQ",
    }
    base.update(overrides)
    return base


class DraftHistoryFileTest(TestCase):
    def test_shipped_file_uses_the_crosswalk_for_every_pick(self):
        with HISTORY.open(newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1520)
        self.assertIn("27_club_abbrev", rows[0])
        names = set()
        for record in rows:
            names.add(record["drafting_team"])
            self.assertEqual(
                record["27_club_abbrev"],
                draft_history.CLUB_ABBREV[record["drafting_team"]],
            )
        self.assertEqual(names, set(draft_history.CLUB_ABBREV))
        self.assertEqual(draft_history.HISTORY_PATH, HISTORY)


class LoadDraftHistoryTest(TestCase):
    def setUp(self):
        self.directory = self._tmp()
        self.path = self.directory / "history.csv"
        self.albuquerque = models.Team.objects.create(
            abbreviation="ABQ", city="Albuquerque", nickname="Redbirds"
        )
        self.hub = models.Team.objects.create(
            abbreviation="HCH", city="Hub City", nickname="Hawks"
        )
        self.peninsula = models.Team.objects.create(
            abbreviation="PEN", city="Peninsula", nickname="Pressmen"
        )
        self.cincinnati = models.Team.objects.create(
            abbreviation="CIN", city="Cincinnati", nickname="Reds"
        )

    def _tmp(self):
        import tempfile

        wrapper = tempfile.TemporaryDirectory()
        self.addCleanup(wrapper.cleanup)
        return Path(wrapper.name)

    def test_pick_uses_the_abbrev_column_and_the_original_owner(self):
        write_history(self.path, [row()])

        result = draft_history.load_history(self.path)

        pick = models.DraftPick.objects.get()
        self.assertEqual(result["created"], 1)
        self.assertEqual(pick.team, self.albuquerque)
        self.assertEqual(pick.original_team, self.hub)
        self.assertEqual(pick.team_name, "Anaheim")
        self.assertEqual(pick.year, "2012")
        self.assertEqual(pick.season, "offseason")
        self.assertEqual(pick.draft_type, "aa")
        self.assertEqual(pick.draft_round, 1)
        self.assertEqual(pick.pick_number, 1)
        self.assertEqual(pick.player_name, "Salvador Perez")
        self.assertIsNone(pick.player)
        self.assertIn("Heartland via Peninsula", pick.pick_notes)
        self.assertIn("2012-draft-results", pick.pick_notes)

    def test_unique_player_is_linked_and_stays_on_his_current_club(self):
        player = models.Player.objects.create(name="Salvador Perez", team=self.cincinnati)
        write_history(self.path, [row()])

        result = draft_history.load_history(self.path)

        pick = models.DraftPick.objects.get()
        player.refresh_from_db()
        self.assertEqual(result["linked"], 1)
        self.assertEqual(pick.player, player)
        self.assertEqual(pick.player_name, "Salvador Perez")
        self.assertEqual(player.team, self.cincinnati)
        self.assertIn("Salvador Perez", pick.slug)

    def test_strat_name_matches_when_the_roster_name_does_not(self):
        player = models.Player.objects.create(
            name="Salvador Perez Diaz", strat_name="Salvador Perez", team=self.cincinnati
        )
        write_history(self.path, [row()])

        draft_history.load_history(self.path)

        pick = models.DraftPick.objects.get()
        player.refresh_from_db()
        self.assertEqual(pick.player, player)
        self.assertEqual(player.team, self.cincinnati)

    def test_ambiguous_name_keeps_the_raw_player_name(self):
        models.Player.objects.create(name="Salvador Perez", team=self.cincinnati)
        models.Player.objects.create(name="Salvador Perez", team=self.hub)
        write_history(self.path, [row()])

        result = draft_history.load_history(self.path)

        pick = models.DraftPick.objects.get()
        self.assertEqual(result["unlinked"], 1)
        self.assertIsNone(pick.player)
        self.assertEqual(pick.player_name, "Salvador Perez")

    def test_compensation_picks_follow_the_numbered_picks(self):
        write_history(
            self.path,
            [
                row(pick_in_round="1", player_name="Vance Worley"),
                row(pick_in_round="comp", player_name="Ivan Nova", notes=""),
                row(pick_in_round="comp", player_name="Alejandro de Aza", notes="Compensation pick"),
            ],
        )

        draft_history.load_history(self.path)

        numbers = {
            pick.player_name: pick.pick_number
            for pick in models.DraftPick.objects.all()
        }
        self.assertEqual(numbers, {"Vance Worley": 1, "Ivan Nova": 2, "Alejandro de Aza": 3})
        nova = models.DraftPick.objects.get(player_name="Ivan Nova")
        deaza = models.DraftPick.objects.get(player_name="Alejandro de Aza")
        self.assertIn("Compensation pick", nova.pick_notes)
        self.assertEqual(deaza.pick_notes.count("Compensation pick"), 1)

    def test_midseason_bonus_draft_is_the_aa_draft(self):
        write_history(
            self.path,
            [
                row(
                    draft_season="midseason",
                    draft_type="Bonus B",
                    round="",
                    pick_in_round="4",
                    player_name="Andrew Heaney",
                    drafting_team="Cincinnati",
                    original_pick_owner="Cincinnati",
                    via_chain="",
                    **{"27_club_abbrev": "CIN"},
                ),
                row(
                    year="2018",
                    draft_type="Competitive Balance",
                    round="",
                    pick_in_round="1",
                    player_name="Greg Holland",
                    drafting_team="Heartland",
                    original_pick_owner="Heartland",
                    via_chain="",
                    **{"27_club_abbrev": "HCH"},
                ),
            ],
        )

        draft_history.load_history(self.path)

        bonus = models.DraftPick.objects.get(player_name="Andrew Heaney")
        balance = models.DraftPick.objects.get(player_name="Greg Holland")
        self.assertEqual(bonus.draft_type, "aa")
        self.assertEqual(bonus.draft_round, 1)
        self.assertEqual(bonus.slug, "CIN AA1")
        self.assertEqual(bonus.team, self.cincinnati)
        self.assertEqual(bonus.original_team, self.cincinnati)
        self.assertEqual(balance.draft_type, "balance")
        self.assertEqual(balance.draft_round, 1)
        self.assertEqual(balance.team, self.hub)

        user = User.objects.create_user("manager", password="secret")
        self.client.force_login(user)
        board = self.client.get("/draft/2012/midseason/aa/")
        self.assertContains(board, "Andrew Heaney")
        index = self.client.get("/draft/")
        self.assertContains(index, 'href="/draft/2012/midseason/aa/"')
        self.assertNotContains(index, "/draft/2012/midseason/bonus/")

    def test_stored_midseason_bonus_pick_becomes_an_aa_pick(self):
        import importlib

        migration = importlib.import_module("ulmg.migrations.0117_midseason_bonus_is_aa")

        pick = models.DraftPick.objects.create(
            year="2014",
            season="midseason",
            draft_type="bonus",
            draft_round=1,
            pick_number=4,
            team=self.cincinnati,
            player_name="Andrew Heaney",
        )
        kept = models.DraftPick.objects.create(
            year="2014",
            season="offseason",
            draft_type="aa",
            draft_round=1,
            pick_number=1,
            team=self.cincinnati,
            player_name="Salvador Perez",
        )
        models.DraftPick.objects.filter(pk=pick.pk).update(slug="CIN BB1 (Andrew Heaney)")
        kept_slug = kept.slug

        migration.bonus_picks_are_aa(apps, None)

        pick.refresh_from_db()
        kept.refresh_from_db()
        self.assertEqual(pick.draft_type, "aa")
        self.assertEqual(pick.slug, "CIN AA1 (Andrew Heaney)")
        self.assertEqual(kept.draft_type, "aa")
        self.assertEqual(kept.slug, kept_slug)

    def test_second_run_leaves_an_existing_draft_alone(self):
        write_history(self.path, [row()])
        draft_history.load_history(self.path)
        models.DraftPick.objects.update(player_name="Already there")

        result = draft_history.load_history(self.path)

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(models.DraftPick.objects.get().player_name, "Already there")

    def test_second_run_adds_only_the_missing_pick(self):
        write_history(
            self.path,
            [
                row(pick_in_round="1", player_name="Vance Worley"),
                row(pick_in_round="2", player_name="Greg Holland"),
            ],
        )
        draft_history.load_history(self.path)
        models.DraftPick.objects.filter(player_name="Greg Holland").delete()
        models.DraftPick.objects.filter(player_name="Vance Worley").update(player_name="Kept")

        result = draft_history.load_history(self.path)

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(models.DraftPick.objects.get(pick_number=1).player_name, "Kept")
        self.assertEqual(models.DraftPick.objects.get(pick_number=2).player_name, "Greg Holland")

    def test_running_twice_does_not_move_a_linked_player(self):
        player = models.Player.objects.create(name="Salvador Perez", team=self.cincinnati)
        write_history(self.path, [row()])
        draft_history.load_history(self.path)

        result = draft_history.load_history(self.path)

        player.refresh_from_db()
        self.assertEqual(result["created"], 0)
        self.assertEqual(models.DraftPick.objects.count(), 1)
        self.assertEqual(player.team, self.cincinnati)

    def test_replace_reloads_an_existing_draft(self):
        write_history(self.path, [row()])
        draft_history.load_history(self.path)
        models.DraftPick.objects.update(player_name="Already there")

        result = draft_history.load_history(self.path, replace=True)

        self.assertEqual(result["created"], 1)
        self.assertEqual(models.DraftPick.objects.count(), 1)
        self.assertEqual(models.DraftPick.objects.get().player_name, "Salvador Perez")

    def test_dry_run_writes_nothing(self):
        write_history(self.path, [row()])

        result = draft_history.load_history(self.path, dry_run=True)

        self.assertEqual(result["created"], 1)
        self.assertEqual(models.DraftPick.objects.count(), 0)

    def test_missing_club_is_an_error(self):
        write_history(self.path, [row(**{"27_club_abbrev": "NOPE"})])

        with self.assertRaises(ValueError):
            draft_history.load_history(self.path)
        self.assertEqual(models.DraftPick.objects.count(), 0)

    def test_command_reads_the_file(self):
        write_history(self.path, [row(player_name="Nobody Real")])
        output = StringIO()

        call_command("load_draft_history", "--file", str(self.path), stdout=output)

        self.assertEqual(models.DraftPick.objects.count(), 1)
        self.assertIn("Created 1 pick", output.getvalue())

    def test_command_rejects_a_missing_file(self):
        with self.assertRaises(CommandError):
            call_command("load_draft_history", "--file", str(self.directory / "missing.csv"))


class PostInstallDraftHistoryTest(TestCase):
    def test_deploy_does_not_load_draft_history(self):
        with patch("ulmg.management.commands.post_install.call_command") as mocked:
            from ulmg.management.commands.post_install import Command

            Command().handle()

        commands = [call.args[0] for call in mocked.call_args_list]
        self.assertIn("migrate", commands)
        self.assertNotIn("load_draft_history", commands)
