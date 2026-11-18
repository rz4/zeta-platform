"""test_clip.py -- the frustum clipper's properties, before it is wired.

The one that matters is test_no_output_vertex_is_outside_the_guard. That
is the entire point of the stage: a face survives clipping only if every
vertex it produces is one the rasteriser can actually address. The filed
analysis claimed that was already true at the exact guard, and it is not
-- Sutherland-Hodgman lands new vertices ON the plane and the guard test
is strict on the far side. Hence CLIP_MARGIN, and hence this file.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import clip, spec

F, CXX, CYY = clip.F, clip.CX, clip.CY
GUARD = spec.GUARD << spec.SUB          # the REAL guard, not the inset one


def v(x, y, z, *attrs):
    return (int(x * 65536), int(y * 65536), int(z * 65536), tuple(attrs))


def projects_inside(vt) -> bool:
    """The rasteriser's own admission test, exactly as gpu._geom asks
    it: strict on the far side, which is the detail the margin exists
    for."""
    vx, vy, vz = vt[0], vt[1], vt[2]
    if vz < spec.ZNEAR:
        return False
    sx = CXX + spec.tdiv(vx * F, vz)
    sy = CYY - spec.tdiv(vy * F, vz)
    return -GUARD <= sx < GUARD and -GUARD <= sy < GUARD


# ---------------------------------------------------------------------------
# the property the stage exists for
# ---------------------------------------------------------------------------
def test_no_output_vertex_is_outside_the_guard():
    """Sweep triangles across the near plane at many angles and offsets.
    Every vertex the clipper emits must be one the rasteriser can take."""
    bad = 0
    total = 0
    for zc in (-4, -2, -0.5, 0, 0.2, 0.5, 1, 3):
        for off in (-12, -6, -2, 0, 2, 6, 12):
            for ay in (-8, 0, 8):
                tri = (v(off - 3, ay - 2, zc, 0),
                       v(off + 4, ay - 1, zc + 2, 31),
                       v(off, ay + 5, zc + 6, 17))
                poly = clip.clip(tri)
                for vt in poly:
                    total += 1
                    if not projects_inside(vt):
                        bad += 1
    assert total > 0, "the sweep produced no surviving geometry at all"
    assert bad == 0, f"{bad} of {total} clipped vertices are still outside"


def test_a_face_entirely_behind_the_eye_is_dropped():
    tri = (v(0, 0, -5, 0), v(1, 0, -6, 0), v(0, 1, -7, 0))
    assert clip.clip(tri) == []
    assert clip.needs_clip(tri)


def test_a_face_wholly_inside_is_returned_unchanged():
    """The fast path's guarantee: if nothing needed clipping, nothing
    moved. This is what keeps every existing cart bit-identical."""
    tri = (v(0, 0, 4, 7), v(1, 0, 4, 9), v(0, 1, 4, 11))
    assert not clip.needs_clip(tri)
    assert clip.clip(tri) == list(tri)


def test_a_straddling_face_survives_and_grows_by_at_most_four():
    tri = (v(-1, 0, -1, 0), v(1, 0, 3, 31), v(0, 1, 3, 15))
    poly = clip.clip(tri)
    assert 3 <= len(poly) <= 7          # 3 + one cut per plane
    assert len(clip.fan(poly)) == len(poly) - 2


def test_attributes_interpolate_and_stay_in_range():
    """A clipped vertex's UV must stay inside the source range, or the
    texture unit samples a texel the face never had."""
    tri = (v(-2, 0, -1, 0, 0), v(2, 0, 5, 31, 31), v(0, 2, 5, 31, 0))
    for vt in clip.clip(tri):
        for k in range(2):
            assert 0 <= vt[3][k] <= 31, f"attribute {k} left its range: {vt}"


def test_the_planes_are_all_constant_coefficient():
    """What keeps the plane tests multiplier-free in silicon, where the
    DSPs have been 66/66 since the crown. If a coefficient ever becomes
    a variable this stops being free and the fit is the one that finds
    out."""
    for name, a, b, c, d in clip.PLANES:
        for k in (a, b, c, d):
            assert isinstance(k, int)


def test_the_margin_is_actually_needed():
    """Guard against someone 'simplifying' CLIP_MARGIN to zero: rebuild
    the planes at the exact guard and show vertices escape."""
    exact = tuple((n, a, b, (c + clip.CLIP_MARGIN if n != "near" else c), d)
                  for n, a, b, c, d in clip.PLANES)
    saved = clip.PLANES
    try:
        clip.PLANES = exact
        escaped = 0
        for zc in (-2, -0.5, 0, 0.5):
            for off in (-12, -6, 6, 12):
                tri = (v(off - 3, -2, zc, 0), v(off + 4, -1, zc + 2, 0),
                       v(off, 5, zc + 6, 0))
                escaped += sum(not projects_inside(vt)
                               for vt in clip.clip(tri))
        assert escaped > 0, ("clipping at the exact guard let nothing "
                             "escape -- if that is genuinely true now, "
                             "CLIP_MARGIN can go, but prove it on the "
                             "carts and not just here")
    finally:
        clip.PLANES = saved
