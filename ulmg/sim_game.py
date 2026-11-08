# ABOUTME: Plays a scheduled game in the sim from an append-only log: opening, seats, one plate appearance per step, changes and the final.
# ABOUTME: Every roll happens on the server through the engine client; the game state is a fold of the log and replays exactly.

import copy
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from ulmg import box_score, cards, computer_manager, engine_client, models, plans, roster_moves, schedule, season_record, usage, utils

Event = models.GameEvent

AWAY = Event.AWAY
HOME = Event.HOME
SIDES = (AWAY, HOME)
SHEET_KEYS = {AWAY: "road", HOME: "home"}

# Pitch around raises the walk rate for one plate appearance without an engine change:
# the hitter's bb rate is multiplied by this and the other outcomes scale down to keep the sum at 1.
PITCH_AROUND_BB_MULT = 2.0
PITCH_AROUND = "pitch_around"
OFFENSE_CALLS = ("bunt", "steal", "hit_and_run")
DEFENSE_CALLS = ("intentional_walk", PITCH_AROUND)
CALL_LABELS = {
    "bunt": "Bunt",
    "steal": "Steal",
    "hit_and_run": "Hit and run",
    "intentional_walk": "Intentional walk",
    PITCH_AROUND: "Pitch around",
}
# The engine's call for a plate appearance a human plays with no call.
NO_CALL = "none"

# Outcomes that are not at-bats. A caught stealing that ends a plate appearance has no batter.
NOT_AT_BATS = {"walk", "hit_by_pitch", "intentional_walk", "bunt_sacrifice", "sacrifice_fly", "caught_stealing"}

# Pitcher cards have no defense yet (#160); the engine takes 0 at P.
PITCHER_DEFENSE = {"rating": 0.0, "measured_at": "P"}
# wRC+ only feeds the engine's fatigue effort. A card without one is league average.
DEFAULT_WRC_PLUS = 100.0
DH = "DH"
CATCHER = "C"

PITCHER_NEED = "pitcher"
BATTER_NEED = "batter"


class GameRefused(Exception):
    """An action that breaks a rule. Nothing was played or written. reasons are messages for the page."""

    def __init__(self, reasons):
        if isinstance(reasons, str):
            reasons = [reasons]
        self.reasons = list(reasons)
        super().__init__(" ".join(self.reasons))


STALE = (
    "The game has moved on since this page loaded, so nothing was played. "
    "Here is the game as it stands now."
)


# Sides, teams and seats


def other_side(side):
    return HOME if side == AWAY else AWAY


def team_for(game, side):
    return game.series.road_team if side == AWAY else game.series.home_team


def side_label(game, side):
    return team_for(game, side).abbreviation


def season_of(game):
    return game.series.slot.season


def is_owner_of(user, team):
    return utils.get_team_for_owner(utils.get_owner_for_user(user)) == team


def open_seat_choices(user, game):
    """
    The seat choices a user may open a game with: a sim tester any unplayed
    game as away, home or both; a manager his team's next unplayed road
    game, from the visiting seat only. Empty when he can't open it.
    """
    if not user.is_authenticated or game.is_played or has_log(game):
        return []
    if utils.is_sim_tester(user):
        return [(AWAY,), (HOME,), (AWAY, HOME)]
    road = game.series.road_team
    if is_owner_of(user, road) and schedule.next_unplayed_road_game(road, season_of(game)) == game:
        return [(AWAY,)]
    return []


def seat_refusal(user, game, side):
    """Why a user may not hold a side's seat in a game, or None."""
    if utils.is_sim_tester(user):
        return None
    if side != AWAY:
        return "Managers play the visiting side of their road games; the home side is the home team's computer."
    if not is_owner_of(user, game.series.road_team):
        return f"Only {game.series.road_team.abbreviation}'s manager can play this game."
    return None


def has_log(game):
    return models.GameLog.objects.filter(game=game).exists()


def can_play(user, game):
    """Whether the schedule should offer this user a Play link for the game."""
    if not user.is_authenticated or game.is_played:
        return False
    if utils.is_sim_tester(user):
        return True
    road = game.series.road_team
    return is_owner_of(user, road) and schedule.next_unplayed_road_game(road, season_of(game)) == game


# Engine cards


def fatigue_problem(fatigue):
    if not fatigue:
        return "no fatigue profile"
    if (
        (fatigue.get("season_pitches_per_appearance") or 0) <= 0
        or (fatigue.get("career_pitches_per_appearance") or 0) <= 0
        or not fatigue.get("age")
    ):
        return "an incomplete fatigue profile"
    return None


def hitter_card_problem(player, card):
    if card is None:
        return f"{player.name} has no card."
    if not card.hitter_rates:
        return f"{player.name}'s card has no batting line."
    return None


def pitcher_card_problem(player, card):
    if card is None:
        return f"{player.name} has no card."
    if not card.pitcher_rates:
        return f"{player.name}'s card has no pitching line."
    problem = fatigue_problem(card.fatigue)
    if problem:
        return f"{player.name}'s card has {problem}."
    return None


def batter_card(player, card, position):
    """The engine BatterCard for a player at a position. A position with no rating, or DH, is 0."""
    defense = None if position == DH else card.sim_defense_rating(position)
    data = {
        "id": str(player.id),
        "name": player.name,
        "position": position,
        "defense": defense or {"rating": 0.0, "measured_at": position},
        "wrc_plus": card.wrc_plus if card.wrc_plus is not None else DEFAULT_WRC_PLUS,
        "rates": dict(card.hitter_rates),
    }
    if card.hitter_batted_balls:
        data["batted_balls"] = dict(card.hitter_batted_balls)
    return data


def pitcher_card(player, card):
    data = {
        "id": str(player.id),
        "name": player.name,
        "defense": dict(PITCHER_DEFENSE),
        "rates": dict(card.pitcher_rates),
        "fatigue": dict(card.fatigue),
    }
    if card.pitcher_batted_balls:
        data["batted_balls"] = dict(card.pitcher_batted_balls)
    return data


