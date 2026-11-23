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
    g.turn("knock", -9)                                       # (0.9, to nothing)
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


MOVES = ("jab", "cross", "lead_hook", "rear_hook", "special", "lead_uppercut", "rear_uppercut", "gun", "gun_charged")


def press(g, button, k=CLONE, wait=12):
    """one press: (the move it threw, did it land on body k)"""
    hp, mv = g.cell(f"e{k}_hp"), None
    g.run(button, 3)
    for _ in range(wait):
        g.run(0, 1)
        if mv is None and g.cell("anim") == 2:
            mv = MOVES[g.cell("f_mv")]
    return mv, g.cell(f"e{k}_hp") < hp


@pytest.mark.parametrize("who,k", [(0, 6), (1, 0), (2, 1)])
@pytest.mark.parametrize("gap,wait", [(1.0, 12), (1.15, 9), (1.3, 16), (1.45, 12)])
def test_four_jabs_land_the_fourth_the_right_and_a_fifth_misses(text, who, k, gap, wait):
    """(the player, of the lab: "jabs can follow for at least 4 hits. the fifth
    should miss and the forth is a right jab")"""
    g = Game(text)
    g.turn("who", who)
    u, v = g.body(k)
    g.put(u, v - gap, NORTH)
    got = [press(g, X, k, wait) for _ in range(6)]
    assert [m for m, _ in got[:4]] == ["jab", "jab", "jab", "cross"], "the fourth X is not the right jab"
    assert [h for _, h in got] == [True, True, True, True, False, False], f"the string landed {[h for _, h in got]}"


def test_y_after_the_fourth_is_a_jab_that_steps_in_and_starts_a_new_string(text):
    g = Game(text)
    g.at_the_clone()
    for _ in range(4):
        press(g, X)
    mv, hit = press(g, Y, wait=20)
    assert mv == "jab" and hit and g.cell("f_c3") == 1, f"Y after the fourth threw {mv} (landed: {hit}), the count {g.cell('f_c3')}"
    assert press(g, X)[0] == "jab" and g.cell("f_c3") == 2
    assert press(g, Y, wait=30)[0] == "rear_uppercut", "the new string's count does not choose its special"


def test_the_specials_are_by_the_count(text):
    for jabs, want in ((0, "lead_hook"), (1, "lead_hook"), (2, "rear_uppercut"), (3, "special")):
        g = Game(text)
        g.at_the_clone()
        for _ in range(jabs):
            press(g, X)
        assert press(g, Y, wait=30)[0] == want, f"Y after {jabs} jabs"


def test_the_gun_is_held_ready_while_b_is_down_whatever_his_legs_do(text):
    g = Game(text)
    g.turn("who", 3)
    up, lo = g.sym("body_desc") + 1, g.sym("body_desc") + 6      # each half's vertices, where its pose is
    g.put(0, -8, NORTH)
    g.run(0, 20)
    idle = g.d[up]
    g.run(B, 30)                                              # standing, B down: the gun's own pose
    ready = g.d[up]
    assert ready != idle
    seen_legs = set()
    for _ in range(40):                                       # walking with it down: his legs walk, his arms do not move
        g.run(B | U, 1)
        assert g.d[up] == ready, "walking, the gun came down"
        seen_legs.add(g.d[lo])
    assert len(seen_legs) > 4, "his legs did not walk"
    g.run(0, 40)                                              # let go (the shot goes): it comes down
    assert g.d[up] != ready


def test_the_lens_looks_up_with_a_body_thrown(text):
    g = Game(text)
    g.run(0, 20)
    flat = g.d[spec.CAM_PITCH]
    g.poke("lab_ey", round(3.0 * 65536), CLONE)
    g.poke("lab_evy", round(0.05 * 65536), CLONE)
    g.run(0, 12)
    up = (flat - g.d[spec.CAM_PITCH]) & 1023
    assert 40 < up <= 100, f"the lens rose {up} with a body three units up"
    g.run(0, 200)
    assert g.cell("lab_ey", CLONE) == 0 and abs(((g.d[spec.CAM_PITCH] - flat + 512) & 1023) - 512) <= 2, "it did not come back down"


def test_launchers_stacked_do_not_stack_the_rise(text):
    """(his first tape: chained launchers threw a body 6.5 units up, and he
    turned the lift off for the last ten minutes)"""
    g = Game(text)
    top, rise = 0.0, 0.0

    def watch(pad, n):
        nonlocal top, rise
        for _ in range(n):
            g.run(pad, 1)
            top = max(top, g.cell("lab_ey", CLONE) / 65536)
            rise = max(rise, g.cell("lab_evy", CLONE) / 65536)
    for _ in range(6):                                        # the rear uppercut's string, again and again,
        g.at_the_clone()                                      # at a body kept in the air
        g.poke("e6_hp", 12)
        for b in (X, X, Y):
            watch(b, 3)
            watch(0, 11)
        watch(0, 14)
    watch(0, 120)
    assert rise <= 0.2401 and 0.5 < top < 3.2, f"a body rose at {rise:.2f} a frame, to {top:.1f} units"


