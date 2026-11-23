"""TND's REACTOR (docs/TND-PORT.md P45): the lab drawn in to one small room.

The player, 2026-11-23: "the world we made for the lab but more concentrated
like a reactor. same checkboard but are unit to the player width ... this way
all the physics is naturalized. now its a corner with the doupleganger except
its at the corner, its facing you and what it does is the exact mirror of the
moves you are doing. This will help with calibration of the games bodies. The
hits can be made felt as if the bodies are responding to eachother."

A check is his body's width (0.58 units); the room is sixteen checks square;
his double stands in the north-east corner, does what he does, and a blow of
his that lands is a blow of its that lands on him.
A local build (TND_LAYER=11 -> build/layer11/tnd.zol).
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
CART = ROOT / "build" / "layer11" / "tnd.zol"
pytestmark = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "clips_190.npz").is_file(),
                                reason="the layer builds from the local tier files (build/tiers)")
U, D, LF, RT, A, B, X, Y, L, R = (spec.PAD_UP, spec.PAD_DOWN, spec.PAD_LEFT, spec.PAD_RIGHT, spec.PAD_A, spec.PAD_B,
                                  spec.PAD_X, spec.PAD_Y, spec.PAD_L, spec.PAD_R)
HALL_X, HALL_Z = -64.0, 0.0
W = 0.58                        # a check: his width
HALF = 8 * W
CORNER = 7.5 * W - 0.02          # (his double's mark: a hair inside the bound)
NORTH, EAST, NE = 256, 0, 128
DOUBLE = 6


@pytest.fixture(scope="module")
def text():
    if not CART.is_file() or CART.stat().st_mtime < GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="11")
        for k in ("TND_SONG", "TND_OUT", "TND_CROWD", "TND_CARTMESH", "TND_AT"):
            env.pop(k, None)
        subprocess.run([sys.executable, str(GEN)], check=True, env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    return CART.read_text().splitlines()


@pytest.fixture(autouse=True)
def no_paint(monkeypatch):
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)


def _s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


class Game:
    def __init__(self, text, mirror=1):
        self.text = text
        self.m = cabinet.VirtualMachine(cabinet.load_cart(CART))
        self.m.frame(spec.PAD_START)
        self.d = self.m.vm.dmem
        self.run(0, 30)
        if not mirror:
            self.poke("knobs", 0)
            self.run(0, 2)

    def sym(self, n):
        return next(int(l.rsplit(" at ", 1)[1]) for l in self.text if l.startswith(f"; {n}: "))

    def cell(self, n, k=0):
        return _s32(self.d[self.sym(n) + k])

    def poke(self, n, v, k=0):
        self.d[self.sym(n) + k] = int(v) & 0xFFFFFFFF

    def run(self, pad, n):
        for _ in range(n):
            self.m.frame(pad)

    def uv(self, x=None, z=None):
        x = self.cell("px") / 65536 if x is None else x
        z = self.cell("pz") / 65536 if z is None else z
        return z - HALL_Z, HALL_X - x

    def double(self):
        return self.uv(self.cell(f"e{DOUBLE}_pos") / 65536, self.cell(f"e{DOUBLE}_pos", 1) / 65536)

    def put(self, u, v, yaw=NE):
        self.poke("px", round((HALL_X - v) * 65536))
        self.poke("pz", round((HALL_Z + u) * 65536))
        for c in ("yaw", "head", "cam_yaw"):
            self.poke(c, yaw)
        self.run(0, 3)

    def before_it(self, checks=1.25):
        """south of his double by so many checks, facing north at it"""
        self.put(CORNER, CORNER - checks * W, NORTH)

    def apart(self):
        (u, v), (du, dv) = self.uv(), self.double()
        return max(abs(u - du), abs(v - dv)) / W

    def poses(self, who):
        return tuple(self.cell(who, k) for k in (1, 3, 6, 8))


def test_the_room_is_sixteen_of_his_widths_and_his_double_is_in_its_corner(text):
    g = Game(text)
    u, v = g.uv()
    assert abs(u - 1.5 * W) < 0.02 and abs(v - 1.5 * W) < 0.02 and g.cell("yaw") & 1023 == NE
    du, dv = g.double()
    assert abs(du - CORNER) < 0.02 and abs(dv - CORNER) < 0.02, "his double is not in the corner"
    assert abs((g.cell(f"e{DOUBLE}_yaw") & 1023) - 640) < 24, "it does not face him"
    for k in range(DOUBLE):
        assert g.cell(f"e{k}_st") == 0, "someone else is in the room"
    for pad, yaw, axis, sign in ((U, EAST, 0, 1), (U, NORTH, 1, 1), (U, 512, 0, -1), (U, 768, 1, -1)):
        g.put(0.0, -2.0, yaw)
        g.run(pad, 260)
        assert abs(g.uv()[axis] - sign * 7.5 * W) < 0.08, f"a wall is not seven and a half checks out (yaw {yaw}: {g.uv()})"


def test_his_double_does_what_he_does(text):
    g = Game(text)
    g.run(0, 20)
    assert g.poses("rival_desc") == g.poses("body_desc"), "standing, its pose is not his"
    seen = set()
    g.run(X, 3)
    for _ in range(14):                                   # a jab: frame for frame
        g.run(0, 1)
        assert g.poses("rival_desc") == g.poses("body_desc")
        seen.add(g.poses("body_desc"))
    assert len(seen) > 4, "he did not move: the test proves nothing"
    g.run(0, 40)
    g.run(B, 16)                                          # the gun up: its upper half too
    assert g.poses("rival_desc") == g.poses("body_desc")
    still = Game(text, mirror=0)                          # the knob off: it stands, as the lab's did
    still.run(X, 3)
    differs = 0
    for _ in range(14):
        still.run(0, 1)
        differs += still.poses("rival_desc") != still.poses("body_desc")
    assert differs > 8, "with the mirror off it still copied him"


def test_it_leaves_the_floor_when_he_does(text):
    g = Game(text)
    g.poke("f_py", int(0.01 * 65536))
    g.poke("f_pvy", int(0.19 * 65536))
    high = 0
    for _ in range(60):
        g.run(0, 1)
        assert abs(g.cell("lab_ey", DOUBLE) - g.cell("f_py")) == 0, "its height is not his, this very frame"
        high = max(high, g.cell("lab_ey", DOUBLE))
    assert high > 65536 // 2, "he never left the floor: the test proves nothing"
    g.run(0, 30)
    assert g.cell("lab_ey", DOUBLE) == 0 and g.cell("f_py") == 0


def test_two_bodies_do_not_stand_in_one_place(text):
    g = Game(text)
    g.run(U, 200)                                         # up the diagonal, into it
    assert g.apart() > 0.93, f"he stands {g.apart():.2f} of a check from his double's middle"
    g.before_it(1.25)
    g.run(U, 60)
    assert 0.93 < g.apart() < 1.1


def test_a_blow_that_lands_sends_him_as_it_sends_a_body(text):
    g = Game(text)
    g.before_it(1.25)
    before = g.uv()
    g.run(Y, 3)                                           # the lead hook
    sent = 0
    for _ in range(90):
        g.run(0, 1)
        sent = max(sent, abs(g.cell("rx_sent")) + abs(g.cell("rx_sent", 1)))
    assert sent > 0, "the hook landed on nobody"
    gone = (before[1] - g.uv()[1]) / W
    assert 0.8 < gone < 2.6, f"the hook sent him {gone:.2f} checks"
    assert g.apart() > 1.8
    still = Game(text, mirror=0)
    still.before_it(1.25)
    before = still.uv()
    still.run(Y, 3)
    still.run(0, 90)
    assert still.cell("rx_sent") == 0 and (before[1] - still.uv()[1]) / W < 0.5, "with the mirror off he was sent all the same"


def test_its_place_is_the_corner_and_it_goes_back_to_it(text):
    g = Game(text)
    g.poke(f"e{DOUBLE}_pos", round((HALL_X - CORNER) * 65536))
    g.poke(f"e{DOUBLE}_pos", round((HALL_Z + 2.0) * 65536), 1)     # along the north wall, away from its corner
    g.run(0, 20)
    assert g.double()[0] < CORNER - 0.5
    g.run(0, 160)
    du, dv = g.double()
    assert abs(du - CORNER) < 0.02 and abs(dv - CORNER) < 0.02
