"""TND's LAB (docs/TND-PORT.md P42): a white room to tune the fight in.

The player: "an empty white room, with a green and white checker board, grey
walls: tall, checker board white and grey. Then having one stationary clone of
the player to fight. think about it as tuning the fighting in this cart. Able
to load n number of tiered enemies. stationary for now. we want to work on how
the weight works with how they will respond to hits ... make the room wide so
at the wall we have platforming with some moving and some structures".
Layer 4's fight in a hall of its own: who stands there is a knob; a blow sends
a body by the move, the knobs and its weight; structures along the north wall
can be stood on, ridden and fallen off.
A local build (TND_LAYER=10 -> build/layer10/tnd.zol); it needs the cart-mesh
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
CART = ROOT / "build" / "layer10" / "tnd.zol"
pytestmark = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "clips_190.npz").is_file(),
                                reason="the layer builds from the local tier files (build/tiers)")
U, D, LF, RT, A, B, X, Y, L, R, SEL = (spec.PAD_UP, spec.PAD_DOWN, spec.PAD_LEFT, spec.PAD_RIGHT, spec.PAD_A, spec.PAD_B,
                                       spec.PAD_X, spec.PAD_Y, spec.PAD_L, spec.PAD_R, spec.PAD_SELECT)
HALL_X, HALL_Z, HALL_U, HALL_V = -64.0, 0.0, 32.0, 16.0   # the hall's middle (zeta x, z), half its width, half its depth
NORTH, EAST, SOUTH, WEST = 256, 0, 768, 512
WHO = (0b1000000, 0b1000001, 0b1000110, 0b0000001, 0b0001111, 0b0111111)     # slot 6 is the clone
MARK_U = (-4, 4, -8, 8, -12, 12, 0)
CLONE = 6
KNOB = {n: i for i, n in enumerate(("who", "weight", "knock", "lift", "stun", "hstop", "slide", "egrav", "pivot", "lunge",
                                    "keep", "hold", "slow", "dodge", "jump"))}


@pytest.fixture(scope="module")
def text():
    if not CART.is_file() or CART.stat().st_mtime < GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="10")
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
    def __init__(self, text):
        self.text = text
        self.m = cabinet.VirtualMachine(cabinet.load_cart(CART))
        self.m.frame(spec.PAD_START)
        self.d = self.m.vm.dmem
        self.run(0, 30)

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
        """(east, north) in the hall of a zeta point (his, by default)"""
        x = self.cell("px") / 65536 if x is None else x
        z = self.cell("pz") / 65536 if z is None else z
        return z - HALL_Z, HALL_X - x

    def put(self, u, v, yaw=NORTH):
        self.poke("px", round((HALL_X - v) * 65536))
        self.poke("pz", round((HALL_Z + u) * 65536))
        for c in ("yaw", "head", "cam_yaw"):
            self.poke(c, yaw)
        self.run(0, 3)

    def body(self, k=CLONE):
        return self.uv(self.cell(f"e{k}_pos") / 65536, self.cell(f"e{k}_pos", 1) / 65536)

    def turn(self, name, notches):
        """turn a knob by whole notches, as the tuner does (its value and its count)"""
        i = KNOB[name]
        step = {"who": 1, "weight": 6553, "knock": 6553, "lift": 6553, "stun": 6553, "hstop": 6553}[name]
        self.poke("knobs", self.cell("knobs", i) + notches * step, i)
        self.poke("knob_n", self.cell("knob_n", i) + notches, i)
        self.run(0, 2)

    def string(self, jabs, end=True):
        """X a count, then Y: the lead hook (0-1), the rear uppercut (2), the haymaker (3 and up)"""
        for _ in range(jabs):
            self.run(X, 3)
            self.run(0, 9)
        if end:
            self.run(Y, 3)
        self.run(0, 4)

    def at_the_clone(self, gap=1.15):
        u, v = self.body()
        self.put(u, v - gap, NORTH)


def test_he_begins_in_the_hall_and_the_clone_stands_alone(text):
    g = Game(text)
    u, v = g.uv()
    assert abs(u) < 0.1 and abs(v + 11) < 0.1 and g.cell("yaw") & 1023 == NORTH
    assert [g.cell(f"e{k}_st") for k in range(7)] == [0, 0, 0, 0, 0, 0, 1], "the clone does not stand alone"
    assert g.body() == pytest.approx((0, 2.0), abs=0.05)
    g.run(0, 200)
    assert g.body() == pytest.approx((0, 2.0), abs=0.05), "it stands, and it moved"
    assert g.d[spec.GRADE_SRC] == 0, "the lab's colours are being graded"


@pytest.mark.parametrize("who", range(6))
def test_who_stands_there_is_the_knobs(text, who):
    g = Game(text)
    g.turn("who", 5 if who != 5 else 0)                       # (away from it, a body knocked somewhere, and to it)
    k0 = next(k for k in range(7) if g.cell(f"e{k}_st"))
    g.poke(f"e{k0}_pos", round((HALL_X - 9) * 65536))
    g.turn("who", who - g.cell("knobs", 0))
    assert [g.cell(f"e{k}_st") for k in range(7)] == [WHO[who] >> k & 1 for k in range(7)]
    for k in range(7):
        if WHO[who] >> k & 1:
            assert g.body(k) == pytest.approx((MARK_U[k], 2.0), abs=0.05), f"slot {k} is not on its mark"


@pytest.mark.parametrize("yaw,axis,limit", [(NORTH, 1, None), (SOUTH, 1, -(HALL_V - 0.6)), (EAST, 0, HALL_U - 0.6), (WEST, 0, -(HALL_U - 0.6))])
def test_the_hall_has_walls(text, yaw, axis, limit):
    g = Game(text)
    g.turn("who", 3)                                          # (nobody in his way down the middle)
    g.put(0.0, -8.0, yaw)
    g.run(U, 700)
    g.run(0, 12)
    u, v = g.uv()
    assert abs(u) <= HALL_U - 0.5 and abs(v) <= HALL_V - 0.5, "he walked out of the hall"
    if limit is not None:
        assert abs((u, v)[axis] - limit) < 0.25, f"he stopped at {(u, v)[axis]:.2f}, not at the wall's {limit:.2f}"


def sent(g, jabs):
    """how far north the clone is sent by a string thrown at it"""
    g.at_the_clone()
    v0 = g.body()[1]
    g.string(jabs)
    high = 0
    for _ in range(140):
        g.run(0, 1)
        high = max(high, g.cell("lab_ey", CLONE))
    return g.body()[1] - v0, high / 65536


def test_a_blow_sends_it_by_the_move(text):
    hook, _ = sent(Game(text), 0)
    upper, up = sent(Game(text), 2)
    hay, _ = sent(Game(text), 3)
    assert 0.2 < hook < hay, f"the hook sent it {hook:.2f}, the haymaker's string {hay:.2f}"
    assert up > 0.5, f"the rear uppercut did not throw it up ({up:.2f})"
    g = Game(text)
    sent(g, 3)
    assert g.cell("lab_evx", CLONE) == 0 and g.cell("lab_evz", CLONE) == 0 and g.cell("lab_ey", CLONE) == 0, "it never came to rest"


def test_heavier_it_is_sent_less_and_lighter_more(text):
    plain, _ = sent(Game(text), 0)                            # (one blow: the lead hook)
    g = Game(text)
    g.turn("weight", 10)                                      # twice as heavy
    heavy, _ = sent(g, 0)
    g = Game(text)
    g.turn("weight", -5)                                      # half
    light, _ = sent(g, 0)
    assert heavy < 0.7 * plain < plain < 0.7 * light, f"sent {heavy:.2f} heavy, {plain:.2f} as it is, {light:.2f} light"
    g = Game(text)                                            # the horde's own weight is less than the clone's
    g.turn("who", 2)
    u, v = g.body(2)
    g.put(u, v - 1.15, NORTH)
    v0 = g.body(2)[1]
    g.string(0)
    g.run(0, 140)
    assert g.body(2)[1] - v0 > 1.2 * plain, "one of the horde went no farther than the clone"


def test_the_knock_knob_at_nothing_it_does_not_move(text):
    g = Game(text)
    g.turn("knock", -10)
    far, _ = sent(g, 3)
    assert abs(far) < 0.05 and g.cell("e6_hp") < 12, "with no knock it still slid (or the blows did not land)"


def test_a_wall_stops_a_body(text):
    g = Game(text)
    g.poke("e6_pos", round((HALL_X - 14.0) * 65536))          # near the north wall, between structures
    g.poke("e6_pos", round((HALL_Z + 14.0) * 65536), 1)
    g.poke("lab_evx", round(-0.9 * 65536), CLONE)             # thrown at it
    g.run(0, 60)
    u, v = g.body()
    assert v <= HALL_V - 0.55, f"the body went through the wall (v {v:.2f})"
    assert g.cell("lab_evx", CLONE) == 0


def test_a_structure_is_stood_on_stepped_off_and_walked_into(text):
    g = Game(text)
    g.turn("who", 3)
    g.put(-29.0, 6.0, NORTH)                                  # the floor before the first step (0.8 high)
    g.run(U, 200)
    g.run(0, 10)
    assert g.uv()[1] < 10.0 and g.cell("lab_gh") == 0, "he walked up a step too high to step"
    g.put(-29.0, 13.0, NORTH)                                 # dropped onto it from above
    g.poke("f_py", round(1.6 * 65536))
    g.run(0, 60)
    assert g.cell("f_py") == 0 and g.cell("lab_gh") == int(0.8 * 65536) and g.cell("lab_si") == 0, "he did not land on the step"
    g.put(-29.0, 13.0, EAST)                                  # along it to the next, 0.8 higher: too high
    g.run(U, 200)
    assert g.cell("lab_si") == 0 and g.uv()[0] < -26.0
    g.put(-29.0, 13.0, SOUTH)                                 # and off its edge
    g.run(U, 120)
    g.run(0, 40)
    assert g.cell("lab_gh") == 0 and g.cell("lab_si") == -1 and g.cell("f_py") == 0 and g.uv()[1] < 10.0, "off the edge, he did not come down"


def test_the_lift_and_the_slider_carry_him(text):
    g = Game(text)
    g.turn("who", 3)
    g.put(23.0, 9.2, NORTH)
    while not (g.cell("lab_lift") == int(0.25 * 65536) and g.cell("lab_t") + 128 & 511 < 20):    # the lift comes to rest at the floor
        g.run(0, 1)
    assert g.cell("lab_lift") == int(0.25 * 65536)
    g.run(U, 40)                                              # it waits there: time to step on
    g.run(0, 5)
    assert g.cell("lab_si") == 5, "he could not step onto the lift while it waited at the floor"
    tops = []
    for _ in range(300):
        g.run(0, 1)
        assert g.cell("lab_si") == 5 and g.cell("f_py") == 0, "the lift left him behind"
        tops.append(g.cell("lab_gh"))
    assert max(tops) > round(3.5 * 65536) and all(t == g_ for t, g_ in zip(tops[-1:], [g.cell("lab_lift")])), "he did not ride it up"
    g2 = Game(text)
    g2.turn("who", 3)
    u0 = g2.cell("lab_slide") / 65536
    g2.put(4.0 + u0, 13.5, NORTH)
    g2.poke("f_py", round(3.0 * 65536))
    g2.run(0, 50)
    assert g2.cell("lab_si") == 4 and g2.cell("f_py") == 0, "he did not land on the slider"
    rel = []
    for _ in range(200):
        g2.run(0, 1)
        rel.append(g2.uv()[0] - g2.cell("lab_slide") / 65536)
    assert g2.cell("lab_si") == 4 and max(rel) - min(rel) < 0.05, "the slider slid out from under him"


def test_the_tuner_reaches_fifteen_knobs(text):
    g = Game(text)
    seen = []
    for _ in range(15):
        seen.append(g.cell("knob_sel"))
        g.run(SEL | RT, 2)
        g.run(SEL, 3)
    assert seen == list(range(15)) and g.cell("knob_sel") == 0, f"the tuner's knobs go {seen}"
    g.run(0, 4)
    g.run(SEL | U, 2)                                         # knob 0, "who": up one
    g.run(SEL, 3)
    g.run(0, 4)
    assert g.cell("knobs", 0) == 1 and [g.cell(f"e{k}_st") for k in range(7)] == [1, 0, 0, 0, 0, 0, 1]
