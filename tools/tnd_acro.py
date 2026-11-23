#!/usr/bin/env python3
# THE ACROBATICS, RE-POSED (TND-PORT P49). The player, of the lab's flips:
# "the legs on the side flip should be tucked too, work on the arcrobatics
# poses". The archive's flips are three SHAPES the renderer spins: a tuck
# (forward), a layout arch (back), and a straddle star with the legs thrown
# wide (the cartwheel, both sides). This bakes three more on the archive's
# own rig, the same way tools/tnd_extract.py bakes the rest, and writes them
# to their OWN file -- assets/tnd/acro.npz -- so boxer.npz, and every layer
# built from it, stays exactly as it is.
#
#   acro_tuck   the forward tuck, the knees to the chest and both hands on
#               the shins (the archive's left the hands at the guard)
#   acro_back   the back tuck: the same knees, the chest open and the head
#               back, the hands on the shins
#   acro_side   the side flip TUCKED: knees up and a hand apart, the trunk
#               curled less than the front tuck, the hands on the shins
#
# Each eases in from the guard over its first fifth, holds, and eases out
# over its last fifth -- the archive's flip_mesh rule -- and the fists are
# put on the shins by the archive's own two-bone reach.
#
#   python3 tools/tnd_acro.py [path/to/archive/TND]

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / "archive" / "TND")
OUT = ROOT / "assets" / "tnd" / "acro.npz"

CHILD = r'''
import sys, numpy as np
sys.path.insert(0, "src")
from zeta.virtual import boxer_mesh as bm
skel = bm._load_skeleton()
F = np.asarray(skel["F"], np.int64)
nv = int(F.max()) + 1
anat = bm.anatomy(skel)

def frozen(res):
    faces, cols = res
    V = np.zeros((nv, 3))
    V[F.reshape(-1)] = np.asarray(faces).reshape(-1, 3)
    return V, np.asarray(cols)

a = bm._ARM_SOLUTION
ARMS = {"LeftArm": [0, a[0], a[1]], "LeftForeArm": [0, a[2], a[3]], "RightArm": [0, a[4], a[5]], "RightForeArm": [0, a[6], a[7]]}
TUCK_LEGS = {"LeftUpLeg": [-112, 0, 6], "LeftLeg": [138, 0, 0], "LeftFoot": [34, 0, 0],
             "RightUpLeg": [-112, 0, -6], "RightLeg": [138, 0, 0], "RightFoot": [34, 0, 0]}
SHAPES = {
    "acro_tuck": dict(TUCK_LEGS, **ARMS, **{"Hips": [0, -18, 0], "Spine": [48, -6, 0], "Spine1": [32, -4, 0],
                                             "Neck": [36, 14, 0], "Head": [30, 8, 0]}),
    "acro_back": dict(TUCK_LEGS, **ARMS, **{"Hips": [0, -18, 0], "Spine": [18, -6, 0], "Spine1": [8, -4, 0],
                                             "Neck": [-24, 14, 0], "Head": [-20, 8, 0]}),
    # (the side: the cart rolls it either way, so it is the same both sides -- the trunk curled less than the
    # front tuck, so the roll's axis runs through a body that is still upright enough to read, the knees a
    # hand apart)
    "acro_side": dict(ARMS, **{"Hips": [0, -18, 0], "Spine": [30, -6, 0], "Spine1": [20, -4, 0],
                               "Neck": [22, 14, 0], "Head": [18, 8, 0],
                               "LeftUpLeg": [-106, 0, 11], "LeftLeg": [140, 0, 0], "LeftFoot": [34, 0, 0],
                               "RightUpLeg": [-106, 0, -11], "RightLeg": [140, 0, 0], "RightFoot": [34, 0, 0]}),
}
LENGTH = {"acro_tuck": 20, "acro_back": 20, "acro_side": 24}
RAMP = 0.2

def weight(t):
    if t < RAMP:
        return bm._smoothstep(t / RAMP)
    if t > 1.0 - RAMP:
        return bm._smoothstep((1.0 - t) / RAMP)
    return 1.0

def pose(kind, t):
    w = weight(t)
    guard, target = bm._guard_pose_dict(), SHAPES[kind]
    p = {k: [guard[k][i] + (target.get(k, guard[k])[i] - guard[k][i]) * w for i in range(3)] for k in guard}
    def repose(Vt, skel_, angles):
        if w <= 0.0:
            return
        body = anat.pose(angles)
        for who in ("lead", "rear"):
            arm, leg = anat.arm(who), anat.leg(who)
            shin = leg.shin_foot & ~leg.foot
            at = Vt[shin].mean(0) + 0.06 * arm.outward          # (the outside of the shin: the hand wraps it)
            bm._reach_arm(Vt, arm, body, at, arm.outward, w)
    return frozen(bm._pose_and_skin(p, np.zeros(3), None, repose))

out = {}
for kind, n in LENGTH.items():
    frames = [pose(kind, f / (n - 1)) for f in range(n)]
    out["V_" + kind] = np.stack([v for v, _ in frames])
    out["S_" + kind] = np.stack([c for _, c in frames])
np.savez_compressed(sys.argv[1], **out)
print({k: v.shape for k, v in out.items()})
'''

OUT.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
r = subprocess.run([sys.executable, "-c", CHILD, str(OUT)], cwd=ARCHIVE, env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-3000:])
print(r.stdout.strip())
print(f"wrote {OUT}")
