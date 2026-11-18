"""pager.py -- E5: the black mirror, and E6: diffs as index ranges.

THE WORLD IS ONE LINEAR ORDER AND THE PLAYER IS A WINDOW OVER IT. The
card stores cells in a single sequence; the resident set is the cells
near the player; and because those two are different shapes, the
resident set is some number of DISCONTIGUOUS RANGES of the sequence.
That number is the number of SEEKS, which is the only expensive thing
about an SD read -- sequential bytes are nearly free.

    world  ->  index  ->  ranges  ->  reads

THE LAYOUT IS THE ONE E3 MEASURED, and it is not the one that was
assumed twice before it:

    slot(x, y, z) = hilbert2d(x, z) * height + y

Height MINOR, and the curve in TWO dimensions over the floor. A Zeta
world stands on a floor -- you see a long way sideways and not far up
or down -- so a 3D curve spends a third of its locality on the axis the
window is thinnest in. Measured over a 64 x 8 x 64 world with a
radius-8 disc: 17 cold seeks against 3D Hilbert's 91 and row-major's
136, and at a 50% over-read budget 4 against 120. The dimension of the
ordering is worth an order of magnitude more than which curve it is.
A column beneath a footprint is one run BY CONSTRUCTION, and what is
left for the curve to do is the part that is actually wide.

WHAT THIS MODULE IS NOT. It does not read the card and does not know
what a cell contains. It answers two questions and nothing else:

    resident(cx, cz, r)      which ranges cover the window
    step(a, b, r)            which ranges are NEW when the player moves

That second one is the whole of "no loading screens": you never stream
the world, you stream the DIFFERENCE, and the difference of two windows
one cell apart is a handful of ranges no matter how large the world is.
"""
from __future__ import annotations

import numpy as np

from . import spec  # noqa: F401  (kept so the module travels with the law)


def _rot(n, x, z, rx, rz):
    """One quadrant's reflection. n is the FULL side, never the current
    step -- getting that wrong yields a curve that is still a bijection
    and still looks local, which is the kind of wrong that survives
    review."""
    if rz == 0:
        if rx == 1:
            x = n - 1 - x
            z = n - 1 - z
        x, z = z, x
    return x, z


def hilbert2d(x, z, n):
    """Canonical xy2d: the position of (x, z) along an n x n Hilbert
    curve. Scalar, and computed rather than looked up, because the
    console cannot afford a table with a million entries in it."""
    d = 0
    s = n >> 1
    while s > 0:
        rx = 1 if (x & s) > 0 else 0
        rz = 1 if (z & s) > 0 else 0
        d += s * s * ((3 * rx) ^ rz)
        x, z = _rot(n, x, z, rx, rz)
        s >>= 1
    return d


def hilbert2d_grid(n):
    """Every column's index at once. Tooling only -- the baker uses this
    to lay the card out; the machine uses hilbert2d() a column at a
    time."""
    d = np.zeros((n, n), np.int64)
    zz, xx = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    x = xx.astype(np.int64).copy()
    z = zz.astype(np.int64).copy()
    s = n >> 1
    while s > 0:
        rx = ((x & s) > 0).astype(np.int64)
        rz = ((z & s) > 0).astype(np.int64)
        d += s * s * ((3 * rx) ^ rz)
        swap = rz == 0
        flip = swap & (rx == 1)
        x = np.where(flip, n - 1 - x, x)
        z = np.where(flip, n - 1 - z, z)
        x, z = np.where(swap, z, x), np.where(swap, x, z)
        s >>= 1
    return d


def _runs(sorted_slots):
    """Maximal contiguous runs of a sorted index array -> [(start, n)]."""
    if sorted_slots.size == 0:
        return []
    brk = np.nonzero(np.diff(sorted_slots) != 1)[0]
    starts = np.concatenate(([0], brk + 1))
    ends = np.concatenate((brk, [sorted_slots.size - 1]))
    return [(int(sorted_slots[s]), int(sorted_slots[e] - sorted_slots[s] + 1))
            for s, e in zip(starts, ends)]


def _merge(runs, want, waste):
    """Close the smallest gaps until the over-read budget is spent.

    Merging two runs separated by g cells costs g cells read and never
    used, and saves exactly ONE seek -- so closing the smallest gaps
    first is optimal for "fewest seeks inside a budget", whichever gaps
    they happen to be.
    """
    if waste <= 0 or len(runs) < 2:
        return runs
    gaps = sorted((runs[i + 1][0] - (runs[i][0] + runs[i][1]), i)
                  for i in range(len(runs) - 1))
    budget = want * waste
    close = set()
    for g, i in gaps:
        if g > budget:
            break
        budget -= g
        close.add(i)
    out, i = [], 0
    while i < len(runs):
        start, n = runs[i]
        while i in close:
            i += 1
            n = runs[i][0] + runs[i][1] - start
        out.append((start, n))
        i += 1
    return out


