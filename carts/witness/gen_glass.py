#!/usr/bin/env python3
"""gen_glass.py -- writes carts/witness/glass.zol: per-pixel blending, at last.

The one axis where this machine sat BEHIND a 1994 console. PS1, Saturn
and N64 all composite per primitive; Zeta could dim four rectangles at
scanout (13b) and nothing else, because the framebuffer lives in CRAM
behind a write path and the paint side could never read it back.

The tile changed that. A BAND of colour is small enough to hold on die
-- 322x32x15 bits, about fifteen of the hundred and eighteen M10K blocks
the shrink returned -- so the destination pixel is one read away and the
blend is an ordinary triangle flag.

    OBJ_BLEND       the object composites instead of overwriting
    alpha           sixteenths, in bits 28:24 of the FACE's colour word
                    (0 = invisible, 16 = opaque)

THE CART OWES TWO THINGS, both era-normal and both stated in spec.py's
blend-order law: submit every opaque object BEFORE any blended one, and
submit blended geometry BACK TO FRONT. A blended face writes no depth --
that is what makes its composite order exactly the order you chose --
so it cannot defend itself against an opaque face submitted later, and
two blended faces cannot resolve each other by depth.

What this draws: an opaque lit cube, and in front of it four upright
panes at alpha 4, 8, 12 and 16 -- a quarter, a half, three quarters,
solid -- sliding across it. The cube reads through each in proportion,
and where two panes overlap the nearer one composites over the farther,
which is the whole point and is only correct because they are submitted
far to near.
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
from zeta.forge import ONE, Cart, Mesh, sine_table       # noqa: E402

PANES = [(-1.4, 0x30E0FF, 4), (-0.5, 0xFF6030, 8),
         (0.4, 0x40FF80, 12), (1.3, 0xFFE040, 16)]


def cube():
    """The opaque thing worth seeing through."""
    xs = ys = zs = (-ONE, ONE)
    verts = []
    for x, y, z in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]:
        verts += [xs[x], ys[y], zs[z]]
    quads = [((0, 1, 2, 3), 0x40C070), ((5, 4, 7, 6), 0x2A7A48),
             ((4, 0, 3, 7), 0x9AC020), ((1, 5, 6, 2), 0xC8A038),
             ((3, 2, 6, 7), 0xE8E8D0), ((4, 5, 1, 0), 0x203040)]
    faces = []
    for (a, b, c, d), col in quads:
        faces += [(a, c, b, col), (a, d, c, col)]
    return Mesh(verts, faces)


def pane(rgb, alpha):
    """An upright quad whose faces carry their alpha in bits 28:24.

    The colour word is 32 bits and only 24 of them were ever the colour,
    so this costs nothing and every mesh already written keeps its
    meaning -- alpha 0 there, which is why OBJ_BLEND has to be opt-in:
    a blended object that forgets its alpha is INVISIBLE, not opaque."""
    w, h = 0.55, 1.6
    verts = []
    for x, y in ((0, 0), (1, 0), (1, 1), (0, 1)):
        verts += [int((x - 0.5) * w * 2 * ONE), int((y - 0.5) * h * ONE), 0]
    col = (rgb & 0xFFFFFF) | ((alpha & spec.BLEND_A_MASK)
                              << spec.BLEND_A_SHIFT)
    # both windings, so the pane is visible from either side without
    # OBJ_CULL having an opinion about it
    return Mesh(verts, [(0, 1, 2, col), (0, 2, 3, col),
                        (0, 2, 1, col), (0, 3, 2, col)])


def main():
    cart = Cart("glass")
    body = cart.data(cube(), "cube")
    metal = [cart.data(pane(rgb, a), f"pane{k}")
             for k, (_, rgb, a) in enumerate(PANES)]
    sin = cart.data(sine_table(), "sin")

    yaw = cart.var("yaw")
    pit = cart.var("pitch")
    ph = cart.var("phase")
    nobj = cart.var("n")
    sway = cart.var("sway")

    p = cart.program()
    p.addi(yaw, 6).load(yaw).push(1023).emit("and").store(yaw)
    p.addi(pit, 3).load(pit).push(1023).emit("and").store(pit)
    p.addi(ph, 4).load(ph).push(1023).emit("and").store(ph)
    # sway = sin(phase) * 1.6 world units, the panes' slide across the cube
    p.load(ph).emit("shr 3").push(127).emit("and")
    p.push(int(sin)).emit("add", "loadi")
    p.push(int(1.6 * ONE)).emit("mulq").store(sway)

    p.set(nobj, 0)
    # OPAQUE FIRST. Not a style note -- a blended face writes no depth,
    # so anything opaque submitted after one simply overwrites it.
    p.object(nobj, int(body), 0, 0, 7 * ONE,
             [f"load {int(pit)}", "shl 10", f"load {int(yaw)}", "or"],
             cube().flags)
    # then the panes, FAR TO NEAR: two blended faces cannot resolve each
    # other by depth, so the order they are handed over is the order they
    # composite in, and that is the whole contract.
    for k, (x, rgb, a) in enumerate(PANES):
        p.object(nobj, int(metal[k]),
                 [f"push {int(x * ONE)}", f"load {int(sway)}", "add"],
                 0, int((5.2 + 0.35 * (len(PANES) - 1 - k)) * ONE),
                 0, pane(rgb, a).flags | spec.OBJ_BLEND)
    p.load(nobj).store(spec.OL_BASE)
    p.emit("halt")

    cart.boot(spec.CAM_Z, 0)
    cart.write(HERE / "glass.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
