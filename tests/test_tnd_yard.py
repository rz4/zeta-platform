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

    def who(self, n):
        """the who knob: 0 everyone, fighting; 1 the ring's two; 2 the range, standing; 3 everyone, standing; 4 the
        double alone; 5 all but the double"""
        self.g.d[self.g.syms["knobs"]] = n
        self.g.step(0)

    def arr(self, name, k):
        return self.g.d[self.g.syms[name] + k]

    def far(self, k):
        (u, v), (bu, bv) = self.uv(), self.body(k)
        return math.hypot(bu - u, bv - v)

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
    """walked north into the ring (everyone standing: the knob), the tank's jabs land on the double"""
    y = Yard(cart)
    y.who(3)
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
    y.who(3)                                     # (everyone, standing: the range as a range)
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


# ---- P71: THE FIGHT ----------------------------------------------------------------------------------------------
NAMES = ("jab", "cross", "lead_hook", "rear_hook", "special", "lead_uppercut", "rear_uppercut", "gun", "gun_charged")
SIZE_OF = (2, 1, 0, 0, 0, 0, 3)                # body -> its size's row: the horde, the common, the elite, the double
FREE, TELL, BLOW, DODGE = range(4)


def _strings(y):
    """the cart's own table: for each size, its four strings as move names"""
    a = y.g.syms["yard_strings"]
    out = []
    for size in range(4):
        rows = []
        for s_ in range(4):
            w, moves = y.g.d[a + 4 * size + s_], []
            while w & 15 != 15:
                moves.append(NAMES[w & 15])
                w >>= 4
            rows.append(moves)
        out.append(rows)
    return out


def test_a_size_is_how_much_of_his_kit_it_has(cart):
    """("the highest tier can essentially use my full kit. lower less of the kit"): the horde's strings are the
    haymaker; the common's of three moves; the elite's of six; the double's of every fist he has. Nobody has the
    gun (P72: "remove gun, from them")"""
    y = Yard(cart)
    horde, common, elite, double = ({m for st in rows for m in st} for rows in _strings(y))
    assert horde == {"special"}
    assert common == {"jab", "cross", "special"}
    assert horde < common < elite and len(elite) == 6 and "gun" not in elite
    assert double == {"jab", "cross", "lead_hook", "rear_hook", "special", "lead_uppercut", "rear_uppercut"}
    assert not any("gun" in m for size in (horde, common, elite, double) for m in size)


def test_they_come_and_strike_and_the_far_ones_sleep(cart):
    """he walks toward the ring and stands: the elite and the double wake (seven and a half units), come to places BEFORE him,
    tell, and their strings land -- he is hurt, by more than one move; the five down the range are asleep on
    their marks; and no more than two are at it at once"""
    y = Yard(cart)
    g = y.g
    marks = [y.body(k) for k in range(7)]
    for _ in range(120):                         # (where he begins, nobody is awake)
        g.step(0)
    assert not any(y.arr("yard_awake", k) for k in range(7)) and g.cell("p_hp") == 140
    for _ in range(70):
        g.step(U)
    hp, moves, most = g.cell("p_hp"), set(), 0
    for i in range(240):
        g.step(0)
        at_it = [k for k in range(7) if y.arr("yard_act", k) in (TELL, BLOW)]
        most = max(most, len(at_it))
        moves |= {NAMES[y.arr("yard_sp", k) & 15] for k in at_it if y.arr("yard_act", k) == BLOW and y.arr("yard_landed", k)}
        if g.cell("f_dead"):
            break
    assert g.cell("p_hp") < hp - 30, f"he had {hp}, has {g.cell('p_hp')}"
    assert len(moves) >= 2, f"what landed: {moves}"
    assert most <= 2, f"{most} at once"
    for k in range(1, 6):
        assert not y.arr("yard_awake", k) and math.dist(y.body(k), marks[k]) < 0.01, f"body {k} left its mark"
    hd = g.cell("head") / 1024 * 2 * math.pi
    (u, v) = y.uv()
    for k in (0, 6):
        bu, bv = y.body(k)
        off = (math.atan2(bv - v, bu - u) - hd + math.pi) % (2 * math.pi) - math.pi
        assert abs(off) < math.radians(80) and y.far(k) < 6, f"body {k} is {math.degrees(off):.0f} degrees off his facing, {y.far(k):.1f} away"


