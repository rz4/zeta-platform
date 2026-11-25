#!/usr/bin/env python3
# HOW A BODY TAKES IT (TND-PORT P97, layer 14). The player, the base kit done: "a layer of polish ... making the
# action more stylized to feel tactical, mature, and hyperviolent" -- and: "hyperviolent is not just gore, its about
# making the fighting correagraphy be hyperviolent".
#
# Until now every body that went down went down the same way -- thrown back, into the air, flat (tools/tnd_react.py's
# `down`) -- whether a haymaker put it there or one round did; and a hook landed as a jab does, the chin taken back.
# These are what the blow itself does, baked on the archive's own rig the way the reactions are, into their OWN
# files -- assets/tnd/falls.npz, and build/tiers/falls_N.npz for the smaller bodies -- so every other layer is built
# as it was:
#
#   fall_drop    12  a light blow or a round to the HEAD: the chin snapped back, the knees gone under it, sat back
#                    on its heels and over -- it goes down where it stood, like a thing switched off
#   fall_fold    12  to the BODY: folded over the blow, onto its knees, pitched onto its face
#   fall_cut     12  to the LEGS: the leg gone from under it, a knee and its hands, onto its face
#   getup_prone  12  up off its face: pushed up, crouched, its guard (the two that end face down rise by this)
#   hurt_hook    8   a HOOK landed: the head and shoulders turned hard away from it, a foot thrown out to hold it
#   hurt_hook_l  8   the same, turned the other way (the other hand's)
#
# P98, the rest of it:
#   shot_hi / _l  8  a ROUND in the head or the shoulder: that side punched back, the head thrown, a foot gone back
#   shot_lo / _l  8  a round in the body: the hip taken back on that side, curled round it
#                    (a side each: rounds landing one after another throw it one way, then the other)
#   jolt_back     6  struck while it lies on its back: the chest bucks off the floor, the limbs jump
#   jolt_prone    6  struck while it lies on its face: the hips kick up, the head comes off the floor
# and two of HIS, for a body on the floor before him (his own bank; layer 14 only):
#   gs_stomp      16 the jab's frames: the lead knee snatched up, the heel driven down into it on the jab's fourth
#   gs_stomp_r    19 the cross's frames: the rear leg's, on the cross's fifth
#
#   python3 tools/tnd_falls.py [path/to/archive/TND]

import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / "archive" / "TND")
OUT = ROOT / "assets" / "tnd" / "falls.npz"
TIERS = ROOT / "build" / "tiers"

# the reactions' own words (tools/tnd_react.py's child script, up to where it makes its clips)
_REACT = (ROOT / "tools" / "tnd_react.py").read_text().split("CHILD = r'''", 1)[1].split("\n'''", 1)[0]
_REACT = _REACT.split("out = {}", 1)[0]

