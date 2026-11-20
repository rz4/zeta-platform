# TEAR NOT DEMON on the Zeta — the port

Written 2026-11-19. The goal: the July 2026 game (`archive/TND`, the one
with the rigged boxer at Bancroft and Shattuck — screenshots in
FLAGSHIP.md) running on the Pocket as a Zeta cart, launched from the
shelf, at a locked 60.

## What kind of port this is

TND was written against the *old* Python virtual console: float
physics, float FK/skinning/IK recomputed every frame, ~11,000 triangles
submitted a frame, no cycle budget, no object limit, no gates. None of
that runs on the Zeta, and almost none of it needs to. The port is a
**rebuild**, and the archive plays two roles:

- **The offline baker.** Its own animation functions are called by
  `tools/tnd_extract.py` and their output frozen; the forge quantises
  it. The float code never ships. This is the alien thesis applied:
  expensive things BAKED EXACTLY and played back.
- **The design source.** Frame data, the input grammar, the cancel
  lattice, the style meter, the AI, the HUD — all ported as design into
  ZOL, under integer law, held by the gates.

The full measured inventory (sizes, file:line references, what is
essential versus optional) was taken 2026-11-19 and its numbers are used
below.

## P1 — the fighter: LANDED (carts/tnd.zol)

The boxer — 737 faces, 459 vertices, 67-joint skinning in the archive —
standing, walking and jabbing on the Zeta, crossed bit-equal on silicon.

    split        ONE horizontal cut satisfies both object limits, at hip
                 height: upper 378 faces / 253 vertices, lower 359 / 244.
                 Seam vertices duplicated; both halves bake from the same
                 posed positions, so the waist cannot tear.
    pose span    one DMA a frame repaints the whole body: 2,967 words,
                 from the upper vertices to the end of the lower faces.
                 Face colours ride in the span, so every pose carries
                 THE ARCHIVE'S OWN PER-FACE SHADING for that frame.
    axes         archive right-handed z-up, forward +x (guard fists ahead
                 of the torso); mapped left->left into Zeta's left-handed
                 view space, winding flipped -- checked by eye.
    measured     peak 315,777 clocks a frame (43.9%), 282 program words,
                 168 poses (idle 120, walk 32, jab 16) = 498k CRAM words
    gates        the jab moves the body (proved live by deleting the DMA:
                 "moved only 0 pixels"), both halves draw, silicon cross
                 90 frames; the regen gate holds the bake where the
                 third-party source exists

## P2 -- the street and the follow: LANDED

Bancroft and Shattuck from the archive's own constants: the crossing,
sidewalks, both zebra crossings, the centreline, four streetlights, the
corner towers and the arms' facades, the red dusk fog; the archive's
follow camera as integer easing. The street is held to the archive's
arena (`tear.py` `_in_arena`): the crossing square inside 10.6 and the
two streets 7.1 either side out to 40, sliding along an edge rather
than sticking to it.

## P3 -- the demons: LANDED

The wave of three -- brute, lean, heavy, the archive's own builds and
palettes -- closing in, squaring up, and swinging.

![The wave on the Zeta: the brute squared up ahead, the lean demon
throwing its cross](images/tnd-zeta-wave.png)

