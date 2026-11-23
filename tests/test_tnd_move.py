"""TND's lab and reactor, P48 (docs/TND-PORT.md): exact dodges, and where he will land.

The player, 2026-11-23: "for the boxing I think we want an exact left right up
down flip jump, not the double press one, this is to quick dodge maybe two
units, the none boxing is a single unit dodge. The running should feel very
good at figuring out where your jump and double jump (flip) should land, maybe
having the camera also cover the ground to see where you are going to land.
over all this positioning tackcially."

A unit is his own width (the reactor's check).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_tnd_lab as LAB                                  # noqa: E402
import test_tnd_reactor as RX                               # noqa: E402
from test_tnd_lab import no_paint, pytestmark               # noqa: E402,F401

A, B, L, R, U, D, LF, RT = RX.A, RX.B, RX.L, RX.R, RX.U, RX.D, RX.LF, RX.RT
W = RX.W
ONE = 65536


def _fresh(mod, layer):
    """the cart's text, rebuilt if the generator is newer (as the lab's and the reactor's own tests do)"""
    import os
    import subprocess
    if not mod.CART.is_file() or mod.CART.stat().st_mtime < mod.GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER=layer)
        for k in ("TND_SONG", "TND_OUT", "TND_CROWD", "TND_CARTMESH", "TND_AT"):
            env.pop(k, None)
        subprocess.run([sys.executable, str(mod.GEN)], check=True, env=env, cwd=mod.ROOT, stdout=subprocess.DEVNULL)
    return mod.CART.read_text().splitlines()


@pytest.fixture(scope="module")
def rx_text():
    return _fresh(RX, "11")


@pytest.fixture(scope="module")
def lab_text():
    return _fresh(LAB, "10")


def went(g, pads, hold=0, tail=40):
    """(east, north) he went, in his widths; how high; frames in the air"""
    u0, v0 = g.uv()
    g.run(hold | pads | A, 3)
    high = air = 0
    for _ in range(tail):
        g.run(hold, 1)
        high = max(high, g.cell("f_py"))
        air += g.cell("f_py") > 0
    u1, v1 = g.uv()
    return round((u1 - u0) / W, 2), round((v1 - v0) / W, 2), high / ONE, air


@pytest.mark.parametrize("pad,want", [(U, (0, 1)), (LF, (-1, 0)), (RT, (1, 0)), (0, (0, -1))])
def test_the_tanks_dodge_is_one_of_his_widths_exactly(rx_text, pad, want):
    g = RX.Game(rx_text)
    g.put(0.0, 0.0, RX.NORTH)
    e, n, high, air = went(g, pad)
    assert (e, n) == want and air == 0, f"the dodge went ({e}, {n}) of his widths"
    g.poke("knobs", 2 * ONE, 13)                              # the dodge knob is that unit's length
    g.put(0.0, 0.0, RX.NORTH)
    e, n, _, _ = went(g, pad)
    assert (e, n) == (2 * want[0], 2 * want[1])


@pytest.mark.parametrize("pad,want", [(U, (0, 4)), (D, (0, -4)), (LF, (-4, 0)), (RT, (4, 0))])
def test_the_boxers_flip_is_one_press_four_widths(rx_text, pad, want):
    g = RX.Game(rx_text)
    g.put(0.0, 0.0, RX.NORTH)
    g.run(L, 10)
    assert g.cell("f_sty") == 2
    e, n, high, air = went(g, pad, hold=L)
    assert (e, n) == want, f"the flip went ({e}, {n}) of his widths"
    assert 1.3 < high < 1.6 and air <= 32, f"it rose {high:.2f} and took {air} frames"   # (P51: over a body)


def test_the_flip_has_no_second_and_the_plain_jump_is_still_the_jump(rx_text):
    g = RX.Game(rx_text)
    g.put(0.0, 0.0, RX.NORTH)
    g.run(L, 10)
    u0, v0 = g.uv()
    g.run(L | LF | A, 3)
    g.run(L, 2)
    g.run(L | LF | A, 3)                                      # again, in the air: nothing
    g.run(L, 30)
    assert round((g.uv()[0] - u0) / W, 2) == -4.0
    g.put(0.0, 0.0, RX.NORTH)
    g.run(L, 10)
    e, n, high, air = went(g, 0, hold=L)
    assert (e, n) == (0, 0) and high > 1.2, "A alone in the boxer is not the jump"


def _run_up(g):
    g.put(0.0, -12.0, LAB.NORTH)
    g.run(L, 2)
    g.run(0, 3)
    g.run(L, 3)
    g.run(L | U, 70)
    assert g.cell("f_sty") == 1


