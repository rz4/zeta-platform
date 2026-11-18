#!/usr/bin/env python3
"""gen_fabric.py -- writes carts/fabric.zol: the world with no edge.

Roadmap 10b, the first rung. Every console generation scaled THE VIEW --
more triangles inside the frustum. This scales THE WORLD: you can walk
in any direction forever, the ground never ends, and the things standing
on it are the same things every time you come back.

Nothing is stored. The world is a pure function of where you are:

  THE GROUND is nine instances of one 16-unit plane, and the whole block
  SNAPS to the cell the camera stands in. Walk east; when you cross a
  cell boundary the block jumps 16 units east. The checker's period
  divides 16, so the jump is invisible -- the floor is a periodic field
  and the window slides over it. Infinite floor, nine object slots.

  THE PROPS are hashed. Cell (i,j) asks h(i,j) whether it holds a
  pillar, and if so where in the cell it stands, which way it faces, and
  which of the two colours it is. There is no table: h IS the world.
  This is the latent tier -- free to persist, because forgetting costs
  nothing when returning regrows it bit-identical.

  THE COMMITTED TIER is what you change. Press A and you plant a rubedo
  pillar in the cell under your feet, whether or not the hash put one
  there. That IS stored -- in eight words, a ring. Plant a ninth and the
  first is forgotten. A bounded store that coarsens on eviction, which
  is the honest version of "the world remembers": what you changed stays
  changed, up to a budget the machine states out loud.

  THE CONSOLE SAYS NO. The object list holds sixteen. Nine are floor, so
  seven props can stand at once. The cells are scanned NEAREST FIRST, so
  when the budget bites it drops the farthest thing -- the one already
  half-eaten by the fog. Fixed cost per frame, by law, never a longer
  frame.

Tank controls, as in orbit.zol: dpad left/right turns, up/down walks
along the heading, Y and B look up and down, A plants.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import spec                                    # noqa: E402
from gen_cube import ground_mesh, data_lines             # noqa: E402

ONE = 65536
CELL_SH = 21            # one world cell is 32 units, and 32 units in
                        # Q16.16 is exactly 2^21 -- so "which cell am I
                        # in" is a SHIFT, not a divide, and this machine
                        # has no divide. The cell size is chosen to make
                        # that true, which is why it is a power of two
                        # and not a round decimal.
SNAP_SH = 19            # ...but the ground SNAPS every 8 units, not every
                        # 32. The snap step only has to preserve the
                        # checker, and the checker's period is two tiles
                        # = 8 units; it does NOT have to equal the cell.
                        # Snapping by a whole cell let the camera drift 16
                        # units off the block's centre, which drags the
                        # block's leading edge from 64 units ahead in to
                        # 32 -- well inside the fog -- and then flings it
                        # back out. That retreat-and-return IS the seam.
                        # At 8 units the drift is 4 and the edge holds
                        # between 44 and 52.
FLOOR_N, FLOOR_TILE = 12, 4      # 48 units across, 288 faces, 169 verts
                                 # (the mesh cap is 256). How far you can
                                 # SEE is set by this and nothing else:
                                 #   range = (1.5*mesh - drift) * cos(40)
                                 # where 40 degrees is the screen's
                                 # diagonal half-angle and the cosine is
                                 # there because the block is a SQUARE --
                                 # its side edge sits nearer in view-depth
                                 # than its leading edge whenever you look
                                 # off-axis. That factor is why 48 units
                                 # of ground only bought 34 units of view.
MESH_SPAN = FLOOR_N * FLOOR_TILE * ONE   # the tiling stride, in Q16.16

# ---- DMEM map -------------------------------------------------------------
CI, CJ, K, DI, DJ, I, J, H = 16, 17, 18, 19, 20, 21, 22, 23
N, BASE, MK, FOUND, MN, PREVA, MESH, T = 24, 25, 26, 27, 28, 29, 30, 31
CP, STEP, SX, SZ, SI, SJ, H2 = 32, 33, 34, 35, 36, 37, 38

MARK_AT = 64            # 8 committed cells, 2 words each -- the ring
MARK_N = 8
SPIRAL = 96             # 9 (di,dj) pairs, nearest first
GROUND_AT = 320
PROP_AT = 1450          # five groves: four latent, one committed
PROP_STRIDE = 288
SINTAB = 2950

NEVER = 8388607         # a cell index no camera can reach: the empty
                        # mark slot. Zero would have meant "cell (0,0)
                        # is marked", and cell (0,0) is where you start.

C_LATENT = (0x46B87C, 0xC8A038, 0x7A8FC4, 0xB5734A)   # the hash picks
C_MARKED = 0xC42020                  # rubedo: the thing you put there

N_GROVE = len(C_LATENT) + 1
MARKED_AT = PROP_AT + (N_GROVE - 1) * PROP_STRIDE   # exported: the test
                                                    # used to recompute
                                                    # this and went stale
                                                    # the moment a fourth
                                                    # latent grove landed

# nearest first, so the object-list budget drops the FARTHEST cell
SPIRAL_ORDER = [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1),
                (1, 1), (-1, 1), (-1, -1), (1, -1)]


def shade(c, f):
    return ((min(255, int(((c >> 16) & 255) * f)) << 16)
            | (min(255, int(((c >> 8) & 255) * f)) << 8)
            | min(255, int((c & 255) * f)))


def post(verts, faces, cx, cz, w, h, colour):
    """One four-sided post, feet at y=0, appended to a mesh in progress.
    The sides are graded because flat shading gives a solid colour per
    face, and a post that is one colour all round is a silhouette."""
    n = len(verts) // 3
    hw, top = int(w * ONE / 2), int(h * ONE)
    cx, cz = int(cx * ONE), int(cz * ONE)
    for x, y, z in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]:
        verts += [cx + (-hw, hw)[x], (0, top)[y], cz + (-hw, hw)[z]]
    for (a, b, c, d), f in (((0, 1, 2, 3), 1.00), ((5, 4, 7, 6), 0.58),
                            ((4, 0, 3, 7), 0.76), ((1, 5, 6, 2), 0.76),
                            ((3, 2, 6, 7), 1.40)):
        col = shade(colour, f)
        faces += [(n + a, n + c, n + b, col), (n + a, n + d, n + c, col)]


# Each object slot draws a GROVE, not a post. The object list caps
# OBJECTS at sixteen; it says nothing about geometry, and this frame has
# headroom to spare -- so the unit of world content is a cluster of five
# or six posts, and a window of seven slots holds forty-odd standing
# things instead of seven. Same cost in the budget that is actually
# scarce.
GROVES = [
    [(0, 0, 1.4, 7.0), (4.5, 2.0, 0.9, 4.2), (-3.2, 3.6, 1.0, 5.1),
     (2.0, -4.4, 0.8, 3.4), (-4.8, -2.6, 1.1, 4.8)],
    [(0, 0, 2.2, 3.0), (0, 5.5, 1.5, 5.6), (5.0, -1.0, 1.2, 4.4),
     (-5.2, 1.2, 1.2, 4.4), (-1.0, -5.4, 1.6, 6.2), (3.4, 4.6, 0.9, 2.6)],
    [(-2.5, -2.5, 1.8, 8.4), (2.5, 2.5, 1.8, 6.6), (-2.5, 2.5, 1.0, 3.2),
     (2.5, -2.5, 1.0, 3.2)],
    [(0, 0, 3.0, 2.2), (0, 0, 1.0, 9.0), (5.6, 0, 0.7, 2.4),
     (-5.6, 0, 0.7, 2.4), (0, 5.6, 0.7, 2.4), (0, -5.6, 0.7, 2.4)],
    # ...and the LAST one is not a grove at all. What you plant should
    # look like something a person put there, and it appears in the cell
    # you are standing in -- a six-post cluster at that range fills the
    # screen. One slender stake reads as a mark; a grove reads as a bug.
    [(0, 0, 0.7, 4.0)],
]


def grove_mesh(shape, colour):
    verts, faces = [], []
    for cx, cz, w, h in GROVES[shape]:
        post(verts, faces, cx, cz, w, h, colour)
    return verts, faces


def hash_code(dst):
    """i,j -> a 23-bit hash, in the cells named I and J, result in `dst`.

    Every constant here fits the ISA's signed 24-bit immediate, which is
    why the multipliers are small and there are two rounds: one round of
    a 23-bit multiplier does not carry the low bits far enough, and the
    presence bit came out striped along j."""
    return [f"load {I}", "push 2654435", "mul",
            f"load {J}", "push 5147621", "mul", "add",
            "shr 8", f"push {NEVER}", "and",
            "push 1274127", "mul",
            "shr 7", f"push {NEVER}", "and",
            f"store {dst}"]


def mark_scan(tag):
    """FOUND := is cell (I,J) in the committed ring? `tag` because this
    is emitted twice and ZOL labels are one flat namespace."""
    return ["push 0", f"store {FOUND}", "push 0", f"store {MK}",
            f"{tag}_top:",
            f"load {MK}", "shl 1", f"push {MARK_AT}", "add", f"store {T}",
            f"load {T}", "loadi", f"load {I}", "eq", f"jz {tag}_next",
            f"load {T}", "push 1", "add", "loadi", f"load {J}", "eq",
            f"jz {tag}_next",
            "push 1", f"store {FOUND}",
            f"{tag}_next:",
            f"load {MK}", "push 1", "add", f"store {MK}",
            f"load {MK}", f"push {MARK_N}", "lt", f"jz {tag}_done",
            f"jmp {tag}_top",
            f"{tag}_done:"]


def grove_from(hc):
    """One grove, placed by the hash in cell `hc`. The grove stands
    OFF-CENTRE in its cell: a grid of posts reads as a grid, not as a
    world. The +2 units centres the spread -- three bits give 0..7 and
    -4 makes that -4..+3, which is LOPSIDED, and at four units a step
    the low end landed exactly on the cell boundary, where "which cell
    owns this grove" has no answer."""
    return put_obj(
        [f"load {MESH}"],
        [f"load {I}", f"shl {CELL_SH}",
         f"load {hc}", "shr 4", "push 7", "and", "push 4", "sub",
         "shl 18", f"push {2 * ONE}", "add", "add"],
        [f"load {J}", f"shl {CELL_SH}",
         f"load {hc}", "shr 8", "push 7", "and", "push 4", "sub",
         "shl 18", f"push {2 * ONE}", "add", "add"],
        # THE YAW COMES FROM BITS 11..20, AND USED TO COME FROM 16..25.
        # The hash is 23 bits (NEVER), so bits 23, 24 and 25 are always
        # zero: the yaw spanned 128 of 1024 values and every prop in the
        # world faced within ONE OCTANT. 44.6 degrees, recorded as an
        # open defect for a long time, and it was three bits that do not
        # exist. Bits 11..20 are inside the hash and unclaimed --
        # presence takes bit 0, the offsets take 4..6 and 8..10.
        [f"load {hc}", "shr 11", "push 1023", "and"])


