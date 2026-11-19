# gen_tnd.py -- TEAR NOT DEMON on the Zeta, P1: the fighter. docs/TND-PORT.md.
#
# The July game's boxer (737 faces, 459 vertices, 67-joint skinning, float
# IK) played back BAKED: tools/tnd_extract.py freezes the archive's own
# animation; this quantises it to Q16.16 and lays it out so ONE mover
# request a frame repaints the whole body.
#
# TWO OBJECTS, ONE CUT. A Zeta object holds 256 vertices and 512 faces;
# the boxer needs two. Exactly one horizontal cut satisfies both limits,
# at hip height (archive z = 1.009): upper 378 faces / 253 vertices,
# lower 359 / 244. Seam vertices are DUPLICATED, and both halves bake
# from the same posed positions, so the waist cannot tear.
#
# ONE DMA, THE WHOLE SPAN. The two meshes sit back to back in DMEM, and
# the mover moves one contiguous block a frame, so each pose in the bank
# is the span from the upper vertices to the end of the lower faces --
# 2,967 words, inside DMA_MAX. Face colours ride inside the span, which
# means every pose carries THE ARCHIVE'S OWN PER-FACE SHADING for that
# frame: TND's light, played back rather than approximated.
#
# AXES. The archive is right-handed z-up, forward +x (the guard fists sit
# ahead of the torso along x). Zeta's view space is x-right, y-up,
# z-forward: left-handed. Mapping left->left keeps the lead hand on the
# correct side, at the price of mirroring winding -- hence FLIP below,
# set by looking at the first render rather than by assuming.

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import spec                                        # noqa: E402
from zeta.forge import ONE, Cart, Mesh, Table                # noqa: E402

HERE = Path(__file__).parent
# THE BUDGET HOOK: TND_OMIT=buildings,paint,... drops street parts and
# TND_OUT sends the variant elsewhere -- for decomposing the frame cost
# one part at a time (the street measured 94.8% before any demon).
import os                                                    # noqa: E402
OMIT = set(filter(None, os.environ.get("TND_OMIT", "").split(",")))
OUT = Path(os.environ.get("TND_OUT", HERE / "tnd.zol"))
BAKE = HERE.parent / "assets" / "tnd" / "boxer.npz"
CUT = 1.009                     # the one hip-height cut that fits both
FLIP = True                     # winding, after the left-handed mirror

d = np.load(BAKE)
F, C = d["F"], d["C"]
SEQS = ("idle", "walk", "jab")


def to_zeta(V):
    """archive (x fwd, y left, z up) -> zeta (x right, y up, z fwd)."""
    return np.stack((-V[:, 1], V[:, 2], V[:, 0]), axis=1)


def rgb(c):
    return (int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])


# ---- the cut, chosen on the bind-ish first idle frame -------------------
V0 = d["V_idle"][0]
upper = V0[F].mean(1)[:, 2] >= CUT
halves = []
for mask in (upper, ~upper):
    faces = F[mask]
    vids = np.unique(faces)                         # this half's vertices
    remap = {int(v): i for i, v in enumerate(vids)}
    tri = [(remap[int(a)], remap[int(b)], remap[int(c)]) for a, b, c in faces]
    if FLIP:
        tri = [(a, c, b) for a, b, c in tri]
    halves.append((mask, vids, tri))
assert all(len(v) <= spec.MESH_NV_MAX and len(t) <= spec.MESH_NF_MAX
           for _, v, t in halves)


def half_words(V, S, h):
    """One half as Mesh words for a pose: posed vertices, that frame's
    per-face shading."""
    mask, vids, tri = h
    P = np.round(to_zeta(V[vids]) * ONE).astype(np.int64).reshape(-1)
    cols = S[mask]
    faces = [(a, b, c, rgb(cols[k])) for k, (a, b, c) in enumerate(tri)]
    return Mesh(P.tolist(), faces).words()


def pose_span(V, S):
    """The DMA span for a pose: everything from the upper vertices to the
    end of the lower faces (both halves' words minus the upper header)."""
    return (half_words(V, S, halves[0])[2:] + half_words(V, S, halves[1]))


cart = Cart("tnd")

# ---- the body: two meshes, back to back, holding the first idle pose ----
first = half_words(d["V_idle"][0], d["S_idle"][0], halves[0]) \
    + half_words(d["V_idle"][0], d["S_idle"][0], halves[1])