def test_the_horde_throws_only_its_haymaker_and_slowly(cart):
    """by the range, the horde's four come: over twenty seconds every blow of theirs is the haymaker, and each tells
    for forty frames before it (the double's tell is twelve)"""
    y = Yard(cart)
    g = y.g
    y.who(5)                                     # (all but the double)
    y.put(-9.0, 5.0, 256)
    thrown, tells, t0 = set(), [], {}
    for i in range(1200):
        g.d[g.syms["p_hp"]] = 140                # (he is kept standing: this is about them)
        g.step(0)
        for k in range(2, 6):
            act = y.arr("yard_act", k)
            if act == TELL and k not in t0:
                t0[k] = i
            if act == BLOW:
                thrown.add(NAMES[y.arr("yard_sp", k) & 15])
                if k in t0:
                    tells.append(i - t0.pop(k))
            if act == FREE:
                t0.pop(k, None)
    assert thrown == {"special"}, thrown
    assert tells and min(tells) >= 40, tells


def test_struck_it_loses_its_string_and_a_dodge_is_not_hit(cart):
    """a body held by a blow is out of its string; and through a dodge's frames nothing of theirs lands"""
    y = Yard(cart)
    g = y.g
    for _ in range(70):
        g.step(U)
    for i in range(300):
        g.step(0)
        k = next((k for k in (0, 6) if y.arr("yard_act", k) == TELL), None)
        if k is not None:
            break
    assert k is not None, "nobody told"
    g.d[g.syms[f"e{k}_stun"]] = 12
    g.step(0)
    assert y.arr("yard_act", k) == FREE, "held, it kept its string"
    hp = g.cell("p_hp")
    for i in range(300):
        g.d[g.syms["f_evf"]] = 6                 # (a dodge's frames, held open)
        g.step(0)
    assert g.cell("p_hp") == hp, f"in a dodge he lost {hp - g.cell('p_hp')}"


def test_down_and_a_is_the_room_again(cart):
    """standing in it he goes down; after the beat, A: his health, his place, and everyone whole on their marks"""
    y = Yard(cart)
    g = y.g
    marks = [y.body(k) for k in range(7)]
    for _ in range(70):
        g.step(U)
    for i in range(1500):
        g.step(0)
        if g.cell("f_dead"):
            break
    assert g.cell("f_dead"), "twenty-five seconds standing in it and he is up"
    assert 150 < i < 1200, f"down after {i} frames"
    for _ in range(60):
        g.step(0)
    for q in [A] * 3 + [0] * 3:
        g.step(q)
    assert g.cell("f_dead") == 0 and g.cell("p_hp") == 140
    assert all(g.cell(f"e{k}_st") == 1 for k in range(7))
    assert all(math.dist(y.body(k), marks[k]) < 0.5 for k in range(7)), [y.body(k) for k in range(7)]
    assert abs(y.uv()[0]) < 1.5 and y.uv()[1] < -7


def test_standing_they_only_stand(cart):
    """the knob's "everyone, standing": he walks in among them and nobody moves or tells"""
    y = Yard(cart)
    g = y.g
    y.who(3)
    marks = [y.body(k) for k in range(7)]
    for _ in range(100):
        g.step(U)
    for _ in range(200):
        g.step(0)
        assert not any(y.arr("yard_act", k) for k in range(7))
    assert g.cell("p_hp") == 140 and all(math.dist(y.body(k), marks[k]) < 0.01 for k in range(7))


def test_nobody_shoots_him(cart):
    """P72 ("remove gun, from them"): he stands eight units from the double, awake and in the open, for fifteen
    seconds: nothing of theirs is a round, and nothing lands from out of a fist's reach"""
    y = Yard(cart)
    g = y.g
    y.who(4)                                     # (the double alone)
    bu, bv = y.body(6)
    y.put(bu, bv - 8.0, 256)
    g.d[g.syms["e6_stun"]] = 4                   # (struck: it is awake)
    for i in range(900):
        hp = g.cell("p_hp")
        y.put(*[a + b for a, b in zip(y.body(6), (0.0, -8.0))], 256)          # (kept eight units off it)
        g.step(0)
        assert g.cell("p_hp") == hp, f"frame {i}: he lost {hp - g.cell('p_hp')} from eight units"
        assert not (y.arr("yard_act", 6) == BLOW and NAMES[y.arr("yard_sp", 6) & 15].startswith("gun"))
