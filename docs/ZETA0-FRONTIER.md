# ZETA-0 GRAPHICS FRONTIER — phase A audit and B1

**The question.** Can Zeta draw about 2,000 *useful* triangles a frame in a
TND combat encounter at a locked 60 Hz, and keep its graphical and
deterministic guarantees?

**The answer so far.** Not yet.
- **Today:** 965 useful triangles at the brawl's worst frame. That frame was
  over budget before B1 and is now inside it with 15% to spare.
- **The first wall** was the rasterizer walking the whole bounding box of
  every triangle. It is removed (B1, below) with no change to the law.
- **The next wall** is the sequencer's cost per face, plus the one-deep
  handoff that couples the sequencer to the rasterizer.
  - A fit over 1,420 frames puts it at ~80 clocks per *submitted* face.
  - At today's ratios that extrapolates to **~941k clocks for 2,000
    triangles, against a 648k ceiling.**
- **The most drawn so far** is 1,229 triangles (tour frame 692), and it fits
  at 511k.
- **2,000 is not yet measured.** It needs a stress scene before anyone
  claims it (C1 in the matrix).

Each item below is **accepted**, **rejected**, **deferred** or
**not yet measured**.

---

## 1. Audit: build 105, the machine as it ships

Source: CI fit run 44698703119 (main, the census commit). The fitter's
full report is now kept in the artifact.

| resource | used | of | |
|---|---:|---:|---|
| ALMs | 16,390 | 18,480 | 89% |
| registers | 19,728 | | |
| M10K blocks | 308 | 308 | **100%: block RAM is full** |
| DSP blocks | 56 | 66 | 85% |

**Setup slack, worst corner:**
- core clock (divclk): +2.586 ns;
- clk_74a: +5.883 ns;
- cram0: +7.114 ns;
- cram1: +9.112 ns.

The core runs at 43.2 MHz: 720,000 clocks a frame, with a ceiling of 90%,
which is 648,000. The DIV=6 clock (51.84 MHz) is still **not closed**; its
path from the vc port B to S_FN wants a register.

**Utilization by module** (ALMs needed, block-RAM blocks, DSP):

| module | ALMs | M10K | DSP | notes |
|---|---:|---:|---:|---|
| zseq (sequencer: transform, project, clip, setup) | 6,114 | 45 | 29 | the largest, 37% of the core |
| zgpu (rasterizer, tile memories, texture) | 3,333 | 113 | 21 | tile depth, colour and texels |
| zsnd (audio) | 2,600 | 16 | 0 | |
| zeta_top glue (movers, meter, bands, PCM) | 1,495 | — | — | |
| cram_fb + 2× cram_burst (PSRAM) | 876 | 8 | 0 | |
| zvm (CPU) | 839 | 97 | 3 | IMEM is 8,192 words |
| cart_loader, card_apf, zcard, glass shell | ~690 | 22 | 0 | |

**What this means for any candidate.**
- No candidate can buy block RAM. RAM blocks are 308 of 308.
- About 2,000 ALMs remain, and the fitter's comfort zone is smaller than that.
- So anything that stores state must count its bits, not estimate them. The
  cheapest win is one that removes *clocks*, not one that adds memory.

## 2. The geometry pipeline, stage by stage

The pipeline runs once per band. TILE_H is 32, so there are 9 bands of 32
rows.

1. **Display list and object fetch** (zseq S_DLN… and S_OLN… S_OT*). The
   sequencer walks the object list again for every band.
2. **Vertex** (S_VW…S_SY, S_R*, S_TW/S_TM). The transform runs through a
   2,048-vertex cache, then projection by the divider, then an int16 clamp.
3. **Face** (S_FW…S_FN). Fetch, cull and bin.
4. **Clip** (S_CL*). The near-plane polygon clipper.
5. **Gradient setup** (S_G*). The edge, depth and colour slopes.
6. **Handoff.** A one-deep triangle register, gated by tri_rdy. While the
   rasterizer is busy, the sequencer holds in S_FE (faces) or S_DLE
   (display list).
7. **Rasterizer** (zgpu S_WALK). One pixel a clock with flat shading. A
   texel ladder runs only for covered pixels.
8. **Write FIFO, then the band's colour to PSRAM** (cram_fb). Each band's
   flush rides the next band's clear.

## 3. The profile before B1

**The silicon meter** (tools/tnd_meter.py, song build), in clocks at each
route's worst frame:

| route (frame) | total | clr | walk | idle | stall | seq | blkd |
|---|---:|---:|---:|---:|---:|---:|---:|
| brawl (466) | **663,546** | 97,666 | 380,204 | 120,798 | 5,550 | 594,472 | 410,973 |
| tour (887) | **686,836** | 97,688 | 342,180 | 194,487 | 5,585 | 632,932 | 387,201 |

- clr, walk, idle and stall are the rasterizer's own states.
- seq means the sequencer is active.
- blkd means the sequencer holds a finished triangle that the rasterizer
  won't take yet.

Before B1, 30 of the brawl's 521 frames and 51 of the tour's 901 frames
were over the ceiling.

**The geometry census** (tools/geo_census.py, on the law), at brawl frame 466:
- 2,140 faces submitted, and 965 distinct triangles reached the rasterizer
  and covered pixels;
- 366,232 pixels walked, 162,834 covered.
- So the box walk landed on its triangle **0.44** of the time, and 0.44–0.52
  across the worst frames.

**Attribution of the walk** (tnd_meter walk, frame 466):

| object | walked pixels |
|---|---:|
| street | 151,534 |
| demon0 | 66,763 |
| ground | 65,280 |
| demon1 | 32,651 |
| demon2 | 29,017 |
| body | 14,699 |
| marker | 5,078 |
| display list | 1,210 |

**The verdict on the bottleneck.**

| suspect | finding | |
|---|---|---|
| **pixel fill** | 380k walk clocks, and the sequencer blocked 411k of the frame waiting on it | **dominant** |
| texture fetch | the ladder runs only for covered pixels | not a wall |
| external memory | stall is 5.5k clocks (<1%) | not a wall |
| transform, clip, setup | hidden behind the blocking | not a wall yet |

Within fill, more than half of the walk landed off the triangle.

## 4. B1: the span walk (accepted)

**Branch:** `frontier/span-walk`. Only one RTL file changes, silicon/zgpu.v.
The law, spec.py and the carts are untouched.

**The idea.** A triangle is convex, so each row's coverage is one interval.
For each row:

- **START.** Begin at the *anchor*, which is the previous row's first
  covered pixel (on the first row, the box corner).
- **SEEKL.** If the anchor is covered and its left neighbour is too, step
  left without drawing.
  - The left neighbour's coverage is read combinationally (e + edx), so the
    walk never steps out and back.
- **SEEKR or SEEKLU.** If the anchor is uncovered, the failing edges name
  the side to search:
  - an edge's function grows in the direction of its x step, and the sign
    of the area fixes the orientation;
  - if the failing edges disagree, or one of them cannot be fixed by any x
    step, the row is empty.
- **DRAW.** Draw left to right, and end the row at the first uncovered
  pixel (the early exit).
- **Degenerate triangles** (zero area) keep the box edge as their anchor.

**Why it is exact by construction.**
- Every pixel the walk visits is reached by the same accumulators stepped
  by the same adds. A left step is the inverse of a right step, and int64
  wraparound commutes.
- Each covered pixel commits exactly once, left to right, rows top to
  bottom. That is the order the law uses, and the order OBJ_LODSPAN's
  first-covered-pixel rule reads.
- Seeks run no texel ladder.

**Verification.**

| gate | result |
|---|---|
| cross, 12 frames, framebuffer and audio: glow, bunny, tex, lodspan, fabric, edged | **PASS** (all six) |
| routed cross: the whole brawl and tour routes on the TND song build (tools/route_cross.py) | **PASS**: 521 + 901 frames bit-equal, framebuffer and audio, every frame |
| CI gates on the branch (run 44700434813) | **PASS** |
| lint | 111 warnings, the baseline |

**Mutation witnesses.** Each mutation must make the cross fail.

| mutant | expected | result |
|---|---|---|
| M1: no left seek over uncovered pixels (the first cut) | fail | **FAIL on all four** (404 / 798 / 297 / 1,193 pixels) |
| M2: a one-pixel row starts the next row from the stale anchor | fail | **FAIL** on bunny (130) and lodspan (8, frame 7); glow and tex pass |
| M3: the left seek commits, drawing right to left | fail | **FAIL on all four** (37 / 81 / 130 / 15) |

**What M2 shows.** The one-pixel-row guard is witnessed, but only by the
carts that happen to produce one-pixel rows: bunny's slivers, and
lodspan's frame 7. A cart that drew no slivers would let a broken guard
through. The routed TND cross adds a fight's worth of slivers to the
evidence.

The first cut really was M1. Rows lying wholly left of the anchor, such as
a left-leaning sliver or the narrowing rows above a bottom vertex, were
lost, and the cross failed on all six carts until the direction-aware
seek went in.

