#!/usr/bin/env python3
"""gen_bigclip.py -- writes carts/bigclip.zol: the clipper at the top of its range.

nearclip.zol stands on a floor of 2-unit tiles: every crossing it makes
interpolates coordinate differences of a few units and plane distances
to match. The clipper's arithmetic is sized for the RANGE -- a 33-bit
difference times a 50-bit distance, an 82-bit product, a 51-bit divisor
-- and nothing in the suite reached the top of it. Frontier B3 rebuilt
that arithmetic (four partial products, a radix-4 divide), and its
mutants said so: dropping the high partial products, or narrowing 3*den
by a bit, passed every cart.

So this floor is the same checker with tiles THOUSANDS of units wide.
Adjacent vertices differ by more than 2^27 in view space, so the
multiplier's high six bits are live; the tiles cross the near plane and
all four side planes at once, so the distances and divisors run to the
top of their widths. It turns and nods so the crossings sweep.

A cart that witnesses a width is worth more than a comment about one.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import spec                                    # noqa: E402
from zeta.forge import Cart, Mesh, sine_table            # noqa: E402

ONE = 1 << 16
N = 4                                   # tiles per side
STEP = 6000.0                           # tile size, world units
FLOOR_Y = -300.0
LIGHT, DARK = 0xD8D8D8, 0x202020
GREEN, RED = 0x20C040, 0xD02020


def floor_mesh():
    verts = []
    for i in range(N + 1):
        for j in range(N + 1):
            verts += [int((i - N / 2) * STEP * ONE),
                      int(FLOOR_Y * ONE),
                      int((j - N / 2) * STEP * ONE)]
    faces = []
    for i in range(N):
        for j in range(N):
            a = i * (N + 1) + j
            b = a + 1
            c = a + (N + 1)
            d = c + 1
            col = LIGHT if (i + j) % 2 == 0 else DARK
            if (i, j) == (1, 2):
                col = GREEN
            elif (i, j) == (2, 1):
                col = RED
            faces += [(a, c, b, col), (b, c, d, col)]
    return Mesh(verts, faces)


def main():
    cart = Cart("bigclip")
    mesh = cart.data(floor_mesh(), "floor")
    cart.data(sine_table(), "sin")
    n = cart.var("n")

    cart.boot(spec.CAM_X, int(0.37 * STEP * ONE))   # off every symmetry
    cart.boot(spec.CAM_Y, 0)
    cart.boot(spec.CAM_Z, int(-0.21 * STEP * ONE))

    p = cart.program()
    p.load(spec.REG_FRAME).emit("shl 3").push(1023).emit("and")
    p.store(spec.CAM_YAW)                 # a turn every 128 frames
    p.load(spec.REG_FRAME).emit("shl 1").push(127).emit("and")
    p.store(spec.CAM_PITCH)               # ...nodding down as it goes
    p.set(n, 0)
    p.object(n, int(mesh), 0, 0, 0, 0, 0)
    p.load(n).store(spec.OL_BASE)
    p.emit("halt")

    cart.write(HERE / "bigclip.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
