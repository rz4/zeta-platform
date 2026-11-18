"""tiled.py -- the tile's semantics, settled before its silicon exists.

Roadmap item 15 named one open question and called it harder than 13b's:
tiling changes the ORDER of pixel writes, so what does the law say the
answer is? The answer turns out to be smaller than the question, and it
is worth writing down exactly why.

    A PIXEL BELONGS TO EXACTLY ONE TILE.

That single fact does most of the work. If a tile's face list keeps
display-list order, then the sequence of fragments arriving at any given
pixel is the SAME SUBSEQUENCE of the global order it is today. The depth
test sees the same fragments in the same order, ties resolve the same
way (`z <= stored`, later wins -- which this machine already legislated
and is NOT order-independent), and the pick register watches the same
last writer. Tiling is therefore a no-op for everything Zeta draws
today, by construction rather than by luck.

This module proves that by running it, because "by construction" is
what people say right before they ship a seam. It renders every frame
twice -- once immediate, once tile by tile -- and demands the two
framebuffers be bit-identical.

TWO THINGS ARE NOT AUTOMATIC, and both were found by building this
rather than by reasoning about it:

  1. THE SPAN LEVEL. With OBJ_LODSPAN the mip is held across a row from
     its first edge-covered pixel. Let a tile shorten the row and each
     slice picks its own level off its own first pixel -- the same face
     textured two ways either side of a seam. The rule is that clipping
     confines WRITES and never the span arithmetic. gpu._fill keeps the
     wrong version runnable (`naive_clip`) so the size of the mistake
     can be measured; see measure_naive().

  2. BLENDING, which is the part item 15 actually worried about. See
     THE BLEND-ORDER LAW below.
"""
from __future__ import annotations

import numpy as np

from . import gpu, spec

TILE_W, TILE_H = 64, 32
TILES_X = (spec.W + TILE_W - 1) // TILE_W
TILES_Y = (spec.H + TILE_H - 1) // TILE_H


def tiles(tw=TILE_W, th=TILE_H):
    for ty in range(0, spec.H, th):
        for tx in range(0, spec.W, tw):
            yield (tx, ty, min(tx + tw, spec.W) - 1, min(ty + th, spec.H) - 1)


# ---------------------------------------------------------------------------
# capture: transform once, keep every face the rasteriser was handed
# ---------------------------------------------------------------------------
class _Capture:
    """Records the arguments of every _fill the law makes, in order, and
    draws nothing. This IS the tiled architecture's first stage: bin
    after transform, so binning replays setup rather than redoing it."""

    def __init__(self):
        self.faces = []

    def __enter__(self):
        self._real = gpu._fill
        cap = self

        def spy(fb, zbuf, *args, **kw):
            cap.faces.append((args, kw))
            return False              # nothing is drawn in the capture pass

        gpu._fill = spy
        return self

    def __exit__(self, *e):
        gpu._fill = self._real


def _box(args):
    x0, y0, x1, y1, x2, y2 = args[:6]
    return (max(min(x0, x1, x2) >> spec.SUB, 0),
            max(min(y0, y1, y2) >> spec.SUB, 0),
            min(max(x0, x1, x2) >> spec.SUB, spec.W - 1),
            min(max(y0, y1, y2) >> spec.SUB, spec.H - 1))


# ---------------------------------------------------------------------------
# the tiled render
# ---------------------------------------------------------------------------
def render_tiled(dmem, cram=None, tex=None, tw=TILE_W, th=TILE_H,
                 naive=False):
    """Same picture, drawn tile by tile. Any difference from
    gpu.render is a defect in the tile's semantics, not a tolerance."""
    with _Capture() as cap:
        gpu.render(list(dmem), cram, tex)         # transform + bin only
    fb, zbuf, _sh = gpu.seed(dmem, cram)         # the identical start

    for (tx0, ty0, tx1, ty1) in tiles(tw, th):
        for args, kw in cap.faces:                # DISPLAY-LIST ORDER: the
            bx0, by0, bx1, by1 = _box(args)       # whole law in one line
            if bx1 < tx0 or bx0 > tx1 or by1 < ty0 or by0 > ty1:
                continue
            k = dict(kw)
            k["clip"] = (tx0, ty0, tx1, ty1)
            k["naive_clip"] = naive
            k.pop("watch", None)                  # pick is tested separately
            gpu._fill(fb, zbuf, *args, **k)
    return fb


def compare(cart, frames=4, pad=lambda f: (f >> 2) & 0x1F, naive=False,
            tw=TILE_W, th=TILE_H):
    """Immediate vs tiled, frame by frame. Returns per-frame pixel diffs."""
    from . import cabinet

    m = cabinet.VirtualMachine(cart)
    out = []
    for f in range(frames):
        m.frame(pad(f))
        direct = m.framebuffer()
        t = render_tiled(m.vm.dmem, m._cram, m._tex, tw, th, naive)
        out.append(int((direct != t).any(axis=2).sum()))
    return out
