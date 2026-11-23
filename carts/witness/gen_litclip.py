#!/usr/bin/env python3
"""gen_litclip.py -- writes carts/witness/litclip.zol: LIT FACES THROUGH THE CLIPPER.

spec.OBJ_LIT's second witness, and the one the first could not be: shaded.zol
is two spheres that never come near the lens. This is a lit corridor with the
lens standing a hand from one wall and turning -- so in every frame lit faces
are cut by the near plane and by the guard band, and long ones have corners
the machine cannot project at all.

WHAT IT CAUGHT (2026-11-22, on glass in TEAR NOT DEMON's lit town since the
day it was lit -- "weird graphic hiccups at the edge of the screen"). The
silicon keeps a lit vertex's LEVEL beside it in the vertex cache, and
  * a vertex that cannot be projected was written with level ZERO, and
  * a face sent to the clipper took its third corner's level from whatever
    the last face had left in a register;
and the clipper interpolates the corners' COLOURS. So a wall cut by the lens
faded to black toward the end that was out of sight, one with all three
corners out of reach was black, and its neighbours wore each other's light.
The law lights every corner before it cuts (gpu.py, vattr), and never did.

Every face here has its own level and its own three vertices (one level a
face: a gradient across a clipped face is the law's own limit, CFP). The last
object is one huge lit triangle whose corners are ALL out of reach while its
middle fills the glass.

Run me after changing anything: python3 carts/witness/gen_litclip.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import spec                                    # noqa: E402
from zeta.forge import ONE, Cart, Mesh                   # noqa: E402

AMB, DIF = 3, 30


def level_word(t):
    """a normal straight up, t long: under a light straight down its level is AMB + about 29 t"""
    return (max(0, min(127, int(round(t * 127)))) & 0xFF) << 8


class Lit:
    def __init__(self):
        self.v, self.f, self.n = [], [], []

    def quad(self, pts, rgb, t):
        b = len(self.v) // 3
        for x, y, z in pts:
            self.v += [int(x * ONE), int(y * ONE), int(z * ONE)]
            self.n.append(level_word(t))
        self.f += [(b, b + 1, b + 2, rgb), (b, b + 2, b + 3, rgb)]

    def tri(self, pts, rgb, t):
        b = len(self.v) // 3
        for x, y, z in pts:
            self.v += [int(x * ONE), int(y * ONE), int(z * ONE)]
            self.n.append(level_word(t))
        self.f.append((b, b + 1, b + 2, rgb))

    def mesh(self):
        assert len(self.v) // 3 <= spec.MESH_NV_MAX and len(self.f) <= spec.MESH_NF_MAX
        return Mesh(self.v, self.f, colors=self.n)


def main():
    cart = Cart("litclip")
    walls = Lit()
    for k in range(6):                      # two walls of long fronts, each at its own level
        z0, z1 = -18 + 6 * k, -12 + 6 * k
        walls.quad([(-1.5, 0, z0), (-1.5, 0, z1), (-1.5, 3, z1), (-1.5, 3, z0)], 0xC87040, 0.15 + 0.16 * k)
        walls.quad([(1.5, 0, z0), (1.5, 0, z1), (1.5, 3, z1), (1.5, 3, z0)], 0x40A0C8, 0.95 - 0.16 * k)
    floor = Lit()
    for i in range(3):                      # a floor in strips, and a low ceiling: cut by all four sides
        for k in range(4):
            x0, z0 = -1.5 + i, -18 + 9 * k
            floor.quad([(x0, 0, z0), (x0 + 1, 0, z0), (x0 + 1, 0, z0 + 9), (x0, 0, z0 + 9)], 0x909088,
                       0.2 + 0.07 * ((3 * i + 5 * k) % 11))
    for k in range(2):
        floor.quad([(-1.5, 3, -18 + 18 * k), (1.5, 3, -18 + 18 * k), (1.5, 3, 18 * k), (-1.5, 3, 18 * k)], 0x6050A0,
                   0.5 + 0.3 * k)
    vast = Lit()                            # every corner out of reach, its middle on the glass
    vast.tri([(-400, 1.4, 6), (400, 1.4, 6.5), (0, 500, 7)], 0x30C050, 0.7)
    mw, mf, mv = (cart.data(m.mesh(), name) for m, name in ((walls, "walls"), (floor, "floor"), (vast, "vast")))
    lit = (walls.mesh().flags & ~spec.OBJ_GOURAUD) | spec.OBJ_LIT
    n = cart.var("n")
    cart.boot(spec.CAM_X, int(1.2 * ONE))   # 0.3 from the right-hand wall
    cart.boot(spec.CAM_Y, int(1.3 * ONE))
    cart.boot(spec.LIGHT_DIR, 127 << 8)     # straight down
    cart.boot(spec.LIGHT_AMB, AMB)
    cart.boot(spec.LIGHT_DIF, DIF)
    p = cart.program()
    p.load(spec.REG_FRAME).push(13).emit("mul").push(1023).emit("and").store(spec.CAM_YAW)
    p.load(spec.REG_FRAME).push(7).emit("and").push(8).emit("mul").store(spec.CAM_PITCH)
    p.set(n, 0)
    p.object(n, int(mf), 0, 0, 0, 0, lit)
    p.object(n, int(mw), 0, 0, 0, 0, lit)
    p.object(n, int(mv), 0, 0, 0, 0, lit)
    p.load(n).store(spec.OL_BASE)
    p.emit("halt")
    cart.write(HERE / "litclip.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
