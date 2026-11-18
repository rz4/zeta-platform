#!/usr/bin/env python3
"""gen_shade.py -- writes carts/shade.zol: the spare bit's witness.

A cube slides across the hall on its own, asks the room where its feet
are, and takes the room's light. When the plate says the sun is blocked
at that pixel the cube darkens; when it says lit, the cube is exact.

WHY IT MOVES ITSELF. `zeta cross` drives no pad, so a cart that needs
the player to walk would sit still for the whole run with the answer
frozen at zero -- a gate that cannot fail. The cube is driven by
REG_FRAME through the sine table instead, so every cross run crosses the
shadow boundary several times whether anyone is holding a button or not.

WHAT IS BEING PROVED. spec.BG_SHADOW: bit 15 of a plate word, read by
nothing in either machine until now, carrying the room's shadow mask;
and spec.PICK_SH, the pick register's third answer, latched during the
CLEAR because that is when the plate streams past. Together they end the
oldest tell of the pre-rendered era -- the character pasted onto the
photograph, because the room's light never touched it.

The depth is FIXED, which makes the projection a single constant:
sx = W/2 + x * (FOCAL/z) needs one mulq and one shift, and sy does not
move at all. The reciprocal table vessel.zol carries is only needed when
the actor's DEPTH changes too.

Run me after changing anything: python3 carts/gen_shade.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from zeta import bake, spec                      # noqa: E402
from zeta.forge import Cart, Mesh, sine_table    # noqa: E402

from gen_hall import EYE, ONE, scene             # noqa: E402

Z_AT = 11.0          # the row of the hall where the map alternates
X_SWING = 6.0        # ...lit at -6, shadowed from -4 to 0, lit past +2
LIT_TINT, DARK_TINT = 31, 10


def cube(s=0.42):
    """A plain box. Its own colours are mid-grey on every face, so what
    the eye sees is the ROOM's light and nothing else."""
    q, h = int(s * ONE), int(s * 2 * ONE)
    v = []
    for x, y, z in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]:
        v += [-q + 2 * q * x, h * y, -q + 2 * q * z]
    quads = [((0, 1, 2, 3), 0xB0B0B0), ((5, 4, 7, 6), 0x8C8C8C),
             ((4, 0, 3, 7), 0xA0A0A0), ((1, 5, 6, 2), 0xA0A0A0),
             ((3, 2, 6, 7), 0xC8C8C8), ((4, 5, 1, 0), 0x606060)]
    f = []
    for (a, b, c, d), col in quads:
        f += [(a, c, b, col), (a, d, c, col)]
    return Mesh(v, f)


def main():
    cart = Cart("shade")
    print("raytracing the hall (the same scene() hall.zol bakes)...")
    col, dep, lit = bake.render(scene(), eye=EYE, shadow_samples=14,
                                ao_samples=24)
    plate = cart.cram(bake.plate(col, dep, lit), "plate")
    boxm = cart.data(cube(), "box")
    sintab = cart.data(sine_table(), "sin")
    bx = cart.var("bx")
    nobj = cart.var("n")

    # FOCAL/z as Q16.16, and the feet's screen row, both fixed by Z_AT.
    k = int(spec.FOCAL * ONE / Z_AT)
    sy = spec.H // 2 + int(EYE[1] * spec.FOCAL / Z_AT)

    p = cart.program()
    # ---- the cube slides, driven by the frame counter alone -------------
    p.load(spec.REG_FRAME).emit("shr 1").push(127).emit("and")
    p.push(int(sintab)).emit("add", "loadi")
    p.push(int(X_SWING * ONE)).emit("mulq").store(bx)

    # ---- ask the room about the pixel under its feet ---------------------
    p.load(bx).push(k).emit("mulq", "shr 16")
    p.push(spec.W // 2).emit("add").store(spec.PICK_X)
    p.push(sy).store(spec.PICK_Y)

    # ---- and wear the answer (spec.PICK_SH -> OBJ_OTINT) -----------------
    # tint = LIT - answer*(LIT-DARK), the same in all three channels: a
    # shadow does not tint, it takes the sun away.
    p.set(nobj, 0)
    p.object(nobj, int(boxm), [f"load {int(bx)}"], 0, int(Z_AT * ONE), 0,
             [f"load {spec.PICK_SH}",
              f"push {LIT_TINT - DARK_TINT}", "mul",
              f"push {LIT_TINT}", "swap", "sub",
              "dup", "dup",
              "shl 27", "swap", "shl 22", "or",
              "swap", "shl 17", "or",
              f"push {spec.OBJ_CULL | spec.OBJ_OTINT}", "or"])
    p.load(nobj).store(spec.OL_BASE)
    p.set(spec.BG_SRC, int(plate))
    p.emit("halt")

    cart.write(Path(__file__).parent / "shade.zol")


if __name__ == "__main__":
    main()