**On glass, 2026-11-19:** the column cart on a Pocket (build 102), film
-> shelf -> X -> TND untouched, captured with Menu+Start: the law's
frame 143 to the pixel, all 92,160 (`tests/glass/tnd-wave-143.ppm`).
That capture also found that the Pocket's own screenshots are RGB565
-- green passes through six bits -- which the witness now models
(`witness.pocket_capture`) instead of a gate nobody could pass.

    rig          rig.fighter's 17 rigid joints; five never rotate against
                 their parent (MEASURED over every clip: 0.0), so they
                 merge -- 12 parts, 12 objects a demon, each placed by its
                 own angles word. Left and right limbs are one mesh
                 (identical, vertex for vertex): 8 meshes a build.
    clips        ONE table of packed character-local rotations serves all
                 three builds; the cart walks the offsets through the
                 parents at run time (three small rotations a part, the
                 GPU's own order). idle 32 + walk 16 at 30/60 Hz, cross 19
                 and lead hook 34 at 60, hurt, the fall: 1,392 words. The
                 bake checks itself: the run-time chain, with QUANTISED
                 angles, lands every joint within 3 mm of the archive's FK.
    horns        the first LOD: the archive's 120-triangle box chains as a
                 curved two-segment spike along the same curl, 18 faces,
                 lit by the archive's own shade().
    winding      the archive drew both sides, so its tapers are wound
                 inward; the bake orients every face outward from its own
                 convex solid.
    minds        tear.py's turret AI in integers: bounded turn (0.034 rad
                 a frame), walk along their own facing, stop inside 1.5,
                 swing from a 0.46 rad cone every 74 frames, cross and
                 hook alternating. Angles without atan2: the side is the
                 sign of a cross product, the cone a ratio of squares.
                 Mass-weighted shove between every pair of bodies.
    gates        the wave closes and squares up; each throws cross, hook,
                 cross with the move's clip rows; the swing moves pixels
                 (0 under mutation); the shove holds (fails under
                 mutation); the street holds him (fails under mutation);
                 culling happens and changes with the view.

## P4 -- the fight: CORE LANDED

Blows land both ways, and the fight has its ends: a demon falls, lies a
beat and is gone; when all three are, the next wave stands round the
crossing; when he falls, the frame darkens and A is a new run.

    the string   combat.resolve: every tap of A swaps hands (the first is
                 the cross), the third tap of a string -- taps within 22
                 frames -- cashes out a hook off the next hand; a tap
                 during a swing is buffered 10 frames. Read on the press:
                 nothing on A is a hold yet, so the archive's tap-on-
                 release would only add a frame.
    a hit        tear.py _resolve_hits: the posed fist, in the move's
                 active frames, within reach of the target's chin or gut
                 (nearest decides; head x1.35 and +3 hitstop). Both
                 fighters freeze, the target is stunned 12 + that, knocked
                 along the blow; the camera shakes; one hit per swing.
                 Fists baked per active frame from the archive's own rig
                 (the one it hit-tests on); chins and guts at GUARD -- a
                 reach of 1.4-1.55 dwarfs how far they move.
    moves        jab, cross, lead hook, rear hook: pose spans baked from
                 the archive (255 poses, 757k CRAM words), the archive's
                 frame data, damage, reach, hitstop, knock and lunge.
    feel         the lunge as one impulse at the launch (both sides),
                 friction 0.82; the struck body flashes blood-red (the
                 object tint can only darken, so red stays and green and
                 blue drop to a third); his stun holds the idle mesh, as
                 the archive's did; down, he folds forward away from the
                 lens.
    the gauge    his health on the compositor's free rectangles, from the
                 first blow either way -- so an untouched opening is the
                 street alone, and the glass witness of frame 143 still
                 stands.
    the lens     a demon within 1.3 of the camera is not drawn: near-
                 clipping it is the sequencer's most expensive path, and
                 one demon 0.95 from the lens put a frame at 722,865
                 clocks -- over 100%. It still fights. (Hidden in 31 of
                 1,560 demon-frames on the brawl, never mid-swing.)
    gates        the string's order; his blows fell the brute; theirs beat
                 him down and A restarts with the wave reset; the fallen go
                 and the wave returns; the lens rule; and a 720-frame
                 silicon cross through blows both ways.

    budget with the fight   brawl 635k peak / 520k median (0 over 90%)
                            street 548k / 477k (0)
                            tour 668k / 459k (6 of 900 over 90%, none
                            over 100%)

