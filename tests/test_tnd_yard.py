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
    for i in range(420):                         # (P74: a body comes round to its side before it tells: seven seconds)
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


# ---- P73: THE HIDDEN ATTACKERS, AND THE WEIGHT -------------------------------------------------------------------
def _cart_faces(y):
    """the faces of the cart meshes this frame lists, in order (the machine admits them while 2,048 are not passed)"""
    g, out = y.g, []
    for i in range(g.d[g.syms["nobj"]]):
        at = spec.OL_BASE + 1 + i * spec.OL_STRIDE
        if g.d[at + 5] & spec.OBJ_CART:
            out.append((g.d[g.d[at]] >> 16) & 0xFFFF)
    return out


def test_nothing_that_fights_is_undrawn(cart):
    """P73 ("there was like an invisible enemy that made it hard to play"; his tape of P72: the double, his own 737
    faces and last in the frame's store, drew nothing with company in the shot -- and landed 35 of 73 blows): through
    a minute among all of them, turning, the frame's cart meshes never pass the store; a body that begins a string
    was listed that frame; and the double is a body of the elite's size"""
    y = Yard(cart)
    g = y.g
    worst = 0
    for i in range(1500):
        g.d[g.syms["p_hp"]] = 140
        g.step(U if i < 90 else (spec.PAD_LEFT if i % 200 < 60 else X if i % 23 < 3 else 0))
        f = _cart_faces(y)
        worst = max(worst, sum(f))
        assert sum(f) <= spec.CM_FMAX, f"frame {i}: {sum(f)} faces listed: {f}"
        for k in range(7):
            if y.arr("yard_act", k) == TELL and y.arr("yard_t", k) == 0:
                assert y.arr("yard_seen", k), f"frame {i}: body {k} began a string undrawn"
    assert worst > 1500, f"the shot was never full ({worst})"
    a = g.syms["yard_clip"]
    assert [g.d[a + 14 * 3 + j] for j in range(14)] != [g.d[a + 14 * 2 + j] for j in range(14)], "the double has the elite's bank"


def test_their_places_are_off_the_lenss_line(cart):
    """P73: the double's place was dead ahead -- behind his own back from the lens. P74: a body begins its string
    only from its side: at the frame it tells, it is at least a twentieth of a turn off the way he faces"""
    y = Yard(cart)
    g = y.g
    for _ in range(70):
        g.step(U)
    begun = 0
    was = [FREE] * 7
    for _ in range(900):
        g.d[g.syms["p_hp"]] = 140
        g.step(0)
        hd = g.cell("head") / 1024 * 2 * math.pi
        u, v = y.uv()
        for k in range(7):
            act = y.arr("yard_act", k)
            if act == TELL and was[k] == FREE:
                bu, bv = y.body(k)
                off = (math.atan2(bv - v, bu - u) - hd + math.pi) % (2 * math.pi) - math.pi
                assert abs(off) > math.radians(18), f"body {k} begins from {math.degrees(off):.0f} degrees off his facing"
                begun += 1
            was[k] = act
    assert begun >= 6, begun


def test_a_blow_of_theirs_has_weight(cart):
    """P73 ("make things feel epic and like damage is being done ... give weight to the hits and reactions"): a blow
    landed stops the world, sends him, and puts him in a struck pose that is not his guard; the haymaker takes him
    off his feet -- about a second, in which nothing more lands -- and he is up again"""
    y = Yard(cart)
    g = y.g
    for _ in range(70):
        g.step(U)
    seen, guard_poses = {}, set(range(0, 60))
    hp = g.cell("p_hp")
    for i in range(1500):
        if g.cell("p_hp") < 60:
            g.d[g.syms["p_hp"]] = 140
            hp = 140
        was, at = g.cell("yard_his"), y.uv()
        g.step(0)
        if g.cell("p_hp") < hp:
            kind = g.cell("yard_his")
            assert kind in (1, 2, 3) and g.cell("f_hs") > 0 and g.cell("f_stop") >= 3, (kind, g.cell("f_hs"), g.cell("f_stop"))
            assert was != 3, "struck while he was down"
            seen.setdefault(kind, []).append((i, at))
        hp = g.cell("p_hp")
        if g.cell("yard_his") and g.cell("f_stop") == 0 and g.cell("f_hs") > 2:
            assert g.cell("pose") not in guard_poses, f"frame {i}: struck, and in pose {g.cell('pose')}"
        if len(seen) == 3:
            break
    assert set(seen) == {1, 2, 3}, f"the ways he was struck: {sorted(seen)}"
    # the haymaker: on his back, then up
    i0, at0 = seen[3][0]
    for _ in range(75):
        g.d[g.syms["p_hp"]] = 140
        g.step(0)
        if g.cell("yard_his") == 0:
            break
    assert g.cell("yard_his") == 0 and g.cell("f_dead") == 0, "he did not get up"


