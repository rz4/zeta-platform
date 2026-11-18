#!/usr/bin/env python3
"""gen_hall.py -- writes carts/hall.zol: offline light, and something to
walk through it.

The roadmap's flagship, now PLAYABLE. room.zol proved the mechanism --
BG_SRC clears the frame to a baked colour AND DEPTH plane, and live
geometry occludes against it per pixel -- but it baked the room through
the law's own rasteriser, so the room looked exactly like something Zeta
would draw. Which is the one thing a pre-rendered backdrop must not
look like.

This hall is raytraced by zeta/bake.py: analytic casts, a sun sampled
across its disc for soft shadows, hemispherical ambient occlusion, a sky
gradient. Eight seconds a frame, and it could as easily be eight hours.
The machine never draws a column. It clears to them.

THE CAMERA IS THE CONTRACT, and it is also the design. The plate is
baked in view space with the eye at (0, 1.7, 0) looking down +z, so the
camera CANNOT move -- move it and the baked world stays put while the
live world slides, and the player floats. That constraint is not a
limitation to work around, it is Resident Evil's whole camera language:
the shot is fixed and authored, and the PLAYER moves inside it under
tank controls. So that is what this is.

    dpad left/right   turn on the spot
    dpad up/down      walk along your heading

COLLISION, and the reason it costs almost nothing here. The columns are
not pixels to this cart -- they are the same Python objects that fed the
raytracer. scene() is walked twice: once by the renderer to make the
picture, and once by the linker to emit an XZ footprint table. The two
CANNOT disagree, because a column that moves in the render moves in the
table in the same edit. That is the honest version of "collision that
matches the art", and it is the property a hand-authored collision mesh
(RE's actual approach) never had.

The test itself is an AABB per box, run TWICE per frame -- once for the
X step and once for the Z step, each rejected on its own. Rejecting the
whole move sticks the player to walls; rejecting per axis slides them
along, which is the difference between a demo and something you can
stand to steer.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import bake, spec                              # noqa: E402
from zeta.forge import ONE, Cart, Mesh, Table, sine_table  # noqa: E402

EYE = (0.0, 1.7, 0.0)
COL_X, COL_Z = 3.2, (5.5, 9.0, 12.5, 16.0, 19.5, 23.0)

BODY_W, BODY_H = 0.75, 1.5
RADIUS = BODY_W / 2                     # the player as a point + this
SPEED = int(0.075 * ONE)                # world units per frame
TURN = 8                                # of 1024 -- ~2.8 degrees a frame
X_LIMIT, Z_LO, Z_HI = 6.5, 1.6, 25.0    # keep the player inside the shot


def scene():
    """The hall. Walked twice: once by the raytracer for the picture,
    once by the linker for the collision table."""
    objs = [bake.Plane(0.0, (0.50, 0.48, 0.44))]
    for z in COL_Z:
        for x in (-COL_X, COL_X):
            objs.append(bake.Box((x - 0.5, 0.0, z - 0.5),
                                 (x + 0.5, 4.6, z + 0.5),
                                 (0.74, 0.70, 0.62)))
    objs.append(bake.Box((-8, 0, 26), (8, 9, 26.6), (0.44, 0.46, 0.52)))
    objs.append(bake.Box((-3.7, 4.6, 4.0), (3.7, 5.2, 25.0),
                         (0.60, 0.56, 0.50)))
    return objs


def blockers():
    """Every box the player's body can reach, as XZ extents already
    grown by the player's radius -- so the runtime test is a point in a
    rectangle, which is four compares and no arithmetic.

    The ceiling slab sits at y 4.6..5.2 and is filtered out here by its
    own geometry, not by a hand-kept list: anything whose underside is
    above the player's head cannot be walked into."""
    out = []
    for ob in scene():
        if not isinstance(ob, bake.Box):
            continue
        if ob.lo[1] > BODY_H:                  # overhead: cannot be hit
            continue
        out += [int((ob.lo[0] - RADIUS) * ONE), int((ob.lo[2] - RADIUS) * ONE),
                int((ob.hi[0] + RADIUS) * ONE), int((ob.hi[2] + RADIUS) * ONE)]
    return out