**The rest of the archive's reachable moveset (P4b):**

    grammar      combat.Grammar on four face buttons -- A carve, B special,
                 X jump, Y shoot. A TAP is a release within 9 frames (a
                 long hold is not one); a CHORD is two buttons down within
                 3 frames, read once, and neither taps -- so carve+jump is
                 the rear uppercut and never also a jab.
    special      B: the haymaker -- 20 frames of coil, 46 damage, reach
                 2.4, a 28-frame hitstop.
    uppercuts    carve+jump (rear), shoot+special (lead): LAUNCHERS. The
                 target goes up at 0.45 a frame against the aerial gravity
                 (0.014) -- seven units -- helpless the whole arc (2 lift /
                 g + 6 frames). A blow on a body already aloft floors its
                 rise to 0.12 and refreshes its stun (AIR_HIT_FLOAT /
                 AIR_HIT_HANG), so a string keeps it up. It is drawn and
                 struck where it is: aloft.
    unreached    the body jab and body cross are in the archive's move
                 table but its grammar never maps them, so they stay out.
    sound        the blow, heard: sfx.meat_impact as a slap (noise at a
                 12 kHz step, switched at sample 192 exactly by the event
                 list), the meat, a falling triangle thump and a pulse
                 ring; a head shot brighter and shorter.
    memory       IMEM 2,936 of 4,096 (the street's visibility test became
                 one loop over a table: -889 words). DMEM: the forge now
                 offers the 536 words above the loader's mirror that the
                 law never legislated.

    cancels      combat.py's lattice: in its recovery a move is cut short
                 by a buffered move it lists -- a light punch by anything,
                 a hook by the launchers and the special, a launcher by the
                 special, the special by nothing.

P4 is the archive's grounded fight, complete: what remains of its combat
is the air layer (the jump, the gun, juggles, the spike), deliberately
after the game ships.

## P5 -- style and sound: STYLE LANDED

    the meter    combat.Style in integers (points x16; the combo's /400 a
                 multiply by its reciprocal -- there is no divider): a
                 landed blow pays its move's style (jab 8 ... haymaker 70)
                 x its variety (1, 0.6, 0.4, 0.25 as it recurs in the last
                 five) x the combo (+5% a hit, to twenty); a blow taken
                 keeps 45% (three at once, as the wave swings in step,
                 keep 9%); idle past 45 frames bleeds 0.6 a frame, past 90
                 2.2 and the combo. Ranks D to SSS at 0 / 60 / 150 / 300 /
                 520 / 800 / 1200; the best run is kept for P6's save.
    on glass     the rank top right in the archive's colours, composed
                 into the display list from five baked glyphs (an S three
                 times is SSS) when it changes; the meter toward the next
                 rank on the compositor's fourth rectangle.

    the music    sfx._synth_battle_stems on this machine's voices: 148
                 BPM, a two-bar loop, the stems un-muting one a rank --
                 drums at D, the bass at C, the chug at B, the half-time
                 breakdown at A, the lead hook revealing itself (fragment,
                 hook, harmony a third up) through S and SS -- all riding
                 one eased intensity, silent when he is down. A step
                 sequencer at the sixteenth on the archive's own sample
                 grid (a sixteenth is 4,864 samples, a frame 800, so one
                 step at most a frame), each note on its exact sample
                 through the event list. The kick a pulse falling in pitch;
                 snare and china on the noise voice; bass and leads on a
                 square page, chug and breakdown on a POWER CHORD page
                 (root, fifth and octave hard-clipped, as _power_chug).
                 One loop over a stem table: unrolled it was 1,150 words
                 and IMEM holds 4,096.
    the small    sfx.py's whiff (a swing that closes on nothing: a noise
    sounds      swell with no transient, never to be taken for a blow), a
                 footstep each half stride, and the rank-up stinger (a square
                 arpeggio with a fifth over it, 3 + r/2 notes from the rank's
                 root) -- on voices nothing else uses, from a noise page.
    room made    the display-list lease cut to 40 triangles (the largest
                 text at once is RETRY's 38) and the blow's curves
                 computed instead of tabled.

**THE SYNTH'S COLD START (build 103).** The music turned the cross
across a launch red, on audio, the first frame after: oscillator phases
and the noise LFSR are machine state outside DMEM, and a launched game
inherited the film's. Silent games never showed it -- every launch
gate passed because nothing in its window sounded. The law gained
spec.AU_RESET: a cart writes it and the machine zeroes every phase and
reseeds the LFSR before this frame's samples (on silicon, a one-clock
pulse at the audio latch). The shelf writes it on its launch frame, and
the film on its launch of the shelf; the launched game sounds as it
does from a cold boot, gated on both machines.

