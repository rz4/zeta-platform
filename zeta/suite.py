"""suite.py -- the standing gate: every subsystem's delivery path proven.

hall.zol had a generator, a passing cross, and a 55-pixel glass failure
that survived for as long as the backdrop feature existed. Not because
anyone skipped a step -- because `deploy` gates only the cart being
SHIPPED, and every cart shipped for months was geometry-only. A whole
subsystem's delivery path had no standing proof, and the defect sat
there waiting for somebody to point a gate at it.

So: a declared TABLE of subsystems and the cart that proves each. Two
properties matter more than the list itself.

  A MISSING LINE IS VISIBLE. A subsystem with no entry is a subsystem
  nothing gates. New feature, new line, the day it is written -- and
  the line is cheap, which is the whole point.

  EVERY CART MUST WITNESS ITS OWN CLAIM. carts/witness/fade.zol once passed
  glass with the compositor doing literally nothing: its fade sat at
  alpha 0 on exactly the frames the gate compares. A gate that cannot
  fail is not a gate, and a coverage table whose carts do not exercise
  what they claim is WORSE than no table -- it reports proof it does
  not have. So every entry carries a witness, checked against the law
  before a single simulation runs. A cart that stops exercising its
  feature fails here, loudly, instead of going quietly green.

The witnesses are Python against machine 1 and cost about a second
total; the gates are machine 2 and cost about a minute in parallel.
"""
from __future__ import annotations

import concurrent.futures as cf
import subprocess
import sys
from pathlib import Path
from typing import Callable, NamedTuple

