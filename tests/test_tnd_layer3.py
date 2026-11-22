"""TND's LAYER 3 (docs/TND-PORT.md P35): the right shoulder -- targeting.

R held, the district's item in reach (the key; the key held, its gate), he
squares up to it: his steering -- in the boxer, his cross -- comes round to
its bearing and stays there, his body with it. He is planted (the tank
neither walks nor turns); the boxer's steps go round it; a blow or a shot
goes AT it whatever the pad says. Not in the run; nothing in reach, nothing.
A local build (TND_LAYER=3 -> build/layer3/tnd.zol).
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
CART = ROOT / "build" / "layer3" / "tnd.zol"
pytestmark = pytest.mark.skipif(not (ROOT / "assets" / "tnd" / "boxer.npz").is_file(),
                                reason="the layer builds from the third-party bake")
U, D, LF, RT, A, B, X, Y, L, R = (spec.PAD_UP, spec.PAD_DOWN, spec.PAD_LEFT, spec.PAD_RIGHT, spec.PAD_A,
                                  spec.PAD_B, spec.PAD_X, spec.PAD_Y, spec.PAD_L, spec.PAD_R)
MOVES = ("jab", "cross", "lead_hook", "rear_hook", "special", "lead_uppercut",
         "rear_uppercut", "gun", "gun_charged")


@pytest.fixture(scope="module")
def text():
    if not CART.is_file() or CART.stat().st_mtime < GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="3")
        env.pop("TND_SONG", None)
        env.pop("TND_OUT", None)
        subprocess.run([sys.executable, str(GEN)], check=True, env=env, cwd=ROOT,
                       stdout=subprocess.DEVNULL)
    return CART.read_text().splitlines()


def _s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


def _wrap(a):
    return (a + 512) % 1024 - 512


class Game:
    def __init__(self, text, at=None, yaw=0):
        """at: where he is put, from the item (x, z) -- else the start, far from it"""
        self.text = text
        self.m = cabinet.VirtualMachine(cabinet.load_cart(CART))
        self.m.frame(spec.PAD_START)
        self.d = self.m.vm.dmem
        self.run(0, 30)
        self.item = self.cell("ctx_x") / 65536, self.cell("ctx_z") / 65536
        if at is not None:
            for name, v in (("px", self.item[0] + at[0]), ("pz", self.item[1] + at[1])):
                self.d[self.sym(name)] = int(v * 65536) & 0xFFFFFFFF
            for name in ("yaw", "head", "cam_yaw"):
                self.d[self.sym(name)] = yaw
            self.run(0, 20)

    def sym(self, n):
        return next(int(l.rsplit(" at ", 1)[1]) for l in self.text if l.startswith(f"; {n}: "))

    def cell(self, n, k=0):
        return _s32(self.d[self.sym(n) + k])

    def run(self, pad, n):
        for _ in range(n):
            self.m.frame(pad)

    def pos(self):
        return self.cell("px") / 65536, self.cell("pz") / 65536

    def bearing(self):
        """the item's, from him, as a yaw (forward is (-sin, cos))"""
        dx, dz = self.item[0] - self.pos()[0], self.item[1] - self.pos()[1]
        return round(np.arctan2(-dx, dz) * 1024 / (2 * np.pi)) % 1024

    def far(self):
        return float(np.hypot(self.item[0] - self.pos()[0], self.item[1] - self.pos()[1]))


def test_r_squares_him_up_to_the_item_and_plants_him(text):
    """R held, the key six units off and behind him: his steering and his
    body come round to it (a half turn in under a quarter second) and stay;
    the key is outlined and marked. The pad neither walks nor turns him.
    Let go, he stands as it left him and the pad is his again."""
    g = Game(text, at=(3.0, 6.0), yaw=0)
    want, p0 = g.bearing(), g.pos()
    assert abs(_wrap(want - g.cell("yaw"))) > 256, "the test: it was not behind him"
    g.run(R, 14)
    assert g.cell("locked") == 1 and abs(_wrap(g.cell("yaw") - want)) <= 1, (g.cell("yaw"), want)
    assert g.cell("head") == g.cell("yaw"), "his body is not on it"
    marked = g.d[spec.OL_BASE]
    g.run(0, 1)                                   # (the same view, a frame on, and no lock)
    assert g.d[spec.OL_BASE] == marked - 1, "the lock's mark"
    g.run(R, 2)
    for pad in (U, D, LF, RT):
        g.run(R | pad, 20)
        assert g.pos() == p0 and abs(_wrap(g.cell("yaw") - want)) <= 1, "locked, the pad moved him"
    g.run(0, 20)
    assert g.cell("locked") == 0 and abs(_wrap(g.cell("yaw") - want)) <= 1
    g.run(LF, 10)
    assert _wrap(g.cell("yaw") - want) > 100, "let go, the tank does not turn"
    g.run(U, 30)
    assert np.hypot(*np.subtract(g.pos(), p0)) > 1.0, "let go, he does not walk"


