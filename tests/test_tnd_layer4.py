"""TND's LAYER 4 (docs/TND-PORT.md P37): the enemies, and choosing among them.

Six bodies from the cart (an elite, a common, four of the horde) come up the
street at him, each to its own stand-off, and stand in the guard. R held
ALONE chooses: the nearest target in reach, Left and Right the next one
round him, Up and Down the spot on it (high, mid, low -- it stays) -- and
with R alone the pad never moves him, in slowed time or not. A locked shot
goes at the spot; a round or a fist that lands takes from what the enemy
has, holds it, and with nothing left it goes down and comes back.
A local build (TND_LAYER=4 -> build/layer4/tnd.zol); it needs the cart-mesh
core (frontier 20) on the machine.
"""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from zeta import cabinet, gpu, spec

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "games" / "tnd" / "gen_tnd.py"
CART = ROOT / "build" / "layer4" / "tnd.zol"
pytestmark = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "clips_190.npz").is_file(),
                                reason="the layer builds from the local tier files (build/tiers)")
U, D, LF, RT, A, B, X, Y, L, R = (spec.PAD_UP, spec.PAD_DOWN, spec.PAD_LEFT, spec.PAD_RIGHT, spec.PAD_A,
                                  spec.PAD_B, spec.PAD_X, spec.PAD_Y, spec.PAD_L, spec.PAD_R)
NE = 6
STAND = (2.4, 2.1, 1.8, 1.8, 1.8, 1.8)                   # each one's stand-off: its size's
RING = [(k * 171 + 60) % 1024 for k in range(NE)]        # ...and its own bearing from him, a sixth round each
HP = (8, 5, 3, 3, 3, 3)


@pytest.fixture(scope="module")
def text():
    if not CART.is_file() or CART.stat().st_mtime < GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="4")
        for k in ("TND_SONG", "TND_OUT", "TND_CROWD", "TND_CARTMESH"):
            env.pop(k, None)
        subprocess.run([sys.executable, str(GEN)], check=True, env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    return CART.read_text().splitlines()


@pytest.fixture(autouse=True)
def no_paint(monkeypatch):
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)


def _s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


def _wrap(a):
    return (a + 512) % 1024 - 512


class Game:
    def __init__(self, text, settle=0):
        self.text = text
        self.m = cabinet.VirtualMachine(cabinet.load_cart(CART))
        self.m.frame(spec.PAD_START)
        self.d = self.m.vm.dmem
        self.run(0, 30 + settle)

    def sym(self, n):
        return next(int(l.rsplit(" at ", 1)[1]) for l in self.text if l.startswith(f"; {n}: "))

    def cell(self, n, k=0):
        return _s32(self.d[self.sym(n) + k])

    def poke(self, n, v, k=0):
        self.d[self.sym(n) + k] = int(v) & 0xFFFFFFFF

    def run(self, pad, n):
        for _ in range(n):
            self.m.frame(pad)

    def pos(self):
        return self.cell("px") / 65536, self.cell("pz") / 65536

    def enemy(self, k):
        return self.cell(f"e{k}_pos") / 65536, self.cell(f"e{k}_pos", 1) / 65536

    def far(self, k):
        return float(np.hypot(*np.subtract(self.enemy(k), self.pos())))

    def bearing(self, k):
        (ex, ez), (px, pz) = self.enemy(k), self.pos()
        return round(np.arctan2(-(ex - px), ez - pz) * 1024 / (2 * np.pi)) % 1024

    def nearest(self):
        return min((k for k in range(NE) if self.cell(f"e{k}_st") == 1 and self.far(k) < 20), key=self.far)

    def tap(self, pad, hold=R, down=4, up=4):
        self.run(hold | pad, down)
        self.run(hold, up)


