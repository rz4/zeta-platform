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

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import carts as _carts                         # noqa: E402
_carts.on_path()                 # sibling generators, wherever they live

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
# THE SWARM HOOK (P20b): TND_SWARM=1 starts the fight in the first plaza with
# the whole swarm (district 4's eight) -- for metering. Local, never committed.
SWARM_TEST = os.environ.get("TND_SWARM") == "1"
# THE LAYERS (P21): TND_LAYER=n builds the game up to layer n, to be judged
# alone on glass. Layer 0 is the BASE -- the city and the player: the tank on
# the d-pad, the dodges, the jab and its context (pick up, unlock), a key and
# a gate a district; no shoulders, no enemies. A local build (build/layerN/),
# never a committed cart; what is settled there is merged into the game.
#   TND_LAYER=1   + THE LEFT SHOULDER (P24, the player's): L held is BOXING --
#                 the lens backs off and he squares up; L clicked twice and
#                 held is the RUN -- the fastest, with momentum, the lens
#                 trailing; A jumps in either, and A again flips.
#   TND_LAYER=2   + SHADOW BOXING (P31, the player's): a blow goes the way
#                 the pad points and his WHOLE BODY turns to throw it --
#                 his steering and the lens do not; moving brings him
#                 back. X is a jab and counts, Y ends the string with what
#                 the count earned (hook, uppercut, haymaker); a button
#                 held slows time, keeps the string, and the lens goes to
#                 where the blow lands.
LAYER = int(os.environ.get("TND_LAYER", "9"))
BASE = LAYER in (0, 1, 2, 3, 4, 5, 6, 7)  # the base's own rules (the layers stand on them)
L1 = LAYER in (1, 2, 3, 4, 5, 6, 7)  # the left shoulder
L2 = LAYER in (2, 3, 4, 5, 6, 7)  # shadow boxing, and the gun
L3 = LAYER in (3, 4, 5, 6, 7)    # the right shoulder: targeting (P35)
L4 = LAYER in (4, 5, 6, 7)       # the enemies (P37): bodies from the cart (frontier 20's core)
L5 = LAYER in (5, 6, 7)          # the world (P38, docs/TND-WORLD.md): a key a gate, bolts, bunkers
L6 = LAYER in (6, 7)             # the bunker's map and his waymarks (P39, TND-WORLD step 3)
L7 = LAYER == 7                  # the bunker is a door and rooms: the prep table, the ring, the range (P40)
SONG_CH = range(4, 11)          # the record's voices (the synth theme's, freed)
SONG_VOL = 15                   # each voice's level at full bus (x bus / 256)
OUT = Path(os.environ.get("TND_OUT", ROOT / "build" / f"layer{LAYER}" / "tnd.zol"
                          if "TND_LAYER" in os.environ else
                          ROOT / "build" / "song" / "tnd.zol" if SONG else HERE / "tnd.zol"))
OUT.parent.mkdir(parents=True, exist_ok=True)
BAKE = ROOT / "assets" / "tnd" / "boxer.npz"
CUT = 1.009                     # the one hip-height cut that fits both
FLIP = True                     # winding, after the left-handed mirror

d = np.load(BAKE)
F, C = d["F"], d["C"]
SEQS = ("idle", "walk", "air", "jab", "cross", "lead_hook", "rear_hook", "special",
        "lead_uppercut", "rear_uppercut", "gun", "gun_charged",
        "run", "kite_fwd", "kite_back", "kite_left", "kite_right",
        "flip_fwd", "flip_back", "flip_cart",
        "dodge_fwd", "dodge_back", "dodge_left", "dodge_right",
        "land")                 # P15: the touchdown's squash
# P25: THE RUN'S ARMS (the player, on glass: "the arms dont swing like how a
# runner would swing there arms"). The archive's run pumps the arm nearly
# straight through 140 degrees with the elbow bent ACROSS the body -- the
# hand passes over his head. The layers play the same stride re-posed on
# the archive's own rig (tools/tnd_extract.py, "run2"): the elbow bent
# forward to a right angle, the upper arm swung 28 degrees ahead and 50
# behind, close in to his sides. (The game's cart keeps the archive's
# until the layers merge.)
# P26: THE WALK'S STRIDE (the player: "the base walking leg cycle looks
# comedically fast, should look more intimidating"). The layers play the
# walk re-solved at a longer stride (0.75 a step, "walk2"), and slower than
# the ground asks -- see the legs knob.
# P29: THE STRIKES, AUTHORED (tools/tnd_extract.py STRIKES): the jab, the
# lead hook, the rear uppercut and the haymaker, each landing on his centre
# line. Their fist paths (P_name) are the layers' hit points too.
# P30: THE BOXER'S FEET (the player: "The boxing model needs better
# footwork"). A boxer's stance -- shorter, wider, sat into the knees -- with
# a guard that is ready, not frozen ("guard2"); the stance's steps as a
# bounce, the near foot down first, never crossing ("hop_*"); and every
# strike's feet PLANTED IN THE WORLD through its lunge ("_n").
# P31: the boxer's STRAFE JUMP, four ways, seven poses by his rise ("sj_*").
STRIKES = ("jab", "lead_hook", "rear_uppercut", "special")
SJ_WAYS = ("fwd", "back", "left", "right")
CLIP_OF = dict({"run": "run2", "walk": "walk2", "idle": "guard2"},
               **{"kite_" + k_: "hop_" + k_ for k_ in ("fwd", "back", "left", "right")},
               **{k_: k_ + "_n" for k_ in STRIKES}) if BASE else {}
if BASE:
    SEQS += ("slide",)           # P27: the run's slide (the layers only; four poses)
if L1:
    SEQS += tuple("sj_" + k_ for k_ in SJ_WAYS)
if L3:
    SEQS += ("run_gun_r", "run_gun_l", "run_gun_f")   # P36: the run, the gun out in one hand


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
DL_LEASE = 79                    # (P19: 78 for the HUD's words, + the pointer)

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
assert 1 + 2 * (_rank + _rects("X") + 2 * _digit + _rects("TND")) <= DL_LEASE, "the HUD"
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
# A PROGRAM'S PAGE: the game, the intro and the pause each fit PAGE words,
# and an overlay copies exactly that much. (It was spec.OVL_MAX, which is
# the whole of IMEM.) 16,384 in the SRAM's IMEM (frontier 19): the game has
# twice the room it had, and a page-in copies 16K words -- a frame's work at
# the SRAM's pace, on the frames the intro or the pause come and go.
PAGE = 16384
if os.environ.get("TND_CARTMESH") == "1" or LAYER in (4, 5, 6, 7):   # (the whole of IMEM is the page --
    PAGE = spec.IMEM_WORDS                    # the machine holds 32,768; a page-in is two frames' work)
INTRO_PROG = cart.cram(Table([0] * PAGE), "intro_prog")
PAUSE_PROG = cart.cram(Table([0] * PAGE), "pause_prog")
MAIN_PROG = cart.cram(Table([0] * PAGE), "main_prog")
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



# ---- EXPERIMENT (exp/cart-mesh; TND_CARTMESH=1, the law only): the body is
# drawn FROM THE CART (spec.OBJ_CART). Each half is a five-word descriptor
# in DMEM; its faces are one stream in the cart, shared by every pose; a
# pose is its vertices (16 bits a coordinate, << CM_SHIFT) and its baked
# face colours (5:5:5), and choosing one is four offsets written -- no
# mover, and no body in DMEM.
CARTMESH = os.environ.get("TND_CARTMESH") == "1" or L4
CM_SHIFT = 2


def _halves16(h):
    h = [int(x) & 0xFFFF for x in h] + [0]
    return [h[i] | h[i + 1] << 16 for i in range(0, len(h) - 1, 2)]


def half_streams(V, S, h):
    """one half of one pose as the cart mesh's two per-pose streams:
    (vertex words, colour words)"""
    mask, vids, tri = h
    P = (np.round(to_zeta(V[vids]) * ONE).astype(np.int64) + (1 << CM_SHIFT >> 1)) >> CM_SHIFT
    assert np.abs(P).max() < 32768, "a vertex does not fit 16 bits at CM_SHIFT"
    c = np.asarray(S[mask]).astype(np.int64) >> 3
    return _halves16(P.reshape(-1)), _halves16((c[:, 0] << 10) | (c[:, 1] << 5) | c[:, 2])


# ---- the body: two meshes, back to back, holding the first idle pose ----
if CARTMESH:
    FSTR = [cart.cram(Table([a | b << 10 | c << 20 for a, b, c in h[2]]), f"body_faces{k}")
            for k, h in enumerate(halves)]
    _s0 = [half_streams(d["V_idle"][0], d["S_idle"][0], h) for h in halves]
    CM_LEN = [len(x) for st in _s0 for x in st]          # vertices, colours; upper then lower
    SPAN = sum(CM_LEN)
else:
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
    for V, S in zip(d["V_" + CLIP_OF.get(s, s)], d["S_" + CLIP_OF.get(s, s)]):
        w = ([x for h in halves for st in half_streams(V, S, h) for x in st] if CARTMESH
             else pose_span(V, S))
        k = tuple(w) if DEDUPE else len(slot)
        if k not in seen:
            seen[k] = len(bank) // SPAN
            bank += w
        slot.append(seen[k])
BANK = cart.cram(Table(bank), "poses")
if CARTMESH:
    _o = [int(BANK), int(BANK) + CM_LEN[0], int(BANK) + sum(CM_LEN[:2]), int(BANK) + sum(CM_LEN[:3])]
    DESC = cart.data(Table([len(halves[0][1]) | len(halves[0][2]) << 16, _o[0], int(FSTR[0]), _o[1], CM_SHIFT,
                            len(halves[1][1]) | len(halves[1][2]) << 16, _o[2], int(FSTR[1]), _o[3], CM_SHIFT]),
                     "body_desc")
    UPPER, LOWER = int(DESC), int(DESC) + spec.CMESH_WORDS
    # THE RIVAL (the experiment's proof): a SECOND full fighter, drawn from
    # the same bank through his own two descriptors and the same two face
    # streams -- ten words of DMEM and four offsets a frame. He stands five
    # units up the street from the start, facing down it, in the guard.
    RIVAL = L3 and not L4
    if RIVAL:
        RDESC = cart.data(Table([len(halves[0][1]) | len(halves[0][2]) << 16, _o[0], int(FSTR[0]), _o[1], CM_SHIFT,
                                 len(halves[1][1]) | len(halves[1][2]) << 16, _o[2], int(FSTR[1]), _o[3], CM_SHIFT]),
                          "rival_desc")
    RIV_T = cart.var("rival_t") if L3 else None
    # THE SIZES BELOW HIM (build/tiers, cut from the archive's full-resolution
    # body by its own pipeline, and posed by this game's own baker): each a
    # single mesh, one face stream a size. TND_CROWD names who stands up the
    # street in the experiment's scenes ("elite:1,common:2,horde:4"); layer 4
    # has its own six, and they WALK (the guard, and the planted walk).
    TIER_FILE = {"elite": "440", "common": "300", "horde": "190"}
    CROWD = [(k_.split(":")[0], int(k_.split(":")[1])) for k_ in
             filter(None, os.environ.get("TND_CROWD", "").split(","))] if L3 else []
    if L4:
        CROWD = [("elite", 1), ("common", 1), ("horde", 4)]
    # (a size's pace a frame, how near it comes, what it takes)
    TIER_IS = {"elite": (0.045, 2.4, 8), "common": (0.040, 2.1, 5), "horde": (0.030, 1.8, 3)}
    TIER, ENEMY = {}, []
    for name_, count_ in CROWD:
        if name_ == "rival" or name_ in TIER:
            continue
        t_ = np.load(ROOT / "build" / "tiers" / (f"clips_{TIER_FILE[name_]}.npz" if L4 else f"pose_{TIER_FILE[name_]}.npz"))
        tri_ = [(int(a), int(c), int(b)) if FLIP else (int(a), int(b), int(c)) for a, b, c in t_["F"]]
        h_ = (np.ones(len(tri_), bool), np.arange(int(t_["F"].max()) + 1), tri_)
        fs_ = cart.cram(Table([a | b << 10 | c << 20 for a, b, c in tri_]), f"{name_}_faces")
        clips_ = ("guard2", "walk2") if L4 else ("idle",)
        ps_ = [half_streams(V_, S_, h_) for c_ in clips_ for V_, S_ in zip(t_["V_" + c_], t_["S_" + c_])]
        TIER[name_] = dict(nv=len(h_[1]), nf=len(tri_), faces=int(fs_), lv=len(ps_[0][0]), span=len(ps_[0][0]) + len(ps_[0][1]),
                           bank=int(cart.cram(Table([x for st in ps_ for part in st for x in part]), f"{name_}_poses")),
                           n=len(t_["V_" + clips_[0]]), walk=len(t_["V_" + clips_[0]]),
                           pace=int(TIER_IS[name_][0] * ONE), stand=TIER_IS[name_][1], hp=TIER_IS[name_][2])
    _slot = 0
    for name_, count_ in CROWD:
        for _ in range(0 if name_ == "rival" else count_):
            T_ = TIER[name_]
            e_ = dict(T=T_, phase=(_slot * 13) % T_["n"], k=_slot,
                      dx=int(((_slot % 4) - 1.5) * 1.5 * ONE), dz=-int((4.5 + 1.6 * (_slot // 4)) * ONE),
                      desc=int(cart.data(Table([T_["nv"] | T_["nf"] << 16, T_["bank"], T_["faces"],
                                                T_["bank"] + T_["lv"], CM_SHIFT]), f"enemy{_slot}")))
            if L4:
                # where it is, where it was (the street's own slide wants both, x then z); its
                # heading; 0 gone / 1 up / 2 down; what it can still take; frames it is held by
                # a blow; frames it flashes; its stride's place; its guard's clock; walking?;
                # frames it has been down
                # (and ITS PLACE ROUND HIM: a sixth of the way round from the last one's, at its
                # size's stand-off -- so they ring him, each on a bearing of its own)
                _a = (_slot * 171 + 60) * 2 * np.pi / 1024
                e_.update(dx=int(((_slot % 3) - 1) * 1.7 * ONE), dz=-int((6.0 + 2.4 * (_slot // 3)) * ONE),
                          rx=int(-np.sin(_a) * T_["stand"] * ONE), rz=int(np.cos(_a) * T_["stand"] * ONE),
                          pos=cart.var(f"e{_slot}_pos", 2), old=cart.var(f"e{_slot}_old", 2),
                          **{k_: cart.var(f"e{_slot}_{k_}") for k_ in ("yaw", "st", "hp", "stun", "fl", "ph", "clk", "walk", "t")})
            ENEMY.append(e_)
            _slot += 1
    RIVAL = RIVAL and (not CROWD or any(k_ == "rival" for k_, _ in CROWD))
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
DEM = np.load(ROOT / "assets" / "tnd" / "demons.npz")
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
        meshes[mk] = cart.data(Mesh([0, 0, 0, ONE // 8, 0, 0, 0, ONE // 8, 0], [(0, 1, 2, 0)])
                               if BASE else            # (no demon stands in the base)
                               part_mesh(np.concatenate(T), np.concatenate(C)),
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
CLIPT = cart.data(Table(clipw[:1] if BASE else clipw), "demon_clips")   # (no demon moves in the base)
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

# ---- P19: THE CITY (games/tnd/city.py; docs/TND-PORT.md P19) ---------------
# The crossroads is gone: the street is a CITY, Terminal Limit's generator
# ported -- a 16x16 tree of streets, districts in order toward the core, a
# plaza at each district's heart. No geometry streams. A node shows one of
# a few PIECES, each built once here and placed as an object at the node,
# turned a quarter turn at a time (yaw 768 is a clockwise quarter: N -> E).
#
# A PIECE is a 16 x 16 tile in nine cells -- the junction, four edges, four
# corners, cut at the facade line FAC either side of the centre. Each side
# of the node is CLOSED, an ARM (a street goes on) or OPEN (inside a plaza:
# the square goes on). The junction is street; an edge is street when its
# side is not closed; a corner only when both its sides are open. A wall
# stands wherever street meets block, facing the street, on a raised
# sidewalk. A wall is FRONTS -- cut where cells meet and mid-junction, each
# its own height, colour, shop and windows -- and a front at the tile's edge
# always stands H_EDGE, so a neighbour, whatever its piece, meets it flush.
import importlib.util as _ilu                                 # noqa: E402
_cs = _ilu.spec_from_file_location("tnd_city", Path(__file__).with_name("city.py"))
city = _ilu.module_from_spec(_cs)
sys.modules["tnd_city"] = city                # (its dataclass asks for itself)
_cs.loader.exec_module(city)
CITY_SEED = 666142
CITY = city.generate(16, CITY_SEED)
CS = CITY.size
WORLD = None
if L5:
    # P38: THE WORLD over the city (world.py; docs/TND-WORLD.md) -- a key a
    # gate, lying at a dead end (often a sector back); bunkers; BACK DOORS,
    # bolted on their deep side; HARD WAYS past a gate. The back doors and
    # the hard ways are streets the tree does not have: they are added to
    # the town here, so its pieces, its map and its arena have them -- and a
    # back door's is shut as a gate's is, until its bolt is drawn.
    sys.modules.setdefault("city", city)          # (world.py asks for it by that name)
    _wsp = _ilu.spec_from_file_location("tnd_world", Path(__file__).with_name("world.py"))
    world = _ilu.module_from_spec(_wsp)
    sys.modules["tnd_world"] = world
    _wsp.loader.exec_module(world)
    WORLD = world.generate(CITY)
    # THE WAY-FINDER'S TREE (the arrow's): the town as it was generated, as
    # a tree from START -- each node's parent, and its place in a walk of
    # the tree (in, out), so "is the waymark under this street" is two
    # comparisons. Built before the new streets: the arrow shows the gates'
    # way, never a bolt's or a hard one.
    _tpar = city._bfs(CITY.adj, CITY.start)[1]
    _tkids = [[m_ for m_ in range(CS * CS) if _tpar[m_] == v_] for v_ in range(CS * CS)]
    _tin, _tout, _clock = [0] * (CS * CS), [0] * (CS * CS), 0
    _stack = [(CITY.start, 0)]
    while _stack:
        v_, i_ = _stack.pop()
        if i_ == 0:
            _tin[v_] = _clock
            _clock += 1
        if i_ < len(_tkids[v_]):
            _stack.append((v_, i_ + 1))
            _stack.append((_tkids[v_][i_], 0))
        else:
            _tout[v_] = _clock - 1
    assert _clock == CS * CS
    for a_, b_ in WORLD.back + WORLD.hard:
        assert b_ not in CITY.adj[a_]
        CITY.adj[a_].append(b_)
        CITY.adj[b_].append(a_)
    for a_ in CITY.adj:
        a_.sort()
# P20: A TOWN, NOT A CANYON (the player, on glass: "still feels too
# spacious ... the streets need the sidewalks like in the original. it
# should feel more like a city, town ... a tighter experience, and feeling
# overwhelmed at times"). The tile halves to 16: a block a few seconds'
# walk, a plaza 25 across, the next corner always near. Urban design's
# measures of a street that holds you -- ENCLOSURE (walls as high as the
# street is wide, or higher), HUMAN SCALE (narrow fronts, a shop at the
# foot of each), TRANSPARENCY (lit windows), COMPLEXITY (no two fronts
# alike side by side) -- are what the pieces build now, on the crossroads'
# own raised sidewalks with their curbs.
TILE = 16.0                                  # = city.BLOCK's role, a power of two
TSH = 20                                     # a node is a shift: Q16 >> TSH
assert TILE * ONE == 1 << TSH
HT = TILE / 2
CITY_LANE = 3.4                              # the centreline to the curb
FAC = CITY_LANE + 1.3                        # the facade line: 9.4 wall to wall
CURB = 0.15                                  # the sidewalk stands this high
H_EDGE = 9.0                                 # every front at a tile's edge: so
                                             # neighbours always meet flush
H_IN = (6.5, 8.0, 11.5, 13.5)                # the fronts between
SHOP_H = 2.6                                 # a shop at the foot of every front
WROWS = ((3.7, 4.6), (6.5, 7.4))             # the floors' windows
# P20b: DARK, as the crossroads was (the player: "i still like the asthetic
# from the original, it should feel dark and demonic heavy fog") -- soot
# and old brick, and the only light is ember
TOWN = ((40, 26, 26), (48, 38, 36), (30, 26, 32), (54, 32, 26), (36, 30, 28))
SHOPS = ((176, 58, 26), (16, 14, 18), (44, 40, 40), (16, 14, 18), (40, 24, 20))   # ember, glass, shutter, glass, door
WIN_LIT, WIN_DARK = (196, 70, 30), (20, 18, 22)
CLOSED, ARMS, OPEN = 0, 1, 2
CSTEP = [CS, 1, -CS, -1]                     # N E S W, in node numbers


def node_sides(n):
    """(N, E, S, W) of node n: CLOSED, ARMS or OPEN"""
    x, y = CITY.xy(n)
    out = []
    for dx, dy, _ in city.DIRS:
        m = (x + dx) + (y + dy) * CS
        if not (0 <= x + dx < CS and 0 <= y + dy < CS) or m not in CITY.adj[n]:
            out.append(CLOSED)
        elif CITY.plaza[n] >= 0 and CITY.plaza[n] == CITY.plaza[m]:
            out.append(OPEN)
        else:
            out.append(ARMS)
    return tuple(out)


def canon(sides):
    """-> (the canonical sides, q): sides is canon turned q clockwise
    quarters, i.e. sides[(k + q) % 4] == canon[k]"""
    best = None
    for q in range(4):
        c = tuple(sides[(k + q) % 4] for k in range(4))
        if best is None or c < best[0]:
            best = (c, q)
    return best


def piece_build(sides):
    """the piece for canonical `sides`, in archive space round the node"""
    def walkable(cx, cy):
        if cx == 0 and cy == 0:
            return True
        if cy == 0:
            return sides[1 if cx > 0 else 3] != CLOSED
        if cx == 0:
            return sides[0 if cy > 0 else 2] != CLOSED
        return sides[0 if cy > 0 else 2] == OPEN and sides[1 if cx > 0 else 3] == OPEN
    span = {-1: (-HT, -FAC), 0: (-FAC, FAC), 1: (FAC, HT)}
    cells = [(cx, cy) for cx in (-1, 0, 1) for cy in (-1, 0, 1)]
    seed_ = sum(s_ * 3 ** k for k, s_ in enumerate(sides))
    # walls: (axis, at, lo, hi, normal sign); axis 0 = a wall of constant x
    # (normal along x), 1 = of constant y; the normal faces the street
    segs = {}
    for a in cells:
        if not walkable(*a):
            continue
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            b_ = (a[0] + d[0], a[1] + d[1])
            if not (b_[0] in span and b_[1] in span) or walkable(*b_):
                continue
            if d[0]:
                key, (lo, hi) = (0, FAC * d[0], -d[0]), span[a[1]]
            else:
                key, (lo, hi) = (1, FAC * d[1], -d[1]), span[a[0]]
            segs.setdefault(key, []).append((lo, hi))
    walls = []
    for (axis, at, sgn), spans in sorted(segs.items()):
        spans.sort()
        cur = list(spans[0])
        for lo, hi in spans[1:] + [(None, None)]:
            if lo is not None and abs(lo - cur[1]) < 1e-6:
                cur[1] = hi
                continue
            walls.append((axis, at, cur[0], cur[1], sgn))
            if lo is not None:
                cur = [lo, hi]
    b = Build()

    def P(axis, at, u, z):
        return (at, u, z) if axis == 0 else (u, at, z)

    def nrm(axis, sgn):
        return (sgn, 0, 0) if axis == 0 else (0, sgn, 0)

    def pick(seq, *k):
        return seq[(seed_ * 7 + sum((i + 3) * int(round(v * 10)) for i, v in enumerate(k))) % len(seq)]
    walk_w = FAC - CITY_LANE
    for wi, (axis, at, lo, hi, sgn) in enumerate(walls):
        # THE FRONTS: cut where the cells meet; one at a tile's edge stands
        # H_EDGE, the rest vary. A front has its shop, and maybe a floor of
        # windows lit or dark (two, if it stands tall)
        cuts = sorted({lo, hi} | {c for c in (-FAC, FAC) if lo + 1e-6 < c < hi - 1e-6})
        fronts = []
        for u0, u1 in zip(cuts, cuts[1:]):
            edge = abs(u0 + HT) < 1e-6 or abs(u1 - HT) < 1e-6
            h = H_EDGE if edge else pick(H_IN, at, u0, sgn, wi)
            fronts.append((u0, u1, h, pick(TOWN, at, u0, sgn), pick(SHOPS, at, u1, sgn),
                           pick((WIN_LIT, None, WIN_LIT, None, None), u0, at, sgn, wi)))
        # (P22, the base: the first wall carries the lantern, and is cut
        # under it -- light is a thing the corners carry, so there must be
        # corners where the light is)
        ul = (lo + hi) / 2 if BASE and wi == 0 else None

        def ucut(u0, u1):
            return [u0, ul, u1] if ul is not None and u0 + 1e-6 < ul < u1 - 1e-6 else [u0, u1]
        for k, (u0, u1, h, col, shop, win) in enumerate(fronts):
            zs = [CURB, SHOP_H]
            if win is not None:
                zs += [z for r in WROWS[:1 if h < 11 else 2] for z in r]
            zs.append(h)
            for j, (z0, z1) in enumerate(zip(zs, zs[1:])):
                c = shop if j == 0 else (win if j % 2 == 0 else col)
                us = ucut(u0, u1)
                for ua, ub in zip(us, us[1:]):
                    b.quad([P(axis, at, ua, z0), P(axis, at, ub, z0),
                            P(axis, at, ub, z1), P(axis, at, ua, z1)], nrm(axis, sgn), c)
            # where the next front is lower, this one's side shows: a cap
            if k + 1 < len(fronts) and fronts[k + 1][2] != h:
                hn = fronts[k + 1][2]
                out = 1 if h > hn else -1
                n = (0, out, 0) if axis == 0 else (out, 0, 0)
                b.quad([P(axis, at, u1, min(h, hn)), P(axis, at - sgn * 3.0, u1, min(h, hn)),
                        P(axis, at - sgn * 3.0, u1, max(h, hn)), P(axis, at, u1, max(h, hn))],
                       n, col if h > hn else fronts[k + 1][3])
        # THE SIDEWALK at its foot, raised, with its curb to the road
        walk_at = at + sgn * walk_w              # (toward the street: the normal)
        scuts = sorted(set(cuts) | ({ul} if ul is not None else set()))
        if BASE and axis == 1:
            # (P24: at an inside corner two walls' sidewalks lay one on the
            # other. Unlit they were one colour and it did not show; lit,
            # each at its own level, they fought for every pixel -- and law
            # and silicon settled the fight differently. The wall across
            # gives the corner to the wall along.)
            s_lo = -CITY_LANE if abs(lo + FAC) < 1e-6 else lo
            s_hi = CITY_LANE if abs(hi - FAC) < 1e-6 else hi
            scuts = sorted({s_lo, s_hi} | {c for c in scuts if s_lo < c < s_hi})
        for u0, u1 in zip(scuts, scuts[1:]):       # (cut at its fronts: a long
            b.quad([P(axis, at, u0, CURB), P(axis, walk_at, u0, CURB),   # flat face's
                    P(axis, walk_at, u1, CURB), P(axis, at, u1, CURB)],  # depth over-
                   (0, 0, 1), SIDEWALK)                                    # reads, and
            b.quad([P(axis, walk_at, u0, 0.0), P(axis, walk_at, u1, 0.0),  # loses to the
                    P(axis, walk_at, u1, CURB), P(axis, walk_at, u0, CURB)],  # ground)
                   nrm(axis, sgn), CURB_C)
    # a jutting corner's pad joins its two sidewalks, curbed on both faces
    for cx, cy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        if walkable(cx, 0) and walkable(0, cy) and not walkable(cx, cy):
            x0, x1 = sorted((cx * CITY_LANE, cx * FAC))
            y0, y1 = sorted((cy * CITY_LANE, cy * FAC))
            b.flat(x0, x1, y0, y1, CURB, SIDEWALK)
            xl, yl = cx * CITY_LANE, cy * CITY_LANE
            b.quad([(xl, y0, 0), (xl, y1, 0), (xl, y1, CURB), (xl, y0, CURB)], (-cx, 0, 0), CURB_C)
            b.quad([(x0, yl, 0), (x1, yl, 0), (x1, yl, CURB), (x0, yl, CURB)], (0, -cy, 0), CURB_C)
    # A LANTERN on the first wall, at its middle, over the sidewalk: warm.
    # (A pool of light under it read as a patch of mud: a flat colour has
    # no falloff.)
    if walls:
        axis, at, lo, hi, sgn = walls[0]
        u = (lo + hi) / 2
        o0, o1 = at, at + sgn * 0.45

        def L3(o, uu, z):
            return P(axis, o, uu, z)
        for z0, z1, c in ((3.1, 3.5, LAMP_C),):
            b.quad([L3(o1, u - .22, z0), L3(o1, u + .22, z0), L3(o1, u + .22, z1),
                    L3(o1, u - .22, z1)], nrm(axis, sgn), c)
            b.quad([L3(o0, u - .22, z0), L3(o0, u + .22, z0), L3(o1, u + .22, z0),
                    L3(o1, u - .22, z0)], (0, 0, -1), c)
        b.lamp = np.array(L3(o1, u, 3.3), float)
        # (P22 tried the pool on the road again, as a lit fan: at a distance
        # it had its falloff at last, but the machine carries light across a
        # face in SCREEN space, and under the lens the fan was a flat pale
        # slab. The lantern lights its wall and the sidewalk under it.)
    return b


LIT_AMB0 = 13                    # P22: the level the town's own dark sits at (of 32)
LIT_GLOW, LIT_GLOW_R = 0.45, 1.6   # what a burning face throws on what is by it, and how far
LIT_LAMP, LIT_LAMP_R = 1.3, 2.4    # the lantern's, by the inverse square
LIT_WALK = 0.12                    # the sidewalks', everywhere the same


def _tri_dist(p_, tri):
    """the distance from p_ to a triangle, near enough: to its corners, the
    middles of its sides and its middle"""
    a_, b_, c_ = tri
    pts = (a_, b_, c_, (a_ + b_) / 2, (b_ + c_) / 2, (c_ + a_) / 2, (a_ + b_ + c_) / 3)
    return min(float(np.linalg.norm(p_ - q_)) for q_ in pts)


def piece_light(b):
    """P22, THE BASE IS LIT (spec.OBJ_LIT). The machine lights a vertex by
    its normal against ONE direction, and does not turn the normal with the
    object -- so with the light straight down, a vertex's 'normal' is simply
    HOW LIT IT IS, whatever way its piece is turned: (0, t * 127, 0) reads
    level = AMB + DIF * t. Baked here, a corner at a time:
      what BURNS (a lit shop, a lit floor, the lantern) has corners of its
        own, fully lit;
      every other corner takes the glow of the burning faces near it
        (falling off with distance), the lantern's light by the inverse
        square, and the street's own level, which lifts the foot of every
        wall a little -- so a shop's glow climbs the wall over it and lies
        on the sidewalk at its foot;
    Faces that do not burn are stored at their LIT colour (x 32 / AMB0), so
    in the town's dark they show as they did.
    -> the mesh, for the object list with OBJ_LIT"""
    _ns = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
    burn = {rgb(shade(c_, n_)) for c_ in (SHOPS[0], WIN_LIT, LAMP_C) for n_ in _ns}
    # (P25: THE WALK IS ONE LEVEL EVERYWHERE. A level a face made each stretch
    # of sidewalk its own grey, and by a lit shop a pale one -- hard-edged
    # slabs along the bottom and sides of the screen wherever the walk ran
    # under the lens: the player's "visual graphics bugs on the edges of the
    # screen". The light is the walls'; the walk stays dark stone.)
    walk = {rgb(shade(c_, n_)) for c_ in (SIDEWALK, CURB_C) for n_ in _ns}
    V = [np.array(v_, float) / ONE for v_ in b.v]              # zeta; distances are the same
    lamp = getattr(b, "lamp", None)
    lampz = None if lamp is None else W(*lamp)
    fires = [[V[i] for i in fc[:3]] for fc in b.f if fc[3] in burn]
    t = []
    for i, p_ in enumerate(V):
        v_ = 0.10 * max(0.0, 1.0 - p_[1] / 5.0)
        if lampz is not None:
            v_ += LIT_LAMP / (1.0 + float(np.sum((p_ - lampz) ** 2)) / LIT_LAMP_R ** 2)
        if fires:
            dmin = min(_tri_dist(p_, tri) for tri in fires)
            v_ += LIT_GLOW / (1.0 + (dmin / LIT_GLOW_R) ** 2)
        t.append(min(0.85, v_))
    # ONE LEVEL A FACE (P24). The first lit base carried the light smoothly
    # across each face, corner to corner -- and where a face ran past the
    # lens and was cut by the near plane, it came out in patches of green
    # and pink. The machine steps a colour across a face from one corner in
    # 1/256ths of a level a pixel, each channel on its own; a cut face's
    # corner lies thousands of pixels off the screen, so each channel's
    # rounding had grown to whole levels by the time it reached the glass
    # (and law and silicon rounded apart: P22's open mismatch). A face whose
    # corners all carry ONE level has no step at all, and is exact. So each
    # face takes the mean of its corners' light, and corners are shared
    # only between faces at the same level.
    verts, key, tl, faces = [], {}, [], []
    gain = 32 / LIT_AMB0

    def vid(i, level):
        q = int(round(min(1.0, max(0.0, level)) * 127))
        if (i, q) not in key:
            key[i, q] = len(verts)
            verts.append(b.v[i])
            tl.append(q << 8)
        return key[i, q]
    fs = list(b.f)
    k = 0
    while k < len(fs):
        grp = [fs[k]]                          # a quad is two faces sharing a side
        if k + 1 < len(fs) and fs[k + 1][3] == fs[k][3] and len(set(fs[k][:3]) & set(fs[k + 1][:3])) == 2:
            grp.append(fs[k + 1])
        col = fs[k][3]
        if col in burn:
            level = 1.0
        elif col in walk:
            level = LIT_WALK
        else:
            cs = {i for fc in grp for i in fc[:3]}
            level = sum(t[i] for i in cs) / len(cs)
            ch = [min(255, int(((col >> sh) & 255) * gain)) for sh in (16, 8, 0)]
            col = ch[0] << 16 | ch[1] << 8 | ch[2]
        for a_, b_, c_, _ in grp:
            faces.append((vid(a_, level), vid(b_, level), vid(c_, level), col))
        k += len(grp)
    assert len(verts) <= spec.MESH_NV_MAX and len(faces) <= spec.MESH_NF_MAX, (len(verts), len(faces))
    return Mesh([c for v_ in verts for c in v_], faces, colors=tl)


CURB_C, LAMP_C = (104, 100, 100), (255, 128, 52)
if BASE:                         # (P22: lit, the walk is darker stone -- at full it was white)
    SIDEWALK, CURB_C = (80, 74, 76), (90, 84, 86)
    # (P25: and dark glass is not a hole -- under the grade (16, 14, 18) was
    # a black rectangle in the wall)
    SHOPS = tuple((30, 27, 34) if c_ == (16, 14, 18) else c_ for c_ in SHOPS)
SIDES = [node_sides(n) for n in range(CS * CS)]
KINDS = sorted({canon(s)[0] for s in SIDES})
PIECE_M = []
CITY_FACES = 0
for kd in KINDS:
    _pb = piece_build(kd)
    CITY_FACES += len(_pb.f)
    if os.environ.get("TND_PIECES"):
        print("piece", kd, "v", len(_pb.v), "f", len(_pb.f), "words", 2 + 3 * len(_pb.v) + 2 * len(_pb.f))
    ms = _pb.meshes()
    assert len(ms) == 1, f"piece {kd} needs {len(ms)} meshes"
    PIECE_M.append(int(cart.data(piece_light(_pb) if BASE else ms[0],
                                 "piece_" + "".join(map(str, kd)))))
# THE ORIGIN IS THE FIRST DISTRICT'S PLAZA: its centre (the corner its four
# nodes share) is world (0, 0), where the crossroads' square was -- so the
# fight begins in an open square half again as wide, the ring of three
# where it always stood.
PX0, PY0 = CITY.plazas[0]
assert CITY.district[PX0 + PY0 * CS] == 0
OXA = PX0 * TILE + HT                     # archive x of the origin, city-wise
OYA = PY0 * TILE + HT
# THE MAP, a word a node: its sides (2 bits each, N E S W from bit 0), the
# piece's yaw (bits 8-17), the piece (bits 18-22), its district (23-26)
# and the way to the core (bits 27-28: the side its next street toward the
# core leaves by -- the pointer's road)
_cd, _cp = city._bfs(CITY.adj, CITY.core)


def side_to(a, b):
    """the side of node a that node b lies through"""
    return CSTEP.index(b - a)


# ...and the way to its own district's plaza (bits 29-30): before the
# district's horde wakes, the pointer leads there
_pl_hop = [0] * (CS * CS)
for _d in range(CITY.districts()):
    _q = [v for v in range(CS * CS) if CITY.plaza[v] >= 0 and CITY.district[v] == _d]
    _seen = set(_q)
    for v in _q:
        for m_ in CITY.adj[v]:
            if m_ not in _seen and CITY.district[m_] == _d:
                _seen.add(m_)
                _pl_hop[m_] = side_to(m_, v)
                _q.append(m_)
CMAP_W = []
for n in range(CS * CS):
    kd, q = canon(SIDES[n])
    yaw = (1024 - 256 * q) & 1023
    w = sum(s << (2 * k) for k, s in enumerate(SIDES[n]))
    hop = side_to(n, _cp[n]) if _cp[n] >= 0 else 0
    CMAP_W.append(w | yaw << 8 | KINDS.index(kd) << 18 | CITY.district[n] << 23 | hop << 27
                  | _pl_hop[n] << 29)
# START: the dead end at one end of the longest street, facing out of it
_sx, _sy = CITY.xy(CITY.start)
START_X = int(round(-(_sy * TILE - OYA) * ONE))
START_Z = int(round((_sx * TILE - OXA) * ONE))
_sk = next(k for k in range(4) if SIDES[CITY.start][k])
_fdx, _fdy, _ = city.DIRS[_sk]
START_YAW = int(round(np.arctan2(_fdy, _fdx) * 1024 / (2 * np.pi))) & 1023   # forward (-sin, cos) = (-dy, dx)
# THE GATES: the streets on the route where one district gives on to the
# next. Shut, a gate is a street whose map bits read CLOSED: the piece still
# shows the street, but the arena stops him at it and the walk draws nothing
# past it -- the gate's own wall stands there instead. Clearing district
# k - 1 opens gate k (its bits OR'd back in).
GATES = sorted((k, e) for e, k in CITY.gates.items())
NDIST = CITY.districts()
GT_W = []
for k, (a, b) in GATES:
    sa, sb = side_to(a, b), side_to(b, a)
    if CITY.district[a] > CITY.district[b]:
        a, b, sa, sb = b, a, sb, sa
    CMAP_W[a] &= ~(3 << 2 * sa)
    CMAP_W[b] &= ~(3 << 2 * sb)
    (ia, ja), (ib, jb) = CITY.xy(a), CITY.xy(b)
    # (standing where the street stops: just past the near junction -- a
    # shut side ends the street at the junction, not at the tile's edge)
    gax = ia * TILE - OXA + (ib - ia) * (FAC + 0.3)
    gay = ja * TILE - OYA + (jb - ja) * (FAC + 0.3)
    GT_W += [a, 1 << 2 * sa, b, 1 << 2 * sb, int(round(-gay * ONE)), int(round(gax * ONE)),
             0 if ia == ib else 256]
if L5:
    # P38: THE DOORS -- the gates (a key each) and the back doors (a bolt,
    # on side a). Each has a place to stand on either side: the wall is
    # drawn on HIS side of it, and a gate opens from either.
    def _node_xz(n_):
        """the zeta point of a node's centre"""
        i_, j_ = CITY.xy(n_)
        return int(round(-(j_ * TILE - OYA) * ONE)), int(round((i_ * TILE - OXA) * ONE))

    def _stand(a_, b_):
        """where the street from a to b stops while it is shut"""
        (ia_, ja_), (ib_, jb_) = CITY.xy(a_), CITY.xy(b_)
        gx_ = ia_ * TILE - OXA + (ib_ - ia_) * (FAC + 0.3)
        gy_ = ja_ * TILE - OYA + (jb_ - ja_) * (FAC + 0.3)
        return int(round(-gy_ * ONE)), int(round(gx_ * ONE))
    DOORS = []
    for k, (a, b) in GATES:
        if CITY.district[a] > CITY.district[b]:
            a, b = b, a
        DOORS.append(dict(a=a, b=b, kind=0, key=k - 1))
    for a, b in WORLD.back:                       # (deep, near): the bolt is on a's side
        CMAP_W[a] &= ~(3 << 2 * side_to(a, b))
        CMAP_W[b] &= ~(3 << 2 * side_to(b, a))
        DOORS.append(dict(a=a, b=b, kind=1, key=-1))
    for d_ in DOORS:
        d_.update(sa=side_to(d_["a"], d_["b"]), sb=side_to(d_["b"], d_["a"]),
                  pa=_stand(d_["a"], d_["b"]), pb=_stand(d_["b"], d_["a"]),
                  yaw=0 if CITY.xy(d_["a"])[0] == CITY.xy(d_["b"])[0] else 256)
    NGATE = len(GATES)
    KEYAT = [_node_xz(WORLD.keys[k]) for k, _ in GATES]          # key g opens gate g + 1
    BUNKS = [_node_xz(v_) for v_ in WORLD.bunkers]
    PACK_HOME = _node_xz(WORLD.hard[0][0]) if WORLD.hard else _node_xz(CITY.core)
XR = 0
if L7:
    # P40: THE BUNKER IS A DOOR AND ROOMS (the player, of layer 6's hatch in
    # the road: "the bunkers were more of doors against a building, and an
    # actual room you enter, in there we can have training rooms with the
    # items as objects you can practice melee and gunplay ... the hub room
    # hold a desk with the map and inventory management. the prep table").
    # The rooms are NODES OF THE MAP like any other -- three rows north of
    # the town, out of its reach -- so the street's own walk, walls, shots
    # and lens are the rooms' too:
    #     the HUB     its middle and two short arms: the prep table, the way out
    #     the RING    north of it, a whole tile: the six bodies, to fight
    #     the RANGE   east of it, a whole tile: items to shoot and strike
    # A room's word carries bit 31: all of its tile is floor (to ROOM_W from
    # its walls), where a street's is a junction and its arms. One set of
    # rooms serves every bunker: a bunker's door is the way in, and the way
    # out is back to the door he came by.
    XR = 3
    HUB_N, RING_N, RANGE_N = 7 + 17 * CS, 7 + 18 * CS, 8 + 17 * CS
    ROOM_W = HT - 0.6
    _ik = len(KINDS)                               # the rooms' pieces follow the town's
    CMAP_W += [0] * (XR * CS)
    CMAP_W[HUB_N] = ARMS | ARMS << 2 | _ik << 18 | 15 << 23
    CMAP_W[RING_N] = ARMS << 4 | (_ik + 1) << 18 | 15 << 23 | 1 << 31
    CMAP_W[RANGE_N] = ARMS << 6 | (_ik + 2) << 18 | 15 << 23 | 1 << 31

    def _room_xz(n_, x_=0.0, y_=0.0):
        """the zeta point of (x east, y north) from a node's centre"""
        cx_, cz_ = n_ % CS * TILE - OXA, -((n_ // CS) * TILE - OYA)
        return int(round((cz_ - y_) * ONE)), int(round((cx_ + x_) * ONE))
    YAW_OF = (256, 0, 768, 512)                    # his heading toward a side: N E S W
    DOOR_IN = FAC - 0.25                           # a door stands this far from the node's middle
    # THE WAYS IN AND THE WAY OUT: each bunker's door, on a closed wall of
    # its dead end (the one facing its street, if that is closed); and the
    # hub's, on its south wall. (place, the door's turn, and where and how
    # he stands having come through it the other way)
    TDOORS = []
    for b_, v_ in enumerate(WORLD.bunkers):
        k_ = next(k for k in range(4) if SIDES[v_][k] != CLOSED and
                  (v_ + CSTEP[k]) in ([_tpar[v_]] + _tkids[v_]))
        c_ = (k_ + 2) % 4 if SIDES[v_][(k_ + 2) % 4] == CLOSED else next(k for k in range(4) if SIDES[v_][k] == CLOSED)
        dx_, dy_, _ = city.DIRS[c_]
        # (the door's mesh faces north unturned; it is turned to face INTO the
        # node, and seen from that side only: the lens, backed through the
        # wall behind him, must not find it)
        TDOORS.append(dict(at=_room_xz(v_, dx_ * DOOR_IN, dy_ * DOOR_IN), yaw=(512, 256, 0, 768)[c_],
                           out=_room_xz(v_, dx_ * (DOOR_IN - 2.0), dy_ * (DOOR_IN - 2.0)), out_yaw=YAW_OF[(c_ + 2) % 4],
                           know=(1 << CITY.district[v_]) | (1 << min(CITY.district[v_] + 1, NDIST - 1)), node=v_))
    TDOORS.append(dict(at=_room_xz(HUB_N, 0, -DOOR_IN), yaw=0, out=_room_xz(HUB_N, 0, -DOOR_IN + 2.0), out_yaw=YAW_OF[0]))
    DESK_XZ = _room_xz(HUB_N, -3.3, 0.0)
    RING_XZ = _room_xz(RING_N)
    # THE RANGE'S ITEMS: keys that are never taken -- they ring and leap for
    # a round or a fist, and are the lock's target, as the street's are
    NKEYS = len(KEYAT)
    KEYAT += [_room_xz(RANGE_N, 5.6, 4.6), _room_xz(RANGE_N, 6.4, -0.4), _room_xz(RANGE_N, 2.0, -5.2)]

    def _cart_piece(b_, name_):
        """a Build as a mesh in the cart (frontier 20): its descriptor's place in data memory"""
        sh_ = 5
        v16_ = [(int(c_) + (1 << sh_ >> 1)) >> sh_ for v_ in b_.v for c_ in v_]
        assert len(b_.v) <= spec.MESH_NV_MAX and len(b_.f) <= spec.MESH_NF_MAX, (name_, len(b_.v), len(b_.f))
        assert max(abs(c_) for c_ in v16_) < 32768
        vw_ = _halves16(v16_)
        cw_ = _halves16([(c_ >> 19 & 31) << 10 | (c_ >> 11 & 31) << 5 | (c_ >> 3 & 31) for *_, c_ in b_.f])
        bank_ = int(cart.cram(Table(vw_ + cw_), name_))
        fs_ = int(cart.cram(Table([a_ | bb_ << 10 | c_ << 20 for a_, bb_, c_, _ in b_.f]), name_ + "_faces"))
        return int(cart.data(Table([len(b_.v) | len(b_.f) << 16, bank_, fs_, bank_ + len(vw_), sh_]), name_ + "_desc"))
    _WALL, _BAND, _FLOOR, _CEIL = (84, 100, 98), (40, 150, 84), (40, 44, 46), (26, 30, 30)
    ROOM_H = 4.6

    def _wall(b_, x0_, y0_, x1_, y1_, n_, h_=ROOM_H, cuts_=1):
        """a wall from (x0, y0) to (x1, y1) facing n_: concrete, a green band at the hand's height"""
        for z0_, z1_, c_ in ((0.0, 1.1, _WALL), (1.1, 1.35, _BAND), (1.35, h_, _WALL)):
            b_.quad([(x0_, y0_, z0_), (x1_, y1_, z0_), (x1_, y1_, z1_), (x0_, y0_, z1_)], n_, c_, cuts_, 1)

    def _floor_ceiling(b_, x0_, x1_, y0_, y1_, h_=ROOM_H, col_=_FLOOR, cuts_=1, out_=(0, 0, 0, 0)):
        """(out_: how far the FLOOR runs on past the west, east, south and
        north walls -- with his back to a wall the lens stands outside the
        room, and looked in over a strip of the street's black ground)"""
        fx0_, fx1_, fy0_, fy1_ = x0_ - out_[0], x1_ + out_[1], y0_ - out_[2], y1_ + out_[3]
        b_.quad([(fx0_, fy0_, 0.03), (fx1_, fy0_, 0.03), (fx1_, fy1_, 0.03), (fx0_, fy1_, 0.03)], (0, 0, 1), col_, cuts_, cuts_)
        b_.quad([(x0_, y0_, h_), (x1_, y0_, h_), (x1_, y1_, h_), (x0_, y1_, h_)], (0, 0, -1), _CEIL, cuts_, cuts_)
    # the hub: its middle (FAC each way), an arm north to the ring and one east to the range
    _hb2 = Build()
    _wall(_hb2, -FAC, -FAC, FAC, -FAC, (0, 1, 0), cuts_=2)            # south, where the way out is
    _wall(_hb2, -FAC, -FAC, -FAC, HT, (1, 0, 0), cuts_=3)             # west, the prep table's
    _wall(_hb2, FAC, FAC, FAC, HT, (-1, 0, 0))                        # the north arm's east side
    _wall(_hb2, FAC, FAC, HT, FAC, (0, -1, 0))                        # the east arm's north side
    _wall(_hb2, FAC, -FAC, HT, -FAC, (0, 1, 0))                       # ...and its south
    _floor_ceiling(_hb2, -FAC, FAC, -FAC, FAC, cuts_=2, out_=(3.6, 0, 3.6, 0))
    _floor_ceiling(_hb2, -FAC, FAC, FAC, HT)
    _floor_ceiling(_hb2, FAC, HT, -FAC, FAC)
    # THE PREP TABLE, against the west wall: the map on it (the town's own red and black), its lamp
    _hb2.box(-FAC + 0.1, -FAC + 1.5, -1.5, 1.5, 0.0, 0.95, (70, 48, 34))
    _hb2.quad([(-FAC + 0.3, -1.0, 0.97), (-FAC + 1.3, -1.0, 0.97), (-FAC + 1.3, 0.4, 0.97), (-FAC + 0.3, 0.4, 0.97)],
              (0, 0, 1), (150, 34, 28), 2, 2)
    _hb2.box(-FAC + 0.4, -FAC + 0.7, 0.9, 1.2, 0.95, 1.5, (236, 196, 64))
    # the ring: a whole tile, its doorway south; a black and white floor to stand a fight on
    _rg = Build()
    _wall(_rg, -HT, -HT, -HT, HT, (1, 0, 0), 5.6, 4)
    _wall(_rg, HT, -HT, HT, HT, (-1, 0, 0), 5.6, 4)
    _wall(_rg, -HT, HT, HT, HT, (0, -1, 0), 5.6, 4)
    _wall(_rg, -HT, -HT, -FAC, -HT, (0, 1, 0), 5.6)
    _wall(_rg, FAC, -HT, HT, -HT, (0, 1, 0), 5.6)
    _floor_ceiling(_rg, -HT, HT, -HT, HT, 5.6, cuts_=4, out_=(3.6, 3.6, 0, 3.6))
    for i_ in range(4):
        for j_ in range(4):
            _rg.quad([(-4 + 2 * i_, -4 + 2 * j_, 0.06), (-2 + 2 * i_, -4 + 2 * j_, 0.06), (-2 + 2 * i_, -2 + 2 * j_, 0.06),
                      (-4 + 2 * i_, -2 + 2 * j_, 0.06)], (0, 0, 1), (200, 196, 186) if (i_ + j_) % 2 == 0 else (22, 20, 22))
    # the range: a whole tile, its doorway west; yellow lines down it, a red wall behind the items
    _rn = Build()
    _wall(_rn, -HT, HT, HT, HT, (0, -1, 0), 5.6, 4)
    _wall(_rn, -HT, -HT, HT, -HT, (0, 1, 0), 5.6, 4)
    _wall(_rn, -HT, FAC, -HT, HT, (1, 0, 0), 5.6)
    _wall(_rn, -HT, -HT, -HT, -FAC, (1, 0, 0), 5.6)
    for z0_, z1_, c_ in ((0.0, 2.8, (150, 34, 28)), (2.8, 5.6, _WALL)):
        _rn.quad([(HT, -HT, z0_), (HT, HT, z0_), (HT, HT, z1_), (HT, -HT, z1_)], (-1, 0, 0), c_, 4, 1)
    _floor_ceiling(_rn, -HT, HT, -HT, HT, 5.6, cuts_=4, out_=(0, 3.6, 3.6, 3.6))
    for y_ in (-2.6, 2.6):
        _rn.quad([(-HT + 1, y_ - 0.08, 0.06), (HT - 1, y_ - 0.08, 0.06), (HT - 1, y_ + 0.08, 0.06), (-HT + 1, y_ + 0.08, 0.06)],
                 (0, 0, 1), (236, 196, 64), 4, 1)
    PIECE_M += [_cart_piece(_hb2, "room_hub"), _cart_piece(_rg, "room_ring"), _cart_piece(_rn, "room_range")]
    PFLAG_T = cart.data(Table([spec.OBJ_CULL | spec.OBJ_LIT] * _ik + [spec.OBJ_CULL | spec.OBJ_CART] * 3), "piece_flags")
    _td = Build()                  # a bunker's door: steel in a dark frame, a green lamp over it
    _td.quad([(-1.9, 0, 0.0), (1.9, 0, 0.0), (1.9, 0, 3.5), (-1.9, 0, 3.5)], (0, 1, 0), (26, 26, 30))
    _td.quad([(-1.4, 0.06, 0.0), (1.4, 0.06, 0.0), (1.4, 0.06, 3.0), (-1.4, 0.06, 3.0)], (0, 1, 0), (96, 110, 104))
    _td.quad([(-1.4, 0.09, 1.3), (1.4, 0.09, 1.3), (1.4, 0.09, 1.6), (-1.4, 0.09, 1.6)], (0, 1, 0), (40, 170, 90))
    _td.quad([(-0.3, 0.09, 3.1), (0.3, 0.09, 3.1), (0.3, 0.09, 3.4), (-0.3, 0.09, 3.4)], (0, 1, 0), (90, 255, 150))
    TDOOR_M = int(cart.data(_td.mesh(), "bunker_door"))
    KNOW_T = cart.data(Table([d_["know"] for d_ in TDOORS[:-1]]), "bunker_know")
    BUNKN_T = cart.data(Table([d_["node"] for d_ in TDOORS[:-1]]), "bunker_node")
GT_N = 7
CMAP = cart.data(Table(CMAP_W), "city_map")
GATE_T = cart.data(Table(GT_W or [0]), "gates")
_gb = Build()                      # the gate: a wall of bars across the street,
for i in range(7):                 # red and black, seen from both sides
    x0, x1 = -FAC + 2 * FAC * i / 7, -FAC + 2 * FAC * (i + 1) / 7
    col = (190, 28, 24) if i % 2 == 0 else (14, 10, 12)
    _gb.quad([(x0, 0, 0.0), (x1, 0, 0.0), (x1, 0, 11), (x0, 0, 11)], (0, 1, 0), col)
                                   # (one side: the gate is drawn unculled)
GATE_M = int(cart.data(_gb.mesh(), "gate"))
if L5:
    DOOR_T = cart.data(Table([w_ for d_ in DOORS for w_ in (d_["a"], 1 << 2 * d_["sa"], d_["b"], 1 << 2 * d_["sb"])]),
                       "doors")
    # the way-finder's word a node: its place in the tree's walk (in, out),
    # the side its parent lies through, and which sides lead to children
    _tw = []
    for v_ in range(CS * CS):
        pd_ = CSTEP.index(_tpar[v_] - v_) if _tpar[v_] >= 0 else 0
        km_ = sum(1 << CSTEP.index(m_ - v_) for m_ in _tkids[v_])
        _tw.append(_tin[v_] | _tout[v_] << 8 | pd_ << 16 | km_ << 18)
    TREE_T = cart.data(Table(_tw), "way_tree")
    _bb = Build()                  # the back door: the gate's bars in bone and black
    for i in range(7):
        x0, x1 = -FAC + 2 * FAC * i / 7, -FAC + 2 * FAC * (i + 1) / 7
        _bb.quad([(x0, 0, 0.0), (x1, 0, 0.0), (x1, 0, 11), (x0, 0, 11)], (0, 1, 0),
                 (214, 206, 190) if i % 2 == 0 else (14, 10, 12))
    BOLT_M = int(cart.data(_bb.mesh(), "bolt"))
    _hb = Build()                  # the bunker: a hatch in the road, green and black, and its lamp
    for i in range(2):             # (archive axes: x, y across the ground, z up)
        for j in range(2):
            x0, y0 = -1.2 + 1.2 * i, -1.2 + 1.2 * j
            _hb.quad([(x0, y0, 0.08), (x0 + 1.2, y0, 0.08), (x0 + 1.2, y0 + 1.2, 0.08), (x0, y0 + 1.2, 0.08)],
                     (0, 0, 1), (40, 170, 90) if (i + j) % 2 == 0 else (14, 10, 12))
    for (x0, y0, x1, y1) in ((1.5, 1.44, 1.62, 1.44), (1.62, 1.44, 1.62, 1.56), (1.62, 1.56, 1.5, 1.56),
                             (1.5, 1.56, 1.5, 1.44)):
        _hb.quad([(x0, y0, 0.0), (x1, y1, 0.0), (x1, y1, 3.0), (x0, y0, 3.0)], (0, 1, 0), (40, 36, 40))
        _hb.quad([(x0 * 1.1 - 0.156, y0 * 1.6 - 0.9, 3.0), (x1 * 1.1 - 0.156, y1 * 1.6 - 0.9, 3.0),
                  (x1 * 1.1 - 0.156, y1 * 1.6 - 0.9, 3.5), (x0 * 1.1 - 0.156, y0 * 1.6 - 0.9, 3.5)], (0, 1, 0),
                 (90, 255, 150))
    BUNK_M = int(cart.data(_hb.mesh(), "bunker"))
if L6:
    # P39: THE MAP (docs/TND-WORLD.md, step 3). The town from above, as
    # GEOMETRY read from the cart (frontier 20: a mesh in the cart costs
    # the data memory five words): a quad a street, a square a plaza, in
    # the colour of the sector's danger -- cut by SECTOR, sixty streets a
    # mesh at most, so a sector he does not know is simply not listed. It
    # stands upright before a lens at the world's origin: a node is a
    # quarter of a unit, north is up.
    MAP_S, MAP_HW, MAP_Z = 0.25, 0.034, 4.4
    MAP_ZQ = int(MAP_Z * ONE)

    def _map_xy(n_):
        i_, j_ = CITY.xy(n_)
        return (i_ - (CS - 1) / 2) * MAP_S, (j_ - (CS - 1) / 2) * MAP_S

    def _map_q(v_):
        return int(round(v_ * ONE))

    def _heat(d_):
        t_ = d_ / (city.LEVELS - 1)
        return (int(140 + 110 * t_), int(60 + 110 * t_ * t_), int(72 + 110 * t_ ** 3))
    _extra = {tuple(sorted(e_)) for e_ in WORLD.back + WORLD.hard}
    _sec_quads = {}
    for u_ in range(CS * CS):
        for m_ in CITY.adj[u_]:
            if m_ > u_ and (u_, m_) not in _extra:
                (x0_, y0_), (x1_, y1_) = _map_xy(u_), _map_xy(m_)
                _sec_quads.setdefault(min(CITY.district[u_], CITY.district[m_]), []).append(
                    (min(x0_, x1_) - MAP_HW, min(y0_, y1_) - MAP_HW, max(x0_, x1_) + MAP_HW, max(y0_, y1_) + MAP_HW,
                     _heat(max(CITY.danger[u_], CITY.danger[m_]))))
    for (px_, py_) in CITY.plazas:
        n0_ = px_ + py_ * CS
        (x0_, y0_), (x1_, y1_) = _map_xy(n0_), _map_xy(n0_ + 1 + CS)
        _sec_quads.setdefault(CITY.district[n0_], []).append(
            (x0_ - 2 * MAP_HW, y0_ - 2 * MAP_HW, x1_ + 2 * MAP_HW, y1_ + 2 * MAP_HW, _heat(CITY.danger[n0_])))
    MAPS = []                              # (sector, the descriptor's place in data memory)
    for sec_ in sorted(_sec_quads):
        qs_ = _sec_quads[sec_]
        for c0_ in range(0, len(qs_), 60):
            v16_, tri_, col_ = [], [], []
            for (x0_, y0_, x1_, y1_, rgb_) in qs_[c0_:c0_ + 60]:
                b_ = len(v16_) // 3
                for (x_, y_) in ((x0_, y0_), (x1_, y0_), (x1_, y1_), (x0_, y1_)):
                    v16_ += [int(round(x_ * ONE)) >> CM_SHIFT, int(round(y_ * ONE)) >> CM_SHIFT, 0]
                tri_ += [(b_, b_ + 1, b_ + 2), (b_, b_ + 2, b_ + 3)]
                col_ += [(rgb_[0] >> 3) << 10 | (rgb_[1] >> 3) << 5 | rgb_[2] >> 3] * 2
            assert len(v16_) // 3 <= spec.MESH_NV_MAX and max(abs(v_) for v_ in v16_) < 32768
            vw_, cw_ = _halves16(v16_), _halves16(col_)
            bank_ = int(cart.cram(Table(vw_ + cw_), f"map{len(MAPS)}"))
            fs_ = int(cart.cram(Table([a_ | b_ << 10 | c_ << 20 for a_, b_, c_ in tri_]), f"map{len(MAPS)}_faces"))
            MAPS.append((sec_, int(cart.data(Table([len(v16_) // 3 | len(tri_) << 16, bank_, fs_, bank_ + len(vw_), CM_SHIFT]),
                                             f"map{len(MAPS)}_desc"))))

    def _marker(name_, quads_):
        """a little flat mesh in the map's plane: (x0, y0, x1, y1, colour) each, or four corners and a colour"""
        v_, f_ = [], []
        for q_ in quads_:
            pts_ = q_[0] if len(q_) == 2 else ((q_[0], q_[1]), (q_[2], q_[1]), (q_[2], q_[3]), (q_[0], q_[3]))
            b_ = len(v_) // 3
            for (x_, y_) in pts_:
                v_ += [_map_q(x_), _map_q(y_), 0]
            f_ += [(b_, b_ + 1, b_ + 2, rgb(q_[-1])), (b_, b_ + 2, b_ + 3, rgb(q_[-1]))]
        return int(cart.data(Mesh(v_, f_), name_))

    def _diamond(r_, c_):
        return (((0, r_), (r_, 0), (0, -r_), (-r_, 0)), c_)
    _g, _y, _w = (60, 220, 120), (236, 196, 64), (240, 236, 224)
    MK = dict(
        key=_marker("mk_key", [_diamond(0.075, _y)]),
        gate=_marker("mk_gate", [(-0.06, -0.06, 0.06, 0.06, (220, 36, 30))]),
        bunker=_marker("mk_bunker", [(-0.085, -0.085, 0.085, 0.085, (20, 60, 34)), (-0.06, -0.06, 0.06, 0.06, _g)]),
        core=_marker("mk_core", [_diamond(0.13, (255, 244, 170)), (-0.06, -0.06, 0.06, 0.06, (255, 255, 255))]),
        you=_marker("mk_you", [_diamond(0.10, (20, 16, 18)), _diamond(0.07, _w)]),
        cursor=_marker("mk_cursor", [(-0.12, 0.09, 0.12, 0.12, _y), (-0.12, -0.12, 0.12, -0.09, _y),
                                     (-0.12, -0.09, -0.09, 0.09, _y), (0.09, -0.09, 0.12, 0.09, _y)]),
        hard_h=_marker("mk_hard_h", [(-MAP_S / 2, -0.03, MAP_S / 2, 0.03, _w)]),
        hard_v=_marker("mk_hard_v", [(-0.03, -MAP_S / 2, 0.03, MAP_S / 2, _w)]),
        shut_h=_marker("mk_shut_h", [(-MAP_S / 2, -0.03, MAP_S / 2, 0.03, (70, 130, 240)), (-0.02, -0.07, 0.02, 0.07, _w)]),
        shut_v=_marker("mk_shut_v", [(-0.03, -MAP_S / 2, 0.03, MAP_S / 2, (70, 130, 240)), (-0.07, -0.02, 0.07, 0.02, _w)]),
        open_h=_marker("mk_open_h", [(-MAP_S / 2, -0.03, MAP_S / 2, 0.03, (70, 130, 240))]),
        open_v=_marker("mk_open_v", [(-0.03, -MAP_S / 2, 0.03, MAP_S / 2, (70, 130, 240))]))
    # (a waymark: as many pips as its place in the plan, over the node)
    WMK = [_marker(f"mk_way{k_}", [(-0.045 * (k_ + 1) + 0.09 * i_ + 0.012, 0.10, -0.045 * (k_ + 1) + 0.09 * i_ + 0.078, 0.166,
                                    (255, 120, 40)) for i_ in range(k_ + 1)]) for k_ in range(4)]
    SBIT = cart.data(Table([1 << k_ for k_ in range(16)]), "sector_bit")
if BASE:
    # P21: A KEY A DISTRICT, in the middle of its plaza -- found, picked up
    # with the jab, and carried to the district's gate, which the jab then
    # unlocks. (In the layers above, something will be holding it.)
    KEYPOS = cart.data(Table([c for (kx_, ky_) in CITY.plazas[:NDIST] for c in (
        int(round(-(ky_ * TILE + HT - OYA) * ONE)), int(round((kx_ * TILE + HT - OXA) * ONE)))]),
        "keypos")
    _kb = Build()
    _kv = [np.array(v_) for v_ in ((0.26, 0, 0), (-0.26, 0, 0), (0, 0, 0.26), (0, 0, -0.26),
                                   (0, 0.42, 0), (0, -0.42, 0))]      # (zeta: y up)
    for a_, b_, c_ in ((0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)):
        t_ = [_kv[a_], _kv[b_], _kv[c_]]
        ids = [_kb.vert(v_) for v_ in t_]
        n_ = np.cross(t_[1] - t_[0], t_[2] - t_[0])
        if np.dot(n_, sum(t_)) < 0:
            ids = [ids[0], ids[2], ids[1]]
        k_ = 0.62 + 0.38 * (len(_kb.f) % 4) / 3
        _kb.f.append((*ids, rgb((int(240 * k_), int(196 * k_), int(60 * k_)))))
    KEY_M = int(cart.data(_kb.mesh(), "key"))
# THE DISTRICTS' DUSK -- the opus, toward the core: black, white, yellow,
# red (nigredo, albedo, citrinitas, rubedo). The fog takes the colour of
# the district he stands in.
_opus = [(0x4C, 0x1C, 0x2A), (0x6A, 0x24, 0x20), (0x76, 0x2E, 0x14), (0x8E, 0x16, 0x0C)]
# (P20b: the opus kept, sunk into the crossroads' blood -- 0x6A2420 is the
# second -- a haze a little LIGHTER than the soot walls, so it reads as
# fog the street dissolves into, not as the dark)
# (black is a bruise, not black: a black dusk sank every wall into the
# sky -- measured on the first city frames, against the old 0x6A2420)


def _dusk(d):
    t = d / max(1, NDIST - 1) * (len(_opus) - 1)
    k = min(int(t), len(_opus) - 2)
    f = t - k
    c = [round(a + (b - a) * f) for a, b in zip(_opus[k], _opus[k + 1])]
    return c[0] << 16 | c[1] << 8 | c[2]


DUSK = cart.data(Table([_dusk(d) for d in range(15)] + [0x141A18 if L7 else _dusk(15)]), "dusk")   # (15: the bunker's rooms)
_aw = []                           # the pointer's eight ways, then none: a
for k in range(8):                 # triangle a way, at the top of the screen
    th = k * np.pi / 4             # (0 ahead, clockwise; screen y is down)
    ux, uy = np.sin(th), -np.cos(th)
    cx_, cy_ = 160, 40
    pts = [(cx_ + 10 * ux, cy_ + 10 * uy), (cx_ - 5 * ux + 6 * uy, cy_ - 5 * uy - 6 * ux),
           (cx_ - 5 * ux - 6 * uy, cy_ - 5 * uy + 6 * ux)]
    _aw += [int(round(c)) for pt in pts for c in pt] + [0xE8C040]
_aw += [0] * spec.DL_STRIDE
ARROWS = cart.data(Table(_aw), "arrows")
if L5:
    PIPS = cart.data(Table([c_ for g_ in range(len(GATES)) for c_ in (
        10 + 12 * g_, 22, 17 + 12 * g_, 28, 10 + 12 * g_, 34, 0xE8C040)]), "key_pips")
if L6:
    MAPICON = cart.data(Table([10, 42, 24, 42, 24, 56, 0x3CDC78, 10, 42, 24, 56, 10, 56, 0x3CDC78]), "map_icon")
CT_MAX = 12                     # pieces a frame, at most
FOG_FROM, FOG_FULL = 2.0, 34.0   # P20b: a HEAVY haze, from his heels to two nodes on
PIECE_CY, PIECE_R = 6.5, 13.5   # a piece's bounding sphere: centre height, radius
PIECE_T = cart.data(Table(PIECE_M), "pieces")

CT = {k: cart.var("ct_" + k) for k in ("n", "x", "z", "w", "c", "k", "n1", "w1", "bk")}
CTLIST = cart.var("ct_list", CT_MAX)


def city_node(g, xcell, zcell):
    """( -- ) CT n, CT w for the zeta point (xcell, zcell): -1 off the map"""
    off = g.label("cnoff")
    g.load(zcell).push32(int((OXA + HT) * ONE)).emit("add")        # u = ax
    g.emit("dup").push(0).emit("lt", f"jz {off}_a", "drop", f"jmp {off}")
    g.mark(f"{off}_a")
    g.emit("dup").push32(int(CS * TILE * ONE)).emit("lt", f"jz {off}_b")
    g.emit(f"shr {TSH}")
    g.push32(int((OYA + HT) * ONE)).load(xcell).emit("sub")         # v = ay
    g.emit("dup").push(0).emit("lt", f"jz {off}_c", "drop", "drop", f"jmp {off}")
    g.mark(f"{off}_c")
    g.emit("dup").push32(int((CS + XR) * TILE * ONE)).emit("lt", f"jz {off}_d")     # (P40: and the rooms' rows)
    g.emit(f"shr {TSH}", "shl 4", "add", "dup").store(CT["n"])
    g.push(int(CMAP)).emit("add", "loadi").store(CT["w"])
    g.emit(f"jmp {off}_e")
    g.mark(f"{off}_d")
    g.emit("drop")
    g.mark(f"{off}_b")
    g.emit("drop")
    g.mark(off)
    g.set(CT["n"], -1)
    g.mark(f"{off}_e")




# 0.2 BELOW the street: everything that stands on the ground (paint at
# 0.04, curbs, feet) must read nearer than the ground at the same pixel,
# and a long face's interpolated depth over-reads -- so the ground is
# lowered until it always loses, at a cost of under a sixteenth of fog.
GROUND_Y = -0.6                  # (P20b: was -0.2; the near rings read true depth now)
G_NEAR = 4.0


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
    # (P20b: the haze starts at 2 now, so the near triangle stops at 4 and
    # rings carry the fog's true depth from there -- one triangle to 15 drew
    # a step in the fog where it met the rings)
    w4 = (G_NEAR - 1.0) * 3.0 / (2.93 - 1.0)
    l4, r4 = v(-w4, G_NEAR), v(w4, G_NEAR)
    tri(apex, l4, r4)
    rings = (G_NEAR, 7.0, 11.0, 15.0, 20.0, 27.0, 36.0, 60.0)   # past the fog (34)
    prev = (l4, r4)
    for z in rings[1:]:
        cur = (v(-half(z), z), v(half(z), z))
        tri(prev[0], prev[1], cur[1])
        tri(prev[0], cur[1], cur[0])
        prev = cur
    if BASE:                                  # (P22: lit, at the town's own dark)
        g_ = 32 / LIT_AMB0
        lc = rgb(tuple(min(255, int(c_ * g_)) for c_ in shade(ASPHALT, (0, 0, 1))))
        return Mesh([int(round(c * ONE)) for p_ in V for c in p_],
                    [(a_, b_, c_, lc) for a_, b_, c_, _ in F], colors=[0] * len(V))
    return Mesh([int(round(c * ONE)) for p_ in V for c in p_], F)


GROUND_M = int(cart.data(ground_mesh(), "ground"))
if BASE:
    # P21b: THE SKY IS THE HAZE (the player: "the skybox the black rn to be
    # the deepest color of the fog"). The frame clears to CLEAR_RGB, a
    # constant of the machine; but a face past the fog's far end IS the fog's
    # colour, whatever the district's. So the sky is one triangle riding the
    # camera like the ground, 60 out: wide enough that the screen's clip of
    # it is wholly covered (its box walks 1x), and behind everything.
    SKY_M = int(cart.data(Mesh([int(round(c * ONE)) for v_ in (
        (-120.0, -2.0, 60.0), (120.0, -2.0, 60.0), (0.0, 60.0, 60.0)) for c in v_],
        [(0, 2, 1, 0)]), "sky"))
    # P21b: HIS SHADOW (OBJ_BLEND's first use here): a dark blot under him,
    # half through, so his weight sits on the street -- and one under the key
    _sv = [(0.0, 0.01, 0.0)] + [(0.36 * np.cos(a_), 0.01, 0.27 * np.sin(a_))
                                for a_ in np.arange(8) * np.pi / 4]
    SHADOW_M = int(cart.data(Mesh([int(round(c * ONE)) for v_ in _sv for c in v_],
                                  [(0, 1 + (k + 1) % 8, 1 + k, 6 << spec.BLEND_A_SHIFT)
                                   for k in range(8)]), "shadow"))

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
# P15: THE SPARK (tear.py 3218, the impact burst). Where a fist lands, for
# six frames: a white-hot tetrahedron drawn twice, tumbling against itself
# -- the archive's burst grows through twelve sizes, and an object on this
# machine cannot be scaled, so this one turns instead. Its cells: where,
# and how many frames are left.
# (P29: in shadow boxing the spark marks WHERE THE FIST LANDED -- a point, so small)
SPARK_M = int(cart.data(tetra_mesh(0.09 if L2 else 0.20, (255, 244, 214)), "spark_m"))
SPARK_FOR = 6
SPK = cart.var("spark", 4)
if L2:
    # P34: THE GUN'S LINE, SEEN. The sight is a row of red beads from him to
    # where the shot will land -- as many beads as rounds in the gun -- and a
    # red point ON that place (white-hot when the shot is charged). The
    # bullet is a streak a unit and a half long, lying along its way.
    GUN_RANGE = 13.0                # (the archive's reach for a shot)
    BULLET_V = int(2.0 * ONE)       # a frame of the fight: a street crossed in five
    RELOAD = 24                     # frames the empty gun takes to be full again
    GUN_Y = int(0.95 * ONE)         # the gun's height (his hand's, in the clip)...
    GUN_F, GUN_R = int(0.5 * ONE), int(0.14 * ONE)   # ...and its place: ahead of him, to his right
    AIM_LINGER = 24                 # frames the aim's lens stays after the shot (to see it land)
    KEY_R = int(0.45 * ONE)         # the key, as a thing a shot can meet
    SHOT_W = int((FAC - 0.05) * ONE)   # a shot stops at the wall's face
    DRAW_MAX = 9                    # (the charged shot's start: it is let go a frame before)
    BEAD_M = int(cart.data(tetra_mesh(0.05, (255, 48, 36)), "bead_m"))
    DOT_M = int(cart.data(tetra_mesh(0.16, (255, 48, 36)), "dot_m"))
    HOT_M = int(cart.data(tetra_mesh(0.22, (255, 244, 214)), "hot_m"))   # (and where a bullet lands)
    SPKM = cart.data(Table([SPARK_M]), "spark_mesh")   # which spark: a fist's point, a bullet's burst
    BK = {k: i for i, k in enumerate(("ex", "ez", "dx", "dz", "rem", "y", "yaw", "hit"))}
    _bl, _br = 0.75, 0.035
    _bv = [(0, 0, 2 * _bl), (0, 0, 0), (_br, 0, 0.4), (-0.5 * _br, 0.87 * _br, 0.4), (-0.5 * _br, -0.87 * _br, 0.4)]
    BULLET_M = int(cart.data(Mesh([int(round(c * ONE)) for v in _bv for c in v],
                                  [(e, a, b, rgb((255, 236 - 40 * (k % 2), 150)))
                                   for e in (0, 1) for k, (a, b) in enumerate(((2, 3), (3, 4), (4, 2)))]),
                             "bullet_m"))
    INVN = cart.data(Table([int(round(ONE / (n + 1))) for n in range(13)]), "inv_n")
AWARE_LIFT = int(1.62 * ONE)

# ---- P6: THE TITLE -- the archive's own start screen, baked -----------------
# tools/tnd_title.py renders it with the archive itself at the panel's
# 320x288 (TEAR / NOT / DEMON in its gothic hand, the demonic Ns, the
# gash, the inverted cross, PRESS START; the menu cut to START, the one
# thing the port does). Here it is a BACKDROP PLATE: on the title the
# frame clears to it, nothing else is drawn, and the music keeps the
# archive's intro lock. ~136k clocks to read, on a screen with no fight.
_title = np.load(ROOT / "assets" / "tnd" / "title.npz")["img"].astype(np.int64)
TITLE = cart.cram(Plate([int(r >> 3) << 10 | int(g >> 3) << 5 | int(b >> 3)
                         for r, g, b in _title.reshape(-1, 3)],
                        [spec.ZFAR] * spec.BG_WORDS), "title")
MODE = cart.data(Table([0]), "mode")             # 0 the title, 1 the fight
TT = cart.data(Table([1500]), "title_t")   # boots at ATTRACT: the intro first

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
JUGGLE_PEAK = 2.0               # P18: a launched body's feet top out at a flip's peak
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
        # P18: THE JUGGLE'S HEIGHT is his jump's. The archive's 0.45 threw a
        # body seven units up, three times higher than any jump; a launcher
        # now peaks at JUGGLE_PEAK, where a flip (2.0) meets it chest-high
        if lift:
            lift = (2 * GRAV * JUGGLE_PEAK) ** 0.5
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
if L2:                          # P30: a jab gives way to the next blow; a terminator
    CANCELS = dict(CANCELS, lead_hook=0, rear_hook=0, lead_uppercut=0, rear_uppercut=0)   # is thrown, and ends


def _fist_path(k, n):
    """the fist's place on each active frame: the authored clip's own, where
    the layers play one (so the hit IS where the drawn fist is)"""
    if n in CLIP_OF and "P_" + CLIP_OF[n] in d.files:
        su, ac = int(DEM["p_moves"][k][0]), int(DEM["p_moves"][k][1])
        return d["P_" + CLIP_OF[n]][su:su + ac]
    return DEM["p_fist_" + n]


_pm, _pf, _pat = move_rows(DEM["p_moves"], [_fist_path(k, n) for k, n in enumerate(PMN)],
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
RING = [(slots[d * NF + DF["x"]], slots[d * NF + DF["z"]]) for d in range(3)]
# A NEW WAVE IS THIS, FETCHED (P15). The image was 78 words of DMEM read
# only when a wave stands up -- so it lives in the segment now, and the
# mover brings it: the one frame's request that would have carried his
# pose carries the wave instead (he holds a pose a frame, as every clip
# already does at 30 Hz). The 78 words went to the sounds below.
SPAWN = cart.cram(Table(slots), "spawn")
CUR = cart.var("cur", NF)                        # the demon being thought
SPN = cart.var("spn")                            # P19: demons sent, to place
WOKE = cart.var("woke")                          # P19: the district's horde is up
LEASH_FOG = int(FOG_FULL * ONE)                  # beyond this on an axis: unseen
# ---- P20b: THE SWARM (the player: "the hordes should be overwhelming") ------
# Three demons are all the object list holds (a demon is twelve objects of
# 64). The horde around them is LESSER: one object each, a hunched charred
# thing lurching out of the haze, as many as N_IMP, that rushes him, rings
# him and claws -- and falls to any blow (a fist cleaves through all it
# meets; a shot drops every one on its line). The fog hides how little
# they are: the PS1's own trick. They come while a district is awake, more
# the deeper the district, and drop where they stand when it is cleared.
N_IMP = 0 if BASE else 8                     # (the base has no swarm, and needs its room)
IMP_F = {k: i for i, k in enumerate(("x", "z", "ox", "oz", "st", "t", "yaw"))}
IMPS = cart.var("imps", max(1, N_IMP) * len(IMP_F))   # st 0 none, 1 up, 2 falling
IACT = cart.var("imp_act")                           # his blow is live this frame
IMP_BASE = cart.data(Table([8 if SWARM_TEST else 4]), "imp_base")   # the first district's
                                                     # swarm (one more a district)
IMP_SPD = int(0.072 * ONE)                           # a lurch: faster than his walk
IMP_NEAR2 = int(0.95 ** 2 * ONE)                     # close enough: it stops
IMP_CLAW2 = int(1.35 ** 2 * ONE)                     # in reach of its claws
IMP_REACH2 = int(1.15 ** 2 * ONE)                    # in reach of his fist
IMP_DMG, IMP_CD = 4, 46                              # a claw, and its wait
IMP_FALL = 26                                        # frames it takes to go down
IMP_RING = 1.1                                       # they ring him, not stack
IMP_SPREAD = [int(round(a * 1024 / 360)) & 1023 for a in (-16, 16, -48, 48, -80, 80, -112, 112)]
IMP_STYLE = 3                                        # a lesser kill's style
IMP_LENS2 = int(2.5 ** 2 * ONE)                      # not drawn this near the lens
IMP_SCALE = 0.75                                     # three quarters of his height
IMP_HOME2 = int(10.0 ** 2 * ONE)                     # nearer than this, it goes for him


def imp(i, k):
    return int(IMPS) + i * len(IMP_F) + IMP_F[k]


def imp_mesh():
    """a lesser demon, hunched, horned, long-armed: archive space, facing +x"""
    b = Build()
    if BASE:                                  # (no swarm in the base: its room is free)
        b.flat(0, 0.1, 0, 0.1, 0, (0, 0, 0))
        return b.mesh()
    BODY, LIMB, HORN, EYE = (54, 18, 16), (34, 12, 12), (120, 96, 78), (255, 92, 30)

    def beam(p0, p1, r0, r1, col):            # four sides between two squares
        p0, p1 = np.array(p0, float), np.array(p1, float)
        d = p1 - p0
        u = np.cross(d, (0, 0, 1.0)) if abs(d[2]) < 0.9 * np.linalg.norm(d) else np.array((0, 1.0, 0))
        u /= np.linalg.norm(u)
        w = np.cross(u, d)
        w /= np.linalg.norm(w)
        ring = lambda c, r: [c + r * (a * u + bb * w) for a, bb in ((1, 1), (-1, 1), (-1, -1), (1, -1))]   # noqa: E731
        A, B = ring(p0, r0), ring(p1, r1)
        for k in range(4):
            q = [A[k], A[(k + 1) % 4], B[(k + 1) % 4], B[k]]
            n = (q[0] + q[1] + q[2] + q[3]) / 4 - (p0 + p1) / 2
            b.quad(q, tuple(n), col)
    for sy in (-1, 1):
        beam((0.0, sy * 0.18, 0.0), (0.02, sy * 0.17, 0.62), 0.07, 0.10, LIMB)       # legs
        beam((0.30, sy * 0.40, 1.18), (0.72, sy * 0.46, 0.32), 0.08, 0.05, LIMB)     # arms
    # the torso, leaning in: a waist under broad shoulders thrown forward
    lo = [(-0.18, -0.26, 0.60), (0.18, -0.26, 0.60), (0.18, 0.26, 0.60), (-0.18, 0.26, 0.60)]
    hi = [(0.06, -0.40, 1.24), (0.46, -0.40, 1.24), (0.46, 0.40, 1.24), (0.06, 0.40, 1.24)]
    for k in range(4):
        q = [lo[k], lo[(k + 1) % 4], hi[(k + 1) % 4], hi[k]]
        c = np.mean(np.array(q), 0) - np.array((0.13, 0, 0.92))
        b.quad(q, tuple(c), BODY)
    b.quad(hi, (0, 0, 1), BODY)
    b.box(0.36, 0.66, -0.15, 0.15, 1.14, 1.44, BODY,
          sides=((1, 0), (-1, 0), (0, 1), (0, -1)))                                # the head
    for sy in (-1, 1):                                                              # its eyes
        y0, y1 = sorted((sy * 0.04, sy * 0.11))
        b.quad([(0.67, y0, 1.30), (0.67, y1, 1.30), (0.67, y1, 1.37), (0.67, y0, 1.37)],
               (1, 0, 0), EYE)
        for n in ((1, 0, 0), (-1, 0, 0)):                                          # horns,
            b.quad([(0.50, sy * 0.08, 1.44), (0.58, sy * 0.14, 1.44),               # both
                    (0.30, sy * 0.34, 1.86), (0.30, sy * 0.33, 1.86)], n, HORN)      # faces
    b.v = [tuple(int(round(c * IMP_SCALE)) for c in v) for v in b.v]   # LESSER: smaller
    return b.mesh()


IMP_M = int(cart.data(imp_mesh(), "imp"))


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
cart.boot(spec.FOG_NEAR, int(FOG_FROM * 512))   # P20b: the haze is HEAVY:
cart.boot(spec.FOG_SHIFT, 10)                   # from 2, full at 2 + 32 = 34 (the
                                                # crossroads' was 15 to 47)

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
AR = {k: cart.var("ar_" + k) for k in ("x", "z", "ox", "oz", "u", "v")}
AR_W = int((CITY_LANE - 0.7) * ONE)    # how near a wall a body's centre comes
if BASE:
    # P23 (the player: "can we step onto the side walk?"): in the base the
    # street is his from wall to wall -- a body's centre comes 0.6 from a
    # wall, over the curb and onto the sidewalk, and his feet step up it.
    # The arena's width is a CELL here, because the lens asks the same
    # question with a wider street (it may come 0.15 from a wall).
    AR_W = int((FAC - 0.6) * ONE)
    LENS_W = int((FAC - 0.15) * ONE)
    AWC = cart.data(Table([AR_W]), "ar_w")
    GYC = cart.var("curb_y")                 # how far up the curb his feet are
    LDX, LDZ = cart.var("lens_dx"), cart.var("lens_dz")   # the lens's eased move off a wall


L_KIA = p.label("kia")
KP = {k: cart.var("kp_" + k) for k in ("p", "o", "x", "y")}  # where x (z next),
                                                     # where ox; (the arena's sides)


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
LAND_FOR = 8                    # ...and of squash: four poses, two frames each
LANDT = cart.var("land_t")      # the squash's frames left
# THE LEAN (tear.py 660, LEAN_VEL_GAIN / LEAN_LAT_GAIN). He leans into his
# run -- 0.11 rad at full speed, the archive's own figure, 18 of this
# machine's 1,024 -- and banks into a turn. The archive bends the spine;
# this machine places a whole object, so both halves tip together from
# the feet, where the mesh's origin already is.
LEAN_PITCH = int(round(0.85 * 1024 / (2 * np.pi)))   # units per (unit a frame)
LEAN_BANK = 14                  # the turn's bank at rest, eased an eighth a frame
LEANR = cart.var("lean_r")
CLEAR2 = int(0.65 ** 2 * ONE)   # tear.py JUMP_CLEARANCE: a flip clears a head
BARGE_KEEP = int(0.15 * ONE)    # tear.py _collide: 85% of the run is lost
F = {k: cart.var("f_" + k) for k in
     ("hs", "stop", "vx", "vz", "con", "ltap", "c3", "alt", "buf", "bmv",
      "mv", "dead", "shake", "act", "fx", "fy", "fz", "pc", "ps", "fight",
      "wave", "tilt", "py", "pvy", "acmb", "uwin", "foe",
      "sty", "chain", "cgr", "latch", "slow", "aim", "skip", "spd", "evf", "evt",
      "evk", "evx", "evz", "flipu", "ph", "kdir",
      "tgt", "plc", "aimh", "sec", "lrp", "brg", "dmi")}
# (P18: slow, aim, skip, aimh and sec were the quick turn's qtw, qtc and
# qts and METEOR's met and metd -- the same cells, so nothing else moves)
AIM = F["aim"]
TOKC = F["alt"]                 # (P18: f_alt, the old string's hand -- unused since
                                # the rhythm -- counts the attack tokens held)
RES, LVL, CLR = SY["n"], SY["dx"], SY["dst"]   # the horde: reserve, district, the
                                # clear's beat (three style scratch cells, unused)
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
# P16: THE RUN GETS THERE. The ramp is not the logistic alone: the speed is
# scrubbed toward the velocity each frame (below), which follows it at the
# grip's 0.34, and together seed 0.35 / growth 0.09 took 79 frames to nine
# tenths of top. On the tape the median run was 17 frames long and not one
# frame of 874 was run at nine tenths. Seed 0.55 / growth 0.30 gets there
# in about 19. The top, the grip and the scrub are unchanged.
PK_TOP, PK_SEED = int(0.13 * ONE), int(0.13 * 0.55 * ONE)
PK_GROWTH, PK_FR, PK_GRIP = int(0.30 * ONE), int(0.84 * ONE), int(0.34 * ONE)
PK_INVTOP = int(ONE / 0.13 * ONE) >> 16                 # (1 / top, Q16)
PK_TURN = int(round(0.085 * PACE * 1024 / (2 * np.pi)))  # yaw units a frame
CHAIN_GRACE, CHAIN_SPEED2 = 26, int(0.10 * 0.10 * ONE)
QT_WINDOW, QT_COOL = 22, 30
# ---- P18: THE FOUR MODES (docs/TND-PORT.md P18) ------------------------------
# The base is the TANK -- unit-like, exact: Left/Right turn, Up/Down walk.
# Every attack goes the way the pad points, relative to his facing, and
# snaps there, so you know where it lands. A is the DODGE, that way too.
#   R      TARGETING: the nearest demon locked, he plants and faces it;
#          Left/Right change targets, Up/Down step the shot high/mid/low;
#          an attack HELD slows the world to a third (FOCUS) until let go
#   L      THE BOXER: square steps on the cross he held; A jumps, and with
#          a direction it is a directional jump and flip
#   L + R  THE RUN: he runs the way the pad points round the target, the
#          camera anchored on it; the gun shoots it
SQ_TARGET = 3                   # f_sty: 0 tank, 1 run, 2 boxer, 3 targeting
HORDE0, HSTEP, CLEAR_FOR = 30, 15, 150   # THE HORDE: the first district's reserve,
                                # each next one's more, and the beat between them
SLOW_EVERY = 3                  # FOCUS: the world moves one frame in three
FOCUS_HOLD = 3                  # ...once an attack is held past a tap (CHORD_SLOP)
SLOW_LAUNCH = 40                # a launcher that lands: 40 of the fight's frames
                                # (two seconds of glass, its hitstop and rise), and
                                # the gun tracks the body in the air
RUN_TURN = 48                   # the run's turn toward the pad: 17 degrees a frame
RUN_DT = 20                     # P20: R's second press within this many frames
FREE_TURN = 12                  # P20: the free run turns as the tank does
RUN_STAND = int(0.02 * ONE)     # P24: under this speed, in the run, he stands
WJ_KICK = int(0.30 * ONE)       # P25: the wall jump's push off the wall, a frame: across a
                                # street (8.1 wall to wall, for him) before he is down, so
                                # the next wall is his -- in the run and the boxer alike
WJ_COYOTE, WJ_MAX = 8, 2        # ...the frames a touch still counts, and how many an air
WJ_FRAMES = 24                  # ...and how long it throws him (a flip's length the spin knows)
# P27: THE SLIDE (the player, asked what Down should do in the run: "slide!!").
SLIDE_MIN = int(0.09 * ONE)     # he must be running this fast to go down into one
SLIDE_MAX, SLIDE_LEAST = 44, 16   # frames: the longest (Down held), and the least once begun
SLIDE_BOOST, SLIDE_KEEP = int(1.30 * ONE), int(0.975 * ONE)   # it starts faster than he ran -- a
                                # lunge at the ball -- and scrubs: 5.4 units held, from a full run
                                # ("make the slide go out a bit further"; it was 1.12 and 3.9)
SLIDE_UP = 6                    # frames to come back up out of it
RDT, FRUN = cart.data(Table([255]), "r_dt"), cart.var("f_frun")   # (long ago)
GUN_CONE = 46                   # the free shot's line: 16 degrees either side
GUN_AIM2 = int(13.0 ** 2 * ONE)
CLOSE_CALL = 30                 # style, a fist dodged through
STEADY, PAUSE = 14, 55          # the rhythm, from the end of the last blow of the
                                # string: a tap during it or within 14 frames keeps
                                # time; 15..55 is a WAIT; longer, a new string
SEC_MAX = 2                     # shots inside a string before it is lost
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
TGT_D, TGT_SH, FOCUS_D = 2.8, -0.55, 2.2          # P18: targeting, over the shoulder
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
L_STEER, L_LINE = p.label("steer"), p.label("line")
if L2:
    L_RAY, L_LAND, L_FIRE = p.label("ray"), p.label("land"), p.label("fire")
if L3:
    L_RING = p.label("ring")
PHP = cart.data(Table([140]), "p_hp")
FRIC = int(round(0.82 * ONE))                   # tear.py: body friction
# ---- P21: THE BASE LAYER'S KNOBS. The feel of the tank is tuned ON GLASS: in
# a layer-0 build, SELECT held makes the d-pad a tuner (Left/Right pick a
# knob, Up/Down turn it a notch) and the screen shows the knob and its notch
# (50 is where it started). The tape carries every press home, so the replay
# reads the values chosen -- no card trip a guess. (name, start, a notch)
# THE STARTS ARE THE PLAYER'S (in a base build: BASE_SET), from his sessions
# on glass on 2026-11-21 ("this feels the best so far"; then "this looks
# good, i think i crounch could be more subtle"). The first base's notches
# were left at walk +17, ramp +17, turn +2, quick turn +9, the lens 5 nearer
# and 5 lower, the wall's slide all the way off; the second kept the heavy
# grade and went looking for a shorter pick-up. The game above the base
# keeps its own until the layer is merged.
BASE_SET = dict(walk=int(0.032 * ONE) + 17 * int(0.002 * ONE),      # 0.066: twice the archive's
                ramp=int(0.22 * ONE) + 17 * int(0.03 * ONE),        # 0.73: all but at once
                turn=14, qturn=80,                                  # half round in 7 frames
                camd=int(3.0 * ONE) - 5 * int(0.2 * ONE),           # 2.0 behind
                camh=int(2.15 * ONE) - 5 * int(0.1 * ONE),          # 1.65 up
                pick=8, grade=2) if BASE else {}
# (name, start, a notch, least, most). THE LIMITS ARE THE GAME'S SAFETY: on
# the second base tape the pick-up's knob was turned to -10 frames, and the
# pick-up it began counted down from -10 for ever -- he stood bowed for the
# last seventeen seconds. No knob can now reach a value the game cannot play.
KNOBS = (("walk", WALK, int(0.002 * ONE), int(0.01 * ONE), int(0.12 * ONE)),            # 0 his pace
         # 1 HIS LEGS: poses of the stride a unit of ground. Planted, the
         # long stride wants 20 (a pose every 0.05) -- five steps a second
         # at his pace; at 13.3 it is 3.3 steps a second, and his feet give
         # up a third of the ground. (Weight, once this knob, is settled.)
         ("legs", int(ONE / 0.075), int(0.67 * ONE), int(ONE / 0.14), int(ONE / 0.04)),
         ("turn", 12, 1, 2, 40),                                    # 2 the tank's turn, a frame
         ("qturn", 44, 4, 8, 256),                                  # 3 the quick turn's, a frame
         ("camd", int(3.0 * ONE), int(0.2 * ONE), ONE, 6 * ONE),    # 4 the follow's distance
         ("camh", int(2.15 * ONE), int(0.1 * ONE), int(0.8 * ONE), 4 * ONE),   # 5 ...and its height
         ("light", LIT_AMB0, 1, 4, 24),                            # 6 the town's own dark (of 32)
         ("pick", 18, 2, 0, 60),                                    # 7 frames a pick-up holds him
         ("grade", 1, 1, 0, 2),                                     # 8 the glass's curve: 0 off, 2 heavy
         ("bow", 40, 8, 0, 128))                                    # 9 how far he bows to pick up
KNOBS = tuple((k, BASE_SET.get(k, v), st_, lo_, hi_) for k, v, st_, lo_, hi_ in KNOBS)
# LAYER 1'S PAGE: the left shoulder. (The base's knobs are settled in a
# layer-1 build -- they read as the constants the player left them at.)
# (The values are the PLAYER'S, read off his tapes of the layer on glass,
# 2026-11-21 -- twenty minutes, then ten more turning them again: the run
# 1.24x (0.16 a frame), turning 13 a frame, gripping at 0.90 -- almost no
# drift, where the archive's run had 0.34 -- its lens 3.4 behind and
# trailing by 0.07; the boxer's lens 2.8 and its step half again the
# archive's; the jump the archive's own; the two clicks 44 frames apart.)
KNOBS_L1 = (("run", 81262, int(0.08 * ONE), int(0.5 * ONE), int(2.5 * ONE)),     # 0 the run's pace (x 0.13)
            ("runacc", 21626, int(0.03 * ONE), int(0.03 * ONE), int(0.9 * ONE)),   # 1 how fast it builds
            ("runturn", 13, 1, 3, 24),                             # 2 its turn, a frame (the tank's is 14)
            ("grip", 58976, int(0.04 * ONE), int(0.06 * ONE), ONE),   # 3 how soon he goes where he faces
            ("runcam", 222822, int(0.2 * ONE), ONE, 8 * ONE),      # 4 the run's lens, behind
            ("trail", 4588, int(0.01 * ONE), int(0.02 * ONE), int(0.25 * ONE)),   # 5 how soon it comes round
            ("boxcam", 183500, int(0.2 * ONE), ONE, 6 * ONE),      # 6 the boxer's lens, behind
            ("boxstep", 989, 60, 200, 2000),                       # 7 the boxer's step
            ("jump", 12190, int(0.01 * ONE), int(0.08 * ONE), int(0.4 * ONE)),   # 8 the jump
            ("dclick", 44, 2, 6, 60))                              # 9 frames between the two clicks
# LAYER 2'S PAGE: the strikes.
KNOBS_L2 = (("pivot", 176, 16, 128, 512),      # 0 his body's turn into a blow's way, a frame (512: at once)
            ("lunge", 58983, int(0.1 * ONE), 0, 3 * ONE),   # 1 how far a strike carries him (x its own; the player's)
            ("keep", 40, 4, 8, 160),           # 2 frames after a blow the string still stands
            ("hold", 14, 2, 6, 40),            # 3 frames a button is down before time slows
            ("slow", 3, 1, 2, 6),              # 4 ...to one frame in this many
            ("sjump", int(round(3.0 / 22 * ONE)), int(0.01 * ONE), int(0.05 * ONE), int(0.4 * ONE)),   # 5 the boxer's strafe jump, a frame (x 22: 3.0 units)
            ("fcam", int(1.3 * ONE), int(0.1 * ONE), int(0.6 * ONE), 4 * ONE),   # 6 time slowed: the lens, this far back
            ("wander", int(0.08 * ONE), int(0.01 * ONE), int(0.01 * ONE), ONE),  # 7 the boxer's lens: its share of the way, a frame
            ("dodge", int(0.20 * ONE), int(0.01 * ONE), int(0.08 * ONE), int(0.4 * ONE)),   # 8 the dodge, a frame (x 12: 2.4 units)
            ("mag", 6, 1, 0, 12))              # 9 rounds in the gun (0: it never runs dry)
SETTLED = {k_[0]: k_[1] for k_ in KNOBS + KNOBS_L1 + KNOBS_L2}
SETTLED["ramp"] = BASE_SET.get("ramp", int(0.22 * ONE))      # (weight: left at 0.73)
if LAYER == 1:
    KNOBS = KNOBS_L1
if LAYER in (2, 3, 4, 5, 6, 7):
    KNOBS = KNOBS_L2
if BASE:
    KN = cart.data(Table([k_[1] for k_ in KNOBS]), "knobs")
    KNOTCH = cart.var("knob_n", len(KNOBS))
    KSEL, KPV, KTUNE = (cart.var(k) for k in ("knob_sel", "knob_pv", "knob_on"))
    WSPD, QT, KEY, PICK, KNEAR, KX, KZ, WACC, LFLASH = (cart.var(k) for k in (
        "walk_v", "qturn_left", "key_held", "pick_t", "ctx_near", "ctx_x", "ctx_z", "walk_acc",
        "light_flash"))
    if L5:
        # P38: THE WORLD's state. The keys in hand and the keys ever taken (a
        # bit a gate); the doors opened (a bit a door: the gates, then the
        # bolts); is there an item at all; the nearest key not yet taken (its
        # number, bit and place) and the nearest door still shut (its number,
        # bit, the key's bit it eats, the place to stand on HIS side, its
        # turn, its mesh, and whether the jab would open it from here); the
        # node the arrow leads to; the nearest bunker, and the last one stood
        # in; is the hard way's pack awake, and where its ring is centred.
        # (KEY keeps its place in the layers under: nonzero, the item is a
        # DOOR, not a key.)
        (KEYS, TAKEN, OPENED, ITEM, K5, KYB, KYX, KYZ, BESTK, D5, DRB, DRK, DRX, DRZ, DRY, DRM, DCAN, BESTD,
         WAYN, BKX, BKZ, BESTB, LASTB, PACK, PKX, PKZ, PIPN, PIPE) = (cart.var("w_" + k) for k in (
            "keys", "taken", "opened", "item", "k5", "kyb", "kyx", "kyz", "bestk", "d5", "drb", "drk", "drx", "drz",
            "dry", "drm", "dcan", "bestd", "wayn", "bkx", "bkz", "bestb", "lastb", "pack", "pkx", "pkz", "pipn",
            "pipe"))
        FAR_ = 0x3FFFFFFF
    if L6:
        # P39: THE MAP's state. Is it open; the cursor's node (column, row);
        # the pad a frame ago and how long a direction has been held; shut
        # with Select still down; his waymarks (how many, their nodes, in
        # order); the sectors he knows (a bit each). And THE ROUTE: a way
        # out of every node toward the waymark, by the streets that are
        # open now (a side, or 4: no way) -- with the search's queue, the
        # waymark and the doors it was made for.
        MAPON, MCX, MCY, MPV, MREP, MAPX, WN, KNOWN, WAYL, OPL, BH, BT, BV, BW, BM = (cart.var("m_" + k) for k in (
            "on", "cx", "cy", "pv", "rep", "x", "wn", "known", "wayl", "opl", "bh", "bt", "bv", "bw", "bm"))
        WP = cart.var("m_wp", 4)
        HOPT = cart.var("m_hop", CS * CS)
        BQ = cart.var("m_q", CS * CS)
    if L7:
        # P40: THE BUNKER'S ROOMS. Is he in them; the nearest way in or out
        # (which, its place, its turn, how far); what the item is (0 a key,
        # 1 a door of the street, 2 a bunker's); is he at the prep table;
        # and the arena's two for a room.
        INSIDE, TDT, TDX, TDZ, TDY, BESTT, ITK, DESKN, RMU, RMV = (cart.var("b_" + k) for k in (
            "in", "tdt", "tdx", "tdz", "tdy", "bestt", "itk", "desk", "rmu", "rmv"))


def item_exists(g):
    """( -- flag ) is there an item (the key, or its gate) for the jab, the
    lock, the shot: in the world, whenever a key or a door is left; under
    it, until the last district"""
    if L5:
        return g.load(ITEM)
    return g.load(LVL).push(len(GATES)).emit("lt")


def manhattan(g, x_, z_, tag):
    """( -- |x - his| + |z - his| ): how far, by the streets' own axes --
    no squares, so the whole town is in range of the word"""
    for c_, cell_, k_ in ((x_, PX, "x"), (z_, PZ, "z")):
        g.push32(c_).load(cell_).emit("sub", "dup").push(0).emit("lt", f"jz {tag}{k_}")
        g.push(0).emit("swap", "sub")
        g.mark(f"{tag}{k_}")
    return g.emit("add")


if BASE:
    # P25: THE WALL JUMP's memory -- which way a wall stopped him in the air,
    # for how many frames more it still counts, and how many he has had
    WALLT, WALLA, WSX, WSZ, WTX, WTZ, WJN = (cart.var(k) for k in (
        "wall_t", "wall_axes", "wall_sx", "wall_sz", "wall_tx", "wall_tz", "wall_n"))
    SLT, SLV, SLF = cart.var("slide_t"), cart.var("slide_v"), cart.var("slide_f")
    # P31: where a blow goes (his BODY turns there; his steering does not),
    # whether he stands turned from his steering, and a place to keep it
    PIVT, TURNED, YKEEP = cart.var("punch_to"), cart.var("turned"), cart.var("yaw_keep")
    # ...the boxer's strafe jump (0, or 1..4 the way), the lens's wander (its
    # place, and its share of the way a frame), and the slowed lens's focus
    SJD = cart.var("sjump_dir")
    BCX, BCZ, WR = cart.var("lens_x"), cart.var("lens_z"), cart.var("lens_share")
    HX, HZ, FOCB = cart.var("focus_x"), cart.var("focus_z"), cart.var("focus_on")
    # P33: time slowed (1) this frame; A's own hold (frames down) and its
    # press, kept till a running frame reads it; a dodge to be stopped
    SLOWON, AHOLD, APEND, EVW = (cart.var(k) for k in ("slow_on", "a_hold", "a_press", "dodge_end"))
    # ...and the pad as the FIGHT last saw it (a running frame's): what a
    # press is "fresh" against, in the fight's own time
    PVF = cart.var("prevpad_f")
    PVE = PVF if L2 else PV     # (the fight's edges: the run's click, the slide's Down)
    if L2:
        # P34: THE GUN. How far it is drawn (frames B has been down, to its
        # shot's first frame), the rounds gone from it and its reload's
        # clock; the key, struck; the line a shot takes (RAY: its way, how
        # far, what it meets and where); and the bullets in the air (where
        # each will land, its way, how far it has left to go).
        DRAW, SHOTS, RLD, KHIT, BNX = (cart.var(k) for k in (
            "gun_draw", "gun_shots", "gun_reload", "key_hit", "bul_next"))
        RAY = {k: cart.var("ray_" + k) for k in ("dx", "dz", "len", "hit", "x", "z", "step", "ox", "oz")}
        AIMT = cart.var("aim_linger")
        # P35: he is AIMING (B held past the hold knob: his steering came
        # round to his body, and the pad moves him), and how long the pad
        # has turned him at it (the turn starts fine)
        AIMED, ATURN = cart.var("aimed"), cart.var("aim_turn")
        BUL = [{k: cart.var(f"bul{i}_{k}") for k in ("ex", "ez", "dx", "dz", "rem", "y", "yaw", "hit")}
               for i in range(2)]
        assert int(BUL[1]["ex"]) == int(BUL[0]["ex"]) + 8 and int(BUL[0]["hit"]) == int(BUL[0]["ex"]) + 7
    if L3:
        # P35: THE RIGHT SHOULDER. R down this frame (the pad's own word:
        # the fight below never sees R), and locked on the item
        RHELD, LOCK = cart.var("r_held"), cart.var("locked")
        LOCK_RANGE, LOCK_TURN = 20.0, 48
        # P36: the item's bearing, kept; frames the gun arm stays out after a
        # shot in the run; the superman punch -- its pace through the air,
        # and how near the item it stops
        LBRG, RSHOT = cart.var("lock_brg"), cart.var("run_shot")
        # ...and the circle he runs: the pad it began with, its radius squared
        RPAD, RAD2 = cart.var("circle_pad"), cart.var("circle_r2")
        CIRCLE_IN = 6                # units of heading turned in, when he is outside it
        SUPER_V, SUPER_STOP, RUN_ARM = int(0.25 * ONE), int(1.2 * ONE), 14
    if L4:
        # P37: THE TARGETS -- the enemies, then the item. Which is chosen (-1:
        # none), the spot on it (0 high, 1 mid, 2 low), where it is, whether
        # there is one; R as it was a frame ago; R held ALONE (he is planted);
        # and, a target each: where, in reach?, how far (squared), its bearing.
        NE = len(ENEMY)
        TSEL, SPOT, TGTX, TGTZ, TOK, RPREV, PLANT = (cart.var(k) for k in (
            "t_sel", "t_spot", "t_x", "t_z", "t_ok", "r_prev", "planted"))
        TPX, TPZ, TV, TD, TB = (cart.var(k, NE + 1) for k in ("t_px", "t_pz", "t_in", "t_d2", "t_brg"))
        SPOTY = cart.data(Table([int(1.60 * ONE), int(1.10 * ONE), int(0.50 * ONE)]), "spot_y")
        FDMG = cart.data(Table([1, 1, 2, 2, 4, 2, 2, 0, 0]), "fist_dmg")     # by move (PMN)
        E_R, E_TURN, DOWN_FOR, E_LEGS = int(0.40 * ONE), 20, 150, 20
    TGX, TGZ = (TGTX, TGTZ) if L4 else (KX, KZ)     # (the lock's target: layer 3 had only the item)
    cart.boot(spec.LIGHT_DIR, 0x007F00)          # P22: straight down (see piece_light)
    cart.boot(spec.LIGHT_AMB, LIT_AMB0)         # (the title's street, before the game
    cart.boot(spec.LIGHT_DIF, 33 - LIT_AMB0)    # sets them a frame at a time)
    KSTR1 = cart.data(Table([1, 0]), "str_k1")
    KSTR2 = cart.data(Table([2, 0, 0]), "str_k2")


def _grade(gr, gg, gb, lift=0.0):
    """a 32-level curve a channel: out = 255 * t ** gamma (sunk when > 1)"""
    out = []
    for i in range(32):
        t = i / 31
        r, g_, b_ = (min(255, int(round(255 * (lift + (1 - lift) * t) ** k))) for k in (gr, gg, gb))
        out.append(r << 16 | g_ << 8 | b_)
    return out


if BASE:
    GRADES = [cart.data(Table(_grade(*k)), f"grade{i}") for i, k in enumerate(
        ((1.0, 1.22, 1.16), (1.08, 1.5, 1.4)) + (((1.45, 2.2, 2.0),) if L2 else ()))]   # (the third: time, slowed)
    cart.boot(spec.EDGE_RGB, 0xFFF4D8)            # the outline: bone-white, on what the jab would take


if L2:
    # P30: each blow's own lunge frame (its drive, not its wind-up)
    LUNGE_AT = {"jab": 1, "cross": 1, "lead_hook": 6, "rear_hook": 6, "special": 13,
                "lead_uppercut": 8, "rear_uppercut": 8}
    LDT = cart.data(Table([LUNGE_AT.get(n_, 0) for n_ in PMN]), "lunge_at")
    TURN_LOCK = 10              # frames after a string's blow the pad still does not turn or walk him
    FOCUS_REACH, FOCUS_SH = 0.7, -0.6             # the slowed lens: a blow's reach; over his right shoulder
    FOCUS_DROP = 0.30                             # ...and down toward the fist's height
if L1:
    SJB = cart.data(Table([base["sj_" + k_] for k_ in SJ_WAYS] + ([base["sj_fwd"]] if L3 else [])),
                    "sjump_poses")          # (the fifth: P36's leap, if its blow ends in the air)
    SJ_TURN = cart.data(Table([0, 0, 512, 256, 768]), "sjump_turn")   # (by sjump_dir: in, out, left, right)
    SJ_RISE = 0.72              # its rise, x the jump's: lower, and longer


def enemy_hurt(g, e):
    """w_dmg off what enemy e can take, and w_stop frames it is held: it
    flashes; with nothing left it goes down"""
    eh = g.label("ehurt")
    g.load(e["hp"]).load(W["dmg"]).emit("sub", "dup").store(e["hp"])
    g.push(1).emit("lt", f"jz {eh}")
    g.set(e["st"], 2).set(e["t"], 0)
    g.mark(eh)
    g.load(W["stop"]).store(e["stun"]).set(e["fl"], 8).set(e["walk"], 0)


def steer_head(g, to_cell):
    """turn his BODY (HEAD) toward to_cell by the pivot knob, the short way;
    his steering (YAW) is put back as it was"""
    g.load(to_cell).store(W["head"])
    g.load(YAW).store(YKEEP).load(HEAD).store(YAW)
    knob(g, "pivot").store(W["dg"]).emit(f"call {L_STEER}")
    g.load(YAW).store(HEAD).load(YKEEP).store(YAW)


def knob(g, name):
    """push the knob: its cell where this build's tuner turns it, else the
    value it is settled at"""
    names = [k_[0] for k_ in KNOBS]
    if BASE and name in names:
        return g.load(int(KN) + names.index(name))
    return g.push32(SETTLED[name])


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
p.set(PX, 0).set(PZ, 0)          # (P19: on the title he stands where the intro films)
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
p.set(RES, HORDE0).set(LVL, 0).set(CLR, 0)          # P18: the first district
# P19: THE STORY STARTS AT THE START -- the dead end at one end of the
# city's longest street, facing out, the street empty. The first district's
# horde is in its plaza, asleep until he walks in.
p.set(PX, START_X).set(PZ, START_Z).set(YAW, START_YAW).set(CY, START_YAW)
p.set(WOKE, 0)
for d in range(3):
    p.set(dslot(d, "st"), 4)
for i in range(N_IMP):
    p.set(imp(i, "st"), 0)
if BASE:
    for c_ in (KEY, PICK, QT, WSPD, KNEAR, TURNED, SJD, FOCB, SLOWON, AHOLD, APEND, EVW):
        p.set(c_, 0)
    if L2:
        for c_ in (DRAW, SHOTS, RLD, KHIT, AIMT, AIMED, ATURN, BUL[0]["rem"], BUL[1]["rem"]) + ((LOCK, RSHOT) if L3 else ()):
            p.set(c_, 0)
    if L4:
        p.set(TSEL, -1).set(SPOT, 1).set(TOK, 0).set(RPREV, 0).set(PLANT, 0)
        for e_ in ENEMY:
            if L5:
                p.push32(PACK_HOME[0] + e_["rx"]).store(int(e_["pos"])).push32(PACK_HOME[1] + e_["rz"]).store(int(e_["pos"]) + 1)
            else:
                p.set(int(e_["pos"]), START_X + e_["dx"]).set(int(e_["pos"]) + 1, START_Z + e_["dz"])
            p.set(e_["yaw"], 0).set(e_["st"], 1).set(e_["hp"], e_["T"]["hp"])
            for k_ in ("stun", "fl", "ph", "walk", "t"):
                p.set(e_[k_], 0)
            p.set(e_["clk"], e_["phase"])
    if L5:
        for c_ in (KEYS, TAKEN, OPENED, ITEM, LASTB, PACK, DCAN):
            p.set(c_, 0)
        p.set(K5, -1).set(D5, -1).set(WAYN, CITY.start).set(PIPN, 0)
        if L6:
            for c_ in (MAPON, MAPX, WN, KNOWN, MREP):
                p.set(c_, 0)
            p.set(WAYL, -1).set(OPL, -1)
        if L7:
            # P40: "we start in a bunker" -- inside the first one's door,
            # facing the room, its survey already his; the six in the ring
            _hub = TDOORS[-1]
            p.push32(_hub["out"][0]).store(PX).push32(_hub["out"][1]).store(PZ)
            p.set(YAW, _hub["out_yaw"]).set(CY, _hub["out_yaw"]).set(HEAD, _hub["out_yaw"])
            p.set(INSIDE, 1).set(LASTB, 0).set(ITK, 0).set(DESKN, 0).set(KNOWN, TDOORS[0]["know"])
            for e_ in ENEMY:
                p.push32(RING_XZ[0] + e_["rx"]).store(int(e_["pos"])).push32(RING_XZ[1] + e_["rz"]).store(int(e_["pos"]) + 1)
        for c_ in (BESTK, BESTD, BESTB):
            p.push32(FAR_).store(c_)
        if os.environ.get("TND_AT"):            # (the meter's hook: begin elsewhere -- "x,z,yaw,keys")
            _at = os.environ["TND_AT"].split(",")
            p.push32(int(float(_at[0]) * ONE)).store(PX).push32(int(float(_at[1]) * ONE)).store(PZ)
            p.set(YAW, int(_at[2])).set(CY, int(_at[2])).set(HEAD, int(_at[2])).set(KEYS, int(_at[3])).set(TAKEN, int(_at[3]))
            if L6 and len(_at) > 4:             # (...and "known", the sectors on the map)
                p.set(KNOWN, int(_at[4]))
            if L7:
                p.set(INSIDE, 0)
    p.set(WR, ONE)
if SWARM_TEST:                                  # (the meter's hook: the fight in the
    p.set(PX, int(3 * ONE)).set(PZ, int(3 * ONE))               # first plaza, the
p.set(GT["jump"], 100).set(GC["jump"], 1)        # whole swarm up)     # the A that left the title is spent
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
p.set(spec.OVL_LEN, PAGE).set(spec.OVL_GO, 1)
p.set(spec.BG_SRC, 0).set(spec.CO_BASE, 1)
p.rect(0, 0, 0, spec.W - 1, spec.H - 1, 0x000000, 16)
p.emit(f"jmp {L_MUSIC}")
p.mark(f"{tl}_fight")
if L6:
    # P39: THE BUNKER'S MAP (docs/TND-WORLD.md, step 3: "the bunker is where
    # you prep, setting your way marks planning routes"). On a hatch, a
    # fresh SELECT opens it and the street stops -- nothing of the fight
    # runs, so its time does not either. The pad moves the cursor a node
    # (held: it runs); A puts a waymark there, or takes off the one that
    # is; Y clears the plan; SELECT shuts it. (Off a hatch SELECT is the
    # knobs, as it was.)
    mp = p.label("map")
    _dirs = spec.PAD_UP | spec.PAD_DOWN | spec.PAD_LEFT | spec.PAD_RIGHT
    _zm = MAP_ZQ - int(0.04 * ONE)

    def _mx(cell_):
        return (f"load {int(cell_)}", "push 15", "and", "push 2", "mul", "push 15", "sub", "push 8192", "mul")

    def _my(cell_):
        return (f"load {int(cell_)}", "shr 4", "push 2", "mul", "push 15", "sub", "push 8192", "mul")

    def _mark_node(mesh_, n_, dz_=0):
        x_, y_ = _map_xy(n_)
        p.object(NOBJ, mesh_, _map_q(x_), _map_q(y_), _zm - dz_, 0, 0)

    def _mark_mid(kind_, a_, b_):
        (x0_, y0_), (x1_, y1_) = _map_xy(a_), _map_xy(b_)
        p.object(NOBJ, MK[kind_ + ("_h" if abs(a_ - b_) == 1 else "_v")], _map_q((x0_ + x1_) / 2), _map_q((y0_ + y1_) / 2),
                 _zm, 0, 0)

    def _knows(tag_, *nodes_):
        """( -- ) jump to tag_ unless he knows the sector of one of these nodes"""
        p.load(KNOWN).push(sum({1 << CITY.district[n_] for n_ in nodes_})).emit("and", f"jz {tag_}")
    p.load(MAPX).emit(f"jz {mp}_nx")                 # (shut, SELECT still down: the knobs
    held(spec.PAD_SELECT)                            # do not open under his thumb)
    p.emit(f"jz {mp}_xr")
    p.emit("load 1").push(0xFFFF & ~spec.PAD_SELECT).emit("and").store(spec.REG_PAD)
    p.emit(f"jmp {mp}_nx")
    p.mark(f"{mp}_xr")
    p.set(MAPX, 0)
    p.mark(f"{mp}_nx")
    p.emit("load 1").load(MPV).push(-1).emit("xor", "and").store(BW)        # pressed now
    p.load(MAPON).emit(f"jz {mp}_off", f"jmp {mp}_on")
    p.mark(f"{mp}_off")
    p.emit("load 1").store(MPV)
    p.load(BW).push(spec.PAD_SELECT).emit("and", f"jz {mp}_end")
    if L7:                                           # (P40: at the prep table, in the hub)
        p.load(DESKN).emit(f"jz {mp}_end")
    else:
        p.load(BESTB).push(int(2.0 * ONE)).emit("lt", f"jz {mp}_end")
    p.set(MAPON, 1).set(MREP, 0).set(spec.FOG_SHIFT, 0)
    if L7:                                           # the cursor begins at the bunker he is in
        p.push(int(BUNKN_T)).load(LASTB).emit("add", "loadi").store(CT["n"])
    else:
        city_node(p, PX, PZ)                         # the cursor begins where he stands
    p.load(CT["n"]).push(15).emit("and").store(MCX).load(CT["n"]).emit("shr 4").push(15).emit("and").store(MCY)
    p.emit(f"jmp {mp}_draw")
    p.mark(f"{mp}_on")
    p.emit("load 1").push(_dirs).emit("and").store(BV)
    p.load(BV).emit(f"jz {mp}_r0")
    p.load(BV).load(MPV).push(_dirs).emit("and", "eq", f"jz {mp}_r0")
    p.addi(MREP, 1)
    p.push(11).load(MREP).emit("lt", f"jz {mp}_r1")                         # held twelve frames:
    p.load(MREP).push(3).emit("and", f"jz {mp}_rr", f"jmp {mp}_r1")         # a step every fourth
    p.mark(f"{mp}_rr")
    p.load(BW).load(BV).emit("or").store(BW)
    p.emit(f"jmp {mp}_r1")
    p.mark(f"{mp}_r0")
    p.set(MREP, 0)
    p.mark(f"{mp}_r1")
    p.emit("load 1").store(MPV)
    p.load(BW).push(spec.PAD_SELECT).emit("and", f"jz {mp}_stay")
    p.set(MAPON, 0).set(MAPX, 1).set(spec.FOG_SHIFT, 10).set(PIPN, 0).set(int(S_SHOWN), 255)
    p.emit(f"jmp {mp}_draw")                         # (this frame is still the map's)
    p.mark(f"{mp}_stay")
    for bit_, cell_, dv_ in ((spec.PAD_RIGHT, MCX, 1), (spec.PAD_LEFT, MCX, -1), (spec.PAD_UP, MCY, 1),
                             (spec.PAD_DOWN, MCY, -1)):
        p.load(BW).push(bit_).emit("and", f"jz {mp}_c{bit_}")
        p.addi(cell_, dv_)
        p.mark(f"{mp}_c{bit_}")
    p.clamp(MCX, 0, CS - 1)
    p.clamp(MCY, 0, CS - 1)
    p.load(BW).push(spec.PAD_A).emit("and", f"jz {mp}_na")
    p.load(MCY).push(CS).emit("mul").load(MCX).emit("add").store(BV)        # the cursor's node
    p.load(BV).push(int(CMAP)).emit("add", "loadi", "shr 23").push(15).emit("and")
    p.push(int(SBIT)).emit("add", "loadi").load(KNOWN).emit("and", f"jz {mp}_na")   # (only where he knows the town)
    for k_ in range(4):
        p.push(k_).load(WN).emit("lt", f"jz {mp}_w{k_}")
        p.load(int(WP) + k_).load(BV).emit("eq", f"jz {mp}_w{k_}")
        for j_ in range(k_, 3):                      # (one of his: taken off, the rest move up)
            p.load(int(WP) + j_ + 1).store(int(WP) + j_)
        p.addi(WN, -1).emit(f"jmp {mp}_na")
        p.mark(f"{mp}_w{k_}")
    p.load(WN).push(4).emit("lt", f"jz {mp}_na")
    p.load(BV).push(int(WP)).load(WN).emit("add", "storei")
    p.addi(WN, 1)
    p.mark(f"{mp}_na")
    p.load(BW).push(spec.PAD_Y).emit("and", f"jz {mp}_ny")
    p.set(WN, 0)
    p.mark(f"{mp}_ny")
    p.mark(f"{mp}_draw")
    p.set(NOBJ, 0)
    for c_ in (spec.CAM_X, spec.CAM_Y, spec.CAM_Z, spec.CAM_YAW, spec.CAM_PITCH, spec.CAM_ROLL):
        p.set(c_, 0)
    for k_, (sec_, desc_) in enumerate(MAPS):        # the streets of the sectors he knows
        p.load(KNOWN).push(1 << sec_).emit("and", f"jz {mp}_s{k_}")
        p.object(NOBJ, desc_, 0, 0, MAP_ZQ, 0, spec.OBJ_CART)
        p.mark(f"{mp}_s{k_}")
    for i_, (a_, b_) in enumerate(WORLD.hard):       # the hard ways out of them
        _knows(f"{mp}_h{i_}", a_, b_)
        _mark_mid("hard", a_, b_)
        p.mark(f"{mp}_h{i_}")
    for i_, d_ in enumerate(DOORS):
        _knows(f"{mp}_d{i_}", d_["a"], d_["b"])
        if d_["kind"] == 0:                          # a gate still shut
            p.load(OPENED).push(1 << i_).emit("and", f"jz {mp}_d{i_}g", f"jmp {mp}_d{i_}")
            p.mark(f"{mp}_d{i_}g")
            (x0_, y0_), (x1_, y1_) = _map_xy(d_["a"]), _map_xy(d_["b"])
            p.object(NOBJ, MK["gate"], _map_q((x0_ + x1_) / 2), _map_q((y0_ + y1_) / 2), _zm, 0, 0)
        else:                                        # a back door: its bolt in, or drawn
            p.load(OPENED).push(1 << i_).emit("and", f"jz {mp}_d{i_}s")
            _mark_mid("open", d_["a"], d_["b"])
            p.emit(f"jmp {mp}_d{i_}")
            p.mark(f"{mp}_d{i_}s")
            _mark_mid("shut", d_["a"], d_["b"])
        p.mark(f"{mp}_d{i_}")
    for g_, (k, _) in enumerate(GATES):              # the keys still lying
        n_ = WORLD.keys[k]
        _knows(f"{mp}_k{g_}", n_)
        p.load(TAKEN).push(1 << g_).emit("and", f"jz {mp}_k{g_}y", f"jmp {mp}_k{g_}")
        p.mark(f"{mp}_k{g_}y")
        _mark_node(MK["key"], n_)
        p.mark(f"{mp}_k{g_}")
    for b_, n_ in enumerate(WORLD.bunkers):
        _knows(f"{mp}_b{b_}", n_)
        _mark_node(MK["bunker"], n_)
        p.mark(f"{mp}_b{b_}")
    _knows(f"{mp}_core", CITY.core)
    _mark_node(MK["core"], CITY.core)
    p.mark(f"{mp}_core")
    if L7:
        p.push(int(BUNKN_T)).load(LASTB).emit("add", "loadi").store(BM)     # the bunker he is in (it blinks)
    else:
        city_node(p, PX, PZ)                         # where he stands (it blinks)
        p.load(CT["n"]).store(BM)
    p.load(spec.REG_FRAME).push(16).emit("and", f"jz {mp}_you")
    p.object(NOBJ, MK["you"], _mx(BM), _my(BM), _zm - int(0.02 * ONE), 0, 0)
    p.mark(f"{mp}_you")
    for k_ in range(4):                              # his plan, in its order
        p.push(k_).load(WN).emit("lt", f"jz {mp}_p{k_}")
        p.object(NOBJ, WMK[k_], _mx(int(WP) + k_), _my(int(WP) + k_), _zm - int(0.03 * ONE), 0, 0)
        p.mark(f"{mp}_p{k_}")
    # (WHICH KEY IS WHICH GATE'S: the cursor on a key, its gate is framed
    # too; on a gate's street end, its key -- if he knows where it lies)
    p.load(MCY).push(CS).emit("mul").load(MCX).emit("add").store(BT)
    for g_, (k, _) in enumerate(GATES):
        d_, n_ = DOORS[g_], WORLD.keys[k]
        (x0_, y0_), (x1_, y1_) = _map_xy(d_["a"]), _map_xy(d_["b"])
        p.load(BT).push(n_).emit("eq", f"jz {mp}_kg{g_}")
        _knows(f"{mp}_kg{g_}", d_["a"], d_["b"])
        p.object(NOBJ, MK["cursor"], _map_q((x0_ + x1_) / 2), _map_q((y0_ + y1_) / 2), _zm - int(0.04 * ONE), 0, 0)
        p.mark(f"{mp}_kg{g_}")
        p.load(BT).push(d_["a"]).emit("eq").load(BT).push(d_["b"]).emit("eq", "or", f"jz {mp}_gk{g_}")
        _knows(f"{mp}_gk{g_}", n_)
        p.load(TAKEN).push(1 << g_).emit("and", f"jz {mp}_gk{g_}y", f"jmp {mp}_gk{g_}")
        p.mark(f"{mp}_gk{g_}y")
        _mark_node(MK["cursor"], n_, int(0.04 * ONE))
        p.mark(f"{mp}_gk{g_}")
    p.object(NOBJ, MK["cursor"], (f"load {int(MCX)}", "push 2", "mul", "push 15", "sub", "push 8192", "mul"),
             (f"load {int(MCY)}", "push 2", "mul", "push 15", "sub", "push 8192", "mul"), _zm - int(0.04 * ONE), 0, 0)
    p.load(NOBJ).store(spec.OL_BASE)
    p.set(spec.DL_BASE, 0)
    p.emit(f"jmp {L_MUSIC}")
    p.mark(f"{mp}_end")
if BASE:
    tn = p.label("tune")
    p.set(KTUNE, 0)
    p.emit("load 1").load(KPV).push(-1).emit("xor", "and").store(W["qy"])   # pressed now
    p.emit("load 1").store(KPV)
    held(spec.PAD_SELECT)
    p.emit(f"jz {tn}")
    p.set(KTUNE, 1)
    for bit, dv in ((spec.PAD_RIGHT, 1), (spec.PAD_LEFT, len(KNOBS) - 1)):
        ns = p.label("ksel")
        p.load(W["qy"]).push(bit).emit("and", f"jz {ns}")
        p.load(KSEL).push(dv).emit("add", "dup").push(len(KNOBS)).emit("lt", f"jz {ns}_w")
        p.emit(f"jmp {ns}_s")
        p.mark(f"{ns}_w")
        p.push(len(KNOBS)).emit("sub")
        p.mark(f"{ns}_s")
        p.store(KSEL)
        p.mark(ns)
    for k, (_, _, step, lo_, hi_) in enumerate(KNOBS):
        nk = p.label("knob")
        p.load(KSEL).push(k).emit("eq", f"jz {nk}")
        p.load(W["qy"]).push(spec.PAD_UP).emit("and", f"jz {nk}_d")
        p.load(int(KN) + k).push32(step).emit("add").push32(hi_ + 1).emit("lt", f"jz {nk}_d")
        p.addi(int(KN) + k, step).addi(int(KNOTCH) + k, 1)
        p.mark(f"{nk}_d")
        p.load(W["qy"]).push(spec.PAD_DOWN).emit("and", f"jz {nk}")
        p.push32(lo_ - 1).load(int(KN) + k).push32(step).emit("sub", "lt", f"jz {nk}")
        p.addi(int(KN) + k, -step).addi(int(KNOTCH) + k, -1)
        p.mark(nk)
    p.push(0).store(spec.REG_PAD)                 # (the game sees nothing meanwhile)
    p.mark(tn)
    # P21b: THE GLASS'S CURVE (spec.GRADE_SRC, free at the scanout): the
    # shadows sunk, the reds kept -- off, or one of two weights
    gr_ = p.label("grade")
    p.push(0)
    knob(p, "grade").push(1).emit("lt", f"jz {gr_}_1", f"jmp {gr_}")     # < 1: off
    p.mark(f"{gr_}_1")
    p.emit("drop").push(int(GRADES[0]))
    knob(p, "grade").push(2).emit("lt", f"jz {gr_}_2", f"jmp {gr_}")
    p.mark(f"{gr_}_2")
    p.emit("drop").push(int(GRADES[1]))
    p.mark(gr_)
    if L2:                                        # (time slowed: the glass sinks)
        p.load(SLOWON).emit(f"jz {gr_}_s")
        p.emit("drop").push(int(GRADES[2]))
        p.mark(f"{gr_}_s")
    p.store(spec.GRADE_SRC)
    # no shoulders in the base; and a pick-up holds him, crouched, till it is done
    if L3:
        p.emit("load 1").push(spec.PAD_R).emit("and").store(RHELD)
    p.emit("load 1").push(0xFFFF & ~((0 if L1 else spec.PAD_L) | spec.PAD_R | spec.PAD_SELECT))
    p.emit("and").store(spec.REG_PAD)
    if L4:
        # P37: R HELD ALONE CHOOSES (the player: "r shoulder alone held does
        # selection of target and hit spot with dpad. same in slow motion" --
        # and "not move when held during slow motion"). Read every frame of
        # glass, so a press in slowed time is a press. R down: the NEAREST
        # target in reach is taken (and again whenever the one he had is gone);
        # then, with L up, Left and Right step to the next target round him
        # that way, and Up and Down step the spot -- high, mid, low -- which
        # STAYS where it is put. And with R alone the pad is only that: he
        # does not walk or turn, whatever time is doing.
        sel = p.label("select")
        p.load(RHELD).push(0).emit("eq", "push 1", "xor")
        p.emit("load 1").push(spec.PAD_L).emit("and").push(0).emit("eq", "and").store(PLANT)
        p.load(RHELD).emit(f"jz {sel}_off")
        for t_ in range(NE + 1):                  # each target: where, and in reach?
            tv = p.label("tv")
            p.set(int(TV) + t_, 0)
            if t_ < NE:
                e_ = ENEMY[t_]
                p.load(e_["st"]).push(1).emit("eq", f"jz {tv}")
                xc_, zc_ = int(e_["pos"]), int(e_["pos"]) + 1
            else:
                item_exists(p).emit(f"jz {tv}")
                xc_, zc_ = int(KX), int(KZ)
            p.load(xc_).store(int(TPX) + t_).load(zc_).store(int(TPZ) + t_)
            p.load(xc_).load(PX).emit("sub").store(W["qx"]).load(zc_).load(PZ).emit("sub").store(W["qz"])
            for q_ in (W["qx"], W["qz"]):
                p.load(q_).emit("dup").push(0).emit("lt", f"jz {tv}_p{int(q_)}")
                p.push(0).emit("swap", "sub")
                p.mark(f"{tv}_p{int(q_)}")
                p.push32(int(LOCK_RANGE * ONE)).emit("lt", f"jz {tv}")
            p.load(W["qx"]).emit("dup", "mulq").load(W["qz"]).emit("dup", "mulq", "add").store(int(TD) + t_)
            p.set(int(TV) + t_, 1)
            p.mark(tv)
        # the one he has: still there? (and R only just down takes the nearest anew)
        p.push(-1).load(TSEL).emit("lt", f"jz {sel}_near")
        p.push(int(TV)).load(TSEL).emit("add", "loadi", f"jz {sel}_near")
        p.load(RPREV).emit(f"jz {sel}_near")
        p.emit("load 1").push(spec.PAD_L).emit("and", f"jz {sel}_pad", f"jmp {sel}_set")
        p.mark(f"{sel}_pad")
        for bit_, d_ in ((spec.PAD_UP, -1), (spec.PAD_DOWN, 1)):      # the spot: it steps, and stays
            sp_ = p.label("spot")
            fresh(bit_)
            p.emit(f"jz {sp_}")
            p.load(SPOT).push(d_).emit("add", "dup").push(0).emit("lt", f"jz {sp_}_a")
            p.emit("drop").push(0)
            p.mark(f"{sp_}_a")
            p.emit("dup").push(2).emit("swap", "lt", f"jz {sp_}_b")
            p.emit("drop").push(2)
            p.mark(f"{sp_}_b")
            p.store(SPOT)
            p.mark(sp_)
        fresh(spec.PAD_LEFT)
        fresh(spec.PAD_RIGHT)
        p.emit("or", f"jz {sel}_set")
        for t_ in range(NE + 1):                  # the next one round him: bearings first
            tb = p.label("tb")
            p.load(int(TV) + t_).emit(f"jz {tb}")
            p.load(int(TPX) + t_).load(PX).emit("sub").store(W["qx"])
            p.load(int(TPZ) + t_).load(PZ).emit("sub").store(W["qz"])
            p.emit(f"call {L_YAW}")
            p.load(F["brg"]).store(int(TB) + t_)
            p.mark(tb)
        # (ORDERED BY BEARING, THEN BY NUMBER: they come at him in a file, so
        # two on one bearing is the common case -- and on bearing alone the
        # second of a pair could never be reached. Left is the next key up,
        # Right the same round backwards.)
        p.push(int(TB)).load(TSEL).emit("add", "loadi").store(W["dg"])       # his own
        p.push(9000).store(W["dc"]).load(TSEL).store(W["k"])
        fresh(spec.PAD_LEFT)
        p.store(W["d2"])                          # (1: leftward -- a raised bearing)
        for t_ in range(NE + 1):
            tc = p.label("tc")
            p.load(int(TV) + t_).emit(f"jz {tc}")
            p.load(TSEL).push(t_).emit("eq", f"jz {tc}_o", f"jmp {tc}")
            p.mark(f"{tc}_o")
            p.load(int(TB) + t_).load(W["dg"]).emit("sub")
            p.load(W["d2"]).emit(f"jz {tc}_r")
            p.push(1023).emit("and").push(8).emit("mul").push(t_).emit("add").load(TSEL).emit("sub")
            p.emit(f"jmp {tc}_w")
            p.mark(f"{tc}_r")
            p.push(0).emit("swap", "sub").push(1023).emit("and").push(8).emit("mul")
            p.load(TSEL).emit("add").push(t_).emit("sub")
            p.mark(f"{tc}_w")
            p.push(8191).emit("and")
            p.emit("dup").load(W["dc"]).emit("lt", f"jz {tc}_n")
            p.store(W["dc"]).set(W["k"], t_).emit(f"jmp {tc}")
            p.mark(f"{tc}_n")
            p.emit("drop")
            p.mark(tc)
        p.load(W["k"]).store(TSEL)
        p.emit(f"jmp {sel}_set")
        p.mark(f"{sel}_near")                     # the nearest in reach, or none
        p.set(TSEL, -1).push32(0x7FFFFFFF).store(W["dc"])
        for t_ in range(NE + 1):
            tn_ = p.label("tn")
            p.load(int(TV) + t_).emit(f"jz {tn_}")
            p.load(int(TD) + t_).load(W["dc"]).emit("lt", f"jz {tn_}")
            p.load(int(TD) + t_).store(W["dc"]).set(TSEL, t_)
            p.mark(tn_)
        p.mark(f"{sel}_set")
        p.set(TOK, 0)
        p.push(-1).load(TSEL).emit("lt", f"jz {sel}")
        p.push(int(TPX)).load(TSEL).emit("add", "loadi").store(TGTX)
        p.push(int(TPZ)).load(TSEL).emit("add", "loadi").store(TGTZ)
        p.set(TOK, 1).emit(f"jmp {sel}")
        p.mark(f"{sel}_off")
        p.set(TOK, 0)
        p.mark(sel)
        p.load(RHELD).store(RPREV)
    if L2:
        # P33: ONE PRESS OF A IS ONE PRESS, WHATEVER TIME IS DOING. The jump
        # read "A's first frame down" off a count the freeze holds at zero
        # (so a press in a hitstop waits for the world): in slowed time that
        # made every running frame of a held A its first -- one press was a
        # jump AND a flip (a strafe jump went 4.1 units, not 3.1). The press
        # is latched here, every frame of glass, and read once.
        ah_ = p.label("ahold")
        p.emit("load 1").push(spec.PAD_A).emit("and", f"jz {ah_}_u")
        p.load(AHOLD).emit(f"jz {ah_}_e", f"jmp {ah_}_h")
        p.mark(f"{ah_}_e")
        p.set(APEND, 1)
        p.mark(f"{ah_}_h")
        p.addi(AHOLD, 1).emit(f"jmp {ah_}")
        p.mark(f"{ah_}_u")
        p.set(AHOLD, 0)
        p.mark(ah_)
        # P33: ANY OF THE FOUR HELD SLOWS TIME (the player: "what if gun and
        # jump/evade also have the slow down"): a strike, the gun as it is
        # held to its shot, a jump or a dodge ridden through.
        knob(p, "hold").load(GT["carve"]).emit("lt")
        knob(p, "hold").load(GT["special"]).emit("lt", "or")
        knob(p, "hold").load(GT["shoot"]).emit("lt", "or")
        knob(p, "hold").load(AHOLD).emit("lt", "or").store(SLOWON)
    pk = p.label("pick")                          # (he bows to it -- the fold the
    p.push(0).load(PICK).emit("lt", f"jz {pk}_up")   # body already has, part way -- and
    p.addi(PICK, -1).set(LANDT, LAND_FOR // 2 + 1)   # comes back up; only ABOVE zero)
    p.push(0).store(spec.REG_PAD)
    knob(p, "bow").load(F["tilt"]).emit("sub", "shr 2").load(F["tilt"]).emit("add").store(F["tilt"])
    p.emit(f"jmp {pk}")
    p.mark(f"{pk}_up")
    p.load(F["tilt"]).emit("dup").push(3).emit("add", "shr 2", "sub").store(F["tilt"])
    p.mark(pk)
# P19: A DEMON SENT IS PLACED IN THE CITY. The mover lands a fresh demon at
# its place on the ring round the origin, a frame after it is asked for
# (SPN marks which); here it is moved to where he is. In a plaza, the same
# ring round the plaza's own centre -- at the first plaza that is nothing
# at all, the fight as it always was. In a street, down one of his node's
# streets (each demon tries its own first), two nodes on: coming in.
sp_ = p.label("spn")
p.load(SPN).emit(f"jz {sp_}", )
city_node(p, PX, PZ)
p.load(CT["n"]).push(0).emit("lt", f"jz {sp_}_on")
p.set(SPN, 0).emit(f"jmp {sp_}")
p.mark(f"{sp_}_on")
p.load(CT["n"]).emit("shr 4", f"shl {TSH}").push32(int(OYA * ONE)).emit("swap", "sub")
p.store(CT["x"])                                   # the node's centre, zeta
p.load(CT["n"]).push(CS - 1).emit("and", f"shl {TSH}").push32(int(OXA * ONE))
p.emit("sub").store(CT["z"])
for d in range(3):
    sd = p.label("spd")
    p.load(SPN).push(1 << d).emit("and", f"jz {sd}")
    p.load(CT["w"]).push(0xAA).emit("and", f"jz {sd}_st")          # a plaza?
    # the plaza's centre: the corner its open sides share (E: +x, N: +y)
    # (its ring place a constant: a demon placed again was anywhere)
    p.load(CT["w"]).push(8).emit("and", f"jz {sd}_w")
    p.load(CT["z"]).push32(int(HT * ONE)).emit("add").emit(f"jmp {sd}_e")
    p.mark(f"{sd}_w")
    p.load(CT["z"]).push32(int(HT * ONE)).emit("sub")
    p.mark(f"{sd}_e")
    p.push32(RING[d][1]).emit("add").store(dslot(d, "z"))
    p.load(CT["w"]).push(2).emit("and", f"jz {sd}_s")
    p.load(CT["x"]).push32(int(HT * ONE)).emit("sub").emit(f"jmp {sd}_n")
    p.mark(f"{sd}_s")
    p.load(CT["x"]).push32(int(HT * ONE)).emit("add")
    p.mark(f"{sd}_n")
    p.push32(RING[d][0]).emit("add").store(dslot(d, "x"))
    p.emit(f"jmp {sd}_o")
    p.mark(f"{sd}_st")
    for t in range(4):
        # P20: TWO STREETS ON -- the tile is 16 now, so a demon comes from
        # the node past the next: on down the same street if it goes on,
        # else round its corner; at a dead end, the dead end
        k = (d + t) % 4
        dx, dy, _ = city.DIRS[k]
        p.load(CT["w"]).emit(f"shr {2 * k}").push(3).emit("and", f"jz {sd}_t{t}")
        p.load(CT["x"]).push32(int(-dy * TILE * ONE)).emit("add").store(dslot(d, "x"))
        p.load(CT["z"]).push32(int(dx * TILE * ONE)).emit("add").store(dslot(d, "z"))
        p.load(CT["n"]).push(CSTEP[k] + int(CMAP)).emit("add", "loadi").store(W["qy"])
        for j in (k, (k + 1) % 4, (k + 3) % 4):
            jx, jy, _ = city.DIRS[j]
            far = (12.0 if j == k else 8.0) + 1.0 * d
            nj = p.label("spj")
            p.load(W["qy"]).emit(f"shr {2 * j}").push(3).emit("and", f"jz {nj}")
            p.load(dslot(d, "x")).push32(int(-jy * far * ONE)).emit("add").store(dslot(d, "x"))
            p.load(dslot(d, "z")).push32(int(jx * far * ONE)).emit("add").store(dslot(d, "z"))
            p.emit(f"jmp {sd}_o")
            p.mark(nj)
        p.emit(f"jmp {sd}_o")
        p.mark(f"{sd}_t{t}")
    p.mark(f"{sd}_o")
    p.load(dslot(d, "x")).store(dslot(d, "ox"))
    p.load(dslot(d, "z")).store(dslot(d, "oz"))
    p.mark(sd)
p.set(SPN, 0)
p.mark(sp_)
du_ = p.label("dusk")                            # P19: his district's dusk
city_node(p, PX, PZ)
p.load(CT["n"]).push(0).emit("lt", f"jz {du_}_on", f"jmp {du_}")
p.mark(f"{du_}_on")
p.load(CT["w"]).emit("shr 23").push(15).emit("and").push(int(DUSK)).emit("add", "loadi")
p.store(spec.FOG_RGB)
if BASE:
    # P22: THE LIGHT, each frame. The town's own dark is the light knob's
    # level, a notch darker a district toward the core (to 3 of 32); what
    # burns stays at full (DIF takes up what AMB gives away). The lanterns
    # GUTTER: now and then, for two frames, a little less. And a FLASH --
    # the gate unlocked, the key taken -- lifts the dark and lets it fall.
    lt_ = p.label("light")
    knob(p, "light").load(CT["w"]).emit("shr 23").push(15).emit("and", "sub")
    p.emit("dup").push(3).emit("lt", f"jz {lt_}_a")
    p.emit("drop").push(3)
    p.mark(f"{lt_}_a")
    p.load(LFLASH).emit("add", "dup").push(32).emit("swap", "lt", f"jz {lt_}_b")   # 32 < it
    p.emit("drop").push(32)
    p.mark(f"{lt_}_b")
    p.emit("dup").store(spec.LIGHT_AMB)
    p.push(33).emit("swap", "sub")                                # what is left, to the top
    p.load(spec.REG_FRAME).emit("shr 1").push32(2654435761).emit("mul", "shr 24")
    p.push(63).emit("and").push(2).emit("lt", f"jz {lt_}_g")      # the gutter
    p.push(3).emit("sub")
    p.mark(f"{lt_}_g")
    p.store(spec.LIGHT_DIF)
    p.load(LFLASH).emit(f"jz {lt_}")
    p.addi(LFLASH, -1)
    p.mark(lt_)
# THE AMBUSH: a district's horde wakes when he walks into its plaza
p.load(CT["w"]).push(0xAA).emit("and", f"jz {du_}")
p.load(CT["w"]).emit("shr 23").push(15).emit("and").load(LVL).emit("eq", f"jz {du_}")
if not BASE:
    p.set(WOKE, 1)
p.mark(du_)
if BASE:
    # THE JAB'S CONTEXT: the district's key within reach and ahead of him
    # (1), or -- the key held -- its gate (2). The jab is then that, and
    # only then: he is never turned or drawn to it.
    kn = p.label("ctx")
    p.set(KNEAR, 0)
    if L5:
        # P38: THE NEAREST BUNKER (its hatch is drawn; standing on it, it is
        # the last he stood in), and THE HARD WAY'S PACK: asleep at its
        # street until he comes within a block of it, and home again once
        # he is two blocks gone.
        p.push32(FAR_).store(BESTB)
        for b_, (bx_, bz_) in enumerate(BUNKS):
            sb_ = f"{kn}_b{b_}"
            manhattan(p, bx_, bz_, f"{sb_}_a").emit("dup").load(BESTB).emit("lt", f"jz {sb_}_d")
            p.store(BESTB).push32(bx_).store(BKX).push32(bz_).store(BKZ)
            if L7:                                 # (P40: the last bunker is the one whose door he took)
                p.emit(f"jmp {sb_}")
            else:
                p.load(BESTB).push(int(2.0 * ONE)).emit("lt", f"jz {sb_}")
                p.set(LASTB, b_).emit(f"jmp {sb_}")
            p.mark(f"{sb_}_d")
            p.emit("drop")
            p.mark(sb_)
        if L7:
            # P40: IN THE ROOMS the six are the ring's -- they stand round
            # its middle and face him, to be fought (they do not strike) --
            # and the prep table is in reach, or not
            manhattan(p, *DESK_XZ, f"{kn}_dk").push32(int(3.4 * ONE)).emit("lt").load(INSIDE).emit("and").store(DESKN)
            p.load(INSIDE).emit(f"jz {kn}_out")
            p.set(PACK, 0).push32(RING_XZ[0]).store(PKX).push32(RING_XZ[1]).store(PKZ).emit(f"jmp {kn}_pk")
            p.mark(f"{kn}_out")
        manhattan(p, *PACK_HOME, f"{kn}_ph").store(W["qx"])
        p.load(PACK).emit(f"jz {kn}_pz")
        p.push32(int(34 * ONE)).load(W["qx"]).emit("lt", f"jz {kn}_pe")     # (34 < d: he is gone)
        p.set(PACK, 0).emit(f"jmp {kn}_pe")
        p.mark(f"{kn}_pz")
        p.load(W["qx"]).push32(int(16 * ONE)).emit("lt", f"jz {kn}_pe")
        p.set(PACK, 1)
        p.mark(f"{kn}_pe")
        p.push32(PACK_HOME[0]).store(PKX).push32(PACK_HOME[1]).store(PKZ)
        p.load(PACK).emit(f"jz {kn}_pk")
        p.load(PX).store(PKX).load(PZ).store(PKZ)
        p.mark(f"{kn}_pk")
        # P38: THE WORLD'S ITEMS. The nearest key not yet taken, and the
        # nearest door still shut (by the place to stand on his side of
        # it); the nearer of the two is THE ITEM -- what the jab, the lock
        # and the shot know. Every key and door is the cart's own constant:
        # the search is written out, one a thing.
        p.set(K5, -1).set(D5, -1).set(DCAN, 0).push32(FAR_).store(BESTK).push32(FAR_).store(BESTD)
        for g_, (kx_, kz_) in enumerate(KEYAT):
            sk = f"{kn}_k{g_}"
            p.load(TAKEN).push(1 << g_).emit("and", f"jz {sk}_o", f"jmp {sk}")
            p.mark(f"{sk}_o")
            manhattan(p, kx_, kz_, f"{sk}_a").emit("dup").load(BESTK).emit("lt", f"jz {sk}_d")
            p.store(BESTK).set(K5, g_).set(KYB, 1 << g_).push32(kx_).store(KYX).push32(kz_).store(KYZ)
            p.emit(f"jmp {sk}")
            p.mark(f"{sk}_d")
            p.emit("drop")
            p.mark(sk)
        for i_, d_ in enumerate(DOORS):
            sd = f"{kn}_d{i_}"
            p.load(OPENED).push(1 << i_).emit("and", f"jz {sd}_o", f"jmp {sd}")
            p.mark(f"{sd}_o")
            manhattan(p, *d_["pa"], f"{sd}_a").store(W["qx"])
            manhattan(p, *d_["pb"], f"{sd}_b").store(W["qz"])
            p.load(W["qx"]).load(W["qz"]).emit("lt", f"jz {sd}_fb")
            for side_, q_ in (("pa", W["qx"]), ("pb", W["qz"])):
                p.load(q_).load(BESTD).emit("lt", f"jz {sd}")
                p.load(q_).store(BESTD).set(D5, i_).set(DRB, 1 << i_)
                p.set(DRK, (1 << d_["key"]) if d_["kind"] == 0 else 0)
                p.push32(d_[side_][0]).store(DRX).push32(d_[side_][1]).store(DRZ)
                p.set(DRY, d_["yaw"]).set(DRM, GATE_M if d_["kind"] == 0 else BOLT_M)
                if d_["kind"] == 0:                    # a gate: its key in hand, from either side
                    p.load(KEYS).push(1 << d_["key"]).emit("and").store(DCAN)
                else:                                  # a bolt: from its own side only
                    p.set(DCAN, 1 if side_ == "pa" else 0)
                p.emit(f"jmp {sd}")
                if side_ == "pa":
                    p.mark(f"{sd}_fb")
            p.mark(sd)
        if L7:
            p.push32(FAR_).store(BESTT)
            for t_, d_ in enumerate(TDOORS):
                st_ = f"{kn}_t{t_}"
                manhattan(p, *d_["at"], f"{st_}_a").emit("dup").load(BESTT).emit("lt", f"jz {st_}_d")
                p.store(BESTT).set(TDT, t_).push32(d_["at"][0]).store(TDX).push32(d_["at"][1]).store(TDZ)
                p.set(TDY, d_["yaw"]).emit(f"jmp {st_}")
                p.mark(f"{st_}_d")
                p.emit("drop")
                p.mark(st_)
            p.set(ITK, 0)
            p.load(BESTT).load(BESTK).emit("lt").load(BESTT).load(BESTD).emit("lt", "and", f"jz {kn}_nt")
            p.set(ITEM, 1).set(KEY, 1).set(ITK, 2).set(DCAN, 1).load(TDX).store(KX).load(TDZ).store(KZ)
            p.push32(int(3.9 ** 2 * ONE)).store(W["d2"]).emit(f"jmp {kn}_t")
            p.mark(f"{kn}_nt")
        p.load(K5).push(0).emit("lt", f"jz {kn}_hk")
        p.load(D5).push(0).emit("lt", f"jz {kn}_door")
        p.set(ITEM, 0).emit(f"jmp {kn}")                             # (nothing left: no item)
        p.mark(f"{kn}_hk")
        p.load(BESTD).load(BESTK).emit("lt", f"jz {kn}_key")
        p.mark(f"{kn}_door")
        if L7:
            p.set(ITK, 1)
        p.set(ITEM, 1).set(KEY, 1).load(DRX).store(KX).load(DRZ).store(KZ)
        p.push32(int(3.9 ** 2 * ONE)).store(W["d2"]).emit(f"jmp {kn}_t")
        p.mark(f"{kn}_key")
        p.set(ITEM, 1).set(KEY, 0).load(KYX).store(KX).load(KYZ).store(KZ)
        p.push32(int(1.4 ** 2 * ONE)).store(W["d2"])
    else:
        p.load(LVL).push(len(GATES)).emit("lt", f"jz {kn}")          # (the last district: none)
        p.load(KEY).emit(f"jz {kn}_k")
        p.load(LVL).push(GT_N).emit("mul").push(int(GATE_T) + 4).emit("add", "dup", "loadi").store(KX)
        p.push(1).emit("add", "loadi").store(KZ)
        p.push32(int(3.9 ** 2 * ONE)).store(W["d2"]).emit(f"jmp {kn}_t")
        p.mark(f"{kn}_k")
        p.push(int(KEYPOS)).load(LVL).push(2).emit("mul", "add", "dup", "loadi").store(KX)
        p.push(1).emit("add", "loadi").store(KZ)
        p.push32(int(1.4 ** 2 * ONE)).store(W["d2"])
    p.mark(f"{kn}_t")
    p.load(KX).load(PX).emit("sub").store(W["qx"]).load(KZ).load(PZ).emit("sub").store(W["qz"])
    # (NEAR ON EACH AXIS FIRST: a square of more than 181 units overflows the
    # word and reads as a small one -- across town from the key, the jab
    # would have picked it up. Found by a test that happened to stand there.)
    for q_ in (W["qx"], W["qz"]):
        p.load(q_).emit("dup").push(0).emit("lt", f"jz {kn}_p{int(q_)}")
        p.push(0).emit("swap", "sub")
        p.mark(f"{kn}_p{int(q_)}")
        p.push32(8 * ONE).emit("lt", f"jz {kn}")
    p.load(W["qx"]).emit("dup", "mulq").load(W["qz"]).emit("dup", "mulq", "add")
    p.load(W["d2"]).emit("lt", f"jz {kn}")                       # in reach
    sin_of(p, 256)
    p.load(W["qz"]).emit("mulq")
    sin_of(p)
    p.load(W["qx"]).emit("mulq", "sub")                          # fwd . to it
    p.push(0).emit("swap", "lt", f"jz {kn}")                     # ahead
    if L5:                                                       # (a door he cannot open: no jab's
        p.load(KEY).emit(f"jz {kn}_can")                         # context -- a gate without its key,
        p.load(DCAN).emit(f"jz {kn}")                            # a bolt from the wrong side)
        p.mark(f"{kn}_can")
        if L7:                                                   # (P40: nor one of the range's items: the
            p.load(KEY).emit(f"jz {kn}_pt", f"jmp {kn}_ptx")     # jab STRIKES those, it does not take them)
            p.mark(f"{kn}_pt")
            p.push(NKEYS - 1).load(K5).emit("lt", f"jz {kn}_ptx", f"jmp {kn}")
            p.mark(f"{kn}_ptx")
    p.load(KEY).push(1).emit("add").store(KNEAR)
    p.mark(kn)
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
p.set(spec.OVL_LEN, PAGE).set(spec.OVL_GO, 1)
p.mark(pa_)
p.load(PX).store(AR["ox"]).load(PZ).store(AR["oz"])     # where he stood
L = {k: p.label(k) for k in ("dead", "frozen", "free", "walk", "idle",
                             "motion", "anim", "pi", "pj", "pd", "iw",
                             "notap", "brk", "hook", "tapd", "nobuf", "busy",
                             "hurt", "launch", "turnd", "pm", "ph")}
# P18: FOCUS. Targeting, an attack held past a tap slows the world to a
# third until it is let go; a launcher that lands does it for a second.
# The slow is a FREEZE two frames in three -- his and theirs, the hitstop's
# own path -- so everything keeps its rhythm in the fight's time, and the
# buttons are read through it. f_skip is the phase: 0 runs, 1 and 2 hold.
fc = p.label("focus")
GEST = p.label("gest")                           # (the grammar, below)
p.load(F["slow"]).emit(f"jz {fc}_n", f"jmp {fc}_s")   # (counted in the fight's
p.mark(f"{fc}_n")                                     # time: on running frames)
if L2:
    # P30: A BUTTON HELD SLOWS TIME (the player: "each button can get held
    # keeping the string, slowing time and releasing ... the slow motion
    # gives time to think"). Past the hold knob's frames the fight -- his own
    # blow too -- runs one frame in the slow knob's; let go, and it runs.
    p.load(SLOWON).emit(f"jz {fc}_o")
else:
    p.load(F["sty"]).push(SQ_TARGET).emit("eq", f"jz {fc}_o")
    p.push(FOCUS_HOLD).load(GT["carve"]).emit("lt")
    p.push(FOCUS_HOLD).load(GT["special"]).emit("lt", "or", f"jz {fc}_o")
p.mark(f"{fc}_s")
p.load(F["skip"]).push(1).emit("add", "dup")
(knob(p, "slow") if L2 else p.push(SLOW_EVERY)).emit("lt", f"jz {fc}_w")
p.store(F["skip"]).emit(f"jmp {fc}")
p.mark(f"{fc}_w")
p.emit("drop")
p.load(F["slow"]).emit(f"jz {fc}_o")
p.addi(F["slow"], -1)
p.mark(f"{fc}_o")
p.set(F["skip"], 0)
p.mark(fc)
p.load(F["dead"]).emit(f"jz {L['dead']}_no", f"jmp {L['dead']}")
p.mark(f"{L['dead']}_no")
p.load(F["skip"]).emit(f"jz {fc}_r")             # a held frame: listen, and hold
p.emit(f"call {GEST}")
p.set(GT["jump"], 0).emit(f"jmp {L['frozen']}")
p.mark(f"{fc}_r")
# P16: THE FREEZE STILL LISTENS. A landed blow stops the world for its
# hitstop, and until now it stopped the buttons too: on the first tape of
# real play (docs/TND-PORT.md, P16) a third of every press began inside a
# freeze -- 39 of 116 on the haymaker's own button -- and was simply lost.
# The grammar below is a subroutine now, run in the freeze as well: a press
# in the stop is buffered and thrown the moment the body is free (the
# buffer does not age while frozen). The jump is the one press that is not
# buffered -- it fires on its first held frame -- so its count is held at
# zero through the freeze and that frame comes when the world moves again.
p.load(F["stop"]).emit(f"jz {L['frozen']}_no")
p.addi(F["stop"], -1).emit(f"call {GEST}")
p.set(GT["jump"], 0).emit(f"jmp {L['frozen']}")
p.mark(f"{L['frozen']}_no")
if L2:
    # P34: THE GUN IS DRAWN WHILE B IS DOWN (the player: "next we work on the
    # gunplay, make it feel more tactical too"). The shot is B's release, as
    # ever -- but the five frames a shot took to come up after it are now
    # spent while the button is held: a frame of draw for each frame down,
    # and the shot starts that far in. Held five frames, it fires the frame
    # after he lets go. (Let go, the gun comes down as it came up.)
    gd_ = p.label("gundraw")
    held(spec.PAD_B)
    p.emit(f"jz {gd_}_u")
    p.load(DRAW).push(DRAW_MAX).emit("lt", f"jz {gd_}")
    p.addi(DRAW, 1).emit(f"jmp {gd_}")
    p.mark(f"{gd_}_u")
    p.load(DRAW).emit(f"jz {gd_}")
    p.addi(DRAW, -1)
    p.mark(gd_)
    # P35: AIMING (the player, of P34 on glass: "just needs some fixing on
    # the movement when in slow motion gun drawn"). On the tape he held B for
    # up to eighteen seconds and tapped Left and Right to bring the sight
    # round -- and each tap threw his body a quarter turn to that side of his
    # steering (the pad was still the shot's way) while his steering crept a
    # notch a frame under it. Now: B held PAST the hold knob, he is aiming.
    # His steering comes round to where his body points (the boxer's cross
    # too) -- once -- and from then the pad moves him as it does with no
    # button down: Left and Right TURN him (finely: below), Up and Down walk
    # him, and the shot goes where he faces. A direction with a FRESH B is
    # still a shot that way.
    # (the aim is taken up below, once this frame's buttons are read)
    if L3:
        # P35: THE LOCK (the player: "do the targeting now too. right shoulder,
        # use the item as the target" -- and, of P18, his own: "R = targeting:
        # planted"). R held, the district's item in reach of it (the key; the
        # key held, its gate), he squares up to it: his steering -- in the
        # boxer, his cross -- comes round to its bearing and stays on it, his
        # body with it. He is planted (the tank neither walks nor turns; the
        # dodges and the boxer's steps are his, round it), and a blow or a
        # shot goes AT it, whatever the pad says. Not in the run.
        # P36: IN THE RUN TOO -- there the lock does not turn him (the run
        # steers ROUND it, below); and his superman punch stops at the item.
        lk3 = p.label("lock3")
        p.load(RSHOT).emit(f"jz {lk3}_rs")
        p.addi(RSHOT, -1)
        p.mark(f"{lk3}_rs")
        p.load(SJD).push(5).emit("eq", f"jz {lk3}_sm")
        p.load(TGX).load(PX).emit("sub", "dup", "mulq").load(TGZ).load(PZ).emit("sub", "dup", "mulq", "add")
        p.push32(int((SUPER_STOP / ONE) ** 2 * ONE)).emit("lt", f"jz {lk3}_sm")
        p.set(F["vx"], 0).set(F["vz"], 0)
        p.mark(f"{lk3}_sm")
        p.set(LOCK, 0)
        p.load(RHELD).emit(f"jz {lk3}_np")
        p.emit("load 1").push(15).emit("and", f"jz {lk3}_np", f"jmp {lk3}_pd")
        p.mark(f"{lk3}_np")                       # (no R, or no pad: the next circle is a new one)
        p.set(RPAD, 0)
        p.mark(f"{lk3}_pd")
        p.load(RHELD).emit(f"jz {lk3}")
        if L4:
            p.load(TOK).emit(f"jz {lk3}")
        else:
            p.load(LVL).push(len(GATES)).emit("lt", f"jz {lk3}")
        p.load(TGX).load(PX).emit("sub").store(W["qx"]).load(TGZ).load(PZ).emit("sub").store(W["qz"])
        for q_ in (W["qx"], W["qz"]):
            p.load(q_).emit("dup").push(0).emit("lt", f"jz {lk3}_p{int(q_)}")
            p.push(0).emit("swap", "sub")
            p.mark(f"{lk3}_p{int(q_)}")
            p.push32(int(LOCK_RANGE * ONE)).emit("lt", f"jz {lk3}")
        p.emit(f"call {L_YAW}")
        p.load(F["brg"]).store(LBRG).set(LOCK, 1)
        p.load(F["sty"]).push(1).emit("eq", f"jz {lk3}_sq", f"jmp {lk3}")
        p.mark(f"{lk3}_sq")
        p.set(TURNED, 0)
        p.load(F["sty"]).push(2).emit("eq", f"jz {lk3}_t")
        p.load(F["latch"]).store(YAW)
        p.mark(f"{lk3}_t")
        p.load(F["brg"]).store(W["head"]).push(LOCK_TURN).store(W["dg"]).emit(f"call {L_STEER}")
        p.load(YAW).store(F["latch"])
        p.mark(lk3)
    if L4:
        # P37: THE ENEMIES MOVE (the player: "lets have then move and make them
        # target able"). Each, up: held by a blow it stands; else it walks to
        # ITS PLACE in the ring round him (its size's stand-off out, on its own
        # bearing), turning as it goes (E_TURN a frame) at its size's pace, a
        # wall a wall for it too; there -- or stopped by a wall -- it stands in
        # its guard and turns to face him. Down, it lies DOWN_FOR frames and is
        # back where it began.
        for e_ in ENEMY:
            ea = p.label("enemy")
            ex_, ez_ = int(e_["pos"]), int(e_["pos"]) + 1

            def e_turn(ea=ea, e_=e_):             # ( -- ) its heading toward (w_qx, w_qz), E_TURN at most
                tl = p.label("eturn")
                p.emit(f"call {L_YAW}")
                p.load(F["brg"]).load(e_["yaw"]).emit("sub").push(512).emit("add").push(1023).emit("and").push(512).emit("sub")
                p.emit("dup").push(E_TURN).emit("swap", "lt", f"jz {tl}_1")
                p.emit("drop").push(E_TURN)
                p.mark(f"{tl}_1")
                p.emit("dup").push(-E_TURN).emit("lt", f"jz {tl}_2")
                p.emit("drop").push(-E_TURN)
                p.mark(f"{tl}_2")
                p.load(e_["yaw"]).emit("add").push(1023).emit("and").store(e_["yaw"])
            p.load(e_["st"]).push(1).emit("eq", f"jz {ea}_dn")
            p.load(e_["stun"]).emit(f"jz {ea}_free")
            p.addi(e_["stun"], -1).set(e_["walk"], 0).emit(f"jmp {ea}")
            p.mark(f"{ea}_free")
            p.set(e_["walk"], 0)
            p.load(PKX if L5 else PX).push32(e_["rx"]).emit("add").load(ex_).emit("sub").store(W["qx"])
            p.load(PKZ if L5 else PZ).push32(e_["rz"]).emit("add").load(ez_).emit("sub").store(W["qz"])
            for q_ in (W["qx"], W["qz"]):         # (across town: it waits)
                p.load(q_).emit("dup").push(0).emit("lt", f"jz {ea}_p{int(q_)}")
                p.push(0).emit("swap", "sub")
                p.mark(f"{ea}_p{int(q_)}")
                p.push32(int(40 * ONE)).emit("lt", f"jz {ea}_clk")
            p.load(W["qx"]).emit("dup", "mulq").load(W["qz"]).emit("dup", "mulq", "add")
            p.push(int(0.3 ** 2 * ONE)).emit("swap", "lt", f"jz {ea}_idle")       # 0.09 < d2: not there yet
            e_turn()
            p.load(ex_).store(int(e_["old"])).load(ez_).store(int(e_["old"]) + 1)
            sin_of(p, cell=e_["yaw"])
            p.push(e_["T"]["pace"]).emit("mulq").load(ex_).emit("swap", "sub").store(ex_)
            sin_of(p, 256, cell=e_["yaw"])
            p.push(e_["T"]["pace"]).emit("mulq").load(ez_).emit("add").store(ez_)
            keep_in_arena(e_["pos"], int(e_["pos"]) + 1, e_["old"], int(e_["old"]) + 1)
            p.load(ex_).load(int(e_["old"])).emit("eq").load(ez_).load(int(e_["old"]) + 1).emit("eq", "and")
            p.emit(f"jz {ea}_went", f"jmp {ea}_idle")                             # (a wall has it: it stands)
            p.mark(f"{ea}_went")
            p.addi(e_["ph"], e_["T"]["pace"] * E_LEGS).set(e_["walk"], 1).emit(f"jmp {ea}")
            p.mark(f"{ea}_idle")
            p.load(PX).load(ex_).emit("sub").store(W["qx"]).load(PZ).load(ez_).emit("sub").store(W["qz"])
            e_turn()
            p.mark(f"{ea}_clk")
            p.addi(e_["clk"], 1).load(e_["clk"]).push(2 * e_["T"]["n"]).emit("lt", f"jz {ea}_w", f"jmp {ea}")
            p.mark(f"{ea}_w")
            p.set(e_["clk"], 0).emit(f"jmp {ea}")
            p.mark(f"{ea}_dn")
            p.load(e_["st"]).push(2).emit("eq", f"jz {ea}")
            p.addi(e_["t"], 1).push(DOWN_FOR).load(e_["t"]).emit("lt", f"jz {ea}")
            if L5:                                # (P38: back at the hard way it holds)
                p.push32(PACK_HOME[0] + e_["rx"]).store(ex_).push32(PACK_HOME[1] + e_["rz"]).store(ez_)
            else:
                p.set(ex_, START_X + e_["dx"]).set(ez_, START_Z + e_["dz"])
            p.set(e_["st"], 1).set(e_["hp"], e_["T"]["hp"]).set(e_["stun"], 0).set(e_["walk"], 0)
            p.mark(ea)
    # THE CYLINDER: the mag knob's rounds. The last one gone, it is RELOAD
    # frames before the gun is full again -- or a terminator thrown fills it
    # at once (the launch): the fists load the gun.
    rl_ = p.label("reload")
    p.load(RLD).emit(f"jz {rl_}")
    p.addi(RLD, -1)
    p.load(RLD).emit(f"jz {rl_}_d", f"jmp {rl_}")
    p.mark(f"{rl_}_d")
    p.set(SHOTS, 0)
    p.mark(rl_)
    # THE BULLETS FLY in the fight's time (slowed, they are seen to), and
    # land where the sight said they would
    for k_, B_ in enumerate(BUL):
        nb = p.label("bul")
        p.load(B_["rem"]).emit(f"jz {nb}")
        p.load(B_["rem"]).push32(BULLET_V).emit("sub", "dup").push(1).emit("lt", f"jz {nb}_f")
        p.emit("drop").set(B_["rem"], 0)
        p.set(W["k"], k_).emit(f"call {L_LAND}", f"jmp {nb}")
        p.mark(f"{nb}_f")
        p.store(B_["rem"])
        p.mark(nb)

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
# P18: THE RHYTHM's strings -- state: ((steady move, next), (wait move, next))
CMB = {1: ((1, 2), (2, 4)),                      # jab, then: cross / (wait) lead hook
       2: ((2, 3), (3, 0)),                      # jab cross, then: lead hook / (wait) rear hook
       3: ((6, 0), (6, 0)),                      # ...the rear uppercut, the launcher
       4: ((6, 0), (6, 0))}                      # (state 0, or a new string: the jab)
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
lt_ = p.label("ltap")                             # P18: the rhythm counts from the END
p.load(ANIM).push(2).emit("eq", f"jz {lt_}")      # of the string's last blow: while
p.load(F["mv"]).push(MOVE["special"]).emit("eq", f"jz {lt_}_s", f"jmp {lt_}")   # one is
p.mark(f"{lt_}_s")                                # thrown (not the special, not a shot)
p.load(F["mv"]).push(MOVE["gun"]).emit("lt", f"jz {lt_}")   # the clock stands at zero
p.set(F["ltap"], 0)
p.mark(lt_)
if L2:
    # P30: THE STRING STANDS while a blow is out, while a button is held, and
    # for the keep knob's frames after -- no beat to hit: mashed or slow, the
    # count is the count.
    # P32: ...and TIME SLOWED, THE PAD MOVES HIM. The string's lock (no walk,
    # no turn, for 10 frames after its blow) was held on for as long as a
    # button was: on the tape he held Up in the tank for 41 seconds of
    # slowed time and stood still. Slowed, the clock is held just past the
    # lock -- the count kept, his legs his own.
    kp_ = p.label("keep")
    p.load(SLOWON).emit(f"jz {kp_}_n")
    p.set(F["ltap"], TURN_LOCK + 1)
    p.mark(f"{kp_}_n")
    knob(p, "keep").load(F["ltap"]).emit("lt", f"jz {kp_}")
    p.set(F["c3"], 0)
    p.mark(kp_)
p.load(F["buf"]).emit(f"jz {L['nobuf']}")
p.addi(F["buf"], -1)
p.load(F["buf"]).emit(f"jz {L['nobuf']}_x", f"jmp {L['nobuf']}")   # P18: a blow that
p.mark(f"{L['nobuf']}_x")                         # expired unthrown takes the string
p.set(F["c3"], 0)                                 # with it (or it would be skipped)
p.mark(L["nobuf"])
p.emit(f"call {GEST}", f"jmp {GEST}_end")
p.mark(GEST)
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
        p.load(F["sty"]).push(SQ_TARGET).emit("eq", f"jz {hd}_t", f"jmp {done}")
        p.mark(f"{hd}_t")                                  # (P18: targeting holds it --
        p.load(GT[b]).push(1 if L2 else CHORD_SLOP + 1).emit("eq", f"jz {done}")   # FOCUS -- and it
        p.set(GTAP[b], 1).set(GC[b], 1)                    # fires on release) (spent)
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
        if L2:                        # (P34: reloading, there is no shot)
            p.load(RLD).emit(f"jz {ns}_m", f"jmp {ns}")
            p.mark(f"{ns}_m")
        p.push(CHARGE - 1).load(GT[b]).emit("lt", f"jz {ns}_p")
        choose(MOVE["gun_charged"])
        p.addi(F["sec"], 1).emit(f"jmp {ns}")        # (P18: a shot in the string)
        p.mark(f"{ns}_p")
        choose(MOVE["gun"])
        p.addi(F["sec"], 1)
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


# (P18: no chords -- the launchers come from the rhythm, and A is the dodge)
# the special: its own tap
sp = p.label("g_sp")
p.load(GTAP["special"]).emit(f"jz {sp}")          # (P30, layer 2: Y is the string's
choose(MOVE["special"])                           # TERMINATOR -- which, the launch says)
p.mark(sp)
# the carve string
p.load(GTAP["carve"]).emit(f"jz {L['notap']}")
if BASE:
    cx_ = p.label("ctxdo")
    p.load(KNEAR).emit(f"jz {cx_}")
    if not L5:
        p.load(ANIM).push(2).emit("eq", f"jz {cx_}_a", f"jmp {cx_}")   # (mid-swing: a jab)
        p.mark(f"{cx_}_a")
    # (P38, his first tape of the world: he came to gate 5 with its key in
    # the middle of a string -- fourteen jabs in ten seconds at a gate that
    # stood outlined, every one "mid-swing: a jab", and it opened only when
    # he stopped. In the world the jab that reaches a key or an open-able
    # door is that, string or no string.)
    p.load(KNEAR).push(1).emit("eq", f"jz {cx_}_g")
    if L5:
        # P38: the key is one of several in hand; the door is whichever
        # stands here -- a gate eats its key, a bolt asks none
        p.load(KEYS).load(KYB).emit("or").store(KEYS).load(TAKEN).load(KYB).emit("or").store(TAKEN)
        p.set(LFLASH, 6).emit(f"jmp {cx_}_do")
        p.mark(f"{cx_}_g")
        if L7:
            # P40: THROUGH A BUNKER'S DOOR. In: he stands inside the hub's
            # door, facing the room; that bunker is the one he will leave
            # by; its survey is his (its sector and the next along); the six
            # are in the ring. Out: at the door he came in by, facing its
            # street; the six are back at their hard way.
            NB_ = len(TDOORS) - 1
            p.load(ITK).push(2).emit("eq", f"jz {cx_}_og")
            p.load(TDT).push(NB_).emit("eq", f"jz {cx_}_in")
            for b_, d_ in enumerate(TDOORS[:NB_]):
                p.load(LASTB).push(b_).emit("eq", f"jz {cx_}_o{b_}")
                p.push32(d_["out"][0]).store(PX).push32(d_["out"][1]).store(PZ)
                p.set(YAW, d_["out_yaw"]).set(CY, d_["out_yaw"]).set(HEAD, d_["out_yaw"])
                p.mark(f"{cx_}_o{b_}")
            p.set(INSIDE, 0)
            for e_ in ENEMY:
                p.push32(PACK_HOME[0] + e_["rx"]).store(int(e_["pos"])).push32(PACK_HOME[1] + e_["rz"]).store(int(e_["pos"]) + 1)
            p.emit(f"jmp {cx_}_td")
            p.mark(f"{cx_}_in")
            p.load(TDT).store(LASTB).set(INSIDE, 1)
            p.push(int(KNOW_T)).load(TDT).emit("add", "loadi").load(KNOWN).emit("or").store(KNOWN)
            p.push32(TDOORS[NB_]["out"][0]).store(PX).push32(TDOORS[NB_]["out"][1]).store(PZ)
            p.set(YAW, TDOORS[NB_]["out_yaw"]).set(CY, TDOORS[NB_]["out_yaw"]).set(HEAD, TDOORS[NB_]["out_yaw"])
            for e_ in ENEMY:
                p.push32(RING_XZ[0] + e_["rx"]).store(int(e_["pos"])).push32(RING_XZ[1] + e_["rz"]).store(int(e_["pos"]) + 1)
                p.set(e_["st"], 1).set(e_["hp"], e_["T"]["hp"]).set(e_["stun"], 0).set(e_["walk"], 0)
            p.mark(f"{cx_}_td")
            p.set(LFLASH, 20).emit(f"jmp {cx_}_do")
            p.mark(f"{cx_}_og")
        p.load(OPENED).load(DRB).emit("or").store(OPENED)
        p.load(DRK).push32(0xFFFFFFFF).emit("xor").load(KEYS).emit("and").store(KEYS)
        p.set(LFLASH, 20)
        for half in (0, 2):
            p.load(D5).push(4).emit("mul").push(int(DOOR_T) + half).emit("add")
            p.emit("dup", "loadi").push(int(CMAP)).emit("add", "dup", "loadi")
            p.emit("swap").store(CT["k"])
            p.emit("swap").push(1).emit("add", "loadi", "or")
            p.load(CT["k"]).emit("storei")
    else:
        p.set(KEY, 1).set(LFLASH, 6).emit(f"jmp {cx_}_do")             # the key: his
        p.mark(f"{cx_}_g")                                             # the gate: open
        p.set(KEY, 0).addi(LVL, 1).set(LFLASH, 20)
        for half in (0, 2):
            p.load(LVL).push(GT_N).emit("mul").push(int(GATE_T) - GT_N + half).emit("add")
            p.emit("dup", "loadi").push(int(CMAP)).emit("add", "dup", "loadi")
            p.emit("swap").store(CT["k"])
            p.emit("swap").push(1).emit("add", "loadi", "or")
            p.load(CT["k"]).emit("storei")
    p.mark(f"{cx_}_do")
    knob(p, "pick").store(PICK)
    p.set(KNEAR, 0).set(WSPD, 0)
    p.emit(f"jmp {L['notap']}")
    p.mark(cx_)
# P18: THE RHYTHM. The gap since the string's last blow ENDED says which
# string this is: a tap during it or within STEADY keeps time; to PAUSE it
# is a WAIT; past that a new string. (A tap while the string's next blow
# still waits in the buffer is that same beat, not another: mashing does not
# skip ahead to the finisher.) (2 x state + wait) indexes CMB, each word a move and the next
# state (move | state << 4):
#   X X X X        jab, cross, lead hook, rear uppercut (the launcher)
#   X - X X        jab, (wait) lead hook, rear uppercut
#   X X - X        jab, cross, (wait) rear hook
# Shots may fill a wait; more than SEC_MAX of them and the string is lost.
if L2:
    # P30: THE COUNT (the player: "the number of times we press the jab it
    # builds to a special terminator ... A player could in theory just button
    # mash fast, and still get combos to work, not working off a specific time
    # signature"). X is a jab, every time, the press's own frame; the launch
    # counts it. No rhythm is read.
    choose(MOVE["jab"])
else:
    rh = p.label("rhythm")
    p.load(F["buf"]).emit(f"jz {rh}_q")               # a blow of the string still waiting
    p.load(F["bmv"]).push(MOVE["special"]).emit("eq", f"jz {rh}_b", f"jmp {rh}_q")   # in the
    p.mark(f"{rh}_b")                                 # buffer: this tap is the same beat
    p.load(F["bmv"]).push(MOVE["gun"]).emit("lt", f"jz {rh}_q", f"jmp {L['notap']}")
    p.mark(f"{rh}_q")
    p.push(0)
    p.push(STEADY).load(F["ltap"]).emit("lt", f"jz {rh}_c")
    p.emit("drop").push(1)
    p.push(PAUSE).load(F["ltap"]).emit("lt", f"jz {rh}_c")
    p.set(F["c3"], 0)                                 # too long: a new string
    p.mark(f"{rh}_c")
    p.push(SEC_MAX).load(F["sec"]).emit("lt", f"jz {rh}_s")
    p.set(F["c3"], 0)                                 # too many shots: lost
    p.mark(f"{rh}_s")
    p.store(W["dc"])                                  # (in code: memory has no room for
    rd_ = p.label("rdone")                            # a table)
    for st_, ((ms, ns_), (mw, nw_)) in CMB.items():
        nx = p.label("rs")
        p.load(F["c3"]).push(st_).emit("eq", f"jz {nx}")
        p.load(W["dc"]).emit(f"jz {nx}_s")
        p.push(mw).set(F["c3"], nw_).emit(f"jmp {rd_}")
        p.mark(f"{nx}_s")
        p.push(ms).set(F["c3"], ns_).emit(f"jmp {rd_}")
        p.mark(nx)
    p.push(0).set(F["c3"], 1)                         # the jab opens a string
    p.mark(rd_)
    choose(mv_cell_ops=())
    p.set(F["ltap"], 0).set(F["sec"], 0)
p.mark(L["notap"])
p.emit("ret")
p.mark(f"{GEST}_end")
if L2:
    # P35: AIMING begins the frame B's hold passes the knob -- read here,
    # after the buttons, so it is the SAME frame the tank is first let turn
    # (a frame later, that first turn was a whole notch).
    am_ = p.label("aim")
    knob(p, "hold").load(GT["shoot"]).emit("lt", f"jz {am_}_n")
    p.load(AIMED).emit(f"jz {am_}_e", f"jmp {am_}")
    p.mark(f"{am_}_e")
    p.load(F["sty"]).push(1).emit("eq", f"jz {am_}_s", f"jmp {am_}")
    p.mark(f"{am_}_s")
    p.load(HEAD).emit("dup").store(YAW).store(F["latch"])
    p.set(TURNED, 0).set(AIMED, 1).set(ATURN, 0).emit(f"jmp {am_}")
    p.mark(f"{am_}_n")                                     # (B up and no shot waiting: it is over)
    p.load(GT["shoot"]).load(F["buf"]).emit("or", f"jz {am_}_c", f"jmp {am_}")
    p.mark(f"{am_}_c")
    p.set(AIMED, 0)
    p.mark(am_)
# THE JUMP: X's press, at once -- unless A is down (carve+jump launches)
jp = p.label("jump")
if L2:
    p.load(APEND).emit(f"jz {jp}")                # (P33: the press, latched: read once)
    p.set(APEND, 0)
else:
    p.load(GT["jump"]).push(1).emit("eq", f"jz {jp}")   # (P18: no chords)
p.load(F["py"]).load(F["acmb"]).emit("or", f"jz {jp}_g", f"jmp {jp}_fl")   # aloft: flip?
p.mark(f"{jp}_g")
dg_ = p.label("dodge")                           # P18: THE DODGE is A in the tank
p.load(F["sty"]).push(SQ_TARGET).emit("eq")      # and in targeting -- the way the
p.load(F["sty"]).push(0).emit("eq", "or", f"jz {dg_}")   # pad points, or back
p.load(F["uwin"]).emit(f"jz {dg_}_u")            # (a launcher's window: A follows
p.emit(f"call {L_FOE}")                          # the body up instead)
p.load(F["foe"]).push(0).emit("lt", f"jz {dg_}")
p.mark(f"{dg_}_u")
p.load(F["evf"]).emit(f"jz {dg_}_a", f"jmp {jp}")
p.mark(f"{dg_}_a")
dcn = p.label("dcan")                            # it CANCELS a swing's recovery
p.load(ANIM).push(2).emit("eq", f"jz {dcn}")     # (not its windup or live frames:
p.load(AF)                                       # a blow thrown is thrown)
row(PMT, F["mv"], "endact")
p.emit("lt", f"jz {dcn}_r", f"jmp {jp}")
p.mark(f"{dcn}_r")
p.set(ANIM, 0)
p.mark(dcn)
if BASE:                                          # P21: Down alone with A: the quick turn
    p.emit("load 1").push(15).emit("and").push(spec.PAD_DOWN).emit("eq", f"jz {dg_}_nq")
    p.set(QT, 512).set(WSPD, 0).emit(f"jmp {jp}")
    p.mark(f"{dg_}_nq")
p.set(F["evk"], 5).push(512).store(W["qx"])      # none held: back
held(15)
p.emit(f"jz {dg_}_go")
p.push(int(OCTANT)).emit("load 1").push(15).emit("and", "add", "loadi").store(W["qx"])
for bit, k in ((spec.PAD_UP, 4), (spec.PAD_DOWN, 5), (spec.PAD_LEFT, 6), (spec.PAD_RIGHT, 7)):
    nb = p.label("dd")                           # (its shape: the last axis read)
    held(bit)
    p.emit(f"jz {nb}")
    p.set(F["evk"], k)
    p.mark(nb)
p.mark(f"{dg_}_go")
p.set(F["evt"], DODGE_F).set(F["evf"], DODGE_F)
p.load(YAW).load(W["qx"]).emit("add").push(1023).emit("and").store(W["qx"])
sin_of(p, cell=W["qx"])
(knob(p, "dodge") if BASE else p.push(DODGE_V)).emit("mulq").push(0).emit("swap", "sub", "dup").store(F["evx"]).store(F["vx"])
sin_of(p, 256, cell=W["qx"])
(knob(p, "dodge") if BASE else p.push(DODGE_V)).emit("mulq", "dup").store(F["evz"]).store(F["vz"])
if BASE:
    p.set(EVW, 1)                                 # (P33: a dodge, to be stopped at its end)
p.emit(f"jmp {jp}")
p.mark(dg_)
p.load(F["uwin"]).emit(f"jz {jp}_p")
p.emit(f"call {L_FOE}")                          # the jump-cancel: a body aloft?
p.load(F["foe"]).push(0).emit("lt", f"jz {jp}_c", f"jmp {jp}_p")
p.mark(f"{jp}_c")
p.set(F["acmb"], ACMB_F).set(F["pvy"], 0).set(F["uwin"], 0).set(F["py"], 1)
p.set(ANIM, 0)                                   # P18: the follow CANCELS the launcher's
                                                 # recovery -- a juggle at jump height is
                                                 # over before the uppercut's 22 frames are
p.emit(f"jmp {jp}")
p.mark(f"{jp}_p")
p.load(ANIM).push(2).emit("eq", f"jz {jp}_j", f"jmp {jp}")   # not mid-swing
p.mark(f"{jp}_j")
if L1:                                            # P24: "jump and pressed again to flip" --
    knob(p, "jump").store(F["pvy"])               # A is the jump, in the boxer too; the
    p.set(F["py"], 1)                             # flip is the second press, in the air
    # P31: THE BOXER'S STRAFE JUMP (the player: "For the boxer, the jumps
    # should be like a strafe jump in the four directions"; on the tape all
    # 21 of his jumps in the stance had the pad held). With the pad, the
    # jump THROWS him that way on his cross -- lower than the jump, at the
    # sjump knob's pace, faster than his step -- still facing as he was.
    sj_ = p.label("sjump")
    p.load(F["sty"]).push(2).emit("eq", f"jz {jp}")
    p.set(SJD, 0)
    for bit_, k_ in ((spec.PAD_UP, 1), (spec.PAD_DOWN, 2), (spec.PAD_LEFT, 3), (spec.PAD_RIGHT, 4)):
        nb_ = p.label("sjd")
        held(bit_)
        p.emit(f"jz {nb_}")
        p.set(SJD, k_)
        p.mark(nb_)
    p.load(SJD).emit(f"jz {jp}")
    p.load(F["pvy"]).push(int(SJ_RISE * ONE)).emit("mulq").store(F["pvy"])
    p.push(int(SJ_TURN)).load(SJD).emit("add", "loadi").load(F["latch"]).emit("add").store(W["qx"])
    sin_of(p, cell=W["qx"])
    knob(p, "sjump").emit("mulq").push(0).emit("swap", "sub").store(F["vx"])
    sin_of(p, 256, cell=W["qx"])
    knob(p, "sjump").emit("mulq").store(F["vz"])
    p.emit(f"jmp {jp}")
p.set(F["pvy"], JUMP_V0).set(F["py"], 1)
p.load(F["sty"]).push(2).emit("eq", f"jz {jp}")   # P18: THE BOXER -- a direction with
p.emit(f"jmp {jp}_f2g")                           # the jump flips that way at once.
                                                  # (The run jumps; its flip is the
                                                  # second press -- below.)
# P10: THE FLIP -- a second A in the air, once a jump: forward from the run,
# any of four ways from the boxing stance (the archive's one-axis rule)
p.mark(f"{jp}_fl")
if L1:
    # P25: THE WALL JUMP (the player: "would be cool if we could do a wall
    # jump"). A in the air with a wall just touched: he kicks off it -- thrown
    # straight back from the wall at WJ_KICK, keeping what he had along it,
    # turned to face the way he is thrown (his heading mirrored in the
    # wall), up again with the flip's rise and its tuck. Twice an air, so a
    # narrow street is two walls to climb between, and no more.
    wj_ = p.label("walljump")
    p.load(WALLT).emit(f"jz {wj_}")
    p.load(WJN).push(WJ_MAX).emit("lt", f"jz {wj_}")
    p.addi(WJN, 1).set(WALLT, 0)
    p.load(F["vx"]).store(F["evx"]).load(F["vz"]).store(F["evz"])
    p.load(WALLA).push(1).emit("and", f"jz {wj_}_z")
    p.push(0).load(WSX).push(WJ_KICK).emit("mul", "sub").store(F["evx"])
    p.push(0).load(YAW).emit("sub").push(1023).emit("and").store(YAW)
    p.mark(f"{wj_}_z")
    p.load(WALLA).push(2).emit("and", f"jz {wj_}_g")
    p.push(0).load(WSZ).push(WJ_KICK).emit("mul", "sub").store(F["evz"])
    p.push(512).load(YAW).emit("sub").push(1023).emit("and").store(YAW)
    p.mark(f"{wj_}_g")
    p.load(F["evx"]).store(F["vx"]).load(F["evz"]).store(F["vz"])
    p.load(YAW).emit("dup").store(F["latch"]).store(F["cgr"])
    p.set(F["evk"], 0).set(F["evt"], WJ_FRAMES).set(F["evf"], WJ_FRAMES)   # (the throw lasts
    p.set(F["pvy"], FLIP_V).set(F["flipu"], 1)                            # the long flip's 24
    p.emit(f"jmp {jp}")                                                   # frames: 7.2 across)
    p.mark(wj_)
p.load(F["acmb"]).load(F["evf"]).emit("or").load(F["flipu"]).emit("or", f"jz {jp}_f1", f"jmp {jp}")
p.mark(f"{jp}_f1")
p.load(ANIM).push(2).emit("eq", f"jz {jp}_f2", f"jmp {jp}")
p.mark(f"{jp}_f2")
# P18: THE DOUBLE JUMP ("think Crash Bandicoot"): the second press in the
# air flips the way the pad points -- or, with no direction, straight up
# again, keeping the way he was going.
held(15)
p.emit(f"jz {jp}_dj", f"jmp {jp}_dir")
p.mark(f"{jp}_f2g")                               # (the boxer, on the ground: no
held(15)                                          # direction is the plain jump)
p.emit(f"jz {jp}")
p.mark(f"{jp}_dir")
# P18: ANY DIRECTION -- "the platformer feel: leap over crowds and land
# where I want". The pad's eight ways (OCTANT), from the boxer's cross, or
# in the run from the target -- Up flips OVER it. The shape is the last axis
# held (a tuck forward, back, a cartwheel either side).
fl_dir = W["qz"]
p.load(YAW).store(W["oy"])
p.load(F["sty"]).push(1).emit("eq", f"jz {jp}_fr")
p.load(F["tgt"]).emit(f"jz {jp}_fr")              # (P20: the free run, his own way)
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).store(W["oy"])
p.mark(f"{jp}_fr")
p.set(fl_dir, 0)
for bit, k in ((spec.PAD_DOWN, 1), (spec.PAD_LEFT, 2), (spec.PAD_RIGHT, 3)):
    nb = p.label("fd")
    held(bit)
    p.emit(f"jz {nb}")
    p.set(fl_dir, k)
    p.mark(nb)
p.mark(f"{jp}_go")
p.load(fl_dir).store(F["evk"])
for k, (spd_, n) in enumerate(FLIPS):                # the flip's speed and length
    nk = p.label("fk")
    p.load(fl_dir).push(k).emit("eq", f"jz {nk}")
    p.push(spd_).store(W["qy"]).set(F["evt"], n).set(F["evf"], n)
    p.mark(nk)
# its direction: the frame (the cross, or the target) turned by the pad
p.push(int(OCTANT)).emit("load 1").push(15).emit("and", "add", "loadi")
p.load(W["oy"]).emit("add").push(1023).emit("and").store(W["qx"])
sin_of(p, cell=W["qx"])
p.load(W["qy"]).emit("mulq").push(0).emit("swap", "sub", "dup").store(F["evx"]).store(F["vx"])
sin_of(p, 256, cell=W["qx"])
p.load(W["qy"]).emit("mulq", "dup").store(F["evz"]).store(F["vz"])
p.emit(f"jmp {jp}_up")
p.mark(f"{jp}_dj")                                # straight up again, as he was going
p.set(F["evk"], 0).set(F["evt"], FLIPS[0][1]).set(F["evf"], FLIPS[0][1])
p.load(F["vx"]).store(F["evx"]).load(F["vz"]).store(F["evz"])
p.mark(f"{jp}_up")
if BASE:
    p.set(EVW, 0)
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
# ---- P20: THE FREE RUN (the player, 2026-11-21: "left shoulder held and
# double clicking right shoulder to hold does the fast running without a
# target"). With L held, a second press of R within RUN_DT frames of the
# first is the run with no lock -- held as long as both are. Steered as the
# tank steers (Left/Right turn, Up drives), at the run's speed.
fr_ = p.label("frun")
if L1:
    # P24: THE RUN IS L, TWICE (the player: "single click hold is boxing ...
    # doubble click hold is running parkour"). L going down within the
    # dclick knob's frames of its last going down is the run, for as long as
    # it is held; any other press of L is the boxer.
    p.load(RDT).push(255).emit("lt", f"jz {fr_}_s")
    p.addi(RDT, 1)                               # frames since L last went down
    p.mark(f"{fr_}_s")
    held(spec.PAD_L)
    p.emit(f"jz {fr_}_no")
    p.load(PVE).push(spec.PAD_L).emit("and", f"jz {fr_}_dn", f"jmp {fr_}")   # still held
    p.mark(f"{fr_}_dn")
    p.load(RDT)
    knob(p, "dclick").emit("lt", f"jz {fr_}_1")
    p.set(FRUN, 1)
    p.mark(f"{fr_}_1")
    p.set(RDT, 0).emit(f"jmp {fr_}")
    p.mark(f"{fr_}_no")
    p.set(FRUN, 0)
    p.mark(fr_)
else:
    p.load(RDT).push(255).emit("lt", f"jz {fr_}_s")
    p.addi(RDT, 1)                                   # frames since R last went down
    p.mark(f"{fr_}_s")
    held(spec.PAD_L)
    p.emit(f"jz {fr_}_no")
    held(spec.PAD_R)
    p.emit(f"jz {fr_}_no")
    p.load(PV).push(spec.PAD_R).emit("and", f"jz {fr_}_dn", f"jmp {fr_}")   # still held
    p.mark(f"{fr_}_dn")                              # R went down this frame, L held:
    p.load(RDT).push(RUN_DT).emit("lt", f"jz {fr_}_1")   # the second press?
    p.set(FRUN, 1)
    p.mark(f"{fr_}_1")
    p.set(RDT, 0).emit(f"jmp {fr_}")
    p.mark(f"{fr_}_no")
    p.set(FRUN, 0)
    held(spec.PAD_R)                                 # (R alone going down still
    p.emit(f"jz {fr_}")                              # starts the count)
    p.load(PV).push(spec.PAD_R).emit("and", f"jz {fr_}_z", f"jmp {fr_}")
    p.mark(f"{fr_}_z")
    p.set(RDT, 0)
    p.mark(fr_)
# ---- P11: THE LOCK, held on R (f_tgt = its slot + 1; 0 is none) -----------
lk = p.label("lock")
held(spec.PAD_R)
p.emit(f"jz {lk}_off")
p.load(FRUN).emit(f"jz {lk}_on", f"jmp {lk}_off")   # P20: the free run locks nothing
p.mark(f"{lk}_on")
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
held(spec.PAD_UP | spec.PAD_DOWN | spec.PAD_LEFT | spec.PAD_RIGHT)
p.emit("dup").load(F["lrp"]).push(-1).emit("xor", "and").store(W["qy"])   # the edges
p.store(F["lrp"])
p.load(F["tgt"]).emit(f"jz {lk}_pl")
p.load(F["sty"]).push(SQ_TARGET).emit("eq", f"jz {lk}_pl")   # (P18: targeting's)
p.load(W["qy"]).push(spec.PAD_LEFT | spec.PAD_RIGHT).emit("and", f"jz {lk}_pl")
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
# P18: TARGETING IS PLANTED -- squared up to it every frame (and so the
# operator's AIM shot, which waits for the plant, frames it)
p.mark(f"{lk}_pl")
p.set(F["plc"], 0)
p.load(F["tgt"]).emit(f"jz {lk}_e")              # (R let go this frame: he keeps the
                                                 # target's bearing -- the plant read
                                                 # "slot -1" and spun him, on glass)
p.load(F["sty"]).push(SQ_TARGET).emit("eq", f"jz {lk}_e")
p.set(F["plc"], PLANT_HOLD)
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).store(YAW)
# ...and Up/Down step the shot: 0 high (the head), 1 mid, 2 low (the legs)
for bit, dv in ((spec.PAD_UP, -1), (spec.PAD_DOWN, 1)):
    nb = p.label("ah")
    p.load(W["qy"]).push(bit).emit("and", f"jz {nb}")
    p.load(F["aimh"]).push(dv).emit("add", "dup").push(0).emit("lt", f"jz {nb}_lo")
    p.emit("drop", f"jmp {nb}")
    p.mark(f"{nb}_lo")
    p.emit("dup").push(3).emit("lt", f"jz {nb}_hi")
    p.store(F["aimh"]).emit(f"jmp {nb}")
    p.mark(f"{nb}_hi")
    p.emit("drop")
    p.mark(nb)
p.mark(f"{lk}_e")

# P18: THE STANCE IS THE SHOULDERS. Neither: the tank. R: targeting. L:
# the boxer. Both: the run. A committed swing keeps the stance it began in.
stn = p.label("stance")
p.load(cmt).emit(f"jz {stn}_c", f"jmp {stn}")
p.mark(f"{stn}_c")
p.push(1).load(FRUN).emit(f"jz {stn}_f", f"jmp {stn}_l")   # P20: the free run
p.mark(f"{stn}_f")
p.emit("drop")
p.push(0).load(F["tgt"]).emit(f"jz {stn}_t")
p.emit("drop").push(SQ_TARGET)
p.mark(f"{stn}_t")
held(spec.PAD_L)
p.emit(f"jz {stn}_l")
p.emit("dup").push(SQ_TARGET).emit("eq", f"jz {stn}_b")
p.emit("drop").push(1).emit(f"jmp {stn}_l")      # L and R: the run
p.mark(f"{stn}_b")
p.emit("drop").push(2)                           # L alone: the boxer
p.mark(f"{stn}_l")
p.emit("dup").load(F["sty"]).emit("eq", f"jz {stn}_ch")
p.emit("drop", f"jmp {stn}")
p.mark(f"{stn}_ch")                              # a new stance
p.load(F["sty"]).push(1).emit("and", f"jz {stn}_nr")    # P18: out of a locked one
p.emit("dup").push(1).emit("and", f"jz {stn}_r", f"jmp {stn}_nr")   # (1, 3) into a free
p.mark(f"{stn}_r")                               # one (0, 2): he faces where the
p.load(F["cgr"]).store(YAW)                      # target was -- the boxer's cross too
p.mark(f"{stn}_nr")
p.emit("dup").store(F["sty"])
p.emit("dup").push(2).emit("eq", f"jz {stn}_nb")
p.load(YAW).store(F["latch"])                    # the boxer: this cross, held
p.mark(f"{stn}_nb")
p.push(SQ_TARGET).emit("eq", f"jz {stn}")
p.set(F["aimh"], 1)                              # targeting opens on the body
p.mark(stn)

tk = p.label("turn")
if BASE:                                           # P21: THE QUICK TURN (Down + A): half
    p.push(0).load(QT).emit("lt", f"jz {tk}_nq")   # round, a knob's worth a frame, and
    p.load(QT)                                     # nothing else turns him meanwhile
    knob(p, "qturn")
    p.emit("over", "over", "lt", f"jz {tk}_q1")
    p.emit("drop", f"jmp {tk}_q2")
    p.mark(f"{tk}_q1")
    p.emit("swap", "drop")
    p.mark(f"{tk}_q2")
    p.emit("dup").load(YAW).emit("add").push(1023).emit("and").store(YAW)
    p.load(QT).emit("swap", "sub").store(QT)
    p.emit(f"jmp {tk}")
    p.mark(f"{tk}_nq")
p.load(F["sty"]).emit(f"jz {tk}_t", f"jmp {tk}")   # (the styles steer themselves)
p.mark(f"{tk}_t")
if L3:                                             # (P35: locked, he is planted;
    p.load(LOCK)                                   # P37: and with R held alone, target or none)
    if L4:
        p.load(PLANT).emit("or")
    p.emit(f"jz {tk}_lk", f"jmp {tk}")
    p.mark(f"{tk}_lk")
if L2:                                             # (P28: nor through a strike: it is thrown;
    p.load(ANIM).push(2).emit("eq", f"jz {tk}_sw", f"jmp {tk}")   # P30: nor between a
    p.mark(f"{tk}_sw")                             # string's blows -- the pad was their step)
    p.load(F["c3"]).emit(f"jz {tk}_sl")
    p.push(TURN_LOCK).load(F["ltap"]).emit("lt", f"jz {tk}")
    p.mark(f"{tk}_sl")
if L2:
    # P32: the tank does not turn with a face button down -- the pad is then
    # a blow's way -- but TIME SLOWED the button is the hold, and he steers.
    # P33: exactly: a button FRESHLY down (not yet past the hold knob) still
    # makes the pad its blow's way, in slowed time as in running time -- or
    # Left + A, slowed, dodged AND turned him. Only a button held past the
    # knob lets him steer.
    # P34: ...nor with a blow waiting to be thrown. The gun fires as B comes
    # UP, and on that frame the button was no longer down: with Left still
    # held the tank turned a notch before the shot left -- five degrees off
    # the line the sight had just shown.
    p.load(F["buf"]).emit(f"jz {tk}_nb", f"jmp {tk}")
    p.mark(f"{tk}_nb")
    p.push(0)
    for cell_ in (GT["carve"], GT["special"], GT["shoot"], AHOLD):
        p.push(0).load(cell_).emit("lt")                          # down...
        knob(p, "hold").load(cell_).emit("lt").push(1).emit("xor", "and", "or")   # ...and not past the hold
    p.emit(f"jz {tk}_go", f"jmp {tk}")
p.emit("load 1").push(spec.PAD_A | spec.PAD_B | spec.PAD_X | spec.PAD_Y)
p.emit("and", f"jz {tk}_go", f"jmp {tk}")
p.mark(f"{tk}_go")
if L2:
    # P35: AIMING, THE TURN STARTS FINE. The tank's notch (14: five degrees)
    # is half a unit of wall at six units -- a key is 0.9 across. Aiming, a
    # turn's first frame is 1, its second 2, and so on up to the tank's own:
    # a tap is a degree or two, a hold sweeps as fast as ever.
    at_ = p.label("aimturn")
    knob(p, "turn").store(W["dg"])
    p.load(AIMED).emit(f"jz {at_}")
    held(spec.PAD_LEFT | spec.PAD_RIGHT)
    p.emit(f"jz {at_}_z")
    p.addi(ATURN, 1)
    p.load(ATURN).load(W["dg"]).emit("lt", f"jz {at_}")
    p.load(ATURN).store(W["dg"]).emit(f"jmp {at_}")
    p.mark(f"{at_}_z")
    p.set(ATURN, 0)
    p.mark(at_)
    p.if_pad(spec.PAD_LEFT, lambda q: q.load(YAW).load(W["dg"]).emit("add").store(YAW))
    p.if_pad(spec.PAD_RIGHT, lambda q: q.load(YAW).load(W["dg"]).emit("sub").store(YAW))
elif BASE:
    p.if_pad(spec.PAD_LEFT, lambda q: knob(q.load(YAW), "turn").emit("add").store(YAW))
    p.if_pad(spec.PAD_RIGHT, lambda q: knob(q.load(YAW), "turn").emit("sub").store(YAW))
else:
    p.if_pad(spec.PAD_LEFT, lambda q: q.addi(YAW, 12))      # a raised yaw turns him
    p.if_pad(spec.PAD_RIGHT, lambda q: q.addi(YAW, -12))    # LEFT (forward is (-sin, cos))
p.load(YAW).push(1023).emit("and").store(YAW)
p.mark(tk)

# ---- a swing owns the body until its frames are done --------------------------
p.load(ANIM).push(2).emit("eq", f"jz {L['free']}")
p.addi(AF, 1)
if L2:
    # P31: HIS BODY COMES ROUND TO THE BLOW, the clock running (the pivot
    # knob a frame: a side in two, behind in three -- there before a jab is
    # out). His steering does not turn, nor the lens.
    # P30: THE BLOW'S DRIVE. Its lunge comes on its own frame -- with the
    # drive, not the wind-up (the haymaker winds back where he stands, then
    # goes) -- along the blow's way. One impulse; the clip's feet are
    # planted to it.
    lg_ = p.label("lunge")
    p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {lg_}_f")
    # P34: THE SHOT IS A BULLET. On the shot's first frame a round leaves the
    # gun along his body's way, from where he stands: RAY says where that
    # line meets a wall (or the key), and the bullet flies there at BULLET_V
    # a frame of the fight. Out of rounds, the hammer falls on nothing.
    p.load(AF)
    row(PMT, F["mv"], "start")
    p.emit("eq", f"jz {lg_}")
    p.load(HEAD).store(W["head"]).emit(f"call {L_FIRE}", f"jmp {lg_}")
    p.mark(f"{lg_}_f")
    steer_head(p, PIVT)
    if L3:                                        # (P36: the superman punch is the leap's own way)
        p.load(SJD).emit(f"jz {lg_}_sj", f"jmp {lg_}")
        p.mark(f"{lg_}_sj")
    p.load(AF).push(int(LDT)).load(F["mv"]).emit("add", "loadi", "eq", f"jz {lg_}")
    row(PMT, F["mv"], "lunge")
    knob(p, "lunge").emit("mulq", "dup").store(W["dmg"])
    sin_of(p, cell=PIVT)
    p.emit("mulq").load(F["vx"]).emit("swap", "sub").store(F["vx"])   # fwd x = -sin
    sin_of(p, 256, cell=PIVT)
    p.load(W["dmg"]).emit("mulq").load(F["vz"]).emit("add").store(F["vz"])
    p.mark(lg_)
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
if L3:
    # P36: IN THE LOCKED RUN (the player: "the gun being shot while running
    # single hand. and then trying to weave and land a super man punch").
    # A SHOT does not stop him: the round leaves at once, AT the item, the
    # run going on under it with the near arm out (the pose, below). A FIST
    # is the superman punch: he leaves the ground at the item -- the jump's
    # own rise, SUPER_V a frame, nothing steering it -- the haymaker wound
    # up through the air to land as he comes down; he stops short of the
    # item and no nearer. Thrown from too far, it falls short: the range is
    # his to find.
    rs_ = p.label("runshot")
    p.load(LOCK).load(F["sty"]).push(1).emit("eq", "and", f"jz {rs_}")
    p.push(MOVE["gun"] - 1).load(F["bmv"]).emit("lt", f"jz {rs_}_p")
    p.load(F["bmv"]).store(F["mv"]).set(F["buf"], 0).set(RSHOT, RUN_ARM)
    p.load(LBRG).store(W["head"]).emit(f"call {L_FIRE}", f"jmp {L['walk']}_q")
    p.mark(f"{rs_}_p")
    p.load(F["py"]).emit(f"jz {rs_}_g", f"jmp {rs_}")
    p.mark(f"{rs_}_g")
    p.set(F["bmv"], MOVE["special"]).set(F["c3"], 3).set(SJD, 5).set(F["spd"], 0).set(F["py"], 1)
    knob(p, "jump").store(F["pvy"])
    p.load(LBRG).emit("dup").store(YAW).store(HEAD)
    sin_of(p, cell=LBRG)
    p.push(SUPER_V).emit("mulq").push(0).emit("swap", "sub").store(F["vx"])
    sin_of(p, 256, cell=LBRG)
    p.push(SUPER_V).emit("mulq").store(F["vz"])
    p.mark(rs_)
# LAUNCH: the buffered move, and its lunge as ONE impulse (tear.py _launch)
p.load(F["bmv"]).store(F["mv"])
p.set(ANIM, 2).set(AF, 0).set(F["con"], 0).set(F["buf"], 0)
if L2:
    # P30: THE COUNT BUILDS TO THE TERMINATOR. A jab thrown is one more; Y
    # ends the string with what the count has earned -- none or one: the
    # lead hook; two: the rear uppercut; three or more: the haymaker.
    ct_ = p.label("count")
    p.load(F["mv"]).push(MOVE["jab"]).emit("eq", f"jz {ct_}_y")
    p.load(F["c3"]).push(3).emit("lt", f"jz {ct_}")
    p.addi(F["c3"], 1).emit(f"jmp {ct_}")
    p.mark(f"{ct_}_y")
    p.load(F["mv"]).push(MOVE["special"]).emit("eq", f"jz {ct_}")
    p.load(F["c3"]).push(2).emit("lt", f"jz {ct_}_2")
    p.set(F["mv"], MOVE["lead_hook"]).emit(f"jmp {ct_}_z")
    p.mark(f"{ct_}_2")
    p.load(F["c3"]).push(2).emit("eq", f"jz {ct_}_z")
    p.set(F["mv"], MOVE["rear_uppercut"])
    p.mark(f"{ct_}_z")
    p.set(F["c3"], 0)
    p.set(SHOTS, 0).set(RLD, 0)                   # (P34: a terminator loads the gun)
    p.mark(ct_)
    gp_ = p.label("gunpre")                       # P34: a shot starts as far in as the
    p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {gp_}")   # gun is drawn (to the
    row(PMT, F["mv"], "start")                    # frame before it fires)
    p.push(1).emit("sub").load(DRAW).emit("over", "over", "swap", "lt", f"jz {gp_}_m", "swap")
    p.mark(f"{gp_}_m")
    p.emit("drop").store(AF)
    p.mark(gp_)
gf = p.label("gunface")
# P18: WHERE THE ATTACK GOES -- the way the pad points from his facing,
# snapped there, all three attacks alike (the gun too: "never the pad" is
# gone); locked, at the target. The gun finds whom its exact line meets
# (L_LINE), and in a launcher's slow motion it tracks the body in the air.
# The shot does not move him: no lunge, only the recoil's shake.
p.set(AIM, 0)
p.load(F["tgt"]).emit(f"jz {gf}_p")
p.load(F["tgt"]).emit("dup").store(AIM).push(1).emit("sub").store(F["brg"])
p.emit(f"call {L_BRG}")
p.load(F["brg"]).store(HEAD).emit(f"jmp {gf}_g")
p.mark(f"{gf}_p")
if L2:
    # P31: THE BLOW GOES THE WAY THE PAD POINTS, AND HIS BODY TURNS TO THROW
    # IT (the player, of P30: "The directional punches are to turn player as
    # if he was making a punch in that direction" -- "The whole body should
    # be turned, the tank and boxer camera does not move. movement returns
    # the direction to where it was before the directional hits"). The way
    # is the pad's, from his STEERING -- which no blow changes, so the pad
    # means the same thing blow after blow -- and with no pad it is the way
    # his body already faces. (The gun still snaps: not this layer's.)
    p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {gf}_pf", f"jmp {gf}_ps")
    p.mark(f"{gf}_pf")
    p.load(HEAD).store(PIVT)
    if L3:                                        # (P35: locked, the blow goes at it)
        p.load(LOCK).emit(f"jz {gf}_pl", f"jmp {L['motion']}")
        p.mark(f"{gf}_pl")
    held(15)
    p.emit(f"jz {L['motion']}")
    p.push(int(OCTANT)).emit("load 1").push(15).emit("and", "add", "loadi")
    p.load(YAW).emit("add").push(1023).emit("and").store(PIVT)
    p.set(TURNED, 1)
    p.emit(f"jmp {L['motion']}")
    # P32: A SHOT IS A BLOW TOO. The gun still snaps to the pad's way the
    # frame it fires (a shot goes exactly where it is pointed) -- but, as a
    # fist does, with no pad it goes where his body faces, and he STAYS as
    # the shot left him till he moves: on the tape 144 of his 203 shots
    # were fired in slowed time, in volleys, and between each two his body
    # snapped back to his steering.
    p.mark(f"{gf}_ps")
    p.set(TURNED, 1)
    p.load(AIMED)                                 # (P35: aimed -- or locked -- the shot goes
    if L3:                                        # where he faces: the pad was his feet)
        p.load(LOCK).emit("or")
    p.emit(f"jz {gf}_pa")
    p.set(AIMED, 0).emit(f"jmp {gf}_g")
    p.mark(f"{gf}_pa")
    held(15)
    p.emit(f"jz {gf}_g")
p.push(int(OCTANT)).emit("load 1").push(15).emit("and", "add", "loadi")
p.load(YAW).emit("add").push(1023).emit("and").store(HEAD)
p.mark(f"{gf}_g")
p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {gf}_m")
p.load(F["slow"]).emit(f"jz {gf}_l")              # the slow motion: track it
p.emit(f"call {L_FOE}")
p.load(F["foe"]).emit("dup").push(0).emit("lt", f"jz {gf}_t")
p.emit("drop", f"jmp {gf}_l")
p.mark(f"{gf}_t")
p.emit("dup").push(1).emit("add").store(AIM).store(F["brg"])
p.emit(f"call {L_BRG}")
p.load(F["brg"]).store(HEAD).emit(f"jmp {gf}_k0")
p.mark(f"{gf}_l")
p.load(AIM).emit(f"jz {gf}_ln", f"jmp {gf}_k0")   # locked: its target
p.mark(f"{gf}_ln")
p.load(HEAD).store(W["head"]).emit(f"call {L_LINE}")
p.mark(f"{gf}_k0")
p.push(3).load(F["mv"]).push(MOVE["gun"]).emit("sub").push(4).emit("mul", "add")
p.load(F["shake"]).emit("over", "over", "lt", f"jz {gf}_k")   # the recoil kick:
p.emit("swap")                                # 3 frames, the charged one 7
p.mark(f"{gf}_k")
p.emit("drop").store(F["shake"])
p.emit(f"jmp {L['motion']}")
p.mark(f"{gf}_m")                               # a fist: its lunge, along HEAD
row(PMT, F["mv"], "lunge")                      # (targeting's haymaker crosses the
hy_ = p.label("hylunge")                        # gap to the target it is sure to
p.load(F["mv"]).push(MOVE["special"]).emit("eq", f"jz {hy_}")   # hit: x2.5, five units)
p.load(F["sty"]).push(SQ_TARGET).emit("eq", f"jz {hy_}")
p.push(int(2.5 * ONE)).emit("mulq")
p.mark(hy_)
p.emit("dup").store(W["dmg"])
sin_of(p, cell=HEAD)
p.emit("mulq").load(F["vx"]).emit("swap", "sub").store(F["vx"])   # fwd x = -sin
sin_of(p, 256, cell=HEAD)
p.load(W["dmg"]).emit("mulq").load(F["vz"]).emit("add").store(F["vz"])
p.emit(f"jmp {L['motion']}")
p.mark(f"{L['walk']}_q")
if L2:
    # P31: A BLOW TURNED HIM, AND HE STANDS AS IT LEFT HIM till he moves:
    # the pad (walking, turning, the boxer's steps) brings his body back
    # round to his steering at the pivot knob's turn; the run, a dodge or a
    # flip, at once. (Held still by a string's lock, the pad is not movement.)
    tn_ = p.label("turned")
    # P34: B DOWN, HIS BODY COMES ROUND TO THE SHOT'S WAY as it does to a
    # blow's -- the pad's, from his steering; no pad, where it faces -- so
    # the gun is seen to point where the sight does before he lets go.
    dr_ = p.label("drawturn")
    held(spec.PAD_B)
    p.emit(f"jz {dr_}")
    p.load(AIMED)                             # (P35: aiming or locked, his body is his steering's)
    if L3:
        p.load(LOCK).emit("or")
    p.emit(f"jz {dr_}_a", f"jmp {dr_}")
    p.mark(f"{dr_}_a")
    p.load(F["sty"]).push(1).emit("eq").load(F["evf"]).emit("or", f"jz {dr_}_t", f"jmp {dr_}")
    p.mark(f"{dr_}_t")
    p.load(HEAD).store(PIVT)
    held(15)
    p.emit(f"jz {dr_}_n")
    p.push(int(OCTANT)).emit("load 1").push(15).emit("and", "add", "loadi")
    p.load(YAW).emit("add").push(1023).emit("and").store(PIVT)
    p.mark(f"{dr_}_n")
    p.set(TURNED, 1)
    steer_head(p, PIVT)
    p.emit(f"jmp {tn_}")
    p.mark(dr_)
    p.load(TURNED).emit(f"jz {tn_}_p")
    p.load(F["sty"]).push(1).emit("eq").load(F["evf"]).emit("or", f"jz {tn_}_m")
    p.set(TURNED, 0).emit(f"jmp {tn_}_p")
    p.mark(f"{tn_}_m")
    held(15)
    p.emit(f"jz {tn_}")
    p.load(F["c3"]).emit(f"jz {tn_}_go")
    p.push(TURN_LOCK).load(F["ltap"]).emit("lt", f"jz {tn_}")
    p.mark(f"{tn_}_go")
    steer_head(p, YAW)
    p.load(HEAD).load(YAW).emit("eq", f"jz {tn_}")
    p.set(TURNED, 0).emit(f"jmp {tn_}")
    p.mark(f"{tn_}_p")
    p.load(YAW).store(HEAD)                   # no strike: he faces his steering
    p.mark(tn_)
else:
    p.load(YAW).store(HEAD)                   # no strike: he faces his steering
# P10: a flip owns the frame; else the style's own step
ev = p.label("evade")
p.load(F["evf"]).emit(f"jz {ev}_n")
p.addi(F["evf"], -1)
p.load(F["evx"]).store(F["vx"]).load(F["evz"]).store(F["vz"])
p.set(ANIM, 0).emit(f"jmp {L['motion']}")
p.mark(f"{ev}_n")
if BASE:
    # P33: THE DODGE ENDS WHERE IT ENDS (the player: "work on the dodges it
    # feels to slippy. for all movement I should be able to have accurate
    # prediction of where I'll land or be"). It went 1.65 in its own twelve
    # frames and then SLID 0.83 more over twenty-two, on the body's friction.
    # Now its twelve frames are the whole of it -- the dodge knob's pace a
    # frame, 2.4 units -- and he is stopped: the same place, every time.
    de_ = p.label("dodgeend")
    p.load(EVW).emit(f"jz {de_}")
    p.set(EVW, 0)
    p.load(F["py"]).emit(f"jz {de_}_g", f"jmp {de_}")       # (thrown into the air: the air's)
    p.mark(f"{de_}_g")
    p.set(F["vx"], 0).set(F["vz"], 0)
    p.mark(de_)
p.load(F["sty"]).push(1).emit("eq", f"jz {ev}_b")
# PARKOUR: the quick turn, the logistic ramp, the fixed turn, grip and scrub
# P18: THE RUN goes the way the pad points round the target -- Up at it,
# Down away, Left and Right round it -- turning there at RUN_TURN a frame
# P20: THE FREE RUN (no target) steers as the tank does: Left/Right turn
# him at FREE_TURN, Up drives; nothing held, he coasts
if L3:
    # P36: LOCKED, THE RUN GOES ROUND THE ITEM (the player: "the running and
    # aiming should feel you are running on the tangent of the circle"): the
    # pad's way is from the item's bearing -- Left and Right ALONG the circle
    # round it, Up at it, Down away, the corners spiralling in and out --
    # P18's own run round a target.
    p.load(LOCK).emit(f"jz {ev}_nl")
    p.load(LBRG).store(F["brg"]).emit(f"jmp {ev}_lb")
    p.mark(f"{ev}_nl")
p.load(F["tgt"]).emit(f"jz {ev}_fr", f"jmp {ev}_lk")
p.mark(f"{ev}_fr")
if L1:
    # P27: THE SLIDE. Down, in the run, at speed and on the ground: he goes
    # down feet first and slides the way he was heading -- a little faster
    # than he ran, scrubbing off -- for as long as Down is held, SLIDE_LEAST
    # frames at least and SLIDE_MAX at most; he does not steer it. He comes
    # up into the run (or to a stand) at the speed the slide has left him.
    # A wall stops it, as it stops him.
    sd_ = p.label("slide")
    p.load(SLT).emit(f"jz {sd_}_no")
    p.addi(SLT, -1).addi(SLF, 1)                                   # sliding
    held(spec.PAD_DOWN)
    p.emit(f"jz {sd_}_rel", f"jmp {sd_}_on")
    p.mark(f"{sd_}_rel")                                           # Down let go: up, once
    p.push(SLIDE_LEAST).load(SLF).emit("lt", f"jz {sd_}_on")       # the least is done
    p.push(SLIDE_UP).load(SLT).emit("lt", f"jz {sd_}_on")          # (SLIDE_UP < left: cut to it)
    p.set(SLT, SLIDE_UP)
    p.mark(f"{sd_}_on")
    p.load(SLV).push(SLIDE_KEEP).emit("mulq", "dup").store(SLV).store(F["spd"])
    sin_of(p)
    p.load(SLV).emit("mulq").push(0).emit("swap", "sub").store(F["vx"])
    sin_of(p, 256)
    p.load(SLV).emit("mulq").store(F["vz"])
    p.set(ANIM, 7).emit(f"jmp {L['motion']}")
    p.mark(f"{sd_}_no")
    held(spec.PAD_DOWN)                                            # a fresh Down, running fast
    p.emit(f"jz {sd_}")
    p.load(PVE).push(spec.PAD_DOWN).emit("and", f"jz {sd_}_e", f"jmp {sd_}")
    p.mark(f"{sd_}_e")
    p.push(SLIDE_MIN).load(F["spd"]).emit("lt", f"jz {sd_}")
    p.load(F["py"]).emit(f"jz {sd_}_g", f"jmp {sd_}")
    p.mark(f"{sd_}_g")
    p.set(SLT, SLIDE_MAX).set(SLF, 0)
    p.load(F["spd"]).push(SLIDE_BOOST).emit("mulq").store(SLV)
    p.emit(f"jmp {sd_}_on")
    p.mark(sd_)
if L1:
    p.if_pad(spec.PAD_LEFT, lambda q: knob(q.load(YAW), "runturn").emit("add").store(YAW))
    p.if_pad(spec.PAD_RIGHT, lambda q: knob(q.load(YAW), "runturn").emit("sub").store(YAW))
else:
    p.if_pad(spec.PAD_LEFT, lambda q: q.addi(YAW, FREE_TURN))
    p.if_pad(spec.PAD_RIGHT, lambda q: q.addi(YAW, -FREE_TURN))
p.load(YAW).push(1023).emit("and", "dup").store(YAW)
p.store(F["cgr"])                                # (out of it, he keeps this way)
held(spec.PAD_UP)
p.emit(f"jmp {ev}_nd")
p.mark(f"{ev}_lk")
p.load(F["tgt"]).push(1).emit("sub").store(F["brg"]).emit(f"call {L_BRG}")
if L3:
    p.mark(f"{ev}_lb")
p.emit("load 1").push(15).emit("and", "dup", f"jz {ev}_nd")
p.push(int(OCTANT)).emit("add", "loadi").load(F["brg"]).emit("add")
p.push(1023).emit("and").store(W["head"])
if L3:
    # P36: ...AND STAYS ON ITS CIRCLE. A step along the tangent ends a little
    # OUTSIDE the circle it began on: left alone he spiralled out an eighth
    # of a unit a second. The radius he had when this pad went down is kept,
    # and outside it his heading is turned CIRCLE_IN toward the item: he
    # holds the circle to a hundredth.
    rc_ = p.label("circle")
    p.load(LOCK).emit(f"jz {rc_}")
    p.load(TGX).load(PX).emit("sub", "dup", "mulq").load(TGZ).load(PZ).emit("sub", "dup", "mulq", "add")
    p.store(W["d2"])
    p.emit("load 1").push(15).emit("and", "dup").load(RPAD).emit("eq", f"jz {rc_}_n")
    p.emit("drop", f"jmp {rc_}_h")
    p.mark(f"{rc_}_n")
    p.store(RPAD).load(W["d2"]).store(RAD2).emit(f"jmp {rc_}")
    p.mark(f"{rc_}_h")
    p.load(RAD2).load(W["d2"]).emit("lt", f"jz {rc_}")
    p.if_pad(spec.PAD_LEFT, lambda q: q.addi(W["head"], -CIRCLE_IN))
    p.if_pad(spec.PAD_RIGHT, lambda q: q.addi(W["head"], CIRCLE_IN))
    p.mark(rc_)
p.push(RUN_TURN).store(W["dg"]).emit(f"call {L_STEER}")
p.push(1)
p.mark(f"{ev}_nd")
p.emit(f"jz {ev}_co")
p.load(F["spd"]).push(PK_SEED).emit("lt", f"jz {ev}_sd")
p.set(F["spd"], PK_SEED)
p.mark(f"{ev}_sd")
p.load(F["spd"]).emit("dup", "dup", "mulq").push(PK_INVTOP).emit("mulq", "sub")  # s(1-s/top)
(knob(p, "runacc") if L1 else p.push(PK_GROWTH)).emit("mulq").load(F["spd"]).emit("add").store(F["spd"])
p.push(PK_TOP).load(F["spd"]).emit("lt", f"jz {ev}_tp")
p.set(F["spd"], PK_TOP)
p.mark(f"{ev}_tp")
p.emit(f"jmp {ev}_tr")
p.mark(f"{ev}_co")
if L1:
    # P33: IN THE AIR THE RUN KEEPS ITS SPEED. Letting go of Up mid-jump
    # coasted him down as it does on the ground: a jump went 4.8 units with
    # Up held and 1.6 without. The air takes nothing: the jump is the jump.
    p.load(F["py"]).emit(f"jz {ev}_cg", f"jmp {ev}_tr")
    p.mark(f"{ev}_cg")
p.load(F["spd"]).push(PK_FR).emit("mulq").store(F["spd"])     # coasting
p.mark(f"{ev}_tr")
# (P18: METEOR and the prowler's turn are the run's steer, above)
for vel, plus, neg in ((F["vx"], 0, True), (F["vz"], 256, False)):
    sin_of(p, plus)
    p.load(F["spd"]).emit("mulq")
    if neg:
        p.push(0).emit("swap", "sub")             # want = forward * speed
    (knob(p.load(vel).emit("sub"), "grip") if L1 else p.load(vel).emit("sub").push(PK_GRIP)).emit(
        "mulq").load(vel).emit("add").store(vel)
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
if BASE:
    # (the player: "when stationary the player should be in the standing
    # position" -- the run held but nothing driven, his speed run down:
    # he STANDS, as the tank stands, till the pad drives him again)
    p.load(F["spd"]).push(RUN_STAND).emit("lt", f"jz {ev}_rn")
    p.set(ANIM, 0).emit(f"jmp {L['motion']}")
    p.mark(f"{ev}_rn")
p.set(ANIM, 5).emit(f"jmp {L['motion']}")
# BOXING: the four steps on the latched cross, and he faces it
p.mark(f"{ev}_b")
p.load(F["sty"]).push(2).emit("eq", f"jz {ev}_tank")
# (P18: FENCING, the locked boxer, is gone -- locked is targeting or the run)
if L2:
    p.load(F["latch"]).store(YAW)                 # (P31: his body, as a blow left it)
    bt_ = p.label("boxturned")
    p.load(TURNED).emit(f"jz {bt_}_p", f"jmp {bt_}")
    p.mark(f"{bt_}_p")
    p.load(YAW).store(HEAD)
    p.mark(bt_)
else:
    p.load(F["latch"]).emit("dup").store(YAW).store(HEAD)
if L1:
    # P31: THE STRAFE JUMP's flight (below, at the jump): thrown, he keeps
    # what the jump gave him -- no step, no drag -- till he lands; and
    # (P33) lands THERE: stopped, 3.0 units from where he left the ground.
    sjf = p.label("sjfly")
    p.load(SJD).emit(f"jz {sjf}")
    p.load(F["py"]).emit(f"jz {sjf}")
    p.set(ANIM, 0).emit(f"jmp {L['motion']}")
    p.mark(sjf)
(knob(p.push(BOX_FR).store(W["qx"]), "boxstep") if L1
 else p.push(BOX_FR).store(W["qx"]).push(BOX_RATE)).store(W["qz"])
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
p.load(F["sty"]).push(SQ_TARGET).emit("eq", f"jz {ev}_tk")    # P18: TARGETING is
p.set(ANIM, 0).emit(f"jmp {L['motion']}")                      # planted: no step
p.mark(f"{ev}_tk")
p.load(F["py"]).load(F["acmb"]).emit("or", f"jz {L['walk']}_gr")   # aloft: no
p.emit(f"jmp {L['idle']}")                    # stride (the air owns him)
p.mark(f"{L['walk']}_gr")
wb = p.label("wback")
if BASE:
    # P21: THE WALK HAS WEIGHT. His pace is a speed that eases to what the pad
    # asks (the ramp knob a frame): he leans into a step and settles out of
    # it. The heading is still the tank's, exact.
    if L1:                                        # (out of the run: its speed, and the
        p.load(F["spd"]).push(int(0.8 * ONE)).emit("mulq").store(F["spd"])   # lean it gives him, die away)
    p.push(0)
    if L3:                                        # (P35: locked, he is planted)
        p.load(LOCK)
        if L4:
            p.load(PLANT).emit("or")
        p.emit(f"jz {wb}_lk", f"jmp {wb}_e")
        p.mark(f"{wb}_lk")
    if L2:                                        # (P30: between a string's blows he stands)
        p.load(F["c3"]).emit(f"jz {wb}_sl")
        p.push(TURN_LOCK).load(F["ltap"]).emit("lt", f"jz {wb}_e")
        p.mark(f"{wb}_sl")
    p.load(QT).emit(f"jz {wb}_t", f"jmp {wb}_e")          # (mid quick turn: he stands)
    p.mark(f"{wb}_t")
    p.emit("load 1", f"push {spec.PAD_UP}", "and", f"jz {wb}_d")
    p.emit("drop")
    knob(p, "walk")
    p.mark(f"{wb}_d")
    p.emit("load 1", f"push {spec.PAD_DOWN}", "and", f"jz {wb}_e")
    p.emit("drop").push(0)
    knob(p, "walk").emit("sub")
    p.mark(f"{wb}_e")
    p.load(WSPD).emit("sub")
    knob(p, "ramp").emit("mulq").load(WSPD).emit("add").store(WSPD)
    sin_of(p)
    p.load(WSPD).emit("mulq").load(PX).emit("swap", "sub").store(PX)
    sin_of(p, 256)
    p.load(WSPD).emit("mulq").load(PZ).emit("add").store(PZ)
    # (THE STRIDE GOES BY THE GROUND, not by the frame: the legs knob's
    # poses a unit he covers. P21 kept his feet planted exactly -- and at
    # the pace the player then chose, the short stride ran at 7.5 steps a
    # second; P26 gives a longer stride and fewer poses than planting asks.)
    p.load(WSPD).emit("dup").push(0).emit("lt", f"jz {wb}_ab")
    p.push(0).emit("swap", "sub")
    p.mark(f"{wb}_ab")
    knob(p, "legs").emit("mulq").load(WACC).emit("add", "dup")
    p.push(0xFFFF).emit("and").store(WACC)
    p.emit("shr 16").store(W["dg"])                                    # poses, this frame
    p.push(int(0.004 * ONE)).load(WSPD).emit("lt", f"jz {wb}_b")       # forward
    p.set(ANIM, 1).load(AF).load(W["dg"]).emit("add").store(AF).emit(f"jmp {L['motion']}")
    p.mark(f"{wb}_b")
    p.load(WSPD).push(-int(0.004 * ONE)).emit("lt", f"jz {wb}_s")      # back
    p.set(ANIM, 1).load(AF).load(W["dg"]).emit("sub").store(AF).emit(f"jmp {L['motion']}")
    p.mark(f"{wb}_s")
    p.emit("load 1").push(spec.PAD_UP | spec.PAD_DOWN).emit("and", f"jz {wb}_z")
    p.emit(f"jmp {L['idle']}")
    p.mark(f"{wb}_z")
    p.set(WSPD, 0).emit(f"jmp {L['idle']}")
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
if BASE:                                          # (a swing, a dodge: the walk is spent)
    ws_ = p.label("wspent")
    p.push(1).load(ANIM).emit("lt").load(F["evf"]).emit("or", f"jz {ws_}")
    p.set(WSPD, 0)
    p.mark(ws_)
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
if L1:                                           # (P31: the strafe jump's flight: free)
    sjq = p.label("sjfree")
    p.load(SJD).emit(f"jz {sjq}")
    p.push(ONE).store(W["dg"])
    p.mark(sjq)
if L1:                                           # P24: the run's pace is a knob -- the
    rp_ = p.label("runpace")                      # step he takes in the run, not the speed
    p.push32(ONE)                                 # its own rules are written in
    p.load(F["sty"]).push(1).emit("eq", f"jz {rp_}")
    if L3:                                        # (P36: nor the superman punch's -- it goes as
        p.load(SJD).emit(f"jz {rp_}_sp", f"jmp {rp_}")   # far with L let go in the air as held)
        p.mark(f"{rp_}_sp")
    p.load(WJN).emit(f"jz {rp_}_k")               # (but a wall jump's throw is its OWN
    p.load(F["evf"]).emit(f"jz {rp_}_k", f"jmp {rp_}")   # pace, whatever the run's knob:
    p.mark(f"{rp_}_k")                            # it must cross the street)
    p.emit("drop")
    knob(p, "run")
    p.mark(rp_)
    p.store(W["stop"])
for pos, vel in ((PX, F["vx"]), (PZ, F["vz"])):
    if L1:
        p.load(pos).load(vel).load(W["stop"]).emit("mulq", "add").store(pos)
    else:
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
if L1:
    p.set(WJN, 0).set(WALLT, 0)                           # (...and the wall jumps)
    sjl = p.label("sjland")                               # (P33: the strafe jump lands,
    p.load(SJD).emit(f"jz {sjl}")                         # and stays where it landed)
    p.set(SJD, 0).set(F["vx"], 0).set(F["vz"], 0)
    p.mark(sjl)
# P15: THE LANDING, FELT (tear.py 2757: "a dead touchdown reads as cartoony
# no matter how the arc above it is shaped"). The frame shakes and the
# ground answers -- the step's own thud, since a sound of its own is 24
# words of a DMEM with 6. (The archive scales both by the fall's speed and
# dips the camera; one strength here.)
ld_ = p.label("land")
p.load(F["shake"]).push(LAND_SHAKE).emit("lt", f"jz {ld_}")
p.set(F["shake"], LAND_SHAKE)
p.mark(ld_)
p.set(SG_T["st"], 0).set(LANDT, LAND_FOR + 1)       # (the clock ticks before it is read)
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
sq_ = p.label("squash")                      # P15: the squash's clock, every frame
p.load(LANDT).emit(f"jz {sq_}")
p.addi(LANDT, -1)
p.mark(sq_)
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
if L1:
    sp7 = p.label("slidepose")
    p.load(ANIM).push(7).emit("eq", f"jz {sp7}")
    p.load(SLF).emit("shr 1")                                       # going down: a pose two frames
    p.load(SLT).push(SLIDE_UP).emit("lt", f"jz {sp7}_d")            # ...or coming up, by what is left
    p.emit("drop").load(SLT).emit("shr 1")
    p.mark(f"{sp7}_d")
    p.emit("dup").push(3).emit("swap", "lt", f"jz {sp7}_c")         # 3 < it: the slide itself
    p.emit("drop").push(3)
    p.mark(f"{sp7}_c")
    p.push(base["slide"]).emit("add").store(POSE).emit(f"jmp {L['pd']}")
    p.mark(sp7)
p.load(ANIM).push(5).emit("eq", f"jz {gp_}_k")
p.load(F["ph"]).emit("shr 16").push(15).emit("and").push(base["run"])
if L3:
    # P36: locked, B down or a shot just gone: the near arm is out at the
    # item -- his right, his left, or ahead of him
    rg_ = p.label("rungun")
    p.load(DRAW).load(RSHOT).emit("or").push(0).emit("eq", "push 1", "xor").load(LOCK).emit("and", f"jz {rg_}")
    p.emit("drop").push(base["run_gun_f"])
    p.load(LBRG).load(YAW).emit("sub").push(512).emit("add").push(1023).emit("and").push(512).emit("sub")
    p.emit("dup").push(96).emit("swap", "lt", f"jz {rg_}_r")           # 96 < it: on his left
    p.emit("drop", "drop").push(base["run_gun_l"]).emit(f"jmp {rg_}")
    p.mark(f"{rg_}_r")
    p.push(-96).emit("lt", f"jz {rg_}")                                # it < -96: on his right
    p.emit("drop").push(base["run_gun_r"])
    p.mark(rg_)
p.emit("add")
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
if L1:
    apj = p.label("sjpose")
    p.load(SJD).emit(f"jz {apj}")
    p.push(int(SJB) - 1).load(SJD).emit("add", "loadi", "add").store(POSE).emit(f"jmp {L['pd']}")
    p.mark(apj)
p.push(base["air"]).emit("add").store(POSE).emit(f"jmp {L['pd']}")
p.mark(ap)
p.load(ANIM).push(2).emit("eq", f"jz {L['pm']}")
row(PMT, F["mv"], "pose")
p.load(AF).emit("add").store(POSE).emit(f"jmp {L['pd']}")
p.mark(L["pm"])
# P15: THE TOUCHDOWN'S KNEES. Standing or walking out of a landing he
# takes it in the legs -- the archive's own absorb, four poses, two frames
# each; anything he DOES (a swing, a flip, the air) is posed above and wins.
p.load(LANDT).emit(f"jz {sq_}_n")
p.push(LAND_FOR).load(LANDT).emit("sub", "shr 1").push(base["land"]).emit("add")
p.store(POSE).emit(f"jmp {L['pd']}")
p.mark(f"{sq_}_n")
p.load(ANIM).push(1).emit("eq", f"jz {L['pi']}")
p.load(AF).push(NPOSE["walk"] - 1).emit("and").push(base["walk"]).emit("add")  # 60 Hz: PLANTED
p.store(POSE).emit(f"jmp {L['pd']}")
p.mark(L["pi"])
if L2:                                       # P34: standing, the gun as far up as
    dp_ = p.label("drawpose")                # it is drawn (the shot's own first poses)
    p.load(DRAW).emit(f"jz {dp_}")
    p.load(DRAW).emit("dup").push(4).emit("swap", "lt", f"jz {dp_}_c")
    p.emit("drop").push(4)
    p.mark(f"{dp_}_c")
    p.push(base["gun"]).emit("add").store(POSE).emit(f"jmp {L['pd']}")
    p.mark(dp_)
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
RETRY_CELLS = ((PX, START_X), (PZ, START_Z), (YAW, START_YAW), (CY, START_YAW),
             (WOKE, 0), (ANIM, 0), (AF, 0),
             (PHP, 140), (F["dead"], 0), (F["tilt"], 0), (F["hs"], 0),
             (F["stop"], 0), (F["vx"], 0), (F["vz"], 0), (F["buf"], 0),
             (F["c3"], 0), (F["fight"], 0), (F["wave"], 0), (SFX_T, SFX_N),
             (F["py"], 0), (F["pvy"], 0), (F["acmb"], 0), (F["uwin"], 0),
             (F["sty"], 0), (F["chain"], 0), (F["cgr"], 0), (F["slow"], 0), (F["skip"], 0),
             (F["spd"], 0), (F["evf"], 0), (F["flipu"], 0), (F["tgt"], 0),
             (F["plc"], 0), (F["sec"], 0),
             (SY["n"], HORDE0), (SY["dx"], 0), (SY["dst"], 0),      # (the horde, anew)
             (SY["pts"], 0), (SY["combo"], 0), (SY["idle"], 0), (int(S_SHOWN), 255),
             *((int(S_REC) + i, 255) for i in range(5)),
             *((imp(i, "st"), 0) for i in range(N_IMP)))       # (P20b: no swarm)
for c, v in RETRY_CELLS:
    p.set(c, v)
for k in range(len(GATES)):                     # (P19: and every gate shut again)
    for half in (0, 2):
        a_, bit_ = GT_W[k * GT_N + half], GT_W[k * GT_N + half + 1]
        p.load(int(CMAP) + a_).push32(~bit_ & 0xFFFFFFFF).emit("and").store(int(CMAP) + a_)
if L5:                                          # (P38: and every bolt, and nothing in hand)
    for d_ in DOORS:
        if d_["kind"] == 1:
            for n_, sd_ in ((d_["a"], d_["sa"]), (d_["b"], d_["sb"])):
                p.load(int(CMAP) + n_).push32(~(3 << 2 * sd_) & 0xFFFFFFFF).emit("and").store(int(CMAP) + n_)
    for c_ in (KEYS, TAKEN, OPENED):
        p.set(c_, 0)
# (the wave: the three are marked gone, and the fight's own respawn -- below,
# this same frame -- fetches the new one, as the pause's QUIT always did)
for d in range(3):
    p.set(dslot(d, "st"), 4)
p.set(F["wave"], -1)
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
if CARTMESH:                                 # the pose is where its streams are: four offsets
    for cell_, step_ in ((UPPER + 1, CM_LEN[0]), (UPPER + 3, CM_LEN[1]), (LOWER + 1, CM_LEN[2]), (LOWER + 3, 0)):
        p.emit("dup").store(cell_)
        if step_:
            p.push(step_).emit("add")
    p.emit("drop")
    if L3:                                   # the others' clock: two frames a pose, the idle's sixty
        rv_ = p.label("rival")
        p.addi(RIV_T, 1).load(RIV_T).push(2 * NPOSE["idle"]).emit("lt", f"jz {rv_}_w", f"jmp {rv_}")
        p.mark(f"{rv_}_w")
        p.set(RIV_T, 0)
        p.mark(rv_)
    if RIVAL:                                # the rival's pose: the guard, from the player's own bank
        p.load(RIV_T).emit("shr 1").push(base["idle"]).emit("add").push(SPAN).emit("mul").push(int(BANK)).emit("add")
        for cell_, step_ in ((int(RDESC) + 1, CM_LEN[0]), (int(RDESC) + 3, CM_LEN[1]),
                             (int(RDESC) + 6, CM_LEN[2]), (int(RDESC) + 8, 0)):
            p.emit("dup").store(cell_)
            if step_:
                p.push(step_).emit("add")
        p.emit("drop")
    for e_ in ENEMY:                         # each of the crowd: its own place in its size's idle
        en_ = p.label("enemy")
        if L4:                               # (P37: the guard by its own clock; walking, the stride)
            p.load(e_["clk"]).emit("shr 1")
            p.load(e_["walk"]).emit(f"jz {en_}")
            p.emit("drop").load(e_["ph"]).emit("shr 16").push(31).emit("and").push(e_["T"]["walk"]).emit("add")
        else:
            p.load(RIV_T).emit("shr 1").push(e_["phase"]).emit("add")
            p.emit("dup").push(e_["T"]["n"]).emit("lt", f"jz {en_}_w", f"jmp {en_}")
            p.mark(f"{en_}_w")
            p.push(e_["T"]["n"]).emit("sub")
        p.mark(en_)
        p.push(e_["T"]["span"]).emit("mul").push(e_["T"]["bank"]).emit("add")
        p.emit("dup").store(e_["desc"] + 1).push(e_["T"]["lv"]).emit("add").store(e_["desc"] + 3)
else:
    pd_ = p.label("posedma")                     # (P13: not on a frame that pages a
    p.load(spec.OVL_GO).emit(f"jz {pd_}_go")     # scene in -- its handshake has the
    p.emit("drop", f"jmp {pd_}")                 # request, and the pose holds anyway)
    p.mark(f"{pd_}_go")
    p.store(spec.DMA_SRC)
    p.push(UPPER + 2).store(spec.DMA_DST)
    p.push(SPAN).store(spec.DMA_LEN)
    p.set(spec.DMA_GO, 1)
    p.mark(pd_)

if L1:
    p.load(PX).store(WTX).load(PZ).store(WTZ)     # (where the step would have put him)
keep_in_arena(PX, PZ, AR["ox"], AR["oz"])
if L1:
    # P25: THE WALL, REMEMBERED. In the air, a step the street refused is a
    # wall touched: which axis (or both), and which way he was going on it --
    # good for WJ_COYOTE frames.
    wd_ = p.label("walltouch")
    p.load(WALLT).emit(f"jz {wd_}_n")
    p.addi(WALLT, -1)
    p.mark(f"{wd_}_n")
    p.load(F["py"]).emit(f"jz {wd_}")
    p.load(PX).load(WTX).emit("eq").push(1).emit("xor")
    p.load(PZ).load(WTZ).emit("eq").push(1).emit("xor").push(2).emit("mul", "or", "dup", f"jz {wd_}_d")
    p.store(WALLA).set(WALLT, WJ_COYOTE)
    for t_, o_, s_ in ((WTX, AR["ox"], WSX), (WTZ, AR["oz"], WSZ)):
        p.push(0).load(t_).load(o_).emit("sub", "lt")           # going up the axis
        p.load(t_).load(o_).emit("sub").push(0).emit("lt", "sub").store(s_)   # ...or down: +1, -1
    p.emit(f"jmp {wd_}")
    p.mark(f"{wd_}_d")
    p.emit("drop")
    p.mark(wd_)
# (P21 gave the base a softened slide along walls, on a knob; the player
# turned it all the way off on glass -- "a wall is a wall" -- and P22 took
# it out. The archive's slide, above, is the base's.)

if BASE:
    # P23: IS HE ON THE SIDEWALK? Where he stands in his tile (u east, v
    # north of its middle), a sidewalk lies wherever a wall stands beside
    # him: past the curb line on an axis with no street on that side there,
    # or on the pad of a jutting corner. His feet ease up the curb's height.
    sw_ = p.label("swalk")
    p.push(0).store(W["dmg"])                                   # the height wanted
    city_node(p, PX, PZ)
    p.load(CT["n"]).push(0).emit("lt", f"jz {sw_}_on", f"jmp {sw_}_e")
    p.mark(f"{sw_}_on")
    p.load(PZ).push32(int((OXA + HT) * ONE)).emit("add")
    p.push32((1 << TSH) - 1).emit("and").push32(1 << (TSH - 1)).emit("sub").store(AR["u"])
    p.push32(int((OYA + HT) * ONE)).load(PX).emit("sub")
    p.push32((1 << TSH) - 1).emit("and").push32(1 << (TSH - 1)).emit("sub").store(AR["v"])
    for cell, hi_side, lo_side, out in ((AR["u"], 1, 3, "x"), (AR["v"], 0, 2, "y")):
        nb = p.label("sws")                    # this axis's side there, and |coordinate|
        p.load(CT["w"]).emit(f"shr {2 * hi_side}").push(3).emit("and").store(KP[out])
        p.push(0).load(cell).emit("lt", f"jz {nb}_n", f"jmp {nb}")
        p.mark(f"{nb}_n")
        p.load(CT["w"]).emit(f"shr {2 * lo_side}").push(3).emit("and").store(KP[out])
        p.push(0).load(cell).emit("sub").store(cell)
        p.mark(nb)
    LANE_Q, FAC_Q = int(CITY_LANE * ONE), int(FAC * ONE)
    # both sides open (a plaza's inside): no block at that corner
    p.load(KP["x"]).push(2).emit("eq").load(KP["y"]).push(2).emit("eq", "and").store(W["dg"])
    for a_, b_, sa in ((AR["u"], AR["v"], KP["x"]), (AR["v"], AR["u"], KP["y"])):
        nb = p.label("swa")
        p.push(LANE_Q).load(a_).emit("lt", f"jz {nb}")          # past the curb line on a
        p.load(b_).push(FAC_Q).emit("lt", f"jz {nb}_c")         # beside the junction:
        p.load(sa).emit(f"jz {sw_}_up", f"jmp {nb}")            # a closed side is a wall
        p.mark(f"{nb}_c")                                       # beside an arm: its corner
        p.load(W["dg"]).emit(f"jz {sw_}_up")                    # block's wall
        p.mark(nb)
    p.push(LANE_Q).load(AR["u"]).emit("lt").push(LANE_Q).load(AR["v"]).emit("lt", "and")
    p.emit(f"jz {sw_}_e")                                       # a jutting corner's pad
    p.load(W["dg"]).emit(f"jz {sw_}_up", f"jmp {sw_}_e")
    p.mark(f"{sw_}_up")
    p.push(int(CURB * ONE)).store(W["dmg"])
    p.mark(f"{sw_}_e")
    p.load(W["dmg"]).load(GYC).emit("sub", "dup").push(0).emit("lt", f"jz {sw_}_p")
    p.emit(f"jmp {sw_}_q")                                      # (toward it by a quarter,
    p.mark(f"{sw_}_p")                                          # rounded so it arrives: up
    p.push(3).emit("add")                                       # rounds up, and down the
    p.mark(f"{sw_}_q")                                          # shift already rounds down)
    p.emit("shr 2").load(GYC).emit("add").store(GYC)

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
if L3:
    # P36: A FIST LANDS ON THE KEY (the superman punch has to LAND on
    # something): a blow whose fist comes within a unit of it, each way, has
    # struck it -- the blow's own hitstop and shake, the burst on the key,
    # and it rings and leaps as it does for a shot. Once a blow.
    fk_ = p.label("fistkey")
    p.load(KEY).load(F["con"]).emit("or", f"jz {fk_}_k", f"jmp {fk_}")
    p.mark(f"{fk_}_k")
    item_exists(p).emit(f"jz {fk_}")
    for k_, f_ in ((KX, "fx"), (KZ, "fz")):
        p.load(k_).load(F[f_]).emit("sub", "dup").push(0).emit("lt", f"jz {fk_}_a{f_}")
        p.push(0).emit("swap", "sub")
        p.mark(f"{fk_}_a{f_}")
        p.push(int(1.0 * ONE)).emit("lt", f"jz {fk_}")
    p.set(F["con"], 1).set(KHIT, 40).emit(f"call {L_RING}")
    row(PMT, F["mv"], "stop")
    p.emit("dup").store(F["stop"]).store(F["shake"])
    p.load(KX).store(int(SPK)).push(int(1.0 * ONE)).store(int(SPK) + 1).load(KZ).store(int(SPK) + 2)
    p.set(int(SPK) + 3, SPARK_FOR).set(SPKM, HOT_M)
    p.mark(fk_)
if L4:
    # P37: A FIST LANDS ON AN ENEMY: its fist within three quarters of a unit
    # of one that is up, each way -- once a blow. The blow's own hitstop and
    # shake; what the move is worth off it (a jab 1, a hook or an uppercut 2,
    # the haymaker 4); it is held, flashes, and is driven a third of a unit
    # the way the blow went (a wall a wall).
    fe_ = p.label("fistenemy")
    p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {fe_}_f", f"jmp {fe_}")
    p.mark(f"{fe_}_f")
    for e_ in ENEMY:
        fn_ = p.label("fe")
        ex_, ez_ = int(e_["pos"]), int(e_["pos"]) + 1
        p.load(F["con"]).emit(f"jz {fn_}_c", f"jmp {fe_}")
        p.mark(f"{fn_}_c")
        p.load(e_["st"]).push(1).emit("eq", f"jz {fn_}")
        for c_, f_ in ((ex_, "fx"), (ez_, "fz")):
            p.load(c_).load(F[f_]).emit("sub", "dup").push(0).emit("lt", f"jz {fn_}_a{f_}")
            p.push(0).emit("swap", "sub")
            p.mark(f"{fn_}_a{f_}")
            p.push(int(0.75 * ONE)).emit("lt", f"jz {fn_}")
        p.set(F["con"], 1)
        p.push(int(FDMG)).load(F["mv"]).emit("add", "loadi").store(W["dmg"])
        row(PMT, F["mv"], "stop")
        p.emit("dup", "dup").store(F["stop"]).store(F["shake"]).push(12).emit("add").store(W["stop"])
        enemy_hurt(p, e_)
        p.load(ex_).store(int(e_["old"])).load(ez_).store(int(e_["old"]) + 1)
        sin_of(p, cell=HEAD)
        p.push(int(0.35 * ONE)).emit("mulq").load(ex_).emit("swap", "sub").store(ex_)
        sin_of(p, 256, cell=HEAD)
        p.push(int(0.35 * ONE)).emit("mulq").load(ez_).emit("add").store(ez_)
        keep_in_arena(e_["pos"], int(e_["pos"]) + 1, e_["old"], int(e_["old"]) + 1)
        p.mark(fn_)
    p.mark(fe_)
if L2:
    # P29: WHERE IT LANDED. Shadow boxing hits the air; the spark is at his
    # fist the first frame the blow is out -- exactly where it would have
    # landed.
    sk2 = p.label("airspark")
    p.load(AF)
    row(PMT, F["mv"], "start")
    p.emit("eq", f"jz {sk2}")
    for k_, c_ in enumerate(("fx", "fy", "fz")):
        p.load(F[c_]).store(int(SPK) + k_)
    p.set(int(SPK) + 3, SPARK_FOR).set(SPKM, SPARK_M)
    # (P34: a shot's kick is its own. This line gave the plain shot a shake
    # of -1, which the lens then counted DOWN from: after every plain shot
    # the lens trembled a twentieth of a unit a frame until his next blow.)
    p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {sk2}_f", f"jmp {sk2}")
    p.mark(f"{sk2}_f")
    row(PMT, F["mv"], "stop")                     # (P30: and a terminator's weight shakes
    p.push(5).emit("sub", "shr 2").store(F["shake"])   # the lens: 2, 2, the haymaker 5)
    p.mark(sk2)
p.mark(nf_)
p.load(F["act"]).store(IACT)                    # P20b: the swarm reads it after

# ---- the camera: the archive's spring follow, in integers -------------------
# CY eases an eighth of the shortest arc toward his yaw each frame. An
# arithmetic >> 3 rounds toward minus infinity, so a small NEGATIVE gap
# would keep closing while a small positive one stalled at 0 -- the camera
# parked up to 2.8 degrees off on one side only. Inside 8 units it snaps.
snap_l = p.label("snap")
CAM_TURN = 36                   # units of 1024 a frame: 12.7 degrees
THREAT_KEEP = 90                # P18: a threat is kept within 32 degrees of the line
DREST = 54                      # a demon's wait, squared up, before it swings (P16)
# P20b: RELENTLESS, DEEPER IN (the player chose "the three attack together,
# wait less, replace each other at once"). The first district keeps the
# fight every mechanic was tuned on; from the second all three may attack
# at once, and each district starts the wait REL_STEP frames in (to
# REL_MAX: the 30-frame tell is never cut)
REL_STEP, REL_MAX = 5, 20
TOKENS = 2                      # demons that may be told or swinging at once (P20b:
                                # all three past the first district, still on screen)
# (HORDE0, HSTEP, CLEAR_FOR: with P18's first constants, the retry reads them)
ONSCREEN_TAN2 = int(0.30 * ONE)  # on screen: within ~29 degrees of the lens's line
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
p.load(F["brg"]).emit("dup").store(W["oy"]).store(F["cgr"])   # (f_cgr: its last bearing)
p.mark(by_)
if L3:                                           # P36: locked, the lens is on the item's line:
    lb_ = p.label("locklens")                    # in the run he crosses the shot, the item
    p.load(LOCK).emit(f"jz {lb_}")               # beyond him
    p.load(LBRG).store(W["oy"])
    p.mark(lb_)
if L2:
    # P34: THE AIM. B held past the hold knob -- time slowed for the shot --
    # the lens comes round behind his BODY and looks down the sight: a shot
    # aimed to the side or behind is a shot he can see land. (A tap leaves
    # the lens where it is.) Let go, it comes back to his steering.
    # ...once the shot has landed (AIM_LINGER frames).
    al_ = p.label("aimlens")
    knob(p, "hold").load(GT["shoot"]).emit("lt", f"jz {al_}_n")
    p.set(AIMT, AIM_LINGER + 1)
    p.mark(f"{al_}_n")
    p.load(AIMT).emit(f"jz {al_}")
    p.addi(AIMT, -1)
    p.load(HEAD).store(W["oy"])
    p.mark(al_)
# P18: THE THREAT IS IN THE FRAME. On glass: "getting hit from behind is
# annoying -- if I'm about to be attacked the camera pans just enough to
# have the enemy in view." The most urgent demon -- swinging, or in the
# last 30 frames of its wait (the amber tell) -- is kept within THREAT_KEEP
# of the camera's line: the line turns toward it just that far, and no
# farther (CAM_TURN still caps the turn). The target, framed already, is
# left to targeting.
th_ = p.label("threat")
p.push(DREST - 30).store(W["dc"]).push(-1).store(W["k"])
for d in range(3):
    nx = p.label("th_n")
    p.load(dslot(d, "st")).push(2).emit("lt", f"jz {nx}")          # free or swinging
    p.load(dslot(d, "ai")).load(dslot(d, "st")).push(DREST).emit("mul", "add", "dup")
    p.load(W["dc"]).emit("swap", "lt", f"jz {nx}_f")               # more urgent
    p.store(W["dc"]).set(W["k"], d).emit(f"jmp {nx}")
    p.mark(f"{nx}_f")
    p.emit("drop")
    p.mark(nx)
p.load(W["k"]).push(0).emit("lt", f"jz {th_}_y", f"jmp {th_}")
p.mark(f"{th_}_y")
p.load(W["k"]).push(1).emit("add").load(F["tgt"]).emit("eq", f"jz {th_}_b", f"jmp {th_}")
p.mark(f"{th_}_b")
p.load(W["k"]).store(F["brg"]).emit(f"call {L_BRG}")
p.load(F["brg"]).load(W["oy"]).emit("sub").push(512).emit("add")
p.push(1023).emit("and").push(512).emit("sub")                     # its gap from the line
p.emit("dup").push(THREAT_KEEP).emit("swap", "lt", f"jz {th_}_l")  # KEEP < gap: turn left
p.emit("drop").load(F["brg"]).push(THREAT_KEEP).emit("sub", f"jmp {th_}_s")
p.mark(f"{th_}_l")
p.push(-THREAT_KEEP).emit("lt", f"jz {th_}")                       # gap < -KEEP: right
p.load(F["brg"]).push(THREAT_KEEP).emit("add")
p.mark(f"{th_}_s")
p.push(1023).emit("and").store(W["oy"])
p.mark(th_)
p.load(W["oy"]).load(CY).emit("sub").push(512).emit("add")
p.push(1023).emit("and").push(512).emit("sub").store(T)   # d in -512..511
if L1:
    # P24: IN THE RUN THE LENS TRAILS -- it comes round to his heading by
    # the trail knob's share of the gap a frame (an eighth, elsewhere), and
    # by a unit at least, so it arrives without a snap
    tr_ = p.label("trail")
    p.load(F["sty"]).push(1).emit("eq", f"jz {tr_}")
    p.load(T)
    knob(p, "trail").emit("mulq", "dup", f"jz {tr_}_s")
    p.emit(f"jmp {tr_}_a")
    p.mark(f"{tr_}_s")
    p.emit("drop").push(0).load(T).emit("lt").load(T).push(0).emit("lt", "sub")   # its sign
    p.mark(f"{tr_}_a")
    p.load(CY).emit("add").push(1023).emit("and").store(CY)
    p.emit(f"jmp {snap_l}_d")
    p.mark(tr_)
p.load(T).emit("shr 3", "dup", f"jz {snap_l}")
# P16: ...and no faster than CAM_TURN a frame. An eighth of a half turn is
# 22 degrees in one frame, and a new lock asks for exactly that: the tape
# has a swing past 3 degrees a frame every 3.5 seconds.
for lim, cmp_ in ((CAM_TURN, ("dup", f"push {CAM_TURN}", "lt")),
                  (-CAM_TURN, (f"push {-CAM_TURN}", "over", "lt"))):
    ok_ = p.label("camcap")
    p.emit(*cmp_, f"jz {ok_}_c", f"jmp {ok_}")
    p.mark(f"{ok_}_c")
    p.emit("drop").push(lim)
    p.mark(ok_)
p.load(CY).emit("add").push(1023).emit("and").store(CY)
p.emit(f"jmp {snap_l}_d")
p.mark(snap_l)
p.emit("drop").load(W["oy"]).store(CY)                      # within 8: snap
p.mark(f"{snap_l}_d")
# ...and stands its eased distance behind him along ITS yaw, leaning by
# its eased shoulder (P12: the mode's -- the tank 3 and square, as before)
CWd = CAM_W
md_ = p.label("camd")
# P18: ONE SHOT A MODE. The tank 3.0 back and square; the boxer 4.0 on its
# cross; the run 5.4, wide, on the target; targeting 2.8 over the right
# shoulder at the target -- and in its FOCUS, in to 2.2. The distance and
# the lean ease between them (DIST_EASE), the yaw at most CAM_TURN.
knob(p, "camd").store(W["dmg"]).push(0).store(W["stop"])
for sty_, d_, sh_ in ((2, BOX_D, BOX_SH), (1, FENCE_D, BOX_SH), (SQ_TARGET, TGT_D, TGT_SH)):
    nm = p.label("cm")
    p.load(F["sty"]).push(sty_).emit("eq", f"jz {nm}")
    if L1 and sty_ in (1, 2):                    # (P24: the boxer's and the run's, knobs; square)
        knob(p, "boxcam" if sty_ == 2 else "runcam").store(W["dmg"]).push(0).store(W["stop"])
    else:
        p.push(int(d_ * ONE)).store(W["dmg"]).push(int(sh_ * ONE)).store(W["stop"])
    p.mark(nm)
p.load(F["sty"]).push(SQ_TARGET).emit("eq")      # FOCUS: targeting, an attack held --
p.push(FOCUS_HOLD).load(GT["carve"]).emit("lt")
p.push(FOCUS_HOLD).load(GT["special"]).emit("lt", "or", "and")
p.load(F["slow"]).emit("or", f"jz {md_}_e")       # -- or a launcher's slow motion
p.push(int(FOCUS_D * ONE)).store(W["dmg"])
p.mark(f"{md_}_e")
if L3:                                           # P35: locked -- targeting's lens (P18): 2.8
    lc_ = p.label("lockcam")                     # behind, over his right shoulder, the
    p.load(LOCK).emit(f"jz {lc_}")               # item ahead of him in the shot
    p.load(F["sty"]).push(1).emit("eq", f"jz {lc_}_t", f"jmp {lc_}")   # (the run: its own lens)
    p.mark(f"{lc_}_t")
    p.push(int(TGT_D * ONE)).store(W["dmg"]).push(int(TGT_SH * ONE)).store(W["stop"])
    p.mark(lc_)
if L2:
    # P31: TIME SLOWED, THE LENS GOES TO WHERE THE BLOW LANDS (the player:
    # "the slow motions need cameras focused on the hit location"): in to
    # the fcam knob's distance, over his right shoulder -- and, below, it
    # LOOKS at the place a blow's reach ahead of his body.
    fo_ = p.label("focuscam")
    p.load(SLOWON).emit("dup").store(W["k"])
    p.emit(f"jz {fo_}")
    knob(p, "fcam").store(W["dmg"]).push(int(FOCUS_SH * ONE)).store(W["stop"])
    p.mark(fo_)
    p.push(0).load(W["k"]).emit(f"jz {fo_}_w")
    p.emit("drop").push(ONE)
    p.mark(f"{fo_}_w")
    p.load(FOCB).emit("sub", "shr 2").load(FOCB).emit("add").store(FOCB)
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
knob(p.load(F["py"]), "camh").emit("add").store(spec.CAM_Y)   # (P9: up with him)
if L2:
    # P31: THE BOXER'S LENS WANDERS (the player: "in the boxer the camera is
    # locked on the player but can wander in position"). Its place comes
    # after him by the wander knob's share of the way a frame -- it trails
    # his steps -- and from wherever it is it looks AT him (below). Out of
    # the stance the share climbs back to all of it: the follow, as it was.
    wn_ = p.label("wander")
    p.load(F["sty"]).push(2).emit("eq", f"jz {wn_}_o")
    knob(p, "wander").load(WR).emit("sub", "shr 2").load(WR).emit("add").store(WR)
    p.emit(f"jmp {wn_}")
    p.mark(f"{wn_}_o")
    p.load(WR).push(ONE >> 4).emit("add", "dup").push(ONE).emit("lt", f"jz {wn_}_c")
    p.store(WR).emit(f"jmp {wn_}")
    p.mark(f"{wn_}_c")
    p.emit("drop").set(WR, ONE)
    p.mark(wn_)
    for have, reg in ((BCX, spec.CAM_X), (BCZ, spec.CAM_Z)):
        p.load(reg).load(have).emit("sub").load(WR).emit("mulq").load(have).emit("add", "dup").store(have)
        p.store(reg)

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
if L2:
    # P32: NOT IN LAYER 2. This shot (the archive's: the tank, a strike
    # button held, the lens goes 3.6 up and back to choose an aim) took the
    # frame whenever he stood in the tank with X or Y held -- which is
    # layer 2's slowed time: on the tape 10,776 frames of it, the lens far
    # overhead instead of at the blow. The slowed lens is this layer's.
    p.emit(f"jmp {op}_p3")
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
# P18: THE LENS STAYS IN THE STREET. On glass the camera "goes wonky,
# targeting down street alleys": over the shoulder, beside a wall, the lens
# stood inside the building. Whatever shot placed it, a lens off the street
# (the arena's own test) is pulled halfway to him, and again if need be.
# (halfway, once, for a soft pull; then the bodies' own slide, from him --
# whichever axis stays in the street -- so the lens is never left outside)
cmc = p.label("lens")
if BASE:
    # P21: THE FOLLOW KEEPS ITS DISTANCE (the player: "make sure the camera
    # stays the same distance to the player when a wall is up close behind").
    # The tank's lens is straight behind him, so a wall it backs into faces
    # away from it and is not drawn: it may stand in the building.
    # P23: on the sidewalk he walks 0.6 from a wall, and a lens BESIDE a
    # wall -- not behind one -- stood in the building looking along it, and
    # that side of the street was gone. So a lens off the street (it may
    # come 0.15 from a wall) is brought back to the wall's face, straight
    # across (found by halving between where it is and where he is) --
    # unless that leaves it under three quarters of its distance: then the
    # wall is behind him, out of the shot, and the lens stays in it. The
    # move is EASED (a quarter a frame), and from wherever it ends the lens
    # looks AT him, so he keeps the middle of the shot.
    p.set(AWC, LENS_W)
    p.set(W["qx"], 0).set(W["qz"], 0)                       # the move wanted
    p.load(spec.CAM_X).store(AR["x"]).load(spec.CAM_Z).store(AR["z"])
    p.emit(f"call {L_ARENA}", f"jz {cmc}_b", f"jmp {cmc}_r")
    p.mark(f"{cmc}_b")
    for ax, (cam_a, me_a, cam_o, tgt) in enumerate(((spec.CAM_Z, PZ, spec.CAM_X, W["qz"]),
                                                    (spec.CAM_X, PX, spec.CAM_Z, W["qx"]))):
        nx = p.label("lensax")

        def probe(val_ops, ax=ax, cam_o=cam_o):              # ( -- inside? ) this axis at val
            if ax == 0:
                p.load(cam_o).store(AR["x"])
                val_ops()
                p.store(AR["z"])
            else:
                val_ops()
                p.store(AR["x"])
                p.load(cam_o).store(AR["z"])
            p.emit(f"call {L_ARENA}")
        probe(lambda me_a=me_a: p.load(me_a))                # his own place on this axis:
        p.emit(f"jz {nx}")                                   # on the street? (else not this axis)
        p.load(me_a).store(W["bx"]).load(cam_a).store(W["bz"])   # in, out
        for _ in range(5):
            hb = p.label("lensh")
            probe(lambda: p.load(W["bx"]).load(W["bz"]).emit("add", "shr 1"))
            p.emit(f"jz {hb}_o")
            p.load(W["bx"]).load(W["bz"]).emit("add", "shr 1").store(W["bx"]).emit(f"jmp {hb}")
            p.mark(f"{hb}_o")
            p.load(W["bx"]).load(W["bz"]).emit("add", "shr 1").store(W["bz"])
            p.mark(hb)
        # far enough still?  (his distance on the other axis is unchanged)
        p.load(W["bx"]).load(me_a).emit("sub", "dup", "mulq")
        p.load(cam_o).load(PX if ax == 0 else PZ).emit("sub", "dup", "mulq", "add")
        knob(p, "camd").push(int(0.75 * ONE)).emit("mulq", "dup", "mulq")
        p.emit("swap", "lt", f"jz {cmc}_r")                  # (3/4 d)^2 < it: take it
        p.load(W["bx"]).load(cam_a).emit("sub").store(tgt)
        p.emit(f"jmp {cmc}_r")
        p.mark(nx)
    p.mark(f"{cmc}_r")
    p.set(AWC, AR_W)
    for want, have, reg in ((W["qx"], LDX, spec.CAM_X), (W["qz"], LDZ, spec.CAM_Z)):
        p.load(want).load(have).emit("sub", "shr 2").load(have).emit("add", "dup").store(have)
        p.load(reg).emit("add").store(reg)
    lk_ = p.label("lenslook")
    for have in (LDX, LDZ):                                  # (moved at all? by 1/256)
        p.load(have).emit("dup", "mulq")
    p.emit("add").push(1).emit("swap", "lt", f"jz {lk_}")
    p.load(PX).load(spec.CAM_X).emit("sub").store(W["qx"])
    p.load(PZ).load(spec.CAM_Z).emit("sub").store(W["qz"])
    p.emit(f"call {L_YAW}")
    p.load(F["brg"]).store(spec.CAM_YAW)
    p.mark(lk_)
    p.emit(f"jmp {cmc}")
p.load(spec.CAM_X).store(AR["x"]).load(spec.CAM_Z).store(AR["z"])
p.emit(f"call {L_ARENA}", f"jz {cmc}_o", f"jmp {cmc}")
p.mark(f"{cmc}_o")
for reg, me, w in ((spec.CAM_X, PX, W["bx"]), (spec.CAM_Z, PZ, W["bz"])):
    p.load(reg).load(me).emit("add", "shr 1").store(w)
keep_in_arena(W["bx"], W["bz"], PX, PZ)
p.load(W["bx"]).store(spec.CAM_X).load(W["bz"]).store(spec.CAM_Z)
p.mark(cmc)
if L2:
    lk2 = p.label("look")
    p.load(WR).push(ONE).emit("lt", f"jz {lk2}")             # (wandering: at him)
    p.load(PX).load(spec.CAM_X).emit("sub").store(W["qx"])
    p.load(PZ).load(spec.CAM_Z).emit("sub").store(W["qz"])
    p.emit(f"call {L_YAW}")
    p.load(F["brg"]).store(spec.CAM_YAW)
    p.mark(lk2)
    # the blow's place: a reach ahead of his body, eased (it is where he
    # will hit before he has turned to it)
    for have, me, plus, neg in ((HX, PX, 0, True), (HZ, PZ, 256, False)):
        sin_of(p, plus, cell=HEAD)
        p.push(int(FOCUS_REACH * ONE)).emit("mulq")
        if neg:
            p.push(0).emit("swap", "sub")
        p.load(me).emit("add").load(have).emit("sub", "shr 2").load(have).emit("add").store(have)
    p.push(64).load(FOCB).emit("lt", f"jz {lk2}_f")
    p.load(HX).load(spec.CAM_X).emit("sub").store(W["qx"])
    p.load(HZ).load(spec.CAM_Z).emit("sub").store(W["qz"])
    p.emit(f"call {L_YAW}")
    p.load(F["brg"]).load(spec.CAM_YAW).emit("sub").push(512).emit("add")
    p.push(1023).emit("and").push(512).emit("sub")           # the gap, -512..511
    p.load(FOCB).emit("mul", "shr 16")
    p.load(spec.CAM_YAW).emit("add").push(1023).emit("and").store(spec.CAM_YAW)
    p.load(spec.CAM_Y).load(FOCB).push(int(FOCUS_DROP * ONE)).emit("mulq", "sub").store(spec.CAM_Y)
    p.mark(f"{lk2}_f")
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
DWALK = int(0.028 * ONE)       # P16: was 0.020. Still slower than his 0.032, so
                               # distance is still his to make -- but a ring
                               # 7.8 out is under four seconds away, not five
DREACH2 = int(1.5 ** 2 * ONE)  # closer than 1.5 they stop and square up
DCONE = int(np.tan(0.46) ** 2 * ONE)
CONE_OUT = int(np.tan(0.60) ** 2 * ONE)            # tear.py ENEMY_CONE_EXIT
# (DREST = 54, defined with P18's constants: the camera reads it first)
                               # P16: was 74. Squared up and in reach, it
                               # swings in under a second; the last 24 frames
                               # of the wait are TOLD (L_TELE, amber)
DTEMP = {k: cart.var("dt_" + k) for k in
         ("ty", "fx", "fz", "dx", "dz", "cr", "dot", "s", "c")}


# ---- P18: ATTACK TOKENS -- "keep the enemies on screen the ones about to
# attack". A demon's wait may cross into its tell (its last 30 frames, the
# amber) only holding one of TOKENS, and only ON SCREEN; held, it waits at
# the threshold, squared up, until both are true. TOKC counts the tokens
# held now: every demon swinging or already told.
p.set(TOKC, 0)
for d in range(3):
    nx = p.label("tok")
    p.load(dslot(d, "st")).push(1).emit("eq")
    p.load(dslot(d, "st")).emit(f"jz {nx}_w")
    p.emit(f"jmp {nx}_c")
    p.mark(f"{nx}_w")
    p.push(DREST - 31).load(dslot(d, "ai")).emit("lt", "or")
    p.mark(f"{nx}_c")
    p.load(TOKC).emit("add").store(TOKC)
# ---- the wave: each demon's mind, on a copy of its slot ----------------------
for d in range(3):
    p.push(int(DS) + d * NF).store(CP["src"]).push(int(CUR)).store(CP["dst"])
    p.push(NF).store(CP["n"]).emit(f"call {L_COPY}")
    p.set(F["dmi"], d + 1)                       # (P11: the aim gun asks who)
    p.emit(f"call {L_DMIND}")
    p.push(int(CUR)).store(CP["src"]).push(int(DS) + d * NF).store(CP["dst"])
    p.push(NF).store(CP["n"]).emit(f"call {L_COPY}")
# P19: THE LEASH. A demon slides along a wall toward him, which takes it
# round one corner and no further: lost in the streets it would stand at
# a wall for ever. One that is neither in his node nor a node his streets
# reach, and is not on screen, is placed again where a fresh one would be
# (SPN), keeping everything but where it stands. Behind the walls, a demon
# is wherever the fight needs it.
city_node(p, PX, PZ)
p.load(CT["n"]).store(CT["n1"]).load(CT["w"]).store(CT["w1"])
for d in range(3):
    ls = p.label("leash")
    p.load(CT["n1"]).push(0).emit("lt", f"jz {ls}_p", f"jmp {ls}")     # he is off the map
    p.mark(f"{ls}_p")
    p.load(dslot(d, "st")).push(4).emit("eq", f"jz {ls}_a", f"jmp {ls}")   # gone
    p.mark(f"{ls}_a")
    city_node(p, dslot(d, "x"), dslot(d, "z"))
    p.load(CT["n"]).load(CT["n1"]).emit("sub", "dup").store(CT["k"])
    p.emit(f"jz {ls}")                                                 # his node
    for k_, df in enumerate((CS + 1, CS - 1, -CS + 1, -CS - 1)):   # (a plaza's
        p.load(CT["k"]).push(df).emit("eq", f"jz {ls}_q{k_}")      # far corner:
        p.load(CT["w"]).push(0xAA).emit("and", f"jz {ls}_q{k_}")   # both
        p.load(CT["w1"]).push(0xAA).emit("and", f"jz {ls}_q{k_}")  # in it)
        p.emit(f"jmp {ls}")
        p.mark(f"{ls}_q{k_}")
    for k in range(4):
        p.load(CT["k"]).push(CSTEP[k]).emit("eq", f"jz {ls}_k{k}")
        p.load(CT["w1"]).emit(f"shr {2 * k}").push(3).emit("and", f"jz {ls}_k{k}")
        p.emit(f"jmp {ls}")                                            # a street away
        p.mark(f"{ls}_k{k}")
    for cell, cam in (("x", spec.CAM_X), ("z", spec.CAM_Z)):      # in the fog:
        p.load(dslot(d, cell)).load(cam).emit("sub", "dup")       # unseen (and
        p.push(0).emit("lt", f"jz {ls}_{cell}p")                  # before the
        p.push(0).emit("swap", "sub")                             # squares can
        p.mark(f"{ls}_{cell}p")                                   # overflow)
        p.push(LEASH_FOG).emit("swap", "lt", f"jz {ls}_{cell}n", f"jmp {ls}_off")
        p.mark(f"{ls}_{cell}n")
    sin_of(p, cell=CY)                                    # on screen? (the
    p.load(dslot(d, "x")).load(spec.CAM_X).emit("sub", "mulq")   # tokens' test:
    p.push(0).emit("swap", "sub")                         # dot > 0, cross^2 <
    sin_of(p, 256, cell=CY)                               # tan^2 dot^2)
    p.load(dslot(d, "z")).load(spec.CAM_Z).emit("sub", "mulq", "add").emit("dup").store(W["dc"])
    p.push(0).emit("swap", "lt", f"jz {ls}_off")
    sin_of(p, 256, cell=CY)
    p.load(dslot(d, "x")).load(spec.CAM_X).emit("sub", "mulq")
    sin_of(p, cell=CY)
    p.load(dslot(d, "z")).load(spec.CAM_Z).emit("sub", "mulq", "add", "dup", "mulq")
    p.load(W["dc"]).emit("dup", "mulq").push(ONSCREEN_TAN2).emit("mulq", "lt", f"jz {ls}_off")
    p.emit(f"jmp {ls}")
    p.mark(f"{ls}_off")
    p.load(SPN).push(1 << d).emit("or").store(SPN)
    p.mark(ls)
# ---- P20b: THE SWARM, each frame (its constants with the demons' slots) -----
L_ISP = [p.label(f"isp{k}") for k in range(4)]   # place one two streets on
ICX, ICZ, IWK, IKILL = (cart.var(k) for k in ("imp_cx", "imp_cz", "imp_wake", "imp_kill"))
ims = p.label("imps")
p.set(IKILL, 0).set(IWK, 0)
p.load(CT["n1"]).push(0).emit("lt", f"jz {ims}_on", f"jmp {ims}_end")   # (off the map)
p.mark(f"{ims}_on")
p.load(CT["n1"]).emit("shr 4", f"shl {TSH}").push32(int(OYA * ONE)).emit("swap", "sub").store(ICX)
p.load(CT["n1"]).push(CS - 1).emit("and", f"shl {TSH}").push32(int(OXA * ONE))
p.emit("sub").store(ICZ)
p.load(WOKE).emit(f"jz {ims}_w")                       # awake, and his district
p.load(CT["w1"]).emit("shr 23").push(15).emit("and").load(LVL).emit("eq").store(IWK)
p.mark(f"{ims}_w")
for i in range(N_IMP):
    e = p.label("imp")
    p.load(imp(i, "st")).emit(f"jz {e}_none")
    p.load(imp(i, "st")).push(2).emit("eq", f"jz {e}_up")
    # FALLING: down, then gone
    p.addi(imp(i, "t"), 1)
    p.load(imp(i, "t")).push(IMP_FALL).emit("lt", f"jz {e}_gone", f"jmp {e}")
    p.mark(f"{e}_gone")
    p.set(imp(i, "st"), 0).emit(f"jmp {e}")
    # NONE: one comes out of the haze -- while the district is awake and his,
    # four at first and one more a district, one every eight frames
    p.mark(f"{e}_none")
    p.load(IWK).emit(f"jz {e}")
    p.push(i).load(LVL).load(IMP_BASE).emit("add", "lt", f"jz {e}")
    p.load(spec.REG_FRAME).push(7).emit("and").push(i).emit("eq", f"jz {e}")
    p.emit(f"call {L_ISP[i % 4]}")
    for c, w in (("x", "bx"), ("ox", "bx"), ("z", "bz"), ("oz", "bz")):
        p.load(W[w]).store(imp(i, c))
    p.set(imp(i, "st"), 1).set(imp(i, "t"), IMP_CD // 2 + 3 * i).emit(f"jmp {e}")
    # UP
    p.mark(f"{e}_up")
    p.load(IWK).emit(f"jz {e}_drop")                  # the district fell: so do they
    # struck? any live blow: a fist through it, or a shot down its line
    p.load(IACT).emit(f"jz {e}_nh")
    p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {e}_fist")
    sin_of(p, cell=HEAD)
    p.store(W["s"])
    sin_of(p, 256, cell=HEAD)
    p.store(W["c"])                                   # fwd = (-s, c)
    p.load(imp(i, "x")).load(PX).emit("sub").store(W["qx"])
    p.load(imp(i, "z")).load(PZ).emit("sub").store(W["qz"])
    p.load(W["qz"]).load(W["c"]).emit("mulq").load(W["qx"]).load(W["s"]).emit("mulq", "sub")
    p.emit("dup").push(0).emit("swap", "lt", f"jz {e}_gn")            # ahead: 0 < along
    p.push32(int(13 * ONE)).emit("lt", f"jz {e}_nh")                  # ...< 13
    p.load(W["qx"]).load(W["c"]).emit("mulq").load(W["qz"]).load(W["s"]).emit("mulq", "add")
    p.emit("dup", "mulq").push(int(0.7 ** 2 * ONE)).emit("lt", f"jz {e}_nh", f"jmp {e}_kill")
    p.mark(f"{e}_gn")
    p.emit("drop", f"jmp {e}_nh")
    p.mark(f"{e}_fist")
    for a, c in ((F["fx"], imp(i, "x")), (F["fz"], imp(i, "z"))):
        p.load(a).load(c).emit("sub", "dup", "mulq")
    p.load(F["fy"]).push(int(0.9 * IMP_SCALE * ONE)).emit("sub", "dup", "mulq", "add", "add")
    p.push(IMP_REACH2).emit("lt", f"jz {e}_nh")
    p.mark(f"{e}_kill")                               # it falls: style, a spark
    p.load(SY["pts"]).push(IMP_STYLE * 16).emit("add").store(SY["pts"])
    p.set(SY["idle"], 0).set(IKILL, 1)
    p.load(imp(i, "x")).store(int(SPK)).push(int(0.8 * ONE)).store(int(SPK) + 1)
    p.load(imp(i, "z")).store(int(SPK) + 2).set(int(SPK) + 3, SPARK_FOR)
    p.mark(f"{e}_drop")
    p.set(imp(i, "st"), 2).set(imp(i, "t"), 0).emit(f"jmp {e}")
    p.mark(f"{e}_nh")
    # too far (lost in the streets, or left behind): gone, to come again
    for a, c in ((PX, imp(i, "x")), (PZ, imp(i, "z"))):
        p.load(a).load(c).emit("sub", "dup").push(0).emit("lt", f"jz {e}_a{a}")
        p.push(0).emit("swap", "sub")
        p.mark(f"{e}_a{a}")
        p.push32(int((FOG_FULL + 4) * ONE)).emit("swap", "lt", f"jz {e}_n{a}")
        p.set(imp(i, "st"), 0).emit(f"jmp {e}")
        p.mark(f"{e}_n{a}")
    p.load(PX).load(imp(i, "x")).emit("sub", "dup", "mulq")
    p.load(PZ).load(imp(i, "z")).emit("sub", "dup", "mulq", "add").store(W["d2"])
    # it turns, every fourth frame: far off, to the middle of his junction
    # (so it comes down the streets, not into their walls); near, to its
    # place in the ring round him
    p.load(spec.REG_FRAME).push(3).emit("and").push(i & 3).emit("eq", f"jz {e}_ft")
    p.load(W["d2"]).push(IMP_HOME2).emit("lt", f"jz {e}_far")
    # (the ring is the CAMERA's: its places spread across the front and the
    # sides of the shot, never between the lens and him -- a crowd in view)
    sin_of(p, IMP_SPREAD[i], cell=CY)
    p.push(int(IMP_RING * ONE)).emit("mulq").load(PX).emit("swap", "sub").store(W["qx"])
    sin_of(p, IMP_SPREAD[i] + 256, cell=CY)
    p.push(int(IMP_RING * ONE)).emit("mulq").load(PZ).emit("add").store(W["qz"])
    p.emit(f"jmp {e}_aim")
    p.mark(f"{e}_far")
    p.load(ICX).store(W["qx"]).load(ICZ).store(W["qz"])
    p.mark(f"{e}_aim")
    p.load(W["qx"]).load(imp(i, "x")).emit("sub").store(W["qx"])
    p.load(W["qz"]).load(imp(i, "z")).emit("sub").store(W["qz"])
    p.emit(f"call {L_YAW}")
    p.load(F["brg"]).store(imp(i, "yaw"))
    p.mark(f"{e}_ft")
    # its claws
    p.load(imp(i, "t")).emit(f"jz {e}_c")
    p.addi(imp(i, "t"), -1).emit(f"jmp {e}_mv")
    p.mark(f"{e}_c")
    p.load(W["d2"]).push(IMP_CLAW2).emit("lt", f"jz {e}_mv")
    p.set(imp(i, "t"), IMP_CD + 5 * i)
    p.load(F["evf"]).load(F["dead"]).emit("or", f"jz {e}_hy", f"jmp {e}_mv")   # (a dodge:
    p.mark(f"{e}_hy")                                                          # untouched)
    p.push(int(0.3 * ONE)).load(F["py"]).emit("lt", f"jz {e}_hit", f"jmp {e}_mv")
    p.mark(f"{e}_hit")
    p.load(PHP).push(IMP_DMG).emit("sub").store(PHP)
    p.load(F["shake"]).push(3).emit("lt", f"jz {e}_sk")
    p.set(F["shake"], 3)
    p.mark(f"{e}_sk")
    p.push(0).load(PHP).emit("lt", f"jz {e}_dn", f"jmp {e}_mv")
    p.mark(f"{e}_dn")                                 # he is down (C's own end)
    p.set(F["dead"], 1).set(ANIM, 4).set(F["hs"], 0)
    p.addi(int(CARDV) + 1, 1)
    p.load(CARDF).push(2).emit("or").store(CARDF)
    p.load(SY["pts"]).emit("shr 4").load(SY["best"]).emit("lt", f"jz {e}_bb", f"jmp {e}_mv")
    p.mark(f"{e}_bb")
    p.load(SY["pts"]).emit("shr 4").store(SY["best"])
    # and it lurches on, unless it is on him; the street slides it
    p.mark(f"{e}_mv")
    p.load(W["d2"]).push(IMP_NEAR2).emit("lt", f"jz {e}_go", f"jmp {e}")
    p.mark(f"{e}_go")
    p.load(imp(i, "x")).store(imp(i, "ox")).load(imp(i, "z")).store(imp(i, "oz"))
    sin_of(p, cell=imp(i, "yaw"))
    p.push(IMP_SPD).emit("mulq").load(imp(i, "x")).emit("swap", "sub").store(imp(i, "x"))
    sin_of(p, 256, cell=imp(i, "yaw"))
    p.push(IMP_SPD).emit("mulq").load(imp(i, "z")).emit("add").store(imp(i, "z"))
    keep_in_arena(imp(i, "x"), imp(i, "z"), imp(i, "ox"), imp(i, "oz"))
    p.mark(e)
p.load(IKILL).push(1).emit("eq", f"jz {ims}_end")   # one blow's sound for all it felled
p.set(W["head"], 0)
sound_blow(W["head"])
p.mark(f"{ims}_end")
# P16: THE FIGHT DOES NOT STOP. The wave came back only when all three
# were gone, so every wave ended on the same two seconds of nothing -- 18%
# of the tape's fight had no demon alive, and every rank the player lost
# was lost to idle decay in that wait. A demon that is gone is replaced
# at once, alone, at its own place on the ring (one slot a frame: the
# mover carries one request; the lowest gone slot first). All three gone
# together -- the retry, the quit -- still come back together, in the one
# request, as they always did. f_wave counts arrivals: a ring, or a demon.
# P18: THE HORDE (frontier 19's first use of the room). A district holds
# RES demons beyond the three on the street; each one that falls is
# replaced from it until it is empty. The last of a district falls in slow
# motion; CLEAR_FOR frames later the next district comes, HSTEP bigger.
# "Fight through hundreds": three are real at any moment.
def here(away):
    """-> away unless he stands in the district being fought (LVL): a
    horde comes only where it lives"""
    h_ = p.label("here")
    p.load(WOKE).emit(f"jz {away}")                  # (asleep in its plaza)
    city_node(p, PX, PZ)
    p.load(CT["n"]).push(0).emit("lt", f"jz {h_}", f"jmp {away}")
    p.mark(h_)
    p.load(CT["w"]).emit("shr 23").push(15).emit("and").load(LVL).emit("eq")
    p.emit(f"jz {away}")


nw = p.label("nowave")
lv_ = p.label("last")
p.load(RES).emit(f"jz {lv_}_z", f"jmp {lv_}")          # the district's last:
p.mark(f"{lv_}_z")
p.load(CLR).emit(f"jz {lv_}_c", f"jmp {lv_}")
p.mark(f"{lv_}_c")
for d in range(3):
    p.load(dslot(d, "st")).push(3).emit("lt")
p.emit("or", "or", f"jz {lv_}_s", f"jmp {lv_}")
p.mark(f"{lv_}_s")
p.set(F["slow"], SLOW_LAUNCH).set(CLR, 1)              # ...falls in slow motion
p.mark(lv_)
p.load(spec.OVL_GO).emit(f"jz {nw}_go", f"jmp {nw}")   # (not on a frame that pages a scene
p.mark(f"{nw}_go")                                      # in: its handshake has the mover)
for d in range(3):
    p.load(dslot(d, "st")).push(4).emit("eq")
p.emit("and", "and", f"jz {nw}_one")
p.load(RES).emit(f"jz {nw}_clr", f"jmp {nw}_ring")     # all gone, none left: CLEARED
p.mark(f"{nw}_clr")
p.addi(CLR, 1)
p.push(CLEAR_FOR).load(CLR).emit("lt", f"jz {nw}")     # (the beat, then the next)
p.addi(LVL, 1).set(CLR, 0).set(WOKE, 0)
p.load(LVL).push(HSTEP).emit("mul").push(HORDE0).emit("add").store(RES)
# P19: THE GATE OPENS -- gate LVL, into the district now owed -- and the
# next horde waits for him there
p.load(LVL).push(NDIST).emit("lt", f"jz {nw}")
for half in (0, 2):
    p.load(LVL).push(GT_N).emit("mul").push(int(GATE_T) - GT_N + half).emit("add")
    p.emit("dup", "loadi").push(int(CMAP)).emit("add", "dup", "loadi")   # [e, a, w]
    p.emit("swap").store(CT["k"])                                        # [e, w]
    p.emit("swap").push(1).emit("add", "loadi", "or")                    # [w | bit]
    p.load(CT["k"]).emit("storei")
p.emit(f"jmp {nw}")
p.mark(f"{nw}_ring")
here(f"{nw}")
p.load(RES).push(3).emit("sub", "dup").push(0).emit("lt", f"jz {nw}_rp")
p.emit("drop").push(0)
p.mark(f"{nw}_rp")
p.store(RES)
p.set(spec.DMA_SRC, int(SPAWN)).set(spec.DMA_DST, int(DS)).set(spec.DMA_LEN, 3 * NF)
p.set(SPN, 7)                                          # (placed next frame)
p.emit(f"jmp {nw}_all")
p.mark(f"{nw}_one")
p.load(RES).emit(f"jz {nw}")                           # the reserve is spent
here(f"{nw}")
for d in range(3):
    p.load(dslot(d, "st")).push(4).emit("eq", f"jz {nw}_{d}")
    p.set(spec.DMA_SRC, int(SPAWN) + d * NF).set(spec.DMA_DST, int(DS) + d * NF)
    p.load(SPN).push(1 << d).emit("or").store(SPN)
    p.emit(f"jmp {nw}_send")
    p.mark(f"{nw}_{d}")
p.emit(f"jmp {nw}")
p.mark(f"{nw}_send")
p.addi(RES, -1)                                        # (one from the reserve)
p.set(spec.DMA_LEN, NF)
p.mark(f"{nw}_all")
p.set(spec.DMA_GO, 1)
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
mover(q, OVL, int(MAIN_PROG), 0, PAGE)
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
# (the three are marked gone, and the fight's own wave respawn fetches the
# new ones on its first frame -- the retry does the same)
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
pz.set(spec.OVL_LEN, PAGE).set(spec.OVL_GO, 1)
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
if L7:
    # (P40: in the rooms, no street's ground and no sky. The ground, a
    # hand's breadth under a room's floor, took the floor's pixels near the
    # lens -- a black band along the bottom of the glass)
    _ng = p.label("noground")
    p.load(INSIDE).emit(f"jz {_ng}_o", f"jmp {_ng}")
    p.mark(f"{_ng}_o")
p.object(NOBJ, GROUND_M, (f"load {spec.CAM_X}",), 0, (f"load {spec.CAM_Z}",),
         (f"load {spec.CAM_YAW}",), spec.OBJ_CULL | (spec.OBJ_LIT if BASE else 0))
if BASE:
    p.object(NOBJ, SKY_M, (f"load {spec.CAM_X}",), 0, (f"load {spec.CAM_Z}",),
             (f"load {spec.CAM_YAW}",), spec.OBJ_CULL)
if L7:
    p.mark(_ng)
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


# THE CITY'S PIECES NEAR HIM (P19): the node he stands on, the nodes its
# streets reach, and the nodes theirs reach -- two streets out is 48 units
# or more, where the fog is already total -- each culled against the view
# and listed once (a plaza's square reaches a node by two ways). The walls
# hide the rest, so the rest is not drawn.
L_CTILE, L_CRING = p_main.label("ctile_sub"), p_main.label("cring_sub")


def city_subs():
  for g in (p_main, q, pz):
    # CTILE: list node CT n's piece, if not listed yet and in view
    ex = g.label("ctile")
    g.mark(L_CTILE)
    g.load(CT["c"]).push(CT_MAX).emit("lt", f"jz {ex}")            # (the cap)
    g.set(CT["k"], 0)
    g.mark(f"{ex}_s")
    g.load(CT["k"]).load(CT["c"]).emit("lt", f"jz {ex}_new")
    g.load(CT["k"]).push(int(CTLIST)).emit("add", "loadi").load(CT["n"]).emit("eq")
    g.emit(f"jz {ex}_nx", f"jmp {ex}")
    g.mark(f"{ex}_nx")
    g.addi(CT["k"], 1).emit(f"jmp {ex}_s")
    g.mark(f"{ex}_new")
    g.load(CT["n"]).load(CT["c"]).push(int(CTLIST)).emit("add", "storei")
    g.addi(CT["c"], 1)
    g.push32(int(OYA * ONE)).load(CT["n"]).emit("shr 4", f"shl {TSH}", "sub").store(CT["x"])
    g.load(CT["n"]).push(CS - 1).emit("and", f"shl {TSH}").push32(int(OXA * ONE))
    g.emit("sub").store(CT["z"])
    g.load(CT["x"]).store(VIS["cx"]).load(CT["z"]).store(VIS["cz"])
    g.push(int(round((PIECE_CY - 2.15) * ONE))).store(VIS["cy"])
    g.push(int(round(PIECE_R * ONE))).store(VIS["r"])
    g.emit(f"call {L_VIS}", f"jz {ex}")
    g.load(CT["n"]).push(int(CMAP)).emit("add", "loadi").store(CT["w"])
    g.object(NOBJ,
             lambda h: h.load(CT["w"]).emit("shr 18").push(31).emit("and")
             .push(int(PIECE_T)).emit("add", "loadi"),
             (f"load {int(CT['x'])}",), 0, (f"load {int(CT['z'])}",),
             lambda h: h.load(CT["w"]).emit("shr 8").push(1023).emit("and"),
             (lambda h: h.load(CT["w"]).emit("shr 18").push(31).emit("and").push(int(PFLAG_T)).emit("add", "loadi"))
             if L7 else spec.OBJ_CULL | (spec.OBJ_LIT if BASE else 0))
    g.mark(ex)
    g.emit("ret")
    # CRING: the nodes CT n1's streets reach, but back the way it came (bk)
    g.mark(L_CRING)
    for d in range(4):
        sk = g.label("cring")
        g.load(CT["bk"]).push(d).emit("eq", f"jz {sk}_go", f"jmp {sk}")
        g.mark(f"{sk}_go")
        g.load(CT["w1"]).emit(f"shr {2 * d}").push(3).emit("and", f"jz {sk}")
        g.load(CT["n1"]).push(CSTEP[d]).emit("add").store(CT["n"])
        g.emit(f"call {L_CTILE}")
        g.mark(sk)
    g.emit("ret")

p.set(CT["c"], 0)
cw_ = p.label("cwalk")
for g in (p_main, q, pz):
    city_node(g, PX, PZ)
p.load(CT["n"]).push(0).emit("lt", f"jz {cw_}_in", f"jmp {cw_}")
p.mark(f"{cw_}_in")
p.load(CT["n"]).store(CT["n1"]).load(CT["w"]).store(CT["w1"])
p.emit(f"call {L_CTILE}")
for d in range(4):
    sk = p.label("cw1")
    p.load(CT["w1"]).emit(f"shr {2 * d}").push(3).emit("and", f"jz {sk}")
    p.load(CT["n1"]).push(CSTEP[d]).emit("add").store(CT["n"])
    p.emit(f"call {L_CTILE}")
    p.load(CT["n"]).store(CT["n1"])
    p.load(CT["n"]).push(int(CMAP)).emit("add", "loadi").store(CT["w1"])
    p.set(CT["bk"], (d + 2) % 4)
    p.emit(f"call {L_CRING}")
    p.load(CT["n1"]).push(CSTEP[d]).emit("sub").store(CT["n1"])      # (back)
    p.load(CT["n1"]).push(int(CMAP)).emit("add", "loadi").store(CT["w1"])
    p.mark(sk)
p.mark(cw_)
# the next gate shut, if it can be seen (gate LVL + 1: the way out of the
# district being fought; every gate before it is open, every one after it
# behind it)
gd_ = p.label("gate")
if L5:
    # P38: the nearest door still shut, on HIS side of it (a gate's bars, a
    # back door's): outlined when the jab would open it from here
    p.load(D5).push(0).emit("lt", f"jz {gd_}_on", f"jmp {gd_}")
    p.mark(f"{gd_}_on")
    p.load(DRX).store(VIS["cx"]).load(DRZ).store(VIS["cz"])
    p.push(int(round((7 - 2.15) * ONE))).store(VIS["cy"]).push(int(12 * ONE)).store(VIS["r"])
    p.emit(f"call {L_VIS}", f"jz {gd_}")
    p.object(NOBJ, (f"load {int(DRM)}",), (f"load {int(DRX)}",), 0, (f"load {int(DRZ)}",), (f"load {int(DRY)}",),
             (lambda h: h.load(KNEAR).push(2).emit("eq").load(ITK).push(1).emit("eq", "and").push(spec.OBJ_EDGE).emit("mul"))
             if L7 else (lambda h: h.load(KNEAR).push(2).emit("eq").push(spec.OBJ_EDGE).emit("mul")))
    if L7:                                           # (P40: and the nearest bunker's door, its own)
        p.mark(gd_)
        gd_ = p.label("tdoor")
        p.load(BESTT).push32(int(60 * ONE)).emit("lt", f"jz {gd_}")
        p.load(TDX).store(VIS["cx"]).load(TDZ).store(VIS["cz"])
        p.push(int(round((2 - 2.15) * ONE))).store(VIS["cy"]).push(int(4 * ONE)).store(VIS["r"])
        p.emit(f"call {L_VIS}", f"jz {gd_}")
        p.object(NOBJ, TDOOR_M, (f"load {int(TDX)}",), 0, (f"load {int(TDZ)}",), (f"load {int(TDY)}",),
                 lambda h: h.load(KNEAR).push(2).emit("eq").load(ITK).push(2).emit("eq", "and").push(spec.OBJ_EDGE).emit("mul")
                 .push(spec.OBJ_CULL).emit("or"))
else:
    p.load(LVL).push(NDIST - 1).emit("lt", f"jz {gd_}")
    p.load(LVL).push(GT_N).emit("mul").push(int(GATE_T)).emit("add").store(CT["k"])
    p.load(CT["k"]).push(4).emit("add", "loadi").store(VIS["cx"])
    p.load(CT["k"]).push(5).emit("add", "loadi").store(VIS["cz"])
    p.push(int(round((7 - 2.15) * ONE))).store(VIS["cy"]).push(int(12 * ONE)).store(VIS["r"])
    p.emit(f"call {L_VIS}", f"jz {gd_}")
    p.object(NOBJ, GATE_M,
             lambda h: h.load(CT["k"]).push(4).emit("add", "loadi"), 0,
             lambda h: h.load(CT["k"]).push(5).emit("add", "loadi"),
             lambda h: h.load(CT["k"]).push(6).emit("add", "loadi"),
             (lambda h: h.load(KNEAR).push(2).emit("eq").push(spec.OBJ_EDGE).emit("mul"))
             if BASE else 0)                                              # (both sides; P21b:
                                                                          # outlined when the
                                                                          # jab would unlock it)
p.mark(gd_)
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
# P15: the bank eases toward the turn he is steering (left is positive: the
# roll that tips his crown to his own left), and only while he runs
lb_ = p.label("bank")
p.push(0)
p.load(F["spd"]).emit(f"jz {lb_}")
held(spec.PAD_LEFT)
p.emit(f"jz {lb_}_r", "drop").push(LEAN_BANK).emit(f"jmp {lb_}")
p.mark(f"{lb_}_r")
held(spec.PAD_RIGHT)
p.emit(f"jz {lb_}", "drop").push(-LEAN_BANK)
p.mark(lb_)
p.load(LEANR).emit("sub", "dup").push(0).emit("swap", "lt", f"jz {lb_}_p")   # (toward it by an
p.push(7).emit("add")                                # eighth, rounded away from zero: it arrives)
p.mark(f"{lb_}_p")
p.emit("shr 3").load(LEANR).emit("add").store(LEANR)
for m in ((UPPER, LOWER) if "player" not in OMIT else ()):
    # down, he folds FORWARD over his feet, away from the lens -- the
    # archive's collapse folds over the guard, and backwards took him out
    # of the bottom of the shot
    p.object(NOBJ, m, (f"load {int(PX)}", f"load {int(W['x'])}", "add"),
             (f"load {int(F['py'])}", f"load {int(W['y'])}", "add")
             + ((f"load {int(GYC)}", "add") if BASE else ()),
             (f"load {int(PZ)}", f"load {int(W['z'])}", "add"),
             (f"load {int(HEAD)}", f"load {int(F['tilt'])}", f"load {int(W['qx'])}", "add",
              f"load {int(F['spd'])}", f"push {LEAN_PITCH}", "mul", "shr 16", "add",   # P15: the lean
              "push 1023", "and", "shl 10", "or",
              f"load {int(W['qy'])}", f"load {int(LEANR)}", "add", "push 1023", "and",
              "shl 20", "or"),
             (f"load {int(PFLAGS)}",) + ((f"push {spec.OBJ_CART}", "or") if CARTMESH else ()))
if CARTMESH and RIVAL:
    for m in (int(RDESC), int(RDESC) + spec.CMESH_WORDS):
        p.object(NOBJ, m, START_X, 0, START_Z - int((3.0 if CROWD else 5.0) * ONE), 0, spec.OBJ_CART)
if CARTMESH and not L4:
    for e_ in ENEMY:
        p.object(NOBJ, e_["desc"], START_X + e_["dx"], 0, START_Z + e_["dz"], 0, spec.OBJ_CART | spec.OBJ_CULL)
if L4:
    # P37: THE ENEMIES, where they can be seen: each from the cart (its
    # descriptor's pose, above). One a blow has just struck flashes; the one
    # he has chosen is outlined; one going down tips over backwards.
    for e_ in ENEMY:
        de_ = p.label("denemy")
        p.load(e_["st"]).emit(f"jz {de_}")
        p.load(e_["fl"]).emit(f"jz {de_}_f")
        p.addi(e_["fl"], -1)
        p.mark(f"{de_}_f")

        def e_body(e_=e_):
            def ang(h):
                ta = h.label("etip")
                h.load(e_["yaw"])
                h.load(e_["st"]).push(2).emit("eq", f"jz {ta}")
                h.load(e_["t"]).push(14).emit("mul", "dup").push(250).emit("swap", "lt", f"jz {ta}_c")
                h.emit("drop").push(250)
                h.mark(f"{ta}_c")
                h.push(1023).emit("swap", "sub", "shl 10", "or")           # (back, away from his face)
                h.mark(ta)

            def flags(h):
                tf = h.label("efl")
                h.push32(spec.OBJ_CART | spec.OBJ_CULL)
                h.load(e_["fl"]).emit(f"jz {tf}")
                h.emit("drop").push32(FLASH | spec.OBJ_CART)
                h.mark(tf)
                h.load(LOCK).load(TSEL).push(e_["k"]).emit("eq", "and", f"jz {tf}_e")
                h.push(spec.OBJ_EDGE).emit("or")
                h.mark(f"{tf}_e")
            p.object(NOBJ, e_["desc"], (f"load {int(e_['pos'])}",), 0, (f"load {int(e_['pos']) + 1}",), ang, flags)
        # (one within arm's length of the LENS is not drawn: it would blot out the shot)
        for c_, cam_ in ((int(e_["pos"]), spec.CAM_X), (int(e_["pos"]) + 1, spec.CAM_Z)):
            p.load(c_).load(cam_).emit("sub", "dup", "mulq")
        p.emit("add").push(int(1.3 ** 2 * ONE)).emit("swap", "lt", f"jz {de_}")
        if_visible((f"load {int(e_['pos'])}",), 1.0, (f"load {int(e_['pos']) + 1}",), 1.3, e_body)
        p.mark(de_)
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
# P20b: THE SWARM -- each up or falling, if there is room in the list and
# it can be seen: lurching (a lean, a sway, a bob), or going down and under
for i in range(N_IMP):
    e = p.label("dimp")
    p.load(imp(i, "st")).emit(f"jz {e}")
    p.load(NOBJ).push(spec.OL_MAX - 2).emit("lt", f"jz {e}")   # (the spark's room)
    for c, cam in (("x", spec.CAM_X), ("z", spec.CAM_Z)):
        p.load(imp(i, c)).load(cam).emit("sub", "dup", "mulq")
    p.emit("add").push(IMP_LENS2).emit("swap", "lt", f"jz {e}")   # (nearer: it would
                                                                   # blot out the fight)

    def body(i=i):
        def y_ops(h):
            fa = h.label("iy")
            h.load(imp(i, "st")).push(2).emit("eq", f"jz {fa}_b")
            h.load(imp(i, "t")).push(-int(0.035 * ONE)).emit("mul", f"jmp {fa}")
            h.mark(f"{fa}_b")
            h.load(spec.REG_FRAME).push(5).emit("mul").push(23 * i).emit("add")
            h.push(31).emit("and").push(int(0.005 * ONE)).emit("mul")
            h.mark(fa)

        def ang_ops(h):
            fa = h.label("ia")
            h.load(imp(i, "st")).push(2).emit("eq", f"jz {fa}_b")
            h.load(imp(i, "t")).push(10).emit("mul").push(40).emit("add", f"jmp {fa}")
            h.mark(f"{fa}_b")
            h.push(40)                                         # the lean
            h.mark(fa)
            h.emit("shl 10").load(imp(i, "yaw")).emit("or")
            h.load(spec.REG_FRAME).push(6).emit("mul").push(41 * i).emit("add")
            h.push(63).emit("and").push(32).emit("sub").push(1023).emit("and")
            h.emit("shl 20", "or")                             # the sway
        p.object(NOBJ, IMP_M, (f"load {imp(i, 'x')}",), y_ops, (f"load {imp(i, 'z')}",),
                 ang_ops, spec.OBJ_CULL)
    if_visible((f"load {imp(i, 'x')}",), 0.7, (f"load {imp(i, 'z')}",), 1.0, body)
    p.mark(e)
if BASE:
    kd_ = p.label("dkey")
    KDX, KDZ = (KYX, KYZ) if L5 else (KX, KZ)
    if L5:
        # P38: the nearest bunker's hatch, and the nearest key not yet taken
        # (each only within a few blocks: past that the fog has them)
        if L7:
            # P40: no hatch in the road. In the rooms, the range's items
            # that are not the nearest (the nearest is drawn below, as the
            # street's key is: it is the one that rings and leaps)
            p.load(INSIDE).emit(f"jz {kd_}_nb")
            for g_ in range(NKEYS, len(KEYAT)):
                p.load(K5).push(g_).emit("eq", f"jz {kd_}_r{g_}", f"jmp {kd_}_x{g_}")
                p.mark(f"{kd_}_r{g_}")
                p.object(NOBJ, KEY_M, lambda h, g_=g_: h.push32(KEYAT[g_][0]), int(0.85 * ONE),
                         lambda h, g_=g_: h.push32(KEYAT[g_][1]),
                         (f"load {spec.REG_FRAME}", "push 5", "mul", "push 1023", "and"), spec.OBJ_CULL)
                p.mark(f"{kd_}_x{g_}")
        else:
            p.load(BESTB).push32(int(60 * ONE)).emit("lt", f"jz {kd_}_nb")
            p.object(NOBJ, BUNK_M, (f"load {int(BKX)}",), 0, (f"load {int(BKZ)}",), 0, 0)
        p.mark(f"{kd_}_nb")
        p.load(K5).push(0).emit("lt", f"jz {kd_}_s", f"jmp {kd_}")
        p.mark(f"{kd_}_s")
        p.load(BESTK).push32(int(60 * ONE)).emit("lt", f"jz {kd_}")
    else:
        p.load(KEY).emit(f"jz {kd_}_s", f"jmp {kd_}")
        p.mark(f"{kd_}_s")
        p.load(LVL).push(len(GATES)).emit("lt", f"jz {kd_}")
    p.object(NOBJ, KEY_M, (f"load {int(KDX)}",),
             (f"load {spec.REG_FRAME}", "push 3", "mul", "push 63", "and", "push 400", "mul",
              f"push {int(0.85 * ONE)}", "add")                  # (it rises and drops)
             + ((f"load {int(KHIT)}", "push 1100", "mul", "add") if L2 else ()),   # (P34: struck, it leaps)
             (f"load {int(KDZ)}",),
             (f"load {spec.REG_FRAME}", "push 5", "mul", f"load {int(KNEAR)}", "push 4", "mul",
              "push 1", "add", "mul", "push 1023", "and"),       # (in reach: it spins fast,
             (f"load {int(KNEAR)}", "push 1", "eq")
             + ((f"load {int(KHIT)}", "push 0", "eq", "push 1", "xor", "or") if L2 else ())
             + ((f"load {int(LOCK)}",) + ((f"load {int(TSEL)}", f"push {NE}", "eq", "and") if L4 else ())
                + ((f"load {int(KEY)}", "push 0", "eq", "and") if L5 else ()) + ("or",)
                if L3 else ())
             + (f"push {spec.OBJ_EDGE}", "mul",                                       # outlined)
              f"push {spec.OBJ_CULL}", "or"))
    p.object(NOBJ, SHADOW_M, (f"load {int(KDX)}",), 0, (f"load {int(KDZ)}",), 0, spec.OBJ_BLEND)
    p.mark(kd_)
    p.object(NOBJ, SHADOW_M, (f"load {int(PX)}",), (f"load {int(GYC)}",), (f"load {int(PZ)}",),
             (f"load {int(HEAD)}",), spec.OBJ_BLEND)
if L2:
    # P34: THE SIGHT (the player, of the movement: "I should be able to have
    # accurate prediction of where I'll land or be" -- and the gun "more
    # tactical too"). B down, the line the shot WILL take is drawn: its way
    # the pad's from his steering (no pad: his body's) -- what the launch
    # does -- and its end where RAY says that line meets the town. A bead
    # for each round in the gun, spaced evenly along it, and a point on the
    # place it lands: red, and white-hot once the shot is charged.
    sg_ = p.label("sight")
    p.load(KHIT).emit(f"jz {sg_}_k")
    p.addi(KHIT, -1)
    p.mark(f"{sg_}_k")
    p.load(F["py"]).push(GUN_Y).emit("add").store(W["oy"])
    if L4:                                        # (P37: locked, at the spot's height)
        p.load(LOCK).emit(f"jz {sg_}_y")
        p.push(int(SPOTY)).load(SPOT).emit("add", "loadi").store(W["oy"])
        p.mark(f"{sg_}_y")
    p.load(GT["shoot"]).emit(f"jz {sg_}")
    p.load(SLOWON).emit(f"jz {sg_}")              # (P35, the player: "the targeting should
    p.load(GC["shoot"]).load(RLD).emit("or", f"jz {sg_}_c", f"jmp {sg_}")   # really only show in slow motion")
    p.mark(f"{sg_}_c")
    p.load(HEAD).store(W["head"])
    p.load(AIMED)
    if L3:
        p.load(LOCK).emit("or")
    p.emit(f"jz {sg_}_a", f"jmp {sg_}_h")
    p.mark(f"{sg_}_a")
    held(15)
    p.emit(f"jz {sg_}_h")
    p.push(int(OCTANT)).emit("load 1").push(15).emit("and", "add", "loadi")
    p.load(YAW).emit("add").push(1023).emit("and").store(W["head"])
    p.mark(f"{sg_}_h")
    p.emit(f"call {L_RAY}")
    p.push(6)
    knob(p, "mag")
    p.emit(f"jz {sg_}_n", "drop")
    knob(p, "mag")
    p.load(SHOTS).emit("sub")
    p.mark(f"{sg_}_n")
    p.store(W["k"])
    p.push(0).load(W["k"]).emit("lt", f"jz {sg_}_d")
    p.push(int(INVN)).load(W["k"]).emit("add", "loadi").load(RAY["len"]).emit("mulq").store(W["d2"])
    for me, d_, at, st_ in ((RAY["ox"], "dx", "bx", "qx"), (RAY["oz"], "dz", "bz", "qz")):
        p.load(RAY[d_]).load(W["d2"]).emit("mulq").store(W[st_]).load(me).store(W[at])
    p.mark(f"{sg_}_l")
    for at, st_ in (("bx", "qx"), ("bz", "qz")):
        p.load(W[at]).load(W[st_]).emit("add").store(W[at])
    p.object(NOBJ, BEAD_M, (f"load {int(W['bx'])}",), (f"load {int(W['oy'])}",),
             (f"load {int(W['bz'])}",), (f"load {spec.REG_FRAME}", "push 37", "mul", "push 1023", "and"), 0)
    p.addi(W["k"], -1).load(W["k"]).emit(f"jz {sg_}_d", f"jmp {sg_}_l")
    p.mark(f"{sg_}_d")
    p.load(RAY["hit"]).emit(f"jz {sg_}")

    def dot_mesh(h):
        dm = h.label("dotm")
        h.push(DOT_M).push(CHARGE - 1).load(GT["shoot"]).emit("lt", f"jz {dm}")
        h.emit("drop").push(HOT_M)
        h.mark(dm)
    p.object(NOBJ, dot_mesh, (f"load {int(RAY['x'])}",), (f"load {int(W['oy'])}",),
             (f"load {int(RAY['z'])}",),
             (f"load {spec.REG_FRAME}", "push 29", "mul", "push 1023", "and", "dup", "shl 10", "or"), 0)
    p.mark(sg_)
    if L3:                                      # P35: the lock's mark, over the item
        lm_ = p.label("lockmark")
        p.load(LOCK).emit(f"jz {lm_}")
        if L4:                                  # P37: at the spot, on his side of the target
            def mark_x(h):
                sin_of(h, cell=LBRG)
                h.push(int(0.45 * ONE)).emit("mulq").load(TGTX).emit("add")

            def mark_z(h):
                sin_of(h, 256, cell=LBRG)
                h.push(int(0.45 * ONE)).emit("mulq").load(TGTZ).emit("swap", "sub")
            p.object(NOBJ, AWARE_M, mark_x, (f"push {int(SPOTY)}", f"load {int(SPOT)}", "add", "loadi"), mark_z,
                     (f"load {spec.REG_FRAME}", "push 23", "mul", "push 1023", "and"), 0)
        else:
            p.object(NOBJ, AWARE_M, (f"load {int(KX)}",), int(1.9 * ONE), (f"load {int(KZ)}",),
                     (f"load {spec.REG_FRAME}", "push 23", "mul", "push 1023", "and"), 0)
        p.mark(lm_)
    for B_ in BUL:                              # the bullets: each a streak along its way
        nb = p.label("dbul")
        p.load(B_["rem"]).emit(f"jz {nb}")
        p.object(NOBJ, BULLET_M,
                 (f"load {int(B_['ex'])}", f"load {int(B_['dx'])}", f"load {int(B_['rem'])}", "mulq", "sub"),
                 (f"load {int(B_['y'])}",),
                 (f"load {int(B_['ez'])}", f"load {int(B_['dz'])}", f"load {int(B_['rem'])}", "mulq", "sub"),
                 (f"load {int(B_['yaw'])}",), 0)
        p.mark(nb)
# P15: the spark, last in the list, while its frames last
sk_ = p.label("spark")
p.load(int(SPK) + 3).emit(f"jz {sk_}")
p.addi(int(SPK) + 3, -1)
for turn in (0, 1):
    p.object(NOBJ, (f"load {int(SPKM)}",) if L2 else SPARK_M, (f"load {int(SPK)}",), (f"load {int(SPK) + 1}",),
             (f"load {int(SPK) + 2}",),
             (f"load {int(SPK) + 3}", f"push {150 + 21 * turn}", "mul",
              f"push {turn * 300}", "add", "push 1023", "and",
              f"load {int(SPK) + 3}", f"push {97 + 60 * turn}", "mul", "push 1023", "and",
              "shl 10", "or"),
             0)
p.mark(sk_)
p.load(NOBJ).store(spec.OL_BASE)

p = p_main                           # (the intro has no style, no HUD)
# ---- the style meter's frame: bleed, rank, best ------------------------------
sb = p.label("sbleed")
p.load(F["dead"]).emit(f"jz {sb}_a", f"jmp {sb}")
p.mark(f"{sb}_a")
p.load(F["skip"]).emit(f"jz {sb}_k", f"jmp {sb}")    # (not while FOCUS holds the world)
p.mark(f"{sb}_k")
p.addi(SY["idle"], 1)
# THE METER COOLS, IT DOES NOT DROP (P17, kept): 0.25 a frame after a
# second idle, 0.75 after two -- it bled 0.6 after 45 frames and 2.2 after
# 90, and the second tape spent three minutes at D
p.push(120).load(SY["idle"]).emit("lt", f"jz {sb}_45")
p.load(SY["pts"]).push(12).emit("sub").store(SY["pts"])      # 0.75 a frame
p.set(SY["combo"], 0).emit(f"jmp {sb}_c")
p.mark(f"{sb}_45")
p.push(60).load(SY["idle"]).emit("lt", f"jz {sb}")
p.load(SY["pts"]).push(4).emit("sub").store(SY["pts"])       # 0.25 a frame
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
if BASE:
    p.load(KTUNE).emit(f"jz {hk}_nt")
    p.push(255).push(int(S_SHOWN)).emit("storei")        # (the HUD draws afresh after)
    p.set(TX["n"], 1)
    p.load(KSEL).push(FONT_CH.index("0")).emit("add").store(int(KSTR1) + 1)
    for k, v in (("str", int(KSTR1)), ("x", 20), ("y", 196), ("sc", 4), ("rgb", 0xE8C040)):
        p.set(TX[k], v)
    p.emit(f"call {L_TEXT}")
    p.push(int(KNOTCH)).load(KSEL).emit("add", "loadi").push(50).emit("add", "dup")
    p.push(205).emit("mul", "shr 11", "dup").store(TX["j"])              # tens
    p.push(10).emit("mul", "sub").push(FONT_CH.index("0")).emit("add").store(int(KSTR2) + 2)
    p.load(TX["j"]).push(FONT_CH.index("0")).emit("add").store(int(KSTR2) + 1)
    for k, v in (("str", int(KSTR2)), ("x", 52), ("y", 196), ("sc", 4), ("rgb", 0xD8CFC1)):
        p.set(TX[k], v)
    p.emit(f"call {L_TEXT}")
    p.load(TX["n"]).store(spec.DL_BASE)
    if L5:
        p.set(PIPN, 0)
    p.emit(f"jmp {hk}")
    p.mark(f"{hk}_nt")
p.load(SY["g"]).push(int(S_SHOWN)).emit("loadi", "eq", f"jz {hk}_draw", f"jmp {hk}")
p.mark(f"{hk}_draw")
p.load(SY["g"]).push(int(S_SHOWN)).emit("storei")
p.set(TX["n"], 1)                  # (P19: triangle 0 is the pointer's)
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
if L5:
    p.set(PIPN, 0)
p.mark(hk)
# P19: THE POINTER. Away from the district being fought -- a district
# cleared behind him, its gate open -- a gold arrow at the top of the
# screen points down the next street toward the core (the map's bits
# 27-28), turned into the camera's view: one of eight ways, by comparison
# (the machine has no divide). Triangle 0 of the display list, every frame;
# the HUD's words start at 1.
pt_ = p.label("ptr")
p.set(CT["k"], 8)                                        # 8: hidden
p.load(F["dead"]).emit(f"jz {pt_}_up", f"jmp {pt_}_w")     # (not while he is down)
p.mark(f"{pt_}_up")
city_node(p, PX, PZ)
p.load(CT["n"]).push(0).emit("lt", f"jz {pt_}_on", f"jmp {pt_}_w")
p.mark(f"{pt_}_on")
if L5:
    # P38: THE ARROW LEADS TO THE WAYMARK. Until the bunker's map sets it
    # (docs/TND-WORLD.md, step 3) the waymark is the game's own: the first
    # gate still shut that is not behind him -- its key's dead end, or, the
    # key in hand, the gate itself; every gate open, the core. The way
    # there is the generated town's own tree (TREE_T): down into the branch
    # that holds the waymark, else back toward the start. It knows no
    # bolts and no hard ways -- those are his to find.
    if L6:
        p.load(CT["w"]).emit("shr 23").push(15).emit("and").store(W["qx"])
        # P39: THE ARROW LEADS TO HIS OWN WAYMARK, the first of his plan --
        # and no plan, no arrow. Reaching its node takes it off and the
        # next is first. The way is no longer the tree's: it is searched,
        # from the waymark outward over the streets OPEN NOW (L_BFS, below),
        # whenever the waymark or the doors change -- so a bolt drawn or a
        # hard way IS a way; and where that finds none (the waymark behind
        # a gate still shut) the tree's way, which leads to that gate.
        # And WHAT HE KNOWS of the town: the sector he stands in; on a
        # bunker's hatch, the next one along too (its survey).
        if L7:                                   # (P40: in the rooms, no arrow; a bunker's survey
            p.load(INSIDE).emit(f"jz {pt_}_st", f"jmp {pt_}_w")     # is taken at its door)
            p.mark(f"{pt_}_st")
        p.load(W["qx"]).push(int(SBIT)).emit("add", "loadi").load(KNOWN).emit("or").store(KNOWN)
        if not L7:
            p.load(BESTB).push(int(2.0 * ONE)).emit("lt", f"jz {pt_}_kn")
            p.load(W["qx"]).push(int(SBIT) + 1).emit("add", "loadi").load(KNOWN).emit("or").store(KNOWN)
            p.mark(f"{pt_}_kn")
        p.load(WN).emit(f"jz {pt_}_w")
        p.load(int(WP)).store(WAYN)
        p.load(CT["n"]).load(WAYN).emit("eq", f"jz {pt_}_go")
        for j_ in range(3):
            p.load(int(WP) + j_ + 1).store(int(WP) + j_)
        p.addi(WN, -1).set(LFLASH, 6).emit(f"jmp {pt_}_w")
        p.emit(f"jmp {pt_}_go")
        L_BFS = p.label("bfs")
        p.mark(L_BFS)
        p.set(BH, 0)
        p.mark(f"{L_BFS}_c")
        p.push(4).push(int(HOPT)).load(BH).emit("add", "storei")
        p.addi(BH, 1)
        p.load(BH).push(CS * CS).emit("lt", f"jz {L_BFS}_c1", f"jmp {L_BFS}_c")
        p.mark(f"{L_BFS}_c1")
        p.push(5).push(int(HOPT)).load(WAYN).emit("add", "storei")
        p.load(WAYN).store(int(BQ))
        p.set(BH, 0).set(BT, 1)
        p.mark(f"{L_BFS}_l")
        p.load(BH).load(BT).emit("lt", f"jz {L_BFS}_e")
        p.push(int(BQ)).load(BH).emit("add", "loadi").store(BV)
        p.addi(BH, 1)
        p.load(BV).push(int(CMAP)).emit("add", "loadi").store(BW)
        for k in range(4):
            p.load(BW).emit(f"shr {2 * k}").push(3).emit("and", f"jz {L_BFS}_k{k}")
            p.load(BV).push(CSTEP[k]).emit("add").store(BM)
            p.push(int(HOPT)).load(BM).emit("add", "loadi").push(4).emit("eq", f"jz {L_BFS}_k{k}")
            p.push((k + 2) & 3).push(int(HOPT)).load(BM).emit("add", "storei")
            p.load(BM).push(int(BQ)).load(BT).emit("add", "storei")
            p.addi(BT, 1)
            p.mark(f"{L_BFS}_k{k}")
        p.emit(f"jmp {L_BFS}_l")
        p.mark(f"{L_BFS}_e")
        p.emit("ret")
        p.mark(f"{pt_}_go")
        p.load(WAYN).load(WAYL).emit("eq").load(OPENED).load(OPL).emit("eq", "and", f"jz {pt_}_bfs", f"jmp {pt_}_rt")
        p.mark(f"{pt_}_bfs")
        p.emit(f"call {L_BFS}")
        p.load(WAYN).store(WAYL).load(OPENED).store(OPL)
        p.mark(f"{pt_}_rt")
        p.load(CT["n"]).push(int(HOPT)).emit("add", "loadi", "dup").store(CT["c"])
        p.push(4).emit("lt", f"jz {pt_}_tree", f"jmp {pt_}_away")
        p.mark(f"{pt_}_tree")
    else:
        p.set(WAYN, CITY.core)
        p.load(CT["w"]).emit("shr 23").push(15).emit("and").store(W["qx"])
        for g_, d_ in enumerate(DOORS[:NGATE]):
            wg = f"{pt_}_g{g_}"
            p.load(OPENED).push(1 << g_).emit("and", f"jz {wg}_s", f"jmp {wg}")
            p.mark(f"{wg}_s")
            p.load(W["qx"]).push(g_ + 1).emit("lt", f"jz {wg}")     # (his sector is past it)
            p.set(WAYN, d_["a"])
            p.load(KEYS).push(1 << g_).emit("and", f"jz {wg}_k", f"jmp {pt_}_wd")
            p.mark(f"{wg}_k")
            p.set(WAYN, WORLD.keys[GATES[g_][0]]).emit(f"jmp {pt_}_wd")
            p.mark(wg)
        p.mark(f"{pt_}_wd")
        p.load(CT["n"]).load(WAYN).emit("eq", f"jz {pt_}_go", f"jmp {pt_}_w")      # (there: no arrow)
        p.mark(f"{pt_}_go")
    p.load(CT["n"]).push(int(TREE_T)).emit("add", "loadi").store(CT["w1"])
    p.load(WAYN).push(int(TREE_T)).emit("add", "loadi").push(255).emit("and").store(CT["n1"])
    p.load(CT["w1"]).emit("shr 16").push(3).emit("and").store(CT["c"])        # (not under him: back)
    p.load(CT["n1"]).load(CT["w1"]).push(255).emit("and", "lt", f"jz {pt_}_ta", f"jmp {pt_}_away")
    p.mark(f"{pt_}_ta")
    p.load(CT["w1"]).emit("shr 8").push(255).emit("and").load(CT["n1"]).emit("lt", f"jz {pt_}_tb", f"jmp {pt_}_away")
    p.mark(f"{pt_}_tb")
    for k in range(4):
        tk = f"{pt_}_t{k}"
        p.load(CT["w1"]).emit(f"shr {18 + k}").push(1).emit("and", f"jz {tk}")
        p.load(CT["n"]).push(CSTEP[k]).emit("add").push(int(TREE_T)).emit("add", "loadi").store(CT["x"])
        p.load(CT["n1"]).load(CT["x"]).push(255).emit("and", "lt", f"jz {tk}_a", f"jmp {tk}")
        p.mark(f"{tk}_a")
        p.load(CT["x"]).emit("shr 8").push(255).emit("and").load(CT["n1"]).emit("lt", f"jz {tk}_b", f"jmp {tk}")
        p.mark(f"{tk}_b")
        p.set(CT["c"], k).emit(f"jmp {pt_}_away")
        p.mark(tk)
else:
    p.set(CT["c"], 27)                                       # the road: to the core,
    p.load(CT["w"]).emit("shr 23").push(15).emit("and").load(LVL).emit("eq")
    p.emit(f"jz {pt_}_away")
    if BASE:                                                 # P21: the key held, on to the
        p.load(KEY).emit(f"jz {pt_}_nk", f"jmp {pt_}_away")  # gate; else to the plaza it
        p.mark(f"{pt_}_nk")                                  # lies in (there: no arrow)
        p.load(CT["w"]).push(0xAA).emit("and", f"jz {pt_}_asl", f"jmp {pt_}_w")
    else:
        p.load(WOKE).emit(f"jz {pt_}_asl", f"jmp {pt_}_w")       # (the fight: none)
    p.mark(f"{pt_}_asl")
    p.set(CT["c"], 29)                                       # ...or, asleep, its plaza
p.mark(f"{pt_}_away")
p.load(CT["n"]).emit("shr 4", f"shl {TSH}").push32(int(OYA * ONE)).emit("swap", "sub")
p.load(PX).emit("sub").store(CT["x"])                    # node centre - him
p.load(CT["n"]).push(CS - 1).emit("and", f"shl {TSH}").push32(int(OXA * ONE))
p.emit("sub").load(PZ).emit("sub").store(CT["z"])
for k in range(4):                                       # ...+ the next street
    dx, dy, _ = city.DIRS[k]
    if L5:
        p.load(CT["c"]).push(k).emit("eq", f"jz {pt_}_h{k}")
    else:
        p.load(CT["w"]).emit("shr 27").load(CT["c"]).push(29).emit("eq", f"jz {pt_}_s{k}")
        p.emit("shr 2")                                      # (bits 29-30: the plaza's way.
                                                             # Until P21b this tested for 27,
                                                             # and the two ways were swapped)
        p.mark(f"{pt_}_s{k}")
        p.push(3).emit("and").push(k).emit("eq", f"jz {pt_}_h{k}")
    if dy:
        p.load(CT["x"]).push32(-dy * int(TILE * ONE)).emit("add").store(CT["x"])
    if dx:
        p.load(CT["z"]).push32(dx * int(TILE * ONE)).emit("add").store(CT["z"])
    p.mark(f"{pt_}_h{k}")
p.load(CT["x"]).load(VIS["rx"]).emit("mulq")             # right
p.load(CT["z"]).load(VIS["rz"]).emit("mulq", "add").store(CT["n1"])
p.load(CT["z"]).load(VIS["rx"]).emit("mulq")             # forward
p.load(CT["x"]).load(VIS["rz"]).emit("mulq", "sub").store(CT["w1"])
for c_, a_ in ((CT["n1"], CT["x"]), (CT["w1"], CT["z"])):   # |right|, |forward|
    ab = p.label("pabs")
    p.load(c_).emit("dup").push(0).emit("lt", f"jz {ab}")
    p.push(0).emit("swap", "sub")
    p.mark(ab)
    p.store(a_)
TAN67 = int(round(2.4142 * ONE))
p.load(CT["z"]).push(TAN67).emit("mulq").load(CT["x"]).emit("lt", f"jz {pt_}_nh")
p.push(0).load(CT["n1"]).emit("lt").push(-4).emit("mul").push(6).emit("add")  # 2 or 6
p.store(CT["k"]).emit(f"jmp {pt_}_w")
p.mark(f"{pt_}_nh")
p.load(CT["x"]).push(TAN67).emit("mulq").load(CT["z"]).emit("lt", f"jz {pt_}_dg")
p.push(0).load(CT["w1"]).emit("lt").push(-4).emit("mul").push(4).emit("add")  # 0 or 4
p.store(CT["k"]).emit(f"jmp {pt_}_w")
p.mark(f"{pt_}_dg")                                       # a diagonal
p.push(0).load(CT["n1"]).emit("lt", f"jz {pt_}_dl")
p.push(0).load(CT["w1"]).emit("lt").push(2).emit("mul").push(3).emit("swap", "sub")   # 3 or 1
p.store(CT["k"]).emit(f"jmp {pt_}_w")
p.mark(f"{pt_}_dl")
p.push(0).load(CT["w1"]).emit("lt").push(2).emit("mul").push(5).emit("add")   # 7 or 5
p.store(CT["k"])
p.mark(f"{pt_}_w")
p.load(CT["k"]).push(spec.DL_STRIDE).emit("mul").push(int(ARROWS)).emit("add").store(CP["src"])
p.push(spec.DL_BASE + 1).store(CP["dst"]).push(spec.DL_STRIDE).store(CP["n"])
p.emit(f"call {L_COPY}")
p.load(spec.DL_BASE).emit(f"jz {pt_}_n1", f"jmp {pt_}")
p.mark(f"{pt_}_n1")
p.set(spec.DL_BASE, 1)
p.mark(pt_)
if L5:
    # P38: THE KEYS IN HAND, a gold pip each along the top -- a key's place
    # in the row is its gate's number
    # (the display list is KEPT from frame to frame -- the HUD writes its
    # words only when they change -- so last frame's pips are taken off the
    # end first: if the count is still the one they left)
    p.load(PIPN).emit(f"jz {pt_}_pp")
    p.load(spec.DL_BASE).load(PIPE).emit("eq", f"jz {pt_}_pp")
    p.load(spec.DL_BASE).load(PIPN).emit("sub").store(spec.DL_BASE)
    p.mark(f"{pt_}_pp")
    p.set(PIPN, 0)
    for g_ in range(NGATE):
        kp = f"{pt_}_pip{g_}"
        p.load(KEYS).push(1 << g_).emit("and", f"jz {kp}")
        p.addi(PIPN, 1)
        p.push(int(PIPS) + g_ * spec.DL_STRIDE).store(CP["src"])
        p.load(spec.DL_BASE).push(spec.DL_STRIDE).emit("mul").push(spec.DL_BASE + 1).emit("add").store(CP["dst"])
        p.push(spec.DL_STRIDE).store(CP["n"])
        p.emit(f"call {L_COPY}")
        p.addi(spec.DL_BASE, 1)
        p.mark(kp)
    if L6:                                       # (on a hatch: the map's green square -- SELECT opens it)
        if L7:
            p.load(DESKN).emit(f"jz {pt_}_mi")
        else:
            p.load(BESTB).push(int(2.0 * ONE)).emit("lt", f"jz {pt_}_mi")
        for t_ in range(2):
            p.push(int(MAPICON) + t_ * spec.DL_STRIDE).store(CP["src"])
            p.load(spec.DL_BASE).push(spec.DL_STRIDE).emit("mul").push(spec.DL_BASE + 1).emit("add").store(CP["dst"])
            p.push(spec.DL_STRIDE).store(CP["n"])
            p.emit(f"call {L_COPY}")
            p.addi(spec.DL_BASE, 1).addi(PIPN, 1)
        p.mark(f"{pt_}_mi")
    p.load(spec.DL_BASE).store(PIPE)

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
# P18: THE HORDE'S BAR, top left under the gauge: two pixels a demon left
# in the district (to 150). On the darken rectangle -- alive and unstruck
# it is free; the fall and the hit flash, below, take it back.
hbr = p.label("hbar")
p.load(F["dead"]).emit(f"jz {hbr}_a", f"jmp {hbr}")
p.mark(f"{hbr}_a")
p.load(RES).emit("dup").push(150).emit("lt", f"jz {hbr}_c", f"jmp {hbr}_k")
p.mark(f"{hbr}_c")
p.emit("drop").push(150)
p.mark(f"{hbr}_k")
p.emit("dup", "add").push(8).emit("add", "shl 10").push(8).emit("or").store(HB + 6)
p.set(HB + 7, 15 | (16 << 10))
p.push(12).load(RES).emit(f"jz {hbr}_0", f"jmp {hbr}_1")
p.mark(f"{hbr}_0")
p.emit("drop").push(0)
p.mark(f"{hbr}_1")
p.emit("shl 24").push32(0xB01818).emit("or").store(HB + 8)
p.mark(hbr)
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
    sd = np.load(ROOT / "assets" / "tnd" / "song.npz")
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
# P15: THE SWING, HEARD (tear.py 1188: sfx.swing_whoosh on every punch's
# launch, sfx.special_boom on the haymaker's). Two more tables and no more
# voices: the whoosh plays through the whiff's descriptor and the boom
# through the step's, each trigger naming its table as it rings.
#   WHOOSH  air moved fast: noise climbing as the arm comes round, gone in
#           nine frames -- brighter and shorter than the whiff, which is
#           the sound of that air finding nothing
#   BOOM    the haymaker's wind-up let go: low noise, loud, falling
SND_WHOOSH = cart.data(Table(seq([hz(46 + 9 * k) for k in range(9)],
                                 (3, 6, 9, 9, 7, 5, 3, 2, 0))), "snd_whoosh", borrow="auto")
SND_BOOM = cart.data(Table(seq([hz(16 - k) for k in range(9)],
                               (15, 15, 13, 11, 9, 7, 5, 3, 0))), "snd_boom", borrow="auto")
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
if not L2:                                   # (P34, layer 2: on the shot's frame, where it is fired)
    p.set(SG["nt"], 0)
p.emit(f"jmp {sw}_w")
p.mark(f"{sw}_w0")
p.load(F["con"]).emit(f"jz {sw}_w1", f"jmp {sw}_w")
p.mark(f"{sw}_w1")
p.load(AF).push(1).emit("add")
row(PMT, F["mv"], "endact")
p.emit("eq", f"jz {sw}_w")
p.set(int(PLAYD["whiff"]) + 1, int(SND_WHIFF)).set(SG["wt"], 0)
p.mark(f"{sw}_w")
# P15: a punch's launch -- the haymaker's boom, or the whoosh
p.load(ANIM).push(2).emit("eq", f"jz {sw}_l")
p.load(AF).emit(f"jz {sw}_l0", f"jmp {sw}_l")
p.mark(f"{sw}_l0")
p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {sw}_lp", f"jmp {sw}_l")   # (a shot: the crack)
p.mark(f"{sw}_lp")
p.load(F["mv"]).push(MOVE["special"]).emit("eq", f"jz {sw}_lw")
p.set(int(PLAYD["step"]) + 1, int(SND_BOOM)).set(SG["st"], 0).emit(f"jmp {sw}_l")
p.mark(f"{sw}_lw")
p.set(int(PLAYD["whiff"]) + 1, int(SND_WHOOSH)).set(SG["wt"], 0)
p.mark(f"{sw}_l")
p.load(ANIM).push(1).emit("eq", f"jz {sw}_s")         # a step each half stride
p.load(AF).push(15).emit("and", f"jz {sw}_s1", f"jmp {sw}_s")
p.mark(f"{sw}_s1")
p.set(int(PLAYD["step"]) + 1, int(SND_STEP)).set(SG["st"], 0)
p.mark(f"{sw}_s")
# P15: the touchdown rang the step's clock from the air's own code, long
# before the sounds were placed: name its table here, on the same frame
p.load(LANDT).push(LAND_FOR).emit("eq", f"jz {sw}_t")
p.set(int(PLAYD["step"]) + 1, int(SND_STEP))
p.mark(f"{sw}_t")
# P15: THE RUN'S FEET (tear.py 2678: footsteps in every gait). A footfall
# is the stride's clock crossing a half -- its pose index reaching 0 or 8
# this frame and not the last
rs_ = p.label("runstep")
p.load(F["spd"]).emit(f"jz {rs_}")
p.load(F["py"]).emit(f"jz {rs_}_g", f"jmp {rs_}")
p.mark(f"{rs_}_g")
p.load(F["ph"]).emit("shr 19")                                        # half strides so far
p.load(F["ph"]).load(F["spd"]).push(int(4 * ONE)).emit("mulq", "sub", "shr 19")   # ...and a frame ago
p.emit("eq", f"jz {rs_}_s", f"jmp {rs_}")
p.mark(f"{rs_}_s")
p.set(int(PLAYD["step"]) + 1, int(SND_STEP)).set(SG["st"], 0)
p.mark(rs_)
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
    # channel count is the volume control (carts/witness/gen_stream.py). Each walks
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
if L2:
    # P33: THE FIGHT'S OWN "BEFORE". A press is fresh against the pad of the
    # frame before -- but that was kept every frame of glass, the held ones
    # too, so in slowed time two presses in three were never fresh to the
    # fight: the run's double click and the slide's Down were lost. The
    # fight keeps its own, from its own frames. (And the click's clock, a
    # thumb's, counts the held frames as well.)
    pvf = p.label("prevf")
    p.load(F["skip"]).emit(f"jz {pvf}_r")
    p.load(RDT).push(255).emit("lt", f"jz {pvf}")
    p.addi(RDT, 1).emit(f"jmp {pvf}")
    p.mark(f"{pvf}_r")
    p.emit("load 1").store(PVF)
    p.mark(pvf)

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
city_subs()


# ARENA: ( -- inside? ) for (ar_x, ar_z), the archive's '+'.
p.mark(L_ARENA)
# P19: THE CITY IS THE ARENA. The point's node and its place in the tile:
# inside the junction (|u|, |v| < AR_W) is street; past it on one axis,
# street if that side is not closed; past it on both (a corner), street
# only if both sides open into a plaza. The crossroads' own test, from a
# map -- the same AR_W from every wall.
city_node(p, AR["x"], AR["z"])
ai_ = p.label("ain")
p.load(CT["n"]).push(0).emit("lt", f"jz {ai_}_on")
p.push(0).emit("ret")
p.mark(f"{ai_}_on")
for cell, coord in ((AR["u"], "x"), (AR["v"], "y")):
    # the coordinate in the tile, -16..16: archive x is zeta z; y is -x
    if coord == "x":
        p.load(AR["z"]).push32(int((OXA + HT) * ONE)).emit("add")
    else:
        p.push32(int((OYA + HT) * ONE)).load(AR["x"]).emit("sub")
    p.push32((1 << TSH) - 1).emit("and").push32(1 << (TSH - 1)).emit("sub").store(cell)
if L7:
    # P40: A ROOM (the word's bit 31) is all floor, to ROOM_W from its
    # walls; past that on one axis it is floor only in a doorway -- within
    # the lane's width on the other axis, on a side that is not closed
    rm = p.label("aroom")
    _rw = int(ROOM_W * ONE)
    p.load(CT["w"]).push(0).emit("lt", f"jz {rm}")
    for cell, dst in ((AR["u"], RMU), (AR["v"], RMV)):
        p.load(cell).emit("dup").push(0).emit("lt", f"jz {rm}_a{int(dst)}")
        p.push(0).emit("swap", "sub")
        p.mark(f"{rm}_a{int(dst)}")
        p.store(dst)
    p.load(RMU).push32(_rw).emit("lt", f"jz {rm}_uo")
    p.load(RMV).push32(_rw).emit("lt", f"jz {rm}_vo")
    p.push(1).emit("ret")
    p.mark(f"{rm}_vo")                                 # past it north or south
    p.load(RMU).load(AWC).emit("lt", f"jz {rm}_zero")
    p.push(0).load(AR["v"]).emit("lt", f"jz {rm}_s")
    p.push(0).load(CT["w"]).push(3).emit("and", "lt", "ret")
    p.mark(f"{rm}_s")
    p.push(0).load(CT["w"]).emit("shr 4").push(3).emit("and", "lt", "ret")
    p.mark(f"{rm}_uo")                                 # past it east or west
    p.load(RMV).load(AWC).emit("lt", f"jz {rm}_zero")
    p.push(0).load(AR["u"]).emit("lt", f"jz {rm}_w")
    p.push(0).load(CT["w"]).emit("shr 2").push(3).emit("and", "lt", "ret")
    p.mark(f"{rm}_w")
    p.push(0).load(CT["w"]).emit("shr 6").push(3).emit("and", "lt", "ret")
    p.mark(f"{rm}_zero")
    p.push(0).emit("ret")
    p.mark(rm)
for cell, hi_side, lo_side, out in ((AR["u"], 1, 3, "x"), (AR["v"], 0, 2, "y")):
    t_ = p.label("aside")
    p.push(9).store(KP[out])                       # 9: inside on this axis
    (p.load(AWC) if BASE else p.push(AR_W)).load(cell).emit("lt", f"jz {t_}_lo")
    p.load(CT["w"]).emit(f"shr {2 * hi_side}").push(3).emit("and").store(KP[out])
    p.mark(f"{t_}_lo")
    (p.load(cell).push(0).load(AWC).emit("sub") if BASE else p.load(cell).push(-AR_W)).emit("lt", f"jz {t_}")
    p.load(CT["w"]).emit(f"shr {2 * lo_side}").push(3).emit("and").store(KP[out])
    p.mark(t_)
p.load(KP["x"]).push(9).emit("eq", f"jz {ai_}_x")
p.push(0).load(KP["y"]).emit("lt", "ret")          # inside on x: y's side open?
p.mark(f"{ai_}_x")
p.load(KP["y"]).push(9).emit("eq", f"jz {ai_}_c")
p.push(0).load(KP["x"]).emit("lt", "ret")
p.mark(f"{ai_}_c")
p.load(KP["x"]).load(KP["y"]).emit("add").push(4).emit("eq", "ret")   # a corner

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
    for k, c in enumerate(("qx", "qy", "qz")):      # P15: the spark, at the fist
        p.load(W[c]).store(int(SPK) + k)
    p.set(int(SPK) + 3, SPARK_FOR)
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
ag_ = p.label("aimgun")                          # P18: THE GUN lands on the
p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt")                # demon its line met --
p.load(F["mv"]).push(MOVE["special"]).emit("eq")                # and in targeting the
p.load(F["sty"]).push(SQ_TARGET).emit("eq", "and", "or", f"jz {ag_}")   # haymaker too
                                                                # ("it needs to hit the
                                                                # target every time")
p.load(AIM).load(F["dmi"]).emit("eq", f"jz {lab['noA']}")        # (or its target),
p.load(F["sty"]).push(SQ_TARGET).emit("eq", f"jz {ag_}_hit")     # at any range, and
p.load(F["aimh"]).push(0).emit("eq").store(W["head"])           # no other -- and in
p.emit(f"jmp {ag_}_hit")                                          # targeting, HIGH is
p.mark(ag_)                                                       # the head
p.load(W["d2"])
row(PMT, F["mv"], "reach2")
p.emit("lt", f"jz {lab['noA']}")
p.mark(f"{ag_}_hit")
landed(PMT, F["mv"], False)
# P18: THE SPARK WHERE IT HIT. It stood at his fist's point -- for the gun
# that is his hand, a street away from the demon it hit. A shot's spark is
# ON the demon at the height it struck (head 1.7, body 1.15, targeting's low
# shot the legs at 0.55); a fist's is the contact, the struck height pulled
# four tenths of the way from the demon toward his fist.
spk = p.label("spk")
p.push(int(1.15 * ONE)).load(W["head"]).push(int(0.55 * ONE)).emit("mul", "add")
p.load(cur("py")).emit("add").store(W["oy"])               # the struck height
p.push(MOVE["gun"] - 1).load(F["mv"]).emit("lt", f"jz {spk}_f")
p.load(F["sty"]).push(SQ_TARGET).emit("eq", f"jz {spk}_g")
p.load(F["aimh"]).push(2).emit("eq", f"jz {spk}_g")
p.push(int(0.55 * ONE)).load(cur("py")).emit("add").store(W["oy"])
p.mark(f"{spk}_g")                              # (on its FRONT, 0.45 out along its
p.load(cur("h8")).emit("shr 8").store(W["dc"])  # facing -- at its centre the spark
sin_of(p, cell=W["dc"])                          # was inside the body, and hidden)
p.push(int(0.45 * ONE)).emit("mulq").load(cur("x")).emit("swap", "sub").store(int(SPK))
p.load(W["oy"]).store(int(SPK) + 1)
sin_of(p, 256, cell=W["dc"])
p.push(int(0.45 * ONE)).emit("mulq").load(cur("z")).emit("add").store(int(SPK) + 2)
p.emit(f"jmp {spk}")
p.mark(f"{spk}_f")
for k, (a, qc) in enumerate(((cur("x"), "qx"), (W["oy"], "qy"), (cur("z"), "qz"))):
    p.load(W[qc]).load(a).emit("sub").push(int(0.4 * ONE)).emit("mulq").load(a).emit("add")
    p.store(int(SPK) + k)
p.mark(spk)
p.load(cur("hp")).load(W["dmg"]).emit("sub").store(cur("hp"))
p.load(W["stop"]).emit("dup", "dup").store(cur("stop")).store(F["stop"])
p.store(F["shake"])
# P16: THE GUN IS A CHIP, NOT A LEASH. Every blow stunned for its stop + 12
# and broke a swing, the plain shot included -- and locked, the shot lands
# at any range, eighteen frames apart. On the tape no demon ever swung: the
# longest any stood ready was 20 of the 74 frames a swing needs. So the
# plain shot on a body with its feet down takes its damage, its flinch
# (the four frames of stop) and its style, and nothing else: it walks on
# through the fire and its swing still comes. A body ALOFT is juggled by
# shots as before, and the charged shot still stops anything.
gch = p.label("gunchip")
p.load(F["mv"]).push(MOVE["gun"]).emit("eq", f"jz {gch}_s")
p.load(cur("py")).emit(f"jz {gch}_g", f"jmp {gch}_s")
p.mark(f"{gch}_g")                              # P18: ...unless targeting aimed it LOW:
p.load(F["sty"]).push(SQ_TARGET).emit("eq", f"jz {gch}")   # the legs -- it staggers,
p.load(F["aimh"]).push(2).emit("eq", f"jz {gch}")          # and its approach stops
p.set(cur("vx"), 0).set(cur("vz"), 0).set(AI, 0)
p.mark(f"{gch}_s")
p.load(W["stop"]).push(12).emit("add").store(cur("hs"))
p.set(ST, 2).set(MF, 0)                         # a hit stops a swing
p.mark(gch)
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
# THE LAUNCHER sends it up, helpless the whole arc; any OTHER blow on a
# body already aloft floors its rise to a nudge and refreshes its stun
# (tear.py AIR_HIT_FLOAT / AIR_HIT_HANG) -- so a string keeps it there
lw, la = p.label("lift"), p.label("airh")
row(PMT, F["mv"], "lift")
p.emit("dup", f"jz {lw}_no")
p.store(cur("vy"))
p.set(F["slow"], SLOW_LAUNCH)                   # P18: a launcher lands: slow motion
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
fz_ = p.label("fskip")
p.load(F["skip"]).emit(f"jz {fz_}", "ret")      # P18: FOCUS holds them too
p.mark(fz_)
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
p.set(MOV, 1)                    # P16: ...and its wait is KEPT while it steps.
# (It was zeroed here. A fighter who keeps moving -- every blow of his
# lunges him forward -- made the ring step after him each time, and each
# step started the wait again: scripted, two demons stood beside a string
# for 760 frames and never swung. Off its nose still clears it, below.)
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
tk_ = p.label("token")                           # P18: into the tell only with a
p.load(AI).push(DREST - 30).emit("eq", f"jz {tk_}")   # token, and on screen
p.load(TOKC).push(TOKENS).push(0).load(LVL).emit("lt", "add", "lt", f"jz {tk_}_h")   # (the camera's line, from
sin_of(p, cell=CY)                               # its lens: dot > 0 and
p.load(X).load(spec.CAM_X).emit("sub", "mulq").push(0).emit("swap", "sub")   # cross^2
sin_of(p, 256, cell=CY)                          # < tan^2 dot^2)
p.load(Z).load(spec.CAM_Z).emit("sub", "mulq", "add").emit("dup").store(W["dc"])   # dot
p.push(0).emit("swap", "lt", f"jz {tk_}_h")
sin_of(p, 256, cell=CY)
p.load(X).load(spec.CAM_X).emit("sub", "mulq")
sin_of(p, cell=CY)
p.load(Z).load(spec.CAM_Z).emit("sub", "mulq", "add", "dup", "mulq")          # cross^2
p.load(W["dc"]).emit("dup", "mulq").push(ONSCREEN_TAN2).emit("mulq", "lt", f"jz {tk_}_h")
p.addi(TOKC, 1).emit(f"jmp {tk_}")               # a token, taken
p.mark(f"{tk_}_h")
p.set(AI, DREST - 31)                            # held at the threshold
p.mark(tk_)
p.load(AI).push(DREST).emit("eq", f"jz {lab['clip']}")
hs0 = p.label("relw")                             # P20b: deeper, the next wait starts in
p.load(LVL).push(REL_STEP).emit("mul", "dup").push(REL_MAX).emit("lt", f"jz {hs0}")
p.emit("drop").push(REL_MAX)
p.mark(hs0)
p.store(AI)
p.set(ST, 1).set(MF, 0).set(cur("con"), 0)
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
p.load(F["hs"]).emit(f"jz {lab['noC']}_h", f"jmp {lab['noC']}")   # NOT WHILE HE REELS
p.mark(f"{lab['noC']}_h")                         # (7 of 39 blows on the second tape)
p.push(int(0.3 * ONE)).load(F["py"]).emit("lt", f"jz {lab['noC']}_y", f"jmp {lab['noC']}")
p.mark(f"{lab['noC']}_y")                         # ...nor aloft, past 0.3 (his keys are on
                                                  # the ground; and a leap over a crowd
                                                  # must not be swatted from it)
cc_ = p.label("close")                            # A DODGE IS UNTOUCHABLE: the fist
p.load(F["evf"]).emit(f"jz {cc_}")                # goes through him, spent, and a
p.set(cur("con"), 1)                              # close call pays
p.load(SY["pts"]).push(CLOSE_CALL * 16).emit("add").store(SY["pts"])
p.set(SY["idle"], 0).emit(f"jmp {lab['noC']}")
p.mark(cc_)
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

# ISP: (P20b) where a lesser demon comes from -- two streets on from his
# node, trying side s first: on down the street if it goes on, else round
# its corner -> (w_bx, w_bz)
for s0 in range(4):
    p.mark(L_ISP[s0])
    for t_ in range(4):
        k = (s0 + t_) % 4
        dx, dy, _ = city.DIRS[k]
        nt = p.label("ispt")
        p.load(CT["w1"]).emit(f"shr {2 * k}").push(3).emit("and", f"jz {nt}")
        p.load(ICX).push32(int(-dy * TILE * ONE)).emit("add").store(W["bx"])
        p.load(ICZ).push32(int(dx * TILE * ONE)).emit("add").store(W["bz"])
        p.load(CT["n1"]).push(CSTEP[k] + int(CMAP)).emit("add", "loadi").store(W["qy"])
        for j in (k, (k + 1) % 4, (k + 3) % 4):
            jx, jy, _ = city.DIRS[j]
            far = 9.0 if j == k else 7.0             # (20-25 off: deep in the haze)
            nj = p.label("ispj")
            p.load(W["qy"]).emit(f"shr {2 * j}").push(3).emit("and", f"jz {nj}")
            p.load(W["bx"]).push32(int(-jy * far * ONE)).emit("add").store(W["bx"])
            p.load(W["bz"]).push32(int(jx * far * ONE)).emit("add").store(W["bz"])
            p.emit("ret")
            p.mark(nj)
        p.emit("ret")
        p.mark(nt)
    p.load(ICX).store(W["bx"]).load(ICZ).store(W["bz"]).emit("ret")

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

# P18: STEER -- turn his yaw toward w_head by at most w_dg, the short way
hi_, lo_ = p.label("sth"), p.label("stl")
p.mark(L_STEER)
p.load(W["head"]).load(YAW).emit("sub").push(512).emit("add")
p.push(1023).emit("and").push(512).emit("sub")           # gap, -512..511
p.emit("dup").load(W["dg"]).emit("swap", "lt", f"jz {hi_}")   # dg < gap: dg
p.emit("drop").load(W["dg"])
p.mark(hi_)
p.emit("dup").push(0).load(W["dg"]).emit("sub", "lt", f"jz {lo_}")   # gap < -dg: -dg
p.emit("drop").push(0).load(W["dg"]).emit("sub")
p.mark(lo_)
p.load(YAW).emit("add").push(1023).emit("and").store(YAW)
p.emit("ret")

if L2:
    # P34: RAY -- the line a shot takes from where he stands, along w_head:
    # ray_len how far it goes (GUN_RANGE at most), ray_hit what stops it (0
    # nothing, 1 a wall, 2 the key), (ray_x, ray_z) where. The town's own
    # test of the street (L_ARENA, at the wall's face), a unit at a time and
    # then halved back to an eighth -- the SAME line for the sight and for
    # the bullet, so what is shown is what is hit. Nothing is aimed for him.
    ry = p.label("ray")
    p.mark(L_RAY)
    sin_of(p, cell=W["head"])
    p.push(0).emit("swap", "sub").store(RAY["dx"])           # forward x = -sin
    sin_of(p, 256, cell=W["head"])
    p.store(RAY["dz"])
    # (from the gun: half a unit ahead of him and a seventh to his right --
    # he comes no nearer a wall than that, so it is always in the street)
    for o_, me, a_, b_, sg in (("ox", PX, "dx", "dz", "add"), ("oz", PZ, "dz", "dx", "sub")):
        p.load(RAY[a_]).push(GUN_F).emit("mulq").load(RAY[b_]).push(GUN_R).emit("mulq", sg)
        p.load(me).emit("add").store(RAY[o_])
    p.set(AWC, SHOT_W).set(RAY["len"], 0).set(RAY["hit"], 0).set(RAY["step"], ONE)
    p.mark(f"{ry}_l")
    p.load(RAY["len"]).load(RAY["step"]).emit("add").store(RAY["len"])
    p.push32(int(GUN_RANGE * ONE)).load(RAY["len"]).emit("lt", f"jz {ry}_t")
    p.push32(int(GUN_RANGE * ONE)).store(RAY["len"]).emit(f"jmp {ry}_d")
    p.mark(f"{ry}_t")
    for c_, me, d_ in ((AR["x"], RAY["ox"], "dx"), (AR["z"], RAY["oz"], "dz")):
        p.load(RAY[d_]).load(RAY["len"]).emit("mulq").load(me).emit("add").store(c_)
    p.emit(f"call {L_ARENA}", f"jz {ry}_o", f"jmp {ry}_l")
    p.mark(f"{ry}_o")                                        # off the street: back, and halve
    p.load(RAY["len"]).load(RAY["step"]).emit("sub").store(RAY["len"])
    p.load(RAY["step"]).emit("shr 1").store(RAY["step"]).set(RAY["hit"], 1)
    p.push(ONE >> 4).load(RAY["step"]).emit("lt", f"jz {ry}_d", f"jmp {ry}_l")
    p.mark(f"{ry}_d")
    # THE KEY (the player: "we can use the item as a target"): lying in its
    # plaza, on the line and nearer than the wall, it is what the shot meets
    p.load(KEY).emit(f"jz {ry}_k", f"jmp {ry}_e")
    p.mark(f"{ry}_k")
    item_exists(p).emit(f"jz {ry}_e")
    p.push(int(0.9 * ONE)).load(F["py"]).emit("lt", f"jz {ry}_g", f"jmp {ry}_e")   # (fired from the air: over it)
    p.mark(f"{ry}_g")
    p.load(KX).load(RAY["ox"]).emit("sub").store(W["qx"]).load(KZ).load(RAY["oz"]).emit("sub").store(W["qz"])
    p.load(W["qx"]).load(RAY["dx"]).emit("mulq").load(W["qz"]).load(RAY["dz"]).emit("mulq", "add")
    p.store(W["d2"])                                         # how far along the line
    p.push(0).load(W["d2"]).emit("lt", f"jz {ry}_e")
    p.load(W["d2"]).load(RAY["len"]).emit("lt", f"jz {ry}_e")
    p.load(W["qx"]).load(RAY["dz"]).emit("mulq").load(W["qz"]).load(RAY["dx"]).emit("mulq", "sub")
    p.emit("dup").push(KEY_R).emit("lt", f"jz {ry}_x")       # ...and how far off it
    p.push(-KEY_R).emit("swap", "lt", f"jz {ry}_e")
    p.load(W["d2"]).store(RAY["len"]).set(RAY["hit"], 2)
    p.emit(f"jmp {ry}_e")
    p.mark(f"{ry}_x")
    p.emit("drop")
    p.mark(f"{ry}_e")
    if L4:
        # P37: ...or AN ENEMY that is up: on the line, within its body's
        # width of it, and nearer than whatever the line met before (3 + its
        # number). The same test the key has; nothing is aimed for him.
        for e_ in ENEMY:
            rn = p.label("rayenemy")
            p.load(e_["st"]).push(1).emit("eq", f"jz {rn}")
            p.load(int(e_["pos"])).load(RAY["ox"]).emit("sub").store(W["qx"])
            p.load(int(e_["pos"]) + 1).load(RAY["oz"]).emit("sub").store(W["qz"])
            p.load(W["qx"]).load(RAY["dx"]).emit("mulq").load(W["qz"]).load(RAY["dz"]).emit("mulq", "add")
            p.store(W["d2"])
            p.push(0).load(W["d2"]).emit("lt", f"jz {rn}")
            p.load(W["d2"]).load(RAY["len"]).emit("lt", f"jz {rn}")
            p.load(W["qx"]).load(RAY["dz"]).emit("mulq").load(W["qz"]).load(RAY["dx"]).emit("mulq", "sub")
            p.emit("dup").push(E_R).emit("lt", f"jz {rn}_x")
            p.push(-E_R).emit("swap", "lt", f"jz {rn}")
            p.load(W["d2"]).store(RAY["len"]).set(RAY["hit"], 3 + e_["k"])
            p.emit(f"jmp {rn}")
            p.mark(f"{rn}_x")
            p.emit("drop")
            p.mark(rn)
    for c_, me, d_ in ((RAY["x"], RAY["ox"], "dx"), (RAY["z"], RAY["oz"], "dz")):
        p.load(RAY[d_]).load(RAY["len"]).emit("mulq").load(me).emit("add").store(c_)
    p.set(AWC, AR_W)
    p.emit("ret")

    if L3:                                      # RING -- the key, struck by a fist
        p.mark(L_RING)
        p.set(SG["gt"], 0).set(SG["gr"], 3).emit("ret")

    # FIRE -- a round leaves the gun along w_head (the shot's frame; or, P36,
    # in the locked run, the release itself)
    fr_ = p.label("fire")
    p.mark(L_FIRE)
    knob(p, "mag")
    p.emit(f"jz {fr_}_s")                                  # (0: it never runs dry)
    p.load(SHOTS)
    knob(p, "mag")
    p.emit("lt", f"jz {fr_}")
    p.addi(SHOTS, 1).load(SHOTS)
    knob(p, "mag")
    p.emit("lt", f"jz {fr_}_e", f"jmp {fr_}_s")
    p.mark(f"{fr_}_e")
    p.set(RLD, RELOAD)                                     # the last round: it reloads
    p.mark(f"{fr_}_s")
    p.emit(f"call {L_RAY}")
    if L4:
        # P37: locked, the round goes at the SPOT (its height and what it
        # does to who it strikes); else the gun's own height, and mid
        fy_ = p.label("firey")
        p.load(F["py"]).push(GUN_Y).emit("add").store(W["bx"]).set(W["bz"], 1)
        p.load(LOCK).emit(f"jz {fy_}")
        p.push(int(SPOTY)).load(SPOT).emit("add", "loadi").store(W["bx"]).load(SPOT).store(W["bz"])
        p.mark(fy_)
    p.push(1).load(BNX).emit("sub", "dup").store(BNX)      # the other slot
    p.push(len(BK)).emit("mul").push(int(BUL[0]["ex"])).emit("add").store(W["k"])
    for name, ops in (("ex", (f"load {int(RAY['x'])}",)), ("ez", (f"load {int(RAY['z'])}",)),
                      ("dx", (f"load {int(RAY['dx'])}",)), ("dz", (f"load {int(RAY['dz'])}",)),
                      ("rem", (f"load {int(RAY['len'])}", "push 2", "add")),
                      ("y", (f"load {int(W['bx'])}",) if L4 else (f"load {int(F['py'])}", f"push {GUN_Y}", "add")),
                      ("yaw", (f"load {int(W['head'])}",)),
                      # (the hit's word. Layer 4: what it meets, 0..15 | charged << 4 | spot << 5)
                      ("hit", (f"load {int(F['mv'])}", f"push {MOVE['gun']}", "sub", "push 16", "mul",
                               f"load {int(RAY['hit'])}", "add", f"load {int(W['bz'])}", "push 32", "mul", "add")
                       if L4 else
                       (f"load {int(F['mv'])}", f"push {MOVE['gun']}", "sub", "push 4", "mul",
                        f"load {int(RAY['hit'])}", "add"))):
        p.emit(*ops).load(W["k"]).push(BK[name]).emit("add", "storei")
    p.set(SG_T["nt"], 0)                                   # the crack, and the kick:
    p.push(3).load(F["mv"]).push(MOVE["gun"]).emit("sub").push(4).emit("mul", "add").store(F["shake"])
    p.mark(fr_)                                            # 3 frames, the charged one 7
    p.emit("ret")

    # P34: LAND -- bullet w_k has come to the end of its line. A wall or the
    # key: the burst there, and the thud; the charged shot shakes the lens;
    # the key rings and leaps. (Out of range it is simply gone.)
    ld = p.label("landed")
    p.mark(L_LAND)
    p.load(W["k"]).push(len(BK)).emit("mul").push(int(BUL[0]["ex"])).emit("add").store(W["k"])

    def bf(name):
        p.load(W["k"]).push(BK[name]).emit("add", "loadi")
    if L4:
        bf("hit")
        p.push(15).emit("and", f"jz {ld}")
    else:
        bf("hit")
        p.push(3).emit("and", f"jz {ld}")
    for k_, name in enumerate(("ex", "y", "ez")):
        bf(name)
        p.store(int(SPK) + k_)
    p.set(int(SPK) + 3, SPARK_FOR).set(SPKM, HOT_M)
    p.set(int(PLAYD["step"]) + 1, int(SND_STEP)).set(SG["st"], 0)
    bf("hit")
    p.push(16 if L4 else 4).emit("and", f"jz {ld}_c")
    p.set(F["shake"], 4)
    p.mark(f"{ld}_c")
    bf("hit")
    p.push(15 if L4 else 3).emit("and").push(2).emit("eq", f"jz {ld}_k")
    p.set(KHIT, 40).set(SG["gt"], 0).set(SG["gr"], 3)
    p.emit(f"jmp {ld}")
    p.mark(f"{ld}_k")
    if L4:
        # P37: AN ENEMY, STRUCK. A round is 1 off it, the charged one 3;
        # HIGH it is doubled; LOW it is held three times as long (it does
        # not come on); and it flashes.
        bf("hit")
        p.emit("shr 4").push(1).emit("and").push(2).emit("mul").push(1).emit("add").store(W["dmg"])
        p.push(12).store(W["stop"])
        bf("hit")
        p.emit("shr 5").push(3).emit("and", "dup", f"jz {ld}_hi")
        p.push(2).emit("eq", f"jz {ld}_e")
        p.push(36).store(W["stop"]).emit(f"jmp {ld}_e")
        p.mark(f"{ld}_hi")
        p.emit("drop").load(W["dmg"]).push(2).emit("mul").store(W["dmg"])
        p.mark(f"{ld}_e")
        for e_ in ENEMY:
            le = p.label("lande")
            bf("hit")
            p.push(15).emit("and").push(3 + e_["k"]).emit("eq", f"jz {le}")
            enemy_hurt(p, e_)
            p.emit(f"jmp {ld}")
            p.mark(le)
    p.mark(ld)
    p.emit("ret")

# P18: LINE -- the free shot's demon: the live one nearest the line w_head,
# within GUN_CONE of it and 13 units -> f_aim (its slot + 1, or 0). A shot
# goes exactly where the pad points; this only says whom that line meets.
p.mark(L_LINE)
p.push(GUN_CONE + 1).store(W["dc"]).set(AIM, 0)
p.load(W["head"]).store(W["oy"])
for d in range(3):
    nx = p.label("ln_n")
    p.load(dslot(d, "st")).push(3).emit("lt", f"jz {nx}")
    p.load(dslot(d, "x")).load(PX).emit("sub", "dup", "mulq")
    p.load(dslot(d, "z")).load(PZ).emit("sub", "dup", "mulq", "add")
    p.push32(GUN_AIM2).emit("lt", f"jz {nx}")
    p.set(F["brg"], d).emit(f"call {L_BRG}")
    p.load(F["brg"]).load(W["oy"]).emit("sub").push(512).emit("add")
    p.push(1023).emit("and").push(512).emit("sub")
    p.emit("dup").push(0).emit("lt", f"jz {nx}_p")      # |gap|
    p.push(0).emit("swap", "sub")
    p.mark(f"{nx}_p")
    p.emit("dup").load(W["dc"]).emit("lt", f"jz {nx}_f")
    p.store(W["dc"]).set(AIM, d + 1).emit(f"jmp {nx}")
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
# P16: ...and BEFORE it starts. A cross is five frames from its first to
# its fist -- nobody dodges on that. The demon's wait is the tell: its last
# 24 frames squared up and in reach show amber, and then the swing's own
# frames go amber and red as before.
p.push(DREST - 25).load(W["k"]).push(DF["ai"]).emit("add", "loadi", "lt", f"jz {tl_}_w")
p.set(FK["aw"], 3)
p.mark(f"{tl_}_w")
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
    assert len(words) <= PAGE, f"a program of {len(words)} words"
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
             ("BORROW_END", END_LO), ("BORROW_END_N", B_END),
             ("POSE_WALK", base["walk"]), ("POSE_LAND", base["land"]),
             ("DREST", DREST), ("PK_TOP", PK_TOP), ("CAM_TURN", CAM_TURN),
             ("PAGE", PAGE), ("DL_LEASE", DL_LEASE), ("CITY_OXA", OXA), ("CITY_OYA", OYA), ("AR_W", AR_W),
             ("CITY_TILE", int(TILE))):
    cart.const(k, int(v))                       # (for the gates: tests/test_tnd.py)
out = cart.write(OUT)
print(cart.report())
print(f"programs: the game {len(_main_w)} words, the intro {len(_intro_w)}, "
      f"the pause {len(_pause_w)}")
print(f"city: {CS}x{CS}, {len(KINDS)} pieces, {CITY_FACES} faces, "
      f"{len(PIECE_M)} meshes")
print(f"poses: {len(bank) // SPAN} x {SPAN} words = {len(bank)} words "
      f"of CRAM; bases {base}")
