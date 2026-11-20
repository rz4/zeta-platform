#!/usr/bin/env python3
"""gen_face.py -- writes carts/system/face.zol: the machine's face, and its demo.

THE SEQUENCE, per the concept storyboard:

  Black. The starfield of Zeta Reticuli resolves, the primary at dead
  centre. A four-point glint blooms at it and condenses into a silver
  teardrop that FALLS, trailing light, the camera tracking it down as
  the stars stream away overhead; it lands under an empty black sky on
  the green-and-white board, a triangle of light stands where it
  struck, and the Grey condenses inside it. The camera settles into a
  slow arc, a dark foreground rim framing the shot; the figure turns,
  RAISING ITS ARMS toward the viewer as the camera pushes in over a
  slowly tilting horizon; the frame washes to white; and Z, Xi, T land
  as still ink while the A -- the machine's own triangle -- turns
  forever at the exact centre-line of the name. Each letter lands on
  its chord note, the last a struck bell, and the sound lets go as the
  sequence ends.

THE MEASURE IS THE GAMECUBE OPENING: a piece of music with a picture
attached. The whistle falls with the drop because its pitch is read
from the same table as the drop's height -- one number, so they cannot
drift.

THE GREY IS THE PS1 SCULPT (assets/ps1low-poly-grey-alien.zip), used
at its own polygon count -- 692 triangles, which is over the machine's
512-a-mesh law, so the figure is CARVED: body, left arm, right arm,
three objects. The carve is the RIG. Each arm's origin is re-based at
its shoulder, so the object's pitch word IS the joint, and the raise
is two table reads a frame. The pivots ride the body's turn through
the law's own _rot, so the arms stay socketed to the shoulders at
every angle of the turn.

THE CAMERA, cinematic within the law:
  - it TRACKS the drop down (the sky leaves on two plate cuts, hidden
    by the motion);
  - it SETTLES into a slow lateral arc around the figure, aimed by a
    precomputed yaw that keeps the Grey centred;
  - the push-in carries a slow DUTCH ROLL through the turn;
  - and everything snaps home to the logo camera under the white,
    where nothing can be seen to snap.

Run me after changing anything: python3 carts/system/gen_face.py
"""
import math
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import carts as _carts                         # noqa: E402
_carts.on_path()                 # sibling generators, wherever they live
# the SONG BUILD (TND_SONG=1, games/tnd/gen_tnd.py): the same column from the
# local build/song/ -- the recorded theme is third-party and never committed
import os as _os                                         # noqa: E402
SONGDIR = ROOT / "build" / "song" if _os.environ.get("TND_SONG") == "1" else HERE
# THE FILM BEFORE ANY GAME (docs/PLATFORM.md). The film has always ended by
# handing the machine to the shelf; what it hands to is just a cart
# shelved in its own segment. FACE_LAUNCH names another -- a game chosen
# in the Pocket's menu still opens on the machine's face and its logo --
# and FACE_OUT says where that film-and-game goes (zeta stage).
LAUNCH = Path(_os.environ["FACE_LAUNCH"]) if _os.environ.get("FACE_LAUNCH") \
    else SONGDIR / "shelf.zol"
OUT = Path(_os.environ.get("FACE_OUT", SONGDIR / "face.zol"))

from zeta import spec                                      # noqa: E402
from zeta.gpu import _rot                                  # noqa: E402
from zeta.forge import ONE, Cart, Mesh, Plate, Table       # noqa: E402

# ---- the timeline: TEN SECONDS, per the shot board -------------------
#   [2s] black -> the constellation fades in, ENDING ON THE BLINK; a
#        single DING as the tear appears
#   [2s] THE SPECIAL PAN: the camera starts AT the impact site, the
#        tear falls toward it, and the camera TRACKS IT -- real pitch,
#        up at the star and easing level -- while backing out to the
#        vantage as the skybox steps away overhead. The board is NOT
#        THERE yet: the stage light wakes only as the tear gets low.
#   [1s] the flash recedes off a SOLID ROTATING YELLOW TETRAHEDRON
#        standing in a circular pool of light -- the alien is INSIDE
#        it and cannot be seen
#   [1s] the tetra stops, and DISSOLVES around the back-facing alien
#   [1s] the whip: violent, square, tight in your face
#   [3s] a RED flash bleeding into white, and the name
T_SKY, T_TEAR, T_FALL = 4, 120, 132
T_LAND = 240
T_SPIN0 = 294            # the tetra comes to rest
T_DISS = 300             # ...and begins to dissolve
T_TURN, T_PAN = 360, 364
T_FLASH, T_WHITE = 420, 446
T_ZETA, T_STEP, T_END = 480, 12, 600
# THE HANDOFF (SLICE stage 3): the mark holds a second after the chord,
# then the film launches the shelf with the mover protocol of
# carts/system/gen_shelf.py -- four descending DMA blocks, the program on the
# last. Driven by REG_FRAME and IMMEDIATES ONLY: the film's variables
# share the pool with its meshes and reach cell ~7500, inside the
# blocks that land first, so any launch counter in DMEM would be
# overwritten mid-launch. The machine rewrites REG_FRAME every frame
# and nothing can clobber it. The film is a ROOT cart (it boots at
# power-on, window 0), so the shelf's window is simply its base.
T_LAUNCH = T_END + 60

GREEN = 0x125C2E
WHITE = 0xDCE2DA
GREY_C = 0x8E98A6
INK = 0x0A0A0C            # the glyphs: level 1, under the threshold
SILVER = 0xE8ECF8
CITRINE = 0xE6C010
GREY_H = 1.45             # the figure's height in world units
# 330, NOT 300: the logo snap lives at f >= T_WHITE = 446, and a table
# that ends short CLAMPS TO THE PORTRAIT CAMERA for the whole logo --
# the A, projected for the logo camera, rendered from the portrait one,
# landed wherever that put it. The ink letters are screen-space and
# never moved, which is why only the A wandered.
CAM_T0, CAM_N = 120, 330  # the camera (120..449; entry 449 IS the logo cam)
DRP_T0, DRP_N = 120, 122  # the tear (appearance to strike)
ARM_T0, ARM_N = 356, 56   # the arms (through the whip and portrait)
TSP_N = 54                # the tetra's spin-down (240..293)
DIS_N = 60                # ...and its dissolve (300..359, into the turn)
ASP_N = 40                # the A: lands 516, at rest facing by 555
# THE TETRAHEDRON THE ALIEN FITS INSIDE. It is OPAQUE while it stands
# -- it writes depth, so the body drawn after it CANNOT be seen -- and
# the cone test below proves every body vertex sits within its INRADIUS
# at that height, which is the worst case over every spin angle.
TET_A, TET_APEX = 1.40, 2.20