def park(team):
    """The team's park for the engine: its Venue's park factor / 100, or 1.0 without one."""
    venue = models.Venue.objects.filter(team=team).first()
    factor = venue.park_factor if venue is not None else None
    return {
        "id": f"park-{team.abbreviation.lower()}",
        "run_factor": factor / 100 if factor else 1.0,
    }


def build_fixture(game, starters, lineups, cards_for):
    """The engine fixture: each side's lineup and starter, and the home team's park."""
    parks = [park(game.series.road_team), park(game.series.home_team)]
    fixture = {"postseason": False, "parks": parks, "weather": None}
    for side, team_park in zip(SIDES, parks):
        team = team_for(game, side)
        fixture[side] = {
            "id": team.abbreviation,
            "name": f"{team.city} {team.nickname}",
            "home_park_id": team_park["id"],
            "lineup": [batter_card(p, cards_for(p), position) for p, position in lineups[side]],
            "pitchers": [pitcher_card(starters[side], cards_for(starters[side]))],
        }
    return fixture


def pitch_around(hitter_rates):
    """The hitter's rates with bb multiplied by PITCH_AROUND_BB_MULT and the others scaled to keep the sum at 1."""
    bb = hitter_rates["bb"]
    raised = min(bb * PITCH_AROUND_BB_MULT, 1.0)
    rest = 1.0 - bb
    scale = (1.0 - raised) / rest if rest > 0 else 0.0
    return {key: (raised if key == "bb" else value * scale) for key, value in hitter_rates.items()}


# The engine state


def batting_side(state):
    return AWAY if state["half"] == "top" else HOME


def fielding_side(state):
    return other_side(batting_side(state))


def current_batter_id(state):
    club = state[batting_side(state)]
    return club["lineup"][club["batter_index"]]["id"]


def current_pitcher_id(state):
    return state[fielding_side(state)]["pitcher_slot"]


def is_final(state):
    return state is not None and state["status"] == "final"


def used_ids(state, side):
    """Engine ids of everyone who has been in the game for a side."""
    club = state[side]
    return set(club["in_game"]) | set(club["unavailable"]) | {b["id"] for b in club["lineup"]}


def with_rates(state, hitter_rates, pitcher_rates):
    """A copy of the state with the current batter's and pitcher's rates set for one plate appearance."""
    state = copy.deepcopy(state)
    batting = state[batting_side(state)]
    batting["lineup"][batting["batter_index"]]["rates"] = hitter_rates
    fielding = state[fielding_side(state)]
    for card in fielding["pitchers"]:
        if card["id"] == fielding["pitcher_slot"]:
            card["rates"] = pitcher_rates
    return state


def situation(state):
    return {
        "inning": state["inning"],
        "half": state["half"],
        "outs": state["outs"],
        "bases": dict(state["bases"]),
        "score": dict(state["score"]),
    }


def new_log_text(before, after):
    """The engine's log lines written between two states."""
    start = len(before["log"]) if before else 0
    return " ".join(entry["text"] for entry in after["log"][start:])


def apply_engine_event(state, event):
    """One event's effect on the engine state. Events that don't touch the engine leave it alone."""
    payload = event.payload
    if event.kind == Event.START:
        return engine_client.start(payload["fixture"], event.seed)
    if event.kind == Event.PLATE_APPEARANCE:
        inputs = payload["inputs"]
        return engine_client.step(
            with_rates(state, inputs["hitter_rates"], inputs["pitcher_rates"]),
            event.seed,
            call=inputs["call"],
            runners=inputs["runners"],
            league_spd=inputs["league_spd"],
        )["state"]
    if event.kind == Event.PITCHING_CHANGE:
        return engine_client.bring_in_pitcher(state, payload["card"], event.seed)
    if event.kind == Event.SUBSTITUTION:
        return engine_client.substitute(state, event.side, payload["index"], payload["card"])
    return state


def replay(events):
    """The engine state the events fold to, played again from the first through the engine."""
    state = None
    for event in events:
        state = apply_engine_event(state, event)
    return state


def load_state(log, events):
    """The cached state when it is current, otherwise the state replayed from the log."""
    last = events[-1].sequence if events else 0
    if log.state is not None and log.state_sequence == last:
        return log.state
    return replay(events)


# The Django side of the fold


class Fold:
    """What the log says outside the engine: who holds each seat, the opening sheet, starters, pauses and the final."""

    def __init__(self, events=()):
        self.seats = {AWAY: None, HOME: None}
        self.sheet = None
        self.league_spd = None
        self.starters = {}
        self.lineups = {}
        self.started = False
        self.first_pitch = False
        self.pause = None
        self.final = False
        for event in events:
            self.apply(event)

    def apply(self, event):
        if event.kind == Event.OPEN:
            self.sheet = event.payload["sheet"]
            self.league_spd = event.payload.get("league_spd")
        elif event.kind == Event.SEAT:
            self.seats[event.side] = event.user_id
        elif event.kind == Event.START:
            self.started = True
            self.starters = {side: pid for side, pid in event.payload["starters"].items()}
            self.lineups = event.payload["lineups"]
        elif event.kind == Event.PLATE_APPEARANCE:
            self.first_pitch = True
        elif event.kind == Event.PAUSE:
            self.pause = dict(event.payload, side=event.side)
        elif event.kind == Event.RESUME:
            self.pause = None
        elif event.kind == Event.FINAL:
            self.final = True

    def holds(self, user, side):
        return user is not None and user.is_authenticated and self.seats[side] == user.id

    def user_sides(self, user):
        return [side for side in SIDES if self.holds(user, side)]

    def is_human(self, side):
        return self.seats[side] is not None


@dataclass
class Need:
    """Something that must happen before the next plate appearance."""

    side: str
    kind: str
    reason: str
    slot: int = None
    player: object = None


@dataclass
class Option:
    player: object
    problem: str = None

    @property
    def legal(self):
        return self.problem is None


