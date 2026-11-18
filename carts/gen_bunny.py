#!/usr/bin/env python3
"""gen_bunny.py -- writes carts/bunny.zol: the Stanford bunny, baked.

Pass --flat for flat shading (the pre-Gouraud cart, and the one to ship
while the silicon Gouraud amendment is still landing).

The classic proof-of-3D: the real 502-vertex bunny (sourced from the
sibling zeta tree's embedded, reproducible asset), decimated and
flat-shaded by zeta/meshtool.py until it fits cart DMEM, spinning on the
checkered plane. Arrows slide it around; a soft triangle hum underneath.
Run me after changing anything: python3 carts/gen_bunny.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import meshtool, spec                # noqa: E402
from gen_cube import ground_mesh, data_lines as cube_data_lines  # noqa: E402

GROUND_AT = 32
BUNNY_PY = HERE.parent.parent / "zeta/src/zeta/assets/bunny.py"


def rainbow(blocks):
    """Give every face its own hue (golden-angle walk around the wheel) --
    the layering instrument: with no two neighbors alike, any face drawn
    at the wrong depth is unmissable. Flat layout only."""
    import colorsys
    k = 0
    for words in blocks:
        nv = words[0]
        for o in range(2 + 3 * nv + 1, len(words), 2):
            r, g, b = colorsys.hsv_to_rgb((k * 0.381966) % 1.0, 0.85, 1.0)
            words[o] = (int(r * 255) << 16) | (int(g * 255) << 8) | int(b * 255)
            k += 1
    return blocks


def parts(blocks, height):
    """Three flat anatomy colors -- ears yellow, head red, body blue --
    so head-vs-body layering reads at a glance. The head points along
    the (-x,-z) diagonal in model space (measured from the ear tips)."""
    ONE = 65536.0
    for words in blocks:
        nv = words[0]
        vs = [(words[2 + 3 * i] / ONE, words[3 + 3 * i] / ONE,
               words[4 + 3 * i] / ONE) for i in range(nv)]
        fbase = 2 + 3 * nv
        for o in range(fbase, len(words), 2):
            w = words[o]
            a, b, c = w & 1023, (w >> 10) & 1023, (w >> 20) & 1023
            cx = (vs[a][0] + vs[b][0] + vs[c][0]) / 3
            cy = (vs[a][1] + vs[b][1] + vs[c][1]) / 3
            cz = (vs[a][2] + vs[b][2] + vs[c][2]) / 3
            yn = cy / height
            fwd = (-0.67 * cx - 0.74 * cz) / height
            if yn > 0.78:
                col = 0xF0D020                       # ears
            elif yn > 0.48 and fwd > 0.04:
                col = 0xE03828                       # head
            else:
                col = 0x2858D0                       # body
            words[o + 1] = col
    return blocks


def main():
    flat = "--flat" in sys.argv
    debug = "--rainbow" in sys.argv       # flat + per-face hues, own cart
    anat = "--parts" in sys.argv          # flat + head/ears/body colors
    flat = flat or debug or anat
    fl = 1 if flat else 3
    # the sibling tree's embedded asset, extracted in a clean subprocess
    # (its package is also called `zeta`, so importing it here would
    # shadow ours)
    import json
    import subprocess
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys, json; sys.path.insert(0, sys.argv[1]);"
         "from zeta.assets import bunny;"
         "print(json.dumps([bunny._raw_vertices(), bunny._raw_faces()]))",
         str(BUNNY_PY.parents[2])],
        capture_output=True, text=True, check=True)
    verts, faces = json.loads(out.stdout)
    # the capacity amendment: the FULL 502-vertex source mesh fits DMEM
    # now -- these budgets are above its size, so decimate() never fires
    blocks = meshtool.bake(verts, faces, tint=(225, 210, 195), height=1.6,
                       gouraud=not flat, max_words=4200)
    if debug:
        blocks = rainbow(blocks)
    if anat:
        blocks = parts(blocks, 1.6)
    g_verts, g_faces = ground_mesh()
    g_lines, g_len = cube_data_lines(GROUND_AT, g_verts, g_faces)
    b_lines, bases, b_len = meshtool.data_lines(blocks, GROUND_AT + g_len)
    assert GROUND_AT + g_len + b_len <= spec.DL_BASE, (g_len, b_len)

    n_obj = 1 + len(bases)
    ol = [f".data {spec.OL_BASE} " + str(n_obj) + f" {GROUND_AT} 0 0 0 0 1"]
    slots = []
    for k, mb in enumerate(bases):             # bunny chunks share one pose
        base = spec.OL_BASE + 1 + (1 + k) * 6
        ol.append(f".data {base} {mb} 0 0 98304 0 {fl}")
        slots.append(base)

    prog = ["", ".const PAD 1", ".const X 16", ".const Z 17", ".const YAW 18",
            "", ".data 16 0 98304 0",
            ".data 8 0 91750 -196608 0  ; camera: y 1.4, z -3",
            f".data {spec.AU_BASE + 4} 25000 5  ; soft 71 Hz hum", ""]
    prog += ol + [""]
    prog += g_lines + [""]
    prog += b_lines
    body = ["", "load PAD", "push 8", "and", "jz n_r",
            "load X", "push 3277", "add", "store X", "n_r:",
            "load PAD", "push 4", "and", "jz n_l",
            "load X", "push 3277", "sub", "store X", "n_l:",
            "load PAD", "push 1", "and", "jz n_u",
            "load Z", "push 3277", "add", "store Z", "n_u:",
            "load PAD", "push 2", "and", "jz n_d",
            "load Z", "push 3277", "sub", "store Z", "n_d:",
            "load YAW", "push 3", "add", "store YAW"]
    for base in slots:                         # every chunk gets the pose
        body += [f"load X", f"store {base + 1}",
                 f"load Z", f"store {base + 3}",
                 f"load YAW", f"store {base + 4}"]
    body.append("halt")

    name = ("bunny_rainbow.zol" if debug else
            "bunny_parts.zol" if anat else "bunny.zol")
    header = [f"; {name} -- the Stanford bunny on the checkered plane.",
              "; GENERATED by carts/gen_bunny.py -- edit that, not this.",
              f"; {sum(len(b) for b in blocks)} mesh words in "
              f"{len(bases)} chunk(s); arrows slide, it spins itself."]
    (HERE / name).write_text("\n".join(header + prog + body))
    nv = sum(b[0] for b in blocks)
    nf = sum(b[1] for b in blocks)
    print(f"wrote {name}: {nv} verts, {nf} faces, "
          f"{len(bases)} chunk(s), {b_len} words at {bases}")


if __name__ == "__main__":
    main()
