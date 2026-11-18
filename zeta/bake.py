"""bake.py -- offline light, composited by depth (docs/FLIGHT.md, item 10).

The roadmap's flagship: render a scene offline at ANY quality -- hours a
frame if you like -- and bake TWO planes, colour and DEPTH. The blit
seeds both, and live geometry then walks through the result occluded per
pixel. Resident Evil's trick without its mask-rectangle seams, because
this machine has the z-buffer the PS1 lacked.

The mechanism landed with the blit engine and room.zol proved it. What
was missing was the CONTENT PATH: room.zol bakes through the law's own
rasteriser, so the room looks exactly like something Zeta would draw --
which is the one thing a pre-rendered backdrop should not look like.

So this module carries a small offline renderer that is deliberately
nothing like the machine: analytic ray casts, a soft sun sampled over
its disc, hemispherical ambient occlusion, and a sky gradient. None of
it is realtime and none of it needs to be.

THE ONE THING THAT MUST MATCH IS THE CAMERA. A plate composites
correctly only if the offline projection is the machine's own:

    sx = W/2 + vx*FOCAL/vz          so a ray through pixel x is
    sy = H/2 - vy*FOCAL/vz          ((x+0.5-W/2)/F, -(y+0.5-H/2)/F, 1)

and with dir.z == 1 the ray parameter IS the view depth, which is what
the depth plane wants. Get this wrong and the actors float.
"""
from __future__ import annotations

import numpy as np

from . import forge, spec

ONE = 65536


# ---------------------------------------------------------------------------
# the camera: the machine's projection, inverted
# ---------------------------------------------------------------------------
def rays():
    """Direction per pixel, with z fixed at 1 so t is the view depth."""
    y, x = np.mgrid[0:spec.H, 0:spec.W]
    dx = (x + 0.5 - spec.W / 2) / spec.FOCAL
    dy = -(y + 0.5 - spec.H / 2) / spec.FOCAL
    return np.stack([dx, dy, np.ones_like(dx)], axis=-1)


# ---------------------------------------------------------------------------
# scene primitives -- analytic, because offline has no reason to be clever
# ---------------------------------------------------------------------------
class Plane:
    """y = height, facing up."""

    def __init__(self, height, albedo):
        self.h, self.albedo = height, np.asarray(albedo, float)

    def hit(self, o, d):
        dy = d[..., 1]
        t = np.where(np.abs(dy) > 1e-9, (self.h - o[..., 1]) / np.where(
            np.abs(dy) > 1e-9, dy, 1), -1.0)
        n = np.zeros(d.shape)
        n[..., 1] = 1.0
        return t, n


class Box:
    """Axis-aligned slab test."""

    def __init__(self, lo, hi, albedo):
        self.lo = np.asarray(lo, float)
        self.hi = np.asarray(hi, float)
        self.albedo = np.asarray(albedo, float)

    def hit(self, o, d):
        inv = 1.0 / np.where(np.abs(d) > 1e-9, d, 1e-9)
        t0 = (self.lo - o) * inv
        t1 = (self.hi - o) * inv
        tn = np.minimum(t0, t1).max(axis=-1)
        tf = np.maximum(t0, t1).min(axis=-1)
        t = np.where((tf >= np.maximum(tn, 0)), tn, -1.0)
        # the normal is the axis that produced the entry plane
        p = o + d * t[..., None]
        c = (self.lo + self.hi) / 2
        r = (self.hi - self.lo) / 2
        q = (p - c) / np.where(r > 1e-9, r, 1e-9)
        k = np.abs(q).argmax(axis=-1)
        n = np.zeros(d.shape)
        for a in range(3):
            m = k == a
            n[..., a] = np.where(m, np.sign(q[..., a]), n[..., a])
        return t, n


def trace(objs, o, d, tmax=1e9):
    """Nearest hit. Returns (t, normal, albedo, mask)."""
    best_t = np.full(d.shape[:-1], tmax)
    best_n = np.zeros(d.shape)
    best_a = np.zeros(d.shape)
    hit = np.zeros(d.shape[:-1], bool)
    for ob in objs:
        t, n = ob.hit(o, d)
        m = (t > 1e-4) & (t < best_t)
        best_t = np.where(m, t, best_t)
        for a in range(3):
            best_n[..., a] = np.where(m, n[..., a], best_n[..., a])
            best_a[..., a] = np.where(m, ob.albedo[a], best_a[..., a])
        hit |= m
    return best_t, best_n, best_a, hit


