#!/usr/bin/env python3
"""gen_crowd.py -- writes carts/witness/crowd.zol: spec.OLX_PTR's witness.

FIVE HUNDRED AND ELEVEN OBJECTS. The list moves to where the cart says
and holds eight times what it held. This cart lists 520 and is entitled
to 511 of them:

    0..508    a crowd of small tetrahedra, sixteen rows of thirty-two,
              every one turned differently, every third one outlined.
              THE FRONT ROW STANDS IN THE LENS: its bodies cross the near
              plane, so the long list goes through the clipper.
    111, 367  a pair whose owners differ only in the ninth bit, touching,
              one of them outlined.
    509       a sweeper, crossing in front of the crowd so that the
              counts are never still.
    510       the marker. THE LAST OBJECT THE LAW ALLOWS: its owner is
              511, every bit of the nine set.
    511..519  nine slabs across the whole glass, close to the lens.
              The law stops at 511 objects and never reaches them. A
              machine that read the count as it was written would.

HOW IT WITNESSES ITSELF, which is seen.zol's way: every object's visible
count -- sixty-four at VIS_BASE, four hundred and forty-seven more at
VISX_BASE -- and the eight owners and depths the gaze names are xored
and folded, and the marker stands where the fold puts it. One pixel of
one object miscounted, or one owner named a bit short, and the marker is
somewhere else, in front of a different part of the crowd, and the next
frame's counts are different again.

Run me after changing anything: python3 carts/witness/gen_crowd.py
"""
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import carts as _carts                         # noqa: E402
_carts.on_path()                 # sibling generators, wherever they live
from zeta import spec                          # noqa: E402
from gen_cube import cube_mesh, data_lines     # noqa: E402

ONE = 65536
TET_A, TET_B, CUBE_AT, SLAB_AT = 512, 560, 620, 700
LIST_AT = 2000
P, ACC, H = 16, 17, 18                         # scratch
LISTED = 520                                   # nine more than the law allows
COLS, ROWS = 32, 16
SWEEPER, MARKER = 509, 510
G, A = spec.GAZE_BASE, spec.GAZE_ANS


def entry(i):
    return LIST_AT + 1 + i * spec.OL_STRIDE


def tetra(colours, s=0.17, h=0.34):
    v = []
    for x, y, z in [(-s, 0, -s), (s, 0, -s), (0, 0, s), (0, h, 0)]:
        v += [int(x * ONE), int(y * ONE), int(z * ONE)]
    f = [(0, 1, 3, colours[0]), (1, 2, 3, colours[1]),
         (2, 0, 3, colours[2]), (0, 2, 1, colours[3])]
    return v, f


def slab():
    """A wall two units wide and tall, facing the lens."""
    v = []
    for x, y in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
        v += [x * ONE, y * ONE, 0]
    return v, [(0, 1, 2, 0xFF00FF), (0, 2, 3, 0xFF00FF)]


