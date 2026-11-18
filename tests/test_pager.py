"""test_pager.py -- the index, the window, and the one claim that matters.

E5 and E6. The properties here are not "the code does what the code
does" -- each is a thing that would silently ruin the pager and that no
picture would show:

  A BIJECTION      two cells sharing a slot is a world that overwrites
                   itself, and it would look like corruption a long way
                   from its cause.
  A COLUMN IS ONE  the whole reason height is minor. If it stops being
  RANGE            true the seek counts quietly multiply by eight.
  WASTE NEVER      merging ranges to save seeks must only ever ADD
  DROPS A CELL     cells, never lose one. A lost cell is a hole in the
                   world that appears only when someone walks there.
  AND THE SIZE OF  the whole of "no loading screens". If a step across
  THE WORLD IS NOT an 8-million-cell world ever costs more than a step
  IN THE ANSWER    across a 32-thousand-cell one, the claim is dead --
                   and it dies quietly, because both still work.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta.pager import Pager, hilbert2d, hilbert2d_grid


def test_the_curve_is_a_curve():
    """Consecutive indices are ADJACENT cells. A wrong Hilbert is still
    a bijection and still looks local, which is why this is checked and
    not assumed."""
    for n in (4, 8, 32):
        g = hilbert2d_grid(n)
        assert sorted(g.ravel().tolist()) == list(range(n * n))
        pos = {int(g[z, x]): (x, z) for z in range(n) for x in range(n)}
        for d in range(n * n - 1):
            (x0, z0), (x1, z1) = pos[d], pos[d + 1]
            assert abs(x1 - x0) + abs(z1 - z0) == 1, (
                f"{n}x{n}: index {d} to {d + 1} jumps "
                f"({x0},{z0}) -> ({x1},{z1})")


def test_the_scalar_and_the_table_agree():
    """The machine computes an index a column at a time; the baker lays
    the card out with the table. If they ever disagree the card is
    written in one order and read in another."""
    for n in (8, 64):
        g = hilbert2d_grid(n)
        for z in range(n):
            for x in range(n):
                assert hilbert2d(x, z, n) == int(g[z, x])


def test_every_cell_has_its_own_slot():
    p = Pager(side=16, height=5)
    slots = [p.slot(x, y, z)
             for z in range(16) for x in range(16) for y in range(5)]
    assert sorted(slots) == list(range(p.cells))


def test_a_column_is_always_one_range():
    p = Pager(side=32, height=8)
    for x, z in ((0, 0), (31, 31), (7, 19), (16, 3)):
        start, n = p.column(x, z)
        assert n == p.height
        assert [p.slot(x, y, z) for y in range(p.height)] == \
            list(range(start, start + n))


def test_the_ranges_cover_the_window_exactly():
    p = Pager(side=32, height=4)
    r = 5
    want = set()
    for dz in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dz * dz <= r * r:
                for y in range(p.height):
                    want.add(p.slot((10 + dx) % 32, y, (10 + dz) % 32))
    got = set()
    for start, n in p.resident(10, 10, r):
        got.update(range(start, start + n))
    assert got == want, (
        f"{len(want - got)} cells of the window are in no range, and "
        f"{len(got - want)} cells are read that are not in it")


def test_waste_only_ever_adds():
    """Merging saves seeks by reading MORE. It must never read less."""
    p = Pager(side=64, height=8)
    tight = set()
    for s, n in p.resident(20, 40, 8):
        tight.update(range(s, s + n))
    for waste in (0.1, 0.25, 0.5, 2.0):
        loose = set()
        rr = p.resident(20, 40, 8, waste=waste)
        for s, n in rr:
            loose.update(range(s, s + n))
        assert tight <= loose, (
            f"waste {waste} dropped {len(tight - loose)} cells of the "
            f"window -- a hole nobody sees until they walk into it")
        assert len(rr) <= len(p.resident(20, 40, 8))


def test_a_step_costs_the_same_in_a_world_256_times_larger():
    """THE CLAIM. The rim of a disc grows with its radius and not with
    the plain it sits on, and the index is local, so what a step costs
    must not know how big the world is.
    """
    r, out = 8, {}
    for side in (64, 256, 1024):
        p = Pager(side=side, height=8, words_per_cell=256)
        seeks, words = [], []
        for i in range(12):
            a = (side // 3 + i, side // 2 + (i * 7) % 11)
            rng, _ = p.step(a, (a[0] + 1, a[1]), r)
            s, w = p.cost(rng)
            seeks.append(s)
            words.append(w)
        out[side] = (max(seeks), max(words), p.cells)
    small, big = out[64], out[1024]
    assert big[2] > 250 * small[2], "the worlds are not far enough apart"
    assert big[0] <= small[0] + 1, (
        f"a step in the {big[2]:,}-cell world takes {big[0]} seeks "
        f"against {small[0]} in the {small[2]:,}-cell one")
    assert big[1] == small[1], (
        f"and reads {big[1]:,} words against {small[1]:,}")


def test_standing_still_costs_nothing():
    p = Pager(side=64, height=8)
    rng, evicted = p.step((20, 20), (20, 20), 8)
    assert rng == [] and evicted == 0


# ---------------------------------------------------------------------
# E4: window collapse as ONE LOD
# ---------------------------------------------------------------------
from zeta.pager import Pyramid    # noqa: E402


def _covers(p, cx, cz, R):
    """The set of (level, column-index) the window holds."""
    return {k: set(((p._annulus(cx, cz, R, k) - p._base[k]) // p.height)
                   .tolist())
            for k in range(p.levels)}


def test_the_pyramid_gives_every_cell_its_own_slot():
    p = Pyramid(side=8, height=3, levels=3)
    slots = [p.slot(k, x, y, z)
             for k in range(3)
             for z in range(p.level_side(k))
             for x in range(p.level_side(k))
             for y in range(3)]
    assert sorted(slots) == list(range(p.cells))
    # 1 + 1/4 + 1/16 -- the PARTIAL sum, because there are three levels
    # and not infinitely many. 4/3 is where it is heading, not where it is.
    want = sum(4.0 ** -k for k in range(3))
    assert abs(p.cells / (8 * 8 * 3) - want) < 1e-9


def test_the_rings_tile_with_no_hole():
    """THE ONE THAT WAS WRONG TWICE.

    Every level-0 cell inside the reach must be covered by SOME level.
    Working in each level's own cell coordinates does not achieve this,
    because a level's centre is cx >> k and TRUNCATES, so the discs sit
    up to half a coarse cell off one another: 2,374 uncovered cells the
    first time and 1,609 after an exact children-are-covered test. The
    hole-free radius came out at 46 to 55 where the arithmetic promised
    64 -- a window that lies about how far it sees.

    Several player positions, because the failure depended on where in
    a coarse cell the player stood, and (400, 400) alone would have
    looked fine at some radii.
    """
    p = Pyramid(side=256, height=4, levels=4)
    R = 4
    g = {k: p._g(k) for k in range(p.levels)}
    for cx, cz in ((100, 100), (101, 100), (103, 107), (111, 111),
                   (96, 96), (127, 64)):
        cov = _covers(p, cx, cz, R)
        rad = p.reach(R)
        holes = []
        for dz in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                if dx * dx + dz * dz > rad * rad:
                    continue
                x, z = (cx + dx) % 256, (cz + dz) % 256
                if not any(int(g[k][(z >> k) % p.level_side(k),
                                    (x >> k) % p.level_side(k)]) in cov[k]
                           for k in range(p.levels)):
                    holes.append((dx, dz))
        assert not holes, (
            f"player at ({cx},{cz}): {len(holes)} level-0 cells inside "
            f"the reach of {rad} that no level covers, first at "
            f"{holes[0]}")


def test_reach_doubles_per_level_while_cost_only_adds():
    """The whole point: reach EXPONENTIAL in levels, cost LINEAR.

    Stated as a bounded RATIO first, which was wrong -- the early
    levels are small so the ratio starts at 2.02 and falls away. The
    property is that each level adds a shell of roughly CONSTANT size:
    measured 448, 464, 464, 512 cells while the reach went 8, 16, 32,
    64, 128. A ratio test would have passed or failed on where the
    threshold was put.
    """
    R = 4
    cost, reach = [], []
    for L in (1, 2, 3, 4, 5, 6):
        p = Pyramid(side=1024, height=8, levels=L)
        cost.append(sum(n for _, n in p.resident(400, 400, R)))
        reach.append(p.reach(R))
    for i in range(1, len(reach)):
        assert reach[i] == 2 * reach[i - 1]
    adds = [cost[i] - cost[i - 1] for i in range(2, len(cost))]
    for a in adds:
        assert 0.7 * adds[0] <= a <= 1.4 * adds[0], (
            f"the shells are not a constant size: {adds}")
    # and so: many times the reach for a few times the cost
    assert reach[-1] == 32 * reach[0]
    assert cost[-1] < 8 * cost[0], (
        f"{reach[-1] // reach[0]}x the reach cost "
        f"{cost[-1] / cost[0]:.1f}x")


def test_the_pyramid_sees_further_than_a_flat_window_it_outweighs():
    """flat r=16 does not fit in CRAM and sees 64 cells of world; the
    pyramid must beat that on BOTH counts or it is not worth its 4/3."""
    flat = Pager(side=1024, height=8, words_per_cell=256)
    pyr = Pyramid(side=1024, height=8, levels=5, words_per_cell=256)
    _, fw = flat.cost(flat.resident(400, 400, 16, waste=0.25))
    _, pw = pyr.cost(pyr.resident(400, 400, 4, waste=0.25))
    assert pyr.reach(4) >= 4 * 16, "the pyramid must see much further"
    assert pw < fw / 2, f"...and cost less: {pw:,} against {fw:,}"


def test_a_pyramid_step_does_not_know_the_world_size():
    R, out = 4, {}
    for side in (128, 1024):
        p = Pyramid(side=side, height=8, levels=4, words_per_cell=256)
        w = max(p.cost(p.step((side // 3 + i, side // 2), 
                              (side // 3 + i + 1, side // 2), R)[0])[1]
                for i in range(8))
        out[side] = (w, p.cells)
    assert out[1024][1] > 50 * out[128][1]
    assert out[1024][0] == out[128][0], (
        f"{out[1024][0]:,} words against {out[128][0]:,}")