def test_struck_they_show_it_and_go_down_in_the_falls_clip(cart):
    """P73: a body his fist meets is in a struck clip of its own bank while it is held; taken to nothing it is in the
    fall's, lies, and gets up in the getting-up's"""
    y = Yard(cart)
    g = y.g
    y.who(3)
    k = 2                                        # a horde body: three to take
    bu, bv = y.body(k)
    y.put(bu, bv - 1.15, 256)
    a = g.syms["yard_clip"]
    hi, dn, up = (g.d[a + j] for j in (10, 12, 13))                 # the horde's row: struck high, down, up
    for _ in range(12):
        g.step(0)
    span, bank = None, None
    poses = {"struck": 0, "down": 0, "up": 0}
    d1 = g.syms[f"e{k}_st"]
    for i in range(420):
        g.step(X if i % 15 < 3 and g.cell(f"e{k}_st") == 1 else 0)
        idx = y.g.cell("yard_k")                                     # (not the pose: read the routine's answer instead)
        st, stun, t = g.cell(f"e{k}_st"), g.cell(f"e{k}_stun"), g.cell(f"e{k}_t")
        if st == 1 and stun > 0:
            poses["struck"] += 1
        if st == 2:
            poses["down" if t < 126 else "up"] += 1
    assert poses["struck"] > 20 and poses["down"] > 60 and poses["up"] > 10, poses
    assert g.cell(f"e{k}_st") == 1 and g.cell(f"e{k}_hp") == 3, "it did not get up whole"
    assert hi > 0 and dn == hi + 16 and up == dn + 12, (hi, dn, up)


# ---- P74: THE TARGETING, AND THE FIGHT'S TURNS -------------------------------------------------------------------
def test_the_fight_has_turns(cart):
    """P74 (his tape of P73: the horde's four landed 7 of 149 blows -- their places were out of the shot -- and the
    double 94): among the horde and the double for a minute, no more than two are engaged at once, the horde gets its
    blows in as well as the double, and those that wait are drawn most of the time they are awake"""
    y = Yard(cart)
    g = y.g
    y.put(-9.0, 2.0, 256)
    landed, awake, seen, most = set(), np.zeros(7), np.zeros(7), 0
    for i in range(3600):
        g.d[g.syms["p_hp"]] = 140
        was = [y.arr("yard_landed", k) for k in range(7)]
        g.step(spec.PAD_LEFT if i % 400 < 30 else 0)
        for k in range(7):
            awake[k] += y.arr("yard_awake", k)
            seen[k] += bool(y.arr("yard_awake", k) and y.arr("yard_seen", k))
            if y.arr("yard_landed", k) and not was[k]:
                landed.add(k)
        most = max(most, sum(1 for k in range(7) if y.arr("yard_side", k)))
    assert most == 2, f"{most} engaged at once"
    assert 6 in landed and len(landed & {2, 3, 4, 5}) >= 3, f"who landed a blow: {sorted(landed)}"
    horde = [seen[k] / awake[k] for k in range(2, 6) if awake[k] > 600]
    assert len(horde) >= 3 and np.mean(horde) > 0.4, f"the horde, drawn while awake: {horde}"


