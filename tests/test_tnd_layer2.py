"""TND's LAYER 2 (docs/TND-PORT.md P28-P31): shadow boxing.

A blow goes the way the pad points and his WHOLE BODY turns to throw it;
his steering and the lens do not, and moving brings him back. X is a jab,
every time, and counts; Y ends the string with what the count has earned:
the lead hook, the rear uppercut, the haymaker. No beat is read. A button
held keeps the string and slows time, and the lens goes to where the blow
lands. In the boxer the jump is a strafe jump and the lens wanders.
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
PIVOT, LUNGE, KEEP, HOLD, SLOW, SJUMP, FCAM, WANDER = range(8)   # the layer's knobs
A = spec.PAD_A
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

    def lens(self):
        """the lens: (x, z, yaw)"""
        return _s32(self.d[spec.CAM_X]) / 65536, _s32(self.d[spec.CAM_Z]) / 65536, self.d[spec.CAM_YAW]

    def throw(self, way, button, frames=60):
        """a thumb's press of `button` with `way` held; -> (the move thrown,
        the most his STEERING changed in any frame, the most the lens turned,
        the frame the spark lit and where it lit in his BODY's frame (ahead,
        off its line, up) with how far his body had turned by then, how far
        he went (ahead, to his left) in his steering's frame)"""
        p0, y0, c0, mv, big, cam, lit = self.pos(), self.cell("yaw"), self.lens()[2], None, 0, 0, None
        for f in range(frames):
            self.run((way | button) if f < 7 else 0, 1)
            big = max(big, abs((self.cell("yaw") - y0 + 512) % 1024 - 512))
            cam = max(cam, abs((self.lens()[2] - c0 + 512) % 1024 - 512))
            if self.cell("anim") == 2:
                mv = self.cell("f_mv")
            if lit is None and self.cell("spark", 3) > 0:
                here, h = self.pos(), self.cell("head")
                sx, sz = self.cell("spark") / 65536 - here[0], self.cell("spark", 2) / 65536 - here[1]
                a = h * 2 * np.pi / 1024
                lit = (f, -np.sin(a) * sx + np.cos(a) * sz, np.cos(a) * sx + np.sin(a) * sz,
                       self.cell("spark", 1) / 65536, (h - y0 + 512) % 1024 - 512)
        return MOVES[mv] if mv is not None else None, big, cam, lit, self.local(p0, y0)

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


@pytest.mark.parametrize("way,angle", [(0, 0), (U, 0), (LF, 256), (RT, -256), (D, 512), (U | LF, 128)])
def test_his_body_turns_to_the_blow_and_his_steering_does_not(text, way, angle):
    """P31: "The directional punches are to turn player as if he was making
    a punch in that direction" -- "The whole body should be turned, the tank
    and boxer camera does not move. movement returns the direction to where
    it was before the directional hits". The jab goes the way the pad points:
    his body is round to it before the fist is out, it lands the same frame
    and at the same reach as one thrown ahead, dead on his body's line, and
    its lunge carries him that way. His steering does not change by a unit
    and the lens does not turn. He stands as the blow left him; a jab with
    no pad goes that way again; and the pad, moving him, brings him back."""
    g = Game(text)
    mv, big, cam, lit0, went0 = g.throw(0, X)
    assert mv == "jab" and big == 0 and cam == 0 and lit0 is not None
    assert lit0[0] <= 5, f"the jab lands {lit0[0]} frames after the press"
    assert abs(lit0[2]) < 0.02 and 0.6 < lit0[1] < 0.8 and 1.1 < lit0[3] < 1.35, f"the jab lands at {lit0}"
    g.run(0, 120)
    y0 = g.cell("yaw")
    mv, big, cam, lit, went = g.throw(way, X)
    assert mv == "jab" and big == 0, f"the jab turned his steering {big}"
    assert cam == 0, f"the lens turned {cam}"
    assert abs(lit[4]) == abs(angle) and (abs(angle) in (0, 512) or lit[4] == angle), \
        f"his body had turned {lit[4]} when it landed, not {angle}"
    assert lit[0] == lit0[0] and all(abs(a - b) < 0.02 for a, b in zip(lit[1:4], lit0[1:4])), \
        f"that way it landed at {lit}, not {lit0}"
    lunge = 0.078 * g.knob(LUNGE) / 65536 / (1 - FRICTION)
    a = angle * 2 * np.pi / 1024
    assert abs(went[0] - lunge * np.cos(a)) < 0.03 and abs(went[1] - lunge * np.sin(a)) < 0.03, \
        f"he went {went}"
    g.run(0, 60)
    turned = (g.cell("head") - y0 + 512) % 1024 - 512
    assert abs(turned) == abs(angle), "standing, he did not stay as the blow left him"
    mv, big, cam, lit, went = g.throw(0, X)
    assert lit[4] == turned and big == 0, f"a jab with no pad went {lit[4]}, not where his body faced"
    g.run(0, 80)                                  # (the count gone: the pad moves him)
    g.run(U, 8)
    assert g.cell("head") == g.cell("yaw") == y0, "moving did not bring him back"


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


