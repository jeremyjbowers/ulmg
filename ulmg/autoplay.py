# ABOUTME: Autoplay: hands a sim game, or the rest of its series, to the computer and plays it to its final in one request.
# ABOUTME: Uses sim_game's computer paths for every decision; each handed-over seat and every computer action is a logged event.

from dataclasses import dataclass

from django.db import transaction

from ulmg import engine_client, models, schedule, sim_game

Event = models.GameEvent


@dataclass
class Result:
    """One autoplayed game: its log, whether it is final, the pause that stopped it, and the plate appearances played."""

    log: object
    final: bool
    paused: dict = None
    plate_appearances: int = 0


def _log_for(game):
    return models.GameLog.objects.filter(game=game).first()


def autoplay_refusal(user, game, log=None):
    """
    Why the user may not autoplay a game, or None. The commissioner (a
    superuser) may autoplay any game that isn't final; the road team's
    manager only his own road game: his next unplayed one if it isn't open
    yet, and one already open only when nobody else holds a seat in it.
    user None is the autoplay_season command, run by whoever runs the site.
    """
    log = log if log is not None else _log_for(game)
    fold = sim_game.Fold(log.events.order_by("sequence")) if log is not None else None
    if fold is not None and fold.final:
        return "The game is final."
    if log is None and game.is_played:
        return "This game already has a score and can't be autoplayed."
    if user is None or user.is_superuser:
        return None
    road = game.series.road_team
    if not user.is_authenticated or not sim_game.is_owner_of(user, road):
        return f"Only {road.abbreviation}'s manager or the commissioner can autoplay this game."
    if log is None:
        if schedule.next_unplayed_road_game(road, sim_game.season_of(game)) != game:
            return "You can autoplay only your next unplayed road game, or one already in progress."
        return None
    for side in sim_game.SIDES:
        holder = fold.seats[side]
        if holder is not None and holder != user.id:
            return (
                f"Someone else holds the {sim_game.side_label(game, side)} seat, so you can't hand this game to the computer."
            )
    return None


def can_autoplay(user, game):
    """Whether the game page should offer the user autoplay."""
    return user.is_authenticated and autoplay_refusal(user, game) is None


def _hand_over_seats(play, user):
    """Each seat a person holds becomes the computer's, with an event naming who handed it over."""
    for side in sim_game.SIDES:
        holder = play.fold.seats[side]
        if holder is None:
            continue
        play.append(
            Event.SEAT,
            side=side,
            computer=True,
            payload={"autoplay": True, "by": user.id if user is not None else None, "from": holder},
            text=f"{sim_game.side_label(play.game, side)} seat: handed to the computer, autoplaying for "
            f"{sim_game.autoplayer_name(user)}.",
        )


def _check_expected(play, expected):
    try:
        position = int(expected)
    except (TypeError, ValueError):
        raise sim_game.GameRefused(sim_game.STALE)
    if position != play.sequence:
        raise sim_game.GameRefused(sim_game.STALE)


def autoplay_game(game, user, expected=None, seeds=engine_client.new_seed):
    """
    Play a game to its final with the computer holding both seats, in one
    transaction. An unopened game is opened from both teams' frozen half
    plans; a game in progress first has every held seat handed to the
    computer. expected is the log position the page showed for a game in
    progress (None skips the check, for the command). Stops early, with the
    game saved where it stands, when a side has no legal player and the
    game pauses. Raises GameRefused, with nothing saved, when the user may
    not autoplay it or it can't be opened.
    """
    with transaction.atomic():
        game = (
            models.ScheduleGame.objects.select_for_update()
            .select_related("series__slot", "series__home_team", "series__road_team")
            .get(pk=game.pk)
        )
        log = _log_for(game)
        refusal = autoplay_refusal(user, game, log)
        if refusal:
            raise sim_game.GameRefused(refusal)
        if log is None:
            log = sim_game.start_log(game, user, (), seeds, autoplay=True)
        elif expected is not None:
            _check_expected(sim_game.Play(log), expected)
        log = models.GameLog.objects.select_for_update().select_related(
            "game__series__slot", "game__series__home_team", "game__series__road_team"
        ).get(pk=log.pk)
        play = sim_game.Play(log, seeds)
        _hand_over_seats(play, user)
        sim_game.settle(play)

        played = 0
        while not play.fold.final and play.fold.pause is None:
            need = play.need()
            if need is not None:
                # settle() leaves a need open only for a person's seat, and autoplay holds none.
                raise sim_game.GameRefused(need.reason)
            call = sim_game.computer_steal(play, sim_game.batting_side(play.state))
            sim_game.play_plate_appearance(play, call, computer=True)
            played += 1
            sim_game.settle(play)
        play.save_state()
    return Result(log=log, final=play.fold.final, paused=play.fold.pause, plate_appearances=played)


def remaining_series_games(game):
    """The game and the later games of its series that aren't final, in schedule order."""
    games = models.ScheduleGame.objects.filter(series=game.series, day__gte=game.day).select_related(
        "series__slot", "series__home_team", "series__road_team"
    )
    return [g for g in games.order_by("day") if not is_final(g)]


def is_final(game):
    log = _log_for(game)
    if log is None:
        return game.is_played
    return log.events.filter(kind=Event.FINAL).exists()


def autoplay_series(game, user, expected=None, seeds=engine_client.new_seed):
    """
    Autoplay the game and then the rest of its series in schedule order,
    each game in its own transaction. Stops after a game that pauses.
    expected applies to the game itself. Returns the Results played; a later
    game that can't be opened raises GameRefused with the earlier games kept.
    """
    results = []
    for next_game in remaining_series_games(game):
        result = autoplay_game(next_game, user, expected=expected if next_game == game else None, seeds=seeds)
        results.append(result)
        if not result.final:
            break
    return results
