# ABOUTME: Non-injury roster moves: a paired call-up and send-down, 10 per half, with a 15-road-game stay for the call-up.
# ABOUTME: Also each team's road and home rosters for a half, the half-start roster snapshot, and the sim reset's restore step.

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ulmg import models, utils

MOVES_PER_HALF = 10
STAY_ROAD_GAMES = 15

UP = "up"
DOWN = "down"


class MoveError(Exception):
    pass


# The roster flag updates behind the to_mlb and to_aaa actions


def update_player_stat_season_roster(player, season=None, **kwargs):
    """Update or create PlayerStatSeason roster status fields for a player."""
    current_season = season if season is not None else utils.get_current_season()
    # Roster flags live on the real season line, never on the ULMG sim line.
    player_stat_season = models.PlayerStatSeason.objects.filter(
        player=player,
        season=current_season,
    ).exclude(classification=models.PlayerStatSeason.ULMG).first()

    if not player_stat_season:
        player_stat_season = models.PlayerStatSeason.objects.create(
            player=player,
            season=current_season,
            classification="1-mlb",
            owned=player.is_owned,
            carded=False,
        )

    for field, value in kwargs.items():
        if hasattr(player_stat_season, field):
            setattr(player_stat_season, field, value)

    player_stat_season.save()
    return player_stat_season


def mlb_roster_error(player, season):
    """Why a player can't go on the MLB roster in a ULMG season, or None."""
    if not player.is_carded_for_season(season - 1):
        return "Only carded players (MLB experience last season) can be placed on MLB roster"
    return None


def aaa_roster_error(player, season):
    """Why a player can't go on the AAA roster in a ULMG season, or None."""
    if player.is_ulmg_2h_draft:
        return "Midseason Open picks must stay on the MLB roster or be released"
    if not player.is_carded_for_season(season - 1):
        return "Only carded players (MLB experience last season) can be placed on AAA roster"
    return None


def _clear_protections(player):
    player.is_ulmg_reserve = False
    player.is_ulmg_1h_c = False
    player.is_ulmg_1h_p = False
    player.is_ulmg_1h_pos = False
    player.is_ulmg_2h_c = False
    player.is_ulmg_2h_p = False
    player.is_ulmg_2h_pos = False


def place_on_mlb_roster(player, season=None):
    """Put a player on the MLB roster and keep his PlayerStatSeason copy in step."""
    _clear_protections(player)
    player.is_ulmg_mlb_roster = True
    player.is_ulmg_aaa_roster = False
    player.save()
    update_player_stat_season_roster(
        player,
        season=season,
        is_ulmg_mlb_roster=True,
        is_ulmg_aaa_roster=False
    )


def place_on_aaa_roster(player, season=None):
    """Put a player on the AAA roster and keep his PlayerStatSeason copy in step."""
    _clear_protections(player)
    player.is_ulmg_mlb_roster = False
    player.is_ulmg_aaa_roster = True
    player.save()
    update_player_stat_season_roster(
        player,
        season=season,
        is_ulmg_mlb_roster=False,
        is_ulmg_aaa_roster=True
    )


# Road games and stays


def _final(games):
    return games.filter(home_score__isnull=False, road_score__isnull=False)


def _not_final(games):
    return games.filter(Q(home_score__isnull=True) | Q(road_score__isnull=True))


def road_games(team, season, half):
    """The team's road games in a half, in day order."""
    return models.ScheduleGame.objects.filter(
        series__road_team=team, series__slot__season=season, series__slot__half=half
    ).order_by("day")


def road_game_in_progress(team, season):
    """The team's road game that has opened and isn't final, or None."""
    games = models.ScheduleGame.objects.filter(
        series__road_team=team, series__slot__season=season, opened_at__isnull=False
    )
    return _not_final(games).order_by("day").first()


def appeared_in(player, game):
    """
    Whether a player has appeared in a game. Until the game log (#164)
    exists, an appearance is his usage ledger row for the game, which
    usage.record_plate_appearance writes on his first plate appearance or
    pitch. The game log must keep writing it, or change this check.
    """
    return models.UsageAppearance.objects.filter(player=player, game=game).exists()


