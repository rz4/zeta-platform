"""light.py -- a mock of LIGHT A PIXEL (docs/ZETA-RECIPROCAL-DESIGN.md, 4.1).

NOT LAW. The room cart's plate already carries a colour and a depth for
every pixel. This file asks what a third thing a pixel -- one byte
naming its NORMAL -- would buy, using only arithmetic the machine could
do: a table lookup and the commit pipeline's tint.

    normal byte  --->  LIGHT TABLE[256]  --->  a tint (5 bits a channel,
                                               16 = unchanged, 31 = 1.94x)
    shown = min(31, (plate colour * tint) >> 4)      a channel

The table is the only thing that knows where the lamps are, and the
program rewrites it; the plate never changes.

The normals here are NOT baked. They are recovered from the plate's own
depth plane, which is the worst case: a baker has the true normal in
hand and would simply write it.

    python3 experiments/light/light.py     # writes sheet.png, prints the table in README.md
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "retina"))

from zeta import cabinet, carts, gpu, spec  # noqa: E402
from retina import Tap                       # noqa: E402

HERE = Path(__file__).resolve().parent
N_SIDE = 16                      # 16 x 16 directions: one byte


# ---- one byte a normal: the octahedron, unfolded -------------------------
def encode(n):
    """unit normals (..., 3) -> a byte. The octahedral map on a 16 x 16
    grid: adds, compares and two divides at BAKE time; nothing at run time."""
    n = n / np.abs(n).sum(axis=-1, keepdims=True)
    x, y = n[..., 0], n[..., 1]
    back = n[..., 2] > 0                    # away from the camera: fold over
    fx = np.where(back, np.sign(x) * (1 - np.abs(y)), x)
    fy = np.where(back, np.sign(y) * (1 - np.abs(x)), y)
    u = np.clip(((fx + 1) / 2 * N_SIDE).astype(int), 0, N_SIDE - 1)
    v = np.clip(((fy + 1) / 2 * N_SIDE).astype(int), 0, N_SIDE - 1)
    return (v * N_SIDE + u).astype(np.uint8)


def decode_all():
    """the 256 directions a byte can name, as unit vectors."""
    k = np.arange(256)
    fx = ((k % N_SIDE) + 0.5) / N_SIDE * 2 - 1
    fy = ((k // N_SIDE) + 0.5) / N_SIDE * 2 - 1
    z = 1 - np.abs(fx) - np.abs(fy)
    back = z < 0
    x = np.where(back, np.sign(fx) * (1 - np.abs(fy)), fx)
    y = np.where(back, np.sign(fy) * (1 - np.abs(fx)), fy)
    n = np.stack([x, y, -z], axis=-1)       # -z: toward the camera is front
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


# ---- normals out of a depth plane ----------------------------------------
def normals_from_depth(z, reach=1):
    """(H, W) depth counts -> unit normals in view space and a mask of the
    pixels where one could be found. Each pixel takes, along each axis,
    whichever of its two neighbours is nearer in depth -- so a pillar's
    edge does not borrow the floor's slope."""
    H, W = z.shape
    zf = z.astype(np.float64)
    sx = np.arange(W)[None, :] - W / 2 + 0.5
    sy = H / 2 - np.arange(H)[:, None] - 0.5
    P = np.stack([sx * zf / spec.FOCAL, sy * zf / spec.FOCAL, zf], axis=-1)

    def step(axis):
        fwd = np.roll(P, -reach, axis=axis) - P
        bwd = P - np.roll(P, reach, axis=axis)
        use_f = np.abs(fwd[..., 2]) <= np.abs(bwd[..., 2])
        return np.where(use_f[..., None], fwd, bwd)

    n = np.cross(step(0), step(1))          # down the glass x across it
    ln = np.linalg.norm(n, axis=-1)
    ok = (ln > 0) & (z < spec.ZFAR)
    ok[:reach, :] = ok[-reach:, :] = ok[:, :reach] = ok[:, -reach:] = False
    n = n / np.where(ln > 0, ln, 1)[..., None]
    # FACE THE CAMERA -- judged against the ray to the pixel, not against
    # the depth axis. A floor's normal has no depth component at all, so
    # the sign of n.z is noise and the first draft of this line flipped
    # the floor between up and down in stripes.
    n = np.where(((n * P).sum(-1) > 0)[..., None], -n, n)
    return n, ok


# ---- the table -----------------------------------------------------------
def table(lamps, ambient):
    """256 tints, 5 bits a channel, 16 = the plate's own colour.
    lamps: [(direction TO the lamp, (r, g, b) strength)]"""
    N = decode_all()
    t = np.tile(np.asarray(ambient, float), (256, 1))
    for d, col in lamps:
        d = np.asarray(d, float)
        d = d / np.linalg.norm(d)
        t += np.clip(N @ d, 0, None)[:, None] * np.asarray(col, float)
    return np.clip(np.round(t * 16), 0, 31).astype(np.int64)