BODY = cart.data(Table(first), "body")
SPAN = len(first) - 2
UPPER, LOWER = int(BODY), int(BODY) + len(half_words(
    d["V_idle"][0], d["S_idle"][0], halves[0]))
assert SPAN <= spec.DMA_MAX, f"pose span {SPAN} exceeds DMA_MAX"

# ---- the pose bank: every frame of every sequence, one span each ---------
bank, base = [], {}
for s in SEQS:
    base[s] = len(bank) // SPAN
    for V, S in zip(d["V_" + s], d["S_" + s]):
        bank += pose_span(V, S)
BANK = cart.cram(Table(bank), "poses")
NPOSE = {s: len(d["V_" + s]) for s in SEQS}

# ---- THE STREET: Bancroft and Shattuck, from the archive's constants -----
# tear.py:5176-5420 builds the "+" from hand-placed constants; the ~11,000
# triangles it submitted were mostly subdivision to dodge a near-plane
# reject the Zeta's clipper does not have. Here the asphalt is TEN faces.
# Archive world is (x, y, z-up) like the boxer, mapped the same way.
A_R = 11.0                       # ARENA_R
EDGE = A_R + 0.5                 # the slab overshoots the square
LANE = A_R - 3.2                 # street half-width, 7.8
REACH = 48.0                     # each arm's length: the archive's 54, cut
                                 # where its own fog is already total (47)
ROAD_HALF = A_R + 0.25
SW_OUT = LANE + 1.1              # the sidewalk's outer edge
ASPHALT, SIDEWALK = (46, 45, 49), (92, 90, 94)
PAINT, LINE = (200, 195, 185), (196, 168, 70)
BCOL = ((28, 22, 26), (34, 26, 24), (24, 20, 22), (30, 24, 28))


def W(x, y, z):
    """archive world -> zeta world, the boxer's own mapping."""
    return np.array((-y, z, x), float)


def shade(col, n):
    """the archive's shade(strength=0.4), as a fixed light per face."""
    k = {(0, 0, 1): 1.15, (1, 0, 0): 1.0, (-1, 0, 0): 0.78,
         (0, 1, 0): 0.9, (0, -1, 0): 0.86}.get(tuple(n), 1.0)
    return tuple(min(255, int(c * k)) for c in col)


