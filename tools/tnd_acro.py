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

# ---- THE RUN'S AIR, ITS LANDING AND ITS ROLL (TND-PORT P50; the player: "the running should also have an
# animation while you are falling. just make the whole running feel better like a true parkourist"). The run
# played its stride in the air -- he sprinted on nothing. A traceur's jump is three shapes by how fast he is
# rising or falling: the DRIVE off the ground (the lead knee up, the rear leg long behind, the arms opposite),
# the STRIDE across the gap (the rear heel up to the seat), and the GATHER for the landing (both feet brought
# forward under him, knees bent to take it, the arms forward and up for balance). Then the landing ABSORBED --
# deep in the knees, the hands forward -- rising back into the run; and after a flip, a ROLL over the shoulder
# that keeps his speed, the tuck taken low so the ball runs along the floor.
RUN = bm._run_pose_dict()

def arms(r_swing, r_elbow, l_swing, l_elbow):
    """the sprinter's convention (tools/tnd_extract.py _run2): a swing forward is positive, the elbow bent forward"""
    return {"RightArm": [0, r_swing, 90.0], "RightForeArm": [0, r_elbow, 0],
            "LeftArm": [0, -l_swing, -90.0], "LeftForeArm": [0, -l_elbow, 0]}

LEAP_KEYS = [
    (0.0, dict(RUN, **arms(-48, 78, 58, 92), **{"Spine": [20, -4, 0],
        "RightUpLeg": [-96, 0, -9], "RightLeg": [96, 0, 0], "RightFoot": [8, 0, 0],
        "LeftUpLeg": [34, 0, 9], "LeftLeg": [18, 0, 0], "LeftFoot": [34, 0, 0]})),
    (0.45, dict(RUN, **arms(-18, 70, 44, 80), **{"Spine": [16, -4, 0],
        "RightUpLeg": [-62, 0, -9], "RightLeg": [42, 0, 0], "RightFoot": [0, 0, 0],
        "LeftUpLeg": [26, 0, 9], "LeftLeg": [104, 0, 0], "LeftFoot": [28, 0, 0]})),
    (1.0, dict(RUN, **arms(62, 36, 62, 36), **{"Spine": [20, -4, 0], "Neck": [-4, 6, 0],
        "RightUpLeg": [-56, 0, -12], "RightLeg": [74, 0, 0], "RightFoot": [-6, 0, 0],
        "LeftUpLeg": [-46, 0, 12], "LeftLeg": [82, 0, 0], "LeftFoot": [-6, 0, 0]})),
]
ABSORB = dict(RUN, **arms(56, 44, 56, 44), **{"Hips": [22, -10, 0], "Spine": [30, -4, 0], "Spine1": [18, -3, 0],
    "Neck": [-12, 6, 0], "RightUpLeg": [-86, 0, -12], "RightLeg": [118, 0, 0], "RightFoot": [30, 0, 0],
    "LeftUpLeg": [-70, 0, 12], "LeftLeg": [112, 0, 0], "LeftFoot": [30, 0, 0]})

def blend(a_, b_, u):
    return {k: [a_.get(k, [0, 0, 0])[i] * (1 - u) + b_.get(k, [0, 0, 0])[i] * u for i in range(3)] for k in set(a_) | set(b_)}

def keyed(keys, u):
    for (u0, a_), (u1, b_) in zip(keys, keys[1:]):
        if u0 <= u <= u1:
            return blend(a_, b_, bm._smoothstep((u - u0) / (u1 - u0)))
    return dict(keys[-1][1])

def grounded(pose_, drop=None):
    """the pose with its lowest point on the floor (the root lowered until it is)"""
    if drop is None:
        drop = 0.0
        for _ in range(8):
            drop += frozen(bm._pose_and_skin(pose_, np.array([0.0, -drop, 0.0]), None))[0][:, 2].min()
    return frozen(bm._pose_and_skin(pose_, np.array([0.0, -drop, 0.0]), None)), drop     # (the root is the rig's: y up)

