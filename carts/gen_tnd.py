# gen_tnd.py -- TEAR NOT DEMON on the Zeta. docs/TND-PORT.md.
#   P1 the fighter (below), P2 the street, P3 the demons -- and the frame
#   budget work that let all three fit (docs/TND-PORT.md, "the frame,
#   measured"; tools/tnd_meter.py).
#
# The July game's boxer (737 faces, 459 vertices, 67-joint skinning, float
# IK) played back BAKED: tools/tnd_extract.py freezes the archive's own
# animation; this quantises it to Q16.16 and lays it out so ONE mover
# request a frame repaints the whole body.
#
# TWO OBJECTS, ONE CUT. A Zeta object holds 256 vertices and 512 faces;
# the boxer needs two. Exactly one horizontal cut satisfies both limits,
# at hip height (archive z = 1.009): upper 378 faces / 253 vertices,
# lower 359 / 244. Seam vertices are DUPLICATED, and both halves bake
# from the same posed positions, so the waist cannot tear.
#
# ONE DMA, THE WHOLE SPAN. The two meshes sit back to back in DMEM, and
# the mover moves one contiguous block a frame, so each pose in the bank
# is the span from the upper vertices to the end of the lower faces --
# 2,967 words, inside DMA_MAX. Face colours ride inside the span, which
# means every pose carries THE ARCHIVE'S OWN PER-FACE SHADING for that
# frame: TND's light, played back rather than approximated.
#
# AXES. The archive is right-handed z-up, forward +x (the guard fists sit
# ahead of the torso along x). Zeta's view space is x-right, y-up,
# z-forward: left-handed. Mapping left->left keeps the lead hand on the
# correct side, at the price of mirroring winding -- hence FLIP below,
# set by looking at the first render rather than by assuming.

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import bakepcm, spec                               # noqa: E402
from zeta.forge import ONE, Cart, Mesh, Plate, Table, Text                # noqa: E402

HERE = Path(__file__).parent
# THE BUDGET HOOK: TND_OMIT=buildings,paint,... drops street parts and
# TND_OUT sends the variant elsewhere -- for decomposing the frame cost
# one part at a time (the street measured 94.8% before any demon).
import os                                                    # noqa: E402
OMIT = set(filter(None, os.environ.get("TND_OMIT", "").split(",")))
# THE SONG BUILD: TND_SONG=1 plays the archive's RECORDED theme through
# its song structure instead of the synth theme (P7 below). The record is
# third-party, so this build is LOCAL: it bakes from the gitignored
# assets/tnd/song.npz (tools/tnd_song.py) and writes to the gitignored
# build/song/, and the column there (gen_shelf, gen_face with the same
# flag) is what the card carries. The committed carts stay synth.
SONG = os.environ.get("TND_SONG") == "1"
# THE STRESS HOOK (frontier C1): TND_STRESS=n draws n extra demons -- each
# a RENDER-ONLY clone of demon 0, 1, 2, 0, ... in its pose, standing a
# stride beside it. It measures what the machine does when TND's own
# combat scene grows: the object list holds 64 and the frame's vertex
# cache 2,048, and the fight already lists 50 and projects 2,049. A local
# build like TND_OMIT's, never a committed cart.
STRESS = int(os.environ.get("TND_STRESS", "0"))
SONG_CH = range(4, 11)          # the record's voices (the synth theme's, freed)
SONG_VOL = 15                   # each voice's level at full bus (x bus / 256)
OUT = Path(os.environ.get("TND_OUT", HERE.parent / "build" / "song" / "tnd.zol"
                          if SONG else HERE / "tnd.zol"))
OUT.parent.mkdir(parents=True, exist_ok=True)
BAKE = HERE.parent / "assets" / "tnd" / "boxer.npz"
CUT = 1.009                     # the one hip-height cut that fits both
FLIP = True                     # winding, after the left-handed mirror

d = np.load(BAKE)
F, C = d["F"], d["C"]
SEQS = ("idle", "walk", "air", "jab", "cross", "lead_hook", "rear_hook", "special",
        "lead_uppercut", "rear_uppercut", "gun", "gun_charged",
        "run", "kite_fwd", "kite_back", "kite_left", "kite_right",
        "flip_fwd", "flip_back", "flip_cart",
        "dodge_fwd", "dodge_back", "dodge_left", "dodge_right")


def to_zeta(V):
    """archive (x fwd, y left, z up) -> zeta (x right, y up, z fwd)."""
    return np.stack((-V[:, 1], V[:, 2], V[:, 0]), axis=1)


def rgb(c):
    return (int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])


# ---- the cut, chosen on the bind-ish first idle frame -------------------
V0 = d["V_idle"][0]
upper = V0[F].mean(1)[:, 2] >= CUT
halves = []
for mask in (upper, ~upper):
    faces = F[mask]
    vids = np.unique(faces)                         # this half's vertices
    remap = {int(v): i for i, v in enumerate(vids)}
    tri = [(remap[int(a)], remap[int(b)], remap[int(c)]) for a, b, c in faces]
    if FLIP:
        tri = [(a, c, b) for a, b, c in tri]
    halves.append((mask, vids, tri))
assert all(len(v) <= spec.MESH_NV_MAX and len(t) <= spec.MESH_NF_MAX
           for _, v, t in halves)


def half_words(V, S, h):
    """One half as Mesh words for a pose: posed vertices, that frame's
    per-face shading."""
    mask, vids, tri = h
    P = np.round(to_zeta(V[vids]) * ONE).astype(np.int64).reshape(-1)
    cols = S[mask]
    faces = [(a, b, c, rgb(cols[k])) for k, (a, b, c) in enumerate(tri)]
    return Mesh(P.tolist(), faces).words()


def pose_span(V, S):
    """The DMA span for a pose: everything from the upper vertices to the
    end of the lower faces (both halves' words minus the upper header)."""
    return (half_words(V, S, halves[0])[2:] + half_words(V, S, halves[1]))


# THE HUD'S PROMISE: at most 78 display-list triangles, ever -- the rank
# (SSS: 30), the combo at its worst digits (X55: 30) and the wordmark
# (TND: 18) together, or RETRY (38) alone, or the title's BEST and a rank
# (P14: 64) -- so the list's other 1,246 words hold content. It was 80,
# on a count of 76 that was two short (X99 is 30, not 28): two triangles
# nobody drew, 14 words, which P14's save needed in a DMEM with none
# left. The promise is PROVED below from the font, not counted by hand.
DL_LEASE = 78

# ---- P8's sizes, which the cart needs before anything is placed -------------
# THE ATTRACT INTRO (P8, below) is a SECOND PROGRAM, paged in by the overlay
# mover, and its text needs more display list than the fight promises: the
# opening line alone is 146 triangles. So the cart holds back two BORROWED
# reserves of the leased tail (forge.Cart dl_borrow) and fills them with
# constants only the fight reads: the intro draws over the front, parks its
# own font, strings and per-frame row in the end, and its last two frames
# put both back from the cart with the mover.
from zeta.forge import glyph_rects                          # noqa: E402
INTRO_LEN = 415                  # tear.py INTRO_LEN: then the title
INTRO_BEAT1 = "THE EVE OF THE APOCALYPSE"
INTRO_BEAT2 = "TEAR THROUGH THE NIGHT"
INTRO_STRS = (INTRO_BEAT1, INTRO_BEAT2, "TEAR", "NOT DEMON")
INTRO_FONT_CH = "".join(sorted(set("".join(INTRO_STRS)) - {" "})) + " "


def _rects(text):
    return sum(len(glyph_rects(c)) for c in text)


INTRO_TRIS = 2 * max(_rects(INTRO_BEAT1), _rects(INTRO_BEAT2),
                     3 * _rects("TEAR") + _rects("NOT DEMON"))   # (+2 ghosts)
INTRO_RW = 16                    # a frame's row: camera, colours, rects
INTRO_CELLS = 4                  # ...and the intro's own cells after it
FONT_CH = "DCBASRETYXN0123456789"
assert len(INTRO_FONT_CH) <= len(FONT_CH)
_digit = max(_rects(d) for d in "0123456789")
_rank = max(_rects(r) for r in ("D", "C", "B", "A", "S", "SS", "SSS"))
assert 2 * (_rank + _rects("X") + 2 * _digit + _rects("TND")) <= DL_LEASE, "the HUD"
assert 2 * _rects("RETRY") <= DL_LEASE, "RETRY"
assert 2 * (_rects("BEST") + _rank) <= DL_LEASE, "the title's BEST"
B_FRONT = spec.DL_STRIDE * (INTRO_TRIS - DL_LEASE)
B_END = 2 * len(FONT_CH) + sum(len(t) + 1 for t in INTRO_STRS) + INTRO_RW + INTRO_CELLS
cart = Cart("tnd", dl_lease=DL_LEASE, dl_borrow=(B_FRONT, B_END))


def font_words(chars):
    """A glyph is its rectangles PACKED -- see the HUD's words, P6."""
    out = []
    for c in chars:
        rs = glyph_rects(c)
        assert len(rs) <= 6, c
        packed = [x | y << 2 | w << 5 | (h - 1) << 7 for x, y, w, h in rs]   # w >= 1: 0 is none
        packed += [0] * (6 - len(packed))
        out += [packed[0] | packed[1] << 10 | packed[2] << 20,
                packed[3] | packed[4] << 10 | packed[5] << 20]
    return out


FONT = cart.data(Table(font_words(FONT_CH)), "font", borrow="end")

# ---- P8's data: the flight, the words, the images (its program is below) ----
INTRO_KEYS = ((0, 13.0, -11.0, 0.55, 1.0, -1.0, 1.2), (95, 9.0, -2.0, 1.05, 1.5, 0.5, 1.4),
              (150, 6.5, 6.5, 1.70, 0.0, 0.0, 1.4), (205, -2.0, 8.5, 2.40, 0.0, 0.0, 1.5),
              (255, -6.0, 10.5, 4.60, 0.0, 0.0, 1.0), (300, 0.5, 12.5, 7.00, 0.0, 0.0, 0.6),
              (345, 0.3, 7.0, 3.40, 0.0, 0.0, 1.6), (380, 0.2, 4.4, 2.30, 0.0, 0.0, 1.6))
BONE, ASH_DIM, BLOOD = (216, 207, 193), (140, 133, 124), (214, 58, 54)
GHOST_C, GHOST_W, FLASH_RGB = (90, 40, 200), (255, 140, 60), (236, 232, 240)
VEIL, BAR = (5, 4, 8), (4, 3, 6)
ATTRACT = 1500                       # tear.py ATTRACT_IDLE: the intro replays


def intro_row(t):
    """tear.py _intro_cam and _intro, frame t, as one row of words"""
    k = INTRO_KEYS
    if t <= k[0][0]:
        v = k[0][1:]
    elif t >= k[-1][0]:
        v = k[-1][1:]
    else:
        a, b = next((a, b) for a, b in zip(k, k[1:]) if a[0] <= t <= b[0])
        u = (t - a[0]) / (b[0] - a[0])
        u = u * u * (3 - 2 * u)
        v = [x + (y - x) * u for x, y in zip(a[1:], b[1:])]
    cx, cy, cz, lx, ly, lz = v
    cx += np.sin(t * 0.05) * 0.06                # the handheld breath
    cz += np.sin(t * 0.037 + 1.0) * 0.04
    cam, look = (-cy, cz, cx), (-ly, lz, lx)     # archive -> zeta axes
    dx, dy, dz = (b - a for a, b in zip(cam, look))
    turn = 1024 / (2 * np.pi)
    yaw = int(round(np.arctan2(-dx, dz) * turn)) & 1023
    pit = int(round(np.arctan2(-dy, np.hypot(dx, dz)) * turn)) & 1023
    q16 = [int(round(c * ONE)) for c in cam]

    def band(t0, t1, fade=16):
        return 0.0 if t < t0 or t >= t1 else max(0.0, min(1.0, (t - t0) / fade, (t1 - t) / fade))

    def col(c, a):
        return rgb([min(255, int(round(x * a))) for x in c]) if a > 0 else 0
    a1, a2 = band(26, 152), band(176, 292)
    tr = t - 305
    slam = min(1.0, tr / 5.0) if tr >= 0 else 0.0
    pulse = 0.9 + 0.1 * np.sin(t / 16.0)
    if t < 24:
        full = (0x000000, 1.0 - t / 24.0)
    elif 0 <= tr < 7:
        full = (rgb(FLASH_RGB), 0.7 * (1 - tr / 7.0))
    else:
        full = (rgb(VEIL), 0.12 + 0.05 * np.sin(t / 40.0))
    barh = int(40 * min(1.0, t / 14.0))
    return [*q16, yaw, pit,
            int(round(np.sin(pit / turn) * ONE)), int(round(np.cos(pit / turn) * ONE)),
            col(ASH_DIM, a1 * 0.9 * 0.95), col(BLOOD, a2 * 0.95),
            col(GHOST_C, 0.16 * slam), col(GHOST_W, 0.16 * slam),
            col(BONE, slam * pulse * 0.95), col(BLOOD, slam * 0.95),
            full[0] | int(round(16 * full[1])) << 24, barh,
            rgb(BAR) | (16 << 24 if barh else 0)]


ROWS = cart.cram(Table([w for t in range(INTRO_LEN + 2) for w in intro_row(t)]), "intro_rows")
assert all(len(intro_row(t)) == INTRO_RW for t in (0, 300))
END_LO, FRONT_LO = cart._borrow_lo["end"], cart._borrow_lo["front"]
_ig = [len(x) + 1 for x in INTRO_STRS]
I_STR = [END_LO + 2 * len(FONT_CH) + sum(_ig[:i]) for i in range(len(INTRO_STRS))]
I_ROW = END_LO + 2 * len(FONT_CH) + sum(_ig)
I_T, I_X = I_ROW + INTRO_RW, I_ROW + INTRO_RW + 1
_iend = font_words(INTRO_FONT_CH)
_iend += [0] * (2 * len(FONT_CH) - len(_iend))
for x in INTRO_STRS:
    _iend += [len(x)] + [INTRO_FONT_CH.index(c) for c in x]
_iend += intro_row(0) + [0] * INTRO_CELLS
assert len(_iend) == B_END
END_INTRO = cart.cram(Table(_iend), "intro_end")
# P13: THE PAUSE's end image -- its font (the glyphs of its two words) at
# FONT's address, the words, and its cursor cell -- the intro's handshake
PAUSE_STRS = ("RESUME", "QUIT")
PAUSE_FONT_CH = "".join(sorted(set("".join(PAUSE_STRS)))) + " "
_pend = font_words(PAUSE_FONT_CH)
_pend += [0] * (2 * len(FONT_CH) - len(_pend))
P_STR = []
for x in PAUSE_STRS:
    P_STR.append(END_LO + len(_pend))
    _pend += [len(x)] + [PAUSE_FONT_CH.index(c) for c in x]
P_CUR = END_LO + len(_pend)
_pend += [0]
_pend += [0] * (B_END - len(_pend))
END_PAUSE = cart.cram(Table(_pend), "pause_end")
# the images filled once everything is placed (the end of this file)
INTRO_PROG = cart.cram(Table([0] * spec.OVL_MAX), "intro_prog")
PAUSE_PROG = cart.cram(Table([0] * spec.OVL_MAX), "pause_prog")
MAIN_PROG = cart.cram(Table([0] * spec.OVL_MAX), "main_prog")
END_MAIN = cart.cram(Table([0] * B_END), "main_end")
FRONT_MAIN = cart.cram(Table([0] * B_FRONT), "main_front")


def ir(k):
    return I_ROW + k


def mover(g, cells, src, dst, n):
    for c, v in zip(cells, (src, dst, n, 1)):
        g.set(c, v)


def black(g):
    g.set(spec.OL_BASE, 0).set(spec.DL_BASE, 0).set(spec.BG_SRC, 0)
    g.set(spec.CO_BASE, 1)
    g.rect(0, 0, 0, spec.W - 1, spec.H - 1, 0x000000, 16)



# ---- the body: two meshes, back to back, holding the first idle pose ----
first = half_words(d["V_idle"][0], d["S_idle"][0], halves[0]) \
    + half_words(d["V_idle"][0], d["S_idle"][0], halves[1])
BODY = cart.data(Table(first), "body")
SPAN = len(first) - 2
UPPER, LOWER = int(BODY), int(BODY) + len(half_words(
    d["V_idle"][0], d["S_idle"][0], halves[0]))
assert SPAN <= spec.DMA_MAX, f"pose span {SPAN} exceeds DMA_MAX"

# ---- the pose bank: every frame of every sequence, one span each ---------
# (Build 105's second dies doubled the segment, so the song build no
# longer stores each distinct pose once through an index: the index's
# ~180 words of DMEM were worth more than the CRAM it saved. DEDUPE keeps
# the switch.)
DEDUPE = False
bank, base, slot, seen = [], {}, [], {}
for s in SEQS:
    base[s] = len(slot)
    for V, S in zip(d["V_" + s], d["S_" + s]):
        w = pose_span(V, S)
        k = tuple(w) if DEDUPE else len(slot)
        if k not in seen:
            seen[k] = len(bank) // SPAN
            bank += w
        slot.append(seen[k])
BANK = cart.cram(Table(bank), "poses")
NPOSE = {s: len(d["V_" + s]) for s in SEQS}
if DEDUPE:
    _sl = slot + [0] * (len(slot) & 1)
    PSLOT = cart.data(Table([_sl[i] | _sl[i + 1] << 16 for i in range(0, len(_sl), 2)]),
                      "pose_slot")

# ---- THE STREET: Bancroft and Shattuck, from the archive's constants -----
# tear.py:5176-5420 builds the "+" from hand-placed constants; the ~11,000
# triangles it submitted were mostly subdivision to dodge a near-plane
# reject the Zeta's clipper does not have. Here the asphalt is TEN faces.
# Archive world is (x, y, z-up) like the boxer, mapped the same way.
A_R = 11.0                       # ARENA_R
EDGE = A_R + 0.5                 # the slab overshoots the square
LANE = A_R - 3.2                 # street half-width, 7.8
REACH = 48.0                     # each arm's length: the archive's 54, cut
                                 # where its own fog is already total (47)
ROAD_HALF = A_R + 0.25
SW_OUT = LANE + 1.1              # the sidewalk's outer edge
ASPHALT, SIDEWALK = (46, 45, 49), (92, 90, 94)
PAINT, LINE = (200, 195, 185), (196, 168, 70)
BCOL = ((28, 22, 26), (34, 26, 24), (24, 20, 22), (30, 24, 28))


def W(x, y, z):
    """archive world -> zeta world, the boxer's own mapping."""
    return np.array((-y, z, x), float)


def shade(col, n):
    """the archive's shade(strength=0.4), as a fixed light per face."""
    k = {(0, 0, 1): 1.15, (1, 0, 0): 1.0, (-1, 0, 0): 0.78,
         (0, 1, 0): 0.9, (0, -1, 0): 0.86}.get(tuple(n), 1.0)
    return tuple(min(255, int(c * k)) for c in col)


