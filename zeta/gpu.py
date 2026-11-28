"""gpu.py -- the Zeta GPU, executable spec of the silicon rasterizer + GEOM.

Two passes over DMEM, both painting through the same triangle fill:
  1. the display list at DL_BASE: screen-space triangles (HUDs, 2D games)
  2. the object list at OL_BASE: 3D meshes, transformed exactly as
     spec.py legislates (Q16.16, SIN_Q14, tdiv) and painted in painter's
     order -- no z-buffer, backface cull, whole-face near reject.

Everything is integer: a pixel (x, y) is inside a triangle iff the three
edge functions e_i = (x_{i+1}-x_i)*(y-y_i) - (y_{i+1}-y_i)*(x-x_i) are
all >= 0 or all <= 0. No floats anywhere -- the silicon produces the SAME
integers and the cross demands bit-equal framebuffers, not "similar".

numpy is only an accelerator: the arithmetic is int64 exact.
"""
from __future__ import annotations

import numpy as np

from . import clip, spec
from .spec import s32, tdiv


def _fill(fb, zbuf, x0, y0, x1, y1, x2, y2, c0, cgrad, z0, dzdx, dzdy,
          watch=None, tex=None, fog=None, tint=None, lodspan=False,
          clip=None, naive_clip=False, alpha=None, page=0,
          bmode=0, idbuf=None, oid=0):
    """`clip` restricts the WRITES to a pixel rectangle (x0,y0,x1,y1)
    without changing any of the arithmetic -- which is exactly what a
    tile-based renderer does to a face, and the reason this parameter
    exists (roadmap item 15, the blend-order law).

    THE SPAN LEVEL MUST NOT SEE THE TILE. With OBJ_LODSPAN the mip level
    is held across a row from its FIRST edge-covered pixel; if the tile
    were allowed to shorten the row, each slice would choose its own
    level off its own first pixel and the same face would be textured
    differently either side of a tile seam. So clipping masks coverage
    at the END and leaves the span math face-wide. `naive_clip` is the
    wrong implementation kept runnable on purpose, so the size of that
    mistake can be measured instead of asserted."""
    """Coordinates in SUBPIXEL units; sampling at pixel centers; per-pixel
    plane-interpolated depth, draws iff z_px <= stored (then stores).
    c0 = (r5, g5, b5) at vertex A; cgrad = 3 (dcdx, dcdy) pairs (all zero
    for flat shading, where c0 is just the face color quantized).
    watch = (wy, wx) or None: returns True iff this fill committed that
    pixel (the pick register's law -- equal depth wins, like the test)."""
    lo_x = max(min(x0, x1, x2) >> spec.SUB, 0)
    hi_x = min(max(x0, x1, x2) >> spec.SUB, spec.W - 1)
    lo_y = max(min(y0, y1, y2) >> spec.SUB, 0)
    hi_y = min(max(y0, y1, y2) >> spec.SUB, spec.H - 1)
    if clip is not None and naive_clip:      # the WRONG one, on purpose
        lo_x, lo_y = max(lo_x, clip[0]), max(lo_y, clip[1])
        hi_x, hi_y = min(hi_x, clip[2]), min(hi_y, clip[3])
    if lo_x > hi_x or lo_y > hi_y:
        return False
    # broadcasted axes instead of mgrid: same grid, a fraction of the
    # setup -- this function runs once per triangle per band and the
    # small-triangle case is all overhead
    yy = np.arange(lo_y, hi_y + 1, dtype=np.int64)
    xx = np.arange(lo_x, hi_x + 1, dtype=np.int64)
    ys = ((yy << spec.SUB) + spec.HALF)[:, None]
    xs = ((xx << spec.SUB) + spec.HALF)[None, :]
    e0 = (x1 - x0) * (ys - y0) - (y1 - y0) * (xs - x0)
    e1 = (x2 - x1) * (ys - y1) - (y2 - y1) * (xs - x1)
    e2 = (x0 - x2) * (ys - y2) - (y0 - y2) * (xs - x2)
    covered = ((e0 >= 0) & (e1 >= 0) & (e2 >= 0)) | \
              ((e0 <= 0) & (e1 <= 0) & (e2 <= 0))
    zfp = (z0 << spec.ZFP) + (xs - x0) * dzdx + (ys - y0) * dzdy
    zpx = np.minimum(np.maximum(zfp >> spec.ZFP, 0), spec.ZFAR)
    ecov = covered.copy()      # EDGE coverage: the silicon latches this
                               # at beat 0 and bails at beat 1, so the
                               # span's level is set by the first
                               # edge-covered pixel whether or not it
                               # survives the depth test
    ztile = zbuf[lo_y:hi_y + 1, lo_x:hi_x + 1]
    covered &= zpx <= ztile
    if clip is not None and not naive_clip:
        # mask AFTER the arithmetic: ecov (and so the span level) stays
        # face-wide, and only the writes are confined to the tile
        covered &= ((xx[None, :] >= clip[0]) & (xx[None, :] <= clip[2])
                    & (yy[:, None] >= clip[1]) & (yy[:, None] <= clip[3]))
    tile = fb[lo_y:hi_y + 1, lo_x:hi_x + 1]
    def _fogged(c5, ch):
        """Blend a 5-bit channel toward the fog colour by depth, in
        sixteenths -- the same arithmetic the silicon does at commit."""
        if fog is None:
            return c5
        f5, near, sh = fog
        t = np.minimum(np.maximum((zpx - near) >> sh, 0), 16)
        # 16, not 15: the far plane must reach the fog colour exactly
        return (c5 * (16 - t) + f5[ch] * t) >> 4

    def _put(ch, c5):
        """Commit one channel. Opaque writes the colour; a blended face
        lerps against the pixel already there, in the SAME sixteenths
        the scanout compositor uses (spec.CO_BASE) -- one blend rule in
        this machine, not two. Legal here only because a tile's colour
        is on-die and readable; the CRAM framebuffer never could be,
        which is the whole reason 13b lives at scanout."""
        if alpha is not None:
            d5 = tile[..., ch].astype(np.int64) >> 3      # 5 bits back
            # Both modes are (dst*16 + M*a) >> 4 and differ only in M --
            # which is why the silicon needs one mux and not a second
            # blender. ADD is the mode that can make a pixel BRIGHTER
            # than either operand, so it is the one that has to saturate.
            if bmode == spec.BLEND_ADD:
                c5 = np.minimum(31, (d5 * 16 + c5 * alpha) >> 4)
            else:
                c5 = (d5 * (16 - alpha) + c5 * alpha) >> 4
        tile[..., ch][covered] = ((c5 << 3) | (c5 >> 2))[covered]

    if tex is not None:
        # THE CROWN (spec's perspective law): the channels carry u*w',
        # v*w', w' -- the affine-legal trio -- and every pixel recovers
        # true u,v through the seed-ROM Newton reciprocal, then picks
        # its OWN mip level by the quotient rule (thresholds divided
        # through by W so they become shifts). Both triangles of a flat
        # quad now sample one projective map: the diagonal crease is
        # gone as an identity, not a patch.
        pl = []
        for ch in range(3):
            dcdx, dcdy = cgrad[ch]
            pl.append((c0[ch] << spec.CFP) + (1 << (spec.CFP - 1))
                      + (xs - x0) * dcdx + (ys - y0) * dcdy)
        wc = np.clip(pl[2], 256, (1 << 20) - 1)
        e = np.full(wc.shape, 8, dtype=np.int64)
        for k in range(9, 20):
            e += wc >= (1 << k)
        n = wc << (19 - e)
        r0 = np.asarray(spec.RECIP_ROM, dtype=np.int64)[(n >> 12) & 127]
        r1 = (r0 * ((1 << 29) - r0 * n)) >> 22
        ucfp = [np.clip((np.clip(pl[ch], -(1 << 26), (1 << 26) - 1) * r1
                         + (np.int64(1) << (e + 6))) >> (e + 7), 0, 8191)
                for ch in range(2)]
        m = np.maximum.reduce(
            [np.abs((cgrad[ch][d] << 8) - ucfp[ch] * cgrad[2][d])
             for ch in range(2) for d in range(2)])
        lod = ((m >= (wc << 5)).astype(np.int64) + (m >= (wc << 6))
               + (m >= (wc << 7)))
        if lodspan:            # one level per ROW, held across the span
            anyc = ecov.any(axis=1)
            first = np.argmax(ecov, axis=1)
            held = lod[np.arange(lod.shape[0]), first]
            lod = np.where(anyc[:, None], held[:, None], lod)
        u5, v5 = ucfp[0] >> spec.CFP, ucfp[1] >> spec.CFP
        texel = tex[page * spec.TEX_STRIDE
                    + np.asarray(spec.TEX_MIP_OFF, dtype=np.int64)[lod]
                    + (v5 >> lod) * (spec.TEX_W >> lod) + (u5 >> lod)]
        for ch, sh in enumerate((10, 5, 0)):
            t5 = (texel >> sh) & 0x1F
            if tint is not None:              # THE TINT: a lit texture.
                t5 = ((tint[ch] + 1) * t5) >> 5   # (t+1) so 31 is exact
            _put(ch, _fogged(t5, ch))
    else:
        for ch in range(3):
            dcdx, dcdy = cgrad[ch]
            cfp = ((c0[ch] << spec.CFP) + (1 << (spec.CFP - 1))
                   + (xs - x0) * dcdx + (ys - y0) * dcdy)
            c5 = np.minimum(np.maximum(cfp >> spec.CFP, 0), 31)
            if tint is not None:      # OBJ_OTINT: a lit ACTOR, not a
                c5 = ((tint[ch] + 1) * c5) >> 5    # lit surface
            _put(ch, _fogged(c5, ch))
    # A BLENDED FACE TESTS DEPTH BUT NEVER WRITES IT. That is what makes
    # the composite order equal to the display-list order the cart chose
    # -- blended faces cannot occlude each other, so nothing depends on
    # which of them the rasteriser happened to reach first.
    if alpha is None:
        ztile[covered] = zpx[covered]
        # THE IDENTITY PLANE. Only an OPAQUE face stamps it, and for the
        # same reason it writes depth: a blended face is a veil over
        # something else, and outlining the veil would draw a line around
        # a pane of glass rather than around the thing behind it.
        if idbuf is not None:
            idbuf[lo_y:hi_y + 1, lo_x:hi_x + 1][covered] = oid
    if watch is not None:
        wy, wx = watch
        if lo_y <= wy <= hi_y and lo_x <= wx <= hi_x:
            return bool(covered[wy - lo_y, wx - lo_x])
    return False