**Measured** (silicon meter, the same routes and the same song build):

| | brawl before | brawl after | tour before | tour after |
|---|---:|---:|---:|---:|
| peak | 663,546 | **551,442** | 686,836 | **543,552** |
| median | 526,795 | **437,528** | 463,398 | **377,601** |
| frames over 90% | 30 | **0** | 51 | **0** |
| walk at the peak | 380,204 | 154,261 | 342,180 | 193,194 |
| blkd at the peak | 410,973 | 211,914 | 387,201 | 243,860 |

- The peak frames moved: brawl 466 → 226, tour stayed at 887.
- The worst frame is now 85% of the frame (77% of the 720k clocks at the
  brawl, 75% at the tour).

**Physical cost** (CI fit run 44700434784, on the branch):

| | build 105 | with B1 | change |
|---|---:|---:|---:|
| ALMs | 16,390 (89%) | 16,743 (91%) | **+353** |
| zgpu ALMs | 3,333 | 3,812 | +479 (the fitter re-packs the rest) |
| registers | 19,728 | 19,847 | +119 |
| M10K | 308 | 308 | 0 |
| DSP | 56 | 56 | 0 |
| core-clock setup slack, worst corner | +2.586 ns | +2.207 ns | still met |

Most of the cost is the left neighbour's three 64-bit edge sums, plus the
row-restart multiplexers. **The trade:** 2% of the ALMs bought 112k clocks
at the brawl's worst frame and 143k at the tour's.

## 5. The profile after B1: where the frame goes now

**The sequencer's state histogram.** The harness samples zseq's state every
clock, enabled by `ZETA_SEQHIST=1` in silicon/server.cpp. Nothing is added
to the bitstream.

| brawl frame | total | face-hold | dl-hold | clip | vertex | gradient | face | obj/fetch | idle |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 226 | 551,442 | 212,864 | — | **117,130** | 76,925 | 33,250 | 31,825 | 25,824 | 53,605 |
| 400 | 491,664 | 163,176 | 98,133 | 5,078 | 61,690 | 46,620 | 37,297 | 23,127 | 53,248 |
| 466 | 514,470 | 164,934 | 98,632 | 7,017 | 61,854 | 45,815 | 38,093 | 23,183 | 69,127 |

**Reading it.**
- **The sequencer and the rasterizer now take turns.** At frame 226 the
  sequencer holds a finished face for 213k clocks, while the rasterizer
  starves for 246k (the meter's idle). The handoff is one deep, so neither
  can run ahead of the other.
- **Clipping is the new heavy stage when the camera is near the street.**
  At frame 226 it costs 117k clocks, against 5–7k at 400 and 466.
- **dl-hold (98k) is waiting on the band clear, and a probe shows it.** The
  number was close to the clear's 97.7k, but a number that fits is not
  evidence. So the harness now cross-tabulates each hold state against the
  rasterizer's state on the same clock:

| frame | hold | rasterizer clearing | rasterizer walking | rasterizer waiting |
|---|---|---:|---:|---:|
| 226 | face-hold (S_FE) | **94,468** | 117,409 | 987 |
| 466 | dl-hold (S_DLE) | **97,538** | 671 | 423 |
| 466 | face-hold (S_FE) | 0 | 163,591 | 1,343 |

  In every band the sequencer gets its first triangle ready, then sits out
  the whole clear. The clear can't be shortened cheaply (B4), but the
  sequencer could *work through it* if it had somewhere to put triangles.
  That is B2.
- **The active work per face is about 85 clocks.** At frame 466 the vertex,
  face, gradient, clip and fetch states total ~182k for 2,140 submitted
  faces.
- **Doubling the faces adds roughly 180k clocks of sequencer work.** Most of
  that is *not* hidden, so 2,000 useful triangles cannot be reached with B1
  alone. This is an estimate and must be measured (C1).

### Extrapolating: what 2,000 would cost after B1

The census ran on every frame of both routes (on the law). Each frame's
census counts were then regressed against that frame's metered silicon
clocks with B1 in place.
- **Fitted:** 1,420 frames (title frames under 50 triangles left out).
- **Model:** linear least squares.
- **Fit quality:** residual σ ≈ 19.8k clocks, worst residual 112k.

| term | clocks |
|---|---:|
| fixed: clear, bands, CPU, audio | 117,065 |
| per **submitted face** | **80.1** |
| per drawn triangle | 30.4 |
| per covered pixel | 1.1 |

At today's ratios (2.34 submitted faces per drawn triangle, a median of 172
covered pixels per triangle):

