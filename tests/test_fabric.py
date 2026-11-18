"""test_fabric.py -- the world with no edge, and the four claims it makes.

fabric.zol is the first rung of roadmap 10b: a bounded live window over
an unbounded latent world. The claims are cheap to state and easy to get
subtly wrong, so each one is pinned here:

  1. NO EDGE          -- walk anywhere, the ground always brackets you
  2. DETERMINISTIC    -- leave and return, the world regrows IDENTICAL
     REGROWTH            (this is what makes forgetting free, and it is
                          the whole basis of an unbounded world)
  3. COMMITTED EDITS  -- what you planted is still there after the cell
     SURVIVE EVICTION    has left the window entirely
  4. BOUNDED COST     -- the object list never overflows and the frame
                          never runs out of fuel, however busy the world

Claim 2 is the one worth being careful about: it must hold for cells the
machine has never visited AND for cells it has, so the tests compare a
place against itself across a round trip, not against a golden table.
"""
import sys
from pathlib import Path

import pytest

from zeta import asm, spec, vm

CARTS = Path(__file__).parent.parent / "carts"
CART = CARTS / "fabric.zol"
sys.path.insert(0, str(CARTS))
import gen_fabric                                          # noqa: E402

# DERIVED, never copied: retuning the cell size in the generator used to
# leave nine tests asserting against the old one
CELL = 1 << gen_fabric.CELL_SH          # prop cells: 32 units
SPAN = gen_fabric.MESH_SPAN             # ground tiling stride: 48
MARKED_MESH = gen_fabric.MARKED_AT
GROUND = gen_fabric.GROUND_AT
PAD_A = spec.PAD_A


@pytest.fixture(scope="module")
def cart():
    if not CART.exists():                       # generated, not committed
        import subprocess
        import sys
        subprocess.run([sys.executable, "gen_fabric.py"],
                       cwd=CART.parent, check=True)
    return asm.assemble(CART)


def machine(cart):
    return vm.VM(cart)


def tick(m, pad=0, n=1):
    for _ in range(n):
        m.frame(pad)
        m.dma()
        m.overlay()
        m.card()
    assert not m.trapped, "the fabric trapped"
    return m


def place(m, ci, cj):
    """Stand the camera in the middle of world cell (ci, cj)."""
    m.dmem[spec.CAM_X] = (ci * CELL) & spec.WORD_MASK
    m.dmem[spec.CAM_Z] = (cj * CELL) & spec.WORD_MASK


def objects(m):
    n = m.dmem[spec.OL_BASE]
    return [tuple(spec.s32(m.dmem[spec.OL_BASE + 1 + k * 6 + i])
                  for i in range(6)) for k in range(n)]


def props(m):
    """Everything that is not the ground, as a set: the world's content
    at this spot, independent of the order the window happened to emit."""
    return frozenset(o for o in objects(m) if o[0] != GROUND)


# --------------------------------------------------------------------------
# 1. no edge
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ci,cj", [(0, 0), (1, 0), (-1, 3), (40, -40),
                                   (511, 511), (-511, -511)])
def test_the_ground_always_brackets_the_camera(cart, ci, cj):
    """Wherever you stand there is floor under you and floor in all eight
    directions -- which is the whole of what "no edge" means."""
    m = machine(cart)
    place(m, ci, cj)
    tick(m)
    floor = {(o[1], o[3]) for o in objects(m) if o[0] == GROUND}
    assert len(floor) == 9, f"expected a 3x3 block, got {len(floor)}"
    xs = sorted({p[0] for p in floor})
    zs = sorted({p[1] for p in floor})
    assert len(xs) == 3 and len(zs) == 3, "the block is not a 3x3 grid"
    # spaced by exactly one MESH -- not by one cell. Spacing them by the
    # cell while the mesh was wider made the planes overlap, and nothing
    # in the picture showed it because the checker agreed on the overlap.
    for a in (xs, zs):
        assert a[1] - a[0] == SPAN and a[2] - a[1] == SPAN, \
            f"instances are {a[1] - a[0]} apart, mesh is {SPAN}"
    x, z = spec.s32(m.dmem[spec.CAM_X]), spec.s32(m.dmem[spec.CAM_Z])
    assert abs(x - xs[1]) <= SPAN // 2 and abs(z - zs[1]) <= SPAN // 2, \
        "the camera is not standing on the middle instance"


