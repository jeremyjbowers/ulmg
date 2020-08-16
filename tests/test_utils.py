import pytest

from ulmg import utils


def test_normalized_pos():
    for if_pos in ["1B", "2B", "3B", "SS"]:
        assert utils.normalize_pos(if_pos) == "IF"
        assert utils.normalize_pos(if_pos.lower()) == "IF"

    for of_pos in ["RF", "CF", "LF"]:
        assert utils.normalize_pos(of_pos) == "OF"
        assert utils.normalize_pos(of_pos.lower()) == "OF"
