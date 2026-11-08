# ABOUTME: The one HTTP client for the stateless baseball engine service at settings.ENGINE_URL.
# ABOUTME: Wraps /start, /step, /matchup, /pitcher, /substitute, /positions and /health; raises EngineUnavailable when it is down.
import secrets

import requests
from django.conf import settings

CONNECT_TIMEOUT_SECONDS = 2
READ_TIMEOUT_SECONDS = 10


class EngineError(Exception):
    """The engine answered and refused the request. `status` is the HTTP status it returned."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class EngineUnavailable(EngineError):
    """The engine could not be reached: ENGINE_URL is unset, nothing answered, it timed out, or it failed."""


def new_seed():
    """A fresh seed for one engine call. 63 bits, so it also fits a signed 64-bit database column."""
    return secrets.randbits(63)


def health():
    return _get("/health")


def start(fixture, seed):
    """Open a game from `fixture`. Returns the opening game state."""
    return _post("/start", {"fixture": fixture, "seed": seed})["state"]


def step(state, seed, call=None, runners=None, league_spd=None):
    """Resolve one plate appearance. Returns {"result": ..., "state": ...}.

    `call` is None for a normal plate appearance (the computer manager decides), "none" for
    a plate appearance with no call at all, or one of
    "bunt", "intentional_walk", "steal", "hit_and_run", "infield_in". The infield-in call is
    honored only with a runner on third and fewer than two outs. The same state, call, seed, and
    runner ratings always give the same result, so record them with the plate appearance.

    `runners` holds the ratings of the runners on base, keyed by "first", "second", "third":
    each is a Card.runner_rating(). `league_spd` is Card.league_spd(card season). Leave both
    None and every runner runs at the engine's league constants.
    """
    payload = {"state": state, "call": call, "seed": seed}
    if runners is not None:
        payload["runners"] = runners
    if league_spd is not None:
        payload["league_spd"] = league_spd
    return _post("/step", payload)


def bring_in_pitcher(state, pitcher, seed):
    """
    A pitching change for the fielding club: `pitcher` is his engine PitcherCard. A pitcher
    already used in the game cannot re-enter. The seed draws his fatigue line. Returns the state.
    """
    return _post("/pitcher", {"state": state, "pitcher": pitcher, "seed": seed})["state"]


def substitute(state, side, index, batter, role=None):
    """
    Put `batter`, an engine BatterCard, in batting-order slot `index` (0-8) of `side`
    ("away" or "home"), at the position of the player he replaces, who leaves the game.
    `role` is None for a plain replacement, or "pinch_hitter" (for the batter due up),
    "pinch_runner" (for a runner on base, whose base he takes) or "defense" (while his
    club is in the field). A pinch hitter or runner for anyone but the DH is listed in
    the club's "pending" until set_positions gives him a position. Draws nothing. Returns the state.
    """
    payload = {"state": state, "side": side, "index": index, "batter": batter}
    if role is not None:
        payload["role"] = role
    return _post("/substitute", payload)["state"]


def set_positions(state, side, changes):
    """
    New fielding positions for the fielding club `side`. `changes` are dicts of index (the
    batting-order slot), position and defense (the card's engine DefenseRating there). The
    DH can't move into the field, and each field position must end with one fielder.
    Draws nothing. Returns the state.
    """
    return _post("/positions", {"state": state, "side": side, "changes": changes})["state"]


def matchup(state):
    """The outcome probabilities the next normal plate appearance will draw from. Draws nothing."""
    return _post("/matchup", {"state": state})


def _base_url():
    url = getattr(settings, "ENGINE_URL", None)
    if not url:
        raise EngineUnavailable("ENGINE_URL is not set, so the engine cannot be reached.")
    return url.rstrip("/")


def _get(path):
    url = _base_url() + path
    return _send(url, lambda: requests.get(url, timeout=_timeouts()))


def _post(path, payload):
    url = _base_url() + path
    return _send(url, lambda: requests.post(url, json=payload, timeout=_timeouts()))


def _timeouts():
    return (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS)


def _send(url, request):
    try:
        response = request()
    except requests.Timeout as err:
        raise EngineUnavailable(f"The engine at {url} did not answer in time: {err}") from err
    except requests.ConnectionError as err:
        raise EngineUnavailable(f"The engine at {url} is down or unreachable: {err}") from err
    if response.status_code >= 500:
        raise EngineUnavailable(
            f"The engine at {url} failed with HTTP {response.status_code}: {response.text[:500]}",
            status=response.status_code,
        )
    if response.status_code >= 400:
        try:
            message = response.json()["error"]
        except (ValueError, KeyError, TypeError):
            message = response.text[:500]
        raise EngineError(
            f"The engine refused {url} with HTTP {response.status_code}: {message}",
            status=response.status_code,
        )
    return response.json()