@dataclass
class Play:
    """One action on a game, inside its transaction: the locked log, its events, the state and the fold."""

    log: object
    seeds: object = engine_client.new_seed
    events: list = field(default_factory=list)
    state: dict = None
    fold: Fold = None

    def __post_init__(self):
        self.game = self.log.game
        self.season = season_of(self.game)
        self.events = list(self.log.events.order_by("sequence"))
        self.state = load_state(self.log, self.events)
        self.fold = Fold(self.events)
        self._players = {}
        self._cards = {}
        self._rosters = {}

    @property
    def sequence(self):
        return self.events[-1].sequence if self.events else 0

    def append(self, kind, *, side=None, user=None, computer=False, seed=None, payload=None, text=""):
        event = Event.objects.create(
            log=self.log,
            sequence=self.sequence + 1,
            kind=kind,
            side=side,
            user=user if user is not None and user.is_authenticated else None,
            computer=computer,
            seed=seed,
            payload=payload or {},
            text=text,
        )
        self.events.append(event)
        self.fold.apply(event)
        return event

    def save_state(self):
        self.log.state = self.state
        self.log.state_sequence = self.sequence
        self.log.save(update_fields=["state", "state_sequence", "last_modified"])

    # Lookups

    def player(self, pid):
        pid = int(pid)
        if pid not in self._players:
            self._players[pid] = models.Player.objects.get(pk=pid)
        return self._players[pid]

    def players(self, ids):
        return [self.player(i) for i in ids if i is not None]

    def card(self, player):
        if player.id not in self._cards:
            self._cards[player.id] = plans.card_for(player, self.season)
        return self._cards[player.id]

    def roster(self, side):
        """Ids of the side's players who can play in this game, read fresh so a mid-game call-up counts."""
        if side not in self._rosters:
            self._rosters[side] = roster_moves.game_roster_ids(team_for(self.game, side), self.game)
        return self._rosters[side]

    def forget_rosters(self):
        self._rosters = {}

    def sheet_side(self, side):
        return self.fold.sheet[SHEET_KEYS[side]]

    # Legality

    def batter_problem(self, side, player, position=None):
        team = team_for(self.game, side)
        if player.id not in self.roster(side):
            return f"{player.name} is not on {team.abbreviation}'s roster for this game."
        if plans.is_pitcher(player):
            return f"{player.name} is a pitcher; pitchers do not hit."
        problem = hitter_card_problem(player, self.card(player))
        if problem:
            return problem
        if position == CATCHER and (self.card(player).defense or {}).get(CATCHER) is None:
            return f"{player.name} has no catcher rating and cannot play C."
        check = usage.check_batter(player, self.game)
        return None if check.legal else check.reason

    def pitcher_problem(self, side, player, starting=False):
        team = team_for(self.game, side)
        if player.id not in self.roster(side):
            return f"{player.name} is not on {team.abbreviation}'s roster for this game."
        if not plans.can_pitch(player):
            return f"{player.name} is not a pitcher."
        problem = pitcher_card_problem(player, self.card(player))
        if problem:
            return problem
        check = usage.check_pitcher(player, self.game, starting=starting)
        return None if check.legal else check.reason

    def is_starter(self, side, player):
        return self.fold.starters.get(side) == player.id

    # Options

    def pitcher_options(self, side):
        """Every pitcher the side could bring in, in bullpen order then by name, with why not for the illegal."""
        used = used_ids(self.state, side)
        sheet = self.sheet_side(side)
        closer = self.player(sheet["closer"]) if sheet.get("closer") else None
        setup = self.players(sheet.get("setup", []))
        middle_long = self.players(sheet.get("middle_long", []))
        planned = {p.id for p in [closer, *setup, *middle_long] if p is not None}
        others = sorted(
            (
                p
                for p in models.Player.objects.filter(pk__in=self.roster(side))
                if plans.can_pitch(p) and p.id not in planned
            ),
            key=lambda p: p.name,
        )
        order = computer_manager.bullpen_order(closer, setup, middle_long, others)
        return [
            Option(p, self.pitcher_problem(side, p))
            for p in order
            if p is not None and str(p.id) not in used
        ]

    def bench_options(self, side, position):
        """Every player who could take a batting-order slot, in bench order then by name, with why not."""
        used = used_ids(self.state, side) if self.state else set()
        bench = self.players(self.sheet_side(side)["bench"])
        others = sorted(
            (
                p
                for p in models.Player.objects.filter(pk__in=self.roster(side))
                if not plans.is_pitcher(p) and p.id not in {q.id for q in bench}
            ),
            key=lambda p: p.name,
        )
        return [
            Option(p, self.batter_problem(side, p, position))
            for p in bench + others
            if str(p.id) not in used
        ]

    # What the next plate appearance needs

    def need(self):
        """The first thing that must happen before the next plate appearance, or None."""
        if not self.fold.started or is_final(self.state):
            return None
        fielding = fielding_side(self.state)
        pid = current_pitcher_id(self.state)
        if pid is None:
            return Need(fielding, PITCHER_NEED, f"{side_label(self.game, fielding)} needs a pitcher: the mound is empty.")
        pitcher = self.player(pid)
        problem = self.pitcher_problem(fielding, pitcher, starting=self.is_starter(fielding, pitcher))
        if problem:
            return Need(fielding, PITCHER_NEED, f"{pitcher.name} must come out before the next batter. {problem}", player=pitcher)
        batting = batting_side(self.state)
        batter = self.player(current_batter_id(self.state))
        problem = self.batter_problem(batting, batter)
        if problem:
            slot = self.state[batting]["batter_index"]
            return Need(
                batting,
                BATTER_NEED,
                f"{batter.name} must be replaced in the {ordinal(slot + 1)} slot before he bats again. {problem}",
                slot=slot,
                player=batter,
            )
        return None

    def options_for(self, need):
        if need.kind == PITCHER_NEED:
            return self.pitcher_options(need.side)
        position = self.state[need.side]["lineup"][need.slot]["position"]
        return self.bench_options(need.side, position)


