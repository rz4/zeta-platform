# THE TND TITLE, BAKED: the archive's own start screen -- TEAR / NOT /
# DEMON in its gothic hand, the demonic Ns, the blood gash, the inverted
# cross, PRESS START, over the frozen street -- rendered by the archive
# itself, offline, at the panel's own 320x288 and without the CRT filter,
# and frozen to a file the cart turns into a backdrop plate
# (games/tnd/gen_tnd.py). Its menu offers START alone: the port has no LOAD or
# OPTIONS, and a title must not promise what the game cannot do.
#
# Runs UNDER THE ARCHIVE's import path, in its own process, like
# tools/tnd_extract.py, and writes the gitignored assets/tnd/title.npz.
#
#   python3 tools/tnd_title.py [path/to/archive/TND]

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = Path(sys.argv[1] if len(sys.argv) > 1
               else ROOT.parent / "archive" / "TND")
OUT = ROOT / "assets" / "tnd" / "title.npz"
FRAME = 61          # the prompt's bright half (it blinks on a 60-frame beat)

CHILD = r'''
import os, sys
sys.path.insert(0, "src")
import numpy as np
import pygame
from zeta.virtual import console
from zeta.virtual.tear import Tear
Tear.MENU_MAIN = ("START",)
grab = {}
real_flip = pygame.display.flip
count = [0]
def flip():
    real_flip()
    if count[0] == int(sys.argv[2]):
        s = pygame.display.get_surface()
        grab["img"] = np.transpose(pygame.surfarray.array3d(s), (1, 0, 2)).copy()
    count[0] += 1
pygame.display.flip = flip
console.run(Tear(menu=True), frames=int(sys.argv[2]) + 2, headless=True, crt=False)
img = grab["img"]
# the console draws at the panel's 320x288 and scales x3 by nearest
# neighbour: every 3x3 block is one pixel (checked, not assumed)
h, w = img.shape[0] // 3, img.shape[1] // 3
b = img.reshape(h, 3, w, 3, 3).swapaxes(1, 2)
assert (b == b[:, :, :1, :1, :]).all(), "the upscale is not nearest-neighbour"
img = b[:, :, 0, 0, :].copy()
np.savez_compressed(sys.argv[1], img=img)
print("title", img.shape)
'''

OUT.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
r = subprocess.run([sys.executable, "-c", CHILD, str(OUT), str(FRAME)],
                   cwd=ARCHIVE, env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-2000:])
print(r.stdout.strip().splitlines()[-1])
print(f"wrote {OUT}")