def _stay_games(move):
    games = road_games(move.team, move.season, move.half)
    if move.stay_last_day is None:
        return games.none()
    return games.filter(day__lte=move.stay_last_day)


def stay_games_left(move):
    """How many of the stay's road games are not yet final."""
    return _not_final(_stay_games(move)).count()


def active_stay(player, season):
    """The move whose 15-road-game stay keeps this player on the 30-man, or None."""
    for move in models.RosterMove.objects.filter(player_up=player, season=season).order_by("-made_at", "-id"):
        if stay_games_left(move):
            return move
    return None


def stay_message(player, move):
    left = stay_games_left(move)
    return (
        f"{player.name} was called up and stays on the 30-man for {STAY_ROAD_GAMES} road games "
        f"or the rest of the half; {left} road game{'' if left == 1 else 's'} left on his stay."
    )


def active_stays(team, season):
    """The team's moves whose stays are still running, with the road games left on each."""
    stays = []
    moves = models.RosterMove.objects.filter(team=team, season=season).select_related("player_up")
    for move in moves.order_by("made_at", "id"):
        left = stay_games_left(move)
        if left and active_stay(move.player_up, season) == move:
            stays.append({"move": move, "player": move.player_up, "games_left": left})
    return stays


# The move log and the cap


def moves_this_half(team, season, half):
    return models.RosterMove.objects.filter(team=team, season=season, half=half).select_related(
        "player_up", "player_down", "game__series__home_team", "made_by"
    )


def moves_left(team, season, half):
    return max(MOVES_PER_HALF - moves_this_half(team, season, half).count(), 0)


def move_log(team, season):
    """The team's moves this season, newest first, with the road games left on each stay."""
    moves = models.RosterMove.objects.filter(team=team, season=season).select_related(
        "player_up", "player_down", "game__series__home_team", "made_by"
    )
    return [
        {"move": move, "games_left": stay_games_left(move)}
        for move in moves.order_by("-made_at", "-id")
    ]


def call_up_error(team, player_up, season):
    """Why a player can't be the call-up in one of the team's moves, or None."""
    abbr = team.abbreviation
    if player_up.team_id != team.id:
        return f"{player_up.name} is not on {abbr}."
    if player_up.is_ulmg_mlb_roster:
        return f"{player_up.name} is already on {abbr}'s 30-man."
    return mlb_roster_error(player_up, season)


def send_down_error(team, player_down, season):
    """Why a player can't be the send-down in one of the team's moves, or None."""
    if player_down.team_id != team.id or not player_down.is_ulmg_mlb_roster:
        return f"{player_down.name} is not on {team.abbreviation}'s 30-man."
    error = aaa_roster_error(player_down, season)
    if error:
        return error
    stay = active_stay(player_down, season)
    if stay is not None:
        return stay_message(player_down, stay)
    game = road_game_in_progress(team, season)
    if game is not None and appeared_in(player_down, game):
        return (
            f"{player_down.name} has appeared in the game in progress (day {game.day}) "
            "and can't be sent down until it is final."
        )
    return None


def cap_error(team, season, half):
    """Why the team can't make another move this half, or None."""
    if moves_this_half(team, season, half).count() >= MOVES_PER_HALF:
        return f"{team.abbreviation} has made its {MOVES_PER_HALF} moves for half {half}."
    return None


def _move_errors(team, player_up, player_down, season, half):
    if player_up.pk == player_down.pk:
        return f"{player_up.name} can't be called up and sent down in the same move."
    return (
        call_up_error(team, player_up, season)
        or send_down_error(team, player_down, season)
        or cap_error(team, season, half)
    )


class MoveChoices:
    """
    The players who can finish a move started from one player, found with
    the same checks make_move runs. `error` says why the move can't start
    at all; `refused` holds each other candidate with the reason he can't.
    """

    def __init__(self, player, direction, error, legal, refused):
        self.player = player
        self.direction = direction
        self.error = error
        self.legal = legal
        self.refused = refused