def ordinal(n):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


# Changes the engine plays


def entered(game, player):
    """A player who enters the game gets a usage row for it, so roster moves see that he appeared."""
    models.UsageAppearance.objects.get_or_create(player=player, game=game)


def start(play, starters, lineups, user=None):
    """Set both sides' starters and lineups in the engine, before the first pitch."""
    fixture = build_fixture(play.game, starters, lineups, play.card)
    seed = play.seeds()
    state = engine_client.start(fixture, seed)
    play.append(
        Event.START,
        user=user,
        seed=seed,
        payload={
            "fixture": fixture,
            "starters": {side: starters[side].id for side in SIDES},
            "lineups": {
                side: [{"player": p.id, "position": position} for p, position in lineups[side]]
                for side in SIDES
            },
        },
        text=new_log_text(None, state),
    )
    play.state = state


def bring_in(play, side, player, *, user=None, computer=False):
    card = pitcher_card(player, play.card(player))
    replaced = play.state[side]["pitcher_slot"]
    seed = play.seeds()
    state = engine_client.bring_in_pitcher(play.state, card, seed)
    entered(play.game, player)
    play.append(
        Event.PITCHING_CHANGE,
        side=side,
        user=user,
        computer=computer,
        seed=seed,
        payload={"pitcher": player.id, "replaced": int(replaced) if replaced else None, "card": card},
        text=f"{side_label(play.game, side)}: {new_log_text(play.state, state)}",
    )
    play.state = state


def put_in_lineup(play, side, slot, player, *, user=None, computer=False):
    replaced = play.state[side]["lineup"][slot]
    position = replaced["position"]
    card = batter_card(player, play.card(player), position)
    state = engine_client.substitute(play.state, side, slot, card)
    entered(play.game, player)
    play.append(
        Event.SUBSTITUTION,
        side=side,
        user=user,
        computer=computer,
        payload={"index": slot, "player": player.id, "replaced": int(replaced["id"]), "position": position, "card": card},
        text=f"{side_label(play.game, side)}: {new_log_text(play.state, state)}",
    )
    play.state = state


def decision(play, side, text, payload=None):
    play.append(Event.DECISION, side=side, computer=True, payload=payload or {}, text=text)


def skipped_text(skipped):
    return " ".join(f"Passed over {p.name}: {reason}" for p, reason in skipped)


# Settling between plate appearances


def settle(play):
    """
    After any change: the computer makes every move its seats need, the game
    pauses when a side has no legal player, resumes when one appears, and a
    finished game is closed. A need on a human seat waits for him.
    """
    while True:
        if play.fold.final or not play.fold.started:
            return
        if is_final(play.state):
            finish(play)
            return
        need = play.need()
        if play.fold.pause is not None:
            if not resume(play, need):
                return
            continue
        if need is None:
            return
        options = play.options_for(need)
        legal = [o.player for o in options if o.legal]
        if not legal:
            pause(play, need, [o.player for o in options])
            return
        if play.fold.is_human(need.side):
            return
        computer_move(play, need, options)


def computer_move(play, need, options):
    if need.kind == PITCHER_NEED:
        choice = computer_manager.next_arm([o.player for o in options], lambda p: play.pitcher_problem(need.side, p))
        decision(
            play,
            need.side,
            f"{side_label(play.game, need.side)} computer: {need.reason} It brings in {choice.player.name}. "
            + skipped_text(choice.skipped),
            {"need": need.kind, "chose": choice.player.id, "skipped": [[p.id, r] for p, r in choice.skipped]},
        )
        bring_in(play, need.side, choice.player, computer=True)
    else:
        position = play.state[need.side]["lineup"][need.slot]["position"]
        choice = computer_manager.bench_replacement(
            [o.player for o in options], lambda p: play.batter_problem(need.side, p, position)
        )
        decision(
            play,
            need.side,
            f"{side_label(play.game, need.side)} computer: {need.reason} {choice.player.name} takes his place. "
            + skipped_text(choice.skipped),
            {"need": need.kind, "chose": choice.player.id, "skipped": [[p.id, r] for p, r in choice.skipped]},
        )
        put_in_lineup(play, need.side, need.slot, choice.player, computer=True)


def pause(play, need, candidates):
    team = team_for(play.game, need.side)
    reason = f"{team.abbreviation} has no legal {'pitcher' if need.kind == PITCHER_NEED else 'replacement'}. {need.reason}"
    paused = None
    if need.kind == PITCHER_NEED:
        paused = usage.pause_if_no_legal_pitcher(play.game, team, candidates)
    if paused is None:
        paused, _ = models.UsagePause.objects.get_or_create(
            game=play.game, team=team, resolved_at=None, defaults={"reason": reason}
        )
    play.append(
        Event.PAUSE,
        side=need.side,
        computer=True,
        payload={"pause": paused.id, "kind": need.kind, "reason": reason},
        text=f"Paused for the commissioner: {reason} A roster move or a usage override resumes it.",
    )


def resume(play, need):
    """Resume a paused game once the side it waits on has a legal player. Returns whether it resumed."""
    paused = models.UsagePause.objects.filter(pk=play.fold.pause["pause"]).first()
    if need is not None:
        legal = [o.player for o in play.options_for(need) if o.legal]
        if not legal:
            return False
    if paused is not None and paused.resolved_at is None:
        paused.resolved_at = timezone.now()
        paused.save(update_fields=["resolved_at", "last_modified"])
    play.append(Event.RESUME, side=play.fold.pause["side"], computer=True, text="Resumed: the side has a legal player again.")
    return True


def finish(play):
    score = play.state["score"]
    game = play.game
    game.road_score = score["away"]
    game.home_score = score["home"]
    game.save(update_fields=["road_score", "home_score", "last_modified"])
    play.append(
        Event.FINAL,
        computer=True,
        payload={"score": dict(score)},
        text=f"Final: {side_label(game, AWAY)} {score['away']}, {side_label(game, HOME)} {score['home']}.",
    )
    # The season's 6-ulmg lines and both clubs' records, summed again from the logs.
    season_record.record_final(play.log)