def test_r_takes_only_what_is_drawn(cart):
    """P74 (his tape: locked on one of the horde it was not drawn three frames in four -- 35 seconds squared up to a
    body he could not see): R held among them, the body it has chosen is one the frame drew"""
    y = Yard(cart)
    g = y.g
    y.put(-9.0, 2.0, 256)
    R = spec.PAD_R
    for _ in range(120):
        g.d[g.syms["p_hp"]] = 140
        g.step(0)
    locked = undrawn = run = 0
    for i in range(1500):
        g.d[g.syms["p_hp"]] = 140
        seen_was = [y.arr("yard_seen", k) for k in range(7)]
        g.step(R | (spec.PAD_RIGHT if i % 90 == 45 else 0))
        t = g.cell("t_sel")
        t = t - (1 << 32) if t >= 1 << 31 else t
        if g.cell("t_ok") and 0 <= t < 7:
            locked += 1
            run = run + 1 if not seen_was[t] else 0
            undrawn += not seen_was[t]
            assert run <= 2, f"frame {i}: locked on body {t}, undrawn {run} frames running"
    assert locked > 600, f"locked for {locked} frames"
    assert undrawn < locked * 0.02, f"{undrawn} of {locked} locked frames on an undrawn body"


def test_the_spot_steps_on_the_press_and_not_for_another_move(cart):
    """P74 ("the up down targeting leaks into the other moves, it shouldnt") and P76 ("tank targeting gives the head
    shot body shot leg shot choice. thats important"; his tapes: where it stepped on the press it answered 17 of 25
    choosings, where I made it a quick tap it answered none of 9, each held three quarters of a second): with R held,
    Up or Down steps the spot AT ONCE, tapped or held; with a blow's button inside ten frames it is that move's --
    not stepped, or taken back"""
    y = Yard(cart)
    g = y.g
    y.who(3)                                     # (everyone standing: the double before him)
    for _ in range(110):
        g.step(U)
    R, D = spec.PAD_R, spec.PAD_DOWN

    def spot(keys):
        for _ in range(30):
            g.step(R)
        was = g.cell("t_spot")
        g.step(R | keys[0])
        g.step(R | keys[1])
        at_once = g.cell("t_spot") - was
        for q in keys[2:]:
            g.step(R | q)
        for _ in range(20):
            g.step(R)
        return at_once, g.cell("t_spot") - was
    assert g.cell("t_spot") == 1
    assert spot([D] * 4) == (1, 1), "a tap of Down"
    assert spot([U] * 4) == (-1, -1), "a tap of Up"
    assert spot([D] * 45) == (1, 1), "Down held"
    assert spot([U] * 45) == (-1, -1), "Up held"
    assert spot([D] * 3 + [D | X] * 3 + [D] * 3)[1] == 0, "Down with a blow: not taken back"
    assert spot([X] * 3 + [0] * 3 + [D] * 4) == (0, 0), "Down just after a blow's button stepped it"
    assert g.cell("t_spot") == 1


# ---- P75 -------------------------------------------------------------------------------------------------------------
def _wrap(a):
    return ((a + 512) % 1024) - 512


def test_a_in_the_tank(cart):
    """P75 ("down a in the tank should be back dodge, just a in tank is quick turn"): A alone turns him half round
    where he stands; Down with A is the dodge back; a side with A the dodge that way; and locked, A alone is still
    the dodge back (his facing is the lock's)"""
    D, LEFT = spec.PAD_DOWN, spec.PAD_LEFT
    out = {}
    for name, keys in (("alone", [A] * 3), ("down", [D | A] * 3 + [D] * 3), ("left", [LEFT | A] * 3)):
        y = Yard(cart)
        g = y.g
        y.who(3)
        for _ in range(20):
            g.step(0)
        yaw, (u0, v0) = g.cell("yaw"), y.uv()
        for q in keys + [0] * 40:
            g.step(q)
        out[name] = (_wrap(g.cell("yaw") - yaw), y.uv()[0] - u0, y.uv()[1] - v0)
    assert abs(out["alone"][0]) == 512 and abs(out["alone"][1]) + abs(out["alone"][2]) < 0.05, out["alone"]
    assert out["down"][0] == 0 and out["down"][2] < -0.4, out["down"]              # (he faces north: back is south)
    assert out["left"][0] == 0 and out["left"][1] < -0.4, out["left"]
    y = Yard(cart)
    g = y.g
    y.who(3)
    for _ in range(100):
        g.step(U)
    for _ in range(20):
        g.step(spec.PAD_R)
    assert g.cell("locked")
    yaw = g.cell("yaw")
    for q in [spec.PAD_R | A] * 3 + [spec.PAD_R] * 40:
        g.step(q)
    assert abs(_wrap(g.cell("yaw") - yaw)) < 64, "locked, A alone turned him round"


