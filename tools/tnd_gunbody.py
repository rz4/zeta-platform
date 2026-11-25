#!/usr/bin/env python3
# ONE BODY WITH THE GUN (TND-PORT P91). The player: "work heavily on the look, make sure it all looks like a single
# mesh, with poses and transitions that all make sense and look tactical and stylish" -- and, of the run with the gun
# out: "the running legs should be the same, and the gun holding from when strationary torso". And his rule: "the
# orginal mesh of the player must stay intact".
#
# The cart drew that as two halves in two poses -- the gun's standing chest set on the stride's hips -- and no way of
# PUTTING a half closes a waist the two poses do not share. So it is baked here as what it is: ONE skinned body on the
# archive's own rig, the same way tools/tnd_acro.py bakes the run it stands on.
#
#   the legs      the park's own clips, bone for bone: the stride (tnd_acro.py pstride), the leap on either leg
#                 (PLEAP_KEYS), the landing (PGATHER -> PABSORB -> the stride's first)
#   the trunk     a shooter's over them: half the clip's own lean, the head level
#   the arms      the archive's own two-handed hold (boxer_mesh._repose_aim's reach, its own targets), at four heights
#                 of the draw -- low ready, coming up, nearly out, locked out. The targets are places before HIM, not
#                 places on his chest: the gun stays where it is while the legs run under it.
#
# Written to their own file, assets/tnd/gunbody.npz; nothing else is touched.
#
#   python3 tools/tnd_gunbody.py [path/to/archive/TND]

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / "archive" / "TND")
OUT = ROOT / "assets" / "tnd" / "gunbody.npz"

# the park's own definitions, as tnd_acro.py has them (its child script, up to where it writes its file)
_ACRO = (ROOT / "tools" / "tnd_acro.py").read_text().split("CHILD = r'''", 1)[1].split("\n'''", 1)[0]
_ACRO = _ACRO.rsplit("np.savez_compressed(sys.argv[1], **out)", 1)[0]

MORE = r'''
cfg = bm._SHAPE_CFG["aim"]
DOWN = np.array((0.0, 0.0, -1.0))
RAISE = (0.0, 0.45, 0.85, 1.0)                    # low ready, coming up, nearly out, locked out
# (locked out, MOVING, is a hand's breadth short of the standing lock-out: over a stride his shoulders are further
# back than a planted man's, and a reach they cannot make puts the gun wherever the arm runs out -- a tenth of a
# unit about, stride to stride. Elbows a little bent, the gun where it is told to be.)
OUT_AT = {"gun_aim": np.asarray((0.46, -0.03, 1.20)), "sup_aim": np.asarray((0.40, 0.04, 1.165))}

def hold(r, up=0.0):
    """both hands on the piece, at raise r of the draw (the archive's _repose_aim, its weight whole); `up`: the body
    is to be let down by this after, so the hold is taken that much high"""
    def repose(Vt, skel_, angles):
        body = anat.pose(angles)
        for rk, ak, who in (("gun_ready", "gun_aim", "rear"), ("sup_ready", "sup_aim", "lead")):
            arm = anat.arm(who)
            bm._reach_arm(Vt, arm, body, cfg[rk] + (OUT_AT[ak] - cfg[rk]) * r + np.array((0.0, 0.0, up)), arm.outward * 0.35 + DOWN, 1.0)
    return repose

def shooter(p_):
    """the pose's own hips and legs under a shooter's trunk: half its lean, the head level over the sights"""
    q = dict(p_)
    for b_ in ("Spine", "Spine1"):
        a_ = list(p_.get(b_, [0, 0, 0]))
        q[b_] = [0.5 * a_[0], a_[1], a_[2]]
    nk, hd = list(p_.get("Neck", [0, 0, 0])), list(p_.get("Head", [0, 0, 0]))
    q["Neck"], q["Head"] = [-3.0, nk[1], nk[2]], [-3.0, hd[1], hd[2]]
    return q

def drop_of(p_):
    return grounded(p_)[1]

gb, hands = {}, {}
_g4 = frozen(bm.move_mesh("gun", 4 / 17.0))[0]
HID = np.argsort(_g4[:, 0])[-12:]                 # (the cart's own rule for his hand: the twelve farthest forward, gun up)

def keep(name, frames):
    gb["V_" + name], gb["S_" + name] = (np.stack(x) for x in zip(*frames))

# the stride: grounded as the park's own is (by the legs: the arms are nowhere near the floor)
fr = []
for r in RAISE:
    for f in range(16):
        p_ = pstride(f / 16)
        fr.append(frozen(bm._pose_and_skin(shooter(p_), np.array([0.0, -drop_of(p_), 0.0]), None, hold(r))))
keep("gb_run", fr)
# the leap, either leg: from the floor over its first three, as the park's
for name, mk in (("gb_leap", lambda p_: p_), ("gb_leap_l", mirror)):
    fr = []
    for r in RAISE:
        for k in range(LEAP_N):
            p_ = mk(keyed(PLEAP_KEYS, k / (LEAP_N - 1)))
            down = 0.0                            # (...let down as the park's is, the hold taken that much high: the
            if k < 3:                             # legs are the park's to the last place, and the gun stays put)
                down = frozen(bm._pose_and_skin(p_, np.zeros(3), None))[0][:, 2].min() * (1.0 - bm._smoothstep(k / 3))
            V_, S_ = frozen(bm._pose_and_skin(shooter(p_), np.zeros(3), None, hold(r, down)))
            V_ = V_.copy()
            V_[:, 2] -= down
            fr.append((V_, S_))
    keep(name, fr)
# the landing
lp = [blend(PGATHER, PABSORB, bm._smoothstep(k / 2)) for k in range(3)] + [blend(PABSORB, PRUN0, bm._smoothstep(k / 5)) for k in range(1, 6)]
fr = []
for r in RAISE:
    for p_ in lp:
        fr.append(frozen(bm._pose_and_skin(shooter(p_), np.array([0.0, -drop_of(p_), 0.0]), None, hold(r))))
keep("gb_land", fr)

# what was made: the legs against the park's own (the same bones: the feet must be where they were), and his hand
legs = np.asarray(anat.leg("lead").shin_foot | anat.leg("rear").shin_foot)
for name, src, n in (("gb_run", "park_run", 16), ("gb_leap", "park_leap", LEAP_N), ("gb_leap_l", "park_leap_l", LEAP_N), ("gb_land", "park_land", 8)):
    V = gb["V_" + name].reshape(len(RAISE), n, -1, 3)
    d_ = np.abs(V[:, :, legs] - out["V_" + src][None][:, :, legs]).max()
    h_ = V[:, :, HID].mean(2)                     # (state, frame, 3)
    print(name, V.shape, "shins and feet off the park's own by at most %.4f" % d_,
          "| his hand, by height of the draw:", [(np.round(h_[s].mean(0), 2).tolist(), "+-%.3f" % np.abs(h_[s] - h_[s].mean(0)).max()) for s in range(len(RAISE))])
gb["RAISE"] = np.array(RAISE)
np.savez_compressed(sys.argv[1], **gb)
print({k: v.shape for k, v in gb.items()})
'''

OUT.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
r = subprocess.run([sys.executable, "-c", _ACRO + MORE, str(OUT)], cwd=ARCHIVE, env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-3000:])
print("\n".join(ln for ln in r.stdout.strip().split("\n") if ln.startswith(("gb_", "{"))))
print(f"wrote {OUT}")
