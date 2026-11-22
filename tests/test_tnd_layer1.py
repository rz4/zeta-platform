"""TND's LAYER 1 (docs/TND-PORT.md P24): the base, and the left shoulder.

L held is BOXING -- he squares up and the lens backs off. L clicked twice
and held is the RUN -- the fastest, with momentum, the lens trailing. A
jumps in either, and A again flips. A local build (TND_LAYER=1 ->
build/layer1/tnd.zol), made here when missing or stale.
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
CART = ROOT / "build" / "layer1" / "tnd.zol"
pytestmark = pytest.mark.skipif(not (ROOT / "assets" / "tnd" / "boxer.npz").is_file(),
                                reason="the layer builds from the third-party bake")
U, D, LF, RT, A, L, R = (spec.PAD_UP, spec.PAD_DOWN, spec.PAD_LEFT, spec.PAD_RIGHT,
                         spec.PAD_A, spec.PAD_L, spec.PAD_R)
# knobs, as the layer's tuner numbers them
RUN, RUNACC, RUNTURN, GRIP, RUNCAM, TRAIL, BOXCAM, BOXSTEP, JUMP, DCLICK = range(10)


@pytest.fixture(scope="module")
def text():
    if not CART.is_file() or CART.stat().st_mtime < GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="1")
        env.pop("TND_SONG", None)
        env.pop("TND_OUT", None)
        subprocess.run([sys.executable, str(GEN)], check=True, env=env, cwd=ROOT,
                       stdout=subprocess.DEVNULL)
    return CART.read_text().splitlines()


def _s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


class Game:
    def __init__(self, text):
        self.text = text
        self.m = cabinet.VirtualMachine(cabinet.load_cart(CART))
        self.m.frame(spec.PAD_START)
        self.d = self.m.vm.dmem
        # a long street to move in: the first straight along zeta x
        T, ox, oy, cm = (self.const("CITY_TILE"), self.const("CITY_OXA"), self.const("CITY_OYA"),
                         self.sym("city_map"))
        n = next(n for n in range(256) if (self.d[cm + n] & 0xFF) == 0x11)
        for name, v in (("px", oy - (n // 16) * T), ("pz", (n % 16) * T - ox)):
            self.d[self.sym(name)] = int(round(v * 65536)) & 0xFFFFFFFF
        self.d[self.sym("yaw")] = self.d[self.sym("cam_yaw")] = 256
        self.run(0, 90)

    def sym(self, n):
        return next(int(l.rsplit(" at ", 1)[1]) for l in self.text if l.startswith(f"; {n}: "))

    def const(self, n):
        return next(int(l.split()[2]) for l in self.text if l.startswith(f".const {n} "))

    def cell(self, n, k=0):
        return _s32(self.d[self.sym(n) + k])

    def knob(self, k):
        return self.cell("knobs", k)

    def run(self, pad, n):
        for _ in range(n):
            self.m.frame(pad)

    def pos(self):
        return self.cell("px") / 65536, self.cell("pz") / 65536

    def lens(self):
        (x, z), d = self.pos(), self.d
        return np.hypot(x - _s32(d[spec.CAM_X]) / 65536, z - _s32(d[spec.CAM_Z]) / 65536)

    def click_twice(self, hold):
        """L down a thumb's nine frames, up seven, down again and held"""
        self.run(L, 9)
        self.run(0, 7)
        self.run(L | hold, 1)


def test_l_held_is_the_boxer_and_the_lens_backs_off(text):
    """One press of L, held: he squares up -- the boxer, on the cross he
    faced, stepping sideways without turning -- and the lens eases back to
    the boxer's distance, farther than the tank's. Let go: the tank, and
    the lens comes back in. R is not in this layer."""
    g = Game(text)
    near = g.lens()
    g.run(L, 70)
    assert g.cell("f_sty") == 2 and g.cell("f_frun") == 0, "L held is not the boxer"
    assert abs(g.lens() - g.knob(BOXCAM) / 65536) < 0.05 and g.lens() > near + 0.3, \
        f"the lens did not back off ({near:.2f} -> {g.lens():.2f})"
    y0, p0 = g.cell("yaw"), g.pos()
    g.run(L | LF, 30)
    assert g.cell("yaw") == y0, "the boxer turned"
    assert np.hypot(*np.subtract(g.pos(), p0)) > 0.8, "the boxer did not step"
    g.run(0, 70)
    assert g.cell("f_sty") == 0 and abs(g.lens() - near) < 0.1, "letting go did not give the tank back"
    g.run(R | L, 20)
    assert g.cell("f_tgt") == 0 and g.cell("f_sty") == 2, "R did something"