def test_locked_a_shot_and_a_blow_go_at_it_whatever_the_pad_says(text):
    """Locked, the gun's line is at the item (a tap, with Left held: the key
    is struck), and a jab with Down held is thrown AT it -- his body does
    not turn away, and its lunge carries him nearer."""
    g = Game(text, at=(-4.0, 5.0), yaw=300)
    g.run(R, 20)
    want = g.bearing()
    g.run(R | LF | B, 5)
    g.run(R | LF, 14)
    assert g.cell("key_hit") > 0, "locked, the shot missed the key"
    assert abs(_wrap(g.cell("head") - want)) <= 1 and g.cell("yaw") == g.cell("head")
    g.run(R, 40)
    far = g.far()
    g.run(R | D | X, 5)
    seen = set()
    for _ in range(20):
        g.run(R | D, 1)
        if g.cell("anim") == 2:
            seen.add((MOVES[g.cell("f_mv")], abs(_wrap(g.cell("head") - g.bearing())) <= 2))
    assert seen == {("jab", True)}, seen
    assert g.far() < far - 0.1, "the jab did not carry him toward it"
    assert g.cell("key_held") == 1 or g.far() > 1.0


def test_locked_the_boxers_steps_go_round_it(text):
    """L + R: the boxer's cross is the item's bearing. Left and Right step
    ROUND it -- a quarter of the way round and no nearer or farther than a
    step -- his body on it all the way; Up steps in."""
    g = Game(text, at=(0.0, 7.0), yaw=512)
    g.run(R | L, 20)
    assert g.cell("f_sty") == 2 and g.cell("locked") == 1
    b0, far = g.bearing(), g.far()
    for _ in range(150):
        g.run(R | L | LF, 1)
        assert abs(_wrap(g.cell("yaw") - g.bearing())) <= 48, "his cross left the item"
    assert abs(_wrap(g.bearing() - b0)) > 128, "he did not go round it"
    assert abs(g.far() - far) < 1.5, (far, g.far())
    g.run(R | L, 20)
    far = g.far()
    g.run(R | L | U, 40)
    assert g.far() < far - 1.0, "Up did not step in"


def test_nothing_in_reach_r_is_nothing_and_not_in_the_run(text):
    """At the start the key is far out of the lock's reach: R does nothing,
    and the pad is his. In the run R is not read."""
    g = Game(text)
    assert g.far() > 20
    p0, y0 = g.pos(), g.cell("yaw")
    g.run(R, 20)
    assert g.cell("locked") == 0 and g.cell("yaw") == y0
    g.run(R | U, 30)
    assert np.hypot(*np.subtract(g.pos(), p0)) > 1.0, "R held, he could not walk"
    g = Game(text, at=(8.0, 8.0), yaw=g.cell("yaw"))
    g.run(L, 3)
    g.run(0, 2)
    g.run(L | U, 20)
    assert g.cell("f_sty") == 1, "no run"
    y0 = g.cell("yaw")
    g.run(L | U | R, 20)
    assert g.cell("locked") == 0 and g.cell("yaw") == y0 and g.cell("f_sty") == 1, "the run was taken by the lock"


def test_the_layers_under_it_still_stand(text):
    """Without R it is layer 2: a jab, the count's terminator, a shot that
    is a bullet, the aim, the boxer."""
    g = Game(text)
    g.run(X, 5)
    g.run(0, 3)
    assert g.cell("anim") == 2 and MOVES[g.cell("f_mv")] == "jab"
    g.run(0, 40)
    g.run(Y, 5)
    g.run(0, 3)
    assert g.cell("anim") == 2 and MOVES[g.cell("f_mv")] == "lead_hook"
    g.run(0, 60)
    g.run(B, 20)
    assert g.cell("aimed") and g.cell("slow_on")
    g.run(0, 4)
    assert max(g.cell(f"bul{i}_rem") for i in (0, 1)) > 0, "no bullet"
    g.run(0, 40)
    g.run(L, 30)
    assert g.cell("f_sty") == 2, "no boxer"
