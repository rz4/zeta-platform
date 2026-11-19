# Dump three telling frames of TEAR, driven by the balance test's own
# pads: the opening stance, a landed hit (enemy hit-flash live), and
# the KO banner. Frames are found by reading the cart's state cells,
# not hand-picked numbers, so the shots regenerate from any build.
import sys
sys.path.insert(0, ".")
import numpy as np, pygame
from zeta import cabinet, spec

PX, EFL, KO, WIN = 16, 23, 24, 25
m = cabinet.VirtualMachine(cabinet.load_cart("carts/tear.zol"))
want = {"stance": None, "hit": None, "ko": None}
for f in range(3000):
    m.frame(spec.PAD_RIGHT | spec.PAD_A)
    d = m.vm.dmem
    if f == 24:
        want["stance"] = (f, np.asarray(m.panel(), dtype=np.uint8).copy())
    if want["hit"] is None and d[EFL] > 2 and d[KO] == 0:
        want["hit"] = (f, np.asarray(m.panel(), dtype=np.uint8).copy())
    if want["ko"] is None and d[KO] > 0 and d[KO] < 110 and d[WIN] == 1:
        want["ko"] = (f, np.asarray(m.panel(), dtype=np.uint8).copy())
        break
for name, got in want.items():
    assert got, f"never saw {name}"
    f, panel = got
    big = panel.repeat(2, axis=0).repeat(2, axis=1)   # 2x nearest for docs
    surf = pygame.surfarray.make_surface(np.transpose(big, (1, 0, 2)))
    path = f"docs/images/tear-{name}.png"
    pygame.image.save(surf, path)
    print(f"{path}: frame {f}")
