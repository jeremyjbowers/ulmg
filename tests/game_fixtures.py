# ABOUTME: Shared test data for sim game tests: two filed half plans with complete engine cards, a manager, a tester and the engine.
# ABOUTME: Builds real rows on a real generated schedule and starts the real engine binary; seeds come from a counter.

import itertools

from django.contrib.auth.models import Group, User
from django.test import override_settings

from tests import plan_fixtures
from tests.engine_process import EngineProcess, build_engine
from ulmg import models, schedule, sim_game, usage, utils

SEASON = plan_fixtures.SEASON
CARD_SEASON = plan_fixtures.CARD_SEASON

HITTER_RATES = dict(plan_fixtures.HITTER_RATES)
HITTER_RATES["bip_out"] = 1 - sum(HITTER_RATES.values())

STARTER_FATIGUE = {
    "role": "starter",
    "age": 28,
    "season_pitches_per_appearance": 100.0,
    "career_pitches_per_appearance": 100.0,
    "season_appearances": 32,
}
RELIEVER_FATIGUE = {
    "role": "reliever",
    "age": 30,
    "season_pitches_per_appearance": 18.0,
    "career_pitches_per_appearance": 18.0,
    "season_appearances": 60,
}

# Rates a hitter can only strike out or homer with: they make a game's runs certain.
STRIKEOUT_RATES = {"k": 1.0, "bb": 0.0, "hbp": 0.0, "single": 0.0, "double": 0.0, "triple": 0.0, "hr": 0.0, "bip_out": 0.0}
HOME_RUN_RATES = {"k": 0.0, "bb": 0.0, "hbp": 0.0, "single": 0.0, "double": 0.0, "triple": 0.0, "hr": 1.0, "bip_out": 0.0}


def complete_cards(roster):
    """Give a plan_fixtures roster the full engine cards a game needs: rates summing to 1 and fatigue lines."""
    for pitcher in roster.starters + [roster.swingman]:
        models.Card.objects.filter(player=pitcher).update(fatigue=STARTER_FATIGUE)
    for pitcher in roster.relievers:
        models.Card.objects.filter(player=pitcher).update(fatigue=RELIEVER_FATIGUE)
    for hitter in roster.hitters + roster.bench:
        models.Card.objects.filter(player=hitter).update(hitter_rates=HITTER_RATES, wrc_plus=100.0)


def set_rates(players, rates):
    for player in players:
        models.Card.objects.filter(player=player).update(hitter_rates=dict(rates))


def first_game():
    """Day 1's first game of the generated season."""
    return (
        models.ScheduleGame.objects.filter(series__slot__season=SEASON, day=1)
        .select_related("series__slot", "series__home_team", "series__road_team")
        .order_by("series__home_team__abbreviation")
        .first()
    )


def create_game_season(test_case):
    """
    The league, its schedule, and filed half-1 plans for both teams of day
    1's first game, on test_case: game, road and home (Rosters), manager
    (the road team's owner), other_manager (the home team's owner) and
    tester (a Sim testers member).
    """
    plan_fixtures.create_season()
    game = first_game()
    test_case.game = game
    test_case.road = plan_fixtures.Roster(game.series.road_team)
    test_case.home = plan_fixtures.Roster(game.series.home_team)
    for roster in (test_case.road, test_case.home):
        complete_cards(roster)
        roster.file(half=1)

    test_case.manager = User.objects.create_user(username="road-manager")
    owner = models.Owner.objects.create(user=test_case.manager, name="Road Manager")
    models.Team.objects.filter(pk=game.series.road_team_id).update(owner_obj=owner)
    test_case.other_manager = User.objects.create_user(username="home-manager")
    other = models.Owner.objects.create(user=test_case.other_manager, name="Home Manager")
    models.Team.objects.filter(pk=game.series.home_team_id).update(owner_obj=other)
    test_case.tester = User.objects.create_user(username="sim-tester")
    group, _ = Group.objects.get_or_create(name=utils.SIM_TESTERS_GROUP)
    test_case.tester.groups.add(group)


def counter(player, **fields):
    """Set a player's usage counter for the season, creating it with his caps first."""
    row = usage.counter_for(player, SEASON)
    for name, value in fields.items():
        setattr(row, name, value)
    row.save()
    return row


def seeds(start=1000):
    return itertools.count(start).__next__


def refresh(log):
    return models.GameLog.objects.get(pk=log.pk)


def first_legal(options):
    return next(o.player for o in options if o.legal)


def play_out(log, user, next_seed, *, limit=600, before_step=None):
    """
    Play a game to its final as the user, one plate appearance at a time.
    When one of his seats must replace a player, he takes the first legal
    option. Returns the log.
    """
    for _ in range(limit):
        log = refresh(log)
        play = sim_game.Play(log)
        if play.fold.final:
            return log
        need = play.need()
        if need is not None and play.fold.holds(user, need.side):
            choice = first_legal(play.options_for(need))
            if need.kind == sim_game.PITCHER_NEED:
                sim_game.change_pitcher(log, user, need.side, choice, play.sequence, seeds=next_seed)
            else:
                sim_game.replace_batter(log, user, need.side, choice, play.sequence, seeds=next_seed)
            continue
        if before_step is not None:
            before_step(play)
        sim_game.step(log, user, play.sequence, seeds=next_seed)
    raise AssertionError(f"the game did not end in {limit} actions")


def events(log, kind=None):
    rows = models.GameEvent.objects.filter(log=log).order_by("sequence")
    return list(rows.filter(kind=kind) if kind else rows)


class EngineMixin:
    """Starts the real engine binary for a test class and points ENGINE_URL at it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = EngineProcess(build_engine()).start()
        cls.addClassCleanup(cls.engine.stop)
        overridden = override_settings(ENGINE_URL=cls.engine.url)
        overridden.enable()
        cls.addClassCleanup(overridden.disable)


def next_road_game(team):
    return schedule.next_unplayed_road_game(team, SEASON)