from . import cabinet, spec

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# what the law saw, gathered once per cart so the witnesses stay one-liners
# ---------------------------------------------------------------------------
class Observed:
    """Everything a witness might ask, watched across a short run.

    Watched DURING, not read after: the machine clears OVL_GO and
    DMA_GO as it acts on them, so a witness that looked at the final
    dmem would see a cart that never moved anything."""

    def __init__(self, cart: dict, frames: int = 8, pad: int = 0,
                 start: int = 0):
        import numpy as np

        m = cabinet.VirtualMachine(cart)
        m.vm.frame_no = start          # some carts only reach their claim
                                       # after a while (choir ramps for 8 s)
        boot_imem = list(m.vm.imem)
        self.flags: set[int] = set()
        self.bg = self.texsrc = self.lodflat = self.wavsrc = 0
        self.dma_len = self.ovl_len = 0
        self.rects = 0
        self.blended = False
        self.moved_code = False
        self.audio_peak = 0
        self.pictures = []
        self.has_segment = bool(cart.get("cram"))
        self.objects = 0
        self.blend_px = 0
        self.clip_px = 0
        self.cart_px = 0          # pixels that MOVE if OBJ_CART is switched
        self.cart_vsrcs = set()   # off in the law; the vertex streams drawn from
        self.otint_px = 0         # pixels that MOVE if OBJ_OTINT is
        self.otint_words = set()  # ignored, and the distinct lights seen
        self.add_px = 0           # pixels that MOVE if BLEND_ADD is
        self.add_up = True        # ignored, and the invariant that it
        self.add_sat = 0          # can only ever push them BRIGHTER
        self.sh_flips = 0         # times the plate's shadow ANSWER
        self.sh_px = 0            # changed, and pixels that move if the
        self.shots: list = []     # spare bit is ignored
        self.vis_hi = 0           # spec.VIS_BASE: the subject's count at
        self.vis_lo = 1 << 30     # its clearest and at its most hidden,
        self.vis_sum = 0          # the whole panel's worth, and where
        self.vis_where: set = set()   # the cart PUT the answer
        self.lit_shades = 0       # spec.OBJ_LIT: shades on the panel,
        self.lit_moved = 0        # frames the picture changed while
        self.lit_still = True     # nothing in the world did
        self._lit_prev = None
        self._lit_pose = None
        self.aud_live = 0         # spec.AUD_BASE: voices ever heard,
        self.aud_span = 0.0       # the widest swing any of them made,
        self.aud_where: set = set()   # and where the cart SPENT it
        self._aud_lo: dict = {}
        self._aud_hi: dict = {}
        self.vis_moved_seen = 0   # objects that MOVED while the panel
        self.vis_moved_hidden = 0  # was showing them, while it was not,
        self.vis_saw = 0          # and how often it was showing anything
        self._vis_prev = None
        self.edge_px = 0          # pixels the OUTLINE draws
        self.edge_pure = True     # ...all of them in EDGE_RGB
        self.edge_clean = True    # ...and none on an unflagged object
        self.grade_px = 0         # pixels the CURVE moves, and which
        self.grade_chans: set = set()   # channels it moved
        self._sh_prev = None
        self.dl_tris = 0
        self.picked = 0
        self.pages = set()
        self.events = 0
        self.onsets: set[int] = set()
        self.voices = 0
        self.wavpages: set[int] = set()
        self.pagemoves = 0        # a voice re-aimed at another page
        self.pageflips = 0        # the TABLE itself replaced, frame to
        _lastpage = None          # frame: a stream, not an instrument
        _lastpg: dict[int, int] = {}
        for _ in range(frames):
            m.frame(pad)
            d = m.vm.dmem
            n = min(d[spec.OL_BASE], spec.OL_MAX)
            self.objects = max(self.objects, n)
            for k in range(n):
                b = spec.OL_BASE + 1 + k * spec.OL_STRIDE
                self.flags.add(d[b + 5])
                if d[b + 5] & spec.OBJ_TEX:      # which page it samples
                    self.pages.add((d[b + 5] >> spec.OBJ_PAGE_SHIFT)
                                   & spec.OBJ_PAGE_MASK)
            self.bg = max(self.bg, d[spec.BG_SRC])
            self.texsrc = max(self.texsrc, d[spec.TEX_SRC])
            self.lodflat = max(self.lodflat, d[spec.LOD_FLAT])
            self.wavsrc = max(self.wavsrc, d[spec.WAV_SRC])
            self.dma_len = max(self.dma_len, d[spec.DMA_LEN])
            self.ovl_len = max(self.ovl_len, d[spec.OVL_LEN])
            live = min(d[spec.CO_BASE], spec.CO_MAX)
            for k in range(live):
                b = spec.CO_BASE + 1 + k * spec.CO_STRIDE
                if (d[b + 2] >> 24) & 0x1F:
                    self.rects += 1
            # THE COMPOSITOR ACTED, which is not the same as "the panel
            # differs from the framebuffer" -- grading (spec.GRADE_SRC)
            # differs too, and it arrives after the compositor. Asking
            # compose() directly keeps `blended` meaning what its name
            # says, and keeps the fade claim honest now that a second
            # thing can move the panel.
            from . import gpu as _g
            if not np.array_equal(_g.compose(m.framebuffer(), d),
                                  m.framebuffer()):
                self.blended = True
            # THE CURVE (spec.GRADE_SRC). Two things: it must MOVE the
            # panel, and where the cart asked for the identity it must
            # move it not at all. The second is the one that catches an
            # index off by one or a channel packed wrong -- a handsome
            # curve looks handsome either way.
            if spec.s32(d[spec.GRADE_SRC]) > 0:
                moved = (m.panel() != m.framebuffer())
                self.grade_px = max(self.grade_px,
                                    int(moved.any(axis=2).sum()))
                self.grade_chans |= {c for c in range(3)
                                     if moved[..., c].any()}
            # WHAT DOES OBJ_BLEND ACTUALLY CHANGE? Re-render the same
            # frame with the flag stripped and count the pixels that
            # move. "The cart sets the flag" is not a witness -- alpha
            # 0 sets it and draws nothing, which is exactly how fade.zol
            # once passed glass doing nothing at all.
            plain = list(d)
            for k in range(min(d[spec.OL_BASE], spec.OL_MAX)):
                b2 = spec.OL_BASE + 1 + k * spec.OL_STRIDE
                plain[b2 + 5] = d[b2 + 5] & ~spec.OBJ_BLEND
            if any(d[spec.OL_BASE + 1 + k * spec.OL_STRIDE + 5]
                   & spec.OBJ_BLEND
                   for k in range(min(d[spec.OL_BASE], spec.OL_MAX))):
                from . import gpu
                off = gpu.render(plain, m._cram, m._tex)
                self.blend_px = max(self.blend_px,
                                    int((off != m.framebuffer())
                                        .any(axis=2).sum()))
            # THE CLIPPER, measured the same way the blend is: re-render
            # with clip.clip switched OFF, which puts a face with a vertex
            # the rasteriser cannot address back to being dropped WHOLE --
            # the machine exactly as it was -- and require the picture to
            # MOVE. "the cart has faces that clip" is NOT a witness:
            # cube.zol has 208 of them and every one lands off-screen.
            from . import clip as _clipmod
            from . import gpu as _gpu
            _keep = _clipmod.clip
            _clipmod.clip = lambda tri: []
            try:
                unclipped = _gpu.render(d, m._cram, m._tex)
            finally:
                _clipmod.clip = _keep
            self.clip_px = max(self.clip_px,
                               int((unclipped != m.framebuffer())
                                   .any(axis=2).sum()))
            # OBJ_OTINT, proved the same way the clipper is: render
            # again with the flag switched OFF in the law and count what
            # moves. "the cart sets the bit" is not a witness -- a bit
            # can be set on an object that never reaches a pixel.
            # ---- THE PANEL AS A SENSOR (spec.VIS_BASE) --------------
            # The counts are checked against the WORLD, not against a
            # second copy of the arithmetic that produced them: an
            # occluder crosses the subject, so its count has to fall and
            # rise, and no object may claim more of the panel than the
            # panel has. Then the marker's position proves the number
            # left DMEM and reached a pixel -- a count nobody spends is
            # a count nobody can check.
            if d[spec.VIS_BASE + 1]:
                self.vis_hi = max(self.vis_hi, d[spec.VIS_BASE + 1])
                self.vis_lo = min(self.vis_lo, d[spec.VIS_BASE + 1])
                self.vis_sum = max(self.vis_sum,
                                   sum(d[spec.VIS_BASE + k] for k in range(n)))
                self.vis_where.add(d[spec.OL_BASE + 1
                                     + 3 * spec.OL_STRIDE + 1])
            # ---- LIGHT ACROSS A SURFACE (spec.OBJ_LIT) ---------------
            # Two things, and the second is the one worth having: the
            # picture must carry many SHADES, and it must CHANGE while
            # every object stands still. A cart that recoloured its own
            # vertices would pass the first and fail the second.
            pic = m.framebuffer()
            self.lit_shades = max(self.lit_shades,
                                  len({tuple(c) for c in
                                       np.asarray(pic).reshape(-1, 3)}))
            pose = tuple(d[spec.OL_BASE + 1 + k * spec.OL_STRIDE + j]
                         for k in range(min(d[spec.OL_BASE], spec.OL_MAX))
                         for j in (0, 1, 2, 3, 4, 5))
            if self._lit_pose is not None and pose != self._lit_pose:
                self.lit_still = False
            self._lit_pose = pose
            if self._lit_prev is not None and \
                    (np.asarray(pic) != self._lit_prev).any():
                self.lit_moved += 1
            self._lit_prev = np.asarray(pic).copy()
            # ---- THE MIXER'S RETURN (spec.AUD_BASE) ------------------
            # A voice's total must MOVE -- a steady tone proves the sum
            # runs but not that it tracks -- and the cart must spend it
            # on something the panel shows, because cross compares
            # pictures and sample streams and never DMEM.
            for c in range(spec.AU_CHANNELS):
                v = d[spec.AUD_BASE + c]
                if not v:
                    continue
                self._aud_lo[c] = min(self._aud_lo.get(c, v), v)
                self._aud_hi[c] = max(self._aud_hi.get(c, v), v)
            self.aud_live = len(self._aud_hi)
            self.aud_span = max(
                (self._aud_hi[c] / max(self._aud_lo[c], 1)
                 for c in self._aud_hi), default=0.0)
            n_ol = min(d[spec.OL_BASE], spec.OL_MAX)
            if n_ol:
                self.aud_where.add(tuple(
                    d[spec.OL_BASE + 1 + k * spec.OL_STRIDE + 2]
                    for k in range(n_ol)))
            # ---- AND WHETHER A CART CAN ACT ON IT --------------------
            # The counts being TRUE is checked above. This checks the
            # other half: that a cart reading them can gate behaviour on
            # them, with no frame of leak. An object the panel showed
            # must not have moved; one it did not show must have.
            # Gathered for every cart and read by only one claim, so
            # that the suite never has to know a cart's name.
            now = {}
            for k in range(min(d[spec.OL_BASE], spec.OL_MAX)):
                b3 = spec.OL_BASE + 1 + k * spec.OL_STRIDE
                now[k] = (d[b3 + 1], d[b3 + 3], d[spec.VIS_BASE + k])
            if self._vis_prev:
                for k, (x, z, _v) in now.items():
                    if k not in self._vis_prev:
                        continue
                    px, pz, pv = self._vis_prev[k]
                    moved = (x != px) or (z != pz)
                    if pv >= 20:
                        self.vis_saw += 1
                        self.vis_moved_seen += moved
                    else:
                        self.vis_moved_hidden += moved
            self._vis_prev = now
            if any(f & spec.OBJ_OTINT for f in self.flags):
                from . import gpu as _gpu
                for b in range(spec.OL_BASE + 1,
                               spec.OL_BASE + 1 + n * spec.OL_STRIDE,
                               spec.OL_STRIDE):
                    if d[b + 5] & spec.OBJ_OTINT:
                        self.otint_words.add(d[b + 5] >> spec.OBJ_OTINT_SHIFT)
                _ot, spec.OBJ_OTINT = spec.OBJ_OTINT, 0
                try:
                    unlit = _gpu.render(d, m._cram, m._tex)
                finally:
                    spec.OBJ_OTINT = _ot
                self.otint_px = max(self.otint_px,
                                    int((unlit != m.framebuffer())
                                        .any(axis=2).sum()))
            # spec.OBJ_CART (frontier 20), by the same mutation: with the
            # flag unread a descriptor is no mesh, and what the cart's
            # meshes drew is gone. The streams it drew from are counted,
            # so a cart that never changes a pose's offsets cannot claim
            # that a pose is "two offsets written".
            if any(f & spec.OBJ_CART for f in self.flags):
                from . import gpu as _gpu
                for b in range(spec.OL_BASE + 1,
                               spec.OL_BASE + 1 + n * spec.OL_STRIDE,
                               spec.OL_STRIDE):
                    if d[b + 5] & spec.OBJ_CART and 0 <= d[b] < spec.DMEM_WORDS - 5:
                        self.cart_vsrcs.add(d[d[b] + 1])
                _oc, spec.OBJ_CART = spec.OBJ_CART, 0
                try:
                    gone = _gpu.render(d, m._cram, m._tex)
                finally:
                    spec.OBJ_CART = _oc
                self.cart_px = max(self.cart_px,
                                   int((gone != m.framebuffer())
                                       .any(axis=2).sum()))
            # BLEND_ADD, proved by the same mutation -- and by an
            # invariant, which a screenshot could not give. The two modes
            # differ by add - lerp = dst*a, which is never negative, so
            # additive must be >= lerp at EVERY pixel. A sign error, a
            # swapped operand or a wrapped saturate all break that.
            if any(f & spec.OBJ_BLEND for f in self.flags):
                from . import gpu as _gpu
                _ba, spec.BLEND_ADD = spec.BLEND_ADD, -1   # no face matches
                try:
                    aslerp = _gpu.render(d, m._cram, m._tex)
                finally:
                    spec.BLEND_ADD = _ba
                real = m.framebuffer()
                moved = (aslerp != real).any(axis=2)
                self.add_px = max(self.add_px, int(moved.sum()))
                if moved.any():
                    self.add_up &= bool((real[moved] >= aslerp[moved]).all())
                self.add_sat = max(self.add_sat, int(
                    ((real == 255) & (aslerp < 255)).any(axis=2).sum()))
            # THE SPARE BIT (spec.BG_SHADOW / PICK_SH). Two things have
            # to be true and neither implies the other: the room must
            # ANSWER differently as the actor moves, and the answer must
            # reach PIXELS. A cart could ask and ignore; a cart could
            # tint and never ask.
            sh = d[spec.PICK_SH]
            if self._sh_prev is not None and sh != self._sh_prev:
                self.sh_flips += 1
            self._sh_prev = sh
            # OBJ_EDGE. Three things, and a cart can fail any one while
            # looking right in the other two: the line must EXIST, it must
            # be the colour the cart asked for, and it must appear only
            # where an owner changes -- never inside a flat region.
            if any(f & spec.OBJ_EDGE for f in self.flags):
                from . import gpu as _gpu
                _e, spec.OBJ_EDGE = spec.OBJ_EDGE, 0    # nobody asks
                try:
                    plain = _gpu.render(list(d), m._cram, m._tex)
                finally:
                    spec.OBJ_EDGE = _e
                real = m.framebuffer()
                drew = (plain != real).any(axis=2)
                self.edge_px = max(self.edge_px, int(drew.sum()))
                if drew.any():
                    want = np.array(spec.display_rgb(
                        spec.s32(d[spec.EDGE_RGB])), np.uint8)
                    self.edge_pure &= bool((real[drew] == want).all())
            self.dl_tris = max(self.dl_tris, d[spec.DL_BASE])
            if spec.s32(d[spec.PICK_ID]) >= 0:      # the machine answered
                self.picked += 1
            if list(m.vm.imem) != boot_imem:
                self.moved_code = True
            nev = d[spec.AU_EV_BASE]
            if 0 <= nev <= spec.AU_EV_MAX:
                self.events = max(self.events, nev)
            for c in range(spec.AU_CHANNELS):
                ctrl = d[spec.AU_BASE + 2 * c + 1]
                if d[spec.AU_BASE + 2 * c] and ctrl & 0xF:
                    self.voices = max(self.voices, c + 1)
                if d[spec.AU_BASE + 2 * c] and d[spec.WAV_SRC]:
                    pg = (ctrl >> spec.AU_PAGE_SHIFT) & spec.AU_PAGE_MASK
                    self.wavpages.add(pg)
                    if _lastpg.get(c, pg) != pg:
                        self.pagemoves += 1
                    _lastpg[c] = pg
            ws = d[spec.WAV_SRC]
            if ws:
                pg = tuple(d[ws:ws + spec.WAV_WORDS])
                if _lastpage is not None and pg != _lastpage:
                    self.pageflips += 1
                _lastpage = pg
            snd = m.audio()
            self.audio_peak = max(self.audio_peak, int(np.abs(snd).max()))
            # WHERE IN THE FRAME the sound begins. A frame-rate machine can
            # only ever answer 0, so a set of DIFFERENT non-zero offsets is
            # the sub-frame timeline itself, measured rather than asserted.
            nz = np.nonzero(snd)[0]
            if len(nz) and nz[0] > 0:
                self.onsets.add(int(nz[0]))
            self.pictures.append(m.panel().copy())
            self.shots.append(m.framebuffer().copy())

        # THE SPARE BIT, PROVED BY RUNNING THE CART TWICE. The mutation
        # cannot be a re-render of one frame: the shadow answer reaches
        # the picture through the CART, a frame later, so by the time a
        # frame is drawn its tint is already sitting in DMEM. Switching
        # spec.BG_SHADOW off and redrawing that frame changes nothing and
        # would read as "the feature does nothing".
        #
        # So the whole cart runs again with the bit switched off, and the
        # pixels that differ are what the room's shadow is actually worth.
        if self.sh_flips and self.bg:
            _bs, spec.BG_SHADOW = spec.BG_SHADOW, 0
            try:
                m2 = cabinet.VirtualMachine(cart)
                m2.vm.frame_no = start          # the same start, the same
                for k in range(frames):         # frames, one bit different
                    m2.frame(pad)
                    self.sh_px = max(self.sh_px,
                                     int((m2.framebuffer()
                                          != self.shots[k])
                                         .any(axis=2).sum()))
            finally:
                spec.BG_SHADOW = _bs

    def any_flag(self, bit: int) -> bool:
        return any(f & bit for f in self.flags)

    def moves(self) -> bool:
        import numpy as np
        return any(not np.array_equal(self.pictures[0], p)
                   for p in self.pictures[1:])

    def drew_something(self) -> bool:
        """More than one colour on screen: the frame is not a bare clear."""
        import numpy as np
        return len(np.unique(self.pictures[-1].reshape(-1, 3), axis=0)) > 1


