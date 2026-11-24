"""what one body costs the frame on the simulated silicon, by its faces and its distance"""
import sys, math, json; sys.path.insert(0, "experiments/park"); sys.path.insert(0, "."); sys.path.insert(0, "tests")
import numpy as np
from zeta import gpu, spec, profile, cabinet, silicon
keep = gpu.render
gpu.render = lambda *a, **k: np.zeros((spec.H, spec.W, 3), np.uint8)
import test_tnd_yard as T
ONE = 65536
silicon.build()
cart = cabinet.load_cart(T.CART)
NF = {0: 369, 1: 252, 2: 150}
def scene(k, dist):
    y = T.Yard(T.CART); g = y.g
    y.who(3)
    mk = g.syms["yard_marks"]
    def place(b, u, v):
        x, z = int(round((y.hx - v) * ONE)) & 0xFFFFFFFF, int(round((y.hz + u) * ONE)) & 0xFFFFFFFF
        a = g.syms[f"e{b}_pos"]
        for o, w in ((0, x), (1, z), (2, x), (3, z)): g.d[a + o] = w
        g.d[mk + 2 * b], g.d[mk + 2 * b + 1] = x, z
    for b in range(7):
        place(b, -28 + 2 * b, -15.6)
    if k is not None: place(k, 0.0, -13.0 + dist)
    for _ in range(30):
        y.put(0.0, -13.0, 256); g.step(0)
    d = g.d; n = d[spec.OL_BASE]; cf = 0; ncart = 0
    for i in range(min(n, spec.OL_MAX)):
        b = spec.OL_BASE + 1 + i * spec.OL_STRIDE
        if d[b + 5] & spec.OBJ_CART: cf += d[d[b]] >> 16; ncart += 1
    seen = None if k is None else d[g.syms["yard_seen"] + k]
    rows = profile.cost(dict(cart), [0, 0, 0], g.m.pack(), 0)
    return np.mean([r["clk"] for r in rows]), {s: int(np.mean([r[s] for r in rows])) for s in ("walk", "seq", "blkd")}, cf, seen, spec.FUEL - g.m.vm.fuel_left
out = {}
base, st, cf, _, fuel = scene(None, 0)
print(f"nobody in shot: {base:,.0f} clocks ({100*base/864000:.1f}%), cart faces {cf}, instructions {fuel}", flush=True)
for dist in (2.5, 5.0, 10.0, 20.0):
    for k in (2, 1, 0):
        c, st, cf, seen, fuel = scene(k, dist)
        out[f"{k}@{dist}"] = c - base
        print(f"  {NF[k]:3d} faces at {dist:4.1f}: +{c - base:8,.0f} clocks (+{100*(c-base)/864000:.2f}% of a frame); drawn {seen}; cart faces {cf}; walk {st['walk']:,} seq {st['seq']:,}", flush=True)
json.dump(out, open(sys.argv[1], "w"))
