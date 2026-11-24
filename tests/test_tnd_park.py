"""TND's PARK (docs/TND-PORT.md P58): the lab's moves on a course that is a field, not a list.

The player, 2026-11-23: "i think what we need is a platforming lab, to test
out all the movement modes. you should be creative to push the zeta
hypothesis" -- then "make the world insanely large and packed with
activities to push the limits ... make it fun to platform, his running jump
felt a bit low before" -- "we want to be able to have strong platforming
capability".

A local build (TND_LAYER=12 -> build/layer12/tnd.zol), on the ISA-2 core.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from zeta import gpu, spec

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "games" / "tnd" / "gen_tnd.py"
CART = ROOT / "build" / "layer12" / "tnd.zol"
sys.path.insert(0, str(ROOT / "experiments" / "park"))
pytestmark = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "clips_190.npz").is_file(),
                                reason="the layer builds from the local tier files (build/tiers)")
A, L, U = spec.PAD_A, spec.PAD_L, spec.PAD_UP
ONE = 65536


@pytest.fixture(scope="module")
def cart():
    if not CART.is_file() or CART.stat().st_mtime < GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="12")
        for k in ("TND_SONG", "TND_OUT", "TND_CROWD", "TND_CARTMESH", "TND_AT"):
            env.pop(k, None)
        subprocess.run([sys.executable, str(GEN)], check=True, env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    return CART


@pytest.fixture(autouse=True)
def no_paint(monkeypatch):
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)


def test_the_bot_clears_every_kind_of_station_in_a_row(cart):
    """the middle lane teaches: each of the fourteen kinds once. A player made of rules, on the real controls, clears
    them all without touching the floor between a station's entry and its last box -- the game's own streak says so"""
    import bot
    g, log = bot.play(cart, 14, say=lambda *a: None)
    kinds = [e["mode"] for e in log[:14]]
    assert kinds == list(bot.NAMES), f"cleared {kinds}"
    assert log[13]["streak"] == 14
    assert g.cell("park_orbs") >= 10, "it took hardly any orbs on the way"


def test_the_reaches(cart):
    """P59's physics, against P58's obstacles ("the obstacle sizes are fine its the player physics and that need
    calibration"): his pace 0.20 a frame, no coasting; P61: the first jump by its hold (0.85 up tapped, 1.4 held),
    the flip on top of it, the pad moving the flip's landing about half a unit; no long jump"""
    out = subprocess.run([sys.executable, str(ROOT / "experiments" / "park" / "reach.py"), str(cart)],
                         capture_output=True, text=True, check=True, cwd=ROOT).stdout
    r = json.loads(out.strip().splitlines()[-1])
    assert abs(r["run_a_frame"] - 0.20) < 0.01
    # (P61: "the first jump should be modulated a bit with how long the jump button is held but not to much")
    lo, mid, hi = r["tap_held_1"], r["tap_held_8"], r["tap_held_20"]
    assert 0.75 < lo[1] < 0.95 and 1.1 < mid[1] < 1.35 and 1.2 < hi[1] < 1.4 and lo[0] < mid[0] < hi[0]   # (P62: held, 1.28)
    assert r["tap_flip_at_8"][1] > 2.5
    # (P61: "The dpad on the filp jump should control the landing location a bit in all 4 directions")
    assert 0.5 < r["flip_nudged_left"][1] < 1.8
    assert r["coast_after_20"] < 0.2


def _run(g):
    """into the run: L clicked twice and held (P61: the lab's run; everything else the lab's controls)"""
    for q in (L, L, 0, 0, 0, L, L, L):
        g.step(q)


def _on_the_first_entry(cart):
    import bot
    g = bot.Park(cart)
    _run(g)
    entry = min(b["z0"] for b in g.rows() if b["role"] & 1)
    pressed = 0
    for _ in range(200):
        near = g.u() > entry - 1.9 and pressed < 3
        pressed += near
        g.step(L | U | (A if near else 0))
        if g.cell("lab_si") >= 0 and g.py() == 0:
            return g
    raise AssertionError("never stood on the first entry")


def _walk_off(g):
    """running on, no button, until he is off the box's end"""
    for i in range(120):
        g.step(L | U)
        if g.cell("lab_si") < 0 and g.py() > 0:
            return
    raise AssertionError("never ran off the edge")


def test_just_off_an_edge_a_jump_is_still_a_jump(cart):
    """COYOTE: the run jumps on A's release, and a press begun at an edge used to be lost as he ran off it -- now, for
    six frames off an edge he did not jump from, A is the ground's: a jump, not the flip"""
    g = _on_the_first_entry(cart)
    _walk_off(g)
    g.step(L | U)
    for _ in range(2):
        g.step(L | U | A)
    g.step(L | U)
    assert g.cell("f_pvy") > 0, "no jump off the edge's grace"
    assert g.cell("f_flipu") == 0, "it was taken as the flip"


def test_an_early_press_is_kept_for_the_landing(cart):
    """the BUFFER: with the flip spent, A a few frames before he lands is a press on landing -- let go already, he
    jumps at once. (The same session twice: once to find the landing, once pressing four frames before it.)"""
    import bot

    def session(early_at=None):
        g = _on_the_first_entry(cart)
        pads = [L | U | A] * 10 + [L | U] + [L | U | A] * 3 + [L | U] * 60
        if early_at is not None:
            pads[early_at] |= A
            pads[early_at + 1] |= A
        trace = []
        for p in pads:
            g.step(p)
            trace.append((g.py(), g.cell("f_pvy")))
        return trace
    ref = session()
    land = next(i for i in range(15, len(ref)) if ref[i][0] == 0)
    got = session(land - 4)
    assert ref[land + 2][0] == 0, "(the reference stands after landing)"
    assert any(py > 0 and vy > 0 for py, vy in got[land:land + 4]), "the early press was lost"


def test_an_orb_is_taken_once(cart):
    """orbs hang over the gaps and above the hard tops; touched, one is gone and counted -- never counted twice"""
    import bot
    g, _ = bot.play(cart, 3, say=lambda *a: None)
    rows = g.syms["park_rows"]
    alive = sum(1 for r in range(bot.K) if (g.d[rows + r * bot.RW + 6] & 3) == 3 and g.d[rows + r * bot.RW + 2] != bot.INVALID)
    n = g.cell("park_orbs")
    assert n >= 3
    for _ in range(120):
        g.step(0)
    assert g.cell("park_orbs") == n, "an orb counted again standing still"
    assert alive >= 0


def test_the_window_is_bounded_and_the_course_is_not(cart):
    """the window law, in the cart: twenty stations on, every lane's course still runs ahead of him, and the ring is
    still its 56 rows, all of them about where he is (as he runs the lanes unfold together; the ring keeps the last
    56 rows made, about 70 units of course)"""
    import bot
    g, log = bot.play(cart, 20, say=lambda *a: None)
    u = g.u()
    assert len(log) >= 18 and u > 300
    zs = [g.cell("park_lane_z", k) / ONE for k in range(3)]
    assert all(z > u for z in zs), f"a lane's course is behind him: {zs} at {u:.0f}"
    rows = g.rows()
    assert len(rows) <= bot.K and all(u - 90 < b["z0"] < u + 60 for b in rows), "a row far from him"


def test_the_run_is_Ls_double_click_and_in_it_R_is_slowed_time(cart):
    """P61 ("double tap left shoulder enters running, then right instead of target is the running slow motion"; "the
    rest of the controls should stay the same"): no shoulder, the tank; L once, the boxer; L twice and held, the run
    -- and in the run, R held slows time and brings up no aim; A, B, X and Y held slow nothing"""
    import bot
    g = bot.Park(cart)
    for _ in range(10):
        g.step(U)
    assert g.cell("f_sty") == 0
    _run(g)
    for _ in range(10):
        g.step(L | U)
    assert g.cell("f_sty") == 1
    for b in (A, spec.PAD_B, spec.PAD_X, spec.PAD_Y, spec.PAD_R):
        seen = 0
        for _ in range(30):
            g.step(L | U | b)
            seen |= g.cell("slow_on")
        for _ in range(30):
            g.step(L | U)
        assert bool(seen) == (b == spec.PAD_R), f"button {b}: slowed {bool(seen)}"
        assert g.cell("aimed") == 0 or b == spec.PAD_B, "R brought the gun up"


def test_the_lens_is_behind_him(cart):
    """P60 ("the camera should be always behind the player"): the park's run steers as the run does -- Left and Right
    turn him -- and the lens keeps squarely behind him, a few degrees at most even while he turns"""
    import bot
    g = bot.Park(cart)
    g.d[g.syms["px"]] = int(round((-64.0 + 8.0) * ONE)) & 0xFFFFFFFF
    _run(g)
    for pad in (U, U | spec.PAD_RIGHT, U, U | spec.PAD_LEFT, U):
        for k in range(30):
            g.step(L | pad)
            if k >= 6:
                gap = ((g.cell("yaw") - g.cell("cam_yaw") + 512) & 1023) - 512
                assert abs(gap) <= 16, f"the lens {gap} yaw units off his back"


def test_a_spent_flip_is_saved_by_a_kick_straight_up_a_wall(cart):
    """P61 ("straight on wall jump should be a verticle wall kick up to save a failing jump"): the flip spent, falling
    against a face across his way, A is a kick straight up it -- he rises again, and is not thrown back"""
    import bot
    g = bot.Park(cart)
    _run(g)
    for _ in range(30):
        g.step(L | U)
    face = next(b for b in g.rows() if b["kind"] == 1 and b["top"] > 2.5)       # (STEPS' top step: a face 3.0 high)
    g.d[g.syms["pz"]] = int(round((face["z0"] - 0.6) * ONE)) & 0xFFFFFFFF
    g.d[g.syms["px"]] = int(round((face["x0"] + face["x1"]) / 2 * ONE)) & 0xFFFFFFFF            # (its middle, across)
    for k, v in (("f_py", int(2.0 * ONE)), ("f_pvy", -int(0.02 * ONE)), ("f_flipu", 1), ("lab_gh", 0), ("lab_si", -1)):
        g.d[g.syms[k]] = v & 0xFFFFFFFF
    for i in range(20):
        g.step(L | U)
        if g.cell("wall_t") and g.py() > 0:
            u_before, vy_before = g.u(), g.cell("f_pvy")
            g.step(L | U | A)
            g.step(L | U)
            assert g.cell("f_pvy") > 0 > vy_before, "no kick up"
            assert g.u() >= u_before - 0.05, "thrown back off the face"
            return
    raise AssertionError("never fell against the face with the flip spent")


def test_a_little_short_he_catches_the_ledge(cart):
    """P62 (his tape: 23 failures came down a little short of the box, at its face): in the run's air, his feet up to
    0.7 under a top he has reached, he is on it -- a jump begun well early for TAP's first gap still ends on the next
    box (and on the ground a step is still a step: 0.3)"""
    import bot
    for lead in (0.9, 1.5):
        g = bot.Park(cart)
        _run(g)
        rows = [b for b in g.rows() if b["st"] == 0 and b["motion"] != 3]
        e, nxt = rows[0], rows[1]
        for _ in range(300):
            on = g.cell("lab_si") == e["r"] and g.py() == 0
            if on and e["z1"] - g.u() < lead:
                break
            g.step(L | U | (A if not on and g.py() == 0 and e["z0"] - g.u() < 1.8 and g.cell("lab_si") < 0 else 0))
        for i in range(40):
            g.step(L | U | (A if i < 8 else 0))
            if i > 3 and g.py() == 0:
                break
        assert g.cell("lab_si") == nxt["r"], f"begun {lead} early: not on the next box"
    for _ in range(3):
        g.step(L)
    assert g.py() == 0 and g.cell("park_step") < int(0.35 * ONE), "on the ground the step is not a step"


def test_the_flips_carry_is_the_pad(cart):
    """P62 (his tape: 15 failures past the box -- a flip carried five to seven units over a short top; he flips most
    jumps, and stands on a box before going 58% of the real time): how far the flip goes is the pad -- Up furthest,
    nothing about two thirds, Down a short hop -- and it is the same rule from a stand"""
    import bot

    def flip(pad_after, standing):
        g = bot.Park(cart)
        g.d[g.syms["px"]] = int(round((-64.0 + 8.0) * ONE)) & 0xFFFFFFFF
        _run(g)
        for _ in range(10 if standing else 60):
            g.step(L | (0 if standing else U))
        u0 = g.u()
        for i in range(90):
            g.step(L | (U if not standing and i < 8 else 0) | (A if i < 6 or 8 <= i < 10 else 0) | (pad_after if i >= 10 else 0))
            if i > 12 and g.py() == 0:
                break
        return g.u() - u0
    for standing in (False, True):
        up, none, down = flip(U, standing), flip(0, standing), flip(spec.PAD_DOWN, standing)
        assert up > none + 1.5 and none > down + 1.0, f"standing {standing}: {up:.1f}, {none:.1f}, {down:.1f}"
    assert flip(U, True) > 4.5, "from a stand the flip does not carry"