def player():
    """A flat-shaded body with ONE bright face, because tank controls are
    unreadable on a uniform box -- you cannot steer what you cannot see
    the heading of. The bright face is +z, which is the direction the
    heading zero walks."""
    h, w = BODY_H, BODY_W
    verts = []
    for x, y, z in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]:
        verts += [int((x - 0.5) * w * ONE), int(y * h * ONE),
                  int((z - 0.5) * w * ONE)]
    # The two sides get DIFFERENT colours on purpose. A left/right
    # symmetric body cannot show a yaw SIGN error -- turn the wrong way
    # and it looks identical -- so the demo could not be checked, only
    # believed. Distinct flanks make the heading fully readable at a
    # glance and make a rotation-sign mistake visible the first frame.
    DARK, LEFT, RIGHT = 0x704018, 0x3A6E9A, 0xA83828
    TOP, FACE = 0xA86A28, 0xFFD060
    quads = [((0, 1, 2, 3), DARK),          # -z, the back
             ((5, 4, 7, 6), FACE),          # +z, the FRONT: the bright one
             ((4, 0, 3, 7), LEFT),          # -x flank
             ((1, 5, 6, 2), RIGHT),         # +x flank
             ((3, 2, 6, 7), TOP), ((4, 5, 1, 0), DARK)]
    faces = []
    for (a, b, c, d), col in quads:
        faces += [(a, c, b, col), (a, d, c, col)]
    return Mesh(verts, faces)


