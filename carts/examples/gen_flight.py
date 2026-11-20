#!/usr/bin/env python3
"""gen_flight.py -- writes carts/examples/flight.zol: the first flight.

Build 90's demonstration of CAM_ROLL, and the FIRST CART BUILT ON THE
FORGE (zeta/forge.py, docs/SDK.md). Not one address is chosen here: the
terrain, the sine table and every scratch cell are placed by the linker,
which reads spec.py and cannot put a table inside a mesh. The previous
version of this file picked MESH_AT = 400 and SINTAB = 2000 by hand and
asserted the gap, which is how fabric.zol lost its floor.

The camera had yaw and pitch, which is enough to walk and look and not
enough to FLY: an aircraft turns by BANKING, and with no roll about the
view axis the horizon never tilts and every turn reads as a skid.

    the dpad LEFT/RIGHT rolls, and roll is the ONLY way to turn --
    heading advances in proportion to bank, as it does in the air.
    Let go and the wings level themselves.
    Y and B are the elevator; altitude follows the pitch.
    Airspeed is constant, because a throttle is a second lesson.

The ground is the fabric's machinery with a heightfield instead of a
plane: one mesh, instanced nine times, the block snapping to the
aircraft so there is no edge. The tile is 128 units because 128 units in
Q16.16 is exactly 2^23 and this machine has no divide -- the same reason
the fabric's cell is 32. The heights are sines whose periods DIVIDE the
tile, so the mesh joins itself exactly and the snap cannot be seen; the
view is shorter than the tile, so the repeat cannot be seen either.

Vertex colours are a baked lambert against a fixed sun, the normal taken
from the analytic slope of the same height function. That is all of
docs/FLIGHT.md's "RE direction" in miniature: light computed offline,
paid for once, free at 60 Hz.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import carts as _carts                         # noqa: E402
_carts.on_path()                 # sibling generators, wherever they live

from zeta import forge, spec                             # noqa: E402
from zeta.forge import ONE, Cart, Mesh                   # noqa: E402

N, TILE = 8, 16                    # 8x8 quads of 16 units = 128 across
SPAN = N * TILE
SNAP_SH = 23                       # 128 units in Q16.16 is exactly 2^23
assert (1 << SNAP_SH) == SPAN * ONE
HSCALE = 6.0
SPEED = 0.34
SUN = (0.40, 0.82, -0.40)

SPIRAL = [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1),
          (1, 1), (-1, 1), (-1, -1), (1, -1)]

# 3x3 of 128 is 384 across, half-extent 192; the snap is one whole tile
# so the aircraft drifts up to 64 off centre, and the screen's diagonal
# half-angle costs the cosine: (192 - 64) * cos(40) = 98 units of sight,
# guaranteed whatever the heading.
FOG_FULL = 98 * 512
FOG_SHIFT = 11
FOG_NEAR = FOG_FULL - 16 * (1 << FOG_SHIFT)


def height(u, v):
    """Periodic in 1.0 on both axes: the tile joins itself exactly."""
    return HSCALE * (
        0.62 * math.sin(2 * math.pi * u) * math.cos(2 * math.pi * v)
        + 0.26 * math.sin(4 * math.pi * u + 1.1)
        * math.cos(4 * math.pi * v + 0.4)
        + 0.12 * math.sin(6 * math.pi * v + 2.2)
        * math.cos(6 * math.pi * u))


def terrain() -> Mesh:
    verts, cols, faces = [], [], []
    n1 = N + 1
    sl = math.sqrt(sum(k * k for k in SUN))
    for j in range(n1):
        for i in range(n1):
            u, v = i / N, j / N
            y = height(u, v)
            verts += [int((i - N / 2) * TILE * ONE), int(y * ONE),
                      int((j - N / 2) * TILE * ONE)]
            e = 1e-4
            du = (height(u + e, v) - height(u - e, v)) / (2 * e)
            dv = (height(u, v + e) - height(u, v - e)) / (2 * e)
            nx, nz = -du / SPAN, -dv / SPAN
            ln = math.sqrt(nx * nx + 1 + nz * nz)
            d = max(0.0, (nx * SUN[0] + SUN[1] + nz * SUN[2]) / (ln * sl))
            lit = 0.30 + 0.82 * d
            hi = max(0.0, min(1.0, (y / HSCALE + 0.6) / 1.4))
            r, g, b = ((0.26 + 0.46 * hi) * lit, (0.46 + 0.24 * hi) * lit,
                       (0.22 + 0.46 * hi) * lit)
            cols.append((min(255, int(r * 255)) << 16)
                        | (min(255, int(g * 255)) << 8)
                        | min(255, int(b * 255)))
    for j in range(N):
        for i in range(N):
            a = j * n1 + i
            faces += [(a, a + n1 + 1, a + 1, 0),
                      (a, a + n1, a + n1 + 1, 0)]
    # colors= is what makes it Gouraud; the flag is never written by hand
    return Mesh(verts, faces, colors=cols)


def main():
    cart = Cart("flight")

    ground = cart.data(terrain(), "terrain")
    sines = cart.data(forge.sine_table(scale=SPEED), "sines")
    bank = cart.var("bank")
    elev = cart.var("elevator")
    nobj = cart.var("n_obj")
    sx, sz = cart.var("step_x"), cart.var("step_z")
    idx = cart.var("heading_idx")
    si, sj = cart.var("snap_i"), cart.var("snap_j")

    p = cart.program()
    PAD, PU, PD, PL, PR = 1, 1, 2, 4, 8

    # ---- the stick: roll is the only way to turn ------------------------
    p.if_pad(PL, lambda q: q.addi(bank, -3))
    p.if_pad(PR, lambda q: q.addi(bank, +3))
    # wings level themselves when the stick is centred
    p.if_no_pad(PL | PR, lambda q: q.toward_zero(bank, 2))
    p.clamp(bank, -170, 170)
    p.load(bank).push(1023).emit("and").store(spec.CAM_ROLL)

    # THE TURN. Heading advances with bank -- the whole difference between
    # an aircraft and a tank. Bank right lowers the yaw, because a rising
    # CAM_YAW swings the gaze LEFT (measured in build 89, not assumed).
    p.load(spec.CAM_YAW).load(bank).emit("shr 4", "sub",
                                         "push 1023", "and")
    p.store(spec.CAM_YAW)

    # ---- the elevator ----------------------------------------------------
    p.if_pad(spec.PAD_Y, lambda q: q.addi(elev, -3))
    p.if_pad(spec.PAD_B, lambda q: q.addi(elev, +3))
    p.clamp(elev, -140, 140)
    p.load(elev).push(1023).emit("and").store(spec.CAM_PITCH)

    # ---- fly --------------------------------------------------------------
    p.load(spec.CAM_YAW).emit("shr 3", "push 127", "and").store(idx)
    p.load(idx).push(int(sines)).emit("add", "loadi").store(sx)
    p.load(idx).push(32).emit("add", "push 127", "and")
    p.push(int(sines)).emit("add", "loadi").store(sz)
    p.load(spec.CAM_X).load(sx).emit("sub").store(spec.CAM_X)
    p.load(spec.CAM_Z).load(sz).emit("add").store(spec.CAM_Z)
    # pitch DOWN is positive, so it descends
    p.load(spec.CAM_Y).load(elev).push(150).emit("mul", "sub")
    p.store(spec.CAM_Y)
    p.clamp(spec.CAM_Y, 10 * ONE, 80 * ONE)

    # ---- the ground, snapped to the aircraft ------------------------------
    p.load(spec.CAM_X).push(1 << (SNAP_SH - 1)).emit("add",
                                                     f"shr {SNAP_SH}")
    p.store(si)
    p.load(spec.CAM_Z).push(1 << (SNAP_SH - 1)).emit("add",
                                                     f"shr {SNAP_SH}")
    p.store(sj)
    p.set(nobj, 0)
    for dx, dz in SPIRAL:
        p.object(nobj, int(ground),
                 [f"load {int(si)}", f"push {dx}", "add", f"shl {SNAP_SH}"],
                 0,
                 [f"load {int(sj)}", f"push {dz}", "add", f"shl {SNAP_SH}"],
                 0, terrain().flags)
    p.load(nobj).store(spec.OL_BASE)
    p.emit("halt")

    # ---- the boot state ---------------------------------------------------
    # written as .data through the same linker, so it cannot land on
    # content either
    for addr, value in ((spec.CAM_Y, 24 * ONE),
                        (spec.FOG_RGB, spec.CLEAR_RGB),
                        (spec.FOG_NEAR, FOG_NEAR),
                        (spec.FOG_SHIFT, FOG_SHIFT),
                        (spec.LOD_FLAT, 26000)):
        cart.boot(addr, value)
    cart.write(HERE / "flight.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