class Pager:
    """A world of side x side columns, `height` cells deep, laid out
    along a 2D Hilbert curve with height minor."""

    def __init__(self, side: int, height: int, words_per_cell: int = 1):
        if side & (side - 1):
            raise ValueError(f"side must be a power of two, not {side}")
        self.side = side
        self.height = height
        self.words_per_cell = words_per_cell
        self.cells = side * side * height

    # ---- the index ---------------------------------------------------
    def slot(self, x: int, y: int, z: int) -> int:
        """Where cell (x, y, z) lives in the card's one sequence."""
        if not (0 <= y < self.height):
            raise ValueError(f"y {y} outside 0..{self.height - 1}")
        return hilbert2d(x % self.side, z % self.side,
                         self.side) * self.height + y

    def column(self, x: int, z: int) -> tuple[int, int]:
        """(first slot, count) of the whole column under (x, z). Always
        ONE range -- that is what height-minor buys."""
        return (hilbert2d(x % self.side, z % self.side, self.side)
                * self.height, self.height)

    # ---- the window --------------------------------------------------
    def footprint(self, cx: int, cz: int, r: int) -> np.ndarray:
        """The columns inside radius r of (cx, cz), as slot starts."""
        d = np.arange(-r, r + 1)
        dz, dx = np.meshgrid(d, d, indexing="ij")
        keep = (dx * dx + dz * dz) <= r * r
        xs = (cx + dx[keep]) % self.side
        zs = (cz + dz[keep]) % self.side
        g = getattr(self, "_grid", None)
        if g is None:
            g = self._grid = hilbert2d_grid(self.side)
        return g[zs, xs] * self.height

    def resident(self, cx: int, cz: int, r: int,
                 waste: float = 0.0) -> list[tuple[int, int]]:
        """The ranges of the card that cover the window, as (slot, n)."""
        col = np.sort(self.footprint(cx, cz, r))
        slots = (col[:, None] + np.arange(self.height)[None, :]).ravel()
        slots.sort()
        return _merge(_runs(slots), slots.size, waste)

    # ---- the difference ----------------------------------------------
    def step(self, a: tuple[int, int], b: tuple[int, int], r: int,
             waste: float = 0.0) -> tuple[list[tuple[int, int]], int]:
        """Moving the window from a to b: the ranges that are NEW, and
        how many cells fall out.

        THIS IS THE WHOLE OF "NO LOADING SCREENS". The world's size does
        not appear anywhere in the answer -- only the window's rim does,
        and the rim of a disc grows with r and not with the world. A
        step across a continent costs the same as a step across a room.
        """
        was = set(self.footprint(*a, r).tolist())
        now = set(self.footprint(*b, r).tolist())
        fresh = np.sort(np.array(sorted(now - was), dtype=np.int64))
        evicted = len(was - now) * self.height
        if fresh.size == 0:
            return [], evicted
        slots = (fresh[:, None] + np.arange(self.height)[None, :]).ravel()
        slots.sort()
        return _merge(_runs(slots), slots.size, waste), evicted

    # ---- what it costs -----------------------------------------------
    def cost(self, ranges: list[tuple[int, int]]) -> tuple[int, int]:
        """(seeks, words) for a list of ranges."""
        return len(ranges), sum(n for _, n in ranges) * self.words_per_cell


