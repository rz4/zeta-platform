"""TND's city (games/tnd/city.py): Terminal Limit's generator, ported."""
import collections
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "games" / "tnd"))
import city  # noqa: E402


@pytest.mark.parametrize("seed", [666142, 7, 42])
def test_the_city_is_one_tree_of_streets(seed):
    """A spanning tree over the grid: every node reached, N-1 streets, each
    a step to a grid neighbour -- and every node's piece is what its streets
    say (a dead end, a straight, a corner, a tee or a crossing, turned)."""
    c = city.generate(16, seed)
    n = 256
    edges = {(min(u, m), max(u, m)) for u in range(n) for m in c.adj[u]}
    inside = {e for e in edges if c.plaza[e[0]] >= 0 and c.plaza[e[0]] == c.plaza[e[1]]}
    # (a plaza joins all its own neighbours: an open square, the tree's
    # only loops -- without them it is the spanning tree)
    assert len(edges - inside) <= n - 1 and len(edges) >= n - 1
    dist, _ = city._bfs(c.adj, c.start)
    assert min(dist) == 0 and all(d >= 0 for d in dist)
    for u, m in edges:
        (ux, uy), (mx, my) = c.xy(u), c.xy(m)
        assert abs(ux - mx) + abs(uy - my) == 1
    for v in range(n):
        kind, turn = c.piece(v)
        if kind == city.PLAZA:
            continue
        assert city._turn(_BASE[kind], turn) == c.ways(v)


def test_every_district_opens_into_a_plaza():
    """Plazas and streets: each district's heart is an open square of
    PLAZA_SPAN x PLAZA_SPAN nodes, all in that district, joined inside."""
    c = city.generate(16, 666142)
    seen = set()
    for pid, (x0, y0) in enumerate(c.plazas):
        cells = [(x0 + i) + (y0 + j) * 16 for i in range(city.PLAZA_SPAN)
                 for j in range(city.PLAZA_SPAN)]
        assert all(c.plaza[v] == pid for v in cells)
        seen.add(c.district[cells[0]])
        assert len({c.district[v] for v in cells}) == 1
    assert seen == set(range(c.districts())), "a district has no plaza"


_BASE = {city.DEAD: city.N_, city.STRAIGHT: city.N_ | city.S_,
         city.CORNER: city.N_ | city.E_, city.TEE: city.N_ | city.E_ | city.S_,
         city.CROSS: 15}


def test_the_same_seed_is_the_same_city_and_another_is_not():
    a, b, c = city.generate(16, 7), city.generate(16, 7), city.generate(16, 8)
    assert a.adj == b.adj and a.district == b.district and a.gates == b.gates
    assert a.adj != c.adj


@pytest.mark.parametrize("seed", [666142, 7, 42, 3, 99])
def test_districts_follow_the_route_and_share_the_ground(seed):
    """The route runs START to the CORE along the tree's longest street; it
    enters the districts in order, through numbered gates, danger rising
    from 0 to 11; and no district holds more than a third of the town."""
    c = city.generate(16, seed)
    assert c.route[0] == c.start and c.route[-1] == c.core
    assert c.order == list(range(c.districts()))
    assert sorted(c.gates.values()) == list(range(1, c.districts()))
    assert c.danger[c.start] == 0 and c.danger[c.core] == city.LEVELS - 1
    sizes = collections.Counter(c.district)
    assert c.districts() >= 6 and max(sizes.values()) <= 256 // 3, sizes
    for a, b in zip(c.route, c.route[1:]):
        assert c.danger[b] >= c.danger[a], "danger fell along the route"


def test_only_gates_cross_districts_on_any_seed():
    """Districts are horde units and a gate opens when one is cleared, so a
    street between districts that is not a gate would walk round the fight.
    Over sixty seeds: none, every district has its plaza, and the city is
    still one piece."""
    for seed in range(60):
        c = city.generate(16, seed)
        loose = [(u, m) for u in range(256) for m in c.adj[u]
                 if m > u and c.district[u] != c.district[m] and (u, m) not in c.gates]
        assert not loose, f"seed {seed}: ungated streets between districts {loose}"
        assert {c.district[x + y * 16] for x, y in c.plazas} == set(range(c.districts()))
        dist, _ = city._bfs(c.adj, c.start)
        assert min(dist) >= 0, f"seed {seed}: the city fell apart"
