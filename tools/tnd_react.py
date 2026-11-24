#!/usr/bin/env python3
# THE REACTIONS (TND-PORT P73). The player, the yard's fight on glass: "we have to
# make things feel epic and like damage is being done, re work the poses as
# needed to give weight to the hits and reactions".
#
# Until now a body struck kept its guard and leaned (a number in its turn). These
# are four clips of what a blow does to a body, baked on the archive's own rig as
# tools/tnd_acro.py bakes the acrobatics, into their OWN file --
# assets/tnd/react.npz -- so every layer built from boxer.npz stays as it is:
#
#   hurt_hi   8   a blow to the head: the chin taken back, the chest opened, the
#                 arms thrown off the guard, a foot gone back under him
#   hurt_lo   8   a blow to the body: folded over it, the arms come in, the knees
#   down      12  taken off his feet: back, into the air, flat on his back
#   getup     12  off the floor: sat, a hand down, crouched, his guard
#
# hurt_* go out to their worst in two frames, hold, and come back; a body held
# longer than the clip is held at its worst.
#
# And FOR THE SMALLER BODIES: each size's clips file (build/tiers/clips_N.npz) was
# baked from a mesh this checkout does not keep for two of the three. So the full
# body's poses are CARRIED to a smaller one: each of its corners follows the
# nearest corner of the full body (found in the guard both have), keeping the gap
# it had there; each of its faces takes the nearest face's shade. Measured on the
# clips both files already have, that is a centimetre off in the walk, the dodge
# and the flip. Written beside the clips: build/tiers/react_N.npz.
#
#   python3 tools/tnd_react.py [path/to/archive/TND]

import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / "archive" / "TND")
OUT = ROOT / "assets" / "tnd" / "react.npz"
TIERS = ROOT / "build" / "tiers"

