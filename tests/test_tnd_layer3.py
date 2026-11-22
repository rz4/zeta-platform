"""TND's LAYER 3 (docs/TND-PORT.md P35): the right shoulder -- targeting.

R held, the district's item in reach (the key; the key held, its gate), he
squares up to it: his steering -- in the boxer, his cross -- comes round to
its bearing and stays there, his body with it. He is planted (the tank
neither walks nor turns); the boxer's steps go round it; a blow or a shot
goes AT it whatever the pad says. Not in the run; nothing in reach, nothing.
In the run (P36) he goes ROUND it -- on the circle he began -- the gun
fired in stride with one hand, and a fist is the superman punch.
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


def test_nothing_in_reach_r_is_nothing(text):
    """At the start the key is far out of the lock's reach: R does nothing,
    and the pad is his."""
    g = Game(text)
    assert g.far() > 20
    p0, y0 = g.pos(), g.cell("yaw")
    g.run(R, 20)
    assert g.cell("locked") == 0 and g.cell("yaw") == y0
    g.run(R | U, 30)
    assert np.hypot(*np.subtract(g.pos(), p0)) > 1.0, "R held, he could not walk"


def _running(text, at):
    g = Game(text, at=at, yaw=512)
    g.run(L, 3)
    g.run(0, 2)
    g.run(L | U, 3)
    assert g.cell("f_sty") == 1, "no run"
    return g


@pytest.mark.parametrize("pad,side", [(LF, 256), (RT, -256)])
def test_locked_the_run_goes_round_the_item_on_its_circle(text, pad, side):
    """P36 ("the running and aiming should feel you are running on the
    tangent of the circle"): locked in the run, Left and Right run ALONG
    the circle round the item -- his heading a quarter turn off its bearing
    -- and he stays on the circle he began (left alone a tangent's step
    spirals out: an eighth of a unit a second). Up runs in."""
    g = _running(text, (0.0, 7.5))
    g.run(L | R | pad, 60)
    far, b0 = g.far(), g.bearing()
    seen = []
    for _ in range(480):
        g.run(L | R | pad, 1)
        seen.append(g.far())
        assert abs(_wrap(g.cell("yaw") - g.bearing() - side)) <= 14, "he left the tangent"
    assert max(seen[120:]) - min(seen[120:]) < 0.05, (min(seen), max(seen), "he does not hold the circle")
    assert abs(seen[-1] - far) < 0.5 and g.cell("f_spd") > 0.1 * 65536
    assert abs(_wrap(g.bearing() - b0)) > 100, "he did not go round it"
    far = g.far()
    g.run(L | R | U, 30)
    assert g.far() < far - 2.0, "Up did not run in"


def test_in_the_locked_run_the_gun_is_fired_in_stride(text):
    """P36 ("the gun being shot while running single hand"): B down, the
    near arm is out at the item (the run's own stride under it); let go,
    the round leaves AT the item and he has not broken stride -- no swing,
    his speed kept, the key struck."""
    g = _running(text, (0.0, 7.5))
    g.run(L | R | LF, 70)
    spd, run = g.cell("f_spd"), g.cell("pose")
    g.run(L | R | LF | B, 6)
    assert g.cell("anim") == 5 and g.cell("pose") != run and g.cell("pose") > 600, "the arm is not out"
    arm = g.cell("pose") - (g.cell("f_ph") >> 16 & 15)
    struck = 0
    for _ in range(14):
        g.run(L | R | LF, 1)
        assert g.cell("anim") == 5 and abs(g.cell("f_spd") - spd) < 300, "the shot broke his stride"
        struck = max(struck, g.cell("key_hit"))
    assert g.cell("gun_shots") == 1 and struck > 0, "the shot in the run did not strike the item"
    g.run(L | R | LF, 20)
    assert g.cell("pose") < 600, "the arm stayed out"
    g.run(L | R | RT, 80)                         # the other way round: the other arm
    g.run(L | R | RT | B, 6)
    other = g.cell("pose") - (g.cell("f_ph") >> 16 & 15)
    assert other > 600 and other != arm, (arm, other, "the same arm, both ways round")


@pytest.mark.parametrize("held", [L | R | LF, R, 0])
def test_the_superman_punch_lands_from_in_range_and_falls_short_from_out(text, held):
    """P36 ("trying to weave and land a super man punch"): a fist thrown in
    the locked run. He leaves the ground AT the item, the haymaker wound up
    through the air, and stops 1.2 short of it: from inside seven units the
    blow lands -- the key rings, its hitstop holds him -- and he ends the
    same place whatever he holds in the air. From nine units it is thrown
    just the same and is over before he gets there."""
    ends = []
    for at, lands in (((0.0, 5.5), True), ((0.0, 7.5), True), ((0.0, 9.5), False)):
        g = _running(text, at)
        g.run(L | R | LF, 30)
        far = g.far()
        g.run(L | R | LF | Y, 4)
        aloft, struck, moves = 0, 0, set()
        for _ in range(100):
            g.run(held, 1)
            aloft += g.cell("f_py") > 0
            struck = max(struck, g.cell("key_hit"))
            if g.cell("anim") == 2:
                moves.add(MOVES[g.cell("f_mv")])
        assert moves == {"special"} and aloft > 15, (moves, aloft)
        assert (struck > 0) == lands, (far, struck)
        if lands:
            assert 0.9 < g.far() < 1.25, (far, g.far())
        ends.append(round(g.far(), 2))
    assert ends[2] < 2.5, "thrown from far, it did not carry"


def test_a_terminator_by_the_key_strikes_it(text):
    """A fist that comes within a unit of the key has struck it: standing
    by it, a Y -- with its own hitstop -- and the key rings; it is not
    picked up by it."""
    g = Game(text, at=(0.0, 1.6), yaw=512)
    g.run(Y, 5)
    struck = stop = 0
    for _ in range(40):
        g.run(0, 1)
        struck, stop = max(struck, g.cell("key_hit")), max(stop, g.cell("f_stop"))
    assert struck > 0 and stop > 5 and g.cell("key_held") == 0, (struck, stop)


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