# Actions


def _begin(log, expected, seeds):
    log = models.GameLog.objects.select_for_update().select_related(
        "game__series__slot", "game__series__home_team", "game__series__road_team"
    ).get(pk=log.pk)
    play = Play(log, seeds)
    try:
        position = int(expected)
    except (TypeError, ValueError):
        raise GameRefused(STALE)
    if position != play.sequence:
        raise GameRefused(STALE)
    return play


def _require_seat(play, user, side=None):
    sides = [side] if side else SIDES
    if not any(play.fold.holds(user, s) for s in sides):
        if side:
            raise GameRefused(f"You don't hold the {side_label(play.game, side)} seat in this game.")
        raise GameRefused("You don't hold a seat in this game.")


def _require_in_progress(play):
    if play.fold.final:
        raise GameRefused("The game is final.")
    if not play.fold.started:
        raise GameRefused("The game has not started.")


def _sheet_starter_and_lineup(play, side):
    sheet = play.sheet_side(side)
    starter = play.player(sheet["starter"]) if sheet.get("starter") else None
    lineup = [(play.player(e["player"]), e["position"]) for e in sheet.get("lineup") or []]
    return starter, lineup


def _filed_card_problems(play, side):
    sheet = play.sheet_side(side)
    problems = []
    pitchers = play.players([sheet.get("starter"), sheet.get("closer"), *sheet.get("setup", []), *sheet.get("middle_long", [])])
    hitters = play.players([e["player"] for e in sheet.get("lineup") or []] + list(sheet.get("bench", [])))
    for p in pitchers:
        problem = pitcher_card_problem(p, play.card(p))
        if problem:
            problems.append(problem)
    for p in hitters:
        problem = hitter_card_problem(p, play.card(p))
        if problem:
            problems.append(problem)
    return problems


def _opening_starter(play, side, human, planned):
    """The side's starter at the opening, with the computer's replacement for an illegal one."""
    team = team_for(play.game, side)
    problem = play.pitcher_problem(side, planned, starting=True)
    if problem is None:
        return planned, None
    if human:
        return None, (
            f"Your planned starter {planned.name} cannot start: {problem} Spot-start another pitcher "
            f"for day {play.game.day} in your plan, then open the game."
        )
    plan = plans.find_plan(team, play.season, play.game.series.slot.half)
    rotation = play.players(plan.rotation if plan else [])
    choice = computer_manager.starter(planned, rotation, lambda p: play.pitcher_problem(side, p, starting=True))
    if choice.player is None:
        return None, f"{team.abbreviation} has no legal starter for day {play.game.day}. {skipped_text(choice.skipped)}"
    decision(
        play,
        side,
        f"{team.abbreviation} computer: {skipped_text(choice.skipped)} {choice.player.name} starts instead, "
        "the next legal pitcher in the rotation.",
        {"need": "starter", "chose": choice.player.id, "skipped": [[p.id, r] for p, r in choice.skipped]},
    )
    return choice.player, None


def _opening_lineup(play, side, planned, starter):
    """The side's lineup at the opening: a capped or unavailable planned batter gives way to the bench order."""
    team = team_for(play.game, side)
    lineup = []
    taken = {p.id for p, _ in planned} | {starter.id}
    problems = []
    for player, position in planned:
        problem = play.batter_problem(side, player)
        if problem is None:
            lineup.append((player, position))
            continue
        bench = [p for p in play.players(play.sheet_side(side)["bench"]) if p.id not in taken]
        choice = computer_manager.bench_replacement(bench, lambda p: play.batter_problem(side, p, position))
        if choice.player is None:
            problems.append(
                f"{team.abbreviation}'s {player.name} cannot play ({problem}) and no one on the bench can replace him at {position}."
            )
            continue
        taken.add(choice.player.id)
        decision(
            play,
            side,
            f"{team.abbreviation} computer: {player.name} cannot play. {problem} {choice.player.name}, "
            f"the first legal player in the bench order, takes his place at {position}. {skipped_text(choice.skipped)}",
            {"need": "lineup", "replaced": player.id, "chose": choice.player.id,
             "skipped": [[p.id, r] for p, r in choice.skipped]},
        )
        lineup.append((choice.player, position))
    return lineup, problems


def open_game(game, user, seats, seeds=engine_client.new_seed):
    """
    Open an unplayed game and start its log. seats are the sides the user
    takes; a side nobody holds is played by its team's computer. Both
    teams' plans for the day are frozen and copied into the log. Raises
    GameRefused, with nothing saved, when the user may not open it this way,
    a filed player has no card, or a starter or lineup can't be set.
    """
    seats = tuple(side for side in SIDES if side in set(seats))
    if not seats:
        raise GameRefused("Pick a seat to play.")
    with transaction.atomic():
        game = (
            models.ScheduleGame.objects.select_for_update()
            .select_related("series__slot", "series__home_team", "series__road_team")
            .get(pk=game.pk)
        )
        if has_log(game):
            raise GameRefused("This game is already open.")
        if seats not in open_seat_choices(user, game):
            reasons = [r for r in (seat_refusal(user, game, side) for side in seats) if r]
            raise GameRefused(reasons or ["You can open only your team's next unplayed road game."])

        frozen = plans.open_game(game)
        game.refresh_from_db()
        log = models.GameLog.objects.create(game=game)
        play = Play(log, seeds)
        play.game = game
        card_season = play.season - 1
        play.append(
            Event.OPEN,
            user=user,
            payload={"sheet": frozen, "card_season": card_season, "league_spd": models.Card.league_spd(card_season)},
            text=f"{game}: opened.",
        )
        for side in SIDES:
            holder = user if side in seats else None
            play.append(
                Event.SEAT,
                side=side,
                user=holder,
                text=f"{side_label(game, side)} seat: {holder.username if holder else 'the computer'}.",
            )

        problems = []
        for side in SIDES:
            team = team_for(game, side)
            sheet = play.sheet_side(side)
            if not sheet.get("starter") or len(sheet.get("lineup") or []) != plans.LINEUP_SIZE:
                problems.append(f"{team.abbreviation} has no planned starter and lineup for day {game.day}.")
                continue
            problems += _filed_card_problems(play, side)
        if problems:
            raise GameRefused(problems)

        starters, lineups = {}, {}
        for side in SIDES:
            planned_starter, planned_lineup = _sheet_starter_and_lineup(play, side)
            starter, problem = _opening_starter(play, side, side in seats, planned_starter)
            if problem:
                problems.append(problem)
                continue
            starters[side] = starter
            lineups[side], lineup_problems = _opening_lineup(play, side, planned_lineup, starter)
            problems += lineup_problems
        if problems:
            raise GameRefused(problems)

        start(play, starters, lineups, user=user)
        settle(play)
        play.save_state()
    return log