class Pyramid:
    """E4: window collapse as ONE LOD.

    THE SIX KNOBS WERE ONE KNOB ALL ALONG. Detail near the player, less
    of it further out, is not a set of thresholds to tune -- it is the
    single question "how many cells wide is the window", asked once and
    then asked again of a world half the size.

    The card holds the world at every level, each in its OWN Hilbert
    order over its own grid:

        level 0   side   x side   columns, the finest
        level 1   side/2 x side/2, each cell covering four of level 0
        level k   side>>k squared

    which costs 1 + 1/4 + 1/16 + ... = 4/3 of level 0 alone. Storing the
    chain INSIDE each cell instead would be the obvious thing and the
    wrong one: a ring that wants level 2 would then read a stride out of
    every cell, and a strided read is a seek per cell.

    THE COLLAPSE. Take radius R at EVERY level, and skip what a finer
    level already covered. Level k-1's disc of R covers R/2 in level k's
    coordinates, so level k contributes the ANNULUS from R/2 to R --
    about 3/4 pi R squared columns, the same at every level. So:

        cost   grows LINEARLY with levels
        reach  grows EXPONENTIALLY with levels

    One knob, R. The descent from a high view to the ground is not a
    different mode; it is the same window with fewer levels under it.
    """

    def __init__(self, side: int, height: int, levels: int,
                 words_per_cell: int = 1):
        if side & (side - 1):
            raise ValueError(f"side must be a power of two, not {side}")
        if (side >> (levels - 1)) < 2:
            raise ValueError(f"{levels} levels is too many for side {side}")
        self.side = side
        self.height = height
        self.levels = levels
        self.words_per_cell = words_per_cell
        self._base = []
        at = 0
        for k in range(levels):
            self._base.append(at)
            at += (side >> k) * (side >> k) * height
        self.cells = at
        self._grid: dict[int, np.ndarray] = {}

    def level_side(self, k: int) -> int:
        return self.side >> k

    def _g(self, k: int) -> np.ndarray:
        if k not in self._grid:
            self._grid[k] = hilbert2d_grid(self.level_side(k))
        return self._grid[k]

    def slot(self, k: int, x: int, y: int, z: int) -> int:
        n = self.level_side(k)
        return (self._base[k]
                + hilbert2d(x % n, z % n, n) * self.height + y)

    # ---- the window --------------------------------------------------
    def _annulus(self, cx: int, cz: int, R: int, k: int) -> np.ndarray:
        """Level k's columns, as a ring measured in LEVEL-0 UNITS.

        Level k owns the shell from R*2^(k-1) to R*2^k away from the
        player, and a cell is in it if its box INTERSECTS that shell.
        Stated this way the shells are [0,R], [R,2R], [2R,4R], ... which
        tile the disc of R*2^(L-1) exactly, with no gap and no appeal to
        where any level's grid happens to line up.

        THE OBVIOUS VERSION DOES NOT TILE. Working in each level's own
        cell coordinates -- keep what is within R of cx >> k, drop what
        the level below covered -- puts every level's centre on a
        TRUNCATED coordinate, so the discs sit up to half a coarse cell
        off one another. Measured: 2,374 level-0 cells inside the window
        that no level covered, and after an exact children-are-covered
        test still 1,609. The hole-free radius came out at 46 to 55
        cells where the arithmetic promised 64 -- a window that lies
        about how far it sees, and nothing about the picture would say
        so. Measuring the ring in level-0 units removes the question
        rather than bounding it.
        """
        n = self.level_side(k)
        sz = 1 << k                       # level-0 cells per level-k cell
        r_out = R * sz
        r_in = 0 if k == 0 else R * (sz >> 1)
        lo, hi = (cx - r_out) // sz, (cx + r_out) // sz
        lz, hz = (cz - r_out) // sz, (cz + r_out) // sz
        X = np.arange(lo, hi + 1)[None, :]
        Z = np.arange(lz, hz + 1)[:, None]
        # each cell's level-0 box, and its nearest / farthest corner
        x0, x1 = X * sz, X * sz + sz - 1
        z0, z1 = Z * sz, Z * sz + sz - 1
        nx = np.maximum(0, np.maximum(x0 - cx, cx - x1))
        nz = np.maximum(0, np.maximum(z0 - cz, cz - z1))
        fx = np.maximum(np.abs(x0 - cx), np.abs(x1 - cx))
        fz = np.maximum(np.abs(z0 - cz), np.abs(z1 - cz))
        keep = (nx * nx + nz * nz) <= r_out * r_out
        if r_in:                          # wholly inside the level below
            keep &= (fx * fx + fz * fz) >= r_in * r_in
        Xs = np.broadcast_to(X, keep.shape)[keep] % n
        Zs = np.broadcast_to(Z, keep.shape)[keep] % n
        return self._g(k)[Zs, Xs] * self.height + self._base[k]

    def footprint(self, cx: int, cz: int, R: int) -> dict[int, np.ndarray]:
        return {k: self._annulus(cx, cz, R, k) for k in range(self.levels)}

    def resident(self, cx: int, cz: int, R: int,
                 waste: float = 0.0) -> list[tuple[int, int]]:
        out = []
        for k, col in self.footprint(cx, cz, R).items():
            s = np.sort(col)
            slots = (s[:, None] + np.arange(self.height)[None, :]).ravel()
            slots.sort()
            out += _merge(_runs(slots), slots.size, waste)
        return out

    def step(self, a: tuple[int, int], b: tuple[int, int], R: int,
             waste: float = 0.0) -> tuple[list[tuple[int, int]], int]:
        """The ranges that are NEW, and how many cells fall out.

        A step of one level-0 cell moves the COARSE levels only one time
        in 2^k, so most frames touch only the finest rings -- which is
        the other half of what the collapse buys.
        """
        was = self.footprint(*a, R)
        now = self.footprint(*b, R)
        out, evicted = [], 0
        for k in range(self.levels):
            w = set(was[k].tolist())
            n = set(now[k].tolist())
            evicted += len(w - n) * self.height
            fresh = np.sort(np.array(sorted(n - w), dtype=np.int64))
            if fresh.size == 0:
                continue
            slots = (fresh[:, None] + np.arange(self.height)[None, :]).ravel()
            slots.sort()
            out += _merge(_runs(slots), slots.size, waste)
        return out, evicted

    def cost(self, ranges: list[tuple[int, int]]) -> tuple[int, int]:
        return len(ranges), sum(n for _, n in ranges) * self.words_per_cell

    def reach(self, R: int) -> int:
        """How far the window sees, in level-0 cells."""
        return R << (self.levels - 1)
