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

## P1 — the fighter: LANDED (games/tnd/tnd.zol)

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

## P7 -- the record: LANDED, LOCAL ONLY (TND_SONG=1)

    the record   "Set It Off" through the archive's SONG STRUCTURE
                 (song_structure.py), not the synth theme: the music walks
                 the record's sections one at a time toward the climax --
                 intro, lift, drive, chorus, verse, surge, climax -- with
                 rank only the CAP on how far it may go, so a fast climb
                 still hears the whole arc. A fall from S or above drops
                 into the BREAKDOWN, a refrain held until a rank is won
                 back; tumbling to D lands on the MOBIUS REPRISE, the
                 record's end run into its start. A forward step waits
                 out the current section's phrase (its own bar count), a
                 setback cuts on the next beat, the reprise on the bar --
                 the archive's grids, counted in stream samples. The bus
                 eases in and falls to nothing when he is down; the rank
                 stinger rides it.
    the cut      tools/tnd_song.py: the archive's section windows at
                 15,360 Hz (the page times the frame rate), each start on
                 its downbeat grid, each loop the archive's bar count
                 rounded to whole frames, each seam folded as _fold_seam
                 does. The reprise tail sits just before the intro, so
                 the reprise is not a copy: it is the section that starts
                 at the tail. 8,457 frames, 541,248 words.
    the stream   a 64-word page a frame into the wave bank's page 1 (the
                 chug's: only the synth theme walked it), sounded by seven
                 voices in unison -- the channel count is the volume --
                 each walking the page exactly once a frame by two
                 increments split at one sample (bakepcm.inc_law).
                 Sample-aligned to the bake: 0.99 correlation in place,
                 0.17 a frame either side.
    the mover    the page needs a move EVERY frame and so does the pose:
                 sharing one request dropped 167 poses in 900 frames of
                 punching. Build 104 adds the second request (spec.DMA2_*).
    the room     the column's CRAM had 468k words free; the record needs
                 541k. The song build stores each distinct pose once -- 44
                 of 313 are exact repeats -- through a pose-to-slot index:
                 130k back, 41.8k to spare.
    the rights   the record is third-party, so this build is LOCAL: it
                 bakes from the gitignored assets/tnd/song.npz into the
                 gitignored build/song/ (gen_tnd, gen_shelf and gen_face
                 under TND_SONG=1), and that column is what the card
                 carries. The committed carts keep the synth theme.

