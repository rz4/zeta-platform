"""spec.py -- THE machine. Every number that defines Zeta lives here, once.

The Python virtual machine, the pygame cabinet, the Verilog generator, and
the cross-checker all import THIS file. There is no second copy of any
constant anywhere in the tree; if the virtual and the silicon ever disagree,
one of them is violating this file and the cross fails.

Contract, per 1/60 s frame:
  1. The cabinet latches the pad into DMEM[REG_PAD], the frame counter
     into DMEM[REG_FRAME].
  2. The VM runs from PC=0 until HALT (or FUEL runs out -- a lawful stop,
     not an error).  DMEM persists across frames; that is the game state.
  3. The GPU reads the display list at DL_BASE and paints the frame.
     What it paints is defined to the pixel (integer edge functions,
     see gpu.py); virtual and silicon framebuffers must be bit-equal.
"""

# ---- video ---------------------------------------------------------------
W, H, FPS = 320, 288, 60
CLEAR_RGB = 0x101018            # the color of an empty frame

# The framebuffer stores RGB555 -- the PS1's own format, half the memory
# and half the bandwidth of 888. Colors quantize on write (r5 = r8 >> 3)
# and replicate on display (r8 = r5<<3 | r5>>2); display_rgb() is the one
# definition of that round trip, and both machines are held to it.


def display_rgb(rgb24: int) -> tuple[int, int, int]:
    """24-bit cart color -> the (r, g, b) actually shown on screen."""
    out = []
    for sh in (16, 8, 0):
        c5 = ((rgb24 >> sh) & 0xFF) >> 3
        out.append((c5 << 3) | (c5 >> 2))
    return tuple(out)

# ---- memories & budgets --------------------------------------------------
IMEM_WORDS = 4096               # instructions per cart
DMEM_WORDS = 16384              # 32-bit words of game state -- the
                                # capacity amendment: 4x the mesh and
                                # state room (BRAM is the currency the
                                # machine still has to spend)
FUEL = 65536                    # instructions per frame, hard ceiling.
                                # WAS 16,384, chosen when the frame
                                # budget was unknown. The census says
                                # the VM is 1.1% of a tick; burning ALL
                                # of this would be ~14%, and the budget
                                # gate is what actually holds the line.
                                # The counter is sized to the RANGE, not
                                # to today's value: 17 bits.
WORD_MASK = 0xFFFFFFFF          # all arithmetic is 32-bit two's complement

# ---- DMEM map ------------------------------------------------------------
REG_FRAME = 0                   # in:  frame counter (cabinet writes)
REG_PAD = 1                     # in:  pad word     (cabinet writes)
# REG_PAD2 lives at 12263 rather than beside REG_PAD for PICK_SH's
# reason: cells 0..15 are full and USER_BASE is hardcoded in every cart.
# The SECOND pad -- a docked controller, or the far end of the link. The
# cabinet latches it exactly as REG_PAD; 0 means no one is there, which
# is also what an undocked pad must read, so a cart needs no other
# presence test. LAW-FIRST: the silicon latch lands with the next RTL
# build; until then the cell reads 0 on silicon, which is the honest
# value for hardware that has no second port yet.
REG_PAD2 = 12263                # in:  pad 2 word   (cabinet writes)
# ---- the pick register: the GPU as a spatial query engine ----------------
# The cart writes a pixel (PICK_X, PICK_Y); after the frame paints, the
# machine answers with the triangle that visibly owns it: PICK_ID = the
# item's place in the WALK (display list entries first, then every GEOM
# face EXAMINED, drawn or not -- so the id is stable and mesh-relative,
# never shifted by culling or near-rejection), or -1 if only the clear
# or the backdrop touched it; PICK_Z = the depth standing at that pixel, so a
# backdrop's depth plane is queryable too. Frame N's answer is readable
# by the program at frame N+1. An out-of-range pixel answers (-1, 0xFFFF).
PICK_X, PICK_Y, PICK_ID, PICK_Z = 2, 3, 4, 5
# PICK_SH is the same question's third answer and lives at 12269 rather
# than beside its siblings, because cells 0..15 are full and USER_BASE is
# 16 -- carts hardcode that number, so moving it would move every cart's
# variables. Better an odd address with its reason written down than a
# renumbering that breaks silently.
PICK_SH = 12269                 # 1 if the BACKDROP PLATE says the sun is
                                # blocked at the watched pixel, else 0.
                                #
                                # THE SPARE BIT. A plate word is
                                # {z16, 1'b?, rgb555} and bit 15 was read
                                # by nothing in either machine -- 92,160
                                # bits per room, already baked, already
                                # streaming through the pipe. It now
                                # carries the room's SHADOW MASK.
                                #
                                # This is the tell of every pre-rendered
                                # game ever shipped: the character looks
                                # pasted onto the photograph, because the
                                # room's light never touches it. The room
                                # and the actor are lit by different
                                # worlds. Now a cart can ask where its
                                # actor is standing and fold the answer
                                # into that object's OBJ_OTINT word --
                                # which is why this needs no new flag and
                                # no per-pixel silicon. The query already
                                # existed; it only lacked an answer.
                                #
                                # Latched during the CLEAR, because that
                                # is when the plate streams past. Geometry
                                # drawn over the pixel afterwards does not
                                # change where the room's sun falls.
# ---- THE GPU AS A SENSOR (spec.VIS_BASE) --------------------------------
# The rasterizer visits every visible point of every surface with its
# interpolants in hand and throws all of it away but the colour. This is
# the first of it kept: OL_MAX words, one an object, each holding HOW
# MANY PIXELS OF THAT OBJECT THE PANEL ACTUALLY SHOWS.
#
# Counted from the identity plane at FLUSH time, not at commit -- so it
# is final visibility and not "pixels this object won when it drew".
# Something drawn over afterwards does not count, which is the only
# reading of the question that is any use.
#
# Frame N's answer is readable at frame N+1: the pick register's
# contract, and for the same reason -- the count is not complete until
# the band is.
VIS_BASE = 14656                # OL_MAX words, one an object
VIS_MAX = 0x1FFFF               # 17 bits; a whole screen is 92,160

# ---- LIGHT ACROSS A SURFACE (spec.OBJ_LIT) -----------------------------
# THE LAST THING IN THE PICTURE THAT READS AS A DECADE. A flat face lit
# uniformly is the shape of 1997; light that VARIES across it is the
# shape of everything after. The machine has interpolated per-vertex
# colour since OBJ_GOURAUD, so the carrying is already built -- what was
# missing is anywhere to say where the light comes FROM.
#
#   LIGHT_DIR   the direction light travels FROM, packed 8:8:8 signed,
#               each component scaled so that 127 IS ONE UNIT -- not
#               128, which a signed byte cannot hold. Written as 128
#               it wraps to -128 and a surface facing AWAY from the
#               light comes back fully lit, which is what the first
#               draft of this note said to do. Not normalised by the
#               machine: a cart handing it a short vector gets a dim
#               world, which is a dimmer and not a bug.
#   LIGHT_AMB   0..32, the floor. What a surface facing away still gets.
#   LIGHT_DIF   0..32, the gain on the part that faces the light.
#
# A LIT VERTEX CARRIES A NORMAL WHERE A GOURAUD VERTEX CARRIES A COLOUR
# -- the same word, the same layout, the same loader. So OBJ_LIT costs
# no new mesh format, and a mesh can be relit every frame by writing one
# DMEM word instead of rewriting its colours.
#
#     level = clamp(LIGHT_AMB + ((LIGHT_DIF * max(0, N.L)) >> 14), 0, 32)
#     vertex colour = (face rgb channel * level) >> 5
#
# The >>14 is 128*128 and the unit is 127, so a surface facing straight
# at the light reaches 127*127/16,384 = 0.984 of LIGHT_DIF rather than
# all of it. That is a sixteenth of one level and invisible; a cart that
# wants hard saturation sets LIGHT_AMB + LIGHT_DIF a little above 32 and
# lets the clamp do it. Level 32 reproduces the face colour exactly,
# which is why the range is 0..32 and not 0..31.
#
# UNTEXTURED FACES ONLY, and that is a limit rather than an oversight: a
# textured vertex spends that same word on its uv and there is nowhere
# left to put a normal without a second layout. Textured surfaces have
# OBJ_TINT and OBJ_OTINT, which light a face as a whole. Per-vertex
# light on a textured mesh wants a normals block of its own and is a
# different build.
LIGHT_DIR = 14736               # packed 8:8:8 signed, 128 = one unit
LIGHT_AMB = 14737               # 0..32
LIGHT_DIF = 14738               # 0..32
LIGHT_FULL = 32                 # the level at which a face is its own colour