def main():
    cart = Cart("hall")

    print("raytracing the hall...")
    col, dep, lit = bake.render(scene(), eye=EYE,
                           shadow_samples=14, ao_samples=24)
    plate = cart.cram(bake.plate(col, dep, lit), "hall_plate")
    mesh = cart.data(player(), "player")
    boxes = cart.data(Table(blockers()), "blockers")
    sintab = cart.data(sine_table(), "sin")
    nbox = len(blockers()) // 4

    # The player's state carries an INITIAL VALUE, so it is a one-word
    # table rather than a var: cart.boot() refuses the content region on
    # purpose (a boot write there would land on a mesh), and "a variable
    # that starts somewhere" is exactly a table of length one.
    px = cart.data(Table([0]), "px")
    pz = cart.data(Table([int(6.0 * ONE)]), "pz")
    head = cart.data(Table([0]), "head")
    dx = cart.var("dx")
    dz = cart.var("dz")
    cx = cart.var("cand_x")
    cz = cart.var("cand_z")
    hit = cart.var("hit")
    ci = cart.var("box_i")
    cb = cart.var("box_at")
    nobj = cart.var("n")

    p = cart.program()

    # ---- turn on the spot ------------------------------------------------
    p.if_pad(spec.PAD_LEFT, lambda q: q.addi(head, -TURN))
    p.if_pad(spec.PAD_RIGHT, lambda q: q.addi(head, TURN))
    p.load(head).push(1023).emit("and").store(head)

    # ---- the step the player WANTS, before the world gets a say ----------
    def sincos(cell, phase, sign):
        """cell = sign * SPEED * sin(head + phase), Q16.16 throughout."""
        def body(q):
            q.load(head)
            if phase:
                q.push(phase).emit("add")
            q.emit("shr 3").push(127).emit("and")          # 128 entries
            q.push(int(sintab)).emit("add", "loadi")
            q.push(sign * SPEED).emit("mulq").store(cell)
        return body

    def walk(sign):
        def body(q):
            sincos(dx, 0, sign)(q)          # x follows sin
            sincos(dz, 256, sign)(q)        # z follows cos = sin(a + 90deg)
        return body

    p.set(dx, 0).set(dz, 0)
    p.if_pad(spec.PAD_UP, walk(1))
    p.if_pad(spec.PAD_DOWN, walk(-1))

    # ---- move on each axis SEPARATELY, so a blocked axis slides ----------
    # X first
    p.load(px).load(dx).emit("add").store(cx)
    p.load(pz).store(cz)
    p.emit("call hit")
    keep = p.label("kx")
    p.load(hit).emit(f"jz {keep}")
    p.load(px).store(cx)                       # blocked: stay where we were
    p.mark(keep).load(cx).store(px)

    # then Z, from the position X just settled on
    p.load(px).store(cx)
    p.load(pz).load(dz).emit("add").store(cz)
    p.emit("call hit")
    keep = p.label("kz")
    p.load(hit).emit(f"jz {keep}")
    p.load(pz).store(cz)
    p.mark(keep).load(cz).store(pz)

    # ---- the edges of the shot -------------------------------------------
    p.clamp(px, -int(X_LIMIT * ONE), int(X_LIMIT * ONE))
    p.clamp(pz, int(Z_LO * ONE), int(Z_HI * ONE))

    # ---- one object, and it is the player --------------------------------
    # THE MESH ANGLE IS THE NEGATED HEADING, and this is not a fudge.
    # `head` drives movement through (sin, cos), which is a LEFT-handed
    # turn in this machine's object rotation: the two agree at 0 and 180
    # and are 180 degrees APART at +/-90. Measured, not reasoned --
    # rendered at head 256 the body walks +x while showing the camera
    # its -x flank. A left/right symmetric body hides this completely,
    # which is exactly why the flanks got different colours first.
    p.set(nobj, 0)
    p.object(nobj, int(mesh),
             [f"load {int(px)}"], 0, [f"load {int(pz)}"],
             [f"push 1024", f"load {int(head)}", "sub", "push 1023", "and"],
             player().flags)
    p.load(nobj).store(spec.OL_BASE)
    p.emit("halt")

    # ---- hit(cand_x, cand_z) -> hit --------------------------------------
    # Four compares per box, first failure moves to the next box. Written
    # as a subroutine because it runs twice a frame and the ISA has had a
    # return stack since build 8.
    p.mark("hit")
    p.set(hit, 0).set(ci, 0)
    p.mark("hit_loop")
    p.load(ci).push(4).emit("mul").push(int(boxes)).emit("add").store(cb)

    def outside(build):
        """`build` leaves a<b on the stack; a TRUE means this box is
        missed, so take the next one. jz falls through on false, which
        is the only way to say 'if true, goto' with one branch op."""
        cont = p.label("in")
        build()
        p.emit("lt", f"jz {cont}", "jmp hit_next").mark(cont)

    def entry(k):                              # table[cb + k]
        p.load(cb).push(k).emit("add", "loadi")

    outside(lambda: (p.load(cx), entry(0)))    # cand_x < x0
    outside(lambda: (entry(2), p.load(cx)))    # x1     < cand_x
    outside(lambda: (p.load(cz), entry(1)))    # cand_z < z0
    outside(lambda: (entry(3), p.load(cz)))    # z1     < cand_z
    p.set(hit, 1).emit("ret")                  # inside all four: blocked

    p.mark("hit_next")
    p.addi(ci, 1)
    p.load(ci).push(nbox).emit("lt", "jz hit_done", "jmp hit_loop")
    p.mark("hit_done").emit("ret")

    # THE CAMERA IS THE CONTRACT -- these must equal the bake
    cart.boot(spec.CAM_X, int(EYE[0] * ONE))
    cart.boot(spec.CAM_Y, int(EYE[1] * ONE))
    cart.boot(spec.CAM_Z, int(EYE[2] * ONE))
    cart.boot(spec.BG_SRC, int(plate))
    cart.write(HERE / "hall.zol")
    print(cart.report())
    print(f"plate at CRAM {int(plate)}, {plate.length} words; "
          f"{nbox} collision boxes")


if __name__ == "__main__":
    main()
