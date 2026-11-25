#!/usr/bin/env python3
# THE YARD'S OWN MOVES, POSED (TND-PORT P92). The player: "work heavily on the look ... poses and transitions that all
# make sense and look tactical and stylish". Four things the yard does had no pose of their own and borrowed another
# move's:
#
#   mv_start    INTO THE RUN. It was the landing's crouch played from its deepest (P76): standing, then squatting, in
#               one frame. From his guard he drops his weight forward and drives -- six poses to the stride's first.
#   mv_stop     OUT OF IT. It was the same landing run backwards. He plants the lead foot, sits back against his pace,
#   mv_stop_l   and comes up into his guard -- eight poses, from the stride's first pose or (_l) its other half.
#   mv_spring   THE HANDSPRING'S SECOND HALF. It was the forward tuck easing out, unturned. Off his hands: inverted,
#               arms long, the legs coming over, the back arched, the feet under him -- fourteen poses that turn him
#               themselves (the hips' own pitch, 165 to 366 degrees), each sat on its lowest point: his hands, then
#               his feet.
#   mv_lance    THE LANCE. It was the slide's body, lying down, falling. A straight line feet first, toes pointed,
#               the arms long behind his head -- four poses: into it, and held.
#
# Baked on the archive's own rig from the same pose words tools/tnd_acro.py uses, to their own file,
# assets/tnd/moves.npz.
#
#   python3 tools/tnd_moves.py [path/to/archive/TND]

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / "archive" / "TND")
OUT = ROOT / "assets" / "tnd" / "moves.npz"

_ACRO = (ROOT / "tools" / "tnd_acro.py").read_text().split("CHILD = r'''", 1)[1].split("\n'''", 1)[0]
_ACRO = _ACRO.rsplit("np.savez_compressed(sys.argv[1], **out)", 1)[0]

MORE = r'''
mv = {}
GUARD = bm._guard_pose_dict()

def keep(name, poses, ground=True):
    fr = [grounded(p_)[0] if ground else frozen(bm._pose_and_skin(p_, np.zeros(3), None)) for p_ in poses]
    mv["V_" + name], mv["S_" + name] = (np.stack(x) for x in zip(*fr))

# ---- into the run: the guard, the weight dropped forward over the lead leg, the stride's first
DRIVE = dict(blend(GUARD, PABSORB, 0.55), **{"Hips": [20, -8, 0], "Spine": [20, -3, 0], "Spine1": [10, -2, 0], "Neck": [-10, 4, 0]},
             **arms(-30, 88, 40, 92))
keep("mv_start", [keyed([(0.0, GUARD), (0.42, DRIVE), (1.0, PRUN0)], (k + 1) / 7) for k in range(6)])

# ---- out of it: the lead foot planted ahead, sat back against his pace, up into the guard
BRAKE = dict(PRUN, **arms(26, 84, 26, 84), **{"Hips": [-4, -8, 0], "Spine": [2, -3, 0], "Spine1": [0, -2, 0], "Neck": [4, 4, 0],
    "RightUpLeg": [-58, 0, -10], "RightLeg": [46, 0, 0], "RightFoot": [-8, 0, 0],
    "LeftUpLeg": [-6, 0, 10], "LeftLeg": [78, 0, 0], "LeftFoot": [26, 0, 0]})
keep("mv_stop", [keyed([(0.0, pstride(0.0)), (0.38, BRAKE), (1.0, GUARD)], (k + 1) / 9) for k in range(8)])
keep("mv_stop_l", [keyed([(0.0, pstride(0.5)), (0.38, mirror(BRAKE)), (1.0, GUARD)], (k + 1) / 9) for k in range(8)])

# ---- the handspring, from his hands: the hips' own pitch turns him (the dive's is 80: flat; 180 is on his hands)
def over(pitch, spine, swing, elbow, thigh, knee, foot, neck, split=0.0):
    return dict(PRUN, **arms(swing, elbow, swing, elbow), **{"Hips": [pitch, 0, 0], "Spine": [spine, 0, 0], "Spine1": [0.6 * spine, 0, 0],
        "Neck": [neck, 0, 0], "Head": [0.5 * neck, 0, 0],
        "RightUpLeg": [thigh - split, 0, -6], "RightLeg": [knee, 0, 0], "RightFoot": [foot, 0, 0],
        "LeftUpLeg": [thigh + split, 0, 6], "LeftLeg": [knee, 0, 0], "LeftFoot": [foot, 0, 0]})
SPRING = [
    (0.00, over(165, -4, 172, 4, 6, 8, 40, -28, split=14)),      # on his hands, the legs still coming up, one ahead
    (0.28, over(212, -16, 168, 4, -6, 6, 40, -18, split=6)),     # through the top: arched, pushing off
    (0.55, over(276, -14, 128, 18, -22, 18, 30, 4)),             # the legs over and reaching for the floor
    (0.82, over(346, 2, 70, 44, -30, 48, 10, 6)),                # the feet under him, the knees taking it
    (1.00, dict(blend(PABSORB, PRUN0, 0.55), **{"Hips": [366 + 0.45 * PABSORB["Hips"][0], -7, 0]})),
]
# (each sits on its lowest point -- his hands, then his feet -- lifted by a clearance that is nothing at either end:
# through the middle he is flat in the air, not lying on the floor; the cart's own rise is added to it)
sp = []
for k in range(14):
    u = k / 13
    p_ = keyed(SPRING, u)
    sp.append(grounded(p_, grounded(p_)[1] - 0.45 * np.sin(np.pi * u) ** 1.3)[0])
mv["V_mv_spring"], mv["S_mv_spring"] = (np.stack(x) for x in zip(*sp))

# ---- the lance: a straight line, feet first
def lance(lean):
    return dict(PRUN, **arms(168, 6, 168, 6), **{"Hips": [-lean, 0, 0], "Spine": [3, 0, 0], "Spine1": [2, 0, 0], "Neck": [10, 0, 0], "Head": [6, 0, 0],
        "RightUpLeg": [-4, 0, -3], "RightLeg": [4, 0, 0], "RightFoot": [44, 0, 0],
        "LeftUpLeg": [2, 0, 3], "LeftLeg": [6, 0, 0], "LeftFoot": [44, 0, 0]})
keep("mv_lance", [blend(PGATHER, lance(30), 0.55), lance(36), lance(40), lance(38)])

for k_, v_ in mv.items():
    if k_.startswith("V_"):
        print(k_[2:], v_.shape, "| up %.2f..%.2f | ahead %.2f..%.2f" % (v_[:, :, 2].min(), v_[:, :, 2].max(), v_[:, :, 0].min(), v_[:, :, 0].max()))
np.savez_compressed(sys.argv[1], **mv)
'''

OUT.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
r = subprocess.run([sys.executable, "-c", _ACRO + MORE, str(OUT)], cwd=ARCHIVE, env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-3000:])
print("\n".join(ln for ln in r.stdout.strip().split("\n") if ln.startswith("mv_")))
print(f"wrote {OUT}")
