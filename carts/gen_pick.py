#!/usr/bin/env python3
"""gen_pick.py -- writes carts/pick.zol: the pick register's demo.

The GPU as a spatial query engine (the user's amendment, legislated at
spec.PICK_*): the cart steers a citrinitas crosshair over banked's
spinning scene, writes the watched pixel into PICK_X/Y, and the machine
answers -- PICK_ID (the visible triangle's paint-order index, -1 when
only the clear owns the pixel) and PICK_Z (the depth standing there),
displayed live as two bit rows. Point at the bunny and the face ids
churn with the spin; point at the floor and the tile face holds steady;
point at the sky and the ID row goes all-white (-1).

Controls, the monitor's law (edge-triggered): dpad moves the crosshair
2 px per tap, x8 while A is held. The crosshair's four ticks never
cover the watched pixel itself.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import meshtool, spec                # noqa: E402
from gen_cube import ground_mesh, cube_mesh, data_lines as cube_lines  # noqa: E402

GROUND_AT = 320
MESH_AT = 900
X, Z, YAW, WANT, PHASE, PICKV, IDX = 16, 17, 18, 19, 20, 21, 22
WX, WY, PREV, S1, S2 = 23, 24, 25, 26, 27
PB, PT = 33, 40                # paint scratch (33: VT owns 31-32!);
                               # the palette table
BR, BV, BI = 28, 29, 30
VT = 31

DL = spec.DL_BASE
SIG = spec.LOADER_SIG
C_TICK = 0xE6C010              # citrinitas
C_ONE, C_OFF = 0xEEEEEE, 0x2A2A33

T_TICKS = 0                    # 4 ticks x 1 quad x 2 tris = 8
T_BITS = T_TICKS + 8
NTRI = T_BITS + 32             # 2 rows x 16 bits
ROWS = [S1, S2]


def rgb_addr(t):
    return DL + 7 + t * 7


def mesh_words(verts, faces, cols=None):
    words = [len(verts) // 3, len(faces)]
    words += list(verts)
    for a, b, c, col in faces:
        words += [a | (b << 10) | (c << 20), col]
    return words


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
    blocks = meshtool.bake(bverts, bfaces, tint=(240, 240, 240),
                           height=1.6, gouraud=True, max_words=4200)

    cram = []
    g_verts, g_faces = cube_lines and ground_mesh()
    g_lines, g_len = cube_lines(GROUND_AT, g_verts, g_faces)
    assert GROUND_AT + g_len <= MESH_AT
    slots = []
    at = MESH_AT
    for b in blocks:
        slots.append(at); at += len(b)
    assert at <= spec.DL_BASE, at
    seg = []
    pieces = []
    for k, b in enumerate(blocks):
        pieces.append((len(seg), slots[k], len(b)))
        seg.extend(b)
    NBP = len(blocks)
    TBL = 80
    table = []
    for src, dst, ln in pieces:
        table += [src, dst, ln]
    assert TBL + len(table) <= GROUND_AT
    for o in range(0, len(seg), 16):
        vals = " ".join(str(spec.s32(w)) for w in seg[o:o + 16])
        cram.append(f".cram {o} {vals}")
    tbl_lines = [f".data {TBL + o} " + " ".join(str(v) for v in table[o:o+12])
                 for o in range(0, len(table), 12)]

    head = ["; pick.zol -- the pick register demo (see gen_pick.py)",
            "; GENERATED -- edit gen_pick.py, not this.",
            "",
            ".data 8 0 91750 -196608 0     ; camera: y 1.4, z -3",
            f".data 16 0 98304 0 -1 0 0 0",
            f".data {WX} 160", f".data {WY} 140",
            # the opus palette, the brush's cycle
            f".data {PT} 0 16777215 2142272 12853280 15122448", ""]
    ol = [f".data {spec.OL_BASE} 1 {GROUND_AT} 0 0 0 0 1"]
    for k, sl in enumerate(slots):
        ol.append(f".data {spec.OL_BASE + 7 + k * 6} {sl} 0 0 98304 0 3")
    ol.append("")

    P = ["load 0", "jz init", "jmp main", "init:"]
    for r, cell in enumerate(ROWS):
        P += [f"push {cell}", f"store {VT + r}"]
    # bit-row geometry at y=8/y=26 (the top strip)
    for r in range(2):
        for b in range(16):
            x = 24 + b * 15 + (b >> 2) * 6
            y = 8 + r * 18
            a = DL + 1 + (T_BITS + r * 16 + b) * 7
            for off, val in enumerate((x, y, x + 12, y, x, y + 14)):
                P += [f"push {val}", f"store {a + off}"]
    P += [f"push {NTRI}", f"store {DL}",
          "push 0", f"store {PREV}"]

    P += ["main:",
          # boot paging, banked's page-once law
          "load WANT", "push 0", "lt", "jz not_boot",
          f"push {NBP}", "store PHASE", "push 0", "store IDX",
          "push 0", "store WANT",
          "not_boot:",
          "load PHASE", "jz steer",
          "load IDX", "push 3", "mul", f"push {TBL}", "add",
          "dup", "loadi", "store SRC",
          "dup", "push 1", "add", "loadi", "store DST",
          "push 2", "add", "loadi", "store LEN",
          "push 1", "store GO",
          "load IDX", "push 1", "add", "store IDX",
          "load PHASE", "push 1", "sub", "store PHASE",
          "steer:",
          # the display flip banked taught: the chunks join the object
          # list only once every landing is complete
          "load PHASE", "jz ol_on", "jmp ol_done",
          "ol_on:", f"push {1 + NBP}", f"store {spec.OL_BASE}",
          "ol_done:",
          # crosshair steering: edge taps, 2 px, x8 with A
          "push 0", f"store {PICKV}",
          "load PAD", "push 8", "and", "jz p_r",
          f"load {PREV}", "push 8", "and", "jz e_r", "jmp p_r",
          "e_r:", "push 2", f"store {PICKV}", "p_r:",
          "load PAD", "push 4", "and", "jz p_l",
          f"load {PREV}", "push 4", "and", "jz e_l", "jmp p_l",
          "e_l:", "push -2", f"store {PICKV}", "p_l:",
          "load PAD", "push 16", "and", "jz p_a",
          f"load {PICKV}", "push 8", "mul", f"store {PICKV}", "p_a:",
          f"load {WX}", f"load {PICKV}", "add", f"store {WX}",
          f"load {WX}", "push 4", "lt", "jz wxlo",
          "push 4", f"store {WX}", "wxlo:",
          "push 315", f"load {WX}", "lt", "jz wxhi",
          "push 315", f"store {WX}", "wxhi:",
          "push 0", f"store {PICKV}",
          "load PAD", "push 1", "and", "jz p_u",
          f"load {PREV}", "push 1", "and", "jz e_u", "jmp p_u",
          "e_u:", "push -2", f"store {PICKV}", "p_u:",
          "load PAD", "push 2", "and", "jz p_d",
          f"load {PREV}", "push 2", "and", "jz e_d", "jmp p_d",
          "e_d:", "push 2", f"store {PICKV}", "p_d:",
          "load PAD", "push 16", "and", "jz p_a2",
          f"load {PICKV}", "push 8", "mul", f"store {PICKV}", "p_a2:",
          f"load {WY}", f"load {PICKV}", "add", f"store {WY}",
          f"load {WY}", "push 48", "lt", "jz wylo",
          "push 48", f"store {WY}", "wylo:",
          "push 283", f"load {WY}", "lt", "jz wyhi",
          "push 283", f"store {WY}", "wyhi:",
          # THE ACTION: B paints the floor face under the mark,
          # cycling the alchemical palette (edge-triggered)
          "load PAD", "push 32", "and", "jz p_b",
          f"load {PREV}", "push 32", "and", "jz e_b", "jmp p_b",
          "e_b:",
          f"push {spec.PICK_ID}", "loadi", f"store {PB}",
          "push 39", f"load {PB}", "lt", "jz p_b",     # id > 39
          f"load {PB}", "push 168", "lt", "jz p_b",    # id < 168: floor
          # the face's color word: GROUND_AT + 2 + 81*3 + 2*(id-40) + 1
          f"load {PB}", "push 40", "sub", "shl 1", "push 566", "add",
          f"store {PB}",
          # find the current color in the table, paint the next
          f"load {PB}", "loadi", f"store {PICKV}",
          f"load {PICKV}", f"push {PT}", "loadi", "eq", "jz t1",
          f"push {PT + 1}", "loadi", "jmp t_put",
          "t1:", f"load {PICKV}", f"push {PT + 1}", "loadi", "eq",
          "jz t2", f"push {PT + 2}", "loadi", "jmp t_put",
          "t2:", f"load {PICKV}", f"push {PT + 2}", "loadi", "eq",
          "jz t3", f"push {PT + 3}", "loadi", "jmp t_put",
          "t3:", f"load {PICKV}", f"push {PT + 3}", "loadi", "eq",
          "jz t4", f"push {PT + 4}", "loadi", "jmp t_put",
          "t4:", f"push {PT}", "loadi",
          "t_put:", f"load {PB}", "storei",
          "p_b:",
          "load PAD", f"store {PREV}",
          # ask the machine
          f"load {WX}", f"store {spec.PICK_X}",
          f"load {WY}", f"store {spec.PICK_Y}",
          # stage last frame's answer
          f"push {spec.PICK_ID}", "loadi", "push 0xFFFF", "and",
          f"store {S1}",
          f"push {spec.PICK_Z}", "loadi", "push 0xFFFF", "and",
          f"store {S2}",
          # the spin
          "load YAW", "push 3", "add", "store YAW"]
    for k in range(len(blocks)):
        base = spec.OL_BASE + 7 + k * 6
        P += [f"load YAW", f"store {base + 4}"]
    # crosshair ticks: 4 one-px-wide quads around (WX, WY), 2 px clear
    # of the watched pixel in every direction
    tick = 0
    for dx, dy, w, h in ((-4, 0, 3, 1), (2, 0, 3, 1),
                         (0, -4, 1, 3), (0, 2, 1, 3)):
        for tri_i, coords in enumerate((
                ("x", "y", "xw", "y", "x", "yh"),
                ("xw", "y", "xw", "yh", "x", "yh"))):
            a = DL + 1 + (T_TICKS + tick) * 7
            for off, c in enumerate(coords):
                if c == "x":
                    P += [f"load {WX}", f"push {dx}", "add"]
                elif c == "xw":
                    P += [f"load {WX}", f"push {dx + w}", "add"]
                elif c == "y":
                    P += [f"load {WY}", f"push {dy}", "add"]
                else:
                    P += [f"load {WY}", f"push {dy + h}", "add"]
                P += [f"push {a + off}", "storei"]
            P += [f"push {C_TICK}", f"push {a + 6}", "storei"]
            tick += 1
    P += ["call bitsc", "halt"]

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
          f"load {BR}", "push 2", "lt", "jz bc_rend", "jmp bcr",
          "bc_rend:", "ret"]

    consts = [".const PAD 1",
              f".const SRC {spec.DMA_SRC}", f".const DST {spec.DMA_DST}",
              f".const LEN {spec.DMA_LEN}", f".const GO {spec.DMA_GO}",
              f".const YAW {YAW}", f".const WANT {WANT}",
              f".const PHASE {PHASE}", f".const IDX {IDX}", ""]
    (HERE / "pick.zol").write_text(
        "\n".join(head[:3] + consts + head[3:] + ol + g_lines + tbl_lines
                  + [""] + cram + [""] + P))
    print(f"wrote pick.zol: crosshair + {len(ROWS)} answer rows, "
          f"{NTRI} triangles")


if __name__ == "__main__":
    main()