## P6 -- the shell of the game: THE TITLE LANDED

    the title    the archive's own start screen -- TEAR / NOT / DEMON in
                 its gothic hand, the demonic Ns, the blood gash, the
                 inverted cross, the boxer on the street -- rendered BY THE
                 ARCHIVE (tools/tnd_title.py) at the panel's own 320x288
                 (its console scales x3 by nearest neighbour, checked
                 block by block) and baked to a backdrop plate. The menu is
                 cut to START: the port has no LOAD or OPTIONS yet, and a
                 title must not promise what the game cannot do. On the
                 title nothing else is drawn, the music keeps the intro
                 lock, and PRESS START breathes on the archive's beat (one
                 compositor rectangle). Start or A begins the fight the
                 next frame; an A held through the cut is no jab.
    the glass    the frame-143 witness stands: Start on frame 0, and the
                 fight that ran from frame 0 on glass runs from frame 1 --
                 its frame 144, to the pixel.
    already      death and retry (P4), the gauge and the rank (P4, P5).

    the hud      a TEXT ENGINE: glyphs as packed rectangles (two words a
                 glyph, not ~57 of baked triangles) composed into the
                 display list when what the HUD says changes -- the rank,
                 the archive's combo counter (X5, X12), RETRY. It gave
                 back 336 words of DMEM with the lease restored to 64.
    the marker   tear.py's AWARE: a gold tetrahedron over every demon that
                 has him in its frontal cone (entered at 0.46 rad, left
                 past 0.60, so circling its edge does not chatter) -- the
                 unmarked are the gaps to move through.
    movement     the tank's other half (down walks back), and the strike's
                 facing: at launch the body faces the D-pad's octant off
                 the steering, the camera never sees it, and steering is
                 frozen while a strike button is held (tear.py
                 _aim_at_dpad, _tank). Taps fire for a THUMB: on release
                 or at the fourth frame held -- the archive's 9-frame
                 release rule is a keyboard's, and on glass it made the
                 string and the haymaker do nothing.

Still to come in P6: the best score saved to the card. Deeper than a law
amendment: on the Pocket the card is one data slot served from Assets,
which every sd push rewrites -- a save needs the Pocket's own save slots
(and likely the card bridge), and the archive never shows the score.
On glass again, 2026-11-19 (core 0.103.0, the build at fbe5bf4): Start
and nothing, the wave in, the aware markers up -- the law's frame 348 to
the pixel (tests/glass/tnd-aware-348.ppm). The frame-143 capture stays as
the witness of the Pocket's RGB565 camera.

## The frame, measured (2026-11-19)

Three demons on the P2 street measured **858,900 clocks** at the worst
frame of a brawl -- 119% of the frame. The silicon's own stage meter
(`zeta_top.v`: clear / walk / idle / stall / seq / blocked) and a law-side
walk attribution (`tools/tnd_meter.py`) found where it went, and the
answers were not the ones the face counts suggested:

