# ABOUTME: The one HTTP client for the stateless baseball engine service at settings.ENGINE_URL.
# ABOUTME: Wraps /start, /step, /matchup, and /health with timeouts and raises EngineUnavailable when it is down.
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


def step(state, seed, call=None):
    """Resolve one plate appearance. Returns {"result": ..., "state": ...}.

    `call` is None for a normal plate appearance (the computer manager decides), or one of
    "bunt", "intentional_walk", "steal", "hit_and_run". The same state, call, and seed always
    give the same result, so record the seed with the plate appearance.
    """
    return _post("/step", {"state": state, "call": call, "seed": seed})


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
