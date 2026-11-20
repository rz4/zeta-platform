"""test_visible.py -- spec.VIS_BASE counts the panel, not itself.

THE FAILURE MODE THIS EXISTS TO CATCH. The count comes off the identity
plane, and so does the outline, and so would any check written the
obvious way -- so a plane that is wrong in both places passes a test
that compares it against itself. `cross` proves the two MACHINES agree;
two machines agreeing about the same wrong number is precisely what it
cannot see.

So the count is checked against something that never touches the plane:
RENDER THE FRAME WITHOUT THE OBJECT AND COUNT THE PIXELS THAT MOVED.

That equals the object's visible pixel count EXACTLY -- no tolerance --
but only where two conditions hold, and both of them had to be found by
running it:

  NO LINES     the outline REPAINTS a pixel at flush without changing
               who OWNS it. A pixel the ground owns, painted over by a
               cube's silhouette, is in the ground's total and does not
               change colour when the ground leaves, because the line is
               still drawn there against nobody. Measured: 78 pixels of
               30,646. Ownership and the colour finally shown are not
               the same question.

  NOTHING OF   removing an object reveals what is behind it, and if that
  ITS COLOUR   is the same colour the pixel does not change. seen.zol
  BEHIND IT    draws every cube from ONE mesh, so an occluder in front
               of a subject hides 269 pixels that are exactly its own
               colour. Nothing is wrong with the count; the check's
               premise is false.

Rather than weaken the assertion to fit a borrowed scene, this file
BUILDS the scene the exact claim needs: cubes far enough apart on the
panel that none is behind another, over a checkered floor no cube's
colour appears in. Then it builds the opposite scene on purpose, to
prove the count falls when something is put in front.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import cabinet, carts, gpu, spec

ONE = 65536
CART = carts.path("seen")


def _meshes():
    """A rendered frame, and the two mesh addresses inside it.

    The cart is a source of GEOMETRY here, not of a scene: its object
    list is thrown away and rebuilt below.
    """
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    m.frame(0)
    b = spec.OL_BASE + 1
    return m, m.vm.dmem[b], m.vm.dmem[b + spec.OL_STRIDE]


def _scene(m, ground, cube, places, drop=None):
    """DMEM holding the floor plus one cube for each (x, z), unlined."""
    d = list(m.vm.dmem)
    d[spec.OL_BASE] = 1 + len(places)
    rec = [(ground, 0, 0, 0)] + [(cube, round(x * ONE), 0, round(z * ONE))
                                 for x, z in places]
    for k, (mesh, x, y, z) in enumerate(rec):
        b = spec.OL_BASE + 1 + k * spec.OL_STRIDE
        d[b], d[b + 1], d[b + 2], d[b + 3] = mesh, x, y, z
        d[b + 4], d[b + 5] = 0, spec.OBJ_CULL      # no OBJ_EDGE: see above
    if drop is not None:
        d[spec.OL_BASE + 1 + drop * spec.OL_STRIDE] = 0   # nothing to walk
    return d


def _render(m, d):
    """Render, and hand back the panel AND the counts it wrote."""
    fb = np.asarray(gpu.render(d, m._cram, m._tex))
    n = min(d[spec.OL_BASE], spec.OL_MAX)
    return fb, [d[spec.VIS_BASE + k] for k in range(n)]


# APART: three cubes side by side at one depth, none behind another.
APART = [(-2.2, 4.0), (0.0, 4.0), (2.2, 4.0)]
# BEHIND: the same three, with a fourth put directly in front of the
# middle one and much closer, so it covers most of it.
BEHIND = APART + [(0.0, 1.2)]


def test_count_is_exactly_what_leaves_with_the_object():
    m, ground, cube = _meshes()
    here, said = _render(m, _scene(m, ground, cube, APART))
    assert len([v for v in said if v]) == 4, f"scene did not draw: {said}"
    for k in range(4):
        gone, _ = _render(m, _scene(m, ground, cube, APART, drop=k))
        moved = int((gone != here).any(axis=2).sum())
        assert said[k] == moved, (
            f"object {k}: VIS_BASE says {said[k]} pixels, removing it "
            f"moves {moved}")


def test_the_count_is_final_visibility_not_pixels_won():
    """A count taken at COMMIT instead of at FLUSH would not drop.

    The middle cube is unchanged between the two scenes -- same pose,
    same triangles, same depth, and it still WINS every pixel it wins,
    because the thing in front of it is drawn afterwards. Only what
    survives to the glass differs. A tally kept where a pixel is
    committed cannot tell these two apart; a tally kept where the band
    is flushed can only tell them apart.
    """
    m, ground, cube = _meshes()
    _, open_ = _render(m, _scene(m, ground, cube, APART))
    _, hidden = _render(m, _scene(m, ground, cube, BEHIND))
    assert hidden[2] < open_[2] / 2, (
        f"putting a cube in front changed the middle one's count from "
        f"{open_[2]} to {hidden[2]} -- it should have roughly halved")
    # ...and the surviving sliver is still exactly what leaves with it
    here, said = _render(m, _scene(m, ground, cube, BEHIND))
    gone, _ = _render(m, _scene(m, ground, cube, BEHIND, drop=2))
    moved = int((gone != here).any(axis=2).sum())
    assert said[2] == moved, (
        f"while covered, VIS_BASE says {said[2]} and removal moves {moved}")
    # the two flanking cubes are untouched by any of it
    assert open_[1] == hidden[1] and open_[3] == hidden[3]


def test_an_object_off_the_panel_counts_nothing():
    """The frustum needs no special case: the pixel simply never lands."""
    m, ground, cube = _meshes()
    _, said = _render(m, _scene(m, ground, cube,
                                [(0.0, 4.0), (0.0, -40.0)]))
    assert said[1] > 200, "the near cube should be plainly visible"
    assert said[2] == 0, f"a cube behind the camera counted {said[2]}"


def test_nothing_claims_more_than_the_panel_has():
    m, ground, cube = _meshes()
    _, said = _render(m, _scene(m, ground, cube, APART))
    assert sum(said) <= spec.W * spec.H, (
        f"{sum(said)} pixels claimed of {spec.W * spec.H}")
    assert all(0 <= v <= spec.VIS_MAX for v in said)


def test_the_accumulator_is_sized_to_the_ol_max_it_was_written_for():
    """The sensor's widths in zgpu.v are literals, and OL_MAX is not.