def light_of(normal_word: int, dmem) -> int:
    """One vertex's level, 0..LIGHT_FULL. The law, in one place, so the
    silicon has something exact to be compared against."""
    def s8(v):
        v &= 0xFF
        return v - 256 if v > 127 else v
    nx, ny, nz = (s8(normal_word >> 16), s8(normal_word >> 8),
                  s8(normal_word))
    lw = dmem[LIGHT_DIR]
    lx, ly, lz = s8(lw >> 16), s8(lw >> 8), s8(lw)
    dot = nx * lx + ny * ly + nz * lz
    amb = max(0, min(LIGHT_FULL, dmem[LIGHT_AMB]))
    dif = max(0, min(LIGHT_FULL, dmem[LIGHT_DIF]))
    return max(0, min(LIGHT_FULL, amb + ((dif * max(0, dot)) >> 14)))


# ---- AND THE MIXER AS ONE TOO (spec.AUD_BASE) --------------------------
# The other half of the same idea as VIS_BASE, and the term that closes
# the machine's own formula:
#
#     Zvm(Wn)[An] -> Wn+1 + In + Sn,  and then
#     Wn+1 = f(Wn, An, VIS, AUD)
#
# One word a voice, holding the SUM OF |sample| that voice contributed
# across the frame's SAMPLES_PER_FRAME samples, in the mixer's own units
# -- before the >>2 and before the clamp. A voice peaks at 15,360, so a
# whole frame peaks at 800 * 15,360 = 12,288,000, which is 24 bits.
#
# WHY THE SUM AND NOT THE PEAK. A peak says a voice was capable of being
# loud on one sample; the sum says how much of the frame it actually
# filled. An envelope that fires for ten samples and one that holds for
# eight hundred have the same peak and differ by eighty times here.
#
# TWO frames late, and NOT one -- which is the one thing here that had
# to be traced rather than assumed. VIS_BASE and the pick are finished
# when the DRAW is finished, so a cart reads them the next frame. A
# frame's SOUND is not finished when its draw is: the draw takes about
# 220,000 of a frame's 720,000 clocks and the samples keep coming for
# the rest of it. The machine's order is frame_go, draw, write the
# answers back, run the cart -- so at the instant it writes, the newest
# COMPLETE frame of audio is the one before last. On glass and in the
# cross alike, for the same reason.
#
# Held one frame instead, heard.zol's bars stood a frame ahead of the
# sound that drew them: 6,555 pixels, while the totals themselves
# matched to the unit on every frame. A number can be right and still be
# read at the wrong time.
AUD_BASE = 14720                # AU_CHANNELS words, one a voice
AUD_MAX = 0xFFFFFF              # 24 bits: 800 samples at 15,360

OBJ_LIT = 8192                  # flags bit 13: the vertex word is a
                                # NORMAL, not a colour -- see LIGHT_DIR

OBJ_EDGE = 128                  # flags bit 7: OUTLINE this object.
                                # The rasterizer keeps WHICH OBJECT owns
                                # each pixel in a band-local identity
                                # plane, and the outline is drawn where a
                                # pixel's owner differs from the owner of
                                # the pixel to its left or above.
                                #
                                # The era's technique was to render every
                                # model a SECOND TIME, inflated and turned
                                # inside out -- twice the geometry, and
                                # wrong at every sharp corner, because an
                                # inflated hull does not know where the
                                # silhouette is. Edge detection over an
                                # identity buffer is a 2003-2005 idea.
                                #
                                # It costs NO CLOCKS. The band is already
                                # walked pixel by pixel on its way to the
                                # framebuffer (the previous band's flush
                                # rides the next band's clear), so the
                                # compare rides that walk. The pixel one
                                # row up arrives through a delay line of
                                # one row, which crosses band boundaries
                                # for free because the walk is continuous
                                # in screen order.
                                #
                                # Opt-in, and zero by default: an outline
                                # on everything is a look, not a feature.
# ---- GRADING: the curve on the way to the glass -------------------------
# The video head already sees every pixel with its address on the way to
# the panel. A table of 32 words -- one per 5-bit level -- turns the
# framebuffer's colour into anything at all on the way out, per channel:
#
#     out_r = table[r5] >> 16 & 0xFF     the levels are the INDEX and the
#     out_g = table[g5] >>  8 & 0xFF     word at each level is the OUTPUT
#     out_b = table[b5]       & 0xFF     colour, so the three channels get
#                                        three independent curves
#
# Warm interiors, bleached exteriors, a sick green in the flooded
# section; the lights failing without touching a single plate. Colour
# grading as a rendering step arrives in the real world around 2005, and
# it costs this machine almost nothing because the scanout was already a
# pixel pipeline.
#
# AND IT WIDENS THE OUTPUT. The framebuffer holds 5 bits a channel and
# the panel takes 8, so today a pixel leaves as (c5<<3)|(c5>>2) -- 32
# levels stretched over 256. Through the table each of those 32 levels
# names a full 8-bit value, so a curve can put them anywhere.
#
# GRADE_SRC is a DMEM address, and 0 means no grading: every cart written
# before this leaves the cell zero and leaves the glass exactly as it was.
# A table that would run past DMEM is refused whole, like every other
# pointer this machine takes.
GRADE_SRC = 12271
GRADE_WORDS = 32                # one word per 5-bit level

EDGE_RGB = 12270                # the outline's colour, 0xRRGGBB. Only
                                # read where OBJ_EDGE put an edge, so a
                                # cart that never sets the flag never
                                # sees this cell.

BG_SHADOW = 1 << 15             # ...that bit, in the plate word. Zero on
                                # every plate baked before this, so a cart
                                # that never bakes shadow reads 0 and is
                                # lit exactly as it always was.

CAM_PITCH = 6                   # camera pitch, 0..1023 (looking up and
                                # down joined the law in build 65; old
                                # carts leave the cell 0 and are exact)
CAM_X, CAM_Y, CAM_Z = 8, 9, 10  # camera position, Q16.16 world units
CAM_YAW = 11                    # camera heading, 0..1023 = full turn
CAM_ROLL = 12287                # camera BANK, 0..1023, applied last --
                                # about the view axis, after yaw and
                                # pitch. The low block (0..15) was full,
                                # so it lives with the other registers.
                                # Objects have had three axes since build
                                # 65; the camera had two, which is enough
                                # to walk and look and not enough to FLY.
                                # 0 leaves every existing cart exact.

# ---- the mover: how content gets bigger than the resident cart -----------
# A cart may carry a CRAM SEGMENT after its resident image -- megabytes of
# meshes, pose banks, rooms -- and page pieces of it into DMEM between
# frames. Four legislated cells:
#   DMA_SRC  word offset into the cart's CRAM segment
#   DMA_DST  DMEM word address to land at
#   DMA_LEN  words to move (0 or > DMA_MAX is a no-op)
#   DMA_GO   the cart writes 1; the machine performs the move and clears it
# The move happens ONCE per frame, AFTER the VM halts and BEFORE the GPU
# reads DMEM -- so a cart can page a mesh in and have it drawn the same
# frame, and the ordering is unambiguous for the cross. A request whose
# source or destination falls outside its memory moves nothing and still
# clears DMA_GO: a cart cannot wedge the machine with a bad pointer.
DMA_SRC, DMA_DST, DMA_LEN, DMA_GO = 12, 13, 14, 15

# ---- OVERLAYS: the cart stops being 4,096 instructions -------------------
# IMEM holds 4,096 instructions and that is the ceiling on how complicated
# a game may be -- not how much CONTENT it has (the mover and the card
# already made content unbounded), but how much CODE. A port of anything
# substantial runs out of program long before it runs out of world.
#
# So the mover gets a second destination. Four cells, its own shape:
#   OVL_SRC  word offset into the cart's CRAM segment
#   OVL_DST  IMEM word address to land at
#   OVL_LEN  instructions to move (0 or > OVL_MAX is a no-op)
#   OVL_GO   the cart writes 1; the machine performs it and clears it
#
# THE SAFETY IS THE FRAME MODEL, not a rule. The move happens at the
# mover's own instant -- after the VM halts, before the paint -- and every
# frame begins at PC 0. A cart therefore cannot overwrite the code it is
# standing on: it asks, its frame ends, and the NEXT frame starts at zero
# in the new program. Swapping code is swapping scenes.
#
# A request that would land outside IMEM moves nothing and still clears
# OVL_GO, exactly as the mover refuses a bad pointer.
OVL_SRC, OVL_DST, OVL_LEN, OVL_GO = 12276, 12277, 12278, 12279

