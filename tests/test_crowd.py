"""test_crowd.py -- spec.OLX_PTR: the long list, 511 objects.

The pointer's rule is the whole of the law here and it is tested as a
rule: a list is long or it is not on the POINTER alone, a cart that
never set the cell is on the short list exactly as before, and the
counts above the sixty-fourth are written only while the list is long.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import cabinet, carts, gpu, spec

LIMIT = spec.DMEM_WORDS - 1 - spec.OLX_MAX * spec.OL_STRIDE


def _crowd(frames=3):
    m = cabinet.VirtualMachine(cabinet.load_cart(carts.path("crowd")))
    for _ in range(frames):
        m.frame(0)
    return m


def test_the_pointer_alone_decides():
    d = [0] * spec.DMEM_WORDS
    d[spec.OL_BASE] = 5
    assert spec.object_list(d) == (spec.OL_BASE, 5)
    for p, n, want in ((2000, 300, (2000, 300)),
                       (2000, 9999, (2000, spec.OLX_MAX)),
                       (LIMIT, 7, (LIMIT, 7)),             # the last address
                       (LIMIT + 1, 7, (spec.OL_BASE, 5)),  # one past it
                       (0xFFFFFFFF, 7, (spec.OL_BASE, 5)),
                       (0x80000000 | 2000, 7, (spec.OL_BASE, 5))):
        d[spec.OLX_PTR] = p
        if p < spec.DMEM_WORDS:
            d[p] = n
        assert spec.object_list(d) == want, (p, n)
        if p < spec.DMEM_WORDS:
            d[p] = 0


def test_the_short_list_still_stops_at_sixty_four():
    d = [0] * spec.DMEM_WORDS
    d[spec.OL_BASE] = 500
    assert spec.object_list(d) == (spec.OL_BASE, spec.OL_MAX)


def test_the_law_draws_511_and_not_the_nine_after():
    """The cart lists 520. The nine past the limit are slabs across the
    whole glass in a colour nothing else has."""
    m = _crowd()
    fb = np.asarray(m.framebuffer())
    slab = np.array(spec.display_rgb(0xFF00FF), np.uint8)
    assert not (fb == slab).all(axis=2).any(), "an object past the 511th drew"
    # ...and they WOULD draw: allow them, and the glass fills
    keep = spec.OLX_MAX
    spec.OLX_MAX = 600
    try:
        over = np.asarray(gpu.render(list(m.vm.dmem), m._cram, m._tex))
    finally:
        spec.OLX_MAX = keep
    assert (over == slab).all(axis=2).sum() > 50_000


def test_objects_past_the_255th_are_seen_and_counted():
    m = _crowd()
    d = m.vm.dmem
    high = [d[spec.VISX_BASE + k - spec.OL_MAX] for k in range(256, spec.OLX_MAX)]
    assert sum(1 for v in high if v) > 100, "few objects past the 255th reached the glass"
    total = sum(d[spec.VIS_BASE + k] for k in range(spec.OL_MAX)) + \
        sum(d[spec.VISX_BASE + k] for k in range(spec.OLX_MAX - spec.OL_MAX))
    assert total <= spec.W * spec.H


def test_a_count_is_what_leaves_with_the_object():
    """test_visible.py's check, on an owner with the ninth bit set: the
    marker, object 510, owner 511."""
    m = _crowd()
    d = list(m.vm.dmem)
    here = np.asarray(gpu.render(d, m._cram, m._tex))
    said = d[spec.VISX_BASE + 510 - spec.OL_MAX]
    base = d[spec.OLX_PTR] + 1 + 510 * spec.OL_STRIDE
    d2 = list(m.vm.dmem)
    d2[base] = 0                                    # nothing to walk
    gone = np.asarray(gpu.render(d2, m._cram, m._tex))
    moved = int((gone != here).any(axis=2).sum())
    assert said > 100
    # the marker is outlined: the line it draws on its neighbours leaves
    # with it too, so removal moves AT LEAST what the count says
    assert said <= moved <= said + 600, (said, moved)


def test_the_short_list_writes_nothing_above_vis_base():
    m = cabinet.VirtualMachine(cabinet.load_cart(carts.path("seen")))
    d = m.vm.dmem
    for k in range(spec.OLX_MAX - spec.OL_MAX):
        d[spec.VISX_BASE + k] = 0xABC000 + k
    m.frame(0)
    assert all(d[spec.VISX_BASE + k] == 0xABC000 + k
               for k in range(spec.OLX_MAX - spec.OL_MAX))


def test_no_cart_in_the_tree_already_uses_these_cells():
    lo, hi = spec.VISX_BASE, spec.VISX_BASE + spec.OLX_MAX - spec.OL_MAX
    for name in carts.names():
        cart = cabinet.load_cart(carts.path(name))
        m = cabinet.VirtualMachine(cart)
        if name != "crowd":
            assert m.vm.dmem[spec.OLX_PTR] == 0, f"{name} boots a long-list pointer"
        assert not any(m.vm.dmem[lo:hi]), f"{name} boots data into the long counts"