def test_l_twice_is_the_run_with_momentum_and_a_trailing_lens(text):
    """L clicked twice and held: the run. It builds to the fastest pace in
    the game (about twice the walk); turning, his path lags his heading
    (momentum) and the lens lags both (it trails), coming round after; a
    slow second press is only the boxer; letting go ends it."""
    g = Game(text)
    g.click_twice(U)
    assert g.cell("f_sty") == 1 and g.cell("f_frun") == 1, "L twice is not the run"
    last, steps = g.pos(), []
    for f in range(80):
        g.run(L | U, 1)
        p = g.pos()
        steps.append(np.hypot(p[0] - last[0], p[1] - last[1]))
        last = p
    top = 0.13 * g.knob(RUN) / 65536
    assert steps[1] < 0.85 * top, "the run had no build"
    assert abs(steps[-1] - top) < 0.006, f"the run's pace is {steps[-1]:.3f}, not {top:.3f}"
    assert g.lens() > g.knob(RUNCAM) / 65536 - 0.1, "the lens did not fall back for the run"
    lag_path, lag_lens = [], []
    for f in range(30):
        g.run(L | U | LF, 1)
        p = g.pos()
        head = np.arctan2(-(p[0] - last[0]), p[1] - last[1]) * 1024 / (2 * np.pi)
        lag_path.append((g.cell("yaw") - head + 512) % 1024 - 512)
        lag_lens.append((g.cell("yaw") - g.d[spec.CAM_YAW] + 512) % 1024 - 512)
        last = p
    assert g.cell("yaw") == (256 + 30 * g.knob(RUNTURN)) % 1024
    assert lag_path[-1] > 0.5, f"no momentum: his path is {lag_path[-1]:.1f} behind his heading"
    assert lag_lens[-1] > 30, f"the lens does not trail ({lag_lens[-1]})"
    g.run(L | U, 90)
    assert abs((g.cell("yaw") - g.d[spec.CAM_YAW] + 512) % 1024 - 512) <= 1, "the lens never came round"
    g.run(L, 40)                                 # the run held, nothing driven: he stands
    assert g.cell("f_sty") == 1 and g.cell("anim") == 0, \
        f"stationary in the run he is not standing (anim {g.cell('anim')})"
    p0 = g.pos()
    g.run(L, 20)
    assert np.hypot(*np.subtract(g.pos(), p0)) < 0.05, "standing, he drifted"
    g.run(L | U, 3)
    assert g.cell("anim") == 5, "driven again, he did not run"
    g.run(0, 30)
    assert g.cell("f_sty") == 0, "letting go did not end the run"
    g.run(L, 9)
    g.run(0, g.knob(DCLICK) + 6)
    g.run(L | U, 20)
    assert g.cell("f_sty") == 2, "a slow second press ran him"


@pytest.mark.parametrize("stance", ["boxer", "run"])
def test_a_jumps_and_a_again_flips(text, stance):
    """In the boxer and in the run: A is a jump, up and down again; A a
    second time in the air is the flip, which carries him higher. In the
    tank A is still the dodge, on the ground."""
    g = Game(text)
    g.run(A, 8)
    g.run(0, 4)
    assert g.cell("f_py") == 0, "the tank's A left the ground"
    g.run(0, 40)
    if stance == "run":
        g.click_twice(U)
        hold, sty = L | U, 1
    else:
        hold, sty = L, 2
    g.run(hold, 40)
    assert g.cell("f_sty") == sty
    top = 0
    for f in range(70):
        g.run(hold | (A if f < 8 else 0), 1)
        assert g.cell("f_evf") == 0, "one press flipped"
        top = max(top, g.cell("f_py") / 65536)
    assert top > 0.8 and g.cell("f_py") == 0, f"the jump: {top:.2f} up, landed {g.cell('f_py') == 0}"
    top2, flipped = 0, False
    for f in range(90):
        g.run(hold | (A if f < 8 or 14 <= f < 22 else 0), 1)
        flipped |= g.cell("f_evf") > 0
        top2 = max(top2, g.cell("f_py") / 65536)
    assert flipped, "A again did not flip"
    assert top2 > top + 0.5 and g.cell("f_py") == 0, "the flip did not carry him up and down again"


