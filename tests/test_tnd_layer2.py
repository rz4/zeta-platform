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
PIVOT, LUNGE, KEEP, HOLD, SLOW, SJUMP, FCAM, WANDER, DODGE, MAG = range(10)   # the layer's knobs
A, B = spec.PAD_A, spec.PAD_B
GUN_V, GUN_RANGE, RELOAD = 2.0, 13.0, 24                # a bullet's pace; a shot's reach; the reload
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


def _seq(*parts):
    return [pad for pad, n in parts for _ in range(n)]


DILATED = {
    "the tank: walk, turn, dodges": (Y, _seq(
        (U, 30), (0, 10), (LF, 12), (U, 20), (U | A, 2), (U, 20), (0, 20), (LF | A, 2), (0, 30), (A, 2), (0, 30),
        (RT | A, 3), (RT, 25), (D | A, 2), (0, 40))),
    "the boxer: steps, strafe jumps, a flip": (Y, _seq(
        (L, 20), (L | LF, 20), (L, 10), (L | LF | A, 2), (L | LF, 30), (L, 20), (L | U | A, 3), (L, 40), (L | A, 2),
        (L, 8), (L | RT | A, 2), (L, 50), (L | D | A, 2), (L | D, 4), (L | D | A, 2), (L, 60))),
    "the run: its click, a jump, a flip, a slide": (Y, _seq(
        (L, 2), (0, 1), (L | U, 60), (L | U | A, 2), (L | U, 40), (L | U | A, 2), (L | U, 5), (L | U | A, 2),
        (L | U, 50), (L | U | LF, 10), (L | U, 10), (L | D, 20), (L | U, 30), (L, 40))),
    "the terminators and the gun": (X, _seq(
        (Y, 2), (0, 50), (LF | Y, 2), (0, 50), (spec.PAD_B, 2), (0, 30), (RT | spec.PAD_B, 2), (0, 30), (U, 10), (0, 20))),
    "the jabs and the count": (Y, _seq(
        (X, 2), (0, 9), (X, 2), (0, 9), (LF | X, 2), (0, 9), (X, 2), (0, 30), (U, 12), (0, 50), (D | X, 2), (0, 30))),
    # (B's holds are short -- 8 fight frames at most, 4 with Left or Right:
    # the hold and the CHARGE are a thumb's clocks, counted in frames of
    # glass, and a longer hold slows time in the "running" play too)
    "the gun: drawn, a volley, shots on the move, the cylinder": (X, _seq(
        (B, 6), (0, 12), (LF | B, 4), (0, 10), (B, 3), (0, 3), (B, 3), (0, 3), (B, 3), (0, 30), (D | B, 8), (0, 40),
        (L | RT | B, 4), (L | RT, 20), (L, 10), (B, 2), (0, 8), (B, 2), (0, 8), (B, 4), (0, 30), (B, 4), (0, 20),
        (U, 30), (0, 20))),
}
FIGHT = ("px", "pz", "f_py", "yaw", "head", "anim", "af", "f_mv", "pose", "f_evf", "f_vx", "f_vz", "f_sty",
         "sjump_dir", "f_spd", "turned", "gun_draw", "gun_shots", "gun_reload", "bul0_rem", "bul1_rem",
         "bul0_ex", "bul0_ez", "bul1_ex", "bul1_ez", "bul0_hit", "bul1_hit")


@pytest.mark.parametrize("name", list(DILATED))
def test_time_dilated_is_the_same_fight(text, monkeypatch, name):
    """P33: "Im sure its about the numerics when time dialates thats the big
    issue here." One script of pads, a fight frame each, played in running
    time and again in slowed time (a strike button held on; each pad kept
    till the fight has moved a frame). Every cell that is the fight's --
    where he is, his height, his steering, his body, what he is doing, its
    frame, his pose, his speed -- is the same, frame for frame. (Found by
    it: one press of A read once a running frame while it was held -- a
    jump AND a flip; the run's double click and the slide's Down lost two
    times in three; Left + A dodging and turning him.)"""
    from zeta import gpu
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)
    button, script = DILATED[name]

    def play(slowed):
        g = Game(text)
        skip, rows = g.sym("f_skip"), []

        def step(pad):
            if not slowed:
                g.run(pad, 1)
                return
            for _ in range(12):                   # until the fight has moved a frame
                g.run(pad | button, 1)
                if g.d[skip] == 0:
                    break
        for k in range(204):                      # the same way in: one blow, then standing
            step(0) if slowed else g.run(button if k < 4 else 0, 1)
        assert bool(g.cell("slow_on")) == slowed
        for pad in script:
            step(pad)
            rows.append([g.cell(c) for c in FIGHT])
        return np.array(rows)
    a, b = play(False), play(True)
    bad = np.flatnonzero((a != b).any(1))
    assert not len(bad), (f"first at fight frame {bad[0]} (pad {script[bad[0]]}): "
                          f"{[(c, int(x), int(y)) for c, x, y in zip(FIGHT, a[bad[0]], b[bad[0]]) if x != y]}")
    assert np.hypot(a[-1][0] - a[0][0], a[-1][1] - a[0][1]) > 65536, "the script went nowhere"