CHILD = r'''
import sys, numpy as np
sys.path.insert(0, "src")
from zeta.virtual import boxer_mesh as bm
skel = bm._load_skeleton()
F = np.asarray(skel["F"], np.int64)
nv = int(F.max()) + 1

def frozen(res):
    faces, cols = res
    V = np.zeros((nv, 3))
    V[F.reshape(-1)] = np.asarray(faces).reshape(-1, 3)
    return V, np.asarray(cols)

def arms(r_swing, r_elbow, l_swing, l_elbow, out=0.0):
    """a swing forward is positive, the elbow bent forward; `out`: the arm carried off the body, sideways"""
    return {"RightArm": [0, r_swing, 90.0 - out], "RightForeArm": [0, r_elbow, 0],
            "LeftArm": [0, -l_swing, -90.0 + out], "LeftForeArm": [0, -l_elbow, 0]}

def blend(a_, b_, u):
    return {k: [a_.get(k, [0, 0, 0])[i] * (1 - u) + b_.get(k, [0, 0, 0])[i] * u for i in range(3)] for k in set(a_) | set(b_)}

def keyed(keys, u):
    for (u0, a_), (u1, b_) in zip(keys, keys[1:]):
        if u0 <= u <= u1:
            return blend(a_, b_, bm._smoothstep((u - u0) / (u1 - u0)))
    return dict(keys[-1][1])

def grounded(pose_):
    """the pose with its lowest point on the floor (the root lowered until it is)"""
    drop = 0.0
    for _ in range(8):
        drop += frozen(bm._pose_and_skin(pose_, np.array([0.0, -drop, 0.0]), None))[0][:, 2].min()
    return frozen(bm._pose_and_skin(pose_, np.array([0.0, -drop, 0.0]), None))

G = bm._guard_pose_dict()
HI = dict(G, **arms(-34, 46, -22, 58, out=34), **{
    "Hips": [-12, -18, 0], "Spine": [-16, -6, 0], "Spine1": [-14, -4, 0], "Neck": [-30, 14, 0], "Head": [-24, 8, 0],
    "LeftUpLeg": [-34, 0, 9], "LeftLeg": [22, 0, 0], "LeftFoot": [10, 0, 0],
    "RightUpLeg": [30, 0, -12], "RightLeg": [44, 0, 0], "RightFoot": [-14, 0, 0]})
LO = dict(G, **arms(34, 122, 30, 126), **{
    "Hips": [26, -18, 0], "Spine": [36, -6, 0], "Spine1": [24, -4, 0], "Neck": [20, 14, 0], "Head": [12, 8, 0],
    "LeftUpLeg": [-46, 0, 9], "LeftLeg": [64, 0, 0], "LeftFoot": [10, 0, 0],
    "RightUpLeg": [-10, 0, -9], "RightLeg": [60, 0, 0], "RightFoot": [-8, 0, 0]})
AIR = dict(G, **arms(40, 30, 40, 30, out=40), **{
    "Hips": [-52, -6, 0], "Spine": [-10, 0, 0], "Spine1": [-8, 0, 0], "Neck": [-14, 0, 0], "Head": [-10, 0, 0],
    "LeftUpLeg": [-58, 0, 10], "LeftLeg": [34, 0, 0], "LeftFoot": [20, 0, 0],
    "RightUpLeg": [-40, 0, -10], "RightLeg": [50, 0, 0], "RightFoot": [20, 0, 0]})
FLAT = dict(G, **arms(-8, 18, -8, 18, out=58), **{
    "Hips": [-88, 0, 0], "Spine": [2, 0, 0], "Spine1": [2, 0, 0], "Neck": [10, 0, 0], "Head": [8, 0, 0],
    "LeftUpLeg": [-10, 0, 14], "LeftLeg": [16, 0, 0], "LeftFoot": [30, 0, 0],
    "RightUpLeg": [-4, 0, -14], "RightLeg": [10, 0, 0], "RightFoot": [30, 0, 0]})
SIT = dict(G, **arms(-30, 20, 24, 70, out=20), **{
    "Hips": [-34, 0, 0], "Spine": [30, 0, 0], "Spine1": [18, 0, 0], "Neck": [10, 0, 0], "Head": [6, 0, 0],
    "LeftUpLeg": [-84, 0, 10], "LeftLeg": [104, 0, 0], "LeftFoot": [10, 0, 0],
    "RightUpLeg": [-70, 0, -12], "RightLeg": [96, 0, 0], "RightFoot": [10, 0, 0]})
CROUCH = dict(G, **arms(40, 80, 40, 80), **{
    "Hips": [22, -10, 0], "Spine": [24, -4, 0], "Spine1": [12, -2, 0], "Neck": [-6, 8, 0], "Head": [0, 4, 0],
    "LeftUpLeg": [-84, 0, 12], "LeftLeg": [112, 0, 0], "LeftFoot": [26, 0, 0],
    "RightUpLeg": [-66, 0, -12], "RightLeg": [108, 0, 0], "RightFoot": [26, 0, 0]})

def clip(keys, n):
    return [grounded(keyed(keys, k / (n - 1))) for k in range(n)]

out = {}
for name, keys, n in (
        ("hurt_hi", [(0.0, G), (0.2, HI), (0.5, blend(HI, G, 0.15)), (1.0, G)], 8),
        ("hurt_lo", [(0.0, G), (0.2, LO), (0.5, blend(LO, G, 0.15)), (1.0, G)], 8),
        ("down", [(0.0, G), (0.18, HI), (0.55, AIR), (0.85, FLAT), (1.0, FLAT)], 12),
        ("getup", [(0.0, FLAT), (0.35, SIT), (0.7, CROUCH), (1.0, G)], 12)):
    out["V_" + name], out["S_" + name] = (np.stack(x) for x in zip(*clip(keys, n)))
    v = out["V_" + name]
    print(name, v.shape, "its worst: top %.2f, back %.2f, fwd %.2f" % (v[n // 3, :, 2].max(), v[n // 3, :, 0].min(), v[n // 3, :, 0].max()))
np.savez_compressed(sys.argv[1], **out)
'''

OUT.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
r = subprocess.run([sys.executable, "-c", CHILD, str(OUT)], cwd=ARCHIVE, env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-3000:])
print(r.stdout.strip())
print(f"wrote {OUT}")

# ---- carried to the smaller bodies
full, react = np.load(ROOT / "assets" / "tnd" / "boxer.npz"), np.load(OUT)
names = sorted(k[2:] for k in react.files if k.startswith("V_"))
for clips in sorted(TIERS.glob("clips_*.npz")):
    t = np.load(clips)
    a, b = full["V_guard2"][0], t["V_guard2"][0]                    # the guard both have
    near = np.argmin(((b[:, None] - a[None]) ** 2).sum(-1), 1)
    gap = b - a[near]
    face = np.argmin(((b[t["F"]].mean(1)[:, None] - a[full["F"]].mean(1)[None]) ** 2).sum(-1), 1)
    err = float(np.sqrt((((full["V_walk2"][:, near] + gap) - t["V_walk2"]) ** 2).sum(-1)).mean())
    out = {}
    for n in names:
        out["V_" + n] = react["V_" + n][:, near] + gap[None]
        out["S_" + n] = react["S_" + n][:, face].astype(t["S_guard2"].dtype)
    dst = TIERS / clips.name.replace("clips_", "react_")
    np.savez_compressed(dst, **out)
    print(f"wrote {dst} ({len(b)} corners; the walk carried the same way is {err * 100:.1f} cm off)")
