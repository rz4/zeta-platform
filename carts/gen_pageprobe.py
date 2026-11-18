#!/usr/bin/env python3
"""gen_pageprobe.py -- writes carts/pageprobe.zol: the paging discriminator.

The ledger so far. v1 (boot 51): big, small, and repeated requests all
deliver IDENTICAL, DETERMINISTIC words that disagree with the golden.
v2 (boots 51-52): the damage is the LAST WORD of every 64-word unit --
30 hits, first at word 63, holding the NEXT unit's first half doubled
({97EC,97EC}, donor word 64 lo) -- and build 52's write-side margins
(close-hold 5, recovery 7) changed NOTHING, bit-identical readings.

That acquits analog timing and exposes v1's overreach: request size
was varied but the machine chunks EVERY request into 64-word mover
units, so a read-side law striking each unit's last word corrupts all
cadences identically. Write flushes are ALSO 64-word banks at the same
absolute positions. The two suspects perfectly overlap -- so far.

v3 separates them by SHIFTING THE CHUNK GEOMETRY: A pages src=0 (unit
boundaries at absolute words 63, 127, ...); B pages src=2 (unit
boundaries move to 65, 129, ...; the boot-time write flush banks stay
at 63, 127, ...). Where the hits go names the culprit:

    hits stay at 63,127 in BOTH    write side (content corrupt in CRAM)
    B's hits move to 65,129        READ side: each mover unit's tail
    B clean entirely               read side, phase-sensitive (the src
                                   shift also moved the row phase)

Two 31-cell maps (A above B, y=96/y=112), green/red per 62-word block.
Six bit rows:
    1  bits 7:0 LOADER_BUILD | bits 15:8 A mismatch count (caps 255)
    2  B mismatch count
    3  first bad word index in A
    4  first bad word index in B
    5  A's value at its first bad word, low 16
    6  B's value at its first bad word, low 16
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import meshtool, spec                # noqa: E402

DL = spec.DL_BASE
SIG = spec.LOADER_SIG

A_AT, B_AT, GOLD_AT = 900, 2900, 4900
BOFF = 2                    # B's source shift, in words

# cells (block 46, the probes' home)
ACNT, BCNT2, AFIX, BFIX, AGOT, BGOT, PH, KK, NN, BLK, BCT, BBAD = (
    11790 + i for i in range(12))
S1, S2, S3, S4, S5, S6 = (11802 + i for i in range(6))
BR, BV, BI = 11808, 11809, 11780   # bitsc scratch, disjoint from all
VT = 11810
ROWS = [S1, S2, S3, S4, S5, S6]

C_ONE, C_OFF = 0xEEEEEE, 0x2A2A33
C_OK, C_BAD, C_DARK = 0x00CC44, 0xEE2222, 0x333344
T_BITS = 0
T_MAPA = T_BITS + len(ROWS) * 16
NBLK, BLKW = 31, 62
T_MAPB = T_MAPA + NBLK
NTRI = T_MAPB + NBLK


def rgb_addr(t):
    return DL + 7 + t * 7


def main():
    import json
    import subprocess
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys, json; sys.path.insert(0, sys.argv[1]);"
         "from zeta.assets import bunny;"
         "print(json.dumps([bunny._raw_vertices(), bunny._raw_faces()]))",
         str(HERE.parent.parent / "zeta/src")],
        capture_output=True, text=True, check=True)
    bverts, bfaces = json.loads(out.stdout)
    blocks = meshtool.bake(bverts, bfaces, tint=(225, 210, 195),
                           height=1.6, gouraud=True, max_words=4200)
    words = [w & 0xFFFFFFFF for w in blocks[0]]
    n = len(words)
    nb = n - BOFF
    assert n == NBLK * BLKW, n
    assert GOLD_AT + n <= 11780, GOLD_AT + n

    def s32(v):
        return v if v < 0x80000000 else v - 0x100000000

    data = [f".data {spec.OL_BASE} 0"]
    for o in range(0, n, 16):
        vals = " ".join(str(s32(w)) for w in words[o:o + 16])
        data.append(f".cram {o} {vals}")
        data.append(f".data {GOLD_AT + o} {vals}")

    P = ["load 0", "jz init", "jmp main", "init:"]
    for r, cell in enumerate(ROWS):
        P += [f"push {cell}", f"store {VT + r}"]
    # bit-row geometry (rows at y=140), the monitor's proven layout
    P += ["push 0", f"store {AFIX}", "bgr:",
          "push 0", f"store {KK}", "bgi:",
          f"load {AFIX}", "push 16", "mul", f"load {KK}", "add",
          f"push {T_BITS}", "add",
          "push 7", "mul", f"push {DL + 1}", "add", f"store {AGOT}",
          f"load {KK}", "push 15", "mul", "push 6", "add",
          f"store {NN}",
          f"load {KK}", "shr 2", "push 6", "mul", f"load {NN}", "add",
          f"store {NN}"]
    for off, kind in ((0, "x"), (1, "y"), (2, "xw"), (3, "y"),
                      (4, "x"), (5, "yh")):
        if kind == "x":
            P += [f"load {NN}"]
        elif kind == "xw":
            P += [f"load {NN}", "push 12", "add"]
        elif kind == "y":
            P += [f"load {AFIX}", "push 24", "mul", "push 140", "add"]
        else:
            P += [f"load {AFIX}", "push 24", "mul", "push 154", "add"]
        P += [f"load {AGOT}", f"push {off}", "add", "storei"]
    P += [f"load {KK}", "push 1", "add", f"store {KK}",
          f"load {KK}", "push 16", "lt", "jz bgi_end", "jmp bgi",
          "bgi_end:",
          f"load {AFIX}", "push 1", "add", f"store {AFIX}",
          f"load {AFIX}", f"push {len(ROWS)}", "lt", "jz bgr_end",
          "jmp bgr", "bgr_end:"]
    # the two block maps: A at y=96, B at y=112
    for base_t, ytop in ((T_MAPA, 96), (T_MAPB, 112)):
        P += ["push 0", f"store {KK}", f"mg{base_t}:",
              f"load {KK}", f"push {base_t}", "add",
              "push 7", "mul", f"push {DL + 1}", "add", f"store {AGOT}",
              f"load {KK}", "push 9", "mul", "push 6", "add",
              f"store {NN}"]
        for off, kind in ((0, "x"), (1, "y"), (2, "xw"), (3, "y"),
                          (4, "x"), (5, "yh")):
            if kind == "x":
                P += [f"load {NN}"]
            elif kind == "xw":
                P += [f"load {NN}", "push 7", "add"]
            elif kind == "y":
                P += [f"push {ytop}"]
            else:
                P += [f"push {ytop + 10}"]
            P += [f"load {AGOT}", f"push {off}", "add", "storei"]
        P += [f"push {C_DARK}", f"load {KK}", "push 7", "mul",
              f"push {rgb_addr(base_t)}", "add", "storei",
              f"load {KK}", "push 1", "add", f"store {KK}",
              f"load {KK}", f"push {NBLK}", "lt", "jz mg{0}e".format(base_t),
              f"jmp mg{base_t}", f"mg{base_t}e:"]
    P += [f"push {NTRI}", f"store {DL}"]
    for c in (ACNT, BCNT2, AFIX, BFIX, AGOT, BGOT, PH, KK, NN, BLK,
              BCT, BBAD):
        P += ["push 0", f"store {c}"]

    P += ["main:"]
    # ---- frame 1: A = src 0; frame 2: B = src BOFF ---------------------
    P += ["load 0", "push 1", "eq", "jz nq1",
          "push 0", f"store {spec.DMA_SRC}",
          f"push {A_AT}", f"store {spec.DMA_DST}",
          f"push {n}", f"store {spec.DMA_LEN}",
          "push 1", f"store {spec.DMA_GO}", "jmp rend",
          "nq1:",
          "load 0", "push 2", "eq", "jz nq2",
          f"push {BOFF}", f"store {spec.DMA_SRC}",
          f"push {B_AT}", f"store {spec.DMA_DST}",
          f"push {nb}", f"store {spec.DMA_LEN}",
          "push 1", f"store {spec.DMA_GO}", "jmp rend",
          "nq2:",
          "load 0", "push 3", "lt", "jz an_go", "jmp rend",
          "an_go:",
          f"load {PH}", "push 2", "lt", "jz rend",
          "push 0", f"store {NN}",
          f"load {PH}", "jz cmpa", "jmp cmpb"]

    # ---- phase 0: A[k] vs GOLD[k], map to T_MAPA ------------------------
    P += ["cmpa:",
          f"push {A_AT}", f"load {KK}", "add", "loadi",
          f"push {GOLD_AT}", f"load {KK}", "add", "loadi",
          "eq", "jz a_ne", "jmp a_nx",
          "a_ne:",
          "push 1", f"store {BBAD}",
          f"load {ACNT}", "push 1", "add", f"store {ACNT}",
          f"load {ACNT}", "push 1", "eq", "jz a_nx",
          f"load {KK}", f"store {AFIX}",
          f"push {A_AT}", f"load {KK}", "add", "loadi", f"store {AGOT}",
          "a_nx:",
          f"load {BCT}", "push 1", "add", f"store {BCT}",
          f"load {BCT}", f"push {BLKW}", "eq", "jz a_bk",
          f"load {BBAD}", "jz a_gd",
          f"push {C_BAD}", "jmp a_pt",
          "a_gd:", f"push {C_OK}",
          "a_pt:",
          f"load {BLK}", "push 7", "mul", f"push {rgb_addr(T_MAPA)}",
          "add", "storei",
          "push 0", f"store {BCT}", "push 0", f"store {BBAD}",
          f"load {BLK}", "push 1", "add", f"store {BLK}",
          "a_bk:",
          f"load {KK}", "push 1", "add", f"store {KK}",
          f"load {KK}", f"push {n}", "eq", "jz a_mr",
          "push 1", f"store {PH}", "push 0", f"store {KK}",
          "push 0", f"store {BLK}", "push 0", f"store {BCT}",
          "push 0", f"store {BBAD}", "jmp rend",
          "a_mr:",
          f"load {NN}", "push 1", "add", f"store {NN}",
          f"load {NN}", "push 384", "lt", "jz rend", "jmp cmpa"]

    # ---- phase 1: B[k] vs GOLD[k+BOFF], map to T_MAPB -------------------
    P += ["cmpb:",
          f"push {B_AT}", f"load {KK}", "add", "loadi",
          f"push {GOLD_AT + BOFF}", f"load {KK}", "add", "loadi",
          "eq", "jz b_ne", "jmp b_nx",
          "b_ne:",
          "push 1", f"store {BBAD}",
          f"load {BCNT2}", "push 1", "add", f"store {BCNT2}",
          f"load {BCNT2}", "push 1", "eq", "jz b_nx",
          f"load {KK}", f"store {BFIX}",
          f"push {B_AT}", f"load {KK}", "add", "loadi", f"store {BGOT}",
          "b_nx:",
          f"load {BCT}", "push 1", "add", f"store {BCT}",
          f"load {BCT}", f"push {BLKW}", "eq", "jz b_bk",
          f"load {BBAD}", "jz b_gd",
          f"push {C_BAD}", "jmp b_pt",
          "b_gd:", f"push {C_OK}",
          "b_pt:",
          f"load {BLK}", "push 7", "mul", f"push {rgb_addr(T_MAPB)}",
          "add", "storei",
          "push 0", f"store {BCT}", "push 0", f"store {BBAD}",
          f"load {BLK}", "push 1", "add", f"store {BLK}",
          "b_bk:",
          f"load {KK}", "push 1", "add", f"store {KK}",
          f"load {KK}", f"push {nb}", "eq", "jz b_mr",
          f"load {BCT}", "jz b_fin",     # the final partial block gets
          f"load {BBAD}", "jz b_fg",     # its verdict too
          f"push {C_BAD}", "jmp b_fp",
          "b_fg:", f"push {C_OK}",
          "b_fp:",
          f"load {BLK}", "push 7", "mul", f"push {rgb_addr(T_MAPB)}",
          "add", "storei",
          "b_fin:",
          "push 2", f"store {PH}", "jmp rend",
          "b_mr:",
          f"load {NN}", "push 1", "add", f"store {NN}",
          f"load {NN}", "push 384", "lt", "jz rend", "jmp cmpb"]

    # ---- stage the rows and render --------------------------------------
    P += ["rend:",
          f"push {SIG + 7}", "loadi", "push 0xFF", "and", f"store {S1}",
          f"load {ACNT}", "push 255", "lt", "jz ac_cap",
          f"load {ACNT}", "shl 8", f"load {S1}", "or", f"store {S1}",
          "jmp ac_d",
          "ac_cap:", f"load {S1}", "push 0xFF00", "or", f"store {S1}",
          "ac_d:",
          f"load {BCNT2}", "push 0xFFFF", "and", f"store {S2}",
          f"load {AFIX}", "push 0xFFFF", "and", f"store {S3}",
          f"load {BFIX}", "push 0xFFFF", "and", f"store {S4}",
          f"load {AGOT}", "push 0xFFFF", "and", f"store {S5}",
          f"load {BGOT}", "push 0xFFFF", "and", f"store {S6}",
          "call bitsc", "halt"]

    # the probes' proven bit renderer, on its own scratch
    P += ["bitsc:", "push 0", f"store {BR}", "bcr:",
          f"push {VT}", f"load {BR}", "add", "loadi", "loadi", "shl 16",
          f"store {BV}",
          "push 0", f"store {BI}", "bci:",
          f"load {BV}", "push 0", "lt", "jz bc_zero",
          f"push {C_ONE}", "jmp bc_put",
          "bc_zero:", f"push {C_OFF}",
          "bc_put:",
          f"load {BR}", "push 16", "mul", f"load {BI}", "add", "push 7",
          "mul", f"push {rgb_addr(T_BITS)}", "add", "storei",
          f"load {BV}", "shl 1", f"store {BV}",
          f"load {BI}", "push 1", "add", f"store {BI}",
          f"load {BI}", "push 16", "lt", "jz bc_iend", "jmp bci",
          "bc_iend:",
          f"load {BR}", "push 1", "add", f"store {BR}",
          f"load {BR}", f"push {len(ROWS)}", "lt", "jz bc_rend",
          "jmp bcr",
          "bc_rend:", "ret"]

    head = ["; pageprobe.zol -- shifted-chunk paging discriminator (v3)",
            "; GENERATED -- edit gen_pageprobe.py, not this."]
    (HERE / "pageprobe.zol").write_text("\n".join(head + data + P))
    print(f"wrote pageprobe.zol v3: A src=0 len={n}, B src={BOFF} "
          f"len={nb}, two {NBLK}-block maps, {NTRI} triangles")


if __name__ == "__main__":
    main()
