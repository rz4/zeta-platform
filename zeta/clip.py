"""clip.py -- the frustum clipper, in view space, integer-exact.

THE OLDEST PLAYER-VISIBLE DEFECT ON THIS MACHINE. A face with any vertex
the rasteriser cannot address is dropped WHOLE, so the ground tile under
the camera vanishes and the backdrop shows through the floor. The player
reported it as "tiles disappear under the camera". It is not a bug in any
one cart; it is a missing stage.

AND "NEAR-PLANE CLIPPING" IS THE WRONG NAME FOR THE FIX. Measured on the
fabric, of 4,167 straddling faces, clipping to z = ZNEAR alone rescues
ZERO -- because every clipped vertex then lands outside the GUARD BAND.
The guard is a SCREEN-space bound (+/-2048 px, the rasteriser's int16
coordinate range), and a vertex a quarter-unit from the eye projects
enormously: at ZNEAR anything past 2 units off-axis is already out.
Raising ZNEAR does not close it either -- swept to 6 units it still loses
25 of 77, and a 6-unit near plane throws away real geometry.

So there are FIVE planes, and the four side ones are the guard band
itself, written in view space. With sx = CX + vx*F/vz and sy = CY -
vy*F/vz, the guard -G <= s < G becomes, multiplying through by vz > 0:

    near    vz - ZNEAR              >= 0
    left    vx*F + (G+CX)*vz        >= 0
    right   (G-CX)*vz - vx*F        >= 0
    bottom  (G+CY)*vz - vy*F        >= 0
    top     vy*F + (G-CY)*vz        >= 0

The CX offset is NOT optional: the screen centre is not the guard's
centre, and a first attempt at these planes that ignored it left 42 of 76
vertices still outside.

THE MARGIN, and why the filed analysis said zero when it is not.
Sutherland-Hodgman places every new vertex EXACTLY ON the plane it
clipped against -- and the guard test is strict on the far side
(`sx < G`), so a vertex exactly at G is still rejected. Integer division
truncates outward on top of that. Clipping to the exact guard leaves 698
vertices outside on the fabric and 84 on the cube; insetting the four
side planes by ONE PIXEL leaves zero on every cart in the suite. The
guard is six screens wide, so a pixel of inset costs nothing that can be
seen, and it is the difference between a clipper that works and one that
merely reports that it does.

EVERYTHING HERE IS EXACT INTEGER ARITHMETIC, because it has to be
reproduced bit-for-bit by silicon. The interpolation is truncating
(spec.tdiv), the plane tests are >= 0 on products that are computed in
full width, and the plane ORDER is legislated -- a different order gives
a different (equally valid) vertex ordering, and the two machines must
agree on which one.

Interpolating in VIEW space rather than screen space is also what makes
the attributes right: view space is affine under the model/camera
transform, so a colour or a UV interpolates linearly along a view-space
edge exactly. Screen space is where that stops being true, which is the
whole reason the crown exists.
"""
from __future__ import annotations

from . import spec

#: the guard band, in subpixels, inset by one pixel -- see the margin
#: note above. This is the number the four side planes are built from.
CLIP_MARGIN = 1 << spec.SUB
F = spec.FOCAL << spec.SUB
G = (spec.GUARD << spec.SUB) - CLIP_MARGIN
CX = (spec.W // 2) << spec.SUB
CY = (spec.H // 2) << spec.SUB

#: (name, a, b, c, d) meaning the plane a*vx + b*vy + c*vz + d >= 0.
#: Every coefficient is a CONSTANT, which is what keeps the plane tests
#: multiplier-free in silicon: a constant times a variable is a handful
#: of shifts and adds, and the DSPs have been 66/66 since the crown.
PLANES = (
    ("near",   0,  0,          1,           -spec.ZNEAR),
    ("left",   F,  0,          G + CX,      0),
    ("right", -F,  0,          G - CX,      0),
    ("bottom", 0, -F,          G + CY,      0),
    ("top",    0,  F,          G - CY,      0),
)


def dist(pl, v) -> int:
    """Signed distance to a plane: >= 0 is inside, and exactly 0 is on
    it. Full-width integer -- the products reach about 2^40 for a world
    the size of the fabric, which is a width the silicon has to carry
    deliberately rather than discover."""
    _, a, b, c, d = pl
    return a * v[0] + b * v[1] + c * v[2] + d


def _lerp(va: int, vb: int, num: int, den: int) -> int:
    """va + (vb - va) * num/den, truncating -- what a hardware divider
    does (spec.tdiv), so the two machines land on the same integer."""
    return va + spec.tdiv((vb - va) * num, den)


def clip(tri):
    """Clip a view-space triangle to the frustum.

    `tri` is three vertices, each (vx, vy, vz, attrs) where attrs is a
    tuple of integers carried along and interpolated (a packed UV word's
    fields, or a colour's channels -- the clipper does not care which,
    which is what keeps it one function instead of three).

    Returns the clipped convex polygon, 0 or 3..7 vertices, in the same
    winding as the input. Fan-triangulate it: v[0], v[i], v[i+1].
    """
    poly = list(tri)
    for pl in PLANES:
        if len(poly) < 3:
            return []
        out = []
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            da, db = dist(pl, a), dist(pl, b)
            if da >= 0:
                out.append(a)
            if (da >= 0) != (db >= 0):
                # the crossing point, on the plane by construction
                out.append((
                    _lerp(a[0], b[0], da, da - db),
                    _lerp(a[1], b[1], da, da - db),
                    _lerp(a[2], b[2], da, da - db),
                    tuple(_lerp(a[3][k], b[3][k], da, da - db)
                          for k in range(len(a[3]))),
                ))
        poly = out
    return poly if len(poly) >= 3 else []


def needs_clip(tri) -> bool:
    """True when any vertex is outside any plane -- the 2.5% of faces
    that pay for the clipper. Every other face takes the path it always
    took, unchanged to the bit, which is the only way a change this deep
    in the pipe can be landed safely."""
    return any(dist(pl, v) < 0 for v in tri for pl in PLANES)


def fan(poly):
    """The polygon as triangles: v0 with each adjacent pair."""
    return [(poly[0], poly[i], poly[i + 1]) for i in range(1, len(poly) - 1)]
