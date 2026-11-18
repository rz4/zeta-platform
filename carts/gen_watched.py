#!/usr/bin/env python3
"""gen_watched.py -- writes carts/watched.zol: what spec.VIS_BASE is FOR.

Five figures stand in a ring around you. Each one walks toward you, and
each one stops dead the moment the panel is showing it. Turn with LEFT
and RIGHT. You have one pair of eyes and there are five of them, so the
question is never "can I stop them" -- it is "which one do I let move".

THE RULE IS ONE LINE, AND IT IS THE HARDWARE'S:

    if fewer than 20 pixels of this figure are on the panel, it advances

Not "is it inside the frustum", which is a guess a cart can make on its
own with four dot products. Not "is its centre behind a wall", which is
a raycast that gets a pillar's edge wrong. The number the rasterizer
hands back is HOW MANY PIXELS OF IT SURVIVED TO THE GLASS -- through
clipping, through the depth test, through everything drawn over it
afterwards. Peeking round a pillar with one corner showing is being
seen. That is the same test for the frustum, the wall and the crowd,
because all three end the same way: the pixel did not get there.

WHY THE ERA COULD NOT DO THIS. The occlusion query arrived on the PC in
2001 or so, and it was a second geometry pass, a pipeline flush and an
answer a frame or two late. A console of 2000 that wanted this rule
faked it: a cone test against the camera, plus hand-placed volumes
saying "you cannot be seen here". Zeta counts the pixels it was already
committing -- a read, an add and a write in one beat of a LUTRAM,
riding a walk that was carrying the band out to the framebuffer anyway.
It costs no clocks and no passes, and the answer is exact.

The counts are a frame old by construction, the same as the pick
register and for the same reason: the tally is not finished until the
last band is. At 60 Hz that is 16 ms of grace, which is generous to the
player and which no player will ever see.

Run me after changing anything: python3 carts/gen_watched.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from zeta import spec                          # noqa: E402
from gen_cube import cube_mesh, data_lines, ground_mesh   # noqa: E402

ONE = 65536
GROUND_AT, CUBE_AT = 512, 2100   # the 14x14 floor is 1,461 words
# WHERE THEY STAND, in 1024ths of a turn. EVENLY SPACED IS A MISTAKE:
# five at 72 degrees with a 60-degree view means you can never have two
# of them on the panel at once, so there is no choice to make -- only a
# rotation to perform. Spaced unevenly, two of them sometimes share a
# view and three of them never do, and the game becomes "which pair do I
# cover while the singles walk".
ANGLES = [0, 48, 132, 190, 262]
N = len(ANGLES)                    # figures in the ring
RING = 6.0                         # how far out they start
# UNWATCHED FRAMES TO CROSS THE RING, one a figure. All the same number
# and the best play is to spin on the spot forever, which is not a
# decision. Different numbers and the fast one has to be answered while
# the slow ones are only managed -- 4.3 seconds against 8.3.
NSTEPS = [260, 320, 380, 440, 500]
assert len(NSTEPS) == len(ANGLES)
SEEN = 20                          # pixels. Fewer than this is HIDDEN.
TURN = 6                           # yaw units a frame: 1024 is a turn
SPINE = 4                          # ...and how fast a figure turns

FLASH, SPIN, W, T = 16, 17, 18, 19   # scratch
AU_LO, AU_SPAN = 18000, 3          # the tracker's pitch floor, and the
                                   # shift that turns progress into rise
# A `push` immediate is 24 bits SIGNED, so a colour with a bright red or
# green channel sign-extends: push 0xFF2010 lands in DMEM as 0xFFFF2010.
# The two colours live in .data cells, which are a full word, and the
# program copies rather than pushes them.
C_NORMAL, C_FLASH = 40, 41
CTR = 20                           # CTR..CTR+N-1: steps each has taken
_OBJ = [spec.OL_BASE + 1 + k * spec.OL_STRIDE for k in range(1 + N)]
_X, _Y, _Z, _YAW = 1, 2, 3, 4
# A RED ALARM ON RED FIGURES IS NOT AN ALARM. The first version flashed
# the outline 0xFF2010 over cubes that are already red, and in a contact
# sheet of four caught frames the flash was invisible in every one. The
# palette has three signal colours against the black-and-white floor and
# the figures have taken red, so the alarm is green: distinct from the
# figures, from the ordinary pale line, and from the floor.
NORMAL_EDGE, FLASH_EDGE = 0xF8F8C0, 0x40FF80


def program():
    p = [".const PAD 1", ""]
    # ---- the head turns ------------------------------------------------
    p += ["; ---- you turn, and nothing else about you moves -------------",
          "load PAD", f"push {spec.PAD_LEFT}", "and", "jz t_l",
          f"load {spec.CAM_YAW}", f"push {1024 - TURN}", "add",
          "push 1023", "and", f"store {spec.CAM_YAW}", "t_l:",
          "load PAD", f"push {spec.PAD_RIGHT}", "and", "jz t_r",
          f"load {spec.CAM_YAW}", f"push {TURN}", "add",
          "push 1023", "and", f"store {spec.CAM_YAW}", "t_r:", ""]
    # ---- they turn too, which is what makes them read as facing you ----
    p += [f"load {SPIN}", f"push {SPINE}", "add", "push 1023", "and",
          f"store {SPIN}", ""]
    for k in range(N):
        th = math.radians(ANGLES[k])
        sx, sz = round(RING * ONE * math.sin(th)), round(RING * ONE * math.cos(th))
        ns = NSTEPS[k]
        dx = round(-RING * ONE * math.sin(th) / ns)
        dz = round(-RING * ONE * math.cos(th) / ns)
        o, c, v = _OBJ[1 + k], CTR + k, spec.VIS_BASE + 1 + k
        p += [f"; ---- figure {k}: {round(math.degrees(th))} degrees round "
              f"the ring ----------------",
              # THE WHOLE GAME. Fewer than SEEN pixels of it reached the
              # glass, so it takes a step. Nothing else is consulted.
              f"load {v}", f"push {SEEN}", "lt", f"jz w{k}",
              f"load {c}", "push 1", "add", f"store {c}", f"w{k}:",
              # it arrives: back to the ring, and the world flinches
              f"push {ns - 1}", f"load {c}", "lt", f"jz g{k}",
              "push 0", f"store {c}", "push 14", f"store {FLASH}", f"g{k}:",
              # position is start + steps*direction: no trigonometry at
              # run time, because the direction never changes
              f"load {c}", f"push {dx}", "mul", f"push {sx}", "add",
              f"store {o + _X}",
              f"load {c}", f"push {dz}", "mul", f"push {sz}", "add",
              f"store {o + _Z}",
              f"load {SPIN}", f"store {o + _YAW}", ""]
    # ---- THE TRACKER ----------------------------------------------------
    # You cannot see behind you, so the machine tells you the one thing
    # you most need and nothing else: HOW CLOSE THE NEAREST OF THEM IS TO
    # ARRIVING. Not where -- that would make turning around pointless --
    # just how long you have. A rising tone, and the only quiet frame is
    # one where nothing has started walking.
    #
    # Each figure crosses the ring in a different number of steps, so a
    # raw counter is not comparable between them. Each is scaled by a
    # constant chosen at build time -- 65536/steps -- which puts all five
    # on one scale of 0..65536 with no division at run time.
    p += ["; ---- the tracker: the pitch is the WORST of them ------------",
          "push 0", f"store {W}"]
    for k in range(N):
        p += [f"load {CTR + k}", f"push {65536 // NSTEPS[k]}", "mul",
              f"store {T}",
              f"load {W}", f"load {T}", "lt", f"jz n{k}",
              f"load {T}", f"store {W}", f"n{k}:"]
    p += ["",
          f"load {W}", f"shr {AU_SPAN}", f"push {AU_LO}", "add",
          f"store {spec.AU_BASE + 4}",
          f"load {W}", "shr 15", "push 3", "add",
          f"store {spec.AU_BASE + 5}", ""]
    # ---- the flinch ----------------------------------------------------
    p += ["; ---- one of them reached you: every outline goes red --------",
          f"load {C_NORMAL}", f"store {spec.EDGE_RGB}",
          f"load {FLASH}", "jz f_n",
          f"load {FLASH}", "push 1", "sub", f"store {FLASH}",
          f"load {C_FLASH}", f"store {spec.EDGE_RGB}", "f_n:",
          "halt"]
    return p


def main():
    g_verts, g_faces = ground_mesh(14, 1)
    c_verts, c_faces = cube_mesh()
    g_lines, g_len = data_lines(GROUND_AT, g_verts, g_faces)
    c_lines, c_len = data_lines(CUBE_AT, c_verts, c_faces)
    assert GROUND_AT + g_len <= CUBE_AT and CUBE_AT + c_len <= spec.DL_BASE

    E = spec.OBJ_CULL | spec.OBJ_EDGE
    objs = [(GROUND_AT, 0, 0, 0, 0, spec.OBJ_CULL)]
    for k in range(N):
        th = math.radians(ANGLES[k])
        objs.append((CUBE_AT, round(RING * ONE * math.sin(th)), 0,
                     round(RING * ONE * math.cos(th)), 0, E))
    ol = " ".join(str(v) for o in objs for v in o)

    out = ["; watched.zol -- what spec.VIS_BASE is FOR. GENERATED by",
           "; carts/gen_watched.py -- edit that, not this.",
           ";",
           "; Five figures in a ring. Each advances on any frame the panel",
           "; showed fewer than 20 pixels of it. LEFT and RIGHT turn your",
           "; head. You have one pair of eyes and they have five.",
           "",
           ".data 8 0 91750 0 0          ; camera: at the centre, y 1.4",
           f".data {spec.EDGE_RGB} {NORMAL_EDGE}",
           f".data {C_NORMAL} {NORMAL_EDGE} {FLASH_EDGE}",
           f".data {spec.AU_BASE + 4} 38448 6",
           "",
           f"; object list: {len(objs)} objects",
           f".data {spec.OL_BASE} {len(objs)} {ol}",
           "",
           f"; ---- ground mesh: {g_len} words ----"]
    out += g_lines
    out += ["", f"; ---- cube mesh: {c_len} words ----"] + c_lines
    out += [""] + program()
    path = Path(__file__).parent / "watched.zol"
    path.write_text("\n".join(out))
    print(f"wrote {path}: {N} figures, ground {g_len}w, cube {c_len}w")


if __name__ == "__main__":
    main()