def occluded(objs, o, d, dist):
    """Any hit closer than dist -- the shadow query."""
    sh = np.zeros(d.shape[:-1], bool)
    for ob in objs:
        t, _ = ob.hit(o, d)
        sh |= (t > 1e-3) & (t < dist)
    return sh


# ---------------------------------------------------------------------------
# the render: soft sun, hemispherical AO, sky gradient
# ---------------------------------------------------------------------------
def render(objs, eye=(0.0, 1.7, 0.0),
           sun=(0.5, 0.75, -0.42), sun_color=(1.5, 1.32, 1.02),
           sky_lo=(0.10, 0.13, 0.20), sky_hi=(0.30, 0.40, 0.62),
           shadow_samples=12, ao_samples=20, sun_radius=0.09, seed=7):
    """Colour and VIEW DEPTH, at whatever quality you pay for."""
    # `seed` is now unused: both sample sets are packed by construction,
    # so the bake is deterministic without needing to be seeded. Kept in
    # the signature because carts pass it and a signature change is churn
    # for nothing.
    _ = seed
    d = rays()
    # The plate is baked in VIEW space with the eye at the origin looking
    # down +z. The cart must therefore park its camera at exactly this
    # point with yaw/pitch/roll zero, and place live objects in the same
    # world coordinates -- otherwise the actors float off the floor.
    o = np.broadcast_to(np.asarray(eye, float), d.shape).copy()
    t, n, alb, hit = trace(objs, o, d)
    p = o + d * t[..., None]

    L = np.asarray(sun, float)
    L = L / np.linalg.norm(L)
    up = np.array([0.0, 1.0, 0.0])
    tang = np.cross(L, up)
    tang /= np.linalg.norm(tang)
    bit = np.cross(L, tang)

    # ---- THE SAMPLES ARE PACKED, NOT DRAWN --------------------------
    # Both loops below share ONE set of directions across the entire
    # image -- `np.broadcast_to` sends the same ray from every shading
    # point. So there are not 14 samples per pixel that average out;
    # there are FOURTEEN, total, and where they clump every pixel in the
    # picture inherits the clump. With that few, the placement IS the
    # quality, and random placement is the worst way to choose it.
    #
    # Golden-angle packing instead: the sunflower on the disc, the
    # Fibonacci spiral on the sphere. Same count, no clumps, and no RNG
    # -- the bake stops being deterministic-because-seeded and becomes
    # deterministic by construction.
    #
    # WITNESSED ON GLASS: the gain is REAL AND MARGINAL TO THE EYE. The
    # measurement is unambiguous -- RMS 0.0472 against random's 0.0565 to
    # 0.0772, so golden 24 is worth random 64 -- but a player looking at
    # the result reported it as working rather than as better. At 5 bits
    # a channel the quantiser eats most of what was won. That is not an
    # argument against packing the samples (it is free, and it removes
    # the seed dependence), but it does say WHERE THE NEXT BAKE WORK
    # GOES: to the weighting below, which changes the ANSWER, not to more
    # placement, which only changes the noise.
    #
    # WEIGHTING IS DELIBERATELY UNCHANGED. These stay uniform over the
    # hemisphere, exactly as before, so this edit moves ONE variable.
    # (Ambient occlusion properly wants COSINE weighting -- a grazing ray
    # delivers less energy per unit area -- which makes the current
    # figure the wrong integral rather than a noisy estimate of the right
    # one. That is a separate change with a separate look, and it must
    # not be folded in here.)
    GOLD = np.pi * (3.0 - 5.0 ** 0.5)          # 2*pi*(1 - 1/phi)

    # SOFT SHADOW: the sun's disc, sunflower-packed. Sampling the disc
    # rather than its centre is the single thing that most stops a render
    # looking rasterised; packing the samples is what stops FOURTEEN of
    # them looking like fourteen.
    lit = np.zeros(t.shape)
    for i in range(shadow_samples):
        a = i * GOLD
        r = sun_radius * np.sqrt((i + 0.5) / shadow_samples)
        s = L + tang * (r * np.cos(a)) + bit * (r * np.sin(a))
        s = s / np.linalg.norm(s)
        sd = np.broadcast_to(s, d.shape).copy()
        lit += ~occluded(objs, p + n * 1e-3, sd, 1e9)
    lit /= shadow_samples

    # AMBIENT OCCLUSION: every shading point is an observer at the centre
    # of a hemisphere of radius 3.5, and these are its receptors. The
    # Fibonacci sphere places them: z walks the axis in equal steps and
    # the azimuth turns by the golden angle, which is the arrangement a
    # sunflower head uses and the one a retina approximates.
    ao = np.zeros(t.shape)
    for i in range(ao_samples):
        z = 1.0 - 2.0 * (i + 0.5) / ao_samples
        rr = np.sqrt(max(0.0, 1.0 - z * z))
        th = i * GOLD
        v = np.array([rr * np.cos(th), rr * np.sin(th), z])
        vd = np.broadcast_to(v, d.shape).copy()
        flip = (vd * n).sum(-1) < 0
        vd = np.where(flip[..., None], -vd, vd)
        ao += ~occluded(objs, p + n * 1e-3, vd, 3.5)
    ao /= ao_samples

    ndl = np.clip((n * L).sum(-1), 0, 1)
    sky_t = np.clip(n[..., 1] * 0.5 + 0.5, 0, 1)[..., None]
    sky = np.asarray(sky_lo) + (np.asarray(sky_hi)
                                - np.asarray(sky_lo)) * sky_t
    col = alb * (np.asarray(sun_color) * (ndl * lit)[..., None]
                 + sky * ao[..., None])

    # the background: a sky gradient by ray height, and FAR depth
    bg_t = np.clip(d[..., 1] * 1.6 + 0.35, 0, 1)[..., None]
    bg = np.asarray(sky_lo) + (np.asarray(sky_hi)
                               - np.asarray(sky_lo)) * bg_t * 1.7
    col = np.where(hit[..., None], col, bg)
    depth = np.where(hit, t, 1e9)
    # THE SHADOW MASK, which this function has always computed and always
    # thrown away. `lit` is the fraction of the sun's disc that reaches
    # each visible point -- the single most expensive thing in the render
    # -- and until now only its product with ndl survived, baked into the
    # colour. Returned raw it becomes a FIELD the machine can query
    # (spec.PICK_SH), which is how an actor finds out it is standing in
    # shade cast by geometry that exists only in this render.
    #
    # Pixels that hit nothing are LIT: the sky is not in shadow, and a
    # cart querying past the room must not get a dark answer.
    return col, depth, np.where(hit, lit, 1.0)


