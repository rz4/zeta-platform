"""meshtool.py -- bake real models into GEOM meshes.

The PS1 pipeline in four moves, all at bake time so the cart pays nothing:
  normalize   feet on y=0, centered, scaled to a requested height
  decimate    vertex clustering on a uniform grid, coarsened until the
              mesh fits the vertex/word budgets (LOD, the honest way)
  shade       flat per-face lambert against a fixed light, baked into the
              face colors -- the machine has no lighting and never will
  chunk       split anything over MESH_NV_MAX vertices into several
              meshes sharing one pose (extra object-list entries)

bake() returns .data-ready word blocks; `zeta mesh model.obj` prints them.
"""
from __future__ import annotations

from pathlib import Path

from . import spec

ONE = 1 << 16


def load_obj(path: str | Path):
    verts, faces = [], []
    for line in Path(path).read_text().splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] == "v":
            verts.append(tuple(float(v) for v in t[1:4]))
        elif t[0] == "f":
            idx = [int(v.split("/")[0]) - 1 for v in t[1:]]
            for k in range(1, len(idx) - 1):          # fan-triangulate
                faces.append((idx[0], idx[k], idx[k + 1]))
    return verts, faces


def normalize(verts, height: float):
    xs, ys, zs = (sorted(v[i] for v in verts) for i in range(3))
    cx, cz = (xs[0] + xs[-1]) / 2, (zs[0] + zs[-1]) / 2
    s = height / max(ys[-1] - ys[0], 1e-9)
    return [((x - cx) * s, (y - ys[0]) * s, (z - cz) * s) for x, y, z in verts]


def decimate(verts, faces, max_verts: int, max_words: int):
    """Shortest-edge collapse with normal-flip rejection: reduces until
    both budgets hold WITHOUT welding unrelated surfaces together --
    grid clustering merged ears into heads, and a correct z-buffer
    faithfully rendered the resulting self-intersections (boot 10)."""
    import heapq
    V = [list(v) for v in verts]
    F = [list(f) for f in faces]
    alive_v = [True] * len(V)
    alive_f = [True] * len(F)
    vfaces = [set() for _ in V]
    for fi, (a, b, c) in enumerate(F):
        for x in (a, b, c):
            vfaces[x].add(fi)

    def d2(u, v):
        return sum((V[u][i] - V[v][i]) ** 2 for i in range(3))

    def normal(fi, override=None, pos=None):
        a, b, c = F[fi]
        pa = pos if override == a else V[a]
        pb = pos if override == b else V[b]
        pc = pos if override == c else V[c]
        ux = [pb[i] - pa[i] for i in range(3)]
        vx = [pc[i] - pa[i] for i in range(3)]
        return (ux[1] * vx[2] - ux[2] * vx[1],
                ux[2] * vx[0] - ux[0] * vx[2],
                ux[0] * vx[1] - ux[1] * vx[0])

    heap = []
    for fi, (a, b, c) in enumerate(F):
        for u, v in ((a, b), (b, c), (c, a)):
            if u < v:
                heapq.heappush(heap, (d2(u, v), u, v))

    def counts():
        nv = sum(alive_v)
        nf = sum(alive_f)
        return nv, nf, 2 + 3 * nv + 2 * nf

    while heap:
        nv, nf, words = counts()
        if nv <= max_verts and words <= max_words:
            break
        _, u, v = heapq.heappop(heap)
        if not (alive_v[u] and alive_v[v]) or not (vfaces[u] & vfaces[v]):
            continue
        # link condition: vertices adjacent to BOTH u and v must be exactly
        # the opposite corners of their shared faces -- otherwise the
        # collapse pinches the surface into a non-manifold fin whose faces
        # wind backwards (culling then draws them inside out)
        def ring(x):
            return {w for fi in vfaces[x] if alive_f[fi]
                    for w in F[fi]} - {x}
        opp = {w for fi in vfaces[u] & vfaces[v] if alive_f[fi]
               for w in F[fi]} - {u, v}
        if ring(u) & ring(v) != opp:
            continue
        mid = [(V[u][i] + V[v][i]) / 2 for i in range(3)]
        flip = False
        for fi in (vfaces[u] | vfaces[v]) - (vfaces[u] & vfaces[v]):
            if not alive_f[fi]:
                continue
            w = u if fi in vfaces[u] else v
            n0 = normal(fi)
            n1 = normal(fi, override=w, pos=mid)
            if sum(n0[i] * n1[i] for i in range(3)) <= 0:
                flip = True
                break
        if flip:
            continue
        V[u] = mid
        alive_v[v] = False
        for fi in list(vfaces[v]):
            if not alive_f[fi]:
                continue
            if fi in vfaces[u]:
                alive_f[fi] = False        # shared face degenerates
            else:
                F[fi] = [u if x == v else x for x in F[fi]]
                vfaces[u].add(fi)
        vfaces[v] = set()
        for fi in vfaces[u]:               # refresh candidate edges
            if alive_f[fi]:
                a, b, c = F[fi]
                for p, q in ((a, b), (b, c), (c, a)):
                    if p != q:
                        heapq.heappush(heap, (d2(p, q), min(p, q),
                                              max(p, q)))

    remap, nvts = {}, []
    for i, ok in enumerate(alive_v):
        if ok:
            remap[i] = len(nvts)
            nvts.append(tuple(V[i]))
    nfs, seen = [], set()
    for fi, ok in enumerate(alive_f):
        if not ok:
            continue
        a, b, c = (remap[x] for x in F[fi])
        if len({a, b, c}) == 3 and (a, b, c) not in seen:
            seen.add((a, b, c))
            nfs.append((a, b, c))
    return nvts, nfs