1. **The rasteriser walks bounding boxes.** Every pixel of a triangle's
   box costs a clock, covered or not, and a triangle covers at most half
   its box. Ten asphalt faces walked 110k-189k pixels a frame: near-
   clipped, they fan into triangles each boxing most of the lower screen.
   **The ground now rides the camera**: the camera's height, pitch and
   roll never change, so the visible ground is one fixed shape in camera
   space -- a single triangle for everything nearer than the fog (its
   screen-clipped box wholly covered: 1x, not 2-4x) and four rings out
   to 60 with true vertex depths so the fog ramp reads right. It sits
   0.2 below the street so that nothing standing on it can sink under
   its over-read interpolated depth. 65k pixels, every frame, flat.
   (A backdrop plate was tried first and cost MORE: reading a
   full-screen plate is ~136k clocks against the clear's ~98k.)
2. **The sequencer caches 2,048 transformed vertices a frame.** Past
   that an object is re-transformed in every band it touches. The street
   plus the player plus three demons came to 2,080-2,140, so the demons
   -- last in the list -- spilled. This is also why cutting faces into
   pieces measured WORSE (+25k to +67k median): every cut added vertices
   past the cache. **What the camera cannot see is not sent**: every
   street object and every demon carries a bounding sphere, tested in
   ZOL against the view (yaw, the fixed pitch, side planes at 40 degrees
   for the screen's 32) -- invisible by construction, 0 pixels differing
   over every route -- and the frame now sends 1,074-1,733 vertices.
3. **Group by place, not by kind** -- the street's faces by layer (the
   floor, what stands up) and by sector round the crossing, so culling
   has compact objects to drop.
4. **Overlapping boxes are overdraw you cannot see.** The corner towers
   are now the boundary of their union (no buried faces, no roofs the
   2.15-high camera could never see).

    route    start of day (peak / median)   now (peak / median)     over 90%
    brawl    858,900 / 584k  (97 frames)   617,186 / 516k  (85.7%)   0 of 520
    street   712,320 / 625k                543,397 / 473k  (75.5%)   0 of 240
    tour     --                            653,012 / 495k  (90.7%)   1 of 900

The one frame over is the player spinning in place with the brute 2.3
units from the lens and a corner tower filling the top of the shot --
under 100%, so it does not drop, but over the gate's 90% margin. P4
(hit effects, HUD) needs headroom this does not have: DIV=6 (+20%
clock, the second PLL) is now on the critical path, not optional.

What did not work, so nobody tries it twice: the backdrop plate (above);
regrouping street faces by region with facades and floor merged (each
region spans the screen again; no saving, +340 words); splitting facades
into strips (their walk does not drop -- they are seen near square-on);
giving the camera a body that shoves demons off the lens (it shoves them
sideways INTO the shot: 1 frame over the ceiling became 20).

**DMEM is the other wall.** 16,384 words hold the player's two meshes
(2,969), three demon builds (~3,000), their clips (1,392), the street,
and the program's state. Two things paid for P3: the sine table folded
to a quarter wave (1,024 -> 257 words) and the forge's new **display-list
lease** -- a cart that promises at most N display-list triangles may
place content in the list's unused tail (TND promises 64 for its HUD,
and the other 1,344 words hold content). 64 triangles is about EIGHT
characters of forge text (a glyph is ~8): P6's HUD has to be mostly the
compositor's four free rectangles, or a different font.

## The constraints that shape everything after P1

1. **ONE MOVER REQUEST A FRAME, and the player's pose takes it.** So
   the demons cannot also stream full-body poses. They animate the way
   the archive's own demons did: rigid parts (17 joints), driven from a
   small table of KEY POSES resident in DMEM, eased between in ZOL —
   the archive's `Move.pose_at` guard -> windup -> strike -> guard
   blend, with the FK done offline into fighter-local joint transforms.
   About 25 key poses x 17 joints x 4 words = 1.7k DMEM words; the three
   builds (brute / lean / heavy) are the same table scaled at runtime.
2. **CRAM FILLS BEFORE TIME DOES.** A pose is 2,967 words. Every move
   and gait at 60 Hz is ~1.6M words; the film and shelf already hold
   ~0.5M of CRAM's 2M. Budget rule: strikes sample at 60 Hz (their
   active frames are what you read), cyclic gaits at 30 Hz with each
   pose held two frames. The second CRAM die (+16 MB, ZETA0.md) is the
   escape hatch if the moveset outgrows that.