# ---------------------------------------------------------------------------
# the plate: colour and depth in the machine's own encoding
# ---------------------------------------------------------------------------
def plate(color, depth, lit=None, shadow_at=0.5) -> forge.Plate:
    """Linear colour and VIEW depth -> a BG_SRC plate.

    z16 = view_z >> ZSHIFT with view_z in Q16.16, which is exactly what
    gpu.render computes for a live vertex -- so an actor at the same
    depth as a baked pillar ties, and one in front wins. Anything that
    misses the scene gets ZFAR, so live geometry always draws over sky.
    """
    c = np.clip(color, 0, 1)
    c = np.sqrt(c)                        # a plain gamma, so the darks live
    c5 = np.clip((c * 31 + 0.5).astype(np.int64), 0, 31)
    col555 = (c5[..., 0] << 10) | (c5[..., 1] << 5) | c5[..., 2]

    z = np.asarray(depth, float)
    z16 = np.clip((z * ONE).astype(np.int64) >> spec.ZSHIFT, 0, spec.ZFAR)

    # ONE BIT, and the threshold is the whole quantisation. A pixel is
    # "in shadow" when less than shadow_at of the sun's disc reaches it,
    # so 0.5 means the penumbra splits at its half-light line -- which is
    # where an eye puts the edge of a shadow anyway. Pass lit=None and
    # every bit is zero, which is exactly what every plate baked before
    # this one already is.
    sh = (None if lit is None
          else (np.asarray(lit, float) < shadow_at)
          .astype(np.int64).reshape(-1).tolist())
    return forge.Plate(col555.reshape(-1).tolist(),
                       z16.reshape(-1).tolist(), sh)
