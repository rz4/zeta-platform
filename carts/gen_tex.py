#!/usr/bin/env python3
"""gen_tex.py -- writes carts/tex.zol: the sampled field's first light.

Build 66's amendment: a 32x32 texture page, sampled per pixel through
the color interpolators (u rides red, v rides green, the channel clamp
is the texel clamp). The demo: a brick-clad cube TUMBLING on all three
axes over the checker floor, the camera flyable as in orbit.zol. The
bricks are alchemical -- rubedo faces, nigredo mortar, one citrinitas
keystone per course.

The cube carries 24 vertices (four per face) so every face owns its
uv corners; texture and mesh are resident .data -- no segment, no
mover: the whole cart is the page and the object.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import spec                          # noqa: E402
from gen_cube import ground_mesh, data_lines as cube_lines  # noqa: E402

GROUND_AT = 320
MESH_AT = 900
TEXIMG_AT = 6000
YAW, PIT, ROL, CP, T = 16, 17, 18, 19, 20
ONE = 65536


def brick_page():
    """32x32 RGB555, the alchemical bricks."""
    def rgb555(r, g, b):
        return ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)
    RUB, NIG, CIT = rgb555(0xC4, 0x20, 0x20), rgb555(8, 8, 8), \
        rgb555(0xE6, 0xC0, 0x10)
    px = [[RUB] * 32 for _ in range(32)]
    for y in range(32):
        for x in range(32):
            course = y // 8
            if y % 8 >= 6:
                px[y][x] = NIG                     # mortar rows, 2 texels
            elif (x + (course % 2) * 8) % 16 >= 14:
                px[y][x] = NIG                     # mortar columns, 2
        if y % 8 == 3:
            kx = (5 + (y // 8) * 16) % 32
            px[y][kx] = CIT                        # the keystone
    return px


def cube24():
    """24-vert cube CENTERED at the origin (it tumbles about its own
    middle), per-face uv corners, windings COMPUTED outward -- the
    hand-wound version culled faces at certain angles and clipped the
    floor mid-tumble (the player's glass reading, boot 66)."""
    h = (ONE * 3) // 4             # a 1.5-unit cube: ~double the
                                   # pixels per texel, half the shimmer
    axes = [(0, 0, -1), (0, 0, 1), (-1, 0, 0), (1, 0, 0),
            (0, 1, 0), (0, -1, 0)]
    verts, uvs, faces = [], [], []
    for fi, (nx, ny, nz) in enumerate(axes):
        # build the face's plane: normal n, spanning u_dir x v_dir
        n = (nx, ny, nz)
        u_dir = (0, 1, 0) if nz else ((0, 0, 1) if nx else (1, 0, 0))
        v_dir = (n[1]*u_dir[2]-n[2]*u_dir[1],
                 n[2]*u_dir[0]-n[0]*u_dir[2],
                 n[0]*u_dir[1]-n[1]*u_dir[0])
        corners = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append(tuple(
                n[i]*h + su*u_dir[i]*h + sv*v_dir[i]*h for i in range(3)))
        # winding: cross(c1-c0, c2-c0) must point along n (outward)
        e1 = tuple(corners[1][i]-corners[0][i] for i in range(3))
        e2 = tuple(corners[2][i]-corners[0][i] for i in range(3))
        cr = (e1[1]*e2[2]-e1[2]*e2[1], e1[2]*e2[0]-e1[0]*e2[2],
              e1[0]*e2[1]-e1[1]*e2[0])
        if cr[0]*n[0]+cr[1]*n[1]+cr[2]*n[2] < 0:
            corners = [corners[0], corners[3], corners[2], corners[1]]
        b = fi * 4
        for (x, y, z), (u, v) in zip(corners,
                                     [(0, 31), (31, 31), (31, 0), (0, 0)]):
            verts += [x, y, z]
            uvs.append(u | (v << 8))
        # THE TINT (build 89): the face's colour word used to be zero
        # and thrown away -- a textured face was UNLIT, flatter than the
        # PS1, which could at least modulate a texture by vertex colour.
        # Now it lights the texel. One lambert term against a light from
        # above and slightly forward, baked once here, costs nothing at
        # runtime and is the whole difference between a brick sticker
        # and a brick that is somewhere.
        L = (0.35, 0.55, 1.0)                 # the light, normalised-ish
        d = max(0.0, sum(n[i] * L[i] for i in range(3))
                / (sum(v * v for v in L) ** 0.5))
        k = int(round((0.42 + 0.58 * d) * 255))
        col = (k << 16) | (k << 8) | k
        faces += [(b, b+1, b+2, col), (b, b+2, b+3, col)]
    return verts, uvs, faces


def page_words(page):
    """A 32x32 page plus its mip chain, packed two texels per word.
    Box-filter each 5-bit channel, truncating -- the toolchain's
    canonical downsample (content, not law)."""
    levels = [page]
    for _ in range(3):
        prev = levels[-1]
        n = len(prev) // 2
        nxt = [[0] * n for _ in range(n)]
        for y in range(n):
            for x in range(n):
                quad = (prev[2*y][2*x], prev[2*y][2*x+1],
                        prev[2*y+1][2*x], prev[2*y+1][2*x+1])
                t = 0
                for sh in (10, 5, 0):
                    c = sum((q >> sh) & 31 for q in quad) >> 2
                    t |= c << sh
                nxt[y][x] = t
        levels.append(nxt)
    flat = [t for lv in levels for row in lv for t in row]
    return [flat[i] | (flat[i + 1] << 16) for i in range(0, len(flat), 2)]


def main():
    g_verts, g_faces = ground_mesh()
    g_lines, g_len = cube_lines(GROUND_AT, g_verts, g_faces)
    assert GROUND_AT + g_len <= MESH_AT

    verts, uvs, faces = cube24()
    mesh = [24, 12] + verts + uvs
    for a, b, c, col in faces:
        mesh += [a | (b << 10) | (c << 20), col]
    mesh_lines = [f".data {MESH_AT + o} " +
                  " ".join(str(spec.s32(w)) for w in mesh[o:o + 12])
                  for o in range(0, len(mesh), 12)]

    words = page_words(brick_page())
    tex_lines = [f".data {TEXIMG_AT + o} " +
                 " ".join(str(spec.s32(w)) for w in words[o:o + 12])
                 for o in range(0, len(words), 12)]

    head = ["; tex.zol -- the brick cube (see gen_tex.py)",
            "; GENERATED -- edit gen_tex.py, not this.",
            "", ".const PAD 1", "",
            ".data 8 0 131072 -262144 0    ; camera: y 2, z -4",
            f".data {spec.TEX_SRC} {TEXIMG_AT}", ""]
    # object list: floor + the textured cube (flags CULL|TEX = 5)
    ol = [f".data {spec.OL_BASE} 2 {GROUND_AT} 0 0 0 0 1",
          f".data {spec.OL_BASE + 7} {MESH_AT} 0 98304 65536 0 {spec.OBJ_CULL | spec.OBJ_TEX | spec.OBJ_TINT}", ""]

    P = ["load 0", "jz init", "jmp main", "init:", "main:",
         # the tumble
         f"load {YAW}", "push 2", "add", "push 1023", "and",
         f"store {YAW}",
         f"load {PIT}", "push 1", "add", "push 1023", "and",
         f"store {PIT}",
         f"load {ROL}", "push 1", "add", "push 1023", "and",
         f"store {ROL}",
         f"load {ROL}", "shl 10", f"load {PIT}", "or",
         "shl 10", f"load {YAW}", "or",
         f"store {spec.OL_BASE + 7 + 4}",
         # the gaze
         "load PAD", "push 8", "and", "jz g_r",
         f"load {spec.CAM_YAW}", "push 8", "add", "push 1023", "and",
         f"store {spec.CAM_YAW}", "g_r:",
         "load PAD", "push 4", "and", "jz g_l",
         f"load {spec.CAM_YAW}", "push 8", "sub", "push 1023", "and",
         f"store {spec.CAM_YAW}", "g_l:",
         "load PAD", "push 1", "and", "jz g_u",
         f"load {CP}", "push 4", "add", f"store {CP}", "g_u:",
         "load PAD", "push 2", "and", "jz g_d",
         f"load {CP}", "push 4", "sub", f"store {CP}", "g_d:",
         f"load {CP}", "push -114", "lt", "jz cp_lo_ok",
         "push -114", f"store {CP}", "cp_lo_ok:",
         "push 114", f"load {CP}", "lt", "jz cp_hi_ok",
         "push 114", f"store {CP}", "cp_hi_ok:",
         f"load {CP}", "push 1023", "and", f"store {spec.CAM_PITCH}",
         "halt"]

    (HERE / "tex.zol").write_text(
        "\n".join(head + ol + g_lines + mesh_lines + tex_lines + [""] + P))
    print(f"wrote tex.zol: brick cube, {len(mesh)}-word mesh, "
          f"512-word page at {TEXIMG_AT}")


if __name__ == "__main__":
    main()
