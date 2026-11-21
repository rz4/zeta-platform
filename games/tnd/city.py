"""city.py -- TEAR NOT DEMON's city, generated: Terminal Limit's level
generator (scratch/Z/main/terminal-horizon, game/scenario/generator) ported
for a streamed street map.

Terminal Limit builds a level as a spanning tree over a grid -- a "snake"
Hamiltonian path mutated size**3 times by backbite steps -- scores every
cell by its centrality, puts doors where the score changes, cuts the walkable
remainder into sectors and orders the doors along the route from start to
goal. The same skeleton is a city:

    a grid node        an intersection (or a bend, or a dead end)
    a tree edge        a street between two of them
    DANGER (0..11)     progress along the route: quiet at START, the horde's
                       worst at the CORE (Terminal Limit's FLOW is kept as
                       `flow`, how much of the town passes a street)
    a DISTRICT         a stretch of the route from START to the CORE, with
                       every side street that hangs from it
    a GATE             a street between two districts; the gates on the route
                       from START to the CORE are numbered in order, and a
                       gate opens when its district's horde is cleared
    a PIECE            what stands at a node, from its streets: a dead end, a
                       straight, a corner, a tee or a crossing, and its turn

What is ported and what is not:
  * the generation, step for step: snake_path, mutate_path (the same
    random.Random(seed) and the same choice order), the tree, the root at the
    mutation's last origin, the goal at the farthest node from it;
  * FLOW without networkx: on a tree with every node in the same state,
    percolation centrality is betweenness, which subtree sizes give in O(N)
    (the archive called networkx's O(N*E) version); then the archive's own
    log, normalisation and Fibonacci buckets;
  * NOT its sectors: on a city of 256 they fell into 130 districts, most of
    one node (every dead end scores zero), and the goal was the quietest
    street in town. Districts are stretches of the route instead;
  * NOT Terminal Limit's per-sector scale and teleporting doors: the city is
    one continuous space, every block BLOCK units across.

Everything here runs when the cart is built. The result is a few small
tables; the game streams the pieces near the player (docs/TND-PORT.md).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

FLOW_THRESHOLDS = [3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 0]   # the archive's
LEVELS = len(FLOW_THRESHOLDS)                                       # 12 dangers
BLOCK = 25.0                    # units from one node to the next

# the four ways out of a node, in the order the pieces name them
N_, E_, S_, W_ = 1, 2, 4, 8
DIRS = ((0, 1, N_), (1, 0, E_), (0, -1, S_), (-1, 0, W_))   # (dx, dy, bit)
OPP = {N_: S_, S_: N_, E_: W_, W_: E_}
# piece kinds, by how many ways out and whether two are opposite
DEAD, STRAIGHT, CORNER, TEE, CROSS = range(5)
KIND_NAMES = ("dead end", "straight", "corner", "tee", "crossing")


def snake_path(s: int) -> tuple[list[int], int]:
    """The archive's: a boustrophedon-free 'next pointer' path over s x s."""
    total = s * s
    path = [(i + 1) if (i + 1) % s != 0 else (i + s) for i in range(total)]
    path[-1] = -1
    return path, total - 1


def mutate_path(path: list[int], origin: int, rng: random.Random) -> int:
    """The archive's backbite step, in place: the origin points at a random
    neighbour, which becomes the new origin. -> the origin."""
    s = int(len(path) ** 0.5)
    x, y = origin % s, origin // s
    dx, dy = rng.choice([(0, 1), (-1, 0), (0, -1), (1, 0)])
    nx_, ny_ = x + dx, y + dy
    if 0 <= nx_ < s and 0 <= ny_ < s:
        new_origin = ny_ * s + nx_
        path[origin] = new_origin
        path[new_origin] = -1
        return new_origin
    return origin


