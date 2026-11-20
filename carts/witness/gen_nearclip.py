#!/usr/bin/env python3
"""gen_nearclip.py -- writes carts/witness/nearclip.zol: the hole under your feet.

THE OLDEST PLAYER-VISIBLE DEFECT ON THIS MACHINE, made reproducible.

A face with any vertex the rasteriser cannot address was dropped WHOLE.
Stand on a floor and the tile you are standing on has its near edge
BEHIND your eye, so it is dropped, so the ground vanishes and the
backdrop shows through -- a hole exactly one tile wide that follows you
around. The player reported it as "tiles disappear under the camera".

fabric.zol contains it by raising the eye to 5 units, which puts the hole
outside the frustum at every reachable pitch. Containment is not a fix,
and it is also why no cart in the suite could witness the clipper: at the
settings everything ships with, there is nothing to recover ON SCREEN.
cube.zol's 208 clipped triangles all land between x = -2048 and -608,
which is real geometry, correctly recovered, and invisible.

So this cart stands the camera ON the floor and looks down at it. A
checkerboard of 2-unit tiles at eye level minus 0.6, sweeping through a
full turn so every angle is exercised. Without the clipper the tile
underfoot is missing and you can see the clear colour through it. With
it, the floor is a floor.

The tiles are the b/w checker of the opus, with one green tile and one
red one placed off-centre -- so a yaw-sign or winding error cannot hide
behind symmetry, which is the mistake gen_hall.py's docstring already
records paying for once.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import carts as _carts                         # noqa: E402
_carts.on_path()                 # sibling generators, wherever they live

from zeta import spec                                    # noqa: E402
from zeta.forge import Cart, Mesh, Table, sine_table     # noqa: E402

ONE = 1 << 16
N = 8                       # tiles per side
STEP = 2.0                  # tile size, world units
FLOOR_Y = -0.6              # the camera stands this far above it
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
            if (i, j) == (2, 5):
                col = GREEN
            elif (i, j) == (5, 2):
                col = RED
            # both windings are drawn (no OBJ_CULL): a floor is only ever
            # seen from one side, and leaving the cull off keeps this
            # cart about CLIPPING and nothing else
            faces += [(a, c, b, col), (b, c, d, col)]
    return Mesh(verts, faces)


def main():
    cart = Cart("nearclip")
    mesh = cart.data(floor_mesh(), "floor")
    sin = cart.data(sine_table(), "sin")
    n = cart.var("n")

    cart.boot(spec.CAM_X, 0)
    cart.boot(spec.CAM_Y, 0)
    cart.boot(spec.CAM_Z, 0)

    p = cart.program()
    # a slow full turn: 1024 units is one revolution, so 2 per frame is
    # about 8.5 seconds a lap and every yaw is visited
    p.load(spec.REG_FRAME).emit("shl 1").push(1023).emit("and")
    p.store(spec.CAM_YAW)
    p.set(spec.CAM_PITCH, 64)             # POSITIVE pitch looks DOWN: the
                                          # first version had the sign
                                          # backwards and rendered nothing
    p.set(n, 0)
    p.object(n, int(mesh), 0, 0, 0, 0, 0)
    p.load(n).store(spec.OL_BASE)
    p.emit("halt")

    cart.write(HERE / "nearclip.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
