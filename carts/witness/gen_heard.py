#!/usr/bin/env python3
"""gen_heard.py -- writes carts/witness/heard.zol: spec.AUD_BASE's witness.

THE MIXER IS A SENSOR TOO. VIS_BASE returns how much of each object the
panel showed; this returns how much of each voice the mixer was heard to
do -- |contribution| summed across the frame's 800 samples, in the
mixer's own units, one word a voice. Together they close the machine's
own formula:

    Zvm(Wn)[An] -> Wn+1 + In + Sn,   then   Wn+1 = f(Wn, An, VIS, AUD)

Four bars stand in a row, one a voice, and each is as tall as that voice
was heard to be TWO frames ago -- not one. A frame's sound is not
finished when its draw is: the draw takes about 220,000 of a frame's
720,000 clocks and the samples keep coming for the rest of it, so at the
instant the machine writes its answers back the newest COMPLETE frame of
audio is the one before last. See spec.AUD_BASE. Nothing in the cart tracks how loud it made them --
it asks the machine what came out. The volumes roll, so the bars dance.

WHY BARS ARE NOT ENOUGH, and what the fifth object is for. `cross`
compares pictures and sample streams and never DMEM, so a number has to
become visible to be checkable -- and a bar's height is AUD >> 6, which
throws away six bits. Two machines could disagree by sixty and draw the
same bar. So a fifth cube, the marker, stands where the XOR-FOLD of all
sixteen words puts it: every bit of every voice lands in the low six,
and the low six move it a whole world unit a step. A one-unit
disagreement anywhere throws it somewhere else.

AND IT CARRIES AN EVENT LIST ON PURPOSE. Events change a voice's volume
partway through a frame, which is exactly where the silicon's tally was
wrong twice while it was being built: once counting an 801st sample
into a finished frame, and once running its walk before the frame's
registers had been loaded, so voices the law called silent came back
loud from the frame before. Both are invisible without a witness whose
volumes MOVE inside the frame. A steady tone would have passed either.

Run me after changing anything: python3 carts/witness/gen_heard.py
"""
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import carts as _carts                         # noqa: E402
_carts.on_path()                 # sibling generators, wherever they live
from zeta import spec                          # noqa: E402
from gen_cube import cube_mesh, data_lines, ground_mesh   # noqa: E402

ONE = 65536
GROUND_AT, CUBE_AT = 512, 1400
NV = 4                             # the four voices that have oscillators
A = spec.AUD_BASE
F, ACC, H = 16, 17, 18             # scratch
_OBJ = [spec.OL_BASE + 1 + k * spec.OL_STRIDE for k in range(2 + NV)]
_X, _Y, _Z = 1, 2, 3

# a chord, one note a voice, and the duties that make them read apart
INC = [38448, 45724, 57672, 24000]
DUTY = [0, 1, 0, 0]


def events():
    """Two volume steps a frame, so a voice's loudness MOVES inside the
    frame the tally is summing. w0 = offset | ch<<10 | ctrl, w1 = value."""
    # LATE IN THE FRAME, and that is not cosmetic. Fired at sample 200
    # the events owned three quarters of every frame and pinned each
    # total to their own two volumes: the voices still moved, but only
    # by 1.2 to 1.5 times, which is not enough to tell a total that
    # TRACKS from one that merely accumulates. From sample 600 the
    # rolling register volume owns most of the frame and the swing is
    # 7 to 23 times measured across the gate's window, while the events
    # still change a voice's loudness partway through -- which is the
    # case being witnessed.
    ev = []
    for c in range(NV):
        for off, vol in ((600 + 20 * c, 3), (700 + 20 * c, 11)):
            w0 = off | (c << spec.AU_EV_CH_SHIFT) | spec.AU_EV_CTRL_BIT
            ev.append((w0, vol | (DUTY[c] << 4)))
    return ev


PROGRAM = f"""
; ---- the volumes roll, so no two frames are the same ----------------
load {F}
push 1
add
push 1023
and
store {F}
"""