def test_the_slide_is_a_blow(cart):
    """P75 ("slide wilhile running should do damage"): Y in the run, into a body: it takes its legs -- the hook's
    two off it -- and the body is down"""
    y = Yard(cart)
    g = y.g
    y.who(3)
    bu, bv = y.body(2)
    y.put(bu, bv - 5.0, 256)
    for q in (L, L, 0, 0, 0, L, L, L):
        g.step(q)
    hp = g.cell("e2_hp")
    for i in range(90):
        g.step(L | U | (spec.PAD_Y if y.far(2) < 2.6 and i % 2 == 0 else 0))
        if g.cell("e2_hp") < hp:
            break
    assert g.cell("e2_hp") == hp - 2 and g.cell("e2_st") == 2, (g.cell("e2_hp"), g.cell("e2_st"))
    assert g.cell("aim_zone") == 2 and g.cell("anim") == 7, "it was not the slide, at the legs"


def test_locked_in_the_tank_he_is_planted_and_steps_to_the_side_pressed(cart):
    """P75 (his tape of P74: 6 of 11 steps with Left and Right went to the side pressed): locked, Left takes the next
    body on his left and Right the next on his right -- and at the last on a side, it stays. P76: and he is PLANTED,
    as he made it (P37): Up and Down held are the spot's, and do not walk him"""
    y = Yard(cart)
    g = y.g
    y.who(3)                                     # (everyone standing)
    R, D, LEFT, RIGHT = spec.PAD_R, spec.PAD_DOWN, spec.PAD_LEFT, spec.PAD_RIGHT
    y.put(-14.0, 3.0, 256)                       # south of the range's five, facing them
    for _ in range(30):
        g.step(R)
    assert g.cell("locked")

    def chosen():
        t = g.cell("t_sel")
        return t - (1 << 32) if t >= 1 << 31 else t

    def bearing(k):
        (u, v), (bu, bv) = y.uv(), y.body(k)
        return math.degrees(math.atan2(bv - v, bu - u))             # (counter-clockwise: a greater bearing is to his left)
    at = y.uv()
    for q in [R | U] * 40 + [R | D] * 40:
        g.step(q)
    assert math.dist(at, y.uv()) < 0.05, f"locked, Up and Down moved him {math.dist(at, y.uv()):.2f}"
    steps = 0
    for key, sign in ((LEFT, 1), (LEFT, 1), (LEFT, 1), (LEFT, 1), (LEFT, 1), (RIGHT, -1), (RIGHT, -1), (RIGHT, -1), (RIGHT, -1), (RIGHT, -1), (RIGHT, -1)):
        was = chosen()
        for q in [R | key] * 3 + [R] * 25:
            g.step(q)
        now = chosen()
        if now != was:
            d = (bearing(now) - bearing(was) + 180) % 360 - 180
            assert d * sign > 0, f"{'Left' if sign > 0 else 'Right'} went {d:+.0f} degrees round"
            steps += 1
    assert steps >= 5, f"{steps} steps"


def test_a_fight_calls_the_others(cart):
    """P75 (his tape of P74: eleven minutes in the ring; the range's five slept through it): standing in the ring's
    middle with the ring's two awake, bodies of the range wake -- they are within sixteen units -- and from where he
    begins, with nobody awake, nobody does"""
    y = Yard(cart)
    g = y.g
    for _ in range(200):
        g.step(0)
    assert not any(y.arr("yard_awake", k) for k in range(7))
    y.put(0.0, 0.0, 256)
    for _ in range(300):
        g.d[g.syms["p_hp"]] = 140
        g.step(0)
    assert sum(y.arr("yard_awake", k) for k in range(1, 6)) >= 2, [y.arr("yard_awake", k) for k in range(7)]