def objects():
    out = []
    for i in range(SWEEPER):
        col, row = i % COLS, i // COLS
        x = (col - (COLS - 1) / 2) * 0.42 + (0.21 if row & 1 else 0.0)
        z = -0.85 + row * 0.5              # row 0 is INSIDE the near plane
        y = row * 0.16 - 0.55
        if row == 0:
            # THE FRONT ROW, LIFTED INTO THE LENS. Where the grid would
            # put it, it crosses the near plane a whole unit BELOW the
            # glass and the clipper cuts nothing anyone can see (the
            # first cut of this cart: zero pixels moved with the clipper
            # switched off). At the camera's own height, a little to the
            # right, one of them is cut across the middle of the view.
            x = (col - COLS // 2) * 0.42 + 0.17
            y = 0.42
        mesh = TET_A if (col + row) & 1 else TET_B
        out.append((mesh, int(x * ONE), int(y * ONE), int(z * ONE),
                    (i * 37) & 1023, spec.OBJ_EDGE if i % 3 == 0 else 0))
    # TWO OWNERS THAT DIFFER ONLY IN THE NINTH BIT, TOUCHING. Object 111 is
    # outlined and stands mid-glass; object 367 (111 + 256) is moved to
    # stand just behind its shoulder. A machine that compared eight bits
    # of owner would see one object there and draw no line between them --
    # and nothing else in this crowd puts such a pair side by side (the
    # mutant survived the first cut of this cart).
    m, x, y, z, a_, f = out[111]
    out[367] = (out[367][0], x + int(0.10 * ONE), y + int(0.06 * ONE),
                z + int(0.10 * ONE), out[367][4], out[367][5])
    out.append((CUBE_AT, 0, int(-0.3 * ONE), int(1.6 * ONE), 0, spec.OBJ_CULL))
    out.append((CUBE_AT, 0, int(0.4 * ONE), int(4.0 * ONE), 0,
                spec.OBJ_CULL | spec.OBJ_EDGE))
    for k in range(LISTED - 511):          # the nine the law never reaches
        out.append((SLAB_AT, 0, int(0.6 * ONE), int((0.2 + 0.1 * k) * ONE), 0, 0))
    assert len(out) == LISTED
    return out


# eight watched pixels, scan order: down the glass, across the crowd
WATCHED = [(30 + 37 * k, 96 + 22 * k) for k in range(spec.GAZE_MAX)]
assert all(b[1] * spec.W + b[0] > a[1] * spec.W + a[0]
           for a, b in zip(WATCHED, WATCHED[1:]))


def program():
    fold = [f"load {spec.VIS_BASE}"]
    for k in range(1, spec.OL_MAX):
        fold += [f"load {spec.VIS_BASE + k}", "xor"]
    for k in range(spec.OLX_MAX - spec.OL_MAX):
        fold += [f"load {spec.VISX_BASE + k}", "xor"]
    for k in range(spec.GAZE_MAX):
        fold += [f"load {A + k}", "xor"]
    fold = "\n".join(fold)
    return f"""
; ---- the sweep: a cube crossing in front of the crowd ---------------
load {P}
push 6
add
push 255
and
store {P}

load {P}
push 128
sub
shl 10
store {entry(SWEEPER) + 1}

; ---- the fold: 511 counts and 8 answers -----------------------------
{fold}
store {ACC}

load {ACC}
load {ACC}
shr 4
xor
load {ACC}
shr 8
xor
load {ACC}
shr 12
xor
load {ACC}
shr 16
xor
load {ACC}
shr 20
xor
store {H}

; ---- the marker stands where they put it ----------------------------
load {H}
push 7
and
shl 16
push 229376
sub
store {entry(MARKER) + 1}

load {H}
shr 3
push 7
and
shl 15
push 131072
add
store {entry(MARKER) + 3}
halt
"""


def main():
    a_v, a_f = tetra((0xD8C060, 0xA08840, 0x786428, 0x403010))
    b_v, b_f = tetra((0x60B0D8, 0x4080A0, 0x285878, 0x102838))
    c_v, c_f = cube_mesh()
    s_v, s_f = slab()
    a_lines, a_len = data_lines(TET_A, a_v, a_f)
    b_lines, b_len = data_lines(TET_B, b_v, b_f)
    c_lines, c_len = data_lines(CUBE_AT, c_v, c_f)
    s_lines, s_len = data_lines(SLAB_AT, s_v, s_f)
    assert TET_A + a_len <= TET_B and TET_B + b_len <= CUBE_AT
    assert CUBE_AT + c_len <= SLAB_AT and SLAB_AT + s_len <= LIST_AT
    objs = objects()
    words = [LISTED] + [v & spec.WORD_MASK for o in objs for v in o]
    assert LIST_AT + len(words) <= spec.DL_BASE
    assert LIST_AT <= spec.DMEM_WORDS - 1 - spec.OLX_MAX * spec.OL_STRIDE
    l_lines = [f".data {LIST_AT + o} " +
               " ".join(str(spec.s32(w)) for w in words[o:o + 16])
               for o in range(0, len(words), 16)]

    out = ["; crowd.zol -- spec.OLX_PTR's witness. GENERATED by",
           "; carts/witness/gen_crowd.py -- edit that, not this.",
           ";",
           f"; {LISTED} objects listed, 511 the law's. The marker stands",
           "; where their 511 visible counts and the gaze's 8 answers put it.",
           "",
           ".data 8 0 39321 -65536 0      ; camera: x 0, y 0.6, z -1",
           f".data {spec.EDGE_RGB} 16316096   ; 0xF8F8C0",
           f".data {spec.AU_BASE + 4} 30000 5",
           f".data {spec.OLX_PTR} {LIST_AT}       ; the long list is HERE",
           f".data {G} {spec.GAZE_MAX} " +
           " ".join(str((y << 16) | x) for x, y in WATCHED),
           "",
           f"; ---- meshes: two tetrahedra, a cube, a slab ----"]
    out += a_lines + b_lines + c_lines + s_lines
    out += ["", f"; ---- the long list: {len(words)} words ----"] + l_lines
    out.append(program())
    path = Path(__file__).parent / "crowd.zol"
    path.write_text("\n".join(out))
    print(f"wrote {path}: {LISTED} objects listed at {LIST_AT}, "
          f"{len(words)} words")


if __name__ == "__main__":
    main()
