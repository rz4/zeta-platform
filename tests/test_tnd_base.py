"""TND's BASE LAYER (docs/TND-PORT.md P21): the city and the player, alone.

A layer-0 build is local (TND_LAYER=0 -> build/layer0/tnd.zol), so this
builds it when it is missing or older than its generator. The tests are
short on purpose: the base is tuned on glass, a few times a day, and its
gate must answer in a minute or two.
"""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from zeta import cabinet, spec

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "games" / "tnd" / "gen_tnd.py"
CART = ROOT / "build" / "layer0" / "tnd.zol"
pytestmark = pytest.mark.skipif(not (ROOT / "assets" / "tnd" / "boxer.npz").is_file(),
                                reason="the base builds from the third-party bake")

U, D, LF, RT = spec.PAD_UP, spec.PAD_DOWN, spec.PAD_LEFT, spec.PAD_RIGHT
A, X, SEL = spec.PAD_A, spec.PAD_X, spec.PAD_SELECT


@pytest.fixture(scope="module")
def text():
    if not CART.is_file() or CART.stat().st_mtime < GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="0")
        env.pop("TND_SONG", None)
        env.pop("TND_OUT", None)
        subprocess.run([sys.executable, str(GEN)], check=True, env=env, cwd=ROOT,
                       stdout=subprocess.DEVNULL)
    return CART.read_text().splitlines()


def _s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


class Base:
    def __init__(self, text):
        self.text = text
        self.m = cabinet.VirtualMachine(cabinet.load_cart(CART))
        self.m.frame(spec.PAD_START)
        self.d = self.m.vm.dmem
        self.run(0, 5)

    def sym(self, n):
        return next(int(l.rsplit(" at ", 1)[1]) for l in self.text if l.startswith(f"; {n}: "))

    def const(self, n):
        return next(int(l.split()[2]) for l in self.text if l.startswith(f".const {n} "))

    def cell(self, n, k=0):
        return _s32(self.d[self.sym(n) + k])

    def run(self, pad, n):
        for _ in range(n):
            self.m.frame(pad)

    def pos(self):
        return self.cell("px") / 65536, self.cell("pz") / 65536

    def put(self, x, z, yaw):
        for n, v in (("px", x), ("pz", z)):
            self.d[self.sym(n)] = int(round(v * 65536)) & 0xFFFFFFFF
        self.d[self.sym("yaw")] = self.d[self.sym("cam_yaw")] = yaw & 1023

    def knob(self, k):
        """knob k as the game reads it (0 walk, 1 ramp, 2 turn, 3 quick turn,
        4 the lens's distance, 5 its height, 6 the town's dark, 7 pick-up
        frames, 8 the grade, 9 the pick-up's bow)"""
        return self.cell("knobs", k)

    def lens(self):
        (x, z), d = self.pos(), self.d
        return np.hypot(x - _s32(d[spec.CAM_X]) / 65536, z - _s32(d[spec.CAM_Z]) / 65536)


def test_the_tank_has_weight_and_the_lens_keeps_its_distance(text):
    """The walk eases up to its pace and back down (it was a switch), the
    quick turn is Down + A, A alone is still the back dodge -- and at the
    start, the dead end's wall right behind him, the lens is the same
    distance behind as it is in the open street. (The pace, the ramp and
    the distance are knobs: read from the cart, they are the player's.)"""
    b = Base(text)
    pace, ramp, far = b.knob(0) / 65536, b.knob(1) / 65536, b.knob(4) / 65536
    b.run(0, 120)                                # (the lens eases to its distance)
    assert abs(b.lens() - far) < 0.05, f"the lens is {b.lens():.2f} behind at the wall, not {far}"
    steps, last = [], b.pos()
    for f in range(30):
        b.run(U, 1)
        p = b.pos()
        steps.append(np.hypot(p[0] - last[0], p[1] - last[1]))
        last = p
    assert abs(steps[0] - ramp * pace) < 0.002 and steps[0] < pace, f"no lean into the walk: {steps[:4]}"
    assert abs(steps[-1] - pace) < 0.002, f"he never reached his pace: {steps[-1]:.4f}"
    assert all(b2 >= a2 - 1e-6 for a2, b2 in zip(steps, steps[1:])), "the walk stuttered"
    assert abs(b.lens() - far) < 0.2
    af0 = b.cell("af")
    b.run(U, 32)
    assert abs((b.cell("af") - af0) - 32 * pace / 0.032) <= 1, "his feet slide: the stride left the ground"
    last = b.pos()
    b.run(0, 1)
    assert 0 < np.hypot(*np.subtract(b.pos(), last)) < pace, "he stopped dead"
    b.run(0, 30)
    y0 = b.cell("yaw")
    for f in range(24):
        b.run(D | (A if f < 9 else 0), 1)           # a thumb's press
    assert (b.cell("yaw") - y0) % 1024 == 512, "Down + A is not a half turn"
    b.run(0, 10)
    p0, y1 = b.pos(), b.cell("yaw")
    for f in range(24):
        b.run(A if f < 9 else 0, 1)
    assert b.cell("yaw") == y1 and np.hypot(*np.subtract(b.pos(), p0)) > 1.5, \
        "A alone is not the back dodge"


