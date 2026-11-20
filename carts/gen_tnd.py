# gen_tnd.py -- TEAR NOT DEMON on the Zeta. docs/TND-PORT.md.
#   P1 the fighter (below), P2 the street, P3 the demons -- and the frame
#   budget work that let all three fit (docs/TND-PORT.md, "the frame,
#   measured"; tools/tnd_meter.py).
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
from zeta.forge import ONE, Cart, Mesh, Plate, Table, Text                # noqa: E402

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
SEQS = ("idle", "walk", "jab", "cross", "lead_hook", "rear_hook", "special",
        "lead_uppercut", "rear_uppercut")


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


# THE HUD'S PROMISE: at most 64 display-list triangles, ever -- the rank
# (SSS: 30) and the combo (X99: 28) together, or RETRY (34) alone -- so the
# list's other 1,344 words hold content.
DL_LEASE = 64
cart = Cart("tnd", dl_lease=DL_LEASE)

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

    def quad(self, corners, n, col, nu=1, nv=1):
        """corners in archive space, in order round the quad; n its
        outward normal. Front-facing on this machine is (b-a)x(c-a)
        toward the viewer -- derived from the P1 floor, which drew from
        above -- so the order is CHECKED against n, never assumed.
        nu, nv cut it into a grid (along c0->c1, c0->c3): see SPLIT."""
        C = [np.array(c, float) for c in corners]
        for i in range(nu):
            for j in range(nv):
                def at(u, v):
                    return (C[0] * (1 - u) * (1 - v) + C[1] * u * (1 - v)
                            + C[2] * u * v + C[3] * (1 - u) * v)
                u0, u1, v0, v1 = i / nu, (i + 1) / nu, j / nv, (j + 1) / nv
                self._quad1([at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)],
                            n, col)

    def _quad1(self, corners, n, col):
        P = [W(*c) for c in corners]
        ids = [self.vert(q) for q in P]
        a, b, c, d = ids
        if np.dot(np.cross(P[1] - P[0], P[2] - P[0]), W(*n)) < 0:
            a, b, c, d = a, d, c, b
        rgb_ = rgb(shade(col, n))
        self.f += [(a, b, c, rgb_), (a, c, d, rgb_)]

    def box(self, x0, x1, y0, y1, z0, z1, col, top=True,
            sides=((1, 0), (-1, 0), (0, 1), (0, -1)), nx=1, ny=1):
        """only the faces in `sides` (outward normals in x/y) are built:
        a face nobody can see still costs its setup, and a face behind
        another still costs every pixel it covers. nx, ny: pieces along
        x and y, on every face that runs that way."""
        if top:
            self.quad([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
                      (0, 0, 1), col, nx, ny)
        if (1, 0) in sides:
            self.quad([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
                      (1, 0, 0), col, ny, 1)
        if (-1, 0) in sides:
            self.quad([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
                      (-1, 0, 0), col, 1, ny)
        if (0, 1) in sides:
            self.quad([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
                      (0, 1, 0), col, nx, 1)
        if (0, -1) in sides:
            self.quad([(x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0)],
                      (0, -1, 0), col, 1, nx)

    def flat(self, x0, x1, y0, y1, z, col, nx=1, ny=1):
        self.quad([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)],
                  (0, 0, 1), col, nx, ny)

    def mesh(self):
        assert len(self.v) <= spec.MESH_NV_MAX and len(self.f) <= spec.MESH_NF_MAX
        return Mesh([c for v in self.v for c in v], self.f)

    def meshes(self):
        """as many meshes as the object limits need, faces in order"""
        out, cur, vmap = [], [], {}
        for f in self.f + [None]:
            need = 0 if f is None else len({*f[:3]} - vmap.keys())
            if f is None or len(vmap) + need > spec.MESH_NV_MAX \
                    or len(cur) + 1 > spec.MESH_NF_MAX:
                if cur:
                    vs = sorted(vmap, key=vmap.get)
                    out.append(Mesh([c for v in vs for c in self.v[v]], cur))
                cur, vmap = [], {}
                if f is None:
                    break
            for v in f[:3]:
                vmap.setdefault(v, len(vmap))
            cur.append((vmap[f[0]], vmap[f[1]], vmap[f[2]], f[3]))
        return out


# ---- P3: THE DEMONS -- three builds of one rigid rig ------------------------
# The archive's demons are not skinned: rig.fighter is 17 rigid joints,
# and five of them (neck, both fists, both feet) never rotate against
# their parent -- MEASURED over every clip, max deviation 0.0 -- so they
# merge into it. Twelve parts, twelve objects a demon, each placed by its
# own angles word (yaw | pitch << 10 | roll << 20, spec.OL_STRIDE).
#
# WHAT IS BAKED AND WHAT IS NOT. A joint's character-local ROTATION
# depends only on the pose; its POSITION depends on the build too (the
# brute is 1.35 tall, the heavy 0.95). So the clip table holds one packed
# angles word per part per frame and serves all three builds, and the
# cart walks the offsets through the parents at run time -- three small
# rotations a part, the same chain the GPU itself runs. That is the
# difference between 1,392 words of clips and 4,176.
#
# LEFT IS RIGHT. A shoulder's mesh in its own frame is identical on both
# sides (checked: every vertex, every colour), so the two arms and the
# two legs draw from one mesh each: eight meshes a build, not twelve.
DEM = np.load(HERE.parent / "assets" / "tnd" / "demons.npz")
JN = list(DEM["names"])
PARTS = (  # part, joints merged into it (root first), parent part, mesh key
    ("pelvis", ("pelvis",), None, "pelvis"),
    ("spine", ("spine",), "pelvis", "spine"),
    ("chest", ("chest", "neck"), "spine", "chest"),
    ("head", ("head",), "chest", "head"),
    ("shoulder_l", ("shoulder_l",), "chest", "shoulder"),
    ("elbow_l", ("elbow_l", "fist_l"), "shoulder_l", "elbow"),
    ("shoulder_r", ("shoulder_r",), "chest", "shoulder"),
    ("elbow_r", ("elbow_r", "fist_r"), "shoulder_r", "elbow"),
    ("hip_l", ("hip_l",), "pelvis", "hip"),
    ("knee_l", ("knee_l", "foot_l"), "hip_l", "knee"),
    ("hip_r", ("hip_r",), "pelvis", "hip"),
    ("knee_r", ("knee_r", "foot_r"), "hip_r", "knee"),
)
PN = [pt[0] for pt in PARTS]
NPART = len(PARTS)
CLIPS = ("idle", "walk", "cross", "hook", "hurt", "dead")
MOVES = DEM["moves"]                       # cross, hook: startup active recovery dmg

# archive -> zeta for vectors and for rotations: M is a reflection, so a
# rotation conjugates (R' = M R M^T) and stays a rotation
MZ = np.array(((0, -1, 0), (0, 0, 1), (1, 0, 0)), float)


def euler(R):
    """R (zeta axes) = Yaw(y) Pitch(p) Roll(r), the GPU's model order, as
    10-bit units. At the pole pitch takes it all and roll is 0."""
    p = np.arcsin(np.clip(-R[1, 2], -1, 1))
    if abs(np.cos(p)) < 1e-6:
        r, y = 0.0, np.arctan2(R[2, 0], R[0, 0])
    else:
        r = np.arctan2(R[1, 0], R[1, 1])
        y = np.arctan2(-R[0, 2], R[2, 2])
    u = [int(round(a * 1024 / (2 * np.pi))) & 1023 for a in (y, p, r)]
    return u[0] | u[1] << 10 | u[2] << 20


def rot_units(w):
    """the packed word back to a matrix, for the bake's own check"""
    y, p, r = [((w >> s) & 1023) * 2 * np.pi / 1024 for s in (0, 10, 20)]
    cy, sy, cp, sp, cr, sr = np.cos(y), np.sin(y), np.cos(p), np.sin(p), \
        np.cos(r), np.sin(r)
    Ry = np.array(((cy, 0, -sy), (0, 1, 0), (sy, 0, cy)))
    Rp = np.array(((1, 0, 0), (0, cp, -sp), (0, sp, cp)))
    Rr = np.array(((cr, -sr, 0), (sr, cr, 0), (0, 0, 1)))
    return Ry @ Rp @ Rr


def shells(tris):
    """connected pieces of a triangle soup (by shared positions): each is
    one of the archive's convex solids"""
    key = lambda v: tuple(np.round(v, 6))                      # noqa: E731
    par = {}

    def find(a):
        while par.setdefault(a, a) != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for t in tris:
        ks = [key(v) for v in t]
        for k in ks[1:]:
            par[find(ks[0])] = find(k)
    return [find(key(t[0])) for t in tris]


def part_mesh(tris, cols):
    """archive-local triangles -> a Zeta mesh, every face wound OUTWARD
    from its own solid's centre. The archive drew both sides, so its
    tapers are wound inward (chest 40% outward, neck 0%); this machine
    culls, so the bake decides, solid by solid."""
    Z = tris @ MZ.T
    sid = shells(tris)
    cen = {s: Z[[i for i, x in enumerate(sid) if x == s]].reshape(-1, 3).mean(0)
           for s in set(sid)}
    b = Build()
    for t, c, s in zip(Z, cols, sid):
        ids = [b.vert(v) for v in t]
        n = np.cross(t[1] - t[0], t[2] - t[0])
        if np.dot(n, t.mean(0) - cen[s]) < 0:
            ids = [ids[0], ids[2], ids[1]]
        b.f.append((*ids, rgb(c)))
    return b.mesh()


def joint_geom(i, j):
    k = JN.index(j)
    return DEM[f"b{i}_j{k}_tris"], DEM[f"b{i}_j{k}_cols"]


def offset(i, j):
    return DEM[f"b{i}_offset"][JN.index(j)]


DMESH, DJT = [], []                    # per build: mesh syms, joint table
for i in range(3):
    meshes = {}
    for name, joints, parent, mk in PARTS:
        if mk in meshes:
            continue
        T, C = [], []
        acc = np.zeros(3)
        for n, j in enumerate(joints):          # merged joints, rigid chain
            if n:
                acc = acc + offset(i, j)
            t, c = joint_geom(i, j)
            T.append(t + acc)
            C.append(c)
        if name == "head":
            T.append(DEM[f"b{i}_spike_tris"])
            C.append(DEM[f"b{i}_spike_cols"])
        meshes[mk] = cart.data(part_mesh(np.concatenate(T), np.concatenate(C)),
                               f"demon{i}_{mk}")
    DMESH.append(meshes)

PT = cart.var("dem_pt", 3 * NPART)     # FK scratch: char-local part origins
rows_all = []
for i in range(3):
    rows = []
    for name, joints, parent, mk in PARTS:
        o = offset(i, joints[0])
        if name == "head":                     # through the merged neck
            o = o + offset(i, "neck")
        par = PN.index(parent) if parent else -1
        oz = MZ @ o
        rows += [par, int(PT) + 3 * max(par, 0)] + \
            [int(round(v * ONE)) for v in oz] + [int(DMESH[i][mk])]
    DJT.append(cart.data(Table(rows), f"demon{i}_joints"))
    rows_all.append(rows)

# the clip table: one packed angles word per part per frame
clipw, CLIP0 = [], {}
for c in CLIPS:
    CLIP0[c] = len(clipw) // NPART
    R = DEM["R_" + c]
    for f in range(len(R)):
        for name, joints, *_ in PARTS:
            clipw.append(euler(MZ @ R[f, JN.index(joints[0])] @ MZ.T))
CLIPT = cart.data(Table(clipw), "demon_clips")
CLIPN = {c: len(DEM["R_" + c]) for c in CLIPS}

# THE BAKE CHECKS ITSELF: the run-time chain, done here in floats with the
# QUANTISED angles, must put every joint where the archive's own FK did.
_err = 0.0
for i in range(3):
    for c in CLIPS:
        T = DEM["T_" + c][i]
        for f in range(len(T)):
            P = []
            for k, (name, joints, parent, mk) in enumerate(PARTS):
                o = np.array(rows_all[i][6 * k + 2:6 * k + 5]) / ONE
                if parent is None:
                    P.append(o)
                else:
                    q = PN.index(parent)
                    P.append(P[q] + rot_units(clipw[(CLIP0[c] + f) * NPART + q]) @ o)
                _err = max(_err, np.abs(P[k] - MZ @ T[f, JN.index(joints[0])]).max())
assert _err < 0.01, f"demon FK drifts {_err:.4f} units from the archive"

# Long thin strips at ground level are cut along their length: a long
# face's depth, interpolated linearly in screen space, over-reads, and
# would sink below the ground (THE GROUND RIDES THE CAMERA, below).
CUTS = {"walk": 6, "line": 6}
SP_ = lambda k: CUTS.get(k, 1)                        # noqa: E731

street = []
# NO ROAD GEOMETRY: the asphalt is ground_mesh(), which rides the camera.
# (Measured first, 2026-11-19, on the brawl route: the old ten faces
# walked 110k-189k pixels a frame. A BACKDROP PLATE was tried -- the
# camera's height, pitch and roll never change, so the ground is the same
# on every row -- and cost MORE: reading a full-screen plate is ~136k
# clocks a frame on its own, where the clear it replaces is ~98k.)

walk = Build()                   # sidewalks: raised 0.12, curb faces in
# The arms' long curbs are gone: 0.12 tall and seen edge-on, they were a
# line of pixels bought with a third of the sidewalks' DMEM -- and the
# tops must be cut into pieces now (THE GROUND RIDES THE CAMERA, below)
for sgn in (-1, 1):
    a0, a1 = (EDGE, REACH) if sgn > 0 else (-REACH, -EDGE)
    for side in (-1, 1):
        l0, l1 = (LANE, SW_OUT) if side > 0 else (-SW_OUT, -LANE)
        walk.box(a0, a1, l0, l1, 0.0, 0.12, SIDEWALK,         # E/W arms
                 sides=((-sgn, 0),), nx=SP_("walk"))
        walk.box(l0, l1, a0, a1, 0.0, 0.12, SIDEWALK,         # N/S arms
                 sides=((0, -sgn),), ny=SP_("walk"))
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
    paint.flat(a0, a1, -0.09, 0.09, 0.04, LINE, SP_("line"), 1)
    paint.flat(-0.09, 0.09, a0, a1, 0.04, LINE, 1, SP_("line"))
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
                     n_front, col, SP_("facade"))
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
street.append(fac) if not OMIT & {"buildings", "facades"} else None
# THE CORNER TOWERS AS ONE SURFACE. Each corner is three boxes that
# INTERPENETRATE (each steps 2 units back and up from the last), so a
# third of their side faces lay inside a neighbour -- never visible, and
# every buried pixel still walked. Each corner is now the boundary of the
# union: every side face minus the parts inside another box of its
# corner. No roofs: the camera never rises above 2.15 and the lowest
# roof is 7.5.
def union_sides(boxes):
    """boxes [(x0,x1,y0,y1,h,col)] -> the visible side rectangles, as
    (axis, at, lo, hi, z0, z1, normal sign, col)"""
    out = []
    for i, (x0, x1, y0, y1, h, col) in enumerate(boxes):
        for axis, at, lo, hi, sgn in ((0, x0, y0, y1, -1), (0, x1, y0, y1, 1),
                                      (1, y0, x0, x1, -1), (1, y1, x0, x1, 1)):
            cuts = []                              # (lo, hi, ztop) inside others
            for k, (a0, a1, b0, b1, hk, _) in enumerate(boxes):
                if k == i:
                    continue
                p0, p1, q0, q1 = (a0, a1, b0, b1) if axis == 0 else (b0, b1, a0, a1)
                if p0 < at < p1 and q0 < hi and q1 > lo:
                    cuts.append((max(q0, lo), min(q1, hi), hk))
            vs = sorted({lo, hi, *(c[0] for c in cuts), *(c[1] for c in cuts)})
            for v0, v1 in zip(vs, vs[1:]):
                mid = (v0 + v1) / 2
                ztop = max([c[2] for c in cuts if c[0] <= mid <= c[1]], default=0.0)
                if ztop < h:
                    out.append((axis, at, v0, v1, ztop, h, sgn, col))
    return out


corners = Build()
for sx in (-1, 1):
    for sy in (-1, 1):
        boxes = []
        for bx, by, w, d, h, col in blocks:
            if np.sign(bx) == sx and np.sign(by) == sy:
                boxes.append((bx - w / 2, bx + w / 2, by - d / 2, by + d / 2, h, col))
        for axis, at, v0, v1, z0, z1, sgn, col in union_sides(boxes):
            if axis == 0:
                q = [(at, v0, z0), (at, v1, z0), (at, v1, z1), (at, v0, z1)]
                n = (sgn, 0, 0)
            else:
                q = [(v0, at, z0), (v1, at, z0), (v1, at, z1), (v0, at, z1)]
                n = (0, sgn, 0)
            corners.quad(q, n, col)
street.append(corners) if not OMIT & {"buildings", "corners"} else None

lamps = Build()                  # four streetlights, warm
for sx in (-1, 1):
    for sy in (-1, 1):
        x, y = sx * ROAD_HALF, sy * ROAD_HALF
        lamps.box(x - .07, x + .07, y - .07, y + .07, 0.0, 3.1, (18, 16, 18))
        lamps.box(x - .22, x + .22, y - .22, y + .22, 3.0, 3.3, (255, 200, 120))
street.append(lamps) if "lamps" not in OMIT else None

# THE STREET BY PLACE, NOT BY KIND. The sequencer draws the frame in
# nine 32-row bands and, for every band an object's projected span
# touches, transforms EVERY vertex of the object again (~45 clocks each,
# zseq.v). Measured at the street route's peak, the rasteriser sat
# STARVED for 278k clocks while the sequencer re-transformed street
# meshes whose pieces, scattered over the screen, spanned every band:
# all four crosswalks as one mesh paid for each stripe 8 times over.
# (Merging whole regions -- facades with the floor under them -- spans
# the screen again, and measured no better.) So faces are grouped by
# LAYER (the floor, and what stands up) and by SECTOR (eight wedges
# round the crossing, the floor's split again near and far): compact in
# the world, so compact on screen, so each object touches few bands.
def place_of(b, f):
    P = np.array([np.array(b.v[i], float) / ONE for i in f[:3]])
    c = P.mean(axis=0)
    x, y = c[2], -c[0]                              # zeta -> archive
    sector = int(((np.arctan2(y, x) + np.pi / 8) % (2 * np.pi)) // (np.pi / 4))
    floor = P[:, 1].max() <= 0.2
    return (floor, sector, floor and np.hypot(x, y) > 2 * EDGE)


merged = {}
for b in street:
    for f in b.f:
        r = merged.setdefault(place_of(b, f), Build())
        ids = [r.vert(np.array(b.v[i], float) / ONE) for i in f[:3]]
        r.f.append((*ids, f[3]))
street = [merged[k] for k in sorted(merged)]
STREET, SPHERE = [], []        # each street object and its bounding sphere
for i, b in enumerate(street):
    for k, m in enumerate(b.meshes()):
        STREET.append(int(cart.data(m, f"street{i}_{k}")))
        V = np.array(m.verts, float).reshape(-1, 3) / ONE
        c = (V.min(0) + V.max(0)) / 2
        SPHERE.append((c, np.linalg.norm(V - c, axis=1).max()))


# 0.2 BELOW the street: everything that stands on the ground (paint at
# 0.04, curbs, feet) must read nearer than the ground at the same pixel,
# and a long face's interpolated depth over-reads -- so the ground is
# lowered until it always loses, at a cost of under a sixteenth of fog.
GROUND_Y = -0.2


def ground_mesh():
    """THE GROUND RIDES THE CAMERA. Measured on silicon, the ten asphalt
    faces walked 110k-189k pixels a frame -- the rasteriser walks every
    pixel of a triangle's bounding box, and a near-clipped quad fans into
    triangles each boxing most of the lower screen. But the camera's
    height, pitch and roll never change, so the visible ground is always
    the same trapezoid IN CAMERA SPACE, and this mesh is placed at the
    camera with the camera's yaw every frame:
      NEAR  one triangle, apex behind the bottom of the screen, base 15
            units out. Its screen-clipped box is wholly covered, so it
            walks 1x its pixels, not 2-4x. Depth is interpolated
            linearly in screen space, which over-reads a ground plane's
            depth -- so it can never hide what stands on it -- and the
            fog starts at 15, so nothing in it is fogged either way.
      FAR   four rings, 15 to 60, vertices at true depth so the fog
            ramp reads right (the error inside a ring is under half a
            sixteenth).
    Model space is camera space: x right, z forward, y = 0 the ground."""
    pit = 20 * 2 * np.pi / 1024
    vz = lambda z: 2.15 * np.sin(pit) + z * np.cos(pit)          # noqa: E731
    half = lambda z: spec.W / 2 / spec.FOCAL * vz(z) * 1.3       # noqa: E731
    V, F = [], []
    col = rgb(shade(ASPHALT, (0, 0, 1)))

    def v(x, z):
        V.append((x, GROUND_Y, z))
        return len(V) - 1

    def tri(a, b, c):
        P = [np.array(V[i]) for i in (a, b, c)]
        if np.cross(P[1] - P[0], P[2] - P[0])[1] < 0:     # face UP
            b, c = c, b
        F.append((a, b, c, col))
    apex = v(0.0, 1.0)
    # the sides must clear the bottom screen corners (2.93 out, 1.98 wide)
    w15 = (15 - 1.0) * 3.0 / (2.93 - 1.0)
    l15, r15 = v(-w15, 15.0), v(w15, 15.0)
    tri(apex, l15, r15)
    rings = (15.0, 20.0, 27.0, 36.0, 60.0)   # past the end walls (47)
    prev = (v(-half(15.0), 15.0), v(half(15.0), 15.0))
    for z in rings[1:]:
        cur = (v(-half(z), z), v(half(z), z))
        tri(prev[0], prev[1], cur[1])
        tri(prev[0], cur[1], cur[0])
        prev = cur
    return Mesh([int(round(c * ONE)) for p_ in V for c in p_], F)


GROUND_M = int(cart.data(ground_mesh(), "ground"))

# THE AWARE MARKER (tear.py _AWARE): a small gold tetrahedron over every
# demon that has you inside its frontal cone and so can swing -- the ones
# without one are facing the wrong way, the gaps to move through.


def tetra_mesh(size, col):
    V = np.array([(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)], float) * size
    F_ = []
    for a, b, c in ((0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)):
        P = V[[a, b, c]]
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if np.dot(n, P.mean(0)) < 0:
            b, c = c, b
        n = n / np.linalg.norm(n)
        k = 0.7 + 0.3 * max(0.0, n[1])                    # lit from above
        F_.append((a, b, c, rgb(tuple(min(255, int(ch * k)) for ch in col))))
    return Mesh([int(round(c * ONE)) for v in V for c in v], F_)


AWARE_M = int(cart.data(tetra_mesh(0.10, (255, 210, 80)), "aware"))
AWARE_LIFT = int(1.62 * ONE)

# ---- P6: THE TITLE -- the archive's own start screen, baked -----------------
# tools/tnd_title.py renders it with the archive itself at the panel's
# 320x288 (TEAR / NOT / DEMON in its gothic hand, the demonic Ns, the
# gash, the inverted cross, PRESS START; the menu cut to START, the one
# thing the port does). Here it is a BACKDROP PLATE: on the title the
# frame clears to it, nothing else is drawn, and the music keeps the
# archive's intro lock. ~136k clocks to read, on a screen with no fight.
_title = np.load(HERE.parent / "assets" / "tnd" / "title.npz")["img"].astype(np.int64)
TITLE = cart.cram(Plate([int(r >> 3) << 10 | int(g >> 3) << 5 | int(b >> 3)
                         for r, g, b in _title.reshape(-1, 3)],
                        [spec.ZFAR] * spec.BG_WORDS), "title")
MODE = cart.data(Table([0]), "mode")             # 0 the title, 1 the fight
TT = cart.var("title_t")
STREET_FACES = sum(len(b.f) for b in street)

# ---- P4: THE KEYS -- what the fight hit-tests (tools/tnd_extract.py) -----
# Archive axes (x fwd, y left, z up) to the cart's, Q16.16.
def zq(v):
    return [int(round(c * ONE)) for c in MZ @ np.asarray(v, float)]


PMN = ("jab", "cross", "lead_hook", "rear_hook", "special", "lead_uppercut",
       "rear_uppercut")
DMN = ("cross", "lead_hook")
# a move row: startup, end of active, total, damage, head damage (x1.35),
# reach^2, hitstop, knock, lunge, its first pose in the bank, its fists
MROW = ("start", "endact", "total", "dmg", "dmgh", "reach2", "stop",
        "knock", "lunge", "pose", "lift", "air", "cancels", "style", "fist")
GRAV = 0.014                    # tear.py: the aerial system's own gravity
GRAVQ = int(round(GRAV * ONE))
AIR_FLOAT = int(round(0.12 * ONE))   # tear.py AIR_HIT_FLOAT
AIR_HANG = 26                        # tear.py AIR_HIT_HANG
MR = {k: i for i, k in enumerate(MROW)}


def move_rows(rows, fists, pose_of=None, cancels=None):
    out, fist_words, at = [], [], []
    for k, r in enumerate(rows):
        su, ac, rc, dmg, reach, stop, knock, lunge, lift, style = r
        at.append(len(fist_words))
        fist_words += [w for f in fists[k] for w in zq(f)]
        # a LAUNCHER keeps its target helpless the whole arc: up and down
        # is 2 lift / g frames, and a beat (tear.py _resolve_hits)
        air = int(2 * lift / GRAV) + 6 if lift else 0
        out.append([int(su), int(su + ac), int(su + ac + rc), int(dmg),
                    int(dmg * 1.35), int(round(reach ** 2 * ONE)), int(stop),
                    int(round(knock * ONE)), int(round(lunge * ONE)),
                    pose_of(k) if pose_of else 0, int(round(lift * ONE)), air,
                    cancels[k] if cancels else 0, int(style), 0])
    return out, fist_words, at


# THE CANCEL LATTICE (combat.py): in its RECOVERY, a move may be cut by a
# buffered move it lists -- a light punch by anything, a hook only by the
# launchers and the special, a launcher only by the special, the special
# by nothing. A bit per move id.
def _bits(*names):
    return sum(1 << PMN.index(n) for n in names)


_LIGHT = _bits(*PMN)                    # (the gun and jump join it later)
_HOOK = _bits("lead_uppercut", "rear_uppercut", "special")
CANCELS = {"jab": _LIGHT, "cross": _LIGHT, "lead_hook": _HOOK, "rear_hook": _HOOK,
           "special": 0, "lead_uppercut": _bits("special"),
           "rear_uppercut": _bits("special")}
_pm, _pf, _pat = move_rows(DEM["p_moves"], [DEM["p_fist_" + n] for n in PMN],
                           lambda k: base[PMN[k]], [CANCELS[n] for n in PMN])
BIT = cart.data(Table([1 << i for i in range(len(PMN))]), "bits")
PFIST = cart.data(Table(_pf), "p_fists")
for k, row in enumerate(_pm):
    row[MR["fist"]] = int(PFIST) + _pat[k]
PMT = cart.data(Table([w for r in _pm for w in r]), "p_moves")
PKEY = cart.data(Table(zq(DEM["p_chin"]) + zq(DEM["p_gut"])), "p_keys")
DKEY, DMT = [], []              # per build: its keypoints, its move rows
for i in range(3):
    rows, fw, at = move_rows(DEM["d_moves"], [DEM[f"b{i}_fist_{n}"] for n in DMN])
    DKEY.append(cart.data(Table(zq(DEM[f"b{i}_chin"]) + zq(DEM[f"b{i}_gut"]) + fw),
                          f"demon{i}_keys"))
    for k, row in enumerate(rows):         # the builds differ only in reach
        row[MR["fist"]] = int(DKEY[i]) + 6 + at[k]   # of arm: their fists
    DMT.append(cart.data(Table([w for r in rows for w in r]), f"demon{i}_moves"))
NMR = len(MROW)

# ---- the wave: three demons round the crossing, facing in (tear.py) -----
# A slot is a demon's whole state; the mind runs on a COPY of it (CUR), so
# its code exists once, not three times (IMEM is 4,096 words).
#   st  0 free (stand / walk / turn), 1 swinging, 2 hit (hitstun),
#       3 falling, 4 gone
DF = {f: k for k, f in enumerate(
    ("x", "z", "h8", "hp", "st", "mf", "mv", "ai", "wf", "mov", "alt", "cf",
     "hs", "stop", "vx", "vz", "con", "dt", "jt", "kp", "mt", "ox", "oz",
     "py", "vy", "aw"))}
NF = len(DF)
DMASS = [0.85 + 0.55 * b for b in (1.40, 0.85, 1.40)]   # tear.py: e.mass
DHP = 70
slots = []
for i in range(3):
    a = i * 2 * np.pi / 3 + 0.6                          # tear.py _spawn_wave
    ax, ay = np.cos(a) * 7.8, np.sin(a) * 7.8
    v = dict.fromkeys(DF, 0)
    v.update(x=int(round(-ay * ONE)), z=int(round(ax * ONE)),
             h8=(int(round((a + np.pi) * 1024 / (2 * np.pi))) & 1023) << 8,
             hp=DHP, wf=21 * i, cf=int(CLIPT) + CLIP0["idle"] * NPART,
             jt=int(DJT[i]), kp=int(DKEY[i]), mt=int(DMT[i]))
    slots += [v[f] for f in DF]
DS = cart.data(Table(slots), "demons")
SPAWN = cart.data(Table(slots), "spawn")       # a new wave is this, copied
CUR = cart.var("cur", NF)                        # the demon being thought


def cur(f):
    return int(CUR) + DF[f]


# THE QUARTER WAVE. A 1,024-word sine table for a function with two
# symmetries was the cheapest DMEM in the cart to give back: 257 words
# and a subroutine (sin_of) that folds the angle. It bought the demons.
QSIN = cart.data(Table([int(round(np.sin(i * 2 * np.pi / 1024) * ONE))
                        for i in range(257)]), "qsin")

PX, PZ, YAW = cart.var("px"), cart.var("pz"), cart.var("yaw")
ANIM, AF, POSE = cart.var("anim"), cart.var("af"), cart.var("pose")
CY = cart.var("cam_yaw")       # the camera's yaw, easing after his
IDLE = cart.var("idle_f")       # idle's own frame, WRAPPED -- never a
                                # modulo off REG_FRAME, whose cost would
                                # grow every frame for as long as you play
PV = cart.var("prevpad")
# THE STRIKE FACING (tear.py _aim_at_dpad): the body faces HEAD, which is
# the steering YAW except while a strike runs -- at its launch HEAD snaps
# to the D-pad's direction off the steering (forward ahead, left to the
# left, back spins and strikes behind, the diagonals between), the camera
# never sees it, and it reverts when the strike is done. Indexed by the
# pad's four direction bits (up 1, down 2, left 4, right 8).
HEAD = cart.var("head")


def _octant(bits):
    f = (1 if bits & 1 else 0) - (1 if bits & 2 else 0)
    t = (1 if bits & 4 else 0) - (1 if bits & 8 else 0)
    if not (f or t):
        return 0
    # left turns are NEGATIVE yaw on this cart (PAD_LEFT: yaw -= 12)
    return int(round(-np.arctan2(t, f) * 1024 / (2 * np.pi))) & 1023


OCTANT = cart.data(Table([_octant(b) for b in range(16)]), "octants")
NOBJ = cart.var("nobj")

cart.boot(spec.CAM_Y, int(2.15 * ONE))           # the archive's follow height
cart.boot(spec.CAM_PITCH, 20)                    # ~0.12 rad DOWN: positive pitches down (the first cut had the sign backwards and put the horizon below centre)
cart.boot(spec.FOG_RGB, 0x6A2420)             # the dusk the street dissolves into
cart.boot(spec.FOG_NEAR, 15 * 512)              # archive _FOG_NEAR = 15 units
cart.boot(spec.FOG_SHIFT, 10)                   # full at 15 + 32 = 47 (archive 46)

p = cart.program()
L_SINE, L_ROT, L_FK = p.label("sine"), p.label("rot"), p.label("fk")
L_VIS = p.label("vis")
L_ARENA = p.label("arena")
L_COPY, L_WPT, L_D2, L_DMIND = (p.label(k) for k in ("copy", "wpt", "d2", "dmind"))
L_TEXT = p.label("text")
CP = {k: cart.var("cp_" + k) for k in ("src", "dst", "n")}
W = {k: cart.var("w_" + k) for k in ("k", "bx", "bz", "c", "s", "x", "y", "z", "oy",
                                     "qx", "qy", "qz", "dc", "dg", "d2", "head",
                                     "dmg", "stop")}
# THE STREET IS THE ARENA (tear.py _in_arena, the movement clamp): the
# crossing square inside 10.6, and the two streets 7.1 either side of
# their centreline out to 40. A step that ends anywhere else keeps only
# what stays on -- for him and for the demons alike.
AR = {k: cart.var("ar_" + k) for k in ("x", "z", "ox", "oz")}
AR_SQ, AR_LANE, AR_REACH = (int(v * ONE) for v in (11 - 0.4, 11 - 3.2 - 0.7, 54 - 14))


L_KIA = p.label("kia")
KP = {k: cart.var("kp_" + k) for k in ("p", "o")}    # where x (z next), where ox


def keep_in_arena(xc, zc, ox, oz):
    """a step that leaves the street keeps whichever axis of it stays on
    -- the archive's own SLIDE (tear.py, the open-world clamp: the whole
    step, else x alone, else z alone, else none), so a wall is a wall you
    can run along rather than glue. (One subroutine through two pointers:
    every pair here sits x then z, ox then oz.)"""
    assert int(zc) == int(xc) + 1 and int(oz) == int(ox) + 1
    p.push(int(xc)).store(KP["p"]).push(int(ox)).store(KP["o"])
    p.emit(f"call {L_KIA}")


def _kia_sub():
    def get(ptr, k):
        p.load(KP[ptr])
        if k:
            p.push(k).emit("add")
        p.emit("loadi")

    def put_from(src, k):                              # *(p + k) = *(o + k)
        get("o", k)
        p.load(KP["p"])
        if k:
            p.push(k).emit("add")
        p.emit("storei")
    ok = p.label("kia")
    p.mark(L_KIA)
    get("p", 0); p.store(AR["x"]); get("p", 1); p.store(AR["z"])
    p.emit(f"call {L_ARENA}", f"jz {ok}_x", "ret")
    p.mark(f"{ok}_x")                                # x alone
    get("p", 0); p.store(AR["x"]); get("o", 1); p.store(AR["z"])
    p.emit(f"call {L_ARENA}", f"jz {ok}_z")
    put_from("o", 1); p.emit("ret")
    p.mark(f"{ok}_z")                                # z alone
    get("o", 0); p.store(AR["x"]); get("p", 1); p.store(AR["z"])
    p.emit(f"call {L_ARENA}", f"jz {ok}_n")
    put_from("o", 0); p.emit("ret")
    p.mark(f"{ok}_n")                                # neither
    put_from("o", 0); put_from("o", 1); p.emit("ret")
WALK = int(0.032 * ONE)                          # the archive's walk pace
CAMD = 3                                         # camera distance, units
L = {k: p.label(k) for k in ("free", "noa", "jab", "walk", "idle",
                             "anim", "pj", "pi", "pd", "iw")}


def sin_of(q, plus=0, cell=None):
    """push sin(angle + plus) in Q16.16, through the quarter wave"""
    q.load(YAW if cell is None else cell)
    if plus:
        q.push(plus).emit("add")
    q.emit(f"call {L_SINE}")


# ---- THE BLOW, HEARD (sfx.meat_impact, on this machine's voices) -------------
# The archive builds an impact in four layers; three carry here, on three
# voices TND leaves free:
#   SLAP   noise stepping at a bright 12 kHz for the first 4 ms -- the
#          contact the ear places the blow by -- then, at sample 192
#          exactly (the EVENT LIST: sub-frame and bit-exact), the MEAT:
#          noise at a wet mid step, fast-decaying
#   THUMP  the triangle, its pitch FALLING as it fades (112 -> 74 Hz on a
#          head, 95 -> 58 on the body: heavy, not merely loud)
#   RING   the archive's metal partial as a thin pulse, a clang that dies
#          into the flesh within four frames
# A head shot is brighter and shorter (150 ms), the body darker and longer
# (190 ms): the same event at two weights.
def hz(f):
    return int(round(f * (1 << 24) / spec.SND_HZ))


SFX_N = 12                                       # frames: 190 ms, rounded up
SFX_SLAP = spec.SND_HZ * 4 // 1000               # sample 192
# The curves are a linear pitch fall and linear fades, so they are COMPUTED
# a frame at a time from six words a weight (a 144-word table, before
# DMEM ran out): ring inc, thump inc and its fall a frame, the thump's
# fade a frame (x256), the meat's inc, the thump's length.
SFXP = []
for head in (0, 1):
    n = 9 if head else 12
    f0, f1 = (112, 74) if head else (95, 58)
    meat, ring = (5200, 1900) if head else (3000, 1350)
    SFXP += [hz(ring), hz(f0), (hz(f1) - hz(f0)) // (n - 1), 15 * 256 // (n - 1),
             hz(meat), n]
SFX = cart.data(Table(SFXP), "sfx_blow")
SFX_V = cart.data(Table([10, 6, 3, 1,                  # the ring's fade
                         15, 13, 9, 5, 15, 12, 7, 3]), "sfx_vol")   # the noise, body / head
SFX_MEAT = cart.data(Table([hz(3000), hz(5200)]), "sfx_meat")
SFX_T = cart.data(Table([SFX_N]), "sfx_t")     # boots past its end: quiet
SFX_H, SFX_R = cart.var("sfx_h"), cart.var("sfx_r")


def sound_blow(head_cell):
    """start the blow from the top; head_cell holds 1 for a head shot"""
    p.set(SFX_T, 0)
    p.load(head_cell).store(SFX_H)



# ---- P5: STYLE (combat.Style) -- variety pays, repetition does not -----------
# A landed blow pays its move's style x the VARIETY of it (1, 0.6, 0.4, 0.25
# as it recurs in the last five) x the combo (+5% a hit, to twenty). A
# blow taken keeps 45% and breaks the combo; standing about bleeds it.
# Ranks D C B A S SS SSS at 0 60 150 300 520 800 1200. Points are kept
# x16 (the archive's 0.6-a-frame bleed is 9.6 of them); no divider, so the
# combo's /400 is a multiply by its reciprocal.
RANKS = ("D", "C", "B", "A", "S", "SS", "SSS")
RANK_AT = (0, 60, 150, 300, 520, 800, 1200)
RANK_RGB = (0x96919A, 0xAA8C78, 0x8C96AA, 0x96AA82, 0xC8A05A, 0xCD6E3C, 0xB92828)
SY = {k: cart.var("s_" + k) for k in ("pts", "combo", "idle", "rp", "rank",
                                       "best", "cnt", "src", "dst", "dx", "n",
                                       "g", "rgb")}
S_REC = cart.data(Table([255] * 5), "s_recent")
S_SHOWN = cart.data(Table([255]), "s_shown")             # 255: draw afresh
S_AT = cart.data(Table([a * 16 for a in RANK_AT] + [1 << 30]), "s_rank_at")
S_MULT = cart.data(Table([20, 12, 8, 5]), "s_mult")      # x/20
BAR_W = 100
S_FAC = cart.data(Table([int(BAR_W * ONE / ((RANK_AT[r + 1] - RANK_AT[r]) * 16))
                         for r in range(6)] + [0]), "s_bar")
S_RGB = cart.data(Table(list(RANK_RGB)), "s_rgb")
# THE TEXT ENGINE. Baked text is finished display-list triangles -- seven
# words a triangle, ~57 a glyph: the five rank letters and RETRY were 552
# words of a DMEM that had none left. A glyph here is its rectangles
# PACKED -- x, y (2 and 3 bits), width, height (2 and 3), ten bits a
# rectangle, three a word, every glyph of this font in six or fewer --
# and one routine (L_TEXT) turns a string of them into triangles when the
# HUD changes. Two words a glyph; a string is its length and its glyphs.
# (The width is stored as itself, 1..3, so an all-zero rectangle is none.)
from zeta.forge import glyph_rects                          # noqa: E402
FONT_CH = "DCBASRETYX0123456789"
_fw = []
for c in FONT_CH:
    rs = glyph_rects(c)
    assert len(rs) <= 6, c
    packed = [x | y << 2 | w << 5 | (h - 1) << 7 for x, y, w, h in rs]   # w >= 1: 0 is none
    packed += [0] * (6 - len(packed))
    _fw += [packed[0] | packed[1] << 10 | packed[2] << 20,
            packed[3] | packed[4] << 10 | packed[5] << 20]
FONT = cart.data(Table(_fw), "font")


def glyphs(text):
    return [len(text)] + [FONT_CH.index(c) for c in text]


STR_RANK = [cart.data(Table(glyphs(r)), "str_" + r) for r in RANKS]
STR_RETRY = cart.data(Table(glyphs("RETRY")), "str_retry")
S_STRS = cart.data(Table([int(x) for x in STR_RANK]), "str_ranks")
S_LEN = cart.data(Table([len(r) for r in RANKS]), "rank_len")
GW = 4 * 3                                     # a glyph and its gap, x3
STR_COMBO = cart.data(Table([3, FONT_CH.index("X"), 0, 0]), "str_combo")  # X + 2 digits
TX = {k: cart.var("tx_" + k) for k in ("str", "x", "y", "sc", "rgb", "n", "gp",
                                        "w", "k", "r", "x0", "y0", "x1", "y1",
                                        "dl", "j")}
TRI_CELLS = cart.data(Table([int(TX[c]) for c in (     # the forge's two triangles
    "x0", "y0", "x1", "y0", "x0", "y1", "rgb", "x1", "y0", "x1", "y1", "x0", "y1",
    "rgb")]), "tri_cells")

# ---- P5: THE MUSIC -- Fable's synth theme, its stems gated by rank -------------
# sfx._synth_battle_stems, on this machine's voices: 148 BPM, a two-bar
# loop, eight layers -- drums, bass, the palm-muted chug, the half-time
# breakdown, and the phrygian lead hook revealing itself by rank (a
# fragment, the hook, the harmony a third up; the octave shred is rank
# eight, which no fight reaches -- as in the archive). Stem k sounds from
# rank k up, all riding one eased intensity (70 + 34 a rank, falling to
# nothing when he is down). The free voices, not the blow's:
#   ch1   the kick: a pulse dropping in pitch, a fast fade
#   ch3   the snare and the china: noise (a blow's slap takes it back)
#   ch5   the bass, ch6 the chug, ch7 the breakdown, ch8-10 the leads --
#         wave voices on two pages: a square, and a POWER CHORD (root,
#         fifth and octave summed and hard-clipped, as _power_chug does,
#         two root cycles a page so it plays at half the root)
# A step sequencer at the sixteenth, on the archive's own sample grid
# (step j at j * BEAT//4): a sixteenth is 4,864 samples and a frame 800,
# so at most one step falls in a frame, and its notes start on their exact
# sample through the event list.
BEAT = spec.SND_HZ * 60 // 148
SIX = BEAT // 4
LOOP = BEAT * 4 * 2                                   # 155,672 samples
A2 = 110.0


def semi_hz(s):
    return A2 * 2 ** (s / 12)


def page(samples):
    w = []
    for i in range(0, 256, 4):
        w.append(sum((samples[i + k] & 0xFF) << (8 * k) for k in range(4)))
    return w


_sq_page = [100 if i < 128 else -100 for i in range(256)]
_chug = []
for i in range(256):                    # 2 root cycles, 3 fifths, 4 octaves
    ph = i / 256
    sq = lambda c: 1 if (ph * c) % 1 < 0.5 else -1   # noqa: E731
    _chug.append(max(-14, min(14, (sq(2) * 5 + sq(3) * 4 + sq(4) * 3) * 4)) * 8)
WAVES = cart.data(Table(page(_sq_page) + page(_chug)), "wave_pages")
cart.boot(spec.WAV_SRC, int(WAVES))
PG_SQ, PG_CHUG = 0, 1

# the stems: (name, voice, page or None, base volume, fade a frame x16)
STEMS = (("drums", None, None, 0, 0),
         ("bass", 5, PG_SQ, 11, 18),
         ("chug", 6, PG_CHUG, 10, 26),
         ("breakdown", 7, PG_CHUG, 12, 9),
         ("lead_tease", 8, PG_SQ, 9, 0),
         ("lead", 9, PG_SQ, 11, 0),
         ("harmony", 10, PG_SQ, 9, 0))
NSTEM = len(STEMS)
HOLD, REST = 0, 1                                      # else 2 + note index
notes = []                                             # inc values, by index


def note(hz_):
    v = hz(hz_)
    if v not in notes:
        notes.append(v)
    return 2 + notes.index(v)


def lead_steps(events):
    out, at = [HOLD] * 32, 0
    for semi, beats in events:
        n = int(beats * 4)
        if at < 32:
            out[at] = REST if semi is None else note(semi_hz(semi))
        at += n
    return out


HOOK = [(0, .5), (3, .5), (5, .5), (3, .5), (0, 1), (1, .5), (0, .5),
        (7, .5), (5, .5), (3, .5), (1, .5), (0, 1.5), (None, .5)]
TIER_B = [(0, .5), (3, .5), (5, .5), (3, .5), (0, 1), (1, .5), (0, .5), (0, 4)]
HARMONY = [(3, .5), (7, .5), (8, .5), (7, .5), (3, 1), (5, .5), (3, .5),
           (10, .5), (8, .5), (7, .5), (5, .5), (None, 2)]
pat = {}
# drums: bit 0 kick, bit 1 snare, bit 2 china (sfx._stem_drums)
kpat = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1,
        1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1]
pat["drums"] = [kpat[j] | (2 if j % 8 == 4 else 0) | (4 if j % 16 == 0 else 0)
                for j in range(32)]
line = (55, 55, 82, 55, 73, 73, 98, 73)               # the root-fifth riff
pat["bass"] = [note(line[(j // 2) % 8]) if j % 2 == 0 else HOLD for j in range(32)]
cpat = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1] * 2
roots = [55, 55, 55, 55, 82, 82, 82, 82, 73, 73, 73, 73, 98, 98, 98, 55] * 2
pat["chug"] = [note(roots[j] / 2) if cpat[j] else HOLD for j in range(32)]
bk = {0: 55, 3: 55, 6: 55, 8: 82, 12: 73, 14: 73}      # half-time, by step
pat["breakdown"] = [note(bk[j % 16] / 2) if j % 16 in bk else HOLD for j in range(32)]
pat["lead_tease"] = lead_steps(TIER_B)
pat["lead"] = lead_steps(HOOK)
pat["harmony"] = lead_steps(HARMONY)
assert len(notes) <= 254
MPAT = cart.data(Table([sum(pat[st[0]][j * 4 + k] << (8 * k) for k in range(4))
                        for st in STEMS for j in range(8)]), "music_steps")
MNOTE = cart.data(Table(notes), "music_notes")
MU = {k: cart.var("mu_" + k) for k in ("t", "step", "inten", "o", "code", "s",
                                        "kick", "drum", "dfade")}
MENV = cart.var("mu_env", NSTEM)                       # each stem's level x16
KICK_HI, KICK_DROP = hz(135), (hz(135) - hz(30)) // 4

# ---- P4: THE FIGHT ----------------------------------------------------------
# tear.py, in integers. A move LANDS when the attacker's posed fist, in its
# active frames, comes within the move's reach of the target's chin or gut
# (nearest decides: a head shot pays x1.35 and freezes 3 frames longer).
# Then both fighters freeze (HITSTOP -- "the single biggest feel
# contributor"), the target is stunned 12 + that many frames and knocked
# along the blow, the camera shakes. One hit per swing. 140 for him, 70 a
# demon; a demon that falls lies down and is gone, and when all three are,
# a new wave stands round the crossing.
#
# THE STRING (combat.resolve): every tap of A alternates the hands -- jab,
# cross, jab -- and every third tap of a string (taps within 22 frames)
# cashes out as a hook off the next hand. A tap during a swing is BUFFERED
# for 10 frames and thrown the moment the swing ends. A tap is read on
# RELEASE, as the archive reads it -- see THE GRAMMAR below.
F = {k: cart.var("f_" + k) for k in
     ("hs", "stop", "vx", "vz", "con", "ltap", "c3", "alt", "buf", "bmv",
      "mv", "dead", "shake", "act", "fx", "fy", "fz", "pc", "ps", "fight",
      "wave", "tilt")}
PHP = cart.data(Table([140]), "p_hp")
FRIC = int(round(0.82 * ONE))                   # tear.py: body friction
J = int(0.05 * ONE)                             # the shake, lateral
BUFFER, STRING = 10, 22


def fresh(bit):
    """push 1 when `bit` went down this frame"""
    p.emit("load 1").push(bit).emit("and").push(0).emit("eq")   # up now?
    p.load(PV).push(bit).emit("and", "or").push(0).emit("eq")   # ...or down before


def row(table_cell_or_sym, mv_cell, field, const_table=True):
    """push field of move row [mv]: table base (a constant symbol, or a
    cell holding one) + NMR * mv + field, loaded"""
    if const_table:
        p.push(int(table_cell_or_sym))
    else:
        p.load(table_cell_or_sym)
    p.load(mv_cell).push(NMR).emit("mul", "add").push(MR[field]).emit("add", "loadi")


BTN = (("carve", spec.PAD_A), ("special", spec.PAD_B),
       ("jump", spec.PAD_X), ("shoot", spec.PAD_Y))
GT = {b: cart.var("g_t_" + b) for b, _ in BTN}       # frames held, 0 = up
GC = {b: cart.var("g_c_" + b) for b, _ in BTN}       # read as a chord
L_MUSIC = p.label("music")
tl = p.label("title")
p.load(int(MODE)).emit(f"jz {tl}", f"jmp {tl}_fight")
p.mark(tl)
p.push(int(TITLE)).store(spec.BG_SRC)
p.set(spec.OL_BASE, 0).set(spec.DL_BASE, 0)
# PRESS START breathes as the archive's does (bright, then dim, on a
# 60-frame beat): one compositor rectangle dims it on the off beat
p.addi(TT, 1)
p.set(spec.CO_BASE, 1)
p.rect(0, 115, 265, 204, 276, 0x16141C,         # the prompt, exactly
       lambda q: q.load(TT).emit("shr 5").push(1).emit("and").push(9).emit("mul"))
# a FRESH press of Start or A (up now? or down last frame? -- neither)
p.emit("load 1").push(spec.PAD_START | spec.PAD_A).emit("and").push(0).emit("eq")
p.load(PV).push(spec.PAD_START | spec.PAD_A).emit("and", "or").push(0).emit("eq")
p.emit(f"jz {L_MUSIC}")
p.set(int(MODE), 1).set(spec.BG_SRC, 0).set(spec.CO_BASE, 0)
p.set(GT["carve"], 100).set(GC["carve"], 1)   # the A that left the title is spent
p.emit(f"jmp {L_MUSIC}")
p.mark(f"{tl}_fight")
p.load(PX).store(AR["ox"]).load(PZ).store(AR["oz"])     # where he stood
L = {k: p.label(k) for k in ("dead", "frozen", "free", "walk", "idle",
                             "motion", "anim", "pi", "pj", "pd", "iw",
                             "notap", "brk", "hook", "tapd", "nobuf", "busy",
                             "hurt", "launch", "turnd", "pm", "ph")}
p.load(F["dead"]).emit(f"jz {L['dead']}_no", f"jmp {L['dead']}")
p.mark(f"{L['dead']}_no")
p.load(F["stop"]).emit(f"jz {L['frozen']}_no")
p.addi(F["stop"], -1).emit(f"jmp {L['frozen']}")
p.mark(f"{L['frozen']}_no")

# ---- THE GRAMMAR (combat.Grammar, combat.resolve) ----------------------------
# Four actions on the face buttons: A carve (the string), B special, X jump,
# Y shoot. A CHORD is two buttons down within 3 frames of each other, read
# once, and neither then taps. A TAP of carve or special fires on release
# or at the fourth frame held, whichever comes first, if no chord took it.
# (The archive reads a tap as a release within 9 frames -- a keyboard's
# tap. On the Pocket a thumb holds a button longer than that, and every
# press read as a HOLD, which carve and special have no use for: on glass
# the string and the haymaker did nothing at all. Waiting out the chord
# window is all a tap needs to wait for.)
#   carve tap      the string (every tap swaps hands; the third a hook)
#   special tap    the haymaker
#   carve+jump     the rear uppercut, a launcher
#   shoot+special  the lead uppercut, a launcher
# (jump and shoot alone -- the jump and the gun -- come after the game
# ships, with the air layer; their buttons already chord.)
GTAP = {b: cart.var("g_tap_" + b) for b in ("carve", "special")}
TAP_MAX, CHORD_SLOP = 9, 3
MOVE = {n: i for i, n in enumerate(PMN)}


def choose(mv_const=None, mv_cell_ops=None):
    """the move is decided at the input and BUFFERED (tear.py f.press)"""
    if mv_const is not None:
        p.push(mv_const)
    else:
        p.emit(*mv_cell_ops)
    p.store(F["bmv"])
    p.set(F["buf"], BUFFER)


p.addi(F["ltap"], 1)
p.load(F["buf"]).emit(f"jz {L['nobuf']}")
p.addi(F["buf"], -1)
p.mark(L["nobuf"])
for b, bit in BTN:
    up, done = p.label("g_up"), p.label("g_d")
    if b in GTAP:
        p.set(GTAP[b], 0)
    p.emit("load 1").push(bit).emit("and", f"jz {up}")
    p.addi(GT[b], 1)
    if b in GTAP:          # held past the chord window, unchorded: it fires
        hd = p.label("g_hd")
        p.load(GC[b]).emit(f"jz {hd}_c", f"jmp {done}")
        p.mark(f"{hd}_c")
        p.load(GT[b]).push(CHORD_SLOP + 1).emit("eq", f"jz {done}")
        p.set(GTAP[b], 1).set(GC[b], 1)                    # (spent)
    p.emit(f"jmp {done}")
    p.mark(up)
    p.load(GT[b]).emit(f"jz {done}")                       # was it down?
    if b in GTAP:                     # released before that, unchorded: it fires
        nt = p.label("g_nt")
        p.load(GC[b]).emit(f"jz {nt}_c", f"jmp {nt}")
        p.mark(f"{nt}_c")
        p.set(GTAP[b], 1)
        p.mark(nt)
    p.set(GT[b], 0).set(GC[b], 0)
    p.mark(done)


def chord(a, b, move):
    """both fresh (down 1..3 frames), neither yet read as a chord"""
    no = p.label("g_ch")
    for x in (a, b):
        p.load(GC[x]).emit(f"jz {no}_{x}", f"jmp {no}")
        p.mark(f"{no}_{x}")
        p.load(GT[x]).emit(f"jz {no}")
        p.push(CHORD_SLOP + 1).load(GT[x]).emit("swap", "lt", f"jz {no}")
    p.set(GC[a], 1).set(GC[b], 1)
    choose(MOVE[move])
    p.mark(no)


chord("carve", "jump", "rear_uppercut")
chord("shoot", "special", "lead_uppercut")
# the special: its own tap
sp = p.label("g_sp")
p.load(GTAP["special"]).emit(f"jz {sp}")
choose(MOVE["special"])
p.mark(sp)
# the carve string
p.load(GTAP["carve"]).emit(f"jz {L['notap']}")
p.load(F["ltap"]).push(STRING).emit("lt", f"jz {L['brk']}")
p.addi(F["c3"], 1)
p.emit(f"jmp {L['brk']}_d")
p.mark(L["brk"])
p.set(F["c3"], 1)                                 # a new string
p.mark(f"{L['brk']}_d")
p.set(F["ltap"], 0)
p.load(F["c3"]).push(3).emit("eq", f"jz {L['hook']}")
p.set(F["c3"], 0)                                 # third tap: the hook
choose(mv_cell_ops=(f"load {int(F['alt'])}", "push 2", "add"))   # 2 lead, 3 rear
p.emit(f"jmp {L['tapd']}")
p.mark(L["hook"])
p.load(F["alt"]).push(1).emit("xor").store(F["alt"])
choose(mv_cell_ops=(f"load {int(F['alt'])}",))    # 0 jab, 1 cross
p.mark(L["tapd"])
p.mark(L["notap"])

# ---- stunned: no will of his own, only the blow's momentum ------------------
p.load(F["hs"]).emit(f"jz {L['hurt']}_no")
p.addi(F["hs"], -1).set(ANIM, 3).set(F["buf"], 0)
p.emit(f"jmp {L['motion']}")
p.mark(f"{L['hurt']}_no")

# ---- tank turn -- frozen while a strike button is held: the D-pad is then
# choosing where the strike goes, and must not spin the frame it is
# measured from (tear.py _tank, `charging`)
tk = p.label("turn")
p.emit("load 1").push(spec.PAD_A | spec.PAD_B | spec.PAD_X | spec.PAD_Y)
p.emit("and", f"jz {tk}_go", f"jmp {tk}")
p.mark(f"{tk}_go")
p.if_pad(spec.PAD_LEFT, lambda q: q.addi(YAW, -12))
p.if_pad(spec.PAD_RIGHT, lambda q: q.addi(YAW, 12))
p.load(YAW).push(1023).emit("and").store(YAW)
p.mark(tk)

# ---- a swing owns the body until its frames are done --------------------------
p.load(ANIM).push(2).emit("eq", f"jz {L['free']}")
p.addi(AF, 1)
p.load(AF)
row(PMT, F["mv"], "total")
p.emit("lt", f"jz {L['free']}_end")
# in its recovery, a buffered move this one lists cuts it short
p.load(F["buf"]).emit(f"jz {L['motion']}")
p.load(AF)
row(PMT, F["mv"], "endact")
p.emit("lt", f"jz {L['free']}_cx", f"jmp {L['motion']}")
p.mark(f"{L['free']}_cx")
row(PMT, F["mv"], "cancels")
p.push(int(BIT)).load(F["bmv"]).emit("add", "loadi", "and", f"jz {L['motion']}")
p.emit(f"jmp {L['free']}")                      # cancel: launch it now
p.mark(f"{L['free']}_end")
p.set(ANIM, 0)
p.mark(L["free"])
p.load(F["buf"]).emit(f"jz {L['walk']}_q")
# LAUNCH: the buffered move, and its lunge as ONE impulse (tear.py _launch)
p.load(F["bmv"]).store(F["mv"])
p.set(ANIM, 2).set(AF, 0).set(F["con"], 0).set(F["buf"], 0)
p.push(int(OCTANT)).emit("load 1").push(15).emit("and", "add", "loadi")
p.load(YAW).emit("add").push(1023).emit("and").store(HEAD)   # the strike's facing
sin_of(p, cell=HEAD)
row(PMT, F["mv"], "lunge")
p.emit("mulq").load(F["vx"]).emit("swap", "sub").store(F["vx"])   # fwd x = -sin
sin_of(p, 256, cell=HEAD)
row(PMT, F["mv"], "lunge")
p.emit("mulq").load(F["vz"]).emit("add").store(F["vz"])
p.emit(f"jmp {L['motion']}")
p.mark(f"{L['walk']}_q")
p.load(YAW).store(HEAD)                       # no strike: he faces his steering
wb = p.label("wback")
p.emit("load 1", f"push {spec.PAD_UP}", "and", f"jz {wb}")
p.set(ANIM, 1)
p.addi(AF, 1)
sin_of(p)                                     # forward is model +z: (-sin, cos)
p.push(WALK).emit("mulq").load(PX).emit("swap", "sub").store(PX)
sin_of(p, 256)
p.push(WALK).emit("mulq").load(PZ).emit("add").store(PZ)
p.emit(f"jmp {L['motion']}")
# BACK: the tank's other half, at the same pace (tear.py _tank: fwd = +-1),
# the walk played backwards
p.mark(wb)
p.emit("load 1", f"push {spec.PAD_DOWN}", "and", f"jz {L['idle']}")
p.set(ANIM, 1)
p.addi(AF, -1)
sin_of(p)
p.push(WALK).emit("mulq").load(PX).emit("add").store(PX)
sin_of(p, 256)
p.push(WALK).emit("mulq").load(PZ).emit("swap", "sub").store(PZ)
p.emit(f"jmp {L['motion']}")
p.mark(L["idle"])
p.set(ANIM, 0)

# ---- momentum: knockback and lunge, scrubbed by friction ----------------------
p.mark(L["motion"])
for pos, vel in ((PX, F["vx"]), (PZ, F["vz"])):
    p.load(pos).load(vel).emit("add").store(pos)
    p.load(vel).push(FRIC).emit("mulq").store(vel)

# ---- pose index: base[anim] + frame within the sequence -----------------------
# 0 idle, 1 walk, 2 a swing, 3 stunned (the archive holds the idle mesh:
# it has no hurt clip), 4 down (idle, tipped over -- see the objects)
p.load(ANIM).push(2).emit("eq", f"jz {L['pm']}")
row(PMT, F["mv"], "pose")
p.load(AF).emit("add").store(POSE).emit(f"jmp {L['pd']}")
p.mark(L["pm"])
p.load(ANIM).push(1).emit("eq", f"jz {L['pi']}")
p.load(AF).push(NPOSE["walk"] - 1).emit("and").push(base["walk"]).emit("add")
p.store(POSE).emit(f"jmp {L['pd']}")
p.mark(L["pi"])
p.addi(IDLE, 1)
p.load(IDLE).push(NPOSE["idle"]).emit("lt", f"jz {L['iw']}")
p.load(IDLE).push(base["idle"]).emit("add").store(POSE)
p.emit(f"jmp {L['pd']}")
p.mark(L["iw"])
p.set(IDLE, 0).set(POSE, base["idle"])
p.mark(L["pd"])
p.emit(f"jmp {L['frozen']}")

# ---- down: he tips over backwards, and after the beat, A is a new run --------
DEATH_BEAT = 46                                     # tear.py
p.mark(L["dead"])
p.addi(F["dead"], 1)
p.load(F["dead"]).push(42).emit("lt", f"jz {L['dead']}_t")
p.load(F["dead"]).push(6).emit("mul").store(F["tilt"])    # to ~89 degrees
p.mark(f"{L['dead']}_t")
p.push(DEATH_BEAT).load(F["dead"]).emit("lt")
fresh(spec.PAD_A)
p.emit("and", f"jz {L['frozen']}")
# RETRY: a fresh run -- full health, the start, a new wave (tear.py _retry)
for c, v in ((PX, 0), (PZ, 0), (YAW, 0), (CY, 0), (ANIM, 0), (AF, 0),
             (PHP, 140), (F["dead"], 0), (F["tilt"], 0), (F["hs"], 0),
             (F["stop"], 0), (F["vx"], 0), (F["vz"], 0), (F["buf"], 0),
             (F["c3"], 0), (F["fight"], 0), (F["wave"], 0), (SFX_T, SFX_N),
             (SY["pts"], 0), (SY["combo"], 0), (SY["idle"], 0), (int(S_SHOWN), 255),
             *((int(S_REC) + i, 255) for i in range(5))):
    p.set(c, v)
p.push(int(SPAWN)).store(CP["src"]).push(int(DS)).store(CP["dst"])
p.push(3 * NF).store(CP["n"]).emit(f"call {L_COPY}")
p.load(PX).store(AR["ox"]).load(PZ).store(AR["oz"])

p.mark(L["frozen"])
# ---- one mover request: the whole posed body ----------------------------------
p.load(POSE).push(SPAN).emit("mul").push(int(BANK)).emit("add")
p.store(spec.DMA_SRC)
p.push(UPPER + 2).store(spec.DMA_DST)
p.push(SPAN).store(spec.DMA_LEN)
p.set(spec.DMA_GO, 1)

keep_in_arena(PX, PZ, AR["ox"], AR["oz"])

# his trig, for his keys and his fist: the BODY's facing
sin_of(p, 256, cell=HEAD)
p.store(F["pc"])
sin_of(p, cell=HEAD)
p.store(F["ps"])
# HIS FIST, if a swing is in its active frames and has not yet landed
p.set(F["act"], 0)
nf_ = p.label("nofist")
p.load(ANIM).push(2).emit("eq", f"jz {nf_}")
p.load(F["con"]).emit(f"jz {nf_}_c", f"jmp {nf_}")
p.mark(f"{nf_}_c")
p.load(AF)
row(PMT, F["mv"], "start")
p.emit("lt", f"jz {nf_}_s", f"jmp {nf_}")        # before the active frames
p.mark(f"{nf_}_s")
p.load(AF)
row(PMT, F["mv"], "endact")
p.emit("lt", f"jz {nf_}")                        # after them
row(PMT, F["mv"], "fist")
p.load(AF)
row(PMT, F["mv"], "start")
p.emit("sub").push(3).emit("mul", "add").store(W["k"])
for a, b in (("bx", PX), ("bz", PZ), ("c", F["pc"]), ("s", F["ps"])):
    p.load(b).store(W[a])
p.set(W["oy"], 0)
p.emit(f"call {L_WPT}")
for a, b in (("x", "fx"), ("y", "fy"), ("z", "fz")):
    p.load(W[a]).store(F[b])
p.set(F["act"], 1)
p.mark(nf_)

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
# THE SHAKE: a landed blow jolts the lens side to side for its hitstop
sk = p.label("shake")
p.load(F["shake"]).emit(f"jz {sk}")
p.addi(F["shake"], -1)
p.load(F["shake"]).push(1).emit("and", f"jz {sk}_l")
p.load(spec.CAM_X).push(J).emit("add").store(spec.CAM_X).emit(f"jmp {sk}")
p.mark(f"{sk}_l")
p.load(spec.CAM_X).push(J).emit("sub").store(spec.CAM_X)
p.mark(sk)

# ---- P3: the demons' minds -- slow to walk, slow to turn, slow to commit ----
# tear.py:3235-3290, in integers. They turn toward you at a BOUNDED rate
# (0.034 rad a frame: a full turn takes three seconds, so a flank is
# real), walk along their OWN facing rather than at you (a slow turner
# drifts wide -- the gap you move through), and swing only from inside a
# 0.46 rad cone, every 74 frames, cross and lead hook alternating. Angles
# without atan2: the side you are on is the sign of facing x offset, and
# the cone is cross^2 < tan^2(0.46) dot^2, dot > 0.
DTURN = int(round(0.034 * 1024 / (2 * np.pi) * 256))  # heading is yaw << 8
DWALK = int(0.020 * ONE)       # slower than his 0.032: distance is yours
DREACH2 = int(1.5 ** 2 * ONE)  # closer than 1.5 they stop and square up
DCONE = int(np.tan(0.46) ** 2 * ONE)
CONE_OUT = int(np.tan(0.60) ** 2 * ONE)            # tear.py ENEMY_CONE_EXIT
DREST = 74
DTEMP = {k: cart.var("dt_" + k) for k in
         ("ty", "fx", "fz", "dx", "dz", "cr", "dot", "s", "c")}


def dslot(d, f):
    return int(DS) + d * NF + DF[f]


# ---- the wave: each demon's mind, on a copy of its slot ----------------------
for d in range(3):
    p.push(int(DS) + d * NF).store(CP["src"]).push(int(CUR)).store(CP["dst"])
    p.push(NF).store(CP["n"]).emit(f"call {L_COPY}")
    p.emit(f"call {L_DMIND}")
    p.push(int(CUR)).store(CP["src"]).push(int(DS) + d * NF).store(CP["dst"])
    p.push(NF).store(CP["n"]).emit(f"call {L_COPY}")
# all three gone: the next wave stands round the crossing (tear.py)
nw = p.label("nowave")
for d in range(3):
    p.load(dslot(d, "st")).push(4).emit("eq")
p.emit("and", "and", f"jz {nw}")
p.push(int(SPAWN)).store(CP["src"]).push(int(DS)).store(CP["dst"])
p.push(3 * NF).store(CP["n"]).emit(f"call {L_COPY}")
p.addi(F["wave"], 1)
p.mark(nw)

# ---- the shove: bodies do not pass through bodies -------------------------
# tear.py weights it by mass (0.85 + 0.55 bulk); he is 1. Inside 0.9
# units apart each pair is pushed apart along the line between them, an
# eighth of that line a frame, shared by mass.
SHOVE2 = int(0.9 ** 2 * ONE)
SH = {k: cart.var("sh_" + k) for k in ("dx", "dz")}


L_SHV = p.label("shv")
SV = {k: cart.var("sv_" + k) for k in ("a", "b", "wa", "wb")}


def shove(ax, az, bx, bz, ma, mb):
    """(through pointers: a's x then z, b's x then z)"""
    assert int(az) == int(ax) + 1 and int(bz) == int(bx) + 1
    p.push(int(ax)).store(SV["a"]).push(int(bx)).store(SV["b"])
    p.push(int(round(ONE / 8 * mb / (ma + mb)))).store(SV["wa"])  # the lighter
    p.push(int(round(ONE / 8 * ma / (ma + mb)))).store(SV["wb"])  # moves more
    p.emit(f"call {L_SHV}")


def _shv_sub():
    def at(ptr, k):
        p.load(SV[ptr])
        if k:
            p.push(k).emit("add")
    sk = p.label("shv")
    p.mark(L_SHV)
    for k, d in ((0, "dx"), (1, "dz")):
        at("b", k); p.emit("loadi"); at("a", k); p.emit("loadi", "sub"); p.store(SH[d])
    p.load(SH["dx"]).load(SH["dx"]).emit("mulq")
    p.load(SH["dz"]).load(SH["dz"]).emit("mulq", "add")
    p.push(SHOVE2).emit("lt", f"jz {sk}")
    for ptr, w, sgn in (("a", "wa", "sub"), ("b", "wb", "add")):
        for k, d in ((0, "dx"), (1, "dz")):
            at(ptr, k); p.emit("loadi").load(SH[d]).load(SV[w]).emit("mulq", sgn)
            at(ptr, k); p.emit("storei")
    p.mark(sk)
    p.emit("ret")


def if_standing(ds, body):
    """body() only while every demon in ds is up (st < 3): the fallen and
    the gone neither shove nor are shoved"""
    skip = p.label("up")
    for d in ds:
        p.load(dslot(d, "st")).push(3).emit("lt", f"jz {skip}")
    body()
    p.mark(skip)


for i in range(3):
    for j in range(i + 1, 3):
        if_standing((i, j), lambda i=i, j=j: shove(
            dslot(i, "x"), dslot(i, "z"), dslot(j, "x"), dslot(j, "z"),
            DMASS[i], DMASS[j]))
    if_standing((i,), lambda i=i: shove(dslot(i, "x"), dslot(i, "z"), PX, PZ,
                                        DMASS[i], 1.0))
# (THE CAMERA HAS NO BODY, measured: shoving demons out of a 1.5 circle
# round the lens pushed them sideways INTO the shot, and the tour route
# went from 1 frame over the ceiling to 20.)
for i in range(3):
    keep_in_arena(dslot(i, "x"), dslot(i, "z"), dslot(i, "ox"), dslot(i, "oz"))
keep_in_arena(PX, PZ, AR["ox"], AR["oz"])          # a shove cannot either

FK = {k: cart.var("fk_" + k) for k in
      ("x", "z", "yaw", "jt", "cf", "j", "rp", "pp", "a", "ra",
       "vx", "vy", "vz", "q", "t", "s", "c", "flags", "y", "aw")}
# THE FLASH (tear.py t.flash): the struck body goes blood-red for the
# blow's first frames. OBJ_OTINT can only darken, so it is red at full and
# green and blue cut to a third -- a cast, not a strobe.
FLASH = spec.OBJ_CULL | spec.OBJ_OTINT | (31 << 27) | (10 << 22) | (10 << 17)
FLASH_FOR = 8                  # while more than this much stun is left
LENS2 = int(1.3 ** 2 * ONE)


# ---- WHAT THE CAMERA CANNOT SEE IS NOT SENT -----------------------------------
# The sequencer transforms every vertex of every listed object, and its
# frame-wide vertex cache holds 2,048 (zseq.v): past that, an object is
# re-transformed in EVERY band. The street, the player and three demons
# came to 2,080-2,140 -- so the last demon's parts ran nine times. Now
# each street sector and each demon carries a bounding sphere, and an
# object wholly behind the camera or outside a side plane of the view is
# never listed. The test is in view space, through the camera's own yaw
# and its FIXED pitch, so it is exact for a sphere; the side planes are
# taken at 40 degrees where the screen's edge is 32, for margin.
VIS = {k: cart.var("vis_" + k) for k in ("cx", "cy", "cz", "r", "rx", "rz", "xc", "zc")}
PCOS, PSIN = (int(round(f(20 * 2 * np.pi / 1024) * ONE)) for f in (np.cos, np.sin))
SCOS, SSIN = int(round(np.cos(np.radians(40)) * ONE)), int(round(np.sin(np.radians(40)) * ONE))
sin_of(p, 256, cell=CY)
p.store(VIS["rx"])                                    # right = (cos, sin)
sin_of(p, cell=CY)
p.store(VIS["rz"])

# ---- the object list --------------------------------------------------------
p.set(NOBJ, 0)
p.object(NOBJ, GROUND_M, (f"load {spec.CAM_X}",), 0, (f"load {spec.CAM_Z}",),
         (f"load {spec.CAM_YAW}",), spec.OBJ_CULL)
def if_visible(cx, cy, cz, r, body):
    """body() only when the sphere can be on screen. cx/cz may be cells
    (tuples of ops) or constants; cy and r are constants."""
    skip = p.label("unseen")
    for cell, v in (("cx", cx), ("cz", cz)):
        p.emit(*v) if isinstance(v, tuple) else p.push(int(round(v * ONE)))
        p.store(VIS[cell])
    p.push(int(round(r * ONE))).store(VIS["r"])
    p.push(int(round((cy - 2.15) * ONE))).store(VIS["cy"])
    p.emit(f"call {L_VIS}", f"jz {skip}")
    body()
    p.mark(skip)


# the street as ONE loop over a table (mesh, centre, radius -- the y
# already relative to the eye): twenty unrolled copies of the test were
# ~500 of IMEM's 4,096 words
ST_TAB = cart.data(Table([w for m, (c, r) in zip(STREET, SPHERE) for w in (
    m, int(round(c[0] * ONE)), int(round((c[1] - 2.15) * ONE)),
    int(round(c[2] * ONE)), int(round((r + 0.05) * ONE)))]), "street_cull")
STP, STN = cart.var("st_p"), cart.var("st_n")
stl = p.label("stl")
p.push(int(ST_TAB)).store(STP).push(len(STREET)).store(STN)
p.mark(stl)
for k, c in enumerate(("cx", "cy", "cz", "r")):
    p.load(STP).push(k + 1).emit("add", "loadi").store(VIS[c])
p.emit(f"call {L_VIS}", f"jz {stl}_s")
p.object(NOBJ, (f"load {int(STP)}", "loadi"), 0, 0, 0, 0, spec.OBJ_CULL)
p.mark(f"{stl}_s")
p.addi(STP, 5).addi(STN, -1)
p.load(STN).emit(f"jz {stl}_e", f"jmp {stl}")
p.mark(f"{stl}_e")
def flash_flags(hs, out):
    """out = FLASH while the blow is fresh -- the STRUCK body only: hitstop
    freezes the attacker too, but only the target carries a stun (12 +
    stop, counted down once the freeze is over)"""
    fl = p.label("flash")
    p.push(spec.OBJ_CULL).store(out)
    p.push(FLASH_FOR).load(hs).emit("lt", f"jz {fl}")
    p.push32(FLASH).store(out)
    p.mark(fl)


PFLAGS = cart.var("p_flags")
flash_flags(F["hs"], PFLAGS)
for m in ((UPPER, LOWER) if "player" not in OMIT else ()):
    # down, he folds FORWARD over his feet, away from the lens -- the
    # archive's collapse folds over the guard, and backwards took him out
    # of the bottom of the shot
    p.object(NOBJ, m, (f"load {int(PX)}",), 0, (f"load {int(PZ)}",),
             (f"load {int(HEAD)}", f"load {int(F['tilt'])}", "shl 10", "or"),
             (f"load {int(PFLAGS)}",))
for d in range(3 if "demons" not in OMIT else 0):     # the demons, last
    for f, c in (("x", "x"), ("z", "z"), ("cf", "cf")):
        p.load(dslot(d, f)).store(FK[c])
    p.load(dslot(d, "h8")).emit("shr 8").store(FK["yaw"])
    p.load(dslot(d, "jt")).store(FK["jt"])
    p.load(dslot(d, "py")).store(FK["y"])
    p.load(dslot(d, "aw")).store(FK["aw"])
    flash_flags(dslot(d, "hs"), FK["flags"])
    gone = p.label("gone")
    p.load(dslot(d, "st")).push(4).emit("eq", f"jz {gone}_n", f"jmp {gone}")
    p.mark(f"{gone}_n")
    # AGAINST THE LENS, NOT DRAWN. A demon within 1.3 of the camera is a
    # wall of near-clipped faces, and the clipper is the sequencer's most
    # expensive path: the tour route's worst frame (one demon 0.95 from
    # the lens) cost 722,865 clocks -- over the frame. It still fights.
    for c, cam in (("x", spec.CAM_X), ("z", spec.CAM_Z)):
        p.load(dslot(d, c)).load(cam).emit("sub", "dup", "mulq")
    p.emit("add").push(LENS2).emit("swap", "lt", f"jz {gone}")   # 1.3^2 < d^2: draw
    if_visible((f"load {dslot(d, 'x')}",), 1.0, (f"load {dslot(d, 'z')}",), 1.6,
               lambda: p.emit(f"call {L_FK}"))
    p.mark(gone)
p.load(NOBJ).store(spec.OL_BASE)

# ---- the style meter's frame: bleed, rank, best ------------------------------
sb = p.label("sbleed")
p.load(F["dead"]).emit(f"jz {sb}_a", f"jmp {sb}")
p.mark(f"{sb}_a")
p.addi(SY["idle"], 1)
p.push(90).load(SY["idle"]).emit("lt", f"jz {sb}_45")
p.load(SY["pts"]).push(35).emit("sub").store(SY["pts"])      # 2.2 a frame
p.set(SY["combo"], 0).emit(f"jmp {sb}_c")
p.mark(f"{sb}_45")
p.push(45).load(SY["idle"]).emit("lt", f"jz {sb}")
p.load(SY["pts"]).push(10).emit("sub").store(SY["pts"])      # 0.6 a frame
p.mark(f"{sb}_c")
p.load(SY["pts"]).push(0).emit("lt", f"jz {sb}")
p.set(SY["pts"], 0)
p.mark(sb)
# the rank: how many thresholds past the first the points have reached
rk = p.label("rank")
p.set(SY["rank"], 0).push(int(S_AT) + 1).store(SY["src"])
p.mark(rk)
p.load(SY["src"]).emit("loadi").load(SY["pts"]).emit("swap", "lt", f"jz {rk}_e")
p.emit(f"jmp {rk}_e2")
p.mark(f"{rk}_e")
p.addi(SY["rank"], 1).addi(SY["src"], 1)
p.load(SY["rank"]).push(6).emit("lt", f"jz {rk}_e2", f"jmp {rk}")
p.mark(f"{rk}_e2")

# ---- the HUD's words: the rank, the combo, or RETRY -------------------------------
# Rebuilt only when what it says changes (a key of what is shown):
#   down, past the beat   RETRY                          (key 1)
#   fighting              the rank, top right, in its colour; X and the
#                         combo over the meter once it passes one -- key
#                         (rank + 1) << 8 | combo, so its fields cannot touch
#   the opening           nothing                        (key 0)
hk = p.label("hudk")
p.set(SY["g"], 0)                                     # (the key, building)
p.push(DEATH_BEAT - 1).load(F["dead"]).emit("lt", f"jz {hk}_f")
p.set(SY["g"], 1).emit(f"jmp {hk}_c")
p.mark(f"{hk}_f")
p.load(F["fight"]).emit(f"jz {hk}_c")
p.load(SY["rank"]).push(1).emit("add").push(1 << 8).emit("mul").store(SY["g"])  # (rank+1)<<8
p.load(SY["combo"]).push(1).emit("swap", "lt", f"jz {hk}_c")     # 1 < combo
p.load(SY["combo"]).emit("dup").push(99).emit("lt", f"jz {hk}_99", f"jmp {hk}_k")
p.mark(f"{hk}_99")
p.emit("drop").push(99)
p.mark(f"{hk}_k")
p.load(SY["g"]).emit("add").store(SY["g"])
p.mark(f"{hk}_c")
p.load(SY["g"]).push(int(S_SHOWN)).emit("loadi", "eq", f"jz {hk}_draw", f"jmp {hk}")
p.mark(f"{hk}_draw")
p.load(SY["g"]).push(int(S_SHOWN)).emit("storei")
p.set(TX["n"], 0)
p.load(SY["g"]).push(1).emit("eq", f"jz {hk}_fight")
for k, v in (("str", int(STR_RETRY)), ("x", 141), ("y", 80), ("sc", 2), ("rgb", 0xE8D8C0)):
    p.set(TX[k], v)
p.emit(f"call {L_TEXT}", f"jmp {hk}_out")
p.mark(f"{hk}_fight")
p.load(SY["g"]).emit(f"jz {hk}_out")
p.push(int(S_RGB)).load(SY["rank"]).emit("add", "loadi").store(TX["rgb"])
# the rank's string: a small table of their addresses
p.push(int(S_STRS)).load(SY["rank"]).emit("add", "loadi").store(TX["str"])
p.push(310).push(GW).push(int(S_LEN)).load(SY["rank"]).emit("add", "loadi", "mul", "sub")
p.store(TX["x"])
p.set(TX["y"], 10).set(TX["sc"], 3)
p.emit(f"call {L_TEXT}")
p.load(SY["g"]).push(255).emit("and", f"jz {hk}_out")       # the combo
# X and the combo, as the archive writes it (X5, X12): the digits are
# glyphs from index 10 of the font; no leading zero
D0 = FONT_CH.index("0")
cz = p.label("cz")
p.load(SY["g"]).push(255).emit("and", "dup").push(205).emit("mul", "shr 11")  # /10
p.emit("dup").store(TX["j"])                               # tens
p.push(10).emit("mul", "sub").push(D0).emit("add").store(TX["r"])   # units glyph
p.set(int(STR_COMBO), 3)
p.load(TX["j"]).push(D0).emit("add").store(int(STR_COMBO) + 2)
p.load(TX["r"]).store(int(STR_COMBO) + 3)
p.load(TX["j"]).emit(f"jz {cz}_one", f"jmp {cz}")
p.mark(f"{cz}_one")
p.set(int(STR_COMBO), 2)
p.load(TX["r"]).store(int(STR_COMBO) + 2)
p.mark(cz)
p.push(int(STR_COMBO)).store(TX["str"])
p.set(TX["x"], 158).set(TX["y"], 218).set(TX["sc"], 3)
p.emit(f"call {L_TEXT}")
p.mark(f"{hk}_out")
p.load(TX["n"]).store(spec.DL_BASE)
p.mark(hk)

# ---- THE GAUGE (P6 dresses it): his health, on the compositor's free
# rectangles, from the first blow either way -- an untouched opening is
# the street and nothing else. And going down, the frame darkens -- to
# 7/16, so the prompt (in the framebuffer, under the compositor) reads.
HB = spec.CO_BASE + 1
hud = p.label("hud")
p.set(spec.CO_BASE, 4)
p.push(0).store(HB + 2).push(0).store(HB + 5).push(0).store(HB + 8).push(0).store(HB + 11)
p.load(F["fight"]).emit(f"jz {hud}")
p.rect(0, 8, 8, 110, 14, 0x100808, 12)
p.push(9).load(PHP).push(183).emit("mul", "shr 8").push(9).emit("add")
p.emit("shl 10", "or").store(HB + 3)               # x1 = 9 + hp * 100/140
p.set(HB + 4, 9 | (13 << 10))
p.push(0).load(PHP).emit("lt", f"jz {hud}")
p.push(16).emit("shl 24").push32(0xB02018).emit("or").store(HB + 5)
p.mark(hud)
# the meter toward the next rank, in the rank's colour (bottom right)
mh = p.label("meter")
p.load(F["fight"]).emit(f"jz {mh}")
p.push(BAR_W).load(SY["rank"]).push(6).emit("eq", f"jz {mh}_p", f"jmp {mh}_w")
p.mark(f"{mh}_p")
p.emit("drop")
p.load(SY["pts"]).push(int(S_AT)).load(SY["rank"]).emit("add", "loadi", "sub")
p.push(int(S_FAC)).load(SY["rank"]).emit("add", "loadi", "mulq")
p.mark(f"{mh}_w")
p.push(208).emit("add", "shl 10").push(208).emit("or").store(HB + 9)
p.set(HB + 10, 272 | (276 << 10))
p.push(14).emit("shl 24").push(int(S_RGB)).load(SY["rank"]).emit("add", "loadi", "or")
p.store(HB + 11)
p.mark(mh)
dk = p.label("dark")
p.load(F["dead"]).emit(f"jz {dk}")
p.set(HB + 6, 0 | (319 << 10)).set(HB + 7, 0 | (287 << 10))
p.load(F["dead"]).emit("shr 2").push(7).emit("over", "over", "lt", f"jz {dk}_m")
p.emit("drop", f"jmp {dk}_k")
p.mark(f"{dk}_m")
p.emit("swap", "drop")
p.mark(f"{dk}_k")
p.emit("shl 24").push32(0x000000).emit("or").store(HB + 8)
p.mark(dk)
# ---- the music's frame (stems as one loop over a table: IMEM is 4,096) ----------
p.mark(L_MUSIC)
EVN = cart.var("ev_n")
EV_BASE = spec.AU_EV_BASE + 1
EVW, EVV = cart.var("ev_w"), cart.var("ev_v")
L_EV = p.label("ev")
p.set(EVN, 0)


def ev_at(o_cell, ch_bits, value_ops):
    """append an event at sample o_cell: ch_bits = ch << 10 | ctrl << 14"""
    p.load(o_cell).push(ch_bits).emit("or").store(EVW)
    p.emit(*value_ops).store(EVV)
    p.emit(f"call {L_EV}")


INC, CTL = 0, 1 << 14
# the voiced stems, one row each: ctrl register, event channel bits,
# page bits, base volume, fade a frame (x16), its rank
_vs = [(s, st) for s, st in enumerate(STEMS) if st[1] is not None]
MSTEM = cart.data(Table([w for s, (n, v, pg, bv, fd) in _vs for w in (
    spec.AU_BASE + 2 * v + 1, v << 10, pg << 8, bv, fd, s)]), "music_stems")
MS = {k: cart.var("ms_" + k) for k in ("r", "n", "env")}
mi = p.label("mint")
p.push(70).load(SY["rank"]).push(34).emit("mul", "add").store(MU["s"])
p.load(F["dead"]).emit(f"jz {mi}_a")
p.set(MU["s"], 0)
p.mark(f"{mi}_a")
p.load(MU["inten"]).load(MU["s"]).emit("lt", f"jz {mi}_dn")
p.load(MU["inten"]).push(10).emit("add").store(MU["inten"])
p.load(MU["s"]).load(MU["inten"]).emit("lt", f"jz {mi}", f"jmp {mi}_cl")
p.mark(f"{mi}_dn")
p.load(MU["inten"]).push(3).emit("sub").store(MU["inten"])
p.load(MU["inten"]).load(MU["s"]).emit("lt", f"jz {mi}")
p.mark(f"{mi}_cl")
p.load(MU["s"]).store(MU["inten"])
p.mark(mi)


def field(k):
    p.load(MS["r"]).push(k).emit("add", "loadi")


def env_addr():
    field(5)
    p.push(int(MENV)).emit("add")


# ---- the frame's fades: every voiced stem, one loop -------------------------------
fl = p.label("fl")
p.push(int(MSTEM)).store(MS["r"]).push(len(_vs)).store(MS["n"])
p.mark(fl)
env_addr()
p.emit("loadi")
field(4)
p.emit("sub", "dup").push(0).emit("lt", f"jz {fl}_c")
p.emit("drop").push(0)
p.mark(f"{fl}_c")
p.store(MS["env"])
field(5)
p.push(1).emit("sub").load(SY["rank"]).emit("lt", f"jz {fl}_g", f"jmp {fl}_k")
p.mark(f"{fl}_g")
p.set(MS["env"], 0)                               # silent below its rank
p.mark(f"{fl}_k")
p.load(MS["env"])
env_addr()
p.emit("storei")
p.load(MS["env"]).emit("shr 4").load(MU["inten"]).emit("mul", "shr 8")
field(2)
p.emit("or")
field(0)
p.emit("storei")
p.addi(MS["r"], 6).addi(MS["n"], -1)
p.load(MS["n"]).emit(f"jz {fl}_e", f"jmp {fl}")
p.mark(f"{fl}_e")
# the kick: four frames of falling pitch and fading level
kk = p.label("kick")
p.load(MU["kick"]).push(4).emit("lt", f"jz {kk}_off")
p.push(KICK_HI).load(MU["kick"]).push(KICK_DROP).emit("mul", "sub")
p.store(spec.AU_BASE + 2)
p.push(15).load(MU["kick"]).push(4).emit("mul", "sub").load(MU["inten"]).emit("mul", "shr 8")
p.push(2 << 4).emit("or").store(spec.AU_BASE + 3)
p.addi(MU["kick"], 1).emit(f"jmp {kk}")
p.mark(f"{kk}_off")
p.set(spec.AU_BASE + 3, 0)
p.mark(kk)
dn = p.label("drumn")
p.load(MU["drum"]).load(MU["dfade"]).emit("sub", "dup").push(0).emit("lt", f"jz {dn}")
p.emit("drop").push(0)
p.mark(dn)
p.store(MU["drum"])
p.load(MU["drum"]).emit("shr 4").load(MU["inten"]).emit("mul", "shr 8")
p.store(spec.AU_BASE + 7)

# ---- a step, if one falls in this frame --------------------------------------------
st_ = p.label("step")
p.push(LOOP).load(MU["step"]).push(32).emit("eq", f"jz {st_}_g", f"jmp {st_}_n")
p.mark(f"{st_}_g")
p.emit("drop").load(MU["step"]).push(SIX).emit("mul")
p.mark(f"{st_}_n")
p.load(MU["t"]).emit("sub").store(MU["o"])
p.load(MU["o"]).push(spec.SAMPLES_PER_FRAME).emit("lt", f"jz {st_}")
p.load(MU["step"]).push(31).emit("and").store(MU["step"])     # 32 -> 0
L_BYTE = p.label("byte")
# the drums (stem 0): bit 0 kick, bit 1 snare, bit 2 china
p.push(int(MPAT)).emit(f"call {L_BYTE}")
nk = p.label("nk")
p.load(MU["code"]).push(1).emit("and", f"jz {nk}")
p.set(MU["kick"], 0)
ev_at(MU["o"], (1 << 10) | INC, (f"push {KICK_HI}",))
ev_at(MU["o"], (1 << 10) | CTL, (f"load {int(MU['inten'])}", "push 15", "mul",
                                 "shr 8", f"push {2 << 4}", "or"))
p.mark(nk)
nd = p.label("nd")
p.load(MU["code"]).push(6).emit("and", f"jz {nd}")
p.push(15 * 16).store(MU["drum"]).set(MU["dfade"], 34).push(hz(9000)).store(MU["s"])
p.load(MU["code"]).push(4).emit("and", f"jz {nd}_s")
p.set(MU["dfade"], 11).push(hz(6000)).store(MU["s"])           # the china
p.mark(f"{nd}_s")
ev_at(MU["o"], (3 << 10) | INC, (f"load {int(MU['s'])}",))
ev_at(MU["o"], (3 << 10) | CTL, (f"load {int(MU['inten'])}", "push 15", "mul", "shr 8"))
p.mark(nd)
# the voiced stems: one loop
sl = p.label("sl")
p.push(int(MSTEM)).store(MS["r"]).push(len(_vs)).store(MS["n"])
p.mark(sl)
field(5)
p.push(1).emit("sub").load(SY["rank"]).emit("lt", f"jz {sl}_nx")   # below its rank
field(5)
p.push(8).emit("mul").push(int(MPAT)).emit("add", f"call {L_BYTE}")
p.load(MU["code"]).emit(f"jz {sl}_nx")           # HOLD
p.load(MU["code"]).push(REST).emit("eq", f"jz {sl}_note")
p.push(0)
env_addr()
p.emit("storei")
field(1)
p.load(MU["o"]).emit("or").push(CTL).emit("or").store(EVW)
field(2)
p.store(EVV).emit(f"call {L_EV}", f"jmp {sl}_nx")
p.mark(f"{sl}_note")
field(3)
p.push(16).emit("mul")
env_addr()
p.emit("storei")
field(1)
p.load(MU["o"]).emit("or").store(EVW)
p.push(int(MNOTE) - 2).load(MU["code"]).emit("add", "loadi").store(EVV)
p.emit(f"call {L_EV}")
field(1)
p.load(MU["o"]).emit("or").push(CTL).emit("or").store(EVW)
field(3)
p.load(MU["inten"]).emit("mul", "shr 8")
field(2)
p.emit("or").store(EVV).emit(f"call {L_EV}")
p.mark(f"{sl}_nx")
p.addi(MS["r"], 6).addi(MS["n"], -1)
p.load(MS["n"]).emit(f"jz {sl}_e", f"jmp {sl}")
p.mark(f"{sl}_e")
p.addi(MU["step"], 1)
p.mark(st_)
p.load(MU["t"]).push(spec.SAMPLES_PER_FRAME).emit("add").store(MU["t"])
lp = p.label("loop")
p.load(MU["t"]).push(LOOP).emit("lt", f"jz {lp}_w", f"jmp {lp}")
p.mark(f"{lp}_w")
p.load(MU["t"]).push(LOOP).emit("sub").store(MU["t"])
p.mark(lp)

sx = p.label("sfx")
p.load(SFX_T).push(SFX_N).emit("lt", f"jz {sx}_q")
p.load(SFX_H).push(6).emit("mul").push(int(SFX)).emit("add").store(SFX_R)
fv = p.label("fv")
p.load(SFX_R).emit("loadi").store(spec.AU_BASE + 0)                  # ring inc
p.load(SFX_T).push(4).emit("lt", f"jz {fv}_r0")
p.push(int(SFX_V)).load(SFX_T).emit("add", "loadi", f"jmp {fv}_r")
p.mark(f"{fv}_r0")
p.push(0)
p.mark(f"{fv}_r")
p.store(spec.AU_BASE + 1)
p.load(SFX_R).push(1).emit("add", "loadi")                          # thump falls
p.load(SFX_R).push(2).emit("add", "loadi").load(SFX_T).emit("mul", "add")
p.store(spec.AU_BASE + 4)
p.push(15 * 256).load(SFX_R).push(3).emit("add", "loadi").load(SFX_T)
p.emit("mul", "sub", "shr 8", "dup").push(0).emit("lt", f"jz {fv}_t")   # ...and fades
p.emit("drop").push(0)
p.mark(f"{fv}_t")
p.load(SFX_T).load(SFX_R).push(5).emit("add", "loadi").emit("lt", f"jz {fv}_t0")
p.emit(f"jmp {fv}_t1")
p.mark(f"{fv}_t0")
p.emit("drop").push(0)
p.mark(f"{fv}_t1")
p.store(spec.AU_BASE + 5)
p.load(SFX_R).push(4).emit("add", "loadi").store(spec.AU_BASE + 6)   # the meat
p.load(SFX_T).emit(f"jz {fv}_s", f"jmp {fv}_m")
p.mark(f"{fv}_s")
p.push(hz(12000)).store(spec.AU_BASE + 6)                            # (the slap)
p.mark(f"{fv}_m")
p.load(SFX_T).push(4).emit("lt", f"jz {fv}_n0")
p.push(int(SFX_V) + 4).load(SFX_H).push(4).emit("mul", "add").load(SFX_T)
p.emit("add", "loadi", f"jmp {fv}_n")
p.mark(f"{fv}_n0")
p.push(0)
p.mark(f"{fv}_n")
p.store(spec.AU_BASE + 7)
p.load(SFX_T).emit(f"jz {sx}_ev", f"jmp {sx}_n")
p.mark(f"{sx}_ev")                               # first frame: slap -> meat
SLAP_AT = cart.var("sfx_slap_at")
p.set(SLAP_AT, SFX_SLAP)
ev_at(SLAP_AT, (3 << 10) | INC, (f"push {int(SFX_MEAT)}", f"load {int(SFX_H)}", "add", "loadi"))
p.mark(f"{sx}_n")
p.addi(SFX_T, 1)
p.emit(f"jmp {sx}")
p.mark(f"{sx}_q")
for reg in (1, 5):                               # quiet (ch3 is the drums')
    p.set(spec.AU_BASE + reg, 0)
p.mark(sx)
p.load(EVN).store(spec.AU_EV_BASE)

p.emit("load 1").store(PV)

# ---- subroutines (after the halt) -------------------------------------------
p.emit("halt")

# VIS: ( -- seen? ). The sphere (vis_cx, vis_cy relative to the eye,
# vis_cz, vis_r) into view space: yaw by the camera's right/forward,
# then its fixed pitch (vy' = vy cos + vz sin, vz' = -vy sin + vz cos).
# Unseen if wholly behind the eye or wholly outside a side plane.
no_l, yes_l = p.label("vno"), p.label("vyes")
p.mark(L_VIS)
p.load(VIS["cx"]).load(spec.CAM_X).emit("sub").store(VIS["cx"])
p.load(VIS["cz"]).load(spec.CAM_Z).emit("sub").store(VIS["cz"])
p.load(VIS["cx"]).load(VIS["rx"]).emit("mulq")          # xc = d . right
p.load(VIS["cz"]).load(VIS["rz"]).emit("mulq", "add").store(VIS["xc"])
p.load(VIS["cz"]).load(VIS["rx"]).emit("mulq")          # zc = d . forward
p.load(VIS["cx"]).load(VIS["rz"]).emit("mulq", "sub").store(VIS["zc"])
p.push(0).load(VIS["cy"]).emit("sub").push(PSIN).emit("mulq")   # -vy sin
p.load(VIS["zc"]).push(PCOS).emit("mulq", "add").store(VIS["zc"])
p.load(VIS["zc"]).load(VIS["r"]).emit("add").push(0)
p.emit("lt", f"jz {no_l}_b")                             # zc + r < 0: behind
p.emit(f"jmp {no_l}")
p.mark(f"{no_l}_b")
p.load(VIS["xc"]).emit("dup").push(0).emit("lt", f"jz {yes_l}_a")
p.push(0).emit("swap", "sub")                            # |xc|
p.mark(f"{yes_l}_a")
p.push(SCOS).emit("mulq")
p.load(VIS["zc"]).push(SSIN).emit("mulq", "sub")         # |xc| cos - zc sin
p.load(VIS["r"]).emit("swap", "lt", f"jz {yes_l}")       # r < that: outside
p.mark(no_l)
p.push(0).emit("ret")
p.mark(yes_l)
p.push(1).emit("ret")

# ARENA: ( -- inside? ) for (ar_x, ar_z), the archive's '+'.
p.mark(L_ARENA)
for c in ("x", "z"):                                 # |x|, |z| in place
    pos = p.label("abs")
    p.load(AR[c]).emit("dup").push(0).emit("lt", f"jz {pos}")
    p.push(0).emit("swap", "sub")
    p.mark(pos)
    p.store(AR[c])
yes = p.label("ain")
p.push(AR_SQ).load(AR["x"]).emit("lt")               # outside the square?
p.push(AR_SQ).load(AR["z"]).emit("lt", "or", f"jz {yes}")
for a, b in (("x", "z"), ("z", "x")):                # either street
    p.push(AR_LANE).load(AR[a]).emit("lt")
    p.push(AR_REACH).load(AR[b]).emit("lt", "or", f"jz {yes}")
p.push(0).emit("ret")
p.mark(yes)
p.push(1).emit("ret")

# COPY: n words from src to dst
cl = p.label("copy_l")
p.mark(L_COPY)
p.mark(cl)
p.load(CP["n"]).emit(f"jz {cl}_e")
p.load(CP["src"]).emit("loadi").load(CP["dst"]).emit("storei")
p.addi(CP["src"], 1).addi(CP["dst"], 1).addi(CP["n"], -1)
p.emit(f"jmp {cl}")
p.mark(f"{cl}_e")
p.emit("ret")

# WPT: the keypoint at w_k (character-local, 3 words) placed in the world
# by (w_bx, w_bz) and the yaw whose cos/sin are (w_c, w_s) -- the GPU's
# own model->world turn, so a key and the drawn body agree.
p.mark(L_WPT)
p.load(W["k"]).emit("loadi").store(W["x"])        # lx
p.load(W["k"]).push(1).emit("add", "loadi").load(W["oy"]).emit("add").store(W["y"])
p.load(W["k"]).push(2).emit("add", "loadi").store(W["z"])   # lz
p.load(W["x"]).load(W["c"]).emit("mulq").load(W["z"]).load(W["s"]).emit("mulq", "sub")
p.load(W["x"]).load(W["s"]).emit("mulq").load(W["z"]).load(W["c"]).emit("mulq", "add")
p.load(W["bz"]).emit("add").store(W["z"])
p.load(W["bx"]).emit("add").store(W["x"])
p.emit("ret")

# D2: ( -- |w - q|^2 )
p.mark(L_D2)
for a, b in (("x", "qx"), ("y", "qy"), ("z", "qz")):
    p.load(W[a]).load(W[b]).emit("sub", "dup", "mulq")
p.emit("add", "add", "ret")


def key_d2(kp_ops, bx, bz, c, s):
    """push |key - q|^2 for the key at kp (ops leaving its address)"""
    p.emit(*kp_ops).store(W["k"])
    for a, b in (("bx", bx), ("bz", bz), ("c", c), ("s", s)):
        p.load(b).store(W[a])
    p.emit(f"call {L_WPT}", f"call {L_D2}")


def nearest(kp_ops, bx, bz, c, s):
    """chin and gut against q: leaves HEAD (1/0) in w_head and the nearer
    distance^2 in w_d2"""
    key_d2(kp_ops, bx, bz, c, s)
    p.store(W["dc"])
    key_d2(kp_ops + ("push 3", "add"), bx, bz, c, s)
    p.store(W["dg"])
    p.load(W["dc"]).load(W["dg"]).emit("lt").store(W["head"])
    hd = p.label("hd")
    p.load(W["dg"]).store(W["d2"])
    p.load(W["head"]).emit(f"jz {hd}")
    p.load(W["dc"]).store(W["d2"])
    p.mark(hd)


def landed(table, mv, table_is_cell):
    """after nearest(): w_dmg and w_stop for the move, head or not"""
    hd = p.label("hdmg")
    row(table, mv, "dmg", const_table=not table_is_cell)
    p.store(W["dmg"])
    row(table, mv, "stop", const_table=not table_is_cell)
    p.store(W["stop"])
    p.load(W["head"]).emit(f"jz {hd}")
    row(table, mv, "dmgh", const_table=not table_is_cell)
    p.store(W["dmg"])
    p.addi(W["stop"], 3)
    p.mark(hd)


# DMIND: one demon, on CUR. Three things, in tear.py's order of effect:
#   A  his swing against me   B  my body: frozen, falling, stunned or
#   free (the turret mind)    C  my swing against him
X, Z, H8 = cur("x"), cur("z"), cur("h8")
ST, MF, MV, AI = (cur(f) for f in ("st", "mf", "mv", "ai"))
WF, MOV, ALT, CF = (cur(f) for f in ("wf", "mov", "alt", "cf"))
t = DTEMP
lab = {k: p.label("dm" + k) for k in
       ("gone", "noA", "missA", "B", "frz", "fall", "fallc", "stun", "mind",
        "noturn", "neg", "turned", "free", "near", "nocone", "clip", "walkc",
        "movec", "idlec", "pose", "cx", "over", "noC", "ret", "deadA")}
p.mark(L_DMIND)
p.load(ST).push(4).emit("eq", f"jz {lab['gone']}")
p.emit("ret")
p.mark(lab["gone"])
p.load(X).store(cur("ox")).load(Z).store(cur("oz"))
p.load(H8).emit("shr 8").store(t["ty"])
sin_of(p, cell=t["ty"])
p.store(t["s"])
sin_of(p, 256, cell=t["ty"])
p.store(t["c"])

# ---- A: his fist, against my chin and gut -------------------------------------
p.load(F["act"]).emit(f"jz {lab['noA']}")
p.load(ST).push(3).emit("lt", f"jz {lab['noA']}")    # the fallen are past it
for a, b in (("qx", "fx"), ("qy", "fy"), ("qz", "fz")):
    p.load(F[b]).store(W[a])
p.load(cur("py")).store(W["oy"])                 # struck where it is: aloft
nearest((f"load {cur('kp')}",), X, Z, t["c"], t["s"])
p.load(W["d2"])
row(PMT, F["mv"], "reach2")
p.emit("lt", f"jz {lab['noA']}")
landed(PMT, F["mv"], False)
p.load(cur("hp")).load(W["dmg"]).emit("sub").store(cur("hp"))
p.load(W["stop"]).emit("dup", "dup").store(cur("stop")).store(F["stop"])
p.store(F["shake"])
p.load(W["stop"]).push(12).emit("add").store(cur("hs"))
p.set(F["con"], 1).set(F["act"], 0).set(F["fight"], 1)
sound_blow(W["head"])
# STYLE: the blow pays its move's style x its variety x the combo
p.set(SY["cnt"], 0)
for i in range(5):
    p.load(int(S_REC) + i).load(F["mv"]).emit("eq").load(SY["cnt"]).emit("add").store(SY["cnt"])
cm = p.label("cmul")
p.load(SY["cnt"]).push(3).emit("lt", f"jz {cm}_3")
p.push(int(S_MULT)).load(SY["cnt"]).emit("add", "loadi", f"jmp {cm}")
p.mark(f"{cm}_3")
p.push(int(S_MULT) + 3).emit("loadi")
p.mark(cm)
row(PMT, F["mv"], "style")
p.emit("mul")
p.load(SY["combo"]).emit("dup").push(20).emit("lt", f"jz {cm}_c20", f"jmp {cm}_c")
p.mark(f"{cm}_c20")
p.emit("drop").push(20)
p.mark(f"{cm}_c")
p.push(20).emit("add", "mul").push(int(round(ONE / 25))).emit("mulq")   # x16/400
p.load(SY["pts"]).emit("add").store(SY["pts"])
p.addi(SY["combo"], 1).set(SY["idle"], 0)
p.load(F["mv"]).push(int(S_REC)).load(SY["rp"]).emit("add", "storei")
p.addi(SY["rp"], 1)
p.load(SY["rp"]).push(5).emit("eq", f"jz {cm}_r")
p.set(SY["rp"], 0)
p.mark(f"{cm}_r")
p.set(ST, 2).set(MF, 0)                         # a hit stops a swing
# THE LAUNCHER sends it up, helpless the whole arc; any OTHER blow on a
# body already aloft floors its rise to a nudge and refreshes its stun
# (tear.py AIR_HIT_FLOAT / AIR_HIT_HANG) -- so a string keeps it there
lw, la = p.label("lift"), p.label("airh")
row(PMT, F["mv"], "lift")
p.emit("dup", f"jz {lw}_no")
p.store(cur("vy"))
row(PMT, F["mv"], "air")
p.store(cur("hs")).emit(f"jmp {lw}")
p.mark(f"{lw}_no")
p.emit("drop")
p.load(cur("py")).emit(f"jz {lw}")
p.load(cur("vy")).push(AIR_FLOAT).emit("lt", f"jz {la}")
p.set(cur("vy"), AIR_FLOAT)
p.mark(la)
p.load(cur("hs")).push(AIR_HANG).emit("lt", f"jz {lw}")
p.set(cur("hs"), AIR_HANG)
p.mark(lw)
for vel, trig, neg in ((cur("vx"), F["ps"], True), (cur("vz"), F["pc"], False)):
    p.load(trig)
    row(PMT, F["mv"], "knock")
    p.emit("mulq").load(vel).emit("swap", "sub" if neg else "add").store(vel)
p.push(0).load(cur("hp")).emit("lt", f"jz {lab['deadA']}")
p.emit(f"jmp {lab['noA']}")
p.mark(lab["deadA"])
p.set(ST, 3).set(cur("dt"), 0).set(cur("hs"), 0)  # down
p.mark(lab["noA"])

# ---- B: my body -------------------------------------------------------------------
p.load(cur("stop")).emit(f"jz {lab['frz']}")
p.addi(cur("stop"), -1).emit("ret")             # frozen in the blow
p.mark(lab["frz"])
for pos, vel in ((X, cur("vx")), (Z, cur("vz"))):
    p.load(pos).load(vel).emit("add").store(pos)
    p.load(vel).push(FRIC).emit("mulq").store(vel)
# ALOFT: the arc under the aerial gravity, down to the street (tear.py
# _enemy_vertical)
gr = p.label("grav")
p.load(cur("py")).load(cur("vy")).emit("or", f"jz {gr}")
p.load(cur("vy")).push(GRAVQ).emit("sub").store(cur("vy"))
p.load(cur("py")).load(cur("vy")).emit("add").store(cur("py"))
p.push(0).load(cur("py")).emit("lt", f"jz {gr}_floor", f"jmp {gr}")
p.mark(f"{gr}_floor")
p.set(cur("py"), 0).set(cur("vy"), 0)
p.mark(gr)
p.load(ST).push(3).emit("eq", f"jz {lab['fall']}")
# FALLING: the archive's collapse (HURT -> DOWN, 26 frames, baked at 30 Hz),
# then down a beat and gone
p.addi(cur("dt"), 1)
p.load(cur("dt")).push(26 + 90).emit("lt", f"jz {lab['fallc']}")
p.load(cur("dt")).emit("shr 1", "dup").push(CLIPN["dead"] - 1)
p.emit("lt", f"jz {lab['fallc']}_m", f"jmp {lab['fallc']}_k")
p.mark(f"{lab['fallc']}_m")
p.emit("drop").push(CLIPN["dead"] - 1)                 # lies there
p.mark(f"{lab['fallc']}_k")
p.push(CLIP0["dead"]).emit("add").push(NPART).emit("mul")
p.push(int(CLIPT)).emit("add").store(CF)
p.emit("ret")
p.mark(lab["fallc"])
p.set(ST, 4).emit("ret")
p.mark(lab["fall"])
p.load(cur("hs")).emit(f"jz {lab['stun']}")
p.addi(cur("hs"), -1)
p.push(CLIP0["hurt"] * NPART + int(CLIPT)).store(CF)
p.load(cur("hs")).emit(f"jz {lab['stun']}_e", "ret")
p.mark(f"{lab['stun']}_e")
p.set(ST, 0).emit("ret")
p.mark(lab["stun"])
# ---- the turret mind (tear.py 3268): slow to walk, turn, commit ----------
p.push(0).load(t["s"]).emit("sub").store(t["fx"])    # forward = (-sin, cos)
p.load(t["c"]).store(t["fz"])
p.load(PX).load(X).emit("sub").store(t["dx"])
p.load(PZ).load(Z).emit("sub").store(t["dz"])
p.load(t["fx"]).load(t["dz"]).emit("mulq")
p.load(t["fz"]).load(t["dx"]).emit("mulq", "sub").store(t["cr"])
p.load(t["fx"]).load(t["dx"]).emit("mulq")
p.load(t["fz"]).load(t["dz"]).emit("mulq", "add").store(t["dot"])
# AWARE: he is inside the frontal cone -- entered at 0.46 rad, left only
# past 0.60, so circling right at its edge does not chatter the marker
p.push(0).load(t["dot"]).emit("lt")
p.load(t["cr"]).load(t["cr"]).emit("mulq")
p.load(t["dot"]).load(t["dot"]).emit("mulq")
p.load(cur("aw")).push(CONE_OUT - DCONE).emit("mul").push(DCONE).emit("add", "mulq")
p.emit("lt", "and").store(cur("aw"))
# turn -- unless already on him (cross^2 < dot^2 / 256, dot > 0)
p.push(0).load(t["dot"]).emit("lt")
p.load(t["cr"]).load(t["cr"]).emit("mulq")
p.load(t["dot"]).load(t["dot"]).emit("mulq", "shr 8", "lt", "and")
p.emit(f"jz {lab['noturn']}", f"jmp {lab['turned']}")
p.mark(lab["noturn"])
p.load(t["cr"]).push(0).emit("lt", f"jz {lab['neg']}")
p.load(H8).push(DTURN).emit("sub").store(H8)
p.emit(f"jmp {lab['turned']}")
p.mark(lab["neg"])
p.load(H8).push(DTURN).emit("add").store(H8)
p.mark(lab["turned"])
p.load(H8).push((1024 << 8) - 1).emit("and").store(H8)
# a swing in progress owns the body until its frames are done
p.load(ST).emit(f"jz {lab['free']}")
p.addi(MF, 1)
p.load(MF)
row(cur("mt"), MV, "total", const_table=False)
p.emit("lt", f"jz {lab['over']}")
p.emit(f"jmp {lab['clip']}")
p.mark(lab["over"])
p.set(ST, 0)                    # done: stands (or walks) this same frame
p.mark(lab["free"])
p.set(MOV, 0)
p.load(t["dx"]).load(t["dx"]).emit("mulq")
p.load(t["dz"]).load(t["dz"]).emit("mulq", "add")
p.push(DREACH2).emit("swap", "lt", f"jz {lab['near']}")
p.load(t["fx"]).push(DWALK).emit("mulq").load(X).emit("add").store(X)
p.load(t["fz"]).push(DWALK).emit("mulq").load(Z).emit("add").store(Z)
p.set(MOV, 1).set(AI, 0)
p.emit(f"jmp {lab['clip']}")
p.mark(lab["near"])
p.load(F["dead"]).emit(f"jz {lab['nocone']}_l")      # nobody hits a corpse
p.emit(f"jmp {lab['nocone']}")
p.mark(f"{lab['nocone']}_l")
p.push(0).load(t["dot"]).emit("lt")              # in front...
p.load(t["cr"]).load(t["cr"]).emit("mulq")
p.load(t["dot"]).load(t["dot"]).emit("mulq").push(DCONE).emit("mulq")
p.emit("lt", "and", f"jz {lab['nocone']}")      # ...and inside the cone
p.addi(AI, 1)
p.load(AI).push(DREST).emit("eq", f"jz {lab['clip']}")
p.set(AI, 0).set(ST, 1).set(MF, 0).set(cur("con"), 0)
p.load(ALT).store(MV)
p.load(ALT).push(1).emit("xor").store(ALT)
for vel, trig in ((cur("vx"), t["fx"]), (cur("vz"), t["fz"])):   # the lunge
    p.load(trig)
    row(cur("mt"), MV, "lunge", const_table=False)
    p.emit("mulq").load(vel).emit("add").store(vel)
p.emit(f"jmp {lab['clip']}")
p.mark(lab["nocone"])
p.set(AI, 0)                                     # off its nose: no swing
# ---- which frame of which clip ------------------------------------------------
p.mark(lab["clip"])
p.load(WF).push(1).emit("add").push(63).emit("and").store(WF)
p.load(ST).emit(f"jz {lab['walkc']}")
p.load(MV).emit(f"jz {lab['movec']}")
p.load(MF).push(CLIP0["hook"]).emit("add", f"jmp {lab['pose']}")
p.mark(lab["movec"])
p.load(MF).push(CLIP0["cross"]).emit("add", f"jmp {lab['pose']}")
p.mark(lab["walkc"])
p.load(MOV).emit(f"jz {lab['idlec']}")
p.load(WF).emit("shr 2").push(15).emit("and").push(CLIP0["walk"])
p.emit("add", f"jmp {lab['pose']}")
p.mark(lab["idlec"])
p.load(WF).emit("shr 1").push(31).emit("and").push(CLIP0["idle"]).emit("add")
p.mark(lab["pose"])
p.push(NPART).emit("mul").push(int(CLIPT)).emit("add").store(CF)

# ---- C: my fist, against his chin and gut ------------------------------------------
p.load(ST).push(1).emit("eq", f"jz {lab['noC']}")
p.load(cur("con")).emit(f"jz {lab['noC']}_c", f"jmp {lab['noC']}")
p.mark(f"{lab['noC']}_c")
p.load(F["dead"]).emit(f"jz {lab['noC']}_d", f"jmp {lab['noC']}")
p.mark(f"{lab['noC']}_d")
p.load(MF)
row(cur("mt"), MV, "start", const_table=False)
p.emit("lt", f"jz {lab['noC']}_s", f"jmp {lab['noC']}")
p.mark(f"{lab['noC']}_s")
p.load(MF)
row(cur("mt"), MV, "endact", const_table=False)
p.emit("lt", f"jz {lab['noC']}")
# my fist in the world -> q
row(cur("mt"), MV, "fist", const_table=False)
p.load(MF)
row(cur("mt"), MV, "start", const_table=False)
p.emit("sub").push(3).emit("mul", "add").store(W["k"])
for a, b in (("bx", X), ("bz", Z), ("c", t["c"]), ("s", t["s"])):
    p.load(b).store(W[a])
p.set(W["oy"], 0)
p.emit(f"call {L_WPT}")
for a, b in (("qx", "x"), ("qy", "y"), ("qz", "z")):
    p.load(W[b]).store(W[a])
nearest((f"push {int(PKEY)}",), PX, PZ, F["pc"], F["ps"])
p.load(W["d2"])
row(cur("mt"), MV, "reach2", const_table=False)
p.emit("lt", f"jz {lab['noC']}")
landed(cur("mt"), MV, True)
p.load(PHP).load(W["dmg"]).emit("sub").store(PHP)
p.load(W["stop"]).emit("dup", "dup").store(cur("stop")).store(F["stop"])
p.store(F["shake"])
p.load(W["stop"]).push(12).emit("add").store(F["hs"])
p.set(cur("con"), 1).set(F["fight"], 1)
sound_blow(W["head"])
p.load(SY["pts"]).push(int(round(0.45 * ONE))).emit("mulq").store(SY["pts"])
p.set(SY["combo"], 0)
for i in range(5):
    p.set(int(S_REC) + i, 255)
p.set(ANIM, 3).set(F["buf"], 0)                   # his swing is broken
for vel, trig, neg in ((F["vx"], t["s"], True), (F["vz"], t["c"], False)):
    p.load(trig)
    row(cur("mt"), MV, "knock", const_table=False)
    p.emit("mulq").load(vel).emit("swap", "sub" if neg else "add").store(vel)
p.push(0).load(PHP).emit("lt", f"jz {lab['noC']}_k")
p.emit(f"jmp {lab['noC']}")
p.mark(f"{lab['noC']}_k")
p.set(F["dead"], 1).set(ANIM, 4).set(F["hs"], 0)  # he is down
bst = p.label("best")
p.load(SY["pts"]).emit("shr 4").load(SY["best"]).emit("lt", f"jz {bst}", f"jmp {bst}_k")
p.mark(bst)
p.load(SY["pts"]).emit("shr 4").store(SY["best"])        # tear.py: the best run
p.mark(f"{bst}_k")
p.mark(lab["noC"])
p.emit("ret")

# EV: append (ev_w, ev_v) to the frame's event list
p.mark(L_EV)
p.load(EVW).push(EV_BASE).load(EVN).push(2).emit("mul", "add", "storei")
p.load(EVV).push(EV_BASE + 1).load(EVN).push(2).emit("mul", "add", "storei")
p.addi(EVN, 1).emit("ret")
# BYTE: ( stem's pattern base -- ) mu_code = that stem's byte at mu_step
bl = p.label("bl")
p.mark(L_BYTE)
p.load(MU["step"]).emit("shr 2", "add", "loadi")
p.load(MU["step"]).push(3).emit("and").store(MU["s"])
p.mark(bl)
p.load(MU["s"]).emit(f"jz {bl}_e")
p.emit("shr 8").addi(MU["s"], -1).emit(f"jmp {bl}")
p.mark(f"{bl}_e")
p.push(255).emit("and").store(MU["code"]).emit("ret")

# TEXT: the string at tx_str (length, then glyphs) at (tx_x, tx_y), x tx_sc,
# in tx_rgb, appended to the display list (tx_n triangles so far) -- each
# glyph's packed rectangles as the forge's Text draws them: two triangles
# a rectangle, the advance four pixels a scale.
tl_, ts_, tw_ = p.label("tl"), p.label("ts"), p.label("tw")
p.mark(L_TEXT)
p.load(TX["str"]).emit("loadi").store(TX["k"])
p.mark(tl_)                                       # each glyph
p.load(TX["k"]).emit(f"jz {tl_}_e")
p.addi(TX["str"], 1)
p.load(TX["str"]).emit("loadi").push(2).emit("mul").push(int(FONT)).emit("add")
p.store(TX["gp"])                                 # its two packed words
p.set(TX["r"], 6)                                 # six rectangle slots
p.mark(ts_)
p.load(TX["r"]).push(3).emit("eq").load(TX["r"]).push(6).emit("eq", "or", f"jz {ts_}_s")
p.load(TX["gp"]).emit("loadi").store(TX["w"]).addi(TX["gp"], 1)   # the next word
p.mark(f"{ts_}_s")
nr = p.label("nr")
p.load(TX["w"]).push(3 << 5).emit("and", f"jz {nr}")          # no width: none
p.load(TX["w"]).push(3).emit("and").load(TX["sc"]).emit("mul")
p.load(TX["x"]).emit("add").store(TX["x0"])
p.load(TX["w"]).emit("shr 2").push(7).emit("and").load(TX["sc"]).emit("mul")
p.load(TX["y"]).emit("add").store(TX["y0"])
p.load(TX["w"]).emit("shr 5").push(3).emit("and").load(TX["sc"]).emit("mul")
p.load(TX["x0"]).emit("add").store(TX["x1"])
p.load(TX["w"]).emit("shr 7").push(7).emit("and").push(1).emit("add")
p.load(TX["sc"]).emit("mul").load(TX["y0"]).emit("add").store(TX["y1"])
# two triangles, fourteen words: which cell each is comes from a table
p.push(spec.DL_BASE + 1).load(TX["n"]).push(spec.DL_STRIDE).emit("mul", "add")
p.store(TX["dl"])
p.set(TX["j"], 0)
p.mark(tw_)
p.push(int(TRI_CELLS)).load(TX["j"]).emit("add", "loadi", "loadi")
p.load(TX["dl"]).load(TX["j"]).emit("add", "storei")
p.addi(TX["j"], 1)
p.load(TX["j"]).push(2 * spec.DL_STRIDE).emit("lt", f"jz {tw_}_e", f"jmp {tw_}")
p.mark(f"{tw_}_e")
p.addi(TX["n"], 2)
p.mark(nr)
p.load(TX["w"]).emit("shr 10").store(TX["w"])
p.addi(TX["r"], -1)
p.load(TX["r"]).emit(f"jz {ts_}_e", f"jmp {ts_}")
p.mark(f"{ts_}_e")
p.load(TX["x"]).load(TX["sc"]).push(4).emit("mul", "add").store(TX["x"])
p.addi(TX["k"], -1).emit(f"jmp {tl_}")
p.mark(f"{tl_}_e")
p.emit("ret")

_kia_sub()
_shv_sub()

# SINE: ( a -- sin a ), Q16.16, from the quarter wave. sin(a) for a in
# 256..511 is sin(512 - a); the lower half-turn negates the upper.
qs = {k: cart.var("qs_" + k) for k in ("a", "i")}
pos_l = p.label("qpos")
p.mark(L_SINE)
p.push(1023).emit("and", "dup").store(qs["a"])
p.push(255).emit("and").store(qs["i"])
p.load(qs["a"]).push(256).emit("and", f"jz {L_SINE}_q")
p.push(256).load(qs["i"]).emit("sub").store(qs["i"])
p.mark(f"{L_SINE}_q")
p.push(int(QSIN)).load(qs["i"]).emit("add", "loadi")
p.load(qs["a"]).push(512).emit("and", f"jz {pos_l}")
p.push(0).emit("swap", "sub")
p.mark(pos_l)
p.emit("ret")

def rot2(u, v, ang):
    """(u, v) <- rotated by the angle in cell `ang`: the GPU's own _rotv"""
    p.load(ang).emit(f"call {L_SINE}").store(FK["s"])
    p.load(ang).push(256).emit("add", f"call {L_SINE}").store(FK["c"])
    p.load(u).load(FK["c"]).emit("mulq").load(v).load(FK["s"]).emit("mulq", "sub")
    p.load(u).load(FK["s"]).emit("mulq").load(v).load(FK["c"]).emit("mulq", "add")
    p.store(v).store(u)


# ROT: (vx, vy, vz) <- R(ra) v, ra a packed angles word: roll (x,y), then
# pitch (y,z), then yaw (x,z) -- exactly the order the GPU poses a model in
p.mark(L_ROT)
for shift, (u, v) in ((20, ("vx", "vy")), (10, ("vy", "vz")), (0, ("vx", "vz"))):
    p.load(FK["ra"])
    if shift:
        p.emit(f"shr {shift}")
    p.push(1023).emit("and").store(FK["t"])
    rot2(FK[u], FK[v], FK["t"])
p.emit("ret")

# FK: one demon's twelve parts into the object list. Args: fk_x, fk_z,
# fk_yaw (its heading), fk_jt (its build's joint table), fk_cf (this
# frame's row of the clip table). Each part: its origin is its parent's
# plus the parent's rotation of its offset (char-local, kept in dem_pt),
# then the whole demon turns by its heading -- which, yaw being the
# GPU's LAST rotation, is also just an add to every part's yaw.
top = p.label("fk_top")
place = p.label("fk_place")
p.mark(L_FK)
p.set(FK["j"], 0)
p.load(FK["jt"]).store(FK["rp"])
p.push(int(PT)).store(FK["pp"])
p.mark(top)
p.load(FK["cf"]).load(FK["j"]).emit("add", "loadi").store(FK["a"])
for k, c in ((2, "vx"), (3, "vy"), (4, "vz")):
    p.load(FK["rp"]).push(k).emit("add", "loadi").store(FK[c])
p.load(FK["rp"]).emit("loadi").push(0).emit("lt", f"jz {place}_par")
p.emit(f"jmp {place}")                                   # the root: no parent
p.mark(f"{place}_par")
p.load(FK["cf"]).load(FK["rp"]).emit("loadi", "add", "loadi").store(FK["ra"])
p.emit(f"call {L_ROT}")
p.load(FK["rp"]).push(1).emit("add", "loadi").store(FK["q"])
for k, c in enumerate(("vx", "vy", "vz")):
    p.load(FK[c]).load(FK["q"])
    if k:
        p.push(k).emit("add")
    p.emit("loadi", "add").store(FK[c])
p.mark(place)
for k, c in enumerate(("vx", "vy", "vz")):
    p.load(FK[c]).load(FK["pp"])
    if k:
        p.push(k).emit("add")
    p.emit("storei")
rot2(FK["vx"], FK["vz"], FK["yaw"])
p.object(NOBJ, (f"load {int(FK['rp'])}", "push 5", "add", "loadi"),
         (f"load {int(FK['vx'])}", f"load {int(FK['x'])}", "add"),
         (f"load {int(FK['vy'])}", f"load {int(FK['y'])}", "add"),
         (f"load {int(FK['vz'])}", f"load {int(FK['z'])}", "add"),
         (f"load {int(FK['a'])}", "push -1024", "and",
          f"load {int(FK['a'])}", f"load {int(FK['yaw'])}", "add",
          "push 1023", "and", "or"),
         (f"load {int(FK['flags'])}",))
p.addi(FK["rp"], 6)
p.addi(FK["pp"], 3)
p.addi(FK["j"], 1)
p.load(FK["j"]).push(NPART).emit("lt", f"jz {top}_end", f"jmp {top}")
p.mark(f"{top}_end")
p.load(FK["aw"]).emit(f"jz {top}_na")                 # the aware marker
p.object(NOBJ, AWARE_M, (f"load {int(FK['x'])}",),
         (f"load {int(FK['y'])}", f"push {AWARE_LIFT}", "add"),
         (f"load {int(FK['z'])}",), 0, spec.OBJ_CULL)
p.mark(f"{top}_na")
p.emit("ret")


out = cart.write(OUT)
print(cart.report())
print(f"street: {len(STREET)} objects, {STREET_FACES} faces")
print(f"poses: {len(bank) // SPAN} x {SPAN} words = {len(bank)} words "
      f"of CRAM; bases {base}")