def _flight(g, flip_at=None, pad=0):
    g.run(L | U | A, 3)
    marks = []
    for i in range(90):
        g.run(L | U | ((A | pad) if flip_at is not None and flip_at <= i < flip_at + 3 else 0), 1)
        if g.cell("land_on"):
            marks.append((i, g.uv(g.cell("land_x") / ONE, g.cell("land_z") / ONE)))
        if g.cell("f_py") == 0 and marks and i > 3:
            break
    landed = g.uv()
    return [(i, float(np.hypot(m[0] - landed[0], m[1] - landed[1]))) for i, m in marks]


def test_the_mark_is_where_the_runs_jump_comes_down_from_its_first_frame(lab_text):
    g = LAB.Game(lab_text)
    _run_up(g)
    off = _flight(g)
    assert len(off) > 20 and max(e for _, e in off) < 0.02, f"the mark was {max(e for _, e in off):.2f} from where he landed"
    assert g.cell("land_on") == 0, "the mark is still there with him on the floor"


@pytest.mark.parametrize("pad", [0, LF, D])
def test_the_mark_is_where_the_flip_comes_down_once_it_is_thrown(lab_text, pad):
    g = LAB.Game(lab_text)
    _run_up(g)
    off = _flight(g, flip_at=8, pad=pad)
    before = [e for i, e in off if i < 8]
    after = [e for i, e in off if i > 12]
    assert min(before) > 1.0, "the flip changed nothing: the test proves nothing"
    assert max(after) < 0.1, f"after the flip the mark was {max(after):.2f} from where he landed"


def test_in_the_air_the_lens_looks_down_and_stands_to_his_right_but_not_when_locked(lab_text):
    g = LAB.Game(lab_text)
    _run_up(g)
    g.run(L | U | A, 3)
    look = 0
    for _ in range(14):
        g.run(L | U, 1)
        look = max(look, g.cell("land_look"))
    assert look >= 15, "the lens did not look down for the floor"
    g.run(L | U, 60)
    assert g.cell("land_look") == 0, "the lens is still looking down with him on the floor"
    b = LAB.Game(lab_text)
    b.at_the_clone(3.0)
    b.run(L | R, 12)
    assert b.cell("locked") == 1
    b.run(L | R | A, 3)
    b.run(L | R, 8)
    assert b.cell("f_py") > 0 and b.cell("land_look") == 0, "locked, the lens left its work to look at the floor"


# ---- P49: the acrobatics -- the side flip tucked, the whole clip played, a whole turn ----

ROOT = Path(__file__).resolve().parents[1]


