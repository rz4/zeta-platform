"""test_texpage.py -- 24 pages, and the eight that are not there.

TEX_PAGES stopped being a power of two in build 97 -- 24 pages, at +17
M10K of the 29 free, where 32 would have been +34 and did not fit. The
selector is five bits, so 24..31 are ASKABLE AND ABSENT, and what they
do had to be legislated rather than left to whichever machine got there
first:

    out of range reads as PAGE 0

Not the nearest slot. Clamping to 23 would show whatever the last page
happened to hold, so the same cart would look different depending on
what some unrelated object had loaded -- a bug that moves. Page 0 is
the page every cart has.

AND THE POINT IS THAT IT IS THE SAME PICTURE. A rule about which page
gets sampled is only worth anything if it is checked against PIXELS:
the law could resolve 30 to 0 in one function and index the texture
with the raw 30 somewhere else, and nothing would say so.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import cabinet, carts, gpu, spec

CART = carts.path("pagemax")


def _loaded(frames=40):
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    for _ in range(frames):
        m.frame(0)
    return m


def test_the_selector_resolves_as_the_law_says():
    for k in range(spec.TEX_PAGES):
        assert spec.tex_page(k) == k
    for k in range(spec.TEX_PAGES, spec.OBJ_PAGE_MASK + 1):
        assert spec.tex_page(k) == 0, f"page {k} must read as 0"
    # and the field cannot name anything the resolver has not considered
    assert spec.OBJ_PAGE_MASK + 1 >= spec.TEX_PAGES


def test_every_slot_holds_something_different():
    """Sixteen of the twenty-four were capacity nobody had ever filled,
    and build 97 found a four-bit wire hiding eight of them. Two slots
    holding the same bytes would make that invisible again."""
    m = _loaded()
    tex = np.asarray(m._tex).reshape(spec.TEX_PAGES, spec.TEX_STRIDE)
    assert all((tex[k] != 0).any() for k in range(spec.TEX_PAGES)), \
        "some slot was never filled"
    seen = {}
    for k in range(spec.TEX_PAGES):
        key = tex[k].tobytes()
        assert key not in seen, f"slot {k} holds the same bytes as {seen[key]}"
        seen[key] = k


def test_a_page_that_is_not_there_draws_as_page_zero():
    """The same object, twice, differing only in its selector."""
    m = _loaded()
    base = list(m.vm.dmem)
    b = spec.OL_BASE + 1                       # object 0's record
    base[spec.OL_BASE] = 1                     # ...and it alone
    keep = base[b + 5] & ~(spec.OBJ_PAGE_MASK << spec.OBJ_PAGE_SHIFT)

    def shot(sel):
        d = list(base)
        d[b + 5] = keep | (sel << spec.OBJ_PAGE_SHIFT)
        return np.asarray(gpu.render(d, m._cram, m._tex))

    zero = shot(0)
    assert (zero != np.asarray(gpu.render(
        [*base[:b + 5], keep | (7 << spec.OBJ_PAGE_SHIFT), *base[b + 6:]],
        m._cram, m._tex))).any(), (
        "page 7 draws the same as page 0, so this test cannot tell "
        "which page was sampled")
    for sel in range(spec.TEX_PAGES, spec.OBJ_PAGE_MASK + 1):
        assert np.array_equal(shot(sel), zero), (
            f"selector {sel} does not draw as page 0")