@dataclass
class City:
    size: int
    seed: int
    adj: list[list[int]]                 # neighbours of each node
    start: int                           # where play begins (the tree's root)
    core: int                            # the goal: the farthest node from it
    danger: list[int]                    # 0..11 a node
    district: list[int]                  # a district id a node
    gates: dict[tuple[int, int], int]    # (u, v) u < v -> 0 (a district line)
                                         # or 1, 2, ... (in order on the route)
    route: list[int]                     # start .. core
    order: list[int] = field(default_factory=list)   # districts, in the order
                                                     # the route enters them
    flow: list[int] = field(default_factory=list)    # Terminal Limit's centrality

    # ---- what the game needs ----------------------------------------------
    def xy(self, n: int) -> tuple[int, int]:
        return n % self.size, n // self.size

    def ways(self, n: int) -> int:
        """the bits of the streets leaving node n (N_ E_ S_ W_)"""
        x, y = self.xy(n)
        bits = 0
        for m in self.adj[n]:
            mx, my = self.xy(m)
            for dx, dy, b in DIRS:
                if (mx - x, my - y) == (dx, dy):
                    bits |= b
        return bits

    def piece(self, n: int) -> tuple[int, int]:
        """(kind, quarter turns) of the piece at n. The unturned pieces:
        dead end opens N; straight N-S; corner N-E; tee N-E-S (closed W)."""
        bits = self.ways(n)
        k = bin(bits).count("1")
        for turn in range(4):
            b = _turn(bits, -turn)             # undo the turn: is it the base?
            if k == 1 and b == N_:
                return DEAD, turn
            if k == 2 and b == N_ | S_:
                return STRAIGHT, turn
            if k == 2 and b == N_ | E_:
                return CORNER, turn
            if k == 3 and b == N_ | E_ | S_:
                return TEE, turn
            if k == 4:
                return CROSS, 0
        raise ValueError(f"node {n} has no streets")

    def districts(self) -> int:
        return max(self.district) + 1

    def district_danger(self, d: int) -> int:
        return max(self.danger[n] for n in range(len(self.danger)) if self.district[n] == d)


def _turn(bits: int, q: int) -> int:
    """the street bits turned q quarter turns clockwise (N -> E -> S -> W)"""
    q %= 4
    return ((bits << q) | (bits >> (4 - q))) & 15


def _betweenness(adj: list[list[int]], root: int) -> list[float]:
    """Pairs whose path passes through each node, on a tree: for node v,
    the sizes of the pieces the tree falls into without v, multiplied in
    pairs. O(N) from subtree sizes."""
    n = len(adj)
    parent, order, seen = [-1] * n, [], [False] * n
    stack = [root]
    seen[root] = True
    while stack:
        v = stack.pop()
        order.append(v)
        for m in adj[v]:
            if not seen[m]:
                seen[m] = True
                parent[m] = v
                stack.append(m)
    size = [1] * n
    for v in reversed(order):
        if parent[v] >= 0:
            size[parent[v]] += size[v]
    out = []
    for v in range(n):
        parts = [size[m] for m in adj[v] if parent[m] == v]
        if parent[v] >= 0:
            parts.append(n - size[v])
        tot = sum(parts)
        out.append((tot * tot - sum(p * p for p in parts)) / 2)
    return out


def _bfs(adj: list[list[int]], src: int) -> tuple[list[int], list[int]]:
    dist, parent = [-1] * len(adj), [-1] * len(adj)
    dist[src] = 0
    q = [src]
    for v in q:
        for m in adj[v]:
            if dist[m] < 0:
                dist[m] = dist[v] + 1
                parent[m] = v
                q.append(m)
    return dist, parent


def _components(nodes: list[int], adj: list[list[int]], keep) -> list[list[int]]:
    """connected components of the nodes over edges keep(u, v) allows"""
    left, out = set(nodes), []
    while left:
        s = min(left)
        comp, q = [], [s]
        left.discard(s)
        for v in q:
            comp.append(v)
            for m in adj[v]:
                if m in left and keep(v, m):
                    left.discard(m)
                    q.append(m)
        out.append(sorted(comp))
    return out


def _flow(adj: list[list[int]], root: int) -> list[int]:
    """Terminal Limit's FLOW, kept: the archive's log-normalised centrality
    in its Fibonacci buckets, 0..11 -- how much of the town passes a street
    (busy junctions are where a crowd would be)."""
    pc = [math.log(b + 1e-12) for b in _betweenness(adj, root)]
    lo, hi = min(pc), max(pc)
    pc = [(p - lo) / (hi - lo) if hi > lo else 0.0 for p in pc]
    th = FLOW_THRESHOLDS[::-1]
    cs = [sum(th[:k + 1]) / sum(th) for k in range(len(th))][:-1]
    return [sum(1 for t in cs if p > t) for p in pc]