# ---- FOG: the z-buffer already knows how far away everything is ---------
# Every pixel the rasterizer commits carries its depth. Blending that
# pixel toward a colour by its distance costs no new information and no
# multiplier -- the blend is in SIXTEENTHS, so it is shifts and adds --
# and it is the one change that makes every scene read as a place rather
# than as objects floating on a flat clear.
#
#   FOG_RGB    the colour distance fades toward (24-bit, quantised 555)
#   FOG_NEAR   the depth (z16) at which fog begins
#   FOG_SHIFT  0 = OFF. Otherwise thickness:
#                  t = clamp((z_px - FOG_NEAR) >> FOG_SHIFT, 0, 16)
#                  out5 = (c5 * (16 - t) + f5 * t) >> 4   per channel
#
# Fog applies to GEOM faces only -- never the clear, never the backdrop,
# and never the display list. The DL is the HUD plane and must not fade
# with distance whatever the cart sets; its triangles carry z = 0 and
# would be unfogged anyway, but a rule that holds by accident is not a
# rule.
# A backdrop is pre-rendered content that already contains whatever air
# its author wanted; fogging it again would be fogging a photograph. What
# this does is settle live geometry INTO that distance, which is exactly
# the seam a depth-composited room needs hidden.
FOG_RGB, FOG_NEAR, FOG_SHIFT = 12272, 12273, 12274

# ---- LOD: the far half of the same bargain -------------------------------
# Fog makes distance uniform in colour. Interpolating colour across a face
# that is about to be fogged into one anyway is work the eye cannot see --
# and it is the expensive work: a Gouraud face runs FOUR channels through
# the gradient divider (z, r, g, b) where a flat face runs one, which is
# why the bunny costs ~47% of a frame while 1,152 floor faces cost ~8%.
#
#   LOD_FLAT   depth (z16) past which Gouraud faces draw FLAT, using the
#              colour at vertex A. 0 = never; interpolate everywhere.
#
# Tuned against FOG_NEAR this is invisible and close to free: set it where
# the fog is already thick and the machine simply stops paying for detail
# nobody can resolve. The trick every late-generation console lived on,
# and the machine can do it itself rather than making each cart do it.
LOD_FLAT = 12275
OVL_MAX = 4096                  # a whole program in one frame if wanted

# ---- the backdrop: rooms the machine could never draw live ---------------
# If BG_SRC is nonzero, the frame does not clear to CLEAR_RGB: it clears
# to an IMAGE -- W*H words read from the cart's CRAM segment starting at
# word offset BG_SRC, one word per pixel, row-major:
#     word = (z16 << 16) | rgb555
# Color fills the framebuffer (555, replicated to 888 on display exactly
# like any pixel); z16 seeds the DEPTH BUFFER. Everything the frame then
# draws tests against that depth -- so an offline-rendered room occludes
# live geometry per-pixel: Resident Evil's trick without its mask-
# rectangle seams. The backdrop is the rasterizer's second front-end
# (docs/WINDOW-LAW.md): the same commit pipeline, fed by a burst reader
# instead of the edge walker.
BG_SRC = 7
BG_WORDS = W * H                # one word per pixel, 92160 per room
DMA_MAX = 4096                  # words per frame -- the copy has to fit in
                                # the gap before painting starts
CRAM_CART_BASE = 131040         # the segment's home in CRAM, above both
                                # framebuffers (each is (W+1)*H words).
                                # 131040 = 126 * 1040: LOGICAL-ROW
                                # ALIGNED, so every 63-word boot flush
                                # opens at a physical row base and the
                                # chip's write-pointer head start (the
                                # scribble law, boots 51-54) lands in
                                # the dead row tail the restride
                                # already skips. Geometry as armor.
CRAM_WORDS = 1 << 21            # 2M cart words addressable, 8 MB
# CRAM is 16 bits wide, so each 32-bit cart word occupies two CRAM cells:
# segment word i is at CRAM_CART_BASE + 2i (low half) and +2i+1 (high).

USER_BASE = 16                  # yours from here up to DL_BASE
DL_BASE = 12288                 # display list: [n_tris, then 7 words/tri]
DL_STRIDE = 7                   # x0 y0 x1 y1 x2 y2 rgb  (pixels, ints)
DL_MAX = 256                    # triangles per frame

# ---- the GEOM block: 3D, PS1-shaped --------------------------------------
# An object list right above the display list. Each object points at a
# mesh in cart DMEM; GEOM rotates (yaw), translates, camera-transforms,
# and perspective-projects its vertices, then feeds each face to the same
# rasterizer a DL triangle uses. DL triangles paint FIRST, then objects
# in list order, faces in mesh order -- painter's algorithm, no z-buffer,
# backface culling, whole-face near rejection. Exactly the PS1's deal.
#
# Mesh layout at mesh_base: [n_verts, n_faces,
#   then n_verts * 3 words: x y z, Q16.16 model space,
#   then n_faces * 2 words: (a | b<<10 | c<<20), rgb]
# An object whose mesh block falls outside DMEM is skipped whole.
OL_BASE = 14084                 # [n_objects, then OL_STRIDE words each]
OL_STRIDE = 6                   # mesh_base x y z angles flags -- the
                                # angles word packs THREE rotations:
                                # bits 9:0 yaw, 19:10 pitch, 29:20 roll
                                # (model -> world order: roll, then
                                # pitch, then yaw). Carts that wrote a
                                # plain yaw are exact by construction.
OL_MAX = 64                     # was 16, and the fabric hit it on its
                                # first outing: nine ground planes leave
                                # seven objects for a whole world. The
                                # cap was the sequencer's 5-bit counter,
                                # not a memory or a time limit -- DMEM
                                # above the list is 2,203 words free and
                                # 64 objects want 385.
OBJ_CULL = 1                    # flags bit 0: cull clockwise faces
OBJ_TEX = 4
# ---- THE BLEND-ORDER LAW (roadmap 15, settled build 91) ------------------
# Legislated BEFORE the tile's silicon exists, because tiling changes the
# order of pixel writes and a reordering is not something you discover
# after the fact -- you discover a seam.
#
# It rests on one fact: A PIXEL BELONGS TO EXACTLY ONE TILE. So if a
# tile's face list keeps display-list order, the fragments arriving at
# any pixel are the same subsequence of the global order they are now.
# The rule that follows is the whole law:
#
#     1. THE BIN PRESERVES DISPLAY-LIST ORDER.
#     2. ONE PASS, in that order. A face without OBJ_BLEND depth-tests
#        and writes colour AND depth (`z <= stored`, so ties go to the
#        later face, exactly as today). A face WITH OBJ_BLEND depth-tests
#        against whatever depth is standing, blends colour, and WRITES NO
#        DEPTH.
#        AMENDED from "two passes per tile" (build 92, when the silicon
#        landed). A second pass means walking the object list again per
#        band, which is precisely the cost the object bin and the vertex
#        buffer were built to remove -- paying it back for ordering the
#        cart can do itself is a bad trade. So the obligation moves to
#        the cart, alongside the sort it already owes:
#            SUBMIT ALL OPAQUE GEOMETRY BEFORE ANY BLENDED GEOMETRY,
#            AND BLENDED GEOMETRY BACK TO FRONT.
#        Interleave them and a blended face drawn before the opaque face
#        behind it composites against the clear and is then overwritten,
#        because it wrote no depth to defend itself. That is not a bug,
#        it is the order the cart asked for.
#     3. CLIPPING CONFINES WRITES, NEVER ARITHMETIC. With OBJ_LODSPAN the
#        mip is held across a row from its first edge-covered pixel; if a
#        tile were allowed to shorten the row, each slice would choose its
#        own level and one face would be textured two ways across a seam.
#        (Latent today: measured 0 of 2,284 lodspan faces have a level
#        that varies along a row. Legislated anyway -- content will.)
#
# Because blended faces write no depth they cannot occlude each other, so
# their composite order IS the display-list order the cart chose. The
# cart sorts back to front, as every console of this era required. What
# the machine promises in exchange is that the order it was given is the
# order it draws, on all three machines, forever.
#
# Proven, not asserted: tests/test_tiled.py renders every cart twice --
# immediate and tile by tile -- and demands bit equality, with each test
# paired against a deliberately mis-ordered bin that must break it.
OBJ_BLEND = 32                  # flags bit 5: this object composites in
                                # the blended pass. Per-face alpha rides
                                # bits 28:24 of the face colour word (0..16
                                # sixteenths, 16 = opaque); the low 24 bits
                                # stay the colour, so every mesh ever
                                # written keeps its meaning with alpha 0.
                                # NOTE: alpha 0 means INVISIBLE, so a
                                # blended object must set it explicitly --
                                # the same opt-in shape as OBJ_TINT, and
                                # for the same reason.
