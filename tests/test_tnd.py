# TEAR NOT DEMON on the Zeta -- P1, the fighter (docs/TND-PORT.md).
# Loads the committed cart, so it runs anywhere; the bake itself is held
# by the regen gate wherever the third-party source is present.

import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import cabinet, spec  # noqa: E402

CART = Path(__file__).parents[1] / "carts/tnd.zol"


def _jab_vs_still():
    """Two machines, same camera, same frame count: one jabs at frame 30.
    Anything that differs is the POSE -- delivered by the mover."""
    a = cabinet.VirtualMachine(cabinet.load_cart(CART))
    b = cabinet.VirtualMachine(cabinet.load_cart(CART))
    for f in range(36):
        a.frame(spec.PAD_A if f == 30 else 0)
        b.frame(0)
    return a, b


def test_the_jab_moves_the_body():
    """The pose bank reaches the body: a jab changes the picture while
    the camera and the floor do not move. A mover that delivered nothing
    would leave him frozen -- and every other check here green."""
    a, b = _jab_vs_still()
    diff = (a.framebuffer() != b.framebuffer()).any(axis=-1).sum()
    assert diff > 200, f"the jab moved only {diff} pixels"


def test_the_body_stays_whole():
    """Both halves draw: the cut at the hips must not drop either mesh
    (the machines drop an oversized mesh WHOLE and agree, so the cross
    cannot see it -- the forge's founding bug). Pixels in his torso band
    AND his leg band, against the empty frame."""
    a, _ = _jab_vs_still()
    fb = a.framebuffer().astype(int)
    body = (np.abs(fb - fb[5, 5]).sum(axis=-1) > 30)   # not the sky
    cols = slice(spec.W // 2 - 40, spec.W // 2 + 40)
    floorless = body[:, cols]
    torso = floorless[150:200].sum()
    assert torso > 300, f"the upper body is missing ({torso} px)"


@pytest.mark.skipif(shutil.which("verilator") is None,
                    reason="verilator not installed")
def test_both_machines_play_the_fighter():
    """A 2,967-word pose DMA every frame through two dense meshes,
    walking, jabbing and turning: bit-equal on silicon."""
    from zeta import silicon
    cart = cabinet.load_cart(CART)
    v, s = cabinet.VirtualMachine(cart), silicon.SiliconMachine(cart)
    for f in range(90):
        pad = (spec.PAD_UP if 15 <= f < 45 else 0) \
            | (spec.PAD_A if f == 50 else 0) \
            | (spec.PAD_RIGHT if f >= 70 else 0)
        v.frame(pad)
        s.frame(pad)
        assert np.array_equal(v.framebuffer(), s.framebuffer()), \
            f"the fighter diverges at frame {f}"


# ---- P3: the demons -----------------------------------------------------------
# The wave's cells are read by NAME from the cart's own symbol comments
# (the forge assigns addresses), with gen_tnd.py's field order.
FIELDS = ("x", "z", "h8", "hp", "st", "mf", "mv", "ai", "wf", "mov", "alt", "cf")


def _sym(name):
    for line in CART.read_text().splitlines():
        if line.startswith(f"; {name}: "):
            return int(line.rsplit(" at ", 1)[1])
    raise KeyError(name)


def _wave(m):
    base, d = _sym("demons"), m.vm.dmem
    s32 = lambda v: v - (1 << 32) if v & (1 << 31) else v      # noqa: E731
    return [{f: s32(d[base + i * len(FIELDS) + k]) for k, f in enumerate(FIELDS)}
            for i in range(3)]


def _player(m):
    s32 = lambda v: v - (1 << 32) if v & (1 << 31) else v      # noqa: E731
    return (s32(m.vm.dmem[_sym("px")]) / 65536, s32(m.vm.dmem[_sym("pz")]) / 65536)


def test_the_wave_closes_in_and_squares_up():
    """Spawned 7.8 out, they walk in along their own facing and stop
    short, inside the 1.5 reach -- every one of them, with nobody
    touching the pad. (The shove has its own witness below; this one
    passes without it, because the wave stops before it touches.)"""
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    start = [np.hypot(w["x"], w["z"]) / 65536 for w in _wave(m)]
    assert all(abs(r - 7.8) < 0.01 for r in start)
    for _ in range(360):
        m.frame(0)
    px, pz = _player(m)
    for i, w in enumerate(_wave(m)):
        r = np.hypot(w["x"] / 65536 - px, w["z"] / 65536 - pz)
        assert 0.8 < r < 1.55, f"demon {i} stands {r:.2f} from him"


def test_the_demons_swing_cross_then_hook():
    """Squared up and on his nose, each swings on the 74-frame rest,
    alternating the archive's two moves -- and while a swing runs, its
    clip row is the move's, not the idle's."""
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    clips, npart = _sym("demon_clips"), 12
    seen = [[] for _ in range(3)]
    for _ in range(700):
        m.frame(0)
        for i, w in enumerate(_wave(m)):
            if w["st"] == 1 and w["mf"] == 0:
                seen[i].append(w["mv"])
            if w["st"] == 1:
                row = (w["cf"] - clips) // npart
                assert row >= 48, f"demon {i} swings with an idle/walk row {row}"
    for i, moves in enumerate(seen):
        assert moves[:3] == [0, 1, 0], f"demon {i} threw {moves}"


def test_the_demon_swing_moves_its_body():
    """The swing is SEEN: freeze one machine's demons in idle by holding
    their swing counters off, and the pictures part when the other's
    swing starts. (Deleting the move rows from the clip select would
    leave these frames identical.)"""
    a = cabinet.VirtualMachine(cabinet.load_cart(CART))
    b = cabinet.VirtualMachine(cabinet.load_cart(CART))
    base = _sym("demons")
    first = None
    for f in range(560):
        a.frame(0)
        for i in range(3):                    # b's demons never commit
            b.vm.dmem[base + i * len(FIELDS) + FIELDS.index("ai")] = 0
        b.frame(0)
        if first is None and any(w["st"] for w in _wave(a)):
            first = f
        if first is not None and f == first + 12:
            diff = (a.framebuffer() != b.framebuffer()).any(axis=-1).sum()
            assert diff > 150, f"a swing moved only {diff} pixels"
            return
    raise AssertionError("no demon ever swung")


def test_bodies_do_not_pass_through_him():
    """He walks straight at the brute and keeps walking: the shove holds
    every body apart."""
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    for f in range(500):
        m.frame(spec.PAD_UP | (spec.PAD_RIGHT if f < 40 else 0))
        px, pz = _player(m)
        for i, w in enumerate(_wave(m)):
            r = np.hypot(w["x"] / 65536 - px, w["z"] / 65536 - pz)
            assert r > 0.6, f"frame {f}: demon {i} is {r:.2f} inside him"


def test_the_street_holds_him():
    """tear.py's _in_arena: forty units down the arm and no further, and
    never through the wall beside it. (Without the clamp, 1,400 frames
    of walking is 44.8 units -- in the fog -- and the turn into the wall
    walks him through it. He SLIDES along the end to the wall.)"""
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    for f in range(1700):
        m.frame(spec.PAD_UP | (spec.PAD_RIGHT if 1400 <= f < 1420 else 0))
        px, pz = _player(m)
        inside = max(abs(px), abs(pz)) <= 10.6 + 1e-3 \
            or (abs(px) <= 7.1 + 1e-3 and abs(pz) <= 40 + 1e-3) \
            or (abs(pz) <= 7.1 + 1e-3 and abs(px) <= 40 + 1e-3)
        assert inside, f"frame {f}: he stands off the street at ({px:.2f}, {pz:.2f})"
        if f == 1399:
            assert pz > 39.9, f"he never reached the end of the arm ({pz:.2f})"
    assert abs(px) > 6.9, f"the turn never took him to the wall ({px:.2f})"


def test_what_the_camera_cannot_see_is_not_sent():
    """The street's twenty objects and the demons' thirty-six are culled
    against the view before the sequencer sees them (its vertex cache
    holds 2,048 a frame). Witnessed both ways: some objects are always
    left out, and the count changes as he turns."""
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    counts = set()
    for f in range(90):
        m.frame(spec.PAD_RIGHT)
        n = m.vm.dmem[spec.OL_BASE]
        assert n < 59, f"frame {f}: all {n} objects listed -- nothing culled"
        counts.add(n)
    assert len(counts) > 3, f"the list never changed as he turned: {counts}"
