# ABOUTME: Tests for player creation in live_update_status_from_mlb_depthcharts.
# ABOUTME: Ensures missing players are created when MLB ID is available (no FG ID).
import json
from unittest.mock import patch

from django.test import TestCase

from ulmg import models
from ulmg.management.commands.live_update_status_from_mlb_depthcharts import Command


class CreatePlayerFromMlbDepthchartsTestCase(TestCase):
    """Test create_player_from_mlb_depthcharts helper."""

    def setUp(self):
        self.cmd = Command()

    def test_creates_player_with_mlbam_id_and_name(self):
        player_data = {
            'mlbam_id': '664774',
            'name': 'Test Player',
            'position': 'SS',
            'mlb_org': 'SFG',
        }
        player = self.cmd.create_player_from_mlb_depthcharts(player_data)
        self.assertIsNotNone(player)
        self.assertEqual(player.name, 'Test Player')
        self.assertEqual(player.level, 'B')
        self.assertEqual(player.mlbam_id, '664774')
        self.assertIsNone(player.fg_id)
        self.assertEqual(player.current_mlb_org, 'SFG')
        self.assertEqual(player.position, 'IF')

    def test_uses_player_key_when_name_missing(self):
        player_data = {'mlbam_id': '123456', 'player': 'Alt Name Key', 'position': 'P'}
        player = self.cmd.create_player_from_mlb_depthcharts(player_data)
        self.assertIsNotNone(player)
        self.assertEqual(player.name, 'Alt Name Key')
        self.assertEqual(player.mlbam_id, '123456')

    def test_uses_mlbamid_key(self):
        player_data = {'mlbamid': '999999', 'name': 'Camel Case ID'}
        player = self.cmd.create_player_from_mlb_depthcharts(player_data)
        self.assertIsNotNone(player)
        self.assertEqual(player.mlbam_id, '999999')

    def test_returns_none_when_no_mlbam_id(self):
        player_data = {'name': 'No ID Player', 'position': 'OF'}
        player = self.cmd.create_player_from_mlb_depthcharts(player_data)
        self.assertIsNone(player)

    def test_returns_none_when_empty_name(self):
        player_data = {'mlbam_id': '664774', 'name': '', 'player': ''}
        player = self.cmd.create_player_from_mlb_depthcharts(player_data)
        self.assertIsNone(player)


class LiveUpdateStatusFromMlbDepthchartsCreateTestCase(TestCase):
    """Test full handle() flow creates players when missing."""

    @patch('builtins.open')
    def test_creates_missing_player_and_updates_status(self, mock_open_func):
        players = [
            {
                'mlbam_id': 888888,
                'name': 'New MLB Player',
                'position': '3B',
                'mlb_org': 'BOS',
                'roster_status': 'MLB',
            }
        ]
        mock_open_func.return_value.__enter__.return_value.read.return_value = json.dumps(players)

        cmd = Command()
        cmd.handle()

        self.assertEqual(models.Player.objects.count(), 1)
        p = models.Player.objects.get()
        self.assertEqual(p.name, 'New MLB Player')
        self.assertEqual(p.mlbam_id, '888888')
        self.assertIsNone(p.fg_id)
        self.assertEqual(p.current_mlb_org, 'BOS')

        pss = models.PlayerStatSeason.objects.filter(player=p).first()
        self.assertIsNotNone(pss)
        self.assertEqual(pss.roster_status, 'MLB')
        self.assertEqual(pss.mlb_org, 'BOS')