Every address in the sensor is [5:0] and vzero reads vclr[6]: all
    correct for 64 objects and ALL BREAKING SILENTLY at 128 -- the
    addresses would alias object 64 onto object 0, and the zeroing walk
    would never terminate. Nothing in the RTL notices, because a width
    that fits today's value fits.

    IT HAS ALREADY EARNED ITS KEEP ONCE: it fired the moment 105a'
    moved the tally from a LUTRAM to an M10K and `vsel` became `a_sel`,
    which is exactly the moment somebody should look at these widths
    again rather than a moment to be surprised.

    OL_MAX has moved once already (16 -> 64, build 89) and took the
    object list through AU_BASE when it did. This is the cheap half of
    the guard: if OL_MAX moves again, this fails and points at the three
    lines that have to move with it. The expensive half -- writing them
    as $clog2(OL_MAX) -- costs a place-and-route to land and belongs to
    the next build that touches this file for another reason.
    """
    rtl = (Path(__file__).resolve().parents[1] / "silicon" / "zgpu.v"
           ).read_text()
    assert spec.OL_MAX == 64, (
        f"OL_MAX is {spec.OL_MAX}; zgpu.v's sensor hardcodes 64 -- every "
        f"[5:0] address, vclr[6], and the `vzero` terminator all have to "
        f"widen together")
    for want in ("wire [5:0]  a_sel", "reg  [5:0]  b_sel",
                 "reg  [5:0]  p_sel", "wire [5:0]  vwa",
                 "wire        vzero = !vclr[6]", "reg  [6:0]  vclr"):
        assert want in rtl, (
            f"zgpu.v no longer declares `{want}` -- if the sensor's "
            f"widths were parameterised, delete this test; if they were "
            f"changed by hand, check them against OL_MAX = {spec.OL_MAX}")


def test_the_witness_still_exercises_the_forwarding_hazard():
    """A hazard nothing triggers is a hazard nothing tests.

    Build 105a' moved the tally off a LUTRAM with a combinational read
    (no hazard, 832 ALM) onto an M10K with a registered one (~70 ALM,
    one hazard). A read issued on clock c returns memory as of before
    clock c's write, so it misses exactly one write -- the immediately
    preceding pixel's -- and misses it only when that pixel had the SAME
    OWNER. The silicon forwards one deep.

    `cross` proves the counts, and would catch a broken forward loudly:
    without it only run-STARTS would count, so seen.zol's 35,606 would
    come out as 250. But that argument is only worth anything while the
    witness actually produces long runs. If a future edit turned these
    carts into confetti the gate would keep passing and stop meaning
    anything, which is the failure this file exists to refuse.

    Measured on the flush order -- rows of ZW + 2 words including the
    two guard columns -- both witnesses run at over 99%.
    """
    for name in ("seen", "watched"):
        m = cabinet.VirtualMachine(
            cabinet.load_cart(carts.path(name)))
        for _ in range(3):
            m.frame(spec.PAD_RIGHT)
        idb = np.zeros((spec.H, spec.W), np.int64)
        fb, zb, _sh = gpu.seed(m.vm.dmem, m._cram)
        gpu._geom(fb, zb, m.vm.dmem, None,
                  {"next": 0, "id": -1, "z": 0xFFFF}, m._tex, None, 0, idb)
        pad = np.zeros((spec.H, spec.W + 2), np.int64)
        pad[:, :spec.W] = idb & 0x7F
        seq = pad.reshape(-1)
        counted = seq[1:] != 0
        same = int(((seq[1:] == seq[:-1]) & counted).sum())
        starts = int(((seq[1:] != seq[:-1]) & counted).sum())
        assert same + starts > 5000, f"{name} barely draws anything"
        share = same / (same + starts)
        assert share > 0.90, (
            f"{name} now repeats an owner on only {share:.1%} of counted "
            f"flush beats; the M10K tally's forwarding path is barely "
            f"exercised and `cross` passing no longer proves it")
