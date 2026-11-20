# THE TND BAKER, STAGE ONE: freeze the July game's animation.
#
# TEAR NOT DEMON's fighter (archive/TND, 2026-07) animates by float FK,
# linear-blend skinning and IK, recomputed every frame. None of that can
# run on the Zeta -- and none of it needs to: the alien thesis is that
# expensive things are BAKED EXACTLY and played back. So the archive's
# own posing functions are called here, offline, and their output is
# frozen to a file the forge quantises (games/tnd/gen_tnd.py).
#
# Runs UNDER THE ARCHIVE's import path, in its own process, because both
# trees name their package `zeta`. Reads the archive by path and writes
# the gitignored assets/tnd/ -- the boxer is third-party PS1-style art
# (tear-charkit/data/boxer_ps1_rigged.glb), so the source and this
# intermediate stay out of git, and the baked cart carries the result,
# exactly as carts/system/face.zol carries the Grey.
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
# THE SLOW CLIPS AT 30 Hz: the idle sway (a 2 s loop) and the walk cycle
# keep every other frame, each held two -- the recorded music needed the
# cart storage, and a sway this slow does not show it. Strikes stay 60.
seqs["idle"] = [frozen(bm.idle_mesh(f / 60.0)) for f in range(0, 120, 2)]
# THE WALK, PLANTED (P15). The archive's walk is a step-drag shuffle whose
# feet travel a fifth of the ground he covers; what keeps them from
# sliding there is leg IK, solved every frame against a foot latched in
# the world (tear.py 645, FOOT_PLANT_WEIGHT). That solve cannot run on
# the Zeta -- but the cart walks at ONE speed (gen_tnd.py WALK, 0.032 a
# frame, no momentum), so the whole stride can be solved HERE, with the
# archive's own IK (walk_mesh's `plant`), and frozen: the stance foot is
# aimed at a point that falls behind him by exactly the ground he covers
# each frame, so on the glass it stays where it was put.
#   Two departures from the archive's rule, both for what it looks like
# at 320 x 288: each foot lands HALF a step ahead and lifts half a step
# behind (the archive lands it under him, so he walks ahead of his own
# support) and keeps its own side of the body (the archive pulls both to
# his centre line); and the swinging foot is carried forward on an arc
# (the archive lets it snap to the authored pose in one frame).
#   At 60 Hz, 32 poses a stride: a planted foot held two frames slides a
# frame's ground and snaps back -- two pixels of shimmer. (The 30 Hz walk
# was a storage economy from before the second dies.)
WALK, STEP = 0.032, 16
anat = bm.anatomy(skel)
def _foot(V, who):
    return V[anat.leg(who).foot].mean(0)
_guard = frozen(bm.walk_mesh(0.0, "fwd"))[0]
_rest = {w: _foot(_guard, w) for w in ("lead", "rear")}
# The solver aims the limb's own end, not the sole's centre, and the
# difference turns with the leg -- so each frame is solved, measured, and
# re-aimed by its own error until the SOLE is where the plant says (four
# passes: the residue is under a millimetre).
def _planted(t, wants):
    aim = {w: np.array(p) for w, p in wants.items()}
    for _ in range(4):
        res = frozen(bm.walk_mesh(t, "fwd", plant=[(w, tuple(aim[w]), 1.0) for w in aim]))
        for w in aim:
            aim[w] += np.array(wants[w]) - _foot(res[0], w)
    return frozen(bm.walk_mesh(t, "fwd", plant=[(w, tuple(aim[w]), 1.0) for w in aim]))
def _at(who, x, lift):
    return (x, _rest[who][1], _rest["lead"][2] + lift)
_half = WALK * (STEP - 1) / 2
walk = []
for f in range(2 * STEP):
    s, fs = divmod(f, STEP)
    down, swing = (("rear", "lead"), ("lead", "rear"))[s]
    u = (fs + 1) / (STEP + 1)
    walk.append(_planted(f / (2.0 * STEP), {
        down: _at(down, _half - WALK * fs, 0.0),
        swing: _at(swing, -_half + 2 * _half * u * u * (3 - 2 * u), 0.10 * np.sin(np.pi * u))}))
