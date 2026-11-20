#!/usr/bin/env python3
"""gen_vessel.py -- writes games/vessel/vessel.zol: THE GAME LOOP.

Thirty-nine carts and not one of them has a goal, a fail state, a score
or a player loop. Every one proves a subsystem; none of them is a game,
and the consequence is measured rather than felt: across eighteen
subsystems the best single cart exercises SIX. No cost model in this
tree has ever seen a frame with the machine's features switched on
together, which is why nobody knows whether the remaining budget belongs
to light or to triangles.

So this is the stress test, and it is a game because a game is the only
thing that turns everything on at once and keeps it on.

WHAT IT IS. You wake in the hall with the air running out. Find the key,
reach the door, get out before the timer does. hall.zol's engine
underneath it, unchanged and imported rather than copied -- the same
scene() feeds the raytracer, the collision table AND this cart, so a
column that moves in the picture moves in the collision in the same
edit.

WHAT IT TURNS ON, and the point is the AND:
    BG_SRC        the room, path-traced offline, carrying its own depth
    GEOM          player, key and door as live objects inside that depth
    display list  the prompts and the air gauge -- the budget every 3D
                  cart in this tree leaves at exactly zero
    compositor    the fade at the end, and the pulse as the air goes
    scenes/timers a mode cell, a countdown, and a death that fires once
    input edges   "press to take" is an EDGE; REG_PAD is a level
    fog           depth the plate and the actors share

STAGE 4'S LIGHT, added once it existed and metered here rather than in
a cart built to flatter it:
    OBJ_OTINT     the key BREATHES -- one sine lookup per frame rebuilds
                  its light in one word, and its mesh is never touched
    BLEND_ADD     the glow coming off it, additive, so the wall behind
                  reads as LIT rather than as stickered
    contact       a blended quad under the key, which is the only thing
                  in the room saying it hovers rather than floats

All three together cost 1,247 clocks: 263,820 -> 265,067, or 0.17% of a
frame. "Light that costs nothing" was the plan's phrase and this is the
number behind it.

Held back deliberately for the next increments, so each one can be
metered on its own: the mover paging a second room, SD saves, textures
on the key.

THE PROMPT IS NOT REDRAWN EVERY FRAME. The display list is ordinary
DMEM and nothing else writes it, so text costs instructions only on the
frame the message changes. `shown` holds which message is up.
"""
import math
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import carts as _carts                         # noqa: E402
_carts.on_path()                 # sibling generators, wherever they live

from zeta import bake, spec
from zeta.forge import Cart, Table, Text, sine_table

from gen_hall import EYE, SPEED, TURN, X_LIMIT, Z_HI, Z_LO, ONE
from gen_hall import blockers, player, scene

# ---- the things in the room ----------------------------------------------
KEY_X, KEY_Z = -2.2, 14.0        # beside the third column pair
DOOR_X, DOOR_Z = 0.0, 25.4       # the slab at the end of the hall
REACH = 1.4                      # how close is "you can touch it"
AIR = 60 * 50                    # fifty seconds, in frames
SAMPLE_RATE = 48000
BLIP = 260                       # the tick's length, in samples
CHIME = 24                       # frames a chime rings for


def inc_for(hz):
    """A channel's phase increment: f = inc * 48000 / 2^24."""
    return int(hz * (1 << 24) / SAMPLE_RATE)


# THE SPEAKER IS THE LAW HERE. A 55 Hz drone is correct on paper, sits
# at the right place under a room tone, and is INAUDIBLE on a Pocket --
# the speaker has nothing below roughly 200 Hz. Reported by ear, not by
# instrument: the tick came through and the drone did not. Pitched up to
# a D3 the little speaker can actually move, and its volume doubled.
DRONE_INC = inc_for(147.0)       # the room, a D the speaker can reach
TICK_INC = inc_for(392.0)        # the air, a G above it
CHIME_INC = inc_for(880.0)       # the key

# message ids, so `shown` can hold one number instead of a string
M_NONE, M_TAKE, M_GOT, M_LOCKED, M_OPEN, M_WON, M_DEAD = range(7)