class Build:
    """A mesh under construction, vertices shared by position."""
    def __init__(self):
        self.v, self.idx, self.f = [], {}, []

    def vert(self, P):
        key = tuple(int(round(c * ONE)) for c in P)
        if key not in self.idx:
            self.idx[key] = len(self.v)
            self.v.append(key)
        return self.idx[key]

    def quad(self, corners, n, col):
        """corners in archive space, in order round the quad; n its
        outward normal. Front-facing on this machine is (b-a)x(c-a)
        toward the viewer -- derived from the P1 floor, which drew from
        above -- so the order is CHECKED against n, never assumed."""
        P = [W(*c) for c in corners]
        ids = [self.vert(q) for q in P]
        a, b, c, d = ids
        if np.dot(np.cross(P[1] - P[0], P[2] - P[0]), W(*n)) < 0:
            a, b, c, d = a, d, c, b
        rgb_ = rgb(shade(col, n))
        self.f += [(a, b, c, rgb_), (a, c, d, rgb_)]

    def box(self, x0, x1, y0, y1, z0, z1, col, top=True,
            sides=((1, 0), (-1, 0), (0, 1), (0, -1))):
        """only the faces in `sides` (outward normals in x/y) are built:
        a face nobody can see still costs its setup, and a face behind
        another still costs every pixel it covers"""
        if top:
            self.quad([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
                      (0, 0, 1), col)
        if (1, 0) in sides:
            self.quad([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
                      (1, 0, 0), col)
        if (-1, 0) in sides:
            self.quad([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
                      (-1, 0, 0), col)
        if (0, 1) in sides:
            self.quad([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
                      (0, 1, 0), col)
        if (0, -1) in sides:
            self.quad([(x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0)],
                      (0, -1, 0), col)

    def flat(self, x0, x1, y0, y1, z, col):
        self.quad([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)],
                  (0, 0, 1), col)

    def mesh(self):
        assert len(self.v) <= spec.MESH_NV_MAX and len(self.f) <= spec.MESH_NF_MAX
        return Mesh([c for v in self.v for c in v], self.f)


street = []
road = Build()                   # the "+": the square and four arms
road.flat(-EDGE, EDGE, -EDGE, EDGE, 0.0, ASPHALT)
road.flat(EDGE, REACH, -LANE, LANE, 0.0, ASPHALT)
road.flat(-REACH, -EDGE, -LANE, LANE, 0.0, ASPHALT)
road.flat(-LANE, LANE, EDGE, REACH, 0.0, ASPHALT)
road.flat(-LANE, LANE, -REACH, -EDGE, 0.0, ASPHALT)
street.append(road) if "road" not in OMIT else None

walk = Build()                   # sidewalks: raised 0.12, curb faces in
for sgn in (-1, 1):
    a0, a1 = (EDGE, REACH) if sgn > 0 else (-REACH, -EDGE)
    for side in (-1, 1):
        l0, l1 = (LANE, SW_OUT) if side > 0 else (-SW_OUT, -LANE)
        walk.box(a0, a1, l0, l1, 0.0, 0.12, SIDEWALK,         # E/W arms
                 sides=((0, -side), (-sgn, 0)))
        walk.box(l0, l1, a0, a1, 0.0, 0.12, SIDEWALK,         # N/S arms
                 sides=((-side, 0), (0, -sgn)))
for sx in (-1, 1):
    for sy in (-1, 1):
        x0, x1 = sorted((sx * LANE, sx * EDGE))
        y0, y1 = sorted((sy * LANE, sy * EDGE))
        walk.box(x0, x1, y0, y1, 0.0, 0.12, SIDEWALK,         # corner pads
                 sides=((-sx, 0), (0, -sy)))
street.append(walk) if "sidewalks" not in OMIT else None

paint = Build()                  # the centreline and four zebra bands
for sgn in (-1, 1):
    a0, a1 = (EDGE, REACH) if sgn > 0 else (-REACH, -EDGE)
    paint.flat(a0, a1, -0.09, 0.09, 0.04, LINE)
    paint.flat(-0.09, 0.09, a0, a1, 0.04, LINE)
for off in (A_R - 2.0, -(A_R - 2.0)):
    x = -LANE
    while x < LANE:
        x1 = min(x + 0.7, LANE)
        paint.flat(x, x1, off - 1.5, off + 1.5, 0.04, PAINT)     # across x
        paint.flat(off - 1.5, off + 1.5, x, x1, 0.04, PAINT)     # across y
        x += 1.2
street.append(paint) if "paint" not in OMIT else None

blocks = []                      # 12 corner + 48 street buildings
for sx in (-1, 1):
    for sy in (-1, 1):
        for j in range(3):
            w = d = 4.6 + (j % 2) * 2.0
            h = 7.5 + j * 3.4
            col = BCOL[(j + (sx > 0) + 2 * (sy > 0)) % 4]
            bx = sx * (ROAD_HALF + w / 2 + j * 2.0)
            by = sy * (ROAD_HALF + d / 2 + j * 2.0)
            blocks.append((bx, by, w, d, h, col))
# THE STREET BUILDINGS BECOME FACADES. The archive's 48 boxes cost
# ~287k clocks a frame here -- measured, by omission -- because looking
# down an arm ten fronts a side stack in depth and the rasteriser pays
# every pixel of every face, hidden or not. A continuous facade per side
# keeps the archive's heights: one front a segment, plus only the height
# steps that FACE the crossing (the camera stands 2.15 high and the roofs
# are 8-17, so no roof is ever seen).
fac = Build()


def arm(dx, dy, u, v, z):
    """an arm's local frame (u out along the arm, v lateral) -> archive"""
    return (dx * u, v, z) if dx else (v, dy * u, z)


for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
    out = (dx, dy, 0)
    for side in (-1, 1):
        face_v = side * (LANE + 1.3)                     # the street wall
        back_v = side * (LANE + 1.3 + 6.0)
        n_front = (0, -side, 0) if dx else (-side, 0, 0)
        n_step = (-dx, -dy, 0)                           # toward the crossing
        segs = []
        for dist in range(20, 46, 6):
            h = 8.0 + ((dist // 6) % 3) * 4.5
            col = BCOL[(dist // 6 + (side > 0)) % 4]
            segs.append((dist - 3.0, dist + 3.0, h, col))
        prev_h = 0.0
        for u0, u1, h, col in segs:
            fac.quad([arm(dx, dy, u0, face_v, 0), arm(dx, dy, u1, face_v, 0),
                      arm(dx, dy, u1, face_v, h), arm(dx, dy, u0, face_v, h)],
                     n_front, col)
            if h > prev_h:                               # a step we can see
                fac.quad([arm(dx, dy, u0, face_v, prev_h),
                          arm(dx, dy, u0, back_v, prev_h),
                          arm(dx, dy, u0, back_v, h),
                          arm(dx, dy, u0, face_v, h)], n_step, col)
            prev_h = h
    # the end wall at the fog line: the fog turns it into the dusk
    w = LANE + 7.3
    fac.quad([arm(dx, dy, REACH - 1, -w, 0), arm(dx, dy, REACH - 1, w, 0),
              arm(dx, dy, REACH - 1, w, 18), arm(dx, dy, REACH - 1, -w, 18)],
             (-dx, -dy, 0), BCOL[0])
street.append(fac) if "buildings" not in OMIT else None
for k in range(0, len(blocks), 30):                  # 30 boxes a mesh
    b = Build()
    for bx, by, w, d, h, col in blocks[k:k + 30]:
        b.box(bx - w / 2, bx + w / 2, by - d / 2, by + d / 2, 0.0, h, col)
    street.append(b) if "buildings" not in OMIT else None

lamps = Build()                  # four streetlights, warm
for sx in (-1, 1):
    for sy in (-1, 1):
        x, y = sx * ROAD_HALF, sy * ROAD_HALF
        lamps.box(x - .07, x + .07, y - .07, y + .07, 0.0, 3.1, (18, 16, 18))
        lamps.box(x - .22, x + .22, y - .22, y + .22, 3.0, 3.3, (255, 200, 120))
street.append(lamps) if "lamps" not in OMIT else None

STREET = [int(cart.data(b.mesh(), f"street{i}")) for i, b in enumerate(street)]
STREET_FACES = sum(len(b.f) for b in street)

SIN = cart.data(Table([int(round(np.sin(i * 2 * np.pi / 1024) * ONE))
                       for i in range(1024)]), "sin")

PX, PZ, YAW = cart.var("px"), cart.var("pz"), cart.var("yaw")
ANIM, AF, POSE = cart.var("anim"), cart.var("af"), cart.var("pose")
CY = cart.var("cam_yaw")       # the camera's yaw, easing after his
IDLE = cart.var("idle_f")       # idle's own frame, WRAPPED -- never a
                                # modulo off REG_FRAME, whose cost would
                                # grow every frame for as long as you play
PV = cart.var("prevpad")
NOBJ = cart.var("nobj")

cart.boot(spec.CAM_Y, int(2.15 * ONE))           # the archive's follow height
cart.boot(spec.CAM_PITCH, 20)                    # ~0.12 rad DOWN: positive pitches down (the first cut had the sign backwards and put the horizon below centre)
cart.boot(spec.FOG_RGB, 0x6A2420)             # the dusk the street dissolves into
cart.boot(spec.FOG_NEAR, 15 * 512)              # archive _FOG_NEAR = 15 units
cart.boot(spec.FOG_SHIFT, 10)                   # full at 15 + 32 = 47 (archive 46)

p = cart.program()
WALK = int(0.032 * ONE)                          # the archive's walk pace
CAMD = 3                                         # camera distance, units
L = {k: p.label(k) for k in ("free", "noa", "jab", "walk", "idle",
                             "anim", "pj", "pi", "pd", "iw")}


def sin_of(q, plus=0, cell=None):
    """push sin(angle + plus) in Q16.16, from the 1024-entry table"""
    q.push(int(SIN)).load(YAW if cell is None else cell)
    if plus:
        q.push(plus).emit("add").push(1023).emit("and")
    q.emit("add", "loadi")


# ---- input: tank turn, walk, the jab ---------------------------------------
p.if_pad(spec.PAD_LEFT, lambda q: q.addi(YAW, -12))
p.if_pad(spec.PAD_RIGHT, lambda q: q.addi(YAW, 12))
p.load(YAW).push(1023).emit("and").store(YAW)

# a jab in progress owns the body until its frames are done
p.load(ANIM).push(2).emit("eq", f"jz {L['free']}")
p.addi(AF, 1)
p.load(AF).push(NPOSE["jab"]).emit("lt", f"jz {L['idle']}")
p.emit(f"jmp {L['anim']}")
p.mark(L["free"])
# a FRESH press of A starts the jab
p.emit("load 1", f"push {spec.PAD_A}", "and", f"jz {L['noa']}")
p.load(PV).push(spec.PAD_A).emit("and", f"jz {L['jab']}")
p.mark(L["noa"])
p.emit("load 1", f"push {spec.PAD_UP}", "and", f"jz {L['idle']}")
p.emit(f"jmp {L['walk']}")
p.mark(L["jab"])
p.set(ANIM, 2).set(AF, 0)
p.emit(f"jmp {L['anim']}")
p.mark(L["walk"])
p.set(ANIM, 1)
p.addi(AF, 1)
# forward is model +z, which the yaw carries to world (-sin, cos)
sin_of(p)
p.push(WALK).emit("mulq").load(PX).emit("swap", "sub").store(PX)
sin_of(p, 256)
p.push(WALK).emit("mulq").load(PZ).emit("add").store(PZ)
p.emit(f"jmp {L['anim']}")
p.mark(L["idle"])
p.set(ANIM, 0)

# ---- pose index: base[anim] + frame within the sequence --------------------
p.mark(L["anim"])
p.load(ANIM).emit(f"jz {L['pi']}")
p.load(ANIM).push(1).emit("eq", f"jz {L['pj']}")
p.load(AF).push(NPOSE["walk"] - 1).emit("and").push(base["walk"]).emit("add")
p.store(POSE).emit(f"jmp {L['pd']}")
p.mark(L["pj"])
p.load(AF).push(base["jab"]).emit("add").store(POSE).emit(f"jmp {L['pd']}")
p.mark(L["pi"])
p.addi(IDLE, 1)
p.load(IDLE).push(NPOSE["idle"]).emit("lt", f"jz {L['iw']}")
p.load(IDLE).push(base["idle"]).emit("add").store(POSE)
p.emit(f"jmp {L['pd']}")
p.mark(L["iw"])
p.set(IDLE, 0).set(POSE, base["idle"])
p.mark(L["pd"])

# ---- one mover request: the whole posed body -------------------------------
p.load(POSE).push(SPAN).emit("mul").push(int(BANK)).emit("add")
p.store(spec.DMA_SRC)
p.push(UPPER + 2).store(spec.DMA_DST)
p.push(SPAN).store(spec.DMA_LEN)
p.set(spec.DMA_GO, 1)

# ---- the camera: the archive's spring follow, in integers -------------------
# CY eases an eighth of the shortest arc toward his yaw each frame. An
# arithmetic >> 3 rounds toward minus infinity, so a small NEGATIVE gap
# would keep closing while a small positive one stalled at 0 -- the camera
# parked up to 2.8 degrees off on one side only. Inside 8 units it snaps.
snap_l = p.label("snap")
T = cart.var("cam_d")
p.load(YAW).load(CY).emit("sub").push(512).emit("add")
p.push(1023).emit("and").push(512).emit("sub").store(T)   # d in -512..511
p.load(T).emit("shr 3", "dup", f"jz {snap_l}")
p.load(CY).emit("add").push(1023).emit("and").store(CY)
p.emit(f"jmp {snap_l}_d")
p.mark(snap_l)
p.emit("drop").load(YAW).store(CY)                          # within 8: snap
p.mark(f"{snap_l}_d")
# ...and stands CAMD behind him along ITS yaw, not his
sin_of(p, cell=CY)
p.push(CAMD).emit("mul").load(PX).emit("add").store(spec.CAM_X)
sin_of(p, 256, cell=CY)
p.push(CAMD).emit("mul").load(PZ).emit("swap", "sub").store(spec.CAM_Z)
p.load(CY).store(spec.CAM_YAW)

# ---- the object list --------------------------------------------------------
p.set(NOBJ, 0)
for m in STREET:
    p.object(NOBJ, m, 0, 0, 0, 0, spec.OBJ_CULL)
for m in (UPPER, LOWER):
    p.object(NOBJ, m, (f"load {int(PX)}",), 0, (f"load {int(PZ)}",),
             (f"load {int(YAW)}",), spec.OBJ_CULL)
p.load(NOBJ).store(spec.OL_BASE)
p.emit("load 1").store(PV)
p.emit("halt")

out = cart.write(OUT)
print(cart.report())
print(f"street: {len(STREET)} meshes, {STREET_FACES} faces")
print(f"poses: {len(bank) // SPAN} x {SPAN} words = {len(bank)} words "
      f"of CRAM; bases {base}")
