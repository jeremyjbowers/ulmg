# ABOUTME: The computer manager's choices in a sim game: its starter, the next arm out of the bullpen, and bench replacements.
# ABOUTME: Each rule walks an order from the half plan and takes the first player a legality check passes; #171 replaces the bullpen rule.

from dataclasses import dataclass, field


@dataclass
class Choice:
    """The player the computer chose, or None, and the (player, reason) pairs it passed over on the way."""

    player: object = None
    skipped: list = field(default_factory=list)


def _first_legal(candidates, problem):
    """The first candidate problem() finds nothing wrong with. problem(player) returns a reason or None."""
    choice = Choice()
    seen = set()
    for player in candidates:
        if player is None or player.id in seen:
            continue
        seen.add(player.id)
        reason = problem(player)
        if reason is None:
            choice.player = player
            return choice
        choice.skipped.append((player, reason))
    return choice


def starter(planned, rotation, problem):
    """
    The computer's starter. The planned starter when he is legal; otherwise
    the next legal pitcher in rotation order after him, wrapping around. A
    planned spot starter who isn't in the rotation is followed by the
    rotation from the top.
    """
    rotation = list(rotation)
    if planned is not None and planned in rotation:
        index = rotation.index(planned)
        order = [planned] + rotation[index + 1:] + rotation[:index]
    else:
        order = [planned] + rotation
    return _first_legal(order, problem)


def bullpen_order(closer, setup, middle_long, others=()):
    """
    The order the computer takes arms in when its mound needs a pitcher: the
    closer, then setup, then middle and long relief, then any other pitcher
    on the game's roster. #171 replaces this with bullpen role rules.
    """
    return [closer, *setup, *middle_long, *others]


def next_arm(order, problem):
    """The next available arm in bullpen order that problem() passes."""
    return _first_legal(order, problem)


def bench_replacement(bench, problem):
    """The first legal player in the side's bench order."""
    return _first_legal(bench, problem)