def keymesh():
    """A small citrinitas tetrahedron: the one bright thing in a grey
    room, which is how you find it without a map."""
    s = 0.16
    v = [0, int(s * 2 * ONE), 0,
         int(-s * ONE), 0, int(s * ONE),
         int(s * ONE), 0, int(s * ONE),
         0, 0, int(-s * 1.4 * ONE)]
    f = [(0, 2, 1, 0xE6C010), (0, 3, 2, 0xC9A80E),
         (0, 1, 3, 0xF2D420), (1, 2, 3, 0x8C7409)]
    from zeta.forge import Mesh
    return Mesh(v, f)


def doormesh(rgb):
    from zeta.forge import Mesh
    w, h, t = 0.9, 2.2, 0.12
    v = [int(-w * ONE), 0, int(-t * ONE),
         int(w * ONE), 0, int(-t * ONE),
         int(w * ONE), int(h * ONE), int(-t * ONE),
         int(-w * ONE), int(h * ONE), int(-t * ONE)]
    f = [(0, 1, 2, rgb), (0, 2, 3, rgb)]
    return Mesh(v, f)


def shadowmesh(r=0.7, alpha=7):
    """A CONTACT SHADOW: a dark quad lying on the floor, blended and
    therefore writing no depth. Zero silicon -- this is stage 4c, and
    the whole feature is content.

    It is worth more than it costs. The key hovers at y=0.25 and the
    door stands on a plate whose floor is painted, not modelled, so
    neither has anything underneath it saying WHERE it is. An object
    with no shadow does not read as floating; it reads as pasted onto
    the picture, which is the same failure additive blending fixes for
    light. The eye takes contact from the shadow and nothing else here
    can give it."""
    from zeta.forge import Mesh
    y, q = int(0.02 * ONE), int(r * ONE)
    v = [-q, y, -q,  q, y, -q,  q, y, q,  -q, y, q]
    col = (0x000000 | (alpha << spec.BLEND_A_SHIFT)
           | (spec.BLEND_LERP << spec.BLEND_MODE_SHIFT))
    return Mesh(v, [(0, 1, 2, col), (0, 2, 3, col)])


# ---- THE SPARE BIT, read back (spec.PICK_SH) -----------------------------
# The plate carries the room's shadow mask in a bit that was read by
# nothing until now. To ask about it the cart must name a PIXEL, and it
# knows only where its actor stands in the WORLD -- so it needs the
# projection, and the projection needs a divide the ISA does not have.
#
# A table of reciprocals is the whole answer. The camera is fixed (the
# plate demands it: bake.render parks the eye and the cart must agree),
# so 1/z over the walkable range is 94 words baked at build time, and the
# projection becomes two mulq and two shifts:
#
#     sx = W/2 + (px * (1/z)) * FOCAL      <- spec's own _project,
#     sy = H/2 + (EYE_Y * (1/z)) * FOCAL      with vy = -EYE_Y
#
# QUARTER-UNIT resolution, because the shadow edge is what is being
# sampled and a whole unit of quantisation puts it a step away from where
# the eye sees it.
RZ_SHIFT = 14                    # a quarter of a world unit per entry
RZ_LO = int(Z_LO * ONE) >> RZ_SHIFT
RZ_N = (int((Z_HI + 1.0) * ONE) >> RZ_SHIFT) - RZ_LO + 1
LIT_TINT, DARK_TINT = 31, 13     # 31 is EXACT passthrough (the +1 law)