def hz(f):
    return int(round(f * (1 << 24) / spec.SND_HZ))


def pack_n(x, y, z):
    """8:8:8 signed, 127 to the unit -- NOT 128 (spec.OBJ_LIT)."""
    def b(t):
        return max(-127, min(127, int(round(t * 127)))) & 0xFF
    return (b(x) << 16) | (b(y) << 8) | b(z)


# ---- the skies -------------------------------------------------------
def sky(shift=0.0, twins=True, dim=0):
    """Starfield with the primary of Zeta Reticuli at dead centre. The
    depth plane is ZFAR everywhere: a PLATE, so the drop occludes the
    stars per pixel. The tracking descent plays on two of these and
    then none -- a plate is glued to the glass and cannot scroll."""
    n = spec.W * spec.H
    col = [0] * n
    dep = [spec.ZFAR] * n
    up = int(spec.H * shift)
    g = math.pi * (3.0 - 5.0 ** 0.5)
    for i in range(430):
        a = i * g
        r = (i + 0.5) / 430
        x = int(spec.W * 0.5 + math.cos(a) * r * spec.W * 0.78)
        y = int(spec.H * 0.46 + math.sin(a) * r * spec.H * 0.78) - up
        if not (0 <= x < spec.W and 0 <= y < spec.H):
            continue
        fade = max(0.0, 1.0 - max(0, y + up - spec.H * 0.55)
                   / (spec.H * 0.4))
        v = int((4 + (i * 7) % 11) * fade) - dim
        if v > 0:
            col[y * spec.W + x] = (max(0, v - 3) << 10) \
                | (max(0, v - 1) << 5) | min(31, v + 2)
    for dx, dy, mag in ((0, 0, 31), (20, -9, 21)) if twins else ():
        cx, cy = spec.W // 2 + dx, int(spec.H * 0.38) + dy - up
        for oy in range(-2, 3):
            for ox in range(-2, 3):
                d = ox * ox + oy * oy
                if d > 5:
                    continue
                v = max(0, mag - d * 6)
                col[(cy + oy) * spec.W + cx + ox] = \
                    (max(0, v - 2) << 10) | (max(0, v - 1) << 5) \
                    | min(31, v + 1)
    return Plate(col, dep)


# ---- the Grey: the PS1 sculpt, carved into its own rig ----------------
def _load_obj():
    z = zipfile.ZipFile(ROOT / "assets" / "ps1low-poly-grey-alien.zip")
    inner = zipfile.ZipFile(z.open("source/Alien2.zip"))
    V, F = [], []
    for raw in inner.open("Alien2.obj"):
        l = raw.decode()
        if l.startswith("v "):
            V.append([float(x) for x in l.split()[1:4]])
        elif l.startswith("f "):
            ids = [int(w.split("/")[0]) - 1 for w in l.split()[1:]]
            for k in range(1, len(ids) - 1):        # quads fan to tris
                F.append((ids[0], ids[k], ids[k + 1]))
    return V, F


def _grey_parts():
    """(body, armL, armR) as Meshes, plus the shoulder pivots.

    THE CARVE IS THE RIG: faces whose centroid sits past |x| = 0.42 at
    arm height are an arm; each arm is re-based so its mesh origin IS
    its shoulder, which makes the object's pitch word the joint. The
    body keeps every one of the artist's remaining polygons -- this
    mesh is already the era's poly count, and decimating it would be
    sanding a coin."""
    import numpy as np
    V, F = _load_obj()
    V = np.array(V)
    F = np.array(F)
    # smooth normals from the WHOLE figure, before the carve, so the
    # shading never sees the seams
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    NV = np.zeros_like(V)
    for c in range(3):
        for a in range(3):
            np.add.at(NV[:, a], F[:, c], fn[:, a])
    NV /= np.linalg.norm(NV, axis=1, keepdims=True) + 1e-12
    # ORIENTATION, corrected on the panel: the head-centroid test said
    # the face was -z, but a Grey's CRANIUM BULGES BACKWARD -- the
    # centroid leans away from the face, not toward it. The sculpt's
    # face is +z, which is the scene's convention already: no transform.
    # The 180-degree version shipped once, and every symptom followed
    # from it -- the figure showed its (featureless) face during the
    # approach, turned AWAY at the climax, raised its arms away from
    # the camera (reported: "the arms are gone"), and aimed its feet at
    # the lens ("the feet look long").
    s = GREY_H / (V[:, 1].max() - V[:, 1].min())
    V = V * s
    V[:, 1] -= V[:, 1].min()
    V[:, 0] -= (V[:, 0].max() + V[:, 0].min()) / 2
    V[:, 2] -= (V[:, 2].max() + V[:, 2].min()) / 2
    C = V[F].mean(1)
    armL = (C[:, 0] < -0.42 * s / (1.45 / 3.25)) & (C[:, 1] > 1.2 * s / (1.45 / 3.25))
    # (the thresholds above are in the SCALED frame: 0.42 and 1.2 were
    # measured on the raw sculpt, whose scale factor is exactly ours)
    armL = (C[:, 0] < -0.42 * s) & (C[:, 1] > 1.2 * s)
    armR = (C[:, 0] > 0.42 * s) & (C[:, 1] > 1.2 * s)
    body = ~(armL | armR)

    def part(mask, pivot=None):
        ids = np.unique(F[mask])
        remap = {int(v): i for i, v in enumerate(ids)}
        P = V[ids].copy()
        if pivot is not None:
            P -= pivot
        verts = [int(v * ONE) for row in P for v in row]
        norms = [pack_n(*NV[v]) for v in ids]
        faces = [(remap[int(a)], remap[int(b)], remap[int(c)], GREY_C)
                 for a, b, c in F[mask]]
        assert len(ids) <= spec.MESH_NV_MAX and \
            len(faces) <= spec.MESH_NF_MAX
        return Mesh(verts, faces, colors=norms)

    pl = np.array([-0.44 * s * 3.25 / 1.45, 0, 0])
    # pivots, measured on the carved arms themselves: the inner-top
    aL = np.unique(F[armL]); aR = np.unique(F[armR])
    pivL = np.array([V[aL][:, 0].max(), V[aL][:, 1].max() - 0.02, 0.0])
    pivR = np.array([V[aR][:, 0].min(), V[aR][:, 1].max() - 0.02, 0.0])
    return (part(body), part(armL, pivL), part(armR, pivR),
            pivL, pivR)


