"""The mesh baker, pinned: budgets hold, indices stay valid, colors shade."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import meshtool, spec


def sphereish(n=24):
    """A crude UV sphere: plenty of verts to force real decimation."""
    import math
    verts, faces = [], []
    for j in range(n + 1):
        for i in range(n):
            th, ph = math.tau * i / n, math.pi * j / n
            verts.append((math.sin(ph) * math.cos(th), 1 - math.cos(ph),
                          math.sin(ph) * math.sin(th)))
    for j in range(n):
        for i in range(n):
            a = j * n + i
            b = j * n + (i + 1) % n
            faces.append((a, b, b + n))
            faces.append((a, b + n, a + n))
    return verts, faces


def test_bake_budgets_and_validity():
    verts, faces = sphereish()
    blocks = meshtool.bake(verts, faces, height=1.0, max_words=900)
    assert sum(len(b) for b in blocks) <= 900 + 4 * len(blocks)
    for words in blocks:
        nv, nf = words[0], words[1]
        assert nv <= spec.MESH_NV_MAX and nf <= spec.MESH_NF_MAX
        assert len(words) == 2 + 3 * nv + 2 * nf
        for k in range(nf):
            idx = words[2 + 3 * nv + 2 * k]
            a, b, c = idx & 1023, (idx >> 10) & 1023, (idx >> 20) & 1023
            assert a < nv and b < nv and c < nv
        ys = words[3:2 + 3 * nv:3]
        assert min(ys) >= -(1 << 12)          # feet at ~y=0 after normalize
        cols = words[2 + 3 * nv + 1::2]
        assert len({c for c in cols}) > 4     # lambert actually varies
