"""world.py -- THE WORLD over the city: the puzzle a game is (docs/TND-WORLD.md).

city.py gives a town: a tree of streets, cut along its route from START to
the CORE into sectors, a gate between each two. That is one chain -- a key,
a gate, the next. The player's frame (2026-11-22): the world of the classic
Resident Evil -- "key puzzles opens routes, shortcuts for back tracking or
hard optional shortcuts to move forward" -- in sectors with more than one
way out, begun in a BUNKER with others scattered, where the route is
planned; and "each game is a random map so the player solves the puzzle".

So, over a city and from the same seed:

    a KEY a gate     lying at a dead end the gate's near side can reach --
                     most often in its own sector, sometimes a sector or two
                     BACK (the walk the back doors are for)
    BUNKERS          the START's dead end, and a dead end off the route in
                     every second sector after it
    BACK DOORS       a street the tree does not have, bolted on its deep
                     side: opened from there, it stays open, and the way back
                     to a bunker is short
    HARD WAYS        a street the tree does not have that skips a gate (and
                     its key): open to anyone, and held -- an elite's pack
    PAR              the fewest blocks from START to the CORE that the keys
                     and bolts allow, the safe way and the hard way: what a
                     game's clock is ranked against

Everything here runs when a cart is built (or a library of worlds is); the
result is a few words a world beside the city's map.
"""
from __future__ import annotations

import heapq
import random
from dataclasses import dataclass, field

import city as _city


@dataclass
class World:
    city: _city.City
    keys: dict[int, int]                 # gate number -> the node its key lies at
    bunkers: list[int]                   # nodes; the first is the START's
    back: list[tuple[int, int]]          # (deep node, near node): bolted on the deep side
    hard: list[tuple[int, int]]          # (from, to): skips a gate; held
    par_safe: int = 0                    # blocks, START to CORE, the gates' way
    par_hard: int = 0                    # ...taking any hard way that helps
    notes: list[str] = field(default_factory=list)


def _tree_dist(c, src):
    return _city._bfs(c.adj, src)[0]


