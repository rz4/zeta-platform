"""TND's LAYER 2 (docs/TND-PORT.md P28): shadow boxing.

"we want to be able to control what gets thrown and where it lands
precisely." The strike goes the way the pad points the frame it is thrown
and lands on its own frame on the line he then faces; his body comes round
inside the wind-up and he stays facing it; the strings are the player's
own; the strikes are authored to land on his centre line (P29).
A local build (TND_LAYER=2 -> build/layer2/tnd.zol).
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
CART = ROOT / "build" / "layer2" / "tnd.zol"
pytestmark = pytest.mark.skipif(not (ROOT / "assets" / "tnd" / "boxer.npz").is_file(),
                                reason="the layer builds from the third-party bake")
U, D, LF, RT, X, Y, L = (spec.PAD_UP, spec.PAD_DOWN, spec.PAD_LEFT, spec.PAD_RIGHT,
                         spec.PAD_X, spec.PAD_Y, spec.PAD_L)
MOVES = ("jab", "cross", "lead_hook", "rear_hook", "special", "lead_uppercut",
         "rear_uppercut", "gun", "gun_charged")
PIVOT, PIVOTH, LUNGE, STEADY, PAUSE = range(5)          # the layer's knobs


@pytest.fixture(scope="module")
def text():
    if not CART.is_file() or CART.stat().st_mtime < GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="2")
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
        self.run(0, 90)                       # at the start: far from any key

    def sym(self, n):
        return next(int(l.rsplit(" at ", 1)[1]) for l in self.text if l.startswith(f"; {n}: "))

    def cell(self, n, k=0):
        return _s32(self.d[self.sym(n) + k])

    def knob(self, k):
        return self.cell("knobs", k)

    def run(self, pad, n):
        for _ in range(n):
            self.m.frame(pad)

    def pos(self):
        return self.cell("px") / 65536, self.cell("pz") / 65536

    def throw(self, way, button, frames=90):
        """a thumb's press of `button` with `way` held; -> (the move thrown,
        how far his heading turned, the biggest turn in any one frame, the
        frame its clock first ran)"""
        y0, mv, big, began = self.cell("yaw"), None, 0, None
        for f in range(frames):
            last = self.cell("yaw")
            self.run((way | button) if f < 7 else 0, 1)
            big = max(big, abs((self.cell("yaw") - last + 512) % 1024 - 512))
            if self.cell("anim") == 2:
                mv = self.cell("f_mv")
                if began is None and self.cell("af") > 0:
                    began = f
        return MOVES[mv] if mv is not None else None, (self.cell("yaw") - y0 + 512) % 1024 - 512, big, began


def _landing(g, way, button, frames=90):
    """throw it; -> (the move, the turn, the biggest turn in a frame, the frame
    the spark lit, where it lit in HIS frame: ahead, off his line, up)"""
    y0, mv, big, lit = g.cell("yaw"), None, 0, None
    for f in range(frames):
        last = g.cell("yaw")
        g.run((way | button) if f < 7 else 0, 1)
        big = max(big, abs((g.cell("yaw") - last + 512) % 1024 - 512))
        if g.cell("anim") == 2:
            mv = g.cell("f_mv")
        if lit is None and g.cell("spark", 3) > 0:
            yaw = g.cell("yaw") * 2 * np.pi / 1024
            dx, dz = g.cell("spark") / 65536 - g.pos()[0], g.cell("spark", 2) / 65536 - g.pos()[1]
            lit = (f, -np.sin(yaw) * dx + np.cos(yaw) * dz, np.cos(yaw) * dx + np.sin(yaw) * dz,
                   g.cell("spark", 1) / 65536)
    return MOVES[mv] if mv is not None else None, (g.cell("yaw") - y0 + 512) % 1024 - 512, big, lit


@pytest.mark.parametrize("way,angle", [(0, 0), (U, 0), (LF, 256), (RT, -256), (D, 512), (U | LF, 128)])
def test_the_jab_lands_where_he_points_it_on_its_own_frame(text, way, angle):
    """P29: "the intention is to place the jab exactly where we want it ...
    I should be able to anticipate where the jab will land". Whichever way
    the pad points, the jab lands on the SAME frame, at the same reach and
    height, dead on the line he then faces (the spark is where it landed);
    his body comes round to it inside the wind-up -- never in one frame
    when it is more than the knob's turn -- and he stays facing it."""
    g = Game(text)
    mv, turned, big, lit = _landing(g, 0, X)
    assert mv == "jab" and turned == 0 and lit is not None
    frame0, ahead0, off0, up0 = lit
    assert abs(off0) < 0.02 and 0.6 < ahead0 < 0.8 and 1.1 < up0 < 1.35, f"the jab ahead lands at {lit}"
    g.run(0, 80)
    mv, turned, big, lit = _landing(g, way, X)
    assert mv == "jab"
    assert abs(turned) == abs(angle) and (abs(angle) in (0, 512) or turned == angle), f"turned {turned}, not {angle}"
    assert big <= g.knob(PIVOT), f"a frame turned him {big}"
    frame, ahead, off, up = lit
    assert frame == frame0, f"that way it landed on frame {frame}, not {frame0}"
    assert abs(off) < 0.02 and abs(ahead - ahead0) < 0.02 and abs(up - up0) < 0.02, f"it landed at {lit[1:]}"
    y = g.cell("yaw")
    g.run(0, 60)
    assert g.cell("yaw") == y, "he did not stay facing it"


