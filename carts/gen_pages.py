#!/usr/bin/env python3
"""gen_pages.py -- writes carts/pages.zol: four textures at once.

One resident 32x32 page was this machine's most generation-typical
limit. N64 fought a 4 KB texture cache and its games look muddy for
exactly that reason; Zeta's 3.84 KB was the same constraint, and it
meant every textured object in a frame shared ONE image. A world could
be brick, or it could be wood, but not both.

The tile returned ~118 M10K blocks, so eight pages are now resident for
about 24 of them. Two cells were legislated for it:

    TEX_PAGE     which SLOT the load at TEX_SRC fills (0..7)
    flags 10:8   which slot an OBJECT samples

Both default to zero, so every cart written before pages existed loads
slot 0 and samples page 0 and is untouched.

THE LOADER STILL MOVES ONE PAGE A FRAME -- 680 words, the same path as
before -- so this cart spends its first four frames filling slots and
then never loads again. That is the intended shape: pages are furniture,
not per-frame traffic. A cart with more textures than slots pages them
the same way it pages meshes, through the mover.

Four cubes, four materials, one frame: brick, timber, verdigris copper,
and a checker. Nothing here is filtered -- point sampling with mips
keeps PS1's sharpness and adds N64's stability, which is the better half
of each, and is a CHOICE rather than a limit.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import spec                                    # noqa: E402
from zeta.forge import ONE, Cart, Mesh, Table, TexturePage  # noqa: E402


def rgb555(r, g, b):
    return ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)


def brick():
    RUB, NIG, CIT = rgb555(0xC4, 0x20, 0x20), rgb555(8, 8, 8), \
        rgb555(0xE6, 0xC0, 0x10)
    px = [[RUB] * 32 for _ in range(32)]
    for y in range(32):
        for x in range(32):
            course = y // 8
            if y % 8 >= 6 or (x + (course % 2) * 8) % 16 >= 14:
                px[y][x] = NIG
        if y % 8 == 3:
            px[y][(y * 5) % 32] = CIT
    return px


def timber():
    """Vertical grain, warm, with knots."""
    px = [[0] * 32 for _ in range(32)]
    for y in range(32):
        for x in range(32):
            g = (x * 7 + (y // 3) * 3) % 16
            v = 0x60 + g * 5
            px[y][x] = rgb555(v, int(v * 0.62), int(v * 0.33))
        if y % 11 == 5:
            px[y][(y * 3) % 32] = rgb555(0x38, 0x20, 0x10)
    return px


def copper():
    """Verdigris: green oxide over metal, blotchy."""
    px = [[0] * 32 for _ in range(32)]
    for y in range(32):
        for x in range(32):
            n = ((x * 13 + y * 7) ^ (x * 3 - y * 5)) & 31
            if n < 12:
                px[y][x] = rgb555(0x2E, 0x8B, 0x74)      # oxide
            elif n < 20:
                px[y][x] = rgb555(0x46, 0xA8, 0x8C)
            else:
                px[y][x] = rgb555(0xB0, 0x73, 0x3A)      # bare metal
    return px


def checker():
    A, B = rgb555(0xF0, 0xF0, 0xF0), rgb555(0x18, 0x18, 0x18)
    return [[A if ((x // 4) + (y // 4)) % 2 else B for x in range(32)]
            for y in range(32)]


PAGES = [("brick", brick), ("timber", timber),
         ("copper", copper), ("checker", checker)]


def uv_cube():
    """24 vertices, four per face, so every face owns its uv corners."""
    verts, uvs = [], []
    faces = []
    dirs = [((1, 0, 0), (0, 1, 0), (0, 0, 1)), ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
            ((0, 1, 0), (0, 0, 1), (1, 0, 0)), ((0, -1, 0), (0, 0, -1), (1, 0, 0)),
            ((0, 0, 1), (0, 1, 0), (-1, 0, 0)), ((0, 0, -1), (0, 1, 0), (1, 0, 0))]
    for n, u, v in dirs:
        base = len(verts) // 3
        for su, sv in ((0, 0), (1, 0), (1, 1), (0, 1)):
            pu, pv = (su * 2 - 1), (sv * 2 - 1)
            verts += [int((n[k] + u[k] * pu + v[k] * pv) * ONE)
                      for k in range(3)]
            uvs.append((su * 31) | ((sv * 31) << 8))
        faces += [(base, base + 1, base + 2, 0),
                  (base, base + 2, base + 3, 0)]
    return Mesh(verts, faces, uvs=uvs)


def main():
    cart = Cart("pages")
    imgs = [cart.data(TexturePage(fn()), name) for name, fn in PAGES]
    mesh = cart.data(uv_cube(), "cube")

    yaw = cart.var("yaw")
    pit = cart.var("pitch")
    nobj = cart.var("n")
    boot = cart.var("boot")

    p = cart.program()
    p.addi(yaw, 5).load(yaw).push(1023).emit("and").store(yaw)
    p.addi(pit, 3).load(pit).push(1023).emit("and").store(pit)

    # ---- fill one slot a frame for the first four frames --------------
    # After that TEX_PAGE and TEX_SRC are left alone and the pages just
    # stay there. Loading is startup work, not per-frame traffic.
    for k, (name, _) in enumerate(PAGES):
        skip = p.label("load")
        p.load(boot).push(k).emit("eq", f"jz {skip}")
        p.set(spec.TEX_PAGE, k)
        p.set(spec.TEX_SRC, int(imgs[k]))
        p.mark(skip)
    done = p.label("loaded")
    p.load(boot).push(len(PAGES)).emit("lt", f"jz {done}")
    p.addi(boot, 1)
    p.mark(done)
    # once loaded, stop asking: TEX_SRC 0 means "no load this frame"
    after = p.label("after")
    p.load(boot).push(len(PAGES)).emit("lt", f"jz {after}").emit(f"jmp {after}")
    p.mark(after)

    # ---- four cubes, one per page, all in the same frame ---------------
    p.set(nobj, 0)
    for k in range(len(PAGES)):
        x = (k - 1.5) * 2.6
        p.object(nobj, int(mesh),
                 int(x * ONE), 0, int(7.5 * ONE),
                 [f"load {int(pit)}", "shl 10", f"load {int(yaw)}", "or"],
                 uv_cube().flags | (k << spec.OBJ_PAGE_SHIFT))
    p.load(nobj).store(spec.OL_BASE)
    p.emit("halt")

    cart.boot(spec.CAM_Z, 0)
    cart.write(HERE / "pages.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
