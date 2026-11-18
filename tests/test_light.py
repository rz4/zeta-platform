"""test_light.py -- spec.OBJ_LIT against arithmetic and against a no-op.

The suite's `shaded` claim proves the panel carries many shades and that
they move when nothing else does. That is the behaviour. These are the
two things behaviour cannot show:

  THE LEVELS ARE RIGHT AT THE ENDS. Facing the light is full, facing
  away is ambient exactly, and side-on is ambient exactly -- because
  max(0, N.L) has to clip at zero rather than fold. And 128, which a
  cart WILL write because it reads like "one unit", is not
  representable in a signed byte and must fail to AMBIENT rather than
  to full brightness. The first draft of the spec said to write 128.

  AND FULL AMBIENT IS AN EXACT NO-OP. LIGHT_AMB at 32 with LIGHT_DIF at
  0 puts every vertex at LIGHT_FULL, and (ch * 32) >> 5 is ch. So a lit
  mesh must then render PIXEL-IDENTICAL to the same mesh with no
  normals at all. That is the strongest statement available about the
  whole path -- layout, clipper, gradients and fill -- because it does
  not depend on any of them being any particular way, only on their
  being the SAME way.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import cabinet, gpu, spec

CART = Path(__file__).resolve().parents[1] / "carts" / "shaded.zol"


def _dm():
    d = [0] * spec.DMEM_WORDS
    d[spec.LIGHT_DIR] = (0 << 16) | (0 << 8) | (127 & 0xFF)   # from +z
    d[spec.LIGHT_AMB] = 6
    d[spec.LIGHT_DIF] = 26
    return d


def _n(x, y, z):
    return ((x & 0xFF) << 16) | ((y & 0xFF) << 8) | (z & 0xFF)


def test_the_ends_of_the_level():
    d = _dm()
    # 31 AND NOT 32, exactly, and the reason is the whole of the
    # 127-versus-128 story: the shift is by 14, which is 128*128, and a
    # unit is 127, so a surface facing straight at the light reaches
    # 127*127/16,384 = 0.984 of the gain. 26 * 16,129 >> 14 is 25, plus
    # 6 of ambient. A cart wanting hard saturation sets amb + dif above
    # LIGHT_FULL and lets the clamp do it -- which is what shaded.zol
    # does. Asserted exactly rather than as "31 or 32", because a range
    # here would accept the scale being wrong by a whole unit.
    assert spec.light_of(_n(0, 0, 127), d) == 31
    assert spec.light_of(_n(0, 0, -127), d) == 6, "facing away is ambient"
    assert spec.light_of(_n(127, 0, 0), d) == 6, "side on is ambient"
    assert spec.light_of(_n(0, -127, 0), d) == 6


def test_a_component_of_128_fails_to_ambient():
    """128 reads like one unit and is -128 in a signed byte. It must go
    DARK, not bright: the first draft of the spec said to write it, and
    a surface facing the light came back facing away."""
    d = _dm()
    assert spec.light_of(_n(0, 0, 128), d) == 6


def test_a_short_vector_is_a_dimmer_and_not_a_bug():
    d = _dm()
    full = spec.light_of(_n(0, 0, 127), d)
    half = spec.light_of(_n(0, 0, 63), d)
    assert 6 < half < full


def test_the_level_never_leaves_its_range():
    d = _dm()
    d[spec.LIGHT_AMB] = 32
    d[spec.LIGHT_DIF] = 32
    for x in (-127, -64, 0, 64, 127):
        for z in (-127, 0, 127):
            lv = spec.light_of(_n(x, 0, z), d)
            assert 0 <= lv <= spec.LIGHT_FULL


def test_full_ambient_is_an_exact_no_op():
    """The whole path, checked without saying what any of it should do."""
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    m.frame(0)
    base = list(m.vm.dmem)
    base[spec.LIGHT_AMB] = spec.LIGHT_FULL
    base[spec.LIGHT_DIF] = 0
    lit_b = spec.OL_BASE + 1                       # object 0 is lit
    flat_b = spec.OL_BASE + 1 + spec.OL_STRIDE     # object 1 is not
    assert base[lit_b + 5] & spec.OBJ_LIT
    assert not base[flat_b + 5] & spec.OBJ_LIT

    def only(which):
        d = list(base)
        d[spec.OL_BASE] = 1
        src = lit_b if which == "lit" else flat_b
        for j in range(spec.OL_STRIDE):            # move it to slot 0
            d[lit_b + j] = base[src + j]
        d[lit_b + 1] = 0                           # ...at the same place
        d[lit_b + 3] = 5 * 65536
        return np.asarray(gpu.render(d, m._cram, m._tex))

    a, b = only("lit"), only("flat")
    moved = int((a != b).any(axis=2).sum())
    assert moved == 0, (
        f"{moved} pixels differ between a lit mesh at full ambient and "
        f"the same mesh unlit -- (ch * 32) >> 5 is ch, so they must be "
        f"the same picture")
    assert (a != a[0, 0]).any(), "the test rendered nothing at all"
