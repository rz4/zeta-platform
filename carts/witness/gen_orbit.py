#!/usr/bin/env python3
"""gen_orbit.py -- writes carts/witness/orbit.zol: full 3-axis rotation's demo.

Build 65's amendment on display: the bunny TUMBLES -- yaw, pitch, and
roll all advancing, packed into the object's single angles word -- and
the dpad aims the CAMERA: left/right turns (CAM_YAW), up/down looks
(CAM_PITCH, clamped to +/-40 degrees so the world never flips). Hold
to move; this is flight, not menu work.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import carts as _carts                         # noqa: E402
_carts.on_path()                 # sibling generators, wherever they live

from zeta import meshtool, spec                # noqa: E402
from gen_cube import ground_mesh, data_lines as cube_lines  # noqa: E402

GROUND_AT = 320
MESH_AT = 2400          # the floor grew; give it room
FLOOR_N, FLOOR_TILE = 8, 2       # 16 units per instance, 48 across in
                                 # 3x3 -- and only 128 faces each. The
                                 # frame is SETUP-bound, not fill-bound:
                                 # at 136 clocks per face the old 15x15
                                 # grid spent 90% of the frame on face
                                 # setup and 8% on pixels. Texturing it
                                 # would have been worse still, since a
                                 # perspective-correct texel is 13 clocks
                                 # against a flat pixel's 1. Fewer,
                                 # larger FLAT faces is the whole win.
                                 # 3x3. ONE unit, not two: this machine
                                 # has no near-plane clipping, so a face
                                 # with any vertex nearer than ZNEAR is
                                 # dropped WHOLE -- the hole under your
                                 # feet is exactly one tile wide, so the
                                 # tile is the thing to shrink
SINTAB = 2000          # 128 entries: sin at each yaw step of 8.
                       # ABOVE the floor mesh: when the floor grew to
                       # 15x15 it reached word 1990, and this table at
                       # 1400 was landing INSIDE its face data. Corrupt
                       # indices are skipped silently by both machines,
                       # so it showed up as bands of missing tiles and
                       # looked for all the world like a clipping bug.
YAW, PIT, ROL, WANT, PHASE, IDX, CP, T = 16, 17, 18, 19, 20, 21, 22, 23
STEP = 24              # scratch for the walk


def main():
    import json
    import subprocess
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys, json; sys.path.insert(0, sys.argv[1]);"
         "from zeta.assets import bunny;"
         "print(json.dumps([bunny._raw_vertices(), bunny._raw_faces()]))",
         str(ROOT.parent / "zeta/src")],
        capture_output=True, text=True, check=True)
    bverts, bfaces = json.loads(out.stdout)
    blocks = meshtool.bake(bverts, bfaces, tint=(240, 240, 240),
                           height=1.6, gouraud=True, max_words=4200)

    g_verts, g_faces = cube_lines and ground_mesh(FLOOR_N, FLOOR_TILE)
    g_lines, g_len = cube_lines(GROUND_AT, g_verts, g_faces)
    # the floor is parameterised now, so its extent is not a constant:
    # check it against everything placed above it, or a silent overlap
    # comes back as missing geometry
    assert GROUND_AT + g_len <= SINTAB, (
        f"ground mesh reaches {GROUND_AT + g_len}, over SINTAB {SINTAB}")
    assert SINTAB + 128 <= MESH_AT, "sine table overruns the mesh area"
    assert GROUND_AT + g_len <= MESH_AT
    slots = []
    at = MESH_AT
    for b in blocks:
        slots.append(at); at += len(b)
    assert at <= spec.DL_BASE
    seg, pieces = [], []
    for k, b in enumerate(blocks):
        pieces.append((len(seg), slots[k], len(b)))
        seg.extend(b)
    NBP = len(blocks)
    TBL = 80
    table = []
    for src, dst, ln in pieces:
        table += [src, dst, ln]
    cram = [f".cram {o} " + " ".join(str(spec.s32(w)) for w in seg[o:o+16])
            for o in range(0, len(seg), 16)]
    # walking needs a heading, and the VM has no trig: 128 entries, one
    # per yaw step of 8, scaled to the walk speed in Q16.16
    SPEED = 0.12
    sintab = [int(round(math.sin(i * 8 * math.tau / 1024) * 65536 * SPEED))
              for i in range(128)]
    sin_lines = [f".data {SINTAB + o} " + " ".join(str(v) for v in sintab[o:o + 12])
                 for o in range(0, len(sintab), 12)]
    tbl_lines = [f".data {TBL + o} " + " ".join(str(v) for v in table[o:o+12])
                 for o in range(0, len(table), 12)]

    head = ["; orbit.zol -- the tumbling bunny, the flyable gaze",
            "; GENERATED -- edit gen_orbit.py, not this.",
            "", ".const PAD 1",
            f".const SRC {spec.DMA_SRC}", f".const DST {spec.DMA_DST}",
            f".const LEN {spec.DMA_LEN}", f".const GO {spec.DMA_GO}",
            "",
            ".data 8 0 131072 -262144 0    ; camera: y 2, z -4",
            f".data {spec.FOG_RGB} 0x101830   ; the far dark",
            f".data {spec.FOG_NEAR} 1024",
            f".data {spec.FOG_SHIFT} 8",
            f".data {spec.LOD_FLAT} 2000   ; flat where the fog is thick",
            f".data {WANT} -1", ""]
    # THE FLOOR IS INSTANCED. The 256-vertex cap is per MESH, not per
    # scene: the object list can point many entries at the same mesh at
    # different places. Nine copies of a 30-unit floor, laid edge to edge,
    # is ninety units across for the price of eight object slots and not
    # one new vertex.
    span = FLOOR_N * FLOOR_TILE * 65536
    ol = []
    n_floor = 0
    for gz in (-1, 0, 1):
        for gx in (-1, 0, 1):
            base = spec.OL_BASE + 1 + n_floor * 6
            ol.append(f".data {base} {GROUND_AT} {gx * span} 0 {gz * span} 0 1")
            n_floor += 1
    ol.insert(0, f".data {spec.OL_BASE} {n_floor}")
    for k, sl in enumerate(slots):
        base = spec.OL_BASE + 1 + (n_floor + k) * 6
        ol.append(f".data {base} {sl} 0 65536 65536 0 3")
    ol.append("")

    P = ["load 0", "jz init", "jmp main", "init:", "main:",
         # page once
         f"load {WANT}", "push 0", "lt", "jz not_boot",
         f"push {NBP}", f"store {PHASE}", "push 0", f"store {IDX}",
         "push 0", f"store {WANT}",
         "not_boot:",
         f"load {PHASE}", "jz shown",
         f"load {IDX}", "push 3", "mul", f"push {TBL}", "add",
         "dup", "loadi", "store SRC",
         "dup", "push 1", "add", "loadi", "store DST",
         "push 2", "add", "loadi", "store LEN",
         "push 1", "store GO",
         f"load {IDX}", "push 1", "add", f"store {IDX}",
         f"load {PHASE}", "push 1", "sub", f"store {PHASE}",
         "shown:",
         f"load {PHASE}", "jz ol_on", "jmp ol_d",
         "ol_on:", f"push {n_floor + NBP}", f"store {spec.OL_BASE}",
         "ol_d:",
         # the tumble
         f"load {YAW}", "push 3", "add", "push 1023", "and",
         f"store {YAW}",
         f"load {PIT}", "push 2", "add", "push 1023", "and",
         f"store {PIT}",
         f"load {ROL}", "push 1", "add", "push 1023", "and",
         f"store {ROL}",
         # compose the packed angles word
         f"load {ROL}", "shl 10", f"load {PIT}", "or",
         "shl 10", f"load {YAW}", "or", f"store {T}"]
    for k in range(len(blocks)):
        base = spec.OL_BASE + 1 + (n_floor + k) * 6
        P += [f"load {T}", f"store {base + 4}"]
    P += [
        # TANK CONTROLS: the dpad drives, the face buttons look.
        # left/right turn on the spot, up/down walk, Y looks up, B down.
        # RIGHT DECREASES the yaw -- measured, not taken from the name,
        # the same way the pitch sign was. These were backwards too.
        "load PAD", "push 8", "and", "jz g_r",
        f"load {spec.CAM_YAW}", "push 8", "sub", "push 1023", "and",
        f"store {spec.CAM_YAW}", "g_r:",
        "load PAD", "push 4", "and", "jz g_l",
        f"load {spec.CAM_YAW}", "push 8", "add", "push 1023", "and",
        f"store {spec.CAM_YAW}", "g_l:",
        # CAM_PITCH counts DOWNWARD: +90 is the floor. These two were
        # the wrong way round from the day they were written -- the sign
        # was assumed from the name and never measured.
        "load PAD", "push 128", "and", "jz g_u",          # Y: look up
        f"load {CP}", "push 4", "sub", f"store {CP}", "g_u:",
        "load PAD", "push 32", "and", "jz g_d",           # B: look down
        f"load {CP}", "push 4", "add", f"store {CP}", "g_d:",
        # clamp the look to +/-114 (~40 deg), then publish wrapped
        f"load {CP}", "push -114", "lt", "jz cp_lo_ok",
        "push -114", f"store {CP}", "cp_lo_ok:",
        "push 114", f"load {CP}", "lt", "jz cp_hi_ok",
        "push 114", f"store {CP}", "cp_hi_ok:",
        f"load {CP}", "push 1023", "and", f"store {spec.CAM_PITCH}",
        # ---- and the feet: A walks forward, B walks back, along the
        # heading the gaze is pointing. sin(yaw) and cos(yaw) come out of
        # the table; cos is sin a quarter turn on, which is 32 entries.
        "load PAD", "push 3", "and", "jz no_walk",     # UP or DOWN
        f"load {spec.CAM_YAW}", "shr 3", "push 127", "and", f"store {STEP}",
        f"load {STEP}", f"push {SINTAB}", "add", "loadi", f"store {T}",
        f"load {STEP}", "push 32", "add", "push 127", "and",
        f"push {SINTAB}", "add", "loadi", f"store {IDX}",
        "load PAD", "push 1", "and", "jz walk_back",   # UP walks forward
        # forward is (-sin, +cos), not (+sin, +cos): the world-to-camera
        # transform rotates by -yaw, so the heading that lands on +z is
        # R(yaw) applied to (0,1). With the sign wrong the walk veered
        # mirrored at every angle except dead ahead.
        f"load {spec.CAM_X}", f"load {T}", "sub", f"store {spec.CAM_X}",
        f"load {spec.CAM_Z}", f"load {IDX}", "add", f"store {spec.CAM_Z}",
        "jmp no_walk",
        "walk_back:",
        f"load {spec.CAM_X}", f"load {T}", "add", f"store {spec.CAM_X}",
        f"load {spec.CAM_Z}", f"load {IDX}", "sub", f"store {spec.CAM_Z}",
        "no_walk:",
        "halt"]

    (HERE / "orbit.zol").write_text(
        "\n".join(head + ol + g_lines + tbl_lines + sin_lines + [""] + cram + [""] + P))
    print(f"wrote orbit.zol: tumbling bunny, camera yaw+pitch")


if __name__ == "__main__":
    main()
