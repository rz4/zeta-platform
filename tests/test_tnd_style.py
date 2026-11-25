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


# ---- P98: on a body that is down; rounds; bodies into bodies ---------------------------------------------------------
def _it_lies(cart):
    """the elite put down before him by a jab, and lying"""
    y, g = _before_him(cart, hp=1)
    for q in [X] * 3 + [0] * 60:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
    assert g.cell("e0_st") == 2
    return y, g


def test_a_jab_over_a_body_that_lies_before_him_is_the_stomp(cart):
    """P98 ("do all the nexxt candidates": a ground strike on X): the jab's frames in the stomp's poses -- his own
    bank's, after every pose the yard has; no step in; two off the body, which bucks where it lies and is not stood
    up to fall again. Over nothing, and on a body that stands, it is the jab"""
    y, g = _it_lies(cart)
    u0, hp, t0, poses, jolt = y.uv(), g.cell("e0_hp"), g.cell("e0_t"), set(), set()
    for q in [X] * 3 + [0] * 20:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
        if g.cell("anim") == 2 and g.cell("yard_stomp"):
            poses.add(g.cell("pose"))
        jolt.add(g.cell("yard_jolt"))
    assert poses and min(poses) >= 1362, f"his poses in the blow: {sorted(poses)[:4]}"
    assert g.cell("e0_hp") == hp - 2 and jolt >= {6, 3, 0}, (g.cell("e0_hp"), hp, sorted(jolt))
    assert np.hypot(y.uv()[0] - u0[0], y.uv()[1] - u0[1]) < 0.05, "he stepped in"
    assert g.cell("e0_st") == 2 and g.cell("e0_t") > t0, "it was stood up to fall again"
    y, g = _before_him(cart, hp=8)
    seen = set()
    for q in [X] * 3 + [0] * 20:
        g.step(q)
        seen.add(g.cell("yard_stomp"))
    assert seen == {0} and g.cell("e0_hp") < 8, "a jab on a body that stands"


def test_the_gun_goes_down_to_a_body_that_lies_before_him(cart):
    """P98 (the gun aimed down into it on B): with the gun up and nothing chosen, he bends over a body that lies
    within reach before him, and the round is fired down into it: it is struck where it lies, and no round goes on
    down the room. With nothing lying there the gun is level and the round flies"""
    y, g = _it_lies(cart)
    hp, bend, on = g.cell("e0_hp"), [], set()
    for q in [B] * 14 + [0] * 30:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
        bend.append(g.cell("aim_bend"))
        on.add(g.cell("yard_exec"))
    assert on == {0, 1} and max(bend) > 100, f"on it {sorted(on)}, his bend at most {max(bend)}"
    assert g.cell("e0_hp") == hp - 1 and g.cell("e0_st") == 2
    y, g = _before_him(cart, hp=99)
    Y13._stand(y, 0, 20.0, -15.0)                # (nobody before him)
    bend = []
    for q in [B] * 14 + [0] * 30:
        g.step(q)
        bend.append(abs(g.cell("aim_bend")))
    assert max(bend) < 20, f"with nothing there he bent {max(bend)}"


def test_a_rounds_jolt_is_its_own_and_takes_a_side_each(cart):
    """P98 (a distinct jolt for each round): a round's reaction is not a fist's -- 4 and 5 high, 6 and 7 low -- and
    rounds landing one after another throw the body one way, then the other"""
    y, g = _before_him(cart, hp=99)
    kinds = []
    for q in ([B] * 3 + [0] * 20) * 4:
        g.d[g.syms["p_hp"]] = 140
        was = g.cell("e0_hp")
        g.step(q)
        if g.cell("e0_hp") < was:
            kinds.append(g.cell("yard_struck"))
    assert len(kinds) >= 3 and all(4 <= k <= 7 for k in kinds), kinds
    assert all(a != b for a, b in zip(kinds, kinds[1:])), f"the same side twice running: {kinds}"


def test_a_body_thrown_into_another_takes_it_off_its_feet(cart):
    """P98 (bodies thrown into each other): the elite, thrown by a charged round into one of the horde standing a
    pace behind it -- that one takes one, is cut down, and has some of the throw; standing clear, nothing"""
    def thrown(v_other):
        y, g = _before_him(cart)
        Y13._stand(y, 3, 0.0, v_other)
        hp, down = g.cell("e3_hp"), 0
        for q in [R | B] * 70 + [R] * 60:
            g.d[g.syms["p_hp"]] = 140
            g.step(q)
            down |= g.cell("e3_st") == 2
        return hp - g.cell("e3_hp"), down, g.cell("yard_fall", 3), y.body(3)[1] - v_other
    took, down, fall, moved = thrown(1.3)
    assert took == 1 and down and fall == 3 and moved > 0.05, (took, down, fall, moved)
    assert thrown(4.5)[:2] == (0, 0), "a body standing clear of the throw"


def test_with_a_body_standing_there_the_blow_and_the_shot_are_its(cart):
    """P98: a body that lies at his feet does not take a jab or a round meant for one that stands before him (his
    session on P97: 420 presses of a strike or the gun within 1.6 of a body that lay)"""
    y, g = _it_lies(cart)
    u, v = y.uv()
    Y13._stand(y, 3, u, v + 1.1)                 # (one of the horde, standing over it)
    g.d[g.syms["e3_st"]], g.d[g.syms["e3_stun"]] = 1, 0
    hp, stomp = g.cell("e3_hp"), set()
    for q in [X] * 3 + [0] * 20:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
        stomp.add(g.cell("yard_stomp"))
    assert stomp == {0} and g.cell("e3_hp") < hp, f"the jab: stomp {sorted(stomp)}, the standing body {hp} -> {g.cell('e3_hp')}"
    g.d[g.syms["e3_hp"]] = 99
    on = set()
    for q in [B] * 14 + [0] * 30:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
        on.add(g.cell("yard_exec"))
    assert on == {0} and g.cell("e3_hp") < 99, f"the shot: on the floor {sorted(on)}, the standing body 99 -> {g.cell('e3_hp')}"
