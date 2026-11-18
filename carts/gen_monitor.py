#!/usr/bin/env python3
"""gen_monitor.py -- writes carts/monitor.zol: the memory monitor.

The hidden task of the Zeta (named on the night of boot 48): machine 3
-- the glass -- needs a residue instrument that answers questions as
fast as a human can type, not as fast as Quartus can fit. This cart is
that instrument: a pad-driven address cursor over DMEM and the cart's
CRAM segment, with the word under the cursor rendered as bit rows.
A new question costs two button presses, not a compile and a mount.

Controls (pad bits: 1=up 2=down 4=left 8=right 16=A 32=B) -- ALL
edge-triggered: one tap is exactly one action, holds do nothing more
(v1's 15 Hz repeat made exact positioning a reflex game; an
instrument must not care how long a human holds a button):
    right / left     cursor +1 / -1     (x16 while A held)
    up / down        cursor +64 / -64   (x16 while A held)
    B (tap)          NEXT WAYPOINT -- a preset tour, deterministic
                     from any fresh boot: tap B exactly N times and
                     you are at stop N, confirmed by row 1:
                       0: DMEM 0        4: CRAM 63
                       1: CRAM 0        5: CRAM 64
                       2: CRAM 1        6: CRAM 126
                       3: CRAM 62       7: CRAM 127

CRAM view pages the 64-word window around the cursor through the
MOVER every frame -- so browsing the segment is also a live, standing
exercise of the exact machinery the read-law hunt convicted; word 63
of any window shows the current truth of the row-tail on real glass.

The six bit rows (white = 1, MSB left):
    1  cursor address, low 16 bits
    2  value at cursor, low half
    3  value at cursor, high half
    4  value at cursor+1, low half
    5  value at cursor+1, high half
    6  status: bit15 = view (1 = CRAM), bits 12..8 = cursor bits 20..16,
       bits 7..0 = LOADER_BUILD (which core answers)

The cart carries the probe's 256-word TAG segment (word i = 0x5A0000+i)
so CRAM view over words 0..255 has a known-truth reference.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import spec                          # noqa: E402

DL = spec.DL_BASE
SIG = spec.LOADER_SIG
SEG_TAG = 0x5A0000
SCRATCH = 15616                                # the CRAM window landing

# scratch cells (block 46, skipped by nothing -- the monitor owns them)
ADDRC, MODE, PREV, V, R, I, STEP = (11790 + i for i in range(7))
NEG1, NEG64, WPIX = 11797, 11798, 11799
WPT = 11820                                    # waypoint table, 8 pairs
WAYPOINTS = [(0, 0), (1, 0), (1, 1), (1, 62), (1, 63), (1, 64),
             (1, 126), (1, 127)]               # (mode, addr)
S_A, S_VL, S_VH, S_NL, S_NH, S_ST = (11800 + i for i in range(6))
VT = 11810
ROWS = [S_A, S_VL, S_VH, S_NL, S_NH, S_ST]

C_ONE, C_OFF = 0xEEEEEE, 0x2A2A33
T_BITS = 0
NTRI = T_BITS + len(ROWS) * 16


def rgb_addr(t):
    return DL + 7 + t * 7


def _quad(w, h):
    """Emit tri geometry for the triangle whose slot address is in
    ADDRC-style cell usage -- borrowed shape from the probe (uses V as
    the DL cursor cell)."""
    out = []
    for off, expr in enumerate(("x", "y", "xw", "y", "x", "yh")):
        out += [f"load {V}", f"push {off}", "add"]
        if expr == "x":
            out += [f"load {STEP}"]
        elif expr == "xw":
            out += [f"load {STEP}", f"push {w}", "add"]
        elif expr == "y":
            out += [f"load {R}"]
        else:
            out += [f"load {R}", f"push {h}", "add"]
        out += ["swap", "storei"] if False else []
    return out


def main():
    data = []
    data.append(f".data {spec.OL_BASE} 0")
    data.append(f".data {NEG1} -1")
    data.append(f".data {NEG64} -64")
    for i, (md, ad) in enumerate(WAYPOINTS):
        data.append(f".data {WPT + i * 2} {md}")
        data.append(f".data {WPT + i * 2 + 1} {ad}")
    # the TAG segment: word i = SEG_TAG + i, 256 words
    for o in range(0, 256, 16):
        vals = " ".join(str(SEG_TAG + o + k) for k in range(16))
        data.append(f".cram {o} {vals}")

    P = ["load 0", "jz init", "jmp main", "init:"]
    # VT table
    for r, cell in enumerate(ROWS):
        P += [f"push {cell}", f"store {VT + r}"]
    # bit-row geometry: row R at y=140+R*24, bit I at x=6+I*15+(I>>2)*6
    P += ["push 0", f"store {R}", "bgr:",
          "push 0", f"store {I}", "bgi:",
          f"load {R}", "push 16", "mul", f"load {I}", "add",
          f"push {T_BITS}", "add",
          "push 7", "mul", f"push {DL + 1}", "add", f"store {V}",
          f"load {I}", "push 15", "mul", "push 6", "add", f"store {STEP}",
          f"load {I}", "shr 2", "push 6", "mul", f"load {STEP}", "add",
          f"store {STEP}"]
    # write the six geometry words: x0 y0 x1 y1 x2 y2 (12 wide, 14 tall)
    geo = [("0", 0), ("1", 1), ("2", 0), ("3", 1), ("4", 0), ("5", 1)]
    for off, kind in ((0, "x"), (1, "y"), (2, "xw"), (3, "y"),
                      (4, "x"), (5, "yh")):
        if kind == "x":
            P += [f"load {STEP}"]
        elif kind == "xw":
            P += [f"load {STEP}", "push 12", "add"]
        elif kind == "y":
            P += [f"load {R}", "push 24", "mul", "push 140", "add"]
        else:
            P += [f"load {R}", "push 24", "mul", "push 154", "add"]
        P += [f"load {V}", f"push {off}", "add", "storei"]
    P += [f"load {I}", "push 1", "add", f"store {I}",
          f"load {I}", "push 16", "lt", "jz bgi_end", "jmp bgi",
          "bgi_end:",
          f"load {R}", "push 1", "add", f"store {R}",
          f"load {R}", f"push {len(ROWS)}", "lt", "jz bgr_end", "jmp bgr",
          "bgr_end:",
          f"push {NTRI}", f"store {DL}",
          "push 0", f"store {ADDRC}", "push 0", f"store {MODE}",
          "push 0", f"store {PREV}", "push 0", f"store {WPIX}"]

    P += ["main:",
          # ---- edges: act only on bits that are DOWN now, UP before ---
          "push 0", f"store {STEP}",
          "load 1", "push 8", "and", "jz n_r",
          f"load {PREV}", "push 8", "and", "jz e_r", "jmp n_r",
          "e_r:", "push 1", f"store {STEP}",
          "n_r:",
          "load 1", "push 4", "and", "jz n_l",
          f"load {PREV}", "push 4", "and", "jz e_l", "jmp n_l",
          "e_l:", f"load {NEG1}", f"store {STEP}",
          "n_l:",
          "load 1", "push 1", "and", "jz n_u",
          f"load {PREV}", "push 1", "and", "jz e_u", "jmp n_u",
          "e_u:", "push 64", f"store {STEP}",
          "n_u:",
          "load 1", "push 2", "and", "jz n_d",
          f"load {PREV}", "push 2", "and", "jz e_d", "jmp n_d",
          "e_d:", f"load {NEG64}", f"store {STEP}",
          "n_d:",
          "load 1", "push 16", "and", "jz n_a",
          f"load {STEP}", "push 16", "mul", f"store {STEP}",
          "n_a:",
          f"load {ADDRC}", f"load {STEP}", "add", f"store {ADDRC}",
          # ---- B edge: next waypoint (deterministic from cold boot) ---
          "load 1", "push 32", "and", "jz b_done",
          f"load {PREV}", "push 32", "and", "jz b_edge", "jmp b_done",
          "b_edge:",
          f"load {WPIX}", "push 1", "add", "push 7", "and",
          f"store {WPIX}",
          f"load {WPIX}", "push 2", "mul", f"push {WPT}", "add",
          "loadi", f"store {MODE}",
          f"load {WPIX}", "push 2", "mul", f"push {WPT + 1}", "add",
          "loadi", f"store {ADDRC}",
          "b_done:",
          "load 1", f"store {PREV}",
          # ---- clamp the cursor to the view's space -------------------
          f"load {MODE}", "jz clamp_d",
          f"load {ADDRC}", "push 0x1FFFFF", "and", f"store {ADDRC}",
          "jmp clamp_done",
          "clamp_d:",
          f"load {ADDRC}", "push 16383", "and", f"store {ADDRC}",
          "clamp_done:",
          # ---- CRAM view: page the cursor's window via the mover ------
          f"load {MODE}", "jz no_page",
          f"load {ADDRC}", "push 0x1FFFC0", "and", f"store {spec.DMA_SRC}",
          f"push {SCRATCH}", f"store {spec.DMA_DST}",
          "push 64", f"store {spec.DMA_LEN}",
          "push 1", f"store {spec.DMA_GO}",
          "no_page:",
          # ---- fetch cursor and neighbor values -----------------------
          f"load {MODE}", "jz fetch_d",
          f"load {ADDRC}", "push 63", "and", f"push {SCRATCH}", "add",
          "loadi", f"store {V}",
          f"load {ADDRC}", "push 1", "add", "push 63", "and",
          f"push {SCRATCH}", "add", "loadi", f"store {STEP}",
          "jmp fetch_done",
          "fetch_d:",
          f"load {ADDRC}", "loadi", f"store {V}",
          f"load {ADDRC}", "push 1", "add", "push 16383", "and",
          "loadi", f"store {STEP}",
          "fetch_done:",
          # ---- stage the six rows -------------------------------------
          f"load {ADDRC}", "push 0xFFFF", "and", f"store {S_A}",
          f"load {V}", "push 0xFFFF", "and", f"store {S_VL}",
          f"load {V}", "shr 16", f"store {S_VH}",
          f"load {STEP}", "push 0xFFFF", "and", f"store {S_NL}",
          f"load {STEP}", "shr 16", f"store {S_NH}",
          f"load {MODE}", "shl 15", f"store {S_ST}",
          f"load {ADDRC}", "shr 16", "push 0x1F", "and", "shl 8",
          f"load {S_ST}", "or", f"store {S_ST}",
          f"push {SIG + 7}", "loadi", "push 0xFF", "and",
          f"load {S_ST}", "or", f"store {S_ST}",
          "call bitsc", "halt"]

    # the probe's proven bit renderer: row r shows dmem[VT[r]] & 0xFFFF
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

    head = ["; monitor.zol -- the memory monitor (see gen_monitor.py)",
            "; GENERATED -- edit gen_monitor.py, not this."]
    (HERE / "monitor.zol").write_text("\n".join(head + data + P))
    print(f"wrote monitor.zol: {len(ROWS)} rows, {NTRI} triangles, "
          f"256-word TAG segment")


if __name__ == "__main__":
    main()