MORE = r'''
def mirror(p_):
    q = {}
    for k_, v_ in p_.items():
        if k_.startswith("Left") or k_.startswith("Right"):
            o_ = ("Right" + k_[4:]) if k_.startswith("Left") else ("Left" + k_[5:])
            q[o_] = [v_[0], -v_[1], -v_[2]]
        else:
            q[k_] = [v_[0], -v_[1], -v_[2]]
    return q

# ---- to the head: switched off
SNAP = dict(G, **arms(-10, 30, -10, 30, out=12), **{
    "Hips": [-4, 0, 0], "Spine": [-10, 0, 0], "Spine1": [-8, 0, 0], "Neck": [-34, 0, 0], "Head": [-26, 0, 0]})
BUCKLE = dict(G, **arms(-4, 14, -4, 14, out=8), **{
    "Hips": [-8, 0, 0], "Spine": [-6, 0, 0], "Spine1": [-4, 0, 0], "Neck": [-30, 6, 0], "Head": [-24, 4, 0],
    "LeftUpLeg": [-62, 0, 10], "LeftLeg": [128, 0, 0], "LeftFoot": [26, 0, 0],
    "RightUpLeg": [-56, 0, -10], "RightLeg": [124, 0, 0], "RightFoot": [26, 0, 0]})
SEATBACK = dict(G, **arms(-20, 10, -20, 10, out=30), **{
    "Hips": [-48, 0, 0], "Spine": [-8, 0, 0], "Spine1": [-6, 0, 0], "Neck": [-20, 10, 0], "Head": [-16, 6, 0],
    "LeftUpLeg": [-70, 0, 14], "LeftLeg": [130, 0, 0], "LeftFoot": [30, 0, 0],
    "RightUpLeg": [-70, 0, -14], "RightLeg": [130, 0, 0], "RightFoot": [30, 0, 0]})
FLATK = dict(G, **arms(-8, 18, -8, 18, out=64), **{
    "Hips": [-88, 0, 0], "Spine": [2, 0, 0], "Spine1": [2, 0, 0], "Neck": [16, 20, 0], "Head": [10, 12, 0],
    "LeftUpLeg": [-52, 0, 18], "LeftLeg": [84, 0, 0], "LeftFoot": [30, 0, 0],
    "RightUpLeg": [-30, 0, -20], "RightLeg": [56, 0, 0], "RightFoot": [30, 0, 0]})

# ---- to the body: folded, its knees, its face
KNEEL = dict(G, **arms(20, 128, 20, 128), **{
    "Hips": [34, 0, 0], "Spine": [44, 0, 0], "Spine1": [28, 0, 0], "Neck": [26, 0, 0], "Head": [14, 0, 0],
    "LeftUpLeg": [-18, 0, 8], "LeftLeg": [118, 0, 0], "LeftFoot": [34, 0, 0],
    "RightUpLeg": [-12, 0, -8], "RightLeg": [112, 0, 0], "RightFoot": [34, 0, 0]})
PITCH = dict(G, **arms(60, 70, 60, 70, out=20), **{
    "Hips": [70, 0, 0], "Spine": [20, 0, 0], "Spine1": [10, 0, 0], "Neck": [-10, 0, 0], "Head": [-8, 0, 0],
    "LeftUpLeg": [-30, 0, 8], "LeftLeg": [70, 0, 0], "LeftFoot": [36, 0, 0],
    "RightUpLeg": [-30, 0, -8], "RightLeg": [70, 0, 0], "RightFoot": [36, 0, 0]})
PRONE = dict(G, **arms(150, 60, 110, 80, out=34), **{
    "Hips": [88, 0, 0], "Spine": [-4, 0, 0], "Spine1": [-2, 0, 0], "Neck": [-18, 34, 0], "Head": [-10, 20, 0],
    "LeftUpLeg": [4, 0, 12], "LeftLeg": [14, 0, 0], "LeftFoot": [50, 0, 0],
    "RightUpLeg": [-6, 0, -16], "RightLeg": [30, 0, 0], "RightFoot": [50, 0, 0]})

# ---- to the legs: the leg gone, a knee and its hands
TILT = dict(G, **arms(30, 60, -30, 40, out=40), **{
    "Hips": [10, 0, -14], "Spine": [8, 0, 8], "Spine1": [4, 0, 6], "Neck": [4, 0, 8], "Head": [2, 0, 4],
    "RightUpLeg": [-30, 0, -6], "RightLeg": [104, 0, 0], "RightFoot": [10, 0, 0],
    "LeftUpLeg": [-16, 0, 14], "LeftLeg": [34, 0, 0], "LeftFoot": [0, 0, 0]})
KNEE1 = dict(G, **arms(70, 30, 60, 40, out=24), **{
    "Hips": [44, 0, -18], "Spine": [24, 0, 6], "Spine1": [12, 0, 4], "Neck": [-14, 0, 0], "Head": [-8, 0, 0],
    "RightUpLeg": [-34, 0, -6], "RightLeg": [124, 0, 0], "RightFoot": [30, 0, 0],
    "LeftUpLeg": [-58, 0, 22], "LeftLeg": [80, 0, 0], "LeftFoot": [10, 0, 0]})

# ---- up off its face
PUSH = dict(G, **arms(84, 26, 84, 26, out=14), **{
    "Hips": [62, 0, 0], "Spine": [-8, 0, 0], "Spine1": [-6, 0, 0], "Neck": [-20, 0, 0], "Head": [-12, 0, 0],
    "LeftUpLeg": [-86, 0, 12], "LeftLeg": [104, 0, 0], "LeftFoot": [40, 0, 0],
    "RightUpLeg": [-86, 0, -12], "RightLeg": [104, 0, 0], "RightFoot": [40, 0, 0]})

# ---- a hook: turned away from it
SPIN = dict(G, **arms(-40, 30, 10, 70, out=44), **{
    "Hips": [-6, 44, 6], "Spine": [-8, 22, 8], "Spine1": [-6, 16, 6], "Neck": [-10, 38, 14], "Head": [-6, 26, 10],
    "LeftUpLeg": [-30, 0, 14], "LeftLeg": [30, 0, 0], "LeftFoot": [8, 0, 0],
    "RightUpLeg": [18, 0, -10], "RightLeg": [40, 0, 0], "RightFoot": [-10, 0, 0]})

GV = grounded(G)[0]
FEET = np.flatnonzero(GV[:, 2] < 0.10)
# ---- a round, standing: one side punched back
SHOT_HI = dict(G, **arms(-30, 40, 6, 70, out=26), **{
    "Hips": [-6, 14, 0], "Spine": [-12, 20, 0], "Spine1": [-10, 14, 0], "Neck": [-22, -10, 0], "Head": [-14, -8, 0],
    "RightUpLeg": [14, 0, -8], "RightLeg": [30, 0, 0], "RightFoot": [-8, 0, 0]})
SHOT_LO = dict(G, **arms(24, 110, 8, 90), **{
    "Hips": [14, -16, 0], "Spine": [26, -14, 0], "Spine1": [14, -8, 0], "Neck": [12, 0, 0], "Head": [8, 0, 0],
    "LeftUpLeg": [-34, 0, 8], "LeftLeg": [50, 0, 0], "RightUpLeg": [8, 0, -8], "RightLeg": [36, 0, 0]})
# ---- struck on the floor
BUCK_BACK = dict(FLAT, **arms(-30, 40, -30, 40, out=70), **{
    "Spine": [-22, 0, 0], "Spine1": [-14, 0, 0], "Neck": [-20, 0, 0], "Head": [-10, 0, 0],
    "LeftUpLeg": [-38, 0, 18], "LeftLeg": [50, 0, 0], "RightUpLeg": [-30, 0, -18], "RightLeg": [40, 0, 0]})
BUCK_PRONE = dict(PRONE, **{
    "Hips": [80, 0, 0], "Spine": [-18, 0, 0], "Spine1": [-12, 0, 0], "Neck": [-30, 34, 0], "Head": [-16, 20, 0],
    "LeftUpLeg": [-14, 0, 12], "LeftLeg": [50, 0, 0], "RightUpLeg": [-20, 0, -16], "RightLeg": [60, 0, 0]})
# ---- his: the heel driven down into what lies before him
LIFT_L = dict(G, **arms(-20, 60, 30, 80, out=24), **{
    "Hips": [-10, 0, 0], "Spine": [6, 0, 0], "Spine1": [4, 0, 0], "Neck": [14, 0, 0], "Head": [10, 0, 0],
    "LeftUpLeg": [-96, 0, 6], "LeftLeg": [118, 0, 0], "LeftFoot": [-10, 0, 0],
    "RightUpLeg": [-6, 0, -8], "RightLeg": [14, 0, 0], "RightFoot": [0, 0, 0]})
DRIVE_L = dict(G, **arms(40, 50, -30, 70, out=30), **{
    "Hips": [16, 0, 0], "Spine": [14, 0, 0], "Spine1": [8, 0, 0], "Neck": [18, 0, 0], "Head": [12, 0, 0],
    "LeftUpLeg": [-42, 0, 6], "LeftLeg": [10, 0, 0], "LeftFoot": [-24, 0, 0],
    "RightUpLeg": [-30, 0, -8], "RightLeg": [60, 0, 0], "RightFoot": [14, 0, 0]})
LIFT_R = dict(G, **arms(30, 80, -20, 60, out=24), **{
    "Hips": [-10, 0, 0], "Spine": [6, 0, 0], "Spine1": [4, 0, 0], "Neck": [14, 0, 0], "Head": [10, 0, 0],
    "RightUpLeg": [-96, 0, -6], "RightLeg": [118, 0, 0], "RightFoot": [-10, 0, 0],
    "LeftUpLeg": [-6, 0, 8], "LeftLeg": [14, 0, 0], "LeftFoot": [0, 0, 0]})
DRIVE_R = dict(G, **arms(-30, 70, 40, 50, out=30), **{
    "Hips": [16, 0, 0], "Spine": [14, 0, 0], "Spine1": [8, 0, 0], "Neck": [18, 0, 0], "Head": [12, 0, 0],
    "RightUpLeg": [-42, 0, -6], "RightLeg": [10, 0, 0], "RightFoot": [-24, 0, 0],
    "LeftUpLeg": [-30, 0, 8], "LeftLeg": [60, 0, 0], "LeftFoot": [14, 0, 0]})

def hit_at(pre, peak, hold, n, at):
    """n poses of a blow whose worst is ON pose `at` (the move's own first live frame), held two more, and back"""
    u = at / (n - 1)
    return [(0.0, G), (0.55 * u, pre), (u, peak), (u + 2.0 / (n - 1), hold), (1.0, G)]

PLANTED = ("fall_drop", "fall_fold", "fall_cut", "getup_prone", "jolt_prone")
GV = grounded(G)[0]
FEET = np.flatnonzero(GV[:, 2] < 0.10)
out = {}
for name, keys, n in (
        ("shot_hi", [(0.0, G), (0.2, SHOT_HI), (0.5, blend(SHOT_HI, G, 0.15)), (1.0, G)], 8),
        ("shot_hi_l", [(0.0, G), (0.2, mirror(SHOT_HI)), (0.5, blend(mirror(SHOT_HI), G, 0.15)), (1.0, G)], 8),
        ("shot_lo", [(0.0, G), (0.2, SHOT_LO), (0.5, blend(SHOT_LO, G, 0.15)), (1.0, G)], 8),
        ("shot_lo_l", [(0.0, G), (0.2, mirror(SHOT_LO)), (0.5, blend(mirror(SHOT_LO), G, 0.15)), (1.0, G)], 8),
        ("jolt_back", [(0.0, FLAT), (0.3, BUCK_BACK), (1.0, FLAT)], 6),
        ("jolt_prone", [(0.0, PRONE), (0.3, BUCK_PRONE), (1.0, PRONE)], 6),
        ("gs_stomp", hit_at(LIFT_L, DRIVE_L, DRIVE_L, 16, 4), 16),
        ("gs_stomp_r", hit_at(LIFT_R, DRIVE_R, DRIVE_R, 19, 5), 19),
        ("fall_drop", [(0.0, G), (0.10, SNAP), (0.46, BUCKLE), (0.72, SEATBACK), (0.92, FLATK), (1.0, blend(FLATK, FLAT, 0.45))], 12),
        ("fall_fold", [(0.0, G), (0.14, LO), (0.42, KNEEL), (0.70, PITCH), (0.90, PRONE), (1.0, PRONE)], 12),
        ("fall_cut", [(0.0, G), (0.16, TILT), (0.48, KNEE1), (0.78, blend(KNEE1, PRONE, 0.6)), (1.0, PRONE)], 12),
        ("getup_prone", [(0.0, PRONE), (0.36, PUSH), (0.7, CROUCH), (1.0, G)], 12),
        ("hurt_hook", [(0.0, G), (0.2, SPIN), (0.5, blend(SPIN, G, 0.15)), (1.0, G)], 8),
        ("hurt_hook_l", [(0.0, G), (0.2, mirror(SPIN)), (0.5, blend(mirror(SPIN), G, 0.15)), (1.0, G)], 8)):
    out["V_" + name], out["S_" + name] = (np.stack(x) for x in zip(*clip(keys, n)))
    v = out["V_" + name]
    # ITS FEET STAY WHERE IT STOOD, by half: the rig turns a body about its hips, so one pitched onto its face threw
    # its legs a unit out behind it -- it seemed to slide away from the blow. Each frame is moved by half of how far
    # its feet have gone from where the guard has them (all of it would lay its head at his feet).
    if name in PLANTED:
        v[:, :, 0] -= 0.5 * (v[:, FEET, 0].mean(1) - GV[FEET, 0].mean())[:, None]
    print(name, v.shape, "its last: top %.2f, back %.2f, fwd %.2f, left %.2f..%.2f" % (v[-1, :, 2].max(), v[-1, :, 0].min(), v[-1, :, 0].max(), v[-1, :, 1].min(), v[-1, :, 1].max()))
np.savez_compressed(sys.argv[1], **out)
'''