3. **64 OBJECTS.** Player 2 + three demons at 17 parts (51) + the
   street = ~60. Demon parts may merge (neck into head, hands into
   forearms: 13 parts, 39 objects) if the street needs more.
4. **THE FRAME -- and the street cost five times its estimate.** The
   plan said ~50k for the street. MEASURED on silicon over a fixed
   route (turn, walk into a corner, sweep, jab), decomposed by omitting
   one part at a time:

       first street, archive geometry    peak 684,846   median 631,064
         of which the 60 buildings          ~247k           ~287k
         sidewalks / paint                  ~37k / ~24k     ~44k / ~27k
         road + boxer alone                 363,856         274,830
       after FACADES (below)              peak 602,851   median 550,861

   The buildings were OVERDRAW: down an arm, ten fronts a side stack
   in depth and the rasteriser pays every pixel of every face, hidden
   or not. The archive never paid this; it had no clock. The 48 street
   buildings became one continuous facade a side (the archive's
   heights, only the steps that face the crossing), the arms end at
   the fog line with an end wall the fog turns to dusk, and sidewalks
   keep only the faces anyone sees.

   So the scene WITH three demons (est. ~75k each, horns dropped) is
   ~775k: over the 648k ceiling at 43.2 MHz, and at the edge of DIV=6's
   777k. To fit: DIV=6 (+20%, ZETA0/SEAMS -- the vertex-C register for
   it landed in build 101; it still needs the second PLL), demon horns
   as the first LOD (152 of 476 faces), the crosswalk as a texture
   (~27k), and a boxer LOD (737 faces is more than ZETA0's arena
   archetype gives a hero). Fill and overdraw get MEASURED, never
   estimated -- the ledger's rule, with a third clause.
5. **THE CAMERA IS FREE.** TND follows behind the player through
   every mode, so no plates in play: the street is real geometry. The
   archive's ~3,000 in-view triangles were incidental (asphalt
   subdivided to dodge a near-plane reject the Zeta's clipper does not
   need, plus a redundant floor) -- a few hundred large faces will do.
6. **THE PC CABINET RUNS IT AT 24 FPS.** The silicon has room; machine
   1's per-triangle overhead does not. The batched opaque rasteriser
   (gpu.py) stops being optional the moment TND is the flagship.

## The phases

    P2  THE STREET AND THE FOLLOW   LANDED (above). Still to come from
        its plan: walk in four directions and the run, more clips.
    P3  THE DEMONS                  LANDED (above).
    P4  THE FIGHT                   the input grammar (tap <= 9, hold
        >= 10, chord within 3, strings within 22, a 10-frame buffer),
        the 11-move table with its frame data, the cancel lattice,
        hitstop, head-versus-gut from keypoints (the player's ride in
        the pose span; the demons' come from their joints), HP 140/70,
        the death beat.
    P5  STYLE AND SOUND             the meter in integers (variety
        decay, combo multiplier, the x0.45 on a hit taken), ranks D to
        SSS; the music as the archive's own synth fallback -- eight
        stems gated by rank, sample-exact on the event list, and free of
        the recorded track's rights question -- and its nine SFX.
    P6  THE SHELL OF THE GAME       HUD (HP gauge, the TND wordmark
        with the horned N, the rank letter, combo, mode), title menu,
        death and retry, best score saved to the card, and its place on
        the shelf.

Deliberately after the game ships: the parkour/meteor/flip movement
modes, the air-combo layer, the gun, the attract intro and the
cutscene, and the recorded music (only with the rights settled).

## Where it diverges from the archive, on purpose

The archive is float and its animation is recomputed; the port is
integer and its animation is baked. So the port is a TRANSLATION held
to the Zeta's gates, not an emulation held to the archive's numbers. The
archive's GOZL reference traces (tick-exact jab and exchange) are worth
keeping as design checks for P4, not as bit-exact goldens.