def test_one_press_is_one_press_and_any_button_held_slows_time(text, monkeypatch):
    """P33: "what if gun and jump/evade also have the slow down" -- any of
    the four held past the hold knob slows time: the gun held to its shot
    (it fires as B comes up, as ever), a jump ridden through. And a thumb's
    press of A in slowed time -- eleven frames of glass -- is ONE jump: no
    flip thrown after it, and he lands where the jump lands."""
    from zeta import gpu
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)
    g = Game(text)
    hold, B = g.knob(HOLD), spec.PAD_B
    g.run(B, hold)
    assert not g.cell("slow_on")
    g.run(B, 12)
    assert g.cell("slow_on") and g.cell("anim") != 2, "the gun, held, did not slow time (or fired early)"
    g.run(0, 2)
    assert g.cell("anim") == 2 and g.cell("f_mv") >= MOVES.index("gun") and not g.cell("slow_on")
    g.run(0, 60)
    g.run(L, 40)
    g.run(L | A, hold + 12)                       # the boxer's jump, A kept down
    assert g.cell("slow_on") and g.cell("f_py") > 0 and g.cell("f_evf") == 0, "the jump, held, did not slow time"
    g.run(L, 120)
    assert g.cell("f_py") == 0
    # a strafe jump inside slowed time, A down eleven frames
    g.run(L | X, hold + 80)
    assert g.cell("slow_on")
    p0, y0, flips, ups, was = g.pos(), g.cell("yaw"), 0, 0, 0
    for f in range(240):
        g.run(L | X | (LF | A if f < 11 else 0), 1)
        flips += g.cell("f_evf") > 0
        ups += (g.cell("f_py") > 0) and not was
        was = g.cell("f_py") > 0
    assert ups == 1 and flips == 0, f"one press of A, slowed: {ups} jumps and {flips} frames of a flip"
    assert abs(g.local(p0, y0)[1] - 3.0) < 0.05, f"it landed {g.local(p0, y0)[1]:.2f} to his left, not 3.0"


@pytest.mark.parametrize("way,ahead,left", [(0, -1, 0), (U, 1, 0), (LF, 0, 1), (RT, 0, -1)])
def test_a_dodge_ends_where_it_ends(text, way, ahead, left):
    """P33: "work on the dodges it feels to slippy. for all movement I
    should be able to have accurate prediction of where I'll land or be."
    The dodge is its own twelve frames at the dodge knob's pace -- 2.4
    units, the way the pad points (no pad: back) -- and then he is STOPPED:
    not an inch more (it slid 0.83 more over twenty-two frames)."""
    g = Game(text)
    g.run(0, 30)
    p0, y0 = g.pos(), g.cell("yaw")
    g.run(way | A, 3)
    g.run(0, 10)
    at = g.local(p0, y0)
    want = g.knob(DODGE) / 65536 * 12
    assert abs(at[0] - ahead * want) < 0.03 and abs(at[1] - left * want) < 0.03, f"he is at {at}, not {want:.2f} that way"
    g.run(0, 40)
    assert np.hypot(*np.subtract(g.local(p0, y0), at)) < 0.005, "he slid on after the dodge"


