"""what a yard frame is made of: the same frame on the simulated silicon with parts of it taken away"""
import sys; sys.path.insert(0, "experiments/park"); sys.path.insert(0, "."); sys.path.insert(0, "tests")
import numpy as np
from zeta import gpu, spec, profile, cabinet, silicon
gpu.render = lambda *a, **k: np.zeros((spec.H, spec.W, 3), np.uint8)
import test_tnd_yard as T
silicon.build()
cart = cabinet.load_cart(T.CART)
def scene(fight):
    y = T.Yard(T.CART); g = y.g
    if fight:
        for _ in range(110): g.step(spec.PAD_UP)          # into the ring: the elite and the double on him
        for _ in range(60): g.d[g.syms["p_hp"]] = 140; g.step(0)
    else:
        y.who(3)
        for _ in range(30): g.step(0)
    return g
def cost(g, edit=None, halt=True):
    vm = g.m.vm; keep_i, keep_d = vm.imem[0], None
    d = g.d
    saved = {a: d[a] for a in range(spec.OL_BASE, spec.OL_BASE + 1 + spec.OL_MAX * spec.OL_STRIDE)}; saved[spec.DL_BASE] = d[spec.DL_BASE]
    if halt: vm.imem[0] = 0
    if edit: edit(d)
    st = g.m.pack()
    vm.imem[0] = keep_i
    for a, v in saved.items(): d[a] = v
    r = profile.cost(dict(cart), [0, 0], st, 0)[1]
    return r
def objs(d):
    n = d[spec.OL_BASE]; return [[d[spec.OL_BASE + 1 + i * spec.OL_STRIDE + j] for j in range(spec.OL_STRIDE)] for i in range(min(n, spec.OL_MAX))]
def keep(pred):
    def e(d):
        o = [x for x in objs(d) if pred(d, x)]
        d[spec.OL_BASE] = len(o)
        for i, x in enumerate(o):
            for j, w in enumerate(x): d[spec.OL_BASE + 1 + i * spec.OL_STRIDE + j] = w
    return e
is_cart = lambda d, x: bool(x[5] & spec.OBJ_CART)
nf = lambda d, x: (d[x[0]] >> 16) if is_cart(d, x) else d[x[0] + 1]
def nodl(d): d[spec.DL_BASE] = 0
def both(*es):
    def e(d):
        for f in es: f(d)
    return e
for name, fight in (("standing in the yard, nobody in shot", False), ("in the ring, the elite and the double on him", True)):
    g = scene(fight); d = g.d
    o = objs(d)
    print(f"== {name}: {len(o)} objects ({sum(is_cart(d, x) for x in o)} from the cart, {sum(nf(d, x) for x in o if is_cart(d, x))} faces; {sum(nf(d, x) for x in o if not is_cart(d, x))} faces from data memory); HUD triangles {d[spec.DL_BASE]}; instructions {spec.FUEL - g.m.vm.fuel_left}", flush=True)
    full = cost(g, halt=False); P = lambda r: f"{r['clk']:8,} ({100 * r['clk'] / 864000:4.1f}%)  clr {r['clr']:,} walk {r['walk']:,} seq {r['seq']:,} idle {r['idle']:,} blkd {r['blkd']:,}"
    print("  the frame whole            ", P(full), flush=True)
    for nm, ed in (("no program (same picture)   ", None), ("  and no HUD                ", nodl), ("  and no cart meshes         ", keep(lambda d, x: not is_cart(d, x))),
                   ("  and only cart meshes       ", keep(is_cart)), ("  and only him (737)         ", keep(lambda d, x: is_cart(d, x) and nf(d, x) == 737)),
                   ("  no objects at all          ", keep(lambda d, x: False)), ("  no objects, no HUD         ", both(keep(lambda d, x: False), nodl))):
        print(" ", nm, P(cost(g, ed)), flush=True)
