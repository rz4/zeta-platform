#!/usr/bin/env python3
"""curves.py -- E3: Morton against Hilbert, MEASURED.

THE QUESTION THE PAGER RESTS ON. The world is a 3D grid of cells. The
resident set is the cells near the player. The cells live on an SD card
in ONE linear order, so the resident set is some number of DISCONTIGUOUS
RANGES of that order -- and that number is the number of SEEKS, which is
the only thing about SD reads that is expensive. Sequential bytes are
nearly free; a seek is not.

So: for a spatial window of radius r, how many ranges?

It has been assumed twice in this project that Hilbert is the answer
because Hilbert has better locality "in theory". This measures it, and
measures the thing that actually matters rather than the thing that is
easy to state:

  RANGES            cold seeks: how many discontiguous runs the whole
                    resident set forms
  SEEKS AT A WASTE  you are allowed to read cells you do not need if it
    BUDGET          saves a seek. At 10%/25%/50% extra bytes, how few
                    seeks can a greedy merge get to? This is the real
                    number -- nobody pages with zero waste.
  STEP RANGES       the player moves one cell. The cells that ENTER the
                    window are the streaming cost, and they form their
                    own runs. A curve can win cold and lose here.

THE CURVE IS CHECKED BEFORE IT IS TRUSTED. A wrong Hilbert still
produces a plausible table, and this project has been burned twice by
instruments that agreed with themselves. Both orderings are verified to
be permutations, and Hilbert is verified to be a HILBERT curve --
consecutive indices one cell apart -- before any measurement runs.

    python3 bench/curves.py
"""
import numpy as np

N_BITS = 6                     # 64 x 64 x 64 cells
N = 1 << N_BITS
RADII = (2, 3, 4, 6, 8)
SAMPLES = 160                  # viewer positions averaged over
SEED = 20260826


# ---------------------------------------------------------------------
def morton(x, y, z, bits=N_BITS):
    """Bit-interleave. The cheap one: a few shifts, no state."""
    out = np.zeros_like(x, dtype=np.int64)
    for b in range(bits):
        out |= ((x >> b) & 1).astype(np.int64) << (3 * b + 2)
        out |= ((y >> b) & 1).astype(np.int64) << (3 * b + 1)
        out |= ((z >> b) & 1).astype(np.int64) << (3 * b + 0)
    return out


def hilbert(x, y, z, bits=N_BITS):
    """Skilling's AxesToTranspose (AIP 707, 2004), vectorised.

    The expensive one: the transform is inherently sequential in the
    bits, so on silicon it is a small state machine rather than a wiring
    pattern. That cost only matters if it BUYS something, which is what
    this file is for.
    """
    X = [x.astype(np.int64).copy(), y.astype(np.int64).copy(),
         z.astype(np.int64).copy()]
    n = 3
    M = 1 << (bits - 1)
    # inverse undo
    Q = M
    while Q > 1:
        P = Q - 1
        for i in range(n):
            mask = (X[i] & Q) != 0
            X[0] = np.where(mask, X[0] ^ P, X[0])
            t = np.where(mask, 0, (X[0] ^ X[i]) & P)
            X[0] ^= t
            X[i] ^= t
        Q >>= 1
    # Gray encode
    for i in range(1, n):
        X[i] ^= X[i - 1]
    t = np.zeros_like(X[0])
    Q = M
    while Q > 1:
        t = np.where((X[n - 1] & Q) != 0, t ^ (Q - 1), t)
        Q >>= 1
    for i in range(n):
        X[i] ^= t
    # transpose -> index
    idx = np.zeros_like(X[0])
    for b in range(bits - 1, -1, -1):
        for i in range(n):
            idx = (idx << 1) | ((X[i] >> b) & 1)
    return idx


def _h2d(x, z, n=N):
    """Canonical 2D Hilbert (xy2d), vectorised. Note the rotation uses
    the FULL side n, not the current s -- getting that wrong yields a
    curve that is still a bijection and still looks local, which is
    exactly the kind of wrong this project keeps having to catch."""
    x = x.astype(np.int64).copy()
    z = z.astype(np.int64).copy()
    d = np.zeros_like(x)
    s = n // 2
    while s > 0:
        rx = ((x & s) > 0).astype(np.int64)
        rz = ((z & s) > 0).astype(np.int64)
        d += s * s * ((3 * rx) ^ rz)
        swap = rz == 0
        flip = swap & (rx == 1)
        x = np.where(flip, n - 1 - x, x)
        z = np.where(flip, n - 1 - z, z)
        x, z = np.where(swap, z, x), np.where(swap, x, z)
        s //= 2
    return d


def column_hilbert(x, y, z, bits=N_BITS):
    """A 2D Hilbert over the FLOOR, with the whole column beneath a
    footprint contiguous.

    THE WORLD STANDS ON A FLOOR. Interleaving y with x and z spends a
    third of the curve's locality on an axis the window is thin in. This
    keeps y minor -- a column is one run, always -- and spends the curve
    only where the window is wide.
    """
    return _h2d(x, z) * N + y.astype(np.int64)


