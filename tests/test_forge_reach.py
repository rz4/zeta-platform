"""forge.reach: a program without what no path from word 0 reaches"""
import pytest

from zeta import forge


def test_what_no_path_reaches_goes_and_the_rest_stays_in_order():
    src = ["load 5", "jz a", "call sub", "halt",
           "dead:", "push 9", "store 20", "jmp dead",
           "a:", "push 2", "halt",
           "sub:", "push 3", "ret",
           "orphan:", "push 4", "ret"]
    out = forge.reach(src)
    assert out == ["load 5", "jz a", "call sub", "halt", "dead:", "a:", "push 2", "halt", "sub:", "push 3", "ret", "orphan:"]


def test_a_branch_keeps_both_sides_and_a_jump_only_its_target():
    src = ["load 5", "load 6", "jne b", "push 5", "jmp c", "push 6", "b:", "push 7", "c:", "halt"]
    assert forge.reach(src) == ["load 5", "load 6", "jne b", "push 5", "jmp c", "b:", "push 7", "c:", "halt"]


def test_a_label_taken_as_a_value_is_refused():
    with pytest.raises(ValueError):
        forge.reach(["push a", "halt", "a:", "halt"])


def test_a_constant_stored_and_read_back_on_one_line_settles_its_branch():
    src = ["push -1", "store 40", "load 40", "push 0", "jnlt on", "jmp off",
           "on:", "push 7", "store 41",
           "off:", "halt"]
    assert forge.reach(src) == ["push -1", "store 40", "load 40", "push 0", "jnlt on", "jmp off", "on:", "off:", "halt"]
    src = ["push 0", "store 40", "load 40", "jz z", "push 1", "z:", "halt"]
    assert forge.reach(src) == ["push 0", "store 40", "load 40", "jz z", "z:", "halt"]


@pytest.mark.parametrize("between", (["mid:"], ["call f"], ["storei"], ["load 9", "store 40"]))
def test_but_not_past_a_label_a_call_an_indirect_store_or_another_value(between):
    src = ["push 5", "push 6", "push -1", "store 40"] + between + ["load 40", "push 0", "jnlt on", "jmp off",
           "on:", "push 7", "off:", "halt", "f:", "ret"]
    out = forge.reach(src)
    assert "push 7" in out
