#!/usr/bin/env python3
"""reach.py -- how far and how high each of the run's moves goes in the park (layer 12), on the open floor.

The park sizes its stations from these (gen_tnd.py PARK_TAP, PARK_LONG, PARK_FLIP). Run me after changing a jump.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bot  # noqa: E402
from bot import A, L, U, ONE  # noqa: E402
from zeta import gpu, spec  # noqa: E402

CART = Path(sys.argv[1]) if len(sys.argv) > 1 else bot.ROOT / "build" / "layer12" / "tnd.zol"


def runner():
    g = bot.Park(CART)
    g.d[g.syms["px"]] = int(round((-64.0 + 8.0) * ONE)) & 0xFFFFFFFF     # (v = -8: the floor beside the course)
    for q in (L, L, 0, 0, 0, L, L, L):
        g.step(q)
    for _ in range(70):
        g.step(L | U)
    return g


def fly(g, hold=3, flip_at=None):
    for _ in range(hold):
        g.step(L | U | A)
    u0, top, air = g.u(), 0.0, 0
    for i in range(140):
        g.step(L | U | (A if flip_at is not None and flip_at <= i < flip_at + 3 else 0))
        if g.py() == 0 and air > 2:
            break
        air += 1
        top = max(top, g.py())
    return round(g.u() - u0, 2), round(top, 2), air


def main():
    keep, gpu.render = gpu.render, (lambda *a, **k: np.zeros((spec.H, spec.W, 3), np.uint8))
    out = {}
    try:
        g = runner()
        u0 = g.u()
        for _ in range(60):
            g.step(L | U)
        out["run_a_frame"] = round((g.u() - u0) / 60, 3)
        out["tap"] = fly(runner())
        for fa in (4, 8, 12):
            out[f"tap_flip_at_{fa}"] = fly(runner(), flip_at=fa)
        out["long"] = fly(runner(), hold=20)
    finally:
        gpu.render = keep
    print(json.dumps(out))


if __name__ == "__main__":
    main()
