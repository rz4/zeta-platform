#!/usr/bin/env python3
"""reach.py -- how far and how high each of the run's moves goes in the park (layer 12), on the open floor.

The park's stations were sized from P58's (gen_tnd.py PARK_TAP, PARK_LONG, PARK_FLIP); the moves must still clear
them. Run me after changing a jump. (P61: no long jump; the first jump by its hold; the pad nudges the flip; X is the superman punch.)
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


def fly(g, hold=3, flip_at=None, press=None):
    """from the press: A (or `press`) held `hold` frames, the flip pressed at `flip_at` frames -- how far, how high,
    how many frames in the air"""
    u0, top, air = g.u(), 0.0, 0
    for i in range(140):
        b = (A if press is None else press) if i < hold else 0
        g.step(L | U | b | (A if flip_at is not None and flip_at <= i < flip_at + 2 else 0))
        if g.py() == 0 and air > 2:
            break
        air += g.py() > 0
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
        for n in (1, 8, 20):
            out[f"tap_held_{n}"] = fly(runner(), hold=n)
        for name, pad in (("left", spec.PAD_LEFT), ("down", spec.PAD_DOWN)):
            g = runner()
            v0 = -64.0 - g.cell("px") / ONE
            d, top, air = fly(g, flip_at=5, press=None) if False else (None, None, None)
            for i in range(3):
                g.step(L | U | A)
            u0 = g.u()
            for i in range(80):
                g.step(L | U | (A if 5 <= i < 7 else 0) | (pad if i >= 7 else 0))
                if i > 9 and g.py() == 0:
                    break
            out[f"flip_nudged_{name}"] = (round(g.u() - u0, 2), round(-64.0 - g.cell("px") / ONE - v0, 2))
        out["superman"] = fly(runner(), hold=2, press=spec.PAD_X)
        g = runner()
        for _ in range(20):
            g.step(L)                            # (let go of Up at full pace: how far he coasts)
        u0 = g.u()
        for _ in range(40):
            g.step(L)
        out["coast_after_20"] = round(g.u() - u0, 2)
    finally:
        gpu.render = keep
    print(json.dumps(out))


if __name__ == "__main__":
    main()
