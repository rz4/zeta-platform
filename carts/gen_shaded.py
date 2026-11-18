#!/usr/bin/env python3
"""gen_shaded.py -- writes carts/shaded.zol: spec.OBJ_LIT's witness.

THE LAST THING IN THE PICTURE THAT READS AS A DECADE. Two identical
spheres, same geometry, same colour, same light. The left one carries a
NORMAL at each vertex and is lit; the right one carries nothing and is
its face colour everywhere. That is the whole of it, and the difference
is the difference between 1997 and everything after.

The light turns while the spheres stand still, so the terminator sweeps
around the lit one and the flat one does not move at all. Nothing in
the cart recolours anything: it writes ONE DMEM word a frame,
spec.LIGHT_DIR, and the machine relights every vertex of every lit mesh
from it. That is what makes this cheaper than the era's answer, which
was to bake the light into the vertex colours and be unable to move it.

WHY BOTH SPHERES ARE SEPARATE MESHES rather than one mesh drawn twice
with the flag off. The per-vertex word is only PRESENT in the layout
when a flag says so, so a mesh with normals read without OBJ_LIT would
find its faces at the wrong offset. The flat copy is the same geometry
written without the normals, which is also what an unlit mesh really
costs: 128 words less.

Run me after changing anything: python3 carts/gen_shaded.py
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import spec                                 # noqa: E402
from zeta.forge import ONE, Cart, Mesh                # noqa: E402

RINGS, SEGS = 10, 14
BASE = 0xC83030                    # the face colour both spheres wear
# AMB 5 left the far side at a sixteenth and the lit ball read as a hole
# in the panel for half of every turn. 9 keeps the shape visible while
# still being unmistakably the dark side; AMB + DIF over LIGHT_FULL on
# purpose, so the lit face saturates and the clamp does the rest.
AMB, DIF = 9, 27


def sphere():
    """Latitude and longitude. Returns (verts, faces, normals) where a
    normal IS the vertex position scaled to 127 -- which is what makes a
    sphere the right shape to prove this on: its normals are exact, so
    anything that looks wrong is the lighting and not the mesh."""
    verts, norms = [], []
    for r in range(RINGS + 1):
        phi = math.pi * r / RINGS
        for sgi in range(SEGS):
            th = 2 * math.pi * sgi / SEGS
            nx = math.sin(phi) * math.sin(th)
            ny = math.cos(phi)
            nz = math.sin(phi) * math.cos(th)
            verts += [int(nx * ONE), int(ny * ONE), int(nz * ONE)]
            norms.append(pack(nx, ny, nz))
            if r in (0, RINGS):        # the poles are one point, once
                break
    faces = []

    def vid(r, sgi):
        if r == 0:
            return 0
        if r == RINGS:
            return 1 + (RINGS - 1) * SEGS
        return 1 + (r - 1) * SEGS + (sgi % SEGS)

    for r in range(RINGS):
        for sgi in range(SEGS):
            a, b = vid(r, sgi), vid(r, sgi + 1)
            c, d = vid(r + 1, sgi), vid(r + 1, sgi + 1)
            if r == 0:
                faces.append((a, d, c, BASE))
            elif r == RINGS - 1:
                faces.append((a, b, c, BASE))
            else:
                faces += [(a, b, c, BASE), (b, d, c, BASE)]
    return verts, faces, norms


def pack(x, y, z):
    """A unit vector as 8:8:8 signed, 127 to the unit. NOT 128 -- a
    signed byte cannot hold it, and 128 reads back as -128, which turns
    a surface facing the light into one facing away."""
    def b(v):
        return max(-127, min(127, int(round(v * 127)))) & 0xFF
    return (b(x) << 16) | (b(y) << 8) | b(z)


def main():
    cart = Cart("shaded")
    verts, faces, norms = sphere()
    assert len(verts) // 3 <= spec.MESH_NV_MAX, len(verts) // 3
    assert len(faces) <= spec.MESH_NF_MAX, len(faces)
    ball = cart.data(Mesh(verts, faces, colors=norms), "ball")
    flat = cart.data(Mesh(verts, faces), "flat")

    ang = cart.var("ang")
    sin = cart.data(spec_sin(), "sin")

    p = cart.program()
    p.addi(ang, 6).load(ang).push(1023).emit("and").store(ang)

    # ---- the light turns, and that is the ONLY thing the cart writes --
    # sin[a] and sin[a+256] are the two components; 127 to the unit, so
    # the table is written scaled and no run-time multiply is needed.
    p.load(ang).push(int(sin)).emit("add", "loadi").emit("shl 16")
    p.load(ang).push(256).emit("add").push(1023).emit("and")
    p.push(int(sin)).emit("add", "loadi", "or").store(spec.LIGHT_DIR)
    p.set(spec.LIGHT_AMB, AMB)
    p.set(spec.LIGHT_DIF, DIF)

    n = cart.var("n")
    p.set(n, 0)
    lit = (Mesh(verts, faces, colors=norms).flags
           & ~spec.OBJ_GOURAUD) | spec.OBJ_LIT
    p.object(n, int(ball), int(-1.35 * ONE), 0, int(5.0 * ONE), ["push 0"], lit)
    p.object(n, int(flat), int(1.35 * ONE), 0, int(5.0 * ONE), ["push 0"],
             Mesh(verts, faces).flags)
    p.load(n).store(spec.OL_BASE)
    p.emit("halt")

    cart.boot(spec.CAM_Z, 0)
    cart.write(HERE / "shaded.zol")
    print(cart.report())


def spec_sin():
    """1024 entries of sin, scaled to 127 and packed as a signed byte in
    the low 8 bits, so the program can OR two of them into LIGHT_DIR."""
    from zeta.forge import Table
    return Table([max(-127, min(127, int(round(
        math.sin(2 * math.pi * i / 1024) * 127)))) & 0xFF
        for i in range(1024)])


if __name__ == "__main__":
    main()
