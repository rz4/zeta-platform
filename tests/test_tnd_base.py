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

    def lens(self):
        (x, z), d = self.pos(), self.d
        return np.hypot(x - _s32(d[spec.CAM_X]) / 65536, z - _s32(d[spec.CAM_Z]) / 65536)


def test_the_tank_has_weight_and_the_lens_keeps_its_distance(text):
    """The walk eases up to its pace and back down (it was a switch), the
    quick turn is Down + A, A alone is still the back dodge -- and at the
    start, the dead end's wall right behind him, the lens is the same 3.0
    behind as it is in the open street."""
    b = Base(text)
    b.run(0, 30)
    assert abs(b.lens() - 3.0) < 0.05, f"the lens is {b.lens():.2f} behind at the wall"
    steps, last = [], b.pos()
    for f in range(30):
        b.run(U, 1)
        p = b.pos()
        steps.append(np.hypot(p[0] - last[0], p[1] - last[1]))
        last = p
    assert steps[0] < 0.4 * 0.032 and steps[4] < 0.9 * 0.032, f"no lean into the walk: {steps[:6]}"
    assert abs(steps[-1] - 0.032) < 0.002, f"he never reached his pace: {steps[-1]:.4f}"
    assert all(b2 >= a2 - 1e-6 for a2, b2 in zip(steps, steps[1:])), "the walk stuttered"
    assert abs(b.lens() - 3.0) < 0.2
    b.run(0, 1)
    assert 0 < np.hypot(*np.subtract(b.pos(), last)) < 0.032, "he stopped dead"
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
    """Walking into a street's wall ten degrees off dead on, he keeps most
    of the slide knob's share of his pace along it (plainly, he crawled at
    a sixth); dead on, he stops. L and R are not in the base."""
    b = Base(text)
    T, ox, oy, cm = b.const("CITY_TILE"), b.const("CITY_OXA"), b.const("CITY_OYA"), b.sym("city_map")
    n = next(n for n in range(256) if (b.d[cm + n] & 0xFF) == 0x11)       # a street along x
    cx, cz = oy - (n // 16) * T, (n % 16) * T - ox
    for off, want in ((80, 0.6 * 0.032), (90, 0.0)):
        b = Base(text)
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
    p0 = b.pos()
    for f in range(12):
        b.run((X if f < 7 else 0) | U, 1)
    assert b.cell("key_held") == 1 and b.cell("pick_t") > 0, "the jab did not pick it up"
    b.run(U, 4)
    assert np.hypot(*np.subtract(b.pos(), p0)) < 0.2, "he walked off mid pick-up"
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
