# ABOUTME: Shared test data for usage ledger tests: real players with card-season stats and a scheduled series.
# ABOUTME: Builds Team, Player, PlayerStatSeason and ScheduleSlot/Series/Game rows in the test database.

from ulmg import models

ULMG_SEASON = 2026
CARD_SEASON = ULMG_SEASON - 1


def create_teams():
    home = models.Team.objects.create(
        abbreviation="HCH", city="Hub City", nickname="Hawks", division="Ringen"
    )
    road = models.Team.objects.create(
        abbreviation="ATL", city="Atlanta", nickname="Crackers", division="Rickey"
    )
    return home, road


def create_series(home, road, length=5, slot_number=1, first_day=1):
    """One slot holding one series of `length` games; returns the games in game-number order."""
    slot = models.ScheduleSlot.objects.create(
        season=ULMG_SEASON,
        half=1,
        number=slot_number,
        slot_type=models.ScheduleSlot.DIVISION,
        length=length,
        first_day=first_day,
    )
    series = models.ScheduleSeries.objects.create(slot=slot, home_team=home, road_team=road)
    return [
        models.ScheduleGame.objects.create(series=series, day=first_day + i)
        for i in range(length)
    ]


def create_pitcher(name, team=None, **pitch_stats):
    player = models.Player.objects.create(name=name, position="P", level="V", team=team)
    models.PlayerStatSeason.objects.create(
        player=player,
        season=CARD_SEASON,
        classification="1-mlb",
        pitch_stats=pitch_stats,
    )
    return player


def create_hitter(name, team=None, **hit_stats):
    player = models.Player.objects.create(name=name, position="OF", level="V", team=team)
    models.PlayerStatSeason.objects.create(
        player=player,
        season=CARD_SEASON,
        classification="1-mlb",
        hit_stats=hit_stats,
    )
    return player