def program():
    p = [PROGRAM]
    for c in range(NV):
        # vol = ((frame >> 3) + 3c) & 15, written into the ctrl word
        # SHR 1, so a voice walks its whole 0..15 in 32 frames. At
        # shr 3 the cycle took 128 and the gate's 40-frame window saw
        # five steps of it, which reads as a total that barely moves.
        p += [f"load {F}", "shr 1", f"push {3 * c}", "add", "push 15", "and",
              f"push {DUTY[c] << 4}", "or", f"store {spec.AU_BASE + 2 * c + 1}"]
        # ---- THE BAR IS AS TALL AS THE VOICE WAS HEARD TO BE ---------
        # TWO frames back, not one, and for a physical reason rather
        # than a chosen one -- spec.AUD_BASE has it.
        p += [f"load {A + c}", "shr 6", f"push {ONE // 2}", "sub",
              f"store {_OBJ[1 + c] + _Y}"]
    # ---- the fold: every bit of every voice, into six ----------------
    p += ["push 0"]
    for c in range(spec.AU_CHANNELS):
        p += [f"load {A + c}", "xor"]
    p += [f"store {ACC}",
          f"load {ACC}", f"load {ACC}", "shr 4", "xor",
          f"load {ACC}", "shr 8", "xor",
          f"load {ACC}", "shr 12", "xor",
          f"load {ACC}", "shr 16", "xor",
          f"load {ACC}", "shr 20", "xor", f"store {H}",
          f"load {H}", "push 7", "and", "shl 16", "push 196608", "sub",
          f"store {_OBJ[1 + NV] + _X}",
          f"load {H}", "shr 3", "push 7", "and", "shl 16", "push 393216",
          "add", f"store {_OBJ[1 + NV] + _Z}",
          "halt"]
    return p


def main():
    g_verts, g_faces = ground_mesh(10, 1)
    c_verts, c_faces = cube_mesh()
    g_lines, g_len = data_lines(GROUND_AT, g_verts, g_faces)
    c_lines, c_len = data_lines(CUBE_AT, c_verts, c_faces)
    assert GROUND_AT + g_len <= CUBE_AT and CUBE_AT + c_len <= spec.DL_BASE

    E = spec.OBJ_CULL | spec.OBJ_EDGE
    objs = [(GROUND_AT, 0, 0, 0, 0, spec.OBJ_CULL)]
    for c in range(NV):                       # the four bars, in a row
        objs.append((CUBE_AT, round((c - 1.5) * 1.6 * ONE), 0,
                     round(4.5 * ONE), 0, E))
    objs.append((CUBE_AT, 0, 0, round(6.0 * ONE), 0, E))   # the marker
    ol = " ".join(str(v) for o in objs for v in o)
    ev = events()
    evw = " ".join(f"{w0} {w1}" for w0, w1 in ev)

    out = ["; heard.zol -- spec.AUD_BASE's witness. GENERATED by",
           "; carts/witness/gen_heard.py -- edit that, not this.",
           ";",
           "; Four bars, one a voice, each as tall as that voice was HEARD",
           "; to be last frame. The fifth cube stands where the xor-fold of",
           "; all sixteen totals puts it, so a one-unit disagreement",
           "; anywhere moves it and the pictures stop matching.",
           "",
           ".data 8 0 91750 -262144 0    ; camera: x 0, y 1.4, z -4",
           f".data {spec.EDGE_RGB} 16316096   ; 0xF8F8C0",
           ""]
    for c in range(NV):
        out.append(f".data {spec.AU_BASE + 2 * c} {INC[c]} {6 | (DUTY[c] << 4)}")
    out += ["",
            f"; the event list: {len(ev)} volume steps inside every frame",
            f".data {spec.AU_EV_BASE} {len(ev)} {evw}",
            "",
            f"; object list: {len(objs)} objects",
            f".data {spec.OL_BASE} {len(objs)} {ol}",
            "",
            f"; ---- ground mesh: {g_len} words ----"]
    out += g_lines
    out += ["", f"; ---- cube mesh: {c_len} words ----"] + c_lines
    out += [""] + program()
    path = Path(__file__).parent / "heard.zol"
    path.write_text("\n".join(out))
    print(f"wrote {path}: {NV} voices, {len(ev)} events, ground {g_len}w")


if __name__ == "__main__":
    main()