def generate(size: int = 16, seed: int = 666142, districts: int = 8) -> City:
    rng = random.Random(seed)
    path, origin = snake_path(size)
    for _ in range(size ** 3):
        origin = mutate_path(path, origin, rng)
    n = size * size
    adj: list[list[int]] = [[] for _ in range(n)]
    for i, j in enumerate(path):
        if j != -1:
            adj[i].append(j)
            adj[j].append(i)
    for a in adj:
        a.sort()
    # START and the CORE are the ends of the tree's longest street (its
    # diameter: the farthest node from the mutation's origin, then the
    # farthest from that). The archive started at the origin itself; on a
    # city that hung half the town off one node of the route, and no cut
    # along the route could share it out.
    d0, _ = _bfs(adj, origin)
    start = max(range(n), key=lambda v: (d0[v], -v))
    dist, parent = _bfs(adj, start)
    core = max(range(n), key=lambda v: (dist[v], -v))
    # the route, start -> core
    route, v = [], core
    while v != -1:
        route.append(v)
        v = parent[v]
    route.reverse()
    # DANGER AND DISTRICTS FOLLOW THE ROUTE. Terminal Limit's FLOW (the
    # archive's log-normalised centrality in Fibonacci buckets, kept below as
    # `flow` for what a street is worth) puts its peak mid-tree and gives every
    # dead end zero: on 256 nodes it made 130 districts, most of one node, and
    # the core -- a leaf -- the quietest street in town. For a fight to the
    # core, danger is PROGRESS: a node's danger is how far along the route its
    # attachment lies (the route node its branch hangs from), 0 at START to 11
    # at the CORE; the route is cut into DISTRICTS stretches of equal length,
    # and every branch belongs to the stretch it hangs from. A side street is
    # optional ground: its district's danger, its own dead ends.
    on_route = {v: k for k, v in enumerate(route)}
    attach = [-1] * n
    for r in route:
        attach[r] = r
    q = list(route)
    for v in q:
        for m in adj[v]:
            if attach[m] < 0:
                attach[m] = attach[v]
                q.append(m)
    # (cut by GROUND, not by route length: the stretches near the root carry
    # most of the side streets, and equal lengths gave one district 122 of
    # 256 nodes and the last six. Each stretch holds about n / DISTRICTS.)
    nd = max(1, min(districts, len(route)))
    hang = [0] * len(route)
    for v in range(n):
        hang[on_route[attach[v]]] += 1
    cut_at, acc = [], 0
    for k, w in enumerate(hang):
        acc += w
        cut_at.append(min(nd - 1, (acc - 1) * nd // n))
    district = [cut_at[on_route[attach[v]]] for v in range(n)]
    used = sorted(set(district))                  # (a big branch can leap a cut:
    ren = {d: k for k, d in enumerate(used)}      # no empty districts)
    district = [ren[d] for d in district]
    nd = len(used)
    danger = [district[v] * (LEVELS - 1) // max(1, nd - 1) for v in range(n)]
    gates = {}
    order = [0]
    k = 1
    for a, b in zip(route, route[1:]):
        if district[a] != district[b]:
            gates[(min(a, b), max(a, b))] = k
            k += 1
            order.append(district[b])
    flow = _flow(adj, start)
    return City(size, seed, adj, start, core, danger, district, gates, route, order, flow)


def render(city: City, path, scale: int = 24) -> None:
    """The map as a picture: streets in the colour of their district's
    danger (dusk to white-hot), the route in bone, numbered gates in red,
    START and CORE marked."""
    from PIL import Image, ImageDraw
    s, pad = city.size, scale
    img = Image.new("RGB", (s * scale + 2 * pad, s * scale + 2 * pad), (16, 12, 14))
    g = ImageDraw.Draw(img)

    def at(v):
        x, y = city.xy(v)
        return pad + x * scale + scale // 2, pad + (s - 1 - y) * scale + scale // 2

    def heat(d):
        t = d / (LEVELS - 1)
        return (int(90 + 165 * t), int(30 + 150 * t * t), int(36 + 160 * t ** 3))
    for u in range(s * s):
        for m in city.adj[u]:
            if m > u:
                c = heat(max(city.danger[u], city.danger[m]))
                g.line([at(u), at(m)], fill=c, width=max(2, scale // 4))
    for a, b in zip(city.route, city.route[1:]):
        g.line([at(a), at(b)], fill=(230, 220, 200), width=max(1, scale // 10))
    for (u, m), k in city.gates.items():
        (x0, y0), (x1, y1) = at(u), at(m)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        r = scale // 5 if k else scale // 8
        g.rectangle([cx - r, cy - r, cx + r, cy + r], fill=(200, 30, 30) if k else (90, 70, 80))
        if k:
            g.text((cx + r + 1, cy - r - 2), str(k), fill=(255, 180, 180))
    for v, label, col in ((city.start, "START", (120, 220, 140)), (city.core, "CORE", (255, 240, 160))):
        x, y = at(v)
        g.ellipse([x - scale // 3, y - scale // 3, x + scale // 3, y + scale // 3], outline=col, width=2)
        g.text((x + scale // 3, y - scale // 3), label, fill=col)
    img.save(path)


if __name__ == "__main__":
    import sys
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 666142
    c = generate(size, seed)
    kinds = [c.piece(v)[0] for v in range(size * size)]
    print(f"{size}x{size} city, seed {seed}: {c.districts()} districts, "
          f"{sum(1 for k in c.gates.values() if k)} gates on the route "
          f"({len(c.route)} nodes long), pieces "
          + ", ".join(f"{KIND_NAMES[k]} {kinds.count(k)}" for k in range(5)))
    if len(sys.argv) > 3:
        render(c, sys.argv[3])
