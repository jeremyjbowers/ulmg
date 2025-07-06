from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count
from datetime import datetime

import ujson as json

from ulmg import models, utils

class Command(BaseCommand):

    def _get_current_season(self):
        """Get the current season year."""
        return datetime.now().year

    def _update_player_stat_season(self, player, season, **kwargs):
        """Update or create PlayerStatSeason with roster status fields."""
        # Get or create the most recent PlayerStatSeason for this player
        # We'll use the most recent stats record or create a new one for the current season
        player_stat_season = models.PlayerStatSeason.objects.filter(
            player=player
        ).order_by('-season', '-classification').first()
        
        if not player_stat_season:
            # Create a new PlayerStatSeason for the current season
            player_stat_season = models.PlayerStatSeason.objects.create(
                player=player,
                season=season,
                classification='2-minors',  # Default to majors, will be corrected by stats updates
                owned=player.is_owned,
                carded=False  # Will be set by separate command
            )
        
        # Update the roster status fields
        for field, value in kwargs.items():
            if hasattr(player_stat_season, field):
                setattr(player_stat_season, field, value)
        
        player_stat_season.save()
        return player_stat_season

    def handle(self, *args, **options):
        current_season = self._get_current_season()
        
        # Clear roster status and organization fields for all current season PlayerStatSeason records
        models.PlayerStatSeason.objects.filter(
            season=current_season
        ).update(roster_status=None, mlb_org=None)
        
        with open('data/rosters/all_mlb_rosters.json', 'r') as readfile:
            players = json.loads(readfile.read())

            for p in players:
                try:
                    obj = models.Player.objects.get(mlbam_id=p['mlbam_id'])

                    # Update permanent player fields (birthdate stays on Player)
                    if not obj.birthdate:
                        if p.get('birthdate', None):
                            obj.birthdate = p['birthdate']
                            obj.save()

                    # Update season-specific fields on PlayerStatSeason
                    roster_updates = {}
                    
                    if p.get('roster_status', None):
                        roster_updates['roster_status'] = p['roster_status']

                    if p.get('mlb_org', None):
                        roster_updates['mlb_org'] = p['mlb_org']

                    if roster_updates:
                        self._update_player_stat_season(obj, current_season, **roster_updates)
                    
                    print(f"Updated roster status for {obj}")

                except models.Player.DoesNotExist:
                    pass