def recip_table():
    """ONE/z in Q16.16, indexed by z >> RZ_SHIFT from RZ_LO."""
    out = []
    for i in range(RZ_N):
        z = (RZ_LO + i) << RZ_SHIFT
        out.append((ONE * ONE) // max(z, 1))
    from zeta.forge import Table
    return Table(out)


# WHERE THE GLOW FACES, and it is a CONSTANT.
#
# It tracked the player's heading for one build, and a player watching it
# said "the halo turns with the player" -- which it did, visibly, every
# time they turned. The mistake was assuming a first-person camera. This
# camera never moves: it sits at the origin looking down the hall while
# the player's BODY walks away from it, so a card that turns with the
# player's heading turns for no reason at all.
#
# With both the camera and the key fixed, the angle that faces one at the
# other is known at build time and costs nothing to hold. Derived, not
# typed -- move KEY_X or KEY_Z and this follows.
#
# IF THE CAMERA EVER MOVES, THIS BECOMES WRONG AGAIN, and it will be
# wrong quietly: a card facing slightly off is still a card.
GLOW_YAW = round(math.atan2(-KEY_X, KEY_Z) / math.tau * 1024) % 1024


def glowmesh(r=0.5, alpha=5):
    """The light coming OFF the key, as an additive billboard.

    Additive is the point: a lerp could only tint the wall behind the
    key toward yellow, which reads as a decal stuck on the wall. This
    makes those pixels BRIGHTER than either the wall or the quad, which
    is what a light source does. The object's yaw is set to the camera's
    heading every frame, so it always faces the player -- one cell read,
    and the cheapest billboard there is."""
    from zeta.forge import Mesh
    q, y = int(r * ONE), int(r * ONE)
    v = [-q, -y, 0,  q, -y, 0,  q, y, 0,  -q, y, 0]
    col = (0xFFD860 | (alpha << spec.BLEND_A_SHIFT)
           | (spec.BLEND_ADD << spec.BLEND_MODE_SHIFT))
    return Mesh(v, [(0, 1, 2, col), (0, 2, 3, col)])


# Blended objects are NOT culled: a floor quad seen from above and a
# billboard seen from either side both need both windings to survive.
BLEND_FLAGS = spec.OBJ_BLEND
# The key's light, rebuilt every frame from one sine lookup (OBJ_OTINT).
KEY_LIT = spec.OBJ_CULL | spec.OBJ_OTINT


def near(p, cx, cz, tx, tz, r, body):
    """Run `body` when the player is inside a square of side 2r about
    (tx, tz). Two-sided compares only -- the ISA has no absolute value
    and this needs none."""
    skip = p.label("far")
    p.push(int((tx - r) * ONE)).load(cx).emit("lt", f"jz {skip}")
    p.load(cx).push(int((tx + r) * ONE)).emit("lt", f"jz {skip}")
    p.push(int((tz - r) * ONE)).load(cz).emit("lt", f"jz {skip}")
    p.load(cz).push(int((tz + r) * ONE)).emit("lt", f"jz {skip}")
    body(p)
    return p.mark(skip)


def main():
    cart = Cart("vessel")

    print("raytracing the hall (the same scene() hall.zol bakes)...")
    col, dep, lit = bake.render(scene(), eye=EYE, shadow_samples=14,
                           ao_samples=24)
    plate = cart.cram(bake.plate(col, dep, lit), "plate")

    body = cart.data(player(), "player")
    keym = cart.data(keymesh(), "key")
    doorm = cart.data(doormesh(0x8A2018), "door_shut")
    doorm2 = cart.data(doormesh(0x20B040), "door_open")
    shadm = cart.data(shadowmesh(), "shadow")
    glowm = cart.data(glowmesh(), "glow")
    boxes = cart.data(Table(blockers()), "blockers")
    sintab = cart.data(sine_table(), "sin")
    nbox = len(blockers()) // 4

    msgs = {
        M_TAKE:   cart.data(Text("PRESS N", 116, 236), "m_take"),
        M_GOT:    cart.data(Text("THE KEY", 116, 236), "m_got"),
        M_LOCKED: cart.data(Text("LOCKED", 122, 236), "m_lock"),
        M_OPEN:   cart.data(Text("PRESS N", 116, 236), "m_open"),
        M_WON:    cart.data(Text("YOU ESCAPED", 92, 130), "m_won"),
        M_DEAD:   cart.data(Text("NO AIR", 122, 130), "m_dead"),
    }

    px = cart.data(Table([0]), "px")
    pz = cart.data(Table([int(6.0 * ONE)]), "pz")
    head = cart.data(Table([0]), "head")
    mode = cart.data(Table([0]), "mode")          # 0 play, 1 won, 2 dead
    air = cart.data(Table([AIR]), "air")
    haskey = cart.data(Table([0]), "haskey")
    shown = cart.data(Table([-1]), "shown")       # -1 = nothing yet
    want = cart.var("want")
    dx, dz = cart.var("dx"), cart.var("dz")
    cx, cz = cart.var("cand_x"), cart.var("cand_z")
    hit, ci, cb = cart.var("hit"), cart.var("box_i"), cart.var("box_at")
    nobj = cart.var("n")
    prev, press = cart.var("prev"), cart.var("press")
    # sound: tpos counts DOWN in samples to the next air tick, so a tick
    # can land ANYWHERE in a frame -- see the block at the bottom
    tpos = cart.data(Table([SAMPLE_RATE]), "tpos")
    ivl, hit, roff = cart.var("ivl"), cart.var("hit"), cart.var("roff")
    evp, nev = cart.var("evp"), cart.var("nev")
    chime = cart.data(Table([0]), "chime")
    rztab = cart.data(recip_table(), "recip_z")
    rz = cart.var("rz")

    p = cart.program()
    p.pad_edges(prev, press)
    p.set(want, M_NONE)

    # ================= PLAYING ==========================================
    def playing(q):
        q.countdown(air)
        q.on_zero(air, lambda r: r.set(mode, 2))

        q.if_pad(spec.PAD_LEFT, lambda r: r.addi(head, -TURN))
        q.if_pad(spec.PAD_RIGHT, lambda r: r.addi(head, TURN))
        q.load(head).push(1023).emit("and").store(head)

        # the sine table is 128 entries and the heading is 1024 steps, so
        # the index is head >> 3 -- hall.zol's own sincos, not a rewrite
        def sincos(cell, phase, sign):
            def go(r):
                r.load(head)
                if phase:
                    r.push(phase).emit("add")
                r.emit("shr 3").push(127).emit("and")
                r.push(int(sintab)).emit("add", "loadi")
                r.push(sign * SPEED).emit("mulq").store(cell)
            return go

        def walk(sign):
            def go(r):
                sincos(dx, 0, sign)(r)        # x follows sin
                sincos(dz, 256, sign)(r)      # z follows cos
            return go
        q.set(dx, 0).set(dz, 0)
        q.if_pad(spec.PAD_UP, walk(1))
        q.if_pad(spec.PAD_DOWN, walk(-1))

        # X then Z, each rejected on its own so walls slide instead of
        # sticking -- hall.zol's rule, and the difference between a demo
        # and something you can walk around in
        for cell, delta, cand in ((px, dx, cx), (pz, dz, cz)):
            keep, done = q.label("keep"), q.label("done")
            q.load(cell).load(delta).emit("add").store(cand)
            q.load(pz if cell is px else px).store(cz if cell is px else cx)
            q.emit("call hit")
            q.load(hit).emit(f"jz {keep}")     # hit == 0: the step is free
            q.emit(f"jmp {done}")              # blocked: stay put
            q.mark(keep).load(cand).store(cell)
            q.mark(done)
        q.clamp(px, -int(X_LIMIT * ONE), int(X_LIMIT * ONE))
        q.clamp(pz, int(Z_LO * ONE), int(Z_HI * ONE))

        # the key
        def at_key(r):
            r.set(want, M_TAKE)
            r.if_bit(press, spec.PAD_A,
                     lambda t: t.set(haskey, 1).set(want, M_GOT)
                                .set(chime, CHIME))
        q.if_zero(haskey, lambda r: near(r, px, pz, KEY_X, KEY_Z, REACH,
                                         at_key))

        # the door
        def at_door(r):
            def locked(t):
                t.set(want, M_LOCKED)
            def unlocked(t):
                t.set(want, M_OPEN)
                t.if_bit(press, spec.PAD_A,
                         lambda u: u.set(mode, 1).set(chime, CHIME * 2))
            r.if_zero(haskey, locked)
            r.if_nonzero(haskey, unlocked)
        near(q, px, pz, DOOR_X, DOOR_Z, REACH + 0.4, at_door)

    p.if_zero(mode, playing)
    p.if_eq(mode, 1, lambda q: q.set(want, M_WON))
    p.if_eq(mode, 2, lambda q: q.set(want, M_DEAD))

    # ---- the prompt, ONLY when it changes --------------------------------
    # SUB, not EQ: `eq` leaves 1 when they match and `jz` jumps on ZERO,
    # so the eq form skips the update on exactly the frames that need it.
    # A subtraction is zero when the message has not changed, which is the
    # condition this wants.
    p.load(want).load(shown).emit("sub")
    nochange = p.label("nochg")
    p.emit(f"jz {nochange}")
    for mid, sym in msgs.items():
        p.if_eq(want, mid, lambda q, s=sym: q.set_text(s))
    p.if_eq(want, M_NONE, lambda q: q.hide_text())
    p.load(want).store(shown)
    p.mark(nochange)

    # ---- the compositor: air pulse, and the fade at the end --------------
    p.rects_off()
    p.if_eq(mode, 1, lambda q: q.rect(0, 0, 0, spec.W - 1, spec.H - 1,
                                      0xFFFFFF, 6))
    p.if_eq(mode, 2, lambda q: q.rect(0, 0, 0, spec.W - 1, spec.H - 1,
                                      0x000000, 9))

    # ---- SOUND, and the one thing no console of either generation had ----
    # AU_EV_BASE is a TIMELINE: (sample offset, channel, value) applied at
    # the exact sample, 800 to a frame. Three of thirty-two generators in
    # this tree use it, on the axis where this machine beats the fifth
    # generation OUTRIGHT -- and the cross gate compares the sample stream
    # bit-equal against silicon, so the timing is provable, not merely
    # close.
    #
    # THE AIR TICK IS THE DEMONSTRATION. Its period shrinks as the air
    # runs out and shares no factor with 800, so the onset lands on a
    # DIFFERENT sample every time. Frame-quantised audio cannot do that:
    # it would drift into a 60 Hz grid and read as a stutter. Here the
    # metronome is exact and the panic is real.
    p.set(nev, 0).set(evp, spec.AU_EV_BASE + 1)

    # the room's drone: a low triangle, always there, dropping a fifth
    # when the air is gone
    p.set(spec.AU_BASE + 4, DRONE_INC)
    p.if_eq(mode, 2, lambda q: q.set(spec.AU_BASE + 4, DRONE_INC // 2))
    p.set(spec.AU_BASE + 5, 4)

    p.set(spec.AU_BASE + 0, TICK_INC)          # the tick's pitch
    def air_tick(q):
        # interval = 6000 + air*16 samples: about one a second at the
        # start, eight a second at the end. A shift, because the ISA has
        # no divide and this needs none.
        q.load(air).emit("shl 4").push(6000).emit("add").store(ivl)
        q.load(tpos).push(spec.SAMPLES_PER_FRAME).emit("sub").store(tpos)
        skip = q.label("notick")
        q.load(tpos).push(0).emit("lt", f"jz {skip}")
        q.push(0).load(tpos).emit("sub").store(hit)      # offset = -tpos
        # ...clamped into the frame. tpos can land on exactly -800, which
        # names sample 800 -- the first sample of the NEXT frame, and an
        # event there simply never fires. One sample late is audible to
        # nobody; an event that silently does nothing is a ghost.
        ok = q.label("inframe")
        q.load(hit).push(spec.SAMPLES_PER_FRAME).emit("lt", f"jz {ok}")
        q.emit(f"jmp {q.label('go2')}")
        last = q._out[-1].split()[-1]
        q.mark(ok).set(hit, spec.SAMPLES_PER_FRAME - 1)
        q.mark(last)
        q.load(tpos).load(ivl).emit("add").store(tpos)
        # the attack, at that exact sample
        q.load(hit).push((0 << spec.AU_EV_CH_SHIFT) | spec.AU_EV_CTRL_BIT)
        q.emit("or").load(evp).emit("storei")
        q.addi(evp, 1)
        q.push(7 | (2 << 4)).load(evp).emit("storei")    # vol 7, 50% duty
        q.addi(evp, 1).addi(nev, 1)
        # ...and the release, clamped into this frame so a tick can never
        # hang over into the next one as a drone
        q.load(hit).push(BLIP).emit("add").store(roff)
        inside, go = q.label("in"), q.label("go")
        q.load(roff).push(spec.SAMPLES_PER_FRAME).emit("lt", f"jz {inside}")
        q.emit(f"jmp {go}")
        q.mark(inside).set(roff, spec.SAMPLES_PER_FRAME - 1)
        q.mark(go)
        q.load(roff).push((0 << spec.AU_EV_CH_SHIFT) | spec.AU_EV_CTRL_BIT)
        q.emit("or").load(evp).emit("storei")
        q.addi(evp, 1)
        q.push(0).load(evp).emit("storei")
        q.addi(evp, 1).addi(nev, 1)
        q.mark(skip)
    p.if_zero(mode, air_tick)

    # the chime: taking the key, and the door opening. Frame-quantised on
    # purpose -- a button press has no sub-frame time, and pretending it
    # does would be a lie the gate could not catch.
    p.set(spec.AU_BASE + 2, CHIME_INC)
    p.if_eq(mode, 1, lambda q: q.set(spec.AU_BASE + 2, CHIME_INC * 3 // 2))
    # `shr` TAKES AN IMMEDIATE. This was `load chime; push 1; shr 1`,
    # which shifts the pushed 1 to zero, stores THAT as the volume, and
    # leaves chime orphaned on the stack -- so the chime was silent every
    # frame and the only reason nothing else broke is that the VM resets
    # the stack each frame. The player heard the air tick and no chime,
    # which is exactly what this code does.
    p.load(chime).emit("shr 1").store(spec.AU_BASE + 3)
    p.countdown(chime)

    p.load(nev).store(spec.AU_EV_BASE)

    # ---- ASK THE ROOM WHERE ITS SHADOW IS --------------------------------
    # Project the player's own feet and park the pick register there. The
    # answer (spec.PICK_SH) is the plate's baked shadow bit at that pixel
    # and arrives NEXT frame, which is the pick register's contract and
    # invisible on a shadow.
    #
    # This is the whole point of the spare bit: the room's light and the
    # actor's light stop being different worlds. Every pre-rendered game
    # ever shipped has the character pasted onto the photograph because
    # nobody could ask this question.
    p.load(int(pz)).emit(f"shr {RZ_SHIFT}").push(RZ_LO).emit("sub")
    p.push(int(rztab)).emit("add", "loadi").store(rz)
    p.load(int(px)).load(rz).emit("mulq", f"shr {8}")
    p.push(spec.W // 2).emit("add").store(spec.PICK_X)
    p.push(int(EYE[1] * ONE)).load(rz).emit("mulq", f"shr {8}")
    p.push(spec.H // 2).emit("add").store(spec.PICK_Y)

    # ---- the objects -----------------------------------------------------
    p.set(nobj, 0)
    # THE ACTOR TAKES THE ROOM'S LIGHT. One word, rebuilt each frame from
    # one bit the room told it -- which is exactly the shape OBJ_OTINT was
    # built for, and why the spare bit needed no new object flag.
    #   tint = DARK if the plate says the sun is blocked here, else LIT,
    # in all three channels (a shadow desaturates nothing; it just takes
    # the sun away).
    lit_word = spec.OBJ_CULL | spec.OBJ_OTINT
    p.object(nobj, int(body),
             [f"load {int(px)}"], 0, [f"load {int(pz)}"],
             ["push 1024", f"load {int(head)}", "sub", "push 1023", "and"],
             [f"load {spec.PICK_SH}",
              f"push {LIT_TINT - DARK_TINT}", "mul",
              f"push {LIT_TINT}", "swap", "sub",       # LIT or DARK
              "dup", "dup",
              "shl 27", "swap", "shl 22", "or",
              "swap", "shl 17", "or",
              f"push {lit_word}", "or"])
    # THE KEY BREATHES (OBJ_OTINT). Its light is one word in its object
    # slot, rebuilt each frame from a single sine lookup -- the mesh is
    # never touched. Before this flag the only way to make the goal
    # pulse was to rewrite its four colour words every frame.
    #   sin is +/-ONE over 128 entries; +ONE >> 13 lands in 0..16, and
    # +15 puts the light in 15..31 so the key dims but never goes out.
    p.if_zero(haskey, lambda q: q.object(
        nobj, int(keym), int(KEY_X * ONE), int(0.25 * ONE),
        int(KEY_Z * ONE),
        [f"load {spec.REG_FRAME}", "push 3", "mul", "push 1023", "and"],
        [f"load {spec.REG_FRAME}", "push 127", "and",
         f"push {int(sintab)}", "add", "loadi",
         f"push {ONE}", "add", "shr 13", "push 15", "add",
         "dup", "shl 27",                 # red
         "swap", "shl 22", "or",          # ...and green: gold
         f"push {KEY_LIT}", "or"]))
    p.if_zero(haskey, lambda q: q.object(
        nobj, int(doorm), int(DOOR_X * ONE), 0, int(DOOR_Z * ONE), 0,
        doormesh(0).flags))
    p.if_nonzero(haskey, lambda q: q.object(
        nobj, int(doorm2), int(DOOR_X * ONE), 0, int(DOOR_Z * ONE), 0,
        doormesh(0).flags))

    # ---- and only now the blended ones ----------------------------------
    # THE BLEND-ORDER LAW (spec.py): every opaque face is submitted before
    # any blended one, and the blended ones back to front.
    #
    # THE DOOR HAS NO SHADOW, AND THAT IS A MEASUREMENT. It had one for
    # an hour and it drew ZERO PIXELS -- not too dark to see, not
    # depth-rejected: zero. This camera is fixed at the origin and the
    # door stands 25.4 units down the hall, where the floor is so nearly
    # edge-on that a quad lying on it is under HALF A PIXEL tall, and
    # covers no pixel centre. Raising it to 0.6 units off the floor
    # changed nothing; stretching it to 6.6 units deep changed nothing;
    # only scaling it 4x in both axes made it appear, by which point it
    # is not a contact shadow.
    #
    # So contact shadows pay near the camera and nowhere else, and the
    # far end of a fixed-camera corridor gets none however it is
    # authored. Leaving it in would have cost full setup every frame,
    # forever, for nothing -- and looked in the source exactly like a
    # feature that works.
    p.if_zero(haskey, lambda q: q.object(
        nobj, int(shadm), int(KEY_X * ONE), 0, int(KEY_Z * ONE), 0,
        BLEND_FLAGS))
    p.if_zero(haskey, lambda q: q.object(
        nobj, int(glowm), int(KEY_X * ONE), int(0.3 * ONE),
        int(KEY_Z * ONE), GLOW_YAW, BLEND_FLAGS))
    p.load(nobj).store(spec.OL_BASE)
    p.emit("halt")

    # ---- hit(cand) -> hit, from hall, unchanged --------------------------
    p.mark("hit")
    p.set(hit, 0).set(ci, 0)
    p.mark("hit_loop")
    p.load(ci).push(nbox).emit("lt")
    p.emit("jz hit_done")
    p.load(ci).push(4).emit("mul").push(int(boxes)).emit("add").store(cb)
    for k, (cell, op) in enumerate(((cx, "lo"), (cx, "hi"),
                                    (cz, "lo"), (cz, "hi"))):
        cont = p.label("in")
        p.load(cb).push(k).emit("add", "loadi")
        if op == "lo":
            p.load(cell)
        else:
            p.load(cell).emit("swap")
        p.emit("lt", f"jz {cont}", "jmp hit_next").mark(cont)
    p.set(hit, 1).emit("ret")
    p.mark("hit_next")
    p.addi(ci, 1).emit("jmp hit_loop")
    p.mark("hit_done").emit("ret")

    # the shot is FIXED and authored: the camera never moves, which is
    # what lets a baked plate and live actors share one depth buffer
    cart.boot(spec.CAM_X, int(EYE[0] * ONE))
    cart.boot(spec.CAM_Y, int(EYE[1] * ONE))
    cart.boot(spec.CAM_Z, int(EYE[2] * ONE))
    cart.boot(spec.BG_SRC, int(plate))

    path = cart.write(Path(__file__).with_name("vessel.zol"))
    print(cart.report())
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