def _rot(x: int, z: int, yaw: int) -> tuple[int, int]:
    """Yaw rotation, wrapped to the silicon's 32-bit datapath."""
    s = spec.SIN_Q14[yaw & 1023]
    c = spec.SIN_Q14[(yaw + 256) & 1023]
    return s32((x * c - z * s) >> 14), s32((x * s + z * c) >> 14)


# ---- the vertex walk, vectorised ------------------------------------------
# The SAME arithmetic as _rot/_project above, over a whole mesh at once.
# Every intermediate is int64 (the widest product is 2^45, the Q14 sine
# against a 32-bit coordinate), every wrap lands exactly where the scalar
# s32 lands, shifts are arithmetic in numpy as in Python, and the divide
# reproduces spec.tdiv's truncation toward zero against an always-positive
# vz. This exists because the film's 692-triangle rig walked one vertex at
# a time at 40 fps; the gates (every cart's framebuffer, and the silicon
# cross) are what hold it to the scalar law bit for bit.

def _w32(a):
    """s32, vectorised: wrap int64 to the silicon's 32-bit datapath."""
    return ((a + (1 << 31)) & 0xFFFFFFFF) - (1 << 31)


def _rotv(x, z, yaw: int):
    s = spec.SIN_Q14[yaw & 1023]
    c = spec.SIN_Q14[(yaw + 256) & 1023]
    return _w32((x * c - z * s) >> 14), _w32((x * s + z * c) >> 14)