@pytest.mark.parametrize("way", [0, LF, D])
def test_time_slowed_the_lens_goes_to_where_the_blow_lands(text, way):
    """P31: "the slow motions need cameras focused on the hit location."
    Time slowed, the lens comes in from the follow's distance and looks AT
    the place a blow's reach ahead of his body -- whichever way the blow
    went; let go, it is the follow again."""
    g = Game(text)
    g.run(0, 30)
    far = np.hypot(*np.subtract(g.lens()[:2], g.pos()))
    c0 = g.lens()[2]
    g.run(way | Y, g.knob(HOLD) + 40)
    x, z, yaw = g.lens()
    a = g.cell("head") * 2 * np.pi / 1024
    hx, hz = g.pos()[0] - 0.7 * np.sin(a), g.pos()[1] + 0.7 * np.cos(a)
    bearing = np.degrees(np.arctan2(-(hx - x), hz - z)) / 360 * 1024
    assert np.hypot(x - g.pos()[0], z - g.pos()[1]) < far - 0.3, "the lens did not come in"
    assert abs((yaw - bearing + 512) % 1024 - 512) < 12, f"the lens looks {yaw}, the blow lands at {bearing:.0f}"
    g.run(0, 60)
    assert abs(np.hypot(*np.subtract(g.lens()[:2], g.pos())) - far) < 0.25, "let go, the lens stayed in"


def test_time_slowed_he_still_moves_and_the_lens_stays_with_the_blow(text):
    """P32, from the tape of P31 (26 minutes; 45% of it in slowed time, and
    in it 138 of his 249 jumps and 144 of his 203 shots): slowed time is
    where he MOVES. In the tank with X held he walks and turns -- the
    string's lock is for running time (he had held Up for 41 seconds and
    stood) -- the count is still kept, and the lens stays in at the blow
    (the tank's old overhead shot had taken it: 3.6 away, looking down)."""
    g = Game(text)
    g.run(0, 30)
    far = np.hypot(*np.subtract(g.lens()[:2], g.pos()))
    g.run(X, g.knob(HOLD) + 30)                   # a jab, held: time slows
    assert g.cell("f_c3") == 1
    p0, y0 = g.pos(), g.cell("yaw")
    for _ in range(150):
        g.run(X | U, 1)
        assert np.hypot(*np.subtract(g.lens()[:2], g.pos())) < far, "the lens left the blow"
    assert g.local(p0, y0)[0] > 1.0, f"slowed, with Up held, he went {g.local(p0, y0)}"
    g.run(X | LF, 60)
    assert (g.cell("yaw") - y0) % 1024 > 100, "slowed, he could not turn"
    assert g.cell("f_c3") == 1, "held, the count was lost"
    g.run(0, 2)
    assert g.string(tap(X, 12) + tap(Y, 10)) == ["jab", "rear_uppercut"], "let go, the count was gone"