def test_the_lab_flips_are_tucked_with_the_hands_on_the_shins():
    """the baked shapes (tools/tnd_acro.py): archive axes, z up. Held in the middle of each, the feet are drawn up to
    within half a unit of the hips -- the archive's cartwheel had them a body's length below, thrown wide -- and each
    hand is at its own shin"""
    acro, old = np.load(ROOT / "assets" / "tnd" / "acro.npz"), np.load(ROOT / "assets" / "tnd" / "boxer.npz")
    for name, n in (("acro_side", 24), ("acro_tuck", 20), ("acro_back", 20)):
        V = acro["V_" + name]
        assert len(V) == n
        mid = V[n // 2]
        assert mid[:, 2].max() - mid[:, 2].min() < 1.0, f"{name} is not tucked: {mid[:, 2].ptp():.2f} tall"
        assert np.abs(V[0] - old["V_flip_fwd"][0]).max() < 0.02, f"{name} does not begin in the guard"
    cart = old["V_flip_cart"][12]
    side = acro["V_acro_side"][12]
    # (across: the cartwheel's feet 1.37 apart; tucked, he is no wider than his elbows on his shins)
    assert np.ptp(cart[:, 1]) > 1.2 and np.ptp(side[:, 1]) < 0.6 * np.ptp(cart[:, 1]), "the side flip's legs are still thrown wide"


def _flip(g, pad):
    g.put(0.0, 0.0, RX.NORTH)
    g.run(L, 12)
    poses, rolls, pitches = [], [], []
    from zeta import spec
    body = g.sym("body_desc")
    g.run(L | pad | A, 3)
    for _ in range(34):
        n = g.d[spec.OL_BASE]
        rows = [g.d[spec.OL_BASE + 1 + i * spec.OL_STRIDE: spec.OL_BASE + 1 + (i + 1) * spec.OL_STRIDE] for i in range(n)]
        ang = next(r[4] for r in rows if r[0] == body)
        poses.append(g.cell("pose"))
        pitches.append((ang >> 10) & 1023)
        rolls.append((ang >> 20) & 1023)
        g.run(L, 1)
    return poses, pitches, rolls


@pytest.mark.parametrize("pad,which", [(LF, "roll"), (RT, "roll"), (U, "pitch"), (D, "pitch")])
def test_the_boxers_flip_turns_once_round_and_plays_its_whole_shape(rx_text, pad, which):
    g = RX.Game(rx_text)
    poses, pitches, rolls = _flip(g, pad)
    turn = rolls if which == "roll" else pitches
    seen = {round(a / 128) % 8 for a in turn}
    assert len(seen) >= 6, f"the flip did not go round: {turn}"
    flip = [x for x in poses if x != poses[-1]]
    assert max(flip) - min(flip) >= 18, f"the flip played {max(flip) - min(flip) + 1} of its poses"


# ---- P50: the run as a traceur's -- the leap in the air, the landing absorbed, the roll out of a flip ----

def _running(lab_text):
    g = LAB.Game(lab_text)
    _run_up(g)
    return g


def test_in_the_air_the_run_leaps_by_how_fast_he_rises_or_falls(lab_text):
    g = _running(lab_text)
    stride = {g.cell("pose") for _ in range(16) if not g.run(L | U, 1)}
    g.run(L | U | A, 3)
    seen = []
    while g.cell("f_py") > 0:
        seen.append((g.cell("f_pvy"), g.cell("pose")))
        g.run(L | U, 1)
    poses = [q for _, q in seen]
    assert not (set(poses) & stride), "he ran the stride in the air"
    assert len(set(poses)) >= 5, f"the leap showed {len(set(poses))} shapes"
    assert poses == sorted(poses), "the leap's shapes did not go from the drive to the gather as he went from rising to falling"
    assert seen[0][1] <= min(poses) + 1 and seen[-1][1] >= max(poses) - 1


def test_a_run_jump_lands_absorbed_then_the_stride_takes_up(lab_text):
    g = _running(lab_text)
    g.run(L | U | A, 3)
    while g.cell("f_py") > 0:
        g.run(L | U, 1)
    land = []
    for _ in range(12):
        land.append((g.cell("run_land"), g.cell("pose")))
        g.run(L | U, 1)
    absorbed = [q for n, q in land if n > 0] + [land[0][1]]
    assert len(set(absorbed)) >= 6, "the landing was not taken in the knees"
    assert g.cell("run_land") == 0 and g.cell("anim") == 5, "he did not run on"
    assert g.cell("f_evf") == 0, "a plain jump rolled"


def test_from_a_flip_he_rolls_out_keeping_his_speed(lab_text):
    g = _running(lab_text)
    pace = g.cell("f_spd")
    g.run(L | U | A, 3)
    g.run(L | U, 8)
    g.run(L | U | A, 3)                                       # the flip
    while g.cell("f_py") > 0 or g.cell("f_evk") != 8:
        g.run(L | U, 1)
        assert g.cell("f_evf") >= 0
    u0, v0 = g.uv()
    assert g.cell("f_evk") == 8 and g.cell("f_evf") == 16, "he did not roll"
    from zeta import spec
    body, pitches = g.sym("body_desc"), []
    while g.cell("f_evf") > 0:
        n = g.d[spec.OL_BASE]
        rows = [g.d[spec.OL_BASE + 1 + i * spec.OL_STRIDE: spec.OL_BASE + 1 + (i + 1) * spec.OL_STRIDE] for i in range(n)]
        pitches.append((next(r[4] for r in rows if r[0] == body) >> 10) & 1023)
        g.run(L | U, 1)
    assert len({round(a / 128) % 8 for a in pitches}) >= 6, "the roll did not go over"
    gone = float(np.hypot(g.uv()[0] - u0, g.uv()[1] - v0))
    assert gone > 1.2, f"he rolled {gone:.2f}: his speed was lost"
    g.run(L | U, 30)
    assert g.cell("anim") == 5 and g.cell("f_spd") > pace // 2, "he did not run on out of the roll"


def test_a_jump_out_of_the_roll_ends_it_and_standing_still_he_does_not_roll(lab_text):
    g = _running(lab_text)
    g.run(L | U | A, 3)
    g.run(L | U, 8)
    g.run(L | U | A, 3)
    while g.cell("f_evk") != 8:
        g.run(L | U, 1)
    g.run(L | U, 4)
    g.run(L | U | A, 3)
    assert g.cell("f_evf") == 0 and g.cell("f_py") > 0, "the jump did not take him out of the roll"
    s = LAB.Game(lab_text)                                    # in the run, but not going: a flip lands absorbed
    s.put(0.0, -12.0, LAB.NORTH)
    s.run(L, 2)
    s.run(0, 3)
    s.run(L, 3)
    s.run(L, 10)
    s.run(L | A, 3)
    s.run(L, 6)
    s.run(L | A, 3)
    for _ in range(60):
        s.run(L, 1)
        assert s.cell("f_evk") != 8, "standing still, he rolled"



# ---- P51: the boxer's flip goes over a body; the sight has no spark; the lens looks into the landing ----

@pytest.mark.parametrize("pad,side", [(U, (0, 1)), (D, (0, -1)), (LF, (-1, 0)), (RT, (1, 0))])
def test_the_boxers_flip_clears_the_clone_every_way(lab_text, pad, side):
    """from a jab's reach on one side of it to a jab's reach on the other, the tuck (its lowest half a unit above
    his feet) over its head (1.41) all the while he is over it"""
    g = LAB.Game(lab_text)
    cu, cv = g.body()
    reach = 2 * W
    g.put(cu - side[0] * reach, cv - side[1] * reach, LAB.NORTH)
    g.run(L, 12)
    g.run(L | pad | A, 3)
    over = []
    for _ in range(40):
        g.run(L, 1)
        u, v = g.uv()
        if max(abs(u - cu), abs(v - cv)) < 0.35:
            over.append(g.cell("f_py") / ONE)
    u, v = g.uv()
    assert over, "he did not pass over it"
    assert min(over) + 0.5 > 1.41, f"he went through its head: {min(over):.2f} up"
    assert abs(u - (cu + side[0] * reach)) < 0.05 and abs(v - (cv + side[1] * reach)) < 0.05, "he did not land a reach beyond it"


def test_aiming_draws_the_laser_and_no_spark_until_a_round_lands(lab_text):
    from zeta import spec
    g = LAB.Game(lab_text)
    g.at_the_clone(4.0)
    g.run(R, 12)
    dots = {g.sym(n) for n in ("lab_dot", "lab_dot_hot", "dot_m", "hot_m")}
    for _ in range(40):
        g.run(R | B, 1)
        n = g.d[spec.OL_BASE]
        rows = [g.d[spec.OL_BASE + 1 + i * spec.OL_STRIDE] for i in range(n)]
        assert not (set(rows) & dots), "a spark is drawn on the target with no round landed"


def _lens_meets_floor(g):
    """where the line through the middle of the glass meets the floor (the lens's own place, yaw and pitch)"""
    from zeta import spec
    s32 = lambda v: v - (1 << 32) if v & (1 << 31) else v      # noqa: E731
    x, y, z = (s32(g.d[r]) / ONE for r in (spec.CAM_X, spec.CAM_Y, spec.CAM_Z))
    yaw, pitch = g.d[spec.CAM_YAW] & 1023, g.d[spec.CAM_PITCH] & 1023
    a, b = 2 * np.pi * yaw / 1024, 2 * np.pi * (pitch if pitch < 512 else pitch - 1024) / 1024
    if b <= 0:
        return None
    run = (y - g.cell("curb_y") / ONE) / np.tan(b)
    return x - np.sin(a) * run, z + np.cos(a) * run


@pytest.mark.parametrize("steer", [0, LF])
def test_in_the_runs_air_the_lens_looks_into_where_he_will_land(lab_text, steer):
    g = _running(lab_text)
    g.run(L | U | A, 3)
    off = []
    for i in range(40):
        g.run(L | U | steer, 1)
        if g.cell("f_py") == 0:
            break
        hit = _lens_meets_floor(g)
        if i > 10 and hit is not None and g.cell("land_on"):
            land = (g.cell("land_x") / ONE, g.cell("land_z") / ONE)
            off.append(float(np.hypot(hit[0] - land[0], hit[1] - land[1])))
    assert off and np.median(off) < 1.2, f"the lens's line met the floor {np.median(off) if off else None} from the spot"


def test_steering_in_the_air_the_lens_stands_on_the_inside(lab_text):
    from zeta import spec
    g = _running(lab_text)
    g.run(L | U | A, 3)
    g.run(L | U | LF, 14)
    s32 = lambda v: v - (1 << 32) if v & (1 << 31) else v      # noqa: E731
    yaw = 2 * np.pi * (g.d[spec.CAM_YAW] & 1023) / 1024
    fx, fz = -np.sin(yaw), np.cos(yaw)                        # the lens's forward
    dx, dz = (g.cell("px") - s32(g.d[spec.CAM_X])) / ONE, (g.cell("pz") - s32(g.d[spec.CAM_Z])) / ONE
    left = fx * dz - fz * dx                                  # (> 0: he is to the lens's right, the lens on his left)
    assert left > 0.2, "turning left, the lens is not on the inside of the turn"


def test_the_landing_and_the_roll_hand_him_to_the_strides_first_pose(lab_text):
    g = _running(lab_text)
    g.run(L | U | A, 3)
    while g.cell("f_py") > 0:
        g.run(L | U, 1)
    while g.cell("run_land") > 0:
        g.run(L | U, 1)
    assert g.cell("f_ph") >> 16 == 0, "the stride did not take up from its first pose"