def put_obj(mesh_ops, x_ops, z_ops, yaw_ops):
    """Write object N of the list, then N := N+1. The entry address is
    computed, so the same twenty instructions place every object -- the
    floor and the props alike."""
    out = [f"load {N}", f"push {spec.OL_STRIDE}", "mul",
           f"push {spec.OL_BASE + 1}", "add", f"store {BASE}"]
    for k, ops in enumerate((mesh_ops, x_ops, None, z_ops, yaw_ops, None)):
        out += (ops if ops is not None else ["push 0"] if k == 2
                else [f"push {spec.OBJ_CULL}"])
        out += [f"load {BASE}", f"push {k}", "add", "storei"]
    return out + [f"load {N}", "push 1", "add", f"store {N}"]


def main():
    g_verts, g_faces = ground_mesh(FLOOR_N, FLOOR_TILE)
    g_lines, g_len = data_lines(GROUND_AT, g_verts, g_faces)
    assert GROUND_AT + g_len <= PROP_AT, "ground overruns the pillars"

    p_lines = []
    palette = C_LATENT + (C_MARKED,)
    for k, col in enumerate(palette):
        pv, pf = grove_mesh(k, col)
        lines, plen = data_lines(PROP_AT + k * PROP_STRIDE, pv, pf)
        assert plen <= PROP_STRIDE, f"grove {k} is {plen} words"
        assert len(pv) // 3 <= spec.MESH_NV_MAX, f"grove {k} has too many verts"
        p_lines += lines
    assert len(palette) == N_GROVE
    assert PROP_AT + N_GROVE * PROP_STRIDE <= SINTAB, "groves reach the sines"

    SPEED = 0.12
    sintab = [int(round(math.sin(i * 8 * math.tau / 1024) * ONE * SPEED))
              for i in range(128)]
    assert SINTAB + 128 <= spec.DL_BASE

    head = ["; fabric.zol -- the world with no edge.",
            "; GENERATED -- edit gen_fabric.py, not this.",
            ";",
            "; Walk in any direction forever. The ground is a periodic",
            "; field the window slides over; the pillars are a hash of",
            "; the cell they stand in, so they regrow identical every",
            "; time you return. Press A to plant one that is NOT in the",
            "; hash -- eight of those are remembered, then the oldest is",
            "; forgotten.",
            "",
            ".const PAD 1",
            "",
            # EYE HEIGHT 5, NOT 3. This machine has no near-plane
            # clipping: a face with any vertex nearer than ZNEAR is
            # dropped WHOLE, so the ground tile under you vanishes and
            # the backdrop shows through the floor. The hole is one tile
            # wide and it travels with you -- which is exactly what
            # "tiles disappear under the camera" looks like. Sweeping
            # eye height against every reachable pitch: at 3 units it
            # costs up to 15,360 pixels, at 4 it still shows at one
            # angle, at 5 it is ZERO everywhere. Lifting the eye does
            # not fix the hole; it puts it outside the frustum, which is
            # all the player can tell apart.
            f".data {spec.CAM_X} 0 327680 0 0     ; standing at 0,0",
            # THE FOG IS THE CLEAR COLOUR, exactly. A face at full fog
            # then equals the empty frame behind it, so the far edge of
            # the ground does not fade to a DIFFERENT dark and draw a
            # horizon line where the world stops -- it fades into the
            # backdrop and there is no line to see. This is the whole
            # trick that makes 96 units of floor read as endless.
            f".data {spec.FOG_RGB} 0x{spec.CLEAR_RGB:06X}",
            # THE FOG SETS THE WORLD'S SIZE, and the number is MEASURED,
            # not chosen. z16 is view depth >> 7. Sweeping every camera
            # offset inside one snap step, every yaw, and every reachable
            # pitch, the shallowest the ground's edge ever comes while
            # still on screen is 53.65 units; the sixteenth fog step at
            # shift 10 lands on 27392 = 53.5, just inside it. So the air
            # is always complete before the floor runs out, from every
            # angle, and the edge cannot be seen at all.
            # Reasoning it out by hand gave 48 and was wrong twice: the
            # camera drifts inside its snap step, and a SQUARE block
            # presents its side edge nearer in view-depth than its front.
            f".data {spec.FOG_NEAR} 11008",
            f".data {spec.FOG_SHIFT} 10",
            ""]

    marks = " ".join(f"{NEVER} 0" for _ in range(MARK_N))
    head.append(f".data {MARK_AT} {marks}   ; the committed ring, empty")
    spir = " ".join(f"{a} {b}" for a, b in SPIRAL_ORDER)
    head.append(f".data {SPIRAL} {spir}     ; nearest first")
    head += [f".data {SINTAB + o} "
             + " ".join(str(v) for v in sintab[o:o + 12])
             for o in range(0, len(sintab), 12)]
    head.append("")

    P = []
    # the gaze starts tilted DOWN a little. Level, this world is half
    # empty sky, and the floor -- the thing that proves it is endless --
    # is squeezed into the bottom third.
    P += ["load 0", "jz first", "jmp go", "first:",
          f"push 34", f"store {CP}", "go:"]
    # ---- tank controls, the same law orbit.zol proved ---------------------
    # RIGHT DECREASES the yaw. Measured, like the pitch sign before it:
    # an object at +x slides FURTHER right as CAM_YAW rises, so a rising
    # yaw swings the gaze LEFT. Both of these were written the way the
    # name suggests instead of the way the machine behaves.
    P += ["load PAD", "push 8", "and", "jz g_r",
          f"load {spec.CAM_YAW}", "push 8", "sub", "push 1023", "and",
          f"store {spec.CAM_YAW}", "g_r:",
          "load PAD", "push 4", "and", "jz g_l",
          f"load {spec.CAM_YAW}", "push 8", "add", "push 1023", "and",
          f"store {spec.CAM_YAW}", "g_l:",
          # CAM_PITCH counts DOWNWARD -- +90 puts the gaze on the floor.
          # Measured, not read off the name: orbit.zol assumed the other
          # sign and its Y and B have been backwards ever since.
          "load PAD", f"push {spec.PAD_Y}", "and", "jz g_u",
          f"load {CP}", "push 4", "sub", f"store {CP}", "g_u:",
          "load PAD", f"push {spec.PAD_B}", "and", "jz g_d",
          f"load {CP}", "push 4", "add", f"store {CP}", "g_d:",
          f"load {CP}", "push -114", "lt", "jz cp_lo",
          "push -114", f"store {CP}", "cp_lo:",
          "push 114", f"load {CP}", "lt", "jz cp_hi",
          "push 114", f"store {CP}", "cp_hi:",
          f"load {CP}", "push 1023", "and", f"store {spec.CAM_PITCH}",
          # the feet: forward is (-sin, +cos) of the yaw
          "load PAD", "push 3", "and", "jz no_walk",
          f"load {spec.CAM_YAW}", "shr 3", "push 127", "and", f"store {STEP}",
          f"load {STEP}", f"push {SINTAB}", "add", "loadi", f"store {SX}",
          f"load {STEP}", "push 32", "add", "push 127", "and",
          f"push {SINTAB}", "add", "loadi", f"store {SZ}",
          "load PAD", "push 1", "and", "jz walk_back",
          f"load {spec.CAM_X}", f"load {SX}", "sub", f"store {spec.CAM_X}",
          f"load {spec.CAM_Z}", f"load {SZ}", "add", f"store {spec.CAM_Z}",
          "jmp no_walk",
          "walk_back:",
          f"load {spec.CAM_X}", f"load {SX}", "add", f"store {spec.CAM_X}",
          f"load {spec.CAM_Z}", f"load {SZ}", "sub", f"store {spec.CAM_Z}",
          "no_walk:"]

    # ---- which cell am I standing in ---------------------------------------
    # rounded, not floored: the camera should sit at the CENTRE of the
    # instance it is on, so the nine-block reaches equally far in every
    # direction. Half a cell in Q16.16 is 2^19.
    # Both of these round to nearest, and both offsets are DERIVED. The
    # half-cell was once written out as 524288 and stayed that way when
    # the cell doubled -- which put the camera 8 units behind its own
    # cell centre and 24 ahead, so groves appeared 24 units in front of
    # you where the fog is barely a quarter on.
    P += [f"load {spec.CAM_X}", f"push {1 << (CELL_SH - 1)}", "add",
          f"shr {CELL_SH}", f"store {CI}",
          f"load {spec.CAM_Z}", f"push {1 << (CELL_SH - 1)}", "add",
          f"shr {CELL_SH}", f"store {CJ}",
          f"load {spec.CAM_X}", f"push {1 << (SNAP_SH - 1)}", "add",
          f"shr {SNAP_SH}", f"store {SI}",
          f"load {spec.CAM_Z}", f"push {1 << (SNAP_SH - 1)}", "add",
          f"shr {SNAP_SH}", f"store {SJ}"]

    # ---- plant: A, on the edge, marks the cell under the camera -----------
    P += ["load PAD", f"push {spec.PAD_A}", "and", f"store {T}",
          f"load {T}", "jz a_up",
          f"load {PREVA}", "jz do_plant",     # held: already planted
          "jmp a_up",
          "do_plant:",
          f"load {CI}", f"store {I}", f"load {CJ}", f"store {J}"]
    P += mark_scan("pl")
    P += [f"load {FOUND}", "jz plant_new",    # already committed: no dupe
          "jmp a_up",
          "plant_new:",
          f"load {MN}", f"push {MARK_N - 1}", "and", "shl 1",
          f"push {MARK_AT}", "add", f"store {T}",
          f"load {CI}", f"load {T}", "storei",
          f"load {CJ}", f"load {T}", "push 1", "add", "storei",
          f"load {MN}", "push 1", "add", f"store {MN}",
          "a_up:",
          f"load {T}", f"store {PREVA}"]

    # ---- the ground: nine instances, snapped to the window ----------------
    P += ["push 0", f"store {N}", "push 0", f"store {K}",
          "gr_top:",
          f"load {K}", "shl 1", f"push {SPIRAL}", "add", f"store {T}",
          f"load {T}", "loadi", f"store {I}",
          f"load {T}", "push 1", "add", "loadi", f"store {J}"]
    # The instances are spaced by the MESH, not by the cell. Those were
    # the same number until the mesh grew to 48 units and the spacing
    # stayed a shift of 32 -- the nine planes then OVERLAPPED by 16 units
    # each way, costing a third of the block's reach and drawing the
    # overlaps twice. Nothing in the picture showed it, because the
    # checker's period divides both numbers, so the doubled strips agreed
    # exactly. 48 units is not a power of two, hence a multiply; it still
    # fits the signed 24-bit immediate with room to spare.
    P += put_obj([f"push {GROUND_AT}"],
                 [f"load {I}", f"push {MESH_SPAN}", "mul",
                  f"load {SI}", f"shl {SNAP_SH}", "add"],
                 [f"load {J}", f"push {MESH_SPAN}", "mul",
                  f"load {SJ}", f"shl {SNAP_SH}", "add"],
                 ["push 0"])
    P += [f"load {K}", "push 1", "add", f"store {K}",
          f"load {K}", "push 9", "lt", "jz gr_done", "jmp gr_top",
          "gr_done:"]

    # ---- the props: the same nine cells, nearest first, until full --------
    P += ["push 0", f"store {K}",
          "pr_top:",
          f"load {N}", f"push {spec.OL_MAX}", "lt", "jz pr_done",
          f"load {K}", "shl 1", f"push {SPIRAL}", "add", f"store {T}",
          f"load {T}", "loadi", f"load {CI}", "add", f"store {I}",
          f"load {T}", "push 1", "add", "loadi", f"load {CJ}", "add",
          f"store {J}"]
    P += hash_code(H)
    P += mark_scan("pm")
    # a committed cell ALWAYS holds a pillar, hash or no hash
    P += [f"load {FOUND}", "jz pr_latent",
          f"push {MARKED_AT}", f"store {MESH}",
          "jmp pr_place",
          "pr_latent:",
          f"load {H}", "push 1", "and", "jz pr_next",   # the hash says no
          f"load {H}", "shr 12", "push 3", "and",
          f"push {PROP_STRIDE}", "mul", f"push {PROP_AT}", "add",
          f"store {MESH}",
          "pr_place:"]
    P += grove_from(H)
    # ---- a SECOND grove in the same cell, from a rehash -------------------
    # OL_MAX was 16 and nine of those were ground, so one grove per cell
    # was all a cell could ever hold. At 64 the cell can be a place rather
    # than a landmark. The rehash is one multiply: H's bits are spent
    # (presence, offset, mesh, yaw all read from it), so a second grove
    # needs a second number, not a second slice of the same one.
    P += [f"load {N}", f"push {spec.OL_MAX}", "lt", "jz pr_next",
          f"load {H}", "push 1274127", "mul", "shr 5",
          f"push {NEVER}", "and", f"store {H2}",
          f"load {H2}", "push 1", "and", "jz pr_next",
          f"load {H2}", "shr 12", "push 3", "and",
          f"push {PROP_STRIDE}", "mul", f"push {PROP_AT}", "add",
          f"store {MESH}"]
    P += grove_from(H2)
    P += ["pr_next:",
          f"load {K}", "push 1", "add", f"store {K}",
          f"load {K}", "push 9", "lt", "jz pr_done", "jmp pr_top",
          "pr_done:",
          f"load {N}", f"store {spec.OL_BASE}",
          "halt"]

    body = head + g_lines + [""] + p_lines + [""] + P
    (HERE / "fabric.zol").write_text("\n".join(body) + "\n")
    n = sum(1 for ln in P if ln and not ln.endswith(":"))
    print(f"wrote fabric.zol: {n} instructions, "
          f"9 floor + up to {spec.OL_MAX - 9} groves, "
          f"{MARK_N} committed cells")


if __name__ == "__main__":
    main()