def test_no_knob_of_the_layer_can_break_him(text, monkeypatch):
    """Every knob of the layer's page turned as far as it goes, down and
    then up (a knob once hung the base): he still boxes, runs and gets
    somewhere, jumps and lands, flips and lands, and comes back to the
    tank. (The paint is skipped: the layer reads nothing it answers.)"""
    from zeta import gpu
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)
    SEL = spec.PAD_SELECT
    for way in (D, U):
        g = Game(text)
        for k in range(10):
            for _ in range(60):
                g.run(SEL | way, 1)
                g.run(SEL, 1)
            g.run(SEL | RT, 1)
            g.run(SEL, 1)
        g.run(0, 2)
        g.run(L, 30)
        assert g.cell("f_sty") == 2, "no boxer"
        for f in range(240):
            g.run(L | (A if f < 8 or 14 <= f < 22 else 0), 1)
        assert g.cell("f_py") == 0 and g.cell("f_evf") == 0, "he never came down"
        g.run(0, 60)
        g.run(L, 3)                                # (clicks to fit the narrowest window)
        g.run(0, 2)
        p0 = g.pos()
        g.run(L | U, 120)
        assert g.cell("f_sty") == 1, "no run"
        assert np.hypot(*np.subtract(g.pos(), p0)) > 2, "the run went nowhere"
        g.run(0, 90)
        assert g.cell("f_sty") == 0 and g.cell("f_py") == 0
        for f in range(40):                        # (at the fastest he has run the street's
            g.run(D | (A if f < 9 else 0), 1)       # length and faces its end: about, first)
        p0 = g.pos()
        g.run(U, 40)
        assert np.hypot(*np.subtract(g.pos(), p0)) > 0.5, "the tank cannot walk after it"


def test_a_wall_in_the_air_is_a_wall_to_jump_from(text):
    """P25, "would be cool if we could do a wall jump": running at a wall he
    jumps, meets it in the air, and A kicks him off it -- turned about (his
    heading mirrored in the wall), thrown back across the street and up
    again. The far wall met in the same air is a second; a third is
    refused; he comes down and the count is new. On the ground A at a wall
    is only the jump."""
    g = Game(text)
    cz = g.pos()[1]
    g.d[g.sym("yaw")] = g.d[g.sym("cam_yaw")] = 0            # at the street's wall
    g.run(0, 20)
    g.click_twice(U)
    g.run(L | U, 12)
    kicks, top, sides = [], 0.0, []
    for f in range(200):
        pad = L | U | (A if f < 8 else 0)
        if g.cell("wall_t") and not g.cell("f_evf") and f > 8 and f % 3 == 0:
            pad |= A                                         # A as he meets a wall
        n0, y0 = g.cell("wall_n"), g.cell("yaw")
        g.run(pad, 1)
        if g.cell("wall_n") > n0:
            kicks.append((y0, g.cell("yaw")))
            sides.append(np.sign(g.pos()[1] - cz))
        top = max(top, g.cell("f_py") / 65536)
        if f > 20 and g.cell("f_py") == 0:
            break
    assert len(kicks) == 2, f"{len(kicks)} wall jumps in the one air, not two"
    assert all((a + b) % 1024 == 512 for a, b in kicks), f"not turned about in the wall: {kicks}"
    assert sides[0] != sides[1], "the second was not off the far wall"
    assert top > 3.0, f"the wall jumps did not carry him up ({top:.2f})"
    assert g.cell("f_py") == 0 and g.cell("wall_n") == 0, "he did not come down with the count new"
    g.run(0, 40)
    g.run(L, 20)
    for f in range(30):
        g.run(L | U | (A if f < 8 else 0), 1)
    assert g.cell("wall_n") == 0