| drawn triangles | predicted clocks | vs the 648k ceiling |
|---:|---:|---|
| 965 (brawl peak) | 514,562 | fits |
| 1,229 (the most either route drew: tour 692) | metered 510,678 | fits |
| 1,500 | ~735,000 | **over** |
| 2,000 | ~941,000 | **over by ~45%** |

**What this says.**
- After B1 the face term dominates. Each submitted face costs ~80
  sequencer-coupled clocks, whether or not it is drawn, and every visible
  triangle costs 2.34 faces.
- **So 2,000 needs two things,** and B1 gives neither:
  1. the sequencer's cost per face must roughly halve, through overlap (B2)
     and cheaper per-band face work (B3);
  2. or fewer faces must be submitted per triangle drawn.
- **This is an extrapolation of a linear fit,** outside the range it was
  measured on. It says which term to attack. It does not certify a number:
  C1, a metered scene with 2,000 triangles, remains the measurement.

## 6. The ALM ledger after B1

- **Headroom left:** 1,737 ALMs (91% used).
  - B2 in MLAB (~280 ALMs plus control) would leave about 1,400.
  - Every further candidate has to be paid for in that same currency.
- **The closure-phase rule still holds:** ALMs are scarce, so a candidate
  wins by removing clocks per ALM, not by adding features.

## 7. The candidate matrix

| # | candidate | target | expected gain | cost | disposition |
|---|---|---|---|---|---|
| B1 | **span walk**: anchor, seek, draw, early exit | fill | walk −50–60% | a few hundred ALMs, no RAM | **accepted** (this branch) |
| — | early row exit only | fill | walk ×0.81 | small | **rejected**: B1 includes it |
| — | serpentine walk | fill | walk ×0.63 (crude model) | small | **rejected**: breaks OBJ_LODSPAN's left-to-right order, so it changes the law |
| C1 | 2,000-triangle stress scene (TND layout, metered) | measurement | answers the question | a cart, no silicon | **not yet measured**: next |
| B2 | **triangle queue**, sequencer → rasterizer | handoff coupling: ~95k of holding through the clear, plus walk/clip turn-taking | at most min(sequencer hold, rasterizer idle), about 200k at brawl 226; an upper bound, not a forecast | counted below: in MLAB, about 280 ALMs and no M10K | **not yet measured**: recommended next |
| B3 | clip cost: the clipper's per-band repeat, serial polygon reads | clip | up to ~100k at near-camera frames | unknown | **not yet measured**: needs a per-band clip count |
| B4 | hide the band clear (lazy or overlapped clear) | clr, and dl-hold if the hypothesis holds | up to ~97k | per-pixel valid bits would need RAM, which is full | **deferred**: confirm the dl-hold hypothesis first |
| B5 | DIV=6 core clock (51.84 MHz) | everything | +20% clocks a frame | one register on the vc → S_FN path, plus timing closure | **deferred**: an orthogonal lever, and it moves every budget |
| — | texture cache or wider texel fetch | texture | none at present | RAM | **rejected for now**: the texel ladder is not a wall |
| — | more PSRAM bandwidth | memory | none at present | | **rejected for now**: stall is under 1% |

### B2: counting the bits

One triangle crossing the zseq → zgpu port is **546 bits**:

| field | bits |
|---|---:|
| tx/ty × 3 (36 each) | 216 |
| tc0 | 51 |
| colour slopes (6 × 26) | 156 |
| tz0 + tzx + tzy | 68 |
| tri_id | 16 |
| t_tex, tint (15+1), oid (8), otint, span, page (5), blend, alpha (5), add | 39 |

**Two ways to store it:**
- **As registers,** a 2-deep queue is 1,092 flip-flops: about 550 ALMs on a
  core at 89%. **Too dear.**
- **As MLAB** (LUTRAM built from ALMs, 32 × 20 bits each), 546 bits is 28
  columns, so one 32-deep queue is about 28 MLABs, roughly **280 ALMs, with
  no M10K at all**.
  - It needs `ramstyle = "MLAB"`.
  - The map report must confirm the queue landed in MLAB, per entity.

**Order is preserved, so the law is untouched.** The rasterizer sees the
same triangles in the same order. One thing changes in zeta_top: a band
ends only when the sequencer is done, the queue is empty, and the
rasterizer is ready.

## 8. Keeping a known-working Pocket build

- `main` is untouched: build 105, last fit 44698703119.
- build/pocket holds the verified column.
- B1 lives only on `frontier/span-walk` until its fit and gates are green,
  the user has seen it on glass, and the user decides on a merge.