seqs["walk"] = walk
# THE LANDING'S SQUASH (P15): the archive's own absorb (idle_mesh's
# `squash`, tear.py land_squash) at four strengths -- the touchdown's
# knees, frozen, since an object on this machine cannot be scaled
seqs["land"] = [frozen(bm.idle_mesh(0.0, squash=q)) for q in (1.0, 0.75, 0.5, 0.25)]
# THE AIR: boxer_mesh.air_mesh is a function of vz alone (the load at
# takeoff, full extension at the apex, the capped brace falling), so seven
# samples over its range -- vz = 0.16 down to -0.16 -- are the whole clip;
# the cart picks by its vz
seqs["air"] = [frozen(bm.air_mesh(0.16 - k * 0.16 / 3)) for k in range(7)]
# THE MOVEMENT LAYER (tear.py _action_move): the parkour sprint and the
# boxing step-drag, one stride each at 16 poses (the cart steps the phase by
# its speed); the flips -- tuck, backflip, and the cartwheel both sides share
# -- and the fencing slips, over their own frames at 60 Hz. (The flip's SPIN
# is the renderer's in the archive, and the cart's here: these are shapes.)
seqs["run"] = [frozen(bm.run_mesh(f / 16.0)) for f in range(16)]
for d in ("fwd", "back", "left", "right"):
    seqs["kite_" + d] = [frozen(bm.boxing_kite_mesh(f / 16.0, d)) for f in range(16)]
for name, kind, n in (("flip_fwd", "fwd", 20), ("flip_back", "back", 20),
                      ("flip_cart", "left", 24)):
    seqs[name] = [frozen(bm.flip_mesh(f / (n - 1), kind)) for f in range(n)]
for d in ("fwd", "back", "left", "right"):
    seqs["dodge_" + d] = [frozen(bm.dodge_mesh(f / 11.0, d)) for f in range(12)]
# the swings, at the game's own timing: the clip stretched over the move's
# startup + active + recovery, as tear.py draws it (t = frame / (total-1))
for mv in ("jab", "cross", "lead_hook", "rear_hook", "special",
           "lead_uppercut", "rear_uppercut", "gun", "gun_charged"):
    n = TOTAL[mv]
    seqs[mv] = [frozen(bm.move_mesh(mv, f / (n - 1))) for f in range(n)]
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

# ---- THE KEYS: what the fight hit-tests (tear.py _resolve_hits) ----------
# A move lands when the attacker's posed FIST, during its active frames,
# comes within the move's reach of the target's CHIN or GUT -- keypoints
# of the primitive rig, which the archive hit-tests on whatever is drawn.
# Fists are baked for every active frame (character-local); chins and guts
# at GUARD (a reach of 1.4-1.55 dwarfs how far they move).
def move_row(m):
    return [m.startup, m.active, m.recovery, m.damage, m.reach, m.hitstop,
            m.knock, m.lunge, m.lift, m.style]
def fists(sk, m):
    return np.array([sk.point(m.limb, m.pose_at(f))
                     for f in range(m.startup, m.startup + m.active)])
player = rig.fighter(rig.Build(body=(38, 52, 96), trim=(255, 214, 92),
                               skin=(226, 178, 140)))   # tear.py's player
PM = (combat.JAB, combat.CROSS, combat.LEAD_HOOK, combat.REAR_HOOK,
      combat.SPECIAL, combat.LEAD_UPPERCUT, combat.REAR_UPPERCUT,
      combat.GUN, combat.GUN_CHARGED)
out["p_moves"] = np.array([move_row(m) for m in PM], float)
for m in PM:
    out["p_fist_" + m.name] = fists(player, m)
out["p_chin"] = np.array(player.point("chin", rig.GUARD))
out["p_gut"] = np.array(player.point("body", rig.GUARD))
DM = (combat.CROSS, combat.LEAD_HOOK)
out["d_moves"] = np.array([move_row(m) for m in DM], float)
for i, sk in enumerate(sks):
    out[f"b{i}_chin"] = np.array(sk.point("chin", rig.GUARD))
    out[f"b{i}_gut"] = np.array(sk.point("body", rig.GUARD))
    for m in DM:
        out[f"b{i}_fist_{m.name}"] = fists(sk, m)
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