def relight(fb, nb, ok, tab):
    c5 = fb.astype(np.int64) >> 3
    out = np.minimum(31, (c5 * tab[nb]) >> 4)
    out = np.where(ok[..., None], out, c5)
    return ((out << 3) | (out >> 2)).astype(np.uint8)


# ---- the body, lit at the load from the SAME table ------------------------
BODY_ALBEDO = (176, 164, 152)       # the bunny unlit: its bake tint, less the bake


def body_normals(dmem, mb):
    """Unit normals a vertex, in the MESH's own space, from its faces."""
    nv, nf = dmem[mb], dmem[mb + 1]
    V = np.array([spec.s32(w) for w in dmem[mb + 2:mb + 2 + nv * 3]],
                 float).reshape(nv, 3)
    fbase = mb + 2 + nv * 3 + nv                 # gouraud: a colour a vertex
    N = np.zeros((nv, 3))
    for f in range(nf):
        idx = dmem[fbase + f * 2]
        a, b, c = idx & 1023, (idx >> 10) & 1023, (idx >> 20) & 1023
        fn = np.cross(V[b] - V[a], V[c] - V[a])  # area-weighted
        N[a] += fn
        N[b] += fn
        N[c] += fn
    if (N * (V - V.mean(0))).sum() < 0:          # which way the winding faces
        N = -N
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)


def light_body(dmem, mb, yaw, tab):
    """What the design calls LIGHT AT THE LOAD: turn each corner's normal
    with its body, look it up in the room's table, and leave a colour
    where the gouraud colour was. The law then draws the body exactly as
    it draws any gouraud body -- nothing downstream knows."""
    d = list(dmem)
    nv = d[mb]
    N = body_normals(d, mb)
    a = (yaw & 1023) * np.pi * 2 / 1024
    s, c = np.sin(a), np.cos(a)
    R = np.stack([N[:, 0] * c - N[:, 2] * s, N[:, 1],
                  N[:, 0] * s + N[:, 2] * c], axis=1)    # gpu._rotv's turn
    tint = tab[encode(R)]                                # (nv, 3), 16 = 1.0
    col = np.minimum(255, (np.array(BODY_ALBEDO) * tint) >> 4)
    cbase = mb + 2 + nv * 3
    for i in range(nv):
        d[cbase + i] = int(col[i, 0]) << 16 | int(col[i, 1]) << 8 | int(col[i, 2])
    return d, len(np.unique(encode(R)))


def shot(m, plate, nb, lit, tab, table_lights_body):
    """One frame of the room under one table."""
    base = spec.OL_BASE + 1
    mb, ang = m.vm.dmem[base], m.vm.dmem[base + 4]
    d = list(m.vm.dmem)
    used = 0
    if table_lights_body:
        d, used = light_body(d, mb, ang & 1023, tab)
    with Tap() as tap:
        frame = np.asarray(gpu.render(d, m._cram, m._tex))
    body = (tap.plane & 0x7F) != 0
    return np.where(body[..., None], frame, relight(plate, nb, lit & ~body, tab)), used


def save(tiles, cols, path):
    rows = [np.concatenate(tiles[i:i + cols], axis=1)
            for i in range(0, len(tiles), cols)]
    sheet = np.concatenate(rows, axis=0)
    Image.fromarray(sheet).resize((sheet.shape[1] * 2, sheet.shape[0] * 2),
                                  Image.NEAREST).save(path)


def body_sheet():
    """Top row: the body keeps the law's own light. Bottom: it takes the table's."""
    m = cabinet.VirtualMachine(cabinet.load_cart(carts.path("room")))
    for f in range(40):
        m.frame(spec.PAD_RIGHT if f < 25 else 0)
    plate, zbuf, _ = gpu.seed(m.vm.dmem, m._cram)
    plate = np.asarray(plate)
    n, ok = normals_from_depth(np.asarray(zbuf))
    nb = encode(n)
    tabs = [
        table([((-1, .6, -.5), (1.5, 1.1, .6))], (.35, .35, .5)),
        table([((1, .5, -.4), (.6, .9, 1.6))], (.4, .35, .3)),
        table([((0, -1, -.6), (1.8, .8, .3))], (.2, .2, .35)),
        table([((-1, .3, -.4), (1.4, .5, .3)), ((1, .3, -.4), (.3, .6, 1.5))],
              (.3, .3, .3)),
    ]
    top = [shot(m, plate, nb, ok, t, False)[0] for t in tabs]
    got = [shot(m, plate, nb, ok, t, True) for t in tabs]
    save(top + [g[0] for g in got], 4, HERE / "sheet_body.png")
    print(f"distinct normal bytes the body's corners use: "
          f"{max(g[1] for g in got)} of 256 (it has {m.vm.dmem[m.vm.dmem[spec.OL_BASE + 1]]} corners)")


