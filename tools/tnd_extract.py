# THE TND BAKER, STAGE ONE: freeze the July game's animation.
#
# TEAR NOT DEMON's fighter (archive/TND, 2026-07) animates by float FK,
# linear-blend skinning and IK, recomputed every frame. None of that can
# run on the Zeta -- and none of it needs to: the alien thesis is that
# expensive things are BAKED EXACTLY and played back. So the archive's
# own posing functions are called here, offline, and their output is
# frozen to a file the forge quantises (carts/gen_tnd.py).
#
# Runs UNDER THE ARCHIVE's import path, in its own process, because both
# trees name their package `zeta`. Reads the archive by path and writes
# the gitignored assets/tnd/ -- the boxer is third-party PS1-style art
# (tear-charkit/data/boxer_ps1_rigged.glb), so the source and this
# intermediate stay out of git, and the baked cart carries the result,
# exactly as carts/face.zol carries the Grey.
#
#   python3 tools/tnd_extract.py [path/to/archive/TND]

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = Path(sys.argv[1] if len(sys.argv) > 1
               else ROOT.parent / "archive" / "TND")
OUT = ROOT / "assets" / "tnd" / "boxer.npz"
DEMONS = ROOT / "assets" / "tnd" / "demons.npz"

# ---- the sequences, as the archive's own calls ---------------------------
# Each entry: name -> (frames, the archive expression for frame f). These
# are the game's clips at the game's own timing (tear.py: a move's clip
# fraction is frame / (total - 1)).
CHILD = r'''
import sys, numpy as np
sys.path.insert(0, "src")
from zeta.virtual import boxer_mesh as bm
from zeta.virtual import combat
skel = bm._load_skeleton()
F = np.asarray(skel["F"], np.int64)
C = np.asarray(skel["C"])
nv = int(F.max()) + 1
TOTAL = {m.name: m.total for m in combat.MOVES.values()} \
    if hasattr(combat, "MOVES") else {}
def frozen(res):
    faces, cols = res
    V = np.zeros((nv, 3))
    V[F.reshape(-1)] = np.asarray(faces).reshape(-1, 3)
    return V, np.asarray(cols)
seqs = {}
seqs["idle"] = [frozen(bm.idle_mesh(f / 60.0)) for f in range(120)]
seqs["walk"] = [frozen(bm.walk_mesh(f / 32.0, "fwd")) for f in range(32)]
jt = TOTAL.get("jab", 16)
seqs["jab"] = [frozen(bm.move_mesh("jab", f / (jt - 1))) for f in range(jt)]
out = {"F": F, "C": C}
for k, frames in seqs.items():
    out["V_" + k] = np.stack([v for v, _ in frames])
    out["S_" + k] = np.stack([c for _, c in frames])
np.savez_compressed(sys.argv[1], **out)
print({k: v.shape for k, v in out.items()})
'''