# ---- the props -------------------------------------------------------
DROP_BODY_NF = 20


def drop():
    verts, faces = [], []
    seg = 10
    verts += [0, int(0.36 * ONE), 0]
    for i in range(seg):
        a = 2 * math.pi * i / seg
        verts += [int(math.cos(a) * 0.15 * ONE), 0,
                  int(math.sin(a) * 0.15 * ONE)]
    verts += [0, int(-0.20 * ONE), 0]
    tip, belly = 0, seg + 1
    for i in range(seg):
        a, b = 1 + i, 1 + (i + 1) % seg
        faces += [(tip, a, b, SILVER), (belly, b, a, SILVER)]
    t0 = len(verts) // 3
    verts += [int(-0.035 * ONE), int(0.30 * ONE), 0,
              int(0.035 * ONE), int(0.30 * ONE), 0,
              0, int(2.9 * ONE), 0]
    tw = SILVER | (7 << 24) | (spec.BLEND_ADD << 29)
    faces += [(t0, t0 + 1, t0 + 2, tw), (t0 + 1, t0, t0 + 2, tw)]
    return Mesh(verts, faces)


def flare():
    verts, faces = [], []
    fw = 0xF8FAFF | (11 << 24) | (spec.BLEND_ADD << 29)
    for (hx, hy) in ((1.35, 0.045), (0.045, 1.35)):
        b = len(verts) // 3
        for px, py in ((-1, 0), (0, -1), (1, 0), (0, 1)):
            verts += [int(px * hx * ONE), int(py * hy * ONE), 0]
        faces += [(b, b + 1, b + 2, fw), (b, b + 2, b + 3, fw),
                  (b + 2, b + 1, b, fw), (b + 3, b + 2, b, fw)]
    return Mesh(verts, faces)


def tetra():
    """SOLID YELLOW, per the board -- not light, a BODY: the citrine of
    the old palette, standing over the impact with the alien hidden
    inside it until the dissolve gives it up. Sized so the WHOLE figure
    sits inside its inradius cone (asserted in main): while the object
    is opaque it writes depth, and the body drawn after it fails that
    test everywhere -- the first cut left it OBJ_BLEND for its whole
    stand, and a blended face writes no depth, so the later-drawn body
    painted straight over the veil and stood in plain sight."""
    tw = CITRINE | (16 << 24)
    a = TET_A
    base = [(-a, -0.05, -a * 0.577), (a, -0.05, -a * 0.577),
            (0, -0.05, a * 1.155)]
    verts = [0, int(TET_APEX * ONE), 0]
    for x, y, z in base:
        verts += [int(x * ONE), int(y * ONE), int(z * ONE)]
    return Mesh(verts,
                [(0, 2, 1, tw), (0, 3, 2, tw), (0, 1, 3, tw),
                 (1, 2, 3, tw)])


def splash():
    """THE LIGHT ON THE SURROUNDINGS: a wide additive sheet lying just
    off the board around the impact, so the landing illuminates the
    world for a beat -- light as an event, not a state."""
    sw = 0xD8E4FF | (9 << 24) | (spec.BLEND_ADD << 29)
    s = 2.6
    verts = []
    for px, pz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        verts += [int(px * s * ONE), int(0.02 * ONE), int(pz * s * ONE)]
    return Mesh(verts, [(0, 2, 1, sw), (0, 3, 2, sw)])


def a_tri():
    """The logo's A: the machine's triangle, solid ink, spinning at the
    fourth letter cell forever."""
    return Mesh([0, int(0.625 * ONE), 0,
                 int(-0.545 * ONE), int(-0.625 * ONE), 0,
                 int(0.545 * ONE), int(-0.625 * ONE), 0],
                [(0, 1, 2, INK), (0, 2, 1, INK)])


def ground():
    """DENSER: 15 x 15 tiles of one unit, which is the law's ceiling --
    (n+1)^2 = 256 vertices exactly, 450 of 512 faces.

    THE STAGE LIGHT IS BAKED INTO THE NORMALS. The fog is a plane of
    view depth, not a circle -- iso-fog contours are parallel to the
    glass, and no tuning of NEAR and SHIFT makes a pool. But a lit
    vertex's level is amb + dif * (N.L >> 14), and NOTHING requires N
    to be unit: scale each board normal by its distance from the impact
    and the law itself draws a CIRCLE of light around the site, glued
    to the world, not the camera. Full light within r=1.1, dark past
    r=3.7; the fog then owns only the far edge and the horizon."""
    n, tile = 15, 1
    verts, faces, cols = [], [], []
    h = n / 2.0
    for j in range(n + 1):
        for i in range(n + 1):
            verts += [int((i - h) * ONE * tile), 0,
                      int((j - h) * ONE * tile)]
            r = math.hypot(i - h, (j - h) - 1.2)
            cols.append(pack_n(0, max(0.0, min(1.0, 1.0 - (r - 1.1) / 2.6)),
                               0))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            b, c, d = a + 1, a + 2 + n, a + 1 + n
            col = WHITE if (i + j) % 2 else GREEN
            faces += [(a, d, c, col), (a, c, b, col)]
    return Mesh(verts, faces, colors=cols)


def bell_page():
    smp = []
    for i in range(spec.WAV_W):
        t = i / spec.WAV_W
        v = (math.sin(2 * math.pi * t) * 0.62
             + math.sin(4 * math.pi * t) * 0.26
             + math.sin(6 * math.pi * t) * 0.12)
        smp.append(max(-127, min(127, int(round(v * 120)))) & 0xFF)
    return [smp[i] | (smp[i + 1] << 8) | (smp[i + 2] << 16)
            | (smp[i + 3] << 24) for i in range(0, spec.WAV_W, 4)]


# ---- ZETA: Z, Xi, T in ink; the A is a body ---------------------------
GLYPHS = [
    [((0, 0), (14, 0), (14, 2), (0, 2)),
     ((12, 2), (14, 2), (2, 14), (0, 14)),
     ((0, 14), (14, 14), (14, 16), (0, 16))],
    [((0, 0), (14, 0), (14, 2), (0, 2)),
     ((0, 7), (14, 7), (14, 9), (0, 9)),
     ((0, 14), (14, 14), (14, 16), (0, 16))],
    [((0, 0), (14, 0), (14, 2), (0, 2)),
     ((6, 2), (8, 2), (8, 16), (6, 16)),
     ((6, 2), (8, 2), (8, 9), (6, 9))],
]

