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

## P32: what the tape of P31 says (2026-11-22; not yet on glass)

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