OUT.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
r = subprocess.run([sys.executable, "-c", _REACT + MORE, str(OUT)], cwd=ARCHIVE, env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-3000:])
print(r.stdout.strip())
print(f"wrote {OUT}")

# ---- carried to the smaller bodies, as the reactions are (tools/tnd_react.py)
full, falls = np.load(ROOT / "assets" / "tnd" / "boxer.npz"), np.load(OUT)
names = sorted(k[2:] for k in falls.files if k.startswith("V_"))
for clips in sorted(TIERS.glob("clips_*.npz")):
    t = np.load(clips)
    a, b = full["V_guard2"][0], t["V_guard2"][0]                    # the guard both have
    near = np.argmin(((b[:, None] - a[None]) ** 2).sum(-1), 1)
    gap = b - a[near]
    face = np.argmin(((b[t["F"]].mean(1)[:, None] - a[full["F"]].mean(1)[None]) ** 2).sum(-1), 1)
    out = {}
    for n in names:
        out["V_" + n] = falls["V_" + n][:, near] + gap[None]
        out["S_" + n] = falls["S_" + n][:, face].astype(t["S_guard2"].dtype)
    dst = TIERS / clips.name.replace("clips_", "falls_")
    np.savez_compressed(dst, **out)
    print(f"wrote {dst} ({len(b)} corners)")
