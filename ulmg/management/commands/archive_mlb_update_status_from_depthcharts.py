# ABOUTME: ARCHIVED - Original live_update_status_from_mlb_depthcharts. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
# ABOUTME: Reads all_mlb_rosters.json (never created by any command) to update roster status.
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.db.models import Count
from datetime import datetime

import ujson as json

from ulmg import models, utils


class Command(BaseCommand):
    def create_player_from_mlb_depthcharts(self, player_data):
        mlbam_id = str(player_data.get('mlbam_id') or player_data.get('mlbamid') or '').strip()
        if not mlbam_id:
            return None
        name = (player_data.get('name') or player_data.get('player') or '').strip()
        if not name:
            return None
        position_raw = player_data.get('position', '')
        position = utils.normalize_pos(position_raw) if position_raw else 'DH'
        with transaction.atomic():
            player = models.Player(
                name=name,
                position=position,
                level=models.Player.B_LEVEL,
                mlbam_id=mlbam_id,
                current_mlb_org=player_data.get('mlb_org') or None,
            )
            player.save()
        return player

    def _get_current_season(self):
        return datetime.now().year

    def _update_player_stat_season(self, player, season, **kwargs):
        player_stat_season = models.PlayerStatSeason.objects.filter(
            player=player
        ).order_by('-season', '-classification').first()
        if not player_stat_season:
            player_stat_season = models.PlayerStatSeason.objects.create(
                player=player,
                season=season,
                classification='2-minors',
                owned=player.is_owned,
                carded=False
            )
        for field, value in kwargs.items():
            if hasattr(player_stat_season, field):
                setattr(player_stat_season, field, value)
        player_stat_season.save()
        return player_stat_season

    def handle(self, *args, **options):
        current_season = self._get_current_season()
        players_created = 0
        models.PlayerStatSeason.objects.filter(
            season=current_season
        ).update(roster_status=None, mlb_org=None)
        with open('data/rosters/all_mlb_rosters.json', 'r') as readfile:
            players = json.loads(readfile.read())
            for p in players:
                mlbam_id = str(p.get('mlbam_id') or p.get('mlbamid') or '').strip()
                if not mlbam_id:
                    continue
                try:
                    obj = models.Player.objects.get(mlbam_id=mlbam_id)
                except models.Player.DoesNotExist:
                    obj = self.create_player_from_mlb_depthcharts(p)
                    if obj:
                        players_created += 1
                        print(f"Created player: {obj.name} (MLB: {mlbam_id})")
                    else:
                        continue
                if not obj.birthdate and p.get('birthdate'):
                    obj.birthdate = p['birthdate']
                    obj.save()
                roster_updates = {}
                if p.get('roster_status'):
                    roster_updates['roster_status'] = p['roster_status']
                if p.get('mlb_org'):
                    roster_updates['mlb_org'] = p['mlb_org']
                if roster_updates:
                    self._update_player_stat_season(obj, current_season, **roster_updates)
                print(f"Updated roster status for {obj}")
        if players_created:
            print(f"\nCreated {players_created} new player(s) from MLB depth charts.")