BLEND_A_SHIFT, BLEND_A_MASK = 24, 0x1F
BLEND_MODE_SHIFT, BLEND_MODE_MASK = 29, 0x3   # bits 30:29 of the same word
BLEND_LERP = 0                  # dst*(16-a) + src*a  -- what blending has
                                # always meant here, and mode 0 so every
                                # blended face ever written keeps meaning it
BLEND_ADD = 1                   # dst + src*a, SATURATED at 31.
                                # The one mode the lerp cannot fake: lerp
                                # can only move a pixel TOWARD the source
                                # colour, so it can darken a bright pixel
                                # and can never brighten one. Glows, fire,
                                # muzzle flash, light shafts -- everything
                                # that should read as EMITTED rather than
                                # painted -- needs a pixel to end up
                                # brighter than either operand.
                                #
                                # It is nearly free because the blend
                                # already computes dst*16 + (src-dst)*a:
                                # additive is the SAME multiply with src
                                # instead of src-dst. One mux, plus the
                                # saturate the lerp never needed.
                                # Modes 2 and 3 are unclaimed.

# ---- THE TILE, step 1: the depth plane is a BAND, not a screen -----------
# The full-screen depth plane was 1,483,776 bits -- 61% of every block
# memory bit on the device -- so the paint now runs once per band and the
# plane only has to exist for the band. Colour still goes straight to CRAM
# per pixel exactly as before: all of the memory was in the DEPTH, and not
# needing on-die colour is what makes this step small.
#
# BANDS ARE FULL WIDTH, deliberately. A triangle row is then wholly inside
# a band or wholly outside it, never divided, so OBJ_LODSPAN cannot choose
# a different mip either side of a seam and the walk may simply be clamped.
# Tiles that divide rows (step 2, 64x32) lose that and must mask coverage
# after the span arithmetic instead -- see gpu._fill's clip/naive_clip.
#
# TILE_H must divide H exactly: the last band is not special-cased.
TILE_H = 32
TILE_ROWS = H // TILE_H
OBJ_LODSPAN = 16                # pick the mip level ONCE PER SPAN, at
                                # the row's first covered pixel, instead
                                # of per pixel. Five of the crown's
                                # thirteen beats are the per-pixel level
                                # (four gradient maxima and the pick), so
                                # this is 13 beats -> 8: textured fill
                                # goes 3.3 -> 5.4 Mpix/s, and a full
                                # screen at 60 needs 5.53. The cost is
                                # that a span crossing a mip boundary
                                # takes one level for its whole length --
                                # which is why it is a FLAG and not the
                                # new law: mipmaps exist here because the
                                # player saw shimmer.
OBJ_TINT = 8                    # a textured face MODULATES by its colour
                                # word instead of ignoring it. Opt-in
                                # because it has to be: every textured
                                # mesh already written puts ZERO there
                                # (tex.zol, microtex.zol), so modulating
                                # unconditionally would paint them black.
                                # texel * (tint+1) >> 5 -- the +1 is what
                                # makes 31 pass the texel through exactly
                                # instead of darkening white to 30.
OBJ_OTINT = 64                  # flags bit 6: the tint comes from the
                                # OBJECT, not from each face's colour
                                # word -- bits 31:17 of this same flags
                                # word, as 5:5:5.
                                #
                                # This is the difference between a lit
                                # SURFACE and a lit ACTOR. With OBJ_TINT
                                # the light is baked into the mesh, so a
                                # character who walks from a bright room
                                # into a dark one has to have all nf of
                                # its colour words rewritten -- which is
                                # why every actor in this tree is lit for
                                # exactly one condition and stays that
                                # way. With OBJ_OTINT its light is ONE
                                # WORD in the object slot, which a cart
                                # can compute per frame from where the
                                # actor is standing.
                                #
                                # And unlike OBJ_TINT it modulates the
                                # UNTEXTURED branch too, because that is
                                # what actors here are made of.
OBJ_OTINT_SHIFT = 17            # the 15 bits are R 31:27, G 26:22, B 21:17                     # flags bit 2: the mesh carries per-vertex
                                # TEXEL coordinates where Gouraud would
                                # carry colors -- one word per vertex,
                                # u | (v << 8), texel units 0..31 -- and
                                # faces sample THE TEXTURE PAGE instead
                                # of interpolating color. The sampled-
                                # field law: u and v ride the red and
                                # green interpolator channels (CFP fixed
                                # point, clamped 0..31 exactly like a
                                # color channel -- the clamp IS the
                                # texel clamp), so the machine grows no
                                # new arithmetic, only a 32x32 page:
TEX_SRC = 12286                 # if nonzero: a DMEM word address of 680
                                # words -- THE MIP CHAIN: 32x32 (512w),
                                # 16x16 (128w), 8x8 (32w), 4x4 (8w),
                                # each row-major RGB555, two texels per
                                # word, low half first -- copied into
                                # the page before each paint. 0 = keep.
                                # EVERY PIXEL selects its own level
                                # (the per-pixel gradient law below) --
                                # tilted faces sample coarser and the
                                # minification shimmer dies.
# ---- MORE THAN ONE PAGE (build 92) --------------------------------------
# One resident 32x32 page was the machine's most generation-typical
# limit: N64 fought a 4 KB texture cache and its games look muddy for
# exactly that reason, and Zeta's 3.84 KB was the same constraint. Every
# textured object in a frame had to share one image.
#
# The tile returned ~118 M10K blocks, so this is now the cheapest gap on
# the board to close: EIGHT pages resident, 8 x 2,048 x 15 = 245,760
# bits, about 24 of them.
#
#   TEX_PAGE   which SLOT the load at TEX_SRC lands in (0..TEX_PAGES-1)
#   flags 10:8 which slot an OBJECT samples
#
# Both default to zero, so every cart ever written keeps its meaning: it
# loads page 0 and samples page 0, exactly as before. A cart fills its
# pages one per frame at startup -- the loader moves 680 words and there
# is no reason to move more than one page's worth in a frame -- and they
# then persist until overwritten.
#
# NOT filtering. Point sampling with mips is a CHOICE: it keeps PS1's
# sharpness and adds N64's stability, which is the better half of each,
# and bilinear would want four fetches and three lerps a pixel on a die
# whose DSPs were 66/66 from the crown until build 96 freed nineteen.
TEX_PAGES = 20                  # was 16. The SELECTOR is bits 12:8,
                                # which took flag bit 11 from the free
                                # set.
                                #   DOUBLING AGAIN COSTS 34 M10K, NOT 16.
                                # The note here used to read "doubling
                                # costs 16", which was true of the 8->16
                                # step it was written for and was read
                                # later as if it were a rate. It is not:
                                # the table is TEX_PAGES * TEX_STRIDE
                                # words of 15 bits, an M10K holds 640 of
                                # those, so 16 pages is 21,760 words and
                                # 34 blocks -- and 32 pages is 68. With
                                # 29 blocks free after build 96 the
                                # doubling does not fit; 24 pages does,
                                # at +17, and needs the selector widened
                                # to five bits with a clamp, because 24
                                # is not a power of two.
                                #   A COST WRITTEN AS AN ABSOLUTE IS
                                # READ AS A RATE. Say which step it was.
                                #   AND 20, NOT 24, BECAUSE OF TIMING AND
                                # NOT SPACE. 24 fits -- 294 of 308
                                # blocks -- and MISSES TIMING: setup
                                # slack went 2.600 -> 0.251 ns at the
                                # 85C corner and to -0.246 at 0C, which
                                # is a core that works warm and glitches
                                # cold.
                                #   AND IT IS A CLIFF, NOT A SLOPE. The
                                # first reading of it was "15 blocks
                                # cost 2.35 ns, so about 0.157 a block",
                                # which is a rate fitted to two points
                                # and it predicted 1.4 ns of slack at
                                # 20 pages. Measured: 2.925 at 85C and
                                # 2.362 at 0C -- BETTER than the 2.600
                                # that 16 pages had. So 16 -> 20 costs
                                # nothing and 20 -> 24 costs everything,
                                # and something changes in how the tool
                                # builds the table between 41 blocks and
                                # 49. Where exactly is unmeasured; it
                                # would take a fit at 22 to find out.
                                #   Capacity was never the constraint
                                # here and the block count said nothing
                                # about the one that was. Going past 20
                                # wants the texture read pipelined a
                                # stage deeper, which is a build of its
                                # own.
                                #   SO 24 AND NOT 32, at +17 of the 29
                                # free after build 96. 24 IS NOT A POWER
                                # OF TWO and the selector is five bits,
                                # so a cart can name a page that does
                                # not exist. It reads as page 0, which
                                # every cart has and which is wrong in a
                                # way that stays put -- clamping to 23
                                # instead would show whatever the last
                                # slot happened to hold, and that is a
                                # bug that moves when unrelated code
                                # changes. Legislated here so both
                                # machines do the same thing.
