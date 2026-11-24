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


def test_the_reaches_the_stations_are_sized_from(cart):
    """P58's jump: the tap 1.28 up and 3.71 far at his pace (it was 0.81 and 3.06), the flip on top of it, the long
    jump unchanged; the stations' gaps are these reaches times a tightness"""
    out = subprocess.run([sys.executable, str(ROOT / "experiments" / "park" / "reach.py"), str(cart)],
                         capture_output=True, text=True, check=True, cwd=ROOT).stdout
    r = json.loads(out.strip().splitlines()[-1])
    assert abs(r["tap"][0] - 3.71) < 0.15 and abs(r["tap"][1] - 1.28) < 0.05
    assert abs(r["tap_flip_at_8"][0] - 7.69) < 0.25 and r["tap_flip_at_8"][1] > 3.0
    assert abs(r["long"][0] - 5.96) < 0.15


def _on_the_first_entry(cart):
    import bot
    g = bot.Park(cart)
    for q in (L, L, 0, 0, 0, L, L, L):
        g.step(q)
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
    jumps at once"""
    g = _on_the_first_entry(cart)
    for _ in range(3):
        g.step(L | U | A)
    g.step(L | U)
    for _ in range(6):
        g.step(L | U)
    for _ in range(3):
        g.step(L | U | A)                       # (the flip)
    while (g.cell("f_pvy") > 0 or g.py() > 0.7) and g.py() > 0:
        g.step(L | U)
    assert g.py() > 0.1
    landed = jumped = False
    for k in range(10):
        g.step(L | U | (A if k < 2 else 0))     # (too early for the ground, the flip spent: kept)
        landed |= g.py() == 0
        jumped |= landed and g.py() > 0 and g.cell("f_pvy") > 0
    assert landed and jumped, "the early press was lost"


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