def test_a_shot_leaves_him_as_a_fist_does(text):
    """P32: the gun snaps to the pad's way the frame it fires, and his body
    STAYS there -- a shot with no pad goes that way again, his steering and
    the lens never turn, and moving brings him back -- so a volley does not
    snap him back to his steering between every two shots."""
    g = Game(text)
    B = spec.PAD_B
    g.run(0, 30)
    y0, c0 = g.cell("yaw"), g.lens()[2]

    def shoot(way):                               # (the gun fires as B comes up: the pad is read then)
        g.run(way | B, 4)
        g.run(way, 1)
        assert g.cell("anim") == 2 and g.cell("f_mv") >= MOVES.index("gun"), "no shot"
        seen = (g.cell("head") - g.cell("yaw") + 512) % 1024 - 512
        g.run(0, 40)
        return seen
    assert shoot(LF) == 256, "the shot did not go the pad's way"
    y0 = g.cell("yaw")
    g.run(0, 60)
    assert (g.cell("head") - y0) % 1024 == 256 and g.cell("yaw") == y0, "he did not stay as the shot left him"
    assert shoot(0) == 256, "a shot with no pad left where his body faced"
    assert abs((g.lens()[2] - c0 + 512) % 1024 - 512) < 32, "the lens came round with the shot"
    g.run(U, 8)
    assert g.cell("head") == g.cell("yaw") == y0, "moving did not bring him back"


@pytest.mark.parametrize("way,ahead,left", [(U, 1, 0), (D, -1, 0), (LF, 0, 1), (RT, 0, -1)])
def test_the_boxers_jump_is_a_strafe_jump(text, way, ahead, left):
    """P31: "For the boxer, the jumps should be like a strafe jump in the
    four directions." In the stance, A with the pad throws him that way on
    his cross -- farther than his step would carry him in that time, lower
    than the jump -- facing as he was; with no pad it is the jump, as it was."""
    g = Game(text)
    g.run(L, 40)
    p0, y0, top0, air0 = g.pos(), g.cell("yaw"), 0, 0
    for f in range(60):
        g.run(L | (A if f < 4 else 0), 1)
        top0 = max(top0, g.cell("f_py"))
        air0 += g.cell("f_py") > 0
    assert top0 > 0 and np.hypot(*g.local(p0, y0)) < 0.1, "the plain jump moved him"
    g.run(L, 30)
    p0, top, air = g.pos(), 0, 0
    for f in range(60):
        g.run(L | (way | A if f < 4 else 0), 1)
        top = max(top, g.cell("f_py"))
        air += g.cell("f_py") > 0
        assert g.cell("yaw") == y0 and g.cell("head") == y0, "the strafe jump turned him"
    went = g.local(p0, y0)
    far = g.knob(SJUMP) / 65536 * air
    assert 0 < top < 0.8 * top0 and air < air0, f"its top {top / 65536:.2f} against the jump's {top0 / 65536:.2f}"
    assert abs(went[0] - ahead * far) < 0.6 and abs(went[1] - left * far) < 0.6 and far > 2, \
        f"he went {went}, not {far:.2f} that way"
    assert g.cell("sjump_dir") == 0 and g.cell("f_py") == 0, "he never landed"


def test_the_boxers_lens_wanders_and_looks_at_him(text):
    """P31: "in the boxer the camera is locked on the player but can wander
    in position." As he steps aside the lens trails him -- off the line
    behind him -- and looks at him from wherever it is; standing, it comes
    back behind him; out of the stance it is the follow, exactly."""
    g = Game(text)
    g.run(L, 60)

    def off():                                    # the lens, off his steering's line; its aim, off him
        x, z, yaw = g.lens()
        back = g.local((x, z), g.cell("yaw"))     # him from the lens: (ahead, to the left)
        bearing = np.degrees(np.arctan2(-(g.pos()[0] - x), g.pos()[1] - z)) / 360 * 1024
        return back[1], abs((yaw - bearing + 512) % 1024 - 512)
    side, aim = off()
    assert abs(side) < 0.1 and aim <= 2
    for _ in range(40):
        g.run(L | LF, 1)
        assert off()[1] <= 2, "the lens lost him"
    assert off()[0] > 0.5, f"the lens did not trail: he is {off()[0]:.2f} to its left"
    g.run(L, 90)
    assert abs(off()[0]) < 0.1, "standing, the lens did not come back behind him"
    g.run(0, 40)
    assert g.cell("lens_share") == 65536 and g.lens()[2] == g.cell("cam_yaw"), "out of the stance, not the follow"


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
        for k in range(8):
            for _ in range(70):
                g.run(SEL | way, 1)
                g.run(SEL, 1)
            g.run(SEL | RT, 1)
            g.run(SEL, 1)
        g.run(0, 2)
        mv, big, cam, lit, went = g.throw(D, X, frames=200)
        assert mv == "jab" and big == 0 and lit is not None and abs(lit[4]) == 512, (mv, big, lit)
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
