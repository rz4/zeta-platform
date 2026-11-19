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

OUT.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
r = subprocess.run([sys.executable, "-c", CHILD, str(OUT)], cwd=ARCHIVE,
                   env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-2000:])
print(r.stdout.strip())
print(f"wrote {OUT}")
