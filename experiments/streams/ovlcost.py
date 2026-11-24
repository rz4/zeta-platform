import sys; sys.path.insert(0, "experiments/park"); sys.path.insert(0, "."); sys.path.insert(0, "tests")
import numpy as np
from zeta import gpu, spec, profile, cabinet, silicon
gpu.render = lambda *a, **k: np.zeros((spec.H, spec.W, 3), np.uint8)
import test_tnd_yard as T
silicon.build()
cart = cabinet.load_cart(T.CART)
y = T.Yard(T.CART); g = y.g; d = g.d; vm = g.m.vm
for _ in range(20): g.step(0)
vm.imem[0] = 0
base = None
for n, dst in ((0, 0), (1000, 20000), (4000, 20000), (8000, 20000), (16000, 8000), (29000, 0)):
    d[spec.OVL_SRC], d[spec.OVL_DST], d[spec.OVL_LEN], d[spec.OVL_GO] = 0, dst, n, 1 if n else 0
    r = profile.cost(dict(cart), [0], g.m.pack(), 0)[0]
    if base is None: base = r["clk"]
    print(f"overlay of {n:6,} words: frame {r['clk']:,} clocks; over none +{r['clk'] - base:,} = {(r['clk'] - base) / max(1, n):.2f} clocks a word, {100 * (r['clk'] - base) / 864000:.1f}% of a frame", flush=True)