def move_choices(team, player, direction, season, half):
    """
    For a player going DOWN, the team's AAA players who can be called up in
    his place; for a player going UP, the team's 30-man players who can be
    sent down for him.
    """
    if direction == DOWN:
        error = send_down_error(team, player, season)
        candidates = models.Player.objects.filter(team=team, is_ulmg_aaa_roster=True, is_ulmg_mlb_roster=False)
        partner_error = call_up_error
    else:
        error = call_up_error(team, player, season)
        candidates = models.Player.objects.filter(team=team, is_ulmg_mlb_roster=True)
        partner_error = send_down_error
    error = error or cap_error(team, season, half)
    legal, refused = [], []
    if error is None:
        for candidate in candidates.exclude(pk=player.pk).order_by("name"):
            reason = partner_error(team, candidate, season)
            if reason:
                refused.append((candidate, reason))
            else:
                legal.append(candidate)
    return MoveChoices(player, direction, error, legal, refused)


def make_move(team, player_up, player_down, *, season, half, user=None):
    """
    Call one player up to the team's 30-man and send one down to AAA, as one
    non-injury move. Legal at any time, including during the team's road
    game in progress, unless the player going down has appeared in it. The
    call-up stays up for the team's next 15 road games, counting a game in
    progress, or the rest of the half if fewer remain. Raises MoveError and
    changes nothing when a rule is broken. Returns the RosterMove.
    """
    with transaction.atomic():
        # One move at a time per team, so two moves can't both take the 10th.
        team = models.Team.objects.select_for_update().get(pk=team.pk)
        player_up = models.Player.objects.get(pk=player_up.pk)
        player_down = models.Player.objects.get(pk=player_down.pk)
        error = _move_errors(team, player_up, player_down, season, half)
        if error:
            raise MoveError(error)

        ensure_snapshot(season, half)
        place_on_mlb_roster(player_up, season=season)
        place_on_aaa_roster(player_down, season=season)

        stay = list(_not_final(road_games(team, season, half))[:STAY_ROAD_GAMES])
        return models.RosterMove.objects.create(
            season=season,
            half=half,
            team=team,
            player_up=player_up,
            player_down=player_down,
            made_by=user if user is not None and user.is_authenticated else None,
            stay_games=len(stay),
            stay_last_day=stay[-1].day if stay else None,
            game=road_game_in_progress(team, season),
        )


# Rosters by game


class HalfRosters:
    """
    A team's rosters for one half. Road games use the 30-man as it stands.
    Home games use the 30-man the half's moves left alone: a player whose
    first move this half was a call-up is road-only, and one whose first
    move was a send-down stays eligible at home while he is on the team.
    """

    def __init__(self, team, season, half):
        self.team = team
        on_team = dict(models.Player.objects.filter(team=team).values_list("id", "is_ulmg_mlb_roster"))
        self.road = {pid for pid, mlb in on_team.items() if mlb}
        first_move = {}
        moves = models.RosterMove.objects.filter(team=team, season=season, half=half).order_by("made_at", "id")
        for player_up_id, player_down_id in moves.values_list("player_up_id", "player_down_id"):
            first_move.setdefault(player_up_id, UP)
            first_move.setdefault(player_down_id, DOWN)
        called_up = {pid for pid, kind in first_move.items() if kind == UP}
        sent_down = {pid for pid, kind in first_move.items() if kind == DOWN}
        self.home = (self.road - called_up) | (sent_down & set(on_team))

    @property
    def all(self):
        """Everyone the team can plan into some game of the half."""
        return self.road | self.home

    def is_home(self, game):
        return game.series.home_team_id == self.team.id

    def for_game(self, game):
        return self.home if self.is_home(game) else self.road

    def problem(self, player, game):
        """Why a player can't be planned into one of the team's games, or None."""
        if player.id in self.for_game(game):
            return None
        if self.is_home(game) and player.id in self.road:
            return f"{player.name} is a call-up and can be planned into road games only."
        if not self.is_home(game) and player.id in self.home:
            return f"{player.name} was sent down and can be planned into home games only."
        return f"{player.name} is not on {self.team.abbreviation}'s 30-man."