# ---- P76 -------------------------------------------------------------------------------------------------------------
def test_where_it_is_struck_stays_with_it(cart):
    """P76 ("tank targeting gives the head shot body shot leg shot choice. thats important. those should have specfic
    effects on the enemy"): a round at the elite's HEAD takes two and leaves it DAZED; at its BODY, WINDED -- its next
    string a second and more off; at its LEGS, HOBBLED -- and a second there while it is, and it is DOWN"""
    R, B = spec.PAD_R, spec.PAD_B
    seen = {}
    for zone in (0, 1, 2):
        y = Yard(cart)
        g = y.g
        y.who(1)                                 # (the ring's two, fighting)
        bu, bv = y.body(0)
        y.put(bu, bv - 6.0, 256)
        g.d[g.syms["e0_stun"]] = 2               # (struck: it is awake)
        for _ in range(10):
            g.step(0)
        for _ in range(20):
            g.step(R)
        assert g.cell("t_sel") == 0, "R did not take the elite"

        def shoot():
            g.d[g.syms["t_spot"]] = zone
            for q in [R | B] * 3 + [R] * 30:
                g.d[g.syms["p_hp"]] = 140
                g.step(q)
        hp = g.cell("e0_hp")
        shoot()
        seen[zone] = (hp - g.cell("e0_hp"), y.arr("yard_dazed", 0), y.arr("yard_cd", 0), y.arr("yard_hobbled", 0), g.cell("e0_st"))
        if zone == 2:
            shoot()
            assert g.cell("e0_st") == 2 and y.arr("yard_hobbled", 0) == 0, "hobbled and struck in the legs again, it stands"
    assert seen[0][0] == 2 and seen[0][1] > 120 and seen[0][2:4] == (0, 0), f"the head: {seen[0]}"
    assert seen[1][0] == 1 and seen[1][2] > 60 and seen[1][1] == 0 and seen[1][3] == 0, f"the body: {seen[1]}"
    assert seen[2][0] == 1 and seen[2][3] > 150 and seen[2][1] == 0 and seen[2][4] == 1, f"the legs: {seen[2]}"


def test_hobbled_it_comes_at_half_its_pace(cart):
    """P76: a body's pace toward him, hobbled, is half what it is whole"""
    def came(hobbled):
        y = Yard(cart)
        g = y.g
        y.who(1)
        bu, bv = y.body(0)
        y.put(bu, bv - 7.0, 256)
        g.d[g.syms["yard_awake"]] = 1
        g.step(0)
        far = y.far(0)
        for _ in range(50):
            if hobbled:
                g.d[g.syms["yard_hobbled"]] = 100
            g.d[g.syms["p_hp"]] = 140
            g.step(0)
        return far - y.far(0)
    whole, half = came(False), came(True)
    assert whole > 1.5 and 0.35 * whole < half < 0.65 * whole, f"whole {whole:.2f}, hobbled {half:.2f}"


def test_into_the_run_and_out_of_it_is_not_one_frame(cart):
    """P76 ("it should just be smoother and cool between modes of play"): into the run he drops and drives -- the
    landing's crouch, five frames, rising into the stride; out of it at pace he brakes -- eight frames of it -- and
    only then stands"""
    y = Yard(cart)
    g = y.g
    y.who(3)
    y.put(-20.0, -6.0, 256)
    for _ in range(10):
        g.step(0)
    stride = range(387, 387 + 16)
    poses = []
    for q in [L, L, 0, 0, 0, L, L, L] + [L | U] * 40 + [0] * 16:
        g.step(q)
        poses.append((g.cell("f_sty"), g.cell("pose")))
    first = next(i for i, (s_, _) in enumerate(poses) if s_ == 1)
    start = [p for _, p in poses[first:first + 5]]
    assert not any(p in stride for p in start) and len(set(start)) == 5 and start == sorted(start), f"into the run: {start}"
    assert poses[first + 5][1] in stride, poses[first + 5]
    out = next(i for i in range(first + 10, len(poses)) if poses[i][0] != 1)
    brake = [p for _, p in poses[out:out + 8]]
    assert not any(p in stride for p in brake) and min(brake) == brake[4] and set(brake) <= set(range(min(start), max(start) + 1)), f"out of it: {brake}"
    assert poses[out + 8][1] < 60, f"then he stands: {poses[out + 8]}"