def change_lineup(log, user, side, entries, expected, seeds=engine_client.new_seed):
    """
    Before the first pitch, the side's holder may change his lineup for this
    game only, from the players on its roster for this game. entries are
    plans-style dicts of order, player and position.
    """
    with transaction.atomic():
        play = _begin(log, expected, seeds)
        _require_seat(play, user, side)
        _require_in_progress(play)
        if play.fold.first_pitch:
            raise GameRefused("The lineup can change only before the first pitch.")
        team = team_for(play.game, side)
        roster = play.roster(side)

        def roster_problem(player):
            if player.id not in roster:
                return f"{player.name} is not on {team.abbreviation}'s roster for this game."
            return None

        errors = plans.lineup_errors(team, play.season, entries, "Lineup", roster_problem)
        if not errors:
            for entry in entries:
                problem = play.batter_problem(side, entry["player"], entry["position"])
                if problem:
                    errors.append(problem)
        if errors:
            raise GameRefused(plans._unique_errors(errors))

        lineup = [(e["player"], e["position"]) for e in sorted(entries, key=lambda e: e["order"])]
        lineups = {
            s: [(play.player(e["player"]), e["position"]) for e in play.fold.lineups[s]] for s in SIDES
        }
        lineups[side] = lineup
        starters = {s: play.player(play.fold.starters[s]) for s in SIDES}
        play.append(
            Event.LINEUP,
            side=side,
            user=user,
            payload={"lineup": [{"player": p.id, "position": pos} for p, pos in lineup]},
            text=f"{team.abbreviation} changes its lineup: "
            + ", ".join(f"{p.name} {pos}" for p, pos in lineup) + ".",
        )
        start(play, starters, lineups, user=user)
        settle(play)
        play.save_state()


def change_pitcher(log, user, side, player, expected, seeds=engine_client.new_seed):
    """A pitching change by the side's holder while his club is in the field. A removed pitcher can't re-enter."""
    with transaction.atomic():
        play = _begin(log, expected, seeds)
        _require_seat(play, user, side)
        _require_in_progress(play)
        if fielding_side(play.state) != side:
            raise GameRefused("You can change pitchers while your club is in the field.")
        need = play.need()
        if not play.fold.first_pitch and not (need and need.kind == PITCHER_NEED and need.side == side):
            raise GameRefused(
                "Before the first pitch, change starters by spot-starting another pitcher in your plan."
            )
        if str(player.id) in set(play.state[side]["unavailable"]):
            raise GameRefused(f"{player.name} has already come out of this game and cannot re-enter.")
        if str(player.id) == play.state[side]["pitcher_slot"]:
            raise GameRefused(f"{player.name} is already pitching.")
        if str(player.id) in used_ids(play.state, side):
            raise GameRefused(f"{player.name} is already in this game.")
        problem = play.pitcher_problem(side, player)
        if problem:
            raise GameRefused(problem)
        bring_in(play, side, player, user=user)
        settle(play)
        play.save_state()


def replace_batter(log, user, side, player, expected, seeds=engine_client.new_seed):
    """The side's holder replaces a batter who can't bat again, in his slot and at his position."""
    with transaction.atomic():
        play = _begin(log, expected, seeds)
        _require_seat(play, user, side)
        _require_in_progress(play)
        need = play.need()
        if need is None or need.kind != BATTER_NEED or need.side != side:
            raise GameRefused("No batter of yours needs replacing. Other substitutions arrive with #170.")
        position = play.state[side]["lineup"][need.slot]["position"]
        if str(player.id) in used_ids(play.state, side):
            raise GameRefused(f"{player.name} has already been in this game.")
        problem = play.batter_problem(side, player, position)
        if problem:
            raise GameRefused(problem)
        put_in_lineup(play, side, need.slot, player, user=user)
        settle(play)
        play.save_state()


def make_roster_move(log, user, side, player_up, player_down, expected, seeds=engine_client.new_seed):
    """A #163 roster move during the game by the side's holder, when he may make that team's moves."""
    with transaction.atomic():
        play = _begin(log, expected, seeds)
        _require_seat(play, user, side)
        _require_in_progress(play)
        team = team_for(play.game, side)
        if not plans.can_edit(user, team):
            raise GameRefused(f"Only {team.abbreviation}'s owner and the commissioner can make its roster moves.")
        slot = play.game.series.slot
        try:
            move = roster_moves.make_move(team, player_up, player_down, season=slot.season, half=slot.half, user=user)
        except roster_moves.MoveError as error:
            raise GameRefused(str(error))
        play.forget_rosters()
        play.append(
            Event.ROSTER_MOVE,
            side=side,
            user=user,
            payload={"move": move.id, "up": player_up.id, "down": player_down.id},
            text=f"{team.abbreviation} calls up {player_up.name} and sends down {player_down.name}.",
        )
        settle(play)
        play.save_state()


