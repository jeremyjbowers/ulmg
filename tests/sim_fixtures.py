# ABOUTME: Shared test data for sim-reset tests: a played season of sim data and one row of every kept model.
# ABOUTME: Builds real rows in the test database; seasons, teams and players are chosen per test.

import datetime

from django.contrib.auth.models import User
from django.utils import timezone

from ulmg import models

STAT_CLASSIFICATIONS = ["1-mlb", "2-milb", "3-npb", "4-kbo", "5-college"]


def create_played_season(season, home, road, player, days=3, first_day=1, slot_number=1):
    """
    One slot and series for the season, every game opened and scored, the
    home team's half plan, the usage ledger rows a played series leaves:
    a counter, appearances, an override, a pause and the player's 6-ulmg
    season line, one roster move made during the first game, and the first
    game's log with two of its events.
    """
    slot = models.ScheduleSlot.objects.create(
        season=season,
        half=1,
        number=slot_number,
        slot_type=models.ScheduleSlot.DIVISION,
        length=days,
        first_day=first_day,
    )
    series = models.ScheduleSeries.objects.create(slot=slot, home_team=home, road_team=road)
    games = []
    for day in range(first_day, first_day + days):
        games.append(
            models.ScheduleGame.objects.create(
                series=series,
                day=day,
                home_score=day + 2,
                road_score=day,
                opened_at=timezone.now(),
                opening_sheet={"home": {"starter": player.id}, "road": {}},
            )
        )
    plan = models.HalfPlan.objects.create(team=home, season=season, half=1, rotation=[player.id])
    for day in range(first_day, first_day + days):
        models.HalfPlanDay.objects.create(plan=plan, day=day, auto_starter=player)
    models.UsageCounter.objects.create(player=player, season=season, starts=1, outs=18)
    for game in games:
        models.UsageAppearance.objects.create(player=player, game=game, outs=6, pitches=90)
    models.UsageOverride.objects.create(
        player=player,
        game=games[0],
        cap=models.UsageOverride.REST,
        request_reason="",
        reason="Test season",
    )
    models.UsagePause.objects.create(game=games[-1], team=home, reason="No legal pitcher")
    models.PlayerStatSeason.objects.create(
        player=player,
        season=season,
        classification="6-ulmg",
        pitch_stats={"ip": 18},
    )
    sent_down = models.Player.objects.create(name=f"Sim Sent Down {season}", position="P", team=road)
    models.RosterMove.objects.create(
        season=season,
        half=1,
        team=road,
        player_up=player,
        player_down=sent_down,
        stay_games=15,
        stay_last_day=first_day + days - 1,
        game=games[0],
    )
    log = models.GameLog.objects.create(game=games[0], state={"status": "final"}, state_sequence=2)
    models.GameEvent.objects.create(log=log, sequence=1, kind=models.GameEvent.OPEN, payload={"sheet": {}})
    models.GameEvent.objects.create(log=log, sequence=2, kind=models.GameEvent.FINAL, payload={})
    return games


def create_kept_rows(season, team, player):
    """One row of every kept model, several tied to the season being reset."""
    user = User.objects.create_user(username="kept-owner")
    owner = models.Owner.objects.create(user=user, name="Kept Owner")
    models.MagicLinkToken.objects.create(
        user=user, token="kept-token", expires_at=timezone.now() + datetime.timedelta(days=1)
    )
    models.Venue.objects.create(
        team=team, name="Kept Park", mlb_team="Kept", mlb_venue_id=1, mlb_venue_url="https://example.com"
    )
    for classification in STAT_CLASSIFICATIONS:
        models.PlayerStatSeason.objects.create(
            player=player, season=season, classification=classification, hit_stats={"pa": 600}
        )
    models.Card.objects.create(player=player, season=season)
    pick = models.DraftPick.objects.create(
        year=str(season),
        season=models.DraftPick.OFFSEASON,
        draft_type=models.DraftPick.OPEN_TYPE,
        draft_round=1,
        team=team,
        original_team=team,
    )
    trade = models.Trade.objects.create(date=datetime.date(season, 7, 1))
    receipt = models.TradeReceipt.objects.create(trade=trade, team=team)
    receipt.players.add(player)
    receipt.picks.add(pick)
    models.TradeSummary.objects.create(season=str(season), trade_type=models.TradeSummary.PLAYERS)
    models.Transaction.objects.create(
        transaction_type="dropped", player=player, season=season, date=datetime.date(season, 5, 1)
    )
    models.ProspectRating.objects.create(year=str(season), player=player)
    wishlist = models.Wishlist.objects.create(owner=owner)
    models.WishlistPlayer.objects.create(player=player, wishlist=wishlist)
    event = models.Event.objects.create(title="Kept event")
    models.Occurrence.objects.create(event=event, season=season, date=datetime.date(season, 4, 1))
    other = models.Player.objects.create(name="Kept Duplicate")
    models.DuplicatePlayerCandidate.objects.create(player1=player, player2=other)
    models.OwnerAPIToken.create_token(owner, label="kept")
    snapshot = models.HalfRosterSnapshot.objects.create(season=season, half=1)
    models.HalfRosterSnapshotPlayer.objects.create(
        snapshot=snapshot,
        player=player,
        team=team,
        is_ulmg_mlb_roster=player.is_ulmg_mlb_roster,
        is_ulmg_aaa_roster=player.is_ulmg_aaa_roster,
    )
