#!/usr/bin/env python3
"""gen_room.py -- writes carts/room.zol: the depth-composited room.

The generation-ahead flagship (docs/WORLD-FABRIC.md), first light. A
room -- checkered floor, a ring of tall pillars -- is rendered ONCE at
bake time by the law's own renderer into color AND depth, and packed
into the cart's CRAM segment. At runtime the machine never draws the
room: BG_SRC makes the frame CLEAR to it, depth included, and a live
Gouraud bunny walks through -- occluded per-pixel by pillars that are
just pixels. Resident Evil's trick without its mask-rectangle seams.

Arrows drive the bunny. Walk it behind a pillar.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np                             # noqa: E402

from zeta import gpu, meshtool, spec           # noqa: E402
from gen_cube import ground_mesh, data_lines as cube_lines  # noqa: E402
from gen_banked import mesh_words              # noqa: E402

ROOM_OFF = 16                  # segment word offset of the room image
CAMERA = [0, 91750, -196608, 0]                # y 1.4, z -3, straight on
GROUND_AT, PILLAR_AT = 32, 600
BUNNY_AT = 700
X, Z, YAW = 16, 17, 18


def pillar_mesh(w=0.22, h=2.0):
    """A tall box, feet on y=0, flat-shaded stone."""
    ONE = 65536
    xs = (int(-w * ONE), int(w * ONE))
    ys = (0, int(h * ONE))
    zs = (int(-w * ONE), int(w * ONE))
    verts = []
    for x, y, z in [(0,0,0),(1,0,0),(1,1,0),(0,1,0),
                    (0,0,1),(1,0,1),(1,1,1),(0,1,1)]:
        verts += [xs[x], ys[y], zs[z]]
    quads = [((0,1,2,3), 0x8A8DA0), ((5,4,7,6), 0x6E7182),
             ((4,0,3,7), 0x7C7F92), ((1,5,6,2), 0x9B9EB2),
             ((3,2,6,7), 0xB0B3C6), ((4,5,1,0), 0x55586A)]
    faces = []
    for (a,b,c,d), col in quads:
        faces += [(a,c,b,col), (a,d,c,col)]
    return verts, faces


def bake_room():
    """Render the room through the law itself, return (fb, zbuf)."""
    dmem = [0] * spec.DMEM_WORDS
    for i, v in enumerate(CAMERA):
        dmem[spec.CAM_X + i] = v & spec.WORD_MASK
    gv, gf = ground_mesh()
    gwords = mesh_words(gv, gf)
    for i, w in enumerate(gwords):
        dmem[GROUND_AT + i] = w & spec.WORD_MASK
    pv, pf = pillar_mesh()
    pwords = mesh_words(pv, pf)
    for i, w in enumerate(pwords):
        dmem[PILLAR_AT + i] = w & spec.WORD_MASK
    # the ring of pillars: three in front of the bunny's lane, three behind
    poses = [(-1.6, 0.9), (0.0, 0.7), (1.6, 0.9),
             (-1.0, 2.6), (0.8, 2.8), (-0.2, 3.4)]
    ONE = 65536
    ol = [(GROUND_AT, 0, 0, 0, 0, 1)]
    for px, pz in poses:
        ol.append((PILLAR_AT, int(px * ONE), 0, int(pz * ONE), 0, 1))
    dmem[spec.OL_BASE] = len(ol)
    for k, e in enumerate(ol):
        b = spec.OL_BASE + 1 + k * spec.OL_STRIDE
        for i, v in enumerate(e):
            dmem[b + i] = v & spec.WORD_MASK
    fb = np.empty((spec.H, spec.W, 3), np.uint8)
    fb[:, :] = spec.display_rgb(0x0A0A14)      # the room's own night sky
    zbuf = np.full((spec.H, spec.W), spec.ZFAR, np.int64)
    gpu._geom(fb, zbuf, dmem)
    return fb, zbuf


def main():
    import json
    import subprocess
    fb, zbuf = bake_room()
    c5 = (fb >> 3).astype(np.int64)
    rgb555 = (c5[..., 0] << 10) | (c5[..., 1] << 5) | c5[..., 2]
    words = ((zbuf & 0xFFFF) << 16) | rgb555
    flat = words.reshape(-1)

    out = subprocess.run(
        [sys.executable, "-c",
         "import sys, json; sys.path.insert(0, sys.argv[1]);"
         "from zeta.assets import bunny;"
         "print(json.dumps([bunny._raw_vertices(), bunny._raw_faces()]))",
         str(HERE.parent.parent / "zeta/src")],
        capture_output=True, text=True, check=True)
    bverts, bfaces = json.loads(out.stdout)
    blocks = meshtool.bake(bverts, bfaces, tint=(225, 210, 195), height=1.3,
                           gouraud=True, max_words=1400)
    bunny = blocks[0]

    cram = []
    for o in range(0, len(flat), 16):
        vals = " ".join(str(int(w) if w < 0x80000000 else int(w) - (1 << 32))
                        for w in flat[o:o + 16])
        cram.append(f".cram {ROOM_OFF + o} {vals}")

    head = ["; room.zol -- the depth-composited room (see gen_room.py)",
            "; GENERATED -- edit gen_room.py, not this.",
            "", ".const PAD 1",
            f".const X {X}", f".const Z {Z}", f".const YAW {YAW}", "",
            f".data {spec.BG_SRC} {ROOM_OFF}   ; the frame clears to the room",
            ".data 8 " + " ".join(str(v) for v in CAMERA),
            f".data {X} 0 98304 512            ; bunny starts mid-room",
            f".data {spec.AU_BASE + 4} 25000 5", ""]
    data = [f".data {BUNNY_AT + i} "
            f"{w if w < 0x80000000 else w - (1 << 32)}"
            for i, w in enumerate(bunny)]
    # pack mesh .data 16 words per line for file size
    dl = []
    for o in range(0, len(bunny), 16):
        vals = " ".join(str(spec.s32(w)) for w in bunny[o:o + 16])
        dl.append(f".data {BUNNY_AT + o} {vals}")
    ol = [f".data {spec.OL_BASE} 1 {BUNNY_AT} 0 0 98304 512 3", ""]

    prog = ["load PAD", "push 8", "and", "jz n_r",
            "load X", "push 2458", "add", "store X", "n_r:",
            "load PAD", "push 4", "and", "jz n_l",
            "load X", "push 2458", "sub", "store X", "n_l:",
            "load PAD", "push 1", "and", "jz n_u",
            "load Z", "push 2458", "add", "store Z", "n_u:",
            "load PAD", "push 2", "and", "jz n_d",
            "load Z", "push 2458", "sub", "store Z", "n_d:",
            "load YAW", "push 2", "add", "store YAW",
            f"load X", f"store {spec.OL_BASE + 2}",
            f"load Z", f"store {spec.OL_BASE + 4}",
            f"load YAW", f"store {spec.OL_BASE + 5}",
            "halt"]

    (HERE / "room.zol").write_text(
        "\n".join(head + ol + dl + [""] + cram + [""] + prog))
    print(f"wrote room.zol: room {len(flat)} segment words at {ROOM_OFF}, "
          f"bunny {len(bunny)} resident words at {BUNNY_AT}")


if __name__ == "__main__":
    main()