def generate(c: _city.City, seed: int | None = None) -> World:
    rng = random.Random((c.seed if seed is None else seed) * 7919 + 17)
    n, s = len(c.adj), c.size
    on_route = set(c.route)
    sector_of = {d: k for k, d in enumerate(c.order)}          # a district -> its place on the route
    sec = [sector_of[d] for d in c.district]
    gate_edge = {k: e for e, k in c.gates.items() if k}        # gate number -> (u, v)
    dead = [v for v in range(n) if len(c.adj[v]) == 1 and v not in (c.start, c.core)]

    # ---- bunkers: the start, then a dead end well off the route every second sector
    d_route = [min(abs(v % s - r % s) + abs(v // s - r // s) for r in c.route) for v in range(n)]
    bunkers = [c.start]
    for k in range(2, len(c.order), 2):
        here = [v for v in dead if sec[v] == k]
        if here:
            bunkers.append(max(here, key=lambda v: (d_route[v], v)))

    # ---- a key a gate: a dead end its near side reaches, own sector or a little back
    keys, taken = {}, set(bunkers)
    for g in sorted(gate_edge):
        own = g - 1                                            # the sector this gate leaves
        back = max(0, own - rng.choice((0, 0, 0, 1, 1, 2)))
        u, v = gate_edge[g]
        near = u if sec[u] == own else v
        dist = _tree_dist(c, near)
        for want in (back, own, *range(own, -1, -1)):
            pool = [x for x in dead if sec[x] == want and x not in taken]
            if pool:
                keys[g] = max(pool, key=lambda x: (dist[x], x))   # the far end of that sector
                taken.add(keys[g])
                break

    # ---- the streets the tree does not have: grid neighbours it left apart
    def apart(a, b):
        return b not in c.adj[a] and c.plaza[a] < 0 and c.plaza[b] < 0
    spare = [(a, b) for a in range(n) for dx, dy in ((1, 0), (0, 1))
             if a % s + dx < s and a // s + dy < s and apart(a, b := a + dx + dy * s)]

    # BACK DOORS: deep end in a later sector than its near end, and the walk it saves home
    home = [min(_tree_dist(c, b)[v] for b in bunkers) for v in range(n)]
    cand = []
    for a, b in spare:
        deep, near_ = (a, b) if sec[a] > sec[b] else (b, a)
        if sec[deep] > sec[near_] and home[deep] - home[near_] - 1 >= 12:
            cand.append((home[deep] - home[near_] - 1, deep, near_))
    back, used = [], set()
    for save, deep, near_ in sorted(cand, reverse=True):
        if all(abs(deep % s - x % s) + abs(deep // s - x // s) > 3 for x in used):
            back.append((deep, near_))
            used.add(deep)
        if len(back) == 3:
            break

    # HARD WAYS: forward, across exactly one or two gates, and worth at least 8 blocks of the route
    to_core = _tree_dist(c, c.core)
    cand = []
    for a, b in spare:
        frm, to = (a, b) if sec[a] < sec[b] else (b, a)
        skip = sec[to] - sec[frm]
        if skip in (1, 2) and to_core[frm] - to_core[to] - 1 >= 8 and frm not in used and to not in used:
            cand.append((to_core[frm] - to_core[to] - 1, frm, to))
    hard = []
    for save, frm, to in sorted(cand, reverse=True):
        if all(sec[frm] != sec[f] for f, _ in hard):
            hard.append((frm, to))
        if len(hard) == 2:
            break

    w = World(c, keys, bunkers, back, hard)
    w.par_safe = _par(w, use_hard=False)
    w.par_hard = _par(w, use_hard=True)
    return w


def _par(w: World, use_hard: bool) -> int:
    """the fewest blocks from START to the CORE: a gate wants its key in hand
    (picked up by standing on its node), a back door wants to have been
    reached from its deep side; a hard way is a street when use_hard"""
    c = w.city
    key_at = {v: g for g, v in w.keys.items()}
    gate_of = {}
    for (u, v), g in c.gates.items():
        if g:
            gate_of[u, v] = gate_of[v, u] = g
    extra = {v: [] for v in range(len(c.adj))}
    for i, (deep, near_) in enumerate(w.back):
        extra[deep].append((near_, ("open", i)))
        extra[near_].append((deep, ("through", i)))
    if use_hard:
        for frm, to in w.hard:
            extra[frm].append((to, None))
            extra[to].append((frm, None))
    start = (c.start, 0, 0)
    best, heap = {start: 0}, [(0, start)]
    while heap:
        d, (v, keys, doors) = heapq.heappop(heap)
        if v == c.core:
            return d
        if best.get((v, keys, doors), 1 << 30) < d:
            continue
        if v in key_at:
            keys |= 1 << key_at[v]
        steps = [(m, None) for m in c.adj[v]] + extra[v]
        for m, how in steps:
            g = gate_of.get((v, m))
            if g and not keys >> g & 1:
                continue
            nd_ = doors
            if how and how[0] == "open":
                nd_ |= 1 << how[1]
            if how and how[0] == "through" and not doors >> how[1] & 1:
                continue
            st = (m, keys, nd_)
            if d + 1 < best.get(st, 1 << 30):
                best[st] = d + 1
                heapq.heappush(heap, (d + 1, st))
    return -1


def render(w: World, path=None, scale: int = 26):
    """the world as a picture: the city's own map (sectors by their danger),
    and over it the keys (gold, numbered for their gates), the bunkers
    (green), the back doors (blue, the bolt's side dotted) and the hard ways
    (white-hot)"""
    from PIL import Image, ImageDraw
    c = w.city
    s, pad = c.size, scale
    img = Image.new("RGB", (s * scale + 2 * pad, s * scale + 2 * pad + 18), (16, 12, 14))
    g = ImageDraw.Draw(img)

    def at(v):
        x, y = c.xy(v)
        return pad + x * scale + scale // 2, pad + (s - 1 - y) * scale + scale // 2

    def heat(d):
        t = d / (_city.LEVELS - 1)
        return (int(70 + 120 * t), int(26 + 90 * t * t), int(34 + 90 * t ** 3))
    for u in range(s * s):
        for m in c.adj[u]:
            if m > u:
                g.line([at(u), at(m)], fill=heat(max(c.danger[u], c.danger[m])), width=max(2, scale // 4))
    for (x0, y0) in c.plazas:
        a, b = at(x0 + y0 * s), at((x0 + 1) + (y0 + 1) * s)
        g.rectangle([min(a[0], b[0]) - scale // 3, min(a[1], b[1]) - scale // 3,
                     max(a[0], b[0]) + scale // 3, max(a[1], b[1]) + scale // 3], fill=heat(c.danger[x0 + y0 * s]))
    for a, b in zip(c.route, c.route[1:]):
        g.line([at(a), at(b)], fill=(150, 140, 130), width=1)
    for deep, near_ in w.back:
        g.line([at(deep), at(near_)], fill=(90, 150, 255), width=3)
        x, y = at(deep)
        g.ellipse([x - 4, y - 4, x + 4, y + 4], outline=(90, 150, 255))
    for frm, to in w.hard:
        g.line([at(frm), at(to)], fill=(255, 250, 220), width=3)
    for (u, m), k in c.gates.items():
        if not k:
            continue
        (x0, y0), (x1, y1) = at(u), at(m)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        g.rectangle([cx - 5, cy - 5, cx + 5, cy + 5], fill=(200, 30, 30))
        g.text((cx - 3, cy - 6), str(k), fill=(255, 230, 230))
    for k, v in w.keys.items():
        x, y = at(v)
        g.polygon([(x, y - 7), (x + 7, y), (x, y + 7), (x - 7, y)], fill=(235, 190, 40))
        g.text((x - 3, y - 6), str(k), fill=(40, 20, 0))
    for v in w.bunkers:
        x, y = at(v)
        g.rectangle([x - 7, y - 7, x + 7, y + 7], fill=(60, 200, 110))
        g.text((x - 3, y - 6), "B", fill=(0, 30, 10))
    x, y = at(c.core)
    g.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(255, 240, 160))
    g.text((6, s * scale + 2 * pad), f"seed {c.seed}: {len(c.order)} sectors, par {w.par_safe} blocks by the gates, "
                                    f"{w.par_hard} by the hard ways", fill=(220, 210, 190))
    if path:
        img.save(path)
    return img


if __name__ == "__main__":
    import sys
    seeds = [int(a) for a in sys.argv[2:]] or [666142, 7, 9]
    from PIL import Image
    ims = []
    for sd in seeds:
        w = generate(_city.generate(16, sd))
        ims.append(render(w))
        print(f"seed {sd}: sectors {len(w.city.order)}, keys {w.keys}, bunkers {w.bunkers}, back doors {w.back}, "
              f"hard ways {w.hard}, par {w.par_safe} / {w.par_hard} blocks (the route alone is {len(w.city.route) - 1})")
    sheet = Image.new("RGB", (sum(i.width for i in ims), max(i.height for i in ims)), (16, 12, 14))
    x = 0
    for i in ims:
        sheet.paste(i, (x, 0))
        x += i.width
    sheet.save(sys.argv[1] if len(sys.argv) > 1 else "worlds.png")