def _tdivv(num, den):
    """tdiv over arrays, den > 0: truncate toward zero."""
    return np.where(num >= 0, num // den, -((-num) // den))


def _cart_mesh(dmem, cram, mb, used):
    """spec.OBJ_CART: the descriptor at mb -> (V, face index words, face
    rgb words), read from the cart's segment; None if any of it falls
    outside its memory. The colours come back as the 24-bit words a flat
    face has always carried (5 bits a channel, << 3), so everything past
    this point is the path that was already built."""
    if cram is None or not 0 <= mb <= spec.DMEM_WORDS - spec.CMESH_WORDS:
        return None
    w0, vsrc, fsrc, csrc, sh = (s32(v) for v in dmem[mb:mb + spec.CMESH_WORDS])
    nv, nf = w0 & 0xFFFF, (w0 >> 16) & 0xFFFF
    if nv > spec.MESH_NV_MAX or nf > spec.MESH_NF_MAX or not 0 <= sh <= 15:
        return None
    seg = s32(dmem[spec.SEG_BASE])
    spans = ((vsrc, (nv * 3 + 1) // 2), (fsrc, nf), (csrc, (nf + 1) // 2))
    for src, n in spans:                       # the mover's own bounds
        if src < 0 or src + seg < 0 or src + seg + n > spec.CRAM_WORDS:
            return None
    # THE STORE (spec.CM_VMAX, CM_FMAX): admitted in list order while the
    # frame's totals fit; one that would not draws nothing and takes no room
    if used[0] + nv > spec.CM_VMAX or used[1] + nf > spec.CM_FMAX:
        return None
    used[0] += nv
    used[1] += nf

    def words(src, n):                         # (past what the cart carried: zeros)
        w = np.zeros(n, np.int64)
        got = cram[src + seg:src + seg + n]
        w[:len(got)] = got
        return w & 0xFFFFFFFF

    def halves(src, n):
        w = words(src, (n + 1) // 2)
        return np.stack((w & 0xFFFF, w >> 16), 1).reshape(-1)[:n]
    v = halves(vsrc, nv * 3)
    V = (((v ^ 0x8000) - 0x8000) << sh).reshape(nv, 3)
    c = halves(csrc, nf)
    rgb = (((c >> 10) & 31) << 19) | (((c >> 5) & 31) << 11) | ((c & 31) << 3)
    return V, words(fsrc, nf).tolist(), rgb.tolist()


def _verts(V, nv, yaw, pit, rol, ox, oy, oz,
           cx, cy, cz, cyaw, cpit, crol):
    """The per-vertex transform chain for one object: model rotations,
    placement, the camera, projection and the guard band -- exactly the
    walk the scalar loop performed, returned as (pts, vws)."""
    vx, vy, vz = _w32(V[:, 0]), _w32(V[:, 1]), _w32(V[:, 2])
    vx, vy = _rotv(vx, vy, rol)                # model: roll (x,y),
    vy, vz = _rotv(vy, vz, pit)                # pitch (y,z),
    vx, vz = _rotv(vx, vz, yaw)                # then yaw (x,z)
    vx, vy, vz = _w32(vx + ox), _w32(vy + oy), _w32(vz + oz)
    vx, vy, vz = _w32(vx - cx), _w32(vy - cy), _w32(vz - cz)
    vx, vz = _rotv(vx, vz, (1024 - cyaw) & 1023)   # world -> camera
    vy, vz = _rotv(vy, vz, (1024 - cpit) & 1023)   # then the pitch
    vx, vy = _rotv(vx, vy, (1024 - crol) & 1023)   # ...then the BANK (see
                                                   # the scalar note)
    vws = [(int(a), int(b), int(c)) for a, b, c in zip(vx, vy, vz)]
    near = vz < spec.ZNEAR
    vzs = np.where(near, 1, vz)                # placeholder; masked out
    sx = (spec.W // 2 << spec.SUB) + \
        _tdivv(vx * (spec.FOCAL << spec.SUB), vzs)
    sy = (spec.H // 2 << spec.SUB) - \
        _tdivv(vy * (spec.FOCAL << spec.SUB), vzs)
    g = spec.GUARD << spec.SUB
    z16 = np.minimum(vz >> spec.ZSHIFT, spec.ZFAR)
    w = np.maximum(spec.PERSP_NUM // vzs, 1)
    bad = near | (sx < -g) | (sx >= g) | (sy < -g) | (sy >= g)
    cols = np.stack((sx, sy, z16, w), 1).tolist()
    return [None if b else tuple(r) for b, r in zip(bad.tolist(), cols)], vws


def _project(v):
    """View space to the rasteriser's four numbers, exactly as the vertex
    walk does it. Written out again rather than shared, because the fast
    path's arithmetic is load-bearing for every cart ever shipped and is
    not going to be refactored on the way past."""
    vx, vy, vz = v[0], v[1], v[2]
    return ((spec.W // 2 << spec.SUB) + tdiv(vx * (spec.FOCAL << spec.SUB), vz),
            (spec.H // 2 << spec.SUB) - tdiv(vy * (spec.FOCAL << spec.SUB), vz),
            min(vz >> spec.ZSHIFT, spec.ZFAR),
            max(tdiv(spec.PERSP_NUM, vz), 1))


def _clipped(vws, a, b, c, vattr, rgb=0):
    """The slow path: a face the rasteriser could not address. Cut it
    against the five planes, fan the survivor, and project the pieces.

    Reached only by faces that were being DROPPED, so it cannot change
    anything that renders today -- it can only add what was missing."""
    poly = clip.clip(((*vws[a], vattr(a, rgb)), (*vws[b], vattr(b, rgb)),
                      (*vws[c], vattr(c, rgb))))
    if len(poly) < 3:
        return []
    return [(_project(p), _project(q), _project(r), p[3], q[3], r[3])
            for p, q, r in clip.fan(poly)]


def _geom(fb, zbuf, dmem, watch, pick, tex=None, fog=None,
          lod_flat=0, idbuf=None, cram=None) -> None:
    n = min(dmem[spec.OL_BASE], spec.OL_MAX)
    cx, cy, cz = (s32(dmem[c]) for c in (spec.CAM_X, spec.CAM_Y, spec.CAM_Z))
    cyaw = dmem[spec.CAM_YAW] & 1023
    cpit = dmem[spec.CAM_PITCH] & 1023
    crol = dmem[spec.CAM_ROLL] & 1023
    cm_used = [0, 0]                           # spec.OBJ_CART's store, this frame
    for o in range(n):
        base = spec.OL_BASE + 1 + o * spec.OL_STRIDE
        mb, ox, oy, oz, ang, flags = (s32(v) for v in
                                      dmem[base:base + spec.OL_STRIDE])
        yaw, pit, rol = ang & 1023, (ang >> 10) & 1023, (ang >> 20) & 1023
        if not 0 <= mb < spec.DMEM_WORDS - 2:
            continue
        cart = bool(flags & spec.OBJ_CART)
        if cart:                           # spec.OBJ_CART: the mesh is in the cart
            cm = _cart_mesh(dmem, cram, mb, cm_used)
            if cm is None:
                continue
            V, fidx, frgb = cm
            nv, nf = len(V), len(fidx)
            flags &= ~(spec.OBJ_GOURAUD | spec.OBJ_LIT | spec.OBJ_TEX | spec.OBJ_TINT | spec.OBJ_BLEND)
        else:
            nv, nf = dmem[mb], dmem[mb + 1]
        gour = bool(flags & spec.OBJ_GOURAUD)
        lit = bool(flags & spec.OBJ_LIT)
        texd = bool(flags & spec.OBJ_TEX) and tex is not None
        vcw = nv if (gour or lit or (flags & spec.OBJ_TEX)) else 0
        if not cart:
            if nv > spec.MESH_NV_MAX or nf > spec.MESH_NF_MAX or \
               mb + 2 + nv * 3 + vcw + nf * 2 > spec.DMEM_WORDS:
                continue                   # a mesh outside DMEM is skipped
            V = np.array(dmem[mb + 2:mb + 2 + nv * 3], np.int64).reshape(nv, 3)
        # the vertex walk, whole-mesh at once (see _verts): the same
        # rotations in the same order -- roll, pitch, yaw, place, camera,
        # then the BANK last and about the view axis, which is what makes
        # it a bank and not a yaw -- with the gates holding it to the
        # scalar arithmetic bit for bit
        pts, vws = _verts(V, nv, yaw, pit, rol, ox, oy, oz,
                          cx, cy, cz, cyaw, cpit, crol)
        cbase = mb + 2 + nv * 3
        fbase = cbase + vcw

        def vattr(i, rgb=0):
            """What a vertex carries through the clipper, unpacked into
            fields the interpolation can act on. WHICH fields depends on
            the branch that will actually run below -- a mesh with
            OBJ_TEX set but no texture page loaded falls through to the
            gouraud branch and reads those same words as COLOURS, which
            is long-standing behaviour and is preserved here rather than
            tidied."""
            if texd:
                uw = dmem[cbase + i]
                return (uw & 31, (uw >> 8) & 31)
            if lit:
                # spec.OBJ_LIT: the word is a NORMAL, and it becomes a
                # COLOUR right here -- before the clipper, so that from
                # this point on a lit face IS a gouraud face and travels
                # the path that was already built.
                #
                # It has to happen before the cut in any case: a clipped
                # vertex is a new vertex with no normal of its own, and
                # interpolating a normal across the cut would need it
                # renormalised. Interpolating the COLOUR it turned into
                # is exactly what gouraud already does.
                #
                # Scaling is linear, so converting then cutting and
                # cutting then converting agree -- except in the low bit
                # the >>5 throws away. Converting first is the one that
                # leaves the silicon with no new attribute class to
                # carry.
                lv = spec.light_of(dmem[cbase + i], dmem)
                return tuple(min(255, (((rgb >> sh) & 0xFF) * lv) >> 5)
                             for sh in (16, 8, 0))
            if gour:
                cw = dmem[cbase + i]
                return ((cw >> 16) & 0xFF, (cw >> 8) & 0xFF, cw & 0xFF)
            return ()
        for f in range(nf):
            # the pick id is the face's place in the WALK, drawn or not:
            # a stable, mesh-relative identity (a camera-dependent count
            # of survivors painted the neighbor -- the off-by-one-tile
            # the player caught on boot 63's glass)
            fid = pick["next"]
            pick["next"] += 1
            if cart:
                idx, rgb = fidx[f], frgb[f]
            else:
                idx = dmem[fbase + f * 2]
                rgb = s32(dmem[fbase + f * 2 + 1])
            # THE LIGHT ON THIS FACE. OBJ_OTINT takes it from the object
            # (one word, so an actor can be re-lit per frame); OBJ_TINT
            # takes it from the face (baked in the mesh). The object wins
            # when both are set, because the object is the later word.
            # OBJ_TINT stays TEXTURED-ONLY: it has meant that since it
            # landed, and lighting a flat face that never asked would
            # move pictures that render today.
            otnt = (tuple((flags >> sh) & 0x1F for sh in (27, 22, 17))
                    if flags & spec.OBJ_OTINT else None)
            # WHO OWNS THIS PIXEL, for the outline pass. Object index + 1
            # so that 0 means "nobody asked" -- the clear, the backdrop,
            # the display list, and every object without OBJ_EDGE. Two
            # DIFFERENT outlined objects touching is an edge too, which
            # falls out of "the owners differ" without a special case.
            # Index + 1 for EVERY object, with the high bit saying
            # whether this owner asked for a line. The plane used to hold
            # 0 for un-outlined objects, which conflated "nobody asked"
            # with "nothing here" and made VIS_BASE impossible: an object
            # that wants to know how visible it is should not have to be
            # outlined to find out.
            oid = (o + 1) | (0x80 if flags & spec.OBJ_EDGE else 0)
            tnt = otnt or (tuple(((rgb >> k) & 0xFF) >> 3
                                 for k in (16, 8, 0))
                           if flags & spec.OBJ_TINT else None)
            a, b, c = idx & 1023, (idx >> 10) & 1023, (idx >> 20) & 1023
            if a >= nv or b >= nv or c >= nv:
                continue
            # ---- THE CLIPPER (zeta/clip.py) -------------------------
            # A face with a vertex the rasteriser cannot address used to
            # be dropped WHOLE -- the ground tile under the camera
            # vanishing, which the player reported as "tiles disappear".
            # Now it is cut against the five planes instead.
            #   THE FAST PATH IS THE OLD PATH, BIT FOR BIT. A face whose
            # three vertices already project inside the guard takes the
            # branch it always took and never meets the clipper, so
            # nothing that renders today can move. The only faces that
            # change are the ones that were invisible.
            if pts[a] is not None and pts[b] is not None \
                    and pts[c] is not None:
                tris = [(pts[a], pts[b], pts[c],
                         vattr(a, rgb), vattr(b, rgb), vattr(c, rgb))]
            else:
                tris = _clipped(vws, a, b, c, vattr, rgb)
            hit = False
            for ((x0, y0, za, wa), (x1, y1, zb, wb), (x2, y2, zc, wg),
                 at0, at1, at2) in tris:
                # FRUSTUM CULL. The guard band is +/-2048 PIXELS -- six screens
                # either side -- so a face far off to the left passes every
                # check above and pays full setup to paint nothing. Measured
                # on the fabric: 928 of 1,385 faces, 67%. The id was taken
                # BEFORE this, so the pick register's walk-order numbering is
                # unchanged and a cart's face ids do not shift.
                if (max(x0, x1, x2) < 0 or min(x0, x1, x2) >= SCR_W
                        or max(y0, y1, y2) < 0 or min(y0, y1, y2) >= SCR_H):
                    continue
                area = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
                # BLENDED FACES COMPOSITE IN DISPLAY-LIST ORDER and never
                # write depth (spec's blend-order law). alpha is None for an
                # ordinary face, which is what keeps every existing cart
                # byte-identical.
                # WHICH PAGE this object samples: flags 10:8, zero for every
                # cart written before there was more than one.
                page = spec.tex_page(flags >> spec.OBJ_PAGE_SHIFT)
                alpha = (min(16, (rgb >> spec.BLEND_A_SHIFT)
                                 & spec.BLEND_A_MASK)
                         if flags & spec.OBJ_BLEND else None)
                bmode = ((rgb >> spec.BLEND_MODE_SHIFT)
                         & spec.BLEND_MODE_MASK)
                if flags & spec.OBJ_CULL and area <= 0:
                    continue                   # front faces (CCW model winding,
                                               # outward normals) project to
                                               # area > 0 after the y flip; the
                                               # old >= kept the BACK faces and
                                               # rendered every mesh hollow
                if area == 0:
                    dzdx = dzdy = 0
                else:
                    cl = spec.ZGRAD_MAX
                    dzdx = max(-cl, min(cl, tdiv(
                        ((zb - za) * (y2 - y0) - (zc - za) * (y1 - y0))
                        << spec.ZFP, area)))
                    dzdy = max(-cl, min(cl, tdiv(
                        ((zc - za) * (x1 - x0) - (zb - za) * (x2 - x0))
                        << spec.ZFP, area)))
                if texd:
                    # the octave normalize: the nearest vertex's w lands in
                    # [2^11, 2^12) (msb of the OR is msb of the max), so
                    # u5*w' stays under 17 bits -- the interpolators as-is
                    sh = (wa | wb | wg).bit_length() - 12
                    wp = [(w >> sh) if sh >= 0 else (w << -sh)
                          for w in (wa, wb, wg)]
                    cors = [(at[0] * wp[i], at[1] * wp[i], wp[i])
                            for i, at in enumerate((at0, at1, at2))]
                    c0 = cors[0]
                    cgrad = []
                    for ch in range(3):
                        va_, vb_, vc_ = cors[0][ch], cors[1][ch], cors[2][ch]
                        if area == 0:
                            cgrad.append((0, 0))
                            continue
                        cl = spec.ZGRAD_MAX
                        dx = max(-cl, min(cl, tdiv(
                            ((vb_ - va_) * (y2 - y0) - (vc_ - va_) * (y1 - y0))
                            << spec.CFP, area)))
                        dy = max(-cl, min(cl, tdiv(
                            ((vc_ - va_) * (x1 - x0) - (vb_ - va_) * (x2 - x0))
                            << spec.CFP, area)))
                        cgrad.append((dx, dy))
                    # THE FACE'S ALPHA (spec.OBJ_BLEND): sixteenths in bits
                    # 28:24 of the colour word, which every mesh ever written
                    # leaves at zero -- hence the opt-in flag, and hence a
                    # blended object that forgets to set alpha is invisible
                    # rather than opaque. Same shape as OBJ_TINT.
                    hit = _fill(fb, zbuf, x0, y0, x1, y1, x2, y2,
                                c0, tuple(cgrad), za, dzdx, dzdy, watch,
                                tex, fog, tnt,
                                bool(flags & spec.OBJ_LODSPAN),
                                alpha=alpha, bmode=bmode, idbuf=idbuf, oid=oid, page=page) or hit
                elif gour or lit:
                    c0 = tuple(v8 >> 3 for v8 in at0)
                    far = bool(lod_flat) and za >= lod_flat
                    cgrad = []
                    for k in range(3):
                        if far:          # past LOD_FLAT the colour is vertex
                            cgrad.append((0, 0))   # A's, held flat: the fog is
                            continue               # already erasing the rest
                        va = at0[k] >> 3
                        vb = at1[k] >> 3
                        vc = at2[k] >> 3
                        if area == 0:
                            cgrad.append((0, 0))
                            continue
                        cl = spec.ZGRAD_MAX
                        dx = max(-cl, min(cl, tdiv(
                            ((vb - va) * (y2 - y0) - (vc - va) * (y1 - y0))
                            << spec.CFP, area)))
                        dy = max(-cl, min(cl, tdiv(
                            ((vc - va) * (x1 - x0) - (vb - va) * (x2 - x0))
                            << spec.CFP, area)))
                        cgrad.append((dx, dy))
                    hit = _fill(fb, zbuf, x0, y0, x1, y1, x2, y2,
                                c0, tuple(cgrad), za, dzdx, dzdy, watch,
                                None, fog, otnt, alpha=alpha, bmode=bmode, idbuf=idbuf, oid=oid) or hit
                else:
                    c0 = tuple(((rgb >> sh) & 0xFF) >> 3 for sh in (16, 8, 0))
                    hit = _fill(fb, zbuf, x0, y0, x1, y1, x2, y2,
                                c0, ((0, 0),) * 3, za, dzdx, dzdy, watch,
                                None, fog, otnt, alpha=alpha, bmode=bmode, idbuf=idbuf, oid=oid) or hit
                if hit:
                    pick["id"] = fid
                    pick["z"] = int(zbuf[watch[0], watch[1]])


SCR_W = spec.W << spec.SUB      # the screen in subpixels: what a
SCR_H = spec.H << spec.SUB      # face must touch to be worth setting up


def compose(fb: np.ndarray, dmem: list[int]) -> np.ndarray:
    """The scanout compositor (spec.CO_BASE): rectangles blended over the
    finished picture on its way to the panel, never into the framebuffer.

    This is what the PANEL shows. render() is what the FRAMEBUFFER holds,
    and cross compares framebuffers -- so cross is correctly blind to
    this and glass is not. Rectangles do not blend with each other: the
    LAST live one covering a pixel wins, which is the law that lets the
    silicon be a priority mux and one lerp.
    """
    n = s32(dmem[spec.CO_BASE])
    if not 0 < n <= spec.CO_MAX:
        return fb
    out = fb.copy()
    ys = np.arange(spec.H)[:, None]
    xs = np.arange(spec.W)[None, :]
    for k in range(n):
        b = spec.CO_BASE + 1 + k * spec.CO_STRIDE
        wx, wy, wc = (s32(dmem[b + i]) for i in range(3))
        x0, x1 = wx & 0x3FF, (wx >> 10) & 0x3FF
        y0, y1 = wy & 0x3FF, (wy >> 10) & 0x3FF
        a = (wc >> 24) & 0x1F
        if a == 0 or x1 < x0 or y1 < y0:
            continue
        a = min(a, 16)
        inside = ((xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1))
        if not inside.any():
            continue
        for ch, sh in enumerate((16, 8, 0)):
            c5 = ((wc >> sh) & 0xFF) >> 3
            # the pixel's own 5 bits, exactly as the framebuffer stores
            # them: render() writes (c5 << 3) | (c5 >> 2), so >> 3 is exact
            p5 = out[..., ch].astype(np.int64) >> 3
            blended = ((p5 * (16 - a) + c5 * a) >> 4).astype(np.int64)
            v = ((blended << 3) | (blended >> 2)).astype(np.uint8)
            out[..., ch] = np.where(inside, v, out[..., ch])
    return out


def grade(panel: np.ndarray, dmem: list[int]) -> np.ndarray:
    """The curve at the video head (spec.GRADE_SRC), applied to the panel
    on its way to the glass and to nothing else.

    LAST IN THE CHAIN, after the compositor, because it is the glass and
    not a layer: a fade drawn by the compositor is part of the picture
    and gets graded with everything else.

    cross is blind to this exactly as it is blind to the compositor --
    the framebuffer never changes. glass is not, and glass is the gate.
    """
    src = s32(dmem[spec.GRADE_SRC])
    if not 0 < src <= spec.DMEM_WORDS - spec.GRADE_WORDS:
        return panel                      # off, or a pointer past DMEM
    tab = np.array([s32(v) for v in dmem[src:src + spec.GRADE_WORDS]],
                   dtype=np.int64)
    out = np.empty_like(panel)
    for ch, sh in enumerate((16, 8, 0)):
        # the pixel's own 5 bits, exactly as the framebuffer stores them
        out[..., ch] = ((tab[panel[..., ch] >> 3] >> sh) & 0xFF).astype(
            np.uint8)
    return out


def fog_of(dmem):
    """The fog triple, or None when the cart has it off."""
    fsh = s32(dmem[spec.FOG_SHIFT])
    if not 0 < fsh <= 16:                  # 0 is OFF, and a shift wider
        return None                        # than the depth is a no-op
    rgb = s32(dmem[spec.FOG_RGB])
    return ([((rgb >> sh) & 0xFF) >> 3 for sh in (16, 8, 0)],
            max(0, s32(dmem[spec.FOG_NEAR])), fsh)


def seed(dmem, cram=None):
    """The frame before any face: a flat clear, or the backdrop's colour
    AND depth planes (spec.BG_SRC).

    Split out so the tiled reference renderer (zeta/tiled.py) can start
    from the identical frame instead of reimplementing this -- a second
    implementation of the seed would be a second thing that can differ,
    and the whole point of that module is to prove nothing differs."""
    fb = np.empty((spec.H, spec.W, 3), np.uint8)
    zbuf = np.full((spec.H, spec.W), spec.ZFAR, np.int64)
    bg = s32(dmem[spec.BG_SRC])
    ebg = bg + s32(dmem[spec.SEG_BASE])     # the segment window (SEG_BASE):
    if bg > 0 and cram is not None \
            and 0 <= ebg and ebg + spec.BG_WORDS <= spec.CRAM_WORDS:
        words = np.zeros(spec.BG_WORDS, np.int64)
        avail = max(0, min(spec.BG_WORDS, len(cram) - ebg))
        if avail:
            words[:avail] = cram[ebg:ebg + avail]
        words = words.reshape(spec.H, spec.W)
        shade = (words & spec.BG_SHADOW) != 0
        zbuf[:, :] = (words >> 16) & 0xFFFF
        for ch, sh in enumerate((10, 5, 0)):
            c5 = (words >> sh) & 0x1F
            fb[..., ch] = ((c5 << 3) | (c5 >> 2)).astype(np.uint8)
    else:
        shade = np.zeros((spec.H, spec.W), bool)   # no plate, no shadow
        fb[:, :] = spec.display_rgb(spec.CLEAR_RGB)
    return fb, zbuf, shade


def render(dmem: list[int], cram: np.ndarray | None = None,
           tex: np.ndarray | None = None) -> np.ndarray:
    """dmem -> (H, W, 3) uint8 framebuffer. Pure function of DL + OL --
    plus the backdrop: if dmem[BG_SRC] is nonzero and the cart carries a
    CRAM segment, the frame clears to an image and a depth plane instead
    of a flat color (spec.BG_SRC)."""
    fb, zbuf, shade = seed(dmem, cram)
    fog = fog_of(dmem)
    # the pick register: watch one pixel through the whole paint
    px, py = s32(dmem[spec.PICK_X]), s32(dmem[spec.PICK_Y])
    in_rng = 0 <= px < spec.W and 0 <= py < spec.H
    watch = (py, px) if in_rng else None
    pick = {"id": -1, "next": 0,
            "z": int(zbuf[py, px]) if in_rng else 0xFFFF}

    n = min(dmem[spec.DL_BASE], spec.DL_MAX)
    for t in range(n):
        base = spec.DL_BASE + 1 + t * spec.DL_STRIDE
        x0, y0, x1, y1, x2, y2, rgb = (s32(v) for v in dmem[base:base + 7])
        c0 = tuple(((rgb >> sh) & 0xFF) >> 3 for sh in (16, 8, 0))
        if _fill(fb, zbuf, x0 << spec.SUB, y0 << spec.SUB, x1 << spec.SUB,
                 y1 << spec.SUB, x2 << spec.SUB, y2 << spec.SUB,
                 c0, ((0, 0),) * 3, 0, 0, 0, watch):
            pick["id"] = pick["next"]
            pick["z"] = int(zbuf[py, px])
        pick["next"] += 1
    lodf = s32(dmem[spec.LOD_FLAT])
    idbuf = np.zeros((spec.H, spec.W), np.int64)
    _geom(fb, zbuf, dmem, watch, pick, tex, fog,
          lodf if lodf > 0 else 0, idbuf, cram)
    # ---- THE OUTLINE PASS (spec.OBJ_EDGE) --------------------------------
    # A pixel is an edge when its owner differs from the owner of the
    # pixel to its LEFT or the one ABOVE. Nothing else: two outlined
    # objects meeting is an edge, an outlined object against the room is
    # an edge, and the room against itself is not.
    #
    # No comparison at x = 0 or y = 0, because there is nothing there to
    # compare against -- and the silicon, which walks the band with a
    # one-row delay line, would otherwise read the previous row's last
    # pixel and the previous FRAME's last band. Legislated so both
    # machines decline the same comparison.
    own = idbuf & 0x7F
    edg = (idbuf & 0x80) != 0
    if edg.any():
        # THE OWNERS MUST DIFFER **AND** ONE MUST HAVE ASKED. With every
        # object recorded, "the owners differ" alone outlines the world.
        e = np.zeros((spec.H, spec.W), bool)
        e[:, 1:] |= (own[:, 1:] != own[:, :-1]) & (edg[:, 1:] | edg[:, :-1])
        e[1:, :] |= (own[1:, :] != own[:-1, :]) & (edg[1:, :] | edg[:-1, :])
        fb[e] = spec.display_rgb(s32(dmem[spec.EDGE_RGB]))
    counts = np.bincount(own.reshape(-1), minlength=spec.OL_MAX + 1)
    for k in range(spec.OL_MAX):
        dmem[spec.VIS_BASE + k] = int(min(counts[k + 1], spec.VIS_MAX))
    # ---- THE GAZE (spec.GAZE_BASE) ---------------------------------------
    # Read off the two finished planes, after everything that can change
    # them has: the owner as VIS counted it, the depth as it stands. A
    # cart that asked for nothing (n = 0) gets nothing written, so every
    # cart from before this one keeps its DMEM to the word.
    if dmem[spec.GAZE_BASE]:
        asked = spec.gaze_list(dmem)
        for i in range(spec.GAZE_MAX):
            if i < len(asked):
                gx, gy = asked[i]
                ans = (int(own[gy, gx]) << 16) | (int(zbuf[gy, gx]) & 0xFFFF)
            else:
                ans = spec.GAZE_NONE
            dmem[spec.GAZE_ANS + i] = ans
    dmem[spec.PICK_ID] = pick["id"] & spec.WORD_MASK
    dmem[spec.PICK_Z] = pick["z"] & spec.WORD_MASK
    # THE PLATE'S ANSWER, taken at the CLEAR and not at the commit: the
    # room's sun does not move because an actor walked in front of it.
    # An out-of-range watch reads 0 -- lit -- for the same reason the
    # sky does.
    dmem[spec.PICK_SH] = int(shade[py, px]) if watch is not None else 0
    return fb


def write_ppm(fb: np.ndarray, path) -> None:
    with open(path, "wb") as f:
        f.write(b"P6 %d %d 255\n" % (spec.W, spec.H))
        f.write(fb.tobytes())