def test_a_wall_carries_him_and_the_shoulders_do_nothing(text):
    """A wall is a wall: walking into a street's wall ten degrees off dead
    on, he keeps what of his step runs along it and no more (P21's softened
    slide was a knob, and the player turned it off); dead on, he stops. L
    and R are not in the base."""
    b = Base(text)
    T, ox, oy, cm = b.const("CITY_TILE"), b.const("CITY_OXA"), b.const("CITY_OYA"), b.sym("city_map")
    n = next(n for n in range(256) if (b.d[cm + n] & 0xFF) == 0x11)       # a street along x
    cx, cz = oy - (n // 16) * T, (n % 16) * T - ox
    for off in (80, 90):
        b = Base(text)
        pace = b.knob(0) / 65536
        want = pace * np.cos(np.radians(off))
        b.put(cx, cz, 256 - int(off * 1024 / 360))
        b.run(U, 140)
        last = b.pos()
        b.run(U, 1)
        along = abs(b.pos()[0] - last[0])
        assert abs(along - want) < 0.003, f"{90 - off} degrees off: {along:.4f} along the wall"
    b = Base(text)
    b.run(spec.PAD_L | spec.PAD_R | U, 40)
    assert b.cell("f_sty") == 0 and b.cell("f_frun") == 0, "a shoulder did something"


def test_the_jab_picks_up_the_key_and_unlocks_the_gate(text):
    """The district's key lies in its plaza. Beside it and facing it, the
    jab picks it up (he is held, bowed, for the pick knob's frames); away
    from it the jab is a jab. With the key, the jab at the district's gate
    opens it, and he walks through."""
    b = Base(text)
    kx, kz = b.cell("keypos") / 65536, b.cell("keypos", 1) / 65536
    b.put(kx, kz - 4.0, 0)
    b.run(0, 3)
    assert b.cell("ctx_near") == 0
    for f in range(16):
        b.run(X if f < 7 else 0, 1)
    assert b.cell("key_held") == 0 and b.cell("anim") == 2, "out of reach, the jab was not a jab"
    b.run(0, 40)
    b.put(kx, kz - 1.0, 0)
    b.run(0, 3)
    assert b.cell("ctx_near") == 1
    for f in range(12):
        b.run(X if f < 7 else 0, 1)
        if b.cell("key_held"):
            break
    hold = b.knob(7)
    assert b.cell("key_held") == 1 and b.cell("pick_t") == hold, "the jab did not pick it up"
    p0 = b.pos()
    b.run(U, hold)
    assert np.hypot(*np.subtract(b.pos(), p0)) < 0.05, "he walked off mid pick-up"
    assert 0 < b.cell("f_tilt") <= b.knob(9), "he did not bow to it"
    b.run(U, 12)
    assert np.hypot(*np.subtract(b.pos(), p0)) > 0.3, "the pick-up never let him go"
    b.run(0, 40)
    g = b.sym("gates")
    a = b.d[g]
    T, ox, oy = b.const("CITY_TILE"), b.const("CITY_OXA"), b.const("CITY_OYA")
    ax, az = oy - (a // 16) * T, (a % 16) * T - ox
    gx, gz = _s32(b.d[g + 4]) / 65536, _s32(b.d[g + 5]) / 65536
    b.put(ax, az, int(round(np.arctan2(-(gx - ax), gz - az) * 1024 / (2 * np.pi))))
    b.run(U, 110)
    assert np.hypot(b.pos()[0] - ax, b.pos()[1] - az) < 3.2, "the shut gate did not stop him"
    assert b.cell("ctx_near") == 2
    for f in range(40):
        b.run(X if f < 7 else 0, 1)
    assert b.cell("s_dx") == 1 and b.cell("key_held") == 0, "the jab did not unlock the gate"
    b.run(U, 160)
    assert np.hypot(b.pos()[0] - ax, b.pos()[1] - az) > 6, "he did not walk through it"


def test_select_tunes_a_knob_and_shows_it(text):
    """SELECT held, the d-pad is the tuner: Right picks the next knob, Up
    turns it a notch -- on the screen, the knob and its notch -- and he does
    not move meanwhile. Let go, the screen clears and the knob holds."""
    b = Base(text)
    b.run(0, 10)
    p0, turn0 = b.pos(), b.cell("knobs", 2)
    for pad in ([SEL | RT] * 9 + [SEL] * 6) * 2 + ([SEL | U] * 9 + [SEL] * 6) * 3:
        b.run(pad, 1)
    assert b.cell("knob_sel") == 2 and b.cell("knobs", 2) == turn0 + 3
    assert b.pos() == p0, "he walked while tuning"
    assert b.d[spec.DL_BASE] > 8, "the tuner drew nothing"
    b.run(0, 3)
    assert b.d[spec.DL_BASE] == 1, "the tuner stayed on the screen"
    y0 = b.cell("yaw")
    b.run(LF, 4)
    assert (b.cell("yaw") - y0) % 1024 == 4 * (turn0 + 3), "the turn did not take its knob"


def test_the_arrow_leads_to_the_key_then_to_the_gate(text):
    """Where the way to the district's plaza (its key) and the way to the
    core (its gate) part, the arrow takes the plaza's without the key and
    the core's with it. (Until P21b the two were swapped, in the game too.)"""
    b = Base(text)
    T, ox, oy, cm = b.const("CITY_TILE"), b.const("CITY_OXA"), b.const("CITY_OYA"), b.sym("city_map")
    w_of = lambda n: b.d[cm + n]                                        # noqa: E731
    n = next(n for n in range(256) if (w_of(n) >> 23) & 15 == 0 and w_of(n) & 0xFF
             and not w_of(n) & 0xAA and (w_of(n) >> 27) & 3 != (w_of(n) >> 29) & 3)
    core, plaza = (w_of(n) >> 27) & 3, (w_of(n) >> 29) & 3
    arrows = b.sym("arrows")
    for key, side in ((0, plaza), (1, core)):
        b.put(oy - (n // 16) * T, (n % 16) * T - ox, 256)              # facing north
        b.d[b.sym("key_held")] = key
        b.run(0, 30)
        tri = [b.d[spec.DL_BASE + 1 + k] for k in range(7)]
        shown = next(k for k in range(8) if [b.d[arrows + 7 * k + j] for j in range(7)] == tri)
        assert shown == 2 * side, f"key {key}: the arrow shows way {shown}, not side {side}"


def test_no_knob_can_break_him(text, monkeypatch):
    """On the second base tape the pick-up's knob was turned to -10 frames;
    the pick-up it began counted down from -10 for ever, and he stood bowed
    until the tape ended. Every knob turned as far as it goes, down and
    then up: he still picks up the key and comes out of it, still quick
    turns half round and no more, still walks. (The paint is skipped: the
    base reads nothing the paint answers, and this is 2,000 frames.)"""
    from zeta import gpu
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)
    for way in (D, U):
        b = Base(text)
        for k in range(10):
            for _ in range(60):
                b.run(SEL | way, 1)
                b.run(SEL, 1)
            b.run(SEL | RT, 1)
            b.run(SEL, 1)
        b.run(0, 2)
        kx, kz = b.cell("keypos") / 65536, b.cell("keypos", 1) / 65536
        b.put(kx, kz - 1.0, 0)
        b.run(0, 3)
        for f in range(12):
            b.run(X if f < 7 else 0, 1)
        assert b.cell("key_held") == 1, "the jab did not pick it up"
        b.run(0, 90)
        assert b.cell("pick_t") == 0 and b.cell("f_tilt") == 0, \
            f"he never came out of the pick-up (pick_t {b.cell('pick_t')})"
        y0 = b.cell("yaw")
        for f in range(80):
            b.run(D | (A if f < 9 else 0), 1)
        assert b.cell("qturn_left") == 0 and (b.cell("yaw") - y0) % 1024 == 512, "the quick turn broke"
        b.run(0, 20)
        p0 = b.pos()
        b.run(U, 60)
        assert np.hypot(*np.subtract(b.pos(), p0)) > 0.3, "he cannot walk"


def test_the_town_is_lit(text):
    """P22: the pieces and the ground are drawn lit (OBJ_LIT), their corners
    carrying how lit they are; the town's own dark is the light knob's level
    and a notch darker a district toward the core, with what burns kept at
    full; unlocking a gate flashes and the flash dies away."""
    b = Base(text)
    b.run(0, 3)
    d = b.d
    lit = [k for k in range(d[spec.OL_BASE])
           if d[spec.OL_BASE + 1 + k * spec.OL_STRIDE + 5] & spec.OBJ_LIT]
    assert len(lit) >= 3, "the street is not drawn lit"
    piece = d[b.sym("pieces")]                       # a piece: its corners' light
    nv = d[piece]
    ts = [(d[piece + 2 + 3 * nv + k] >> 8) & 255 for k in range(nv)]
    assert max(ts) == 127 and min(ts) < 30, f"no light and dark in a piece: {min(ts)}..{max(ts)}"
    amb0 = b.knob(6)
    assert d[spec.LIGHT_AMB] == amb0 and d[spec.LIGHT_AMB] + d[spec.LIGHT_DIF] in (33, 30)
    T, ox, oy, cm = b.const("CITY_TILE"), b.const("CITY_OXA"), b.const("CITY_OYA"), b.sym("city_map")
    n = next(n for n in range(256) if (d[cm + n] >> 23) & 15 == 4 and d[cm + n] & 0xFF)
    b.put(oy - (n // 16) * T, (n % 16) * T - ox, 0)
    b.run(0, 3)
    assert d[spec.LIGHT_AMB] == amb0 - 4, "district 4 is not darker"
    d[b.sym("light_flash")] = 20
    b.run(0, 1)
    assert d[spec.LIGHT_AMB] > amb0, "no flash"
    b.run(0, 30)
    assert d[spec.LIGHT_AMB] == amb0 - 4, "the flash did not die away"
