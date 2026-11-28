"""loop.py -- closing the loop on a real route: sight -> the field.

NOT LAW. The retina and the field were mocked apart; the field's README
ended on what was missing: nothing turns what was SEEN into deposits,
and a sparse gaze warms nothing.

The first idea fails on TND before it starts: deposit at each seen
object's position. TND's town pieces all sit at the origin with their
meshes in world space, so an object's position says nothing about
where its pixels are.

What the machine already answers is better: PICK gives the depth
standing at a pixel the program chose (spec.PICK_Z). A pixel and its
depth, with the camera, IS a point in the world -- the place the
player's eye actually landed. So:

    each frame, the program picks K pixels, and next frame deposits at
    the K world cells their depths name.

The law has one pick a frame. The design proposes eight. This asks how
many it takes, against the truth: every pixel of every frame unprojected.

    python3 experiments/loop/loop.py     # map.png, loop.gif, the table in README.md
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from zeta import cabinet, carts, gpu, spec  # noqa: E402
import tnd_meter                             # noqa: E402

HERE = Path(__file__).resolve().parent
N = 256                         # the field's window
CELLS = 8                       # cells a world unit
X0, Z0 = -16.0, -6.0            # the world corner the window's corner sits on
ROUTE = "tour"


class DepthTap:
    """Keeps the depth plane of the last render. The law is not changed."""

    def __init__(self):
        self.z = None
        self._geom = gpu._geom

    def __enter__(self):
        def geom(*a, **k):
            self._geom(*a, **k)
            self.z = a[1]
        gpu._geom = geom
        return self

    def __exit__(self, *exc):
        gpu._geom = self._geom


def to_cells(sx, sy, zc, dmem):
    """pixels and their depth counts -> field cells (row, col), and which
    of them are real (a depth, and inside the window). The inverse of
    gpu._verts: undo the projection, the pitch, the yaw, the camera."""
    z = zc.astype(np.float64) * (1 << spec.ZSHIFT) / 65536.0
    vx = (sx - spec.W / 2 + 0.5) * z / spec.FOCAL
    vy = (spec.H / 2 - sy - 0.5) * z / spec.FOCAL
    pit = (dmem[spec.CAM_PITCH] & 1023) * 2 * np.pi / 1024
    yaw = (dmem[spec.CAM_YAW] & 1023) * 2 * np.pi / 1024
    vy, vz = vy * np.cos(pit) - z * np.sin(pit), vy * np.sin(pit) + z * np.cos(pit)
    wx = vx * np.cos(yaw) - vz * np.sin(yaw) + spec.s32(dmem[spec.CAM_X]) / 65536
    wz = vx * np.sin(yaw) + vz * np.cos(yaw) + spec.s32(dmem[spec.CAM_Z]) / 65536
    col = np.floor((wx - X0) * CELLS).astype(int)
    row = np.floor((wz - Z0) * CELLS).astype(int)
    wy = vy + spec.s32(dmem[spec.CAM_Y]) / 65536    # height above the ground
    ok = (zc < spec.ZFAR) & (col >= 0) & (col < N) & (row >= 0) & (row < N)
    return row, col, ok, wy


def halton(i, base):
    f, r = 1.0, 0.0
    while i:
        f /= base
        r += f * (i % base)
        i //= base
    return r


def picks(frame, k):
    """K pixels for this frame: a sequence that never repeats a pattern
    and covers the glass evenly. Whole numbers a program could compute."""
    i = np.arange(frame * k, frame * k + k) + 1
    sx = np.array([int(halton(int(j), 2) * spec.W) for j in i])
    sy = np.array([int(halton(int(j), 3) * spec.H) for j in i])
    return sx, sy


def stamp(grid, row, col, r):
    for y, x in zip(row, col):
        grid[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] = True


def main():
    frames = tnd_meter.ROUTES[ROUTE]
    ks = (1, 8, 32, 128)
    radii = (0, 1, 2)
    truth = np.zeros((N, N), bool)
    weight = np.zeros((N, N), np.int64)             # how MUCH of the glass fell on a cell
    stands = np.zeros((N, N), bool)                 # a pick landed above the ground here
    got = {(k, r): np.zeros((N, N), bool) for k in ks for r in radii}
    trace = np.zeros((N, N), np.int64)             # the field's own trace, K = 8
    gx, gy = np.meshgrid(np.arange(0, spec.W, 2), np.arange(0, spec.H, 2))
    gx, gy = gx.ravel(), gy.ravel()
    shots = []
    path = []
    m = cabinet.VirtualMachine(cabinet.load_cart(carts.path("tnd")))
    with DepthTap() as tap:
        for f in range(frames):
            m.frame(tnd_meter.pad(ROUTE, f))
            d, z = m.vm.dmem, np.asarray(tap.z)
            row, col, ok, _ = to_cells(gx, gy, z[gy, gx], d)
            truth[row[ok], col[ok]] = True
            np.add.at(weight, (row[ok], col[ok]), 1)
            for k in ks:
                sx, sy = picks(f, k)
                r_, c_, ok_, wy = to_cells(sx, sy, z[sy, sx], d)
                if k == 8:
                    up = ok_ & (wy > 0.4)
                    stands[r_[up], c_[up]] = True
                for r in radii:
                    stamp(got[(k, r)], r_[ok_], c_[ok_], r)
                if k == 8:                         # what the field would hold
                    for y, x in zip(r_[ok_], c_[ok_]):
                        trace[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = np.minimum(
                            255, trace[max(0, y - 1):y + 2, max(0, x - 1):x + 2] + 90)
            p = np.pad(trace, 1, mode="edge")
            trace = (4 * trace + p[:-2, 1:-1] + p[2:, 1:-1]
                     + p[1:-1, :-2] + p[1:-1, 2:]) >> 3
            if f % 3 == 0:
                trace = np.maximum(0, trace - 1)   # a slow fade: DECAY 1 every third step
            cx = int((spec.s32(d[spec.CAM_X]) / 65536 - X0) * CELLS)
            cz = int((spec.s32(d[spec.CAM_Z]) / 65536 - Z0) * CELLS)
            path.append((cz, cx))
            if f % 10 == 0:
                shots.append(panel(np.asarray(m.framebuffer()), truth, trace, (cz, cx)))
    shots = [s.quantize(48) for s in shots]
    shots[0].save(HERE / "loop.gif", save_all=True, append_images=shots[1:],
                  duration=160, loop=0, optimize=True)
    final = map_image(truth, got[(8, 1)], path, stands)
    Image.fromarray(final).resize((N * 3, N * 3), Image.NEAREST).save(HERE / "map.png")

    seen = int(truth.sum())
    print(f"route: tnd, {ROUTE}, {frames} frames; world cells any pixel landed on: "
          f"{seen:,} of {N * N:,}")
    print(f"cells where eight picks a frame found something standing: {int(stands.sum()):,}\n")
    print("OF THE CELLS sight ever touched, the share the picks marked\n")
    print("| picks a frame | a pick marks 1 cell | 3 x 3 cells | 5 x 5 cells |")
    print("|---:|---:|---:|---:|")
    for k in ks:
        cov = [100 * (got[(k, r)] & truth).sum() / seen for r in radii]
        print(f"| {k} | {cov[0]:.1f}% | {cov[1]:.1f}% | {cov[2]:.1f}% |")
    print("\nOF EVERYTHING THE GLASS SHOWED (pixels x frames), the share that fell on marked cells\n")
    print("| picks a frame | a pick marks 1 cell | 3 x 3 cells | 5 x 5 cells |")
    print("|---:|---:|---:|---:|")
    for k in ks:
        cov = [100 * weight[got[(k, r)]].sum() / weight.sum() for r in radii]
        print(f"| {k} | {cov[0]:.1f}% | {cov[1]:.1f}% | {cov[2]:.1f}% |")


def map_image(truth, marked, path, stands):
    """Top down. Dim blue: every cell sight ever landed on. Brown: the
    cells eight picks a frame marked. Bright: where a pick landed above
    the ground -- the plan of what stands there, learned by looking.
    White: where the camera went."""
    img = np.zeros((N, N, 3), np.uint8)
    img[truth] = (30, 34, 56)
    img[marked & truth] = (96, 66, 34)
    img[stands] = (255, 214, 120)
    for y, x in path:
        if 0 <= y < N and 0 <= x < N:
            img[y, x] = (255, 255, 255)
    return img[::-1]                                # far is up


def panel(frame, truth, trace, cam):
    """The game's frame beside what the field holds at that instant."""
    img = np.zeros((N, N, 3), np.int64)
    img[truth] = (30, 34, 56)
    img += (trace[..., None] * np.array([1.0, 0.62, 0.2])).astype(np.int64)
    y, x = cam
    if 1 <= y < N - 1 and 1 <= x < N - 1:
        img[y - 1:y + 2, x - 1:x + 2] = 255
    img = np.clip(img, 0, 255).astype(np.uint8)[::-1]
    left = np.zeros((spec.H, spec.W, 3), np.uint8) + frame
    right = np.zeros((spec.H, N, 3), np.uint8)
    right[(spec.H - N) // 2:(spec.H - N) // 2 + N] = img
    return Image.fromarray(np.concatenate([left, right], axis=1))


if __name__ == "__main__":
    main()