class Claim(NamedTuple):
    cart: str
    proves: str
    witness: Callable[[Observed], bool]
    why: str                       # what a failed witness means
    # HOW THE CART IS MEANT TO BE EXERCISED. Both of these were learned
    # the hard way while writing the table: overlay.zol swaps program at
    # frame 120, so eight frames witnessed nothing; fabric.zol has tank
    # controls, so with the pad at rest it correctly stands still. A
    # witness that does not drive the cart measures its own laziness.
    frames: int = 8
    pad: int = 0
    start: int = 0                 # frame number to begin at
    # THE GLASS STATUS (SLICE stage 2). The cross and glass gates above
    # prove the two SIMULATED machines; this field records whether the
    # claim has been seen on the REAL panel, and by what. "" means never
    # witnessed on the Pocket, or witnessed before build 94 when nobody
    # wrote down which claim a boot covered -- either way it belongs in
    # the queue. The honest entries come from the docs' own words
    # ("WITNESSED ON THE POCKET", with a build number); a Menu+Start
    # capture through `zeta sd witness` is how an entry is earned now.
    glass: str = ""


# ---------------------------------------------------------------------------
# THE TABLE. A subsystem absent from this list is a subsystem nothing gates.
# ---------------------------------------------------------------------------
CLAIMS: list[Claim] = [
    Claim("cube", "geometry: transform, backface cull, depth, painter's 3D",
          lambda o: o.drew_something() and o.any_flag(spec.OBJ_CULL),
          "no culled geometry reached the screen"),
    Claim("orbit", "full 3-axis rotation, and LOD_FLAT (the Spyro trick)",
          lambda o: o.moves() and o.lodflat,
          "the picture never changed, or LOD_FLAT is off"),
    Claim("tex", "the sampled field: perspective-correct texturing",
          lambda o: o.texsrc and o.any_flag(spec.OBJ_TEX),
          "no textured object, or no page loaded"),
    Claim("pages", "several texture pages resident at once (flags 12:8)",
          lambda o: len(o.pages) >= 3,
          "every textured object samples the same page -- this proves "
          "nothing that one resident page did not already prove"),
    # ...AND ALL OF THEM. pages.zol has used four since it was written,
    # unchanged through TEX_PAGES 8 -> 16 -> 24, so sixteen of the
    # twenty-four slots were capacity nothing had ever looked at. Build
    # 97 found out why that matters: the wire carrying the selector
    # between zseq and zgpu was still four bits, so 16..23 silently
    # became 0..7 and every one of them sampled a page that WAS loaded
    # and therefore looked entirely plausible.
    Claim("pagemax", "every texture page at once, and one that is not there",
          lambda o: len(o.pages) >= spec.TEX_PAGES + 1,
          "fewer than every slot is being sampled, so the pages nobody "
          "reaches are the pages nobody tests -- which is how a "
          "four-bit wire hid eight of them",
          frames=30, glass="build 97, ALIEN.md 106"),
    Claim("lodspan", "OBJ_LODSPAN and OBJ_TINT -- the mip and the light",
          lambda o: o.any_flag(spec.OBJ_LODSPAN) and o.any_flag(spec.OBJ_TINT),
          "the span-mip or the tint is not actually switched on"),
    Claim("hall", "BG_SRC: the depth-composited pre-rendered backdrop",
          lambda o: o.bg and o.has_segment,
          "no plate -- the cart clears to flat colour and proves nothing"),
    Claim("fade", "the scanout compositor (blending at the video head)",
          lambda o: o.blended and o.rects,
          "the panel equals the framebuffer: the compositor did NOTHING. "
          "This is the exact failure this table exists to catch"),
    # "there is audio" is NOT the claim, and testing it that way passed
    # cube.zol, which makes noise from the plain channels and touches no
    # wavetable at all. The claim is the SAMPLED FIELD at the audio rate:
    # a WAV_SRC page loaded, and sound coming out of it.
    # LIGHT THAT MOVES. OBJ_TINT could light a textured SURFACE and only
    # from words baked in the mesh; OBJ_OTINT lights an untextured ACTOR
    # from one word in its object slot, so a cart can re-light it every
    # frame. Both halves have to be witnessed, because a cart that sets
    # a constant tint proves only the first.
    # ADDITIVE. The lerp can only move a pixel TOWARD the source colour,
    # so it can darken a bright pixel and can never brighten one -- which
    # is why a glow composited with a lerp reads as a sticker over the
    # picture instead of as light coming off something. The claim is
    # gated on the INVARIANT (add >= lerp everywhere, since they differ
    # by dst*a) rather than on a picture, because a swapped operand or a
    # wrapped saturate would still make a plausible picture.
    # THE CURVE AT THE GLASS. cross is blind to this and correctly so --
    # the framebuffer never changes -- which makes glass the only gate
    # that can see it, exactly as with the compositor.
    Claim("graded", "GRADE_SRC: the curve on the way to the panel",
          lambda o: o.grade_px > 20000 and o.grade_chans == {1, 2},
          "either the curve moved nothing -- a table the video head never "
          "read -- or it moved the channel the cart asked to leave ALONE, "
          "which is an index off by one or a channel packed wrong",
          frames=3),
    # THE OUTLINE. The era drew every model a SECOND TIME, inflated and
    # turned inside out -- twice the geometry, and wrong at every sharp
    # corner, because an inflated hull does not know where the silhouette
    # is. Here the rasterizer already knows who owns each pixel and the
    # line is a comparison riding the walk that was carrying the band out
    # anyway. It costs no clocks.
    # THE PANEL AS A SENSOR. The rasterizer visits every visible point of
    # every surface and throws all of it away but the colour. This keeps
    # the first of it: how many pixels of each object the panel ACTUALLY
    # SHOWED -- counted at flush, so being drawn over costs you the
    # pixel. The era's answer was an occlusion query a frame late off a
    # separate pass; here it is a LUTRAM read-add-write riding the walk
    # that was carrying the band out anyway, and it costs no clocks.
    Claim("seen", "spec.VIS_BASE: what the panel actually showed",
          lambda o: o.vis_hi > o.vis_lo * 5 and o.vis_sum <= spec.W * spec.H
                    and len(o.vis_where) > 4,
          "either the count did not track the occluder crossing the "
          "subject, or some object claimed more of the panel than the "
          "panel has, or the marker never moved -- a number the cart "
          "never spends is a number nothing can check",
          frames=40, glass="builds 94-95, ALIEN.md 105a"),
    # ...AND WHAT IT IS FOR. Five figures in a ring, each advancing on
    # any frame the panel showed fewer than 20 pixels of it. The era
    # faked this rule with a cone test against the camera plus hand-
    # placed "you cannot be seen here" volumes; the occlusion query that
    # would have done it properly arrived on the PC around 2001, cost a
    # second geometry pass and answered a frame or two late. Here the
    # answer is exact, covers the frustum and the wall and the crowd with
    # one number, and costs no clocks.
    # THE MIXER AS A SENSOR, and the term that closes the formula:
    # Wn+1 = f(Wn, An, VIS, AUD). One word a voice, the sum of
    # |contribution| across the frame's samples -- so a cart can ask what
    # came OUT of the machine rather than remembering what it put in.
    # The era's answer was to keep your own envelope and hope the mixer
    # agreed; here the mixer answers.
    # LIGHT ACROSS A SURFACE. A flat face lit uniformly is the shape of
    # 1997; light that VARIES across it is the shape of everything after,
    # and the machine has carried per-vertex colour since OBJ_GOURAUD --
    # what was missing was anywhere to say where the light comes FROM.
    # The vertex word becomes a NORMAL and the mesh format does not
    # change, so a mesh is relit by writing ONE DMEM word.
    # THE MACHINE'S FACE, gated across its own finale: the window spans
    # the turn, the eye-flash, the white-out and the first glyphs, so
    # the claim holds only while the sky plate, the lit Grey, the tint
    # eyelids, the display-list glyphs and the score all fire in ONE
    # cart. It is the demo of everything at once, and this is the line
    # that keeps it one.
    Claim("face", "the boot: plates + lit rig + grade + DL + score, one cart",
          lambda o: o.bg and o.any_flag(spec.OBJ_LIT)
                    and o.objects >= 7 and o.dl_tris > 0
                    and o.audio_peak > 1000,
          "the face lost one of its organs -- no plate (sky or "
          "foreground), no lit figure, fewer objects than the carved "
          "rig carries, no glyphs, or no score in the witnessed window",
          # 200..500 of the TEN-SECOND cut: starts while a sky plate
          # is still up (they leave at 214), ends after the first
          # glyphs (480). Moved four times now, once per timeline --
          # the claim refusing to witness a show that no longer plays
          # where it is looking, which is the claim working.
          frames=300, start=200),
    Claim("shaded", "spec.OBJ_LIT: light that varies across a surface",
          lambda o: o.any_flag(spec.OBJ_LIT) and o.lit_shades > 20
                    and o.lit_still and o.lit_moved > 5,
          "either nothing set the flag, or the panel wears too few "
          "shades to be carrying light at all, or the picture only "
          "changed because something MOVED -- a cart recolouring its "
          "own vertices would look identical and prove nothing",
          frames=30, glass="build 98, ALIEN.md 107"),
    Claim("heard", "spec.AUD_BASE: what each voice was heard to do",
          lambda o: o.aud_live >= 3 and o.aud_span > 5.0
                    and len(o.aud_where) > 20,
          "either fewer than three voices ever registered, or none of "
          "them swung far enough to prove the total TRACKS rather than "
          "merely accumulates, or the cart never spent the answer on a "
          "pixel -- and a number nothing spends is a number cross "
          "cannot check",
          frames=40),
    Claim("watched", "a figure moves only while the panel cannot see it",
          lambda o: o.vis_moved_seen == 0 and o.vis_moved_hidden > 100
                    and o.vis_saw > 30,
          "either a figure stepped on a frame the panel was showing it -- "
          "the rule leaking, which is the whole game -- or the run never "
          "saw one at all, which measures nothing",
          frames=60, pad=spec.PAD_RIGHT),
    Claim("edged", "OBJ_EDGE: the silhouette, from the identity plane",
          lambda o: o.edge_px > 150 and o.edge_pure,
          "either the outline reached no pixel -- a flag set on an object "
          "the walk never committed -- or it was drawn in some colour "
          "other than the one the cart asked for",
          frames=12),
    # THE SPARE BIT. bit 15 of a plate word was read by nothing in either
    # machine -- 92,160 bits per room, baked and delivered and ignored.
    # It carries the room's shadow now, and the pick register answers
    # from it, which is how an actor stops being lit by a different world
    # than the room it is standing in.
    Claim("shade", "the room tells an actor where its light is",
          lambda o: o.sh_flips > 3 and o.sh_px > 300
                    and len(o.otint_words) > 1,
          "either the room never answered differently as the actor moved "
          "-- a query that cannot fail -- or the answer reached no pixel, "
          "which is a cart that asks and then ignores what it hears",
          frames=60),
    Claim("glow", "BLEND_ADD: a pixel brighter than either operand",
          lambda o: o.add_px > 2000 and o.add_up and o.add_sat > 200,
          "either the additive mode reaches no pixel, or it came out "
          "DARKER than the lerp somewhere -- which the arithmetic "
          "forbids -- or it never drove a channel to full, which is the "
          "saturation the lerp cannot reach",
          frames=4),
    Claim("lit", "OBJ_OTINT: light that comes from the OBJECT, per frame",
          lambda o: o.otint_px > 2000 and len(o.otint_words) > 4,
          "either switching OBJ_OTINT off in the law changes nothing -- a "
          "flag set on an object that reaches no pixel -- or the light "
          "never CHANGED, which is the whole difference from OBJ_TINT",
          frames=40),
    Claim("nearclip", "THE CLIPPER: five view-space planes, the hole closed",
          lambda o: o.clip_px > 5000,
          "switching the clipper off changes almost nothing -- this cart "
          "is not standing where the ground vanishes, so it witnesses a "
          "clipper that could be absent"),
    # THE CLIPPER'S RANGE. nearclip's tiles are 2 units wide, so every
    # crossing it makes is small arithmetic; the clipper is sized for a
    # 33-bit difference times a 50-bit distance and NOTHING reached the
    # top of it -- frontier B3's mutants (the multiply's high partial
    # products dropped) passed every cart until this one.
    Claim("bigclip", "THE CLIPPER AT THE TOP OF ITS RANGE: tiles thousands "
                     "of units wide, differences past 2^27",
          lambda o: o.clip_px > 5000,
          "switching the clipper off changes almost nothing -- the huge "
          "floor is not crossing the planes, so the wide end of the "
          "crossing's multiply and divide is unwitnessed again",
          frames=40),
    # MESHES DRAWN FROM THE CART (frontier 20): three streams in the
    # segment through a five-word descriptor -- the clipper, the outline,
    # the object's tint, a refusal, the store's limit, a pose by offsets.
    Claim("cartmesh", "spec.OBJ_CART: meshes drawn from the cart, a pose two offsets",
          lambda o: o.cart_px > 5000 and len(o.cart_vsrcs) > 5,
          "switching OBJ_CART off in the law changes almost nothing -- the "
          "cart's meshes reach no pixel -- or no descriptor's vertices ever "
          "moved to another stream, which is the whole of a pose",
          frames=40),
    # LIT FACES THROUGH THE CLIPPER (2026-11-22). shaded's two spheres
    # never come near the lens, so the silicon's lit path had never been
    # crossed where a lit face is CUT: a vertex the machine cannot project
    # was cached with level zero, and the clipper took a face's third
    # corner's level from a stale register -- black and wrong-coloured
    # strips down the side of the glass in TND's lit town, on the Pocket
    # and never in the law. The claim is the clipper's own mutation on a
    # cart that is lit and nothing else; the cross does the rest.
    Claim("litclip", "spec.OBJ_LIT through the clipper: a lit face cut by the lens",
          lambda o: o.any_flag(spec.OBJ_LIT) and o.clip_px > 5000,
          "either nothing is lit, or switching the clipper off changes "
          "almost nothing -- no lit face is being cut on the glass, which "
          "is the only place the silicon's lit levels were ever wrong",
          frames=40),
    # THE GAME, and the line that would have caught the defect it found:
    # a backdrop AND more than one mesh, which no other cart in this table
    # combines. hall proves the backdrop with ONE object, which is exactly
    # how the mover's ungated cursor survived every gate.
    # THE ORACLE, and it had no line at all until build 95 -- the GPU as a
    # spatial query, FRONTIER axis I, used by ONE cart and gated by
    # nothing. That cart was failing cross by 168 px the whole time.
    Claim("pick", "the pick register: the GPU answering about SPACE",
          lambda o: o.picked > 0 and o.dl_tris > 0,
          "the machine never named a triangle under the watched pixel -- "
          "or the readout is gone, which is what makes the answer visible",
          frames=40),
    # THE ID RIDES WITH THE TRIANGLE (frontier B2). pick starts on the
    # bunny, whose faces the rasterizer takes the moment they are offered;
    # the floor's are offered during the clear and WAIT -- so only a pick
    # on the floor can tell an id carried through the queue from one read
    # off the sequencer's counter when the triangle is finally drawn.
    Claim("pickfloor", "the pick register names a triangle that WAITED in "
                       "the queue",
          lambda o: o.picked > 0 and o.dl_tris > 0,
          "the machine never named a triangle under the watched pixel -- "
          "the crosshair is no longer on the floor, so the queued id is "
          "unwitnessed again",
          frames=24),
    Claim("vessel", "THE GAME: a goal, a fail state, text over a backdrop, "
                    "more than one mesh, SUB-FRAME sound -- and stage 4's "
                    "light, in a cart that is not a demo of it",
          lambda o: (o.bg and o.dl_tris > 0 and o.objects >= 2
                     and o.events > 0 and o.audio_peak > 0
                     and len(o.otint_words) > 4 and o.add_px > 100
                     and o.add_up),
          "no room, no prompt, fewer than two objects, a silent event "
          "list, a key that does not breathe, or a glow that adds "
          "nothing -- two objects over a plate is the combination that "
          "found the backdrop cursor bug, and a feature that works only "
          "in the cart built to show it off is a feature that does not "
          "work",
          frames=340, pad=spec.PAD_UP),
    Claim("glass", "OBJ_BLEND: per-pixel blending in the rasteriser",
          lambda o: o.any_flag(spec.OBJ_BLEND) and o.blend_px > 500,
          "the flag is set but stripping it changes nothing -- alpha is "
          "zero, or nothing blended is on screen"),
    Claim("voice", "the wavetable voice (WAV_SRC) through the 4-channel mix",
          lambda o: o.wavsrc and o.audio_peak > 0,
          "no wave page loaded, or silence -- the plain channels alone "
          "prove nothing about the sampled field"),
    # THE TIMELINE. Not "there are events" -- a list of events that all
    # sat at offset 0 would satisfy that and would be a frame-rate
    # machine wearing a costume. The claim is that the sound STARTS AT
    # DIFFERENT SAMPLE OFFSETS on different frames, which is the one
    # thing 60 Hz control cannot express, and which is precisely what
    # the silicon failed to do while every other gate was green.
    Claim("pulse", "the event list: sub-frame timing at the sample",
          lambda o: o.events > 0 and len(o.onsets) > 2,
          "the events are all frame-aligned (or absent) -- a timeline "
          "that only ever fires at offset 0 is just a frame-rate cart",
          frames=12),
    Claim("choir", "sixteen channels: the mix beyond the four oscillators",
          lambda o: o.voices > spec.AU_TONE_CHANNELS and o.audio_peak > 0,
          "nothing above channel 3 is sounding -- the twelve added "
          "voices are inert and the four originals prove nothing",
          frames=8, start=13 * 32),      # the ramp reaches voice 13 here
    # NOT "the cart sets some page bits". The witness counts DISTINCT
    # pages actually being read by sounding voices, because a bank whose
    # every voice points at page 0 is the single shared page this feature
    # exists to end -- and it would set the field, and it would pass a
    # laxer check.
    Claim("band", "the wave bank: eight timbres resident at once",
          lambda o: len(o.wavpages) > 4 and o.events > 0 and o.audio_peak > 0,
          "fewer than five pages are being read -- the voices are still "
          "sharing one table and the bank proves nothing"),
    # BAND proves eight pages can be resident together. This proves the
    # OTHER half, and they are not the same claim: that a page is chosen
    # by RATE, which is the mip law and the reason the bank is worth
    # having at 48 kHz rather than just more timbres.
    Claim("octave", "the audio mip chain: the page follows the pitch",
          lambda o: o.pagemoves > 4 and len(o.wavpages) > 4,
          "one voice never moved between pages -- the chain is baked but "
          "nothing selects from it, so the top octave still aliases",
          frames=200),          # a sweep steps every 2 frames
    # THE ONE CLAIM NO SYNTHESISER CAN FAKE. Every other cart loads a
    # wave page and leaves it there; this one has the mover replace the
    # table's CONTENTS every single frame, out of a CRAM segment, which
    # is what playing a recording actually is. Witnessed as page flips,
    # because "there is audio" and "a page is loaded" were both already
    # true of carts that stream nothing.
    Claim("stream", "recorded sound: a page re-delivered every frame",
          lambda o: o.pageflips > 20 and o.has_segment
                    and o.dma_len == spec.WAV_WORDS and o.events > 0,
          "the wave table is not changing frame to frame -- the mover is "
          "not feeding it, so this is an instrument, not a recording",
          frames=120),      # the track's own lead-in is silent until
                            # frame 66, and a silent page does not flip
    Claim("overlay", "overlays: a cart larger than IMEM rewrites itself",
          lambda o: o.moved_code,
          "IMEM never changed -- no overlay actually landed",
          frames=130),          # it swaps program at frame 120
    Claim("banked", "the mover: cart content that does not fit in DMEM",
          lambda o: o.dma_len and o.has_segment,
          "nothing was paged in from the CRAM segment"),
    Claim("fabric", "the world fabric: hashed props over an endless ground",
          lambda o: o.moves() and o.objects > 9,
          "the world does not move, or nothing but the nine floor tiles "
          "is ever instanced",
          frames=24, pad=spec.PAD_UP),      # tank controls: walk forward
]


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------
def _cart_path(name: str) -> Path:
    from . import carts
    return carts.path(name)