NOTES = [432.0, 540.0, 648.0, 864.0]


def main():
    cart = Cart("face")
    plates = [cart.cram(sky(), "sky0"),
              cart.cram(sky(shift=0.16, twins=True, dim=1), "sky1"),
              cart.cram(sky(shift=0.34, twins=False, dim=2), "sky2"),
              cart.cram(sky(shift=0.52, twins=False, dim=3), "sky3")]
    m_ground = cart.data(ground(), "ground")
    m_drop = cart.data(drop(), "drop")
    m_flare = cart.data(flare(), "flare")
    m_tet = cart.data(tetra(), "tetra")
    m_spl = cart.data(splash(), "splash")
    m_atri = cart.data(a_tri(), "a_tri")
    m_body, m_arml, m_armr, pivL, pivR = _grey_parts()
    # THE CONE TEST: every body vertex inside the tetra's inradius at
    # its height, the worst case over every spin angle. If this fires,
    # the head or a heel would poke through the standing tetra.
    worst = 0.0
    for vi in range(0, len(m_body.verts), 3):
        vx, vy, vz = (m_body.verts[vi + k2] / ONE for k2 in range(3))
        need = math.hypot(vx, vz) / max(1e-6, 0.577 * TET_A
                                        * (1 - vy / TET_APEX))
        worst = max(worst, need)
    assert worst <= 1.0, f"tetra too small: scale TET_A by {worst:.3f}"
    m_body = cart.data(m_body, "body")
    m_arml = cart.data(m_arml, "armL")
    m_armr = cart.data(m_armr, "armR")
    bell = cart.data(Table(bell_page()), "bell")

    ease = lambda u: u * u * (3 - 2 * u)

    def tt(f, a, b):
        return max(0.0, min(1.0, (f - a) / float(b - a)))

    # ---- THE SPECIAL PAN --------------------------------------------
    # The camera BEGINS AT THE IMPACT SITE, close to the board, the sky
    # over it; as the tear commits to its fall the camera slides out and
    # back to the vantage, arriving as the tear strikes the spot it
    # left. The retreat eases; the TEAR accelerates; the two cross.
    # AND IT TRACKS: real CAM_PITCH aimed at the tear, eased in after
    # the flash-in (the blink weld needs pitch zero) and eased back to
    # level before the strike, so the pan lands exactly on the vantage
    # framing. The pitch is up at the star first, then sweeps down and
    # a hair PAST level as the tear plunges under the eye-line.
    def drop_at(f):
        d = tt(f, T_FALL, T_LAND) ** 2
        return 2.05 * (1 - d) + 0.42 * d, 5.2 * (1 - d) + 1.2 * d
    cam_y, cam_z, cam_x, cam_w, cam_p = [], [], [], [], []
    for i2 in range(CAM_N):
        f = CAM_T0 + i2
        u = ease(tt(f, T_FALL, T_LAND - 6))
        cy = 0.42 * (1 - u) + 1.05 * u
        cz = -0.45 * (1 - u) + -3.4 * u
        cx = 0.55 * math.sin(math.pi * u)          # a bow, not a slide
        dy, dz = drop_at(f)
        raw = math.atan2(dy - cy, dz - cz) / math.tau * 1024
        raw = max(-60.0, min(60.0, raw))
        gain = ease(tt(f, T_FALL + 2, T_FALL + 26)) \
            * (1 - ease(tt(f, T_LAND - 40, T_LAND - 6)))
        pit = round(raw * gain)
        # THE WHIP: square and tight -- dead-centre, close enough that
        # the head and shoulders own the frame
        v = ease(tt(f, T_PAN, T_PAN + 18))
        cy = cy * (1 - v) + 1.22 * v
        cz = cz * (1 - v) + 0.50 * v
        cx = cx * (1 - v)
        if f >= T_WHITE:
            cx, cy, cz = 0.0, 1.10, -1.70
        yaw = round(-math.atan2(cx - 0.0, 1.2 - cz)
                    / math.tau * 1024) % 1024 if abs(cx) > 1e-4 else 0
        cam_y.append(int(cy * ONE))
        cam_z.append(int(cz * ONE))
        cam_x.append(int(cx * ONE))
        cam_w.append(yaw)
        cam_p.append(pit & 1023)
    # the tear: hangs at the star, then falls with ACCELERATION into
    # the strike -- and its riser is the same number, inverted
    drop_y, drop_z, riser = [], [], []
    for i2 in range(DRP_N):
        f = DRP_T0 + i2
        # spawned WHERE THE STAR IS SEEN: the first cut used the old
        # high-camera heavens (y 6.4), which from the ground-level
        # opening projects 125 pixels above the frame -- the ding rang
        # on an empty sky and the tear only entered mid-fall.
        dy, dz = drop_at(f)
        drop_y.append(int(dy * ONE))
        drop_z.append(int(dz * ONE))
        riser.append(hz(170.0 + (2.05 - dy) * 480.0))
    aXl, aZl, aXr, aZr, aAl, aAr = [], [], [], [], [], []
    for i2 in range(ARM_N):
        f = ARM_T0 + i2
        yaw = min(512, max(0, (f - T_TURN) * 26))   # the whip: violent
        pxl, pzl = _rot(int(pivL[0] * ONE), int(pivL[2] * ONE), yaw)
        pxr, pzr = _rot(int(pivR[0] * ONE), int(pivR[2] * ONE), yaw)
        aXl.append(spec.s32(pxl) & spec.WORD_MASK)
        aZl.append(spec.s32(pzl + int(1.2 * ONE)) & spec.WORD_MASK)
        aXr.append(spec.s32(pxr) & spec.WORD_MASK)
        aZr.append(spec.s32(pzr + int(1.2 * ONE)) & spec.WORD_MASK)
        rl = int(150 * ease(tt(f, T_TURN + 2, T_PAN + 12)))
        rr = int(135 * ease(tt(f, T_TURN + 5, T_PAN + 15)))
        ol_ = int(80 * ease(tt(f, T_TURN + 2, T_PAN + 12)))
        or_ = int(72 * ease(tt(f, T_TURN + 5, T_PAN + 15)))
        aAl.append(yaw | (((-rl) & 1023) << 10) | ((ol_ & 1023) << 20))
        aAr.append(yaw | (((-rr) & 1023) << 10) | (((-or_) & 1023) << 20))
    tspin = []
    for i2 in range(TSP_N):
        u = i2 / (TSP_N - 1)
        tspin.append(int(2.5 * 1024 * (1 - (1 - u) ** 2)) % 1024)
    tspin[-1] = 0                       # at rest before the dissolve
    aspin = []
    for i2 in range(ASP_N):
        u = i2 / (ASP_N - 1)
        aspin.append(int(2 * 1024 * (1 - (1 - u) ** 2)) % 1024)
    aspin[-1] = 0
    t_cy = cart.data(Table(cam_y), "cam_y")
    t_cz = cart.data(Table(cam_z), "cam_z")
    t_cx = cart.data(Table(cam_x), "cam_x")
    t_cw = cart.data(Table(cam_w), "cam_yaw")
    t_cp = cart.data(Table(cam_p), "cam_pit")
    t_dy = cart.data(Table(drop_y), "drop_y")
    t_dz = cart.data(Table(drop_z), "drop_z")
    t_ri = cart.data(Table(riser), "riser")
    t_axl = cart.data(Table(aXl), "arm_xl")
    t_azl = cart.data(Table(aZl), "arm_zl")
    t_axr = cart.data(Table(aXr), "arm_xr")
    t_azr = cart.data(Table(aZr), "arm_zr")
    t_aal = cart.data(Table(aAl), "arm_al")
    t_aar = cart.data(Table(aAr), "arm_ar")
    t_tsp = cart.data(Table(tspin), "t_spin")
    t_asp = cart.data(Table(aspin), "a_spin")
    t_thr = cart.data(Table([0x0A0A0C, 0x0A0A0C] + [0xFFFFFF] * 30),
                      "thresh")
    IDENT = [(i2 << 3) | (i2 >> 2) for i2 in range(spec.GRADE_WORDS)]

    grade = cart.var("grade", spec.GRADE_WORDS)
    fr = cart.var("fr")
    tmp = cart.var("tmp")
    tmp2 = cart.var("tmp2")
    tw_c = cart.var("tw")
    rd_c = cart.var("rd")

    # the shelf rides in the film's segment, AFTER every plate, so no
    # offset the film already uses moves
    SH_P, SH_D, SH_S = cart.shelve(LAUNCH)
    assert SH_D - SH_S > 0 and SH_P - SH_S > 0   # pre-compensated offsets
                                                 # must stay presentable
    p = cart.program()

    # ---- the handoff: from T_LAUNCH the film is only a launcher --------
    film_l, fdone_l = p.label("film"), p.label("fdone")
    p.push(T_LAUNCH - 1).load(spec.REG_FRAME).emit("lt", f"jz {film_l}")
    # step k = REG_FRAME - T_LAUNCH + 1 ; dst = 16384 - 4096k
    p.push(16384).load(spec.REG_FRAME).push(T_LAUNCH - 1).emit("sub")
    p.push(4096).emit("mul", "sub")
    p.emit("dup").store(spec.DMA_DST)
    p.push(int(SH_D)).emit("add").store(spec.DMA_SRC)
    p.push(spec.DMA_MAX).store(spec.DMA_LEN)
    p.set(spec.DMA_GO, 1)
    p.load(spec.REG_FRAME).push(T_LAUNCH + 3).emit("eq", f"jz {fdone_l}")
    # the final step: the shelf's window is armed during this run, so
    # this frame's own movers present PRE-COMPENSATED offsets (dst is 0)
    p.push(int(SH_D) - SH_S).store(spec.DMA_SRC)
    p.push(int(SH_P) - SH_S).store(spec.OVL_SRC)
    p.set(spec.OVL_DST, 0)
    p.push(spec.OVL_MAX).store(spec.OVL_LEN)
    p.set(spec.OVL_GO, 1)
    p.push(SH_S).store(spec.SEG_BASE)
    p.set(spec.AU_RESET, 1)              # the shelf's synth starts cold
    p.mark(fdone_l)
    p.emit("halt")
    p.mark(film_l)

    def cap_hi(cell, x):
        q = p.label("chi")
        p.push(x).load(cell).emit("lt", f"jz {q}")
        p.push(x).store(cell)
        p.mark(q)

    def cap_lo(cell, x):
        q = p.label("clo")
        p.load(cell).push(x).emit("lt", f"jz {q}")
        p.push(x).store(cell)
        p.mark(q)

    p.load(spec.REG_FRAME).store(fr)
    cap_hi(fr, T_END)

    def after(T, label):
        p.push(T - 1).load(fr).emit("lt", f"jz {label}")

    def before(T, label):
        p.load(fr).push(T).emit("lt", f"jz {label}")

    def seg(sym, T0, N):
        p.load(fr).push(T0).emit("sub").store(tmp2)
        cap_lo(tmp2, 0)
        cap_hi(tmp2, N - 1)
        p.load(tmp2).push(int(sym)).emit("add", "loadi")

    # ---- THE GRADE: fade-in; impact spike; RED bleeding to white -----
    gs = p.label("grade_static")
    gd = p.label("grade_done")
    after(T_ZETA - 6, gs)
    p.set(spec.GRADE_SRC, int(t_thr))
    p.emit(f"jmp {gd}")
    p.mark(gs)
    # HELD AT PURE BLACK for the first eight frames, then the ramp:
    # (fr - 8) * 5 >> 4 tops out at frame 111, TWO SECONDS to the
    # blink, per the board. Two prior versions of this line each failed
    # a different gate: (fr - 4) >> 1 shifts a NEGATIVE for the opening
    # frames -- logical shift, huge, clamped to FULL BRIGHT: the show
    # opened on four lit frames. Plain fr >> 1 opened black but CHANGED
    # every other frame from frame zero, and the glass scan straddles a
    # fade step and matches neither side. The clamp must come BEFORE
    # the multiply, and the hold gives the scan a static frame.
    p.load(fr).push(8).emit("sub").store(tmp)
    cap_lo(tmp, 0)
    p.load(tmp).push(5).emit("mul").emit("shr 4").store(tmp)
    cap_hi(tmp, 32)
    # the impact spike: full white at the strike, one step a frame off
    # two steps a frame: at one, the posterized mid-greys of the wash
    # sit on the panel for half a second and read as BANDS. The grade
    # has 32 rungs and nothing below them; the only cure is to spend
    # less time on the ladder.
    p.push(16 + T_LAND).load(fr).emit("sub").push(2).emit("mul").store(tw_c)
    cap_lo(tw_c, 0)
    cap_hi(tw_c, 32)
    lbl = p.label("nospike"); before(T_LAND, lbl)
    p.push(0).store(tw_c)
    p.mark(lbl)
    # the final wash rises AFTER the red has struck
    p.load(fr).push(T_FLASH + 8).emit("sub").push(2).emit("mul").store(tmp2)
    cap_lo(tmp2, 0)
    cap_hi(tmp2, 32)
    q = p.label("twmax")
    p.load(tw_c).load(tmp2).emit("lt", f"jz {q}")
    p.load(tmp2).store(tw_c)
    p.mark(q)
    # THE RED: a hard flash at T_FLASH that drains as the white rises --
    # rd scales how far the green and blue channels are HELD DOWN, so
    # the frame goes blood-first and bleeds to white as rd dies
    p.push(32 + T_FLASH).load(fr).emit("sub").store(rd_c)
    cap_lo(rd_c, 0)
    cap_hi(rd_c, 32)
    lbl = p.label("nored"); before(T_FLASH, lbl)
    p.push(0).store(rd_c)
    p.mark(lbl)
    # gb_tint = 255 - 7*rd  (32 -> 31: the flash floor)
    p.load(rd_c).push(7).emit("mul").store(tmp2)
    cap_hi(tmp2, 224)
    p.push(255).load(tmp2).emit("sub").store(rd_c)
    for i2, ident in enumerate(IDENT):
        p.load(tmp).push(ident).emit("mul").emit("shr 5").store(int(grade) + i2)
        p.push(255).load(int(grade) + i2).emit("sub")
        p.load(tw_c).emit("mul").emit("shr 5")
        p.load(int(grade) + i2).emit("add").store(int(grade) + i2)
        # entry = R<<16 | (M*gb>>8)<<8 | (M*gb>>8)
        p.load(int(grade) + i2).load(rd_c).emit("mul").emit("shr 8").store(tmp2)
        p.load(int(grade) + i2).emit("shl 16")
        p.load(tmp2).emit("shl 8").emit("or")
        p.load(tmp2).emit("or").store(int(grade) + i2)
    p.set(spec.GRADE_SRC, int(grade))
    p.mark(gd)

    # ---- the skybox: four plates stepping away during the pan --------
    p.set(spec.BG_SRC, int(plates[0]))
    for k2, T in ((1, T_FALL + 16), (2, T_FALL + 38), (3, T_FALL + 60)):
        lbl = p.label(f"skb{k2}"); after(T, lbl)
        p.set(spec.BG_SRC, int(plates[k2]))
        p.mark(lbl)
    lbl = p.label("sky_gone"); after(T_FALL + 82, lbl)
    p.set(spec.BG_SRC, 0)
    p.mark(lbl)

    # ---- the camera ---------------------------------------------------
    seg(t_cy, CAM_T0, CAM_N); p.store(spec.CAM_Y)
    seg(t_cz, CAM_T0, CAM_N); p.store(spec.CAM_Z)
    seg(t_cx, CAM_T0, CAM_N); p.store(spec.CAM_X)
    seg(t_cw, CAM_T0, CAM_N); p.store(spec.CAM_YAW)
    seg(t_cp, CAM_T0, CAM_N); p.store(spec.CAM_PITCH)
    p.load(fr).push(T_PAN).emit("sub").store(tmp)
    cap_lo(tmp, 0)
    cap_hi(tmp, 13)
    lbl = p.label("roll_home"); after(T_PAN + 26, lbl)
    p.push(0).store(tmp)
    p.mark(lbl)
    p.load(tmp).store(spec.CAM_ROLL)

    # ---- eight slots ---------------------------------------------------
    # DRAW ORDER IS SLOT ORDER, and the tetra must come AFTER the body:
    # opaque, drawn later, it depth-tests NEARER and paints over the
    # figure (hidden); dissolving, blended, drawn later, it composites
    # OVER the figure already in the frame (revealed by degrees). In
    # the tetra's old slot ahead of the body, the blended veil went
    # down first and the body painted straight over it.
    G, D, BD, AL, AR, TR, FL, SP = (spec.OL_BASE + 1 + k2 * spec.OL_STRIDE
                                    for k2 in range(8))
    p.set(spec.OL_BASE, 8)
    for b in (G, D, TR, BD, AL, AR, FL, SP):
        p.set(b, 0)
        p.set(b + 1, 0); p.set(b + 2, 0); p.set(b + 3, 0)
        p.set(b + 4, 0); p.set(b + 5, spec.OBJ_CULL)

    world = p.label("no_world")
    before(T_WHITE, world)

    # the board is LIT now -- its vertex words are the pool's scaled
    # normals, so with the light down it is NOT THERE: a black horizon
    # under the stars until the tear gets low and the stage wakes
    p.set(G, int(m_ground))
    p.set(G + 5, spec.OBJ_CULL | spec.OBJ_LIT)

    # the tear: flashes in at the star, then falls at the camera's spot
    lbl = p.label("nodrop")
    after(T_TEAR, lbl)
    before(T_LAND, lbl)
    p.set(D, int(m_drop))
    seg(t_dy, DRP_T0, DRP_N); p.store(D + 2)
    seg(t_dz, DRP_T0, DRP_N); p.store(D + 3)
    p.set(D + 5, spec.OBJ_CULL | spec.OBJ_BLEND)
    p.load(fr).push(T_TEAR + 6).emit("lt").push(4).emit("mul")
    p.push(11).emit("add").store(tmp)
    p.load(tmp).emit("shl 24")
    p.push(spec.BLEND_ADD).emit(f"shl {spec.BLEND_MODE_SHIFT}").emit("or")
    # push32, NOT push: SILVER has bit 23 set, and a bare push immediate
    # is 24-BIT SIGNED -- the machine sign-extends it and the OR paints
    # 0xFF over the alpha and mode bits. Every frame of the first cut
    # ran with this word's top byte solid ones.
    p.push32(SILVER).emit("or").store(tmp)
    fb0 = int(m_drop) + 2 + 15 * 3
    for fi in range(DROP_BODY_NF):
        p.load(tmp).store(fb0 + fi * 2 + 1)
    p.mark(lbl)

    # the glint at the primary, until the tear owns the frame
    lbl = p.label("noflare")
    after(T_TEAR - 34, lbl)
    before(T_TEAR + 12, lbl)
    p.set(FL, int(m_flare))
    p.set(FL + 2, int(2.05 * ONE))
    p.set(FL + 3, int(5.2 * ONE))
    p.set(FL + 5, spec.OBJ_CULL | spec.OBJ_BLEND)
    p.mark(lbl)

    # THE TETRAHEDRON: solid yellow, spinning down, then DISSOLVING
    lbl = p.label("notet")
    after(T_LAND, lbl)
    before(T_DISS + DIS_N, lbl)
    p.set(TR, int(m_tet))
    p.set(TR + 3, int(1.2 * ONE))
    # OPAQUE while it stands -- writing depth is what KEEPS the alien;
    # blended only once the dissolve begins and the veil must composite
    p.set(TR + 5, spec.OBJ_CULL)
    lbl2 = p.label("tet_solid")
    after(T_DISS, lbl2)
    p.set(TR + 5, spec.OBJ_CULL | spec.OBJ_BLEND)
    p.mark(lbl2)
    seg(t_tsp, T_LAND, TSP_N)
    p.store(TR + 4)
    # alpha: opaque 16 while it spins; then a step down every three
    # frames -- the dissolve that gives the alien up
    p.load(fr).push(T_DISS).emit("sub").store(tmp)
    cap_lo(tmp, 0)
    p.load(tmp).emit("shr 2").store(tmp)
    p.push(16).load(tmp).emit("sub").store(tmp)
    cap_lo(tmp, 0)
    # push32: CITRINE also carries bit 23 -- see the drop writer above
    p.load(tmp).emit("shl 24").push32(CITRINE).emit("or").store(tmp)
    tfb = int(m_tet) + 2 + 4 * 3
    for fi in range(4):
        p.load(tmp).store(tfb + fi * 2 + 1)
    # the light it throws on the tiles, while it stands
    # (one handle a label -- p.label() MINTS a fresh name every call,
    # so jmp p.label(x) ... mark p.label(x) are two different places)
    lbl2 = p.label("nospl")
    spd = p.label("spl_done")
    after(T_DISS, lbl2)
    p.set(SP, 0)
    p.emit(f"jmp {spd}")
    p.mark(lbl2)
    p.set(SP, int(m_spl))
    p.set(SP + 3, int(1.2 * ONE))
    p.set(SP + 5, spec.OBJ_CULL | spec.OBJ_BLEND)
    p.mark(spd)
    p.mark(lbl)

    # THE GREY: inside the tetrahedron from the strike, kept by it
    # until the dissolve; back to the camera; then the whip
    lbl = p.label("nogrey"); after(T_LAND, lbl)
    p.set(BD, int(m_body))
    p.set(BD + 3, int(1.2 * ONE))
    p.set(BD + 5, spec.OBJ_CULL | spec.OBJ_LIT)
    p.load(fr).push(T_TURN).emit("sub").store(tmp)
    cap_lo(tmp, 0)
    p.load(tmp).push(26).emit("mul").store(tmp)
    cap_hi(tmp, 512)
    p.load(tmp).store(BD + 4)
    for slot, tx, tz, ta in ((AL, t_axl, t_azl, t_aal),
                             (AR, t_axr, t_azr, t_aar)):
        p.set(slot, int(m_arml) if slot == AL else int(m_armr))
        seg(tx, ARM_T0, ARM_N); p.store(slot + 1)
        p.set(slot + 2, int(pivL[1] * ONE))
        seg(tz, ARM_T0, ARM_N); p.store(slot + 3)
        seg(ta, ARM_T0, ARM_N); p.store(slot + 4)
        p.set(slot + 5, spec.OBJ_CULL | spec.OBJ_LIT)
    p.mark(lbl)

    p.mark(world)

    # ---- the light and the fog ---------------------------------------
    # THE KEY IS OVERHEAD NOW -- a beam down onto the site, which is
    # what a stage light is: the pool normals catch nearly all of it
    # (N.L 0.87 at full scale), the figure is crowned from above and
    # kept moody in the face, and its back is a rim-lit silhouette for
    # the reveal. And it RAMPS: dark through the whole fall, waking
    # over the last three-quarters of a second as the tear gets low --
    # no board until near the impact, then a circle of light waiting
    # for the strike. amb rides dif at a sixteenth, so the ramp is one
    # number.
    p.set(spec.LIGHT_DIR, (28 << 16) | (112 << 8) | (45 & 0xFF))
    p.load(fr).push(T_LAND - 44).emit("sub").push(3).emit("mul").store(tmp)
    cap_lo(tmp, 0)
    p.load(tmp).emit("shr 2").store(tmp)
    cap_hi(tmp, 32)
    p.load(tmp).store(spec.LIGHT_DIF)
    p.load(tmp).emit("shr 4").store(spec.LIGHT_AMB)
    # the fog CLOSES the world: nothing past it. From the vantage the
    # subject sits at 4.6 units (z16 2355), inside the clear zone; the
    # board's far reaches drown by 8 units. The circle itself is the
    # normals' work above -- fog is planes of DEPTH, and only the pool
    # can be round.
    p.set(spec.FOG_RGB, 0x02030A)
    p.set(spec.FOG_NEAR, 3100)
    p.set(spec.FOG_SHIFT, 6)

    # ---- ZETA ---------------------------------------------------------
    p.set(spec.DL_BASE, 0)
    zt = p.label("nozeta"); after(T_ZETA, zt)
    # letter count by COMPARISON, not shift: the 12-frame step is not a
    # power of two and this ISA has no divide
    p.push(1)
    p.push(T_ZETA + T_STEP - 1).load(fr).emit("lt").emit("add")
    p.push(T_ZETA + 2 * T_STEP - 1).load(fr).emit("lt").emit("add")
    p.store(tmp)
    p.load(tmp).push(6).emit("mul").store(spec.DL_BASE)
    at = spec.DL_BASE + 1
    for gi, strokes in enumerate(GLYPHS):
        ox = 77 + gi * 46
        for corners in strokes:
            c = [(ox + x * 2, 128 + y * 2) for (x, y) in corners]
            for tri in ((c[0], c[1], c[2]), (c[0], c[2], c[3])):
                for k2, (vx, vy) in enumerate(tri):
                    p.set(at + 2 * k2, vx)
                    p.set(at + 2 * k2 + 1, vy)
                p.set(at + 6, INK)
                at += spec.DL_STRIDE
    p.mark(zt)

    av = p.label("no_atri")
    after(T_ZETA + 3 * T_STEP, av)
    p.set(TR, int(m_atri))
    p.set(TR + 1, int(2.715 * ONE))
    p.set(TR + 2, int(1.10 * ONE))
    p.set(TR + 3, int(8.30 * ONE))
    p.set(TR + 5, spec.OBJ_CULL)
    seg(t_asp, T_ZETA + 3 * T_STEP, ASP_N)
    p.store(TR + 4)
    p.mark(av)

    # ================= THE SCORE: the visitor's ==========================
    A = spec.AU_BASE

    def voice(ch, inc_ops, vol, duty=0, wave=False):
        if callable(inc_ops):
            inc_ops()
        else:
            p.push(inc_ops)
        p.store(A + 2 * ch)
        p.set(A + 2 * ch + 1, (vol & 15) | (duty << 4)
              | (spec.AU_WAVE if wave else 0))

    for ch in range(4):
        p.set(A + 2 * ch + 1, 0)
    p.set(spec.WAV_SRC, int(bell))

    # [1s] SILENCE while the sky resolves -- then the DING: one struck
    # bell, high and pure, as the tear appears
    s0 = p.label("s_ding")
    after(T_TEAR, s0)
    before(T_TEAR + 40, s0)
    p.set(A + 6, hz(1728.0))
    p.push(T_TEAR + 40).load(fr).emit("sub").emit("shr 2").store(tmp)
    cap_hi(tmp, 10)
    p.load(tmp).push(spec.AU_WAVE).emit("or").store(A + 7)
    p.mark(s0)

    # [2s] THE RISER: two voices a hair apart climbing with the fall --
    # the beat between them quickens as they rise -- over a sub that
    # sinks. Everything converges on the strike.
    s1 = p.label("s_riser")
    after(T_FALL, s1)
    before(T_LAND, s1)
    seg(t_ri, DRP_T0, DRP_N); p.store(A + 0)
    seg(t_ri, DRP_T0, DRP_N)
    p.store(tmp)
    p.load(tmp).emit("shr 6").load(tmp).emit("add").store(A + 2)
    p.load(fr).push(T_FALL).emit("sub").emit("shr 4").push(3).emit("add").store(tmp)
    cap_hi(tmp, 9)
    p.load(tmp).push(2 << 4).emit("or").store(A + 1)
    p.load(tmp).push(1).emit("sub").push(1 << 4).emit("or").store(A + 3)
    p.push(hz(85.0)).load(fr).push(T_FALL).emit("sub").push(170).emit("mul")
    p.emit("sub").store(A + 4)
    p.set(A + 5, 5)
    p.mark(s1)

    # the STRIKE: riser silenced dead, one thump
    s2 = p.label("s_strike")
    after(T_LAND, s2)
    before(T_ZETA, s2)
    p.set(A + 1, 0)
    p.set(A + 3, 0)
    p.set(A + 5, 0)
    p.mark(s2)
    s2b = p.label("s_thump")
    after(T_LAND, s2b)
    before(T_LAND + 22, s2b)
    p.set(A + 6, hz(70.0))
    p.push(T_LAND + 22).load(fr).emit("sub").emit("shr 1").store(tmp)
    p.load(tmp).store(A + 7)
    p.mark(s2b)

    # [3-5s] THE PRESENCE: a low toll off the strike, then a thin high
    # wire and a breathing sub -- the room is not empty any more
    s3 = p.label("s_toll")
    after(T_LAND + 24, s3)
    before(T_DISS + 20, s3)
    p.set(A + 6, hz(216.0))
    p.push(T_DISS + 20).load(fr).emit("sub").emit("shr 3").store(tmp)
    cap_hi(tmp, 8)
    p.load(tmp).push(spec.AU_WAVE).emit("or").store(A + 7)
    p.mark(s3)
    s4 = p.label("s_wire")
    after(T_DISS, s4)
    before(T_FLASH, s4)
    voice(1, hz(1296.0), 2, duty=1)
    p.load(fr).emit("shr 3").push(1).emit("and").push(2).emit("add").store(tmp)
    p.load(tmp).store(A + 5)
    p.push(hz(54.0)).store(A + 4)
    p.mark(s4)

    # [5-6s] THE WHIP: a rushing rise of noise, cut dead on the portrait
    s5 = p.label("s_whip")
    after(T_TURN, s5)
    before(T_PAN + 20, s5)
    p.set(A + 6, hz(400.0))
    p.load(fr).push(T_TURN).emit("sub").emit("shr 1").store(tmp)
    cap_hi(tmp, 11)
    p.load(tmp).store(A + 7)
    p.mark(s5)
    s5b = p.label("s_hold")
    after(T_PAN + 20, s5b)
    before(T_FLASH, s5b)
    for ch in range(4):
        p.set(A + 2 * ch + 1, 0)
    p.mark(s5b)

    # [6s] THE RED: one dissonant metal hit as the frame goes blood
    s6 = p.label("s_red")
    after(T_FLASH, s6)
    before(T_FLASH + 30, s6)
    p.set(A + 6, hz(610.0))
    p.push(T_FLASH + 30).load(fr).emit("sub").emit("shr 1").store(tmp)
    cap_hi(tmp, 12)
    p.load(tmp).push(spec.AU_WAVE).emit("or").store(A + 7)
    p.mark(s6)
    s6b = p.label("s_gap")
    after(T_FLASH + 30, s6b)
    before(T_ZETA, s6b)
    for ch in range(4):
        p.set(A + 2 * ch + 1, 0)
    p.mark(s6b)

    # [the name] the chord assembles, and the sound ends with the show
    BASES = ((5, 0, False), (4, 1, False), (4, 0, False), (7, 0, True))
    for gi, f0 in enumerate(NOTES):
        sg = p.label(f"s_g{gi}")
        after(T_ZETA + gi * T_STEP, sg)
        vol, duty, wave = BASES[gi]
        p.push(hz(f0)).store(A + 2 * gi)
        p.push(T_END).load(fr).emit("sub").emit("shr 3").store(tmp)
        cap_hi(tmp, vol)
        p.load(tmp)
        extra = (duty << 4) | (spec.AU_WAVE if wave else 0)
        if extra:
            p.push(extra).emit("or")
        p.store(A + 2 * gi + 1)
        p.mark(sg)

    p.emit("halt")
    print(cart.report())
    cart.write(OUT)


if __name__ == "__main__":
    main()