def take_seat(log, user, side, expected, seeds=engine_client.new_seed):
    with transaction.atomic():
        play = _begin(log, expected, seeds)
        if play.fold.final:
            raise GameRefused("The game is final.")
        refusal = seat_refusal(user, play.game, side)
        if refusal:
            raise GameRefused(refusal)
        holder = play.fold.seats[side]
        if holder is not None:
            if holder == user.id:
                raise GameRefused(f"You already hold the {side_label(play.game, side)} seat.")
            raise GameRefused(f"Someone else holds the {side_label(play.game, side)} seat.")
        play.append(Event.SEAT, side=side, user=user, text=f"{side_label(play.game, side)} seat: {user.username}.")
        settle(play)
        play.save_state()


def leave_seat(log, user, side, expected, seeds=engine_client.new_seed):
    with transaction.atomic():
        play = _begin(log, expected, seeds)
        _require_seat(play, user, side)
        if play.fold.final:
            raise GameRefused("The game is final.")
        play.append(
            Event.SEAT,
            side=side,
            user=None,
            text=f"{side_label(play.game, side)} seat: {user.username} leaves it to the computer.",
        )
        settle(play)
        play.save_state()


def check_pause(log, user, expected, seeds=engine_client.new_seed):
    """Look again at a paused game: it resumes when the side now has a legal player."""
    with transaction.atomic():
        play = _begin(log, expected, seeds)
        _require_seat(play, user)
        settle(play)
        play.save_state()


def runner_ratings(play, state):
    runners = {}
    for base in ("first", "second", "third"):
        runner = state["bases"].get(base)
        if runner is None:
            continue
        card = play.card(play.player(runner))
        if card is not None:
            runners[base] = card.runner_rating(runner)
    return runners


def plate_appearance_inputs(play, call):
    """The batter, pitcher and everything the engine's step is given for the next plate appearance."""
    state = play.state
    batting, fielding = batting_side(state), fielding_side(state)
    batter = play.player(current_batter_id(state))
    pitcher = play.player(current_pitcher_id(state))
    rates = cards.plate_appearance_rates(play.card(batter), play.card(pitcher), batter.bats, pitcher.throws)
    hitter_rates = dict(rates["hitter_rates"])
    if call == PITCH_AROUND:
        hitter_rates = pitch_around(hitter_rates)
    if call in OFFENSE_CALLS or call == "intentional_walk":
        engine_call = call
    elif play.fold.is_human(batting):
        engine_call = NO_CALL
    else:
        engine_call = None
    return batter, pitcher, {
        "call": engine_call,
        "pitch_around": call == PITCH_AROUND,
        "hitter_rates": hitter_rates,
        "pitcher_rates": dict(rates["pitcher_rates"]),
        "runners": runner_ratings(play, state),
        "league_spd": play.fold.league_spd,
    }


def step(log, user, expected, call=None, seeds=engine_client.new_seed):
    """
    Play one plate appearance. expected is the log position the page was
    showing; a duplicate or stale request plays nothing. The usage ledger
    counts the plate appearance in the same transaction as the log append.
    """
    call = call or None
    with transaction.atomic():
        play = _begin(log, expected, seeds)
        _require_seat(play, user)
        _require_in_progress(play)
        if play.fold.pause is not None:
            raise GameRefused(f"The game is paused. {play.fold.pause['reason']}")
        need = play.need()
        if need is not None:
            raise GameRefused(need.reason)
        batting, fielding = batting_side(play.state), fielding_side(play.state)
        if call is not None:
            if call in OFFENSE_CALLS:
                caller = batting
            elif call in DEFENSE_CALLS:
                caller = fielding
            else:
                raise GameRefused(f"{call} is not a call.")
            if not play.fold.holds(user, caller):
                raise GameRefused(f"{CALL_LABELS[call]} is {side_label(play.game, caller)}'s call to make.")
            play.append(
                Event.CALL,
                side=caller,
                user=user,
                payload={"call": call},
                text=f"{side_label(play.game, caller)} calls {CALL_LABELS[call].lower()}.",
            )

        if not play.fold.first_pitch:
            for side in SIDES:
                for entry in play.state[side]["lineup"]:
                    entered(play.game, play.player(entry["id"]))
                entered(play.game, play.player(play.state[side]["pitcher_slot"]))

        batter, pitcher, inputs = plate_appearance_inputs(play, call)
        seed = play.seeds()
        before = situation(play.state)
        stepped = engine_client.step(
            with_rates(play.state, inputs["hitter_rates"], inputs["pitcher_rates"]),
            seed,
            call=inputs["call"],
            runners=inputs["runners"],
            league_spd=inputs["league_spd"],
        )
        result = stepped["result"]
        completed = result["batter_completed"]
        try:
            usage.record_plate_appearance(
                play.game,
                batter if completed else None,
                pitcher,
                at_bat=completed and result["outcome"] not in NOT_AT_BATS,
                outs=result["change"]["outs_added"],
                pitches=len(result["pitches"]),
                pitcher_starting=play.is_starter(fielding, pitcher),
            )
        except usage.UsageViolation as violation:
            raise GameRefused(violation.check.reason)
        play.append(
            Event.PLATE_APPEARANCE,
            side=batting,
            user=user,
            seed=seed,
            payload={
                "inputs": inputs,
                "batting": batting,
                "batter": batter.id,
                "pitcher": pitcher.id,
                "before": before,
                "result": result,
            },
            text=new_log_text(play.state, stepped["state"]),
        )
        play.state = stepped["state"]
        settle(play)
        play.save_state()


# Reading the game for its page


def _usage_line(play, side, player, pitching):
    """Remaining usage for one player, for the page."""
    summary = usage.usage_summary(player, play.season)
    if not pitching:
        left = summary["plate_appearances_left"]
        return f"PA left: {'unlimited' if left is None else left}"
    check = usage.check_pitcher(player, play.game, starting=play.is_starter(side, player))
    remaining = check.remaining
    season_outs = remaining.get("season_outs")
    innings = "unlimited" if season_outs is None else usage.outs_to_innings(season_outs)
    return (
        f"Starts left: {remaining.get('starts')} · IP left this season: {innings} · "
        f"IP left this outing: {usage.outs_to_innings(remaining.get('game_outs') or 0)}"
    )