def check_witnesses() -> list[str]:
    """Machine 1 only, about a second: does each cart do what it claims?"""
    from . import asm

    bad = []
    for c in CLAIMS:
        p = _cart_path(c.cart)
        if not p.exists():
            bad.append(f"{c.cart}: MISSING ({p.relative_to(ROOT)})")
            continue
        try:
            o = Observed(asm.assemble(p), frames=c.frames, pad=c.pad,
                         start=c.start)
        except Exception as e:                    # a cart that cannot run
            bad.append(f"{c.cart}: will not run -- {e}")
            continue
        if not c.witness(o):
            bad.append(f"{c.cart}: claims '{c.proves}' but {c.why}")
    return bad


def _gate(cart: str, gate: str, frames: int) -> tuple[str, str, int, str]:
    """One gate on one cart, in its own process so they can run at once."""
    argv = ["glass", str(_cart_path(cart))] if gate == "glass" else \
           ["cross", str(_cart_path(cart)), "-f", str(frames)]
    r = subprocess.run([sys.executable, "-c",
                        "import sys;from zeta import cli;"
                        "sys.exit(cli.main(sys.argv[1:]))", *argv],
                       capture_output=True, text=True, cwd=ROOT)
    tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    return cart, gate, r.returncode, (tail[-1] if tail else
                                      (r.stderr or "").strip()[-160:])