def test_the_enemies_come_at_him_and_ring_him(text):
    """each walks to its own place round him -- its size's stand-off out, a
    sixth of the way round from the last -- and stands there in the guard,
    facing him; when he moves the ring moves, and they come after. (In the
    street's width a wall may hold one short of its place: it stands.)"""
    g = Game(text)
    start = [g.far(k) for k in range(NE)]
    assert all(g.cell(f"e{k}_st") == 1 for k in range(NE)) and min(start) > 4
    walked = [0] * NE
    for _ in range(600):
        g.run(0, 1)
        for k in range(NE):
            walked[k] += g.cell(f"e{k}_walk")

    def off(k):                                   # how far it is from its place
        a = RING[k] * 2 * np.pi / 1024
        want = (g.pos()[0] - np.sin(a) * STAND[k], g.pos()[1] + np.cos(a) * STAND[k])
        return float(np.hypot(*np.subtract(g.enemy(k), want)))
    for k in range(NE):
        assert off(k) <= 0.31, (k, off(k), g.far(k))
        assert abs(g.far(k) - STAND[k]) <= 0.31
        assert abs(_wrap(g.cell(f"e{k}_yaw") - (g.bearing(k) + 512))) <= 20, "it does not face him"
        assert walked[k] > 40 and g.cell(f"e{k}_walk") == 0
    bearings = sorted(g.bearing(k) for k in range(NE))
    assert min((b - a) % 1024 for a, b in zip(bearings, bearings[1:] + bearings[:1])) > 100, "they do not ring him"
    p0 = g.pos()
    g.run(U, 60)                                  # he walks up the street: the ring goes with him
    assert g.pos() != p0
    g.run(0, 300)
    assert all(g.far(k) <= STAND[k] + 0.31 for k in range(NE)), [g.far(k) for k in range(NE)]


def test_r_alone_takes_the_nearest_and_the_pad_steps_round_them(text):
    g = Game(text, settle=400)
    p0 = g.pos()
    g.run(R, 3)
    first = g.cell("t_sel")
    assert g.cell("t_ok") == 1 and first == g.nearest() and g.cell("planted") == 1 and g.cell("t_spot") == 1
    g.run(R, 30)
    assert g.cell("locked") == 1 and abs(_wrap(g.cell("yaw") - g.bearing(first))) <= 2, "he did not square up to it"
    # Left: the next one round him to the left (a raised bearing), one a press
    seen = [first]
    for _ in range(NE - 1):
        b0, c = g.bearing(seen[-1]), seen[-1]
        g.tap(LF)
        now = g.cell("t_sel")
        rel = {k: (((g.bearing(k) - b0) % 1024) * 8 + k - c) % 8192 for k in range(NE) if k != c}
        assert now == min(rel, key=rel.get), (seen, now, rel)          # (by bearing, then by number)
        seen.append(now)
    assert sorted(seen) == list(range(NE)), "Left did not go round them all"
    g.tap(RT)
    assert g.cell("t_sel") == seen[-2], "Right did not step back"
    g.run(R | LF, 40)                             # held: one step, not a run of them
    assert g.cell("t_sel") == seen[-1]
    # the spot: Up and Down step it, it stops at its ends, and it stays
    for pad, want in ((U, 0), (U, 0), (D, 1), (D, 2), (D, 2), (U, 1), (U, 0)):
        g.tap(pad)
        assert g.cell("t_spot") == want
    g.run(0, 30)
    g.run(R, 5)
    assert g.cell("t_spot") == 0, "the spot did not stay where it was put"
    assert g.pos() == p0, "with R alone the pad moved him"


def test_with_r_alone_the_pad_never_moves_him_and_in_slowed_time_a_press_is_a_press(text):
    g = Game(text)
    for k in range(NE):
        g.poke(f"e{k}_st", 0)                     # none of them: and the key is across town
    g.run(0, 5)
    p0, y0 = g.pos(), g.cell("yaw")
    for pad in (U, D, LF, RT):
        g.run(R | pad, 25)
    assert g.cell("t_ok") == 0 and g.cell("planted") == 1
    assert g.pos() == p0 and g.cell("yaw") == y0, "R alone, no target: the pad moved him"
    g.run(U, 30)
    assert g.pos() != p0, "R let go, he does not walk"
    g.run(R | L | U, 30)                          # R with L is the boxer's: it steps
    assert g.cell("planted") == 0
    g = Game(text, settle=400)
    g.run(R | B, 40)                              # B held: time slowed, and he is aiming
    assert g.cell("slow_on") == 1 and g.cell("t_ok") == 1
    p0, sel = g.pos(), g.cell("t_sel")
    g.run(R | B | LF, 7)
    g.run(R | B, 12)
    assert g.cell("t_sel") != sel, "slowed, Left did not change the target"
    one = g.cell("t_sel")
    g.run(R | B, 20)
    assert g.cell("t_sel") == one
    g.run(R | B | D, 7)
    g.run(R | B, 9)
    assert g.cell("t_spot") == 2 and g.pos() == p0, "slowed: the spot, and he stood"


