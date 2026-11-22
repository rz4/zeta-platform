"""TND's LAYER 2 (docs/TND-PORT.md P28-P30): shadow boxing.

Every blow goes where he faces -- a blow never turns him -- and the pad
at its launch is its STEP: in, out, off the line. X is a jab, every time,
and counts; Y ends the string with what the count has earned: the lead
hook, the rear uppercut, the haymaker. No beat is read: mashed or slow,
the count is the count. A button held keeps the string and slows time.
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
STEP, LUNGE, KEEP, HOLD, SLOW = range(5)                # the layer's knobs
FRICTION = 0.82                                         # a swing's, a frame


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

    def local(self, p0, yaw0):
        """where he has got to from p0, in the frame he faced: (ahead, to his left)"""
        dx, dz = self.pos()[0] - p0[0], self.pos()[1] - p0[1]
        a = yaw0 * 2 * np.pi / 1024
        return -np.sin(a) * dx + np.cos(a) * dz, -np.cos(a) * dx - np.sin(a) * dz

    def throw(self, way, button, frames=60):
        """a thumb's press of `button` with `way` held; -> (the move thrown,
        the most his heading changed in any frame, the frame the spark lit,
        where it lit in HIS frame (ahead, off his line, up), how far he went
        (ahead, to his left))"""
        p0, y0, mv, big, lit = self.pos(), self.cell("yaw"), None, 0, None
        for f in range(frames):
            self.run((way | button) if f < 7 else 0, 1)
            big = max(big, abs((self.cell("yaw") - y0 + 512) % 1024 - 512))
            if self.cell("anim") == 2:
                mv = self.cell("f_mv")
            if lit is None and self.cell("spark", 3) > 0:
                here = self.pos()
                sx, sz = self.cell("spark") / 65536 - here[0], self.cell("spark", 2) / 65536 - here[1]
                a = y0 * 2 * np.pi / 1024
                lit = (f, -np.sin(a) * sx + np.cos(a) * sz, np.cos(a) * sx + np.sin(a) * sz,
                       self.cell("spark", 1) / 65536)
        return MOVES[mv] if mv is not None else None, big, lit, self.local(p0, y0)

    def string(self, presses, tail=90):
        """presses: [(pad, frames), ...]; -> the blows launched, in order"""
        out = []
        for pad, n in list(presses) + [(0, tail)]:
            for _ in range(n):
                self.run(pad, 1)
                if self.cell("anim") == 2 and self.cell("af") == 0:
                    out.append(MOVES[self.cell("f_mv")])
        self.run(0, 120)
        return out


def tap(button, gap, down=5):
    return [(button, down), (0, gap - down)]


@pytest.mark.parametrize("way,ahead,left", [(0, 1, 0), (U, 1, 0), (D, 0, 0), (LF, 1, 1), (RT, 1, -1)])
def test_a_blow_goes_where_he_faces_and_the_pad_steps_it(text, way, ahead, left):
    """P30: "the jabs turn the player, it shouldn't" -- "Always straight;
    d-pad is footwork". Whatever the pad holds, the jab does not turn him by
    one unit on any frame; it lands the same frame, at the same reach and
    height, dead on the line he faces; and the pad is its step: Up in, Down
    out (and no lunge), Left and Right off the line -- as far as the clip's
    feet were planted for (the lunge and the step knobs, over the friction)."""
    g = Game(text)
    mv, big, lit0, went0 = g.throw(0, X)
    assert mv == "jab" and big == 0 and lit0 is not None
    assert lit0[0] <= 5, f"the jab lands {lit0[0]} frames after the press"
    assert abs(lit0[2]) < 0.02 and 0.6 < lit0[1] < 0.8 and 1.1 < lit0[3] < 1.35, f"the jab lands at {lit0}"
    g.run(0, 120)
    mv, big, lit, went = g.throw(way, X)
    assert mv == "jab" and big == 0, f"the jab turned him {big}"
    assert lit[0] == lit0[0] and all(abs(a - b) < 0.02 for a, b in zip(lit[1:], lit0[1:])), \
        f"stepped, it landed at {lit}, not {lit0}"
    lunge = 0.078 * g.knob(LUNGE) / 65536 / (1 - FRICTION)
    step = g.knob(STEP) / 65536 / (1 - FRICTION)
    want = (lunge * ahead + step * ((way == U) - (way == D)), step * left)
    assert abs(went[0] - want[0]) < 0.03 and abs(went[1] - want[1]) < 0.03, f"he went {went}, not {want}"


def test_the_count_builds_to_the_terminator(text):
    """"the number of times we press the jab it builds to a special
    terminator ... A player could in theory just button mash fast, and still
    get combos to work, not working off a specific time signature." X is a
    jab every time; Y ends the string: none or one jab, the lead hook; two,
    the rear uppercut; three or more, the haymaker -- at a thumb's fastest
    (9 frames) or slow (35); and left alone past the keep knob the count is
    gone. Every one lands on his centre line."""
    g = Game(text)
    assert g.string(tap(Y, 10)) == ["lead_hook"]
    assert g.string(tap(X, 12) + tap(Y, 10)) == ["jab", "lead_hook"]
    assert g.string(tap(X, 12) * 2 + tap(Y, 10)) == ["jab", "jab", "rear_uppercut"]
    assert g.string(tap(X, 12) * 3 + tap(Y, 10)) == ["jab"] * 3 + ["special"]
    assert g.string(tap(X, 9) * 6 + tap(Y, 10)) == ["jab"] * 6 + ["special"], "mashed, a jab was lost"
    assert g.string(tap(X, 35) * 2 + tap(Y, 10)) == ["jab", "jab", "rear_uppercut"], "slow, the count was lost"
    gone = g.knob(KEEP) + 16 + 30
    assert g.string(tap(X, 12) * 2 + [(0, gone)] + tap(Y, 10)) == ["jab", "jab", "lead_hook"], "the count never ends"
    for n, last in ((0, "lead_hook"), (2, "rear_uppercut"), (3, "special")):
        g.run(0, 60)
        y0, lit, was = g.cell("yaw"), [], 0
        for pad, k in tap(X, 12) * n + tap(Y, 10) + [(0, 70)]:
            for _ in range(k):
                g.run(pad, 1)
                before, was = was, g.cell("spark", 3)
                if was > before:                  # (a spark just lit)
                    a = y0 * 2 * np.pi / 1024
                    sx, sz = g.cell("spark") / 65536 - g.pos()[0], g.cell("spark", 2) / 65536 - g.pos()[1]
                    lit.append((MOVES[g.cell("f_mv")], np.cos(a) * sx + np.sin(a) * sz))
        assert len(lit) == n + 1 and lit[-1][0] == last and all(abs(off) < 0.03 for _, off in lit), \
            f"{n} jabs and Y: off his line: {lit}"
        assert g.cell("yaw") == y0, "a blow turned him"
        g.run(0, 60)


def test_a_terminator_is_thrown_and_ends(text):
    """Heavy: a jab gives way to the next blow as soon as it has landed; a
    terminator does not -- a press in it waits it out."""
    g = Game(text)
    out, f = [], 0
    for pad, n in tap(X, 9) + tap(X, 9) + tap(Y, 9) + tap(X, 9) * 6 + [(0, 60)]:
        for _ in range(n):
            g.run(pad, 1)
            if g.cell("anim") == 2 and g.cell("af") == 0:
                out.append((f, MOVES[g.cell("f_mv")]))
            f += 1
    assert [m for _, m in out[:3]] == ["jab", "jab", "rear_uppercut"], out
    assert out[1][0] - out[0][0] < 12, "the second jab waited for the first to end"
    assert out[3][1] == "jab" and out[3][0] - out[2][0] >= 39, f"the uppercut was cut short: {out}"


def test_a_button_held_keeps_the_string_and_slows_time(text):
    """"each button can get held keeping the string, slowing time and
    releasing ... the slow motion gives time to think." Past the hold
    knob's frames his own blow runs one frame in the slow knob's and the
    glass sinks to its third curve; let go, it runs again; and however long
    it was held, the count is still there for Y."""
    g = Game(text)
    hold, slow = g.knob(HOLD), g.knob(SLOW)
    grade2 = g.sym("grade2")
    g.run(X, 1)
    g.run(0, 20)                                  # one jab, tapped: no slow
    assert g.d[spec.GRADE_SRC] != grade2
    af = []
    for f in range(hold + 3 * slow * 4):
        g.run(Y, 1)
        af.append(g.cell("af"))
    assert g.cell("f_mv") == MOVES.index("lead_hook")
    assert af[hold - 1] - af[0] == hold - 1, "time slowed before the hold was a hold"
    late = af[hold + slow:]
    assert late[-1] - late[0] == (len(late) - 1) // slow, f"held, his clock ran {late}"
    assert g.d[spec.GRADE_SRC] == grade2, "the glass did not sink"
    p0 = g.pos()
    a0 = g.cell("af")
    g.run(0, 6)
    assert g.cell("af") - a0 == 6 and g.d[spec.GRADE_SRC] != grade2, "let go, time did not run"
    g.run(0, 150)
    assert g.string(tap(X, 12) + [(X, 200), (0, 3)] + tap(Y, 10)) == ["jab", "jab", "rear_uppercut"], \
        "held, the string was lost"
    assert np.hypot(*np.subtract(g.pos(), p0)) < 6, "held, he was carried off"


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
        mv, big, lit, went = g.throw(D, X, frames=200)
        assert mv == "jab" and big == 0 and lit is not None, (mv, big, lit)
        assert g.cell("anim") != 2, "the blow never ended"
        assert g.string(tap(X, 12) * 3 + tap(Y, 10))[-1] in ("special", "lead_hook"), "no terminator"
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
