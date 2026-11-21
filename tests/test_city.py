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
    assert len(edges) == n - 1
    dist, _ = city._bfs(c.adj, c.start)
    assert min(dist) == 0 and all(d >= 0 for d in dist)
    for u, m in edges:
        (ux, uy), (mx, my) = c.xy(u), c.xy(m)
        assert abs(ux - mx) + abs(uy - my) == 1
    for v in range(n):
        kind, turn = c.piece(v)
        assert city._turn(_BASE[kind], turn) == c.ways(v)


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
