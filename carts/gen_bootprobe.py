#!/usr/bin/env python3
"""gen_bootprobe.py -- writes carts/bootprobe.zol: the slot-delivery probe.

Boots 16-19 each failed in the gap between what the simulations wrap, and
every diagnosis so far has been inferred from artifacts. This cart makes
the console testify. It carries bunny.zol's ENTIRE data image -- so a
healthy machine renders the bunny and ground behind the overlay, with the
hum playing -- and draws four instruments:

  * an 8x8 grid, one cell per 256-word block of ALL 16384 DMEM words,
    RESCANNED FOREVER (one block per frame, ~1 s per sweep) so it shows
    the machine's CURRENT state, not a first-glance race:
        green = block matches the cart image   blue = block is all zeros
        red   = block holds other data         gray = skipped by design
                                               dark = not yet scanned
    Skipped blocks are the ones this cart writes itself: 0 and 5 and 46,
    47, 60, 63 (probe scratch and the persistence cells) and 48..54 (the
    display list).

  * a bar: green if cart_loader signed this boot with its magic word.

  * six persistence cells: this cart writes a magic value into six cells
    spread across DMEM at frame 1 and rechecks them every frame after.
    Green = still holds it. If a cell goes RED, something is writing to
    DMEM after the console started -- the difference between "the
    signature never arrived" and "the signature was overwritten".

  * six 16-bit rows (white = 1, dark = 0, MSB left, nibble-grouped), the
    loader's own delivery counters:
        1 words accepted from the declared bridge window   (want 20480)
        2 words actually replayed onto the boot port       (want 20480)
        3 of those, carrying zeros                         (want     0)
        4 writes seen in the old low window, now ignored
        5 console clocks (x1024) from power-up to release
        6 LOADER_BUILD -- WHICH core is running this cart
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import asm, spec                     # noqa: E402

NBLK = 64
MASK = 0x7FFFFF                                # sums stay push-able (imm24)
DL = spec.DL_BASE
SIG = spec.LOADER_SIG
SIG2 = spec.LOADER_SIG2
MAGIC = 0x123456

BIDX, ACC, I, ADDR, X, Y, S, K, V, R, T = (11790 + i for i in range(11))
SH0, SH1 = 11801 + 60, 11802 + 60   # decoded high halves (block 46, skipped)
SH2 = 11803 + 60
EXP, RES, SKF, VT, PT = 11810, 11880, 11950, 12020, 12030

PCELLS = [11, 1300, 11780, 12100, 15400, 16360]      # persistence probes
ROWS = [SIG2 + 1,           # words accepted (want 20736)
        SIG2 + 2,           # words replayed into memory (want 20736)
        0, 0, 0, 0]         # seg word 0 lo/hi, word 1 lo/hi (patched)
SKIP = {0, 5, 45, 46, 47, 60, 61, 63} | set(range(48, 55))  # we write

C_OK, C_BAD, C_ZERO = 0x00CC44, 0xEE2222, 0x2266EE
C_SKIP, C_DARK, C_ONE, C_OFF = 0x666677, 0x333344, 0xEEEEEE, 0x2A2A33

SEG_AT, SEG_N, SEG_TAG = 15616, 256, 0x5A0000   # the paged-in
                                    # landing zone (block 61)
T_GRID, T_BAR, T_PERS, T_BITS = 0, 0, 4, 10   # grid dropped;
# persistence squares keep their 6 slots (cheap, informative)
T_SEG = T_BITS + len(ROWS) * 16     # the segment verdict bar
T_MAP = T_SEG + 2                   # 128 cells, one per WORD PAIR --
NTRI = T_MAP + 128                  # the DL caps at 256 triangles, so
                                    # the 64-block grid and persistence
                                    # rows are dropped this build


def rgb_addr(t):
    return DL + 7 + t * 7                      # the rgb word of triangle t


def geom(t, x, y, w, h):
    """Fixed geometry for one right triangle, written once at init."""
    a = DL + 1 + t * 7
    out = []
    for off, val in enumerate((x, y, x + w, y, x, y + h)):
        out += [f"push {val}", f"store {a + off}"]
    return out


def main():
    cart = asm.assemble(HERE / "bunny.zol")
    dmem = {int(a): v & 0xFFFFFFFF for a, v in cart["dmem"].items()}
    sums = []
    for b in range(NBLK):
        s = 0
        for w in range(b * 256, b * 256 + 256):
            s = (s + (dmem.get(w, 0) & MASK)) & MASK
        sums.append(s)

    data = [f".data {a} {v if v < 0x80000000 else v - 0x100000000}"
            for a, v in sorted(dmem.items())]
    # no 3D scene: v6's bunny rendered behind the bit rows and its bright
    # pixels read as ON bits in photos. A later .data wins in the
    # assembler, so this single line blanks the inherited object list.
    data.append(f".data {spec.OL_BASE} 0")
    # a CRAM segment with a checkable pattern: word i = SEG_TAG + i
    for o in range(0, SEG_N, 16):
        vals = " ".join(str(SEG_TAG + o + k) for k in range(16))
        data.append(f".cram {o} {vals}")
    # v10: a position-encoded BACKDROP after the probe pattern -- the
    # pump paints CRAM straight to the glass, no mover in the loop, so
    # the screen itself becomes the CRAM dump: red ramps down the
    # frame, green ramps across, an 8px checker carries the phase (any
    # word shift breaks the checker seam), z = far everywhere so the
    # instruments overlay it.
    BG_OFF = 512
    data.append(f".data {spec.BG_SRC} {BG_OFF}")
    for y in range(spec.H):
        row = []
        r5 = (y * 31) // (spec.H - 1)
        for x in range(spec.W):
            g5 = (x * 31) // (spec.W - 1)
            b5 = 26 if (((x >> 3) ^ (y >> 3)) & 1) else 4
            row.append((0xFFFF << 16) | (r5 << 10) | (g5 << 5) | b5)
        for o in range(0, spec.W, 16):
            vals = " ".join(str(v if v < 0x80000000 else v - 0x100000000)
                            for v in row[o:o + 16])
            data.append(f".cram {BG_OFF + y * spec.W + o} {vals}")

    # ---- frame 0: expectations, tables, geometry, persistence magic -----
    P = ["load 0", "jz init", "jmp main", "init:"]
    for b in range(NBLK):
        P += [f"push {sums[b]}", f"store {EXP + b}",
              f"push {1 if b in SKIP else 0}", f"store {SKF + b}",
              "push 0", f"store {RES + b}"]
    # boot 38's null result: rows now testify about THREE flush
    # boundaries -- word 127 (flush-2 end), 128 (flush-3 start),
    # 192 (flush-4 start); delivery counters retired (proven 20736)
    # row 6 shows LOADER_BUILD again -- boots 39/40 read identically and
    # the Pocket caches core+cart across sleep/wake: WHICH machine ran
    # must be on the glass, not assumed
    # v15: the frame-2 SNAPSHOT of word 63 vs its LIVE value -- if they
    # differ, the landing was clean and something rewrites it later
    rows = [SH2 + 1, SH0, SEG_AT + 63, SH1, SEG_AT, SIG + 7]
    for r, cell in enumerate(rows):
        P += [f"push {cell}", f"store {VT + r}"]
    for k, cell in enumerate(PCELLS):
        P += [f"push {cell}", f"store {PT + k}",
              f"push {MAGIC}", f"store {cell}"]

    P += ["jmp gg_end"] if True else []
    P += ["push 0", f"store {K}", "gg:",                  # grid geometry
          f"load {K}", "push 7", "mul", f"push {DL + 1}", "add",
          f"store {ADDR}",
          f"load {K}", "push 7", "and", "push 16", "mul", "push 6", "add",
          f"store {X}",
          f"load {K}", "shr 3", "push 16", "mul", "push 6", "add",
          f"store {Y}"]
    P += _quad(12, 12)
    P += [f"load {K}", "push 1", "add", f"store {K}",
          f"load {K}", f"push {NBLK}", "lt", "jz gg_end", "jmp gg",
          "gg_end:"]

    P += geom(T_SEG, 140, 52, 78, 16) + geom(T_SEG + 1, 218, 68, -78, -16)
    for k in range(128):                 # 32 x 4 pair map
        P += geom(T_MAP + k, 6 + (k % 32) * 6, 96 + (k // 32) * 10, 5, 8)
    P += (geom(T_BAR, 140, 6, 78, 16) + geom(T_BAR + 1, 218, 22, -78, -16)
          + geom(T_BAR + 2, 222, 6, 78, 16)
          + geom(T_BAR + 3, 300, 22, -78, -16))
    for k in range(len(PCELLS)):
        P += geom(T_PERS + k, 140 + k * 20, 30, 14, 14)

    P += ["push 0", f"store {R}", "bgr:",                 # bit-row geometry
          "push 0", f"store {I}", "bgi:",
          f"load {R}", "push 16", "mul", f"load {I}", "add",
          f"push {T_BITS}", "add", f"store {T}",
          f"load {T}", "push 7", "mul", f"push {DL + 1}", "add",
          f"store {ADDR}",
          f"load {I}", "push 15", "mul", "push 6", "add", f"store {X}",
          f"load {I}", "shr 2", "push 6", "mul", f"load {X}", "add",
          f"store {X}",
          f"load {R}", "push 24", "mul", "push 140", "add", f"store {Y}"]
    P += _quad(12, 14)
    P += [f"load {I}", "push 1", "add", f"store {I}",
          f"load {I}", "push 16", "lt", "jz bgi_end", "jmp bgi",
          "bgi_end:",
          f"load {R}", "push 1", "add", f"store {R}",
          f"load {R}", f"push {len(ROWS)}", "lt", "jz bgr_end", "jmp bgr",
          "bgr_end:",
          f"push {NTRI}", f"store {DL}", "push 0", f"store {BIDX}"]

    # ---- every frame -----------------------------------------------------
    P += ["main:",
          # grid + persistence dropped: the pair map takes their triangles
          
          # frame 1: ask the mover for the segment
          "load 0", "push 1", "eq", "jz no_req",
          f"push 0", f"store {spec.DMA_SRC}",
          f"push {SEG_AT}", f"store {spec.DMA_DST}",
          f"push {SEG_N}", f"store {spec.DMA_LEN}",
          "push 1", f"store {spec.DMA_GO}",
          "no_req:",
          # v15: at frame 2, SNAPSHOT the suspect cell -- four identical
          # fingerprints through four different read-path fixes say the
          # frame-1 landing may be innocent and OVERWRITTEN later. The
          # display shows live memory; the snapshot shows history. The
          # v11 leftover requests are gone: they were background noise
          # and suspects both.
          "load 0", "push 2", "eq", "jz no_snap",
          f"push {SEG_AT + 63}", "loadi", f"store {SH2 + 1}",
          "no_snap:",
          "call barc",
          "call bitsc", "call segc",
          # decode the burst-boundary words 63 and 64 high halves
          f"push {SH2 + 1}", "loadi", "shr 16", f"store {SH0}",
          f"push {SEG_AT + 63}", "loadi", "shr 16", f"store {SH1}",
          "call wmap", "halt"]

    # did the segment arrive, and intact? green yes, blue all-zero
    # (never written), red something else
    P += ["segc:", "push 0", f"store {K}", "push 0", f"store {S}",
          "sg:",
          f"push {SEG_AT}", f"load {K}", "add", "loadi",
          f"push {SEG_TAG}", f"load {K}", "add", "eq", "jz sg_bad",
          "jmp sg_next",
          "sg_bad:", f"load {S}", "push 1", "or", f"store {S}",
          f"push {SEG_AT}", f"load {K}", "add", "loadi", "jz sg_next",
          f"load {S}", "push 2", "or", f"store {S}",
          "sg_next:",
          f"load {K}", "push 1", "add", f"store {K}",
          f"load {K}", f"push {SEG_N}", "lt", "jz sg_done", "jmp sg",
          "sg_done:",
          f"load {S}", "jz sg_ok",                    # nothing wrong
          f"load {S}", "push 2", "and", "jz sg_zero",  # only mismatches
          f"push {C_BAD}", "jmp sg_put",
          "sg_zero:", f"push {C_ZERO}", "jmp sg_put",
          "sg_ok:", f"push {C_OK}",
          "sg_put:", "dup", f"store {rgb_addr(T_SEG)}",
          f"store {rgb_addr(T_SEG + 1)}", "ret"]

    P += ["wmap:", "push 0", f"store {K}", "wm:",
          # V = 0 ok so far; word 2K then 2K+1
          "push 0", f"store {V}",
          f"push {SEG_AT}", f"load {K}", "shl 1", "add", "loadi",
          f"push {SEG_TAG}", f"load {K}", "shl 1", "add", "eq",
          "jz wm_b0", "jmp wm_w1",
          "wm_b0:", "push 1", f"store {V}",
          "wm_w1:",
          f"push {SEG_AT}", f"load {K}", "shl 1", "add", "push 1", "add",
          "loadi",
          f"push {SEG_TAG}", f"load {K}", "shl 1", "add", "push 1", "add",
          "eq", "jz wm_b1", "jmp wm_col",
          "wm_b1:", "push 1", f"store {V}",
          "wm_col:",
          f"load {V}", "jz wm_ok",
          f"push {C_BAD}", "jmp wm_put",
          "wm_ok:", f"push {C_OK}",
          "wm_put:",
          f"load {K}", "push 7", "mul", f"push {rgb_addr(T_MAP)}", "add",
          "storei",
          f"load {K}", "push 1", "add", f"store {K}",
          f"load {K}", "push 128", "lt", "jz wm_done", "jmp wm",
          "wm_done:", "ret"]

    P += ["scan:",                            # one block, then advance
          f"push {SKF}", f"load {BIDX}", "add", "loadi", "jz sc_sum",
          "push 4", "jmp sc_put",
          "sc_sum:", "push 0", f"store {ACC}", "push 0", f"store {I}",
          "sloop:",
          f"load {BIDX}", "shl 8", f"load {I}", "add", "loadi",
          f"push {MASK}", "and",
          f"load {ACC}", "add", f"push {MASK}", "and", f"store {ACC}",
          f"load {I}", "push 1", "add", f"store {I}",
          f"load {I}", "push 256", "lt", "jz sc_done", "jmp sloop",
          "sc_done:",
          f"load {BIDX}", f"push {EXP}", "add", "loadi",
          f"load {ACC}", "eq", "jz sc_not",
          "push 1", "jmp sc_put",
          "sc_not:", f"load {ACC}", "jz sc_zero",
          "push 2", "jmp sc_put",
          "sc_zero:", "push 3",
          "sc_put:", f"load {BIDX}", f"push {RES}", "add", "storei",
          f"load {BIDX}", "push 1", "add", f"store {BIDX}",
          f"load {BIDX}", f"push {NBLK}", "lt", "jz sc_wrap", "ret",
          "sc_wrap:", "push 0", f"store {BIDX}", "ret"]

    P += ["gridc:", "push 0", f"store {K}", "gc:",
          f"load {K}", f"push {RES}", "add", "loadi", f"store {S}",
          f"load {S}", "jz gc_dark",
          f"load {S}", "push 1", "eq", "jz gc_n1",
          f"push {C_OK}", "jmp gc_put",
          "gc_n1:", f"load {S}", "push 2", "eq", "jz gc_n2",
          f"push {C_BAD}", "jmp gc_put",
          "gc_n2:", f"load {S}", "push 3", "eq", "jz gc_n3",
          f"push {C_ZERO}", "jmp gc_put",
          "gc_n3:", f"push {C_SKIP}", "jmp gc_put",
          "gc_dark:", f"push {C_DARK}",
          "gc_put:",
          f"load {K}", "push 7", "mul", f"push {rgb_addr(T_GRID)}", "add",
          "storei",
          f"load {K}", "push 1", "add", f"store {K}",
          f"load {K}", f"push {NBLK}", "lt", "jz gc_end", "jmp gc",
          "gc_end:", "ret"]

    P += ["barc:",                          # left bar: the top-of-memory
          "push 0x5A45", "shl 16", "push 0x5441", "or",   # signature
          f"load {SIG}", "eq", "jz bar_bad",
          f"push {C_OK}", "jmp bar_put",
          "bar_bad:", f"push {C_BAD}",
          "bar_put:", "dup", f"store {rgb_addr(T_BAR)}",
          f"store {rgb_addr(T_BAR + 1)}",
          "push 0x5A45", "shl 16", "push 0x5441", "or",   # right bar: the
          f"load {SIG2}", "eq", "jz bar2_bad",            # mirror
          f"push {C_OK}", "jmp bar2_put",
          "bar2_bad:", f"push {C_BAD}",
          "bar2_put:", "dup", f"store {rgb_addr(T_BAR + 2)}",
          f"store {rgb_addr(T_BAR + 3)}", "ret"]

    P += ["persc:", "push 0", f"store {K}", "pc:",
          f"push {PT}", f"load {K}", "add", "loadi", "loadi",
          f"push {MAGIC}", "eq", "jz pc_bad",
          f"push {C_OK}", "jmp pc_put",
          "pc_bad:", f"push {C_BAD}",
          "pc_put:",
          f"load {K}", "push 7", "mul", f"push {rgb_addr(T_PERS)}", "add",
          "storei",
          f"load {K}", "push 1", "add", f"store {K}",
          f"load {K}", f"push {len(PCELLS)}", "lt", "jz pc_end", "jmp pc",
          "pc_end:", "ret"]

    P += ["bitsc:", "push 0", f"store {R}", "bcr:",
          f"push {VT}", f"load {R}", "add", "loadi", "loadi", "shl 16",
          f"store {V}",
          "push 0", f"store {I}", "bci:",
          f"load {V}", "push 0", "lt", "jz bc_zero",
          f"push {C_ONE}", "jmp bc_put",
          "bc_zero:", f"push {C_OFF}",
          "bc_put:",
          f"load {R}", "push 16", "mul", f"load {I}", "add", "push 7",
          "mul", f"push {rgb_addr(T_BITS)}", "add", "storei",
          f"load {V}", "shl 1", f"store {V}",
          f"load {I}", "push 1", "add", f"store {I}",
          f"load {I}", "push 16", "lt", "jz bc_iend", "jmp bci",
          "bc_iend:",
          f"load {R}", "push 1", "add", f"store {R}",
          f"load {R}", f"push {len(ROWS)}", "lt", "jz bc_rend", "jmp bcr",
          "bc_rend:", "ret"]

    head = ["; bootprobe.zol -- slot-delivery probe (see gen_bootprobe.py)",
            "; GENERATED -- edit gen_bootprobe.py, not this."]
    (HERE / "bootprobe.zol").write_text("\n".join(head + data + P))
    print(f"wrote bootprobe.zol: {NBLK} blocks (rescanned), "
          f"{len(PCELLS)} persistence cells, {len(ROWS)} counter rows, "
          f"{NTRI} triangles")


def _quad(w, h):
    """Write the six coordinate words from X/Y/ADDR (shared by both loops)."""
    return [f"load {X}", f"load {ADDR}", "storei",
            f"load {Y}", f"load {ADDR}", "push 1", "add", "storei",
            f"load {X}", f"push {w}", "add", f"load {ADDR}", "push 2",
            "add", "storei",
            f"load {Y}", f"load {ADDR}", "push 3", "add", "storei",
            f"load {X}", f"load {ADDR}", "push 4", "add", "storei",
            f"load {Y}", f"push {h}", "add", f"load {ADDR}", "push 5",
            "add", "storei"]


if __name__ == "__main__":
    main()
