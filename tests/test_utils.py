import pytest

from ulmg import utils


def test_normalized_pos():
    for p in ["1B", "2B", "3B", "SS"]:
        assert utils.normalize_pos(p) == "IF"
        assert utils.normalize_pos(p.lower()) == "IF"

    for p in ["RF", "CF", "LF"]:
        assert utils.normalize_pos(p) == "OF"
        assert utils.normalize_pos(p.lower()) == "OF"


"""
def str_to_bool(possible_bool):
    if possible_bool:
        if possible_bool.lower() in ["y", "yes", "t", "true"]:
            return True
        if possible_bool.lower() in ["n", "no", "f", "false"]:
            return False
    return None
"""


def test_str_to_bool():
    for b in ["y", "yes", "t", "true"]:
        assert (utils.str_to_bool(b)) == True
        assert (utils.str_to_bool(b.upper())) == True

    for b in ["n", "no", "f", "false"]:
        assert (utils.str_to_bool(b)) == False
        assert (utils.str_to_bool(b.upper())) == False

    for b in ["nope", "yup", "yessir", 12345, True]:
        assert (utils.str_to_bool(b)) == None