def shade(verts, faces, tint, light=(0.15, 1.0, -0.2)):
    ll = sum(c * c for c in light) ** 0.5
    lx, ly, lz = (c / ll for c in light)
    cols = []
    for a, b, c in faces:
        ux = [verts[b][i] - verts[a][i] for i in range(3)]
        vx = [verts[c][i] - verts[a][i] for i in range(3)]
        n = (ux[1] * vx[2] - ux[2] * vx[1], ux[2] * vx[0] - ux[0] * vx[2],
             ux[0] * vx[1] - ux[1] * vx[0])
        nl = max(sum(v * v for v in n) ** 0.5, 1e-9)
        lam = max(0.0, (n[0] * lx + n[1] * ly + n[2] * lz) / nl)
        k = 0.30 + 0.70 * lam
        r, g, b_ = (min(255, int(t * k)) for t in tint)
        cols.append((r << 16) | (g << 8) | b_)
    return cols


def vertex_shade(verts, faces, tint, light=(0.15, 1.0, -0.2)):
    """Per-vertex lambert from area-weighted averaged normals -- the
    smooth-shading companion to shade(), for OBJ_GOURAUD meshes.

    The light is mostly OVERHEAD on purpose: baked colors rotate with the
    model, and a frontal light makes the far side brighter at some yaws --
    brightness then contradicts depth and correctly-occluded geometry
    reads as popping through (the butt-to-camera bunny illusion). Top
    light keeps brightness yaw-invariant."""
    ll = sum(c * c for c in light) ** 0.5
    lx, ly, lz = (c / ll for c in light)
    acc = [[0.0, 0.0, 0.0] for _ in verts]
    for a, b, c in faces:
        ux = [verts[b][i] - verts[a][i] for i in range(3)]
        vx = [verts[c][i] - verts[a][i] for i in range(3)]
        n = (ux[1] * vx[2] - ux[2] * vx[1], ux[2] * vx[0] - ux[0] * vx[2],
             ux[0] * vx[1] - ux[1] * vx[0])          # area-weighted
        for i in (a, b, c):
            for k in range(3):
                acc[i][k] += n[k]
    cols = []
    for n in acc:
        nl = max(sum(v * v for v in n) ** 0.5, 1e-9)
        lam = max(0.0, (n[0] * lx + n[1] * ly + n[2] * lz) / nl)
        k = 0.25 + 0.75 * lam
        r, g, b = (min(255, int(t * k)) for t in tint)
        cols.append((r << 16) | (g << 8) | b)
    return cols


def bake(verts, faces, tint=(210, 200, 190), height=1.0,
         max_verts=None, max_words=1400, gouraud=False):
    max_verts = max_verts or spec.MESH_NV_MAX
    verts = normalize(verts, height)
    verts, faces = decimate(verts, faces, 4 * max_verts, max_words)
    cols = shade(verts, faces, tint)
    vcols = vertex_shade(verts, faces, tint) if gouraud else None

    chunks, cur_map, cur_f = [], {}, []
    for f, (a, b, c) in enumerate(faces):
        need = sum(1 for i in (a, b, c) if i not in cur_map)
        if len(cur_map) + need > max_verts or len(cur_f) + 1 > spec.MESH_NF_MAX:
            chunks.append((cur_map, cur_f))
            cur_map, cur_f = {}, []
        for i in (a, b, c):
            cur_map.setdefault(i, len(cur_map))
        cur_f.append((cur_map[a], cur_map[b], cur_map[c], cols[f]))
    chunks.append((cur_map, cur_f))

    blocks = []
    for vmap, fl in chunks:
        inv = {l: g for g, l in vmap.items()}
        words = [len(vmap), len(fl)]
        for l in range(len(vmap)):
            x, y, z = verts[inv[l]]
            words += [int(round(x * ONE)), int(round(y * ONE)),
                      int(round(z * ONE))]
        if gouraud:
            for l in range(len(vmap)):
                words.append(vcols[inv[l]])
        for a, b, c, col in fl:
            words += [a | (b << 10) | (c << 20), col]
        blocks.append(words)
    return blocks


def data_lines(blocks, base: int):
    """(.data lines, per-chunk bases) -- feed the bases to OL entries."""
    lines, bases, at = [], [], base
    for words in blocks:
        bases.append(at)
        for o in range(0, len(words), 16):
            vals = " ".join(str(w) for w in words[o:o + 16])
            lines.append(f".data {at + o} {vals}")
        at += len(words)
    return lines, bases, at - base
