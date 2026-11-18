#!/usr/bin/env python3
"""gen_fade.py -- writes carts/fade.zol: the scanout compositor on glass.

Roadmap 13b, and under the amended aesthetic (item 22) the most
era-defining thing on the list: fades, dimming, washes and flashes are
ATMOSPHERE, and atmosphere is the thesis.

Blending needs the destination pixel, and this machine's framebuffer is
in external CRAM behind a WRITE path -- the paint side cannot read it
back. At SCANOUT it can: the finished picture is already streaming past
a pixel per clock with its coordinates in hand. So the blend happens on
the way out and never touches CRAM at all.

The cart shows the four things the primitive buys, cycling every two
seconds over a lit tumbling cube so there is something to blend AGAINST:

    FADE      a full-screen wash to black, alpha ramping 0..16 and back
    PANEL     a dimmed rectangle -- the pause menu, the dialogue box
    FLASH     a brief white wash over everything: damage, impact
    LETTERBOX two opaque bars, top and bottom: the cutscene

Watch what cross and glass say about it, because they disagree ON
PURPOSE. cross compares painted FRAMEBUFFERS and cannot see any of this;
glass compares the SCANNED STREAM and sees all of it. That is not a hole
in the proof, it is the compositor's position in the machine, and the
gates were pointed at their own side of it before a line was written.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import spec                                    # noqa: E402
from zeta.forge import ONE, Cart, Mesh                   # noqa: E402

W, H = spec.W - 1, spec.H - 1


def cube():
    """A lit cube, so the compositor has something with form under it."""
    xs = ys = zs = (-ONE, ONE)
    verts = []
    for x, y, z in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]:
        verts += [xs[x], ys[y], zs[z]]
    quads = [((0, 1, 2, 3), 0x40C070), ((5, 4, 7, 6), 0x2A7A48),
             ((4, 0, 3, 7), 0x9AC020), ((1, 5, 6, 2), 0xC8A038),
             ((3, 2, 6, 7), 0xE8E8D0), ((4, 5, 1, 0), 0x203040)]
    faces = []
    for (a, b, c, d), col in quads:
        faces += [(a, c, b, col), (a, d, c, col)]
    return Mesh(verts, faces)


def main():
    cart = Cart("fade")
    mesh = cart.data(cube(), "cube")
    yaw = cart.var("yaw")
    pit = cart.var("pitch")
    nobj = cart.var("n")
    mode = cart.var("mode")
    t = cart.var("phase")
    a = cart.var("alpha")

    p = cart.program()

    # ---- the cube turns, so the blend has form under it ------------------
    p.addi(yaw, 7).load(yaw).push(1023).emit("and").store(yaw)
    p.addi(pit, 3).load(pit).push(1023).emit("and").store(pit)
    p.set(nobj, 0)
    p.object(nobj, int(mesh),
             0, 0, 5 * ONE,
             [f"load {int(pit)}", "shl 10", f"load {int(yaw)}", "or"],
             cube().flags)
    p.load(nobj).store(spec.OL_BASE)

    # ---- the phase: four modes, two seconds each -------------------------
    p.load(spec.REG_FRAME).push(127).emit("and").store(t)
    # +1 so the cart OPENS on the panel, which is on from frame zero.
    # glass compares frame 2 or 3, and the fade's ramp is at alpha 0
    # there -- so starting on the fade made glass pass with the
    # compositor doing literally nothing. A gate that cannot fail is
    # not a gate.
    p.load(spec.REG_FRAME).emit("shr 7").push(1).emit("add")
    p.push(3).emit("and").store(mode)

    # a triangle ramp 0..16..0 across the 128 frames, for the fade
    #   t < 64 : a = t >> 2      (0..15)
    #   t >= 64: a = (127-t) >> 2
    hi = p.label("ramp_hi")
    done = p.label("ramp_done")
    p.load(t).push(64).emit("lt", f"jz {hi}")
    p.load(t).emit("shr 2").store(a).emit(f"jmp {done}")
    p.mark(hi).push(127).load(t).emit("sub", "shr 2").store(a)
    p.mark(done)
    p.clamp(a, 0, 16)

    # ---- every entry off, then the mode turns its own on -----------------
    p.rects_off()

    def case(n, body):
        skip = p.label("mode")
        p.load(mode).push(n).emit("eq", f"jz {skip}")
        body()
        p.mark(skip)

    # 0: FADE -- the whole screen washes to black and back
    case(0, lambda: p.rect(0, 0, 0, W, H, 0x000000,
                         lambda q: q.load(a)))
    # 1: PANEL -- a dimmed box, the pause menu
    case(1, lambda: p.rect(1, 40, 60, 279, 227, 0x101830, 11))
    # 2: FLASH -- brief and white, on the first eighth of the phase
    case(2, lambda: p.rect(2, 0, 0, W, H, 0xFFFFFF,
                         lambda q: q.load(t).push(16).emit("lt")
                         .push(4).emit("mul")))
    # 3: LETTERBOX -- two opaque bars
    def bars():
        p.rect(3, 0, 0, W, 33, 0x000000, 16)
        p.rect(2, 0, H - 33, W, H, 0x000000, 16)
    case(3, bars)

    p.emit("halt")

    for addr, value in ((spec.CAM_Z, -7 * ONE),
                        (spec.CAM_Y, ONE // 2)):
        cart.boot(addr, value)
    cart.write(HERE / "fade.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