def test_walking_never_leaves_the_floor(cart):
    """The window follows on its own -- 900 frames of walking, and the
    camera is inside the middle instance on every single one."""
    m = machine(cart)
    for _ in range(900):
        tick(m, pad=spec.PAD_UP)
        x = spec.s32(m.dmem[spec.CAM_X])
        z = spec.s32(m.dmem[spec.CAM_Z])
        floor = [o for o in objects(m) if o[0] == GROUND]
        assert any(abs(x - o[1]) <= SPAN // 2 and abs(z - o[3]) <= SPAN // 2
                   for o in floor), "walked off the world"
    assert abs(spec.s32(m.dmem[spec.CAM_Z])) > 50 * 65536, "never moved"


# --------------------------------------------------------------------------
# 2. deterministic regrowth -- the claim the unbounded world rests on
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ci,cj", [(7, 3), (-19, 42), (300, -87)])
def test_a_place_regrows_identical_after_leaving_it(cart, ci, cj):
    m = machine(cart)
    place(m, ci, cj)
    tick(m)
    first = props(m)

    place(m, 0, 0)                       # go somewhere else entirely and
    tick(m, n=30)                        # let the window turn over
    place(m, ci + 200, cj - 150)
    tick(m, n=30)

    place(m, ci, cj)                     # ...and come back
    tick(m)
    assert props(m) == first, "the world did not regrow identical"


def test_regrowth_holds_across_a_fresh_machine(cart):
    """Not merely stable within one run: the SAME place on a machine that
    has never been anywhere else. Nothing is being cached."""
    a, b = machine(cart), machine(cart)
    place(a, 55, -23)
    tick(a)
    tick(b, n=40, pad=spec.PAD_UP)       # b wandered first
    place(b, 55, -23)
    tick(b)
    assert props(a) == props(b)


def test_neighbouring_cells_are_not_all_the_same(cart):
    """A hash that returns the same answer everywhere would pass every
    determinism test above and produce a world of nothing, or a world of
    identical posts on a perfect grid."""
    seen = set()
    m = machine(cart)
    for ci in range(-6, 7):
        for cj in range(-6, 7):
            place(m, ci, cj)
            tick(m)
            for o in props(m):
                seen.add(o)
    meshes = {o[0] for o in seen}
    yaws = {o[4] for o in seen}
    offs = {(o[1] % CELL, o[3] % CELL) for o in seen}
    assert len(meshes) >= 2, "the hash never picks a second colour"
    assert len(yaws) > 20, f"pillars barely turn: {len(yaws)} angles"
    assert len(offs) > 8, f"pillars sit on a grid: {len(offs)} offsets"


# --------------------------------------------------------------------------
# 3. committed edits survive eviction
# --------------------------------------------------------------------------
def plant(m):
    """A is edge-triggered, so a press is down-then-up."""
    tick(m, pad=PAD_A)
    tick(m, pad=0)


def test_a_planted_pillar_survives_leaving_the_window(cart):
    m = machine(cart)
    place(m, 12, -5)
    tick(m)
    before = props(m)
    plant(m)
    after = props(m)
    assert after != before, "planting changed nothing"
    marked = [o for o in after if o[0] == MARKED_MESH]
    assert len(marked) == 1, "no rubedo pillar in the cell under the camera"

    place(m, 12 + 400, -5 - 400)          # far outside the window
    tick(m, n=20)
    assert not [o for o in props(m) if o[0] == MARKED_MESH], "mark followed us"

    place(m, 12, -5)                      # ...and back
    tick(m)
    assert props(m) == after, "the committed edit did not survive"


def test_planting_twice_in_one_cell_does_not_consume_two_slots(cart):
    m = machine(cart)
    place(m, 3, 3)
    for _ in range(4):
        plant(m)
    n_marked = len([o for o in props(m) if o[0] == MARKED_MESH])
    assert n_marked == 1, f"{n_marked} pillars planted in one cell"
    # ...and the ring still has room for seven more distinct cells
    for k in range(7):
        place(m, 3 + 3 * (k + 1), 3)
        plant(m)
    place(m, 3, 3)
    tick(m)
    assert [o for o in props(m) if o[0] == MARKED_MESH], "the first mark was evicted"