def test_a_locked_shot_goes_at_the_spot_and_does_what_the_spot_does(text):
    g = Game(text, settle=400)
    g.run(R, 20)
    t = g.cell("t_sel")
    assert t == 0 or HP[t] >= 3

    def shot():
        hp, seen, held = g.cell(f"e{t}_hp"), [], 0
        g.run(R | B, 5)
        for _ in range(16):
            g.run(R, 1)
            seen += [g.cell(f"bul{i}_y") / 65536 for i in (0, 1) if g.cell(f"bul{i}_rem") > 0]
            held = max(held, g.cell(f"e{t}_stun"))
        return hp - g.cell(f"e{t}_hp"), held, round(seen[0], 2) if seen else None
    took, held, y = shot()
    assert (took, y) == (1, 1.10) and 0 < held <= 12, (took, held, y)
    g.run(R, 30)
    g.tap(D)
    took, held, y = shot()
    assert (took, y) == (1, 0.50) and held > 15, ("low: it is held, and comes no nearer", took, held, y)
    g.run(R, 50)
    g.tap(U)
    g.tap(U)
    hp = g.cell(f"e{t}_hp")
    took, held, y = shot()
    assert y == 1.60 and (took == 2 or hp == 1), ("high: doubled", took, y)


def test_an_enemy_with_nothing_left_goes_down_and_comes_back(text):
    g = Game(text, settle=400)
    g.run(R, 20)
    t = g.cell("t_sel")
    home = g.enemy(t)
    for _ in range(12):
        if g.cell(f"e{t}_st") != 1:
            break
        g.run(R | B, 5)
        g.run(R, 14)
    assert g.cell(f"e{t}_st") == 2, "it did not go down"
    g.run(R, 3)
    assert g.cell("t_sel") != t and g.cell("t_ok") == 1, "the lock stayed on one that is down"
    g.run(R, 160)
    assert g.cell(f"e{t}_st") == 1 and g.cell(f"e{t}_hp") == HP[t], "it did not come back"
    assert g.enemy(t) != home


def test_a_fist_lands_on_the_one_he_faces(text):
    g = Game(text, settle=400)
    g.run(R, 30)
    for _ in range(NE):                           # the nearest of the horde: inside a jab's lunge
        if g.far(g.cell("t_sel")) < 1.8:
            break
        g.tap(LF)
    t = g.cell("t_sel")
    assert g.far(t) < 1.8, "none of them stands within a blow"
    g.run(R, 20)
    hp, far = g.cell(f"e{t}_hp"), g.far(t)
    g.run(R | Y, 5)                               # the count is nothing: the lead hook (2)
    took = stop = 0
    for _ in range(40):
        g.run(R, 1)
        took, stop = max(took, hp - g.cell(f"e{t}_hp")), max(stop, g.cell("f_stop"))
    assert took == 2 or g.cell(f"e{t}_st") == 2, ("the hook did not land", took, g.far(t))
    assert stop > 5, "no hitstop"


def test_the_layers_under_it_still_stand(text):
    g = Game(text)
    for k in range(NE):
        g.poke(f"e{k}_st", 0)
    g.run(0, 5)
    g.run(X, 5)
    g.run(0, 3)
    assert g.cell("anim") == 2 and g.cell("f_mv") == 0
    g.run(0, 40)
    g.run(B, 20)
    assert g.cell("aimed") and g.cell("slow_on")
    g.run(0, 4)
    assert max(g.cell(f"bul{i}_rem") for i in (0, 1)) > 0, "no bullet"
    g.run(0, 40)
    g.run(L, 30)
    assert g.cell("f_sty") == 2, "no boxer"