def _string(g, presses, gaps):
    g.run(0, 140)
    seen = []
    for b, gap in zip(presses, gaps):
        for f in range(gap):
            g.run(b if f < 6 else 0, 1)
            if g.cell("anim") == 2 and g.cell("af") == 1:
                seen.append(MOVES[g.cell("f_mv")])
    g.run(0, 70)
    return seen


def test_the_strings_are_the_players(text):
    """"two combo jab jab, three combo jab jab left hiok, jab jab wait right
    upper cut. hay maker is the special button with no previous jab input."
    And every one of them lands on his centre line."""
    g = Game(text)
    assert _string(g, (X, X), (20, 50)) == ["jab", "jab"]
    assert _string(g, (X, X, X), (20, 20, 60)) == ["jab", "jab", "lead_hook"]
    assert _string(g, (X, X, X), (20, 44, 70)) == ["jab", "jab", "rear_uppercut"]
    assert _string(g, (Y,), (80,)) == ["special"]
    assert _string(g, (X, Y), (20, 70)) == ["jab"], "Y was read inside a string"
    for presses, gaps, last in (((X, X, X), (20, 20, 60), "lead_hook"),
                                ((X, X, X), (20, 44, 70), "rear_uppercut"), ((Y,), (80,), "special")):
        g.run(0, 140)
        lit, was = [], 0
        for b, gap in zip(presses, gaps):
            for f in range(gap):
                g.run(b if f < 6 else 0, 1)
                before, was = was, g.cell("spark", 3)
                if was > before:                  # (a spark just lit)
                    yaw = g.cell("yaw") * 2 * np.pi / 1024
                    dx, dz = g.cell("spark") / 65536 - g.pos()[0], g.cell("spark", 2) / 65536 - g.pos()[1]
                    lit.append((MOVES[g.cell("f_mv")], np.cos(yaw) * dx + np.sin(yaw) * dz))
        assert lit and lit[-1][0] == last and all(abs(off) < 0.03 for _, off in lit), \
            f"{presses}: off his line: {lit}"


def test_the_layers_under_it_still_stand(text, monkeypatch):
    """The base's walk and quick turn, and the left shoulder's boxer and
    run, are all still here; and the layer's knobs, at either end, break
    nothing (a blow still lands its clock and ends)."""
    from zeta import gpu
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)
    SEL = spec.PAD_SELECT
    for way in (D, U):
        g = Game(text)
        for k in range(5):
            for _ in range(60):
                g.run(SEL | way, 1)
                g.run(SEL, 1)
            g.run(SEL | RT, 1)
            g.run(SEL, 1)
        g.run(0, 2)
        mv, turned, big, began = g.throw(D, X, frames=200)
        assert mv == "jab" and abs(turned) == 512 and began is not None, (mv, turned, began)
        assert g.cell("anim") != 2 and g.cell("pivot_on") == 0, "the blow never ended"
        p0 = g.pos()
        g.run(U, 40)
        assert np.hypot(*np.subtract(g.pos(), p0)) > 0.5, "he cannot walk"
        g.run(L, 30)
        assert g.cell("f_sty") == 2, "no boxer"
        g.run(0, 20)
        g.run(L, 3)
        g.run(0, 2)
        g.run(L | U, 30)
        assert g.cell("f_sty") == 1, "no run"
