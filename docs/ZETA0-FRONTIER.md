# ZETA-0 GRAPHICS FRONTIER — phase A audit, B1, B2, B3

**The question.** Can Zeta draw about 2,000 *useful* triangles a frame in a
TND combat encounter at a locked 60 Hz, and keep its graphical and
deterministic guarantees?

**The answer so far.** Not yet, but the machine now holds about 1,400.
- **Build 105:** the worst TND frames were over budget (30 brawl frames and
  51 tour frames above the 648k ceiling).
- **With B1 + B2 + B3** (branch `frontier/stack`), the worst frame of either
  route is **482k clocks, 74% of the ceiling**. That is 27% below build 105
  on the brawl and 30% below on the tour.
- **What 2,000 would cost now.** A cost model fitted to the stack (§12) puts
  one drawn triangle at about 400 clocks at TND's mix.
  - The 43.2 MHz ceiling therefore holds about **1,400 drawn triangles**.
  - 2,000 would cost about 893k clocks.
  - At the 51.84 MHz clock (not closed) the ceiling would hold about 1,730.
- **The most drawn so far** is 1,229 triangles (tour frame 692): 461k on the
  stack.
- **These are extrapolations of a linear fit.** A metered 2,000-triangle
  scene (C1) is still the measurement that settles it.

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
- **The sequencer and the rasterizer seem to take turns.** At frame 226 the
  sequencer holds a finished face for 213k clocks, while the rasterizer
  sits in S_WAIT for 246k (the meter's "idle").
  - **This reading was wrong in an important way; §9 corrects it.** The
    holding and the starving happen in *different bands*, so a queue cannot
    trade one against the other.
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

Clock figures are at the route peaks unless stated otherwise.

| # | candidate | target | measured or expected gain | cost | disposition |
|---|---|---|---|---|---|
| B1 | **span walk**: anchor, seek, draw, early exit | fill | **measured:** −112k brawl peak, −143k tour peak | +353 ALMs, no RAM | **accepted** |
| B3 | **fast clipper**: 2-beat DSP multiply, radix-4 divide | the geometry pass, on clip-heavy frames | **measured:** −61k (brawl 226), −41k (tour 887); small elsewhere | +4 DSP; ALMs between ~120 and ~830 depending on the run (§11) | **accepted**: the stack fits with it |
| B2 | **triangle queue**, 32 deep in MLAB | the sequencer's holds inside band 0 | **measured:** −28k on the *average* frame, −30k at the peaks | +422 ALMs (93%), no M10K | **accepted with a caveat**: one mutant unkilled (§9) |
| — | early row exit only | fill | walk ×0.81 | small | **rejected**: B1 includes it |
| — | serpentine walk | fill | walk ×0.63 (crude model) | small | **rejected**: breaks OBJ_LODSPAN's left-to-right order, so it changes the law |
| — | deeper queue (64 to 2,048) | handoff | **measured:** 3k more at most | 280 ALMs per doubling | **rejected**: depth is not the limit (§9) |
| B6 | radix-16 projection divider (two radix-4 stages a beat) | the geometry pass: 55k of divides every frame | est. −25k every frame; also shortens the gradient ladder | est. ~100 ALMs, plus a longer path | **not yet measured**: next |
| B4 | hide the band clear | 97.7k every frame, all of it rasterizer-bound | up to ~90k | per-pixel valid bits would need RAM, which is full | **deferred**: no RAM to pay for it |
| B5 | DIV=6 core clock (51.84 MHz) | everything | +20% clocks a frame | one register on the vc → S_FN path, plus timing closure at 93–94% ALMs | **deferred**: orthogonal, and harder now that the device is fuller |
| B7 | overlap the geometry pass with rasterizing (frame pipelining) | the structure itself (§9) | large: up to the whole geometry pass | a second vertex cache and bin store; RAM is full | **rejected for this device** unless RAM is freed |
| C1 | 2,000-triangle stress scene, metered | measurement | answers the question | a cart, no silicon | **not yet measured** |
| — | texture cache or wider texel fetch | texture | none at present | RAM | **rejected for now**: the texel ladder is not a wall |
| — | more PSRAM bandwidth | memory | none at present | | **rejected for now**: stall is under 1% |

### B2: counting the bits (written before it was built)

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
- Nothing merges until the user has seen it on glass and decides.

**The branches:**

| branch | contents | staged for glass |
|---|---|---|
| `frontier/span-walk` | B1 | build/frontier-b1 |
| `frontier/tri-queue` | B1 + B2 | build/frontier-b2 |
| `frontier/clip-fast` | B1 + B3, plus the bigclip cart | build/frontier-b3 |
| `frontier/stack` | B1 + B2 + B3 | build/frontier-stack |

## 9. B2: the triangle queue, and what it taught

**What it is.** A 32-deep, 546-bit queue in zeta_top between zseq and zgpu
(`frontier/tri-queue`).
- The rasterizer sees the same handshake as before (ready observed, go one
  clock later), now driven from the queue's head.
- The sequencer's ready is the queue's, with one slot kept in hand for the
  write in flight.
- A band ends when the rasterizer is idle *and* nothing is queued or in
  flight.
- The law is untouched: the same triangles in the same order.

**The prediction was wrong.** §5 bounded the gain at about 200k, by taking
min(sequencer hold, rasterizer idle) at frame 226. The measured gain at
that frame is 30k.

**Why: depth is not the limit.** Queue depth was swept in simulation, with
nothing else changed:

| depth | brawl 226 | brawl 466 |
|---:|---:|---:|
| 1 (B1, no queue) | 551,442 | 514,470 |
| 32 | 521,589 | 485,766 |
| 64 | 518,663 | 475,018 |
| 256 | 518,583 | 470,981 |
| 2,048 | 518,583 | 470,981 |

With an unlimited queue the sequencer is never blocked, and it finishes
the frame's work in 286k clocks. The frame is still 518k.

**The per-band profile shows the real structure.** The harness now reports
what each band waits on, and zseq's state histogram per band. Frame 226,
with the 32-deep queue:

| band | band clocks | sequencer busy | rasterizer walking | vertex | clip | face + gradient |
|---:|---:|---:|---:|---:|---:|---:|
| **0** | **231,648** | 231,647 | 10,192 | 76,925 | 117,130 | 17,928 |
| 1 | 29,155 | 12,942 | 18,160 | 0 | 0 | 1,988 |
| 2 | 27,638 | 13,057 | 16,636 | 0 | 0 | 1,988 |
| 3 | 28,453 | 23,218 | 17,412 | 0 | 0 | 2,733 |
| 4 | 38,180 | 37,095 | 26,852 | 0 | 0 | 9,173 |
| 5 | 32,979 | 32,727 | 20,201 | 0 | 0 | 12,155 |
| 6 | 31,933 | 31,932 | 18,937 | 0 | 0 | 11,422 |
| 7 | 24,967 | 24,574 | 13,865 | 0 | 0 | 4,544 |
| 8 | 34,515 | 22,812 | 12,006 | 0 | 0 | 3,144 |

- **Band 0 is the geometry pass for the whole frame.** Every vertex is
  transformed and every face clipped and binned there. The rasterizer has
  only band 0's own triangles to draw, so it waits.
- **Bands 1–8 replay the bins.** The sequencer's own work is 2–12k a band,
  and the rasterizer is the limit (the clear's 10.8k, plus the walk).
- **So a frame is the sequencer's pass plus eight rasterizer-bound bands,**
  on top of the VM's 31–44k. The holding and the starving that §5 counted
  sit in different bands, which is why a queue cannot trade them.
- **The meter's "idle" misleads.** It is "rasterizer in S_WAIT", counted
  across the whole frame, the VM's run included. It does not mean a queue
  could have fed it.

**What B2 does buy.** It recovers the sequencer's holds inside band 0, and
its first-triangle wait for each clear. That is worth about 28k on the
average frame, not only at the peaks:

| route | mean, B1 | mean, B1+B2 | peak, B1 | peak, B1+B2 |
|---|---:|---:|---:|---:|
| brawl | 430,349 | 400,531 | 551,442 | 521,589 |
| tour | 416,340 | 388,736 | 543,552 | 516,473 |

**Verification.**
- Cross bit-equal on the six stress carts.
- Routed cross bit-equal on all 521 + 901 TND frames.
- CI gates green.
- Lint at the baseline.

**Physical cost** (fit 44730285068):

| | B1 | B1 + B2 | change |
|---|---:|---:|---:|
| ALMs | 16,743 (91%) | 17,165 (93%) | **+422** |
| ALMs used for memory | 190 | 470 | +280 |
| M10K | 308 | 308 | 0 |
| DSP | 56 | 56 | 0 |
| core-clock setup slack, worst corner | +2.207 ns | +2.506 ns | still met |

The queue landed in MLAB as written: memory ALMs rose by exactly 280.

**Mutation witnesses.**

| mutant | result |
|---|---|
| Q1: the band ends with triangles still queued | **FAIL on all four carts** |
| Q2: flags read live from zseq, not from the queue | **FAIL** on glow and tex; bunny and fabric pass |
| Q4: the queue never says full | **FAIL on all four** |
| Q5: the pop is not guarded against the go in flight | **FAIL on all four** |
| Q3: the pick id read live (cur_tri), not from the queue | **SURVIVES** |

**The open gap (Q3).** No cart tried kills Q3: pick, watched, vessel,
banked, and pick.zol re-aimed at a display-list triangle for 60 frames.
- The queued id is the right design: the id belongs to the triangle, not
  to whatever the sequencer is doing when the rasterizer takes it.
- But no gate shows it. A cart whose picked triangle sits behind a backlog
  would. That cart is owed before B2 merges.

## 10. B3: the clipper's arithmetic

**What was there.** For each coordinate of each plane crossing, the clipper
computed va + (vb − va)·da / (da − db) one bit a clock: 33 beats of
shift-and-add, then 33 of restoring divide. It was written when the device
had no DSP block to spare; it now has ten.

**What it cost.** The band profile at brawl frame 226 (all of it in band 0):

| state | clocks |
|---|---:|
| S_CLM (multiply) | 43,164 |
| S_CLDV (divide) | 43,164 |
| the rest of the clipper | 30,802 |

That is 436 crossings × 3 coordinates × 66 beats = 86,328.

**The change** (`frontier/clip-fast`, silicon/zseq.v only):
- **The multiply takes two beats.** The 33 × 50-bit product is split into
  four partial products (27×27, 27×23, 6×27, 6×23). They are registered,
  then summed modulo 2^82, exactly as the old 82-bit accumulator took it.
- **The divide takes seventeen beats.** It is the same restoring quotient in
  radix 4: sixteen two-bit beats, then one radix-2 beat for the odd 33rd
  bit. This is the projection divider's own form.
- **Widths come from the declared range:** den < 2^51, so 3·den and the
  doubly shifted remainder are 53 bits.

**Measured.** The prediction was 47 clocks saved per coordinate:

| frame | B1 | B1 + B3 | saved | predicted |
|---|---:|---:|---:|---:|
| brawl 226 | 551,442 | 489,996 | **61,446** | 61,476 |
| tour 887 | 543,552 | 502,371 | **41,181** | 41,172 |
| brawl 466 (little clipping) | 514,470 | 510,485 | 3,985 | — |

B3 is a peak fix, not an average one: the brawl's mean frame moves by 3k
and the tour's by 9k.

**Verification.**
- Cross bit-equal on nearclip, hall and tex (40 frames each).
- Routed cross bit-equal on all 521 + 901 TND frames.
- Lint at the baseline.

**Mutation witnesses, and the hole they found in the suite.**

| mutant | nearclip | bigclip (new) |
|---|---|---|
| C1: a partial product one bit off | **FAIL** | |
| C2: the divide one beat short | **FAIL** | |
| C3: the digit never reaches 3 | **FAIL** | |
| C4: the top partial product (6×23) dropped | survives | **FAIL** (85,369 px) |
| C5: the high-multiplier partial (6×27) dropped | survives | **FAIL** (11,270 px) |
| C6: 3·den narrowed to 52 bits | survives | survives: **equivalent** |

- **The suite never reached the top of the clipper's range.** nearclip's
  tiles are 2 units wide, so every crossing it makes is small arithmetic.
  The wide end of the old serial datapath was just as unwitnessed.
- **`carts/bigclip.zol` closes that.** It is the same checker with tiles
  6,000 units wide, so adjacent vertices differ by more than 2^27 in view
  space, and the tiles cross all five planes at once. It crosses bit-equal
  and kills C4 and C5. It is a suite claim now, so it is a standing gate.
- **C6 is equivalent, not unwitnessed.** Plane distances are signed 50-bit,
  so den ≤ 2^50 and 3·den < 2^52. The 53-bit width is the declared range's,
  and it stays.

**Physical cost** (fit 44737066652, B1 + B3):

| | B1 | B1 + B3 |
|---|---:|---:|
| ALMs needed | 16,743 (91%) | 17,572 (95%) |
| combinational ALUTs | 26,575 | 28,235 |
| DSP | 56 | **60** |
| M10K | 308 | 308 |
| core-clock setup slack, worst corner | +2.207 ns | +2.396 ns |

That reads as +829 ALMs, four times the estimate. **But §11 shows the
number cannot be taken at face value:** the stack, which contains the same
B3 code, used 1,096 fewer ALUTs than this run did.

## 11. The stack: B1 + B2 + B3

Branch `frontier/stack`. Both routes cross bit-equal on every frame.

| | build 105 | B1 | B1+B2 | B1+B3 | **B1+B2+B3** |
|---|---:|---:|---:|---:|---:|
| brawl peak | 663,546 | 551,442 | 521,589 | 510,485 | **481,842** |
| brawl mean | — | 430,349 | 400,531 | 427,486 | **397,640** |
| tour peak | 686,836 | 543,552 | 516,473 | 522,746 | **482,273** |
| tour mean | — | 416,340 | 388,736 | 407,158 | **379,920** |
| frames over 480k (brawl / tour) | — | 144 / 286 | 10 / 48 | 123 / 245 | **1 / 22** |

- B2 and B3 are complementary: B3 lowers the clip-heavy frames, and B2
  lowers every frame.
- The stack's worst frame is 67% of the 720k frame and 74% of the ceiling.

**Physical cost** (fit 44739753754; CI gates 44739754175 green):

| | build 105 | B1 | B1+B2 | B1+B3 | **stack** |
|---|---:|---:|---:|---:|---:|
| ALMs needed | 16,390 (89%) | 16,743 (91%) | 17,165 (93%) | 17,572 (95%) | **17,286 (94%)** |
| ALMs in final placement | 17,426 | 17,757 | 17,999 | 18,143 | **18,056** |
| combinational ALUTs | 26,336 | 26,575 | 26,886 | 28,235 | **27,139** |
| registers | 19,694 | 19,813 | 19,979 | 19,805 | **19,765** |
| DSP | 56 | 56 | 56 | 60 | **60** |
| M10K | 308 | 308 | 308 | 308 | **308** |
| core-clock setup slack, worst corner | +2.586 ns | +2.207 ns | +2.506 ns | +2.396 ns | **+2.571 ns** |

**Two things to take from this table.**
- **The stack fits and closes timing.** It ends at 94%, with as much slack
  as build 105 had.
- **Per-candidate ALM costs are noisy by several hundred.**
  - The stack holds everything B1+B3 holds, plus the queue, yet it reports
    286 fewer ALMs and 1,096 fewer ALUTs than B1+B3 alone.
  - Synthesis is resolving the same RTL differently between runs, and the
    fitter packs harder as the device fills ("difficulty packing" went
    from Medium to High).
  - So a single fit says whether a configuration *fits*. It does not price
    one candidate to the ALM.
- **The device is close to physically full.** Final placement uses 18,056
  of 18,480 ALMs. The 94% figure counts on about 1,100 ALMs the fitter
  estimates it could recover by packing more densely. Every further
  candidate has to be weighed against that.

**Staged for glass** (each is build/pocket's cart with a different core):

| directory | core |
|---|---|
| build/pocket | build 105, the known-working one |
| build/frontier-b1 | B1 |
| build/frontier-b2 | B1 + B2 |
| build/frontier-b3 | B1 + B3 |
| build/frontier-stack | B1 + B2 + B3 |

## 12. The cost model on the stack

The same regression as §5 (1,420 frames, census against metered clocks),
on the stack. The fit is tighter: residual σ ≈ 11.4k, worst 62k.

| term | after B1 | on the stack |
|---|---:|---:|
| fixed | 117,065 | 89,156 |
| per submitted face | 80.1 | 68.4 |
| per drawn triangle | 30.4 | 47.5 |
| per covered pixel | 1.1 | 1.1 |

At TND's mix (2.34 faces and 172 covered pixels per drawn triangle), one
drawn triangle costs about **400 clocks**: 160 for its faces, 48 for
itself, 190 for its pixels.

| ceiling | clocks | drawn triangles it holds |
|---|---:|---:|
| 43.2 MHz, 90% | 648,000 | about 1,400 |
| 51.84 MHz, 90% (not closed) | 777,600 | about 1,730 |
| needed for 2,000 | about 893,000 | |

**What would close the gap to 2,000.**
- The clock alone is not enough: it reaches about 1,730.
- The remaining 14% has to come out of the per-triangle cost. The
  candidates are the projection divides (B6) and the clear (B4).
- The alternative is content that submits fewer faces per triangle drawn.
  Culling earlier would cut the 160-clock face share.
- All of this is extrapolation. C1 measures it.
