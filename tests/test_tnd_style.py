"""TND layer 14, the yard styled (TND-PORT P97): how a body takes a blow -- the fall by what put it down, a hook's
turn, the wall. The yard's own tests (tests/test_tnd_yard.py) are layer 13's, which is built as it was."""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import test_tnd_yard as Y13                                    # noqa: E402  (its room, its helpers)
from zeta import gpu, spec                                     # noqa: E402

CART = ROOT / "build" / "layer14" / "tnd.zol"
X, Yb, B, R, D = spec.PAD_X, spec.PAD_Y, spec.PAD_B, spec.PAD_R, spec.PAD_DOWN
pytestmark = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "falls_190.npz").is_file(), reason="tools/tnd_falls.py has not been run")


@pytest.fixture(scope="module")
def cart():
    if not CART.is_file() or CART.stat().st_mtime < Y13.GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="14")
        for k in ("TND_SONG", "TND_OUT", "TND_CROWD", "TND_CARTMESH", "TND_AT"):
            env.pop(k, None)
        subprocess.run([sys.executable, str(Y13.GEN)], check=True, env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    return CART


@pytest.fixture(autouse=True)
def no_paint(monkeypatch):
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)


def _before_him(cart, v0=0.0, u0=0.0, hp=None):
    """the elite a pace before him, the rest away"""
    y = Y13.Yard(cart)
    g = y.g
    y.who(3)
    for k in range(7):
        Y13._stand(y, k, 28.0 - k, -15.0)
    Y13._stand(y, 0, u0, v0 + 1.1)
    y.put(u0, v0, 256)
    for _ in range(5):
        g.step(0)
    if hp:
        g.d[g.syms["e0_hp"]] = hp
    return y, g


def _play(y, g, keys):
    """-> the frame it went down (or None), how far it went from where it stood, what was seen of it while held"""
    v0, down, struck = y.body(0), None, set()
    for i, q in enumerate(keys):
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
        if down is None and g.cell("e0_st") == 2:
            down = i
        if g.cell("e0_stun"):
            struck.add(g.cell("yard_struck"))
    v1 = y.body(0)
    return down, float(np.hypot(v1[0] - v0[0], v1[1] - v0[1])), struck


def test_a_body_goes_down_by_what_put_it_down(cart):
    """P97 ("hyperviolent is not just gore, its about making the fighting correagraphy be hyperviolent"): every body
    went down the one way, thrown back. Now a light blow or a round to the HEAD drops it where it stood (1), to the
    BODY folds it onto its knees and its face (2), to the LEGS cuts it down (3); a heavy blow throws it (0) as it
    did -- and what drops, folds or is cut down stays where it stood"""
    aim_low = [R] * 12 + [R | D] * 3 + [R] * 4 + [R | B] * 3 + [R] * 60
    for name, keys, want, hp in (("a jab, to its head", [X] * 3 + [0] * 60, 1, 1), ("a round, to its body", [B] * 3 + [0] * 60, 2, 1),
                                 ("a round, to its legs", aim_low, 3, 1), ("a charged round", [R | B] * 70 + [R] * 60, 0, None)):
        y, g = _before_him(cart, hp=hp)
        down, went, _ = _play(y, g, keys)
        assert down is not None, f"{name}: it did not go down"
        assert g.cell("yard_fall") == want, f"{name}: fell as {g.cell('yard_fall')}, not {want}"
        if want:
            assert went < 0.5, f"{name}: it went {went:.2f} from where it stood"
        else:
            assert went > 0.8, f"{name}: thrown, it went only {went:.2f}"


def test_a_hook_turns_it_and_a_jab_does_not(cart):
    """P97: a hook landed is a hook's reaction -- the head and shoulders turned away from the hand (2 the lead's,
    3 the rear's); a jab is the chin taken back, as it was"""
    y, g = _before_him(cart)
    assert _play(y, g, [Yb] * 3 + [0] * 50)[2] == {spec_move("lead_hook")}
    y, g = _before_him(cart)
    assert _play(y, g, [X] * 3 + [0] * 30)[2] == {0}


def spec_move(name):
    return {"lead_hook": 2, "rear_hook": 3}[name]


def test_the_wall_strikes_a_body_sent_into_it(cart):
    """P97: a body a blow sends along the floor into a wall, still moving, is STRUCK by the wall: one more off it,
    its chin back and held, the lens shaken -- and if that is the last of it, it folds off the wall. A jab sends
    nothing that far; in the open nothing strikes it"""
    def hits(keys, v0, hp=None):
        y, g = _before_him(cart, v0=v0, u0=-10.0, hp=hp)
        seen, last, shook = [], g.cell("e0_hp"), 0
        for q in keys:
            g.d[g.syms["p_hp"]] = 140
            g.step(q)
            if g.cell("e0_hp") != last:
                last = g.cell("e0_hp")
                seen.append((last, g.cell("yard_struck"), g.cell("e0_stun"), g.cell("f_shake")))
        return seen, g
    hook, jab = [Yb] * 3 + [0] * 70, [X] * 3 + [0] * 70
    by_wall, g = hits(hook, 13.7)
    assert len(by_wall) == 2 and by_wall[1][0] == by_wall[0][0] - 1, f"a hook by the wall: {by_wall}"
    assert by_wall[1][1] == 0 and by_wall[1][2] >= 20 and by_wall[1][3] >= 8, f"the wall's blow: {by_wall[1]}"
    assert g.cell("e0_st") == 1
    last, g = hits(hook, 13.7, hp=4)
    assert last[-1][0] == 0 and g.cell("e0_st") == 2 and g.cell("yard_fall") == 2, f"the wall took the last of it: {last}"
    assert len(hits(jab, 13.7)[0]) == 1, "a jab by the wall"
    assert len(hits(hook, 0.0)[0]) == 1, "a hook in the open"
