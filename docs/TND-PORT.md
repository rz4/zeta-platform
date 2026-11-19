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
4. **THE FRAME.** Measured 316k for the player and floor. Three demons
   at 476 faces each, half culled, estimate ~250k; the street ~50k:
   ~615k against the 648k ceiling at 43.2 MHz. Tight, so the horns
   (152 of a demon's 476 faces) are the first LOD, and DIV=6 (+20%,
   SEAMS/ZETA0) is the headroom.
5. **THE CAMERA IS FREE.** TND follows behind the player through
   every mode, so no plates in play: the street is real geometry. The
   archive's ~3,000 in-view triangles were incidental (asphalt
   subdivided to dodge a near-plane reject the Zeta's clipper does not
   need, plus a redundant floor) -- a few hundred large faces will do.
6. **THE PC CABINET RUNS IT AT 24 FPS.** The silicon has room; machine
   1's per-triangle overhead does not. The batched opaque rasteriser
   (gpu.py) stops being optional the moment TND is the flagship.

## The phases

    P2  THE STREET AND THE FOLLOW   Bancroft and Shattuck as lean
        geometry (the "+" intersection, sidewalks, crosswalks, box
        buildings, streetlights, fog); the archive's spring follow as
        integer smoothing; walk in four directions and the run. More
        clips baked under the 30/60 Hz rule.
    P3  THE DEMONS                  rigid rigs from resident key poses,
        three builds, the slow-turn turret AI (0.034 rad a frame, a
        0.46 rad cone, a swing every 74 frames), waves of three,
        mass-weighted shove.
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