TEX_PAGE = 12268                # slot selector for the next page load
OBJ_PAGE_SHIFT, OBJ_PAGE_MASK = 8, 31


def tex_page(sel: int) -> int:
    """A page selector, resolved. Out of range reads as page 0 --
    TEX_PAGES is not a power of two and the field holds 0..31."""
    sel &= OBJ_PAGE_MASK
    return sel if sel < TEX_PAGES else 0

TEX_W = 32                      # level 0 is TEX_W x TEX_W texels
TEX_WORDS = 680                 # the whole chain, in words
TEX_STRIDE = 2 * TEX_WORDS      # ...and in TEXELS: 1024 + 256 + 64 + 16.
                                # THE PAGE STRIDE IS THE PAGE, not the
                                # next power of two. It was 2048 because
                                # a concatenation is free and a multiply
                                # is not -- and that convenience cost
                                # 8.1 M10K blocks, a third of the texture
                                # memory, holding nothing.
                                #
                                # Multiplying by 1360 is four shifts and
                                # three adds, on a THREE-BIT page number.
                                # That is the trade, and it is the first
                                # instance of a category worth hunting:
                                # silicon that exists only because an
                                # address scheme was convenient.
TEX_MIP_OFF = (0, 1024, 1280, 1344)   # texel offset of each level

# ---- THE CROWN: perspective-correct sampling -----------------------------
# A projected quad's texture map is projective; one affine plane per
# triangle approximates it, and the two halves disagree along the
# diagonal (the crease the player read on boot 68's glass). The cure is
# the identity: u/z, v/z, 1/z ARE affine-legal. So, integer-exactly:
#
#   per vertex   w  = max(tdiv(PERSP_NUM, vz), 1)   (the projection z)
#   per triangle e  = msb_index(wa | wb | wc); each w' = w >> (e - 11)
#                 (<< if negative) -- the octave normalize: the nearest
#                 vertex lands in [2^11, 2^12) and the interpolators
#                 never see more than 17 bits
#   the three color channels carry u5*w', v5*w', w' (CFP=8 planes, the
#   SAME interpolators, the same rounding half-quantum)
#   per pixel    W  = clip(Wacc, 256, 2^20 - 1)
#                e  = msb_index(W); N = W << (19 - e)   (N in [2^19, 2^20))
#                R0 = RECIP_ROM[(N >> 12) & 127]        (9-bit seed)
#                R1 = (R0 * ((1 << 29) - R0 * N)) >> 22 (one Newton step,
#                                                        ~2^-14 relative)
#                u_cfp = clip((clip(Uacc, -2^26, 2^26-1) * R1
#                              + (1 << (e + 6))) >> (e + 7), 0, 8191)
#   per pixel LOD (the quotient rule, divided through by W so the
#   thresholds become SHIFTS):
#                m = max |(dU << 8) - u_cfp * dW| over the four
#                    (dU/dx, dU/dy, dV/dx, dV/dy) pairings
#                level 1 at m >= W << 5, 2 at << 6, 3 at << 7
#   then the texel is u_cfp >> 8 (already the channel clamp's 0..31).
#
# Both machines run THIS algorithm -- the law is the seed table and the
# shift discipline, not "true division"; the cross holds bit-for-bit.
# Where a single triangle spans more depth than 2^17:1 the far w' hits
# zero and W clamps at 256: perspective degrades lawfully, identically,
# in both machines. Cut such spans in content.
PERSP_NUM = 1 << 30
RECIP_ROM = tuple((1 << 28) // ((1 << 19) + (i << 12) + (1 << 11))
                  for i in range(128))
OBJ_GOURAUD = 2                 # flags bit 1: the mesh carries per-vertex
                                # colors after the vertex block --
                                # [nv, nf, nv*3 verts, nv vcolors (24-bit),
                                #  nf*2 faces] -- and faces interpolate
                                # them (each 5-bit channel plane-
                                # interpolated exactly like depth, CFP=8
                                # fixed point, clamped 0..31); the face
                                # rgb word is ignored. Without the flag,
                                # the classic flat layout and behavior.
CFP = 8
MESH_NV_MAX = 256               # 10-bit face indices
MESH_NF_MAX = 512
FOCAL = 256                     # projection: sx = W/2 + tdiv(x*FOCAL, z)
ZNEAR = 1 << 14                 # 0.25 units; a face touching closer is out
GUARD = 2048                    # a vertex projecting outside +/-GUARD
                                # PIXELS in either axis invalidates its
                                # faces -- with SUB fraction bits that is
                                # exactly the int16 coordinate range

# ---- the precision laws: subpixel vertices + the depth buffer ------------
# Projected coordinates carry SUB fraction bits (1/16 pixel), and the
# rasterizer samples every triangle at PIXEL CENTERS ((px<<SUB)+HALF) --
# geometry is rock-solid under motion instead of snapping to the grid
# (the PS1's wobble). Display-list coordinates stay integer pixels and
# are shifted left by SUB on entry.
#
# Depth: per-vertex 16-bit z (camera z >> ZSHIFT, saturated), then a
# per-PIXEL plane-equation interpolation -- constant per-face depth
# misorders where a slanted face's depth range straddles a neighbor
# (seen on glass, boot 9). With vertices A,B,C in subpixel coords and
# area2 = (x1-x0)*(y2-y0) - (y1-y0)*(x2-x0)  (the cull area):
#   dzdx = clamp(tdiv(((z1-z0)*(y2-y0) - (z2-z0)*(y1-y0)) << ZFP, area2))
#   dzdy = clamp(tdiv(((z2-z0)*(x1-x0) - (z1-z0)*(x2-x0)) << ZFP, area2))
# (clamped to +/-ZGRAD_MAX; both 0 when area2 == 0), and at a sample
# point (sx, sy):
#   z_px = clamp((z0 << ZFP) + (sx-x0)*dzdx + (sy-y0)*dzdy >> ZFP,
#                0, ZFAR)
# A pixel draws iff z_px <= the stored depth, then stores z_px. The
# buffer clears to ZFAR. Display-list triangles carry z0 = 0 with zero
# gradients -- drawn first, they occlude 3D (HUDs on top), and equal
# depths let the later triangle win, so pure-DL carts render exactly as
# under painter's order.
SUB = 4
HALF = 1 << (SUB - 1)
ZSHIFT = 7                      # 1/512 world unit per depth count, range
                                # 128 units -- coarse steps let tangent
                                # surfaces flicker through each other
ZFAR = 0xFFFF
ZFP = 8
ZGRAD_MAX = 1 << 24

# All GEOM math is integer-exact in both machines:
#   rotate:  xr = s32((x*cos - z*sin) >> 14)   (arithmetic shift, wrap 32)
#   cos/sin: SIN_Q14, 1024 entries per turn; cos(a) = sin(a + 256)
#   project: tdiv truncates toward zero; z >= ZNEAR guaranteed first
# The table is BUILT from its first quadrant by exact folding -- the
# silicon stores only the 257-entry quarter wave, so the fold must be the
# law, not an accident of float symmetry.
import math as _math
SIN_QUARTER = [int(round(_math.sin(i * _math.tau / 1024) * 16384))
               for i in range(257)]
SIN_Q14 = [(SIN_QUARTER[i & 255] if i < 256 else
            SIN_QUARTER[512 - i] if i < 512 else
            -SIN_QUARTER[i - 512] if i < 768 else
            -SIN_QUARTER[1024 - i]) for i in range(1024)]


