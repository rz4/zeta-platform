#!/usr/bin/env python3
"""census.py -- EVERY COMPONENT AGAINST ITS LIMIT, over the player's own session.

The probe of the Zeta-n hypothesis (README.md) asks what binds. This counts,
frame by frame on the law, what a cart takes of each of the machine's stated
stores, and from its build what it holds for good:

  per frame    objects (spec.OL_MAX), display-list triangles (spec.DL_MAX),
               cart-mesh vertices and faces (spec.CM_VMAX, CM_FMAX), the
               data-memory meshes' faces, instructions (spec.FUEL)
  for good     the program page, data memory, CRAM (its pose bank)

The frame's clocks, the other half, come from zeta.profile (the simulated
silicon's own stage counters).

    python3 experiments/isa/census.py CART.zol TAPE.ztp CARD.bin [FRAMES]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import cabinet, deploy, gpu, spec  # noqa: E402
from zeta import tape as ztape  # noqa: E402


def per_frame(m):
    d = m.vm.dmem
    n = d[spec.OL_BASE]
    objs = cv = cf = df = 0
    for i in range(min(n, spec.OL_MAX)):
        b = spec.OL_BASE + 1 + i * spec.OL_STRIDE
        mesh, flags = d[b], d[b + 5]
        objs += 1
        if flags & spec.OBJ_CART:
            w = d[mesh]
            cv += w & 0xFFFF
            cf += w >> 16
        elif 0 < mesh < spec.DMEM_WORDS - 1:
            df += d[mesh + 1]
    return objs, d[spec.DL_BASE], cv, cf, df, spec.FUEL - m.vm.fuel_left


def main():
    zol, tape_, card = sys.argv[1], sys.argv[2], sys.argv[3]
    header, pads = ztape.decode(Path(tape_).read_bytes())
    if len(sys.argv) > 4:
        pads = pads[:int(sys.argv[4])]
    cart = cabinet.load_cart(zol)
    cart["sd"] = deploy.card_images(Path(card))
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    keep, gpu.render = gpu.render, (lambda *a, **k: blank)
    rows = []
    try:
        m = cabinet.VirtualMachine(cart)
        for p in pads:
            m.frame(p)
            rows.append(per_frame(m))
    finally:
        gpu.render = keep
    r = np.array(rows[60:])
    names = ("objects", "display-list triangles", "cart-mesh vertices", "cart-mesh faces", "data-memory mesh faces",
             "instructions")
    limits = (spec.OL_MAX, spec.DL_MAX, spec.CM_VMAX, spec.CM_FMAX, None, spec.FUEL)
    out = {"cart": Path(zol).name, "frames": len(r), "per_frame": {}}
    for k, (nm, lim) in enumerate(zip(names, limits)):
        col = r[:, k]
        out["per_frame"][nm] = {"median": int(np.median(col)), "p99": int(np.percentile(col, 99)), "worst": int(col.max()),
                                "limit": lim, "worst_share": round(float(col.max()) / lim, 3) if lim else None}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
