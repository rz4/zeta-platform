#!/usr/bin/env python3
"""gen_sweep.py -- writes carts/probes/sweep.zol: the write-window probe, v2.

v1's coarse sweep (boot 56, on glass) proved the masks REAL: fat lines
through K=4, thinning 5-6, wide spans full at 7, visible erosion from
8 -- and 1-px spans dying at 7 said the word-0 beat sits exactly at
the window's edge, below the eye's resolution on wide spans.

v2's graded bars asked the eye for arithmetic; v3 asks it for the
one thing it does at hyperacuity: is a straight edge straight.

  * THE VERNIER: two large abutting rectangles sharing one vertical
    edge -- RED left, WHITE right. The white spans' scribbles smear
    white INTO the red (the boundary BULGES left, serrated); masking
    too far makes white recede (RED shows through at the boundary).
    A reversed pair (white left, red right) sits below: its boundary
    moves the OPPOSITE way, disambiguating under- from over-masking.
    Two 1-px white lines remain as the word-0 canary.

  * FINE K CONTROL: dpad right/left steps K by one (edge-triggered).
    Boots at K=6. The K strip and bit row label everything.

Reading protocol, per K, one word per boundary: BULGE (scribble
alive) / RAZOR (clean) / RECEDE (over-masked). The perfect K: both
boundaries razor and the 1-px lines present.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import carts as _carts                         # noqa: E402
_carts.on_path()                 # sibling generators, wherever they live

from zeta import spec                          # noqa: E402

DL = spec.DL_BASE
SIG = spec.LOADER_SIG
WPROBE = 11789
K, V, A, I, PREV = 11790, 11791, 11792, 11793, 11794
ARM = 11798
BR, BV, BI = 11795, 11796, 11797

C_LINE = 0xFFFFFF
C_ON, C_DIM = 0x44EE66, 0x223328
C_ONE, C_OFF = 0xEEEEEE, 0x2A2A33

C_RED = 0xD03030
T_VERN = 0                      # 2 pairs x 2 rects x 2 tris = 8
T_LINES = T_VERN + 8            # 2 one-px lines x 2 tris
T_K = T_LINES + 4
T_BITS = T_K + 16
NTRI = T_BITS + 16


def rgb_addr(t):
    return DL + 7 + t * 7


def tri(t, coords, rgb=None):
    a = DL + 1 + t * 7
    out = []
    for off, val in enumerate(coords):
        out += [f"push {val}", f"store {a + off}"]
    if rgb is not None:
        out += [f"push {rgb}", f"store {a + 6}"]
    return out


def quad(t, x, y, w, h, rgb):
    return (tri(t, (x, y, x + w, y, x, y + h), rgb)
            + tri(t + 1, (x + w, y, x + w, y + h, x, y + h), rgb))


def main():
    data = [f".data {spec.OL_BASE} 0"]
    # the LOAD: a small segment paged by the mover EVERY frame -- the
    # jitter law says steady-state paint measurements lie; the probe
    # must run with refresh and bus pressure in the room
    for o in range(0, 256, 16):
        vals = " ".join(str(0x3C0000 + o + k) for k in range(16))
        data.append(f".cram {o} {vals}")
    P = ["load 0", "jz init", "jmp main", "init:",
         "push 6", f"store {K}", "push 0", f"store {PREV}",
         "push 1", f"store {ARM}"]
    # vernier pair 1: red | white, edge at x=160, y 30..92
    P += quad(T_VERN + 0, 60, 30, 100, 62, C_RED)
    P += quad(T_VERN + 2, 160, 30, 100, 62, C_LINE)
    # vernier pair 2: white | red, edge at x=160, y 100..162
    P += quad(T_VERN + 4, 60, 100, 100, 62, C_LINE)
    P += quad(T_VERN + 6, 160, 100, 100, 62, C_RED)
    # the word-0 canaries
    P += quad(T_LINES + 0, 290, 30, 1, 132, C_LINE)
    P += quad(T_LINES + 2, 30, 170, 1, 20, C_LINE)
    for k in range(16):
        P += tri(T_K + k, (24 + k * 16, 200, 36 + k * 16, 200,
                           24 + k * 16, 212))
    for b in range(16):
        x = 24 + b * 15 + (b >> 2) * 6
        P += tri(T_BITS + b, (x, 240, x + 12, 240, x, 254))
    P += [f"push {NTRI}", f"store {DL}"]

    P += ["main:",
          # dpad edges: right K+1, left K-1, clamped 0..15
          "load 1", "push 8", "and", "jz n_r",
          f"load {PREV}", "push 8", "and", "jz e_r", "jmp n_r",
          "e_r:", f"load {K}", "push 15", "lt", "jz n_r",
          f"load {K}", "push 1", "add", f"store {K}",
          "n_r:",
          "load 1", "push 4", "and", "jz n_l",
          f"load {PREV}", "push 4", "and", "jz e_l", "jmp n_l",
          "e_l:", f"load {K}", "push 0", "eq", "jz kdec", "jmp n_l",
          "kdec:", f"load {K}", "push 1", "sub", f"store {K}",
          "n_l:",
          # B toggles armed (knob-K) vs disarmed (the BAKED lift): the
          # A/B that separates the two RTL paths on one screen
          "load 1", "push 32", "and", "jz n_b",
          f"load {PREV}", "push 32", "and", "jz e_b", "jmp n_b",
          "e_b:", f"load {ARM}", "push 1", "xor", f"store {ARM}",
          "n_b:",
          "load 1", f"store {PREV}",
          # armed: 0x5EEB high, fine bit + K low; disarmed: zero
          f"load {ARM}", "jz disarm",
          "push 0x5EEB", "shl 16", "push 0x8000", "or",
          f"load {K}", "or", f"store {WPROBE}", "jmp armd",
          "disarm:", "push 0", f"store {WPROBE}",
          "armd:",
          # the mover load: 64 words, a walking window, every frame
          "load 0", "push 3", "and", "push 64", "mul",
          f"store {spec.DMA_SRC}",
          "push 11600", f"store {spec.DMA_DST}",
          "push 64", f"store {spec.DMA_LEN}",
          "push 1", f"store {spec.DMA_GO}",
          # K strip (cells turn RED when disarmed = baked path)
          "push 0", f"store {I}", "kc:",
          f"load {I}", f"load {K}", "eq", "jz kc_dim",
          f"load {ARM}", "jz kc_red",
          f"push {C_ON}", "jmp kc_put",
          "kc_red:", f"push {C_RED}", "jmp kc_put",
          "kc_dim:", f"push {C_DIM}",
          "kc_put:",
          f"load {I}", f"push {T_K}", "add", "push 7", "mul",
          f"push {rgb_addr(0)}", "add", "storei",
          f"load {I}", "push 1", "add", f"store {I}",
          f"load {I}", "push 16", "lt", "jz kc_end", "jmp kc",
          "kc_end:",
          # the bit row: build | K<<8
          f"push {SIG + 7}", "loadi", "push 0xFF", "and",
          f"load {K}", "shl 8", "or", "shl 16", f"store {BV}",
          "push 0", f"store {BI}", "bc:",
          f"load {BV}", "push 0", "lt", "jz b_off",
          f"push {C_ONE}", "jmp b_put",
          "b_off:", f"push {C_OFF}",
          "b_put:",
          f"load {BI}", f"push {T_BITS}", "add", "push 7", "mul",
          f"push {rgb_addr(0)}", "add", "storei",
          f"load {BV}", "shl 1", f"store {BV}",
          f"load {BI}", "push 1", "add", f"store {BI}",
          f"load {BI}", "push 16", "lt", "jz b_end", "jmp bc",
          "b_end:", "halt"]

    head = ["; sweep.zol -- the write-window probe v2 (see gen_sweep.py)",
            "; GENERATED -- edit gen_sweep.py, not this."]
    (HERE / "sweep.zol").write_text("\n".join(head + data + P))
    print(f"wrote sweep.zol v3: vernier pairs + canaries, dpad K, "
          f"{NTRI} triangles")


if __name__ == "__main__":
    main()
