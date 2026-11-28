"""field.py -- a mock of THE FIELD (docs/ZETA-RECIPROCAL-DESIGN.md, 4.4).

NOT LAW. A first draft of one: a grid of cells that steps by a table,
written so that every operation is one the proposed engine has --

    matter   3 bits a cell. Stepped in blocks of 2 x 2 whose origin
             alternates each step. The four kinds (12 bits) index a
             TABLE; the table answers four kinds and three gate bits.
    gates    COIN    apply only if this block's coin came up
             WARM    apply only if the block's trace is at or above GATE
             COLD    apply only if it is below GATE
    trace    8 bits a cell, of the PLACE: (4t + N + S + E + W) >> 3,
             less DECAY, floored at 0; deposits are added before the step.
    coin     one bit a block from a 16-bit shift register, stepped once a
             block in scan order, seeded once.

No floating point, no order that is not scan order, nothing random that
is not the register. Two runs from one seed must agree to the bit.

    python3 experiments/field/field.py     # field.gif and the numbers in README.md
"""
import hashlib
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
N = 256                                   # the window: 256 x 256 cells
EMPTY, SAND, WATER, STONE, MOSS = 0, 1, 2, 3, 4
COIN, WARM, COLD = 1 << 12, 1 << 13, 1 << 14
GATE, DECAY = 24, 1


# ---- the rule, written once as a function and frozen into a table ---------
def rule(tl, tr, bl, br):
    """One block in, one block and its gates out. This is the CART's part:
    the machine only ever sees the 4,096 words it compiles to."""
    def heavier(a, b):            # may a (above) sink through b (below)?
        return (a == SAND and b in (EMPTY, WATER)) or (a == WATER and b == EMPTY)
    # 1. straight down, both columns at once
    ntl, ntr, nbl, nbr = tl, tr, bl, br
    moved = False
    if heavier(tl, bl):
        ntl, nbl, moved = bl, tl, True
    if heavier(tr, br):
        ntr, nbr, moved = br, tr, True
    if moved:
        return ntl, ntr, nbl, nbr, 0
    # 2. a grain or a drop on something solid slides to the empty side, on the coin
    if tl in (SAND, WATER) and bl != EMPTY and tr == EMPTY and br == EMPTY:
        return EMPTY, tr, bl, tl, COIN
    if tr in (SAND, WATER) and br != EMPTY and tl == EMPTY and bl == EMPTY:
        return tl, EMPTY, tr, br, COIN
    # 3. water levels: a drop beside an empty cell, both resting, swaps on the coin
    if bl == WATER and br == EMPTY and tl == EMPTY and tr == EMPTY:
        return tl, tr, EMPTY, WATER, COIN
    if br == WATER and bl == EMPTY and tl == EMPTY and tr == EMPTY:
        return tl, tr, WATER, EMPTY, COIN
    if tl == WATER and tr == EMPTY and bl != EMPTY and br != EMPTY:
        return EMPTY, WATER, bl, br, COIN
    if tr == WATER and tl == EMPTY and bl != EMPTY and br != EMPTY:
        return WATER, EMPTY, bl, br, COIN
    # 4. moss takes one empty cell that touches STONE -- only where it is
    #    COLD (nobody has looked), and only on the coin. It is a skin on
    #    stone and not a flood: the first draft let moss grow from moss and
    #    it filled the world, watched and unwatched alike, in 1,500 steps.
    cells = [tl, tr, bl, br]
    if STONE in cells:
        for i, c in enumerate(cells):
            if c == EMPTY and any(cells[j] == STONE
                                  for j in ((1, 2), (0, 3), (0, 3), (1, 2))[i]):
                out = list(cells)
                out[i] = MOSS
                return (*out, COIN | COLD)
    return tl, tr, bl, br, 0


def compile_table():
    """4,096 entries of 15 bits: 61,440 bits, six block RAMs exactly."""
    t = np.zeros(4096, np.int64)
    for i in range(4096):
        k = [(i >> s) & 7 for s in (9, 6, 3, 0)]
        a, b, c, d, g = rule(*k)
        t[i] = g | a << 9 | b << 6 | c << 3 | d
    return t


