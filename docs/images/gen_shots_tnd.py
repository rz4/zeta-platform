# Capture frames of the archive TND TEAR headless: fake the keyboard,
# grab the display surface on every flip, save every Nth frame.
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, "src")

import pygame

OUT = sys.argv[1]
MENU = sys.argv[2] == "menu"
FRAMES = int(sys.argv[3])
EVERY = int(sys.argv[4])

os.makedirs(OUT, exist_ok=True)


class Keys:
    """A fake get_pressed: scripted by frame number."""
    def __init__(self):
        self.frame = 0
        self.down = set()

    def __getitem__(self, k):
        return k in self.down


KEYS = Keys()
real_get_pressed = pygame.key.get_pressed
pygame.key.get_pressed = lambda: KEYS

count = [0]
real_flip = pygame.display.flip


def flip():
    real_flip()
    f = count[0]
    count[0] += 1
    KEYS.frame = f
    KEYS.down = script(f)
    if f % EVERY == 0:
        surf = pygame.display.get_surface()
        if surf:
            import numpy as np
            arr = np.transpose(pygame.surfarray.array3d(surf), (1, 0, 2))
            with open(f"{OUT}/f{f:05d}.ppm", "wb") as fh:
                fh.write(b"P6 %d %d 255\n" % (arr.shape[1], arr.shape[0]))
                fh.write(np.ascontiguousarray(arr).astype("u1").tobytes())


pygame.display.flip = flip


def script(f):
    if MENU:
        return set()
    k = set()
    if f < 150:
        k.add(pygame.K_PERIOD)            # walk forward into the field
    elif f < 400:
        if (f // 8) % 2 == 0:
            k.add(pygame.K_c)             # fists, tapped
        if (f // 40) % 3 == 0:
            k.add(pygame.K_PERIOD)
    else:
        k.add(pygame.K_o)                 # turn, look around
    return k


from zeta.virtual import console
from zeta.virtual.tear import Tear

console.run(Tear(menu=MENU), frames=FRAMES, headless=True, crt=True)
print(f"saved {len(os.listdir(OUT))} frames to {OUT}")