# P51 (the player: "the parkour feels better but can be improved so animations feel like smooth transitions and
# more realistic runs"). THE STRIDE, A TRACEUR'S: sixteen poses, the thigh driven well forward (65 degrees) and
# back (30), the heel folded to the seat in the recovery, a light knee at contact that catches the weight just
# after, the arms pumping opposite with the elbow closing as the hand comes up, the pelvis turning with the
# stride and the shoulders against it, and the body highest between contacts, lowest just after each. Every
# clip that hands him to the stride ends in ITS first pose, and the cart starts the stride there.
def knee_at(ph):
    keys = [(0.0, 95), (0.12, 55), (0.25, 16), (0.36, 38), (0.55, 26), (0.72, 22), (0.82, 78), (0.92, 120), (1.0, 95)]
    ph = ph % 1.0
    for (a0, k0), (a1, k1) in zip(keys, keys[1:]):
        if a0 <= ph <= a1:
            return k0 + (k1 - k0) * bm._smoothstep((ph - a0) / (a1 - a0))

def stride(ph):
    p_ = dict(RUN)
    for side, m, q in (("Right", 1.0, ph), ("Left", -1.0, ph + 0.5)):
        sn = np.sin(2 * np.pi * q)
        p_[side + "UpLeg"] = [-17.5 - 47.5 * sn, 0, -9.0 * m]
        p_[side + "Leg"] = [knee_at(q), 0, 0]
        p_[side + "Foot"] = [10 + 18 * max(0.0, np.sin(2 * np.pi * (q - 0.5))), 0, 0]
        p_.update({k_: v_ for k_, v_ in arms(-42 * sn, 88 - 18 * sn, 0, 0).items() if k_.startswith(side)} if side == "Right"
                  else {k_: v_ for k_, v_ in arms(0, 0, -42 * sn, 88 - 18 * sn).items() if k_.startswith(side)})
    tw = np.sin(2 * np.pi * ph)
    p_["Hips"] = [RUN["Hips"][0], RUN["Hips"][1] + 7 * tw, RUN["Hips"][2]]
    p_["Spine1"] = [RUN["Spine1"][0], RUN["Spine1"][1] - 7 * tw, RUN["Spine1"][2]]
    return p_

def run_frame(ph):
    """the lower foot on the floor: the body rides up and down on the stride's own legs (lowest in the loading,
    highest as the stance leg straightens under him)"""
    return grounded(stride(ph))[0]

def mirror(p_):
    """the same shape, the other side leading"""
    q = {}
    for k_, v_ in p_.items():
        if k_.startswith("Left") or k_.startswith("Right"):
            o_ = ("Right" + k_[4:]) if k_.startswith("Left") else ("Left" + k_[5:])
            q[o_] = [v_[0], -v_[1], -v_[2]]
        else:
            q[k_] = [v_[0], -v_[1], -v_[2]]
    return q

out = {}
out["V_acro_run"], out["S_acro_run"] = (np.stack(x) for x in zip(*[run_frame(f / 16) for f in range(16)]))
LEAP_N = 13
for name, mk in (("acro_leap", lambda p_: p_), ("acro_leap_l", mirror)):
    out["V_" + name], out["S_" + name] = (np.stack(x) for x in zip(*[frozen(bm._pose_and_skin(mk(keyed(LEAP_KEYS, k / (LEAP_N - 1))), np.zeros(3), None))
                                                                      for k in range(LEAP_N)]))
