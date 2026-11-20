# THE ROUTED CROSS: machines 1 and 2 bit-equal along a scripted TND route.
#
# `zeta cross` drives a deterministic wiggle; a rasterizer change wants the
# geometry a real fight puts on screen -- three demons, the street, the
# lock marker, the HUD -- so this drives the meter's routes (tnd_meter.pad)
# through both machines and compares every frame, framebuffer and audio.
#
#   python3 tools/route_cross.py carts/tnd.zol brawl [frames]
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from zeta import cabinet, gpu, silicon   # noqa: E402
from tnd_meter import pad, ROUTES        # noqa: E402

path, route = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else ROUTES[route]
cart = cabinet.load_cart(path)
virt, sil = cabinet.VirtualMachine(cart), silicon.SiliconMachine(cart)
for f in range(n):
    p = pad(route, f)
    virt.frame(p)
    sil.frame(p)
    a, b = virt.framebuffer(), sil.framebuffer()
    if not np.array_equal(a, b):
        gpu.write_ppm(a, f"cross_virtual_{f}.ppm")
        gpu.write_ppm(b, f"cross_silicon_{f}.ppm")
        print(f"ROUTE CROSS FAIL at {route} frame {f}: "
              f"{int((a != b).any(axis=2).sum())} pixels differ")
        sys.exit(1)
    if not np.array_equal(virt.audio(), sil.audio()):
        print(f"ROUTE CROSS FAIL at {route} frame {f}: audio")
        sys.exit(1)
sil.close()
print(f"ROUTE CROSS PASS: {path} {route}, {n} frames bit-equal")
