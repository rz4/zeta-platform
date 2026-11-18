"""test_compositor.py -- transparency without a framebuffer read.

Blending needs the destination pixel, and this machine's framebuffer is
in external CRAM behind a WRITE path: the paint side cannot read it
back. At SCANOUT it can, because the finished picture is already
streaming past a pixel per clock with its coordinates in hand. So the
blend happens there and never touches CRAM.

That position is why the two gates disagree ON PURPOSE, and the
disagreement was settled before a line was written: cross compares
painted FRAMEBUFFERS and is correctly blind to all of this; glass
compares the SCANNED STREAM and sees it. These tests pin the law; glass
on carts/fade.zol pins the silicon against it (and fails when the
silicon's alpha is mutated by one shift).
"""
import numpy as np
import pytest

from zeta import gpu, spec


def dmem(entries):
    d = [0] * spec.DMEM_WORDS
    d[spec.CO_BASE] = len(entries)
    for k, (x0, y0, x1, y1, rgb, a) in enumerate(entries):
        b = spec.CO_BASE + 1 + k * spec.CO_STRIDE
        d[b] = (x0 & 0x3FF) | ((x1 & 0x3FF) << 10)
        d[b + 1] = (y0 & 0x3FF) | ((y1 & 0x3FF) << 10)
        d[b + 2] = (rgb & 0xFFFFFF) | ((a & 0x1F) << 24)
    return d


def flat(c5=25):
    """A field of a REPRESENTABLE pixel. The framebuffer stores five bits
    and render() writes them back as (c5 << 3) | (c5 >> 2), so 200 is not
    a colour this machine can hold -- 200 >> 3 is 25 and 25 expands to
    206. Testing against an unrepresentable value measures the fixture,
    not the compositor."""
    v = (c5 << 3) | (c5 >> 2)
    return np.full((spec.H, spec.W, 3), v, np.uint8)


PX = (25 << 3) | (25 >> 2)          # == 206


def test_alpha_zero_changes_nothing():
    fb = flat()
    out = gpu.compose(fb, dmem([(0, 0, spec.W - 1, spec.H - 1, 0, 0)]))
    assert np.array_equal(out, fb)


def test_alpha_sixteen_is_exactly_opaque():
    """16 must land ON the colour, not one short of it -- which is why
    the blend is (p<<4) + a*(c-p) and not p*(16-a) + c*a computed with a
    truncating multiply."""
    out = gpu.compose(flat(), dmem([(0, 0, 9, 9, 0xFFFFFF, 16)]))
    assert tuple(out[5, 5]) == (255, 255, 255)
    out = gpu.compose(flat(), dmem([(0, 0, 9, 9, 0x000000, 16)]))
    assert tuple(out[5, 5]) == (0, 0, 0)


@pytest.mark.parametrize("a", range(17))
def test_the_ramp_is_monotonic_and_matches_the_arithmetic(a):
    """Every step of the sixteenths, against the law's own formula in
    five-bit space -- the space the framebuffer actually stores."""
    fb = flat()
    out = gpu.compose(fb, dmem([(0, 0, 9, 9, 0x000000, a)]))
    want5 = (25 * (16 - a) + 0 * a) >> 4
    want = (want5 << 3) | (want5 >> 2)
    assert out[5, 5, 0] == want


def test_only_the_rectangle_is_touched():
    out = gpu.compose(flat(), dmem([(10, 20, 29, 39, 0, 16)]))
    assert tuple(out[20, 10]) == (0, 0, 0)        # inclusive corners
    assert tuple(out[39, 29]) == (0, 0, 0)
    assert tuple(out[19, 10]) == (PX, PX, PX)  # one row above
    assert tuple(out[20, 30]) == (PX, PX, PX)  # one column right


def test_the_last_live_rectangle_wins():
    """Legislated: rectangles do NOT blend with each other. That is what
    lets the silicon be a priority mux and one lerp instead of a chain,
    which is what meets timing at the pixel clock."""
    out = gpu.compose(flat(), dmem([(0, 0, 99, 99, 0xFF0000, 16),
                                    (0, 0, 99, 99, 0x00FF00, 16)]))
    assert tuple(out[50, 50]) == (0, 255, 0), "the first entry won"


def test_a_count_of_zero_disables_the_whole_block():
    d = dmem([(0, 0, spec.W - 1, spec.H - 1, 0, 16)])
    d[spec.CO_BASE] = 0
    assert np.array_equal(gpu.compose(flat(), d), flat())


def test_a_count_past_the_cap_is_refused_whole():
    d = dmem([(0, 0, 9, 9, 0, 16)])
    d[spec.CO_BASE] = spec.CO_MAX + 1
    assert np.array_equal(gpu.compose(flat(), d), flat())


def test_an_inverted_rectangle_draws_nothing():
    out = gpu.compose(flat(), dmem([(50, 50, 10, 10, 0, 16)]))
    assert np.array_equal(out, flat())


def test_compose_does_not_mutate_its_input():
    fb = flat()
    gpu.compose(fb, dmem([(0, 0, spec.W - 1, spec.H - 1, 0, 16)]))
    assert np.array_equal(fb, flat()), "compose wrote into the framebuffer"