def column_morton(x, y, z, bits=N_BITS):
    """The same idea with the cheap curve, to separate 'columns help'
    from 'Hilbert helps'."""
    m = np.zeros_like(x, dtype=np.int64)
    for b in range(bits):
        m |= ((x >> b) & 1).astype(np.int64) << (2 * b + 1)
        m |= ((z >> b) & 1).astype(np.int64) << (2 * b + 0)
    return m * N + y.astype(np.int64)


def rowmajor(x, y, z, bits=N_BITS):
    """The baseline. Without it the other two numbers mean nothing."""
    return (z.astype(np.int64) << (2 * bits)) | (y.astype(np.int64) << bits) | x


# ---------------------------------------------------------------------
def check(name, idx, xs, ys, zs, hilbert_adjacency=False):
    """A curve that is not a permutation is not a curve."""
    n = idx.size
    assert idx.min() == 0 and idx.max() == n - 1, f"{name}: not a bijection"
    assert np.unique(idx).size == n, f"{name}: collisions"
    if hilbert_adjacency:
        order = np.argsort(idx)
        px, py, pz = xs[order], ys[order], zs[order]
        d = (np.abs(np.diff(px.astype(int)))
             + np.abs(np.diff(py.astype(int)))
             + np.abs(np.diff(pz.astype(int))))
        bad = int((d != 1).sum())
        assert bad == 0, f"{name}: {bad} consecutive pairs are not adjacent"
    return True


def runs_of(sorted_idx):
    """Maximal contiguous runs. Returns (starts, lengths, gaps-before)."""
    brk = np.nonzero(np.diff(sorted_idx) != 1)[0]
    starts = np.concatenate(([0], brk + 1))
    ends = np.concatenate((brk, [sorted_idx.size - 1]))
    return sorted_idx[starts], sorted_idx[ends] - sorted_idx[starts] + 1


def seeks_at_waste(sorted_idx, budgets=(0.10, 0.25, 0.50)):
    """Greedily close the smallest gaps until the waste budget is spent.

    Merging two runs separated by a gap of g costs g wasted cells and
    saves one seek. Closing gaps smallest-first is optimal for "fewest
    seeks within a byte budget", because every merge saves exactly one
    seek regardless of which gap it closes.
    """
    starts, lens = runs_of(sorted_idx)
    want = sorted_idx.size
    gaps = np.sort(starts[1:] - (starts[:-1] + lens[:-1]))
    csum = np.cumsum(gaps)
    out = []
    for b in budgets:
        allowed = want * b
        merges = int(np.searchsorted(csum, allowed, side="right"))
        out.append(len(starts) - merges)
    return len(starts), out


