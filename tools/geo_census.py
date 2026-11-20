# THE GEOMETRY CENSUS: where a frame's triangles and pixels go, on the law.
#
# The silicon meter (tools/tnd_meter.py) says WHICH UNIT spends the clocks
# (clr / walk / idle / seq / blkd); this says what the rasterizer's walk is
# made of, by wrapping the law's own rasterizer (gpu._fill, which runs once
# per triangle per band and masks its writes to the band) and counting,
# per frame:
#
#   faces      submitted -- every face of every listed object
#   tris       distinct triangles that reached the rasterizer (post cull,
#              post clip: a clipped face may become several)
#   fills      triangle x band visits (a tall triangle is walked once per
#              band it crosses -- the walk restarts each band)
#   walked     pixels the silicon walks: the box's width x its rows inside
#              the band, one clock each for a flat face (spec: the walk)
#   covered    pixels inside the triangle (edge coverage), in the band
#   committed  covered pixels that won the depth test
#
# covered / walked is the bounding-box walk's efficiency: the fraction of
# the rasterizer's walk clocks that land on the triangle at all.
#
#   python3 tools/geo_census.py games/tnd/tnd.zol brawl [frame ...]
#   python3 tools/geo_census.py build/song/tnd.zol tour 887

import collections
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from zeta import cabinet, gpu, spec  # noqa: E402
from tnd_meter import pad, ROUTES     # noqa: E402

C = collections.Counter()
SEEN = set()


def census_fill(orig):
    def fill(fb, zbuf, x0, y0, x1, y1, x2, y2, *a, **k):
        clip = k.get("clip")
        lo_x = max(min(x0, x1, x2) >> spec.SUB, 0)
        hi_x = min(max(x0, x1, x2) >> spec.SUB, spec.W - 1)
        lo_y = max(min(y0, y1, y2) >> spec.SUB, 0)
        hi_y = min(max(y0, y1, y2) >> spec.SUB, spec.H - 1)
        if clip is not None:
            ry0, ry1 = max(lo_y, clip[1]), min(hi_y, clip[3])
        else:
            ry0, ry1 = lo_y, hi_y
        if lo_x <= hi_x and ry0 <= ry1:
            C["fills"] += 1
            C["walked"] += (hi_x - lo_x + 1) * (ry1 - ry0 + 1)
            yy = np.arange(ry0, ry1 + 1, dtype=np.int64)
            xx = np.arange(lo_x, hi_x + 1, dtype=np.int64)
            ys = ((yy << spec.SUB) + spec.HALF)[:, None]
            xs = ((xx << spec.SUB) + spec.HALF)[None, :]
            e0 = (x1 - x0) * (ys - y0) - (y1 - y0) * (xs - x0)
            e1 = (x2 - x1) * (ys - y1) - (y2 - y1) * (xs - x1)
            e2 = (x0 - x2) * (ys - y2) - (y0 - y2) * (xs - x2)
            cov = ((e0 >= 0) & (e1 >= 0) & (e2 >= 0)) | \
                  ((e0 <= 0) & (e1 <= 0) & (e2 <= 0))
            C["covered"] += int(cov.sum())
            # the box's rows that hold any coverage, and their span widths:
            # what an exact span walk (first..last covered pixel a row) costs
            rows = cov.any(axis=1)
            if rows.any():
                first = np.argmax(cov, axis=1)
                last = cov.shape[1] - 1 - np.argmax(cov[:, ::-1], axis=1)
                C["spans"] += int(((last - first + 1) * rows).sum())
                C["span_rows"] += int(rows.sum())
            C["box_rows"] += ry1 - ry0 + 1
            key = (x0, y0, x1, y1, x2, y2, k.get("oid", 0))
            if key not in SEEN:
                SEEN.add(key)
                C["tris"] += 1
        before = None
        res = orig(fb, zbuf, x0, y0, x1, y1, x2, y2, *a, **k)
        return res
    return fill


def frame_census(m, padv):
    C.clear()
    SEEN.clear()
    d = m.vm.dmem
    m.frame(padv)
    n = min(d[spec.OL_BASE], spec.OL_MAX)
    faces = 0
    for o in range(n):
        mb = d[spec.OL_BASE + 1 + o * spec.OL_STRIDE]
        if 0 <= mb < spec.DMEM_WORDS - 2:
            faces += d[mb + 1]
    C["faces"] = faces
    C["objects"] = n
    C["dl_tris"] = d[spec.DL_BASE]
    return dict(C)


if __name__ == "__main__":
    path, route = sys.argv[1], sys.argv[2]
    want = {int(f) for f in sys.argv[3:]} or None
    orig = gpu._fill
    gpu._fill = census_fill(orig)
    m = cabinet.VirtualMachine(cabinet.load_cart(path))
    rows = []
    for f in range(ROUTES[route]):
        c = frame_census(m, pad(route, f))
        if want is None or f in want:
            rows.append((f, c))
    gpu._fill = orig
    keys = ("objects", "faces", "tris", "fills", "walked", "covered", "spans", "dl_tris")
    print("frame " + " ".join(f"{k:>8s}" for k in keys) + "  cov/walk span/walk")
    for f, c in rows:
        w = max(1, c.get("walked", 0))
        print(f"{f:5d} " + " ".join(f"{c.get(k, 0):8d}" for k in keys)
              + f"  {c.get('covered', 0) / w:7.2f} {c.get('spans', 0) / w:9.2f}")