def _player_block(play, side, player, pitching):
    if player is None:
        return None
    card = play.card(player)
    return {
        "player": player,
        "side": side,
        "team": team_for(play.game, side),
        "card": card,
        "lines": (card.pitcher_lines() if pitching else card.hitter_lines()) if card else [],
        "usage": _usage_line(play, side, player, pitching),
    }


MATCHUP_LABELS = [
    ("k", "Strikeout"),
    ("bb", "Walk"),
    ("hbp", "Hit by pitch"),
    ("single", "Single"),
    ("double", "Double"),
    ("triple", "Triple"),
    ("hr", "Home run"),
    ("bip_out", "Out in play"),
]


def matchup(play):
    """The engine's outcome probabilities for the next normal plate appearance, with the platoon split rates."""
    _, _, inputs = plate_appearance_inputs(play, None)
    odds = engine_client.matchup(with_rates(play.state, inputs["hitter_rates"], inputs["pitcher_rates"]))
    return [(label, odds["probabilities"][key] * 100) for key, label in MATCHUP_LABELS]


def _lineup_rows(play, side):
    """The side's current lineup in batting order, for the pregame lineup form."""
    return [
        {"order": i + 1, "player_id": int(entry["id"]), "position": entry["position"]}
        for i, entry in enumerate(play.state[side]["lineup"])
    ]


def page(log, user):
    """Everything the game page shows: the situation, both cards, the odds, usage, choices and the play-by-play."""
    play = Play(log)
    game, state, fold = play.game, play.state, play.fold
    context = {
        "game": game,
        "log": log,
        "expected": play.sequence,
        "final": fold.final,
        "paused": fold.pause,
        "user_sides": fold.user_sides(user),
        "events": [e for e in reversed(play.events) if e.text],
        "box": box_score.box_score(log),
    }
    users = models.User.objects.in_bulk([uid for uid in fold.seats.values() if uid])
    context["seats"] = [
        {
            "side": side,
            "team": team_for(game, side),
            "holder": users.get(fold.seats[side]),
            "mine": fold.holds(user, side),
            "can_take": not fold.final
            and fold.seats[side] is None
            and seat_refusal(user, game, side) is None,
        }
        for side in SIDES
    ]
    if state is None or fold.final:
        return context

    batting, fielding = batting_side(state), fielding_side(state)
    pitcher_id = current_pitcher_id(state)
    pitcher = play.player(pitcher_id) if pitcher_id else None
    batter = play.player(current_batter_id(state))
    need = play.need()
    context.update(
        {
            "inning": state["inning"],
            "half": "Top" if state["half"] == "top" else "Bottom",
            "outs": state["outs"],
            "score": state["score"],
            "away_team": team_for(game, AWAY),
            "home_team": team_for(game, HOME),
            "runners": [
                (base, play.player(state["bases"][base]))
                for base in ("first", "second", "third")
                if state["bases"].get(base)
            ],
            "batting_team": team_for(game, batting),
            "fielding_team": team_for(game, fielding),
            "batter": _player_block(play, batting, batter, pitching=False),
            "pitcher": _player_block(play, fielding, pitcher, pitching=True),
            "need": need,
            "first_pitch": fold.first_pitch,
            "can_step": bool(context["user_sides"]) and need is None and fold.pause is None,
        }
    )
    if need is None and pitcher is not None:
        context["matchup"] = matchup(play)
    offense = OFFENSE_CALLS if fold.holds(user, batting) else ()
    defense = DEFENSE_CALLS if fold.holds(user, fielding) else ()
    context["calls"] = [(call, CALL_LABELS[call]) for call in offense + defense]
    if need is not None and fold.holds(user, need.side):
        context["need_options"] = play.options_for(need)
        context["need_mine"] = True
    if fold.holds(user, fielding) and (fold.first_pitch or (need and need.kind == PITCHER_NEED)):
        context["pitcher_options"] = play.pitcher_options(fielding)
        context["pitching_side"] = fielding

    context["pregame"] = []
    if not fold.first_pitch:
        for side in context["user_sides"]:
            roster = models.Player.objects.filter(pk__in=play.roster(side)).order_by("name")
            context["pregame"].append(
                {
                    "side": side,
                    "team": team_for(game, side),
                    "rows": _lineup_rows(play, side),
                    "hitters": [p for p in roster if not plans.is_pitcher(p)],
                    "positions": plans.LINEUP_POSITIONS,
                }
            )

    context["moves"] = [
        {
            "side": side,
            "team": team_for(game, side),
            "up": models.Player.objects.filter(team=team_for(game, side), is_ulmg_mlb_roster=False).order_by("name"),
            "down": models.Player.objects.filter(team=team_for(game, side), is_ulmg_mlb_roster=True).order_by("name"),
        }
        for side in context["user_sides"]
        if plans.can_edit(user, team_for(game, side))
    ]
    return context


SEAT_LABELS = {(AWAY,): "Away", (HOME,): "Home", (AWAY, HOME): "Both"}


def pregame(game, user):
    """The page for a game nobody has opened: both sides' plans for the day and the seats the user may take."""
    sheet = plans.game_sheet(game)
    sides = []
    for side in SIDES:
        team = team_for(game, side)
        team_sheet = sheet[SHEET_KEYS[side]]
        sides.append(
            {
                "side": side,
                "team": team,
                "starter": team_sheet["starter"],
                "lineup": team_sheet["lineup"],
                "plan_day_url": f"/teams/{team.abbreviation.lower()}/plan/{game.series.slot.half}/day/{game.day}/"
                f"?season={season_of(game)}",
                "can_edit_plan": plans.can_edit(user, team),
            }
        )
    return {
        "game": game,
        "log": None,
        "sides": sides,
        "seat_choices": [(",".join(seats), SEAT_LABELS[seats]) for seats in open_seat_choices(user, game)],
    }