def test_a_jump_lands_where_it_was_thrown(text, monkeypatch):
    """P33: the boxer's strafe jump is 3.0 units and he stays where he
    lands; the run's jump keeps its speed through the air whether Up is
    held or not (letting go mid-air cut it from 4.8 units to 1.6)."""
    from zeta import gpu
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)
    g = Game(text)
    g.run(L, 40)
    p0, y0 = g.pos(), g.cell("yaw")
    g.run(L | RT | A, 3)
    for _ in range(40):
        g.run(L, 1)
        if g.cell("f_py") == 0 and g.cell("sjump_dir") == 0:
            break
    at = g.local(p0, y0)
    assert abs(at[1] + 3.0) < 0.05 and abs(at[0]) < 0.02, f"the strafe jump landed at {at}"
    g.run(L, 30)
    assert np.hypot(*np.subtract(g.local(p0, y0), at)) < 0.005, "he slid on after landing"
    far = []
    for keep in (U, 0):
        g = Game(text)
        g.run(L, 2)
        g.run(0, 1)
        g.run(L | U, 70)                          # the run, at its speed
        assert g.cell("f_sty") == 1
        p0 = g.pos()
        g.run(L | U | A, 2)
        while g.cell("f_py") > 0:
            g.run(L | keep, 1)
        far.append(np.hypot(*np.subtract(g.pos(), p0)))
    assert far[0] > 4 and abs(far[0] - far[1]) < 0.05 * far[0], f"the run's jump: {far[0]:.2f} with Up, {far[1]:.2f} without"


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


def _flying(g):
    return max(g.cell(f"bul{i}_rem") for i in (0, 1)) > 0


@pytest.mark.parametrize("way", [0, LF, RT, D, U | LF])
def test_a_shot_is_a_bullet_and_lands_where_the_sight_said(text, way):
    """P34 ("make it feel more tactical too"): B down, the sight is drawn --
    a bead a round and a point where the shot will land -- along the line a
    release would fire: the pad's way from his steering, or his body's. The
    bullet then flies that line at its pace and lands on that point: a wall's
    face, where the street ends (or nothing, 13 units out)."""
    g = Game(text)
    g.run(0, 30)
    n0, y0 = g.d[spec.OL_BASE], g.cell("yaw")
    g.run(way | B, 8)
    (x0, z0), still = g.pos(), way in (0, LF, RT)                   # (Up and Down walk him, the button held)
    assert g.cell("yaw") == y0, "a button freshly down, and the tank turned"
    hit, far = g.cell("ray_hit"), g.cell("ray_len") / 65536
    assert g.d[spec.OL_BASE] == n0 + 6 + (1 if hit else 0), "the sight: six beads, and its point on a wall"
    end = (g.cell("ray_x"), g.cell("ray_z"))
    a = (y0 + {0: 0, LF: 256, RT: -256, D: 512, U | LF: 128}[way]) * 2 * np.pi / 1024
    fx, fz = -np.sin(a), np.cos(a)                                  # the pad's way, from his steering
    ox, oz = x0 + 0.5 * fx + 0.14 * fz, z0 + 0.5 * fz - 0.14 * fx   # the gun: ahead, to his right
    assert abs(end[0] / 65536 - (ox + far * fx)) < 0.01 and abs(end[1] / 65536 - (oz + far * fz)) < 0.01
    if way in (LF, RT):                                             # the street's walls: 4.65 either side
        assert hit == 1 and abs(abs(end[0] / 65536 - x0) - 4.65) < 0.13, (hit, end[0] / 65536 - x0)
    if way == 0:
        assert hit == 0 and far == GUN_RANGE, "down the street: nothing in reach"
    g.run(way, 1)
    assert g.d[spec.OL_BASE] <= n0, "the sight outlived the button"
    g.run(0, 1)
    assert _flying(g), "no bullet the frame after he let go"
    assert (g.cell("head") - y0) % 1024 == round(a * 1024 / (2 * np.pi) - y0) % 1024
    flew = 1
    while _flying(g):
        g.run(0, 1)
        flew += 1
        assert flew < 12
    there = [(g.cell(f"bul{i}_ex"), g.cell(f"bul{i}_ez")) for i in (0, 1) if g.cell(f"bul{i}_hit") & 3 or not hit]
    if still:
        assert flew - 1 == int(far // GUN_V) + 1, (flew, far)       # (it lands the frame it passes the place)
        assert end in there, "the bullet's line is not the sight's"
    if hit:
        assert g.cell("spark", 3) > 0 and (g.cell("spark"), g.cell("spark", 2)) in there, "it did not land there"
    else:
        assert (g.cell("spark"), g.cell("spark", 2)) != end


def test_the_drawn_gun_fires_as_he_lets_go(text):
    """P34: the frames a shot took to come up are spent while B is down --
    held five frames or more, the bullet leaves the frame after he lets go;
    a one-frame press is no later than it was. Standing, the gun is seen to
    come up; and a plain shot does not leave the lens trembling (it did,
    from P30: a shake of -1, counted down for ever)."""
    for down, most in ((8, 2), (5, 2), (1, 6)):
        g = Game(text)
        g.run(0, 30)
        poses = []
        for _ in range(down):
            g.run(B, 1)
            poses.append(g.cell("pose"))
        if down == 8:
            assert poses[:4] == sorted(set(poses[:4])) and len(set(poses[3:])) == 1, poses
        f = 0
        while not _flying(g):
            g.run(0, 1)
            f += 1
            assert f < 12, "no shot"
        assert f <= most, (down, f)
        lens = []
        for _ in range(70):
            g.run(0, 1)
            assert g.cell("f_shake") >= 0
            lens.append(g.lens())
        assert g.cell("f_shake") == 0 and len(set(lens[-20:])) == 1, "the lens is still shaking"


def test_the_cylinder_empties_reloads_and_a_terminator_fills_it(text, monkeypatch):
    """P34: the mag knob's rounds (six). The last one fired, the gun is
    RELOAD frames from full, and B in that time is no shot; a terminator
    thrown fills it at once -- the fists load the gun. The sight shows a
    bead a round. At 0 the gun never runs dry."""
    from zeta import gpu
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)
    g = Game(text)
    g.run(0, 30)
    n0 = g.d[spec.OL_BASE]

    def shot():                                   # a thumb's tap; -> (beads on the sight, did a bullet leave?)
        g.run(B, 5)
        beads, went = g.d[spec.OL_BASE] - n0, False
        for _ in range(12):
            g.run(0, 1)
            went = went or _flying(g)
        return beads, went
    assert [shot() for _ in range(6)] == [(6 - k, True) for k in range(6)]
    assert g.cell("gun_reload") > 0
    assert shot() == (0, False), "it fired while it was reloading"
    g.run(0, RELOAD)
    assert g.cell("gun_shots") == 0 and shot() == (6, True), "it did not reload"
    shot(), shot()
    assert g.cell("gun_shots") == 3
    g.run(Y, 5)
    g.run(0, 50)
    assert g.cell("gun_shots") == 0 and shot()[0] == 6, "a terminator did not fill it"
    g.d[g.sym("knobs") + MAG] = 0
    assert all(shot() == (6, True) for _ in range(9)) and g.cell("gun_reload") == 0, "at 0 it ran dry"