def tdiv(a: int, b: int) -> int:
    """Truncate-toward-zero division -- what a hardware divider does."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q

# ---- the SND block: 4-channel fantasy-console audio ------------------------
# 48,000 Hz mono, signed 16-bit -- exactly 800 samples per frame (the video
# and audio clocks are the same law: 720,000 core clocks / 900 = 800).
# The cabinet/silicon latch the 8 register words at AU_BASE once per frame
# AFTER the VM runs, then synthesize; channel phase persists across frames.
#
# Channels 0,1: pulse   word0 = phase increment (24-bit; f = inc*48000/2^24)
#                       word1 = vol[3:0], duty[5:4] (12.5/25/50/75%)
# Channel  2:   triangle word1 = vol[3:0]
# Channel  3:   noise    15-bit LFSR (taps 0,1; seed 1 at reset), stepped on
#                        each phase wrap; word1 = vol[3:0]
#
# Exact synthesis per 48 kHz tick (all integer, per channel):
#   phase = (phase + inc) & 0xFFFFFF
#   pulse:    out = +vol*1024 if phase[23:21] < (1,2,4,6)[duty] else -vol*1024
#   triangle: tri = ~phase[22:15] if phase[23] else phase[22:15]  (8-bit)
#             out = (tri - 128) * vol * 8
#   noise:    out = +vol*1024 if lfsr&1 else -vol*1024
#   wave:     out = wave[phase[23:16]] * vol * 8   (ctrl bit 6, any channel)
#   sample = (ch0 + ch1 + ch2 + ch3) >> 2      (always fits int16)
# MOVED from 14184 (build 92). The object list is OL_BASE + 1 +
# OL_MAX*OL_STRIDE = 14084..14468, and when OL_MAX rose 16 -> 64 in build
# 89 it grew straight through the audio registers: object SIXTEEN's entry
# spans 14181..14186, so a cart with seventeen objects overwrote its own
# sound. It survived because fabric.zol -- the only cart with many
# objects -- peaks at exactly sixteen, ending at 14180. Four words short,
# every gate green.
# The amendment's own note read "DMEM above the list is 2,203 words free
# and 64 objects want 385": correct against the TOP of memory and blind
# to what sat in between. tests/test_dmem_map.py now checks every
# legislated region against its NEIGHBOUR, which is the cap that binds.
AU_BASE = 14480                 # channels x 2 words: inc, ctrl
# ---- SIXTEEN VOICES (build 92) ------------------------------------------
# Four channels was the last axis where this machine sat behind every
# console on the table -- PS1 had 24, Saturn 32, N64 about 20. It was
# never a memory problem; it was that nobody had legislated the CLAMP.
#
# Channels 0..3 keep their character exactly: two pulses, a triangle, a
# noise LFSR, each able to become a wavetable voice with ctrl bit 6.
# Channels 4..15 are VOICES ONLY -- they have no oscillator of their own
# and read the wave page always. That keeps every existing cart's sound
# bit-identical (they write 0..3 and nothing else) and makes the new
# twelve exactly what the sampled field is for.
#
# THE CLAMP IS THE PRICE. Four channels peak at 4 x 15,360 = 61,440 into
# a >>2, which is 15,360 -- comfortably inside int16, so the mix could
# simply wrap and never did. Sixteen peak at 245,760, and >>2 is 61,440,
# which is NOT. So the sum saturates at the end:
#     out = clamp(mix >> 2, -32768, 32767)
# With four channels the clamp can never fire, so it costs nothing and
# every cart written before it stays exact. It cannot be skipped either:
# without it a loud sixteen-voice frame wraps to the opposite sign, which
# is the ugliest failure an audio path has.
AU_CHANNELS = 16
AU_TONE_CHANNELS = 4            # 0..3 have oscillators; 4..15 are voices
AU_CLAMP = 32767

# ---- THE EVENT LIST: sub-frame automation, sample-exact ------------------
# The reason this machine had no envelopes was never the mixer. It was the
# FRAME CONTRACT: audio registers latch once per frame, so a cart could
# change a volume sixty times a second against an engine running at
# forty-eight thousand. A ten-millisecond attack is six tenths of a frame
# and simply cannot be expressed. PS1 answered that with fixed hardware
# ADSR shapes; N64 answered it by burning CPU in software.
#
# Zeta can do something neither could, and it falls straight out of what
# the machine already is. SAMPLES_PER_FRAME is 800 EXACTLY, and the whole
# machine is bit-exact across three implementations. So the cart does not
# have to send a VALUE once a frame -- it can send a TIMELINE:
#
#   AU_EV_BASE     count, 0..AU_EV_MAX (anything else is read as 0)
#   then per event, two words:
#     w0   bits  9:0   sample offset within the frame, 0..799
#          bits 13:10  channel, 0..15
#          bit     14  0 = write inc (pitch), 1 = write ctrl (vol/flags)
#     w1           the value, exactly as the register takes it
#
# At sample s the machine applies every event whose offset has been
# reached, IN LIST ORDER, and then synthesizes s. Events are expected in
# ascending offset; one that goes backwards simply fires with its
# predecessor, which is deterministic rather than an error.
#
# WHAT THIS BUYS, and why it is not just ADSR: the shape is arbitrary.
# Attack, decay, tremolo, pitch bends, drum transients, a note that
# starts 3 samples into a frame because that is where the beat fell --
# any automation a composer can describe, at sample resolution, and
# BIT-IDENTICAL on the law and on glass forever. No console of either
# generation could place a parameter change at a known sample.
#
# The cart still writes once per frame. It just writes intent instead of
# state -- the same "one description, many rates" the texture page and
# the wave page already are.
AU_EV_BASE = 14512
AU_EV_MAX = 64                  # events per frame; 1 + 64*2 = 129 words
AU_EV_OFF_MASK = 0x3FF          # w0 bits 9:0   sample offset
AU_EV_CH_SHIFT = 10             # w0 bits 13:10 channel
AU_EV_CTRL_BIT = 1 << 14        # w0 bit 14     0 = inc, 1 = ctrl

# ---- THE VOICE: the sampled field at 48 kHz ------------------------------
# The rasterizer's texture unit is an accumulator walking a bounded table
# (docs/WINDOW-LAW.md's field law). So is this. The four channels above
# walk tables the silicon knows by heart -- a square, a triangle, an LFSR;
# set ctrl bit 6 and the channel walks a table the CART wrote instead, at
# the same 24-bit phase, by the same law. One primitive, two rates:
# 43.2 MHz through the page, 48 kHz through the wave.
#
#   ctrl bit 6 (AU_WAVE): this channel is a wavetable voice
#   phase advances exactly as always; the sample is
#       s8 = wave[(phase >> 16) & 255]        (signed 8-bit)
#       out = s8 * vol * 8                    (the triangle's own scale,
#                                              so the mix still fits)
# Duty and the LFSR are ignored while the bit is set -- a wave channel is
# a wave channel, on any of the four.
# ---- THE CARD: content beyond the boot image -----------------------------
# The mover pages CRAM (which arrived at boot) into DMEM. This pages the
# SD CARD into DMEM -- the whole card, not the 8 MB the console booted
# with -- and it is what lets a cart save, stream rooms, and hold a world
# larger than its own delivery.
#
# Five cells, the mover's own shape:
#   SD_SLOT  the data slot to read (a file the .json declares)
#   SD_OFF   word offset within that slot's file
#   SD_DST   DMEM word address to land at
#   SD_LEN   words to move (0 or > SD_MAX is a no-op)
#   SD_GO    the cart writes 1 to READ the card into SD_DST, or 2 to
#            SAVE SD_LEN words FROM SD_DST back to the slot. The machine
#            clears it when the transfer has completed, so polling SD_GO
#            for zero is the whole protocol in both directions. One cell,
#            one poll, one legislated wait -- a save is a read with its
#            arrow reversed, and nothing else about it is special.
#
# THE SAVE. Without it nothing survives a power cycle and no game can
# exist; with it the card is the machine's memory as well as its library.
# A save is legislated exactly like a read: latched at the mover's
# instant, completed SD_LATENCY frames later, one transfer in flight,
# a bad request refused with nothing moved. The law models the slot
# image being REWRITTEN, so a cart that saves and reads back gets what
# it wrote -- on both machines, which is what keeps saves inside the
# cross rather than beside it.
#
# THE LEGISLATED LATENCY. The mover completes inside its own frame; a
# card cannot. Real SD latency varies, and variable latency would put the
# two machines' memories out of step -- the cross would fail on timing
# rather than on truth. So the wait is legislated, not measured: a
# request latched at the end of frame N lands at the end of frame
# N + SD_LATENCY, and the silicon WAITS if the card was quicker. The
# machine is deliberately slower so that it is deterministic, which is
# the same bargain the whole console runs on.
#
# One request at a time. A request issued while another is in flight is
# refused (SD_GO cleared, nothing moved), so no queue can build up and
# no cart can wedge the machine with a bad pointer -- exactly the mover's
# guarantee.
#
# The law models the card: a cart carries its slot images the way it
# already carries its CRAM segment, so machine 1 can answer a read
# exactly. Reads past the end of a slot deliver zeros, which is a
# defined answer, not an error.
SD_SLOT, SD_OFF, SD_DST, SD_LEN, SD_GO = 12280, 12281, 12282, 12283, 12284
# ---- the SCANOUT COMPOSITOR: transparency without a framebuffer read ------
# Blending needs the destination pixel, and this machine's framebuffer
# lives in external CRAM behind a WRITE path -- the paint side cannot
# read it back. But at SCANOUT the finished picture is already streaming
# past a pixel per clock with its coordinates in hand, so the blend
# happens there instead, and never touches the framebuffer at all.
#
#   CO_BASE      how many rectangles are live (0..CO_MAX)
#   +1 + 3k      x0 | (x1 << 10)
#   +2 + 3k      y0 | (y1 << 10)          both bounds INCLUSIVE
#   +3 + 3k      rgb | (alpha << 24)      alpha in SIXTEENTHS, 0..16
#
# Alpha in sixteenths keeps it to shifts and adds -- NO multiplier, which
# is decisive: the DSPs have been 66/66 since the crown.
#
# LEGISLATED SIMPLIFICATION: rectangles do not blend with each other. The
# LAST live rectangle covering a pixel wins, so the hardware is a
# priority mux and ONE lerp rather than a chain of four, which is what
# keeps the combinational path short enough to meet timing at scanout.
#
# WHERE THE LAW APPLIES IT, settled before building: the compositor sits
# between the framebuffer and the panel, so each gate sees the side it
# models. CROSS compares painted framebuffers and is correctly blind to
# it. GLASS compares the scanned stream and therefore sees it -- which is
# why the cabinet has both framebuffer() and panel().
CO_BASE = 12244
CO_MAX = 4
CO_STRIDE = 3


# THE CARD SIGNS ITS OWN DELIVERY (cart_loader.v's trick, which is what
# broke boots 17-23 open): two words of hardware counters, written every
# frame, so the console can report where a card read actually stops
# instead of us inferring it from a colour. HARDWARE ONLY -- the law
# writes zeros here, because machine 1 has no APF to count. A probe cart
# reading these is therefore an instrument, not a gated cart.
#   word 0: [7:0] ds_read pulses issued   [15:8] ds_ack seen
#           [23:16] ds_done seen          [26:24] last err code
#   word 1: [15:0] bridge writes into our window (UNGATED, so a write
#                  that arrives when we did not ask still counts)
#           [31:16] bridge writes anywhere at all
#   word 2: [15:0] words actually CAPTURED into the FIFO. Against word
#                  1's ungated count this is the whole story of a
#                  dropped transfer: arriving and being kept are two
#                  different things, and only the difference names the
#                  bug.
CARD_DIAG = 12264
#   word 3: [7:0] the MEASURED latency of the last completed request,
#                 in frames -- request latched to card ready. This is
#                 the number SD_LATENCY should be legislated from.
CARD_DIAG_WORDS = 4
SD_READ, SD_SAVE = 1, 2       # SD_GO's two directions
# DO NOT ASK THE CARD IN THE FIRST SECOND. A read issued at frame 1
# returns zeros on glass, every time, while the identical read at frame
# 60 returns the file -- the console is up long before the card is. Carts
# that load state at boot should wait ~1 s (build 85's readings: the save
# demo read zero at frame 1 through three power cycles, and read 111
# correctly the moment it was moved to frame 60). This is a property of
# the device, not of the law, so machine 1 cannot see it -- which is
# exactly why it is written here.
SD_MAX = 1024                   # words per request. The mover's ceiling is
                                # 4096, but a card request must be HELD in
                                # a staging buffer until its legislated
                                # frame, and 4096 words is 13 of the
                                # device's 308 M10K blocks -- which it
                                # does not have. A cart streams more by
                                # asking more often; this is the price of
                                # the buffer, written where it is paid.
SD_SIM_SLOTS = 4                # THE MODELLED CARD (zeta/silicon.py's hex
SD_SIM_SLOT_WORDS = 4096        # image and silicon/card_model.v) is bounded:
                                # slots 0..3, SD_MAX words each. Machine 1
                                # would happily serve any slot number, so
                                # the harness REFUSES a cart that asks for
                                # more rather than letting the two machines
                                # quietly disagree about a card neither can
                                # see. Real hardware is bounded by the
                                # .json's slot table, not by these.
SD_LATENCY = 4                  # frames from latch to landing. FOUR was
                                # my first estimate, and when the glass
                                # refused it I assumed the card was slow
                                # and raised this to 30. The MEASUREMENT
                                # said otherwise: CARD_DIAG's fourth word
                                # reported a latency of ONE FRAME. The
                                # card was never slow; the drain in
                                # card_apf.v handed zcard each word one
                                # cycle late. So four frames stands, now
                                # as a reading with 4x margin instead of
                                # a guess -- which is what the diagnostic
                                # word exists for.
                                # This remains the ONE place the law
                                # asserts a hardware timing property
                                # instead of deriving it, which is exactly
                                # why it had to be measured on glass.

AU_WAVE = 64                    # ctrl bit 6
WAV_SRC = 12285                 # if nonzero: a DMEM word address of
                                # WAV_WORDS words, copied into the wave
                                # page before each frame's synthesis
                                # (0 = keep what is loaded), exactly like
                                # TEX_SRC feeds the page
WAV_W = 256                     # samples in the table, phase[23:16]
WAV_WORDS = WAV_W // 4          # four signed bytes per word, low byte
                                # first: word i holds samples 4i..4i+3

# ---- THE WAVE BANK: eight pages, one chosen per voice --------------------
# Sixteen voices sharing ONE table is a choir, not an orchestra: every
# channel had the same timbre and the only thing a cart could vary was
# pitch and volume. That is the audio side of the exact limit the texture
# pages closed for the rasterizer -- "every object in a frame must share
# one image" -- and it closes the same way, because it is the same law.
# A bounded window over a table, and now the window may sit in one of
# eight places.
#
#   WAV_SRC points at a BANK of up to WAV_PAGES consecutive pages
#   ctrl bits 10:8 choose which page THIS channel walks
#
# Both default to zero, so every cart written before this reads page 0 --
# the single page at WAV_SRC, byte for byte what it had. Nothing about an
# existing stream moves.
#
# THE PAGE IS A LOAD-TIME PROPERTY, NOT A REGISTER. vol, duty and the
# wave bit can be re-aimed at any sample by the event list; the page
# cannot, and this is legislated rather than accidental. A page is 2,048
# bits copied into a voice's private table between frames, and there is
# no instant during synthesis at which that copy could be re-made without
# stalling the mix. So the page is read from the register ctrl word only.
# A cart changes a voice's timbre on a frame boundary, which is where an
# instrument change belongs; it changes a voice's ENVELOPE at the sample,
# which is where an envelope belongs.
#
# If WAV_SRC is zero, or a channel's chosen page would run past DMEM,
# that channel keeps the table it already had -- the same rule WAV_SRC
# has always had, now asked once per voice.
WAV_PAGES = 8
AU_PAGE_SHIFT, AU_PAGE_MASK = 8, 7

# ---- the loader signature: eight words the SILICON owns ------------------
# On hardware the cart arrives over the Pocket's bridge, and cart_loader.v
# signs its own delivery into these cells before releasing the console:
#   +0 magic 0x5A455441 ('ZETA')   +3 zero-data writes into DMEM 0..4095
#   +1 words accepted              +4 writes seen outside the declared
#   +2 accepted into DMEM 0..4095     bridge window (observed, ignored)
#                                  +5 last such foreign word index
# A cart may not use them: they are overwritten every boot. The Python
# law has no loader, so under the VM they simply stay zero -- carts that
# read them are reading a hardware fact, not a legislated value.
LOADER_SIG = 16376
LOADER_SIG_WORDS = 8
LOADER_SIG2 = 11700             # a MIRROR of the signature, written into
                                # the one DMEM region hardware has proven it
                                # delivers intact -- so the loader's
                                # testimony survives even if the top of
                                # memory does not
LOADER_BUILD = 100              # bumped per bitstream: word +7 of the
                                # signature, so a cart can say WHICH core
                                # it is running on.
                                #   AND IT HAPPENED AGAIN: 93 shipped on
                                # FIVE bitstreams -- the texture stride,
                                # the grade table, the outline, radix-4,
                                # the texture ladder -- before build 94
                                # (spec.VIS_BASE) bumped it.
                                #   THE REASON IS STRUCTURAL, not
                                # forgetfulness, and it is worth stating
                                # because it will cause the next lapse
                                # too. ONLY REAL HARDWARE WRITES THIS
                                # SIGNATURE: pocket/cart_loader.v is not
                                # in the Verilated sim and the law does
                                # not emulate it, so a cart that GATES on
                                # the build number behaves differently on
                                # the Pocket than on the two machines
                                # that can be checked -- and stops being
                                # crossable, which costs more than the
                                # gate is worth. So nothing gates on it,
                                # so nothing fails when it is stale.
                                #   100 IS 98's TWIN, as 95 was 94's:
                                # the card's save buffer moved from
                                # 977 ALM of LUT RAM to four M10K
                                # (its read had been registered since
                                # the card came back a word early),
                                # and the clipper's three tables to
                                # MLAB. 16,733 -> 15,770 ALM, +1.1 ns
                                # of setup slack. A cart cannot tell
                                # them apart. 99 was the face: content,
                                # no bitstream, so the number is skipped
                                # here as 92 was.
                                #   98 ADDS spec.OBJ_LIT, so a cart
                                # wanting light across a surface should
                                # ask for >= 98.
                                #   97 TAKES TEX_PAGES TO 20, so a cart
                                # wanting more than sixteen pages should
                                # ask for >= 97.
                                #   96 ADDS spec.AUD_BASE, so like 94 it
                                # changes what a cart can SEE and a cart
                                # wanting the mixer's returns should ask
                                # for >= 96.
                                #   95 IS 94's TWIN. It moved the tally
                                # from a LUTRAM to an M10K and freed
                                # ~760 ALM, and a cart cannot tell the
                                # two apart -- same cells, same numbers,
                                # same clock. So anything wanting
                                # VIS_BASE should ask for >= 94 and not
                                # for a particular build: the number
                                # says WHICH bitstream, never WHAT it
                                # can do.
                                #   The fix, when it is wanted, is to
                                # make the law and the sim EMIT the same
                                # signature the loader does. Until then
                                # this number is a label a diagnostic
                                # cart can read, not a capability check,
                                # and it has to be bumped by hand with
                                # every bitstream that changes what a
                                # cart can see -- of which VIS_BASE is
                                # one: on an older core those cells hold
                                # whatever the cart last left there, and
                                # a rule gated on them fails SILENTLY and
                                # PLAUSIBLY, the worst way to fail.
                                #   92 IS SKIPPED, and deliberately: the
                                # gradient-numerator bitstream (roadmap
                                # 23) shipped without its bump, so a core
                                # signing 91 could have been either of
                                # two different cores. Skipping the
                                # number keeps the signature aligned with
                                # the roadmap from here rather than
                                # hiding the miss -- and this is the
                                # exact failure the field exists to
                                # prevent, so it is worth the gap.
SND_HZ = 48000
SAMPLES_PER_FRAME = SND_HZ // FPS               # 800, exactly
PULSE_DUTY = (1, 2, 4, 6)       # phase[23:21] thresholds per duty setting

# ---- THE STATE: what a snapshot IS (docs/ZETA0.md D1, POCKET.md D) -------
# Rewind, Memories, Sleep and the cross across time all rest on one
# definition: the machine's whole state between two frames. Legislated
# here so all three machines agree on it, and witnessed by
# tests/test_rewind.py -- restore a snapshot and the machine continues
# BIT-EQUAL to a machine that was never interrupted: framebuffer, panel
# and every sample.
#
#   frame_no, trapped     the frame counter and the sticky trap
#   IMEM                  overlays make it state (spec.OVL_*)
#   DMEM                  the game, and every register cell in it
#   the texture pages     TEX_PAGES x TEX_STRIDE texels. Loaded from
#                         DMEM HISTORY, one slot a frame, so they are
#                         not derivable from DMEM now
#   the wave pages        AU_CHANNELS x WAV_W samples -- a voice whose
#                         page would run past DMEM keeps the one it had
#   the mixer             AU_CHANNELS phases and the noise LFSR
#   the heard ring        two frames of AUD_BASE (the answer is two
#                         frames old, see cabinet.py)
#   the card's counters   CARD_DIAG's four words, as the law keeps them
#
# NOT state: the CRAM segment (immutable after boot), the card (external
# storage -- a Memory on the Pocket does not roll the SD card back
# either), the grade table, the compositor block and VIS (derived or
# already in DMEM), the VM stack (it resets every frame).
#
# A SNAPSHOT WHILE A CARD REQUEST IS IN FLIGHT IS REFUSED, on every
# machine: the words are in the card's staging and land at a legislated
# frame at most SD_LATENCY frames away. Ask again then.
#
# The image (cabinet.VirtualMachine.pack): little-endian words --
# STATE_MAGIC, LOADER_BUILD, frame_no, trapped, lfsr, the four card
# counters; IMEM; DMEM; the phases; the heard ring; the texels as
# halves; the wave samples as bytes. STATE_BYTES of them.
STATE_MAGIC = 0x5A535330        # 'ZSS0'
STATE_BYTES = (4 * (9 + IMEM_WORDS + DMEM_WORDS + AU_CHANNELS
                    + 2 * AU_CHANNELS)
               + 2 * TEX_PAGES * TEX_STRIDE + AU_CHANNELS * WAV_W)

# ---- pad bits: the Analogue Pocket's full set ------------------------------
PAD_UP, PAD_DOWN, PAD_LEFT, PAD_RIGHT = 1, 2, 4, 8
PAD_A, PAD_B, PAD_X, PAD_Y = 16, 32, 64, 128
PAD_L, PAD_R, PAD_START, PAD_SELECT = 256, 512, 1024, 2048

# ---- the ISA -------------------------------------------------------------
# One instruction = one 32-bit word: [31:24] opcode, [23:0] signed immediate.
# One instruction = one unit of fuel.  Stack of 32-bit words, depth STACK_MAX.
# Binary ops pop b then a and push a OP b (so "load X / push 5 / lt" asks
# "is X < 5").  LT is SIGNED.  SHR is ARITHMETIC.
# call/ret use a separate 16-deep RETURN stack (addresses only, invisible
# to the data ops); it resets every frame, and overflow/underflow trap
# exactly like data-stack abuse.
STACK_MAX = 64
RSTACK_MAX = 16

OPS = {  # name: (code, takes_immediate)
    "halt":  (0x00, False),  # end the frame
    "push":  (0x01, True),   # push sign-extended imm24
    "load":  (0x02, True),   # push DMEM[imm]
    "store": (0x03, True),   # DMEM[imm] = pop
    "loadi": (0x04, False),  # a=pop; push DMEM[a]
    "storei":(0x05, False),  # a=pop; v=pop; DMEM[a]=v
    "add":   (0x10, False),
    "sub":   (0x11, False),
    "mul":   (0x12, False),  # low 32 bits of signed product
    "mulq":  (0x13, False),  # (a*b)>>16 of signed product: Q16.16 multiply
    "and":   (0x14, False),
    "or":    (0x15, False),
    "xor":   (0x16, False),
    "shl":   (0x17, True),   # push(pop << imm)
    "shr":   (0x18, True),   # push(pop >> imm), arithmetic
    "lt":    (0x19, False),  # push(1 if a<b else 0), signed
    "eq":    (0x1A, False),
    "dup":   (0x20, False),
    "drop":  (0x21, False),
    "swap":  (0x22, False),
    "over":  (0x23, False),  # push copy of second-from-top
    "jmp":   (0x30, True),   # pc = imm
    "jz":    (0x31, True),   # if pop==0: pc = imm
    "call":  (0x32, True),   # rstack.push(pc); pc = imm
    "ret":   (0x33, False),  # pc = rstack.pop()
}
CODE_TO_NAME = {c: n for n, (c, _) in OPS.items()}


def s32(v: int) -> int:
    """Fold any int into signed 32-bit -- the only numeric domain Zeta has."""
    v &= WORD_MASK
    return v - 0x100000000 if v & 0x80000000 else v
