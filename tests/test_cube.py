"""The GEOM contract, pinned through the cube cart: projection, painter's
order, backface culling, and the cart-visible driving model."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import asm, gpu, spec, vm

CART = Path(__file__).parents[1] / "carts/cube.zol"

# THE ALCHEMICAL PALETTE (boot 61), which is what gen_cube.py emits.
# These constants used to be an older set -- 0xEE5544 and friends --
# because carts/cube.zol on disk had never been regenerated after the
# palette amendment, and the tests were written against the STALE CART
# rather than its generator. Nothing regenerates carts as a gate, so the
# drift was invisible until an unrelated change forced a rebuild.
CHECK_A, CHECK_B = 0xFFFFFF, 0x000000        # albedo / nigredo
FRONT, SIDE, TOP, UNDER = 0xC42020, 0x9A1818, 0xE84040, 0x501010


def lit(fb, rgb):
    return int((fb == spec.display_rgb(rgb)).all(axis=2).sum())


def test_cube_on_checkered_ground():
    m = vm.VM(asm.assemble(CART))
    for _ in range(45):
        m.frame(0)
    fb = gpu.render(m.vm.dmem if hasattr(m, "vm") else m.dmem)
    assert lit(fb, CHECK_A) > 5000 and lit(fb, CHECK_B) > 5000    # checker
    faces = [FRONT, SIDE, TOP]
    assert sum(lit(fb, c) for c in faces) > 800          # a side is showing
    assert lit(fb, UNDER) == 0                            # never its underside


def test_spin_and_culling():
    m = vm.VM(asm.assemble(CART))
    m.frame(0)                                           # yaw = 6: near-front
    fb = gpu.render(m.dmem)
    assert lit(fb, FRONT) > 400                           # front face
    assert lit(fb, UNDER) == 0                            # underside culled
    frames = []
    for _ in range(30):
        m.frame(0)
    frames.append(gpu.render(m.dmem))
    for _ in range(30):
        m.frame(0)
    frames.append(gpu.render(m.dmem))
    assert not np.array_equal(*frames)                   # it actually spins


def test_driving():
    m = vm.VM(asm.assemble(CART))
    for _ in range(30):
        m.frame(spec.PAD_RIGHT)
    assert spec.s32(m.dmem[16]) == 30 * 3277             # x drove right
    for _ in range(10):
        m.frame(spec.PAD_UP)
    assert spec.s32(m.dmem[17]) == 131072 + 10 * 3277    # z drove away