# ---- the machine's part ----------------------------------------------------
class Field:
    def __init__(self, seed=0xACE1):
        self.m = np.zeros((N, N), np.int64)       # matter
        self.t = np.zeros((N, N), np.int64)       # trace
        self.lfsr = seed
        self.steps = 0
        self.table = compile_table()

    def coins(self, n):
        """n bits of a 16-bit shift register (taps 16, 14, 13, 11), one a block."""
        out = np.empty(n, np.int64)
        r = self.lfsr
        for i in range(n):
            bit = (r ^ (r >> 2) ^ (r >> 3) ^ (r >> 5)) & 1
            r = (r >> 1) | (bit << 15)
            out[i] = r & 1
        self.lfsr = r
        return out

    def step(self, deposits=()):
        for y, x, amount in deposits:             # in list order, saturating
            self.t[y, x] = min(255, self.t[y, x] + amount)
        # trace: the place's own slow arithmetic (edges see themselves)
        p = np.pad(self.t, 1, mode="edge")
        self.t = np.maximum(0, ((4 * self.t + p[:-2, 1:-1] + p[2:, 1:-1]
                                 + p[1:-1, :-2] + p[1:-1, 2:]) >> 3) - DECAY)
        # matter: blocks, origin alternating
        o = self.steps & 1
        m = self.m
        tl, tr = m[o:N - o:2, o:N - o:2], m[o:N - o:2, o + 1:N - o + 1:2]
        bl, br = m[o + 1:N - o + 1:2, o:N - o:2], m[o + 1:N - o + 1:2, o + 1:N - o + 1:2]
        if o:                                      # the odd phase leaves a border out
            tl, tr = m[1:N - 1:2, 1:N - 1:2], m[1:N - 1:2, 2:N:2]
            bl, br = m[2:N:2, 1:N - 1:2], m[2:N:2, 2:N:2]
        e = self.table[tl << 9 | tr << 6 | bl << 3 | br]
        coin = self.coins(tl.size).reshape(tl.shape)
        tt = self.t
        warm = (tt[o:o + 2 * tl.shape[0]:2, o:o + 2 * tl.shape[1]:2] >= GATE)
        go = np.ones(tl.shape, bool)
        go &= ((e & COIN) == 0) | (coin == 1)
        go &= ((e & WARM) == 0) | warm
        go &= ((e & COLD) == 0) | ~warm
        new = [np.where(go, (e >> s) & 7, old)
               for s, old in ((9, tl), (6, tr), (3, bl), (0, br))]
        if o:
            m[1:N - 1:2, 1:N - 1:2], m[1:N - 1:2, 2:N:2] = new[0], new[1]
            m[2:N:2, 1:N - 1:2], m[2:N:2, 2:N:2] = new[2], new[3]
        else:
            m[0:N:2, 0:N:2], m[0:N:2, 1:N:2] = new[0], new[1]
            m[1:N:2, 0:N:2], m[1:N:2, 1:N:2] = new[2], new[3]
        self.steps += 1

    def digest(self):
        return hashlib.sha256(self.m.astype(np.uint8).tobytes()
                              + self.t.astype(np.uint8).tobytes()).hexdigest()[:16]


PALETTE = np.array([(10, 10, 20), (214, 180, 110), (60, 110, 220),
                    (110, 112, 128), (60, 170, 80), (0, 0, 0), (0, 0, 0), (0, 0, 0)])


def picture(f):
    """What a page aimed at the field would show: a colour by kind, warmed
    by the top bits of trace (the design's 256-entry colour table)."""
    rgb = PALETTE[f.m].astype(np.int64)
    w = (f.t >> 3)[..., None]
    rgb = np.minimum(255, rgb + w * np.array([6, 2, 0]))
    return rgb.astype(np.uint8)


def world():
    f = Field()
    f.m[N - 1, :] = STONE                               # a floor
    f.m[150, 40:120] = STONE                            # two ledges
    f.m[110, 140:230] = STONE
    f.m[110:150, 140] = STONE                           # a wall, making a basin
    f.m[200:N, 128] = STONE
    f.m[20:60, 60:100] = SAND                           # a block of sand, in the air
    f.m[30:80, 170:210] = WATER                         # and one of water
    return f


def run(frames, gaze=True, keep=None):
    f = world()
    shots = []
    for s in range(frames):
        dep = []
        if gaze:        # where the player keeps looking: the left ledge and
            #             the floor under it, deposited every step
            #             Every cell of it: the first draft deposited on every
            #             fourth cell and two rows off, the trace between
            #             never reached GATE, and the gaze changed nothing
            #             (344 cells of moss watched, 344 unwatched).
            dep = [(y, x, 60) for y in range(147, 154) for x in range(36, 124)]
        f.step(dep)
        if keep and s % keep == 0:
            shots.append(Image.fromarray(picture(f)))
    return f, shots


def main():
    table = compile_table()
    start = world()
    sand0, water0 = int((start.m == SAND).sum()), int((start.m == WATER).sum())
    f, shots = run(1500, keep=10)
    g, _ = run(1500)
    shots[0].save(HERE / "field.gif", save_all=True, append_images=shots[1:],
                  duration=50, loop=0, optimize=True)
    h, _ = run(1500, gaze=False)
    box = (slice(146, 155), slice(36, 124))
    print(f"moss on the watched ledge, watched / not watched: "
          f"{int((f.m[box] == MOSS).sum())} / {int((h.m[box] == MOSS).sum())}")
    moved = int((table != np.array([(i >> 9 & 7) << 9 | (i >> 6 & 7) << 6
                                    | (i >> 3 & 7) << 3 | i & 7
                                    for i in range(4096)])).sum())
    print(f"table: 4,096 x 15 bits = {4096 * 15:,} bits; entries that do anything: {moved:,}")
    print(f"steps: {f.steps}")
    print(f"sand   before / after: {sand0:,} / {int((f.m == SAND).sum()):,}")
    print(f"water  before / after: {water0:,} / {int((f.m == WATER).sum()):,}")
    print(f"moss elsewhere, the same two runs: "
          f"{int((f.m == MOSS).sum() - (f.m[box] == MOSS).sum())} / "
          f"{int((h.m == MOSS).sum() - (h.m[box] == MOSS).sum())}")
    print(f"two runs from one seed: {f.digest()} {g.digest()} {'SAME' if f.digest() == g.digest() else 'DIFFER'}")
    print(f"a step of the window: {2 * N * N:,} words in and out = {2 * N * N / 720000:.1%} of a frame at a word a clock")


if __name__ == "__main__":
    main()
