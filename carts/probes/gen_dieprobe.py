#!/usr/bin/env python3
"""gen_dieprobe.py -- writes carts/probes/dieprobe.zol: does the second die answer?

Build 105 enables the second 64 Mbit die of each Pocket CRAM chip (bit 22
of the half address picks it), doubling the cart segment. The sims model
a second die that refuses a burst before its own BCR is programmed; only
glass can say the real dies agree.

Five regions of 64 words, each filled with a pattern that is a function
of its absolute segment offset (so a region read from the WRONG place --
the other die, a folded address -- cannot pass by accident):

    bar 1  offset 1,000          die 0, low
    bar 2  offset 1,990,000      die 0, its top
    bar 3  offset 2,000,000      die 1, its bottom (the first rows past
                                 the boundary)
    bar 4  offset 3,000,000      die 1, middle
    bar 5  offset 4,063,000      die 1, the top of the new ceiling

Each frame the mover brings one region (round robin, both requests) and
the cart compares it word by word against the pattern computed in code.
A bar is GREEN while its region has always matched and RED once it ever
missed; it is GREY until first checked. Bars 1-2 are the control: if they
go red, the probe -- not the die -- is wrong.

    python3 carts/probes/gen_dieprobe.py     (then stage it as the cart instead
                                       of the column, and look)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import carts as _carts                         # noqa: E402
_carts.on_path()                 # sibling generators, wherever they live
from zeta import spec                                    # noqa: E402
from zeta.forge import Cart, Table                       # noqa: E402

REGIONS = (1_000, 1_990_000, 2_000_000, 3_000_000, 4_063_000)
N = 64
assert REGIONS[-1] + N <= spec.CRAM_WORDS


def phys(off):
    """a segment word's physical half address (cram_fb.v's restride)"""
    lg = spec.CRAM_CART_BASE + 2 * off
    return lg + 2 * (lg // 126)


assert phys(REGIONS[1] + N) < 1 << 22 <= phys(REGIONS[2]), "the bars straddle the die"


def pat(off):
    """a word that names its own offset, hashed so neighbours differ in
    every byte -- and computable by the cart with a multiply and an xor"""
    return ((off * 2654435761) ^ (off << 7)) & 0xFFFFFFFF


cart = Cart("dieprobe")
# the segment: the five regions, nothing between (the forge packs CRAM
# sequentially, so pad with explicit tables to the exact offsets)
at = 1
for k, base in enumerate(REGIONS):
    if base > at:
        cart.cram(Table([0] * (base - at)), f"gap{k}")
    cart.cram(Table([pat(base + i) for i in range(N)]), f"region{k}")
    at = base + N
cart.cram(Table([0] * 16), "tail")      # past the last region: the boot
                                         # tail flush race (test_movers)
BUF = cart.var("buf", 2 * N)             # request 1 lands here, request 2 after
OK = cart.data(Table([2] * len(REGIONS)), "ok")      # 2 unchecked, 1 good, 0 bad
R = cart.var("r")                        # which region the PREVIOUS frame asked for
I = cart.var("i")
W = cart.var("w")
p = cart.program()

# ---- check what last frame's request delivered (both copies) -------------
chk = p.label("chk")
p.load(0).emit(f"jz {chk}_skip")         # frame 0: nothing has landed yet
p.set(I, 0)
p.mark(chk)
# expected = pat(REGIONS[r] + (i mod N)); computed with the same arithmetic
p.push(int(cart.data(Table(list(REGIONS)), "regions"))).load(R).emit("add", "loadi")
p.load(I).push(N - 1).emit("and", "add").store(W)                # off
p.load(W).push32(2654435761).emit("mul").load(W).emit("shl 7", "xor")   # expected
p.push(int(BUF)).load(I).emit("add", "loadi")                    # got
p.emit("eq", f"jz {chk}_bad")
p.addi(I, 1)
p.load(I).push(2 * N).emit("lt", f"jz {chk}_good", f"jmp {chk}")
p.mark(f"{chk}_bad")
p.push(0).push(int(OK)).load(R).emit("add", "storei").emit(f"jmp {chk}_skip")
p.mark(f"{chk}_good")
gd = p.label("gd")
p.push(int(OK)).load(R).emit("add", "loadi", f"jz {gd}")         # once bad: stays
p.push(1).push(int(OK)).load(R).emit("add", "storei")
p.mark(gd)
p.mark(f"{chk}_skip")

# ---- next region: both requests, the same 64 words twice ------------------
p.load(R).push(1).emit("add", "dup").push(len(REGIONS)).emit("lt", f"jz {chk}_w0")
p.emit(f"jmp {chk}_w1")
p.mark(f"{chk}_w0")
p.emit("drop").push(0)
p.mark(f"{chk}_w1")
p.store(R)
regs = int(cart.data(Table([REGIONS[k] for k in range(len(REGIONS))]), "srcs"))
for cells, dst in (((spec.DMA_SRC, spec.DMA_DST, spec.DMA_LEN, spec.DMA_GO), int(BUF)),
                   ((spec.DMA2_SRC, spec.DMA2_DST, spec.DMA2_LEN, spec.DMA2_GO), int(BUF) + N)):
    p.push(regs).load(R).emit("add", "loadi").store(cells[0])
    p.set(cells[1], dst).set(cells[2], N).set(cells[3], 1)

# ---- the bars: five rectangles of the display list --------------------------
p.set(spec.DL_BASE, 2 * len(REGIONS))
for k in range(len(REGIONS)):
    x0, x1, y0, y1 = 30 + 54 * k, 30 + 54 * k + 44, 100, 190
    base = spec.DL_BASE + 1 + 14 * k
    for t, tri in enumerate(((x0, y0, x1, y0, x0, y1), (x1, y0, x1, y1, x0, y1))):
        for j, v in enumerate(tri):
            p.set(base + 7 * t + j, v)
        sel = p.label("c")
        p.push(int(OK) + k).emit("loadi", "dup", f"jz {sel}_r")
        p.push(2).emit("eq", f"jz {sel}_g")
        p.push(0x606060).emit(f"jmp {sel}_s")
        p.mark(f"{sel}_g")
        p.push(0x20C040).emit(f"jmp {sel}_s")
        p.mark(f"{sel}_r")
        p.emit("drop").push32(0xE02020)
        p.mark(f"{sel}_s")
        p.store(base + 7 * t + 6)
p.emit("halt")

# the gaps are zeros, which the segment already is: write the cart SPARSE
# (an all-zero .cram line says nothing), 12.8 MB of padding down to KB
out = [ln for ln in cart.lines()
       if not (ln.startswith(".cram ") and set(ln.split()[2:]) == {"0"})]
(HERE / "dieprobe.zol").write_text("\n".join(out) + "\n")
print(cart.report())