def game_roster_ids(team, game):
    """
    The ids of the team's players who can play in one of its games. The
    road game (#164) reads this before each plate appearance, so a call-up
    made during the game is available from the next one.
    """
    slot = game.series.slot
    return HalfRosters(team, slot.season, slot.half).for_game(game)


# The half-start snapshot


def half_has_started(season, half):
    """A half starts when its first game opens or is played, or its first move is made."""
    games = models.ScheduleGame.objects.filter(series__slot__season=season, series__slot__half=half)
    started = games.filter(opened_at__isnull=False).exists() or _final(games).exists()
    return started or models.RosterMove.objects.filter(season=season, half=half).exists()


def single_move_error(user, season, half):
    """
    Once a half has started, moving one player at a time would dodge the
    10-move cap, so owners must use a paired move. The commissioner still can.
    """
    if getattr(user, "is_superuser", False) or not half_has_started(season, half):
        return None
    return (
        "The half has started: make a roster move instead, calling one player up "
        "and sending one down together."
    )


def ensure_snapshot(season, half):
    """
    The half's roster snapshot, taken now if there is none, and retaken
    while the half hasn't started. Called when a game opens and before a
    move, so the snapshot is the rosters as the half began.
    """
    with transaction.atomic():
        snapshot, created = models.HalfRosterSnapshot.objects.get_or_create(season=season, half=half)
        snapshot = models.HalfRosterSnapshot.objects.select_for_update().get(pk=snapshot.pk)
        if created or not half_has_started(season, half):
            snapshot.players.all().delete()
            models.HalfRosterSnapshotPlayer.objects.bulk_create(
                models.HalfRosterSnapshotPlayer(
                    snapshot=snapshot,
                    player_id=player_id,
                    team_id=team_id,
                    is_ulmg_mlb_roster=mlb,
                    is_ulmg_aaa_roster=aaa,
                )
                for player_id, team_id, mlb, aaa in models.Player.objects.filter(team__isnull=False).values_list(
                    "id", "team_id", "is_ulmg_mlb_roster", "is_ulmg_aaa_roster"
                )
            )
            snapshot.taken_at = timezone.now()
            snapshot.save(update_fields=["taken_at", "last_modified"])
        return snapshot


def restore_snapshot(season):
    """
    The sim reset's restore step: put every player who was on a team in the
    season's earliest half snapshot back to his snapshot 30-man and AAA
    flags, and his PlayerStatSeason copy for the season with them. Teams are
    left alone; trades are real data. Returns a line for the reset to report.
    """
    snapshot = models.HalfRosterSnapshot.objects.filter(season=season).order_by("half").first()
    if snapshot is None:
        return f"no roster snapshot for {season}; roster flags left as they are"
    restored = 0
    for row in snapshot.players.select_related("player"):
        player = row.player
        target = (row.is_ulmg_mlb_roster, row.is_ulmg_aaa_roster)
        stats = (
            models.PlayerStatSeason.objects.filter(player=player, season=season)
            .exclude(classification=models.PlayerStatSeason.ULMG)
            .first()
        )
        player_changed = (player.is_ulmg_mlb_roster, player.is_ulmg_aaa_roster) != target
        stats_changed = stats is not None and (stats.is_ulmg_mlb_roster, stats.is_ulmg_aaa_roster) != target
        if player_changed:
            player.is_ulmg_mlb_roster, player.is_ulmg_aaa_roster = target
            player.save()
        if player_changed or stats_changed:
            update_player_stat_season_roster(
                player, season=season, is_ulmg_mlb_roster=target[0], is_ulmg_aaa_roster=target[1]
            )
            restored += 1
    return f"put {restored} players' roster flags back to the half {snapshot.half} roster snapshot"