class Build:
    """A mesh under construction, vertices shared by position."""
    def __init__(self):
        self.v, self.idx, self.f = [], {}, []

    def vert(self, P):
        key = tuple(int(round(c * ONE)) for c in P)
        if key not in self.idx:
            self.idx[key] = len(self.v)
            self.v.append(key)
        return self.idx[key]

    def quad(self, corners, n, col, nu=1, nv=1):
        """corners in archive space, in order round the quad; n its
        outward normal. Front-facing on this machine is (b-a)x(c-a)
        toward the viewer -- derived from the P1 floor, which drew from
        above -- so the order is CHECKED against n, never assumed.
        nu, nv cut it into a grid (along c0->c1, c0->c3): see SPLIT."""
        C = [np.array(c, float) for c in corners]
        for i in range(nu):
            for j in range(nv):
                def at(u, v):
                    return (C[0] * (1 - u) * (1 - v) + C[1] * u * (1 - v)
                            + C[2] * u * v + C[3] * (1 - u) * v)
                u0, u1, v0, v1 = i / nu, (i + 1) / nu, j / nv, (j + 1) / nv
                self._quad1([at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)],
                            n, col)

    def _quad1(self, corners, n, col):
        P = [W(*c) for c in corners]
        ids = [self.vert(q) for q in P]
        a, b, c, d = ids
        if np.dot(np.cross(P[1] - P[0], P[2] - P[0]), W(*n)) < 0:
            a, b, c, d = a, d, c, b
        rgb_ = rgb(shade(col, n))
        self.f += [(a, b, c, rgb_), (a, c, d, rgb_)]

    def box(self, x0, x1, y0, y1, z0, z1, col, top=True,
            sides=((1, 0), (-1, 0), (0, 1), (0, -1)), nx=1, ny=1):
        """only the faces in `sides` (outward normals in x/y) are built:
        a face nobody can see still costs its setup, and a face behind
        another still costs every pixel it covers. nx, ny: pieces along
        x and y, on every face that runs that way."""
        if top:
            self.quad([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
                      (0, 0, 1), col, nx, ny)
        if (1, 0) in sides:
            self.quad([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
                      (1, 0, 0), col, ny, 1)
        if (-1, 0) in sides:
            self.quad([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
                      (-1, 0, 0), col, 1, ny)
        if (0, 1) in sides:
            self.quad([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
                      (0, 1, 0), col, nx, 1)
        if (0, -1) in sides:
            self.quad([(x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0)],
                      (0, -1, 0), col, 1, nx)

    def flat(self, x0, x1, y0, y1, z, col, nx=1, ny=1):
        self.quad([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)],
                  (0, 0, 1), col, nx, ny)

    def mesh(self):
        assert len(self.v) <= spec.MESH_NV_MAX and len(self.f) <= spec.MESH_NF_MAX
        return Mesh([c for v in self.v for c in v], self.f)

    def meshes(self):
        """as many meshes as the object limits need, faces in order"""
        out, cur, vmap = [], [], {}
        for f in self.f + [None]:
            need = 0 if f is None else len({*f[:3]} - vmap.keys())
            if f is None or len(vmap) + need > spec.MESH_NV_MAX \
                    or len(cur) + 1 > spec.MESH_NF_MAX:
                if cur:
                    vs = sorted(vmap, key=vmap.get)
                    out.append(Mesh([c for v in vs for c in self.v[v]], cur))
                cur, vmap = [], {}
                if f is None:
                    break
            for v in f[:3]:
                vmap.setdefault(v, len(vmap))
            cur.append((vmap[f[0]], vmap[f[1]], vmap[f[2]], f[3]))
        return out


# ---- P3: THE DEMONS -- three builds of one rigid rig ------------------------
# The archive's demons are not skinned: rig.fighter is 17 rigid joints,
# and five of them (neck, both fists, both feet) never rotate against
# their parent -- MEASURED over every clip, max deviation 0.0 -- so they
# merge into it. Twelve parts, twelve objects a demon, each placed by its
# own angles word (yaw | pitch << 10 | roll << 20, spec.OL_STRIDE).
#
# WHAT IS BAKED AND WHAT IS NOT. A joint's character-local ROTATION
# depends only on the pose; its POSITION depends on the build too (the
# brute is 1.35 tall, the heavy 0.95). So the clip table holds one packed
# angles word per part per frame and serves all three builds, and the
# cart walks the offsets through the parents at run time -- three small
# rotations a part, the same chain the GPU itself runs. That is the
# difference between 1,392 words of clips and 4,176.
#
# LEFT IS RIGHT. A shoulder's mesh in its own frame is identical on both
# sides (checked: every vertex, every colour), so the two arms and the
# two legs draw from one mesh each: eight meshes a build, not twelve.
DEM = np.load(HERE.parent / "assets" / "tnd" / "demons.npz")
JN = list(DEM["names"])
PARTS = (  # part, joints merged into it (root first), parent part, mesh key
    ("pelvis", ("pelvis",), None, "pelvis"),
    ("spine", ("spine",), "pelvis", "spine"),
    ("chest", ("chest", "neck"), "spine", "chest"),
    ("head", ("head",), "chest", "head"),
    ("shoulder_l", ("shoulder_l",), "chest", "shoulder"),
    ("elbow_l", ("elbow_l", "fist_l"), "shoulder_l", "elbow"),
    ("shoulder_r", ("shoulder_r",), "chest", "shoulder"),
    ("elbow_r", ("elbow_r", "fist_r"), "shoulder_r", "elbow"),
    ("hip_l", ("hip_l",), "pelvis", "hip"),
    ("knee_l", ("knee_l", "foot_l"), "hip_l", "knee"),
    ("hip_r", ("hip_r",), "pelvis", "hip"),
    ("knee_r", ("knee_r", "foot_r"), "hip_r", "knee"),
)
PN = [pt[0] for pt in PARTS]
NPART = len(PARTS)
CLIPS = ("idle", "walk", "cross", "hook", "hurt", "dead")
MOVES = DEM["moves"]                       # cross, hook: startup active recovery dmg

# archive -> zeta for vectors and for rotations: M is a reflection, so a
# rotation conjugates (R' = M R M^T) and stays a rotation
MZ = np.array(((0, -1, 0), (0, 0, 1), (1, 0, 0)), float)


def euler(R):
    """R (zeta axes) = Yaw(y) Pitch(p) Roll(r), the GPU's model order, as
    10-bit units. At the pole pitch takes it all and roll is 0."""
    p = np.arcsin(np.clip(-R[1, 2], -1, 1))
    if abs(np.cos(p)) < 1e-6:
        r, y = 0.0, np.arctan2(R[2, 0], R[0, 0])
    else:
        r = np.arctan2(R[1, 0], R[1, 1])
        y = np.arctan2(-R[0, 2], R[2, 2])
    u = [int(round(a * 1024 / (2 * np.pi))) & 1023 for a in (y, p, r)]
    return u[0] | u[1] << 10 | u[2] << 20


def rot_units(w):
    """the packed word back to a matrix, for the bake's own check"""
    y, p, r = [((w >> s) & 1023) * 2 * np.pi / 1024 for s in (0, 10, 20)]
    cy, sy, cp, sp, cr, sr = np.cos(y), np.sin(y), np.cos(p), np.sin(p), \
        np.cos(r), np.sin(r)
    Ry = np.array(((cy, 0, -sy), (0, 1, 0), (sy, 0, cy)))
    Rp = np.array(((1, 0, 0), (0, cp, -sp), (0, sp, cp)))
    Rr = np.array(((cr, -sr, 0), (sr, cr, 0), (0, 0, 1)))
    return Ry @ Rp @ Rr


def shells(tris):
    """connected pieces of a triangle soup (by shared positions): each is
    one of the archive's convex solids"""
    key = lambda v: tuple(np.round(v, 6))                      # noqa: E731
    par = {}

    def find(a):
        while par.setdefault(a, a) != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for t in tris:
        ks = [key(v) for v in t]
        for k in ks[1:]:
            par[find(ks[0])] = find(k)
    return [find(key(t[0])) for t in tris]


def part_mesh(tris, cols):
    """archive-local triangles -> a Zeta mesh, every face wound OUTWARD
    from its own solid's centre. The archive drew both sides, so its
    tapers are wound inward (chest 40% outward, neck 0%); this machine
    culls, so the bake decides, solid by solid."""
    Z = tris @ MZ.T
    sid = shells(tris)
    cen = {s: Z[[i for i, x in enumerate(sid) if x == s]].reshape(-1, 3).mean(0)
           for s in set(sid)}
    b = Build()
    for t, c, s in zip(Z, cols, sid):
        ids = [b.vert(v) for v in t]
        n = np.cross(t[1] - t[0], t[2] - t[0])
        if np.dot(n, t.mean(0) - cen[s]) < 0:
            ids = [ids[0], ids[2], ids[1]]
        b.f.append((*ids, rgb(c)))
    return b.mesh()


def joint_geom(i, j):
    k = JN.index(j)
    return DEM[f"b{i}_j{k}_tris"], DEM[f"b{i}_j{k}_cols"]


def offset(i, j):
    return DEM[f"b{i}_offset"][JN.index(j)]


DMESH, DJT = [], []                    # per build: mesh syms, joint table
for i in range(3):
    meshes = {}
    for name, joints, parent, mk in PARTS:
        if mk in meshes:
            continue
        T, C = [], []
        acc = np.zeros(3)
        for n, j in enumerate(joints):          # merged joints, rigid chain
            if n:
                acc = acc + offset(i, j)
            t, c = joint_geom(i, j)
            T.append(t + acc)
            C.append(c)
        if name == "head":
            T.append(DEM[f"b{i}_spike_tris"])
            C.append(DEM[f"b{i}_spike_cols"])
        meshes[mk] = cart.data(part_mesh(np.concatenate(T), np.concatenate(C)),
                               f"demon{i}_{mk}")
    DMESH.append(meshes)

PT = cart.var("dem_pt", 3 * NPART)     # FK scratch: char-local part origins
rows_all = []
for i in range(3):
    rows = []
    for name, joints, parent, mk in PARTS:
        o = offset(i, joints[0])
        if name == "head":                     # through the merged neck
            o = o + offset(i, "neck")
        par = PN.index(parent) if parent else -1
        oz = MZ @ o
        rows += [par, int(PT) + 3 * max(par, 0)] + \
            [int(round(v * ONE)) for v in oz] + [int(DMESH[i][mk])]
    DJT.append(cart.data(Table(rows), f"demon{i}_joints"))
    rows_all.append(rows)

# the clip table: one packed angles word per part per frame
clipw, CLIP0 = [], {}
for c in CLIPS:
    CLIP0[c] = len(clipw) // NPART
    R = DEM["R_" + c]
    for f in range(len(R)):
        for name, joints, *_ in PARTS:
            clipw.append(euler(MZ @ R[f, JN.index(joints[0])] @ MZ.T))
CLIPT = cart.data(Table(clipw), "demon_clips")
CLIPN = {c: len(DEM["R_" + c]) for c in CLIPS}

# THE BAKE CHECKS ITSELF: the run-time chain, done here in floats with the
# QUANTISED angles, must put every joint where the archive's own FK did.
_err = 0.0
for i in range(3):
    for c in CLIPS:
        T = DEM["T_" + c][i]
        for f in range(len(T)):
            P = []
            for k, (name, joints, parent, mk) in enumerate(PARTS):
                o = np.array(rows_all[i][6 * k + 2:6 * k + 5]) / ONE
                if parent is None:
                    P.append(o)
                else:
                    q = PN.index(parent)
                    P.append(P[q] + rot_units(clipw[(CLIP0[c] + f) * NPART + q]) @ o)
                _err = max(_err, np.abs(P[k] - MZ @ T[f, JN.index(joints[0])]).max())
assert _err < 0.01, f"demon FK drifts {_err:.4f} units from the archive"

# Long thin strips at ground level are cut along their length: a long
# face's depth, interpolated linearly in screen space, over-reads, and
# would sink below the ground (THE GROUND RIDES THE CAMERA, below).
CUTS = {"walk": 6, "line": 6}
SP_ = lambda k: CUTS.get(k, 1)                        # noqa: E731

street = []
# NO ROAD GEOMETRY: the asphalt is ground_mesh(), which rides the camera.
# (Measured first, 2026-11-19, on the brawl route: the old ten faces
# walked 110k-189k pixels a frame. A BACKDROP PLATE was tried -- the
# camera's height, pitch and roll never change, so the ground is the same
# on every row -- and cost MORE: reading a full-screen plate is ~136k
# clocks a frame on its own, where the clear it replaces is ~98k.)

walk = Build()                   # sidewalks: raised 0.12, curb faces in
# The arms' long curbs are gone: 0.12 tall and seen edge-on, they were a
# line of pixels bought with a third of the sidewalks' DMEM -- and the
# tops must be cut into pieces now (THE GROUND RIDES THE CAMERA, below)
for sgn in (-1, 1):
    a0, a1 = (EDGE, REACH) if sgn > 0 else (-REACH, -EDGE)
    for side in (-1, 1):
        l0, l1 = (LANE, SW_OUT) if side > 0 else (-SW_OUT, -LANE)
        walk.box(a0, a1, l0, l1, 0.0, 0.12, SIDEWALK,         # E/W arms
                 sides=((-sgn, 0),), nx=SP_("walk"))
        walk.box(l0, l1, a0, a1, 0.0, 0.12, SIDEWALK,         # N/S arms
                 sides=((0, -sgn),), ny=SP_("walk"))
for sx in (-1, 1):
    for sy in (-1, 1):
        x0, x1 = sorted((sx * LANE, sx * EDGE))
        y0, y1 = sorted((sy * LANE, sy * EDGE))
        walk.box(x0, x1, y0, y1, 0.0, 0.12, SIDEWALK,         # corner pads
                 sides=((-sx, 0), (0, -sy)))
street.append(walk) if "sidewalks" not in OMIT else None

paint = Build()                  # the centreline and four zebra bands
for sgn in (-1, 1):
    a0, a1 = (EDGE, REACH) if sgn > 0 else (-REACH, -EDGE)
    paint.flat(a0, a1, -0.09, 0.09, 0.04, LINE, SP_("line"), 1)
    paint.flat(-0.09, 0.09, a0, a1, 0.04, LINE, 1, SP_("line"))
for off in (A_R - 2.0, -(A_R - 2.0)):
    x = -LANE
    while x < LANE:
        x1 = min(x + 0.7, LANE)
        paint.flat(x, x1, off - 1.5, off + 1.5, 0.04, PAINT)     # across x
        paint.flat(off - 1.5, off + 1.5, x, x1, 0.04, PAINT)     # across y
        x += 1.2
street.append(paint) if "paint" not in OMIT else None

blocks = []                      # 12 corner + 48 street buildings
for sx in (-1, 1):
    for sy in (-1, 1):
        for j in range(3):
            w = d = 4.6 + (j % 2) * 2.0
            h = 7.5 + j * 3.4
            col = BCOL[(j + (sx > 0) + 2 * (sy > 0)) % 4]
            bx = sx * (ROAD_HALF + w / 2 + j * 2.0)
            by = sy * (ROAD_HALF + d / 2 + j * 2.0)
            blocks.append((bx, by, w, d, h, col))
# THE STREET BUILDINGS BECOME FACADES. The archive's 48 boxes cost
# ~287k clocks a frame here -- measured, by omission -- because looking
# down an arm ten fronts a side stack in depth and the rasteriser pays
# every pixel of every face, hidden or not. A continuous facade per side
# keeps the archive's heights: one front a segment, plus only the height
# steps that FACE the crossing (the camera stands 2.15 high and the roofs
# are 8-17, so no roof is ever seen).
fac = Build()


def arm(dx, dy, u, v, z):
    """an arm's local frame (u out along the arm, v lateral) -> archive"""
    return (dx * u, v, z) if dx else (v, dy * u, z)


for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
    out = (dx, dy, 0)
    for side in (-1, 1):
        face_v = side * (LANE + 1.3)                     # the street wall
        back_v = side * (LANE + 1.3 + 6.0)
        n_front = (0, -side, 0) if dx else (-side, 0, 0)
        n_step = (-dx, -dy, 0)                           # toward the crossing
        segs = []
        for dist in range(20, 46, 6):
            h = 8.0 + ((dist // 6) % 3) * 4.5
            col = BCOL[(dist // 6 + (side > 0)) % 4]
            segs.append((dist - 3.0, dist + 3.0, h, col))
        prev_h = 0.0
        for u0, u1, h, col in segs:
            fac.quad([arm(dx, dy, u0, face_v, 0), arm(dx, dy, u1, face_v, 0),
                      arm(dx, dy, u1, face_v, h), arm(dx, dy, u0, face_v, h)],
                     n_front, col, SP_("facade"))
            if h > prev_h:                               # a step we can see
                fac.quad([arm(dx, dy, u0, face_v, prev_h),
                          arm(dx, dy, u0, back_v, prev_h),
                          arm(dx, dy, u0, back_v, h),
                          arm(dx, dy, u0, face_v, h)], n_step, col)
            prev_h = h
    # the end wall at the fog line: the fog turns it into the dusk
    w = LANE + 7.3
    fac.quad([arm(dx, dy, REACH - 1, -w, 0), arm(dx, dy, REACH - 1, w, 0),
              arm(dx, dy, REACH - 1, w, 18), arm(dx, dy, REACH - 1, -w, 18)],
             (-dx, -dy, 0), BCOL[0])
street.append(fac) if not OMIT & {"buildings", "facades"} else None
# THE CORNER TOWERS AS ONE SURFACE. Each corner is three boxes that
# INTERPENETRATE (each steps 2 units back and up from the last), so a
# third of their side faces lay inside a neighbour -- never visible, and
# every buried pixel still walked. Each corner is now the boundary of the
# union: every side face minus the parts inside another box of its
# corner. No roofs: the camera never rises above 2.15 and the lowest
# roof is 7.5.
def union_sides(boxes):
    """boxes [(x0,x1,y0,y1,h,col)] -> the visible side rectangles, as
    (axis, at, lo, hi, z0, z1, normal sign, col)"""
    out = []
    for i, (x0, x1, y0, y1, h, col) in enumerate(boxes):
        for axis, at, lo, hi, sgn in ((0, x0, y0, y1, -1), (0, x1, y0, y1, 1),
                                      (1, y0, x0, x1, -1), (1, y1, x0, x1, 1)):
            cuts = []                              # (lo, hi, ztop) inside others
            for k, (a0, a1, b0, b1, hk, _) in enumerate(boxes):
                if k == i:
                    continue
                p0, p1, q0, q1 = (a0, a1, b0, b1) if axis == 0 else (b0, b1, a0, a1)
                if p0 < at < p1 and q0 < hi and q1 > lo:
                    cuts.append((max(q0, lo), min(q1, hi), hk))
            vs = sorted({lo, hi, *(c[0] for c in cuts), *(c[1] for c in cuts)})
            for v0, v1 in zip(vs, vs[1:]):
                mid = (v0 + v1) / 2
                ztop = max([c[2] for c in cuts if c[0] <= mid <= c[1]], default=0.0)
                if ztop < h:
                    out.append((axis, at, v0, v1, ztop, h, sgn, col))
    return out


corners = Build()
for sx in (-1, 1):
    for sy in (-1, 1):
        boxes = []
        for bx, by, w, d, h, col in blocks:
            if np.sign(bx) == sx and np.sign(by) == sy:
                boxes.append((bx - w / 2, bx + w / 2, by - d / 2, by + d / 2, h, col))
        for axis, at, v0, v1, z0, z1, sgn, col in union_sides(boxes):
            if axis == 0:
                q = [(at, v0, z0), (at, v1, z0), (at, v1, z1), (at, v0, z1)]
                n = (sgn, 0, 0)
            else:
                q = [(v0, at, z0), (v1, at, z0), (v1, at, z1), (v0, at, z1)]
                n = (0, sgn, 0)
            corners.quad(q, n, col)
street.append(corners) if not OMIT & {"buildings", "corners"} else None

lamps = Build()                  # four streetlights, warm
for sx in (-1, 1):
    for sy in (-1, 1):
        x, y = sx * ROAD_HALF, sy * ROAD_HALF
        lamps.box(x - .07, x + .07, y - .07, y + .07, 0.0, 3.1, (18, 16, 18))
        lamps.box(x - .22, x + .22, y - .22, y + .22, 3.0, 3.3, (255, 200, 120))
street.append(lamps) if "lamps" not in OMIT else None

# THE STREET BY PLACE, NOT BY KIND. The sequencer draws the frame in
# nine 32-row bands and, for every band an object's projected span
# touches, transforms EVERY vertex of the object again (~45 clocks each,
# zseq.v). Measured at the street route's peak, the rasteriser sat
# STARVED for 278k clocks while the sequencer re-transformed street
# meshes whose pieces, scattered over the screen, spanned every band:
# all four crosswalks as one mesh paid for each stripe 8 times over.
# (Merging whole regions -- facades with the floor under them -- spans
# the screen again, and measured no better.) So faces are grouped by
# LAYER (the floor, and what stands up) and by SECTOR (eight wedges
# round the crossing, the floor's split again near and far): compact in
# the world, so compact on screen, so each object touches few bands.
def place_of(b, f):
    P = np.array([np.array(b.v[i], float) / ONE for i in f[:3]])
    c = P.mean(axis=0)
    x, y = c[2], -c[0]                              # zeta -> archive
    sector = int(((np.arctan2(y, x) + np.pi / 8) % (2 * np.pi)) // (np.pi / 4))
    floor = P[:, 1].max() <= 0.2
    return (floor, sector, floor and np.hypot(x, y) > 2 * EDGE)


merged = {}
for b in street:
    for f in b.f:
        r = merged.setdefault(place_of(b, f), Build())
        ids = [r.vert(np.array(b.v[i], float) / ONE) for i in f[:3]]
        r.f.append((*ids, f[3]))
street = [merged[k] for k in sorted(merged)]
STREET, SPHERE = [], []        # each street object and its bounding sphere
for i, b in enumerate(street):
    for k, m in enumerate(b.meshes()):
        STREET.append(int(cart.data(m, f"street{i}_{k}")))
        V = np.array(m.verts, float).reshape(-1, 3) / ONE
        c = (V.min(0) + V.max(0)) / 2
        SPHERE.append((c, np.linalg.norm(V - c, axis=1).max()))


# 0.2 BELOW the street: everything that stands on the ground (paint at
# 0.04, curbs, feet) must read nearer than the ground at the same pixel,
# and a long face's interpolated depth over-reads -- so the ground is
# lowered until it always loses, at a cost of under a sixteenth of fog.
GROUND_Y = -0.2


def ground_mesh():
    """THE GROUND RIDES THE CAMERA. Measured on silicon, the ten asphalt
    faces walked 110k-189k pixels a frame -- the rasteriser walks every
    pixel of a triangle's bounding box, and a near-clipped quad fans into
    triangles each boxing most of the lower screen. But the camera's
    height, pitch and roll never change, so the visible ground is always
    the same trapezoid IN CAMERA SPACE, and this mesh is placed at the
    camera with the camera's yaw every frame:
      NEAR  one triangle, apex behind the bottom of the screen, base 15
            units out. Its screen-clipped box is wholly covered, so it
            walks 1x its pixels, not 2-4x. Depth is interpolated
            linearly in screen space, which over-reads a ground plane's
            depth -- so it can never hide what stands on it -- and the
            fog starts at 15, so nothing in it is fogged either way.
      FAR   four rings, 15 to 60, vertices at true depth so the fog
            ramp reads right (the error inside a ring is under half a
            sixteenth).
    Model space is camera space: x right, z forward, y = 0 the ground."""
    pit = 20 * 2 * np.pi / 1024
    vz = lambda z: 2.15 * np.sin(pit) + z * np.cos(pit)          # noqa: E731
    half = lambda z: spec.W / 2 / spec.FOCAL * vz(z) * 1.3       # noqa: E731
    V, F = [], []
    col = rgb(shade(ASPHALT, (0, 0, 1)))

    def v(x, z):
        V.append((x, GROUND_Y, z))
        return len(V) - 1

    def tri(a, b, c):
        P = [np.array(V[i]) for i in (a, b, c)]
        if np.cross(P[1] - P[0], P[2] - P[0])[1] < 0:     # face UP
            b, c = c, b
        F.append((a, b, c, col))
    apex = v(0.0, 1.0)
    # the sides must clear the bottom screen corners (2.93 out, 1.98 wide)
    w15 = (15 - 1.0) * 3.0 / (2.93 - 1.0)
    l15, r15 = v(-w15, 15.0), v(w15, 15.0)
    tri(apex, l15, r15)
    rings = (15.0, 20.0, 27.0, 36.0, 60.0)   # past the end walls (47)
    prev = (v(-half(15.0), 15.0), v(half(15.0), 15.0))
    for z in rings[1:]:
        cur = (v(-half(z), z), v(half(z), z))
        tri(prev[0], prev[1], cur[1])
        tri(prev[0], cur[1], cur[0])
        prev = cur
    return Mesh([int(round(c * ONE)) for p_ in V for c in p_], F)


GROUND_M = int(cart.data(ground_mesh(), "ground"))

# THE AWARE MARKER (tear.py _AWARE): a small gold tetrahedron over every
# demon that has you inside its frontal cone and so can swing -- the ones
# without one are facing the wrong way, the gaps to move through.


def tetra_mesh(size, col):
    V = np.array([(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)], float) * size
    F_ = []
    for a, b, c in ((0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)):
        P = V[[a, b, c]]
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if np.dot(n, P.mean(0)) < 0:
            b, c = c, b
        n = n / np.linalg.norm(n)
        k = 0.7 + 0.3 * max(0.0, n[1])                    # lit from above
        F_.append((a, b, c, rgb(tuple(min(255, int(ch * k)) for ch in col))))
    return Mesh([int(round(c * ONE)) for v in V for c in v], F_)


AWARE_M = int(cart.data(tetra_mesh(0.10, (255, 210, 80)), "aware"))
AWARE_LIFT = int(1.62 * ONE)

# ---- P6: THE TITLE -- the archive's own start screen, baked -----------------
# tools/tnd_title.py renders it with the archive itself at the panel's
# 320x288 (TEAR / NOT / DEMON in its gothic hand, the demonic Ns, the
# gash, the inverted cross, PRESS START; the menu cut to START, the one
# thing the port does). Here it is a BACKDROP PLATE: on the title the
# frame clears to it, nothing else is drawn, and the music keeps the
# archive's intro lock. ~136k clocks to read, on a screen with no fight.
_title = np.load(HERE.parent / "assets" / "tnd" / "title.npz")["img"].astype(np.int64)
TITLE = cart.cram(Plate([int(r >> 3) << 10 | int(g >> 3) << 5 | int(b >> 3)
                         for r, g, b in _title.reshape(-1, 3)],
                        [spec.ZFAR] * spec.BG_WORDS), "title")
MODE = cart.data(Table([0]), "mode")             # 0 the title, 1 the fight
TT = cart.data(Table([1500]), "title_t")   # boots at ATTRACT: the intro first
STREET_FACES = sum(len(b.f) for b in street)

# ---- P4: THE KEYS -- what the fight hit-tests (tools/tnd_extract.py) -----
# Archive axes (x fwd, y left, z up) to the cart's, Q16.16.
def zq(v):
    return [int(round(c * ONE)) for c in MZ @ np.asarray(v, float)]


PMN = ("jab", "cross", "lead_hook", "rear_hook", "special", "lead_uppercut",
       "rear_uppercut", "gun", "gun_charged")
DMN = ("cross", "lead_hook")
# a move row: startup, end of active, total, damage, head damage (x1.35),
# reach^2, hitstop, knock, lunge, its first pose in the bank, its fists
MROW = ("start", "endact", "total", "dmg", "dmgh", "reach2", "stop",
        "knock", "lunge", "pose", "lift", "air", "cancels", "style", "fist")
GRAV = 0.014                    # tear.py: the aerial system's own gravity
GRAVQ = int(round(GRAV * ONE))
AIR_FLOAT = int(round(0.12 * ONE))   # tear.py AIR_HIT_FLOAT
AIR_HANG = 26                        # tear.py AIR_HIT_HANG
MR = {k: i for i, k in enumerate(MROW)}


def move_rows(rows, fists, pose_of=None, cancels=None):
    out, fist_words, at = [], [], []
    for k, r in enumerate(rows):
        su, ac, rc, dmg, reach, stop, knock, lunge, lift, style = r
        at.append(len(fist_words))
        fist_words += [w for f in fists[k] for w in zq(f)]
        # a LAUNCHER keeps its target helpless the whole arc: up and down
        # is 2 lift / g frames, and a beat (tear.py _resolve_hits)
        air = int(2 * lift / GRAV) + 6 if lift else 0
        out.append([int(su), int(su + ac), int(su + ac + rc), int(dmg),
                    int(dmg * 1.35), int(round(reach ** 2 * ONE)), int(stop),
                    int(round(knock * ONE)), int(round(lunge * ONE)),
                    pose_of(k) if pose_of else 0, int(round(lift * ONE)), air,
                    cancels[k] if cancels else 0, int(style), 0])
    return out, fist_words, at


# THE CANCEL LATTICE (combat.py): in its RECOVERY, a move may be cut by a
# buffered move it lists -- a light punch by anything, a hook only by the
# launchers and the special, a launcher only by the special, the special
# by nothing. A bit per move id.
def _bits(*names):
    return sum(1 << PMN.index(n) for n in names)


# (combat.py's sets: the plain shot is in every one, the charged shot in
# none -- it is too slow to cancel into -- and it cancels only to the special)
_LIGHT = _bits(*(n for n in PMN if n != "gun_charged"))
_HOOK = _bits("lead_uppercut", "rear_uppercut", "gun", "special")
_UPPER = _bits("gun", "special")
CANCELS = {"jab": _LIGHT, "cross": _LIGHT, "lead_hook": _HOOK, "rear_hook": _HOOK,
           "special": 0, "lead_uppercut": _UPPER, "rear_uppercut": _UPPER,
           "gun": _LIGHT, "gun_charged": _bits("special")}
_pm, _pf, _pat = move_rows(DEM["p_moves"], [DEM["p_fist_" + n] for n in PMN],
                           lambda k: base[PMN[k]], [CANCELS[n] for n in PMN])
BIT = cart.data(Table([1 << i for i in range(len(PMN))]), "bits", borrow="auto")
PFIST = cart.data(Table(_pf), "p_fists", borrow="auto")
for k, row in enumerate(_pm):
    row[MR["fist"]] = int(PFIST) + _pat[k]
PMT = cart.data(Table([w for r in _pm for w in r]), "p_moves", borrow="auto")
PKEY = cart.data(Table(zq(DEM["p_chin"]) + zq(DEM["p_gut"])), "p_keys", borrow="auto")
DKEY, DMT = [], []              # per build: its keypoints, its move rows
for i in range(3):
    rows, fw, at = move_rows(DEM["d_moves"], [DEM[f"b{i}_fist_{n}"] for n in DMN])
    DKEY.append(cart.data(Table(zq(DEM[f"b{i}_chin"]) + zq(DEM[f"b{i}_gut"]) + fw),
                          f"demon{i}_keys", borrow="auto"))
    for k, row in enumerate(rows):         # the builds differ only in reach
        row[MR["fist"]] = int(DKEY[i]) + 6 + at[k]   # of arm: their fists
    DMT.append(cart.data(Table([w for r in rows for w in r]), f"demon{i}_moves", borrow="auto"))
NMR = len(MROW)

# ---- the wave: three demons round the crossing, facing in (tear.py) -----
# A slot is a demon's whole state; the mind runs on a COPY of it (CUR), so
# its code exists once, not three times (IMEM is 4,096 words).
#   st  0 free (stand / walk / turn), 1 swinging, 2 hit (hitstun),
#       3 falling, 4 gone
DF = {f: k for k, f in enumerate(
    ("x", "z", "h8", "hp", "st", "mf", "mv", "ai", "wf", "mov", "alt", "cf",
     "hs", "stop", "vx", "vz", "con", "dt", "jt", "kp", "mt", "ox", "oz",
     "py", "vy", "aw"))}
NF = len(DF)
DMASS = [0.85 + 0.55 * b for b in (1.40, 0.85, 1.40)]   # tear.py: e.mass
DHP = 70
slots = []
for i in range(3):
    a = i * 2 * np.pi / 3 + 0.6                          # tear.py _spawn_wave
    ax, ay = np.cos(a) * 7.8, np.sin(a) * 7.8
    v = dict.fromkeys(DF, 0)
    v.update(x=int(round(-ay * ONE)), z=int(round(ax * ONE)),
             h8=(int(round((a + np.pi) * 1024 / (2 * np.pi))) & 1023) << 8,
             hp=DHP, wf=21 * i, cf=int(CLIPT) + CLIP0["idle"] * NPART,
             jt=int(DJT[i]), kp=int(DKEY[i]), mt=int(DMT[i]))
    slots += [v[f] for f in DF]
DS = cart.data(Table(slots), "demons")
SPAWN = cart.data(Table(slots), "spawn", borrow="auto")       # a new wave is this, copied
CUR = cart.var("cur", NF)                        # the demon being thought


def dslot(d, f):
    return int(DS) + d * NF + DF[f]




def cur(f):
    return int(CUR) + DF[f]


# THE QUARTER WAVE. A 1,024-word sine table for a function with two
# symmetries was the cheapest DMEM in the cart to give back: 257 words
# and a subroutine (sin_of) that folds the angle. It bought the demons.
QSIN = cart.data(Table([int(round(np.sin(i * 2 * np.pi / 1024) * ONE))
                        for i in range(257)]), "qsin")

PX, PZ, YAW = cart.var("px"), cart.var("pz"), cart.var("yaw")
ANIM, AF, POSE = cart.var("anim"), cart.var("af"), cart.var("pose")
CY = cart.var("cam_yaw")       # the camera's yaw, easing after his
IDLE = cart.var("idle_f")       # idle's own frame, WRAPPED -- never a
                                # modulo off REG_FRAME, whose cost would
                                # grow every frame for as long as you play
PV = cart.var("prevpad")
# THE STRIKE FACING (tear.py _aim_at_dpad): the body faces HEAD, which is
# the steering YAW except while a strike runs -- at its launch HEAD snaps
# to the D-pad's direction off the steering (forward ahead, left to the
# left, back spins and strikes behind, the diagonals between), the camera
# never sees it, and it reverts when the strike is done. Indexed by the
# pad's four direction bits (up 1, down 2, left 4, right 8).
HEAD = cart.var("head")


def _octant(bits):
    f = (1 if bits & 1 else 0) - (1 if bits & 2 else 0)
    t = (1 if bits & 4 else 0) - (1 if bits & 8 else 0)
    if not (f or t):
        return 0
    # a left turn RAISES yaw (forward is (-sin, cos); the archive's heading
    # maps to it one to one, and its left turn raises the heading). Until
    # 2026-11-20 both this and the tank turn had it backwards -- caught on
    # glass by the player, not by any gate.
    return int(round(np.arctan2(t, f) * 1024 / (2 * np.pi))) & 1023


OCTANT = cart.data(Table([_octant(b) for b in range(16)]), "octants", borrow="auto")
NOBJ = cart.var("nobj")

cart.boot(spec.CAM_Y, int(2.15 * ONE))           # the archive's follow height
cart.boot(spec.CAM_PITCH, 20)                    # ~0.12 rad DOWN: positive pitches down (the first cut had the sign backwards and put the horizon below centre)
cart.boot(spec.FOG_RGB, 0x6A2420)             # the dusk the street dissolves into
cart.boot(spec.FOG_NEAR, 15 * 512)              # archive _FOG_NEAR = 15 units
cart.boot(spec.FOG_SHIFT, 10)                   # full at 15 + 32 = 47 (archive 46)

p = cart.program()
L_SINE, L_ROT, L_FK = p.label("sine"), p.label("rot"), p.label("fk")
L_RSQRT = p.label("rsqrt")
L_TELE = p.label("tele")
L_VIS = p.label("vis")
L_ARENA = p.label("arena")
L_COPY, L_WPT, L_D2, L_DMIND = (p.label(k) for k in ("copy", "wpt", "d2", "dmind"))
L_TEXT = p.label("text")
W = {k: cart.var("w_" + k) for k in ("k", "bx", "bz", "c", "s", "x", "y", "z", "oy",
                                     "qx", "qy", "qz", "dc", "dg", "d2", "head",
                                     "dmg", "stop")}
# THE STREET IS THE ARENA (tear.py _in_arena, the movement clamp): the
# crossing square inside 10.6, and the two streets 7.1 either side of
# their centreline out to 40. A step that ends anywhere else keeps only
# what stays on -- for him and for the demons alike.
AR = {k: cart.var("ar_" + k) for k in ("x", "z", "ox", "oz")}
AR_SQ, AR_LANE, AR_REACH = (int(v * ONE) for v in (11 - 0.4, 11 - 3.2 - 0.7, 54 - 14))


L_KIA = p.label("kia")
KP = {k: cart.var("kp_" + k) for k in ("p", "o")}    # where x (z next), where ox


def keep_in_arena(xc, zc, ox, oz):
    """a step that leaves the street keeps whichever axis of it stays on
    -- the archive's own SLIDE (tear.py, the open-world clamp: the whole
    step, else x alone, else z alone, else none), so a wall is a wall you
    can run along rather than glue. (One subroutine through two pointers:
    every pair here sits x then z, ox then oz.)"""
    assert int(zc) == int(xc) + 1 and int(oz) == int(ox) + 1
    p.push(int(xc)).store(KP["p"]).push(int(ox)).store(KP["o"])
    p.emit(f"call {L_KIA}")


def _kia_sub():
    def get(ptr, k):
        p.load(KP[ptr])
        if k:
            p.push(k).emit("add")
        p.emit("loadi")

    def put_from(src, k):                              # *(p + k) = *(o + k)
        get("o", k)
        p.load(KP["p"])
        if k:
            p.push(k).emit("add")
        p.emit("storei")
    ok = p.label("kia")
    p.mark(L_KIA)
    get("p", 0); p.store(AR["x"]); get("p", 1); p.store(AR["z"])
    p.emit(f"call {L_ARENA}", f"jz {ok}_x", "ret")
    p.mark(f"{ok}_x")                                # x alone
    get("p", 0); p.store(AR["x"]); get("o", 1); p.store(AR["z"])
    p.emit(f"call {L_ARENA}", f"jz {ok}_z")
    put_from("o", 1); p.emit("ret")
    p.mark(f"{ok}_z")                                # z alone
    get("o", 0); p.store(AR["x"]); get("p", 1); p.store(AR["z"])
    p.emit(f"call {L_ARENA}", f"jz {ok}_n")
    put_from("o", 0); p.emit("ret")
    p.mark(f"{ok}_n")                                # neither
    put_from("o", 0); put_from("o", 1); p.emit("ret")
WALK = int(0.032 * ONE)                          # the archive's walk pace
CAMD = 3                                         # camera distance, units
L = {k: p.label(k) for k in ("free", "noa", "jab", "walk", "idle",
                             "anim", "pj", "pi", "pd", "iw")}


def sin_of(q, plus=0, cell=None):
    """push sin(angle + plus) in Q16.16, through the quarter wave"""
    q.load(YAW if cell is None else cell)
    if plus:
        q.push(plus).emit("add")
    q.emit(f"call {L_SINE}")


# ---- THE BLOW, HEARD (sfx.meat_impact, on this machine's voices) -------------
# The archive builds an impact in four layers; three carry here, on three
# voices TND leaves free:
#   SLAP   noise stepping at a bright 12 kHz for the first 4 ms -- the
#          contact the ear places the blow by -- then, at sample 192
#          exactly (the EVENT LIST: sub-frame and bit-exact), the MEAT:
#          noise at a wet mid step, fast-decaying
#   THUMP  the triangle, its pitch FALLING as it fades (112 -> 74 Hz on a
#          head, 95 -> 58 on the body: heavy, not merely loud)
#   RING   the archive's metal partial as a thin pulse, a clang that dies
#          into the flesh within four frames
# A head shot is brighter and shorter (150 ms), the body darker and longer
# (190 ms): the same event at two weights.
def hz(f):
    return int(round(f * (1 << 24) / spec.SND_HZ))


SFX_N = 12                                       # frames: 190 ms, rounded up
SFX_SLAP = spec.SND_HZ * 4 // 1000               # sample 192
# The curves are a linear pitch fall and linear fades, so they are COMPUTED
# a frame at a time from six words a weight (a 144-word table, before
# DMEM ran out): ring inc, thump inc and its fall a frame, the thump's
# fade a frame (x256), the meat's inc, the thump's length.
SFXP = []
for head in (0, 1):
    n = 9 if head else 12
    f0, f1 = (112, 74) if head else (95, 58)
    meat, ring = (5200, 1900) if head else (3000, 1350)
    SFXP += [hz(ring), hz(f0), (hz(f1) - hz(f0)) // (n - 1), 15 * 256 // (n - 1),
             hz(meat), n]
SFX = cart.data(Table(SFXP), "sfx_blow", borrow="auto")
SFX_V = cart.data(Table([10, 6, 3, 1,                  # the ring's fade
                         15, 13, 9, 5, 15, 12, 7, 3]), "sfx_vol", borrow="auto")   # the noise, body / head
SFX_MEAT = cart.data(Table([hz(3000), hz(5200)]), "sfx_meat", borrow="auto")
SFX_T = cart.data(Table([SFX_N]), "sfx_t")     # boots past its end: quiet
SFX_H, SFX_R = cart.var("sfx_h"), cart.var("sfx_r")


def sound_blow(head_cell):
    """start the blow from the top; head_cell holds 1 for a head shot"""
    p.set(SFX_T, 0)
    p.load(head_cell).store(SFX_H)



# ---- P5: STYLE (combat.Style) -- variety pays, repetition does not -----------
# A landed blow pays its move's style x the VARIETY of it (1, 0.6, 0.4, 0.25
# as it recurs in the last five) x the combo (+5% a hit, to twenty). A
# blow taken keeps 45% and breaks the combo; standing about bleeds it.
# Ranks D C B A S SS SSS at 0 60 150 300 520 800 1200. Points are kept
# x16 (the archive's 0.6-a-frame bleed is 9.6 of them); no divider, so the
# combo's /400 is a multiply by its reciprocal.
RANKS = ("D", "C", "B", "A", "S", "SS", "SSS")
RANK_AT = (0, 60, 150, 300, 520, 800, 1200)
RANK_RGB = (0x96919A, 0xAA8C78, 0x8C96AA, 0x96AA82, 0xC8A05A, 0xCD6E3C, 0xB92828)
SY = {k: cart.var("s_" + k) for k in ("pts", "combo", "idle", "rp", "rank",
                                       "best", "cnt", "src", "dst", "dx", "n",
                                       "g", "rgb")}
S_REC = cart.data(Table([255] * 5), "s_recent")
S_SHOWN = cart.data(Table([255]), "s_shown")             # 255: draw afresh
S_AT = cart.data(Table([a * 16 for a in RANK_AT] + [1 << 30]), "s_rank_at", borrow="auto")
S_MULT = cart.data(Table([20, 12, 8, 5]), "s_mult", borrow="auto")      # x/20
BAR_W = 100
S_FAC = cart.data(Table([int(BAR_W * ONE / ((RANK_AT[r + 1] - RANK_AT[r]) * 16))
                         for r in range(6)] + [0]), "s_bar", borrow="auto")
S_RGB = cart.data(Table(list(RANK_RGB)), "s_rgb", borrow="auto")
# THE TEXT ENGINE. Baked text is finished display-list triangles -- seven
# words a triangle, ~57 a glyph: the five rank letters and RETRY were 552
# words of a DMEM that had none left. A glyph here is its rectangles
# PACKED -- x, y (2 and 3 bits), width, height (2 and 3), ten bits a
# rectangle, three a word, every glyph of this font in six or fewer --
# and one routine (L_TEXT) turns a string of them into triangles when the
# HUD changes. Two words a glyph; a string is its length and its glyphs.
# (The width is stored as itself, 1..3, so an all-zero rectangle is none.)
# (FONT_CH and the font's words: placed with the cart, P8 -- the intro
# swaps in its own font at the same address)


def glyphs(text):
    return [len(text)] + [FONT_CH.index(c) for c in text]


STR_RANK = [cart.data(Table(glyphs(r)), "str_" + r, borrow="auto") for r in RANKS]
STR_RETRY = cart.data(Table(glyphs("RETRY")), "str_retry", borrow="auto")
# the wordmark, top left under the gauge: T and D in bone, the N in blood
# (the archive draws its N demonic -- horned, ember-tipped -- in blood)
WORDMARK = [(cart.data(Table(glyphs(c)), "str_wm_" + c, borrow="auto"), x, col)
            for c, x, col in (("T", 9, 0xD8CFC1), ("N", 17, 0xD63A36), ("D", 25, 0xD8CFC1))]
S_STRS = cart.data(Table([int(x) for x in STR_RANK]), "str_ranks", borrow="auto")
S_LEN = cart.data(Table([len(r) for r in RANKS]), "rank_len", borrow="auto")
GW = 4 * 3                                     # a glyph and its gap, x3
# ---- P14: THE CARD -- what survives the power ---------------------------------
# Two words in slot 2: the best rank ever reached (0 none yet, 1..7 for
# D..SSS) and the runs that ended. Read once, a second after the machine
# starts; a rank passed or a run ended is OWED to the card and goes out
# when the card is free (one transfer in flight is the law's own rule).
# (Placed at the TOP of the display list's tail -- Cart.tail_top -- so
# these eight words move nothing else in a DMEM that is exactly full.)
CARDV = cart.tail_top(Table([0, 0]), "save")
CARDF = cart.tail_top(Table([0]), "save_f")    # bit 0: the read is asked;
                                               # bit 1: CARDV is owed to the card
SAVE_SLOT = 2
cart.sd(SAVE_SLOT, Table([0, 0]), "save_img")
STR_BEST = cart.data(Table(glyphs("BEST")), "str_best", borrow="auto")
BEST_X, BEST_Y = 124, 246                      # over the prompt (to calibrate)
STR_COMBO = cart.data(Table([3, FONT_CH.index("X"), 0, 0]), "str_combo")  # X + 2 digits
FK = {k: cart.var("fk_" + k) for k in
      ("x", "z", "yaw", "jt", "cf", "j", "rp", "pp", "a", "ra",
       "vx", "vy", "vz", "q", "t", "s", "c", "flags", "y", "aw")}
# THE TEXT ENGINE SHARES THE SKELETON'S SCRATCH: its sixteen cells live only
# while the HUD (after the objects) or the intro (before them) is writing
# words, and FK's only while the demons are being posed -- two phases a frame
# never overlaps -- so they are the same sixteen words (P10's movement state
# is what that bought). TX[k] is an alias, not an allocation.
from zeta.forge import Sym                                   # noqa: E402
_tx_keys = ("str", "x", "y", "sc", "rgb", "n", "gp", "w", "k", "r", "x0", "y0",
            "x1", "y1", "dl", "j")
TX = {k: Sym(int(list(FK.values())[i]), "tx_" + k, 1) for i, k in enumerate(_tx_keys)}
# ...and COPY's three parameters take FK's last cells, which the text engine
# leaves alone: COPY runs in the retry, the wave and the minds -- all before
# the objects are posed (P12's camera state is what that bought)
CP = {k: Sym(int(list(FK.values())[16 + i]), "cp_" + k, 1)
      for i, k in enumerate(("src", "dst", "n"))}
TRI_CELLS = cart.data(Table([int(TX[c]) for c in (     # the forge's two triangles
    "x0", "y0", "x1", "y0", "x0", "y1", "rgb", "x1", "y0", "x1", "y1", "x0", "y1",
    "rgb")]), "tri_cells")

# ---- P5: THE MUSIC -- Fable's synth theme, its stems gated by rank -------------
# sfx._synth_battle_stems, on this machine's voices: 148 BPM, a two-bar
# loop, eight layers -- drums, bass, the palm-muted chug, the half-time
# breakdown, and the phrygian lead hook revealing itself by rank (a
# fragment, the hook, the harmony a third up; the octave shred is rank
# eight, which no fight reaches -- as in the archive). Stem k sounds from
# rank k up, all riding one eased intensity (70 + 34 a rank, falling to
# nothing when he is down). The free voices, not the blow's:
#   ch1   the kick: a pulse dropping in pitch, a fast fade
#   ch3   the snare and the china: noise (a blow's slap takes it back)
#   ch5   the bass, ch6 the chug, ch7 the breakdown, ch8-10 the leads --
#         wave voices on two pages: a square, and a POWER CHORD (root,
#         fifth and octave summed and hard-clipped, as _power_chug does,
#         two root cycles a page so it plays at half the root)
# A step sequencer at the sixteenth, on the archive's own sample grid
# (step j at j * BEAT//4): a sixteenth is 4,864 samples and a frame 800,
# so at most one step falls in a frame, and its notes start on their exact
# sample through the event list.
BEAT = spec.SND_HZ * 60 // 148
SIX = BEAT // 4
LOOP = BEAT * 4 * 2                                   # 155,672 samples
A2 = 110.0


def semi_hz(s):
    return A2 * 2 ** (s / 12)


def page(samples):
    w = []
    for i in range(0, 256, 4):
        w.append(sum((samples[i + k] & 0xFF) << (8 * k) for k in range(4)))
    return w


_sq_page = [100 if i < 128 else -100 for i in range(256)]
_chug = []
for i in range(256):                    # 2 root cycles, 3 fifths, 4 octaves
    ph = i / 256
    sq = lambda c: 1 if (ph * c) % 1 < 0.5 else -1   # noqa: E731
    _chug.append(max(-14, min(14, (sq(2) * 5 + sq(3) * 4 + sq(4) * 3) * 4)) * 8)
_noise, _lf, _acc = [], 0xACE1, 0          # a deterministic grain, softened
for i in range(256):
    _lf = (_lf >> 1) ^ (0xB400 if _lf & 1 else 0)
    _acc = (_acc * 3 + ((_lf & 0xFF) - 128)) // 4      # one-pole low-pass
    _noise.append(max(-110, min(110, _acc * 2)))
# (the song build's page 1 is the RECORD's: the mover lands a page of it
# there every frame -- P7 -- and nothing else walked the chug)
WAVES = cart.data(Table(page(_sq_page) + ([0] * spec.WAV_WORDS if SONG else page(_chug))
                        + page(_noise)), "wave_pages")
cart.boot(spec.WAV_SRC, int(WAVES))
PG_SQ, PG_CHUG, PG_NOISE = 0, 1, 2

# the stems: (name, voice, page or None, base volume, fade a frame x16)
STEMS = (("drums", None, None, 0, 0),
         ("bass", 5, PG_SQ, 11, 18),
         ("chug", 6, PG_CHUG, 10, 26),
         ("breakdown", 7, PG_CHUG, 12, 9),
         ("lead_tease", 8, PG_SQ, 9, 0),
         ("lead", 9, PG_SQ, 11, 0),
         ("harmony", 10, PG_SQ, 9, 0))
NSTEM = len(STEMS)
HOLD, REST = 0, 1                                      # else 2 + note index
notes = []                                             # inc values, by index


def note(hz_):
    v = hz(hz_)
    if v not in notes:
        notes.append(v)
    return 2 + notes.index(v)


def lead_steps(events):
    out, at = [HOLD] * 32, 0
    for semi, beats in events:
        n = int(beats * 4)
        if at < 32:
            out[at] = REST if semi is None else note(semi_hz(semi))
        at += n
    return out


HOOK = [(0, .5), (3, .5), (5, .5), (3, .5), (0, 1), (1, .5), (0, .5),
        (7, .5), (5, .5), (3, .5), (1, .5), (0, 1.5), (None, .5)]
TIER_B = [(0, .5), (3, .5), (5, .5), (3, .5), (0, 1), (1, .5), (0, .5), (0, 4)]
HARMONY = [(3, .5), (7, .5), (8, .5), (7, .5), (3, 1), (5, .5), (3, .5),
           (10, .5), (8, .5), (7, .5), (5, .5), (None, 2)]
pat = {}
# drums: bit 0 kick, bit 1 snare, bit 2 china (sfx._stem_drums)
kpat = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1,
        1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1]
pat["drums"] = [kpat[j] | (2 if j % 8 == 4 else 0) | (4 if j % 16 == 0 else 0)
                for j in range(32)]
line = (55, 55, 82, 55, 73, 73, 98, 73)               # the root-fifth riff
pat["bass"] = [note(line[(j // 2) % 8]) if j % 2 == 0 else HOLD for j in range(32)]
cpat = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1] * 2
roots = [55, 55, 55, 55, 82, 82, 82, 82, 73, 73, 73, 73, 98, 98, 98, 55] * 2
pat["chug"] = [note(roots[j] / 2) if cpat[j] else HOLD for j in range(32)]
bk = {0: 55, 3: 55, 6: 55, 8: 82, 12: 73, 14: 73}      # half-time, by step
pat["breakdown"] = [note(bk[j % 16] / 2) if j % 16 in bk else HOLD for j in range(32)]
pat["lead_tease"] = lead_steps(TIER_B)
pat["lead"] = lead_steps(HOOK)
pat["harmony"] = lead_steps(HARMONY)
assert len(notes) <= 254
if not SONG:                  # (the song build plays the record instead: P7)
    MPAT = cart.data(Table([sum(pat[st[0]][j * 4 + k] << (8 * k) for k in range(4))
                            for st in STEMS for j in range(8)]), "music_steps")
    MNOTE = cart.data(Table(notes), "music_notes")
MU = {k: cart.var("mu_" + k) for k in ("t", "step", "inten", "o", "code", "s",
                                        "kick", "drum", "dfade")}
if not SONG:
    MENV = cart.var("mu_env", NSTEM)                   # each stem's level x16
KICK_HI, KICK_DROP = hz(135), (hz(135) - hz(30)) // 4

# ---- P4: THE FIGHT ----------------------------------------------------------
# tear.py, in integers. A move LANDS when the attacker's posed fist, in its
# active frames, comes within the move's reach of the target's chin or gut
# (nearest decides: a head shot pays x1.35 and freezes 3 frames longer).
# Then both fighters freeze (HITSTOP -- "the single biggest feel
# contributor"), the target is stunned 12 + that many frames and knocked
# along the blow, the camera shakes. One hit per swing. 140 for him, 70 a
# demon; a demon that falls lies down and is gone, and when all three are,
# a new wave stands round the crossing.
#
# THE STRING (combat.resolve): every tap of A alternates the hands -- jab,
# cross, jab -- and every third tap of a string (taps within 22 frames)
# cashes out as a hook off the next hand. A tap during a swing is BUFFERED
# for 10 frames and thrown the moment the swing ends. A tap is read on
# RELEASE, as the archive reads it -- see THE GRAMMAR below.
# the small sounds' time cells (99: quiet), declared here because the fight
# rings them long before the sounds themselves are placed (P15's landing)
SG_T = {k: cart.data(Table([99]), "sg_" + k) for k in ("wt", "st", "gt", "nt")}
LAND_SHAKE = 5                  # P15: frames of shake a touchdown is worth
CLEAR2 = int(0.65 ** 2 * ONE)   # tear.py JUMP_CLEARANCE: a flip clears a head
BARGE_KEEP = int(0.15 * ONE)    # tear.py _collide: 85% of the run is lost
F = {k: cart.var("f_" + k) for k in
     ("hs", "stop", "vx", "vz", "con", "ltap", "c3", "alt", "buf", "bmv",
      "mv", "dead", "shake", "act", "fx", "fy", "fz", "pc", "ps", "fight",
      "wave", "tilt", "py", "pvy", "acmb", "uwin", "foe",
      "sty", "chain", "cgr", "latch", "qtw", "qtc", "qts", "spd", "evf", "evt",
      "evk", "evx", "evz", "flipu", "ph", "kdir",
      "tgt", "plc", "met", "metd", "lrp", "brg", "dmi")}
# ---- P10: THE MOVEMENT LAYER (tear.py _action_move, _parkour, _boxing) ------
# L held is DEVIL TRIGGER. From the tank: UP enters PARKOUR -- a run whose
# speed ramps logistically to 0.13 a frame, turning at a fixed rate (so
# faster is WIDER: momentum), velocity gripping toward the facing and
# scrubbed when they fight; DOWN in the run is a QUICK TURN, and UP within
# 22 frames carries the speed into the new heading (else it settles into
# boxing). DOWN from the tank enters BOXING -- four-way steps on the cross
# latched at entry, heavy, mass in every step. Releasing L returns to the
# tank. A CHAIN counts clean transitions (re-entering within 26 frames
# while still moving), and the run pays STYLE every frame he threads fast
# (>= 0.11) within 3.2 of a demon: 0.85 x closeness x speed x (1 + 0.12 a
# link, to 8) -- the archive's way to SSS that is not a punch. In the air
# a second A is a FLIP: forward from the run, or any of four ways from the
# boxing stance (the cartwheel to the sides), spun by the renderer as the
# archive spins it. (f_sty 0 tank, 1 parkour, 2 boxing; the targeted modes
# -- prowler, fencing, meteor, the dodges -- come with the lock.)
PACE = 0.6
PK_TOP, PK_SEED = int(0.13 * ONE), int(0.13 * 0.35 * ONE)
PK_GROWTH, PK_FR, PK_GRIP = int(0.09 * ONE), int(0.84 * ONE), int(0.34 * ONE)
PK_INVTOP = int(ONE / 0.13 * ONE) >> 16                 # (1 / top, Q16)
PK_TURN = int(round(0.085 * PACE * 1024 / (2 * np.pi)))  # yaw units a frame
CHAIN_GRACE, CHAIN_SPEED2 = 26, int(0.10 * 0.10 * ONE)
QT_WINDOW, QT_COOL = 22, 30
BOX_RATE, BOX_FR = int(0.016 * PACE * ONE), int(0.865 * ONE)
FLIP_V = int(0.20 * ONE)
FLIPS = ((int(0.18 * ONE), 20), (int(0.14 * ONE), 20),
         (int(0.15 * ONE), 24), (int(0.15 * ONE), 24))   # fwd, back, left, right
PK_STYLE_SPEED, PK_NEAR = int(0.11 * ONE), 3.2


def held(bit):
    p.emit("load 1").push(bit).emit("and")


def speed2():
    """push |v|^2 (Q16)"""
    p.load(F["vx"]).emit("dup", "mulq").load(F["vz"]).emit("dup", "mulq", "add")


# ---- P11: THE LOCK (tear.py _action_move's TARGET, _cycle_target, _meteor) --
# R held locks the nearest living demon (a red marker over it); a left/right
# flick in the tank moves the lock round him by bearing. Standing still
# locked for 6 frames PLANTS -- he squares up to it, and the gun then
# hitscans it at any range. Locked, the styles become their targeted
# selves: the run is the PROWLER (it turns three times as fast, for
# threading), the boxing stance is FENCING (its cross re-latched onto the
# target every frame, the steps quicker and crisper), and the two FLIP into
# each other live -- Down in the run, Up in the stance -- each flip paying
# style (9 x (1 + 0.1 a link)); Up with a direction from the stance is
# METEOR, running the circle round it (Up reels you in, the direction
# alone drifts you out). Jump with a direction in the stance is a DODGE.
# (f_tgt the slot or -1, f_plc the plant's count, f_met/f_metd the meteor
# and its turn, f_lrp last frame's left/right, f_brg a bearing, f_dmi the
# demon whose mind is running.)
PLANT_HOLD, SWITCH_STYLE = 6, 9.0
PK_TURN_FAST = int(round(0.24 * PACE * 1024 / (2 * np.pi)))
FENCE_RATE, FENCE_FR = int(0.044 * PACE * ONE), int(0.72 * ONE)
METEOR_IN, METEOR_OUT, METEOR_RMIN2 = int(0.055 * ONE), int(0.022 * ONE), int(1.6 * 1.6 * ONE)
DODGE_V, DODGE_F = int(0.15 * ONE), 12
L_BRG, L_NEAR = p.label("brg"), p.label("near")
VPS, VPC = cart.var("vis_ps"), cart.var("vis_pc")   # the camera's pitch, sin / cos
# ---- P12: THE CAMERA OPERATOR (tear.py _cam, _target_cam) -------------------
# The follow stays the base -- its yaw an eighth of the arc behind his,
# three back, at the archive's height. Over it, in the archive's priority:
#   JUGGLE   a body aloft (the lock's, or the one he follows up): the
#            over-the-shoulder shot pulled back and raised with its height,
#            gazing between his chin and its
#   AIM      planted on the lock: over the right shoulder at its chin
#   ALIGN    the haymaker connects: the same shot at who it hit, for the
#            hitstop and 16 frames -- the money shot
# blended in and out by a smoothstepped weight; then, on top, the CHARGE
# shot (R held while B charges: tight on the shoulder, eased in over the
# 26-frame charge) and the PUNCH overhead (the tank, a strike button held
# choosing its aim: back and up, looking down at the compass). Every shot
# is an eye and a point to look at, solved to yaw and pitch by bisection.
CAM_W = {k: cart.var("cam_" + k) for k in ("sp", "kind", "who", "hal", "halt", "ch",
                                           "chh", "pu", "sh", "cv")}
CAM_W["d"] = cart.data(Table([3 * ONE]), "cam_d3")     # the follow's distance, eased
if SONG:                     # P7's record state (here: the pause's QUIT resets it)
    SM = {k: cart.var("sm_" + k) for k in ("cur", "pos", "pend", "q", "acc", "bib", "phr",
                                            "bus", "t", "r", "last", "hs", "ref", "dwell",
                                            "ret", "j")}
# THE ACTION SHOT (tear.py _action_cam, _follow_cam, _prowl_cam): the tank's
# follow stays as it has played -- three back, square, pitched 20 -- while
# DEVIL TRIGGER's follow comes in to 2.6 and leans onto the right shoulder
# (RE5's over-the-shoulder), BOXING pulls out to 4.0 and FENCING to 5.4,
# both facing the cross (or the target). Distance and lean ease (0.07).
# The PROWLER blends to its own low, close panther's-eye shot toward the
# target -- lower and tighter with speed, boring in within 10 units -- in
# at 0.024 a frame and out at 0.028, or CUT straight to it if he already
# faces the target.
TANK_D, DT_D, BOX_D, FENCE_D = 3.0, 2.6, 4.0, 5.4
DT_SH, BOX_SH, DIST_EASE = -0.5, -0.12, 0.07
PROWL_D, PROWL_UP, PROWL_PITCH = 4.3, 2.5, 0.34
PROWL_SURGE, PROWL_CROUCH, PROWL_FLAT = 1.0, 0.45, 0.12
STALK_RANGE, STALK_PULL, STALK_DROP = 10.0, 1.9, 0.75
CARVE_IN, CARVE_OUT, SNAP_CONE = 0.024, 0.028, 0.6
L_GAZE, L_YAW = p.label("gaze"), p.label("yaw")
L_SHOT, L_BLEND = p.label("shot"), p.label("blend")
AIM_DIST, AIM_UP, AIM_SH = 2.1, 2.35, -0.48
JUG_FLOOR, JUG_BACK, JUG_RISE, JUG_LOOK = 0.6, 0.55, 0.38, 0.55
CHIN = 1.55                                  # his chin, theirs (near enough)
CH_DIST, CH_SH, CH_UP, CH_FULL, CH_EASE = 1.6, -0.72, 2.32, 26, 0.13
PU_DIST, PU_UP, PU_PITCH, PU_EASE = 3.6, 2.55, 0.20, 0.30
ALIGN_LINGER = 16


# ---- P9: THE AIR (tear.py _locomotion_tail, _air_follow, _resolve_hits) -----
# X jumps -- an instant edge, a light rise and a heavy fall to the same ~1.73
# unit peak. A REAR uppercut that lands opens a 40-frame window: jump inside
# it with a body aloft and he RISES WITH it, eased to just below it and 0.8
# units off, turned to face it, its fall held to a drift -- an air combo
# that every connecting air hit tops back up. The special, in the air, is
# the SPIKE: it slams the body down. (f_py his height, f_pvy his rise,
# f_acmb the follow's frames, f_uwin the window, f_foe who he follows.)
JUMP_V0 = int(round(0.186 * ONE))
JUMP_RISE, JUMP_FALL = int(round(0.010 * ONE)), int(round(0.024 * ONE))
UWIN_F, ACMB_F, ACMB_REFRESH = 40, 110, 48
FOLLOW_GAP, FOLLOW_RANGE = int(round(0.12 * ONE)), 0.80
FOLLOW_EASE = int(round(0.34 * ONE))
SLOWFALL = int(round(0.03 * ONE))
SLAM = int(round(0.62 * ONE))
L_FOE = p.label("foe")
PHP = cart.data(Table([140]), "p_hp")
FRIC = int(round(0.82 * ONE))                   # tear.py: body friction
J = int(0.05 * ONE)                             # the shake, lateral
BUFFER, STRING = 10, 22


def fresh(bit):
    """push 1 when `bit` went down this frame"""
    p.emit("load 1").push(bit).emit("and").push(0).emit("eq")   # up now?
    p.load(PV).push(bit).emit("and", "or").push(0).emit("eq")   # ...or down before


def row(table_cell_or_sym, mv_cell, field, const_table=True):
    """push field of move row [mv]: table base (a constant symbol, or a
    cell holding one) + NMR * mv + field, loaded"""
    if const_table:
        p.push(int(table_cell_or_sym))
    else:
        p.load(table_cell_or_sym)
    p.load(mv_cell).push(NMR).emit("mul", "add").push(MR[field]).emit("add", "loadi")


# THE BUTTONS, as the player asked for them on glass (2026-11-20): X the
# string, Y the haymaker, A the jump, B the gun -- the launchers keep their
# physical pairs, A+X (carve+jump) and Y+B (shoot+special)
BTN = (("carve", spec.PAD_X), ("special", spec.PAD_Y),
       ("jump", spec.PAD_A), ("shoot", spec.PAD_B))
GT = {b: cart.var("g_t_" + b) for b, _ in BTN}       # frames held, 0 = up
GC = {b: cart.var("g_c_" + b) for b, _ in BTN}       # read as a chord
L_MUSIC = p.label("music")
tl = p.label("title")
# P14: THE CARD'S FRAME, in the title and the fight alike. The read waits
# for frame 60 -- gen_save.py's first version read at frame 1 and got zero
# every time, the card not yet answering -- and is asked exactly once.
cd = p.label("card")
p.load(spec.SD_GO).emit(f"jz {cd}_free", f"jmp {cd}")        # one in flight
p.mark(f"{cd}_free")
p.load(CARDF).push(1).emit("and", f"jz {cd}_ask")
p.load(CARDF).push(3).emit("eq", f"jz {cd}")                   # asked, and owed
p.set(CARDF, 1).push(spec.SD_SAVE).emit(f"jmp {cd}_go")
p.mark(f"{cd}_ask")
p.push(59).load(spec.REG_FRAME).emit("lt", f"jz {cd}")
p.load(CARDF).push(1).emit("or").store(CARDF)
p.push(spec.SD_READ)
p.mark(f"{cd}_go")                                           # (the direction rides the stack)
p.set(spec.SD_SLOT, SAVE_SLOT).set(spec.SD_OFF, 0)
p.set(spec.SD_DST, int(CARDV)).set(spec.SD_LEN, 2)
p.store(spec.SD_GO)
p.mark(cd)
p.load(int(MODE)).emit(f"jz {tl}", f"jmp {tl}_fight")
p.mark(tl)
p.push(int(TITLE)).store(spec.BG_SRC)
p.set(spec.OL_BASE, 0).set(spec.DL_BASE, 0)
# P14: BEST and the rank, once the card has one to show (a word outside
# 1..7 is not a rank: a card this cart never wrote says nothing)
tb = p.label("tbest")
p.load(CARDV).emit(f"jz {tb}")
p.push(7).load(CARDV).emit("lt", f"jz {tb}_ok", f"jmp {tb}")
p.mark(f"{tb}_ok")
p.set(TX["n"], 0)
for k, v in (("str", int(STR_BEST)), ("x", BEST_X), ("y", BEST_Y), ("sc", 2),
             ("rgb", 0xD8CFC1)):
    p.set(TX[k], v)
p.emit(f"call {L_TEXT}")
p.push(int(S_RGB) - 1).load(CARDV).emit("add", "loadi").store(TX["rgb"])
p.push(int(S_STRS) - 1).load(CARDV).emit("add", "loadi").store(TX["str"])
p.set(TX["x"], BEST_X + 5 * 8).set(TX["y"], BEST_Y).set(TX["sc"], 2)
p.emit(f"call {L_TEXT}")
p.load(TX["n"]).store(spec.DL_BASE)
p.mark(tb)
# PRESS START breathes as the archive's does (bright, then dim, on a
# 60-frame beat): one compositor rectangle dims it on the off beat
p.addi(TT, 1)
p.set(spec.CO_BASE, 1)
p.rect(0, 115, 265, 204, 276, 0x16141C,         # the prompt, exactly
       lambda q: q.load(TT).emit("shr 5").push(1).emit("and").push(9).emit("mul"))
# a FRESH press of Start or A (up now? or down last frame? -- neither)
p.emit("load 1").push(spec.PAD_START | spec.PAD_A).emit("and").push(0).emit("eq")
p.load(PV).push(spec.PAD_START | spec.PAD_A).emit("and", "or").push(0).emit("eq")
gi = p.label("gointro")
p.emit(f"jz {gi}")
p.set(int(MODE), 1).set(spec.BG_SRC, 0).set(spec.CO_BASE, 0)
p.set(GT["jump"], 100).set(GC["jump"], 1)     # the A that left the title is spent
p.set(spec.DL_BASE, 0).set(int(S_SHOWN), 255)  # P14: the title's words go,
                                               # and the HUD draws afresh
p.emit(f"jmp {L_MUSIC}")
# THE INTRO (P8): on the title's first frame, and after ATTRACT idle frames,
# page it in -- with its font, strings and first row over the borrowed end
p.mark(gi)
p.push(ATTRACT - 1).load(TT).emit("lt", f"jz {L_MUSIC}")   # TT >= ATTRACT
p.set(TT, 0)
p.set(spec.DMA_SRC, int(END_INTRO)).set(spec.DMA_DST, END_LO)
p.set(spec.DMA_LEN, B_END).set(spec.DMA_GO, 1)
p.set(spec.OVL_SRC, int(INTRO_PROG)).set(spec.OVL_DST, 0)
p.set(spec.OVL_LEN, spec.OVL_MAX).set(spec.OVL_GO, 1)
p.set(spec.BG_SRC, 0).set(spec.CO_BASE, 1)
p.rect(0, 0, 0, spec.W - 1, spec.H - 1, 0x000000, 16)
p.emit(f"jmp {L_MUSIC}")
p.mark(f"{tl}_fight")
# P13: a FRESH Start in the fight pages in the pause (its words over the end)
pa_ = p.label("pause")
held(spec.PAD_START)
p.emit(f"jz {pa_}")
p.load(PV).push(spec.PAD_START).emit("and", f"jz {pa_}_g", f"jmp {pa_}")
p.mark(f"{pa_}_g")
p.load(F["dead"]).emit(f"jz {pa_}_go", f"jmp {pa_}")
p.mark(f"{pa_}_go")
p.set(spec.DMA_SRC, int(END_PAUSE)).set(spec.DMA_DST, END_LO)
p.set(spec.DMA_LEN, B_END).set(spec.DMA_GO, 1)
p.set(spec.OVL_SRC, int(PAUSE_PROG)).set(spec.OVL_DST, 0)
p.set(spec.OVL_LEN, spec.OVL_MAX).set(spec.OVL_GO, 1)
p.mark(pa_)
p.load(PX).store(AR["ox"]).load(PZ).store(AR["oz"])     # where he stood
L = {k: p.label(k) for k in ("dead", "frozen", "free", "walk", "idle",
                             "motion", "anim", "pi", "pj", "pd", "iw",
                             "notap", "brk", "hook", "tapd", "nobuf", "busy",
                             "hurt", "launch", "turnd", "pm", "ph")}
p.load(F["dead"]).emit(f"jz {L['dead']}_no", f"jmp {L['dead']}")
p.mark(f"{L['dead']}_no")
p.load(F["stop"]).emit(f"jz {L['frozen']}_no")
p.addi(F["stop"], -1).emit(f"jmp {L['frozen']}")
p.mark(f"{L['frozen']}_no")

# ---- THE GRAMMAR (combat.Grammar, combat.resolve) ----------------------------
# Four actions on the face buttons: A carve (the string), B special, X jump,
# Y shoot. A CHORD is two buttons down within 3 frames of each other, read
# once, and neither then taps. A TAP of carve or special fires on release
# or at the fourth frame held, whichever comes first, if no chord took it.
# (The archive reads a tap as a release within 9 frames -- a keyboard's
# tap. On the Pocket a thumb holds a button longer than that, and every
# press read as a HOLD, which carve and special have no use for: on glass
# the string and the haymaker did nothing at all. Waiting out the chord
# window is all a tap needs to wait for.)
#   carve tap      the string (every tap swaps hands; the third a hook)   X
#   special tap    the haymaker                                           Y
#   carve+jump     the rear uppercut, a launcher                        A+X
#   shoot+special  the lead uppercut, a launcher                        Y+B
#   shoot          the GUN on release -- the CHARGED shot if held 26 frames
#                  (holding is the charge, so the shot cannot fire early)
#   jump+shoot     the gun
# (jump alone comes with the air layer.)
GTAP = {b: cart.var("g_tap_" + b) for b in ("carve", "special")}
TAP_MAX, CHORD_SLOP = 9, 3
CHARGE = 26                     # combat.resolve: a shot held this long is charged
MOVE = {n: i for i, n in enumerate(PMN)}


def choose(mv_const=None, mv_cell_ops=None):
    """the move is decided at the input and BUFFERED (tear.py f.press)"""
    if mv_const is not None:
        p.push(mv_const)
    else:
        p.emit(*mv_cell_ops)
    p.store(F["bmv"])
    p.set(F["buf"], BUFFER)


p.addi(F["ltap"], 1)
p.load(F["buf"]).emit(f"jz {L['nobuf']}")
p.addi(F["buf"], -1)
p.mark(L["nobuf"])
for b, bit in BTN:
    up, done = p.label("g_up"), p.label("g_d")
    if b in GTAP:
        p.set(GTAP[b], 0)
    p.emit("load 1").push(bit).emit("and", f"jz {up}")
    p.addi(GT[b], 1)
    if b in GTAP:          # held past the chord window, unchorded: it fires
        hd = p.label("g_hd")
        p.load(GC[b]).emit(f"jz {hd}_c", f"jmp {done}")
        p.mark(f"{hd}_c")
        p.load(GT[b]).push(CHORD_SLOP + 1).emit("eq", f"jz {done}")
        p.set(GTAP[b], 1).set(GC[b], 1)                    # (spent)
    p.emit(f"jmp {done}")
    p.mark(up)
    p.load(GT[b]).emit(f"jz {done}")                       # was it down?
    if b in GTAP:                     # released before that, unchorded: it fires
        nt = p.label("g_nt")
        p.load(GC[b]).emit(f"jz {nt}_c", f"jmp {nt}")
        p.mark(f"{nt}_c")
        p.set(GTAP[b], 1)
        p.mark(nt)
    if b == "shoot":                  # THE GUN, on release, unchorded: the
        ns = p.label("g_ns")          # charged shot past CHARGE frames held
        p.load(GC[b]).emit(f"jz {ns}_c", f"jmp {ns}")
        p.mark(f"{ns}_c")
        p.push(CHARGE - 1).load(GT[b]).emit("lt", f"jz {ns}_p")
        choose(MOVE["gun_charged"])
        p.emit(f"jmp {ns}")
        p.mark(f"{ns}_p")
        choose(MOVE["gun"])
        p.mark(ns)
    p.set(GT[b], 0).set(GC[b], 0)
    p.mark(done)


def chord(a, b, move):
    """both fresh (down 1..3 frames), neither yet read as a chord"""
    no = p.label("g_ch")
    for x in (a, b):
        p.load(GC[x]).emit(f"jz {no}_{x}", f"jmp {no}")
        p.mark(f"{no}_{x}")
        p.load(GT[x]).emit(f"jz {no}")
        p.push(CHORD_SLOP + 1).load(GT[x]).emit("swap", "lt", f"jz {no}")
    p.set(GC[a], 1).set(GC[b], 1)
    choose(MOVE[move])
    p.mark(no)


chord("carve", "jump", "rear_uppercut")
chord("shoot", "special", "lead_uppercut")
chord("jump", "shoot", "gun")
# the special: its own tap
sp = p.label("g_sp")
p.load(GTAP["special"]).emit(f"jz {sp}")
choose(MOVE["special"])
p.mark(sp)
# the carve string
p.load(GTAP["carve"]).emit(f"jz {L['notap']}")
p.load(F["ltap"]).push(STRING).emit("lt", f"jz {L['brk']}")
p.addi(F["c3"], 1)
p.emit(f"jmp {L['brk']}_d")
p.mark(L["brk"])
p.set(F["c3"], 1)                                 # a new string
p.mark(f"{L['brk']}_d")
p.set(F["ltap"], 0)
p.load(F["c3"]).push(3).emit("eq", f"jz {L['hook']}")
p.set(F["c3"], 0)                                 # third tap: the hook
choose(mv_cell_ops=(f"load {int(F['alt'])}", "push 2", "add"))   # 2 lead, 3 rear
p.emit(f"jmp {L['tapd']}")
p.mark(L["hook"])
p.load(F["alt"]).push(1).emit("xor").store(F["alt"])
choose(mv_cell_ops=(f"load {int(F['alt'])}",))    # 0 jab, 1 cross
p.mark(L["tapd"])
p.mark(L["notap"])
# THE JUMP: X's press, at once -- unless A is down (carve+jump launches)
jp = p.label("jump")
p.load(GT["jump"]).push(1).emit("eq", f"jz {jp}")
p.load(GT["carve"]).emit(f"jz {jp}_a", f"jmp {jp}")
p.mark(f"{jp}_a")
p.load(F["py"]).load(F["acmb"]).emit("or", f"jz {jp}_g", f"jmp {jp}_fl")   # aloft: flip?
p.mark(f"{jp}_g")
dg_ = p.label("dodge")                           # P11: FENCING + jump + one way:
p.load(F["tgt"]).emit(f"jz {dg_}")               # a DODGE, not a jump
p.load(F["sty"]).push(2).emit("eq", f"jz {dg_}")
p.load(F["evf"]).emit(f"jz {dg_}_a", f"jmp {dg_}")
p.mark(f"{dg_}_a")
p.set(W["qz"], -1)
for bit, k in ((spec.PAD_UP, 0), (spec.PAD_DOWN, 1), (spec.PAD_LEFT, 2), (spec.PAD_RIGHT, 3)):
    nb = p.label("dd")
    held(bit)
    p.emit(f"jz {nb}")
    p.load(W["qz"]).push(0).emit("lt", f"jz {dg_}")    # two axes: a plain jump
    p.set(W["qz"], k)
    p.mark(nb)
p.load(W["qz"]).push(0).emit("lt", f"jz {dg_}_go", f"jmp {dg_}")
p.mark(f"{dg_}_go")
p.load(W["qz"]).push(4).emit("add").store(F["evk"])
p.set(F["evt"], DODGE_F).set(F["evf"], DODGE_F)
p.push(0).store(W["qx"])
for k, off in ((1, 512), (2, 256), (3, -256)):
    nk = p.label("do")
    p.load(W["qz"]).push(k).emit("eq", f"jz {nk}")
    p.push(off).store(W["qx"])
    p.mark(nk)
p.load(F["latch"]).load(W["qx"]).emit("add").push(1023).emit("and").store(W["qx"])
sin_of(p, cell=W["qx"])
p.push(DODGE_V).emit("mulq").push(0).emit("swap", "sub", "dup").store(F["evx"]).store(F["vx"])
sin_of(p, 256, cell=W["qx"])
p.push(DODGE_V).emit("mulq", "dup").store(F["evz"]).store(F["vz"])
p.emit(f"jmp {jp}")
p.mark(dg_)
p.load(F["uwin"]).emit(f"jz {jp}_p")
p.emit(f"call {L_FOE}")                          # the jump-cancel: a body aloft?
p.load(F["foe"]).push(0).emit("lt", f"jz {jp}_c", f"jmp {jp}_p")
p.mark(f"{jp}_c")
p.set(F["acmb"], ACMB_F).set(F["pvy"], 0).set(F["uwin"], 0).set(F["py"], 1)
p.emit(f"jmp {jp}")
p.mark(f"{jp}_p")
p.load(ANIM).push(2).emit("eq", f"jz {jp}_j", f"jmp {jp}")   # not mid-swing
p.mark(f"{jp}_j")
p.set(F["pvy"], JUMP_V0).set(F["py"], 1)
p.emit(f"jmp {jp}")
# P10: THE FLIP -- a second A in the air, once a jump: forward from the run,
# any of four ways from the boxing stance (the archive's one-axis rule)
p.mark(f"{jp}_fl")
p.load(F["acmb"]).load(F["evf"]).emit("or").load(F["flipu"]).emit("or", f"jz {jp}_f1", f"jmp {jp}")
p.mark(f"{jp}_f1")
p.load(ANIM).push(2).emit("eq", f"jz {jp}_f2", f"jmp {jp}")
p.mark(f"{jp}_f2")
fl_dir = W["qz"]
p.set(fl_dir, -1)
p.load(F["sty"]).push(1).emit("eq", f"jz {jp}_fb")
held(spec.PAD_UP)                                   # the run: straight ahead only
p.emit(f"jz {jp}")
held(spec.PAD_LEFT | spec.PAD_RIGHT)
p.emit(f"jz {jp}_f0", f"jmp {jp}")
p.mark(f"{jp}_f0")
p.set(fl_dir, 0).emit(f"jmp {jp}_go")
p.mark(f"{jp}_fb")
p.load(F["sty"]).push(2).emit("eq", f"jz {jp}")
for bit, k in ((spec.PAD_UP, 0), (spec.PAD_DOWN, 1), (spec.PAD_LEFT, 2), (spec.PAD_RIGHT, 3)):
    nb = p.label("fd")
    held(bit)
    p.emit(f"jz {nb}")
    p.load(fl_dir).push(0).emit("lt", f"jz {jp}")      # a second axis: no flip
    p.set(fl_dir, k)
    p.mark(nb)
p.load(fl_dir).push(0).emit("lt", f"jz {jp}_go", f"jmp {jp}")
p.mark(f"{jp}_go")
p.load(fl_dir).store(F["evk"])
for k, (spd_, n) in enumerate(FLIPS):                # the flip's speed and length
    nk = p.label("fk")
    p.load(fl_dir).push(k).emit("eq", f"jz {nk}")
    p.push(spd_).store(W["qy"]).set(F["evt"], n).set(F["evf"], n)
    p.mark(nk)
# its direction: the stance's yaw (the run's facing, or the latch), turned
# by the input -- forward 0, back 512, left +256, right -256
p.push(0).store(W["qx"])
for k, off in ((1, 512), (2, 256), (3, -256)):
    nk = p.label("fo")
    p.load(fl_dir).push(k).emit("eq", f"jz {nk}")
    p.push(off).store(W["qx"])
    p.mark(nk)
p.load(YAW).load(W["qx"]).emit("add").push(1023).emit("and").store(W["qx"])
sin_of(p, cell=W["qx"])
p.load(W["qy"]).emit("mulq").push(0).emit("swap", "sub", "dup").store(F["evx"]).store(F["vx"])
sin_of(p, 256, cell=W["qx"])
p.load(W["qy"]).emit("mulq", "dup").store(F["evz"]).store(F["vz"])
p.set(F["pvy"], FLIP_V).set(F["flipu"], 1)
p.mark(jp)

# ---- stunned: no will of his own, only the blow's momentum ------------------
p.load(F["hs"]).emit(f"jz {L['hurt']}_no")
p.addi(F["hs"], -1).set(ANIM, 3).set(F["buf"], 0)
p.emit(f"jmp {L['motion']}")
p.mark(f"{L['hurt']}_no")

# ---- tank turn -- frozen while a strike button is held: the D-pad is then
# choosing where the strike goes, and must not spin the frame it is
# measured from (tear.py _tank, `charging`)
# ---- P10: the style, from the shoulder ------------------------------------
mvl = p.label("mvl")
cmt = W["dc"]                                    # committed: a swing before its
p.set(cmt, 0)                                    # recovery (stun never gets here)
p.load(ANIM).push(2).emit("eq", f"jz {mvl}_c")
p.load(AF)
row(PMT, F["mv"], "endact")
p.emit("lt", f"jz {mvl}_c")
p.set(cmt, 1)
p.mark(f"{mvl}_c")
# ---- P11: THE LOCK, held on R (f_tgt = its slot + 1; 0 is none) -----------
lk = p.label("lock")
held(spec.PAD_R)
p.emit(f"jz {lk}_off")
p.load(F["tgt"]).emit(f"jz {lk}_new")
p.push(int(DS) + DF["st"] - NF).load(F["tgt"]).push(NF).emit("mul", "add")
p.emit("loadi").push(3).emit("lt", f"jz {lk}_new", f"jmp {lk}_cy")   # still standing
p.mark(f"{lk}_new")                              # none, or it fell: the nearest
p.emit(f"call {L_NEAR}")
p.load(F["foe"]).push(1).emit("add").store(F["tgt"]).emit(f"jmp {lk}_cy")
p.mark(f"{lk}_off")
p.set(F["tgt"], 0)
p.mark(f"{lk}_cy")
# a left/right FLICK (its edge) in the tank moves the lock by bearing: right
# to the next bearing up, left to the next down (tear.py's sort, its order)
held(spec.PAD_LEFT | spec.PAD_RIGHT)
p.emit("dup").load(F["lrp"]).push(-1).emit("xor", "and").store(W["qy"])   # the edges
p.store(F["lrp"])
p.load(F["tgt"]).emit(f"jz {lk}_pl")
p.load(F["sty"]).emit(f"jz {lk}_c0", f"jmp {lk}_pl")
p.mark(f"{lk}_c0")
p.load(W["qy"]).emit(f"jz {lk}_pl")
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).store(W["head"])                # its bearing
p.push(1024).store(W["dmg"])                     # the best gap so far
p.load(F["tgt"]).store(W["stop"])                # ...and who
for d in range(3):
    nx = p.label("cy")
    p.load(F["tgt"]).push(d + 1).emit("eq", f"jz {nx}_a", f"jmp {nx}")
    p.mark(f"{nx}_a")
    p.load(dslot(d, "st")).push(3).emit("lt", f"jz {nx}")
    p.set(F["brg"], d).emit(f"call {L_BRG}")
    p.load(W["qy"]).push(spec.PAD_RIGHT).emit("and", f"jz {nx}_l")
    p.load(F["brg"]).load(W["head"]).emit("sub", f"jmp {nx}_g")
    p.mark(f"{nx}_l")
    p.load(W["head"]).load(F["brg"]).emit("sub")
    p.mark(f"{nx}_g")
    p.push(1023).emit("and", "dup").load(W["dmg"]).emit("lt", f"jz {nx}_f")
    p.store(W["dmg"]).set(W["stop"], d + 1).emit(f"jmp {nx}")
    p.mark(f"{nx}_f")
    p.emit("drop")
    p.mark(nx)
p.load(W["stop"]).store(F["tgt"])
# THE PLANT: in the tank, still for 6 frames, locked -- he squares up to it
p.mark(f"{lk}_pl")
p.load(F["tgt"]).emit(f"jz {lk}_np")
p.load(F["sty"]).emit(f"jz {lk}_s0", f"jmp {lk}_np")
p.mark(f"{lk}_s0")
held(spec.PAD_UP | spec.PAD_DOWN | spec.PAD_LEFT | spec.PAD_RIGHT)
p.emit(f"jz {lk}_s1", f"jmp {lk}_np")
p.mark(f"{lk}_s1")
speed2()
p.push(CHAIN_SPEED2).emit("lt", f"jz {lk}_np")
p.load(F["plc"]).push(PLANT_HOLD).emit("lt", f"jz {lk}_pf")
p.addi(F["plc"], 1)
p.mark(f"{lk}_pf")
p.load(F["plc"]).push(PLANT_HOLD).emit("eq", f"jz {lk}_e")
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).store(YAW).emit(f"jmp {lk}_e")
p.mark(f"{lk}_np")
p.set(F["plc"], 0)
p.mark(f"{lk}_e")

held(spec.PAD_L)
p.emit(f"jz {mvl}_up")
p.load(F["sty"]).emit(f"jz {mvl}_in", f"jmp {mvl}_g")
p.mark(f"{mvl}_in")                              # into a style from the tank
for bit, sty in ((spec.PAD_UP, 1), (spec.PAD_DOWN, 2)):
    nx = p.label("mvi")
    held(bit)
    p.emit(f"jz {nx}")
    p.set(F["sty"], sty)
    if sty == 2:
        p.load(YAW).store(F["latch"])
    if sty == 1:
        p.set(F["spd"], 0)
    p.load(F["cgr"]).emit(f"jz {nx}_n")          # a clean transition: the chain
    p.addi(F["chain"], 1).set(F["cgr"], 0).emit(f"jmp {mvl}_g")
    p.mark(f"{nx}_n")
    p.load(F["chain"]).emit(f"jz {nx}_z", f"jmp {mvl}_g")
    p.mark(f"{nx}_z")
    p.set(F["chain"], 1).emit(f"jmp {mvl}_g")
    p.mark(nx)
p.emit(f"jmp {mvl}_g")
p.mark(f"{mvl}_up")                              # L released: back to the tank
p.load(cmt).emit(f"jz {mvl}_r", f"jmp {mvl}_g")
p.mark(f"{mvl}_r")
p.load(F["sty"]).emit(f"jz {mvl}_g")
speed2()
p.push(CHAIN_SPEED2).emit("swap", "lt", f"jz {mvl}_s")   # still moving: grace
p.set(F["cgr"], CHAIN_GRACE).emit(f"jmp {mvl}_t")
p.mark(f"{mvl}_s")
p.set(F["chain"], 0)
p.mark(f"{mvl}_t")
p.set(F["sty"], 0).set(F["qtw"], 0).set(F["qts"], 0).set(F["met"], 0)
p.mark(f"{mvl}_g")
# P11: LOCKED, the run and the stance flip into each other live, and pay
lf = p.label("lflip")
p.load(F["tgt"]).emit(f"jz {lf}")
p.load(cmt).load(F["plc"]).push(PLANT_HOLD).emit("eq", "or", f"jz {lf}_a", f"jmp {lf}")
p.mark(f"{lf}_a")
p.load(F["sty"]).push(1).emit("eq", f"jz {lf}_b")
held(spec.PAD_DOWN)                              # the prowler, Down: fencing
p.emit(f"jz {lf}")
p.set(F["sty"], 2).load(YAW).store(F["latch"]).set(F["met"], 0)
p.emit(f"jmp {lf}_pay")
p.mark(f"{lf}_b")
p.load(F["sty"]).push(2).emit("eq", f"jz {lf}")
held(spec.PAD_UP)                                # fencing, Up: the prowler --
p.emit(f"jz {lf}")                               # with a direction, METEOR
p.set(F["sty"], 1).load(F["latch"]).store(YAW).set(F["met"], 0)
for bit, dr in ((spec.PAD_LEFT, 1), (spec.PAD_RIGHT, -1)):
    nb = p.label("mt")
    held(bit)
    p.emit(f"jz {nb}")
    p.set(F["met"], 1).set(F["metd"], dr)
    p.mark(nb)
p.mark(f"{lf}_pay")                              # tear.py _style_switch
p.addi(F["chain"], 1)
p.load(F["chain"]).emit("dup").push(10).emit("lt", f"jz {lf}_c", f"jmp {lf}_d")
p.mark(f"{lf}_c")
p.emit("drop").push(10)
p.mark(f"{lf}_d")
p.push(int(0.10 * SWITCH_STYLE * 16)).emit("mul").push(int(SWITCH_STYLE * 16)).emit("add")
p.load(SY["pts"]).emit("add").store(SY["pts"]).set(SY["idle"], 0)
p.mark(lf)
p.load(F["cgr"]).emit(f"jz {mvl}_cg")            # the grace runs out; standing
p.addi(F["cgr"], -1)                             # still breaks the chain
p.mark(f"{mvl}_cg")
p.load(F["cgr"]).emit(f"jz {mvl}_cs", f"jmp {mvl}_q")
p.mark(f"{mvl}_cs")
held(spec.PAD_UP | spec.PAD_DOWN | spec.PAD_LEFT | spec.PAD_RIGHT)
p.emit(f"jz {mvl}_cs2", f"jmp {mvl}_q")
p.mark(f"{mvl}_cs2")
speed2()
p.push(CHAIN_SPEED2).emit("lt", f"jz {mvl}_q")    # (|v|^2 < 0.01)
p.set(F["chain"], 0)
p.mark(f"{mvl}_q")
# the quick turn's window: UP carries the speed on, else it settles to boxing
p.load(F["qtw"]).emit(f"jz {mvl}_e")
p.load(cmt).emit(f"jz {mvl}_w", f"jmp {mvl}_e")
p.mark(f"{mvl}_w")
p.addi(F["qtw"], -1)
held(spec.PAD_UP)
p.emit(f"jz {mvl}_w2")
p.load(F["qts"]).emit(f"jz {mvl}_w2")
p.set(F["sty"], 1).load(F["qts"]).store(F["spd"])
sin_of(p)
p.load(F["qts"]).emit("mulq").push(0).emit("swap", "sub").store(F["vx"])
sin_of(p, 256)
p.load(F["qts"]).emit("mulq").store(F["vz"])
p.set(F["qts"], 0).set(F["qtw"], 0).addi(F["chain"], 1).emit(f"jmp {mvl}_e")
p.mark(f"{mvl}_w2")
p.load(F["qtw"]).emit(f"jz {mvl}_w3", f"jmp {mvl}_e")
p.mark(f"{mvl}_w3")
p.set(F["sty"], 2).load(YAW).store(F["latch"]).set(F["qts"], 0)
p.mark(f"{mvl}_e")

tk = p.label("turn")
p.load(F["sty"]).emit(f"jz {tk}_t", f"jmp {tk}")   # (the styles steer themselves)
p.mark(f"{tk}_t")
p.emit("load 1").push(spec.PAD_A | spec.PAD_B | spec.PAD_X | spec.PAD_Y)
p.emit("and", f"jz {tk}_go", f"jmp {tk}")
p.mark(f"{tk}_go")
p.if_pad(spec.PAD_LEFT, lambda q: q.addi(YAW, 12))      # a raised yaw turns him
p.if_pad(spec.PAD_RIGHT, lambda q: q.addi(YAW, -12))    # LEFT (forward is (-sin, cos))
p.load(YAW).push(1023).emit("and").store(YAW)
p.mark(tk)

# ---- a swing owns the body until its frames are done --------------------------
p.load(ANIM).push(2).emit("eq", f"jz {L['free']}")
p.addi(AF, 1)
p.load(AF)
row(PMT, F["mv"], "total")
p.emit("lt", f"jz {L['free']}_end")
# in its recovery, a buffered move this one lists cuts it short
p.load(F["buf"]).emit(f"jz {L['motion']}")
p.load(AF)
row(PMT, F["mv"], "endact")
p.emit("lt", f"jz {L['free']}_cx", f"jmp {L['motion']}")
p.mark(f"{L['free']}_cx")
row(PMT, F["mv"], "cancels")
p.push(int(BIT)).load(F["bmv"]).emit("add", "loadi", "and", f"jz {L['motion']}")
p.emit(f"jmp {L['free']}")                      # cancel: launch it now
p.mark(f"{L['free']}_end")
p.set(ANIM, 0)
p.mark(L["free"])
p.load(F["buf"]).emit(f"jz {L['walk']}_q")
# LAUNCH: the buffered move, and its lunge as ONE impulse (tear.py _launch)
p.load(F["bmv"]).store(F["mv"])
p.set(ANIM, 2).set(AF, 0).set(F["con"], 0).set(F["buf"], 0)
gf = p.label("gunface")
p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {gf}_p")   # the gun fires
p.push(0)                                     # along his facing, never the pad
p.push(3).load(F["mv"]).push(MOVE["gun"]).emit("sub").push(4).emit("mul", "add")
p.load(F["shake"]).emit("over", "over", "lt", f"jz {gf}_k")   # the recoil kick:
p.emit("swap")                                # 3 frames, the charged one 7
p.mark(f"{gf}_k")
p.emit("drop").store(F["shake"])
p.emit(f"jmp {gf}")
p.mark(f"{gf}_p")
p.push(int(OCTANT)).emit("load 1").push(15).emit("and", "add", "loadi")
p.mark(gf)
p.load(YAW).emit("add").push(1023).emit("and").store(HEAD)   # the strike's facing
sin_of(p, cell=HEAD)
row(PMT, F["mv"], "lunge")
p.emit("mulq").load(F["vx"]).emit("swap", "sub").store(F["vx"])   # fwd x = -sin
sin_of(p, 256, cell=HEAD)
row(PMT, F["mv"], "lunge")
p.emit("mulq").load(F["vz"]).emit("add").store(F["vz"])
p.emit(f"jmp {L['motion']}")
p.mark(f"{L['walk']}_q")
p.load(YAW).store(HEAD)                       # no strike: he faces his steering
# P10: a flip owns the frame; else the style's own step
ev = p.label("evade")
p.load(F["evf"]).emit(f"jz {ev}_n")
p.addi(F["evf"], -1)
p.load(F["evx"]).store(F["vx"]).load(F["evz"]).store(F["vz"])
p.set(ANIM, 0).emit(f"jmp {L['motion']}")
p.mark(f"{ev}_n")
p.load(F["sty"]).push(1).emit("eq", f"jz {ev}_b")
# PARKOUR: the quick turn, the logistic ramp, the fixed turn, grip and scrub
p.load(F["qtc"]).emit(f"jz {ev}_qt")
p.addi(F["qtc"], -1).emit(f"jmp {ev}_qd")
p.mark(f"{ev}_qt")
held(spec.PAD_DOWN)
p.emit(f"jz {ev}_qd")
p.load(YAW).push(512).emit("add").push(1023).emit("and").store(YAW)
p.load(F["spd"]).load(F["qts"]).emit("over", "over", "lt", f"jz {ev}_qm")
p.emit("swap")
p.mark(f"{ev}_qm")
p.emit("drop").store(F["qts"])
p.set(F["qtw"], QT_WINDOW).set(F["qtc"], QT_COOL)
p.set(F["vx"], 0).set(F["vz"], 0).set(F["spd"], 0)
p.mark(f"{ev}_qd")
held(spec.PAD_UP)
p.emit(f"jz {ev}_co")
p.load(F["spd"]).push(PK_SEED).emit("lt", f"jz {ev}_sd")
p.set(F["spd"], PK_SEED)
p.mark(f"{ev}_sd")
p.load(F["spd"]).emit("dup", "dup", "mulq").push(PK_INVTOP).emit("mulq", "sub")  # s(1-s/top)
p.push(PK_GROWTH).emit("mulq").load(F["spd"]).emit("add").store(F["spd"])
p.push(PK_TOP).load(F["spd"]).emit("lt", f"jz {ev}_tp")
p.set(F["spd"], PK_TOP)
p.mark(f"{ev}_tp")
p.emit(f"jmp {ev}_tr")
p.mark(f"{ev}_co")
p.load(F["met"]).emit(f"jz {ev}_cf", f"jmp {ev}_tr")         # (METEOR keeps its own)
p.mark(f"{ev}_cf")
p.load(F["spd"]).push(PK_FR).emit("mulq").store(F["spd"])     # coasting
p.mark(f"{ev}_tr")
# P11: METEOR -- the circle round the target, facing its tangent
mt_ = p.label("meteor")
p.load(F["met"]).emit(f"jz {mt_}_x")
p.load(F["tgt"]).emit(f"jz {mt_}_off")
held(spec.PAD_LEFT | spec.PAD_RIGHT)
p.emit(f"jz {mt_}_nd")
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).store(W["head"])                # inward
p.load(F["spd"]).push(PK_SEED).emit("lt", f"jz {mt_}_s")   # at parkour speed,
p.set(F["spd"], PK_SEED)                         # Up or not
p.mark(f"{mt_}_s")
p.load(F["spd"]).emit("dup", "dup", "mulq").push(PK_INVTOP).emit("mulq", "sub")
p.push(PK_GROWTH).emit("mulq").load(F["spd"]).emit("add").store(F["spd"])
p.push(PK_TOP).load(F["spd"]).emit("lt", f"jz {mt_}_t")
p.set(F["spd"], PK_TOP)
p.mark(f"{mt_}_t")
p.load(F["metd"]).push(256).emit("mul").load(W["head"]).emit("add")
p.push(1023).emit("and").store(YAW)              # the tangent
p.push(-METEOR_OUT).store(W["dmg"])              # outward, gently...
held(spec.PAD_UP)
p.emit(f"jz {mt_}_v")
p.push(0).store(W["dmg"])                        # ...or reeled in, not through him
p.push(METEOR_RMIN2).load(W["qx"]).emit("dup", "mulq").load(W["qz"]).emit("dup", "mulq", "add")
p.emit("lt", f"jz {mt_}_v")
p.push(METEOR_IN).store(W["dmg"])
p.mark(f"{mt_}_v")
for vel, plus, neg in ((F["vx"], 0, True), (F["vz"], 256, False)):
    sin_of(p, plus)
    p.load(F["spd"]).emit("mulq")
    sin_of(p, plus, cell=W["head"])
    p.load(W["dmg"]).emit("mulq", "add")
    if neg:
        p.push(0).emit("swap", "sub")
    p.store(vel)
p.emit(f"jmp {ev}_ph")
p.mark(f"{mt_}_nd")                              # the direction let go: if Up,
held(spec.PAD_UP)                                # run straight at it
p.emit(f"jz {mt_}_off")
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).store(YAW)
p.mark(f"{mt_}_off")
p.set(F["met"], 0)
p.mark(f"{mt_}_x")
tr_ = p.label("prowl")                           # P11: the PROWLER turns fast
p.push(PK_TURN).store(W["dg"])
p.load(F["tgt"]).emit(f"jz {tr_}")
p.push(PK_TURN_FAST).store(W["dg"])
p.mark(tr_)
held(spec.PAD_LEFT)
p.emit(f"jz {tr_}_r")
p.load(YAW).load(W["dg"]).emit("add").store(YAW)
p.mark(f"{tr_}_r")
held(spec.PAD_RIGHT)
p.emit(f"jz {tr_}_e")
p.load(YAW).load(W["dg"]).emit("sub").store(YAW)
p.mark(f"{tr_}_e")
p.load(YAW).push(1023).emit("and").store(YAW)
for vel, plus, neg in ((F["vx"], 0, True), (F["vz"], 256, False)):
    sin_of(p, plus)
    p.load(F["spd"]).emit("mulq")
    if neg:
        p.push(0).emit("swap", "sub")             # want = forward * speed
    p.load(vel).emit("sub").push(PK_GRIP).emit("mulq").load(vel).emit("add").store(vel)
# the scrub (align ~ (v . forward) / speed): speed = 0.3 speed + 0.7 (v . fwd)
sin_of(p)
p.load(F["vx"]).emit("mulq").push(0).emit("swap", "sub")
sin_of(p, 256)
p.load(F["vz"]).emit("mulq", "add", "dup").push(0).emit("lt", f"jz {ev}_al")
p.emit("drop").push(0)
p.mark(f"{ev}_al")
p.push(int(0.7 * ONE)).emit("mulq")
p.load(F["spd"]).push(int(0.3 * ONE)).emit("mulq", "add").store(F["spd"])
p.mark(f"{ev}_ph")
p.load(F["spd"]).push(int(4 * ONE)).emit("mulq").load(F["ph"]).emit("add").store(F["ph"])   # (a 4-unit stride)
p.set(ANIM, 5).emit(f"jmp {L['motion']}")
# BOXING: the four steps on the latched cross, and he faces it
p.mark(f"{ev}_b")
p.load(F["sty"]).push(2).emit("eq", f"jz {ev}_tank")
fn_ = p.label("fence")                         # P11: FENCING -- the cross
p.load(F["tgt"]).emit(f"jz {fn_}")               # re-latched onto the target
held(spec.PAD_A | spec.PAD_B | spec.PAD_X | spec.PAD_Y)   # (not while a strike
p.emit(f"jz {fn_}_l", f"jmp {fn_}")              # button chooses its aim)
p.mark(f"{fn_}_l")
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).store(F["latch"])
p.mark(fn_)
p.load(F["latch"]).emit("dup").store(YAW).store(HEAD)
p.push(BOX_FR).store(W["qx"]).push(BOX_RATE).store(W["qz"])
p.load(F["tgt"]).emit(f"jz {fn_}_r")
p.push(FENCE_FR).store(W["qx"]).push(FENCE_RATE).store(W["qz"])
p.mark(f"{fn_}_r")
for vel, plus, neg in ((F["vx"], 0, True), (F["vz"], 256, False)):
    p.load(vel).load(W["qx"]).emit("mulq").store(vel)
    # + (forward * (up - down) + left * (left - right)) * rate; left = fwd(+256)
    for bit, off, sgn in ((spec.PAD_UP, 0, 1), (spec.PAD_DOWN, 0, -1),
                          (spec.PAD_LEFT, 256, 1), (spec.PAD_RIGHT, 256, -1)):
        nb = p.label("bx")
        held(bit)
        p.emit(f"jz {nb}")
        sin_of(p, plus + off, cell=F["latch"])
        p.load(W["qz"]).emit("mulq")
        if neg != (sgn < 0):
            p.push(0).emit("swap", "sub")
        p.load(vel).emit("add").store(vel)
        p.mark(nb)
for bit, k in ((spec.PAD_UP, 0), (spec.PAD_DOWN, 1), (spec.PAD_LEFT, 2), (spec.PAD_RIGHT, 3)):
    nb = p.label("kd")
    held(bit)
    p.emit(f"jz {nb}")
    p.set(F["kdir"], k)
    p.mark(nb)
# the step-drag's clock: |vx| + |vz| at ~0.07 a frame is a stride in ~30
p.load(F["vx"]).emit("dup").push(0).emit("lt", f"jz {ev}_ax")
p.push(0).emit("swap", "sub")
p.mark(f"{ev}_ax")
p.load(F["vz"]).emit("dup").push(0).emit("lt", f"jz {ev}_az")
p.push(0).emit("swap", "sub")
p.mark(f"{ev}_az")
p.emit("add").push(int(7.5 * ONE)).emit("mulq")
p.load(F["ph"]).emit("add").store(F["ph"])
held(spec.PAD_UP | spec.PAD_DOWN | spec.PAD_LEFT | spec.PAD_RIGHT)
p.emit(f"jz {ev}_bi")
p.set(ANIM, 6).emit(f"jmp {L['motion']}")
p.mark(f"{ev}_bi")
p.set(ANIM, 0).emit(f"jmp {L['motion']}")
p.mark(f"{ev}_tank")
p.load(F["py"]).load(F["acmb"]).emit("or", f"jz {L['walk']}_gr")   # aloft: no
p.emit(f"jmp {L['idle']}")                    # stride (the air owns him)
p.mark(f"{L['walk']}_gr")
wb = p.label("wback")
p.emit("load 1", f"push {spec.PAD_UP}", "and", f"jz {wb}")
p.set(ANIM, 1)
p.addi(AF, 1)
sin_of(p)                                     # forward is model +z: (-sin, cos)
p.push(WALK).emit("mulq").load(PX).emit("swap", "sub").store(PX)
sin_of(p, 256)
p.push(WALK).emit("mulq").load(PZ).emit("add").store(PZ)
p.emit(f"jmp {L['motion']}")
# BACK: the tank's other half, at the same pace (tear.py _tank: fwd = +-1),
# the walk played backwards
p.mark(wb)
p.emit("load 1", f"push {spec.PAD_DOWN}", "and", f"jz {L['idle']}")
p.set(ANIM, 1)
p.addi(AF, -1)
sin_of(p)
p.push(WALK).emit("mulq").load(PX).emit("add").store(PX)
sin_of(p, 256)
p.push(WALK).emit("mulq").load(PZ).emit("swap", "sub").store(PZ)
p.emit(f"jmp {L['motion']}")
p.mark(L["idle"])
p.set(ANIM, 0)

# ---- momentum: knockback and lunge, scrubbed by friction ----------------------
p.mark(L["motion"])
# (P10: a style owns its velocity -- no friction while it steps or a flip
# carries him, 0.90 while a swing or a blow commits him; the tank's 0.82)
fr_ = p.label("fric")
p.push(FRIC).store(W["dg"])
p.load(F["sty"]).load(F["evf"]).emit("or", f"jz {fr_}")
p.push(int(0.90 * ONE)).store(W["dg"])
p.load(ANIM).push(5).emit("lt", f"jz {fr_}_f")        # 5 run, 6 step: free
p.load(F["evf"]).emit(f"jz {fr_}")
p.mark(f"{fr_}_f")
p.push(ONE).store(W["dg"])
p.mark(fr_)
for pos, vel in ((PX, F["vx"]), (PZ, F["vz"])):
    p.load(pos).load(vel).emit("add").store(pos)
    p.load(vel).load(W["dg"]).emit("mulq").store(vel)
# ---- P9: aloft -- the follow owns him, or his own arc ------------------------
av = p.label("air")
p.load(F["uwin"]).emit(f"jz {av}_w")
p.addi(F["uwin"], -1)
p.mark(f"{av}_w")
p.load(F["acmb"]).emit(f"jz {av}_arc")
p.addi(F["acmb"], -1)
p.emit(f"call {L_FOE}")
p.load(F["foe"]).push(0).emit("lt", f"jz {av}_f")
p.mark(f"{av}_lapse")                            # no body aloft, or time: drop
p.set(F["acmb"], 0).emit(f"jmp {av}_arc")
p.mark(f"{av}_f")
p.load(F["acmb"]).emit(f"jz {av}_lapse")
# the body he follows: its slot through f_foe (x, z, py, vy, stop)
def foe(f):
    p.push(int(DS) + DF[f]).load(F["foe"]).push(NF).emit("mul", "add")
foe("py"); p.emit("loadi").push(FOLLOW_GAP).emit("sub", "dup").push(0).emit("lt", f"jz {av}_g0")
p.emit("drop").push(0)
p.mark(f"{av}_g0")
p.load(F["py"]).emit("sub").push(FOLLOW_EASE).emit("mulq").load(F["py"]).emit("add")
p.store(F["py"])
p.set(F["pvy"], 0).set(F["vx"], 0).set(F["vz"], 0)
# turn to face it: the sign of forward x (it - him), a quick fixed step
foe("x"); p.emit("loadi").load(PX).emit("sub").store(W["qx"])
foe("z"); p.emit("loadi").load(PZ).emit("sub").store(W["qz"])
sin_of(p)
p.push(0).emit("swap", "sub").load(W["qz"]).emit("mulq")         # f.x * d.z
sin_of(p, 256)
p.load(W["qx"]).emit("mulq", "sub").store(W["qy"])               # - f.z * d.x
for sign, cmp in ((24, ("push 3277", f"load {int(W['qy'])}")), (-24, (f"load {int(W['qy'])}", "push -3277"))):
    tl_ = p.label("ft")
    p.emit(*cmp).emit("lt", f"jz {tl_}")
    p.addi(YAW, sign)
    p.mark(tl_)
p.load(YAW).push(1023).emit("and").store(YAW)
# hold 0.8 off it along his forward: there = it - forward * 0.8
for pos, fld, plus, sgn in ((PX, "x", 0, 1), (PZ, "z", 256, -1)):
    foe(fld); p.emit("loadi")
    sin_of(p, plus)
    p.push(int(round(FOLLOW_RANGE * ONE))).emit("mulq")
    p.emit("add" if sgn > 0 else "sub")
    p.load(pos).emit("sub").push(FOLLOW_EASE).emit("mulq").load(pos).emit("add").store(pos)
# hang it: while it is not frozen in a blow, it falls no faster than a drift
foe("stop"); p.emit("loadi", f"jz {av}_h")
p.emit(f"jmp {av}_e")
p.mark(f"{av}_h")
foe("vy"); p.emit("loadi").push(-SLOWFALL).emit("lt", f"jz {av}_e")
p.push(-SLOWFALL)
foe("vy"); p.emit("storei")
p.emit(f"jmp {av}_e")
# his own arc: a light rise, a heavy fall, down to the street
p.mark(f"{av}_arc")
p.load(F["py"]).load(F["pvy"]).emit("or", f"jz {av}_e")
p.push(0).load(F["pvy"]).emit("lt", f"jz {av}_fall")
p.load(F["pvy"]).push(JUMP_RISE).emit("sub").store(F["pvy"]).emit(f"jmp {av}_int")
p.mark(f"{av}_fall")
p.load(F["pvy"]).push(JUMP_FALL).emit("sub").store(F["pvy"])
p.mark(f"{av}_int")
p.load(F["py"]).load(F["pvy"]).emit("add").store(F["py"])
p.push(0).load(F["py"]).emit("lt", f"jz {av}_land", f"jmp {av}_e")
p.mark(f"{av}_land")
p.set(F["py"], 0).set(F["pvy"], 0).set(F["flipu"], 0)   # (a landing re-arms the flip)
# P15: THE LANDING, FELT (tear.py 2757: "a dead touchdown reads as cartoony
# no matter how the arc above it is shaped"). The frame shakes and the
# ground answers -- the step's own thud, since a sound of its own is 24
# words of a DMEM with 6. (The archive scales both by the fall's speed and
# dips the camera; one strength here.)
ld_ = p.label("land")
p.load(F["shake"]).push(LAND_SHAKE).emit("lt", f"jz {ld_}")
p.set(F["shake"], LAND_SHAKE)
p.mark(ld_)
p.set(SG_T["st"], 0)
p.mark(f"{av}_e")
# ---- P10: THREADING pays (tear.py _parkour_style) ---------------------------
th = p.label("thread")
p.load(F["sty"]).push(1).emit("eq", f"jz {th}")
p.load(ANIM).push(2).emit("eq", f"jz {th}_a", f"jmp {th}")
p.mark(f"{th}_a")
p.push(PK_STYLE_SPEED - 1).load(F["spd"]).emit("lt", f"jz {th}")   # running, not jogging
p.push32(int(PK_NEAR * PK_NEAR * ONE)).store(W["d2"])
for d in range(3):                               # the nearest live demon, squared
    nx = p.label("th_n")
    p.load(dslot(d, "st")).push(3).emit("lt", f"jz {nx}")
    p.load(dslot(d, "x")).load(PX).emit("sub", "dup", "mulq")
    p.load(dslot(d, "z")).load(PZ).emit("sub", "dup", "mulq", "add", "dup")
    p.load(W["d2"]).emit("lt", f"jz {nx}_f")
    p.store(W["d2"]).emit(f"jmp {nx}")
    p.mark(f"{nx}_f")
    p.emit("drop")
    p.mark(nx)
p.push32(int(PK_NEAR * PK_NEAR * ONE)).load(W["d2"]).emit("eq", f"jz {th}_n", f"jmp {th}")
p.mark(f"{th}_n")
# near = d2 * r, r = 1/sqrt(d2) by Newton (no divide on this machine):
# r <- r (1.5 - 0.5 d2 r^2), from 1/3.2, which converges for all d2 < 3.2^2
p.push(int(ONE / PK_NEAR)).store(W["qx"])
for _ in range(5):
    p.load(W["qx"]).emit("dup", "mulq").load(W["d2"]).emit("mulq", "shr 1")
    p.push(int(1.5 * ONE)).emit("swap", "sub").load(W["qx"]).emit("mulq").store(W["qx"])
p.load(W["d2"]).load(W["qx"]).emit("mulq")                 # near
p.push(int(ONE / PK_NEAR)).emit("mulq").push(ONE).emit("swap", "sub")   # close = 1 - near/3.2
p.load(F["spd"]).push(PK_INVTOP).emit("mulq", "dup").push(ONE).emit("swap", "lt", f"jz {th}_f")
p.emit("drop").push(ONE)                                    # fast = min(1, spd/top)
p.mark(f"{th}_f")
p.emit("mulq")
p.load(F["chain"]).emit("dup").push(8).emit("lt", f"jz {th}_c8", f"jmp {th}_c")
p.mark(f"{th}_c8")
p.emit("drop").push(8)
p.mark(f"{th}_c")
p.push(int(0.12 * ONE)).emit("mul").push(ONE).emit("add", "mulq")    # x(1 + 0.12 chain)
p.push(int(0.85 * 16 * ONE)).emit("mulq")                 # x0.85, in the meter's 16ths
p.emit("shr 16").load(SY["pts"]).emit("add").store(SY["pts"])
p.set(SY["idle"], 0)                                       # threading is fighting
p.mark(th)

# ---- pose index: base[anim] + frame within the sequence -----------------------
# 0 idle, 1 walk, 2 a swing, 3 stunned (the archive holds the idle mesh:
# it has no hurt clip), 4 down (idle, tipped over -- see the objects)
# P10: a flip's shape by its progress; the run and the step-drag by their
# gait clocks (the step-drag by its last direction)
fp = p.label("flippose")
p.load(F["evf"]).emit(f"jz {fp}")
p.load(F["evt"]).load(F["evf"]).emit("sub")
for k, seq in enumerate(("flip_fwd", "flip_back", "flip_cart", "flip_cart",
                         "dodge_fwd", "dodge_back", "dodge_left", "dodge_right")):
    nk = p.label("fp")
    p.load(F["evk"]).push(k).emit("eq", f"jz {nk}")
    p.push(base[seq]).emit("add").store(POSE).emit(f"jmp {L['pd']}")
    p.mark(nk)
p.emit("drop")
p.mark(fp)
gp_ = p.label("gaitpose")
p.load(ANIM).push(5).emit("eq", f"jz {gp_}_k")
p.load(F["ph"]).emit("shr 16").push(15).emit("and").push(base["run"]).emit("add")
p.store(POSE).emit(f"jmp {L['pd']}")
p.mark(f"{gp_}_k")
p.load(ANIM).push(6).emit("eq", f"jz {gp_}")
p.load(F["ph"]).emit("shr 16").push(15).emit("and")
for k, seq in enumerate(("kite_fwd", "kite_back", "kite_left", "kite_right")):
    nk = p.label("kp")
    p.load(F["kdir"]).push(k).emit("eq", f"jz {nk}")
    p.push(base[seq]).emit("add").store(POSE).emit(f"jmp {L['pd']}")
    p.mark(nk)
p.emit("drop")
p.mark(gp_)
ap = p.label("airpose")                      # ALOFT and not swinging: the
p.load(ANIM).push(2).emit("eq", f"jz {ap}_n", f"jmp {ap}")   # air pose by
p.mark(f"{ap}_n")                            # his rise (7 samples, 0.16..-0.16)
p.load(F["py"]).load(F["acmb"]).emit("or", f"jz {ap}")
p.push(int(round(0.16 * ONE)) + int(round(0.16 / 6 * ONE))).load(F["pvy"]).emit("sub")
p.push(int(round(3 / 0.16 * ONE))).emit("mulq", "shr 16", "dup").push(0).emit("lt", f"jz {ap}_lo")
p.emit("drop").push(0)
p.mark(f"{ap}_lo")
p.emit("dup").push(6).emit("swap", "lt", f"jz {ap}_hi")
p.emit("drop").push(6)
p.mark(f"{ap}_hi")
p.push(base["air"]).emit("add").store(POSE).emit(f"jmp {L['pd']}")
p.mark(ap)
p.load(ANIM).push(2).emit("eq", f"jz {L['pm']}")
row(PMT, F["mv"], "pose")
p.load(AF).emit("add").store(POSE).emit(f"jmp {L['pd']}")
p.mark(L["pm"])
p.load(ANIM).push(1).emit("eq", f"jz {L['pi']}")
p.load(AF).emit("shr 1").push(NPOSE["walk"] - 1).emit("and").push(base["walk"]).emit("add")  # 30 Hz
p.store(POSE).emit(f"jmp {L['pd']}")
p.mark(L["pi"])
p.addi(IDLE, 1)                              # (the idle at 30 Hz: a pose
p.load(IDLE).push(2 * NPOSE["idle"]).emit("lt", f"jz {L['iw']}")   # held two)
p.load(IDLE).emit("shr 1").push(base["idle"]).emit("add").store(POSE)
p.emit(f"jmp {L['pd']}")
p.mark(L["iw"])
p.set(IDLE, 0).set(POSE, base["idle"])
p.mark(L["pd"])
p.emit(f"jmp {L['frozen']}")

# ---- down: he tips over backwards, and after the beat, A is a new run --------
DEATH_BEAT = 46                                     # tear.py
p.mark(L["dead"])
p.addi(F["dead"], 1)
p.load(F["dead"]).push(42).emit("lt", f"jz {L['dead']}_t")
p.load(F["dead"]).push(6).emit("mul").store(F["tilt"])    # to ~89 degrees
p.mark(f"{L['dead']}_t")
p.push(DEATH_BEAT).load(F["dead"]).emit("lt")
fresh(spec.PAD_A)
p.emit("and", f"jz {L['frozen']}")
# RETRY: a fresh run -- full health, the start, a new wave (tear.py _retry)
RETRY_CELLS = ((PX, 0), (PZ, 0), (YAW, 0), (CY, 0), (ANIM, 0), (AF, 0),
             (PHP, 140), (F["dead"], 0), (F["tilt"], 0), (F["hs"], 0),
             (F["stop"], 0), (F["vx"], 0), (F["vz"], 0), (F["buf"], 0),
             (F["c3"], 0), (F["fight"], 0), (F["wave"], 0), (SFX_T, SFX_N),
             (F["py"], 0), (F["pvy"], 0), (F["acmb"], 0), (F["uwin"], 0),
             (F["sty"], 0), (F["chain"], 0), (F["cgr"], 0), (F["qtw"], 0), (F["qts"], 0),
             (F["spd"], 0), (F["evf"], 0), (F["flipu"], 0), (F["tgt"], 0),
             (F["plc"], 0), (F["met"], 0),
             (SY["pts"], 0), (SY["combo"], 0), (SY["idle"], 0), (int(S_SHOWN), 255),
             *((int(S_REC) + i, 255) for i in range(5)))
for c, v in RETRY_CELLS:
    p.set(c, v)
p.push(int(SPAWN)).store(CP["src"]).push(int(DS)).store(CP["dst"])
p.push(3 * NF).store(CP["n"]).emit(f"call {L_COPY}")
p.load(PX).store(AR["ox"]).load(PZ).store(AR["oz"])

p.mark(L["frozen"])
# ---- one mover request: the whole posed body ----------------------------------
if DEDUPE:                     # the pose's slot: two 16-bit slots a word
    _ps = p.label("pslot")
    p.load(POSE).emit("shr 1").push(int(PSLOT)).emit("add", "loadi")
    p.load(POSE).push(1).emit("and", f"jz {_ps}")
    p.emit("shr 16")
    p.mark(_ps)
    p.push(0xFFFF).emit("and")
else:
    p.load(POSE)
p.push(SPAN).emit("mul").push(int(BANK)).emit("add")
pd_ = p.label("posedma")                     # (P13: not on a frame that pages a
p.load(spec.OVL_GO).emit(f"jz {pd_}_go")     # scene in -- its handshake has the
p.emit("drop", f"jmp {pd_}")                 # request, and the pose holds anyway)
p.mark(f"{pd_}_go")
p.store(spec.DMA_SRC)
p.push(UPPER + 2).store(spec.DMA_DST)
p.push(SPAN).store(spec.DMA_LEN)
p.set(spec.DMA_GO, 1)
p.mark(pd_)

keep_in_arena(PX, PZ, AR["ox"], AR["oz"])

# his trig, for his keys and his fist: the BODY's facing
sin_of(p, 256, cell=HEAD)
p.store(F["pc"])
sin_of(p, cell=HEAD)
p.store(F["ps"])
# HIS FIST, if a swing is in its active frames and has not yet landed
p.set(F["act"], 0)
nf_ = p.label("nofist")
p.load(ANIM).push(2).emit("eq", f"jz {nf_}")
p.load(F["con"]).emit(f"jz {nf_}_c", f"jmp {nf_}")
p.mark(f"{nf_}_c")
p.load(AF)
row(PMT, F["mv"], "start")
p.emit("lt", f"jz {nf_}_s", f"jmp {nf_}")        # before the active frames
p.mark(f"{nf_}_s")
p.load(AF)
row(PMT, F["mv"], "endact")
p.emit("lt", f"jz {nf_}")                        # after them
row(PMT, F["mv"], "fist")
p.load(AF)
row(PMT, F["mv"], "start")
p.emit("sub").push(3).emit("mul", "add").store(W["k"])
for a, b in (("bx", PX), ("bz", PZ), ("c", F["pc"]), ("s", F["ps"])):
    p.load(b).store(W[a])
p.load(F["py"]).store(W["oy"])                  # aloft: his fist is up there
p.emit(f"call {L_WPT}")
for a, b in (("x", "fx"), ("y", "fy"), ("z", "fz")):
    p.load(W[a]).store(F[b])
p.set(F["act"], 1)
p.mark(nf_)

# ---- the camera: the archive's spring follow, in integers -------------------
# CY eases an eighth of the shortest arc toward his yaw each frame. An
# arithmetic >> 3 rounds toward minus infinity, so a small NEGATIVE gap
# would keep closing while a small positive one stalled at 0 -- the camera
# parked up to 2.8 degrees off on one side only. Inside 8 units it snaps.
snap_l = p.label("snap")
T = cart.var("cam_d")
# P12: the follow's yaw is his -- or, boxing, the latched cross; or, locked,
# the bearing to the target (tear.py _action_cam's base_yaw)
by_ = p.label("byaw")
p.load(YAW).store(W["oy"])
p.load(F["sty"]).push(2).emit("eq", f"jz {by_}_t")
p.load(F["latch"]).store(W["oy"])
p.mark(f"{by_}_t")
p.load(F["tgt"]).emit(f"jz {by_}")
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).store(W["oy"])
p.mark(by_)
p.load(W["oy"]).load(CY).emit("sub").push(512).emit("add")
p.push(1023).emit("and").push(512).emit("sub").store(T)   # d in -512..511
p.load(T).emit("shr 3", "dup", f"jz {snap_l}")
p.load(CY).emit("add").push(1023).emit("and").store(CY)
p.emit(f"jmp {snap_l}_d")
p.mark(snap_l)
p.emit("drop").load(W["oy"]).store(CY)                      # within 8: snap
p.mark(f"{snap_l}_d")
# ...and stands its eased distance behind him along ITS yaw, leaning by
# its eased shoulder (P12: the mode's -- the tank 3 and square, as before)
CWd = CAM_W
md_ = p.label("camd")
p.push(int(TANK_D * ONE)).store(W["dmg"]).push(0).store(W["stop"])
p.load(F["sty"]).push(2).emit("eq", f"jz {md_}_dt")
p.push(int(BOX_D * ONE)).store(W["dmg"]).push(int(BOX_SH * ONE)).store(W["stop"])
p.load(F["tgt"]).emit(f"jz {md_}_e")
p.push(int(FENCE_D * ONE)).store(W["dmg"]).emit(f"jmp {md_}_e")
p.mark(f"{md_}_dt")
held(spec.PAD_L)
p.emit(f"jz {md_}_e")
p.push(int(DT_D * ONE)).store(W["dmg"]).push(int(DT_SH * ONE)).store(W["stop"])
p.mark(f"{md_}_e")
for cell, want in ((CWd["d"], W["dmg"]), (CWd["sh"], W["stop"])):
    p.load(want).load(cell).emit("sub").push(int(DIST_EASE * ONE)).emit("mulq")
    p.load(cell).emit("add").store(cell)
for reg, me, plus, fsgn in ((spec.CAM_X, PX, 0, 1), (spec.CAM_Z, PZ, 256, -1)):
    sin_of(p, plus, cell=CY)
    p.load(CWd["d"]).emit("mulq")
    if fsgn < 0:
        p.push(0).emit("swap", "sub")
    p.load(me).emit("add")
    sin_of(p, plus + 256, cell=CY)                 # left = forward(yaw + 256)
    p.load(CWd["sh"]).emit("mulq")
    if fsgn > 0:
        p.push(0).emit("swap", "sub")
    p.emit("add").store(reg)
p.load(CY).store(spec.CAM_YAW)
p.load(F["py"]).push(int(2.15 * ONE)).emit("add").store(spec.CAM_Y)   # (P9: up with him)

# ---- P12: THE OPERATOR -- the special shots over the follow -----------------
CW = CAM_W
p.load(CAM_W["sh"]).push(10).emit("mul", "shr 16").push(20).emit("add").store(spec.CAM_PITCH)


def shot(face_cell, dist_ops, up_ops, sh):
    """eye = him - forward(face) * dist + left(face) * sh, up at py + up:
    into w_x, w_y, w_z (dist and up are op tuples leaving Q16) -- through
    L_SHOT (face w_oy, dist w_head, up w_dmg, lean w_d2): IMEM is full"""
    p.emit(*dist_ops).store(W["head"])
    p.emit(*up_ops).store(W["dmg"])
    p.push(int(sh * ONE)).store(W["d2"])
    if face_cell != W["oy"]:
        p.load(face_cell).store(W["oy"])
    p.emit(f"call {L_SHOT}")


def blend(wcell):
    """the camera registers toward (w_x, w_y, w_z, f_brg yaw, w_dg pitch) by
    smoothstep(weight) -- through L_BLEND (the weight in w_k)"""
    p.load(wcell).store(W["k"]).emit(f"call {L_BLEND}")


def slot_of(cell):
    """push the address base of demon slot [cell] (a slot index)"""
    p.push(int(DS)).load(cell).push(NF).emit("mul", "add")


# THE PROWLER'S SHOT: locked in the run, blended (or cut) to it
pw_ = p.label("prowlcam")
p.push(0).store(W["head"])
p.load(F["sty"]).push(1).emit("eq", f"jz {pw_}_w")
p.load(F["tgt"]).emit(f"jz {pw_}_w")
p.push(ONE).store(W["head"])
p.mark(f"{pw_}_w")
p.load(W["head"]).emit(f"jz {pw_}_out")
p.push(int(0.05 * ONE)).load(CAM_W["cv"]).emit("lt", f"jz {pw_}_cut", f"jmp {pw_}_in")
p.mark(f"{pw_}_cut")                              # facing it already: a cut
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
p.load(YAW).load(F["brg"]).emit("sub").push(512).emit("add").push(1023).emit("and")
p.push(512).emit("sub", "dup").push(0).emit("lt", f"jz {pw_}_ab")
p.push(0).emit("swap", "sub")
p.mark(f"{pw_}_ab")
p.push(int(SNAP_CONE * 1024 / (2 * np.pi))).emit("lt", f"jz {pw_}_in")
p.set(CAM_W["cv"], ONE)
p.mark(f"{pw_}_in")
p.load(CAM_W["cv"]).push(int(CARVE_IN * ONE)).emit("add", "dup").push(ONE).emit("swap", "lt", f"jz {pw_}_i1")
p.emit("drop").push(ONE)
p.mark(f"{pw_}_i1")
p.store(CAM_W["cv"]).emit(f"jmp {pw_}_s")
p.mark(f"{pw_}_out")
p.load(CAM_W["cv"]).push(int(CARVE_OUT * ONE)).emit("sub", "dup").push(0).emit("lt", f"jz {pw_}_o1")
p.emit("drop").push(0)
p.mark(f"{pw_}_o1")
p.store(CAM_W["cv"])
p.mark(f"{pw_}_s")
p.load(CAM_W["cv"]).emit(f"jz {pw_}_x")
p.load(F["tgt"]).emit(f"jz {pw_}_x")
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).store(W["oy"])                   # (dx, dz in w_qx, w_qz)
p.load(F["spd"]).push(PK_INVTOP).emit("mulq", "dup").push(ONE).emit("swap", "lt", f"jz {pw_}_f")
p.emit("drop").push(ONE)
p.mark(f"{pw_}_f")
p.store(W["c"])                                   # fast, 0..1
# the range, for the bore-in: 1/sqrt by Newton, as GAZE does (and with it)
p.emit(f"call {L_RSQRT}")
p.load(W["d2"]).load(W["s"]).emit("mulq")         # range
p.push(int(ONE / STALK_RANGE)).emit("mulq").push(ONE).emit("swap", "sub", "dup").push(0)
p.emit("lt", f"jz {pw_}_cl")                       # close = 1 - range/10, >= 0
p.emit("drop").push(0)
p.mark(f"{pw_}_cl")
p.store(W["stop"])
# eye: back (4.3 - fast - 1.9 close) along the bearing, up (2.5 - .45 fast
# - .75 close), pitched (0.34 - 0.12 fast) rad down, looking along it
shot(W["oy"], (f"push {int(PROWL_D * ONE)}", f"load {int(W['c'])}", f"push {int(PROWL_SURGE * ONE)}",
               "mulq", "sub", f"load {int(W['stop'])}", f"push {int(STALK_PULL * ONE)}", "mulq", "sub"),
     (f"push {int(PROWL_UP * ONE)}", f"load {int(W['c'])}", f"push {int(PROWL_CROUCH * ONE)}",
      "mulq", "sub", f"load {int(W['stop'])}", f"push {int(STALK_DROP * ONE)}", "mulq", "sub"), 0.0)
p.load(W["oy"]).store(F["brg"])
p.push(int(PROWL_PITCH * 1024 / (2 * np.pi))).load(W["c"])
p.push(int(PROWL_FLAT * 1024 / (2 * np.pi) * ONE)).emit("mulq", "shr 16", "sub").store(W["dg"])
blend(CAM_W["cv"])
p.mark(f"{pw_}_x")


op = p.label("op")
# which special shot wants the frame (the archive's priority)
p.set(W["head"], 0)                               # (kind)
p.load(CW["hal"]).emit(f"jz {op}_h")
p.addi(CW["hal"], -1)
p.mark(f"{op}_h")
p.load(F["tgt"]).emit(f"jz {op}_j2")              # JUGGLE: the lock aloft...
p.load(F["tgt"]).push(1).emit("sub").store(W["dmg"])
slot_of(W["dmg"]); p.push(DF["py"]).emit("add", "loadi")
p.push(int(JUG_FLOOR * ONE)).emit("swap", "lt", f"jz {op}_j2")
p.set(W["head"], 1).emit(f"jmp {op}_k")
p.mark(f"{op}_j2")
p.load(F["acmb"]).emit(f"jz {op}_a")              # ...or the body he follows up
p.load(F["foe"]).push(0).emit("lt", f"jz {op}_j3", f"jmp {op}_a")
p.mark(f"{op}_j3")
p.load(F["foe"]).store(W["dmg"])
slot_of(W["dmg"]); p.push(DF["py"]).emit("add", "loadi")
p.push(int(JUG_FLOOR * ONE)).emit("swap", "lt", f"jz {op}_a")
p.set(W["head"], 1).emit(f"jmp {op}_k")
p.mark(f"{op}_a")
p.load(F["tgt"]).emit(f"jz {op}_al")              # AIM: planted on the lock
p.load(F["plc"]).push(PLANT_HOLD).emit("eq", f"jz {op}_al")
p.load(F["tgt"]).push(1).emit("sub").store(W["dmg"])
p.set(W["head"], 2).emit(f"jmp {op}_k")
p.mark(f"{op}_al")
p.load(CW["hal"]).emit(f"jz {op}_k")              # ALIGN: the haymaker's money shot
p.load(CW["halt"]).store(W["dmg"])
p.set(W["head"], 2)
p.mark(f"{op}_k")
p.load(W["head"]).emit(f"jz {op}_out")
p.load(W["head"]).store(CW["kind"]).load(W["dmg"]).store(CW["who"])
p.load(CW["sp"]).push(int(0.2 * ONE)).emit("add", "dup").push(ONE).emit("swap", "lt", f"jz {op}_in")
p.emit("drop").push(ONE)
p.mark(f"{op}_in")
p.store(CW["sp"]).emit(f"jmp {op}_s")
p.mark(f"{op}_out")
p.load(CW["sp"]).push(int(0.12 * ONE)).emit("sub", "dup").push(0).emit("lt", f"jz {op}_o")
p.emit("drop").push(0)
p.mark(f"{op}_o")
p.store(CW["sp"])
p.mark(f"{op}_s")
p.load(CW["sp"]).emit(f"jz {op}_ch")
p.load(CW["kind"]).emit(f"jz {op}_ch")
# the shot: face the body, back off and rise with its height (juggle), look
# between his chin and its (juggle) or at its (aim)
p.load(CW["who"]).store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).store(W["oy"])                   # (the face, kept)
p.push(0).store(W["stop"])                        # lift above the floor
p.load(CW["kind"]).push(1).emit("eq", f"jz {op}_lf")
slot_of(CW["who"]); p.push(DF["py"]).emit("add", "loadi")
p.push(int(JUG_FLOOR * ONE)).emit("sub", "dup").push(0).emit("lt", f"jz {op}_l0")
p.emit("drop").push(0)
p.mark(f"{op}_l0")
p.store(W["stop"])
p.mark(f"{op}_lf")
shot(W["oy"], (f"load {int(W['stop'])}", f"push {int(JUG_BACK * ONE)}", "mulq",
               f"push {int(AIM_DIST * ONE)}", "add"),
     (f"load {int(W['stop'])}", f"push {int(JUG_RISE * ONE)}", "mulq",
      f"push {int(AIM_UP * ONE)}", "add"), AIM_SH)
# the subject: its chin, or (juggle) 0.55 of the way there from his
for out, f_, me in ((W["bx"], "x", PX), (W["bz"], "z", PZ)):
    slot_of(CW["who"]); p.push(DF[f_]).emit("add", "loadi").store(out)
slot_of(CW["who"]); p.push(DF["py"]).emit("add", "loadi").push(int(CHIN * ONE)).emit("add")
p.store(W["c"])
p.load(CW["kind"]).push(1).emit("eq", f"jz {op}_g")
for out, me in ((W["bx"], PX), (W["bz"], PZ), (W["c"], None)):
    p.load(out)
    if me is None:
        p.load(F["py"]).push(int(CHIN * ONE)).emit("add")
    else:
        p.load(me)
    p.emit("dup").store(W["s"]).emit("sub").push(int(JUG_LOOK * ONE)).emit("mulq")
    p.load(W["s"]).emit("add").store(out)
p.mark(f"{op}_g")
p.emit(f"call {L_GAZE}")
blend(CW["sp"])
# THE CHARGE: R held while B charges -- in tight on the shoulder
p.mark(f"{op}_ch")
held(spec.PAD_R)
p.emit(f"jz {op}_c0")
held(spec.PAD_B)
p.emit(f"jz {op}_c0")
p.addi(CW["chh"], 1).emit(f"jmp {op}_c1")
p.mark(f"{op}_c0")
p.set(CW["chh"], 0)
p.mark(f"{op}_c1")
p.load(CW["chh"]).push(int(ONE / CH_FULL)).emit("mul", "dup").push(ONE).emit("swap", "lt", f"jz {op}_c2")
p.emit("drop").push(ONE)
p.mark(f"{op}_c2")
p.load(CW["ch"]).emit("sub").push(int(CH_EASE * ONE)).emit("mulq").load(CW["ch"]).emit("add")
p.store(CW["ch"])
p.push(64).load(CW["ch"]).emit("lt", f"jz {op}_pu")      # (a weight worth drawing)
p.load(YAW).store(W["oy"])
p.load(F["tgt"]).emit(f"jz {op}_cy")
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).store(W["oy"])
p.mark(f"{op}_cy")
shot(W["oy"], (f"push {int(CH_DIST * ONE)}",), (f"push {int(CH_UP * ONE)}",), CH_SH)
p.load(W["oy"]).store(F["brg"]).push(23).store(W["dg"])   # (no lock: a slight dip)
p.load(F["tgt"]).emit(f"jz {op}_cb")
p.load(F["tgt"]).push(1).emit("sub").store(W["dmg"])
for out, f_ in ((W["bx"], "x"), (W["bz"], "z")):
    slot_of(W["dmg"]); p.push(DF[f_]).emit("add", "loadi").store(out)
slot_of(W["dmg"]); p.push(DF["py"]).emit("add", "loadi").push(int(CHIN * ONE)).emit("add")
p.store(W["c"])
p.emit(f"call {L_GAZE}")
p.mark(f"{op}_cb")
blend(CW["ch"])
# THE PUNCH OVERHEAD: the tank, a strike button held choosing its aim
p.mark(f"{op}_pu")
p.push(0).store(W["head"])
p.load(F["sty"]).emit(f"jz {op}_p1", f"jmp {op}_p3")
p.mark(f"{op}_p1")
p.load(ANIM).push(2).emit("eq", f"jz {op}_p2", f"jmp {op}_p3")
p.mark(f"{op}_p2")
p.load(F["plc"]).push(PLANT_HOLD).emit("eq", f"jz {op}_p4", f"jmp {op}_p3")
p.mark(f"{op}_p4")
held(spec.PAD_X | spec.PAD_Y | spec.PAD_B)
p.emit(f"jz {op}_p3")
p.push(ONE).store(W["head"])
p.mark(f"{op}_p3")
p.load(W["head"]).load(CW["pu"]).emit("sub").push(int(PU_EASE * ONE)).emit("mulq")
p.load(CW["pu"]).emit("add").store(CW["pu"])
p.push(64).load(CW["pu"]).emit("lt", f"jz {op}_e")
shot(YAW, (f"push {int(PU_DIST * ONE)}",), (f"push {int(PU_UP * ONE)}",), 0.0)
p.load(YAW).store(F["brg"])
p.push(int(round(PU_PITCH * 1024 / (2 * np.pi)))).store(W["dg"])
blend(CW["pu"])
p.mark(f"{op}_e")
# THE SHAKE: a landed blow jolts the lens side to side for its hitstop
sk = p.label("shake")
p.load(F["shake"]).emit(f"jz {sk}")
p.addi(F["shake"], -1)
p.load(F["shake"]).push(1).emit("and", f"jz {sk}_l")
p.load(spec.CAM_X).push(J).emit("add").store(spec.CAM_X).emit(f"jmp {sk}")
p.mark(f"{sk}_l")
p.load(spec.CAM_X).push(J).emit("sub").store(spec.CAM_X)
p.mark(sk)
sin_of(p, cell=spec.CAM_PITCH)                    # P12: the cull's pitch
p.store(VPS)
sin_of(p, 256, cell=spec.CAM_PITCH)
p.store(VPC)

# ---- P3: the demons' minds -- slow to walk, slow to turn, slow to commit ----
# tear.py:3235-3290, in integers. They turn toward you at a BOUNDED rate
# (0.034 rad a frame: a full turn takes three seconds, so a flank is
# real), walk along their OWN facing rather than at you (a slow turner
# drifts wide -- the gap you move through), and swing only from inside a
# 0.46 rad cone, every 74 frames, cross and lead hook alternating. Angles
# without atan2: the side you are on is the sign of facing x offset, and
# the cone is cross^2 < tan^2(0.46) dot^2, dot > 0.
DTURN = int(round(0.034 * 1024 / (2 * np.pi) * 256))  # heading is yaw << 8
DWALK = int(0.020 * ONE)       # slower than his 0.032: distance is yours
DREACH2 = int(1.5 ** 2 * ONE)  # closer than 1.5 they stop and square up
DCONE = int(np.tan(0.46) ** 2 * ONE)
CONE_OUT = int(np.tan(0.60) ** 2 * ONE)            # tear.py ENEMY_CONE_EXIT
DREST = 74
DTEMP = {k: cart.var("dt_" + k) for k in
         ("ty", "fx", "fz", "dx", "dz", "cr", "dot", "s", "c")}


# ---- the wave: each demon's mind, on a copy of its slot ----------------------
for d in range(3):
    p.push(int(DS) + d * NF).store(CP["src"]).push(int(CUR)).store(CP["dst"])
    p.push(NF).store(CP["n"]).emit(f"call {L_COPY}")
    p.set(F["dmi"], d + 1)                       # (P11: the aim gun asks who)
    p.emit(f"call {L_DMIND}")
    p.push(int(CUR)).store(CP["src"]).push(int(DS) + d * NF).store(CP["dst"])
    p.push(NF).store(CP["n"]).emit(f"call {L_COPY}")
# all three gone: the next wave stands round the crossing (tear.py)
nw = p.label("nowave")
for d in range(3):
    p.load(dslot(d, "st")).push(4).emit("eq")
p.emit("and", "and", f"jz {nw}")
p.push(int(SPAWN)).store(CP["src"]).push(int(DS)).store(CP["dst"])
p.push(3 * NF).store(CP["n"]).emit(f"call {L_COPY}")
p.addi(F["wave"], 1)
p.mark(nw)

# ---- the shove: bodies do not pass through bodies -------------------------
# tear.py weights it by mass (0.85 + 0.55 bulk); he is 1. Inside 0.9
# units apart each pair is pushed apart along the line between them, an
# eighth of that line a frame, shared by mass.
SHOVE2 = int(0.9 ** 2 * ONE)
SH = {k: cart.var("sh_" + k) for k in ("dx", "dz")}


L_SHV = p.label("shv")
SV = {k: cart.var("sv_" + k) for k in ("a", "b", "wa", "wb")}


def shove(ax, az, bx, bz, ma, mb):
    """(through pointers: a's x then z, b's x then z)"""
    assert int(az) == int(ax) + 1 and int(bz) == int(bx) + 1
    p.push(int(ax)).store(SV["a"]).push(int(bx)).store(SV["b"])
    p.push(int(round(ONE / 8 * mb / (ma + mb)))).store(SV["wa"])  # the lighter
    p.push(int(round(ONE / 8 * ma / (ma + mb)))).store(SV["wb"])  # moves more
    p.emit(f"call {L_SHV}")


def _shv_sub():
    def at(ptr, k):
        p.load(SV[ptr])
        if k:
            p.push(k).emit("add")
    sk = p.label("shv")
    p.mark(L_SHV)
    for k, d in ((0, "dx"), (1, "dz")):
        at("b", k); p.emit("loadi"); at("a", k); p.emit("loadi", "sub"); p.store(SH[d])
    p.load(SH["dx"]).load(SH["dx"]).emit("mulq")
    p.load(SH["dz"]).load(SH["dz"]).emit("mulq", "add")
    p.push(SHOVE2).emit("lt", f"jz {sk}")
    for ptr, w, sgn in (("a", "wa", "sub"), ("b", "wb", "add")):
        for k, d in ((0, "dx"), (1, "dz")):
            at(ptr, k); p.emit("loadi").load(SH[d]).load(SV[w]).emit("mulq", sgn)
            at(ptr, k); p.emit("storei")
    p.push(1).emit("ret")           # P15: ...and says so (1: they touched)
    p.mark(sk)
    p.push(0).emit("ret")


def if_standing(ds, body):
    """body() only while every demon in ds is up (st < 3): the fallen and
    the gone neither shove nor are shoved"""
    skip = p.label("up")
    for d in ds:
        p.load(dslot(d, "st")).push(3).emit("lt", f"jz {skip}")
    body()
    p.mark(skip)


def barge(i):
    """Him against demon i. P15, both from tear.py _collide:
    CLEARED OVER, NOT BLOCKED BY -- more than 0.65 apart in height (a
    flip's peak, a launched body) and there is no push at all, which is
    what lets a flip clear a head; and YOU STOP AGAINST A BODY -- a touch
    costs 85% of the run, so nobody slides along a demon at speed. (The
    run only: a strike's lunge is an impulse that has to arrive.)"""
    over = p.label("over")
    p.load(F["py"]).load(dslot(i, "py")).emit("sub", "dup", "mulq")
    p.push(CLEAR2).emit("lt", f"jz {over}")
    shove(dslot(i, "x"), dslot(i, "z"), PX, PZ, DMASS[i], 1.0)
    p.emit(f"jz {over}")
    p.load(F["spd"]).push(BARGE_KEEP).emit("mulq").store(F["spd"])
    p.mark(over)


for i in range(3):
    for j in range(i + 1, 3):
        if_standing((i, j), lambda i=i, j=j: (shove(
            dslot(i, "x"), dslot(i, "z"), dslot(j, "x"), dslot(j, "z"),
            DMASS[i], DMASS[j]), p.emit("drop")))
    if_standing((i,), lambda i=i: barge(i))
# (THE CAMERA HAS NO BODY, measured: shoving demons out of a 1.5 circle
# round the lens pushed them sideways INTO the shot, and the tour route
# went from 1 frame over the ceiling to 20.)
for i in range(3):
    keep_in_arena(dslot(i, "x"), dslot(i, "z"), dslot(i, "ox"), dslot(i, "oz"))
keep_in_arena(PX, PZ, AR["ox"], AR["oz"])          # a shove cannot either

# THE FLASH (tear.py t.flash): the struck body goes blood-red for the
# blow's first frames. OBJ_OTINT can only darken, so it is red at full and
# green and blue cut to a third -- a cast, not a strobe.
FLASH = spec.OBJ_CULL | spec.OBJ_OTINT | (31 << 27) | (10 << 22) | (10 << 17)
FLASH_FOR = 8                  # while more than this much stun is left
# P15: THE TELEGRAPH (tear.py 4503, _WINDUP / _DANGER). The marker over a
# demon's head says what its body is about to do: AMBER through a swing's
# startup, RED while the fist is live -- the same marker the gold AWARE and
# the red lock already use, tinted, so it costs no mesh and no object.
# (OTINT can only darken: gold x (31, 19, 9) is the amber.)
AMBER = spec.OBJ_CULL | spec.OBJ_OTINT | (31 << 27) | (19 << 22) | (9 << 17)
LENS2 = int(1.3 ** 2 * ONE)


# ---- P8: THE ATTRACT INTRO -- a second program, paged in ------------------------
# tear.py _intro / _intro_cam: a scripted flight over the FROZEN arena --
# low across the crosswalk, up past the demons, a crane for the skyline,
# then down behind the fighter as the title slams in -- under two beats of
# text and the slam: THE EVE OF THE APOCALYPSE (the place line is cut: the
# subtext stands alone), TEAR THROUGH THE NIGHT, then TEAR / NOT DEMON with
# its cold and warm ghosts and a white flash. Letterbox bars slide in, the
# frame fades up from black, a faint veil breathes over it.
#
# WHY A SECOND PROGRAM: the game's IMEM is full. The overlay mover (spec.OVL_*)
# swaps scenes at a frame boundary, so the intro is its own 4,096 words:
# its frame code, then -- emitted into BOTH programs by one generator, so
# they cannot drift -- the street, the fighter, the demons, the music and
# the sounds. The arena is frozen because nothing here runs their minds.
#
# THE INTRO IS DATA. Everything that changes per frame -- the camera
# (smoothstepped between the archive's keys, its handheld sway, the gaze
# solved for this machine's yaw and pitch), every string's colour (its
# fade baked in: the display list has no alpha, so a fade is a colour
# walked down to black over the dark street), the veil, fade and flash,
# the bars -- is one ROW, baked here and fetched a frame ahead by the
# first mover into the borrowed end. The archive's drop shadows are not
# drawn: they would double every string's triangles.
#
# THE HANDSHAKE. The title, on its first frame (its timer boots at the
# attract threshold) and after 25 idle seconds, pages the intro in and
# lands the intro's font, strings and first row over the borrowed end. The
# intro ends at INTRO_LEN or on a fresh Start in two frames: the mover puts
# back the borrowed front, then the end -- with the camera cells the game
# never rewrites -- and the overlay pages the game back in. Its title then
# sees the Start that skipped as held, not fresh.
from zeta.forge import Program                               # noqa: E402
p_main = p
q = Program(cart)                    # the intro (cart.program() is the game)
q.label = p_main.label               # ONE label space: shared code is in both


class Tee:
    """The forge's Program, twice: everything emitted lands in both."""

    def __init__(self, *progs):
        self.progs = progs

    def label(self, base):
        return self.progs[0].label(base)

    def __getattr__(self, name):
        fns = [getattr(g, name) for g in self.progs]

        def both(*a, **k):
            for f in fns:
                f(*a, **k)
            return self
        return both


DMA1 = (spec.DMA_SRC, spec.DMA_DST, spec.DMA_LEN, spec.DMA_GO)
OVL = (spec.OVL_SRC, spec.OVL_DST, spec.OVL_LEN, spec.OVL_GO)
# exit, the second frame: the end back, the camera the game never rewrites,
# and the game itself
ix = q.label("ix")
q.load(I_X).emit(f"jz {ix}")
black(q)
mover(q, DMA1, int(END_MAIN), END_LO, B_END)
mover(q, OVL, int(MAIN_PROG), 0, spec.OVL_MAX)
q.set(spec.CAM_Y, int(2.15 * ONE)).set(spec.CAM_PITCH, 20).set(spec.CAM_ROLL, 0)
q.load(YAW).store(CY)
q.emit(f"jmp {L_MUSIC}")
q.mark(ix)
# the flight's end, or a fresh Start: the first exit frame puts the front back
ie = q.label("ie")
q.load(I_T).push(INTRO_LEN).emit("lt")
q.emit("load 1").push(spec.PAD_START).emit("and").push(0).emit("eq")
q.load(PV).push(spec.PAD_START).emit("and", "or")             # not a fresh Start
q.emit("and", f"jz {ie}_x", f"jmp {ie}")
q.mark(f"{ie}_x")
q.set(I_X, 1)
black(q)
mover(q, DMA1, int(FRONT_MAIN), FRONT_LO, B_FRONT)
q.emit(f"jmp {L_MUSIC}")
q.mark(ie)
# the frame: the row the mover brought last frame
for k, c in enumerate((spec.CAM_X, spec.CAM_Y, spec.CAM_Z, spec.CAM_YAW, spec.CAM_PITCH)):
    q.load(ir(k)).store(c)
q.set(spec.CAM_ROLL, 0).set(spec.BG_SRC, 0)
q.load(ir(3)).store(CY)                                   # (the cull reads it)
q.load(ir(5)).store(VPS).load(ir(6)).store(VPC)
q.load(I_T).push(INTRO_RW).emit("mul").push(int(ROWS) + INTRO_RW).emit("add")
q.store(spec.DMA_SRC)                                     # ...and the next row
q.set(spec.DMA_DST, I_ROW).set(spec.DMA_LEN, INTRO_RW).set(spec.DMA_GO, 1)
# the words: (string, x, y, scale, colour field) -- a colour of 0 is unshown
_w = lambda text, sc: len(text) * 4 * sc                  # noqa: E731
_ty = int(spec.H * 0.32)
_gx = (spec.W - _w("TEAR", 8)) // 2
for si, x, y, sc, fk in ((0, (spec.W - _w(INTRO_BEAT1, 2)) // 2, int(spec.H * 0.40) + 24, 2, 6),
                         (1, (spec.W - _w(INTRO_BEAT2, 3)) // 2, int(spec.H * 0.44), 3, 7),
                         (2, _gx - 1, _ty, 8, 8), (2, _gx + 1, _ty, 8, 9),
                         (2, _gx, _ty, 8, 10),
                         (3, (spec.W - _w("NOT DEMON", 4)) // 2, _ty + 8 * 5 + 8, 4, 11)):
    if si == 0:
        q.set(TX["n"], 0)
    sk = q.label("iw")
    q.load(ir(fk + 1)).emit(f"jz {sk}")
    q.set(TX["str"], I_STR[si]).set(TX["x"], x).set(TX["y"], y).set(TX["sc"], sc)
    q.load(ir(fk + 1)).store(TX["rgb"]).emit(f"call {L_TEXT}")
    q.mark(sk)
q.load(TX["n"]).store(spec.DL_BASE)
# the compositor: the full frame (veil, fade or flash), then the two bars
_b = spec.CO_BASE + 1
q.set(spec.CO_BASE, 3)
q.set(_b, (spec.W - 1) << 10).set(_b + 1, (spec.H - 1) << 10).load(ir(13)).store(_b + 2)
q.set(_b + 3, (spec.W - 1) << 10)
q.load(ir(14)).push(1).emit("sub").push(1023).emit("and", "shl 10").store(_b + 4)
q.load(ir(15)).store(_b + 5)
q.set(_b + 6, (spec.W - 1) << 10)
q.push(spec.H).load(ir(14)).emit("sub").push((spec.H - 1) << 10).emit("or").store(_b + 7)
q.load(ir(15)).store(_b + 8)
q.addi(I_T, 1)
# ---- P13: THE PAUSE -- a third program (tear.py _update_pause) ------------
# Start in the fight pages it in; the street stands frozen under a dim and
# two words, RESUME and QUIT, the chosen one in bone. Up and Down choose; A
# confirms, and Start always resumes. Resuming puts the end back and pages
# the game in with every face button SPENT, so the press that resumed is
# not also a jump or a punch; QUIT is the retry's reset and the title.
# The music plays on through it (the shared frame, as the intro's).
pz = Program(cart)
pz.label = p_main.label
pc_ = pz.label("pz")
for b, bit in ((spec.PAD_UP, 0), (spec.PAD_DOWN, 1)):        # Up / Down: choose
    nb = pz.label("pu")
    pz.emit("load 1").push(b).emit("and", f"jz {nb}")
    pz.load(PV).push(b).emit("and", f"jz {nb}_g", f"jmp {nb}")
    pz.mark(f"{nb}_g")
    pz.set(P_CUR, bit)
    pz.mark(nb)
pz.set(W["head"], -1)                                         # (the choice, if any)
pz.emit("load 1").push(spec.PAD_START).emit("and", f"jz {pc_}_a")
pz.load(PV).push(spec.PAD_START).emit("and", f"jz {pc_}_s", f"jmp {pc_}_a")
pz.mark(f"{pc_}_s")
pz.set(W["head"], 0).emit(f"jmp {pc_}_go")                    # Start: resume
pz.mark(f"{pc_}_a")
pz.emit("load 1").push(spec.PAD_A).emit("and", f"jz {pc_}_dr")
pz.load(PV).push(spec.PAD_A).emit("and", f"jz {pc_}_af", f"jmp {pc_}_dr")
pz.mark(f"{pc_}_af")
pz.load(P_CUR).store(W["head"])
pz.mark(f"{pc_}_go")
pz.load(W["head"]).emit(f"jz {pc_}_res")
# QUIT: the retry's reset, the wave back, the title (its attract clock fresh)
for c, v in RETRY_CELLS:
    pz.set(c, v)
# (the spawn table lives in the borrowed end, which holds the pause's words
# right now: the three are marked gone instead, and the fight's own wave
# respawns them from the restored table on its first frame)
for d in range(3):
    pz.set(dslot(d, "st"), 4)
pz.set(F["wave"], -1)
pz.set(int(MODE), 0).set(TT, 0)
if SONG:
    for c in ("cur", "pos", "pend", "acc", "bib", "phr", "ref", "ret", "j", "last"):
        pz.set(SM[c], 0)                         # the record back to its intro lock
pz.mark(f"{pc_}_res")
for b, _ in BTN:                                 # resuming: every button spent
    pz.set(GT[b], 100).set(GC[b], 1)
pz.set(spec.DMA_SRC, int(END_MAIN)).set(spec.DMA_DST, END_LO)
pz.set(spec.DMA_LEN, B_END).set(spec.DMA_GO, 1)
pz.set(spec.OVL_SRC, int(MAIN_PROG)).set(spec.OVL_DST, 0)
pz.set(spec.OVL_LEN, spec.OVL_MAX).set(spec.OVL_GO, 1)
pz.set(spec.DL_BASE, 0).emit(f"jmp {L_MUSIC}")
pz.mark(f"{pc_}_dr")
# the dim and the two words
pz.set(spec.CO_BASE, 1)
pz.rect(0, 0, 0, spec.W - 1, spec.H - 1, 0x050408, 9)
pz.set(TX["n"], 0)
for k, word in enumerate(PAUSE_STRS):
    sc = 3
    x = (spec.W - len(word) * 4 * sc) // 2
    pz.set(TX["str"], P_STR[k]).set(TX["x"], x).set(TX["y"], 120 + 30 * k).set(TX["sc"], sc)
    cs = pz.label("pc")
    pz.push32(0x948E84).store(TX["rgb"])
    pz.load(P_CUR).push(k).emit("eq", f"jz {cs}")
    pz.push32(0xD8CFC1).store(TX["rgb"])
    pz.mark(cs)
    pz.emit(f"call {L_TEXT}")
pz.load(TX["n"]).store(spec.DL_BASE)
p = Tee(p_main, q, pz)               # ...and from here, the shared frame

# ---- WHAT THE CAMERA CANNOT SEE IS NOT SENT -----------------------------------
# The sequencer transforms every vertex of every listed object, and its
# frame-wide vertex cache holds 2,048 (zseq.v): past that, an object is
# re-transformed in EVERY band. The street, the player and three demons
# came to 2,080-2,140 -- so the last demon's parts ran nine times. Now
# each street sector and each demon carries a bounding sphere, and an
# object wholly behind the camera or outside a side plane of the view is
# never listed. The test is in view space, through the camera's own yaw
# and its FIXED pitch, so it is exact for a sphere; the side planes are
# taken at 40 degrees where the screen's edge is 32, for margin.
# (VIS shares the demon minds' scratch: the minds have run before the
# objects are listed, and nothing else touches either -- 8 words for P12)
VIS = {k: Sym(int(list(DTEMP.values())[i]), "vis_" + k, 1)
       for i, k in enumerate(("cx", "cy", "cz", "r", "rx", "rz", "xc", "zc"))}
PCOS, PSIN = (int(round(f(20 * 2 * np.pi / 1024) * ONE)) for f in (np.cos, np.sin))
SCOS, SSIN = int(round(np.cos(np.radians(40)) * ONE)), int(round(np.sin(np.radians(40)) * ONE))
sin_of(p, 256, cell=spec.CAM_YAW)                    # (P12: the camera's own yaw)
p.store(VIS["rx"])                                    # right = (cos, sin)
sin_of(p, cell=spec.CAM_YAW)
p.store(VIS["rz"])

# ---- the object list --------------------------------------------------------
p.set(NOBJ, 0)
p.object(NOBJ, GROUND_M, (f"load {spec.CAM_X}",), 0, (f"load {spec.CAM_Z}",),
         (f"load {spec.CAM_YAW}",), spec.OBJ_CULL)
def if_visible(cx, cy, cz, r, body):
    """body() only when the sphere can be on screen. cx/cz may be cells
    (tuples of ops) or constants; cy and r are constants."""
    skip = p.label("unseen")
    for cell, v in (("cx", cx), ("cz", cz)):
        p.emit(*v) if isinstance(v, tuple) else p.push(int(round(v * ONE)))
        p.store(VIS[cell])
    p.push(int(round(r * ONE))).store(VIS["r"])
    p.push(int(round((cy - 2.15) * ONE))).store(VIS["cy"])
    p.emit(f"call {L_VIS}", f"jz {skip}")
    body()
    p.mark(skip)


# the street as ONE loop over a table (mesh, centre, radius -- the y
# already relative to the eye): twenty unrolled copies of the test were
# ~500 of IMEM's 4,096 words
ST_TAB = cart.data(Table([w for m, (c, r) in zip(STREET, SPHERE) for w in (
    m, int(round(c[0] * ONE)), int(round((c[1] - 2.15) * ONE)),
    int(round(c[2] * ONE)), int(round((r + 0.05) * ONE)))]), "street_cull")
STP, STN = cart.var("st_p"), cart.var("st_n")
stl = p.label("stl")
p.push(int(ST_TAB)).store(STP).push(len(STREET)).store(STN)
p.mark(stl)
for k, c in enumerate(("cx", "cy", "cz", "r")):
    p.load(STP).push(k + 1).emit("add", "loadi").store(VIS[c])
p.emit(f"call {L_VIS}", f"jz {stl}_s")
p.object(NOBJ, (f"load {int(STP)}", "loadi"), 0, 0, 0, 0, spec.OBJ_CULL)
p.mark(f"{stl}_s")
p.addi(STP, 5).addi(STN, -1)
p.load(STN).emit(f"jz {stl}_e", f"jmp {stl}")
p.mark(f"{stl}_e")
def flash_flags(hs, out):
    """out = FLASH while the blow is fresh -- the STRUCK body only: hitstop
    freezes the attacker too, but only the target carries a stun (12 +
    stop, counted down once the freeze is over)"""
    fl = p.label("flash")
    p.push(spec.OBJ_CULL).store(out)
    p.push(FLASH_FOR).load(hs).emit("lt", f"jz {fl}")
    p.push32(FLASH).store(out)
    p.mark(fl)


PFLAGS = cart.var("p_flags")
flash_flags(F["hs"], PFLAGS)
# P10: THE FLIP'S SPIN (the archive's renderer, evade_tilt): a full turn,
# smoothstepped over the flip -- pitched for the tuck (forward) and the
# backflip, rolled for the cartwheels -- about his MIDDLE, 0.9 up, so the
# object is moved by the difference between that point and its rotation.
# W cells, free at draw time: qx pitch, qy roll, x / y / z the shift.
sp_ = p.label("spin")
for c in ("qx", "qy", "x", "y", "z"):
    p.set(W[c], 0)
p.load(F["evf"]).emit(f"jz {sp_}")
p.load(F["evt"]).load(F["evf"]).emit("sub").push(ONE).emit("mul")       # prog * t
p.store(W["k"])
for n in sorted({n for _, n in FLIPS}):                          # (no divide: one
    nk = p.label("sn")                                           # reciprocal per length)
    p.load(F["evt"]).push(n).emit("eq", f"jz {nk}")
    p.load(W["k"]).push(int(round(ONE / n))).emit("mulq").store(W["k"])
    p.mark(nk)
p.load(W["k"]).emit("dup", "mulq").push(3 * ONE).load(W["k"]).emit("dup", "add", "sub", "mulq")   # smoothstep
p.push(1024).emit("mul", "shr 16").push(1023).emit("and").store(W["dg"])   # the angle
CENTER = int(0.9 * ONE)
for k, (cell, sign) in enumerate(((W["qx"], 1), (W["qx"], -1), (W["qy"], 1), (W["qy"], -1))):
    nk = p.label("sk")
    p.load(F["evk"]).push(k).emit("eq", f"jz {nk}")
    p.load(W["dg"]) if sign > 0 else p.push(1024).load(W["dg"]).emit("sub")
    p.push(1023).emit("and").store(cell)
    p.mark(nk)
# the pivot: pitch a -> shift (sinH c sin a, c (1 - cos a), -cosH c sin a);
#            roll r  -> shift (cosH c sin r, c (1 - cos r), sinH c sin r)
for cell, isroll in ((W["qx"], False), (W["qy"], True)):
    sin_of(p, cell=cell)
    p.push(CENTER).emit("mulq").store(W["s"])                    # c sin
    sin_of(p, 256, cell=cell)
    p.push(CENTER).emit("mulq").push(CENTER).emit("swap", "sub")  # c (1 - cos)
    p.load(W["y"]).emit("add").store(W["y"])
    for out, plus, sgn in (((W["x"], 0, 1), (W["z"], 256, -1)) if not isroll
                           else ((W["x"], 256, 1), (W["z"], 0, 1))):
        sin_of(p, plus, cell=HEAD)
        p.load(W["s"]).emit("mulq")
        if sgn < 0:
            p.push(0).emit("swap", "sub")
        p.load(out).emit("add").store(out)
p.mark(sp_)
for m in ((UPPER, LOWER) if "player" not in OMIT else ()):
    # down, he folds FORWARD over his feet, away from the lens -- the
    # archive's collapse folds over the guard, and backwards took him out
    # of the bottom of the shot
    p.object(NOBJ, m, (f"load {int(PX)}", f"load {int(W['x'])}", "add"),
             (f"load {int(F['py'])}", f"load {int(W['y'])}", "add"),
             (f"load {int(PZ)}", f"load {int(W['z'])}", "add"),
             (f"load {int(HEAD)}", f"load {int(F['tilt'])}", f"load {int(W['qx'])}", "add",
              "push 1023", "and", "shl 10", "or", f"load {int(W['qy'])}", "shl 20", "or"),
             (f"load {int(PFLAGS)}",))
for d in range(3 if "demons" not in OMIT else 0):     # the demons, last
    for f, c in (("x", "x"), ("z", "z"), ("cf", "cf")):
        p.load(dslot(d, f)).store(FK[c])
    p.load(dslot(d, "h8")).emit("shr 8").store(FK["yaw"])
    p.load(dslot(d, "jt")).store(FK["jt"])
    p.load(dslot(d, "py")).store(FK["y"])
    p.load(dslot(d, "aw")).store(FK["aw"])
    tm_ = p.label("tmark")                       # P11: the lock's marker, red
    p.load(F["tgt"]).push(d + 1).emit("eq", f"jz {tm_}")
    p.set(FK["aw"], 2)
    p.mark(tm_)
    p.set(W["k"], dslot(d, "x")).emit(f"call {L_TELE}")   # P15: its swing, told
    flash_flags(dslot(d, "hs"), FK["flags"])
    gone = p.label("gone")
    p.load(dslot(d, "st")).push(4).emit("eq", f"jz {gone}_n", f"jmp {gone}")
    p.mark(f"{gone}_n")
    # AGAINST THE LENS, NOT DRAWN. A demon within 1.3 of the camera is a
    # wall of near-clipped faces, and the clipper is the sequencer's most
    # expensive path: the tour route's worst frame (one demon 0.95 from
    # the lens) cost 722,865 clocks -- over the frame. It still fights.
    for c, cam in (("x", spec.CAM_X), ("z", spec.CAM_Z)):
        p.load(dslot(d, c)).load(cam).emit("sub", "dup", "mulq")
    p.emit("add").push(LENS2).emit("swap", "lt", f"jz {gone}")   # 1.3^2 < d^2: draw
    def draw_demon(d=d):
        p.emit(f"call {L_FK}")
        for k in range(STRESS):                  # C1: the clones, beside it
            if k % 3 != d:
                continue
            side = (1 + k // 3) * (1 if (k // 3) % 2 == 0 else -1)
            p.load(dslot(d, "x")).push(int(side * 1.4 * ONE)).emit("add").store(FK["x"])
            p.load(dslot(d, "z")).push(int(0.9 * (1 + k // 3) * ONE)).emit("add").store(FK["z"])
            p.set(FK["aw"], 0)                   # (no marker: one more object)
            p.emit(f"call {L_FK}")
    if_visible((f"load {dslot(d, 'x')}",), 1.0, (f"load {dslot(d, 'z')}",), 1.6,
               draw_demon)
    p.mark(gone)
p.load(NOBJ).store(spec.OL_BASE)

p = p_main                           # (the intro has no style, no HUD)
# ---- the style meter's frame: bleed, rank, best ------------------------------
sb = p.label("sbleed")
p.load(F["dead"]).emit(f"jz {sb}_a", f"jmp {sb}")
p.mark(f"{sb}_a")
p.addi(SY["idle"], 1)
p.push(90).load(SY["idle"]).emit("lt", f"jz {sb}_45")
p.load(SY["pts"]).push(35).emit("sub").store(SY["pts"])      # 2.2 a frame
p.set(SY["combo"], 0).emit(f"jmp {sb}_c")
p.mark(f"{sb}_45")
p.push(45).load(SY["idle"]).emit("lt", f"jz {sb}")
p.load(SY["pts"]).push(10).emit("sub").store(SY["pts"])      # 0.6 a frame
p.mark(f"{sb}_c")
p.load(SY["pts"]).push(0).emit("lt", f"jz {sb}")
p.set(SY["pts"], 0)
p.mark(sb)
# the rank: how many thresholds past the first the points have reached
rk = p.label("rank")
p.set(SY["rank"], 0).push(int(S_AT) + 1).store(SY["src"])
p.mark(rk)
p.load(SY["src"]).emit("loadi").load(SY["pts"]).emit("swap", "lt", f"jz {rk}_e")
p.emit(f"jmp {rk}_e2")
p.mark(f"{rk}_e")
p.addi(SY["rank"], 1).addi(SY["src"], 1)
p.load(SY["rank"]).push(6).emit("lt", f"jz {rk}_e2", f"jmp {rk}")
p.mark(f"{rk}_e2")
# P14: a rank past the card's best is the new best, the moment it is reached
# (a run quit at SSS still reached SSS), and it is owed to the card
lm = p.label("svmax")
p.load(F["fight"]).emit(f"jz {lm}")
p.load(CARDV).load(SY["rank"]).push(1).emit("add", "lt", f"jz {lm}")   # best < rank + 1
p.load(SY["rank"]).push(1).emit("add").store(CARDV)
p.load(CARDF).push(2).emit("or").store(CARDF)
p.mark(lm)

# ---- the HUD's words: the rank, the combo, or RETRY -------------------------------
# Rebuilt only when what it says changes (a key of what is shown):
#   down, past the beat   RETRY                          (key 1)
#   fighting              the rank, top right, in its colour; X and the
#                         combo over the meter once it passes one -- key
#                         (rank + 1) << 8 | combo, so its fields cannot touch
#   the opening           nothing                        (key 0)
hk = p.label("hudk")
p.set(SY["g"], 0)                                     # (the key, building)
p.push(DEATH_BEAT - 1).load(F["dead"]).emit("lt", f"jz {hk}_f")
p.set(SY["g"], 1).emit(f"jmp {hk}_c")
p.mark(f"{hk}_f")
p.load(F["fight"]).emit(f"jz {hk}_c")
p.load(SY["rank"]).push(1).emit("add").push(1 << 8).emit("mul").store(SY["g"])  # (rank+1)<<8
p.load(SY["combo"]).push(1).emit("swap", "lt", f"jz {hk}_c")     # 1 < combo
p.load(SY["combo"]).emit("dup").push(99).emit("lt", f"jz {hk}_99", f"jmp {hk}_k")
p.mark(f"{hk}_99")
p.emit("drop").push(99)
p.mark(f"{hk}_k")
p.load(SY["g"]).emit("add").store(SY["g"])
p.mark(f"{hk}_c")
p.load(SY["g"]).push(int(S_SHOWN)).emit("loadi", "eq", f"jz {hk}_draw", f"jmp {hk}")
p.mark(f"{hk}_draw")
p.load(SY["g"]).push(int(S_SHOWN)).emit("storei")
p.set(TX["n"], 0)
p.load(SY["g"]).push(1).emit("eq", f"jz {hk}_fight")
for k, v in (("str", int(STR_RETRY)), ("x", 141), ("y", 80), ("sc", 2), ("rgb", 0xE8D8C0)):
    p.set(TX[k], v)
p.emit(f"call {L_TEXT}", f"jmp {hk}_out")
p.mark(f"{hk}_fight")
p.load(SY["g"]).emit(f"jz {hk}_out")
p.push(int(S_RGB)).load(SY["rank"]).emit("add", "loadi").store(TX["rgb"])
# the rank's string: a small table of their addresses
p.push(int(S_STRS)).load(SY["rank"]).emit("add", "loadi").store(TX["str"])
p.push(310).push(GW).push(int(S_LEN)).load(SY["rank"]).emit("add", "loadi", "mul", "sub")
p.store(TX["x"])
p.set(TX["y"], 10).set(TX["sc"], 3)
p.emit(f"call {L_TEXT}")
for sym_, x_, col_ in WORDMARK:
    for k, v in (("str", int(sym_)), ("x", x_), ("y", 18), ("sc", 2), ("rgb", col_)):
        p.set(TX[k], v)
    p.emit(f"call {L_TEXT}")
p.load(SY["g"]).push(255).emit("and", f"jz {hk}_out")       # the combo
# X and the combo, as the archive writes it (X5, X12): the digits are
# glyphs from index 10 of the font; no leading zero
D0 = FONT_CH.index("0")
cz = p.label("cz")
p.load(SY["g"]).push(255).emit("and", "dup").push(205).emit("mul", "shr 11")  # /10
p.emit("dup").store(TX["j"])                               # tens
p.push(10).emit("mul", "sub").push(D0).emit("add").store(TX["r"])   # units glyph
p.set(int(STR_COMBO), 3)
p.load(TX["j"]).push(D0).emit("add").store(int(STR_COMBO) + 2)
p.load(TX["r"]).store(int(STR_COMBO) + 3)
p.load(TX["j"]).emit(f"jz {cz}_one", f"jmp {cz}")
p.mark(f"{cz}_one")
p.set(int(STR_COMBO), 2)
p.load(TX["r"]).store(int(STR_COMBO) + 2)
p.mark(cz)
p.push(int(STR_COMBO)).store(TX["str"])
p.set(TX["x"], 158).set(TX["y"], 218).set(TX["sc"], 3)
p.emit(f"call {L_TEXT}")
p.mark(f"{hk}_out")
p.load(TX["n"]).store(spec.DL_BASE)
p.mark(hk)

# ---- THE GAUGE (P6 dresses it): his health, on the compositor's free
# rectangles, from the first blow either way -- an untouched opening is
# the street and nothing else. And going down, the frame darkens -- to
# 7/16, so the prompt (in the framebuffer, under the compositor) reads.
HB = spec.CO_BASE + 1
hud = p.label("hud")
p.set(spec.CO_BASE, 4)
p.push(0).store(HB + 2).push(0).store(HB + 5).push(0).store(HB + 8).push(0).store(HB + 11)
p.load(F["fight"]).emit(f"jz {hud}")
p.rect(0, 8, 8, 110, 14, 0x100808, 12)
p.push(9).load(PHP).push(183).emit("mul", "shr 8").push(9).emit("add")
p.emit("shl 10", "or").store(HB + 3)               # x1 = 9 + hp * 100/140
p.set(HB + 4, 9 | (13 << 10))
p.push(0).load(PHP).emit("lt", f"jz {hud}")
p.push(16).emit("shl 24").push32(0xB02018).emit("or").store(HB + 5)
p.mark(hud)
# the meter toward the next rank, in the rank's colour (bottom right)
mh = p.label("meter")
p.load(F["fight"]).emit(f"jz {mh}")
p.push(BAR_W).load(SY["rank"]).push(6).emit("eq", f"jz {mh}_p", f"jmp {mh}_w")
p.mark(f"{mh}_p")
p.emit("drop")
p.load(SY["pts"]).push(int(S_AT)).load(SY["rank"]).emit("add", "loadi", "sub")
p.push(int(S_FAC)).load(SY["rank"]).emit("add", "loadi", "mulq")
p.mark(f"{mh}_w")
p.push(208).emit("add", "shl 10").push(208).emit("or").store(HB + 9)
p.set(HB + 10, 272 | (276 << 10))
p.push(14).emit("shl 24").push(int(S_RGB)).load(SY["rank"]).emit("add", "loadi", "or")
p.store(HB + 11)
p.mark(mh)
dk = p.label("dark")
p.load(F["dead"]).emit(f"jz {dk}")
p.set(HB + 6, 0 | (319 << 10)).set(HB + 7, 0 | (287 << 10))
p.load(F["dead"]).emit("shr 2").push(7).emit("over", "over", "lt", f"jz {dk}_m")
p.emit("drop", f"jmp {dk}_k")
p.mark(f"{dk}_m")
p.emit("swap", "drop")
p.mark(f"{dk}_k")
p.emit("shl 24").push32(0x000000).emit("or").store(HB + 8)
p.mark(dk)
# P13: THE HIT FLASH (tear.py self.flash): struck, the frame washes red
# through his hitstop -- on the darken rectangle, which only the fallen use
fl_ = p.label("hflash")
p.load(F["dead"]).emit(f"jz {fl_}_a", f"jmp {fl_}")
p.mark(f"{fl_}_a")
p.load(F["hs"]).push(12).emit("sub", "dup").push(1).emit("lt", f"jz {fl_}_p")
p.emit("drop", f"jmp {fl_}")
p.mark(f"{fl_}_p")
p.emit("dup").push(6).emit("swap", "lt", f"jz {fl_}_c")
p.emit("drop").push(6)
p.mark(f"{fl_}_c")
p.set(HB + 6, 0 | (319 << 10)).set(HB + 7, 0 | (287 << 10))
p.emit("shl 24").push32(0xC01010).emit("or").store(HB + 8)
p.mark(fl_)
# ---- the music's frame (stems as one loop over a table: IMEM is 4,096) ----------
p = Tee(p_main, q, pz)               # the music and the sounds: in all three
p.mark(L_MUSIC)
EVN = cart.var("ev_n")
EV_BASE = spec.AU_EV_BASE + 1
EVW, EVV = cart.var("ev_w"), cart.var("ev_v")
L_EV = p.label("ev")
p.set(EVN, 0)


def ev_at(o_cell, ch_bits, value_ops):
    """append an event at sample o_cell: ch_bits = ch << 10 | ctrl << 14"""
    p.load(o_cell).push(ch_bits).emit("or").store(EVW)
    p.emit(*value_ops).store(EVV)
    p.emit(f"call {L_EV}")


INC, CTL = 0, 1 << 14
if not SONG:
    # the voiced stems, one row each: ctrl register, event channel bits,
    # page bits, base volume, fade a frame (x16), its rank
    _vs = [(s, st) for s, st in enumerate(STEMS) if st[1] is not None]
    MSTEM = cart.data(Table([w for s, (n, v, pg, bv, fd) in _vs for w in (
        spec.AU_BASE + 2 * v + 1, v << 10, pg << 8, bv, fd, s)]), "music_stems")
    MS = {k: cart.var("ms_" + k) for k in ("r", "n", "env")}
    mi = p.label("mint")
    p.push(70).load(SY["rank"]).push(34).emit("mul", "add").store(MU["s"])
    p.load(F["dead"]).emit(f"jz {mi}_a")
    p.set(MU["s"], 0)
    p.mark(f"{mi}_a")
    p.load(MU["inten"]).load(MU["s"]).emit("lt", f"jz {mi}_dn")
    p.load(MU["inten"]).push(10).emit("add").store(MU["inten"])
    p.load(MU["s"]).load(MU["inten"]).emit("lt", f"jz {mi}", f"jmp {mi}_cl")
    p.mark(f"{mi}_dn")
    p.load(MU["inten"]).push(3).emit("sub").store(MU["inten"])
    p.load(MU["inten"]).load(MU["s"]).emit("lt", f"jz {mi}")
    p.mark(f"{mi}_cl")
    p.load(MU["s"]).store(MU["inten"])
    p.mark(mi)


    def field(k):
        p.load(MS["r"]).push(k).emit("add", "loadi")


    def env_addr():
        field(5)
        p.push(int(MENV)).emit("add")


    # ---- the frame's fades: every voiced stem, one loop -------------------------------
    fl = p.label("fl")
    p.push(int(MSTEM)).store(MS["r"]).push(len(_vs)).store(MS["n"])
    p.mark(fl)
    env_addr()
    p.emit("loadi")
    field(4)
    p.emit("sub", "dup").push(0).emit("lt", f"jz {fl}_c")
    p.emit("drop").push(0)
    p.mark(f"{fl}_c")
    p.store(MS["env"])
    field(5)
    p.push(1).emit("sub").load(SY["rank"]).emit("lt", f"jz {fl}_g", f"jmp {fl}_k")
    p.mark(f"{fl}_g")
    p.set(MS["env"], 0)                               # silent below its rank
    p.mark(f"{fl}_k")
    p.load(MS["env"])
    env_addr()
    p.emit("storei")
    p.load(MS["env"]).emit("shr 4").load(MU["inten"]).emit("mul", "shr 8")
    field(2)
    p.emit("or")
    field(0)
    p.emit("storei")
    p.addi(MS["r"], 6).addi(MS["n"], -1)
    p.load(MS["n"]).emit(f"jz {fl}_e", f"jmp {fl}")
    p.mark(f"{fl}_e")
    # the kick: four frames of falling pitch and fading level
    kk = p.label("kick")
    p.load(MU["kick"]).push(4).emit("lt", f"jz {kk}_off")
    p.push(KICK_HI).load(MU["kick"]).push(KICK_DROP).emit("mul", "sub")
    p.store(spec.AU_BASE + 2)
    p.push(15).load(MU["kick"]).push(4).emit("mul", "sub").load(MU["inten"]).emit("mul", "shr 8")
    p.push(2 << 4).emit("or").store(spec.AU_BASE + 3)
    p.addi(MU["kick"], 1).emit(f"jmp {kk}")
    p.mark(f"{kk}_off")
    p.set(spec.AU_BASE + 3, 0)
    p.mark(kk)
    dn = p.label("drumn")
    p.load(MU["drum"]).load(MU["dfade"]).emit("sub", "dup").push(0).emit("lt", f"jz {dn}")
    p.emit("drop").push(0)
    p.mark(dn)
    p.store(MU["drum"])
    p.load(MU["drum"]).emit("shr 4").load(MU["inten"]).emit("mul", "shr 8")
    p.store(spec.AU_BASE + 7)

    # ---- a step, if one falls in this frame --------------------------------------------
    st_ = p.label("step")
    p.push(LOOP).load(MU["step"]).push(32).emit("eq", f"jz {st_}_g", f"jmp {st_}_n")
    p.mark(f"{st_}_g")
    p.emit("drop").load(MU["step"]).push(SIX).emit("mul")
    p.mark(f"{st_}_n")
    p.load(MU["t"]).emit("sub").store(MU["o"])
    p.load(MU["o"]).push(spec.SAMPLES_PER_FRAME).emit("lt", f"jz {st_}")
    p.load(MU["step"]).push(31).emit("and").store(MU["step"])     # 32 -> 0
    L_BYTE = p.label("byte")
    # the drums (stem 0): bit 0 kick, bit 1 snare, bit 2 china
    p.push(int(MPAT)).emit(f"call {L_BYTE}")
    nk = p.label("nk")
    p.load(MU["code"]).push(1).emit("and", f"jz {nk}")
    p.set(MU["kick"], 0)
    ev_at(MU["o"], (1 << 10) | INC, (f"push {KICK_HI}",))
    ev_at(MU["o"], (1 << 10) | CTL, (f"load {int(MU['inten'])}", "push 15", "mul",
                                     "shr 8", f"push {2 << 4}", "or"))
    p.mark(nk)
    nd = p.label("nd")
    p.load(MU["code"]).push(6).emit("and", f"jz {nd}")
    p.push(15 * 16).store(MU["drum"]).set(MU["dfade"], 34).push(hz(9000)).store(MU["s"])
    p.load(MU["code"]).push(4).emit("and", f"jz {nd}_s")
    p.set(MU["dfade"], 11).push(hz(6000)).store(MU["s"])           # the china
    p.mark(f"{nd}_s")
    ev_at(MU["o"], (3 << 10) | INC, (f"load {int(MU['s'])}",))
    ev_at(MU["o"], (3 << 10) | CTL, (f"load {int(MU['inten'])}", "push 15", "mul", "shr 8"))
    p.mark(nd)
    # the voiced stems: one loop
    sl = p.label("sl")
    p.push(int(MSTEM)).store(MS["r"]).push(len(_vs)).store(MS["n"])
    p.mark(sl)
    field(5)
    p.push(1).emit("sub").load(SY["rank"]).emit("lt", f"jz {sl}_nx")   # below its rank
    field(5)
    p.push(8).emit("mul").push(int(MPAT)).emit("add", f"call {L_BYTE}")
    p.load(MU["code"]).emit(f"jz {sl}_nx")           # HOLD
    p.load(MU["code"]).push(REST).emit("eq", f"jz {sl}_note")
    p.push(0)
    env_addr()
    p.emit("storei")
    field(1)
    p.load(MU["o"]).emit("or").push(CTL).emit("or").store(EVW)
    field(2)
    p.store(EVV).emit(f"call {L_EV}", f"jmp {sl}_nx")
    p.mark(f"{sl}_note")
    field(3)
    p.push(16).emit("mul")
    env_addr()
    p.emit("storei")
    field(1)
    p.load(MU["o"]).emit("or").store(EVW)
    p.push(int(MNOTE) - 2).load(MU["code"]).emit("add", "loadi").store(EVV)
    p.emit(f"call {L_EV}")
    field(1)
    p.load(MU["o"]).emit("or").push(CTL).emit("or").store(EVW)
    field(3)
    p.load(MU["inten"]).emit("mul", "shr 8")
    field(2)
    p.emit("or").store(EVV).emit(f"call {L_EV}")
    p.mark(f"{sl}_nx")
    p.addi(MS["r"], 6).addi(MS["n"], -1)
    p.load(MS["n"]).emit(f"jz {sl}_e", f"jmp {sl}")
    p.mark(f"{sl}_e")
    p.addi(MU["step"], 1)
    p.mark(st_)
    p.load(MU["t"]).push(spec.SAMPLES_PER_FRAME).emit("add").store(MU["t"])
    lp = p.label("loop")
    p.load(MU["t"]).push(LOOP).emit("lt", f"jz {lp}_w", f"jmp {lp}")
    p.mark(f"{lp}_w")
    p.load(MU["t"]).push(LOOP).emit("sub").store(MU["t"])
    p.mark(lp)

# ---- P7: THE RECORD (the song build) -- "Set It Off" through its STRUCTURE ----
# song_structure.py on this machine: the record is cut into the archive's
# sections (tools/tnd_song.py) and the music WALKS them, one at a time,
# toward the climax -- rank is only the CAP on how far it may go, so even a
# fast climb hears the whole arc. A fall from S or above drops it into the
# BREAKDOWN, a refrain that holds until a rank is won back; tumbling all the
# way to D lands on the MOBIUS REPRISE, the record's end run into its start.
# A forward step waits for the current section's phrase (its own bar count),
# a setback cuts on the next beat, the reprise on the bar -- the archive's
# grids, counted in stream samples (a beat is 7,554 of them at 15,360 Hz).
# The archive crossfades its cuts over 280 ms; one stream cannot, so every
# cut lands on the grid instead, where the record itself is cutting.
# The page: the SECOND mover request (spec.DMA2_*, build 104) brings this
# frame's 256 samples into the wave bank's page 1 -- the pose has the first.
else:
    sd = np.load(HERE.parent / "assets" / "tnd" / "song.npz")
    _order = [str(x) for x in sd["order"]]
    _words, _at = [], {}
    for n in _order:
        _at[n] = len(_words)
        b8 = sd[n].astype(np.int64) & 0xFF
        _words += [int(b8[i] | b8[i + 1] << 8 | b8[i + 2] << 16 | b8[i + 3] << 24)
                   for i in range(0, len(b8), 4)]
    SONGC = cart.cram(Table(_words), "song")
    _fr = dict(zip(_order, (int(x) for x in sd["frames"])))
    PHRASE = {"intro": 4, "lift": 4, "drive": 4, "chorus": 6, "verse": 12, "surge": 6}
    SECS = ("intro", "lift", "drive", "chorus", "verse", "surge", "climax",  # the ladder
            "breakdown", "reprise")                                          # 7, 8
    _rows = []
    for n in SECS:
        st0, nf = (_at["tail"], _fr["tail"] + _fr["intro"]) if n == "reprise" \
            else (_at[n], _fr[n])
        _rows += [int(SONGC) + st0, nf, PHRASE.get(n, 4)]
    SECT = cart.data(Table(_rows), "song_sections")
    SBEAT = round(bakepcm.PCM_HZ * 60 / 122)               # 7,554 samples
    pg = p.label("prog")
    # the journey has come as far as the section playing (if on the ladder)
    p.load(SM["cur"]).push(7).emit("lt", f"jz {pg}_j")
    p.load(SM["cur"]).store(SM["j"])
    p.mark(f"{pg}_j")
    # a SETBACK from S or above: a rank lost, or a knockdown (hitstun rising
    # through 24), while alive
    p.load(F["dead"]).emit(f"jz {pg}_al", f"jmp {pg}_held")
    p.mark(f"{pg}_al")
    p.push(3).load(SM["last"]).emit("lt", f"jz {pg}_held")          # last >= 4
    p.load(SY["rank"]).load(SM["last"]).emit("lt")                   # dropped
    p.load(SM["hs"]).push(24).emit("lt")
    p.load(F["hs"]).push(24).emit("lt").push(0).emit("eq", "and", "or")   # knocked
    p.emit(f"jz {pg}_held")
    p.set(SM["ref"], 1).set(SM["dwell"], 0).emit(f"jmp {pg}_rk")
    p.mark(f"{pg}_held")
    p.load(SM["ref"]).emit(f"jz {pg}_rk")
    p.addi(SM["dwell"], 1)
    p.load(SY["rank"]).emit(f"jz {pg}_bot")
    p.load(SM["last"]).load(SY["rank"]).emit("lt", f"jz {pg}_rk")    # won one back
    p.push(44).load(SM["dwell"]).emit("lt", f"jz {pg}_rk")           # ...after 45
    p.set(SM["ref"], 0).emit(f"jmp {pg}_rk")
    p.mark(f"{pg}_bot")                                              # all the way
    p.set(SM["ref"], 0).set(SM["ret"], 1).set(SM["j"], 0)            # down: reprise
    p.mark(f"{pg}_rk")
    p.load(SY["rank"]).emit(f"jz {pg}_r0")
    p.set(SM["ret"], 0)
    p.mark(f"{pg}_r0")
    # the target, and the grid its cut waits for (0 beat, 1 bar, 2 phrase)
    p.load(SM["ref"]).emit(f"jz {pg}_t1")
    p.set(SM["t"], 7).set(SM["q"], 0).emit(f"jmp {pg}_go")
    p.mark(f"{pg}_t1")
    p.set(SM["q"], 2)
    p.load(SY["rank"]).emit(f"jz {pg}_d", f"jmp {pg}_t2")
    p.mark(f"{pg}_d")
    p.load(SM["ret"]).emit(f"jz {pg}_t2")
    p.set(SM["t"], 8).set(SM["q"], 1).emit(f"jmp {pg}_go")
    p.mark(f"{pg}_t2")
    p.load(SM["j"]).store(SM["t"])
    p.load(SM["cur"]).push(7).emit("lt", f"jz {pg}_go")
    p.load(SM["j"]).load(SY["rank"]).emit("lt", f"jz {pg}_go")
    p.addi(SM["t"], 1)                                   # one step further
    p.mark(f"{pg}_go")
    p.load(SY["rank"]).store(SM["last"]).load(F["hs"]).store(SM["hs"])
    p.load(SM["t"]).store(SM["pend"])                    # (pend == cur: none)
    # the cut, if one is pending and its grid line falls in this frame
    p.load(SM["pend"]).load(SM["cur"]).emit("eq", f"jz {pg}_p", f"jmp {pg}_play")
    p.mark(f"{pg}_p")
    p.push(SBEAT - 1 - spec.WAV_W).load(SM["acc"]).emit("lt", f"jz {pg}_play")  # a beat
    p.load(SM["q"]).emit(f"jz {pg}_cut")
    p.load(SM["bib"]).push(3).emit("eq", f"jz {pg}_play")                       # a bar
    p.load(SM["q"]).push(1).emit("eq", f"jz {pg}_ph", f"jmp {pg}_cut")
    p.mark(f"{pg}_ph")
    p.push(int(SECT) + 2).load(SM["cur"]).push(3).emit("mul", "add", "loadi")   # a phrase
    p.push(1).emit("sub").load(SM["phr"]).emit("eq", f"jz {pg}_play")
    p.mark(f"{pg}_cut")
    for c in ("pos", "acc", "bib", "phr"):
        p.set(SM[c], 0)
    p.load(SM["pend"]).store(SM["cur"])
    # this frame's page: the second request
    p.mark(f"{pg}_play")
    p.push(int(SECT)).load(SM["cur"]).push(3).emit("mul", "add").store(SM["r"])
    p.load(SM["r"]).emit("loadi").load(SM["pos"]).push(spec.WAV_WORDS).emit("mul", "add")
    p.store(spec.DMA2_SRC)
    p.set(spec.DMA2_DST, int(WAVES) + spec.WAV_WORDS).set(spec.DMA2_LEN, spec.WAV_WORDS)
    p.set(spec.DMA2_GO, 1)
    p.addi(SM["pos"], 1)
    p.load(SM["r"]).push(1).emit("add", "loadi").load(SM["pos"]).emit("eq", f"jz {pg}_w")
    p.set(SM["pos"], 0)                                  # the seam (folded)
    p.mark(f"{pg}_w")
    p.load(SM["acc"]).push(spec.WAV_W).emit("add").store(SM["acc"])
    p.push(SBEAT - 1).load(SM["acc"]).emit("lt", f"jz {pg}_c")
    p.load(SM["acc"]).push(SBEAT).emit("sub").store(SM["acc"])
    p.addi(SM["bib"], 1)
    p.load(SM["bib"]).push(4).emit("eq", f"jz {pg}_c")
    p.set(SM["bib"], 0).addi(SM["phr"], 1)
    p.load(SM["r"]).push(2).emit("add", "loadi").load(SM["phr"]).emit("eq", f"jz {pg}_c")
    p.set(SM["phr"], 0)
    p.mark(f"{pg}_c")
    # the bus: up 6 a frame toward 176, down 4 -- and to nothing when he is down
    p.push(176).load(F["dead"]).emit(f"jz {pg}_wa")
    p.emit("drop").push(0)
    p.mark(f"{pg}_wa")
    p.store(SM["t"])
    p.load(SM["bus"]).load(SM["t"]).emit("lt", f"jz {pg}_dn")
    p.addi(SM["bus"], 6)
    p.load(SM["t"]).load(SM["bus"]).emit("lt", f"jz {pg}_bs", f"jmp {pg}_cl")
    p.mark(f"{pg}_dn")
    p.addi(SM["bus"], -4)
    p.load(SM["bus"]).load(SM["t"]).emit("lt", f"jz {pg}_bs")
    p.mark(f"{pg}_cl")
    p.load(SM["t"]).store(SM["bus"])
    p.mark(f"{pg}_bs")
    p.load(SM["bus"]).store(MU["inten"])                 # (the stinger rides it)

sx = p.label("sfx")
p.load(SFX_T).push(SFX_N).emit("lt", f"jz {sx}_q")
p.load(SFX_H).push(6).emit("mul").push(int(SFX)).emit("add").store(SFX_R)
fv = p.label("fv")
p.load(SFX_R).emit("loadi").store(spec.AU_BASE + 0)                  # ring inc
p.load(SFX_T).push(4).emit("lt", f"jz {fv}_r0")
p.push(int(SFX_V)).load(SFX_T).emit("add", "loadi", f"jmp {fv}_r")
p.mark(f"{fv}_r0")
p.push(0)
p.mark(f"{fv}_r")
p.store(spec.AU_BASE + 1)
p.load(SFX_R).push(1).emit("add", "loadi")                          # thump falls
p.load(SFX_R).push(2).emit("add", "loadi").load(SFX_T).emit("mul", "add")
p.store(spec.AU_BASE + 4)
p.push(15 * 256).load(SFX_R).push(3).emit("add", "loadi").load(SFX_T)
p.emit("mul", "sub", "shr 8", "dup").push(0).emit("lt", f"jz {fv}_t")   # ...and fades
p.emit("drop").push(0)
p.mark(f"{fv}_t")
p.load(SFX_T).load(SFX_R).push(5).emit("add", "loadi").emit("lt", f"jz {fv}_t0")
p.emit(f"jmp {fv}_t1")
p.mark(f"{fv}_t0")
p.emit("drop").push(0)
p.mark(f"{fv}_t1")
p.store(spec.AU_BASE + 5)
p.load(SFX_R).push(4).emit("add", "loadi").store(spec.AU_BASE + 6)   # the meat
p.load(SFX_T).emit(f"jz {fv}_s", f"jmp {fv}_m")
p.mark(f"{fv}_s")
p.push(hz(12000)).store(spec.AU_BASE + 6)                            # (the slap)
p.mark(f"{fv}_m")
p.load(SFX_T).push(4).emit("lt", f"jz {fv}_n0")
p.push(int(SFX_V) + 4).load(SFX_H).push(4).emit("mul", "add").load(SFX_T)
p.emit("add", "loadi", f"jmp {fv}_n")
p.mark(f"{fv}_n0")
p.push(0)
p.mark(f"{fv}_n")
p.store(spec.AU_BASE + 7)
p.load(SFX_T).emit(f"jz {sx}_ev", f"jmp {sx}_n")
p.mark(f"{sx}_ev")                               # first frame: slap -> meat
SLAP_AT = cart.var("sfx_slap_at")
p.set(SLAP_AT, SFX_SLAP)
ev_at(SLAP_AT, (3 << 10) | INC, (f"push {int(SFX_MEAT)}", f"load {int(SFX_H)}", "add", "loadi"))
p.mark(f"{sx}_n")
p.addi(SFX_T, 1)
p.emit(f"jmp {sx}")
p.mark(f"{sx}_q")
for reg in (1, 5):                               # quiet (ch3 is the drums')
    p.set(spec.AU_BASE + reg, 0)
p.mark(sx)
# ---- THE SMALL SOUNDS (sfx.py): the whiff, the step, the stinger ----------------
# WHIFF  a swing whose active window closes on nothing: air only -- a noise
#        swell with no transient and no low end, so it can never be taken
#        for a blow ("how a player learns their own range")
# STEP   a low noise thud every half stride (the page stepped slowly)
# STING  a rank climbed: a square arpeggio with a fifth's shimmer over it,
#        higher and longer the higher the rank (_STINGER_ROOT, 3 + r/2 notes)
# On voices nothing else uses: ch11 the whiff, ch12 the step, ch13-14 the
# stinger. The whiff and the step play per-frame (inc, vol) tables through
# one subroutine; the stinger computes its notes, three frames each.
def seq(incs, vols):
    return [w for i, v in zip(incs, vols) for w in (i, v)]


_wv = (4, 8, 10, 9, 7, 5, 4, 2, 1)                  # the swell, then the air
_sv = (10, 8, 6, 4, 3, 2, 1, 1, 0)
SND_WHIFF = cart.data(Table(seq([hz(70 - 3 * k) for k in range(9)], _wv)), "snd_whiff")
SND_STEP = cart.data(Table(seq([hz(9)] * 9, _sv)), "snd_step")
# GUN the crack (sfx.gun_crack): a bright noise burst dropping fast, on ch15
SND_GUN = cart.data(Table(seq([hz(260 - 26 * k) for k in range(9)],
                              (15, 13, 10, 7, 5, 3, 2, 1, 0))), "snd_gun")
SG = {k: cart.var("sg_" + k) for k in ("gr", "last", "d", "t", "n")}
SG.update(SG_T)                                     # (their time cells: declared with F)
# a player's descriptor: its time cell, its table, its length, its voice
PLAYD = {name: cart.data(Table([int(SG[tc]), int(tab), 9, spec.AU_BASE + 2 * ch,
                                PG_NOISE << 8]), "play_" + name)
         for name, tc, tab, ch in (("whiff", "wt", SND_WHIFF, 11),
                                   ("step", "st", SND_STEP, 12),
                                   ("gun", "nt", SND_GUN, 15))}
STING = cart.data(Table([hz(root * 2 ** (semi / 12)) for root in
                         (196, 220, 262, 330, 392, 494, 587)
                         for semi in (0, 4, 7, 12, 16)]), "snd_sting", borrow="auto")
L_PLAY = p.label("play")
sw = p.label("smalls")
# triggers: the whiff on a swing's last active frame with nothing struck
# (a punch's: a shot that misses is not air), the crack on a shot's launch
p.load(ANIM).push(2).emit("eq", f"jz {sw}_w")
p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {sw}_w0")
p.load(AF).emit(f"jz {sw}_wg", f"jmp {sw}_w")
p.mark(f"{sw}_wg")
p.set(SG["nt"], 0).emit(f"jmp {sw}_w")
p.mark(f"{sw}_w0")
p.load(F["con"]).emit(f"jz {sw}_w1", f"jmp {sw}_w")
p.mark(f"{sw}_w1")
p.load(AF).push(1).emit("add")
row(PMT, F["mv"], "endact")
p.emit("eq", f"jz {sw}_w")
p.set(SG["wt"], 0)
p.mark(f"{sw}_w")
p.load(ANIM).push(1).emit("eq", f"jz {sw}_s")         # a step each half stride
p.load(AF).push(15).emit("and", f"jz {sw}_s1", f"jmp {sw}_s")
p.mark(f"{sw}_s1")
p.set(SG["st"], 0)
p.mark(f"{sw}_s")
p.load(SG["last"]).load(SY["rank"]).emit("lt", f"jz {sw}_g")   # a rank climbed
p.set(SG["gt"], 0).load(SY["rank"]).store(SG["gr"])
p.mark(f"{sw}_g")
p.load(SY["rank"]).store(SG["last"])
for name in ("whiff", "step", "gun"):
    p.push(int(PLAYD[name])).store(SG["d"]).emit(f"call {L_PLAY}")
# the stinger: note k = t / 3 of (3 + rank/2), a fifth above at half level
sg = p.label("sting")
p.load(SG["gr"]).emit("shr 1").push(3).emit("add").store(SG["n"])     # notes
p.load(SG["gt"]).load(SG["n"]).push(3).emit("mul", "lt", f"jz {sg}_q")
p.load(SG["gt"]).push(86).emit("mul", "shr 8").store(SG["t"])       # t / 3
p.push(int(STING)).load(SG["gr"]).push(5).emit("mul", "add").load(SG["t"]).emit("add", "loadi")
p.emit("dup").store(spec.AU_BASE + 26)
p.push(3).emit("mul", "shr 1").store(spec.AU_BASE + 28)              # the fifth
p.push(11).load(SG["gt"]).load(SG["t"]).push(3).emit("mul", "sub").push(3).emit("mul", "sub")
p.load(MU["inten"]).push(128).emit("add", "mul", "shr 8")   # (rides the music, louder)
p.emit("dup").push(PG_SQ << 8).emit("or").store(spec.AU_BASE + 27)
p.emit("shr 1").push(PG_SQ << 8).emit("or").store(spec.AU_BASE + 29)
p.addi(SG["gt"], 1).emit(f"jmp {sg}")
p.mark(f"{sg}_q")
p.set(spec.AU_BASE + 27, 0).set(spec.AU_BASE + 29, 0)
p.mark(sg)
if SONG:
    # THE RECORD'S VOICES, ch4-10 in unison on page 1: one voice is quiet by
    # construction (the mix has sixteen channels of headroom), so the
    # channel count is the volume control (carts/gen_stream.py). Each walks
    # the page exactly once a frame by two increments split at one sample
    # (bakepcm.inc_law) -- an event per voice, and LAST in the list, since
    # the list is read in ascending offset and the slap's comes earlier.
    _ia, _ib, _split = bakepcm.inc_law()
    assert SFX_SLAP < _split
    vv = p.label("songv")
    p.load(SM["bus"]).push(SONG_VOL).emit("mul", "shr 8").push(1 << 8).emit("or")
    p.store(SM["t"]).set(SM["r"], SONG_CH[0])
    p.mark(vv)
    p.push(_ia).load(SM["r"]).emit("dup", "add").push(spec.AU_BASE).emit("add", "storei")
    p.load(SM["t"]).load(SM["r"]).emit("dup", "add").push(spec.AU_BASE + 1).emit("add", "storei")
    p.load(SM["r"]).emit(f"shl {spec.AU_EV_CH_SHIFT}").push(_split).emit("or").store(EVW)
    p.push(_ib).store(EVV).emit(f"call {L_EV}")
    p.addi(SM["r"], 1)
    p.load(SM["r"]).push(SONG_CH[-1] + 1).emit("lt", f"jz {vv}_e", f"jmp {vv}")
    p.mark(f"{vv}_e")
p.load(EVN).store(spec.AU_EV_BASE)

p.emit("load 1").store(PV)

# ---- subroutines (after the halt) -------------------------------------------
p.emit("halt")

# VIS: ( -- seen? ). The sphere (vis_cx, vis_cy relative to the eye,
# vis_cz, vis_r) into view space: yaw by the camera's right/forward,
# then its fixed pitch (vy' = vy cos + vz sin, vz' = -vy sin + vz cos).
# Unseen if wholly behind the eye or wholly outside a side plane.
for g, intro_vis in ((p_main, False), (q, True), (pz, True)):   # (the intro: its real pitch and height)
    no_l, yes_l = g.label("vno"), g.label("vyes")
    g.mark(L_VIS)
    g.load(VIS["cx"]).load(spec.CAM_X).emit("sub").store(VIS["cx"])
    g.load(VIS["cz"]).load(spec.CAM_Z).emit("sub").store(VIS["cz"])
    g.load(VIS["cx"]).load(VIS["rx"]).emit("mulq")          # xc = d . right
    g.load(VIS["cz"]).load(VIS["rz"]).emit("mulq", "add").store(VIS["xc"])
    g.load(VIS["cz"]).load(VIS["rx"]).emit("mulq")          # zc = d . forward
    g.load(VIS["cx"]).load(VIS["rz"]).emit("mulq", "sub").store(VIS["zc"])
    # vy = (cy - 2.15) + 2.15 - CAM_Y, at the camera's own pitch (P12: the
    # game's camera pitches now too; the intro writes its row's)
    g.push(0).load(VIS["cy"]).push(int(2.15 * ONE)).emit("add").load(spec.CAM_Y)
    g.emit("sub", "sub").load(VPS).emit("mulq")
    g.load(VIS["zc"]).load(VPC).emit("mulq", "add").store(VIS["zc"])
    g.load(VIS["zc"]).load(VIS["r"]).emit("add").push(0)
    g.emit("lt", f"jz {no_l}_b")                             # zc + r < 0: behind
    g.emit(f"jmp {no_l}")
    g.mark(f"{no_l}_b")
    g.load(VIS["xc"]).emit("dup").push(0).emit("lt", f"jz {yes_l}_a")
    g.push(0).emit("swap", "sub")                            # |xc|
    g.mark(f"{yes_l}_a")
    g.push(SCOS).emit("mulq")
    g.load(VIS["zc"]).push(SSIN).emit("mulq", "sub")         # |xc| cos - zc sin
    g.load(VIS["r"]).emit("swap", "lt", f"jz {yes_l}")       # r < that: outside
    g.mark(no_l)
    g.push(0).emit("ret")
    g.mark(yes_l)
    g.push(1).emit("ret")


# ARENA: ( -- inside? ) for (ar_x, ar_z), the archive's '+'.
p.mark(L_ARENA)
for c in ("x", "z"):                                 # |x|, |z| in place
    pos = p.label("abs")
    p.load(AR[c]).emit("dup").push(0).emit("lt", f"jz {pos}")
    p.push(0).emit("swap", "sub")
    p.mark(pos)
    p.store(AR[c])
yes = p.label("ain")
p.push(AR_SQ).load(AR["x"]).emit("lt")               # outside the square?
p.push(AR_SQ).load(AR["z"]).emit("lt", "or", f"jz {yes}")
for a, b in (("x", "z"), ("z", "x")):                # either street
    p.push(AR_LANE).load(AR[a]).emit("lt")
    p.push(AR_REACH).load(AR[b]).emit("lt", "or", f"jz {yes}")
p.push(0).emit("ret")
p.mark(yes)
p.push(1).emit("ret")

# COPY: n words from src to dst
cl = p.label("copy_l")
p.mark(L_COPY)
p.mark(cl)
p.load(CP["n"]).emit(f"jz {cl}_e")
p.load(CP["src"]).emit("loadi").load(CP["dst"]).emit("storei")
p.addi(CP["src"], 1).addi(CP["dst"], 1).addi(CP["n"], -1)
p.emit(f"jmp {cl}")
p.mark(f"{cl}_e")
p.emit("ret")

# WPT: the keypoint at w_k (character-local, 3 words) placed in the world
# by (w_bx, w_bz) and the yaw whose cos/sin are (w_c, w_s) -- the GPU's
# own model->world turn, so a key and the drawn body agree.
p.mark(L_WPT)
p.load(W["k"]).emit("loadi").store(W["x"])        # lx
p.load(W["k"]).push(1).emit("add", "loadi").load(W["oy"]).emit("add").store(W["y"])
p.load(W["k"]).push(2).emit("add", "loadi").store(W["z"])   # lz
p.load(W["x"]).load(W["c"]).emit("mulq").load(W["z"]).load(W["s"]).emit("mulq", "sub")
p.load(W["x"]).load(W["s"]).emit("mulq").load(W["z"]).load(W["c"]).emit("mulq", "add")
p.load(W["bz"]).emit("add").store(W["z"])
p.load(W["bx"]).emit("add").store(W["x"])
p.emit("ret")

# D2: ( -- |w - q|^2 )
p.mark(L_D2)
for a, b in (("x", "qx"), ("y", "qy"), ("z", "qz")):
    p.load(W[a]).load(W[b]).emit("sub", "dup", "mulq")
p.emit("add", "add", "ret")


def key_d2(kp_ops, bx, bz, c, s):
    """push |key - q|^2 for the key at kp (ops leaving its address)"""
    p.emit(*kp_ops).store(W["k"])
    for a, b in (("bx", bx), ("bz", bz), ("c", c), ("s", s)):
        p.load(b).store(W[a])
    p.emit(f"call {L_WPT}", f"call {L_D2}")


def nearest(kp_ops, bx, bz, c, s):
    """chin and gut against q: leaves HEAD (1/0) in w_head and the nearer
    distance^2 in w_d2"""
    key_d2(kp_ops, bx, bz, c, s)
    p.store(W["dc"])
    key_d2(kp_ops + ("push 3", "add"), bx, bz, c, s)
    p.store(W["dg"])
    p.load(W["dc"]).load(W["dg"]).emit("lt").store(W["head"])
    hd = p.label("hd")
    p.load(W["dg"]).store(W["d2"])
    p.load(W["head"]).emit(f"jz {hd}")
    p.load(W["dc"]).store(W["d2"])
    p.mark(hd)


def landed(table, mv, table_is_cell):
    """after nearest(): w_dmg and w_stop for the move, head or not"""
    hd = p.label("hdmg")
    row(table, mv, "dmg", const_table=not table_is_cell)
    p.store(W["dmg"])
    row(table, mv, "stop", const_table=not table_is_cell)
    p.store(W["stop"])
    p.load(W["head"]).emit(f"jz {hd}")
    row(table, mv, "dmgh", const_table=not table_is_cell)
    p.store(W["dmg"])
    p.addi(W["stop"], 3)
    p.mark(hd)


# DMIND: one demon, on CUR. Three things, in tear.py's order of effect:
#   A  his swing against me   B  my body: frozen, falling, stunned or
#   free (the turret mind)    C  my swing against him
X, Z, H8 = cur("x"), cur("z"), cur("h8")
ST, MF, MV, AI = (cur(f) for f in ("st", "mf", "mv", "ai"))
WF, MOV, ALT, CF = (cur(f) for f in ("wf", "mov", "alt", "cf"))
t = DTEMP
lab = {k: p.label("dm" + k) for k in
       ("gone", "noA", "missA", "B", "frz", "fall", "fallc", "stun", "mind",
        "noturn", "neg", "turned", "free", "near", "nocone", "clip", "walkc",
        "movec", "idlec", "pose", "cx", "over", "noC", "ret", "deadA")}
p.mark(L_DMIND)
p.load(ST).push(4).emit("eq", f"jz {lab['gone']}")
p.emit("ret")
p.mark(lab["gone"])
p.load(X).store(cur("ox")).load(Z).store(cur("oz"))
p.load(H8).emit("shr 8").store(t["ty"])
sin_of(p, cell=t["ty"])
p.store(t["s"])
sin_of(p, 256, cell=t["ty"])
p.store(t["c"])

# ---- A: his fist, against my chin and gut -------------------------------------
p.load(F["act"]).emit(f"jz {lab['noA']}")
p.load(ST).push(3).emit("lt", f"jz {lab['noA']}")    # the fallen are past it
for a, b in (("qx", "fx"), ("qy", "fy"), ("qz", "fz")):
    p.load(F[b]).store(W[a])
p.load(cur("py")).store(W["oy"])                 # struck where it is: aloft
nearest((f"load {cur('kp')}",), X, Z, t["c"], t["s"])
ag_ = p.label("aimgun")                          # P11: THE AIM GUN -- locked, a
p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {ag_}")   # shot goes down
p.load(F["tgt"]).emit(f"jz {ag_}")               # the line to the target, at any
p.load(F["tgt"]).load(F["dmi"]).emit("eq", f"jz {lab['noA']}", f"jmp {ag_}_hit")   # range
p.mark(ag_)
p.load(W["d2"])
row(PMT, F["mv"], "reach2")
p.emit("lt", f"jz {lab['noA']}")
p.mark(f"{ag_}_hit")
landed(PMT, F["mv"], False)
p.load(cur("hp")).load(W["dmg"]).emit("sub").store(cur("hp"))
p.load(W["stop"]).emit("dup", "dup").store(cur("stop")).store(F["stop"])
p.store(F["shake"])
p.load(W["stop"]).push(12).emit("add").store(cur("hs"))
p.set(F["con"], 1).set(F["act"], 0).set(F["fight"], 1)
sound_blow(W["head"])
# STYLE: the blow pays its move's style x its variety x the combo
p.set(SY["cnt"], 0)
for i in range(5):
    p.load(int(S_REC) + i).load(F["mv"]).emit("eq").load(SY["cnt"]).emit("add").store(SY["cnt"])
cm = p.label("cmul")
p.load(SY["cnt"]).push(3).emit("lt", f"jz {cm}_3")
p.push(int(S_MULT)).load(SY["cnt"]).emit("add", "loadi", f"jmp {cm}")
p.mark(f"{cm}_3")
p.push(int(S_MULT) + 3).emit("loadi")
p.mark(cm)
row(PMT, F["mv"], "style")
p.emit("mul")
p.load(SY["combo"]).emit("dup").push(20).emit("lt", f"jz {cm}_c20", f"jmp {cm}_c")
p.mark(f"{cm}_c20")
p.emit("drop").push(20)
p.mark(f"{cm}_c")
p.push(20).emit("add", "mul").push(int(round(ONE / 25))).emit("mulq")   # x16/400
p.load(SY["pts"]).emit("add").store(SY["pts"])
p.addi(SY["combo"], 1).set(SY["idle"], 0)
p.load(F["mv"]).push(int(S_REC)).load(SY["rp"]).emit("add", "storei")
p.addi(SY["rp"], 1)
p.load(SY["rp"]).push(5).emit("eq", f"jz {cm}_r")
p.set(SY["rp"], 0)
p.mark(f"{cm}_r")
p.set(ST, 2).set(MF, 0)                         # a hit stops a swing
# THE LAUNCHER sends it up, helpless the whole arc; any OTHER blow on a
# body already aloft floors its rise to a nudge and refreshes its stun
# (tear.py AIR_HIT_FLOAT / AIR_HIT_HANG) -- so a string keeps it there
lw, la = p.label("lift"), p.label("airh")
row(PMT, F["mv"], "lift")
p.emit("dup", f"jz {lw}_no")
p.store(cur("vy"))
row(PMT, F["mv"], "air")
p.store(cur("hs")).emit(f"jmp {lw}")
p.mark(f"{lw}_no")
p.emit("drop")
p.load(cur("py")).emit(f"jz {lw}")
# P9: the SPECIAL on a body aloft, from the air, is the SPIKE (tear.py)
sk_ = p.label("spike")
p.load(F["mv"]).push(MOVE["special"]).emit("eq", f"jz {sk_}_n")
p.load(F["acmb"]).load(F["py"]).emit("or", f"jz {lw}")          # (from the street:
p.set(cur("vy"), -SLAM)                                          # no air rule at all)
p.load(cur("hs")).push(40).emit("lt", f"jz {sk_}_h")
p.set(cur("hs"), 40)
p.mark(f"{sk_}_h")
p.set(F["acmb"], 0)
p.push(-int(round(0.12 * ONE))).load(F["pvy"]).emit("lt", f"jz {sk_}_v")   # he follows
p.set(F["pvy"], -int(round(0.12 * ONE)))                         # it down a touch
p.mark(f"{sk_}_v")
p.load(F["shake"]).push(14).emit("lt", f"jz {lw}")
p.set(F["shake"], 14).emit(f"jmp {lw}")
p.mark(f"{sk_}_n")
p.load(cur("vy")).push(AIR_FLOAT).emit("lt", f"jz {la}")
p.set(cur("vy"), AIR_FLOAT)
p.mark(la)
p.load(F["acmb"]).emit(f"jz {la}_r")                             # P9: his follow,
p.load(F["acmb"]).push(ACMB_REFRESH).emit("lt", f"jz {la}_r")    # topped back up
p.set(F["acmb"], ACMB_REFRESH)
p.mark(f"{la}_r")
p.load(cur("hs")).push(AIR_HANG).emit("lt", f"jz {lw}")
p.set(cur("hs"), AIR_HANG)
p.mark(lw)
ha_ = p.label("halign")                          # P12: the haymaker's money shot
p.load(F["mv"]).push(MOVE["special"]).emit("eq", f"jz {ha_}")
p.load(W["stop"]).push(ALIGN_LINGER).emit("add").store(CAM_W["hal"])
p.load(F["dmi"]).push(1).emit("sub").store(CAM_W["halt"])
p.mark(ha_)
uw = p.label("uwin")                             # P9: the REAR launcher opens the
p.load(F["mv"]).push(MOVE["rear_uppercut"]).emit("eq", f"jz {uw}")   # jump-cancel
p.set(F["uwin"], UWIN_F)
p.mark(uw)
for vel, trig, neg in ((cur("vx"), F["ps"], True), (cur("vz"), F["pc"], False)):
    p.load(trig)
    row(PMT, F["mv"], "knock")
    p.emit("mulq").load(vel).emit("swap", "sub" if neg else "add").store(vel)
p.push(0).load(cur("hp")).emit("lt", f"jz {lab['deadA']}")
p.emit(f"jmp {lab['noA']}")
p.mark(lab["deadA"])
p.set(ST, 3).set(cur("dt"), 0).set(cur("hs"), 0)  # down
p.mark(lab["noA"])

# ---- B: my body -------------------------------------------------------------------
p.load(cur("stop")).emit(f"jz {lab['frz']}")
p.addi(cur("stop"), -1).emit("ret")             # frozen in the blow
p.mark(lab["frz"])
for pos, vel in ((X, cur("vx")), (Z, cur("vz"))):
    p.load(pos).load(vel).emit("add").store(pos)
    p.load(vel).push(FRIC).emit("mulq").store(vel)
# ALOFT: the arc under the aerial gravity, down to the street (tear.py
# _enemy_vertical)
gr = p.label("grav")
p.load(cur("py")).load(cur("vy")).emit("or", f"jz {gr}")
p.load(cur("vy")).push(GRAVQ).emit("sub").store(cur("vy"))
p.load(cur("py")).load(cur("vy")).emit("add").store(cur("py"))
p.push(0).load(cur("py")).emit("lt", f"jz {gr}_floor", f"jmp {gr}")
p.mark(f"{gr}_floor")
p.set(cur("py"), 0).set(cur("vy"), 0)
p.mark(gr)
p.load(ST).push(3).emit("eq", f"jz {lab['fall']}")
# FALLING: the archive's collapse (HURT -> DOWN, 26 frames, baked at 30 Hz),
# then down a beat and gone
p.addi(cur("dt"), 1)
p.load(cur("dt")).push(26 + 90).emit("lt", f"jz {lab['fallc']}")
p.load(cur("dt")).emit("shr 1", "dup").push(CLIPN["dead"] - 1)
p.emit("lt", f"jz {lab['fallc']}_m", f"jmp {lab['fallc']}_k")
p.mark(f"{lab['fallc']}_m")
p.emit("drop").push(CLIPN["dead"] - 1)                 # lies there
p.mark(f"{lab['fallc']}_k")
p.push(CLIP0["dead"]).emit("add").push(NPART).emit("mul")
p.push(int(CLIPT)).emit("add").store(CF)
p.emit("ret")
p.mark(lab["fallc"])
p.set(ST, 4).emit("ret")
p.mark(lab["fall"])
p.load(cur("hs")).emit(f"jz {lab['stun']}")
p.addi(cur("hs"), -1)
p.push(CLIP0["hurt"] * NPART + int(CLIPT)).store(CF)
p.load(cur("hs")).emit(f"jz {lab['stun']}_e", "ret")
p.mark(f"{lab['stun']}_e")
p.set(ST, 0).emit("ret")
p.mark(lab["stun"])
# ---- the turret mind (tear.py 3268): slow to walk, turn, commit ----------
p.push(0).load(t["s"]).emit("sub").store(t["fx"])    # forward = (-sin, cos)
p.load(t["c"]).store(t["fz"])
p.load(PX).load(X).emit("sub").store(t["dx"])
p.load(PZ).load(Z).emit("sub").store(t["dz"])
p.load(t["fx"]).load(t["dz"]).emit("mulq")
p.load(t["fz"]).load(t["dx"]).emit("mulq", "sub").store(t["cr"])
p.load(t["fx"]).load(t["dx"]).emit("mulq")
p.load(t["fz"]).load(t["dz"]).emit("mulq", "add").store(t["dot"])
# AWARE: he is inside the frontal cone -- entered at 0.46 rad, left only
# past 0.60, so circling right at its edge does not chatter the marker
p.push(0).load(t["dot"]).emit("lt")
p.load(t["cr"]).load(t["cr"]).emit("mulq")
p.load(t["dot"]).load(t["dot"]).emit("mulq")
p.load(cur("aw")).push(CONE_OUT - DCONE).emit("mul").push(DCONE).emit("add", "mulq")
p.emit("lt", "and").store(cur("aw"))
# turn -- unless already on him (cross^2 < dot^2 / 256, dot > 0)
p.push(0).load(t["dot"]).emit("lt")
p.load(t["cr"]).load(t["cr"]).emit("mulq")
p.load(t["dot"]).load(t["dot"]).emit("mulq", "shr 8", "lt", "and")
p.emit(f"jz {lab['noturn']}", f"jmp {lab['turned']}")
p.mark(lab["noturn"])
p.load(t["cr"]).push(0).emit("lt", f"jz {lab['neg']}")
p.load(H8).push(DTURN).emit("sub").store(H8)
p.emit(f"jmp {lab['turned']}")
p.mark(lab["neg"])
p.load(H8).push(DTURN).emit("add").store(H8)
p.mark(lab["turned"])
p.load(H8).push((1024 << 8) - 1).emit("and").store(H8)
# a swing in progress owns the body until its frames are done
p.load(ST).emit(f"jz {lab['free']}")
p.addi(MF, 1)
p.load(MF)
row(cur("mt"), MV, "total", const_table=False)
p.emit("lt", f"jz {lab['over']}")
p.emit(f"jmp {lab['clip']}")
p.mark(lab["over"])
p.set(ST, 0)                    # done: stands (or walks) this same frame
p.mark(lab["free"])
p.set(MOV, 0)
p.load(t["dx"]).load(t["dx"]).emit("mulq")
p.load(t["dz"]).load(t["dz"]).emit("mulq", "add")
p.push(DREACH2).emit("swap", "lt", f"jz {lab['near']}")
p.load(t["fx"]).push(DWALK).emit("mulq").load(X).emit("add").store(X)
p.load(t["fz"]).push(DWALK).emit("mulq").load(Z).emit("add").store(Z)
p.set(MOV, 1).set(AI, 0)
p.emit(f"jmp {lab['clip']}")
p.mark(lab["near"])
p.load(F["dead"]).emit(f"jz {lab['nocone']}_l")      # nobody hits a corpse
p.emit(f"jmp {lab['nocone']}")
p.mark(f"{lab['nocone']}_l")
p.push(0).load(t["dot"]).emit("lt")              # in front...
p.load(t["cr"]).load(t["cr"]).emit("mulq")
p.load(t["dot"]).load(t["dot"]).emit("mulq").push(DCONE).emit("mulq")
p.emit("lt", "and", f"jz {lab['nocone']}")      # ...and inside the cone
p.addi(AI, 1)
p.load(AI).push(DREST).emit("eq", f"jz {lab['clip']}")
p.set(AI, 0).set(ST, 1).set(MF, 0).set(cur("con"), 0)
p.set(SG["wt"], 0)                              # P13: its lunge, heard (the whoosh)
p.load(ALT).store(MV)
p.load(ALT).push(1).emit("xor").store(ALT)
for vel, trig in ((cur("vx"), t["fx"]), (cur("vz"), t["fz"])):   # the lunge
    p.load(trig)
    row(cur("mt"), MV, "lunge", const_table=False)
    p.emit("mulq").load(vel).emit("add").store(vel)
p.emit(f"jmp {lab['clip']}")
p.mark(lab["nocone"])
p.set(AI, 0)                                     # off its nose: no swing
# ---- which frame of which clip ------------------------------------------------
p.mark(lab["clip"])
p.load(WF).push(1).emit("add").push(63).emit("and").store(WF)
p.load(ST).emit(f"jz {lab['walkc']}")
p.load(MV).emit(f"jz {lab['movec']}")
p.load(MF).push(CLIP0["hook"]).emit("add", f"jmp {lab['pose']}")
p.mark(lab["movec"])
p.load(MF).push(CLIP0["cross"]).emit("add", f"jmp {lab['pose']}")
p.mark(lab["walkc"])
p.load(MOV).emit(f"jz {lab['idlec']}")
p.load(WF).emit("shr 2").push(15).emit("and").push(CLIP0["walk"])
p.emit("add", f"jmp {lab['pose']}")
p.mark(lab["idlec"])
p.load(WF).emit("shr 1").push(31).emit("and").push(CLIP0["idle"]).emit("add")
p.mark(lab["pose"])
p.push(NPART).emit("mul").push(int(CLIPT)).emit("add").store(CF)

# ---- C: my fist, against his chin and gut ------------------------------------------
p.load(ST).push(1).emit("eq", f"jz {lab['noC']}")
p.load(cur("con")).emit(f"jz {lab['noC']}_c", f"jmp {lab['noC']}")
p.mark(f"{lab['noC']}_c")
p.load(F["dead"]).emit(f"jz {lab['noC']}_d", f"jmp {lab['noC']}")
p.mark(f"{lab['noC']}_d")
p.load(MF)
row(cur("mt"), MV, "start", const_table=False)
p.emit("lt", f"jz {lab['noC']}_s", f"jmp {lab['noC']}")
p.mark(f"{lab['noC']}_s")
p.load(MF)
row(cur("mt"), MV, "endact", const_table=False)
p.emit("lt", f"jz {lab['noC']}")
# my fist in the world -> q
row(cur("mt"), MV, "fist", const_table=False)
p.load(MF)
row(cur("mt"), MV, "start", const_table=False)
p.emit("sub").push(3).emit("mul", "add").store(W["k"])
for a, b in (("bx", X), ("bz", Z), ("c", t["c"]), ("s", t["s"])):
    p.load(b).store(W[a])
p.set(W["oy"], 0)
p.emit(f"call {L_WPT}")
for a, b in (("qx", "x"), ("qy", "y"), ("qz", "z")):
    p.load(W[b]).store(W[a])
nearest((f"push {int(PKEY)}",), PX, PZ, F["pc"], F["ps"])
p.load(W["d2"])
row(cur("mt"), MV, "reach2", const_table=False)
p.emit("lt", f"jz {lab['noC']}")
landed(cur("mt"), MV, True)
p.load(PHP).load(W["dmg"]).emit("sub").store(PHP)
p.load(W["stop"]).emit("dup", "dup").store(cur("stop")).store(F["stop"])
p.store(F["shake"])
p.load(W["stop"]).push(12).emit("add").store(F["hs"])
p.set(cur("con"), 1).set(F["fight"], 1)
sound_blow(W["head"])
p.load(SY["pts"]).push(int(round(0.45 * ONE))).emit("mulq").store(SY["pts"])
p.set(SY["combo"], 0)
for i in range(5):
    p.set(int(S_REC) + i, 255)
p.set(ANIM, 3).set(F["buf"], 0)                   # his swing is broken
for vel, trig, neg in ((F["vx"], t["s"], True), (F["vz"], t["c"], False)):
    p.load(trig)
    row(cur("mt"), MV, "knock", const_table=False)
    p.emit("mulq").load(vel).emit("swap", "sub" if neg else "add").store(vel)
p.push(0).load(PHP).emit("lt", f"jz {lab['noC']}_k")
p.emit(f"jmp {lab['noC']}")
p.mark(f"{lab['noC']}_k")
p.set(F["dead"], 1).set(ANIM, 4).set(F["hs"], 0)  # he is down
p.addi(int(CARDV) + 1, 1)                            # P14: a run ended, and the
p.load(CARDF).push(2).emit("or").store(CARDF)         # card is owed the count
bst = p.label("best")
p.load(SY["pts"]).emit("shr 4").load(SY["best"]).emit("lt", f"jz {bst}", f"jmp {bst}_k")
p.mark(bst)
p.load(SY["pts"]).emit("shr 4").store(SY["best"])        # tear.py: the best run
p.mark(f"{bst}_k")
p.mark(lab["noC"])
p.emit("ret")

# EV: append (ev_w, ev_v) to the frame's event list
p.mark(L_EV)
p.load(EVW).push(EV_BASE).load(EVN).push(2).emit("mul", "add", "storei")
p.load(EVV).push(EV_BASE + 1).load(EVN).push(2).emit("mul", "add", "storei")
p.addi(EVN, 1).emit("ret")
# BYTE: ( stem's pattern base -- ) mu_code = that stem's byte at mu_step
if not SONG:
    bl = p.label("bl")
    p.mark(L_BYTE)
    p.load(MU["step"]).emit("shr 2", "add", "loadi")
    p.load(MU["step"]).push(3).emit("and").store(MU["s"])
    p.mark(bl)
    p.load(MU["s"]).emit(f"jz {bl}_e")
    p.emit("shr 8").addi(MU["s"], -1).emit(f"jmp {bl}")
    p.mark(f"{bl}_e")
    p.push(255).emit("and").store(MU["code"]).emit("ret")

# TEXT: the string at tx_str (length, then glyphs) at (tx_x, tx_y), x tx_sc,
# in tx_rgb, appended to the display list (tx_n triangles so far) -- each
# glyph's packed rectangles as the forge's Text draws them: two triangles
# a rectangle, the advance four pixels a scale.
tl_, ts_, tw_ = p.label("tl"), p.label("ts"), p.label("tw")
p.mark(L_TEXT)
p.load(TX["str"]).emit("loadi").store(TX["k"])
p.mark(tl_)                                       # each glyph
p.load(TX["k"]).emit(f"jz {tl_}_e")
p.addi(TX["str"], 1)
p.load(TX["str"]).emit("loadi").push(2).emit("mul").push(int(FONT)).emit("add")
p.store(TX["gp"])                                 # its two packed words
p.set(TX["r"], 6)                                 # six rectangle slots
p.mark(ts_)
p.load(TX["r"]).push(3).emit("eq").load(TX["r"]).push(6).emit("eq", "or", f"jz {ts_}_s")
p.load(TX["gp"]).emit("loadi").store(TX["w"]).addi(TX["gp"], 1)   # the next word
p.mark(f"{ts_}_s")
nr = p.label("nr")
p.load(TX["w"]).push(3 << 5).emit("and", f"jz {nr}")          # no width: none
p.load(TX["w"]).push(3).emit("and").load(TX["sc"]).emit("mul")
p.load(TX["x"]).emit("add").store(TX["x0"])
p.load(TX["w"]).emit("shr 2").push(7).emit("and").load(TX["sc"]).emit("mul")
p.load(TX["y"]).emit("add").store(TX["y0"])
p.load(TX["w"]).emit("shr 5").push(3).emit("and").load(TX["sc"]).emit("mul")
p.load(TX["x0"]).emit("add").store(TX["x1"])
p.load(TX["w"]).emit("shr 7").push(7).emit("and").push(1).emit("add")
p.load(TX["sc"]).emit("mul").load(TX["y0"]).emit("add").store(TX["y1"])
# two triangles, fourteen words: which cell each is comes from a table
p.push(spec.DL_BASE + 1).load(TX["n"]).push(spec.DL_STRIDE).emit("mul", "add")
p.store(TX["dl"])
p.set(TX["j"], 0)
p.mark(tw_)
p.push(int(TRI_CELLS)).load(TX["j"]).emit("add", "loadi", "loadi")
p.load(TX["dl"]).load(TX["j"]).emit("add", "storei")
p.addi(TX["j"], 1)
p.load(TX["j"]).push(2 * spec.DL_STRIDE).emit("lt", f"jz {tw_}_e", f"jmp {tw_}")
p.mark(f"{tw_}_e")
p.addi(TX["n"], 2)
p.mark(nr)
p.load(TX["w"]).emit("shr 10").store(TX["w"])
p.addi(TX["r"], -1)
p.load(TX["r"]).emit(f"jz {ts_}_e", f"jmp {ts_}")
p.mark(f"{ts_}_e")
p.load(TX["x"]).load(TX["sc"]).push(4).emit("mul", "add").store(TX["x"])
p.addi(TX["k"], -1).emit(f"jmp {tl_}")
p.mark(f"{tl_}_e")
p.emit("ret")

_kia_sub()
_shv_sub()

# BRG: f_brg = the bearing (yaw) from him to the demon in slot f_brg, by
# bisection on the cross product's sign -- there is no atan2 (or divide) on
# this machine. Leaves dx, dz in w_qx, w_qz (METEOR wants the range).
bg_ = p.label("bg")
p.mark(L_BRG)
for c, f, me in (("qx", "x", PX), ("qz", "z", PZ)):
    p.push(int(DS) + DF[f]).load(F["brg"]).push(NF).emit("mul", "add", "loadi")
    p.load(me).emit("sub").store(W[c])
p.mark(L_YAW)                                    # (YAW: from w_qx, w_qz as they are)
p.set(F["brg"], 0)
p.push(0).load(W["qz"]).emit("lt", f"jz {bg_}_0")      # behind: start half round
p.set(F["brg"], 512)
p.mark(f"{bg_}_0")
p.push(256)                                      # (the step rides the stack)
p.mark(f"{bg_}_t")
sin_of(p, cell=F["brg"])                         # cross = (-sin) dz - cos dx
p.load(W["qz"]).emit("mulq").push(0).emit("swap", "sub")
sin_of(p, 256, cell=F["brg"])
p.load(W["qx"]).emit("mulq", "sub")
p.push(0).emit("swap", "lt", f"jz {bg_}_d")      # it lies to the left: up
p.emit("dup").load(F["brg"]).emit("add", f"jmp {bg_}_s")
p.mark(f"{bg_}_d")
p.load(F["brg"]).emit("over", "sub")
p.mark(f"{bg_}_s")
p.store(F["brg"])
p.emit("shr 1", "dup", f"jz {bg_}_x", f"jmp {bg_}_t")
p.mark(f"{bg_}_x")
p.emit("drop")
p.load(F["brg"]).push(1023).emit("and").store(F["brg"])
p.emit("ret")

# GAZE: from the eye (w_x, w_y, w_z) at the point (w_bx, w_c, w_bz): its yaw
# into f_brg, its pitch (down positive) into w_dg -- the yaw by YAW's
# bisection, the range by Newton (1/sqrt, no divide), the pitch by another
# bisection on the sign of (-dy cos p - h sin p)
gz_ = p.label("gz")
p.mark(L_GAZE)
p.load(W["bx"]).load(W["x"]).emit("sub").store(W["qx"])
p.load(W["bz"]).load(W["z"]).emit("sub").store(W["qz"])
p.emit(f"call {L_YAW}")
p.emit(f"call {L_RSQRT}")
p.load(W["d2"]).load(W["s"]).emit("mulq").store(W["s"])   # h
p.load(W["c"]).load(W["y"]).emit("sub").store(W["d2"])     # dy
p.set(W["dg"], 0)
# (THE STEP RIDES THE STACK: this search was eight copies of its body, and
# YAW's nine of its own -- 380 words of a program with 41 left. One body
# each now, halving the step it carries until it is spent.)
p.push(128)
p.mark(f"{gz_}_t")
sin_of(p, 256, cell=W["dg"])
p.load(W["d2"]).emit("mulq").push(0).emit("swap", "sub")   # -dy cos p
sin_of(p, cell=W["dg"])
p.load(W["s"]).emit("mulq", "sub")                         # - h sin p
p.push(0).emit("swap", "lt", f"jz {gz_}_d")
p.emit("dup").load(W["dg"]).emit("add", f"jmp {gz_}_s")
p.mark(f"{gz_}_d")
p.load(W["dg"]).emit("over", "sub")
p.mark(f"{gz_}_s")
p.push(1023).emit("and").store(W["dg"])
p.emit("shr 1", "dup", f"jz {gz_}_x", f"jmp {gz_}_t")
p.mark(f"{gz_}_x")
p.emit("drop", "ret")

# RSQRT: w_s = 1/sqrt(w_qx^2 + w_qz^2) by Newton, the square left in w_d2 --
# no divide on this machine. r0 = 0.08 converges for ranges under ~21.
# GAZE and the prowl's bore-in each carried the nine steps unrolled.
p.mark(L_RSQRT)
p.load(W["qx"]).emit("dup", "mulq").load(W["qz"]).emit("dup", "mulq", "add").store(W["d2"])
p.push(int(0.08 * ONE)).store(W["s"])
p.push(9)
p.mark(f"{gz_}_n")
p.load(W["s"]).emit("dup", "mulq").load(W["d2"]).emit("mulq", "shr 1")
p.push(int(1.5 * ONE)).emit("swap", "sub").load(W["s"]).emit("mulq").store(W["s"])
p.push(1).emit("sub", "dup", f"jz {gz_}_nx", f"jmp {gz_}_n")
p.mark(f"{gz_}_nx")
p.emit("drop", "ret")

# SHOT: the eye him - forward(w_oy) * w_head + left(w_oy) * w_d2, at py +
# w_dmg, into w_x, w_y, w_z (P12's shots share it: IMEM is full)
p.mark(L_SHOT)
for out, me, plus, fsgn in ((W["x"], PX, 0, 1), (W["z"], PZ, 256, -1)):
    sin_of(p, plus, cell=W["oy"])
    p.load(W["head"]).emit("mulq")
    if fsgn < 0:
        p.push(0).emit("swap", "sub")
    p.load(me).emit("add")
    sin_of(p, plus + 256, cell=W["oy"])              # left = forward(face + 256)
    p.load(W["d2"]).emit("mulq")
    if fsgn > 0:
        p.push(0).emit("swap", "sub")
    p.emit("add").store(out)
p.load(F["py"]).load(W["dmg"]).emit("add").store(W["y"])
p.emit("ret")

# BLEND: the camera registers toward (w_x, w_y, w_z, f_brg, w_dg) by
# smoothstep(w_k) -- position straight, the angles the short way round
p.mark(L_BLEND)
p.load(W["k"]).emit("dup", "mulq").push(3 * ONE).load(W["k"]).emit("dup", "add", "sub", "mulq")
p.store(W["k"])
for reg, src in ((spec.CAM_X, W["x"]), (spec.CAM_Y, W["y"]), (spec.CAM_Z, W["z"])):
    p.load(src).load(reg).emit("sub").load(W["k"]).emit("mulq").load(reg).emit("add").store(reg)
for reg, src in ((spec.CAM_YAW, F["brg"]), (spec.CAM_PITCH, W["dg"])):
    p.load(src).load(reg).emit("sub").push(512).emit("add").push(1023)
    p.emit("and").push(512).emit("sub").load(W["k"]).emit("mulq").load(reg)
    p.emit("add").push(1023).emit("and").store(reg)
p.emit("ret")

# NEAR: f_foe = the nearest live demon, or -1 (tear.py _nearest_enemy)
p.mark(L_NEAR)
p.set(F["foe"], -1).push32(1 << 30).store(W["d2"])
for d in range(3):
    nx = p.label("ne")
    p.load(dslot(d, "st")).push(3).emit("lt", f"jz {nx}")
    p.load(dslot(d, "x")).load(PX).emit("sub", "dup", "mulq")
    p.load(dslot(d, "z")).load(PZ).emit("sub", "dup", "mulq", "add", "dup")
    p.load(W["d2"]).emit("lt", f"jz {nx}_f")
    p.store(W["d2"]).set(F["foe"], d).emit(f"jmp {nx}")
    p.mark(f"{nx}_f")
    p.emit("drop")
    p.mark(nx)
p.emit("ret")

# FOE: f_foe = the nearest live demon ALOFT (tear.py _airborne_foe), or -1
fo = p.label("fo")
p.mark(L_FOE)
p.set(F["foe"], -1).push32(1 << 30).store(W["d2"])
for d in range(3):
    nx = p.label("fo_n")
    p.load(dslot(d, "st")).push(3).emit("lt", f"jz {nx}")         # alive
    p.load(dslot(d, "py")).load(dslot(d, "vy")).emit("or", f"jz {nx}")   # aloft (or
                                                                 # launched, in its hitstop)
    p.load(dslot(d, "x")).load(PX).emit("sub", "dup", "mulq")
    p.load(dslot(d, "z")).load(PZ).emit("sub", "dup", "mulq", "add", "dup")
    p.load(W["d2"]).emit("lt", f"jz {nx}_f")
    p.store(W["d2"]).set(F["foe"], d).emit(f"jmp {nx}")
    p.mark(f"{nx}_f")
    p.emit("drop")
    p.mark(nx)
p.emit("ret")

# PLAY: the descriptor at sg_d -- [time cell, table, length, voice inc
# register, page bits]: the table's (inc, vol) for this frame, or silence
pl = p.label("pl")
p.mark(L_PLAY)
def dfield(k):
    p.load(SG["d"])
    if k:
        p.push(k).emit("add")
    p.emit("loadi")
dfield(0); p.emit("loadi").store(SG["t"])
p.load(SG["t"]); dfield(2); p.emit("lt", f"jz {pl}_q")
dfield(1); p.load(SG["t"]).push(2).emit("mul", "add", "dup", "loadi")
dfield(3); p.emit("storei")                                 # inc
p.push(1).emit("add", "loadi"); dfield(4); p.emit("or")
dfield(3); p.push(1).emit("add", "storei")                  # ctrl: page | vol
p.load(SG["t"]).push(1).emit("add"); dfield(0); p.emit("storei")
p.emit("ret")
p.mark(f"{pl}_q")
dfield(4); dfield(3); p.push(1).emit("add", "storei")       # silent
p.emit("ret")

# SINE: ( a -- sin a ), Q16.16, from the quarter wave. sin(a) for a in
# 256..511 is sin(512 - a); the lower half-turn negates the upper.
qs = {k: cart.var("qs_" + k) for k in ("a", "i")}
pos_l = p.label("qpos")
p.mark(L_SINE)
p.push(1023).emit("and", "dup").store(qs["a"])
p.push(255).emit("and").store(qs["i"])
p.load(qs["a"]).push(256).emit("and", f"jz {L_SINE}_q")
p.push(256).load(qs["i"]).emit("sub").store(qs["i"])
p.mark(f"{L_SINE}_q")
p.push(int(QSIN)).load(qs["i"]).emit("add", "loadi")
p.load(qs["a"]).push(512).emit("and", f"jz {pos_l}")
p.push(0).emit("swap", "sub")
p.mark(pos_l)
p.emit("ret")

def rot2(u, v, ang):
    """(u, v) <- rotated by the angle in cell `ang`: the GPU's own _rotv"""
    p.load(ang).emit(f"call {L_SINE}").store(FK["s"])
    p.load(ang).push(256).emit("add", f"call {L_SINE}").store(FK["c"])
    p.load(u).load(FK["c"]).emit("mulq").load(v).load(FK["s"]).emit("mulq", "sub")
    p.load(u).load(FK["s"]).emit("mulq").load(v).load(FK["c"]).emit("mulq", "add")
    p.store(v).store(u)


# ROT: (vx, vy, vz) <- R(ra) v, ra a packed angles word: roll (x,y), then
# pitch (y,z), then yaw (x,z) -- exactly the order the GPU poses a model in
p.mark(L_ROT)
for shift, (u, v) in ((20, ("vx", "vy")), (10, ("vy", "vz")), (0, ("vx", "vz"))):
    p.load(FK["ra"])
    if shift:
        p.emit(f"shr {shift}")
    p.push(1023).emit("and").store(FK["t"])
    rot2(FK[u], FK[v], FK["t"])
p.emit("ret")

# FK: one demon's twelve parts into the object list. Args: fk_x, fk_z,
# fk_yaw (its heading), fk_jt (its build's joint table), fk_cf (this
# frame's row of the clip table). Each part: its origin is its parent's
# plus the parent's rotation of its offset (char-local, kept in dem_pt),
# then the whole demon turns by its heading -- which, yaw being the
# GPU's LAST rotation, is also just an add to every part's yaw.
# TELE: the demon whose slot starts at w_k is swinging (st 1)? Then its
# marker tells it -- fk_aw 3 through the startup, 5 while the fist is live;
# in the recovery, whatever it was. (w_k and w_s: free once he is drawn.)
tl_ = p.label("tele")
p.mark(L_TELE)
p.load(W["k"]).push(DF["st"]).emit("add", "loadi").push(1).emit("eq", f"jz {tl_}")
p.load(W["k"]).push(DF["mt"]).emit("add", "loadi")
p.load(W["k"]).push(DF["mv"]).emit("add", "loadi").push(NMR).emit("mul", "add").store(W["s"])
p.load(W["k"]).push(DF["mf"]).emit("add", "loadi").store(W["k"])     # its frame
p.load(W["k"]).load(W["s"]).push(MR["endact"]).emit("add", "loadi", "lt", f"jz {tl_}")
p.set(FK["aw"], 5)
p.load(W["k"]).load(W["s"]).push(MR["start"]).emit("add", "loadi", "lt", f"jz {tl_}")
p.set(FK["aw"], 3)
p.mark(tl_)
p.emit("ret")

top = p.label("fk_top")
place = p.label("fk_place")
p.mark(L_FK)
p.set(FK["j"], 0)
p.load(FK["jt"]).store(FK["rp"])
p.push(int(PT)).store(FK["pp"])
p.mark(top)
p.load(FK["cf"]).load(FK["j"]).emit("add", "loadi").store(FK["a"])
for k, c in ((2, "vx"), (3, "vy"), (4, "vz")):
    p.load(FK["rp"]).push(k).emit("add", "loadi").store(FK[c])
p.load(FK["rp"]).emit("loadi").push(0).emit("lt", f"jz {place}_par")
p.emit(f"jmp {place}")                                   # the root: no parent
p.mark(f"{place}_par")
p.load(FK["cf"]).load(FK["rp"]).emit("loadi", "add", "loadi").store(FK["ra"])
p.emit(f"call {L_ROT}")
p.load(FK["rp"]).push(1).emit("add", "loadi").store(FK["q"])
for k, c in enumerate(("vx", "vy", "vz")):
    p.load(FK[c]).load(FK["q"])
    if k:
        p.push(k).emit("add")
    p.emit("loadi", "add").store(FK[c])
p.mark(place)
for k, c in enumerate(("vx", "vy", "vz")):
    p.load(FK[c]).load(FK["pp"])
    if k:
        p.push(k).emit("add")
    p.emit("storei")
rot2(FK["vx"], FK["vz"], FK["yaw"])
p.object(NOBJ, (f"load {int(FK['rp'])}", "push 5", "add", "loadi"),
         (f"load {int(FK['vx'])}", f"load {int(FK['x'])}", "add"),
         (f"load {int(FK['vy'])}", f"load {int(FK['y'])}", "add"),
         (f"load {int(FK['vz'])}", f"load {int(FK['z'])}", "add"),
         (f"load {int(FK['a'])}", "push -1024", "and",
          f"load {int(FK['a'])}", f"load {int(FK['yaw'])}", "add",
          "push 1023", "and", "or"),
         (f"load {int(FK['flags'])}",))
p.addi(FK["rp"], 6)
p.addi(FK["pp"], 3)
p.addi(FK["j"], 1)
p.load(FK["j"]).push(NPART).emit("lt", f"jz {top}_end", f"jmp {top}")
p.mark(f"{top}_end")
p.load(FK["aw"]).emit(f"jz {top}_na")                 # the aware marker
p.object(NOBJ, AWARE_M, (f"load {int(FK['x'])}",),
         (f"load {int(FK['y'])}", f"push {AWARE_LIFT}", "add"),
         (f"load {int(FK['z'])}",), 0, spec.OBJ_CULL)     # (the lock's: tinted below)
p.load(FK["aw"]).push(1).emit("eq", f"jz {top}_tn", f"jmp {top}_na")   # 1: gold, as cast
p.mark(f"{top}_tn")
p.push32(FLASH)                                            # the lock, or DANGER: red
p.load(FK["aw"]).push(3).emit("eq", f"jz {top}_ts")
p.emit("drop").push32(AMBER)                               # the windup: amber
p.mark(f"{top}_ts")
p.load(int(NOBJ)).push(1).emit("sub").push(spec.OL_STRIDE).emit("mul")
p.push(spec.OL_BASE + 1 + 5).emit("add", "storei")
p.mark(f"{top}_na")
p.emit("ret")


# ---- P8's images, now that everything is placed ------------------------------
def _imem(g):
    import tempfile
    from zeta import asm
    with tempfile.NamedTemporaryFile("w", suffix=".zol", delete=False) as f:
        f.write("\n".join(g.lines()) + "\n")
    words = asm.assemble(f.name)["imem"]
    os.unlink(f.name)
    assert len(words) <= spec.OVL_MAX, f"a program of {len(words)} words"
    return words


_main_w, _intro_w, _pause_w = _imem(p_main), _imem(q), _imem(pz)
if os.environ.get("TND_LIST"):          # (a debugging aid: each program's ZOL)
    for nm, g in (("main", p_main), ("intro", q), ("pause", pz)):
        (OUT.parent / f"tnd-{nm}.lst").write_text("\n".join(g.lines()) + "\n")
cart_tables = {int(INTRO_PROG): _intro_w, int(MAIN_PROG): _main_w, int(PAUSE_PROG): _pause_w,
               int(END_MAIN): cart.borrowed("end")[1],
               int(FRONT_MAIN): cart.borrowed("front")[1]}
for sym, res in cart._cram:
    if int(sym) in cart_tables:
        w = cart_tables[int(sym)]
        res._w[:len(w)] = [spec.s32(int(v)) & spec.WORD_MASK for v in w]
for k, v in (("INTRO_PROG", INTRO_PROG), ("MAIN_PROG", MAIN_PROG), ("INTRO_LEN", INTRO_LEN),
             ("PAUSE_PROG", PAUSE_PROG),
             ("BORROW_FRONT", FRONT_LO), ("BORROW_FRONT_N", B_FRONT),
             ("BORROW_END", END_LO), ("BORROW_END_N", B_END)):
    cart.const(k, int(v))                       # (for the gates: tests/test_tnd.py)
out = cart.write(OUT)
print(cart.report())
print(f"programs: the game {len(_main_w)} words, the intro {len(_intro_w)}, "
      f"the pause {len(_pause_w)}")
print(f"street: {len(STREET)} objects, {STREET_FACES} faces")
print(f"poses: {len(bank) // SPAN} x {SPAN} words = {len(bank)} words "
      f"of CRAM; bases {base}")
