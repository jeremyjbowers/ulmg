# ABOUTME: A test 30-man for every team: carded players, Open picks first, then innings and wRC+.
# ABOUTME: The seed command is the only caller. Nothing here is a league rule or a page.

from django.conf import settings
from django.db.models import Q

from ulmg import models, plans, roster_moves, usage, utils

# A playable test roster: a staff, then a lineup and a bench. Not a roster rule.
PITCHER_SLOTS = 13
HITTER_SLOTS = 17


def _count(stats, key):
    try:
        return int(stats.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def carded_ids(players, card_season):
    """Player ids with a card for card_season: the stored list, a carded row, or an MLB appearance."""
    ids = [player.id for player in players]
    listed = {player.id for player in players if card_season in (player.carded_seasons or [])}
    rows = models.PlayerStatSeason.objects.filter(player_id__in=ids, season=card_season, is_career=False)
    marked = set(rows.filter(carded=True).values_list("player_id", flat=True))
    appeared = set(
        rows.filter(classification="1-mlb").filter(utils.mlb_appearances_q()).values_list("player_id", flat=True)
    )
    return listed | marked | appeared


def _ranks(players, season):
    """Pitchers by card-season innings, hitters by card wRC+. A missing number sorts last."""
    ids = [player.id for player in players]
    stats = usage.card_stats_by_player(players, season)
    wrc = {
        row["player_id"]: row["wrc_plus"]
        for row in models.Card.objects.filter(player_id__in=ids, season=season - 1).values("player_id", "wrc_plus")
    }
    pitchers, hitters = [], []
    for player in players:
        if plans.can_pitch(player):
            _hit, pitch = stats.get(player.id, ({}, {}))
            pitchers.append((-usage.innings_to_outs(pitch.get("ip")), -_count(pitch, "gs"), player.name, player.id, player))
        else:
            value = wrc.get(player.id)
            hitters.append((-(value if value is not None else float("-inf")), player.name, player.id, player))
    pitchers.sort()
    hitters.sort()
    return [row[-1] for row in pitchers], [row[-1] for row in hitters]


def choose(players, season, size=None):
    """
    The test 30-man. Midseason Open picks stay on it. The rest are carded
    players: up to 13 pitchers with the most card-season innings, then up to
    17 hitters with the highest card wRC+, then whoever is left until the
    roster is full.
    """
    size = settings.MLB_ROSTER_SIZE if size is None else size
    locked = [player for player in players if player.is_ulmg_2h_draft]
    locked_ids = {player.id for player in locked}
    eligible_ids = carded_ids(players, season - 1) - locked_ids
    eligible = [player for player in players if player.id in eligible_ids]
    pitchers, hitters = _ranks(eligible, season)

    pitcher_room = max(0, PITCHER_SLOTS - sum(1 for player in locked if plans.can_pitch(player)))
    hitter_room = max(0, HITTER_SLOTS - sum(1 for player in locked if not plans.can_pitch(player)))
    room = max(0, size - len(locked))
    taken_pitchers = pitchers[: min(pitcher_room, room)]
    room -= len(taken_pitchers)
    taken_hitters = hitters[: min(hitter_room, room)]
    room -= len(taken_hitters)
    taken_ids = {player.id for player in taken_pitchers + taken_hitters}
    rest = [player for player in pitchers + hitters if player.id not in taken_ids]
    return locked + taken_pitchers + taken_hitters + rest[:room]


def write_team(team, chosen, season):
    """Replace the team's MLB and AAA flags with chosen. Chosen is the test 30-man."""
    chosen_ids = [player.id for player in chosen]
    models.Player.objects.filter(team=team).update(is_ulmg_mlb_roster=False, is_ulmg_aaa_roster=False)
    models.Player.objects.filter(pk__in=chosen_ids).update(is_ulmg_mlb_roster=True, is_ulmg_aaa_roster=False)
    stat_rows = models.PlayerStatSeason.objects.filter(player__team=team, season=season).exclude(
        classification=models.PlayerStatSeason.ULMG
    )
    stat_rows.update(is_ulmg_mlb_roster=False, is_ulmg_aaa_roster=False)
    stat_rows.filter(player_id__in=chosen_ids).update(is_ulmg_mlb_roster=True, is_ulmg_aaa_roster=False)
    have = set(stat_rows.filter(player_id__in=chosen_ids).values_list("player_id", flat=True))
    for player in chosen:
        if player.id not in have:
            roster_moves.update_player_stat_season_roster(
                player, season=season, is_ulmg_mlb_roster=True, is_ulmg_aaa_roster=False
            )


def blank(season):
    """Set every MLB and AAA flag to false, on players and on the season's stat lines."""
    players = models.Player.objects.filter(Q(is_ulmg_mlb_roster=True) | Q(is_ulmg_aaa_roster=True))
    player_count = players.update(is_ulmg_mlb_roster=False, is_ulmg_aaa_roster=False)
    stat_rows = models.PlayerStatSeason.objects.filter(season=season).filter(
        Q(is_ulmg_mlb_roster=True) | Q(is_ulmg_aaa_roster=True)
    )
    stat_count = stat_rows.update(is_ulmg_mlb_roster=False, is_ulmg_aaa_roster=False)
    return player_count, stat_count


def blank_counts(season):
    """How many player rows and stat lines a blank would clear."""
    players = models.Player.objects.filter(Q(is_ulmg_mlb_roster=True) | Q(is_ulmg_aaa_roster=True)).count()
    stats = models.PlayerStatSeason.objects.filter(season=season).filter(
        Q(is_ulmg_mlb_roster=True) | Q(is_ulmg_aaa_roster=True)
    ).count()
    return players, stats
