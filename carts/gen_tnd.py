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

# ---- the floor: a checker, black and white (the opus' first colours) -----
N, SZ = 12, 2 * ONE
fv, ff = [], []
for j in range(N + 1):
    for i in range(N + 1):
        fv += [(i - N // 2) * SZ, 0, (j - N // 2) * SZ]
for j in range(N):
    for i in range(N):
        a = j * (N + 1) + i
        b, c, e = a + 1, a + N + 1, a + N + 2
        col = 0xE8E8E8 if (i + j) & 1 else 0x202020
        ff += [(a, c, b, col), (b, c, e, col)]
FLOOR = cart.data(Mesh(fv, ff), "floor")

SIN = cart.data(Table([int(round(np.sin(i * 2 * np.pi / 1024) * ONE))
                       for i in range(1024)]), "sin")

PX, PZ, YAW = cart.var("px"), cart.var("pz"), cart.var("yaw")
ANIM, AF, POSE = cart.var("anim"), cart.var("af"), cart.var("pose")
IDLE = cart.var("idle_f")       # idle's own frame, WRAPPED -- never a
                                # modulo off REG_FRAME, whose cost would
                                # grow every frame for as long as you play
PV = cart.var("prevpad")
NOBJ = cart.var("nobj")

cart.boot(spec.CAM_Y, int(2.15 * ONE))           # the archive's follow height
cart.boot(spec.CAM_PITCH, 20)                    # ~0.12 rad DOWN: positive pitches down (the first cut had the sign backwards and put the horizon below centre)
cart.boot(spec.FOG_RGB, 0x101018)
cart.boot(spec.FOG_NEAR, 9000)
cart.boot(spec.FOG_SHIFT, 7)

p = cart.program()
WALK = int(0.032 * ONE)                          # the archive's walk pace
CAMD = 3                                         # camera distance, units
L = {k: p.label(k) for k in ("free", "noa", "jab", "walk", "idle",
                             "anim", "pj", "pi", "pd", "iw")}


def sin_of(q, plus=0):
    """push sin(yaw + plus) in Q16.16, from the 1024-entry table"""
    q.push(int(SIN)).load(YAW)
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

# ---- the camera, behind: fighter - CAMD * forward ---------------------------
sin_of(p)
p.push(CAMD).emit("mul").load(PX).emit("add").store(spec.CAM_X)
sin_of(p, 256)
p.push(CAMD).emit("mul").load(PZ).emit("swap", "sub").store(spec.CAM_Z)
p.load(YAW).store(spec.CAM_YAW)

# ---- the object list --------------------------------------------------------
p.set(NOBJ, 0)
p.object(NOBJ, int(FLOOR), 0, 0, 0, 0, spec.OBJ_CULL)
for m in (UPPER, LOWER):
    p.object(NOBJ, m, (f"load {int(PX)}",), 0, (f"load {int(PZ)}",),
             (f"load {int(YAW)}",), spec.OBJ_CULL)
p.load(NOBJ).store(spec.OL_BASE)
p.emit("load 1").store(PV)
p.emit("halt")

out = cart.write(HERE / "tnd.zol")
print(cart.report())
print(f"poses: {len(bank) // SPAN} x {SPAN} words = {len(bank)} words "
      f"of CRAM; bases {base}")