# ---- the demons: three builds of one rigid rig, and their clips ----------
# The archive's demons are NOT skinned: rig.fighter is 17 rigid joints,
# each carrying its own baked-lit triangles. So the bake is two things:
#   per build   each joint's parent, offset and local triangles (the
#               build scales them: brute, lean, heavy)
#   per frame   each joint's CHARACTER-LOCAL rotation, which depends only
#               on the pose, never on the build -- so ONE clip table
#               serves all three, and the cart redoes the cheap part (the
#               offsets through the parents) at run time.
# The clips are the archive's own calls at the archive's own timing.
DEMON_CHILD = r'''
import sys, math, numpy as np
sys.path.insert(0, "src")
from zeta.virtual import rig, combat
from zeta.virtual import tear
import inspect
src = inspect.getsource(tear.Tear._spawn_wave)
# the three builds, exactly as the wave spawns them
builds = (
    rig.Build(stature=1.35, reach=0.95, bulk=1.40, stance=1.25,
              body=(36, 28, 26), trim=(150, 38, 22), skin=(92, 60, 54), species="demon"),
    rig.Build(stature=1.30, reach=1.30, bulk=0.85, stance=0.85,
              body=(30, 26, 36), trim=(130, 26, 32), skin=(80, 68, 76), species="demon"),
    rig.Build(stature=0.95, reach=0.80, bulk=1.40, stance=1.40,
              body=(42, 32, 20), trim=(168, 70, 26), skin=(96, 66, 50), species="demon"),
)
for b in builds:          # the copy above must still BE the wave's builds
    assert f"stature={b.stature:.2f}" in src, "the archive's builds moved"
sks = [rig.fighter(b) for b in builds]
names = list(sks[0].order)
out = {"names": np.array(names)}
for i, sk in enumerate(sks):
    out[f"b{i}_parent"] = np.array([names.index(sk.joints[n].parent)
                                    if sk.joints[n].parent else -1 for n in names])
    out[f"b{i}_offset"] = np.array([sk.joints[n].offset for n in names])
    for k, n in enumerate(names):
        tr = sk.joints[n].tris
        out[f"b{i}_j{k}_tris"] = np.array([[a, b_, c] for a, b_, c, _ in tr]).reshape(-1, 3, 3)
        out[f"b{i}_j{k}_cols"] = np.array([col for *_, col in tr]).reshape(-1, 3)
    # THE HORNS, AS THE FIRST LOD. The archive's are 2 x 5 overlapping
    # boxes, 120 of the head's 152 triangles. The head's geometry ENDS with
    # them (head = node + taper + horns), so they are cut off the tail --
    # checked against the archive's own horn function -- and rebuilt as a
    # curved two-segment spike per side along the SAME curl, lit by the
    # archive's own shade().
    s_ = builds[i].stature
    raw = rig._demon_horns(s_, (20, 17, 19))
    hk = names.index("head")
    full = sk.joints["head"].tris
    assert np.allclose([t[:3] for t in full[-len(raw):]], [t[:3] for t in raw])
    out[f"b{i}_j{hk}_tris"] = out[f"b{i}_j{hk}_tris"][:-len(raw)]
    out[f"b{i}_j{hk}_cols"] = out[f"b{i}_j{hk}_cols"][:-len(raw)]
    spikes = []
    for sgn in (1.0, -1.0):
        x, y, z = -0.02 * s_, sgn * 0.050 * s_, 0.104 * s_
        dx, dy, dz = -0.020 * s_, sgn * 0.010 * s_, 0.050 * s_
        pts = [(x, y, z)]
        for k in range(5):                  # the archive's curl, verbatim
            x, y, z = x + dx, y + dy, z + dz
            pts.append((x, y, z))
            dz *= 0.66; dx *= 1.50; dy *= 1.35
        ring = []
        for c, wc in ((pts[0], 0.036 * s_), (pts[2], 0.036 * s_ * 0.5)):
            ring.append([(c[0] + wc * math.cos(a), c[1] + wc * math.sin(a), c[2])
                         for a in (0.0, 2.094, 4.189)])
        tip = pts[5]
        HORN = (20, 17, 19)
        for k in range(3):
            a0, a1 = ring[0][k], ring[0][(k + 1) % 3]
            b0, b1 = ring[1][k], ring[1][(k + 1) % 3]
            spikes += [(a0, a1, b1, HORN), (a0, b1, b0, HORN), (b0, b1, tip, HORN)]
    sh = rig.shade(spikes)
    out[f"b{i}_spike_tris"] = np.array([[a, b_, c] for a, b_, c, _ in sh])
    out[f"b{i}_spike_cols"] = np.array([col for *_, col in sh])
# the clips (60 Hz unless noted)
TAU = 2 * math.pi
def idle(f):
    # rig.guard_idle runs three incommensurate periods (34, 68, 103
    # frames) so it never visibly loops; a cart needs a loop. Same terms,
    # periods rounded to 32 / 64 / 64, so 64 frames close it.
    base = rig.GUARD
    out = {k: rig._angles(base, k) for k in base}
    bounce, rock = math.sin(TAU * f / 32), math.sin(TAU * f / 64)
    roll = math.sin(TAU * f / 64 + 1.1)
    A = rig._add
    A(out, "knee_l", (0.13 * (bounce * 0.5 + 0.5), 0, 0))
    A(out, "knee_r", (0.13 * (0.5 - bounce * 0.5), 0, 0))
    A(out, "hip_l", (-0.07 * bounce, 0, 0)); A(out, "hip_r", (0.07 * bounce, 0, 0))
    A(out, "pelvis", (0, 0.10 * rock, 0))
    A(out, "spine", (-0.035 * bounce, 0.05 * rock, 0))
    A(out, "chest", (-0.03 * bounce, 0.07 * roll, 0))
    A(out, "shoulder_l", (-0.075 * bounce, 0.055 * roll, 0))
    A(out, "shoulder_r", (-0.065 * math.sin(TAU * f / 32 + 0.9), -0.05 * roll, 0))
    A(out, "elbow_l", (0.055 * bounce, 0, 0))
    A(out, "elbow_r", (0.05 * math.sin(TAU * f / 32 + 0.6), 0, 0))
    A(out, "head", (0.03 * bounce, 0.045 * rock, 0))
    return out
clips = {
    "idle": [idle(2 * f) for f in range(32)],                 # 30 Hz
    "walk": [rig.locomotion(TAU * f / 16, 0.20, top_speed=0.20) for f in range(16)],
    "cross": [combat.CROSS.pose_at(f) for f in range(combat.CROSS.total)],
    "hook": [combat.LEAD_HOOK.pose_at(f) for f in range(combat.LEAD_HOOK.total)],
    "hurt": [rig.HURT],
    "dead": [rig.blend(rig.HURT, rig.DOWN, (k := min(1.0, f / 26.0)) * (2 - k))
             for f in range(0, 27, 2)],                       # 30 Hz
}
for c, poses in clips.items():
    R = np.zeros((len(poses), len(names), 3, 3))
    T = np.zeros((3, len(poses), len(names), 3))
    for f, pose in enumerate(poses):
        for i, sk in enumerate(sks):
            xf = sk.transforms(pose)
            for k, n in enumerate(names):
                if i == 0:
                    R[f, k] = xf[n][0]
                T[i, f, k] = xf[n][1]
    out["R_" + c], out["T_" + c] = R, T
out["moves"] = np.array([[combat.CROSS.startup, combat.CROSS.active, combat.CROSS.recovery,
                          combat.CROSS.damage],
                         [combat.LEAD_HOOK.startup, combat.LEAD_HOOK.active,
                          combat.LEAD_HOOK.recovery, combat.LEAD_HOOK.damage]])
np.savez_compressed(sys.argv[1], **out)
print(names, {c: len(v) for c, v in clips.items()})
'''

OUT.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
r = subprocess.run([sys.executable, "-c", CHILD, str(OUT)], cwd=ARCHIVE,
                   env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-2000:])
print(r.stdout.strip())
print(f"wrote {OUT}")
r = subprocess.run([sys.executable, "-c", DEMON_CHILD, str(DEMONS)], cwd=ARCHIVE,
                   env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-3000:])
print(r.stdout.strip())
print(f"wrote {DEMONS}")
