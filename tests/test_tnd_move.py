"""TND's lab and reactor, P48 (docs/TND-PORT.md): exact dodges, and where he will land.

The player, 2026-11-23: "for the boxing I think we want an exact left right up
down flip jump, not the double press one, this is to quick dodge maybe two
units, the none boxing is a single unit dodge. The running should feel very
good at figuring out where your jump and double jump (flip) should land, maybe
having the camera also cover the ground to see where you are going to land.
over all this positioning tackcially."

A unit is his own width (the reactor's check).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_tnd_lab as LAB                                  # noqa: E402
import test_tnd_reactor as RX                               # noqa: E402
from test_tnd_lab import no_paint, pytestmark               # noqa: E402,F401

A, L, R, U, D, LF, RT = RX.A, RX.L, RX.R, RX.U, RX.D, RX.LF, RX.RT
W = RX.W
ONE = 65536


def _fresh(mod, layer):
    """the cart's text, rebuilt if the generator is newer (as the lab's and the reactor's own tests do)"""
    import os
    import subprocess
    if not mod.CART.is_file() or mod.CART.stat().st_mtime < mod.GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER=layer)
        for k in ("TND_SONG", "TND_OUT", "TND_CROWD", "TND_CARTMESH", "TND_AT"):
            env.pop(k, None)
        subprocess.run([sys.executable, str(mod.GEN)], check=True, env=env, cwd=mod.ROOT, stdout=subprocess.DEVNULL)
    return mod.CART.read_text().splitlines()


@pytest.fixture(scope="module")
def rx_text():
    return _fresh(RX, "11")


@pytest.fixture(scope="module")
def lab_text():
    return _fresh(LAB, "10")


def went(g, pads, hold=0, tail=40):
    """(east, north) he went, in his widths; how high; frames in the air"""
    u0, v0 = g.uv()
    g.run(hold | pads | A, 3)
    high = air = 0
    for _ in range(tail):
        g.run(hold, 1)
        high = max(high, g.cell("f_py"))
        air += g.cell("f_py") > 0
    u1, v1 = g.uv()
    return round((u1 - u0) / W, 2), round((v1 - v0) / W, 2), high / ONE, air


@pytest.mark.parametrize("pad,want", [(U, (0, 1)), (LF, (-1, 0)), (RT, (1, 0)), (0, (0, -1))])
def test_the_tanks_dodge_is_one_of_his_widths_exactly(rx_text, pad, want):
    g = RX.Game(rx_text)
    g.put(0.0, 0.0, RX.NORTH)
    e, n, high, air = went(g, pad)
    assert (e, n) == want and air == 0, f"the dodge went ({e}, {n}) of his widths"
    g.poke("knobs", 2 * ONE, 13)                              # the dodge knob is that unit's length
    g.put(0.0, 0.0, RX.NORTH)
    e, n, _, _ = went(g, pad)
    assert (e, n) == (2 * want[0], 2 * want[1])


@pytest.mark.parametrize("pad,want", [(U, (0, 2)), (D, (0, -2)), (LF, (-2, 0)), (RT, (2, 0))])
def test_the_boxers_flip_is_one_press_two_widths_and_quick(rx_text, pad, want):
    g = RX.Game(rx_text)
    g.put(0.0, 0.0, RX.NORTH)
    g.run(L, 10)
    assert g.cell("f_sty") == 2
    e, n, high, air = went(g, pad, hold=L)
    assert (e, n) == want, f"the flip went ({e}, {n}) of his widths"
    assert 0.15 < high < 0.5 and air <= 12, f"it rose {high:.2f} and took {air} frames"


def test_the_flip_has_no_second_and_the_plain_jump_is_still_the_jump(rx_text):
    g = RX.Game(rx_text)
    g.put(0.0, 0.0, RX.NORTH)
    g.run(L, 10)
    u0, v0 = g.uv()
    g.run(L | LF | A, 3)
    g.run(L, 2)
    g.run(L | LF | A, 3)                                      # again, in the air: nothing
    g.run(L, 30)
    assert round((g.uv()[0] - u0) / W, 2) == -2.0
    g.put(0.0, 0.0, RX.NORTH)
    g.run(L, 10)
    e, n, high, air = went(g, 0, hold=L)
    assert (e, n) == (0, 0) and high > 1.2, "A alone in the boxer is not the jump"


def _run_up(g):
    g.put(0.0, -12.0, LAB.NORTH)
    g.run(L, 2)
    g.run(0, 3)
    g.run(L, 3)
    g.run(L | U, 70)
    assert g.cell("f_sty") == 1


def _flight(g, flip_at=None, pad=0):
    g.run(L | U | A, 3)
    marks = []
    for i in range(90):
        g.run(L | U | ((A | pad) if flip_at is not None and flip_at <= i < flip_at + 3 else 0), 1)
        if g.cell("land_on"):
            marks.append((i, g.uv(g.cell("land_x") / ONE, g.cell("land_z") / ONE)))
        if g.cell("f_py") == 0 and marks and i > 3:
            break
    landed = g.uv()
    return [(i, float(np.hypot(m[0] - landed[0], m[1] - landed[1]))) for i, m in marks]


def test_the_mark_is_where_the_runs_jump_comes_down_from_its_first_frame(lab_text):
    g = LAB.Game(lab_text)
    _run_up(g)
    off = _flight(g)
    assert len(off) > 20 and max(e for _, e in off) < 0.02, f"the mark was {max(e for _, e in off):.2f} from where he landed"
    assert g.cell("land_on") == 0, "the mark is still there with him on the floor"


@pytest.mark.parametrize("pad", [0, LF, D])
def test_the_mark_is_where_the_flip_comes_down_once_it_is_thrown(lab_text, pad):
    g = LAB.Game(lab_text)
    _run_up(g)
    off = _flight(g, flip_at=8, pad=pad)
    before = [e for i, e in off if i < 8]
    after = [e for i, e in off if i > 12]
    assert min(before) > 1.0, "the flip changed nothing: the test proves nothing"
    assert max(after) < 0.1, f"after the flip the mark was {max(after):.2f} from where he landed"


def test_in_the_air_the_lens_looks_down_and_stands_to_his_right_but_not_when_locked(lab_text):
    g = LAB.Game(lab_text)
    _run_up(g)
    g.run(L | U | A, 3)
    look = 0
    for _ in range(14):
        g.run(L | U, 1)
        look = max(look, g.cell("land_look"))
    assert look >= 15, "the lens did not look down for the floor"
    g.run(L | U, 60)
    assert g.cell("land_look") == 0, "the lens is still looking down with him on the floor"
    b = LAB.Game(lab_text)
    b.at_the_clone(3.0)
    b.run(L | R, 12)
    assert b.cell("locked") == 1
    b.run(L | R | A, 3)
    b.run(L | R, 8)
    assert b.cell("f_py") > 0 and b.cell("land_look") == 0, "locked, the lens left its work to look at the floor"
