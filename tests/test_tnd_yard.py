"""TND's YARD (docs/TND-PORT.md P70): one room for the whole moveset.

The player, 2026-11-24: "design a new lab room, something that would be a good
playground for the full moveset" -- and, of the design (a ring in the middle,
a track round the walls, a range): "looks fine get to work".

The lab's hall (64 by 32) with the park's ROWS in it, written once as a table:
the room is data. A local build (TND_LAYER=13 -> build/layer13/tnd.zol).
"""
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from zeta import gpu, spec

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "games" / "tnd" / "gen_tnd.py"
CART = ROOT / "build" / "layer13" / "tnd.zol"
sys.path.insert(0, str(ROOT / "experiments" / "park"))
pytestmark = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "clips_190.npz").is_file(),
                                reason="the layer builds from the local tier files (build/tiers)")
A, B, X, L, U = spec.PAD_A, spec.PAD_B, spec.PAD_X, spec.PAD_L, spec.PAD_UP
ONE = 65536
START_V = -8.5                      # he begins this far south of the room's middle


@pytest.fixture(scope="module")
def cart():
    if not CART.is_file() or CART.stat().st_mtime < GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="13")
        for k in ("TND_SONG", "TND_OUT", "TND_CROWD", "TND_CARTMESH", "TND_AT"):
            env.pop(k, None)
        subprocess.run([sys.executable, str(GEN)], check=True, env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    return CART


@pytest.fixture(autouse=True)
def no_paint(monkeypatch):
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)


class Yard:
    """the room in its own measures: u east, v north, from its middle"""

    def __init__(self, cart):
        import bot
        self.bot = bot
        self.g = g = bot.Park(cart)
        for _ in range(5):
            g.step(0)
        self.hx, self.hz = g.cell("px") / ONE - (-START_V), g.cell("pz") / ONE

    def uv(self):
        g = self.g
        return g.cell("pz") / ONE - self.hz, self.hx - g.cell("px") / ONE

    def body(self, k):
        a = self.g.syms[f"e{k}_pos"]
        return self.bot.s32(self.g.d[a + 1]) / ONE - self.hz, self.hx - self.bot.s32(self.g.d[a]) / ONE

    def put(self, u, v, yaw, up=0.0):
        g = self.g
        g.d[g.syms["px"]] = int(round((self.hx - v) * ONE)) & 0xFFFFFFFF
        g.d[g.syms["pz"]] = int(round((self.hz + u) * ONE)) & 0xFFFFFFFF
        g.d[g.syms["f_py"]] = int(up * ONE)
        for k in ("yaw", "head", "cam_yaw"):
            g.d[g.syms[k]] = yaw & 1023

    def boxes(self):
        out = []
        for r in self.g.rows():
            if r["motion"] == 3:
                continue
            out.append(dict(r, u0=r["z0"] + r["dz"] - self.hz, u1=r["z1"] + r["dz"] - self.hz, v0=self.hx - r["x1"], v1=self.hx - r["x0"]))
        return out


def test_the_room_is_a_table(cart):
    """the hall, and in it the rows the cart was built with: every one inside the walls; the seven stand where the
    room puts them -- the elite and the double in the ring, five down the range; he begins south of the ring"""
    y = Yard(cart)
    rows = y.g.rows()
    assert 35 <= len(rows) <= 56, len(rows)
    for b in y.boxes():
        assert -32 <= b["u0"] < b["u1"] <= 32 and -16 <= b["v0"] < b["v1"] <= 16, b
    assert [y.g.cell(f"e{k}_st") for k in range(7)] == [1] * 7, "not everyone stands"
    for k in (0, 6):
        u, v = y.body(k)
        assert abs(u) < 6.5 and abs(v) < 5.5, f"body {k} is not in the ring: {u:.1f}, {v:.1f}"
    for k in range(1, 6):
        u, v = y.body(k)
        assert 7 < v < 10 and -20 < u < -6, f"body {k} is not on the range: {u:.1f}, {v:.1f}"
    u, v = y.uv()
    assert abs(u) < 0.1 and abs(v - START_V) < 0.1 and y.g.cell("f_sty") == 0


def test_the_ring_takes_fists(cart):
    """walked north into the ring, the tank's jabs land on the double"""
    y = Yard(cart)
    for _ in range(120):
        y.g.step(U)
    hp = y.g.cell("e6_hp")
    for _ in range(6):
        for q in [X] * 3 + [0] * 14:
            y.g.step(q)
    assert y.g.cell("e6_hp") < hp, "six jabs and the double has what it had"


