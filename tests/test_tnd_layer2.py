"""TND's LAYER 2 (docs/TND-PORT.md P28): shadow boxing.

"we want to be able to control what gets thrown and where it lands
precisely ... it should feel like theirs weight to each and the player
shouldnt be looking like he's just teleported to the other directions."
The strike goes the way the pad points, he PIVOTS there at a turn a frame
and stays facing it, and Y throws the heavy version of what X would have.
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


def test_a_strike_ahead_is_thrown_at_once(text):
    """Nothing held (or Up): the jab goes where he faces -- no turn, its
    clock running from the frame it is read."""
    g = Game(text)
    mv, turned, big, began = g.throw(0, X)
    assert mv == "jab" and turned == 0 and big == 0, (mv, turned, big)
    assert began is not None and began <= 5, f"the jab ahead waited ({began})"
    g.run(0, 80)
    mv, turned, big, _ = g.throw(U, X)
    assert mv == "jab" and turned == 0 and big == 0, (mv, turned, big)


@pytest.mark.parametrize("way,angle", [(LF, 256), (RT, -256), (D, 512), (U | LF, 128)])
def test_he_pivots_to_where_it_goes_and_stays(text, way, angle):
    """The pad's way with X: he turns there at the pivot knob's units a
    frame -- never more in one frame: no teleport -- the blow's clock held
    until he is there, so the farther round, the later it lands; and when
    it is done he is still facing it."""
    g = Game(text)
    rate = g.knob(PIVOT)
    mv, turned, big, began = g.throw(way, X)
    assert mv == "jab"
    assert abs(turned) == abs(angle) and (abs(angle) == 512 or turned == angle), \
        f"he turned {turned}, not {angle}"
    assert 0 < big <= rate, f"a frame turned him {big} (the knob is {rate})"
    assert began >= abs(angle) // rate + 3, f"the blow did not wait for the pivot (clock at {began})"
    y = g.cell("yaw")
    g.run(0, 60)
    assert g.cell("yaw") == y, "he did not stay facing it"


def test_y_is_the_heavy_version_and_turns_slower(text):
    """Y takes the string's next place as X would and throws that blow's
    heavy: alone, the lead hook where X is the jab; X X Y Y is jab, cross,
    the lead uppercut, the haymaker; four Ys are the two hooks, the
    uppercut, the haymaker. A heavy blow pivots at its own, slower knob."""
    g = Game(text)
    mv, turned, big, began = g.throw(LF, Y)
    assert mv == "lead_hook", f"Y alone threw {mv}"
    assert turned == 256 and 0 < big <= g.knob(PIVOTH) < g.knob(PIVOT)
    for presses, want in (((X, X, X, X), ["jab", "cross", "lead_hook", "rear_uppercut"]),
                          ((X, X, Y, Y), ["jab", "cross", "lead_uppercut", "special"]),
                          ((Y, Y, Y, Y), ["lead_hook", "rear_hook", "lead_uppercut", "special"])):
        g.run(0, 140)
        seen = []
        for b in presses:
            for f in range(44 if b == Y else 24):
                g.run(b if f < 6 else 0, 1)
                if g.cell("anim") == 2 and (not seen or seen[-1] != g.cell("f_mv")):
                    seen.append(g.cell("f_mv"))
        assert [MOVES[m] for m in seen] == want, f"{presses}: {[MOVES[m] for m in seen]}"


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
