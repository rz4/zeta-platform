"""tilecost.py -- pricing the tile (roadmap item 15) before any Verilog.

The tile proposes replacing the full-screen depth buffer -- 1,483,776
bits, 61% of every block-memory bit on this device -- with a 64x32 tile
of depth held on-die, returning ~145 M10K-equivalents. That memory is
the currency four separate deficits are denominated in: per-pixel
blending, a texture cache, sixteen voices, and room for game logic.

The roadmap states its own gate: "this must be MEASURED on a model
before a line of Verilog", because the amendment runs straight at this
machine's known bottleneck. Zeta is SETUP-bound, not fill-bound -- 136
clocks per face -- and a tiled renderer sets a face up once PER TILE IT
TOUCHES. If the average face touches six tiles, binning multiplies the
exact cost that already dominates and the trade is a disaster. If it
touches 1.2, the memory is nearly free.

So the whole question is one number: THE BINNING FANOUT, measured on
real frames rather than assumed. This module measures it, and to turn
it into clocks it first has to split the 136 into its parts:

    clocks_per_frame  =  C  +  S * faces  +  P * raster_pixels

C is the fixed overhead (the clear, the display list, scanout
bookkeeping), S the per-face setup, P the per-pixel raster cost. Three
unknowns, so it is fitted across carts whose face/pixel ratios differ
by an order of magnitude -- a cube of six big faces against a fabric of
three thousand small ones. The silicon reports its own clocks (the
ZETA_CLK meter in server.cpp); the law reports faces and pixels for the
same frames. Neither number is estimated.
"""
from __future__ import annotations

import os
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import gpu, spec

ROOT = Path(__file__).resolve().parents[1]
CLOCKS_PER_FRAME = 720_000           # 43.2 MHz / 60: the whole budget

TILE_W, TILE_H = 64, 32
TILES_X = (spec.W + TILE_W - 1) // TILE_W
TILES_Y = (spec.H + TILE_H - 1) // TILE_H
NTILES = TILES_X * TILES_Y


# ---------------------------------------------------------------------------
# the law, watched: every triangle the rasteriser actually sets up
# ---------------------------------------------------------------------------
class Trace:
    """Wraps gpu._fill so the geometry is observed EXACTLY as rasterised
    -- after culling, after the frustum reject, with the real clipped
    bounding box. Re-deriving the triangle list beside the law would be
    a second implementation, and a second implementation is a second
    thing that can be wrong."""

    def __init__(self):
        self.boxes: list[tuple[int, int, int, int]] = []
        self.covered = 0

    def __enter__(self):
        self._real = gpu._fill
        tr = self

        def spy(fb, zbuf, x0, y0, x1, y1, x2, y2, *a, **kw):
            lo_x = max(min(x0, x1, x2) >> spec.SUB, 0)
            hi_x = min(max(x0, x1, x2) >> spec.SUB, spec.W - 1)
            lo_y = max(min(y0, y1, y2) >> spec.SUB, 0)
            hi_y = min(max(y0, y1, y2) >> spec.SUB, spec.H - 1)
            if lo_x <= hi_x and lo_y <= hi_y:
                tr.boxes.append((lo_x, lo_y, hi_x, hi_y))
            return tr._real(fb, zbuf, x0, y0, x1, y1, x2, y2, *a, **kw)

        gpu._fill = spy
        return self

    def __exit__(self, *exc):
        gpu._fill = self._real

    # ---- the derived quantities -------------------------------------------
    @property
    def faces(self) -> int:
        return len(self.boxes)

    @property
    def raster_px(self) -> int:
        """Bounding-box pixels: what the rasteriser VISITS, which is what
        costs clocks -- not what survives the depth test."""
        return sum((x1 - x0 + 1) * (y1 - y0 + 1) for x0, y0, x1, y1 in self.boxes)

    def fanout(self, tw=TILE_W, th=TILE_H) -> tuple[int, list[int]]:
        """(face,tile) pairs, and the per-tile face counts."""
        pairs = 0
        per = [0] * (((spec.W + tw - 1) // tw) * ((spec.H + th - 1) // th))
        nx = (spec.W + tw - 1) // tw
        for x0, y0, x1, y1 in self.boxes:
            for ty in range(y0 // th, y1 // th + 1):
                for tx in range(x0 // tw, x1 // tw + 1):
                    pairs += 1
                    per[ty * nx + tx] += 1
        return pairs, per

    def tile_px(self, tw=TILE_W, th=TILE_H) -> int:
        """Raster pixels after binning: each face's box CLIPPED to each
        tile it touches. Sums to the same area plus nothing -- the point
        is that binning does not multiply the FILL, only the SETUP."""
        tot = 0
        for x0, y0, x1, y1 in self.boxes:
            for ty in range(y0 // th, y1 // th + 1):
                for tx in range(x0 // tw, x1 // tw + 1):
                    cx0, cx1 = max(x0, tx * tw), min(x1, tx * tw + tw - 1)
                    cy0, cy1 = max(y0, ty * th), min(y1, ty * th + th - 1)
                    tot += (cx1 - cx0 + 1) * (cy1 - cy0 + 1)
        return tot


# ---------------------------------------------------------------------------
# the silicon, metered
# ---------------------------------------------------------------------------
def silicon_clocks(cart: dict, frames: int, pads) -> list[int]:
    """Clocks between `start` and `frame_done`, straight from the RTL."""
    from . import silicon

    sim = silicon.build()
    work = Path(tempfile.mkdtemp(prefix="zeta-clk-"))
    ip, dp, cp = silicon.write_cart_hex(cart, work)
    env = dict(os.environ, ZETA_CLK="1")
    err = open(work / "clk.log", "w+")
    proc = subprocess.Popen([str(sim), str(ip), str(dp)]
                            + ([str(cp)] if cp else []),
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=err, cwd=work, env=env)
    n = spec.W * spec.H * 3 + spec.SAMPLES_PER_FRAME * 2
    for f in range(frames):
        proc.stdin.write(struct.pack("<I", pads(f) & 0xFFFF))
        proc.stdin.flush()
        if len(proc.stdout.read(n)) < n:
            raise SystemExit("the silicon frame server died mid-frame")
    proc.stdin.close()
    proc.wait(timeout=30)
    err.seek(0)
    return [int(l.split()[1]) for l in err if l.startswith("CLK ")]


def profile(path, frames=8, pad=lambda f: (f >> 2) & 0x1F):
    """One cart: silicon clocks and law geometry, frame by frame."""
    from . import asm, cabinet

    cart = asm.assemble(path)
    clocks = silicon_clocks(cart, frames, pad)
    m = cabinet.VirtualMachine(cart)
    rows = []
    for f in range(frames):
        with Trace() as tr:
            m.frame(pad(f))
        pairs, _ = tr.fanout()
        rows.append(dict(clocks=clocks[f], faces=tr.faces,
                         raster_px=tr.raster_px, pairs=pairs,
                         tile_px=tr.tile_px()))
    return rows


# ---------------------------------------------------------------------------
# the fit: clocks = C + S*faces + P*pixels
# ---------------------------------------------------------------------------
def fit(rows):
    A = np.array([[1.0, r["faces"], r["raster_px"]] for r in rows])
    b = np.array([float(r["clocks"]) for r in rows])
    (C, S, P), *_ = np.linalg.lstsq(A, b, rcond=None)
    pred = A @ np.array([C, S, P])
    err = np.abs(pred - b) / np.maximum(b, 1)
    return C, S, P, float(err.max()), float(err.mean())