# ---- P44: the pass, the close shot, the held jab's choice, the run down the sights (the agent's readings of his words) ----

def test_a_held_jab_chooses_the_special_and_letting_go_throws_it(text):
    for taps, want in ((1, "lead_hook"), (2, "rear_uppercut"), (3, "special"), (5, "special")):
        g = Game(text)
        g.at_the_clone()
        g.run(X, 20)                                          # the jab, and X stays down
        thrown = set()
        for _ in range(taps):
            g.run(X | Y, 3)
            for _ in range(8):
                g.run(X, 1)
                if g.cell("anim") == 2:
                    thrown.add(MOVES[g.cell("f_mv")])
        assert thrown <= {"jab"}, f"with X held, Y threw {thrown}"
        assert g.cell("lab_seln") == min(taps, 3)
        mv = None
        for _ in range(40):                                   # X let go: the choice is thrown
            g.run(0, 1)
            if mv is None and g.cell("anim") == 2 and g.cell("f_mv") != 0:
                mv = MOVES[g.cell("f_mv")]
        assert mv == want and g.cell("lab_seln") == 0, f"{taps} presses of Y under a held jab threw {mv}"


def test_the_boxers_pass_is_a_stun(text):
    g = Game(text)
    g.at_the_clone()
    g.run(L, 10)                                              # the boxer
    hooks = 0

    def hook(pads):
        g.run(pads | Y, 3)
        st = 0
        for _ in range(60):
            g.run(L, 1)
            st = max(st, g.cell("e6_stun"))
        return st
    plain = hook(L)                                           # a lead hook, the gun down
    assert g.cell("lab_pass") == 0
    g.at_the_clone()
    g.run(L, 30)
    g.run(L | B, 6)                                           # the gun up, and the pass
    stunned = hook(L | B)
    assert g.cell("lab_pass") == 1, "Y with the gun up in the boxer was not the stun"
    assert plain > 0 and stunned >= 3 * plain, f"the stun held it {stunned} frames; a plain hook {plain}"


def test_the_runs_pass_is_a_tackle_along_the_floor_and_puts_it_down(text):
    g = Game(text)
    u, v = g.body()
    g.put(u, v - 7.0, NORTH)
    g.run(L, 2)                                               # L, twice: the run
    g.run(0, 3)
    g.run(L, 3)
    g.run(L | R | U, 24)                                      # locked, and at it
    assert g.cell("f_sty") == 1 and g.cell("locked") == 1, "he is not in the locked run"
    g.run(L | R | U | B, 6)
    g.run(L | R | U | B | Y, 3)
    high, kinds = 0, set()
    for _ in range(90):
        g.run(L | R | U, 1)
        high = max(high, g.cell("f_py"))
        kinds.add(g.cell("lab_pass"))
        if g.cell("e6_st") == 2:
            break
    assert 2 in kinds, "Y with the gun up in the locked run was not the tackle"
    assert high == 0, "the tackle left the floor"
    assert g.cell("e6_st") == 2, "the tackle did not put the body down"


def _shot(g, k=CLONE):
    hp = g.cell(f"e{k}_hp")
    g.run(R, 12)
    g.run(R | B, 4)
    g.run(R, 40)
    return hp - g.cell(f"e{k}_hp")


def test_a_round_from_close_is_three_and_reaches_a_body_that_is_down(text):
    far = Game(text)
    far.at_the_clone(6.0)
    near = Game(text)
    near.at_the_clone(1.4)
    assert (_shot(far), _shot(near)) == (1, 3), "a close-quarters round is not three times the round"
    down = Game(text)
    down.at_the_clone(1.4)
    down.poke("e6_st", 2)
    down.poke("e6_hp", 9)
    hp = down.cell("e6_hp")
    down.poke("e6_t", 40)
    down.run(B, 4)
    t0 = down.cell("e6_t")
    down.run(0, 40)
    assert down.cell("e6_hp") < hp, "a round from close did not reach the body on the floor"
    assert down.cell("e6_t") >= t0, "a round into a body on the floor stood it up to fall again"
    away = Game(text)
    away.at_the_clone(6.0)
    away.poke("e6_st", 2)
    hp = away.cell("e6_hp")
    away.run(B, 4)
    away.run(0, 40)
    assert away.cell("e6_hp") == hp, "a round from across the room hit a body on the floor"


def test_locked_and_aiming_the_run_goes_down_the_sights(text):
    def gap_after(aim):
        g = Game(text)
        u, v = g.body()
        g.put(u, v - 9.0, NORTH)
        g.run(L, 2)
        g.run(0, 3)
        g.run(L, 3)
        g.run(L | R | LF | (B if aim else 0), 70)             # the pad says: round it
        (hu, hv), (bu, bv) = g.uv(), g.body()
        return float(np.hypot(hu - bu, hv - bv))
    circle, charge = gap_after(False), gap_after(True)
    assert circle > 7.5, f"without the gun he did not keep his circle ({circle:.1f})"
    assert charge < circle - 2.0, f"aiming, he did not run at the target ({charge:.1f} against {circle:.1f})"
