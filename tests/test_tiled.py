"""test_tiled.py -- THE BLEND-ORDER LAW, pinned before its silicon exists.

Roadmap item 15 flagged one question as harder than 13b's and said to
settle it before building: tiling changes the ORDER of pixel writes, so
what does the law say the answer is?

The answer rests on one fact -- A PIXEL BELONGS TO EXACTLY ONE TILE --
and therefore on one rule:

    THE BIN PRESERVES DISPLAY-LIST ORDER.

Given that, the fragments arriving at any pixel are the same subsequence
of the global order they are today, so the depth test sees the same
faces in the same sequence and ties resolve identically. Tiling becomes
a no-op for everything Zeta draws.

These tests exist because "no-op by construction" is what people say
right before they ship a seam. Every one of them is paired with its own
negative: a deliberately wrong bin order that MUST change the picture.
An equality test whose inputs are order-insensitive proves nothing, and
the first version of this file had exactly that problem -- reversing
face order on fabric.zol changed nothing, because z-buffered opaque
geometry at distinct depths genuinely IS order-independent. The order
only becomes visible at exact depth ties and under blending, so that is
what these fixtures are made of.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import asm, carts, gpu, spec, tiled

SUB = spec.SUB


def blank():
    # seed() gained a third plane (the plate's shadow mask, spec.PICK_SH)
    # and these tests want only the two they always did.
    fb, zb, _sh = gpu.seed([0] * spec.DMEM_WORDS)
    return fb, zb


def tri(fb, zb, pts, col, z, clip=None, alpha=None):
    a, b, c, d, e, f = pts
    kw = {}
    if clip is not None:
        kw["clip"] = clip
    if alpha is not None:
        kw["alpha"] = alpha
    gpu._fill(fb, zb, a << SUB, b << SUB, c << SUB, d << SUB, e << SUB,
              f << SUB, col, ((0, 0),) * 3, z, 0, 0, **kw)


def diff(a, b):
    return int((a != b).any(axis=2).sum())


# --------------------------------------------------------------------------
# ties: where order is observable at all
# --------------------------------------------------------------------------
TIE = (10, 10, 200, 10, 10, 200)


def paint_tie(fb, zb, order, clip=None):
    cols = [(31, 0, 0), (0, 31, 0)]
    for i in order:
        tri(fb, zb, TIE, cols[i], 1000, clip)


def test_equal_depth_resolves_to_the_later_face():
    """The machine's depth test is `z <= stored`, so coplanar faces are
    NOT order-independent -- the last one wins. This is the existing law
    and the reason tiling has to preserve order at all."""
    fb, zb = blank(); paint_tie(fb, zb, [0, 1])
    assert tuple(fb[50, 50]) == (0, 255, 0)
    fb, zb = blank(); paint_tie(fb, zb, [1, 0])
    assert tuple(fb[50, 50]) == (255, 0, 0)


def test_tiling_preserves_tie_resolution():
    fb, zb = blank(); paint_tie(fb, zb, [0, 1])
    t, tz = blank()
    for box in tiled.tiles():
        paint_tie(t, tz, [0, 1], clip=box)
    assert diff(fb, t) == 0


def test_a_bin_out_of_order_changes_the_picture():
    """The negative half. Without this the test above passes for a
    renderer that draws nothing at all."""
    fb, zb = blank(); paint_tie(fb, zb, [0, 1])
    t, tz = blank()
    for box in tiled.tiles():
        paint_tie(t, tz, [1, 0], clip=box)
    assert diff(fb, t) > 10000


# --------------------------------------------------------------------------
# THE BLEND-ORDER LAW
# --------------------------------------------------------------------------
OPAQUE = ((0, 0, 300, 0, 0, 280), (31, 31, 31), 400)
BLEND = [((20, 20, 260, 20, 20, 240), (31, 0, 0), 300, 8),
         ((60, 40, 300, 40, 60, 260), (0, 31, 0), 200, 8),
         ((40, 80, 280, 80, 40, 270), (0, 0, 31), 100, 8)]


def paint_blend(fb, zb, order, clip=None):
    pts, col, z = OPAQUE
    tri(fb, zb, pts, col, z, clip)                       # pass 1: opaque
    for i in order:                                      # pass 2: blended
        pts, col, z, a = BLEND[i]
        tri(fb, zb, pts, col, z, clip, alpha=a)


def test_blend_order_is_observable():
    fb, zb = blank(); paint_blend(fb, zb, [0, 1, 2])
    other, oz = blank(); paint_blend(other, oz, [2, 1, 0])
    assert diff(fb, other) > 10000, "the fixture cannot see order"


def test_tiled_blending_equals_immediate_blending():
    """The law's central claim. Per pixel the fragment sequence is
    (opaque in list order) then (blended in list order) either way, so
    the two must agree to the bit."""
    fb, zb = blank(); paint_blend(fb, zb, [0, 1, 2])
    t, tz = blank()
    for box in tiled.tiles():
        paint_blend(t, tz, [0, 1, 2], clip=box)
    assert diff(fb, t) == 0


def test_a_blended_face_tests_depth_but_never_writes_it():
    """What makes the composite order equal the cart's chosen order:
    blended faces cannot occlude one another."""
    fb, zb = blank(); tri(fb, zb, OPAQUE[0], OPAQUE[1], OPAQUE[2])
    before = zb.copy()
    for i in (0, 1, 2):
        pts, col, z, a = BLEND[i]
        tri(fb, zb, pts, col, z, alpha=a)
    assert np.array_equal(zb, before)


@pytest.mark.parametrize("a", range(17))
def test_the_face_blend_is_the_compositor_blend(a):
    """One blend rule in this machine, not two: a blended FACE uses the
    same sixteenths as the scanout compositor (spec.CO_BASE), so 16 is
    exactly opaque and 0 is exactly invisible."""
    fb, zb = blank()
    dst = int(fb[50, 50, 0]) >> 3
    tri(fb, zb, TIE, (0, 0, 0), 1000, alpha=a)
    want5 = (dst * (16 - a) + 0 * a) >> 4
    assert fb[50, 50, 0] == ((want5 << 3) | (want5 >> 2))


# --------------------------------------------------------------------------
# the whole machine, tiled: every cart, bit for bit
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cart", ["cube", "orbit", "fabric", "tex",
                                  "lodspan", "hall", "fade"])
def test_real_carts_render_identically_tile_by_tile(cart):
    path = carts.path(cart)
    assert tiled.compare(asm.assemble(path), frames=2) == [0, 0]
