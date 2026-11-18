#!/usr/bin/env python3
"""gen_pagemax.py -- writes carts/pagemax.zol: EVERY page at once.

pages.zol proved that four textures can be resident together. It has
proved that ever since, unchanged, while TEX_PAGES went 8 -> 16 -> 24 --
so the eight pages added in build 105 and the eight added in 97 were
capacity nothing ever looked at. A limit that no cart reaches is a limit
nobody has tested.

This cart fills every slot the machine has and samples all of them in
one frame. Each page is a checker in its own hue, so a page landing in
the wrong slot does not merely look odd -- it looks like a DIFFERENT
CUBE, which is the only way a mix-up shows.

AND IT NAMES A PAGE THAT DOES NOT EXIST. TEX_PAGES is 24 and the
selector is five bits, so 24..31 are askable and absent. The law says
they read as page 0 (spec.tex_page) -- not as the nearest slot, because
clamping would show whatever the last page happened to hold and that is
a bug that moves when unrelated code does. The last cube asks for page
30 and must come back wearing page 0.

Run me after changing anything: python3 carts/gen_pagemax.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import spec                                    # noqa: E402
from zeta.forge import ONE, Cart, Table, TexturePage     # noqa: E402
from zeta.forge import Mesh                              # noqa: E402
from gen_pages import rgb555                             # noqa: E402

N = spec.TEX_PAGES
OUT_OF_RANGE = 30              # askable, absent, must read as page 0


def uv_quad():
    """One flat textured square. A CUBE WOULD DO, and it does not fit:
    twenty-five of them is 300 textured triangles and the frame measured
    1,601,976 clocks, 222% of the budget -- and a cart that misses the
    frame also fails `glass`, because there is no complete frame for the
    scan to match. Two triangles an object is 50 in all, and sampling a
    page is the only thing this cart needs an object to do.
    """
    # SMALL, and that is the second thing that had to shrink. Twenty-five
    # two-unit quads at z=7 overlap and cover the panel twice over: 50
    # triangles measured 1,670,731 clocks, 232% of the frame, against
    # pages.zol's 449,505 for FORTY-EIGHT triangles. The cost was never
    # the triangles, it was the fill.
    verts, uvs = [], []
    for su, sv in ((0, 0), (1, 0), (1, 1), (0, 1)):
        verts += [int((su - 0.5) * 0.9 * ONE),
                  int((sv - 0.5) * 0.9 * ONE), 0]
        uvs.append((su * 31) | ((sv * 31) << 8))
    # BOTH SIDES. A flat quad with OBJ_CULL is visible from one side
    # only, and every square here shares one yaw -- so they do not take
    # turns disappearing, they ALL vanish together for a third of every
    # rotation. Measured: 17 frames of 90 with nothing on the panel at
    # all. Culling is right for a closed mesh and wrong for a sheet.
    return Mesh(verts, [(0, 2, 1, 0), (0, 3, 2, 0)], uvs=uvs)


def source():
    """One page, and a marker that says where the window starts.

    TWENTY-FOUR SEPARATE PAGES DO NOT FIT: a page is 680 words and DMEM
    has room for about eleven of them before DL_BASE. So there is ONE
    page here, stored with its first 24 words repeated on the end, and
    slot k loads the 680 words beginning at k -- a ROTATION of the same
    image by 2k texels, since a word is two texels.

    That is not a weaker test than 24 hand-drawn pages, it is a sharper
    one. Every slot holds provably different bytes, and they differ by a
    known amount, so a slot that aliases another shows up as a marker in
    the wrong place rather than as a texture that merely looks odd.
    """
    a = rgb555(0x30, 0x90, 0xC0)
    b = rgb555(0x10, 0x10, 0x18)
    lit = rgb555(0xF8, 0xF8, 0xC0)
    px = [[a if ((x // 4) + (y // 4)) % 2 else b for x in range(32)]
          for y in range(32)]
    for x in range(32):                  # a ramp along the top row, so
        px[0][x] = lit if x < 6 else b   # a rotation is unmistakable
        px[1][x] = lit if x < 6 else b
    return px


def main():
    cart = Cart("pagemax")
    page = TexturePage(source()).words()
    buf = cart.data(Table(page + page[:N]), "pages")
    quad = uv_quad()
    mesh = cart.data(quad, "quad")

    yaw = cart.var("yaw")
    boot = cart.var("boot")
    nobj = cart.var("n")

    p = cart.program()
    p.addi(yaw, 4).load(yaw).push(1023).emit("and").store(yaw)

    # ---- one slot a frame, N frames, then never again -----------------
    for k in range(N):
        skip = p.label("load")
        p.load(boot).push(k).emit("eq", f"jz {skip}")
        p.set(spec.TEX_PAGE, k)
        p.set(spec.TEX_SRC, int(buf) + k)      # ...the window for slot k
        p.mark(skip)
    done = p.label("loaded")
    p.load(boot).push(N).emit("lt", f"jz {done}")
    p.addi(boot, 1)
    p.mark(done)

    # ---- every page, in one frame -------------------------------------
    p.set(nobj, 0)
    # The bottom row is the COMPARISON: page 0 again, and beside it the
    # page that is not there. They must come out identical, and putting
    # them side by side is the whole reason the cart is worth looking at
    # rather than only worth crossing.
    cells = [(k, k) for k in range(N)] + [(N, 0), (N + 1, OUT_OF_RANGE)]
    for slot, sel in cells:
        col, row = slot % 5, slot // 5
        p.object(nobj, int(mesh),
                 int((col - 2.0) * 1.15 * ONE),
                 int((1.15 - row * 1.05) * ONE),
                 int(7.0 * ONE),
                 [f"load {int(yaw)}"],
                 (quad.flags & ~spec.OBJ_CULL)
                 | (sel << spec.OBJ_PAGE_SHIFT))
    p.load(nobj).store(spec.OL_BASE)
    p.emit("halt")

    cart.boot(spec.CAM_Z, 0)
    cart.write(HERE / "pagemax.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