def film():
    """The lamp circles and gutters while the bunny walks the room: 96
    frames, the table rewritten on every one, the plate never."""
    m = cabinet.VirtualMachine(cabinet.load_cart(carts.path("room")))
    plate = nb = ok = None
    frames = []
    rng = np.random.default_rng(7)                 # the gutter, repeatably
    for f in range(96):
        m.frame(spec.PAD_RIGHT if f < 48 else spec.PAD_LEFT)
        if plate is None:
            plate, zbuf, _ = gpu.seed(m.vm.dmem, m._cram)
            plate = np.asarray(plate)
            n, ok = normals_from_depth(np.asarray(zbuf))
            nb = encode(n)
        a = f / 96 * 2 * np.pi
        g = 0.85 + 0.3 * rng.random()
        tab = table([((np.cos(a), .45, -abs(np.sin(a)) - .2),
                      (1.7 * g, 1.0 * g, .45 * g))], (.22, .24, .4))
        frames.append(Image.fromarray(shot(m, plate, nb, ok, tab, True)[0]))
    frames[0].save(HERE / "film.gif", save_all=True, append_images=frames[1:],
                   duration=33, loop=0, optimize=True)


def main():
    m = cabinet.VirtualMachine(cabinet.load_cart(carts.path("room")))
    with Tap() as tap:
        for f in range(40):
            m.frame(spec.PAD_RIGHT if f < 25 else 0)
    frame = np.asarray(m.framebuffer())
    body = (tap.plane & 0x7F) != 0
    plate, zbuf, _ = gpu.seed(m.vm.dmem, m._cram)
    plate = np.asarray(plate)

    n, ok = normals_from_depth(np.asarray(zbuf))
    nb = encode(n)
    lit = ok & ~body                       # the body keeps the law's own light

    # what one byte loses
    back = decode_all()[nb]
    err = np.degrees(np.arccos(np.clip((back * n).sum(-1), -1, 1)))[ok]

    scenes = [
        ("as baked", None),
        ("a warm lamp, left", table([((-1, .6, -.5), (1.5, 1.1, .6))], (.35, .35, .5))),
        ("a cold lamp, right", table([((1, .5, -.4), (.6, .9, 1.6))], (.4, .35, .3))),
        ("from above only", table([((0, 1, -.1), (1.3, 1.3, 1.2))], (.25, .25, .3))),
        ("a fire on the floor", table([((0, -1, -.6), (1.8, .8, .3))], (.2, .2, .35))),
        ("two lamps", table([((-1, .3, -.4), (1.4, .5, .3)),
                             ((1, .3, -.4), (.3, .6, 1.5))], (.3, .3, .3))),
    ]
    tiles = []
    for name, tab in scenes:
        img = frame if tab is None else np.where(
            body[..., None], frame, relight(plate, nb, lit, tab))
        tiles.append(img)
    # the normals themselves, as colours, to see what was recovered
    vis = np.where(ok[..., None], ((back + 1) * 127.5), 0).astype(np.uint8)
    tiles.append(vis)
    # a pixel is 1 clock from the plate, +1 lookup: nothing else to show
    cols = 4
    while len(tiles) % cols:
        tiles.append(np.zeros_like(frame))
    rows = [np.concatenate(tiles[i:i + cols], axis=1)
            for i in range(0, len(tiles), cols)]
    sheet = np.concatenate(rows, axis=0)
    Image.fromarray(sheet).resize((sheet.shape[1] * 2, sheet.shape[0] * 2),
                                  Image.NEAREST).save(HERE / "sheet.png")

    print(f"plate pixels with a depth:            {int((np.asarray(zbuf) < spec.ZFAR).sum()):,} of {spec.W * spec.H:,}")
    print(f"...where a normal was recovered:      {int(ok.sum()):,}")
    print(f"distinct normal bytes the room uses:  {len(np.unique(nb[ok]))} of 256")
    print(f"error of one byte, degrees:           median {np.median(err):.1f}, 95th {np.percentile(err, 95):.1f}, worst {err.max():.1f}")
    print("tiles, left to right, top to bottom:  " + "; ".join(s[0] for s in scenes) + "; the recovered normals")


if __name__ == "__main__":
    main()
    body_sheet()
    film()