@pytest.mark.parametrize("off,struck", [(0.0, True), (0.5, True), (0.9, False), (-0.5, False)])
def test_a_shot_meets_the_key_only_on_its_line(text, off, struck):
    """P34 (the player: "we can use the item as a target"): the district's
    key, lying in its plaza, is a thing a shot can meet -- on the gun's
    line (it leaves 0.14 to his right) and within 0.45 of it, and not
    otherwise: nothing is aimed for him. Struck, it rings and leaps."""
    g = Game(text)
    g.run(0, 30)
    kx, kz = g.cell("ctx_x"), g.cell("ctx_z")
    for name, v in (("px", kx + int(off * 65536)), ("pz", kz + 5 * 65536), ("yaw", 512), ("head", 512)):
        g.d[g.sym(name)] = v & 0xFFFFFFFF
    g.run(B, 8)                                   # facing -z: his right is -x, the gun at off - 0.14
    assert (g.cell("ray_hit") == 2) == struck, (g.cell("ray_hit"), g.cell("ray_len") / 65536)
    if struck:
        assert abs(g.cell("ray_len") / 65536 - 4.5) < 0.01 and g.cell("ray_z") == kz
    g.run(0, 10)
    assert (g.cell("key_hit") > 0) == struck
    assert g.cell("key_held") == 0, "a shot picked it up"


def test_held_to_aim_the_lens_comes_round_behind_the_shot(text):
    """P34: a tap leaves the lens where it is. B held past the hold knob --
    time slowed for the shot -- the lens comes round behind his BODY and
    looks down the sight; it stays to see the shot land, and comes back."""
    g = Game(text)
    g.run(0, 30)
    y0 = g.cell("yaw")

    def off(to):
        return abs((g.lens()[2] - to + 512) % 1024 - 512)
    g.run(RT | B, 8)
    assert off(y0) < 16, "a tap turned the lens"
    g.run(RT, 1)
    g.run(0, 60)
    assert off(g.cell("yaw")) < 16
    g.run(D | B, 70)
    assert g.cell("slow_on") and off(g.cell("head")) < 96, (off(g.cell("head")), "the lens is not behind the shot")
    g.run(D, 1)
    g.run(0, 12)
    assert off(g.cell("head")) < 96, "the lens left before the shot landed"
    g.run(0, 90)
    assert off(g.cell("yaw")) < 16, "the lens did not come back"


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
        for k in range(10):
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