def run(gates=("glass", "cross"), frames: int = 120, jobs: int = 8) -> int:
    print(f"the standing gate: {len(CLAIMS)} subsystems, "
          f"{', '.join(gates)}\n")

    print("witnesses (machine 1) -- does each cart exercise its claim?")
    bad = check_witnesses()
    for c in CLAIMS:
        mark = "FAIL" if any(b.startswith(c.cart + ":") for b in bad) else "ok"
        print(f"  {mark:>4}  {c.cart:<9} {c.proves}")
    if bad:
        print("\nWITNESS FAILURE -- these carts do not prove what the table")
        print("says they prove, so their gate results are meaningless:")
        for b in bad:
            print(f"  {b}")
        return 1

    # build both simulations ONCE; they are content-hash cached, and
    # concurrent builders would race for the same directory
    from . import silicon
    if "cross" in gates:
        silicon.build()
    if "glass" in gates:
        silicon.build_glass()

    work = [(c.cart, g) for c in CLAIMS for g in gates]
    print(f"\ngates (machine 2) -- {len(work)} runs, {jobs} at a time")
    fails = []
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(_gate, cart, g, frames) for cart, g in work]
        for f in cf.as_completed(futs):
            cart, gate, rc, line = f.result()
            print(f"  {'ok' if rc == 0 else 'FAIL':>4}  "
                  f"{cart:<9} {gate:<6} {line[:96]}")
            if rc:
                fails.append(f"{cart} {gate}: {line}")

    if fails:
        print(f"\nSUITE FAIL: {len(fails)} of {len(work)}")
        for f in fails:
            print(f"  {f}")
        return 1
    print(f"\nSUITE PASS: {len(CLAIMS)} subsystems, {len(work)} gate runs, "
          f"every cart witnessed against its own claim")
    return 0


def glass_queue() -> int:
    """The claims that have never been seen on the REAL panel. The cross
    and glass gates prove the two simulated machines; this is the queue
    of what still rests on them alone. Burn it down with `zeta sd push`,
    Menu+Start on the Pocket, `zeta sd witness CART` -- and record the
    witnessing by filling the claim's `glass` field."""
    seen = [(c.cart, c.glass) for c in CLAIMS if c.glass]
    queue = [(c.cart, c.proves) for c in CLAIMS if not c.glass]
    print(f"witnessed on glass ({len(seen)}):")
    for cart, how in seen:
        print(f"  {cart:<10} {how}")
    print(f"\nthe queue ({len(queue)}) -- proven in simulation only:")
    for cart, proves in queue:
        print(f"  {cart:<10} {proves[:62]}")
    print("\n(a pre-build-94 boot may well have shown some of these; a "
          "witnessing nobody wrote down is a witnessing the queue does "
          "not count)")
    return 0