# THE LONG JUMP (TND-PORT P52; the player: "a held jump release should be that distance long jump, olympic
# style"): the HANG -- off the board the free knee drives and the arms swing up; in the flight the arms go
# overhead and the legs hang back under him, the back arched; then the JACKKNIFE -- arms sweeping forward and
# down, the legs brought up and straight out in front, the trunk folded over them to reach the sand. Thirteen
# shapes by the fraction of the flight.
LONG_KEYS = [
    (0.0, dict(RUN, **arms(-30, 70, 70, 60), **{"Spine": [14, -4, 0],
        "RightUpLeg": [-88, 0, -9], "RightLeg": [90, 0, 0], "RightFoot": [8, 0, 0],
        "LeftUpLeg": [26, 0, 9], "LeftLeg": [16, 0, 0], "LeftFoot": [30, 0, 0]})),
    (0.35, dict(RUN, **arms(120, 20, 120, 20), **{"Hips": [0, -10, 0], "Spine": [-8, -4, 0], "Spine1": [-6, -3, 0], "Neck": [4, 6, 0],
        "RightUpLeg": [14, 0, -9], "RightLeg": [62, 0, 0], "RightFoot": [24, 0, 0],
        "LeftUpLeg": [18, 0, 9], "LeftLeg": [66, 0, 0], "LeftFoot": [24, 0, 0]})),
    (0.7, dict(RUN, **arms(80, 20, 80, 20), **{"Hips": [6, -10, 0], "Spine": [20, -4, 0], "Spine1": [12, -3, 0],
        "RightUpLeg": [-62, 0, -9], "RightLeg": [34, 0, 0], "RightFoot": [-4, 0, 0],
        "LeftUpLeg": [-60, 0, 9], "LeftLeg": [36, 0, 0], "LeftFoot": [-4, 0, 0]})),
    (1.0, dict(RUN, **arms(34, 14, 34, 14), **{"Hips": [10, -10, 0], "Spine": [36, -4, 0], "Spine1": [22, -3, 0], "Neck": [-14, 6, 0],
        "RightUpLeg": [-88, 0, -9], "RightLeg": [8, 0, 0], "RightFoot": [-12, 0, 0],
        "LeftUpLeg": [-88, 0, 9], "LeftLeg": [8, 0, 0], "LeftFoot": [-12, 0, 0]})),
]
out["V_acro_long"], out["S_acro_long"] = (np.stack(x) for x in zip(*[frozen(bm._pose_and_skin(keyed(LONG_KEYS, k / (LEAP_N - 1)), np.zeros(3), None))
                                                                  for k in range(LEAP_N)]))
# the landing: from the gather into the knees (three frames), and up into the stride's first pose (five)
GATHER, RUN0 = LEAP_KEYS[-1][1], stride(0.0)
land = [grounded(blend(GATHER, ABSORB, bm._smoothstep(k / 2)))[0] for k in range(3)] + \
       [grounded(blend(ABSORB, RUN0, bm._smoothstep(k / 5)))[0] for k in range(1, 6)]
out["V_acro_land"], out["S_acro_land"] = (np.stack(x) for x in zip(*land))
# the roll: from the knees into the tuck, over, and up into the stride's first pose -- its lowest point on the floor
# throughout; the cart turns it about the ball's middle
full = pose("acro_tuck", 0.5)[0]
mid = full.mean(0)
r = np.sqrt(((full - mid) ** 2).sum(1)).max()
TUCK = SHAPES["acro_tuck"]
roll = []
for f in range(16):
    t = f / 15
    if t < 0.25:
        p_, w = blend(ABSORB, TUCK, bm._smoothstep(t / 0.25)), bm._smoothstep(t / 0.25)
    elif t > 0.75:
        p_, w = blend(TUCK, RUN0, bm._smoothstep((t - 0.75) / 0.25)), bm._smoothstep((1.0 - t) / 0.25)
    else:
        p_, w = dict(TUCK), 1.0
    def repose(Vt, skel_, angles, w=w):
        body = anat.pose(angles)
        for who in ("lead", "rear"):
            arm, leg = anat.arm(who), anat.leg(who)
            shin = leg.shin_foot & ~leg.foot
            bm._reach_arm(Vt, arm, body, Vt[shin].mean(0) + 0.06 * arm.outward, arm.outward, w)
    # (P55: posed where it stands, THEN brought down to the floor -- lowered through the root, the reach that puts
    # the hands on the shins aimed from shoulders that were no longer there, and an arm stretched 0.4 across him)
    V_, S_ = frozen(bm._pose_and_skin(p_, np.zeros(3), None, repose))
    V_ = V_.copy()
    V_[:, 2] -= V_[:, 2].min()
    roll.append((V_, S_))
out["V_acro_roll"], out["S_acro_roll"] = (np.stack(x) for x in zip(*roll))
out["roll_centre"] = np.array([r])                 # the ball's middle, over the floor, at the full tuck
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