## P8 -- the attract intro: LANDED

    the flight   tear.py _intro_cam over the FROZEN arena: low across the
                 crosswalk, up past the demons, a crane for the skyline,
                 down behind the fighter as the title lands -- the
                 archive's eight keys, smoothstepped, its handheld sway,
                 the gaze solved in closed form for this machine's yaw
                 (atan2(-dx, dz)) and pitch (positive looks down).
    the words    THE EVE OF THE APOCALYPSE (the place line, BANCROFT AND
                 SHATTUCK, is cut by request: the subtext stands alone),
                 TEAR THROUGH THE NIGHT, then TEAR / NOT DEMON slammed in
                 with its cold and warm ghosts and a white flash. Bars
                 slide in, the frame fades up from black, a veil breathes.
                 Not drawn: the archive's drop shadows (they would double
                 every string's triangles) and its skip hint (the title
                 that follows says PRESS START). The display list has no
                 alpha, so a fade is a colour walked down to black over
                 the dark street.
    a program    the game's IMEM is full, so the intro is a SECOND
                 program the overlay mover pages in: its own frame code,
                 then -- emitted into both by one generator (a Tee over
                 the forge's Program), so they cannot drift -- the
                 street, the fighter, the demons, the music and the
                 sounds. The music runs straight through the handover. Its
                 visibility test reads the frame's real pitch and height.
    the data     everything that moves is one 16-word ROW a frame, baked
                 and fetched a frame ahead by the mover.
    the borrow   its words need 146 display-list triangles against the
                 fight's promise of 80, and the tail past the promise is
                 full. So the cart holds back two BORROWED reserves of the
                 tail (forge Cart dl_borrow) filled with constants only the
                 fight reads -- move tables, the spawn, the style tables,
                 the HUD's strings: the intro draws over the front, parks
                 its font, strings and row in the end, and its two exit
                 frames put both back from the cart (with the camera cells
                 the fight never rewrites) before paging the game in.
                 Gated: the regions come back exactly as the cart boots
                 them, and poisoning the front mid-intro changes no
                 picture and no sample of the intro, the title or the
                 fight after.
    the handover the title's timer boots at the attract threshold, so the
                 title's first frame pages the intro in, and 25 idle
                 seconds replay it. Start skips it in two frames, and the
                 title reads that Start as held, not fresh. Start on the
                 very first frame still begins the fight at once.

## P14 -- the card: LANDED, witnessed on the Pocket

What survives the power: two words in card slot 2 (the Pocket's card.bin).
The best rank ever reached (0 none yet, 1..7 for D..SSS) and the runs
that ended.

- **Read** once, a second after the machine starts. carts/probes/gen_save.py's
  first version read at frame 1 and got zero every time.
- **Owed, then written.** A rank past the card's best is the new best the
  moment it is reached, so a run quit at SSS still reached SSS. A death is
  a run. Either marks the pair as owed, and it goes out when the card is
  free. One transfer in flight is the law's own rule.
- **Shown.** The title says BEST and the rank, in the rank's colour, over
  the prompt. A word outside 1..7 is not a rank, and the title stays
  silent. Its position (124, 246) is a first guess, to calibrate.

Three things had to give to make room:

- **DMEM had no word left**, and the save needs eight. The HUD's promise
  was 80 display-list triangles on a hand count of 76. The font says the
  true worst is 78 (X55 is 30 triangles, not 28), so the promise is 78
  now, PROVED by an assert from the font, and the 14 words go to the
  borrowed front.
- **The save's three cells sit at the top of the display list's tail**
  (forge `Cart.tail_top`), so adding them early moves nothing else in a
  pool that fills first-fit.
- **The shelf refused any cart that used the card.** Slots are absolute
  (SLOT_BASE is not law yet), so the real hazard is two shelved carts
  naming the same slot. The forge now adopts a shelved cart's slot images
  and refuses only that collision. The column (film → shelf → TND)
  carries slot 2.

Gates: tests/test_tnd.py (the card is written when a run ends; the title
shows the card's best and a lesser run keeps it; a better rank is owed at
once; a foreign card says nothing; the HUD's promise holds at its forced
worst), tests/test_forge.py (adoption, collision), tests/test_shelf.py
(the column carries the card).

**WITNESSED ON THE POCKET (2026-11-20, the stack core):** a run played,
the machine switched off and on, and the title said BEST and the rank.
The Pocket keeps card.bin across a power cycle. (The card's file had to
be two words long first: it held one blank word from August, and a push
never replaces a card*.bin, so it was replaced by hand.)

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
modes, the air-combo layer and the gun. The cutscene is dropped. The
attract intro landed (P8); the recorded music landed as a local build
(P7).

## Where it diverges from the archive, on purpose

The archive is float and its animation is recomputed; the port is
integer and its animation is baked. So the port is a TRANSLATION held
to the Zeta's gates, not an emulation held to the archive's numbers. The
archive's GOZL reference traces (tick-exact jab and exchange) are worth
keeping as design checks for P4, not as bit-exact goldens.

## P16: what the first tape of real play asked for (2026-11-20; not yet on glass)

The recorder's first tape (docs/ZETA0-FRONTIER.md, 18) was replayed with
the game's own cells logged every frame. 181 seconds of fighting, 15
waves, 44 kills.

**What it showed**

| | |
|---|---|
| hits taken | 0 (health never left 140) |
| demon swings started | **0**: the longest any demon stood ready was 20 of the 74 frames a swing needed |
| moves thrown | 356: gun 237, haymaker 39, every other fist 80 |
| killing blows | haymaker 35 of 44 |
| first hit after a wave spawned | a median 0.2 s, from a median 5.2 units |
| time with no demon alive | 33 s (18%); every one of 9 rank drops was idle decay |
| time frozen in hitstop | 48.5 s (27%); a third of all presses began in a freeze |
| the walk | 0.5% of the fight; 43 runs, median 17 frames, never at nine tenths of top speed |
| facing changed | on 2% of frames; Left and Right were pressed 10 times |
| camera | a swing past 3 degrees a frame every 3.5 s, the largest 22 degrees in one frame |
| unused | boxing 4%, dodge 0, quick turn 0, meteor 0, launchers 3, charged shots 2 |

The telegraphs P15 added were never seen, because nothing ever swung.

**What changed**

| | was | is | why |
|---|---|---|---|
| The plain shot on a standing demon | stun (stop + 12) and breaks a swing | its damage, a four-frame flinch, its style | locked, it lands at any range every 18 frames: a leash |
| A demon's wait before it swings | 74 frames, restarted by every step | 54 frames, kept while it steps | scripted, two demons stood beside a string for 760 frames |
| The tell | amber for the swing's startup (5 frames for a cross) | amber for the last 24 frames of the wait as well | nobody dodges on five frames |
| A demon's walk | 0.020 a frame | 0.028 (his is 0.032) | the ring is under four seconds away |
| A fallen demon | the wave returns when all three are gone | replaced alone, at once, at its own place | no two seconds of nothing; no decay in a wait the game made |
| Buttons during hitstop | not read | read and buffered (the jump aside) | 100 of 303 gun presses, 36 of 108 string presses |
| The run | 79 frames to nine tenths of top speed | about 19 | a run lasts 17 frames |
| The camera's turn | an eighth of the arc a frame (up to 22 degrees) | the same, capped at 12.7 degrees a frame | a new lock whipped it |

- The charged shot still stops a demon, and a demon aloft is still
  juggled by plain shots.
- The retry and the quit bring the whole ring back in one request, as
  before; `f_wave` counts arrivals now (a ring, or a demon).
- 64 program words (7,895 to 7,959 of 8,192); no new cells.
- **Not changed, on purpose, until a tape of this build exists:** the
  haymaker (46 of a demon's 70 health, the longest reach, the most
  style), the absence of any escalation, health that never returns, the
  instant snap of his facing when he plants on a lock.

**Standing still costs more:** untouched, the first blow reaches him at
frame 283 and he is down at 556 (nine seconds). It was 394 and 727.

## P16 on glass, and the second tape (2026-11-20)

The player's verdict on P16: "definitely more engaging and difficult,
good". The tape (5 m 4 s, 18,223 frames) replays on the law from the save
it started with and writes the save the Pocket wrote, word for word: best
SSS, and the run count from 0 to 4. That is the first replay gate with a
save that changed.

| | first tape (P15 rules) | second tape (P16 rules) |
|---|---:|---:|
| hits taken | 0 | 39 |
| deaths | 0 | 4 |
| demon swings started / landed | 0 / 0 | 41 / 39 |
| time at D | 6 s | 186 s |
| rank drops to idle decay | 9 | 36 of 50 |
| boxing stance | 4% | 44% |
| jumps / flips and dodges | 6 / 3 | 76 / 48 |
| time with no demon alive | 33 s | 0.2 s |

- The demons fight back now, and **almost every swing lands**: 39 of 41.
  The dodge had no invulnerability, and 7 blows landed on a body still
  stunned from the one before.
- The player found the boxing stance (L+Down) and lived in it, mostly
  backflipping out of trouble.
- The style meter bled faster than anyone could earn it.

The player's direction: "focus on the movement, the feeling of the
fighting, the camera angles -- dance with the enemies and feel like John
Wick with the gun play and fighting", and "think heavier Devil May Cry".

## P17: the dance (2026-11-20; not yet on glass)

**Movement**

| | was (the archive's tank) | is |
|---|---|---|
| the d-pad, free | Left/Right turn 12 a frame, Up/Down walk at 0.032 | the screen's eight directions: he turns to the one held (96 a frame) and jogs along it at 0.068 |
| "the screen" | -- | the camera as it stood when the direction was pressed, so a held direction is a straight line |
| L | the style grammar: L+Up the run, L+Down boxing | the sprint, steered by the pad on screen |
| R | lock; Left/Right flick moved it | the dance: he faces the demon and the pad steps round it (Up in, Down out, Left and Right circle) |
| L+R + Left/Right | (fencing, then Up+direction) | METEOR, the circle at full speed |
| the quick turn, the locked style flips, boxing unlocked | | gone: a pad that means the screen turns him in three frames |

**The fight**

| | is |
|---|---|
| blows, free | go along the pad on screen (or his facing), then onto the demon nearest that line within 63 degrees and 3.2 units; he turns to it |
| blows, locked | at the demon |
| the gun, free | at the demon nearest the pad's line, out to 13 units: shoot the one behind you by pressing Down |
| the gun, point blank | inside 1.8 the plain shot staggers as a fist does |
| Stinger | locked, Up and the haymaker: the lunge x2.5, five units to the demon |
| High Time | locked, Down and a carve tap: the rear uppercut, the launcher |
| the dodge | locked, A and one direction, as before -- now **untouchable** for its 12 frames, and it **cancels a swing's recovery** |
| a close call | a fist that would have landed on a dodge pays 30 style |
| reeling, or aloft | no fist lands on him while he is still stunned, or more than 0.9 up |
| the meter | bleeds 0.25 a frame after a second idle, 0.75 after two (was 0.6 after 0.75 s, 2.2 after 1.5 s) |

**The camera:** free, it holds while he stands or runs across or toward
it, and eases in behind him only while he runs away. Free 3.6 back
(was 3.0), the sprint 3.2 on the shoulder, locked 5.4 wide.

- Program memory went down: 7,885 words of 8,192 (P16 was 7,959). The
  tank's walk and turn, the quick turn, the flick and the style grammar
  paid for everything above. No new cells: the quick turn's and the
  flick's became the dance's.
- 68 tests: ten rewritten for the new scheme, eight new.
- **Not done:** the walk's planted stride (P15) has no slow gait to play
  any more -- the jog uses the run's poses at a jog's cadence. A dash
  (DMC's Trickster) has no button of its own; the dodge is the closest.

## P17 on glass: turned down (2026-11-20)

The player played P17 for 81 seconds and said no. The design they gave
instead, close to verbatim: the base d-pad is TANK CONTROLS -- controlled,
unit-like movement, "for exactness, that is at the core". On top are the
three attacks, which go "in the direction of the d-pad -- fast, and snaps
to the direction so you know where the hit will land". No magnetism: the
precision is the point. P17 is kept on its branch as a record; P18 is
built on P16.

## P18: the four modes (2026-11-20; not yet on glass)

| mode | buttons | movement | A | attacks |
|---|---|---|---|---|
| the tank | neither shoulder | Left/Right turn, Up/Down walk | the DODGE, the way the pad points (back with none) | the way the pad points from his facing, snapped there |
| targeting | R | planted, facing the target; Left/Right change targets; Up/Down step the shot high / mid / low | the dodge | at the target; an attack HELD is FOCUS: the world at a third until it is let go, then the blow |
| the boxer | L | square steps on the cross he held | the jump; with a direction, a directional jump and flip | the way the pad points from the cross |
| the run | L + R | runs the way the pad points round the target (Up at it, Down away, Left/Right round it) | the jump | the gun shoots the target |

**The three attacks**
- **Primary (X): rhythm.** The gap since the string's last blow *ended*:
  a tap during it or within 14 frames keeps time; 15 to 55 is a wait;
  longer, a new string.

  | rhythm | string |
  |---|---|
  | X X X X | jab, cross, lead hook, rear uppercut (the launcher) |
  | X - X X | jab, (wait) lead hook, rear uppercut |
  | X X - X | jab, cross, (wait) rear hook |

  Shots may fill a wait; a third shot in one loses the string. A tap while
  the string's next blow still waits in the buffer is the same beat, so
  mashing plays the steady string instead of skipping to its finisher.
- **Secondary (B): the gun.** Tap, or hold 26 frames for the charged
  shot. It goes exactly along the pad (16 degrees either side) and hits
  only the demon that line meets -- the old shot hit anything within 13
  units. It does not move him.
- **Special (Y): the haymaker.**

**Targeting's shot height:** high is the head (x1.35, so 9 for a plain
shot); mid the body; low the legs, which staggers a standing demon and
stops its approach (a plain shot at mid only chips, as P16 made it).

**Slow motion** is a freeze two frames in three for him and the demons
alike, on the hitstop's own path, so every rhythm keeps the fight's time
and the buttons are read throughout. FOCUS (targeting, an attack held)
lasts while it is held. A launcher that lands gives 40 of the fight's
frames of it (about two seconds), and a shot in it tracks the body in the
air.

**The camera, a shot a mode:** the tank 3.0 back and square; the boxer
4.0 on its cross; the run 5.4 wide on the target; targeting 2.8 over the
right shoulder, in to 2.2 in focus. Distance and lean ease between modes;
the yaw turns at most 12.7 degrees a frame. Targeting is a permanent plant,
so the operator's AIM shot frames it.

**Kept from P17:** the dodge is untouchable for its 12 frames, cancels a
swing's recovery, and a fist dodged through pays 30 style; no fist lands
while he reels or more than 0.9 up; the style meter cools at 0.25 then
0.75 a frame after one and two seconds idle.

**Gone:** the chords (A+X, B+Y, A+B), the quick turn, METEOR and the
prowler's turn, fencing, the locked style flips, the Devil Trigger shot.

Program memory 7,974 of 8,192 words (P16 7,959); no new cells. 66 tests.

## P19: the city (planned 2026-11-21; on the SRAM build, frontier 19)

The player's direction: expand the world; "plazas and streets"; take what
serves from Terminal Limit's generator. `games/tnd/city.py` is that
generator, ported and changed where measurement said so (its docstring
and tests/test_city.py): a 16x16 spanning tree of streets, START and the
CORE at the ends of its longest street, 6-8 districts in order along the
route through numbered gates, danger 0..11 rising toward the core, and a
2x2-node plaza at each district's heart.

**No geometry streams.** The street a node shows is one of six PIECES --
dead end, straight, corner, tee, crossing, plaza -- and the six meshes live
in DMEM once, where the crossroads' 3,940 words are today. A node's piece
is an OBJECT: the kind's mesh, placed at the node and turned a quarter
turn at a time. The city itself is the map: a byte a node (its four ways,
its district, plaza or not), 64 words for 16x16.

**What is drawn:** the nodes within two streets of the one he stands on
(walls hide the rest, and the fog takes everything past ~47 units), found
by walking the map each frame -- about 5 to 9 pieces, the 20 objects the
crossroads costs today.

**BLOCK = 32 units**, a power of two: a position's node is a shift, as the
VM has no divide. 16 nodes is 512 units across.

**As built** (the plan above, then what measurement changed):
- **Pieces, not kinds.** A node's sides are CLOSED, a street ARM, or OPEN
  into a plaza; a piece is the canonical side pattern (9 occur on seed
  666142), built in nine cells cut at the facade line 9.1 out: walls where
  street meets block, one height a block so corners meet flush, every wall
  dropping to 8 units for its last 3 before the tile's edge (so any
  neighbour meets it), a set-back tower over long walls, a lamp at a jutting
  corner, a centreline down each arm. 538 faces for all nine; one object a
  node, turned by yaw (768 is a clockwise quarter, exact).
- **The origin is the first plaza's centre**, so the fight opens where the
  crossroads stood, the ring of three unchanged -- in a square 46 across.
- **The map word**: sides (8 bits), yaw (10), piece (5), district (4), the
  side toward the core (2). The arena, the walk, the spawns, the gates,
  the dusk and the pointer all read it.
- **The arena** is the map's: the junction, plus a side if it is not
  closed, plus a corner only between two open sides; 7.1 from any wall.
- **Spawns** land a frame after their request (DMA), so they are placed
  then: in a plaza, the old ring round the plaza's centre; in a street, down
  one of his node's streets 22-30 out. **The leash** re-places a demon that
  is neither in his node nor one his streets reach, once it is off screen
  (or past the fog, before the cone test's squares can overflow).
- **Gates** are map bits: shut, the street reads CLOSED (the piece still
  shows it; the arena stops him; the walk stops there) and a red-and-black
  wall stands across it at the junction's edge, where he stops. Clearing a
  district opens the next; its horde waits until he stands in it. Retry
  shuts them all again.
- **The dusk is the district's**, the opus toward the core: a bruise
  violet, ash, ochre, blood red (pure black sank every wall into the sky).
- **The pointer**: away from the fight, a gold arrow at the top of the
  screen points down the next street toward the core -- one of eight ways,
  by comparison, the machine having no divide. Display-list triangle 0,
  every frame; the HUD's words moved to 1.

- **The story starts at the start** (the player: "start at the start,
  more cinematic and narrative"). Start puts him in the dead end at one end
  of the longest street, facing out; the street is empty. Each district's
  horde sleeps in its plaza and WAKES when he walks in -- the ring round
  the plaza's centre. Before that the arrow leads to the plaza (map bits
  29-30); after a clear, on toward the core. A death is the story again:
  the alley, every gate shut. (The mechanics tests still open in the first
  plaza, the three awake: they test the fight, not the walk to it.)
- **Tight streets** (the player: "tighter and less wide"): 4.4 to the curb
  where the crossroads' arms had 7.8, walls 5.7 out, a body kept 3.7 from
  either; the tile stays 32, so the blocks are deep and the streets are
  canyons. Plazas stay near 40 across.
- **Measured on silicon** (the first 48 s of the 28-minute P18 tape, the
  same thumbs on both carts): peak 59% on the crossroads, 52% in the city;
  median 30% on both; no dropped frame. The walls hide what the
  crossroads' long arms drew.

**Steps**
1. The six piece meshes (the crossroads' own builders: sidewalks,
   facades, corner towers, lamps, paint), the map table, and the draw
   window. Gate: the cart builds, the law renders a city frame.
2. The arena test becomes the map's: a point is in the street if it lies
   in its node's square, in one of its open arms, or anywhere in a plaza.
   He, the demons and the lens (all three already ask L_ARENA).
3. The horde lives in districts: a district's reserve from its danger,
   spawns at its plaza; a gate is a wall until its district is cleared.
4. A district's fog and light; the pointer to the next gate; then the
   pause screen's map.

## P20: a town, and the free run (2026-11-21; not yet on glass)

On glass, the city "is getting there" but "still feels too spacious ...
the streets need the side walks like in the original. it should feel more
like a city, town ... a tighter experience, and feeling overwhelmed at
times." And a control the player designed: "left shoulder held and double
clicking right shoulder to hold does the fast running without a target."

- **The free run.** L held, R pressed twice within 20 frames and held:
  the run with no lock, steered as the tank steers (Left/Right turn at the
  tank's 12 a frame, Up drives, nothing held coasts), at the run's 0.13.
  Letting go of either shoulder ends it, keeping his heading. One press of
  R with L is still the locked run; a slow second press is not a double.
- **The tile halves to 16.** A block is a few seconds' walk; START to the
  first plaza is half what it was; the plaza is 25 wall to wall (was ~43).
  The road is 3.4 to the curb, the walls 4.7 out (9.4 wall to wall, was
  11.4), a body kept 2.7 from the centreline.
- **What makes a street hold you** -- urban design's measures, and what
  the pieces build for each:
  - *enclosure*: walls as high as the street is wide or higher -- fronts
    of 6.5 to 13.5 over a 9.4 street, and the haze near (8 to 40, was 15
    to 47), so the street ahead closes in;
  - *human scale*: narrow fronts, a shop at the foot of each -- every wall
    cut into fronts at its cells, each with its own height, colour and
    shopfront (lit, glass, shutter, door);
  - *transparency*: lit windows -- two fronts in five carry a lit floor
    (two, if tall);
  - *complexity*: no two fronts alike side by side -- heights step, with a
    cap where they do; a warm lantern on a wall of every piece.
  A front at a tile's edge always stands 9.0, so pieces meet flush whatever
  they are.
- **The sidewalks are back**, the crossroads' own: raised 0.15, a curb face
  to the road, a pad round every jutting corner. (The city's had been
  built behind the walls -- the offset's sign was backwards since P19 --
  which is why they never showed.)
- **Demons come from two streets on**: a sent demon is placed at the node
  past the next, on down the street if it goes on, else round its corner.
- **Paid for in place**: the nine pieces are 3,074 words of DMEM against
  the canyon pieces' 3,250 (no towers, no seam steps); the gate is drawn
  unculled at half its faces.
- **Measured on silicon** (the same first 48 s of the P18 tape): peak 55%,
  median 30%, no frame over the ceiling, none dropped (the canyon city 52%,
  the crossroads 59%).
- **Overwhelm**: see P20b.

## P20b: dark, demonic, and the horde (2026-11-21; not yet on glass)

"the hordes should be overwhelming / i still like the asthetic from the
original, it should feel dark and demonic heavy fog." Asked how (the
object list holds 64; a demon is 12), the player chose two answers at once:
a lesser swarm, and the three made relentless.

- **The crossroads' look, kept dark**: soot and old brick fronts, black
  glass, and the only light ember -- shopfronts, lit floors and lanterns
  burn red-orange. The haze is HEAVY, from his heels (2) to full at 34, the
  districts' opus sunk into the crossroads' blood (0x4C1C2A to 0x8E160C,
  0x6A2420 among them): a little lighter than the walls, so the street
  dissolves into red murk rather than into dark.
- **The ground rides the camera in rings from 4** (was one triangle to
  15): with the haze starting at 2, a triangle's linear depth stepped the
  fog where it met the rings. True depth near the lens let the ground win
  over the sidewalks, so the plane drops from -0.2 to -0.6 -- it is one
  flat colour, so only its fog moves, by under a sixteenth.
- **The swarm**: up to eight lesser demons, one object each (a hunched,
  horned, long-armed thing, three quarters his height, ember eyes, 322
  words), four in the first district and one more a district. They come
  out of the haze two streets on, one every eight frames while the
  district is awake and his; far off they make for his junction (so they
  come down the streets), near they take a place in a ring round him that
  is the CAMERA's (across the front and sides of the shot, never between
  the lens and him). They lurch (a lean, a sway, a bob), claw for 4 every
  46+ frames (a dodge is untouched), and fall to any blow: a fist cleaves
  through every one it meets, a shot drops every one on its line. They
  drop where they stand when the district is cleared. Not drawn within 2.5
  of the lens; never past the list's room.
- **The three, relentless -- deeper in**: from the second district all
  three may attack at once (still only on screen), and each district
  starts the next wait 5 frames in, to 20 (the 30-frame tell is never
  cut). The first district keeps the fight every mechanic was tuned on.
  District 3 against district 0, untouched for 600 frames: 17 swings
  against 12, all three swinging together on 89 frames.
- **Measured on silicon** (a local build that starts the fight in the
  first plaza with all eight: TND_SWARM=1): peak 669,149 (77%), median 72%,
  none over the ceiling, none dropped. The frame's vertices peak at 2,040
  of the cache's 2,048.

## P21: layers, and the base (2026-11-21; not yet on glass)

The first town tape (1m41s, replayed to the Pocket's save word for word):
93 seconds in the streets and never the first plaza -- no fight at all.
Fifteen seconds of it the free run; much of the rest swings at nothing. Of
672 frames of tank walking, 227 were slowed by a wall and 149 stopped.

The player's frame for the game: the city is a gauntlet to the core;
things are locked, and he fights through to a key to unlock the way. The
combat's feel comes first, and it is LAYERED -- comfortable at the base
(walk, aim, fire, close), RE6 as it heats, DMC at its hottest -- so the
game is built in layers, each judged alone on glass:

    TND_LAYER=0   the BASE: the city and the player. The tank on the
                  d-pad, the dodges, the jab and its context; a key and a
                  gate a district. No shoulders, no enemies.

A layer build is local (build/layerN/tnd.zol); the committed cart is the
whole game and is byte-identical with the flag unset. What a layer settles
is merged into the game.

**The base, as built** (all of it behind BASE in gen_tnd.py):

- **The walk has weight**: his pace is a speed that eases to what the pad
  asks (the ramp knob a frame: 90% in ten frames, and as long to settle).
  The heading is still the tank's, exact; the turn is not eased.
- **The quick turn**: Down + A, half round in eleven frames. A with any
  other direction is that dodge still; A alone the back dodge.
- **A wall carries him along it**: it leaves him at least the slide knob's
  share (0.6) of his pace along it; under an eighth of his pace along it
  (dead on, to about 7 degrees) he still stops. At 10 degrees off dead on
  he slid at 0.0056 a frame; now 0.0191.
- **The follow keeps its distance**: the tank's lens is straight behind
  him, so a wall it backs into faces away and is not drawn -- it stands in
  the building rather than closing to half. 3.0 at the dead end's wall.
- **The jab's context**: a district's key lies in the middle of its plaza
  (a gold thing that spins faster in reach). In reach (1.4) and ahead of
  him, the jab picks it up: he bows and is held for the pick knob's 18
  frames. The key held, the jab at the district's gate (in reach of its
  bars, ahead) unlocks it. Anywhere else the jab is a jab; he is never
  turned or drawn to anything. The arrow leads to the plaza, then, the key
  held, to the gate.
- **Tuned on glass**: SELECT held makes the d-pad a tuner -- Left/Right
  pick a knob (0 walk, 1 ramp, 2 turn, 3 quick turn, 4 the lens's distance,
  5 its height, 6 slide, 7 pick-up frames), Up/Down turn it a notch -- and
  the screen shows the knob and its notch (50 where it started). The tape
  carries the presses home; the replay reads the values.
- **Fast gates**: tests/test_tnd_base.py is four tests, half a minute in
  parallel (the game's suite is twenty minutes).
- **Measured on silicon** (out of the dead end, into walls, quick turns):
  peak 55%, median 44%, none dropped.

**Found on the way**: the swarm's code is eight unrolled copies, and the
game's program is 16,152 words of its 16,384-word page. The swarm must
become one routine over an index before anything else is added above the
base.

## P21b: the base on glass, and the machine's unused parts (2026-11-21)

**On glass**: eleven minutes in the first base, "the best so far". The
tuner's notches, read from the tape's pad log (and matching the replay at
its 5,000-frame mark), are the base's starts now: walk 0.066 (twice the
archive's), ramp 0.73 (all but at once), turn 14, the quick turn 80 a frame
(seven frames), the lens 2.0 behind and 1.65 up, and the wall's slide OFF --
a wall leaves what runs along it and no more. The stride advances by the
ground covered, so at twice the pace his feet stay planted.

**The horde tape** (10m43s on the P20b cart, seen only now): 351 s in the
game, one death 61 s after the plaza woke, ten of the district's thirty
felled, the district never cleared. The boxer 44% of it, the tank 33%, the
run 15% (44 s of it free), targeting 7%.

**The arrow was wrong since P19**: its two ways -- to the district's plaza,
to the core -- were swapped (a test for bit 27 that should have been 29).
Asleep, a district's arrow led to its gate, not its plaza, at the ten
street nodes of district 0 where the ways part. Fixed in the game and the
base; the base has its test.

**The machine's unused parts, in the base** (asked: "add the zeta
subsystems we havent used to this layer"):

- **The sky is the haze.** CLEAR_RGB is a constant of the machine, so the
  sky cannot be cleared to another colour; but a face past the fog's far
  end is exactly the fog's colour, whatever the district's. One triangle
  rides the camera 60 out, wide enough that its screen clip is wholly
  covered. (knob 9)
- **OBJ_BLEND**: his shadow, a dark blot half through under him, and one
  under the key -- weight on the street, and the key's hover read.
- **OBJ_EDGE**: the jab's context shown -- the key outlined bone-white
  when the jab would take it, the gate when it would unlock it. Free, the
  spec says, and the meter agrees.
- **GRADE_SRC**: a curve at the glass that sinks green and blue under red
  -- off, or one of two weights. (knob 8; starts at 1)
- Law against silicon on two routes through all of it: 484 frames, none
  differ, 33 of them outlined. Peak 50% of the frame.
- **Not yet, and why**: the PICK register and the visibility counts are
  for the gun and for enemies -- the layers above. Textures and per-vertex
  light are the base's next step: they change the pieces' mesh format
  (a texel word a vertex) and want measuring first.

## P21c: the second base tape -- five gates, and a knob that hung him (2026-11-21)

4m44s on the base with the player's starts: "this looks good, i think i
crounch could be more subtle but I got into a glitch at the end". Five
keys found and five gates unlocked in four minutes (district 5 of 7), the
sixth key picked up -- and there he stood, bowed, for the last seventeen
seconds.

- **The glitch**: looking for a shorter pick-up he turned the pick knob
  down past zero, to -10 frames. The pick-up it began counted down from
  -10 for ever (the test was "is it zero", not "is it above zero"), holding
  his pad at nothing and his body in its bow. Not a fault of the game's
  rules: a tuning tool with no limits.
- **Every knob has a least and a most** now, chosen so the game can play
  at either; the pick-up and the quick turn count only while ABOVE zero.
  tests/test_tnd_base.py turns every knob as far as it goes, both ways,
  and then picks up, quick turns and walks.
- **A subtler pick-up**: held 8 frames (was 18), bowed 14 degrees (was
  34). The bow is knob 9; the sky (kept on, both sessions) is no longer a
  knob. The heavy grade he chose is the start.
- **A faster trace**: the VM without the paint replays a tape at ~145
  frames a second (the paint is 90% of a law frame) -- sound for any cart
  that reads nothing the paint answers (PICK, VIS), as TND does not. The
  4m44s tape in two minutes.

## P22: the base is lit (2026-11-21; not yet on glass)

"lighting then i think we can discuss the next layer advanced movement."

- **What the machine gives**: one light direction and two levels for the
  whole frame (LIGHT_DIR, LIGHT_AMB, LIGHT_DIF), and a word a vertex that
  OBJ_LIT reads as a normal: level = AMB + DIF * max(0, N.L), carried
  across the face. The normal is NOT turned with the object.
- **So the light is baked a corner at a time**: with the light straight
  down, a vertex's "normal" (0, t, 0) is simply how lit it is, whatever
  way its piece is turned. What burns -- a lit shop, a lit floor of
  windows, the lantern -- has corners of its own at full; every other
  corner takes the glow of the burning faces near it, the lantern's light
  by the inverse square, and the street's own level at the foot of every
  wall. A shop's glow climbs the wall over it and lies on the sidewalk at
  its foot; fronts shade from a lit neighbour into the dark. The first
  wall is cut under its lantern so there are corners where the light is.
- **Stored lit**: faces that do not burn are stored at their lit colour
  (x 32/13), so in the town's own dark they show as they did.
- **Each frame**: the town's dark is the light knob's level (knob 6; the
  wall's slide, which the player had turned off, gave up its place and its
  code), a notch darker a district toward the core -- 13 at the start, 7
  in the last -- with what burns kept at full. The lanterns gutter (two
  frames, three levels, about once a second). A flash lifts the dark when
  a gate unlocks (20 levels, dying over a third of a second) and a little
  when the key is taken.
- **The pool on the road, tried again and taken out again**: as a lit fan
  it had its falloff at a distance, but the machine carries light across a
  face in screen space, and under the lens the fan was a flat pale slab.
- **Room**: the base carries no demon meshes now (3,000 words), which is
  where the corners' words came from. The game above the base has 63
  words free: lighting the game is a budget question for the merge.
- **Measured**: peak 55% of the frame on the street route (50% unlit).
- **LAW AND SILICON DISAGREE, by a level, where a lit face is clipped**:
  on the street route 42 of 337 frames differ -- one 5-bit level (rarely
  three) on the pixels of a lit face cut by the near plane (the sidewalk
  beside the lens; at the start, the sidewalk at the wall behind him).
  Unlit, the same routes were bit-equal, and the plaza route still is. It
  cannot be seen and no game state reads it, but the cross gate's promise
  is bit-equality: a platform fault in how the clipper carries a vertex's
  light, law or RTL, to be run down. (The lit witness cart has no clipped
  face.)

## P23: onto the sidewalk (2026-11-21; not yet on glass)

"can we step onto the side walk?" In the base the street is his from wall
to wall.

- **The arena's width** is 0.6 from a wall now (it was 0.7 inside the
  curb), and a cell, because the lens asks the same question of a wider
  street.
- **His feet step up the curb**: where he stands in his tile, a sidewalk
  lies wherever a wall stands beside him -- past the curb line with no
  street on that side there, or on a jutting corner's pad. His body and
  his shadow ease up its 0.15 and back down.
- **The lens beside a wall**: 0.6 from a wall, turned a little from it, the
  lens stood in the building looking along it and that side of the street
  was gone. Off the street (0.15 from a wall, for the lens) it is brought
  straight back across to the wall's face -- found by halving between it
  and him -- eased a quarter a frame, and from there it looks AT him, so
  he keeps the middle of the shot. If that would leave it under three
  quarters of its distance, the wall is BEHIND him and out of the shot,
  and the lens stays in it at its whole distance, as P21 promised.
  Against a wall and turned 25 degrees off it: the lens 0.17 inside the
  wall's face, 1.87 from him, looking 10 degrees off his heading.

## P24: layer 1 -- the left shoulder (2026-11-21; not yet on glass)

The player's design for the layer above the base: "single click hold is
boxing camera backs up a bit and it should feel like your squaring up,
doubble click hold is running parkour, fastest should feel momementum and
camera trailling to follow. jump and pressed again to flip".

    TND_LAYER=1   the base + L. R is still nothing; no enemies.

Almost all of it was in the game already, behind other inputs (P10's
parkour, P18's boxer and double jump, P20's free run): the layer rewires
it to L and gives it a page of knobs.

- **L held: the boxer.** He squares up on the cross he faced (steps the
  four ways without turning), and the lens eases back from the tank's 2.0
  to 2.8, square behind.
- **L clicked twice and held: the run.** L going down within 20 frames of
  its last going down. The pace builds to 0.13 a frame (twice his walk) in
  about 0.7 s; he steers as the tank steers but slower (9 a frame), and his
  path comes round after his heading (the grip): momentum. The lens falls
  back to 3.4 and TRAILS -- it comes round to his heading by a tenth of the
  gap a frame (an eighth elsewhere, capped), a unit at least, so it arrives
  without a snap. Out of the run he slides to a stop on the tank's
  friction, and the run's lean dies away.
- **A jumps, in either; A again flips** -- the way the pad points, or
  forward with none held -- and the flip carries him higher (1.6 up, then
  to 3.4). In the boxer a direction with A no longer flips from the
  ground: the jump is the first press, the flip the second. In the tank A
  is still the dodge, and Down + A the quick turn.
- **Its knobs** (SELECT + the d-pad, as the base's): 0 the run's pace,
  1 how fast it builds, 2 its turn, 3 the grip, 4 the run's lens, 5 its
  trail, 6 the boxer's lens, 7 the boxer's step, 8 the jump, 9 the frames
  between the two clicks. Each has its least and most, and a test turns
  them all to both ends and plays. The base's knobs are settled in this
  build at what the player left them.
- **Measured on silicon** (boxing, jumping, flipping, then ten seconds of
  running with turns and flips): peak 57%, median 49%, none dropped.
- tests/test_tnd_layer1.py: five tests, about half a minute in parallel.

## P24b: standing in the run; and the light, one level a face (2026-11-21)

- **"when stationary the player should be in the standing position"**: the
  run held with nothing driven and his speed run down (under 0.02), he
  stands as the tank stands, and the pad drives him again at once.
- **The smooth light came out in green and pink.** A render of the
  standing run showed patches of wrong hue on the sidewalk by the lens.
  The pick register named the faces: plain sidewalk, corners lit 76, 76,
  55 -- drawn (16, 24, 14) where (17, 16, 15) was meant. The machine steps
  a colour across a face from one of its corners in 1/256ths of a level a
  pixel, each channel on its own (CFP = 8). A face cut by the near plane
  has that corner thousands of pixels off the screen, so each channel's
  rounding has grown to whole levels by the glass, and the channels part:
  hue. A limit of the machine, law and silicon alike.
- **So the light is one level a face.** Each face takes the mean of its
  corners' light, and corners are shared only between faces at one level:
  no step across a face, nothing to round, exact. The glow now climbs a
  wall band by band and lies on the sidewalk a segment at a time. It costs
  corners (a piece is 109 to 187 vertices, 66 to 110 before), paid for by
  the demons' clip table, which the layers do not use. LIGHTING THE GAME
  ABOVE THE LAYERS IS NOW A REAL BUDGET: the lit pieces are 6,700 words,
  the unlit 3,100, and the game has 63 free.
- **Overlapping sidewalks**: at an inside corner two walls' sidewalks lay
  one on the other; at different levels they would fight for every pixel.
  The wall across now gives the corner to the wall along.
- **P22's open mismatch, narrowed, still open.** One level a face did NOT
  close it (43 of 337 frames on the street route, as before), nor did the
  overlaps. With EVERY face at one same level, 29 pixels still differ on
  the frame tried, along the edges of lit faces cut by the near plane:
  law and silicon draw a cut lit face's EDGE a pixel apart, where unlit
  they agree to the bit on the same geometry. So the fault is in the lit
  path's clipping, not in the light's arithmetic. The silicon's picture is
  what the glass shows, and it is sound; the replay's may differ from it
  on those pixels.

## P25: the layer on glass -- the walk's slabs, a runner's arms, the wall jump (2026-11-21)

Twenty minutes of layer 1 on glass (the tape: 71,006 frames, to the last
district in under four minutes; the run 51% of it, the tank 29%, the boxer
20%; 147 jumps, 120 flips). "theres a few visual graphics bugs on the
edges of the screen, also the running animation, the arms dont swing like
how a runner would swing there arms. would be cool if we could do a wall
jump."

- **The knobs he left are the layer's starts**, read off the tape and
  checked against the build word for word: the run 1.4x (0.18 a frame)
  and quicker to build, turning as the tank's 12, gripping more than twice
  as hard (0.74: less drift than the archive's run), the lenses a notch
  nearer (the run's 3.2, the boxer's 2.6), the run's trailing longer
  (0.07), the boxer stepping half again as fast, the jump a little lower,
  and the two clicks given 40 frames -- the most the knob allowed, so its
  ceiling is 60 now.
- **The bugs at the edges** were P24b's light, found in frames of his own
  tape: one level a face made each stretch of sidewalk its own grey, and
  by a lit shop a pale one -- hard-edged slabs along the bottom and sides
  of the screen wherever the walk ran under the lens; and dark glass,
  under the grade, was a black rectangle in the wall. The walk is ONE
  level everywhere now (the light is the walls'), and dark glass is a dark
  colour, not a hole. (Law and silicon drew four moments of the tape alike
  to the pixel: what he saw was the picture, not the glass.)
- **A runner's arms.** The archive's run pumps the arm nearly straight
  through 140 degrees with the elbow bent across the body: the hand goes
  over his head. Re-posed on the archive's own rig (tools/tnd_extract.py,
  the clip "run2"): the same stride and trunk, the upper arm swung 28
  degrees ahead and 50 behind, the elbow bent FORWARD to a right angle,
  closing as the hand comes up. The layers play run2; the game keeps the
  archive's until the merge.
- **The wall jump.** In the air, a step the street refuses is a wall
  touched, remembered eight frames. A then kicks him off it: thrown
  straight back at 0.20 a frame (in the run, across the street before he
  is down), keeping what he had along the wall, his heading mirrored in
  it, up with the flip's rise and its tuck. Twice an air -- a street is
  two walls to climb between -- and a landing makes the count new.
- **Measured on silicon** (the layer's route): peak 64% (57% before the
  light was one level a face: more corners), median 51%, none dropped.
- tests: 8 for the base, 6 for the layer.

## P26: the walk's stride; the layer's knobs again; the wall jump crosses (2026-11-21)

"this feels good, only thing i found was the base walking leg cycle looks
comedically fast, should look more intimidating."

- **Why it raced.** P21b tied the stride to the ground covered, so his feet
  stayed planted -- and at the pace the player then chose (0.066 a frame,
  twice the archive's) the archive's 0.48-unit shuffle ran at 7.5 steps a
  second. The rig cannot plant a slow walk at that pace: its legs are 0.7
  long and its hips do not drop, so the planted foot misses its mark by
  more than a tenth past a 0.75 step, and even a 1.0 step would be four a
  second. At 4 units a second he is, in his own body's terms, running.
- **What was done.** The walk is re-solved on the archive's rig at a longer
  stride ("walk2": 0.75 a step, the same guard), and played SLOWER than
  the ground asks: the legs knob (the base's knob 1, where weight was --
  that is settled at 0.73) is poses of the stride a unit of ground. It
  starts at 13.3: 3.3 steps a second, his feet giving up a third of the
  ground. Planted would be 20 (five steps a second). The player chooses
  between a slower stride and a truer plant on glass.
- **The layer's knobs, a second time**: ten more minutes turned them again
  (the run 1.24x, grip 0.90 -- almost no drift -- the lenses back out to
  3.4 and 2.8, the jump the archive's, the clicks 44 frames); those are
  the starts.
- **The wall jump crosses the street at any run pace.** Its throw was the
  run's pace knob times 0.20, for a flip's 20 frames; at the player's
  slower run it fell short of the far wall and the second jump never
  came. The throw is its own now: 0.30 a frame for 24 frames, 7.2 units,
  whatever the run's knob. Two walls, two jumps, to 4.2 up.
- **Open, for the player**: Down in the run does nothing (he coasts). On
  the second tape Down was held 2% of the run.

## P27: the slide (2026-11-21; not yet on glass)

Asked what Down should do in the run (it did nothing; a skid turn, a hard
brake and a slide were offered): "slide!!"

- **Down, in the run, at speed and on the ground**: he goes down feet
  first and slides the way he was heading, unsteered -- a little faster
  than he ran (x 1.12), scrubbing 2.8% a frame -- for as long as Down is
  held: 16 frames at least, 44 at most, 3.9 units held from a full run. He
  comes up over 6 frames into the run at the speed the slide left him, or
  to a stand. A wall stops it. Standing in the run, Down is still nothing.
- **Its pose** is new, on the archive's rig (tools/tnd_extract.py,
  "slide"): the hips thrown back and dropped until the lowest of him is on
  the ground, the lead leg out ahead, the rear folded under, the guard
  kept; two poses going down, the slide held. The layers' pose bank only.
- The third tape of the layer (four minutes, to the last district) turned
  no knob: the layer's starts are settled.
- tests: 8 for the base, 7 for the layer.

## P28: layer 2 -- shadow boxing (2026-11-21; on glass: reworked in P29)

"for the fighting next, think shadow boxing. we want to be able to control
what gets thrown and where it lands precisely. thats why i was thinkg
directional with dpad. it should feel like theirs weight to each and the
player shouldnt be looking like he's just teleported to the other
directions." Asked three things, the player chose: the pad picks the
DIRECTION (not the punch); after a turn he STAYS facing it; Y is the HEAVY
version of each.

    TND_LAYER=2   the base + the left shoulder + this. No enemies: the
                  blows are thrown at the air.

- **He turns to it.** Until now a fist thrown any way but ahead snapped
  his body there for the blow and back after -- the teleport. Now he
  PIVOTS there first: the blow held at its wind-up, its lunge kept, his
  heading turned at the pivot knob's units a frame (36: a side in 7
  frames, behind him in 14) -- then the blow runs. The farther round, the
  later it lands: that is its weight. Ahead (nothing held, or Up) it is
  thrown at once, as before.
- **He stays.** The strike commits his heading: he is facing where he
  struck, the lens comes round after him, and the pad means "from where
  he faces NOW" for the next blow. (So a string to one side is Left + X,
  then X, X.) Through a strike the tank's turn is off: it is thrown.
- **Y is the heavy version.** Y takes the string's next place exactly as
  X would and throws that blow's heavy, from the blows already in the
  bank: the jab's is the lead hook, the cross's the rear hook, a hook's
  its uppercut, the string's last the haymaker. Y Y Y Y: the two hooks,
  the uppercut, the haymaker. X X Y Y: jab, cross, lead uppercut,
  haymaker. Heavy blows (hooks and up) pivot at their own slower knob (24).
  Y alone was always the haymaker; that is the string's end now.
- **Its knobs**: 0 the pivot, 1 the heavy pivot, 2 the lunge (x each
  blow's own), 3 the frames a tap still keeps the string, 4 how long a
  wait may be.
- **A fault found on the way, in the base since P21**: the jab's context
  (is the key in reach?) squared the distance to the key, and past 181
  units the square overflows the word and reads small -- across town from
  the key, the jab picked it up. A layer test happened to stand there.
  Each axis is checked near first, now.
- **Measured on silicon** (strings in every direction): peak 58%, median
  49%, none dropped. tests: 8 base, 7 layer 1, 7 layer 2.

## P29: shadow boxing again -- placed, and posed (2026-11-21; on glass: reworked in P30)

The player, on glass, of P28: "we need major improvements on the shadow
boxing, the directional snappiness was important because the intention
is to place the jab exactly where we want it. i thing the punching poses
need substanitlal work. I should be able to anticipate where the jab will
land. then its two combo jab jab, three combo jab jab left hiok, jab jab
wait right upper cut. hay maker is the special button with no previous
jab input. all the punches should posed tactically".

- **What P28 got wrong, on the tape** (54 s, no knob touched): a blow to
  the side or behind HELD at its wind-up until he had turned -- up to 24
  frames for a hook thrown behind. Weight bought with the one thing the
  layer is for.
- **Placed.** The blow goes the way the pad points the frame it is
  thrown: its clock runs at once, its lunge is along that way, and it
  lands on its own frame whichever way that is (the jab: the same frame
  ahead, to a side, behind). His body comes round INSIDE the wind-up --
  176 of 1024 a frame for a jab (a side in 2 frames, behind in 3), 128
  for the heavy ones -- so he is never teleported, and never late. He
  still stays facing it. Knobs 0 and 1 are those turns (512: at once).
- **Posed** (tools/tnd_extract.py STRIKES). The archive's jab travelled
  25-30 degrees off his facing line, and the hook and uppercut ended off
  it too: there was no line to read. The four blows are authored now as
  keys over their own frames -- where the fist IS (two-bone IK puts it
  there exactly), the trunk's turn and lean, where his weight is, both
  feet planted -- and every one lands ON HIS CENTRE LINE:
  the jab at 0.70 ahead, shoulder height, the lead shoulder turned in
  behind it; the lead hook loads out to his left and comes across level
  at 0.44; the rear uppercut dips (the weight 0.12 down) and drives up
  the line at 0.40 to chin height and through; the haymaker winds back
  behind his rear shoulder, the lead hand out as the range-finder, and
  comes over the top to 0.72 with the weight behind it. Clips jab2,
  lead_hook2, rear_uppercut2, special2 (layers only; the archive's stay
  beside them). The fist's authored path is the hit's too, so the hit is
  where the drawn fist is.
- **Where it landed.** A small spark at the fist the first frame the blow
  is out. Shadow boxing hits air; the spark is the mark.
- **The strings are the player's.** X X: jab, jab. X X X: jab, jab, the
  left hook. X X (wait) X: jab, jab, the right uppercut. Y, with no
  string on: the haymaker. Y inside a string is not read. (P28's "Y is
  the heavy version of each" is gone.)
- **Not remeasured on silicon**: same vertex counts, one more small
  object for 6 frames; P28 measured 58%. tests: 8 base, 7 layer 1, 8
  layer 2; the full cart is byte-identical.

## P30: the count, the hold, and the boxer's feet (2026-11-22; on glass: revised in P31)

The player, on glass, of P29: "The boxing model needs better footwork and
the jabs turn the player, it shouldn't. Let's make a fun rythm system with
the jab button and the special. essentially the number of times we press
the jab it builds to a special terminator. each button can get held
keeping the string, slowing time and releasing. for specials the same, but
the damage output is higher and harder hitting. A player could in theory
just button mash fast, and still get combos to work, not working off a
specific time signature." And: "the slow motion gives time to think."
Asked: the pad with a punch -- "Always straight; d-pad is footwork"; the
ladder -- hook, uppercut, haymaker; the footwork -- all three (moving in
the stance, the feet during punches, the standing guard).

- **The tape** (9m30 of layer 2; 788 blows, 45% with the pad held): both
  pivot knobs turned to their floor, the lunge down a notch (0.9, kept).
  A thumb's X is down 7 frames at the median, 11 at the 95th centile;
  the fastest mash is a press every 9.
- **A blow goes where he faces.** No blow turns him, by a unit, on any
  frame. The pad at the launch is the blow's STEP, given with its lunge:
  Up in (0.81 for a jab against 0.39), Down out (0.42 back, no lunge),
  Left and Right 0.42 off the line. The tank's turn and walk are held
  through a blow and for 10 frames after one while a count stands, so a
  pad held for the steps does not creep his heading between them.
- **The count.** X is a jab, every time, and the jab thrown is counted
  (to three). Y ends the string with what the count has earned: none or
  one, the lead hook; two, the rear uppercut; three or more, the
  haymaker. No beat is read. The count stands while a blow is out, while
  a button is held, and 40 frames after (the keep knob). A jab gives way
  to the next blow once it has landed (7 frames: a 9-frame mash throws
  and lands every one); a terminator is thrown and ends.
- **The press's own frame.** The grammar waited out a 3-frame chord
  window before a tap was a tap; layer 2 has no chords. A jab pressed
  lands 4 frames later (it was 7).
- **A button held slows time.** Past 14 frames down (the hold knob; over
  any tap on the tape) the fight -- his own blow too -- runs one frame in
  three (the slow knob), on the freeze path the full game's FOCUS uses,
  and the glass sinks to a third curve; let go and it runs. Nothing else
  moves in this layer, so his own blow is what shows it. It hits no
  harder for being held: held is for thinking.
- **The drive.** A blow's lunge came with its launch: the haymaker slid
  1.3 units while still winding back. Now on its own frame -- the jab's
  1, the hook's 6, the uppercut's 8, the haymaker's 13 -- so he winds up
  where he stands and goes with the blow. A terminator's landing shakes
  the lens (2, 2, 5 frames).
- **The feet** (tools/tnd_extract.py, the P30 engine).
  The stance: the archive's guard stood 0.57 long and 0.20 wide with the
  rear leg straight out behind -- a lunge. Now 0.40 by 0.30, sat into the
  knees; the guard rocks its weight and bounces ("guard2", every layer's
  standing pose). The stance's steps are a bounce, the near foot down
  first, never crossing ("hop_*"; the archive's barely lifted a foot).
  A strike's feet are PLANTED IN THE WORLD: the lunge is an impulse then
  x0.82 a frame, so a planted foot goes back under him exactly as far as
  he has gone and the stepping foot lands where he will end -- the lead
  foot down with the jab's fist, the rear dragged up after; past his
  reach a foot drags. Five ways a strike (as it is, in, out, left,
  right), 20 clips; each foot moves in the world once, by exactly what he
  travels (the bake prints it).
- **CRAM.** 580 more poses did not fit beside the recorded song
  (4,063,248 words); layer 2 keeps one pose each of the cross, the rear
  hook and the lead uppercut, which its strings cannot throw.
- **Knobs**: 0 the step, 1 the lunge, 2 keep, 3 hold, 4 slow.
- **Not done**: the count is not shown on the glass; the stepped clips
  are baked for the knobs' defaults (off them the feet slide by the
  difference); layers 0 and 1 play the new clips with the old launch-frame
  lunge. Not remeasured on silicon (no new geometry; P28: 58%).
  tests: 8 base, 7 layer 1, 9 layer 2; the full cart is byte-identical.

## P31: the body turns to the blow; the strafe jump; the slowed lens (2026-11-22; not yet on glass)

The player, on glass, of P30: "The directional punches are to turn player
as if he was making a punch in that direction. For the boxer, the jumps
should be like a strafe jump in the four directions. the slow motions
need cameras focused on the hit location." Asked what his facing is after
such a punch: "The whole body should be turned, the tank and boxer camera
does not move. movement returns the direction to where it was before the
directional hits in the tank. in the boxer the camera is locked on the
player but can wander in position."

Three readings of the pad-with-a-punch had each been half of this: P28
and P29 turned his STEERING (so the lens came round, and the pad meant
something new after every blow); P30 turned nothing. There are two
headings, and the cart always had both: his steering (YAW: the tank's,
the lens's, what the pad is read from) and his body's (HEAD: what is
drawn, where a blow goes).

- **The tape** (7m54 of P30; no knob touched): 123 blows; all 21 of his
  jumps in the stance had the pad held.
- **His body turns to the blow.** The pad at the launch, read from his
  steering, is where the blow goes; his body comes round to it with the
  blow's clock running (176 of 1024 a frame: a side in two frames, behind
  in three -- there before a jab is out). It lands on the same frame, at
  the same reach, on his body's line, and its lunge carries him that way.
  His steering does not change by a unit, and the lens does not turn. He
  stands as the blow left him; a blow with no pad goes that way again
  (so Left + X, X, X is three to the left, and Up + X is ahead again);
  and movement -- the pad walking or turning him, the boxer's steps --
  brings his body back round. P30's stepped clips and its step knob are
  gone (the pad is the blow's way again, not its step); the planted feet
  stay, one way a strike.
- **The boxer's strafe jump.** In the stance, A with the pad throws him
  that way on his cross: 0.13 a frame (his step is 0.11) for a lower,
  shorter jump -- 3.1 units -- facing as he was, with its own seven poses
  each way (the pushed-off leg trailing, the near one reaching). In
  flight he keeps what the jump gave him; he lands with half. No pad: the
  jump, as it was. A again in the air is still the flip.
- **Time slowed, the lens goes to where the blow lands.** It comes in to
  1.3 behind him, over his right shoulder and 0.3 lower, and LOOKS at the
  place a blow's reach ahead of his body -- so a blow ahead is seen over
  his shoulder, one to the side in profile, one behind him coming at the
  glass. Eased in and out in real frames, not the slowed ones.
- **The boxer's lens wanders.** Its place comes after him by a share of
  the way a frame (8%), so it trails his steps, and from wherever it is
  it looks at him. Standing, it comes back behind him; out of the stance
  it is the follow exactly.
- **Knobs** (layer 2's page): 0 the body's turn a frame, 1 the lunge,
  2 keep, 3 hold, 4 slow, 5 the strafe jump's pace, 6 the slowed lens's
  distance, 7 the boxer lens's share.
- Not remeasured on silicon (no new geometry). tests: 8 base, 7 layer 1,
  18 layer 2; the full cart is byte-identical.

## P32: what the tape of P31 says (2026-11-22; on glass)

The player: "I don't think we need any more plain strong design decision
here. Look at the replay, do you see what I am going for?" The tape: 26
minutes of layer 2, three gates opened, no knob touched.

- **Slowed time is where he plays.** 45% of the tape was slowed (137 X
  holds and 92 Y holds past the hold knob; the longest 25 seconds). In
  it: 138 of his 249 jumps (176 of them strafe jumps), 245 of his 394
  flips and dodges, 46 wall jumps, and 144 of his 203 shots. X is held
  with A beside it -- one hold had 53 leaps and flips in it; Y is held
  with B beside it -- a hook thrown, held, and a volley (one hold: 48
  shots). The blow is the way in; the hold is the stage.
- **The lock held him still.** P30's lock (no walk or turn for 10 frames
  after a string's blow) ran off a clock that a held button stopped: in
  the tank he held Up through 41 seconds of slowed time and stood. Time
  slowed, the clock is now held just PAST the lock: the count kept, his
  legs his own. And the tank's rule that it does not turn with a face
  button down (the pad is then a blow's way) gives way too once time is
  slowed -- the button is the hold, and he steers.
- **The slowed lens was not the lens in the tank.** The archive's "punch
  overhead" (P12: the tank, a strike button held, the lens 3.6 up and
  back to choose an aim) took the frame whenever he stood in the tank
  with X or Y down: 10,776 frames of the tape. It is off in layer 2; on
  the same tape replayed, the tank's slowed lens is 1.43 from him (it
  was 3.60) and one frame is past 3.
- **A shot is a blow.** The gun snapped his body to the pad's way and
  back to his steering every shot -- in a volley, every shot. It still
  snaps there the frame it fires (a shot goes where it is pointed), but
  now he stays as it left him, a shot with no pad goes where his body
  faces, and moving brings him back: the fists' rule (P31).
- **Seen, and left**: R is held 106 seconds, 80 of them with L in the
  stance, where it does nothing -- the right shoulder is the next layer.
  Slowed, the lens is 1.4 from him in the run and in the air, where no
  blow is out (the run's own is 3.4): the tape cannot say how that
  feels. A pressed again in the air does nothing about 55 times (one flip an
  air).
- tests: 8 base, 7 layer 1, 20 layer 2; the full cart is byte-identical.

## P33: time dilated is the same fight; movement that ends where it ends (2026-11-22; not yet on glass)

The player, on glass, of P32: "what if gun and jump/evade also have the
slow down. work on the dodges it feels to slippy. for all movement I
should be able to have accurate prediction of where I'll land or be. It
should feel like a good platforming kit." And: "Im sure its about the
numerics when time dialates thats the big issue here." (And, for after:
the gunplay, "more tactical too"; then targeting, with the item as a
target.) The tape (8m21 of P32): 62% of it slowed; 194 shots, 142 of
them slowed; 53 of his 208 presses of B and 57 of his 189 of A already
held past the hold knob.

He was right about the numerics. The measure: one script of pads, a
fight frame each, played in running time and again in slowed time (each
pad kept till the fight has moved a frame); every cell that is the
fight's compared, frame for frame.

- **One press of A was a jump AND a flip.** The jump read "A's first
  frame down" off a count the freeze holds at zero (so a press in a
  hitstop waits for the world to move). In slowed time that made every
  running frame of a held A its first: one press jumped, and on the next
  running frame flipped. A strafe jump went 4.1 units, not 3.1. The
  press is latched now every frame of glass and read once.
- **The run's double click and the slide's Down were lost two times in
  three.** A press is fresh against the pad of the frame before -- kept
  every frame of glass, the held ones too. The fight keeps its own
  "before" from its own frames; and the click's clock, a thumb's, counts
  the held frames as well.
- **Left + A, slowed, dodged and turned him** (P32's own: slowed, the
  tank steers with a face button down). Exactly now: a button freshly
  down is a blow's or a dodge's way in either time; only one held past
  the hold knob lets him steer.
- With those, five scripts are the same in both times, every cell: the
  tank's walk, turns and dodges; the boxer's steps, strafe jumps and a
  flip; the run's click, jump, flip and slide; the terminators and the
  gun; the jabs and the count.
- **Any of the four held slows time**: the gun held to its shot (it
  fires as B comes up, as ever), a jump or a dodge ridden through.
- **The dodge ends where it ends.** It went 1.65 in its own twelve
  frames, then slid 0.83 more over twenty-two on the body's friction.
  Now the twelve frames are all of it -- 0.20 a frame, 2.4 units (the
  reach it had) -- and he is stopped. (Every layer's; knob 8.)
- **The strafe jump lands and stays**: 3.0 units exactly, stopped (it
  landed with half its speed and slid 0.39).
- **In the air the run keeps its speed.** Letting go of Up mid-jump
  coasted him down as on the ground: 4.8 units with Up held, 1.6
  without. The air takes nothing now.
- tests: 8 base, 7 layer 1, 31 layer 2 (the dilation scripts are five of
  them); the full cart is byte-identical.

## P34: the gun -- a sight, a bullet, a cylinder (2026-11-22; not yet on glass)

The player: "next we work on the gunplay, make it feel more tactical too"
(too: as the movement now is -- "accurate prediction of where I'll land or
be"). The tape of P32 already said how he shoots: 208 presses of B in eight
minutes, 155 of them taps; most in the boxer with Y held beside it and the
pad pointing the shot (Up, Up+Left, Down, Left, Right); 117 volleys of
three. Until now a shot was a pose, a crack and a shake: nothing left the
gun and nothing was hit. Layer 2 only; behind L2.

- **The sight.** B down, the line the shot WILL take is drawn: its way
  the launch's own (the pad's from his steering; no pad, his body's), from
  the gun (half a unit ahead of him, a seventh to his right), to where
  that line leaves the street -- the town's own test of a wall, a unit at
  a time and halved back to an eighth (L_RAY). A red bead a round along
  it, and a red point on the place it lands; white-hot once the shot is
  charged. Nothing is aimed for him.
- **The bullet.** On the shot's frame a round leaves along that same line
  (the same routine: what was shown is what is hit) at two units a frame
  of the fight -- a street crossed in five, and in slowed time seen to
  cross it -- and lands in a burst on the wall's face with a thud; the
  charged shot shakes the lens when it lands. Thirteen units out, it is
  gone.
- **The gun is drawn while B is down.** The five frames a shot took to
  come up AFTER the release are spent during the hold (a frame of draw a
  frame down, the gun coming up in his hand as he stands): held five
  frames, the bullet leaves the frame after he lets go -- in slowed time
  that was fifteen frames of glass between letting go and the shot. His
  body comes round to the shot's way as it does to a blow's, while he
  holds.
- **The aim.** A tap leaves the lens where it is. B held past the hold
  knob -- time slowed for the shot -- the lens comes round behind his
  BODY and looks down the sight, so a shot to the side or behind is a
  shot he can see land; it stays 24 frames after the release, and comes
  back to his steering.
- **The cylinder** (knob 9, "mag": six; 0 never runs dry). The last round
  fired, the gun is 24 frames from full and B is no shot (no sight: no
  shot); a terminator thrown fills it at once -- the fists load the gun.
  The sight's beads are the rounds left. It is the one thing here he did
  not ask for: on the tape one hold had 48 shots in it.
- **The key is a thing a shot can meet** (for the targeting to come: "we
  can use the item as a target"): on the gun's line and within 0.45 of
  it, nearer than the wall, and not fired over from the air. Struck, it
  rings, leaps and is outlined. A miss by half a unit is a miss.
- **Found on the way: the lens trembled after every plain shot.** P30's
  "a terminator's weight shakes the lens" computed (hitstop - 5) >> 2 for
  every move; the plain shot's hitstop is 4, so its shake was -1, and the
  lens counts a shake down to zero -- from -1, for ever: a twentieth of a
  unit side to side every frame until his next fist. A shot's kick is its
  own now (3 frames, the charged one 7, on the shot's frame).
- **Found by the sight's test: a shot let go a frame before the pad went
  five degrees wide.** The gun fires as B comes up; on that frame no
  button was down, so with Left still held the tank turned a notch before
  the shot left. A blow waiting to be thrown now holds his steering too.
- The crack is on the shot's frame (it was the launch's). The layer's dead
  rhythm code is out of its build (99 words); the game is 15,822 of
  16,384.
- **Measured on silicon** (the sim; a gun route on the street -- taps, a
  volley, two aimed shots, shots inside a held Y): peak 550,655 clocks
  (64% of the frame), median 51%, none dropped. A shot at the key from a
  placed state -- the sight, the bullet, the burst, the key struck: 100
  frames, law and silicon the same on every one. (The street route differs
  on 232 of 335 frames from its second frame, before any shot: the lit
  faces' open mismatch, not the gun's.)
- tests: 44 layer 2 (the sight and the bullet in five ways, the draw, the
  cylinder, the key on and off the line, the aim's lens, and a sixth
  dilation script for the gun). Layers 0 and 1 build byte-identical to
  P33's; the full cart is byte-identical.

## P35: aiming; the sight in slowed time only; layer 3 -- the right shoulder (2026-11-22; not yet on glass)

The player, of P34 on glass: "feels a bit better. just needs some fixing on
the movement when in slow motion gun drawn. The targeting should really
only show in slow motion." And: "do the targeting now too. right shoulder,
use the item as the target." The tape (3m08 of P34): 56% of it slowed, B
down for 59% of it -- 28 holds past the hold knob, the longest 18 seconds;
ten shots struck the key; R held 22 seconds, where it did nothing.

- **What was wrong with the movement.** Holding B with the gun drawn he
  tapped Left and Right to bring the sight round. The pad was still the
  SHOT'S way: each tap threw his body a quarter turn to that side of his
  steering (Left, then Right: a half turn across), while his steering
  crept a notch a frame under it and the lens came round after his body.
- **Aiming** (layer 2 on). B held PAST the hold knob -- the moment time
  slows for it -- his steering comes round to where his body points (in
  the boxer, his cross), once. From then the pad moves him as it does with
  no button down, and the shot goes where he faces: Left and Right turn
  him, Up and Down walk him, the lens behind him the tank's own. A
  direction with a FRESH B (under the knob) is still a shot that way.
- **The turn starts fine.** The tank's notch is 14 (five degrees: half a
  unit of wall at six units, and a key is 0.9 across). Aiming, a turn's
  first frame is 1, its second 2, up to the tank's own: a thumb's tap is
  three units -- a degree -- and a hold sweeps a quarter turn in a little
  over a second of glass.
- **The sight shows in slowed time only.** A tap in running time is just
  the shot (and its bullet); held past the knob, or with another button
  holding time, the beads and the point are drawn.
- **Layer 3: the lock** (TND_LAYER=3; the P18 design, his: "R = targeting:
  planted"). R held, the district's item within 20 units (the key; the
  key held, its gate): he squares up to it -- his steering, in the boxer
  his cross, comes round to its bearing at 48 a frame and stays on it,
  his body with it. The item is outlined, a mark over it. He is planted:
  the tank neither walks nor turns (the dodges are his). A blow or a shot
  goes AT it whatever the pad says, so a shot strikes the key. L + R, the
  boxer's steps go round it -- Left and Right circle, Up in, Down out.
  The lens is targeting's: 2.8 behind, over his right shoulder. Not in
  the run; nothing in reach, R is nothing. (One target: Left/Right to
  change it and Up/Down for a shot's height wait for more to aim at.)
  The fight never sees R: it is read off the pad before the layer's mask.
- **Known, and left**: walking with the gun drawn he plays the walk (the
  gun is not up in it): there is no clip of that yet.
- **Found by the aiming's test: the first turn after the knob was a whole
  notch.** The aim was taken up at the top of the fight's frame, before
  that frame's buttons were read; the tank's own guard, read after them,
  let him turn a frame sooner -- fourteen units, then the fine ones. The
  aim begins where the buttons are read.
- **Measured on silicon** (the sim; layer 3 from a state by the key: the
  lock, a locked shot in slowed time, a jab, the boxer round it, then
  aiming with no lock -- on the build before the fix above): 288 frames,
  law and silicon the same on every one; peak 454,849 clocks (53%).
- tests: 45 layer 2 (the sight in slowed time only; aiming), 5 layer 3.
  Layers 0 and 1 build byte-identical to P33's; the full cart is
  byte-identical. Layer 2 is 15,890 words of 16,384, layer 3 16,026.

## P36: the locked run -- round the item, the gun in one hand, the superman punch (2026-11-22; not yet on glass)

The player: "The running and aiming should feel you are running on the
tangent of the circle, the gun being shot while running single hand. and
then trying to weave and land a super man punch." Layer 3 (the lock was
"not in the run" in P35); layer 2 is unchanged but for the shot's frame
being a subroutine.

- **The run goes round it.** Locked, the run's pad is from the item's
  bearing (P18's own run round a target, given the item): Left and Right
  ALONG the circle round it, Up at it, Down away, the corners spiralling
  in and out. The lens is on the item's line, so he crosses the shot in
  profile with the item beyond him.
- **...on its circle.** A step along the tangent ends a little outside
  the circle it began on: left alone he spiralled out 0.12 a second (7.4
  to 8.3 units in eight seconds). The radius he had when the pad went
  down is kept, and outside it his heading is turned six units in: over
  eight seconds round the key he holds 7.68-7.69.
- **The gun, in stride, one hand.** In the locked run a shot is not a
  move: B down, the near arm comes out at the item over the run's own
  stride (three new clips of sixteen: his right arm out, his left, his
  right ahead -- the head turned to it; tools/tnd_extract.py); let go,
  the round leaves at once, AT the item, and his speed is untouched. The
  arm stays out fourteen frames after.
- **The superman punch.** A fist thrown in the locked run (X or Y): he
  leaves the ground at the item with the jump's own rise, a quarter unit
  a frame, nothing steering it, the haymaker wound up through the air to
  land as he comes down; 1.2 from the item he stops. Thrown from inside
  about seven units it lands; from nine it is thrown just the same and is
  over before he arrives. The same whatever he holds in the air (the
  run's pace knob is not in it: with L let go mid-air it went a fifth
  less far).
- **A fist lands on the key.** A blow whose fist comes within a unit of
  the lying key has struck it: the blow's own hitstop (the haymaker's is
  28 frames) and shake, the burst on the key, the ring and the leap.
  Once a blow; it does not pick it up.
- **Known, and left**: through the air he is in the haymaker's standing
  clip (no flying pose yet); the strike is on the key only (the gate has
  no answer to a blow).
- Layer 3 is 16,291 words of 16,384 and 663 poses.
- **Measured on silicon** (the sim; from a state 7 units from the key:
  into the run, round it both ways, two shots in stride, a spiral in and
  the superman punch landing): 294 frames, law and silicon the same on
  every one; peak 445,048 clocks (52%), median 47%.
- tests: 12 layer 3 (the circle held both ways, the shot in stride, the
  superman punch from 5.5, 7.5 and 9.5 units with three things held in
  the air, a terminator by the key); layer 2's 14 gun tests after the
  subroutine. Layers 0 and 1 and the full cart build byte-identical.

## P37: layer 4 -- the enemies, and choosing among them (2026-11-22; not yet on glass)

On the cart-mesh core (ZETA0-FRONTIER 20; branch exp/cart-mesh), which
the player has on glass: "starting to feel alot better". And: "the
targeting needs up and down for high and low shots, and not move when
held during slow motion. for the enemies, lets have then move and make
them target able, r shoulder alone held does selection of target and hit
spot with dpad. same in slow motion." TND_LAYER=4: layer 3, the body from
the cart, and six enemies.

- **The enemies** are the player's own body cut smaller from the
  archive's full-resolution mesh (an elite 243 vertices / 369 triangles,
  a common 172 / 252, four of the horde 109 / 150), each with the WHOLE
  clip set from this game's own baker run on it (build/tiers; the guard
  and the planted walk are in the cart so far). With him: 1,320 vertices
  and 1,958 faces of the store's 2,048 and 2,048.
- **They move.** Each walks to its own place in a ring round him -- its
  size's stand-off out (2.4, 2.1, 1.8), a sixth of the way round from the
  last one's -- turning twenty a frame, at its size's pace (0.045, 0.040,
  0.030), a wall a wall; there, or held short by a wall, it stands in its
  guard and faces him. The ring goes where he goes. (The first cut sent
  them all straight at him: one clump, in a file, on one bearing.) One
  within arm's length of the lens is not drawn.
- **R held ALONE chooses**, read every frame of glass (so in slowed time
  a press is a press): the nearest target in reach (twenty units) on R's
  press, and again whenever the one he has is gone; Left and Right, the
  next one round him that way -- ordered by bearing and then by number,
  so two on one line can both be reached; Up and Down, the spot: high,
  mid, low, which STAYS. The item is the last target of the round. And
  with R alone the pad is only that: the tank neither walks nor turns,
  target or none, running time or slowed. (R with L is the boxer's steps
  round the target; in the run, the circle -- as layer 3.)
- **The spot.** A locked shot flies at the spot's height (1.6, 1.1, 0.5;
  the sight's beads and the mark on the target stand there too) and does
  what the spot does: a round is 1 off the enemy and holds it 12 frames;
  HIGH it is doubled; LOW it is held 36 -- it comes no nearer. The
  charged round is 3.
- **What lands.** The gun's line meets an enemy as it meets the key (its
  body's width, the nearest thing on the line -- locked or not; nothing
  is aimed for him). A fist within three quarters of a unit of one has
  struck it: the move's hitstop and shake, a jab 1, a hook or an uppercut
  2, the haymaker 4, and it is driven a third of a unit the way the blow
  went. Struck, it flashes; with nothing left (8, 5, 3) it tips over,
  lies 150 frames, and is back where it began. They do not strike yet.
- **Measured on the silicon** (the simulation, 383 frames from power-on:
  they come, the lock, both ways round, the spot, shots, a hook, the
  boxer round one): median 61% of the frame, peak 73%. Where the lit
  town's own open fault is not in the shot, law and silicon are the same
  to the pixel (a median of 0 differing); where it is -- the boxer's lens
  against a wall: the wall black, 38,000 pixels -- it is there with every
  enemy removed too.
- tests: 7 layer 4; 12 layer 3 and layer 2's 14 gun tests after it.
  Layers 0 and 1 and the full cart build byte-identical.

## P38: layer 5 -- the world in the street (2026-11-22; not yet on glass)

docs/TND-WORLD.md is the design (the player's frame: the classic Resident
Evil's world of keys, shortcuts and hard optional ways; sectors with more
than one way out; bunkers; a random map he solves; two ranks) and its
order of building. This is its step 2: ONE generated world -- the city the
layers already walk, seed 666142 -- in the street. TND_LAYER=5: layer 4,
and over it:

- **The world is the generator's** (`games/tnd/world.py`, run when the
  cart is built): six gates and a key for each, four bunkers, three back
  doors, two hard ways. The back doors and the hard ways are streets the
  generated tree never had; they are added to the town before its pieces
  and its map are made (the town is still nine pieces), and a back door's
  street is shut as a gate's is.
- **A key a gate, several in hand.** Each key lies at a dead end -- its
  own sector's far end, or a sector or two back -- and the jab takes it
  (as P21's). The keys in hand are a row of gold pips at the top left: a
  pip's place in the row is its gate's number. The nearest key not yet
  taken is the one drawn (within sixty units).
- **A gate eats its own key, from either side.** The nearest door still
  shut stands on HIS side of its street (a hard way can bring him round
  behind one); it is outlined when the jab would open it from where he
  stands -- a gate with its key in hand. Opened, the key is gone from the
  row and the street is a street.
- **A back door opens from its bolt's side only** (bone and black, where
  a gate is red and black): from the other it is a wall and no outline;
  from the bolt's the jab draws it and it stays drawn.
- **A hard way is an open street** that skips a gate and its key. The
  first is HELD: the six enemies of layer 4 are its pack -- asleep in
  their ring at its mouth until he is within a block (sixteen units),
  then layer 4's ring round him; two blocks gone and they walk home; one
  put down comes back there. (They still do not strike: held is a
  promise, kept in the design's step 7. The second hard way is empty.)
- **The bunkers**: a green and black hatch in the road with a green lamp
  on a post, at a dead end off the route in every second sector -- and
  the first is under his feet at the start. Standing on one, it is the
  last he stood in (kept for the save). They do nothing more yet: the
  map, the waymarks, the pack and the save are steps 3 to 5.
- **The arrow leads to the waymark.** Until the bunker's map sets it, the
  waymark is the game's: the first gate still shut that is not behind
  him -- its key's dead end, or, the key in hand, the gate; every gate
  open, the core. The way is the generated town's own tree, a word a
  node (its place in a walk of the tree, the side its parent lies
  through, the sides that lead down): down into the branch that holds
  the waymark, else back toward the start. So it shows the gates' way;
  the bolts and the hard ways are his to find. At the waymark's own node
  there is no arrow.
- **The item** the lock, the shot and the fist know (P35-P37) is the
  nearer of that key and that door.
- **Found on the way.** The display list is KEPT between frames (the HUD
  writes its words only when they change), so the first pips were added
  again every frame: 585 triangles in a few seconds, and a write off the
  end of memory. Last frame's pips are now taken off the end first, if
  the count is still the one they left. And key 1 lies the other side of
  the start's own wall: sixteen units away and a long walk round.
- **Measured on the silicon** (the simulation; five scenes, begun at
  their places by a build hook, TND_AT): the start 57% of the frame at
  the median and 73% at the peak; a key taken 57 / 60; a gate opened and
  walked through 53 / 63; a bolt drawn and walked through 52 / 61; the
  pack woken, locked on, shot and struck 67 / 77. Law and silicon agree
  on every new thing -- the pack's 388 frames to the pixel -- and differ
  only where the lit town's open fault is in the shot: a wall cut by the
  lens's near edge (a strip at the screen's side, black or the wrong
  colour; up to 13,600 pixels in one frame at the start's dead end).
- tests: 10 layer 5; base 8, layer 1's 7, layer 3's 12, layer 4's 7 and
  layer 2's 45 after it. Layers 0 to 4 and the full cart build
  byte-identical.

### P38b: his first tape of the world (2026-11-22; 7m57s of TND L5)

- **What he did.** From the start round to key 1, and then gates 1 to 5
  in order -- keys 1, 2, 3, 5, 4 (key 5's dead end first: its back door
  drawn straight into the second bunker), every key taken with ONE jab,
  118 blocks walked -- and the tape ends on the way back for key 6. A
  third of it slowed (34%). He never came by a hard way: the arrow does
  not show them, nothing else does, and the pack never woke. Eight
  minutes of the world with nothing in it to fight.
- **At key 1, ninety-five seconds**: R held three quarters of it and
  fifty shots at the key -- the only target in reach -- with the spot
  stepped up and down. And thirty-five seconds of Y held, B beside it,
  walking on key 5. The item is his practice target.
- **The snag, at gate 5.** He came to it with its key in the middle of a
  string: thirty-four jabs in eighteen seconds, the last fourteen at a
  gate that stood outlined, and each was "mid-swing: a jab" (P21's rule:
  a jab thrown while a blow is in flight is only a jab). It opened when
  he stopped. In the world the rule is gone: the jab that reaches a key
  or a door he can open IS that, string or no string. (A test mashes X
  all the way up to gate 1: shut before the change, open after.)

## P39: layer 6 -- the bunker's map, and his waymarks (2026-11-22; not yet on glass)

docs/TND-WORLD.md's step 3 ("the bunker is where you prep, setting your
way marks planning routes"). TND_LAYER=6: layer 5, and:

- **On a bunker's hatch, SELECT opens the map** (a green square under
  the key pips says so while he stands on one) and the street stops:
  nothing of the fight runs, so its time does not either. SELECT shuts
  it. Off a hatch SELECT is the knobs, as it was -- and shutting the map
  does not open them under his thumb.
- **The map is geometry read from the cart** (frontier 20): a quad a
  street and a square a plaza, in the colour of its sector's danger, cut
  by sector into meshes of sixty streets at most, standing upright
  before a lens at the world's origin, north up. It costs the data
  memory five words a mesh; a sector he does not know is not listed.
- **What he knows** is by sector: the one he stands in, and from a
  bunker's hatch the next one along too (its survey) -- so the first
  hatch shows two sectors of seven. In them: the keys still lying (gold),
  the gates still shut (red), bunkers (green), the hard ways (white), the
  back doors (blue; a white bolt across one still bolted), the core, and
  himself, blinking. The cursor on a key frames that key's gate as well,
  and on a gate's end its key: which key is which gate's.
- **The plan**: the pad moves the cursor a node (held twelve frames, it
  runs); A puts a waymark under it -- only where he knows the town, four
  at most, each with as many pips as its place in the plan -- or takes
  off the one there (the rest move up); Y clears the plan.
- **The arrow leads to HIS waymark**, the first of the plan -- and no
  plan, no arrow (layer 5's arrow, which chose for him, is gone).
  Reaching its node takes it off, with the light's flash, and the next
  is first.
- **The way is searched, not the tree's.** From the waymark outward over
  the streets OPEN NOW (the map's own bits: a gate opened, a bolt drawn,
  the hard ways), a way out of every node, made again whenever the
  waymark or the doors change: 256 nodes, in the frame it happens. So a
  hard way IS a way, and a bolt drawn is one from then on. Where the
  search finds none -- the waymark behind a gate still shut -- the
  arrow goes by layer 5's tree, which leads to that gate.
- **Measured on the silicon** (the simulation): a map of two sectors is
  17% of the frame, the whole town 29%; the street with a plan 53-57% at
  the median and 59% at its peak, the frame of the search among them.
  Every map frame, law and silicon the same to the pixel (293 frames).
- tests: 9 layer 6; layer 5's 11 after it. Layers 0 to 5 and the full
  cart build byte-identical.

## P40: layer 7 -- the bunker is a door and rooms (2026-11-22; not yet on glass)

The player, shown layer 6's hatch in the road and its map: "i was
thinking the bunkers were more of doors against a building, and an
actual room you enter, in there we can have training rooms with the
items as objects you can practice melee and gunplay. that will also help
calibrate the game play, those training rooms. the hub room hold a desk
with the map and inventory management. the prep table". TND_LAYER=7:
layer 6, the hatch gone, and:

- **The rooms are nodes of the map**, three rows north of the town and
  out of its reach, so the street's own walk, walls, shots, lock and
  lens are the rooms' and nothing was written twice:
  - the HUB: a junction's middle (9.4 across) with a short arm north
    and one east. The PREP TABLE stands against its west wall, the map
    on it; the way out is in its south wall;
  - the RING, north: a whole tile (16 across), a black and white floor
    in its middle. The six bodies stand round it and face him -- they
    do not strike, so they are what he practises on: the lock, the
    spot, rounds, fists, down and up again;
  - the RANGE, east: a whole tile, yellow lines down it and a red wall
    at its end, three ITEMS before it. They are keys that are never
    taken: the lock's target, and they ring and leap for a round or a
    fist. (The jab STRIKES one; it does not pick it up.)
- **A room's word carries bit 31**: all of its tile is floor, to 0.6
  from its walls; past that on one axis it is floor only in a doorway
  -- within the lane's width on the other axis, on a side not closed.
  The hub is an ordinary node. So the doorways are the lane's width and
  cost nothing: a room's open side meets the hub's arm.
- **The rooms are drawn from the cart** (frontier 20), flat: five words
  of data memory each, and no lit face for the lens to cut -- the lit
  town's open fault cannot show indoors. (A piece's flags are now read
  from a table by its kind.) Each floor runs on past its walls: with
  his back to a wall the lens stands outside the room, and looked in
  over a strip of the street's black ground.
- **A bunker is a door** on a closed wall of its dead end -- the one
  facing its street where that is closed -- steel, a green band, a
  green lamp over it; seen from its front only. The jab at it is the
  way through: he stands inside the hub's door facing the room, that
  bunker is the one he will leave by, its survey is his (its sector and
  the next along -- layer 6 took that on the hatch), and the six are in
  the ring. The jab at the hub's door: he stands at the door he came in
  by, facing its street, and the six are back at their hard way. ONE
  set of rooms serves every bunker (and, later, one stash).
- **"We start in a bunker"**: inside the first one's door.
- **The map is the prep table's**: SELECT within reach of it (the green
  square shows there). Its cursor begins on the bunker he is in, which
  is where he blinks. In the rooms there is no arrow; his plan waits
  for the street.
- **The item** is now the nearest of three: a key, a door of the
  street, a bunker's door.
- **No ground and no sky indoors.** The street's ground, a hand's
  breadth under a room's floor, took the floor's pixels near the lens: a
  black band along the bottom of the glass. In the rooms neither is
  listed.
- **Measured on the silicon** (the simulation; two scenes from power-on:
  the ring -- the lock, a round, a hook, the boxer's steps -- and the
  range; and the table's map, out by the door, the street, in again):
  in the rooms 54% of the frame at the median and 64% at the peak, the
  ring with its six 54 / 57. Indoors law and silicon are the same to the
  pixel in every frame, 949 of them; the street outside the door has the
  lit town's open fault as before (a median of 178 pixels, 11,331 in its
  worst frame).
- tests: 17 layer 7; layer 6's 9 and layer 5's 11 after it. Layers 0 to
  6 and the full cart build byte-identical.

### P40b: his tape of the rooms (2026-11-22; 5m43s of TND L7), and the glass's edge

- **What he did.** The prep table found and the map opened twice; 55
  seconds on the range (47 rounds rung off its items, ten blows); the
  ring's six shot down four times, from the ring and through the hub's
  doorway, and never struck; out by the door, key 1 taken, a plan made at
  the table, gate 1 opened at his own waymark; then on into the second
  sector with no plan and no arrow.
- **The snag: fourteen presses of A on one node** -- the waymark at gate
  1 on, off, on. Its pips sat under the cursor's own frame and he could
  not see that it was set. A waymark is now a solid orange lozenge ON the
  node, inside the cursor's frame, its pips above the frame.
- **B in the map** (five times): it shuts the map now, as SELECT does,
  and the thumb that shut it fires no round.
- **"Fix all of the weird graphic hiccups at the edge of the screen, it
  shows up on the pocket."** The lit town's open fault, run down at last
  -- in the silicon, two things where a lit face goes to the clipper
  (silicon/zseq.v; carts/witness/litclip.zol is its witness):
  a vertex the machine cannot project was cached with light level ZERO,
  and a clipped face's third corner took the LAST face's level. So a wall
  cut by the lens faded to black toward its unseen end, or was black, or
  wore its neighbour's light: the strips down the side of the glass. The
  law never did. Five street scenes that differed by up to 16,480 pixels
  a frame are bit-equal over 1,583 frames with the fix. It is a new core.

- **The core, fitted** (CI run 45100833653, Quartus 25.1std, four
  corners): 17,934 of 18,480 ALMs (97%), 299 of 308 M10K, 60 of 66 DSP;
  worst setup +0.395 ns, worst hold +0.099 ns. The whole suite's cross on
  the fixed RTL: 35 carts, every one bit-equal, litclip among them.

## P41: layer 8 -- the world persists (2026-11-22; not yet on glass)

The player, asked what the old "memory fabric" was for: "persistent
worlds, having all the enemies known over time, as part of the route
optimizing." And of the steps left: "just do all the steps for the next
build we try out." TND_LAYER=8: layer 7, and what follows. (Two steps are
NOT in it, and why is at the end.)

- **A PACK is three things**, as the fabric's world was.
  LATENT: where it is -- a walk of sixteen steps along its sector's
  streets, out and back, a step every 512 frames -- is a pure function of
  the street's clock (PATROL_T; the step and the tick): nothing is stored
  and nothing runs for a pack he is not by, and the same seed is the same
  walks. COMMITTED: who of it is left, six bits a pack, the only thing he
  changes. LIVE: the six bodies, worn by the NEAREST pack with anyone
  left, changed only while nobody is after him; who of the live pack
  stands is written back every frame. Eight packs: one a sector, the
  first two of the horde and the last all six, and the one that holds
  the first hard way, which stands.
- **A body down stays down** in the street (the ring's still get up).
  **A REST** -- taking a bunker's door, or waking in one -- makes him
  whole and gives every pack ONE of its missing back.
- **They strike, one at a time**, in turn round the ring: the one whose
  turn it is waits 26 frames, then, if he is in reach, winds up its
  haymaker for 44, BLINKING, and throws it. It lands if he is still in
  reach, not in a dodge's frames and not in the air: 12 off his 140 for
  one of the horde, 20 a common, 30 the elite; the lens shakes, his own
  blow is broken. One held by a blow of his loses its turn. They are
  quicker than layer 4's by six tenths (the patrol's pace is the horde's).
- **Down, he wakes in the bunker he last took**, rested; doors, keys,
  plan and clock as they were -- the clock keeps what the outing cost.
- **THE CLOCK** is the street's: a frame of glass a frame, slowed time
  and all; not in the rooms, not on the map, not while he is down.
- **MEDICINE**: a green box at a dead end in each sector past the first;
  walked onto, it is his, three at most in hand (green pips beside the
  keys). SELECT in the street takes one: half of what he can hold. (The
  knobs, which SELECT was, are put away.) One is in the STASH to begin
  with: at the prep table's map R takes one from it, L puts one back.
- **A sector's RANK** is by the blows he took in it -- S none, A one, B
  to three, C past that -- taken when its gate opens and worn by the
  opened gate on the map (gold, bone, grey, dark red).
- **A pack he has SEEN** (within 28 units) is on the map from then on:
  its walk drawn over its streets, and a red mark where the clock has it
  now -- which, the clock standing while the map is open, is where it
  will be as he walks out. The map also reads the clock and the medicine
  in hand and in the stash.
- **THE CORE ends the run**: its time, and its rank against this world's
  own par (S within three seconds a block of the hard ways' 99 blocks; A
  within four of the gates' 123; B within six).
- **Measured on the silicon** (the simulation, the fixed RTL): a fight
  with the first pack -- they come, three blows land, the lock, a round,
  a hook, one of them down -- 56% of the frame at the median and 67% at
  its peak, 560 frames bit-equal; the prep table's map with its words,
  and the end's, bit-equal too.
- tests: 14 layer 8. Layers 0 to 7 and the full cart build
  byte-identical.
- **NOT IN IT, and why.**
  *Saving across sittings.* The card's save file is 8 bytes, shared by
  every build; a world's state is some thirty words past them, and
  whether the Pocket's bridge writes past a file's end has never been
  tried on glass. Growing the player's save file is his to allow.
  *A random city a game.* Every fact of this one world is a constant in
  the program -- each key's and door's place written out, the town's map
  and its pieces in data memory -- so another world is another build
  until those are tables and the generator's nine pieces are all on
  hand; data memory has 554 words left.
  *Also short of the design:* carried weight does not slow him; the
  combat rank is blows taken, not the style meter; the rival is not here.

### P41b: his tape of the rooms, read for how he fights (2026-11-22; 29m01s of TND L7)

He asked: "check my fight styles." Twenty-four and a half of the 29
minutes in the RANGE, on its three items; two in the ring.

- **Fists two to one over the gun**: 989 blows to 461 rounds (131 of
  them charged). 786 jabs; 203 terminators, and by the count before them
  77 on none and 48 on one (the lead hook), 39 on two (the rear
  uppercut), 39 on three and up (the haymaker): all three, the short one
  most. 757 times an item rang.
- **Slowed time is half of it**: 53% of the tape; a third of his blows
  begin in it.
- **He steps round the target**: L and R held together a quarter of the
  tape -- the BOXER's steps round what he has locked (the boxer is 29% of
  his stance, the tank 62%, the run 9%). (CORRECTED 2026-11-23: this
  first read "he circles at a run". The stance cell is 0 tank, 1 run, 2
  boxer, and the reading had 1 and 2 the wrong way round.)
- **The spot is used**: high 43% of his locked time, mid 41%, low 14%;
  seventy changes. Thirty changes of target.
- **153 dodges and flips, 76 jumps**; nine blows in 989 thrown from the
  air.
- **After a terminator** he mostly starts another string (80) or stops
  (111); a round follows one ten times.
- **Why two minutes in the ring.** Layer 7's dummies, put down, came back
  at the hard way they hold in the street -- not in the ring. He put six
  down and the ring was empty. (Layer 8's get up where they lie; so do
  the lab's.)

## P42: the lab -- a white room to tune the fight in (2026-11-22; not yet on glass)

The player: "for the next experiment. We want to do a empty white room,
with a green and white checker board, grey walls : tall, checker board
white and grey. Then having one stationary clone of the player to fight.
think about it as tuning the fighting in this cart. Able to load n number
of tiered enemies. stationary for now. we want to work on how the weight
works with how the will respond to hits. and tuning all the fighting
mechanics. make the room wide so at the wall we have platforming with some
moving and some structures to try things out." TND_LAYER=10 (9 is the
whole game's own number, the default: the first cut used it and rebuilt
the full cart as a lab): layer 4's fight, no town.

- **The hall** is 64 by 32 and 12 high: a green and white floor in
  checks of four, grey and white walls the same, a white ceiling, a
  white haze the far wall goes to. Eight tiles of three meshes in data
  memory, flat; its bounds are one test, not the town's map. No colour
  curve (time slowed still sinks the glass).
- **Who stands there is knob 0**: the CLONE alone (his own body, whole,
  through the rival's two descriptors, in his own idle); the clone and
  the elite; the clone, a common and one of the horde; the elite alone;
  the elite, the common and two of the horde; the six. (The store's
  2,048 faces decide the sets: he and his clone are 1,474 of them.)
  Turned, they are put back on their marks. They stand, and turn to
  face him; down, one gets up where it lies.
- **WEIGHT -- what a blow does to a body** (L_HITR). Each has a speed
  along the floor and a rise. A blow adds to them, the way his body
  faced (a round: the round's way): the MOVE's speed (a jab 0.05 a
  frame, the cross 0.07, a hook 0.11, the haymaker 0.26, an uppercut
  0.05, a round 0.04, a charged one 0.12) by the KNOCK knob, over the
  body's own weight (the clone and the elite 1, a common 0.8, the horde
  0.63) and the WEIGHT knob; a launcher's rise (the haymaker 0.04, the
  lead uppercut 0.17, the rear 0.20) the same way by the LIFT knob. It
  leans back by how hard it was sent, and comes upright. Each frame it
  keeps the SLIDE knob's share of its speed (0.88) and falls by the
  EGRAV knob (0.012); a wall or a structure stops it. The STUN knob is
  how long a blow holds it (by the move's own frames), HSTOP the
  hitstop.
- **Fifteen knobs** (SELECT held, as ever; the tuner's digit now runs
  0-9, A-E): who, weight, knock, lift, stun, hstop, slide, egrav -- and
  the strikes' pivot, lunge, keep, hold, slow and dodge, and the jump.
- **THE STRUCTURES, along the north wall**: three steps (0.8, 1.6, 2.4
  high), a ledge at 2.4, a SLIDER at 2.4 that carries him ten units and
  back, a LIFT from the floor to 4.0, and a platform at 4.0. Each waits
  48 frames at its ends. What he stands on is the highest top under him
  no more than a step (0.3) above his feet, and his height is counted
  from it -- so everything that asks "is he on the ground" asks the same
  thing it did. Onto another, his height in the room is kept; off an
  edge he is in the air; on the same one he rides. A structure is a
  wall to anything on the floor, and to him while its top is more than
  a step above his feet. His drawn feet, his shadow and the lens follow.
- tests: 18. Layers 0 to 8 and the full cart build byte-identical.

## P43: the lab, turned by his first tape of it (2026-11-23)

His words, on the lab: "wow this is getting fucking cool. Couldn't get
through all the knobs. but what i feel is getting better is understanding
the subcontext of each held chord. these are typically shoulders, and one
held action, so three. the way the thumb moves best depends on which was
held. ergonically, the at command button is special for gun, and jab for
jump/evade. I found you can hot pass to the command button and then pump
the previous held action. so you get a heavy hit then gun shots if you
were holding gun.. when running that could be a tackle taken down and
close quarters shot. for boxer its a stun and close quarter shot. all
while still holding slow-mo. Then I assume you could do that move in fast
mode if the transfer is within range. The gun needs to be always held in
ready position if the gun button is held. the running needs to be stearing
down the sights of the gun and of at the taret if targeting is active. The
melee needs to feel like the movement of the enemy is enough so that jabs
can follow for at least 4 hits. the fifth should miss and the forth is a
right jab. the first jab special is left cross, second is right uppercut,
the third is the haymaker. the forth can be strung to a new combo, if
special is hit after it's a jab. that jab can be held, and essentially you
can select the next major special you want. so maybe an uppercut to launch
the enemy, one jab, then jab held, release held special and then held
echange back with uppercut submited then gun shot. With the camera
tracking the juggled enemy."

**The tape (32m26s, TND LAB).** 14 minutes on the clone alone, 10 with
the elite beside it, 8 with a common and one of the horde. 713 jabs, 191
terminators, 403 rounds; 720 blows landed, 94 bodies put down. Long jab
strings kept landing -- eight thrown, 8.8 landed. Y with B held (the
"hot pass") twenty times, every one in slowed time (the lead hook 11, the
haymaker 6), and B pressed with Y held 127 times: the pump. B was down
24% of the tape -- standing 32% of that, running 24%, walking 7%. Knobs:
weight 1.0 for 14 minutes, then 0.8, then 0.9; knock 1.0 for 21, then
0.9; LIFT 1.0 for 22 minutes and then OFF for the last ten (a body had
been thrown 6.5 units up by launchers one on another), 0.3 as it ended;
the jump tried from 0.146 to 0.226 and left where it was. A fifth of a
minute on the structures, to the top of the lift.

**Built from it (the lab only):**

- **THE STRING.** Four jabs land and a fifth misses. The count runs to
  five; the fourth X is the RIGHT jab (the cross), whose knock (0.30)
  sends the body two and a half units -- out of a fifth's reach; the
  jab's own is 0.04, which his lunge keeps up with. On the clone, the
  elite and a common, from 0.9 to 1.45 away and a press every ten to
  twenty-five frames. (One of the horde is down at the third.)
- **Y BY THE COUNT**, as it was: none or one, the lead hook (his "left
  cross": the left hand's); two, the rear -- right -- uppercut; three,
  the haymaker. PAST the third, Y is a JAB that STEPS IN (3.6 times a
  jab's lunge) and is the first of a new string.
- **THE GUN IS HELD READY.** His body is two halves with a pose each:
  while the gun is up (B down, or just let go) and he is not throwing a
  blow, reeling, down or in a flip, his upper half is the gun's ready
  pose over whatever his legs do -- standing, walking, the boxer's
  steps, the free run, the air. (The locked run keeps its one-handed
  poses.)
- **THE LENS LOOKS UP WITH A BODY THROWN**: thirty of the turn's 1,024 a
  unit of the highest body's height, ninety at most, eased.
- **A RISE IS CAPPED** at 0.24 a frame (2.4 units up): launchers stacked
  do not stack it. The lift knob begins at 1.0 again; weight and knock
  begin at his 0.9.
- tests: 35 lab. Layers 0 to 8 and the full cart build byte-identical.

**Not built, because they are his to say:** the pass's moves by stance
(the run's tackle and the boxer's stun, each with a close-quarters shot
after; and the same in running time); the run "down the sights"; and how
a HELD jab chooses the next special.

### P43b: the loop written down (2026-11-23)

The developer's proposal of this date ("Zeta Experience Imprinting and
Architectural Evolution") asked for the loop this file has been running
by hand to be made a thing with records. Now: `docs/ZETA-N-HYPOTHESIS.md`
(the machine's loop: the hypothesis, and what is established against
what is hoped), `docs/EXPERIENCE-IMPRINTING.md` (the player's loop),
`CLAUDE.md` (a session's orientation), `zeta/experience.py` (a tape and
its cart to a record), `games/tnd/axes.json` (the lab's knobs as named
axes), `games/tnd/observe.py`, `experiments/tnd/tnd-lab-0001.json` (the
first record: his 32-minute tape of the lab, his words, P43's changes),
`games/tnd/IMPRINTS.md` (what has been kept, thirteen entries) and
`experiments/tnd/REJECTED.md` (what was turned down, nine). The next
tape of the lab is the comparison; it has not been played.

## P44: the lab -- the pass, the close shot, the held jab's choice, the run down the sights (2026-11-23)

"get something on my card now." Three things of P43 had been asked of
him rather than built; they are built here as THE AGENT'S READINGS of
his words, to be judged on glass and corrected. The lab only.

- **THE PASS** (Y thrown with the gun up -- B down, or let go within
  the nine frames it takes to come down, which is the transfer's range
  in running time too). Standing: the heavy blow it was. In the BOXER:
  the STUN -- a lead hook that holds the body four times as long and
  hardly sends it. In the locked RUN: the leap at the target is a
  TACKLE along the floor (the slide's poses), and where it lands the
  body is DOWN and he stops.
- **THE CLOSE-QUARTERS SHOT**: a round whose line meets its mark nearer
  than 2.6 units is three times the round, holds the body 24 frames
  more, sends it as a charged one does -- and from that close a round
  reaches a body that is down.
- **A HELD JAB CHOOSES THE SPECIAL**: while X is down a press of Y
  throws nothing and steps the choice -- once the lead hook, twice the
  rear uppercut, three times the haymaker, the light blinking for each
  -- and letting X go throws it.
- **LOCKED, AIMING, THE RUN GOES DOWN THE SIGHTS**: with B held past the
  hold knob he runs straight at the target whatever way the pad points.
  A tapped B is still the one-handed shot off the circle.
- tests: 40 lab (each of the four has its own). Layers 0 to 8 and the
  full cart build byte-identical.
- the law against the simulated silicon: 708 frames of the four,
  bit-equal; the frame 51% at the median, 54% at the peak. (The scene
  showed a round into a body already down standing it up to fall again;
  it no longer restarts the fall. That mend is staged, NOT on the card:
  the card went home with the build before it.)
- **His second tape of the lab came home on this visit** (38m40s, of
  P43's build): `experiments/tnd/tnd-lab-0002.json`, compared with the
  first by `python3 -m zeta.experience compare`. He turned no knob but
  `who`. Highest body 2.28 units (6.47); 62 crosses; five or more jabs
  in a row still landed 20 times (12); haymakers 22 (80); the pass 13
  times, 12 in the boxer; 2.8 minutes on the structures (0.2); 188
  jumps (94), 203 dodges and flips (44); slowed 46% (36%). He has not
  yet spoken of it.

## P45: the REACTOR -- the lab drawn in, its checks his width, his double in the corner (2026-11-23)

The player, of the game as it stands: "It feels like we are getting
closer to an infinite imersive game where we can play fast with the
controls of the Pocket. Feels good just needs more finesse. the camera
angles, where the enemies are." And the test he asked for: "the world
we made for the lab but more concentrated like a reactor. same
checkboard but are unit to the player width a spacial economy of
motion moves to pressed. this way all the physics is naturalized. now
its a corner with the doupleganger except its at the corner, its
facing you and what it does is the exact mirror of the moves you are
doing. This will help with calibration of the games bodies. The hits
can be made felt as if the bodies are responding to eachother."

`TND_LAYER=11` (a variant of the lab: everything P42-P44 is in it).

- **A CHECK IS HIS BODY'S WIDTH**, measured off his own idle: 0.58
  units. The room is sixteen checks square and eight high (9.28 by 4.64
  units; the lab's hall was 64 by 32 with checks of 4). Three meshes,
  twelve objects; no structures. A body's middle comes to half a check
  of a wall: its shoulder touches.
- **HIS DOUBLE IS IN THE NORTH-EAST CORNER**, on the middle of the
  corner's own check, facing him; he begins six checks down the
  diagonal. Nobody else is in the room.
- **IT DOES WHAT HE DOES** (the first knob, `mirror`, on): up and free
  of a blow, its two halves take his two halves' poses of the same
  frame, and its height is his. Held by a blow or down, it is in its
  own idle -- a blow breaks off what it was doing. THE SAME HAND, not
  the other: the machine has no way to turn a mesh inside out, so this
  is a twin and not a reflection. It does not copy his steps: the
  corner is its place, and knocked out of it, it walks back.
- **A BLOW OF HIS THAT LANDS IS A BLOW OF ITS THAT LANDS ON HIM**: he
  is sent back by exactly what it is sent by (the move, the knock and
  weight knobs), and slides as a body slides (the slide knob), a wall
  a wall. It is in the corner and cannot go; he can -- so how many
  checks he goes is how far that blow sends a body. At the knobs'
  beginnings, from a check and a quarter: a jab a quarter of a check;
  the lead hook 1.2; the rear uppercut 0.5; the cross 4.1; the
  haymaker 3.3. (He is not thrown up, and its rounds are not fired.)
- **TWO BODIES DO NOT STAND IN ONE PLACE**: up, his double is a check
  of floor he cannot be on (over its head he may pass). The lab let
  him walk through it.
- READINGS OF MINE, to be judged: that "mirror" is of his MOVES and
  not of his steps (a reflection that walked toward him as he walked
  toward it is the other reading); that the hits "responding to each
  other" is his own body being sent.
- NOT TOUCHED: the lens. At a check apart it looks over his shoulder
  and his own back hides most of his double.
- tests: `tests/test_tnd_reactor.py`, 6. The lab and layers 0, 4, 8 and
  the full cart build byte-identical. `games/tnd/axes-reactor.json` is
  its knob registry.
- the law against the simulated silicon: 652 frames, bit-equal; the
  frame 56% at the median, 72% at the peak (the lab: 51% and 54% --
  the room is more faces, nearer the lens).
- on the card 2026-11-23 as TND REACTOR, with the lab's mend of P44.
  The card brought back his tape of P44's lab (35m25s):
  `experiments/tnd/tnd-lab-0003.json`.

## P46: where it lands -- zones, a waist that bends to the spot, the round's own line, a gun in his hand (2026-11-23)

The player, bringing the reactor's first tape (3m50s): "I think what we
want now is to use the zeta see where the hits and shots land. make the
damagae and reaction to the hit be based on where it lands. also the gun
shooting needs to be made more sleak and sexy. a gun in hand with the aim
at an angle when lookuing up and down. The goal is to make it easier to
land the shot where it needs to either punch or gunshot."

The lab and the reactor only (`TND_LAYER` 10 and 11).

What was there: under the lock, Up and Down chose a spot (P37: high, mid,
low) and a round did what the CHOICE said; it flew level at 1.6, 1.1 or
0.5 -- the high one over the head of a body 1.41 tall -- from no gun; his
pose did not change; a fist's height was nothing.

- **A BODY IS THREE PARTS, by the height a fist or a round meets it at
  above its own feet**: the HEAD from 1.18, the LEGS under 0.70, the
  BODY between. Over 1.55 or under its feet a round meets nothing.
- **THE SPOT IS A HEIGHT ON THE TARGET**: its head (1.30), its chest
  (0.95), its knee (0.40) -- above ITS feet, so the spot goes up with a
  body thrown. The mark and the sight stand there.
- **HIS WAIST BENDS TO IT.** His body is two halves; the upper turns
  about the waist (and is moved so the waist stays whole). With the gun
  up, by the slope from his hand to the spot; with his fists: high, a
  touch back; mid, the clip as it was drawn (a jab is at the head, 1.22;
  the cross at the body, 1.01); low, thirty degrees down -- a jab lands
  on the body. His fist is where the bend puts it, so the blow lands
  there. Eased a quarter of the way a frame. The lens takes a third of it.
- **THE ROUND FLIES THE LINE FROM HIS HAND** to where it lands: the
  sight's beads climb or fall along it, the bullet too (its streak
  pitched). No lock: level from his hand (1.11), which is the body. The
  machine has no divide; a slope needs one, so the cart has an
  eighteen-step one (QDIV).
- **WHAT A PART DOES.** A round: the head doubles it and holds it twelve
  frames more; the legs hold it three times as long, and a charged or a
  close round there takes them from under it (it lies fifty frames and
  gets up with what it had -- a body no longer gets up healed). A fist:
  the head takes half as much again (a jab's one stays one; a hook's two
  is three; the haymaker's four, six), is held half as long again and
  snaps back; the body is the move as it was made; the legs (a body in
  the air) are held twice as long and its rise is over. How far a blow
  SENDS it is as before for head and body -- the string he tuned stands:
  four land, the cross puts it out of a fifth's reach -- and the legs
  are hardly sent.
- **THE BURST IS WHERE IT LANDED and says which part**: white-hot the
  head, the spark the body, red the legs.
- **THE GUN IS IN HIS HAND**: a slide, a grip and a red front sight,
  at his hand's own place in every pose of the gun's two clips while his
  arm is out, lying along his aim; a flash at its mouth for three frames
  and it rides up for six after a round.
- "Use the zeta": the machine works out where a hit lands. The
  pixel-pick register (`spec.PICK`) was NOT used: the lens is behind him,
  and at the place a blow lands the pixel is his own back.
- READINGS OF MINE, to be judged: all of the above past his words. Not
  done: a pitch for the aim WITHOUT the lock (Up and Down walk him
  there, and that is his design); his double in the reactor does not
  bend or hold a gun; the sight still shows in slowed time only (P35,
  his).
- tests: `tests/test_tnd_aim.py`, 9; the lab's 40 and the reactor's 6
  pass unchanged. Layers 0, 4, 8 and the full cart byte-identical.
- the law against the simulated silicon, the lab: 495 frames (the lock,
  a round at each spot, fists low, a hook, a round with no lock),
  bit-equal; the frame 51% at the median, 58% at the peak.
- on the card 2026-11-23, both.
- The reactor's first tape: `experiments/tnd/tnd-reactor-0001.json`.

## P47: the lock is a red outline; a locked round always lands; the laser (2026-11-23)

The player, of P46 on glass (4m45s of the reactor): "i think this is
starting to feel better. the targeting needs a bit more work, the
outline and the diamond are too much ui, just a red outline would be
good. also the line of sight marker and target are too imprecise,
smaller would be better, a targeted gun shot should always land, and a
red hit like the punches so you know when the shot lands and where."
And while it was being built: "are we able to do a laser sight? like a
line to the target?" The lab and the reactor only.

- **WHAT HIS TAPE SAID, and it was mine: of 59 rounds he fired locked on
  his double, ONE reached it** (and none of 20 with no lock). In the
  reactor the double's middle is a fiftieth of a unit inside the floor's
  bound; the gun's line finds where it leaves the floor to a sixteenth,
  so the wall had the line a hair before the body did. He never saw a
  round land because none did. A body standing against a wall is now in
  front of the wall (the line that met a wall runs a fifth of a unit on
  while the bodies are tried).
- **A LOCKED ROUND ALWAYS LANDS**: locked on a body, it is what the line
  meets, whatever else stands on it; and the round carries the part he
  chose, so it does that part's work wherever the body has got to since
  it left the gun. With no lock a round is still judged by the height
  it lands at.
- **THE LOCK'S MARK IS A RED OUTLINE** and nothing else: the diamond is
  gone, the outline's colour red.
- **THE LASER** replaces the beads: a red line from his hand to where
  the round will land, on whenever the gun is out with B down -- in
  running time too. The machine draws no lines and scales no mesh, so
  it is laid from seven pieces (eight units down to an eighth), the
  longest that fits first, each two thin blades crossed. Its pitch is
  the angle of its slope (s / (1 + 0.28 s^2): two of the cart's own
  divides a frame). The point where it lands is less than half its old
  size.
- **THE LINE BEGINS AT THE GUN**: with the gun in his hand the line, the
  round and the laser start at the hand itself, not at a fixed place
  beside him.
- **WHERE A ROUND LANDS: a red burst**, on the body where the body now
  is; and the body flashes red as it does for a fist (it always did --
  once a round lands).
- tests: 12 in `test_tnd_aim.py` (the red outline alone, the laser from
  hand to spot in running time, a locked round landing on a body thrown
  up under it), 7 in `test_tnd_reactor.py` (a round reaches his double
  in its corner, locked and not); the lab's 40 pass. Layers 0, 4, 8 and
  the full cart byte-identical.
- NOT DONE: the beads counted the rounds left in the gun; the laser
  does not.
- the law against the simulated silicon: the lab 495 frames, the
  reactor 381, bit-equal; the frame 51% / 58% and 55% / 61% (median /
  peak). On the card 2026-11-23.

## P48: exact dodges in his own widths; where he will land (2026-11-23)

The player, of P47 on glass (ten minutes of the reactor): "this feels
alot better, for the boxing I think we want an exact left right up down
flip jump, not the double press one, this is to quick dodge maybe two
units, the none boxing is a single unit dodge. The running should feel
very good at figuring out where your jump and double jump (flip) should
land, maybe having the camera also cover the ground to see where you
are going to land. over all this positioning tackcially." The lab and
the reactor only.

- **A UNIT IS HIS OWN WIDTH** (0.58: the reactor's check, which he asked
  to be "unit to the player width"). MY READING; the dodge knob is now
  that unit's length (1.0), so it is one turn to change.
- **THE TANK'S DODGE IS ONE**, exactly, in six frames (it was 2.4 units
  -- four of his widths -- in twelve). The way the pad points; none
  held, back; Down with A is still the quick turn.
- **THE BOXER'S A WITH A DIRECTION IS A FLIP THAT WAY, AT ONCE**: one
  press (the flip was the second press in the air; the first was a
  strafe jump of three units), the flip's own tuck or cartwheel, low (a
  quarter of a unit) and over in ten frames, and down EXACTLY two of his
  widths from where he left the floor, stopped. There is no second. A
  with no direction is the jump, and A again in the air its flip, as
  before.
- **WHERE HE WILL COME DOWN IS MARKED**: in the air on his own arc, a
  small red lozenge lies on the floor where he will land -- his arc run
  on to the floor, the same steps, counted, and that many frames on at
  the pace he has. For the run's jump it is right to a thousandth of a
  unit from the first frame; a flip moves it at the press (it cannot be
  known before) and from then it is right to a twentieth; steering in
  the air, it goes where he is steering. A wall is not looked for.
- **THE LENS COVERS THE FLOOR**: it goes up with him, so in the air it
  looks DOWN -- sixteen of the turn's 1,024 a unit of his height, sixty
  at most -- and steps nine tenths of a unit to his right, because the
  floor he is coming to is straight ahead of him and from square behind
  his own body stands on it. Not while he is locked.
- NOT DONE: nothing shows where a jump WOULD land before it is thrown.
- tests: `tests/test_tnd_move.py`, 14 (each dodge and flip to the
  hundredth of a width; the knob doubling it; the mark against where he
  lands, with and without a flip; the lens). The lab's 40, the aim's 12
  and the reactor's 7 pass. Layers 0, 4, 8 and the full cart
  byte-identical. The knob registries are at mapping_version 2.
- the law against the simulated silicon: the lab 405 frames (the run's
  jump and flip, the dodges, the flips, a locked round), the reactor
  386, bit-equal; the frame 48% / 56% and 59% / 65% (median / peak). On
  the card 2026-11-23.
- His tape: `experiments/tnd/tnd-reactor-0003.json`.

## P49: the acrobatics, tucked (2026-11-23)

The player, of P48 on glass (3m08s of the lab: 122 jumps, 136 dodges and
flips): "the legs on the side flip should be tucked too, work on the
arcrobatics poses." The lab and the reactor only.

- **WHAT WAS THERE.** The flips are SHAPES the cart spins: the archive's
  tuck (forward), a layout arch (back), and for both sides a straddle
  star -- the legs thrown wide and straight, a cartwheel. And two faults
  of mine under them: the boxer's quick flip (P48, ten frames) played a
  flip's clip a pose a frame, so it showed the first half of the shape;
  and its length was not in the spin's table of reciprocals, so its
  progress went in unscaled and made only whole turns -- IT DID NOT TURN
  AT ALL. What he saw from the side was the straddle, upright. (The tank's
  dodge, six frames, played half its clip the same way; a wall jump,
  24 frames on a 20-pose clip, ran four poses into the next.)
- **THREE NEW SHAPES, baked on the archive's own rig** by
  `tools/tnd_acro.py` into their own file (`assets/tnd/acro.npz`, beside
  `boxer.npz`; every other layer is built from boxer.npz as it was):
  the forward tuck with both hands on the shins; a back TUCK (the knees
  the same, the chest open and the head back, hands on the shins) for
  the layout; and the side flip TUCKED -- knees up a hand apart, the
  trunk curled less than the front tuck, hands on the shins. Each eases
  in from the guard over its first fifth and out over its last; the
  hands are put on the shins by the archive's own two-bone reach.
- **EVERY FLIP AND DODGE PLAYS ITS WHOLE CLIP**, at the same fraction of
  the clip as of its own frames, whatever their number.
- **THE QUICK FLIP TURNS ONCE ROUND** -- a roll for left and right, a
  pitch forward and back -- in its ten frames.
- NOT DONE: the reactor's double copies his shape but not his turn, so
  mirroring a flip it does a tuck jump.
- tests: `tests/test_tnd_move.py` (5 more: the shapes are tucked and
  begin in the guard, the side's legs no longer wide; each quick flip
  goes round and plays its whole shape). 86 pass across the lab, the
  reactor and the tools. Layers 0, 4, 8 and the full cart byte-identical.
- the law against the simulated silicon: the lab 315 frames, the reactor
  283, bit-equal; the frame 49% / 65% and 59% / 61%. On the card
  2026-11-23.
- His tape: `experiments/tnd/tnd-lab-0004.json`.

## P50: the run as a traceur's -- the leap, the landing taken, the roll (2026-11-23)

The player: "the running should also have an animation while you are
falling. just make the whole running feel better like a true
parkourist". The lab and the reactor only.

- **WHAT WAS THERE**: in the run the stride's clock went on in the air,
  so he sprinted on nothing, up and down; and he came down straight into
  the stride.
- **THE LEAP** (`tools/tnd_acro.py`, seven shapes on the archive's rig,
  chosen by how fast he rises or falls): the DRIVE off the ground -- the
  lead knee up, the rear leg long behind, the arms opposite; the STRIDE
  across -- the rear heel up to the seat; and the GATHER -- both feet
  brought forward under him, the knees bent to take it, the arms
  forward and up. A run off an edge falls in the gather.
- **THE LANDING TAKEN**: in the run he comes down deep in the knees, the
  hands forward, and rises into the stride over eight frames.
- **THE ROLL**: down from a flip in the run, going, he rolls over the
  shoulder -- the tuck, its ball brought down to the floor and turned
  about its own middle -- sixteen frames, KEEPING his speed (1.2 units
  and more), and runs on. A jump during the roll ends it and jumps.
  Standing still a flip lands taken in the knees.
- READINGS OF MINE: the three shapes, the absorb, the roll and that a
  flip (not a plain jump) is what rolls.
- Found on the way, mine: two tests in the new code read "is the roll
  on" as `evk == 8 AND evf` -- a bitwise and of a truth and a count:
  12 is even, so a roll of twelve frames left was "off". Each is two
  tests now.
- tests: `tests/test_tnd_move.py`, 4 more (23): the leap goes from the
  drive to the gather and never shows the stride; the landing is taken
  and the stride takes up; a flip rolls over, keeps his speed and runs
  on; a jump ends a roll and a flip standing still does not roll. 90 pass
  across the lab, the reactor and the tools. Layers 0, 4, 8 and the full
  cart byte-identical.
- the law against the simulated silicon: the lab 361 frames, the reactor
  258, bit-equal; the frame 49% / 63% and 57% / 61%. On the card
  2026-11-23.

## P51: over the clone; the traceur's stride; the lens into the landing (2026-11-23)

The player, of P50 on glass: "the boxing jump flips should be calibrated
by being able to jump over the clone in all four directions. the gun
aiming still shows the hit spark on the target, that is only on hit.
also the parkour feels better but can be improved so animations feel
like smooth transitions and more realistic runs and the camera when
jumping should be like the inner tangent of the curve, so the point of
view is going into where you'll land to help with precision." The lab
and the reactor only.

- **THE BOXER'S FLIP GOES OVER A BODY**: from a jab's reach on this side
  to a jab's reach on the other -- four of his widths (it was two), the
  dodge knob still its length -- rising to 1.4, so the tuck (its lowest
  half a unit over his feet) clears a head 1.41 up the whole time he is
  over it. A test does it all four ways. In the reactor the double is
  not solid to a flip that clears it.
- **NO SPARK UNTIL A ROUND LANDS**: the point at the laser's end is gone;
  the laser is the whole sight, and the red burst is the hit.
- **A TRACEUR'S STRIDE** (`tools/tnd_acro.py`, `acro_run`, sixteen poses
  on the archive's rig, for the lab's run): the thigh driven 65 degrees
  forward and 30 back, the heel folded to the seat in the recovery, a
  light knee at contact catching the weight just after, the arms pumping
  opposite with the elbow closing as the hand comes up, the pelvis
  turning with the stride and the shoulders against it, the lower foot
  always on the floor.
- **TRANSITIONS WITHOUT A POP**: the leap has thirteen shapes (it had
  seven) and two sides -- the knee that drives is the one that was
  swinging when he left the floor; the landing goes from the gather into
  the knees and up into the stride's FIRST pose, and the stride takes up
  from there; the roll goes from the knees into the tuck and up into the
  same pose, and the stride takes up from there too.
- **THE LENS IN THE AIR LOOKS INTO THE LANDING**: in the run its line
  comes round to the way from him to where he will come down (a quarter
  of the gap a frame), so steering in the air it goes into the turn; it
  stands on the INSIDE of that turn (on his right when straight); and in
  any jump it pitches so that the middle of the glass is on the spot --
  over the line of his own body, the spot below him in the frame. A test
  holds the middle of the glass within a unit of the spot.
- READINGS OF MINE: "the inner tangent of the curve" as the lens on the
  inside of his turn looking into the landing; every shape.
- tests: `tests/test_tnd_move.py`, 32 (9 more). 99 pass across the lab,
  the reactor and the tools. Layers 0, 4, 8 and the full cart
  byte-identical.
- the law against the simulated silicon: the lab 586 frames, the reactor
  323, bit-equal; the frame 50% / 62% and 57% / 62%. On the card
  2026-11-23.

## P52: the run's two jumps -- a running jump, and the long jump (2026-11-23)

The player: "i feel like the overal jump feels a bit cartoony in the
distance covered, a held jump release should be that distance long
jump, olympic style". The lab and the reactor only.

- **WHAT WAS THERE**: in the run every press of A was the same jump, at
  once: five units (six and a half metres at his height, if he is 1.8 m)
  with his feet 1.64 up -- two metres -- in thirty frames, under a light
  pull rising and a heavy one falling.
- **IN THE RUN A IS READ WHEN IT IS LET GO.**
- **A TAP IS A RUNNING JUMP**: 3.1 units (four metres) at his full pace,
  his feet 0.81 up -- enough for the lab's first step -- eighteen frames,
  the same pull up and down, heavy.
- **HELD A FIFTH OF A SECOND (12 frames of glass) AND LET GO, THE LONG
  JUMP**: 6.0 units (7.6 metres) at his full pace, low -- his feet 0.53
  up -- and flat, thirty-six frames under a pull close to the world's
  (one and a half g at his scale). Its own thirteen shapes
  (`tools/tnd_acro.py`, `acro_long`): off the board the free knee drives
  and the arms swing up; the HANG, arms overhead, legs under him, the
  back arched; then the JACKKNIFE, arms sweeping forward, the legs
  straight out in front, the trunk over them. Held longer, time slows as
  for any held button; let go, he jumps in running time.
- Either goes as far as his pace takes it; the landing mark is right to
  a thousandth of a unit for both. A flip in the air is the flip's own
  arc again, whichever jump it came out of.
- READINGS OF MINE: the release; the hold of twelve frames; the two
  distances (from his height and his pace: his run is 0.16 units a frame,
  twelve metres a second -- faster than any sprinter, so the long jump's
  pull is a little over the world's to keep it at an Olympic length).
- tests: `tests/test_tnd_move.py`, 35 (3 more; eleven older ones release
  A after a run's jump now). 102 pass across the lab, the reactor and
  the tools. Layers 0, 4, 8 and the full cart byte-identical.
- the law against the simulated silicon: the lab 406 frames, the reactor
  232, bit-equal; the frame 49% / 58% and 58% / 60%. On the card
  2026-11-23.

## P53: reading a route -- the arc through the room, the wall's dot, the lens (2026-11-23)

The player: "i like how it starting to feel. learn a bit about what ive
been trying to do on the platforming. there are some visual bugs and the
held jump landing to precise put the player in slow motion is fun. also
a dot where the player would hit on the wall for a wall jump. make those
dots for jumping yellow. the long jump would be if jump is held and the
player enters parkour from stationary." The lab and the reactor only.

- **WHAT HE HAS BEEN DOING** (`experiments/tnd/tnd-lab-0005.json`, his
  5m49 of P51's lab): a COURSE through the structures along the north
  wall, run again and again -- the steps 0.8, 1.6, 2.4, the ledge, the
  slider, the lift, the 4.0 platform, and back -- in the run 61% of the
  time; 151 jumps and falls, 87 onto a structure; flips to reach the lift
  and the platform; 55 walls touched.
- **THE VISUAL BUGS, in his own frames**: the landing mark floating in
  the air or drawn on a step's side -- it was drawn at the height of what
  he stood on, and its arc knew nothing of the structures; and the glass
  dark purple -- the lens inside the lift.
- **THE ARC IS WALKED THROUGH THE ROOM**, a frame at a time as he will go
  (the same pull, the same paces): a structure's side or the hall's wall
  stops it the way the arena stops him (the axis it blocks, the other
  kept); a structure's top under him as he comes down is where he lands;
  else the floor. The mark is drawn there, AT ITS HEIGHT. On the floor,
  onto a step and along a wall it is right to a hundredth of a unit from
  his first frame in the air. About 4,000 more instructions a frame at
  most (18,700 of 65,536).
- **THE WALL'S DOT**: the first wall the arc meets, a yellow dot on its
  face at his chest -- where he will touch it, the wall jump's place.
- **THE JUMP'S MARKS ARE YELLOW** (the gun's stay red).
- **THE LENS**: a lens inside a structure's box is lifted over its top;
  and in the air it now looks halfway between the spot and his chest
  (P51 looked at the spot alone: a high flip toward the lift took him
  off the top of the glass).
- **THE LONG JUMP IS FROM A STAND**: A goes down with him standing in
  the run (or he goes into the run with A down), he runs up, and lets
  go: the long jump. Held while he is already running, time slows (as
  for any held button: "the held jump ... in slow motion is fun") and
  let go it is the running jump.
- tests: `tests/test_tnd_move.py`, 40 (the mark on the step at its
  height, the wall's dot on the east wall at his chest, the lens never
  inside a structure, a high flip keeping him and the spot in the glass,
  the long jump from a stand, held at speed in slowed time). 107 pass.
  Layers 0, 4, 8 and the full cart byte-identical.
- the law against the simulated silicon: the lab 428 frames, the reactor
  217, bit-equal; the frame 47% / 63% and 59% / 63%. On the card
  2026-11-23.

## P54: the marks against his own jumps (2026-11-23)

His tape of P53's lab (4m33, `experiments/tnd/tnd-lab-0006.json`): the
course again, 74% in the run; the long jump from a stand armed eight
times and thrown four (one onto the lift, 6.3 units); 61 walls touched
and 25 wall jumps, the wall's dot showing in 1,072 frames. His motion
replays the same on a build whose marks differ (the marks move nothing),
so the marks can be judged against where he really came down: of 36
jumps with no flip, wall jump or steering in the air, the FIRST mark
was off by more than a third of a unit 16 times -- climbing the steps.

- **Two faults of mine, both the arc not following the game**: a way the
  arc found blocked stayed blocked for the rest of the jump (the arena
  tries the whole step again every frame); and it waited to come DOWN
  onto a step's top, where the game steps him up onto a top the moment
  his feet are within a step of it, rising or not, and the arc goes on
  from there. Both follow the game now.
- On the same tape: the first mark's median 0.011 units, 8 of 36 over a
  third -- the lift and the slider move under the arc (the mark takes
  them where they are), a run still gathering pace at the jump, and a
  slide along the south wall; each converges as he flies.
- tests: `tests/test_tnd_move.py`, 41: one replays his tape (local:
  tapes are not in the repository) and holds the marks to that. 107 pass
  besides. Layers 0, 4, 8 and the full cart byte-identical.
- the law against the simulated silicon: the lab 353 frames, bit-equal;
  the frame 47% / 59%. On the card 2026-11-23.

## P55: no structure clips him; the long jump on a hold, shown while held; one marker; the flip drops; the roll's arms (2026-11-23)

The player: "the platforms have some geometry issues, clipping and
collision. the long jump should just be after holding the jump button,
the location of the jump should be in slow motion and on the wall if it
will hit the wall, only 1 marker either it lands on a wall or floor. the
second flip jump slow mo, back down should drop more immediately for
targetted landing. also the arm on the roll looks a bit glitchy". The
lab and the reactor only.

- **CLIPPING AND COLLISION, on his tape of P53**: 943 frames with his
  body INSIDE the slider, up to 1.37 deep -- it slid into him and nothing
  put him out; the others up to 0.3 at their edges. Now a structure is a
  box he is never in: found inside one (his middle within its side's
  reach, his feet under its top by more than a step) he is put out by
  the nearest face whose way out is clear -- the steps stand side by
  side, and the nearest face of one is inside the next (the first cut
  put him into the 0.8 step out of the 1.6). On both his platforming
  tapes replayed: no frame inside the slider; the rest a few frames at
  an edge, at most 0.28 -- his body's own half-width as he steps up or
  off.
- **THE LONG JUMP IS A HELD A**, whatever his pace (P53's stand is
  gone): held twelve frames of glass in the run, the long jump's
  landing is SHOWN from then on -- held past the hold knob, in slowed
  time -- and let go, that is where he lands (to a hundredth).
- **ONE MARKER**: if the arc meets a wall, the marker is on the wall,
  and the floor's is not drawn; else the floor's (or a top's). The lens
  aims at that one.
- **THE FLIP DROPS**: it rises as it did and comes down at more than
  twice the pull (0.050 a frame, it was 0.024) -- from its top it is
  down in about half the frames it took to rise. MY READING of "the
  second flip jump slow mo": a flip in slowed time (A held) is the same
  flip, and what was asked is the drop.
- **THE ROLL'S ARMS**: the roll was lowered to the floor through the
  rig's root, so the reach that puts the hands on the shins aimed from
  where the shoulders had been -- an arm stretched 0.4 across him. Now
  it is posed where it stands, and lowered after.
- tests: `tests/test_tnd_move.py`, 44 (the long jump shown while held
  and landing there; one marker at the wall; the slider never has him
  inside, nor puts him into the ledge; a flip down in fewer frames than
  it rose; the roll no wider than the tuck); two lab tests now drop him
  from above instead of putting him inside a step at the floor. The
  test that replays his tape is looser: his presses no longer make the
  same session. 111 pass. Layers 0, 4, 8 and the full cart
  byte-identical.
- the law against the simulated silicon: the lab 338 frames, the reactor
  217, bit-equal; the frame 50% / 60% and 59% / 63%.

## P56: how he plays -- the course, timed; the lens drawn in clear of the tops (2026-11-23)

The player: "look at how im trying to play and optimize" and "look at
the top of platforms graphics are clipped". The lab only (the lens's
draw-in is the reactor's too; it has no structures).

- **HOW HE PLAYS** (`tnd-lab-0007`, 31m32 of P54; `tnd-lab-0008`, 4m28
  of P55): the north wall's structures as a ROUTE, run again and again,
  getting faster -- from the first step without touching the floor: to
  the ledge in 1.9 s at best, the slider 3.8, the lift 17.9 and then 9.4;
  the 4.0 platform never reached in one go; off the course mostly from
  the ledge, the lift and the slider. Long jumps 13 in 31 minutes, then
  30 in four and a half once they were a held A; slowed time 39%, 48%.
- **THE COURSE'S CLOCK**: the time from leaving the first step to
  standing on the 4.0 platform, in time as he lives it (slowed time
  costs: the traversal rank of TND-WORLD), top middle in seconds and a
  small tenth; gold when done, and his best under it; on the floor the
  run is void. (The font has no point: the tenth is the small figure.)
  On his own P55 session replayed: two runs, both void (to the lift in
  16.1 s, to the slider in 13.4).
- **THE TOPS CUT AT THE GLASS**: P53 lifted a lens found inside a
  structure just over its top; in his P55 session the lens was 0.1 to
  0.4 over a top for 232 frames, the top sliced by the lens. Now the
  lens is DRAWN IN: from his head toward where it would be, in eighths,
  it stops at the last place clear of every structure (a quarter of a
  unit off its sides, 0.7 over its top); with none clear -- his back to a
  structure's side -- it is over his head. Replayed on his session the
  lens is clear in every frame but those 23 (at his back to the
  platform, on the lift); a test holds four places by the structures.
- tests: 113 pass. Layers 0, 4, 8 and the full cart byte-identical.
- the law against the simulated silicon: the lab 333 frames, the reactor
  217, bit-equal; the frame 46% / 58% and 59% / 63%. On the card
  2026-11-23.

## P57: the lab's worst frames, from a census of his whole session (2026-11-23)

`experiments/isa/census.py` read every one of his 16,109 frames against the
machine's stores. The two frames past the 90% gate were the pause opening
and closing (each copied the whole 32,768-word page): the lab copies the
incoming program's own length now (98% -> 64%, 91% -> 81%). The instruction
worst (54,898) was the landing arc testing every structure's four bounds at
every step: its tests give up at the first failed bound (worst 44,341, the
marks identical). On ISA generation 2 (`experiments/isa/README.md`).

## P58: the park -- the lab's moves on a course that is a field (2026-11-23)

The player: "i think what we need is a platforming lab, to test out all the
movement modes. you should be creative to push the zeta hypothesis"; "make
the world insanely large and packed with activities to push the limits ...
make it fun to platform, his running jump felt a bit low before"; "we want
to be able to have strong platforming capability".

TND_LAYER=12, "TND PARK" (`experiments/park/README.md`):

- an endless corridor (16,000 units each way), three lanes of stations, each
  lane its own course: a FUNCTION of the station's number -- one of fourteen
  kinds (TAP, STEPS, LONG, FLIP, FLIP UP, PADS, SLIDE, LIFT, DROP, WALL, and
  the combinations HIGH, CHAIN, RIDES, TOWER), its gaps the measured reach of
  the move it tests times a tightness rising from 0.70 to 0.94. The middle
  lane teaches: each kind once, in order. Unfolded a station a frame into a
  ring of 56 rows; the 8 nearest are the window every test asks. The lab's
  seven structures cost 3,115 program words; the park's course costs 4,541,
  for any length.
- ORBS over the gaps and above the hard tops; the HUD shows the streak
  (stations cleared without the floor between entry and last box) and the
  orbs. Tops coloured by what the station asks (green a jump, red a power
  move, yellow a mover, black a wall).
- strong platforming, in the park only: the tap 1.28 up and 3.71 far (0.81,
  3.06); COYOTE (six frames off an edge, A is the ground's -- a press begun
  at an edge was cancelled as he ran off it); a BUFFER (A in the air with the
  flip spent is kept eight frames for the landing); six wall kicks an air,
  for the WALL station's chimney.
- in the park the P55 push-out runs on the ground only: run first, it put
  him out of a structure before the arena could refuse the step, so a
  structure in the air was never a wall touched (no kick off it).
- `experiments/park/bot.py` plays it on the real controls: 31 stations in a
  row, 38 orbs, 97 seconds. tests/test_tnd_park.py (6).
- the bot's run on the simulated silicon: the frame median 60%, peak 83%,
  none over; 600 frames bit-equal against the law. Instructions a frame
  median 27,109, worst 50,474 of 65,536; data memory 248 words free.
- every other layer and the full cart byte-identical.

## P59: the park's controls and physics, recalibrated (2026-11-23)

The player, after fourteen minutes of P58's park (`experiments/tnd/tnd-park-0001.json`): "i think its just to
precise for a human to do. maybe long jump should be down in running where you can see the do extending to judge
it correctly, and the jump be on press no release. the slide can be the special button, superman punch on jab
during running too. it looks cool but its too slidy i should feel more snappy to the ground, also the wall jump get
annoying at times when the goal is straight ahead"; "the obstacle sizes are fine its the player physics and that
need calibration"; "it should just feel a bit more like controlled parkour and be able to be run without the slow
mo, slow mo is more of just for extra precision. maybe we have to rethink the controls"; "the camera must
compensate for the lack of analog control."

His tape: 759 A presses held a median 11 frames -- on P58's rules a held A slowed time and became the long jump
(79 of them); the run only 64% of the time (a shoulder had to be held); 94 attempts, 20 cleared.

The park's own controls (layer 12 only; MY READING of "rethink", to be judged on glass):

| | |
|---|---|
| the pad | the run, always; its eight ways are the COURSE'S, the lens holding the course's line (Up straight down it, a diagonal 45 degrees, Left straight across); Down turns him round, and let go Up carries on the new way |
| A | the jump, on the press; in the air the flip; at a side wall, going into it or with the pad toward it, the kick |
| B held | the long jump: its landing shown, running out from 3.6 to 10.8 units over 40 frames; let go, he goes ("down" read as held down: the pad's Down steers) |
| Y | the slide |
| X | the superman punch: the jab in a lunging leap (2.6 units) |
| R held | slowed time -- and nothing else slows it |

Physics, against the same obstacles: his pace 0.20 a frame (0.161); the tap 1.28 up, 3.8 far, coming down at 1.7
times its pull going up (18 frames in the air, was 22); the grip on his heading 0.70 (0.34), coasting 0.62 (0.84),
the pick-up 0.60 (0.30) -- let go, he stands within 20 frames; in the air, the pad let go brakes him (0.88 a frame)
to stick a short top; no kick off a face across his way (it threw him back the way he came). The bot clears 41
stations in a row; the law against the silicon 400 frames bit-equal; instructions median 26,774, worst 49,138.

## P60: the park is the run -- the lens behind him, no gun, and the whine was the record (2026-11-23)

The player: "feels a bit better but the camera should be always behind the player. the gun stuff is still linked
in this mode, and all the other controls are working, it should be the running mode with the double right
shoulder. also there's a beap whine i hear through out."

- the park steers as the parkour run does (P24's double click): Left and Right turn him, Up drives -- P59's
  course-relative pad is taken back -- and the lens is behind him: half the gap to his heading a frame, in the air
  too (within 12 yaw units while he turns).
- R is the park's slowed time and nothing else: it was the lab's targeting key, so holding it for slowed time
  chose the clone, locked, brought the aim up and planted him. Now the targeting never sees it.
- THE WHINE: the record's intro carries a steady 2,004 Hz line -- in the original MP3 at 44.1 kHz, not made by the
  bake (a low-pass or the soxr resampler leave it as it is). The song climbs its ladder with a fight's rank; the
  lab and the park have none, so they loop the intro and its line for ever. In the park the ladder is the streak:
  from the lift, a section higher every two stations cleared in a row (the 2 kHz line: 31.6 times its band in the
  lab's song, 5.6 in the park's). The lab still loops the intro: a question for the player.
- the bot clears 41 in a row; tests 9 pass; every other layer byte-identical.

## P61: the park keeps the lab's controls; its run is the parkour (2026-11-24)

The player: "make sure this is mode of button only works when double tap holding [the] shoulder. The rest of the
controls should stay the same" -- "double tap left shoulder enters running, then right instead of target is the
running slow motion"; "The dpad on the filp jump should control the landing location a bit in all 4 directions.
drop the b long jump ... b should just be the gun. the wall jump is getting better, the marker should also just be
a plain circle on the wall like how its on the floor. straight on wall jump should be a verticle wall kick up to
save a failing jump. The camera for the turning and the jumps needs work. in slow motion its almost perfect. in non
slowmotion it should should be the outer tangent of the jump curve. the first jump should be modulated a bit with
how long the jump button is held but not to much. the second jump is not but the added control with the dpad can
make precision landing better."

- the lab's controls everywhere: the tank, L the boxer, R the target, B the gun. L clicked twice and held is the
  run (the lab's P24); in the run R is slowed time (never the target), and nothing else slows it there.
- no long jump.
- the first jump by its hold: 0.85 up and 3.2 far tapped, 1.29 and 4.2 held 8 frames, 1.40 and 4.6 held 20 (0.92
  of its pull rising while held, 1.45 let go). The flip is not modulated.
- the flip steered: in it the pad moves him, 0.045 a frame, on, back and aside (about half a unit over a flip);
  it does not turn him.
- a face across his way, the flip spent: A is a kick straight up it (the flip's rise, nothing thrown back). With
  the flip still his, A at a face is the flip.
- the wall's mark is the floor's, stood on the wall facing the way it stops him.
- time running, in the air, the lens rides the outside of the arc (MY READING of "outer tangent"): up at once to
  the walked arc's top, looking down at where he comes down. Slowed, as it was.
- the bot clears 41 in a row; tests 9 pass; every other layer byte-identical.

## P62: the park made playable in real time, from his own twenty minutes (2026-11-24)

The player: "look at my game play improve this based on how i want to use it. it should still be human playable
not in slow mo."

His tape of P61 (20 minutes; `experiments/tnd/tnd-park-0004.json`), observed: 87% in the run, 62% of the run in
slowed time; 154 attempts, 80 cleared -- in real time 32 of 75, slowed 48 of 79; real time WALL 0 of 9, PADS 2 of
11, CHAIN 0 of 3. The 74 failures: 23 short of the box (many by 0.4, at its face), 15 past it (a flip carried
five to seven units over a short top), 14 run off an edge unjumped, 10 under a top (7 the chimney's cap), 10 beside
it. A is held, never tapped (median 17 frames); most jumps are flipped, Up held through 65% of the flip; in real
time he stands still on a box 58% of the time before going. So: stop, line up, the full jump, the flip, the flip
steered. Layer 12 only, the obstacles as they were:

- THE LEDGE CAUGHT: in the run's air, his feet up to 0.7 under a top he has reached, he is on it (on the ground a
  step is still 0.3). A jump begun 1.7 early for a 2.6 gap still ends on the box.
- THE FLIP'S CARRY IS THE PAD: Up his full pace, nothing half, Down a seventh, whatever pace he left the ground
  with -- from a run 7.8 / 5.0 / 3.0 units, from a stand 5.8 / 3.0 / 1.0; Left and Right 0.05 a frame aside.
- the held jump is the jump the course was sized for (1.28 up, about 4 far); a quick tap the low one (0.85, 3.2).
- ten frames of grace off an edge, ten for an early press.
- the chimney: after the first kick any side wall kicks; a kick rises 0.24 (the flip 0.20); a touch counts 12 frames.

Measured with the bot given a human's timing (each jump up to 6 frames early or late, 150 seconds, three seeds):
P61 cleared 1, 37 and 19 stations (best streaks 1, 12, 11); P62 43, 47 and 48 (41, 47, 45). Tests 11.

## P63: Down held brakes the roll (2026-11-24)

The player: "i also think holding down depad from coming of the roll should slow it down may help". The roll out
of a flip keeps the pace he lands with: 16 frames, 3.65 units after the landing with the pad let go -- off the end
of a short top. In the park, with Down held, each frame of the roll takes a fifth of its pace: 0.78 units, and he
comes out nearly at a stand. (Up held, he runs on as before.) tests/test_tnd_park.py: 12.

## P64: the run's lens, steady -- measured on his own session (2026-11-24)

The player: "feels a lot better, maybe what we need is is just improving the cameras for running and slow mo
running, it still feels to jaring. maybe making the running not move with the arc, since thats more with slow mo
since its over the shoulder. i think we are close".

His tape of P63 (7 minutes; 47 attempts, 35 cleared -- 74%, from 52% on P61; slowed time 47% of the run, from 62%).
The run's steering does not read the lens, so the tape replays to the same motion under any lens (checked: his
place, height, heading, the streak and the orbs equal every frame), and the lens is measured on his own play:

| in the run, a frame | P63, real time | P64, real time | P63, slowed | P64, slowed |
|---|---|---|---|---|
| height moved more than 0.25 | 505 (worst 2.47) | 15 (worst 0.50) | 375 (worst 5.83) | 23 (worst 0.49) |
| distance from him more than 0.25 | 233 (worst 3.50) | 78 (worst 0.29) | 30 | 0 |
| yaw more than 24 of 1,024 | 102 (worst 134) | 0 (worst 20) | 31 (worst 234) | 0 (worst 20) |
| pitch more than 8 | 572 (worst 34) | 0 (worst 7) | 473 | 0 |

What was jolting it, and what it is now (layer 12, in the run):
- its HEIGHT went to the arc's top at a takeoff and back at a landing (P61's "outer tangent", my reading). Time
  running, it is level with where he will STAND -- the walked arc's landing height, so it comes level with a higher
  top as he comes to it -- and does not go with a plain jump; past 0.9 over that (a flip) it goes up by nine tenths
  of the rest, or he left the glass. Slowed, it is with his feet (over the shoulder, with the arc). Eased a quarter
  of the way a frame, 0.20 a frame at most (0.30 slowed).
- its PITCH dived at the landing spot: time running it is level; slowed, 6 of 1,024 a frame at most.
- its YAW: a quarter of the gap to his heading, held through a wall kick's throw (the kick mirrors his heading),
  and 20 a frame at most whatever asks (slowed, the focus lens swung it 64 to 88).
- the DRAW-IN clear of structures stepped an eighth of the way (0.43): it is a goal now, in quickly, out slowly.
- the town's LENS-OUT-OF-WALLS rule asked the arena, and the park's arena counts a box's footprint a wall at any
  height: over a box the lens was shoved and re-aimed. In the park it asks about the corridor's walls only.
- no landing SHAKE in the park's run (five frames side to side, a landing a second).
Tests 13; every other layer byte-identical.

## P65: the park's run is a fighter's; the kick up a face is a save (2026-11-24)

The player: "control and jumping in both feels good, the wall jump still has some issues. the thing that needs
work now is just the player poses and animation so it doesnt feel as cartoony, it should blend well with the rest
of the move set like the boxer and tank."

THE POSES. Rendered from his side beside the tank's walk and the boxer's jab, the run was another animal: the
trunk bent 56 degrees forward through hips, spine and chest (the boxer's guard is 27), the head thrust out, the
trailing leg thrown straight back; the jump a hurdler's split. tools/tnd_acro.py bakes the same clips again with
the fighter's carriage, under their own names (park_run, park_leap, park_leap_l, park_land, park_roll -- the same
lengths; the lab's are bit for bit as they were): the trunk 30 degrees and the head up; the thigh 52 forward and
24 back (65 and 30); the hands pumping close, up by the chest; the leap a driven knee with the other leg folding
under him; the landing sat into the knees with the fists up. Layer 12 reads those. Its stride is five units a
cycle (four): at his pace there the legs turned over six times a second.

THE WALL JUMP. His tape of P64 (8 minutes; 90 attempts, 67 cleared; slowed 35% of the run; best streak 12): he
does not climb the chimney wall to wall -- all 24 of his kicks were the kick straight up a face, at the cap. Each
was the flip's whole rise (two units) and there was no limit: four took him to 7.7 over a cap at 4.5 and out over
the chimney's walls, in three of his five tries. It is a save now: once an air, 1.3 units -- with the ledge caught,
the cap from a flip that fell short.

Tests 15 (the lab's clips unchanged; every other layer byte-identical).

## P66: the jump's arc is one arc; the shot and the jab ride the run (2026-11-24)

The player: "plugged, almost there. the jump looks like the player snaps to the highest part of the arc to quick,
controls and movement are good though. the gun shot in running should not stop the running, the running jab should
not make the player jump."

THE SNAP. His tape of P65 (3.5 minutes; 29 attempts, 22 cleared; slowed 17% of the run): of 135 jumps from the
ground, 18 were lifted 0.6 in ONE frame (0.87 the most), three frames off the ground and still rising -- 17 of them
in real time. It was P62's ledge catch: a jump begun near a face was over the box's edge within 0.7 of its top at
once, was put on it, and went on rising from there, 0.4 higher than the jump is. (The ground's step did the same by
0.2.) Rising, nothing puts him on a top now: a top is under him when his feet are over it; the catch is for a jump
that has stopped rising (slower than 0.05 a frame). A jump begun against a face is the arc of one begun far from it
(1.25 held, 0.92 tapped), he waits at the face a few frames as he rises and goes on at his pace. The bot with six
frames of jitter clears as many (12/12/12 in 43 seconds; P65 12/11/13). And the leap's first poses hung 0.17 over
his feet (the legs gathered at once), so the body was drawn 0.39 up in a frame his feet rose 0.22: they leave from
the floor, the gap taken up over three poses.

THE SHOT. The park's run has no lock (R is its slowed time), so its shot was the standing one: the whole body in
the gun's clip, sliding along at the run's pace with its legs still. It is the locked run's (P36): the round leaves
at once the way he faces; the stride goes on, his upper half the gun's.

THE JAB. P59's superman leap is gone. X on the run is the jab's ARM over the run's legs, on the ground or in the
air (the body's two halves, P43): fourteen poses of his upper half baked on the stride's own trunk and height
(tools/tnd_acro.py, park_rjab) -- the boxer's standing jab laid over the stride tore at the waist, its trunk a
lunge ahead of the hips. It is an arm: it lands no blow (the park has nothing to hit on the run).

Tests 17. Every other layer byte-identical; the lab's clips bit for bit.

## P67: he is drawn where he is; the cylinder turns by the clock; the jab is thrown with the body (2026-11-24)

The player: "plugged. better, but the snapping still happens when in platforms especially high ones. the gun in
slowmo only does 3 shot bursts. and the jab needs improvement."

THE SNAPPING WAS THE DRAWING. P66 looked for it in the physics and found a real fault (the catch lifting a rising
jump), but not this one. His tape of P66 (11 minutes; 88 attempts, 56 cleared; best streak 15) replayed with the
drawn height beside the true: his height in the room made 10 one-frame rises over 0.3; the height he was DRAWN at
made 488, the worst 5.96, and was more than 0.3 from where he was for 2,556 of 33,472 frames of the run. He is
drawn at his height over what is under him plus a copy of ITS height that comes to it a quarter a frame (the
kerb's ease, P42's platforms riding on it). In the air, his feet crossing a box's edge, what is under him changes
at once and his height over it with it -- so that frame he was drawn the box's height too low, and leaving it too
high: 0.5 down and 0.6 up on a box of 0.8, and by the box's height on a higher one, as he said. In the park the
copy IS the height. What is eased is a lift GIVEN him -- the ledge caught (up to 0.7 in a frame), a step: a rise no
jump gives (over 0.25, or any on the frame he lands) is owed to the drawing and paid back a third a frame, no more
than 0.15 (slowed: a seventh, 0.05) -- he comes up onto it. The same tape on P67, his motion frame for frame the
tape's: 0 one-frame rises over 0.25 (the most 0.24, a jump's own speed); 29 frames more than 0.3 from where he is,
all of them the 17 climbs.

THE GUN, SLOWED. He taps B every 8 frames slowed: six rounds in fifty frames, and then the cylinder's 24 frames of
reload were the FIGHT's frames -- 84 on the clock, in which 23 of his 77 slowed presses met an empty gun (51
answered). The park's cylinder turns by the clock: 72 of 77 answered on the same tape. (Six rounds is the mag knob.)

THE JAB. Through the game's lens, behind him, P66's arm went straight out on his centre line and his own back hid
it. It is thrown with the body, as the boxer's is: the lead shoulder turned in behind the hand (26 degrees), the
other hand at his chin, and the fist PUT by the rig's own reach ahead of that shoulder and outside it, where the
lens sees the arm go out past him; out in two frames, held five. It is heard (the swing's whoosh). And it is a
string, as the boxer's X is: pressed again inside a second it is the CROSS off the other hand (the same poses
mirrored, park_rcross), then the jab; a press while the arm is going out is kept and thrown as it comes back.

Tests 21. Every other layer byte-identical; the lab's clips bit for bit. (The lab layers draw him the same lagging
way over their structures; not changed here.)

## P68: X on the run is the dive -- a tackle, and its roll (2026-11-24)

The player, of P67's jab on the run: "it should hit" -- and, plugged again: "i think its almost done, the jab
should be switched for a dive tackle roll. and then the running mode is done for now."

(The jab was first made to land: through the frames its arm was out it entered the swing's own landing path --
the key rung, a body struck, the hitstop, the spark. That path is the dive's now; the jab, its cross and their
poses are gone from the park.)

THE DIVE. X on the run, from the ground: he throws himself flat along his line -- 0.30 up, eleven frames, at the
burst of pace P59's leap had -- in thirteen poses of its own (tools/tnd_acro.py, park_dive: thrown off the stride,
laid out with his arms ahead and his head up, gathered for the floor), chosen by his rise and fall as the leap's
are. They ride the long jump's flag and clip, which the park does not otherwise have. The flip is spent in it.

THE TACKLE. Through the dive's fourteen frames his shoulder is a blow as a swing's fist is, 0.7 ahead of him and
0.7 up: what it meets takes the hook's two, is held and sent 0.9 -- and is DOWN. The blow's own hitstop and shake;
the spark where it landed; once a dive. Dived at nothing, nothing.

THE ROLL. He comes down into the flip's roll, the speed kept, Down its brake -- taken up a quarter of the way
round: he lands flat and head first, where the roll's turn is a quarter in, and its upright absorb is not his.
Twelve frames, and up into the stride.

Tests 22. Every other layer byte-identical; the lab's clips bit for bit.

The running mode, as he left it ("done for now"): L twice and held, the run; R, slowed time; A, the jump by its
hold, again the flip by the pad, at a wall the kick; B, the shot over the stride; X, the dive; Y, the slide.

## P69: the dive at a body's middle; the run's turn a rate, paid every frame (2026-11-24)

The player: "last issues. tackl should be higher like hitting the ceneter of mass of he clone, and make the
running left right thurning while running smoother, use the laser in the gun for reference if thats smooth then
good."

THE DIVE, HIGHER. It leaves at 0.15 (0.12): half a unit up, fourteen frames; and its poses fly half a unit over
his feet's height (a quarter): at its middle his body is between 0.9 and 1.25 over the floor -- a standing body's
middle. The blow lands THERE whatever his own height in the arc: 0.95 up a body, its trunk (carried on his own
height it reached 1.22, the head's zone, and took three).

THE TURN. Measured, holding Right in the run with the gun out: his heading went round 13 of the turn's 1,024 (4.6
degrees) on every frame, all at once from the first and none after the last -- and SLOWED, 13 on every THIRD frame
and nothing between, where the fight's time runs: his body, the laser on it and the lens after it stepped 4.6
degrees twenty times a second. The lens besides: slowed and running straight its yaw went +4, -2, -2 a frame --
the point the focus lens looks at moves on the fight's frames only -- so the laser, steady in the world, shook on
the glass.
- the park's turn is a RATE, in 256ths of a notch: toward the runturn knob's by half of what is left a frame
  (6, 10, 11, 12, 13), let go by three quarters (3, 1, 0); thirty frames of Right turn him 382 (390)
- it is paid EVERY frame: slowed, the slow knob's share (a third), the fraction carried -- 4, 4, 5 a frame, and as
  far round in all (128 of 130); on a held frame his body comes to his heading a frame behind it, as on the fight's
- slowed, the lens's last step is a quarter of its gap, toward nothing (a gap under 4 is left): straight, it is
  still (0 or 1 a frame; it was 2 to 4)
Roughness (the mean change of a frame's change), slowed and turning: heading 8.7 to 0.4; the lens 4.0 to 0.7.

One spot is as rough as it was: on the chimney's cap the walls squeeze the lens onto his head and its height moves
half a unit in a frame as its reach changes (0.48 on P64's run, 0.53 on the path the bot takes now).

Tests 23. Every other layer byte-identical; the lab's clips bit for bit.

## P70: THE YARD -- one room for the whole moveset (layer 13, 2026-11-24)

The player, the running mode done: "lets discuss how to start formalize the lab. it should be used to optimize the
feel of the player, enemies, items and combat. we should have a menu for configs of the lab and it would be cool if
we had also a menu that is like an action guide with a live rendering of the move being done" -- then "design a new
lab room, something that would be a good playground for the full moveset" -- and of the design, "looks fine get to
work". (The menus are not begun; this is the room.)

The lab tests fists in a box and the park the run down a corridor. The yard is the lab's hall, whole (64 by 32),
with the park's rows in it -- and everything the park's run became (P58 to P69) with them. First cut, of six zones
designed: the RING (its middle: four posts, the double and the elite), the TRACK (a lane round the walls with the
park's stations laid along it: 36 boxes and movers, 8 orbs), the RANGE (a firing pad and five bodies down a lane
north of the ring). experiments/yard/README.md has the plan, drawn from the cart's rows.

THE ROOM IS DATA. Layer 13 is the park's machine (PARK is true of it) with three differences: the hall's tiles are
the lab's, not the corridor's; park_unfold emits nothing; and the ring of rows is not cleared at the start, because
the cart's data already holds it -- YARD_BOXES, a list of boxes in the room's own measures, written into the rows'
table as the cart is built. Nothing in the program knows the layout. Its kinds are its colours.

WHAT THE RANGE TAUGHT. A round flies 13 units, tapped or charged (the charged one takes three, not one): the first
range stood bodies at 10 to 45 in one line, and only the nearest could be hit -- too far, and each behind the last.
They stand 5 to 12.6 from the pad, each on a bearing of its own.

MEASURED, a minute of walking, fists, the run, jumps, dives and shots at random with all seven standing: 27,581
instructions a frame at the median and 39,444 at the worst (of 65,536); 46 objects at the worst (of 64); on the
simulated silicon the frame is 53% of its clocks at the median and 73% at its peak (the gate is 90%).

Tests 5 (tests/test_tnd_yard.py): the table inside the walls and the seven on their marks; fists in the ring; the
range from the pad; the track's south side run by a scripted runner without the floor; a minute of anything inside
the room and the frame. The other three sides of the track are laid from the park's measured reaches and are not yet
run by a test. Layers 0, 4, 8, 10, 11 and 12 and the full cart are byte-identical.

## P71: THE YARD'S FIGHT -- a size is how much of his kit it has (2026-11-24)

The player, the yard on glass: "lets at the fighting. i want a challenge, remember the enemies depending on which
tier they are should be the difficulty, still meaty and modest health, the highest tier can essentially use my full
kit. lower less of the kit".

Until now the lab's bodies stood and answered a blow (P42), and layer 8's packs walked up and threw one haymaker in
turn (P41). Every size's pose file already held his whole kit. In the yard:

| | its kit | its strings | its tell | then it waits | it slips | its blows weigh |
|---|---|---|---|---|---|---|
| the horde (3 to take) | the haymaker | the haymaker | 40 frames | 90 | never | 0.8 |
| the common (5) | jab, cross, haymaker | jab-cross; jab-jab-cross; haymaker; cross | 26 | 60 | never | 1.0 |
| the elite (8) | and the hooks, the lead uppercut, a dodge | jab-cross-hook; jab-jab-rear hook; uppercut-cross; hook-haymaker | 18 | 40 | 100 of 256 | 1.15 |
| the double (12) | every fist he has, the dodge, the gun | jab-cross-hook-haymaker; jab-jab-cross-uppercut; hook-hook-uppercut; the gun | 12 | 26 | 170 of 256 | 1.25 |

(What they take is as it was -- a jab one, a hook two, the haymaker four -- and they answer a blow as the lab's do:
sent, lifted, held, down. A blow's worth off his 140: jab 5, cross 8, a hook 12, an uppercut 14, the haymaker 26,
a round 10, times its size's weight.)

A BODY'S PART. Up, free and on the floor: AWAKE (he came within 7.5 units, or struck it; asleep again past 24, and
back to its mark) it walks at its size's pace to its place BEFORE HIM -- a fan about the way he faces, the double
dead ahead, the elite and the common a ninth of a turn either side, the horde wider: the lens is behind him, and
what strikes him he can see. In reach, its wait over and fewer than two at it, it TELLS -- it blinks, still closing
-- and throws a string, each blow the move's own frames, in the move's own clip of its size's bank. A blow lands if
he is in that move's reach, before it, on the ground and not in a dodge's, a flip's or a roll's frames: he reels
(the hitstop by the blow's worth), and at nothing he is down -- and A, after the beat, is the room again, everyone
whole on their marks. Struck, a body loses its string: that is how it is stopped. A size with a dodge slips his
swing on its second frame, some of the time, a unit and a third back. The double, from four units to twelve, draws:
the round goes where the draw aimed, and a step aside is a miss.

THE WHO KNOB says who stands and whether they fight: everyone, fighting; the ring's two; the range, standing;
everyone, standing; the double alone; all but the double.

ONE ROUTINE. Written out a body each it was 2,900 words and the cart 34,201 against a page of 32,768 -- the loader
refused it. It is one routine now, run through three pointers (which body, its record, its size's row), 2,000 words
smaller; the strings are a word each, a move a nibble; the sizes are rows. The census's lesson again: the bodies
are data, and so is what they do.

MEASURED. He walks toward the ring and stands: down in five seconds (the elite and the double: eleven blows).
Mashing X without turning: he puts the double down once, they slip 14 of his swings, and he is down in thirteen
seconds. A minute of everything at random with the fight on: 44,422 instructions a frame at the worst (of 65,536),
48 objects; on the simulated silicon 54% of the frame at the median, 74% at the peak. The program is 28,759 words
(about 500 from its limit); data memory has 109 words free.

Not done: they walk through the track's boxes and the ring's posts (the arena they are kept in is the hall's
walls); they do not jump, run or dive; a blow of theirs does not move him; nothing is tuned on glass yet.

Tests 11 (tests/test_tnd_yard.py). Layers 0, 4, 8, 10, 11 and 12 and the full cart are byte-identical.

## P72: nobody shoots him (2026-11-24)

The player, the fight on glass: "remove gun, from them".

The double's fourth string was the gun's, drawn from four units to twelve. It is a fist string (cross, uppercut,
haymaker); the routine's gun branches, the size rows' gun word and the aim cells are gone. The double's kit is every
fist he has, and the dodge. (P71's table: strike "the gun" from the double's row.)

Tests 12 (one new: eight units from the double, awake, for fifteen seconds -- nothing lands). The program is 28,697
words; data memory has 113 free.

## P73: the invisible enemy; and the weight of a blow (2026-11-24)

The player, the fight on glass (P72, 2m55s): "make improvements its plugged in. remember we have to make things feel
epic and like damage is being done, re work the poses as needed to give weight to the hits and reactions. also
there was like an invisible enemy that made it hard to play".

THE INVISIBLE ENEMY WAS THREE. His tape, replayed with every body and the lens beside him: 73 blows landed on him,
35 of them the double's; he took 172 off the elite and put it down 14 times, 24 off the double and never put it
down.
1. THE FRAME'S STORE. A frame's cart meshes may have 2,048 faces, admitted in the order they are listed; one that
   would not fit draws nothing. He is 737, the double (his own body, whole) 737, the elite 369, the common 252, a
   horde body 150 -- 2,695 with everyone standing, before a box -- and the double was LAST. With company in the shot
   it was not drawn, and it fought. (Found late: the double's pose and its flags were right, and it was missing from
   every render with another body in it.) The double is a body of the ELITE's size now, with every clip of the kit
   in a bank of its own, drawn dark; the cart COUNTS the faces it lists (the rows, his own, each body) and lists a
   body only where the lens can have it and the store has room -- the double first; and what is not listed neither
   begins a string nor lands one. The same tape's route on P73: 2,015 faces at the most; no string begun undrawn.
2. ITS PLACE. The double's place in the fan was dead ahead of him: behind his own back from the lens, in his own
   skin. Nobody's place is on that line: the double and the elite a tenth of a turn to either side, the others wider.
3. THE LENS'S ARM. A body within 1.3 of the lens is not drawn (it would blot out the shot) -- for 606 of his 10,520
   frames one was, and it told and struck from there (6 of the 73 blows). It is not SEEN, as above.

THE WEIGHT. Until now a body struck kept its guard and leaned; he, struck, went red. tools/tnd_react.py bakes four
clips on the archive's rig -- struck HIGH (the chin taken back, the chest opened, a foot gone back), struck LOW
(folded over it), DOWN (back, into the air, flat), UP (sat, crouched, his guard) -- and carries them to the three
smaller bodies: each of a body's corners follows the nearest corner of the full one, each face takes the nearest
face's shade (half a centimetre off, measured on the walk both already had).
- A BLOW OF THEIRS ON HIM: the move's own hitstop (fourteen frames at most) and the lens shaken by it; he is SENT
  the way it faces by the move's own knock (a jab an eighth of a unit, the haymaker a unit and a half); the burst
  and the blow's sound at his chest; by the move he is struck high or low -- sixteen frames in that clip -- or TAKEN
  OFF HIS FEET: the haymaker puts him on his back, a second down and up, and nothing lands on him meanwhile. An
  uppercut lifts him.
- A BLOW OF HIS ON THEM: struck, a body is in its own bank's clip (high if his fist met its head, else low) for as
  long as it is held; taken to nothing it falls in the fall's clip, lies, and gets up in the getting-up's (it was
  tipped over, stiff); and the blow that takes the last of it stops the world six frames more.

MEASURED, a minute of everything at random with the fight on: 42,205 instructions a frame at the worst (of 65,536);
on the simulated silicon 50% of the frame at the median, 74% at the peak. The program is 29,045 words (about 220
from its limit), data memory 58 free: the next thing in this room needs room made first.

Tests 16 (tests/test_tnd_yard.py). Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical. (The lab and the
reactor have the same store and the same single double; with one body standing they are inside it.)

## P74: the lock takes what is drawn; the spot is a tap of its own; the fight has turns (2026-11-24)

The player, ten minutes of P73 on glass: "plugged. its starting to be fun. the targeting needs work. one thing i
noticed is that the up down targeting leaks into the other moves, it shouldnt. look at how i played and make as
many improvements as you can".

HIS TAPE (38,442 frames: the tank 39%, the boxer 49%, the run 12%; R held 53%; down 10 times). 149 blows landed on
him: the double 94, the elite 33, the common 15, the horde's four 7. He took 1,967 off them -- 1,671 of it with the
gun up -- and put bodies down 232 times; 63% of his jabs landed.

THE LOCK. Locked on a body for 17,501 frames: it was NOT DRAWN 28% of them -- on one of the horde, 75% (35 seconds
squared up to a body he could not see; a drawn one stood within six units in 713 of 996 of those frames sampled).
The chosen body changed 287 times, 232 of them with neither Left nor Right down (the one he had went down and the
nearest was taken anew), and his body swung more than 53 degrees after 40. R TAKES, AND STEPS TO, ONLY A BODY THE
FRAME DREW: what it squares him to is in the shot.

THE SPOT. It stepped 22 times; 17 of them were Up or Down HELD for something else (10 to 95 frames, a face button
inside ten frames either side -- a blow's way, the gun, a dodge), all in the tank with R held, and it sat at HIGH
for 9,548 of his locked frames against 6,342 at the middle. THE SPOT STEPS ON A TAP OF ITS OWN: Up or Down pressed
with no face button down or let go inside ten frames, and let go inside fourteen frames with none pressed
meanwhile. Held, or with a button, it is that move's.

THE FIGHT HAS TURNS. The horde's places were at his sides and behind -- out of the shot, where since P73 a body
neither is drawn nor begins -- so the four of them were awake two thirds of the time, drawn a fifth of that, and
landed 7 blows. Now: two SIDES before him, a tenth of a turn either way, in reach. A body ENGAGES -- takes a free
side -- on its own frame of an eight-frame round if it is ready and drawn; engaged it closes, comes round to its
side (a sixteenth of a turn off his line before it may tell), tells and throws its string; the string done, or it
struck, or two and a half seconds with no blow begun, it gives the side up. The others WAIT in an arc three units
before him, each on its own bearing, as many as the frame's store can draw; past that, out wide behind the shot
until there is room. A minute among the horde and the double: every one of them lands, two engaged at the most,
the horde drawn half the time it is awake.

MEASURED, a minute of everything at random: 48,018 instructions a frame at the worst (of 65,536); on the simulated
silicon 50% of the frame at the median, 80% at the peak (it was 74%: more bodies are in the shot). The program is
29,167 words -- about 100 from its limit -- and data memory has 37 free.

Seen on the tape and NOT changed: the gun is 85% of what he takes off them (a round is one, of bodies of three to
twelve, six rounds, 0.4 seconds to load); bodies get up whole after two and a half seconds, for ever.

Tests 19 (tests/test_tnd_yard.py). Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P75: the lock, again; A in the tank; the slide is a blow (2026-11-24)

The player, two more sessions (17 minutes of P73, 11 of P74): "look at both, targeting still needs work. also slide
wilhile running should do damage, and down a in the tank should be back dodge, just a in tank is quick turn".

HIS TAPE OF P74 (39,488 frames; the tank 67%, the boxer 26%; down 7 times; 100 blows on him: the double 50, the
elite 46, the common 4, the horde none). What P74 changed held: locked on a body, it was undrawn 0% of the time
(17% on the second P73 session); the spot changed twice (58). What the tape shows of the lock now:
- STEPS WENT THE WRONG WAY: of 11 steps with Left or Right, 6 went to the side he pressed. The order is round the
  ring, so the next one left of the leftmost is the rightmost. A step takes the next one on THAT side, half a turn
  at most; none there: it stays.
- HE STOOD, HOLDING THE PAD: R alone in the tank plants him (P37, his own rule: the pad is only the choosing) -- and
  with it held he held Up for 1,109 frames and Down for 925 of 9,111, 38 and 22 presses, and stood; 14 of the 100
  blows landed on him so. In the yard, locked, UP AND DOWN WALK him to it and from it (his steering is on it); Left
  and Right still step; he does not turn. (MY READING of the tape, against his rule of P37: to be judged on glass.)
- R took the nearest drawn body 81 times in 84, and one that was at him 58 times against 11: left as it is.

A IN THE TANK: alone, the quick turn (it was Down with A); with Down, the dodge back (it was A alone); with a side,
the dodge that way, as ever. Locked, A alone is still the dodge back: his facing is the lock's. (On the tape he
pressed A alone 70 times and Down with A 38.)

THE SLIDE IS A BLOW (Y in the run): through its eighteen frames his feet take a body's legs -- the hook's two off
it, held twice as long -- and the body is down, as the dive's is.

A FIGHT CALLS THE OTHERS: in eleven minutes in the ring the range's five, twelve units off, slept and landed
nothing. With anybody awake, he wakes what is within sixteen units. (From where he begins nobody is awake.)

Room made: the long jump's charge and the locked run's shot and superman punch are not built into the yard (its run
has no lock and no long jump). The program is 29,095 words, 170 from its limit; data memory 35 free.

MEASURED, a minute of everything at random: 43,855 instructions a frame at the worst; on the simulated silicon 51%
of the frame at the median, 80% at the 99th percentile, 87% AT THE PEAK -- under the gate of 90%, by less than it
was (80% at P74): more bodies come to the fight.

Tests 23. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical. (A in the tank and the slide's blow are the
yard's only: the other layers keep Down+A for the quick turn until he says.)

## P76: where it is struck stays with it; the spot on the press; into the run and out (2026-11-24)

The player, after P75's push: "geneally it feeling good you have a good intuition, it should just be smoother and
cool between modes of play / tank targeting gives the head shot body shot leg shot choice. thats important. those
should have specfic effects on the enemy".

TWO OF MY READINGS TAKEN BACK. Both were mine, against his design, and his tapes had already said so:
- P74 made the spot "a tap of its own" (Up or Down pressed and let go inside a quarter second). On that build he
  chose the spot nine times, each a HOLD (median 46 frames), and it answered none; where it stepped on the press
  (P73) it answered 17 of 25. Now Up or Down with R held steps the spot AT ONCE, tapped or held. What P74 was for
  ("the up down targeting leaks into the other moves") is kept another way: a blow's button within ten frames
  after a step takes the step back, and within ten frames before it, the step is not taken.
- P75 let Up and Down walk him while locked. Locked, he is PLANTED again (P37, his rule): the pad is the choosing.
  Left and Right still step to the side pressed.

WHERE IT IS STRUCK STAYS WITH IT (a fist or a round, the spot he chose):
- the HEAD: DAZED, 200 frames. It slips nothing, its tell is twice as long, and it sways. (A round there still
  takes two; a fist half again.)
- the BODY: WINDED. Its string is lost with its side, as any blow does, and it begins no other for 100 frames.
- the LEGS: HOBBLED, 260 frames at half its pace. Struck in the legs again while it is: DOWN.
Read on the elite with rounds: head 8 -> 6 and dazed; body 8 -> 7 and its wait at 87 thirty frames on; legs 8 -> 7,
hobbled, and the second there puts it down. (MY CHOICE of the three effects and their lengths: to be judged on
glass. What a hobbled or winded body LOOKS like is only its pace and its waiting; the dazed one sways.)

INTO THE RUN AND OUT OF IT. The camera was already eased between styles (0.12 a frame at most); the body was not:
standing to full stride in one frame, and back. Into the run he DROPS AND DRIVES, the landing's crouch rising into
the stride over five frames; out of it at pace he BRAKES, eight frames down through the crouch and up, and then
stands. Not in the air, struck, or flipping. (MY READING of "smoother and cool between modes of play": the tank and
the boxer change by a guard only and were left.)

A FAULT OF MINE ON THE WAY: the new cell for which of the two it is was named YMK, the name of the bodies' marks
table. The generator is one scope; every body walked "home" to an address read out of the wrong cell, and five
tests failed that this round had not touched. Found by building halves: the fight routine old and the rest new.

Room made: the streak's digits and the superman punch's stop are not built into the yard. The program is 29,211
words, 55 from its limit; data memory 11 free. THE YARD IS FULL: the next thing in needs something out.

MEASURED, a minute of everything at random on the simulated silicon: 52% of the frame at the median, 81% at the
99th percentile, 88.0% AT THE PEAK (87.3% at P75) -- under the gate of 90% by two points, and no frame over.

Tests 26. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P77: the yard does not carry what it cannot reach (2026-11-24)

No change to play. From the probe in `experiments/streams/`: 35% of the yard's program never ran in the player's
sixteen minutes, and by its labels most of that was the city's.

- `forge.reach` (new): a program without the instructions no path from word 0 reaches. Every jump and call names
  its label, so the walk is exact. It settles a branch one way only where the test is a constant it can see on the
  straight line it stands on (a cell stored from a constant and read straight back).
- THE HALL IS OFF THE CITY'S MAP (checked at the build over the hall and two units past its walls). For him, in the
  yard's game, "which node" is -1: the generator says so in one store, and `reach` drops every "on the map" behind
  it -- the city's walk and its pieces' listing, the dusk, the pointer, the hordes' "here".
- Two cuts by hand, each with its reason at the place: the leash's three bodies (off the map each goes straight to
  its end), and the placing of demons sent (nothing the yard can reach stores SPN; the build checks that).

THE PROGRAM: 29,211 words -> 25,351; 3,915 from its limit where there were 55.

DATA MEMORY: the yard's cart shows the city only at its title, from the first plaza; a piece is listed within two
streets of where he stands. Of the city's nine kinds of piece, two (the crossing and the open square's, 1,520
words) lie further than three streets from that plaza with every gate open: the yard carries them as nothing.
11 words free -> 1,521 (without the song).

PROVED THE SAME: the program's cuts, data memory identical every frame against P76 on a minute at random (3,860
frames) and on the presses of his 16.5-minute session (59,381 frames; about 120 instructions a frame fewer). The
pieces' cut moves data, so: the picture identical on the title's sixty frames and every twenty-fifth after (212
pictures), and every named cell the same or moved by exactly the 1,510 words. Tests 26, and 8 for the pass.
Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P78: far off, a body is its far body (2026-11-24)

The player: "see if it makes sense to have the more detailed fighters rendered when in the foreground, have the less
detailed models in the distance. ivestigate first" -- and, the measurements read (`experiments/streams/`), "go ahead".

WHAT WAS MEASURED: a body costs the frame by its FACES (about 73 clocks each), the same at twenty units as at two;
and the frame's store of 2,048 faces, not the clock, is what kept bodies out of the fight (his session of P75: 2,018
at the most, and a body with no room waits out wide, behind the shot).

SO: the elite, the common and the double each have a second bank -- their whole kit, pose for pose, on the horde's
150-face body. Past 2.9 units from HIM a body is listed as its far body; inside 2.6, as its own (369, 252). Those at
his sides, fighting him, stand at 1.35 and are whole; those that wait their turn in the arc, at 3, are far bodies,
and a waiting body asks the store for 150 faces, not its own. The double keeps its dark.
(MY FIRST RULE was by the lens, seven units out: in a fight it changed nothing -- everyone in a fight is within
seven of the lens. Kept as the rejection it is.)

IN A FIGHT (a minute among all seven, from three places, he standing): bodies in the shot 3.8-4.2 -> 4.9-5.2 at
the mean; the horde, drawn while awake, 25-43% of the time -> 53-59%.

ON THE SIMULATED SILICON, a minute of everything at random: 51% at the median, 66% at the 99th percentile, 70.3% AT
THE PEAK (P76: 52%, 81%, 88.0%). The two minutes are not the same play -- the same presses meet different fights --
so the peak's fall is observed, not yet attributed.

Cost: 292 words of the program (25,676; 3,590 from its limit), 22 of data memory, three banks in the cart.
Tests 29. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical. TO BE JUDGED ON GLASS: whether a body
changing at 2.6-2.9 units is seen to change.

## P79: a tap is the spot, a hold is the walk; the gun is not in the way (2026-11-24)

The player, two minutes of P78: "I liked the walking back and forward when gun aiming in tank instead of planted.
also the I try to select the target spot with up down but nothing happens then it gets locked in low. I should be
able to see the laser move to the target."

HIS TAPE (7,789 frames; locked 3,495; the gun out for 1,471 of them): 46 presses of Up or Down with R held; the spot
answered 3. It went low at frame 1,896 and stayed there for the rest: 2,389 locked frames low, 46 high. 27 of the 46
had the GUN's button down or inside twelve frames -- P76's "a face button inside ten frames is a move's" counted the
gun as a move, and he aims with it held. In the tank his presses fall in two heaps: 8 to 22 frames, and 29 to 159.
(In the boxer, L held, the pad was never the choosing: P37, "R alone".)

SO (MY READING of the two wants together): with R held in the tank, Up or Down HELD walks him to it and from it, as
P75 had it; Up or Down TAPPED -- let go inside 22 frames -- steps the spot as it is let go. The gun's button does
not stand in the way; a fist's or the dodge's does. The laser already goes at the spot's height: it moves when the
spot does. (A tap also walks him its few frames. P76's planting was mine to take back, and is.)

Tests 29. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P80: R alone is the targeting -- planted, and on the press (2026-11-24)

The player, half a minute of P79: "ohhhh now I remember yes it needs to be planted because that mode is essentially
the smart targeting system. picking which enemy and which location to hit" -- and "should be immediate because the
player will do quick choices."

R HELD ALONE IS THE TARGETING (P37, his): he is planted; Left and Right pick the enemy; Up and Down pick the spot ON
THE PRESS, tapped or held, as fast as he presses. With any button down the pad is that button's; a fist's or the
dodge's button inside six frames of a step, the pad still held, takes the step back (P74's leak). P79's tap-and-walk
is withdrawn.

MY READING, of what he liked in P79 ("the walking back and forward when gun aiming"): with the GUN'S button held the
pad is not the targeting's -- Up and Down walk him to it and from it, and the spot stays. To be judged on glass.

Tests 29. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P81: the gun's slowed time is the targeting too (2026-11-24)

The player, of P80: "ah i understand what you did. the up and down is only if the gun is pulled out in slow mo, and
slowmo it should be planted too." (And P37, his: "same in slow motion".)

P80's walk with the gun's button held was MY READING and is withdrawn: with R held he is planted, the gun out or
not. The gun's button is not "another move": with it held, in its slowed time, Up and Down step the spot on the
press and the laser goes there. A fist's or the dodge's button still keeps the pad for itself.

Tests 29. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P82: out of slowed time, the spot is the body's again (2026-11-24)

The player, three minutes of P81: "ok. i think is almost there. it should always return to the neutral position
after slow mo is exited, i think that would also solve the problem of the players torso being locked into the angle
after your end firing".

The frame slowed time ends, the spot is the body's. His waist bends to the spot while he is locked (the gun's slope
to it; his fists' own bend for it): the spot left low, the gun put away, he stayed bent -- that was the angle. It
comes up with the spot. Chosen with R alone in time as it runs, the spot stays where it is put, as before.
(Slowed time is any of the four held: a fist held and let go returns it too.)

Tests 30. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P83: the run's laser is his heading's; a blow strikes every body it meets (2026-11-24)

The player: "The next thing is making aure the laser is fixed when slow mo shooting in running. and make the slide
hurt all the contacts. I think that would be a cool added layer throughout, the attacks have an area of effect."

THE LASER IN THE RUN. On his tape of P78 (1,185 frames in the run, slowed, the gun out) and scripted: with Left held
to steer, the laser stood an eighth of a turn off his heading for the whole turn -- it went the PAD's way, which in
the tank is where the gun snaps. In the run the pad steers him: the laser is his heading's (within 5 of 1,024 as he
turns), and the round goes where it points. (MY READING of "fixed": fixed to where he faces.)

A BLOW STRIKES EVERY BODY IT MEETS, each once: the slide and the dive through all their frames, a fist through its
swing. It was the first body, and the blow was spent. What "meets" is, is what it was -- within three quarters of a
unit of the fist, each way; the round is still one body's. (How WIDE an attack's area should be is his to say.)

Tests 33. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P84: in the run's air -- the lance, the dive down, the gun on where he lands (2026-11-25)

The player, 46.8 minutes of P83 (the tape full, the session running on): "really take a look at this one / the
controls are really fun, see where theirs no actions and i tried to play ... i think down in running should for
shooting from high up, i was finding this thing where jumping and firing could be linked to where you'll be landing.
that way you can jump and hit some one from above. the tackle makes it feal like football americano, and we can make
it do a prowler like dive with a that acts differently depending if it grounded, jump or flip. and the same for the
slide, or make it go down like the body is a a lance of longinus, the gun is like small ones." And, the reading put
to him: "i agree with all this. the lance is a land because it wants to get to land quick thats why its more
associated with a slide. The area of effect can be a hand spring on first jump".

HIS TAPE (168,483 frames: the run 64%, the tank 24%, the boxer 11%; 530 dives, 241 slides, 819 bodies put down,
96 blows on him, down 6 times; the run slowed 81% of its time, in the air 26%, in a flip 11%):
- WHERE NOTHING CAME OF A PRESS: of 5,117 presses of A, B, X, Y, 461 began nothing inside fourteen frames. In the
  run, X in the air 183 times and 148 nothing; X in a flip 63 and 40; Y in the air 50 and 40; Y in a flip 42 and 23;
  Y again while sliding 44 and 39. The gun's button answered all 1,971 times; the tank and the boxer are near clean.
- THE GUN IN THE RUN: 76% of its presses under eight frames, 20% eight to twenty, 4% longer. A round fired on the
  ground was followed by a body losing something 78% of the time (1,368 rounds); fired in the air, 12% (214) -- it
  leaves level, over their heads. B with Down held, 108 times.
- A blow took two or more bodies in one frame 102 times, three or more 8 (P83's rule).

WHAT IS BUILT (the yard):
- THE LANCE, Y in the air: his body the slide's, feet first, thrown DOWN at once (0.32 a frame); as it meets the
  ground it is the slide, through everything in its way. (Y waits for the ground; it was spent in the air.)
- THE DIVE DOWN, X in the air: onto where he lands, and what stands within its reach there is struck and down.
  From his FIRST JUMP it is the HANDSPRING: a unit and a half round his hands, and they throw him up again, the flip
  still his. From a FLIP it is the SLAM: 2.2 round him, and he comes down into the roll. The world stops for the
  blow's first body only (three under a handspring held him in the air most of a second).
- THE GUN ON WHERE HE LANDS, Down held in the air: the laser goes down to the spot his landing mark shows, and the
  round with it, to a standing body's middle there. Scripted, a body before him, a jump and a flip, a round at the
  top: level, 0 of 12 took anything off it; with Down held, 12 of 12.
MY CHOICES, his to judge: the speeds and the two reaches; that the handspring rises in the jump's own poses (a
handspring's own is not baked); that Down's aim needs the landing mark shown.

NOT DONE: the joins between his halves in the air (the six moments rendered were from the game's own lens, steeply
down, his upper half off the top of the glass: they have to be drawn from the side first); the mirrored double in
slowed time; Y while already sliding.

Tests 36 (and the park's 23 unchanged). Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical. Not profiled on
the silicon since P78.

## P85: his chest sits on his hips (2026-11-25)

The player: "the meshes and poses need work blending between peices where you do things like jump and act" -- and,
P84 on the card, "then do the pose joins."

SEEN, drawn from the side (the game's own lens looks steeply down in the air and cuts his upper half off): his body
is two halves with a pose each, and with the gun out his upper half is a STANDING pose's over whatever his legs do.
Its waist is where a standing man's is (1.02 up, 0.13 ahead); a stride's is 0.16 behind that, a landing's crouch
0.30 below it, the dive's 0.42. His chest floated off his hips -- over a landing by a third of a unit -- and the
gun and the laser with it.

SO: every pose says where ITS waist is -- the middle of the 38 vertices the halves share: how high, how far ahead,
a byte each in 48ths (383 words) -- and an upper half over other legs is moved to theirs; his hand, the gun and
the laser go with it. With one pose in both halves nothing moves.

NOT DONE: the upper half stays UPRIGHT (the gun level) over legs that lean -- moved, not turned. In the fired
poses (the gun's clip, five frames on) the gun sits a fifth of a unit over his hands: there before this, seen now.
A blow thrown in the air still brings its own standing legs.

Tests 37. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical. The program 26,060 words (3,206 from its
limit); data memory 1,107 free.

## P86: the chest leans with the legs; the handspring comes over; a wall gives his flip back (2026-11-25)

The player: "The walls should be treated like floors, two jumps at max then gravity changes back to the floor. think
of those as mirrors." (Asked which of three readings -- a wall re-arms his jumps; he sticks and stands on it; he runs
on it -- he chose the first.) "the running gun waist needs fixing too," "and the running jump dive pose is a hand
spring then jump if strung together like id to do front hand springing."

THE RUNNING GUN'S WAIST. P85 moved his chest to his legs' waist and left it UPRIGHT -- and the gun's own pose leans
BACK a twentieth of a turn where a stride leans FORWARD a twelfth. Every pose now says its own chest's lean too (the
line from its waist to its chest and head; the waist's ring itself is no measure -- the thighs pull it sixty degrees
a stride), a third byte; an upper half over other legs is turned A THIRD of the way to theirs (the whole of it would
put the gun on the floor). The gun lies along his AIM and is not turned with it.
AND HIS HAND LEANS WITH HIM: his whole body leans into his pace about his feet (P15, eight degrees at the run's) and
his hand was reckoned upright, so the gun rode a fifteenth of a unit over his fists and as far behind them -- in the
run, and in the fired poses P85 reported. Drawn from the side, the gun is in his fists now.

THE HANDSPRING COMES OVER: off his hands he is the forward flip's second half, fourteen frames, hands down to feet
under him; and X again in that air is the next one -- dive, hands, over, dive -- the flip never spent.

A WALL GIVES HIS FLIP BACK: a kick off a wall is a landing on it -- the flip is his again once the kick's throw is
done, and the dive and the lance -- and the kick is the jump from it, mirrored, as it was. Twice an air (it was six,
for the park's chimneys); then the walls give nothing and he comes down to the floor. What a kick needs is unchanged
(his way INTO the wall; a face across his way is the kick straight up).

Tests 40. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical. Data memory 720 words free without the song
(the waists' table is a word a pose now).

## P87: on the stride with the gun he is one body; the wall, straight up then the return flip (2026-11-25)

The player, eight minutes of P86: "running gunning still needs mesh work, and the wall jump needs fixing, any of the
directions of wall, jump onto wall is verticle with a second clickable being the returned back flip. flip onto wall
is return flip."

RUNNING WITH THE GUN. Drawn from behind, the front quarter and above (P85 and P86 looked from the side only): the
gun's upper half is a BLADED stance's -- its shoulders and its waist's ring turned a ninth of a turn off the hips of
a man running straight -- so from behind his chest stood narrow and to one side of his hips, and the ring flared
out of them. Moving and leaning it cannot mend a turn; turning it would take the gun off his line. The cart already
holds the cure: the run's OWN gun poses (P36's, for the locked run the yard has not) -- sixteen, one baked body, the
gun out in one hand over its own stride. On the stride with the gun out he is THAT, both halves; his hand is found
in it and the gun and the laser are there. In the air he is two halves still, joined (P85, P86).
(MY CHOICE, his to judge: it is a one-handed sprint where the ready pose was two-handed.)

THE WALL: any wall he has touched, whichever way it faces and however he came at it (P59's "only going into it",
P61's "a face across his way" and P62's pad are the park's, not the yard's). From a JUMP, A is the kick STRAIGHT UP
it, and the wall is his for forty frames more, where A again is the RETURN FLIP -- thrown back off it, his heading
mirrored in it, the flip's rise and tuck. From a FLIP, A is the return flip at once. Two an air; the return flip is
his flip, spent (P86 gave it back: withdrawn). (MINE: the return flip is the wall kick's own throw as it was; a
true BACK flip, facing the wall still, is not baked for every way a wall can face.)

Tests 41. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P88: the gun's chest has its own belly; the one-handed sprint withdrawn (2026-11-25)

The player, a minute and a half of P87: "the wall jumping is good now. the running gunning, looked better before, and
now there's a floating gun, the only thing tha was wrong before was some floating triangles around the waist."

P87's one-handed body on the stride is WITHDRAWN (my choice, turned down: recorded): he is two halves again, joined
as in P85 and P86.

THE FLOATING TRIANGLES, drawn close from behind, the side and the front quarter. The halves are cut at 1.0 -- over
his BELLY, a fifth of a unit above his trousers -- and that band of belly is the LEGS' half's, posed with the
stride's own leaning, turning chest. Under the gun's chest it reaches up for a chest that is not there and stands in
the air beside the one that is, with air through the waist behind it. TRIED AND TURNED DOWN on the way: both rings
tucked in (a hollow waist); a black band round the join (the join is at his chest's foot, not his belt: it covered
his chest). WHAT IS BUILT, where the halves are in different poses:
- the gun's upper half has its OWN belly: a second copy of the gun's poses with the ring of 38 let straight down a
  fifth of a unit, to the trousers;
- the legs' band is drawn IN under it: a second copy of every pose's lower vertices with the ring at a third of its
  width and a sixth down, inside that belly.
Whole poses are as they were. The cart: 51 poses and 766 lower halves more.

Tests 41. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P89: his mesh is his own -- P88 withdrawn (2026-11-25)

The player, of P88: "this has corrputed the shooting mesh and poses. the orginal mesh of the player must stay intact."

P88's second copies -- the gun's poses with their ring let down, every pose's legs with their band drawn in -- are
OUT of the cart, and with them everything that drew from them. His body is the baked one, every vertex where the
archive put it, in every pose. What stands: P85 and P86 (an upper half over other legs is MOVED to their waist and
turned a third of the way to their lean; his hand, the gun and the laser with it -- no vertex changed) and P87's
wall. The floating triangles at his waist with the gun out on the run are as they were at P86: not mended.

A RULE, his: the player's mesh is not altered. What may be done to it is what the machine does to a whole half --
where it is put and how it is turned -- and what is baked on the archive's own rig.

Tests 40. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P90: the chest closes on the hips; the laser through a flip; the run's air aims at the landing (2026-11-25)

The player, seven minutes of P89: "all we need is to blend them a bit better, the running legs should be the same,
and the gun holding from when strationary torso (no legs), maybe with a slighty boundce to match tehh runnig. and
also look into the slow mo boxing jump/flips and actions. flip shooting making sure to follow the target with laser
and on running the jump flip shooting lazer should be on the jump landing."

THE BLEND (no vertex changed: his rule). The gun's standing torso over the run's legs, as it is. Four settings of how
that half is PUT, drawn close from behind, the side and the front quarter: as P86; sunk; sunk with half the legs'
lean; two thirds of it (the gun at his hip). Kept: P86's third of the lean, the half SUNK a twentieth of a unit into
the legs' waist and a thirtieth ahead -- the two bands overlap where they stood apart, and most of the floating
triangles are inside his chest. (His torso already rises and falls with the stride: it rides the legs' own waist,
three hundredths either way. A bounce of its own is not added.) Not all gone: one of the legs' belly band still
shows at his side from the front quarter.

HIS TAPE (25,544 frames), the gun by where he was:
  the boxer, on the ground 87 rounds, a body lost something after 93%; in a flip 48 rounds, 96% (locked: the round
  goes at what he has chosen); the run, on the ground 101 and 69%; in a jump 7 and 29%; in a flip 15 and 13%.
  The gun's button held in a flip: the boxer 661 frames, the run 189 -- THE LASER ON IN NONE OF THEM.
THE LASER THROUGH A FLIP: in a flip his upper half is the flip's and his hand is not "out", which is what switched
the laser on. With the gun's button held it stays, from his hand's height; and locked, its way is the way TO what he
has chosen (his body's own heading, mid-flip, is anywhere).
THE RUN'S AIR AIMS AT THE LANDING, jump or flip, with no Down asked (P84 asked it; 7 of his next 47 rounds from the
air had it).

Tests 41. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P91: with the gun on the run he is one body, baked (2026-11-25)

The player: "work heavily on the look, make sure it all looks like a single mesh, with poses and transitions that
all make sense and look tactical and stylish." (And before it: "the running legs should be the same, and the gun
holding from when strationary torso"; "the orginal mesh of the player must stay intact".)

WHY PUTTING A HALF COULD NOT DO IT (P85 to P90): his body was two halves in two poses -- the gun's standing chest set
on the stride's hips -- and the two poses do not share a waist. So it is baked as what it is: ONE skinned body on the
archive's own rig (`tools/tnd_gunbody.py` -> assets/tnd/gunbody.npz), as `tools/tnd_acro.py` bakes the run it
stands on. No vertex of his mesh is moved by hand; these are poses the rig makes.
- THE LEGS are the park's own clips bone for bone -- the stride, the leap on either leg, the landing: their shins
  and feet are the park's to the last place (checked: 0.0000 off, every frame).
- THE TRUNK is a shooter's over them: half the clip's own lean, the head level.
- THE ARMS are the archive's own two-handed hold (its `_repose_aim` reach), at four heights of the draw: low
  ready, coming up, nearly out, locked out. The hold is taken at places before HIM, not on his chest: the gun stays
  where it is (a hundredth of a unit, stride to stride) while the legs run under it. Moving, the lock-out is a
  hand's breadth short of the standing one: his shoulders cannot make the standing reach over a stride.
In the cart 200 poses more (64, 52, 52, 32). Where his upper half would have been made the gun's over those legs he
is that body instead, at the height the gun's frame is (held ready, the second; through a shot, locked out; then
down through the third to the ready). Both halves one pose: nothing joined, his waist not broken for a round's kick
(the kick is the gun's, in his hands). The dive is a whole body's: the gun's chest is not put over it.

MEASURED, the presses of his seven minutes of P89 on this build: his halves in different poses on 43 frames of
25,544 (0.2%; it was 3,370, 13.2%) -- the tank's walk, the boxer's landing and strafe jump, the air: joined as P85,
P86, P90; one baked body on 8,153 frames (31.9%).

Tests 42. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical. Data memory 487 words free.

## P92: the yard's own moves, posed; the transitions measured (2026-11-25)

The same asking as P91: "poses and transitions that all make sense and look tactical and stylish."

MEASURED FIRST -- how far his drawn body moves from one frame to the next (the rms of its 459 vertices), over the
presses of his seven minutes of P89 on P91: his pose changed on 8,588 frames; median 0.045 of a unit, the 99th
percentile 0.274, and 137 changes over 0.22 -- by which clips: standing into the run and out of it (the landing's
crouch, borrowed by P76: 0.40 and 0.45 in a frame), the hold to the stride's arms as the gun went (0.26, twelve
times), the stride into a leap, a leap or the dive into the roll, the reactions' own frames.

FOUR MOVES HAD NO POSE OF THEIR OWN and borrowed another's. Baked on the archive's rig from the pose words the
park's clips use (`tools/tnd_moves.py` -> assets/tnd/moves.npz):
- INTO THE RUN (6): from his guard, the weight dropped forward and driven, to the stride's first pose.
- OUT OF IT (8, and 8 from the stride's other half): the lead foot planted, sat back against his pace, up into
  the guard. Both begin as the STRIDE begins and ends -- P76 began them as the style changed, and he changes it
  standing: the drive was played on the spot and the stride then began from his guard in a frame, six times in
  seven minutes. The stride begins at its own first pose.
- THE HANDSPRING'S SECOND HALF (14): on his hands, inverted, the legs over, the back arched, the feet under him.
  It turns him itself. (It was the forward tuck easing out, unturned.)
- THE LANCE (4): a straight line feet first, toes pointed, the arms long behind his head. (It was the slide's
  body, lying down, falling.) And it comes down into the slide after a flip too: the flip is over as it lands.
THE GUN COMES TO HAND AND GOES in a pose of its own: the hold HALF-TAKEN, a fifth height of the one body (250
poses now) -- the first frame of the draw, and two frames after the gun is gone.

AFTER: 113 changes over 0.22 (137); the 99th percentile 0.242 (0.274). What is left at the top is motion, not a
join: the roll's own frames, the reactions', a leap or the dive into the roll.

TWO FAULTS OF MINE ON THE WAY, both found by a test that was not about them:
- the one body's hand entries were put after the gun's in the table, and the stride's first four poses are numbered
  just past the gun's clips: a gun floated beside him for a quarter of every stride (P91, as committed; never on
  the card). Only the one body reads those entries now.
- a label marked twice in one block of mine (`_a0`): the assembler takes it without a word and a jump went into
  the middle of the other, with nothing on the stack. THE GENERATOR NOW REFUSES a label marked twice, in every
  program of every layer (none had one).

Tests 42. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical. Data memory 393 words free.

## P93: aiming up or down he hinges at the hips, one body (2026-11-25)

The same asking ("make sure it all looks like a single mesh"). MEASURED, the presses of two of his sessions on P92
(53,687 frames): his upper half turned at the waist on 45% of the tank's frames and 31% of the boxer's -- the gun's
bend to the spot he has chosen -- by over ten degrees on 23% of the tank's, by 53 degrees at the most. The gun's
clip is a whole body; that turn was the one place a whole pose still broke in two.

A man aiming up or down hinges at his HIPS. Each frame of the gun's two clips is baked six times more
(`tools/tnd_gunbody.py`), leant there the archive's own way -- its `_lean_forward`: posed points turned as one
block about the pelvis, as its haymaker leans -- with his arms in the block (at these angles they go with his
shoulders): everything that is not a leg, 15, 30 and 45 degrees up and down, the faces shaded again where they now
face. The legs are the clip's own to the last place. 306 poses.
In the cart he is the one nearest his bend; what is left over (seven and a half degrees at the most, inside 45) is
still turned at the waist. His hand is reckoned as that body's is -- the clip's own hand, turned about the pelvis
by the lean, then about the waist by what is left: to a thousandth of a unit of the baked hand -- and the gun lies
along the whole aim.

The table of waists stops before the whole bodies (no half of theirs is ever set against another pose's): data
memory 625 words free without the song. The cart's poses: 1,362.

Tests 43. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P95: the lens does not go into him (2026-11-25)

The player, of the lens on his own sessions (found while costing P94): "this is a bug with the camera going into
the player as he gets close to walls".

OBSERVED: the yard's lens is DRAWN IN (P56, P64) along the line from his head to where it would be, to the last
eighth clear of every structure; with his back to a structure's side none is clear and it was put "over his own
head" -- four tenths over the point that line starts from, which is inside his skull. The glass was the inside of
his head, or one face of the wall. Within 0.3 of him 5 times in his 7.1 minutes on P89 and 15 times in his 12.7 on
P84, for up to 144 frames. A low step behind him did it too (the first eighth is under a 0.8 step's clearance,
and the search stopped there though the lens's own place was clear). And in the boxer, from over him, the look
"at him" had no way to turn: it came out 513 of the turn's 1,024 whatever he faced.

NOW (the yard only): nearer than a unit and four tenths to him the lens goes UP instead of in -- R - h^2/R over
its line, 1.4 over his head at his own place -- and from there looks DOWN at him: the pitch whose line meets his
chest, less 25 degrees, so he is low in the glass and what is before him is seen. The eighths are tried where the
lens will then be, so it is not drawn in for what it can see over. Within half a unit of his place the boxer's
lens keeps the way it last looked at him.

On his 7.1 minutes of P89, the change put on that commit: the lens's nearest to his head 1.02 (it was 0.06);
never under 1.0 (it was on 535 frames). Before the two sessions part the lens is as it was on 87% of frames.
THEY DO PART, at frame 7,055: in the boxer his steps go by the lens's yaw, and that yaw was the 513. It is a
change to how he moves in that one place, and it is the bug's.
The going up and looking down is a reading: he named the fault, not the cure.

Tests 43. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical. Program 26,574 words.

## P96: a blow in the boxer's flip does not stop the flip (2026-11-25)

The player (P95 on glass: "all looks good played both"): "the last thing that's very still a big glitchy bug is
doing multple jab, special and gun inputs during a boxer flip jump. when i do it it lags and moves the player like
a hovering attack. It's fun but just looks strange maybe we can make it less floaty and make it some sort of kick
attacks. for the gun multiple shots just lags the filp."

OBSERVED (his tape of TND RANK, 20261125-105008): a swing owns the body, and the flip's clock is the free body's
-- so a blow or a shot begun in a flip stopped the flip where it was. From frame 700 he fell to the floor in one
pose of a back flip and stayed in it 127 frames while he fired and jabbed, each jab's lunge sliding him on: 21
units across the room. Flips with a strike button in them ran to 187 frames; without, 14 to 48.

NOW (the yard, the boxer's flip): A SHOT leaves at once, the way his body faces, and the flip goes on. A FIST is
the flip's own KICK -- no swing, no lunge: for eight frames his turning body strikes every body within a unit and
a quarter of him, once each, with the worth of the move he pressed; one kick at a time, and its hitstop three
frames at the most. Scripted, buttons mashed through a flip: the flip 27 frames with shots (as with none), 33
with jabs or specials, every pose of it shown.
A reading: the kick has no clip of its own -- it is the flip's legs. He asked for "some sort of kick attacks".

Tests 44. Layers 0, 4, 8, 10, 11, 12 and the full cart byte-identical.

## P97: layer 14, the yard styled -- how a body takes it (2026-11-25)

The player, P96 on glass: "i think this is the complete base kit. it feels insanely good to play now, of course what
we can do from here is first a layer of polish, the controls feel good no changing that, just making the action more
stylized to feel tactical, mature, and hyperviolent." And, when I began on blood: "hyperviolent is not just gore, its
about making the fighting correagraphy be hyperviolent."

So the base kit is FROZEN as layer 13, and the polish is a layer of its own: `TND_LAYER=14` is the yard, and what is
its own is under `STYLE` in the generator. Layer 13 is built byte for byte as it was. No button does anything it did
not; his own bank of poses is untouched. This first slice is the other half of every exchange -- the body.

OBSERVED: every body that went down went down ONE way -- thrown back, into the air, flat (P73's `down`) -- whether
a haymaker put it there or one round did (about 170 falls in his last five minutes); a hook landed as a jab does,
the chin taken back; and a body sent into a wall stopped at it and nothing more.

- **IT GOES DOWN BY WHAT PUT IT DOWN.** Baked on the archive's rig as the reactions are (`tools/tnd_falls.py`,
  carried to the three smaller bodies the same way), into the bodies' banks only:
  - a light blow or a round to the HEAD: **dropped** -- the chin snapped back, the knees gone under it, sat back
    on its heels and over, where it stood;
  - to the BODY: **folded** -- over the blow, onto its knees, pitched onto its face;
  - to the LEGS: **cut down** -- the leg gone from under it, a knee and its hands, its face;
  - a heavy blow (the hooks, the haymaker, the uppercuts, a charged round, the run's body blows, a flip's kick):
    **thrown**, as it was.
  What drops, folds or is cut down goes down where it stood: a quarter of the blow's send, and its feet kept (by
  half) where they were -- the rig turns a body about its hips, and one pitched onto its face threw its legs a unit
  out behind it. The two that end on its face rise by a clip of their own.
- **A HOOK TURNS IT.** The head and shoulders hard away from the hand that threw it -- the lead hand's to the
  body's left, the rear's to its right -- an arm thrown wide. (And a round's flinch is now where the round went
  in: it was the last fist's.)
- **THE WALL HITS IT.** A body a blow sends along the floor into a wall or a structure's side, with a quarter of a
  unit still to go, is struck by it: one more off what it can take, its chin back and held 22 frames, the world
  stopped three frames, the lens shaken, the blow's sound. If that is the last of it, it folds off the wall.
  A jab sends nothing that far.

All of it a reading of his three words: he has not seen it. On the presses of his last session it would have shown
44 thrown, 47 dropped, 43 folded (he did not aim low). In one scripted scene layer 14 runs 1 to 63 instructions a
frame more than layer 13. Program 27,368 words (the limit 29,266); data memory 562 free; the cart 12.9 MB of 16.

Tests: the yard's 44 as they were; layer 14's own 3 (`tests/test_tnd_style.py`). Layers 0, 4, 8, 10, 11, 12, 13 and
the full cart byte-identical.

## P98: layer 14 -- on a body that is down; a round's own jolt; bodies into bodies (2026-11-25)

The player, P97 on glass (he played 4.7 minutes of it), of the three things I had named as next: "do all the nexxt
candidates".

OBSERVED on that session (TND STYLE, its own build): bodies down -- thrown 63, dropped 51, folded 57, cut down 14;
hooks that turned a body 11; and 420 fresh presses of a strike or the gun within 1.6 of a body that lay, of which
5 rounds and no fist landed on it -- a fist could not meet a body that was down at all, and a round met one only
by having been fired at it standing.

- **HIS HEEL.** A jab or a cross thrown over a body that lies before him is the STOMP: the knee snatched up, the
  heel driven down on the move's own first live frame (two clips of his own -- `tools/tnd_falls.py`, gs_stomp on
  the jab's sixteen frames, gs_stomp_r on the cross's nineteen with the other leg -- after every pose the yard has:
  his bank is otherwise as it was). No step in. Two off the body; it BUCKS where it lies (below); the world stops
  five frames. It does not look for a body: it is thrown where he throws it, and it is the stomp only if a body
  that is down is within nine tenths of a unit of where the heel lands.
- **THE GUN GOES DOWN TO IT.** With the gun up and nothing chosen, a body that lies within a unit of the place a
  unit ahead of him is what the gun is on: he hinges over it (41 degrees: P93's bodies) and the round is fired
  down into it -- one off it (a charged round four), struck where it lies, and no round goes on down the room.
  Choosing with R is as it was: it takes a body that stands. (So what he has chosen and put down is not shot
  where it lies by the lock; he walks to it.)
- **NEITHER, WITH ONE STANDING THERE.** A body standing within reach of the blow, or before him within five units
  of the gun, keeps the jab a jab and the gun level: a body at his feet does not take what was meant for the one
  over it.
- **STRUCK WHERE IT LIES, IT BUCKS** -- six poses, by how it lies (on its back; on its face): his heel, a round
  fired down into it, a round that was in the air when it fell. A body that was only off its feet and is finished
  there lies the whole count again.
- **A ROUND'S JOLT IS ITS OWN.** Not the fist's chin-back: the side it went in punched back, high or low -- and a
  side each, so rounds landing one after another throw a body one way and then the other.
- **A BODY THROWN INTO ANOTHER TAKES IT OFF ITS FEET.** One sent along the floor (a sixth of a unit still to go:
  never a jab's) that comes within six tenths of a unit of one that stands: that one takes one, has half the
  throw, and is cut down -- up again as a tripped body is, or down for the count with nothing left.

Readings, all: he named the candidates in my words, not his.
THE PROGRAM IS FULL. The game's program is 27,759 words and the cart loads with about a hundred to spare (the first
cut was 153 over: the per-body code went into routines). The yard still carries some 6,000 words that never run
(P77 cut what it could prove); the next thing built on layer 14 has to free some first.
Tests: layer 14's own 8; the yard's 44 as they were. Layers 0, 4, 8, 10, 11, 12, 13 and the full cart
byte-identical. Data memory 501 words free; the cart 13.5 MB of 16.