def test_the_range_is_the_guns_reach(cart):
    """from the firing pad each body has a bearing of its own, and all five are inside the 13 units a round flies:
    a tapped round takes one off each; from a unit further back, the last is out of reach -- of the charged round too"""
    y = Yard(cart)
    pad = (-23.0, 8.5)
    far = max(range(1, 6), key=lambda k: y.body(k)[0])
    for k in range(1, 6):
        bu, bv = y.body(k)
        assert math.hypot(bu - pad[0], bv - pad[1]) < 13
        y.put(*pad, int(round(math.atan2(bv - pad[1], bu - pad[0]) / (2 * math.pi) * 1024)))
        for _ in range(6):
            y.g.step(0)
        assert y.g.cell("lab_gh") > 0, "he is not on the pad"
        hp = y.g.cell(f"e{k}_hp")
        for q in [B] * 3 + [0] * 40:
            y.g.step(q)
        assert y.g.cell(f"e{k}_hp") == hp - 1, f"body {k}: {hp} -> {y.g.cell(f'e{k}_hp')}"
    bu, bv = y.body(far)
    y.put(bu - 14.0, bv, 0)
    for _ in range(6):
        y.g.step(0)
    hp = y.g.cell(f"e{far}_hp")
    for q in [B] * 3 + [0] * 40 + [B] * 60 + [0] * 40:
        y.g.step(q)
    assert y.g.cell(f"e{far}_hp") == hp, "a round reached 14 units"


def test_the_tracks_south_side_is_run_without_the_floor(cart):
    """from the south-west corner, east: three taps, two steps up, the flip down, the slider ridden, the corner --
    a runner that jumps at each box's edge (and flips a long gap) never touches the floor"""
    y = Yard(cart)
    g = y.g
    y.put(-28.5, -13.0, 0, up=1.2)
    for q in (L, L, 0, 0, 0, L, L, L):
        g.step(q)
    stood, keys, floor = [], [], 0
    for i in range(1200):
        u, v = y.uv()
        on, q = g.cell("lab_si"), L | U
        boxes = y.boxes()
        me = next((b for b in boxes if b["r"] == on), None) if g.py() == 0 else None
        if me is not None:
            if not stood or stood[-1] != on:
                stood.append(on)
            ahead = [b for b in boxes if b["r"] != on and b["u1"] > me["u1"] + 0.3 and abs((b["v0"] + b["v1"]) / 2 - v) < 2.5]
            nxt = min(ahead, key=lambda b: b["u0"], default=None)
            if nxt is not None and not keys:
                gap = nxt["u0"] - me["u1"]
                riding = me["motion"] == 1 and me["dz"] < 7.0
                if not riding and me["u1"] - u < (0.5 if gap > 1.5 else 1.3):
                    keys = [1] * 10 + ([0] * 3 + [1] * 3 if gap > 4.5 else [])
        elif g.py() == 0 and i > 20:
            floor += 1
        if keys:
            q |= A if keys.pop(0) else 0
        g.step(q)
        if u > 27:
            break
    assert floor == 0, f"{floor} frames on the floor; stood on {stood}"
    assert len(stood) >= 10 and y.uv()[0] > 26, f"stood on {stood}, ended at {y.uv()}"


def test_a_minute_of_anything_stays_in_the_room_and_the_frame(cart):
    """walking, fists, the run, jumps, dives and shots at random for a minute: he is in the hall, the program never
    runs out of its frame's instructions, and the object list has room"""
    y = Yard(cart)
    g = y.g
    used, objs = [], []

    def step(q):
        g.step(q)
        used.append(spec.FUEL - g.m.vm.fuel_left)
        objs.append(g.d[g.syms["nobj"]])
    for _ in range(100):
        step(U)
    for q in (L, L, 0, 0, 0, L, L, L):
        step(q)
    rng = random.Random(3)
    for i in range(3600):
        q, r = L | U, rng.random()
        if i % 90 < 12:
            q |= spec.PAD_RIGHT if (i // 90) % 3 else spec.PAD_LEFT
        q |= A if r < 0.03 else X if r > 0.985 else B if 0.5 < r < 0.51 else 0
        step(q)
        u, v = y.uv()
        assert abs(u) <= 32 and abs(v) <= 16, f"frame {i}: he is at {u:.1f}, {v:.1f}"
    assert max(used) < spec.FUEL, f"a frame ran out of fuel ({max(used)})"
    assert max(objs) <= spec.OL_MAX - 4, f"{max(objs)} objects"