def test_the_committed_store_is_bounded_and_forgets_the_oldest(cart):
    """Eight is the budget, stated out loud. The ninth plant costs the
    first -- the machine degrades, it does not grow without limit."""
    m = machine(cart)
    cells = [(20 + 3 * k, 60) for k in range(9)]
    for ci, cj in cells:
        place(m, ci, cj)
        plant(m)
    place(m, *cells[0])
    tick(m)
    assert not [o for o in props(m) if o[0] == MARKED_MESH], \
        "the ninth plant did not evict the first"
    place(m, *cells[-1])
    tick(m)
    assert [o for o in props(m) if o[0] == MARKED_MESH], "the newest mark is gone"


def test_a_plant_needs_a_fresh_press(cart):
    """Holding A must not empty the ring by planting every frame."""
    m = machine(cart)
    place(m, 9, 9)
    tick(m, pad=PAD_A, n=30)
    place(m, 9 + 3, 9)
    tick(m, pad=PAD_A)                    # still held: no new plant
    tick(m, pad=0)
    place(m, 9, 9)
    tick(m)
    assert [o for o in props(m) if o[0] == MARKED_MESH], \
        "a held button planted repeatedly and evicted the original"


# --------------------------------------------------------------------------
# 4. bounded cost -- the console says no
# --------------------------------------------------------------------------
def test_the_object_list_never_overflows(cart):
    m = machine(cart)
    for ci in range(-25, 26):
        for cj in (-7, 0, 13):
            place(m, ci, cj)
            tick(m)
            assert m.dmem[spec.OL_BASE] <= spec.OL_MAX, "object list overran"


def test_cells_are_admitted_nearest_first(cart):
    """The order the window emits cells IS the budget policy. While
    OL_MAX was 16 this was provable by exhausting it -- nine ground
    planes left seven slots and the corners fell off the end. At 64 the
    budget no longer bites on a 3x3 window, so the property has to be
    asserted where it actually lives: the emission ORDER. If that is
    nearest-first, then whenever the cap does bind, what it costs is the
    horizon."""
    m = machine(cart)
    ring = [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1),
            (1, 1), (-1, 1), (-1, -1)]
    for ci, cj in ring:
        place(m, ci, cj)
        plant(m)
    place(m, 0, 0)
    tick(m)
    order = [o for o in objects(m) if o[0] != GROUND]
    assert len(order) > 8, f"expected a busy window, got {len(order)}"
    # cell distance of each emitted object, in the order emitted
    dist = [max(abs(round(o[1] / CELL)), abs(round(o[3] / CELL)))
            for o in order]
    assert dist == sorted(dist), f"not nearest-first: {dist}"
    assert dist[0] == 0, "the cell under the camera was not admitted first"


def test_the_cap_is_never_exceeded_however_busy(cart):
    """Whatever the world does, the list stays inside the law."""
    m = machine(cart)
    for ci, cj in [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1),
                   (1, 1), (-1, 1), (-1, -1)]:
        place(m, ci, cj)
        plant(m)
    for ci in range(-12, 13):
        place(m, ci, ci)
        tick(m)
        assert m.dmem[spec.OL_BASE] <= spec.OL_MAX


def test_the_frame_never_runs_out_of_fuel(cart):
    """FUEL is 16384 instructions. A window where every cell is committed
    is the most expensive frame the fabric can ask for -- it must still
    finish, or the cart halts mid-list and the picture tears."""
    m = machine(cart)
    for ci, cj in [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1),
                   (1, 1), (-1, 1), (-1, -1)]:
        place(m, ci, cj)
        plant(m)
    place(m, 0, 0)
    tick(m, n=5)
    assert not m.trapped
    assert m.dmem[spec.OL_BASE] > 9, "the window emitted ground and nothing else"
    assert m.dmem[spec.OL_BASE] <= spec.OL_MAX
