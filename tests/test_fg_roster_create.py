# ABOUTME: Tests for player creation in live_update_status_from_fg_rosters.
# ABOUTME: Ensures missing players are created when FG ID or MLB ID is available.
from unittest.mock import patch

from django.test import TestCase

from ulmg import models
from ulmg.management.commands.live_update_status_from_fg_rosters import Command


class CreatePlayerFromFgRosterTestCase(TestCase):
    """Test create_player_from_fg_roster helper."""

    def setUp(self):
        self.cmd = Command()

    def test_creates_player_with_fg_id_and_mlbam_id(self):
        player_data = {
            'player': 'Test Player',
            'position': 'SS',
            'dbTeam': 'SFG',
        }
        player = self.cmd.create_player_from_fg_roster(
            player_data, fg_id='12345', mlbam_id='664774'
        )
        self.assertIsNotNone(player)
        self.assertEqual(player.name, 'Test Player')
        self.assertEqual(player.level, 'B')
        self.assertEqual(player.fg_id, '12345')
        self.assertEqual(player.mlbam_id, '664774')
        self.assertEqual(player.current_mlb_org, 'SFG')
        self.assertEqual(player.position, 'IF')

    def test_creates_player_with_fg_id_only(self):
        player_data = {'player': 'FG Only Player', 'position': '1B'}
        player = self.cmd.create_player_from_fg_roster(
            player_data, fg_id='99999', mlbam_id=None
        )
        self.assertIsNotNone(player)
        self.assertEqual(player.name, 'FG Only Player')
        self.assertEqual(player.fg_id, '99999')
        self.assertIsNone(player.mlbam_id)

    def test_creates_player_with_mlbam_id_only(self):
        player_data = {'player': 'MLB Only Player', 'position': 'P'}
        player = self.cmd.create_player_from_fg_roster(
            player_data, fg_id=None, mlbam_id='123456'
        )
        self.assertIsNotNone(player)
        self.assertEqual(player.name, 'MLB Only Player')
        self.assertIsNone(player.fg_id)
        self.assertEqual(player.mlbam_id, '123456')
        self.assertEqual(player.position, 'P')

    def test_returns_none_when_no_ids(self):
        player_data = {'player': 'No ID Player', 'position': 'OF'}
        player = self.cmd.create_player_from_fg_roster(
            player_data, fg_id=None, mlbam_id=None
        )
        self.assertIsNone(player)

    def test_returns_none_when_empty_name(self):
        player_data = {'player': '', 'position': '1B'}
        player = self.cmd.create_player_from_fg_roster(
            player_data, fg_id='12345', mlbam_id='664774'
        )
        self.assertIsNone(player)

    def test_uses_position1_when_position_missing(self):
        player_data = {'player': 'Multi Pos', 'position1': 'SS'}
        player = self.cmd.create_player_from_fg_roster(
            player_data, fg_id='11111', mlbam_id=None
        )
        self.assertIsNotNone(player)
        self.assertEqual(player.position, 'IF')


class LiveUpdateStatusFromFgRostersCreateTestCase(TestCase):
    """Test full handle() flow creates players when missing."""

    @patch('ulmg.management.commands.live_update_status_from_fg_rosters.settings.ROSTER_TEAM_IDS', [(30, 'SFG', 'San Francisco Giants')])
    @patch('ulmg.management.commands.live_update_status_from_fg_rosters.utils.s3_manager')
    def test_creates_missing_player_and_updates_status(self, mock_s3):

        roster = [
            {
                'player': 'New Roster Player',
                'position': '2B',
                'oPlayerId': '77777',
                'mlbamid': 888888,
                'dbTeam': 'SFG',
                'role': '1',
                'mlevel': 'MLB',
                'type': 'mlb-sl',
                'roster40': 'Y',
            }
        ]
        mock_s3.get_file_content.return_value = roster

        cmd = Command()
        cmd.handle()

        self.assertEqual(models.Player.objects.count(), 1)
        p = models.Player.objects.get()
        self.assertEqual(p.name, 'New Roster Player')
        self.assertEqual(p.fg_id, '77777')
        self.assertEqual(p.mlbam_id, '888888')

        pss = models.PlayerStatSeason.objects.get(player=p)
        self.assertEqual(pss.roster_status, 'MLB')
        self.assertEqual(pss.classification, '1-mlb')
        self.assertEqual(pss.mlb_org, 'SFG')