# ---------------------------------------------------------------------
def main():
    g = np.arange(N)
    zz, yy, xx = np.meshgrid(g, g, g, indexing="ij")
    xs, ys, zs = xx.ravel(), yy.ravel(), zz.ravel()

    curves = {}
    for name, fn, adj in (("row-major", rowmajor, False),
                          ("morton", morton, False),
                          ("hilbert", hilbert, True),
                          ("col-morton", column_morton, False),
                          ("col-hilbert", column_hilbert, False)):
        idx = fn(xs, ys, zs)
        check(name, idx, xs, ys, zs, hilbert_adjacency=adj)
        curves[name] = idx.reshape(N, N, N)      # [z][y][x]
    gg = np.arange(N)
    q2, p2 = np.meshgrid(gg, gg, indexing="ij")
    d2 = _h2d(p2.ravel(), q2.ravel())
    o2 = np.argsort(d2)
    st = (np.abs(np.diff(p2.ravel()[o2].astype(int)))
          + np.abs(np.diff(q2.ravel()[o2].astype(int))))
    assert np.unique(d2).size == N * N and int((st != 1).sum()) == 0, \
        "the 2D hilbert is not a hilbert curve"
    print(f"  all five orderings verified over {N}^3 = {N**3:,} cells;"
          f" both hilberts checked cell by cell for adjacency\n")

    rng = np.random.default_rng(SEED)
    # THE WINDOW IS A SLAB, NOT A BALL. Zeta's worlds stand on a floor:
    # you can see a long way sideways and not far up or down. A ball
    # flatters whichever curve treats the three axes alike, which is
    # exactly the assumption under test.
    for label, ry_div in (("ball  (r,r,r)", 1), ("slab  (r,r/3,r)", 3)):
        print(f"  {label}")
        print(f"    {'r':>2s} {'cells':>7s} | "
              + " | ".join(f"{c:>26s}" for c in curves))
        print(f"    {'':>2s} {'':>7s} | "
              + " | ".join(f"{'cold  +10%  +25%  +50%':>26s}" for c in curves))
        for r in RADII:
            ry = max(1, r // ry_div)
            dz, dy, dx = np.meshgrid(np.arange(-r, r + 1),
                                     np.arange(-ry, ry + 1),
                                     np.arange(-r, r + 1), indexing="ij")
            ball = ((dx / r) ** 2 + (dy / ry) ** 2 + (dz / r) ** 2) <= 1.0
            odz, ody, odx = dz[ball], dy[ball], dx[ball]
            ncell = odz.size
            acc = {c: np.zeros(4) for c in curves}
            for _ in range(SAMPLES):
                cx, cy, cz = rng.integers(r, N - r, 3)
                px, py, pz = (cx + odx) % N, (cy + ody) % N, (cz + odz) % N
                for c, table in curves.items():
                    s = np.sort(table[pz, py, px])
                    cold, budg = seeks_at_waste(s)
                    acc[c] += [cold] + budg
            cells = f"{ncell:,}"
            row = f"    {r:2d} {cells:>7s} | "
            row += " | ".join(
                "  ".join(f"{v/SAMPLES:5.0f}" for v in acc[c])
                for c in curves)
            print(row)
        print()

    # ---- THE WORLD STANDS ON A FLOOR --------------------------------
    # The cube above is the wrong model and the identical column figures
    # are the proof: with 64 cells of height the window never takes a
    # whole column, so every column is its own run no matter what curve
    # orders them, and all three column schemes collapse onto row-major.
    #
    # A Zeta world is a FLOOR with a few cells of headroom. The window is
    # then a DISC of radius r taking the FULL height -- and that is when
    # a column ordering means anything, because a column is one run by
    # construction. The 3D curves are ranked densely over the cells that
    # EXIST, since cells above the ceiling are not on the card and a gap
    # you never stored is not a gap you pay for.
    H = 8
    print(f"  the floor-bound world: {N} x {H} x {N} cells, and the window"
          f" is a DISC of radius r taking the whole height\n")
    zz2, yy2, xx2 = np.meshgrid(g, np.arange(H), g, indexing="ij")
    fx, fy, fz = xx2.ravel(), yy2.ravel(), zz2.ravel()
    dense = {}
    for name, fn in (("row-major", rowmajor), ("morton", morton),
                     ("hilbert", hilbert), ("col-morton", column_morton),
                     ("col-hilbert", column_hilbert)):
        raw = fn(fx, fy, fz)
        rank = np.empty(raw.size, np.int64)
        rank[np.argsort(raw, kind="stable")] = np.arange(raw.size)
        t = np.empty((N, H, N), np.int64)
        t[fz, fy, fx] = rank
        dense[name] = t
    print(f"    {'r':>2s} {'cells':>7s} | "
          + " | ".join(f"{c:>26s}" for c in dense))
    print(f"    {'':>2s} {'':>7s} | "
          + " | ".join(f"{'cold  +10%  +25%  +50%':>26s}" for c in dense))
    for r in RADII:
        ddz, ddy, ddx = np.meshgrid(np.arange(-r, r + 1), np.arange(H),
                                    np.arange(-r, r + 1), indexing="ij")
        disc = (ddx ** 2 + ddz ** 2) <= r * r
        ez, ey, ex = ddz[disc], ddy[disc], ddx[disc]
        acc = {c: np.zeros(4) for c in dense}
        for _ in range(SAMPLES):
            cx, cz = rng.integers(r, N - r, 2)
            px, pz = (cx + ex) % N, (cz + ez) % N
            for c, table in dense.items():
                srt = np.sort(table[pz, ey, px])
                cold, budg = seeks_at_waste(srt)
                acc[c] += [cold] + budg
        print(f"    {r:2d} {ez.size:>7,} | " + " | ".join(
            "  ".join(f"{v/SAMPLES:5.0f}" for v in acc[c]) for c in dense))
    print()

    # ---- THE STEP: what one cell of movement costs ------------------
    print("  one step of the player: cells entering the window, and the"
          " runs they form")
    print(f"    {'r':>2s} {'new':>5s} | "
          + " | ".join(f"{c:>12s}" for c in curves))
    for r in RADII:
        ry = max(1, r // 3)
        dz, dy, dx = np.meshgrid(np.arange(-r, r + 1), np.arange(-ry, ry + 1),
                                 np.arange(-r, r + 1), indexing="ij")
        ball = ((dx / r) ** 2 + (dy / ry) ** 2 + (dz / r) ** 2) <= 1.0
        odz, ody, odx = dz[ball], dy[ball], dx[ball]
        acc = {c: 0.0 for c in curves}
        nnew = 0.0
        for _ in range(SAMPLES):
            cx, cy, cz = rng.integers(r + 1, N - r - 1, 3)
            for c, table in curves.items():
                was = set(table[(cz + odz) % N, (cy + ody) % N,
                                (cx + odx) % N].tolist())
                now = table[(cz + odz) % N, (cy + ody) % N,
                            (cx + 1 + odx) % N]
                fresh = np.sort(np.array(sorted(set(now.tolist()) - was),
                                         dtype=np.int64))
                if fresh.size:
                    acc[c] += len(runs_of(fresh)[0])
                    if c == "morton":
                        nnew += fresh.size
        print(f"    {r:2d} {nnew/SAMPLES:5.0f} | "
              + " | ".join(f"{acc[c]/SAMPLES:12.1f}" for c in curves))


if __name__ == "__main__":
    main()
