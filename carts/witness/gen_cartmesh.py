#!/usr/bin/env python3
"""gen_cartmesh.py -- writes carts/witness/cartmesh.zol: meshes drawn from the cart.

spec.OBJ_CART's witness (frontier 20). Lumps of triangles that live in the
cart's segment as three streams -- 16-bit vertices, packed faces, 5:5:5
colours -- and are drawn through five-word descriptors: turning, culled
and not, outlined, object-tinted, one swung through the near plane (the
clipper), two poses of one body swapped by its offsets every eight frames,
one whose descriptor is refused, a rank that overruns the store (the last
is not drawn), and an ordinary DMEM mesh among them. The lens turns.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
import numpy as np                                       # noqa: E402
from zeta import spec                                    # noqa: E402
from zeta.forge import Cart, Mesh, Table, ONE            # noqa: E402

SHIFT = 2


def lump(seed, nv, nf, r=9000):
    g = np.random.default_rng(seed)
    v = g.integers(-r, r, (nv, 3))
    f = [tuple(int(i) for i in g.choice(nv, 3, replace=False)) for _ in range(nf)]
    return v, f, g.integers(1, 1 << 15, nf)


def halves(h):
    h = [int(x) & 0xFFFF for x in h] + [0]
    return [h[i] | h[i + 1] << 16 for i in range(0, len(h) - 1, 2)]


def main():
    cart = Cart("cartmesh")
    descs = {}

    def place(name, v, f, c, shift=SHIFT, faces_at=None):
        vs = cart.cram(Table(halves(v.reshape(-1))), name + "_v")
        fs = faces_at if faces_at is not None else cart.cram(Table([a | b << 10 | c_ << 20 for a, b, c_ in f]), name + "_f")
        cs = cart.cram(Table(halves(c)), name + "_c")
        descs[name] = cart.data(Table([len(v) | len(f) << 16, int(vs), int(fs), int(cs), shift]), name)
        return int(vs), int(fs), int(cs)
    a = lump(1, 60, 90)
    place("a", *a)
    b = lump(2, 33, 41)                     # odd counts: the streams' padded halves
    place("b", *b, shift=3)
    p0 = lump(3, 48, 70)
    v0, f0, c0 = place("pose", *p0)
    p1 = lump(4, 48, 70)
    v1 = int(cart.cram(Table(halves(p1[0].reshape(-1))), "pose1_v"))
    c1 = int(cart.cram(Table(halves(p1[2])), "pose1_c"))
    big = lump(5, 250, 300, r=5000)
    place("big", *big)
    bad = cart.data(Table([40 | 60 << 16, spec.CRAM_WORDS - 3, 1, 1, SHIFT]), "bad")     # its vertices run off the cart
    dm = lump(6, 30, 44)
    rgb = [(int(c) >> 10 & 31) << 19 | (int(c) >> 5 & 31) << 11 | (int(c) & 31) << 3 for c in dm[2]]
    plain = cart.data(Mesh([int(x) << SHIFT for x in dm[0].reshape(-1)], [(i, j, k, c) for (i, j, k), c in zip(dm[1], rgb)]), "plain")
    n = cart.var("n")
    cart.boot(spec.CAM_Y, int(0.3 * ONE))
    p = cart.program()
    p.load(spec.REG_FRAME).push(3).emit("mul").push(1023).emit("and").store(spec.CAM_YAW)
    # the pose's offsets, swapped every eight frames
    sw = p.label("swap")
    p.load(spec.REG_FRAME).push(8).emit("and", f"jz {sw}")
    p.set(int(descs["pose"]) + 1, v1).set(int(descs["pose"]) + 3, c1).emit(f"jmp {sw}_d")
    p.mark(sw)
    p.set(int(descs["pose"]) + 1, v0).set(int(descs["pose"]) + 3, c0)
    p.mark(f"{sw}_d")
    p.set(n, 0)
    spin = (f"load {spec.REG_FRAME}", "push 5", "mul", "push 1023", "and")
    tumble = (f"load {spec.REG_FRAME}", "push 7", "mul", "push 1023", "and", "dup", "shl 10", "or")
    F = spec.OBJ_CART
    p.object(n, int(descs["a"]), 0, 0, int(3 * ONE), spin, F | spec.OBJ_CULL)
    p.object(n, int(plain), int(-2 * ONE), 0, int(2.5 * ONE), spin, spec.OBJ_CULL)
    p.object(n, int(descs["b"]), int(2 * ONE), 0, int(2 * ONE), tumble, F | spec.OBJ_EDGE)
    p.object(n, int(descs["pose"]), 0, 0, int(-3 * ONE), spin,
             lambda q: q.push32(F | spec.OBJ_OTINT | 25 << 27 | 12 << 22 | 30 << 17))
    p.object(n, int(descs["a"]), 0, 0, int(0.4 * ONE), tumble, F)                    # through the near plane
    p.object(n, int(bad), int(3 * ONE), 0, 0, 0, F)                                   # refused: nothing
    for k in range(6):                      # six bigs: with a (twice), b and the pose the store's vertices run out
        p.object(n, int(descs["big"]), int((k - 2.5) * 1.2 * ONE), int(1.2 * ONE), int(-2 * ONE) + int(k * 0.3 * ONE), spin, F | spec.OBJ_CULL)
    p.object(n, int(descs["b"]), int(-3 * ONE), 0, 0, spin, F)                       # ...but a small one after still fits
    p.load(n).store(spec.OL_BASE)
    p.emit("halt")
    cart.write(HERE / "cartmesh.zol")
    print(cart.report())
    used_v = 60 + 33 + 48 + 60 + 250 * 6 + 33
    print("vertices asked of the store:", used_v, "of", spec.CM_VMAX)


if __name__ == "__main__":
    main()
