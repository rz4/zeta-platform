# ZETA-0 GRAPHICS FRONTIER — phase A audit, B1, B2, B3

**The question.** Can Zeta draw about 2,000 *useful* triangles a frame in a
TND combat encounter at a locked 60 Hz, and keep its graphical and
deterministic guarantees?

**The answer so far.** Not yet, but the machine now holds about 1,400.
- **Build 105:** the worst TND frames were over budget (30 brawl frames and
  51 tour frames above the 648k ceiling).
- **With B1 + B2 + B3** (branch `frontier/stack`), the worst frame is
  **483k clocks on the brawl and 488k on the tour, 75% of the ceiling**.
  That is 27% and 29% below build 105.
- **It costs 543 ALMs** (16,390 → 16,933, 92%), four DSP blocks and no block
  RAM. Timing closes with +2.468 ns of slack.
- **What 2,000 would cost now.** A cost model fitted to the stack (§12) puts
  one drawn triangle at about 400 clocks at TND's mix.
  - The 43.2 MHz ceiling therefore holds about **1,400 drawn triangles**.
  - 2,000 would cost about 885k clocks.
  - At the 51.84 MHz clock (not closed) the ceiling would hold about 1,730.
- **The most drawn so far** is 1,229 triangles (tour frame 692): 464k on the
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
| B3 | **fast clipper multiply**: one inferred product, one beat | the geometry pass, on clip-heavy frames | **measured:** −42k (brawl 226), −28k (tour 887); small elsewhere | +4 DSP, **−47 ALMs**, −232 registers | **accepted** |
| — | radix-4 clipper divide | the same | **measured:** a further −20k (brawl 226), −13k (tour 887) | +1,019 ALMs fitted alone | **rejected**: the dear half of the first B3 (§10) |
| B2 | **triangle queue**, 32 deep in MLAB | the sequencer's holds inside band 0 | **measured:** −28k on the *average* frame, −30k at the peaks | +422 ALMs fitted alone (+237 in the stack), no M10K | **accepted** |
| — | early row exit only | fill | walk ×0.81 | small | **rejected**: B1 includes it |
| — | serpentine walk | fill | walk ×0.63 (crude model) | small | **rejected**: breaks OBJ_LODSPAN's left-to-right order, so it changes the law |
| — | deeper queue (64 to 2,048) | handoff | **measured:** 3k more at most | 280 ALMs per doubling | **rejected**: depth is not the limit (§9) |
| B6 | radix-16 projection divider (two radix-4 stages a beat) | the geometry pass: 55k of divides every frame | **measured:** −23k on every frame (brawl peak 483k → 460k) | **+986 ALMs: 17,919, 97%**; slack +1.960 ns | **rejected**: exact, but it does not fit this device (§13) |
| B4 | hide the band clear | 97.7k every frame, all of it rasterizer-bound | up to ~90k | per-pixel valid bits would need RAM, which is full | **deferred**: no RAM to pay for it |
| B5 | DIV=6 core clock (51.84 MHz) | everything | +20% clocks a frame | one register on the vc → S_FN path, plus timing closure at 93–94% ALMs | **deferred**: orthogonal, and harder now that the device is fuller |
| B7 | overlap the geometry pass with rasterizing (frame pipelining) | the structure itself (§9) | large: up to the whole geometry pass | a second vertex cache and bin store; RAM is full | **rejected for this device** unless RAM is freed |
| C1 | stress scene: TND with a fourth demon, metered | measurement | **done** (§14): the object list and the vertex cache bind before the clock does | a build flag, no silicon | **measured** |
| B8 | a longer object list (64 → ~100) and a larger vertex cache | the two limits C1 found | lets the scene grow past one more demon | a law change (OL_MAX), registers for the list, and M10K for the cache, which is full | **deferred**: needs RAM freed first |
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
| Q3: the pick id read live (cur_tri), not from the queue | survives the four carts; **FAIL on pickfloor (new)** |

**The gap Q3 found, and the cart that closed it.** Q3 survived pick,
watched, vessel and banked, and pick.zol re-aimed at a display-list
triangle.
- **Why it survived.** Those carts pick small triangles that the rasterizer
  takes the moment they are offered. An id read at that moment is the same
  whether it rode in the queue or was read off the sequencer's counter.
- **What waits is the floor.** It is the first mesh in the list, so every
  band offers its triangles while the rasterizer is still clearing.
- **`carts/witness/pickfloor.zol`** is pick.zol with the crosshair started on the
  floor at (160, 250). It crosses bit-equal, and Q3 fails it at frame 1 by
  420 pixels. It is a suite claim now, so it is a standing gate.

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

**The first cut** did both halves:
- **Multiply, two beats:** four hand-split partial products (27×27, 27×23,
  6×27, 6×23), registered, then summed modulo 2^82.
- **Divide, seventeen beats:** the same restoring quotient in radix 4:
  sixteen two-bit beats, then one radix-2 beat for the odd 33rd bit.

It was exact and it measured as predicted (47 beats saved per coordinate):

| frame | B1 | B1 + first-cut B3 | saved | predicted |
|---|---:|---:|---:|---:|
| brawl 226 | 551,442 | 489,996 | **61,446** | 61,476 |
| tour 887 | 543,552 | 502,371 | **41,181** | 41,172 |
| brawl 466 (little clipping) | 514,470 | 510,485 | 3,985 | — |

**But its fit came back at +829 ALMs,** four times the estimate. Two
experiment branches split the cost by building each half alone
(`exp/clip-m`, `exp/clip-d`; neither is for merging):

| variant | zseq ALUTs | ALMs | registers | DSP | slack |
|---|---:|---:|---:|---:|---:|
| B1 baseline | 9,403 | 16,743 | 19,813 | 56 | +2.207 ns |
| multiply alone, as one inferred product | **9,376** | **16,696** | **19,581** | 60 | +2.014 ns |
| radix-4 divide alone | 11,418 | 17,762 | 19,701 | 56 | +1.735 ns |
| both (the first cut) | 10,994 | 17,572 | 19,805 | 60 | +2.396 ns |

- **The multiply is free.** As a single inferred product it is *smaller*
  than the shift-and-add it replaces, and it is 32 of the 47 beats.
- **The radix-4 divide is the dear half:** about 1,000 ALMs for the
  remaining 15 beats.

**The final form** (`frontier/clip-fast`, silicon/zseq.v only): the multiply
in one beat, `cl_mac <= cl_mul * cl_dam`, taken modulo 2^82 exactly as the
82-bit accumulator took it. The divide stays serial.

| frame | B1 | B1 + final B3 (from the stack, §11) |
|---|---|---|
| brawl 226 | 551,442 | −42k of the first cut's −61k |
| tour 887 | 543,552 | −28k of the first cut's −41k |

**Verification of the final form.**
- Cross bit-equal on nearclip, bigclip, hall and tex (40 frames each).
- Routed cross bit-equal on all 521 + 901 TND frames (on the stack).
- Lint at the baseline.
- Fit 44747000736: 16,696 ALMs (90%), DSP 60, slack +2.014 ns.

**Mutation witnesses, and the hole they found in the suite.** The first
cut's mutants were where the hole showed:

| mutant (first cut) | nearclip | bigclip (new) |
|---|---|---|
| C1: a partial product one bit off | **FAIL** | |
| C2: the divide one beat short | **FAIL** | |
| C3: the digit never reaches 3 | **FAIL** | |
| C4: the top partial product (6×23) dropped | survives | **FAIL** (85,369 px) |
| C5: the high-multiplier partial (6×27) dropped | survives | **FAIL** (11,270 px) |
| C6: 3·den narrowed to 52 bits | survives | survives: **equivalent** (den ≤ 2^50) |

- **The suite never reached the top of the clipper's range.** nearclip's
  tiles are 2 units wide, so every crossing it makes is small arithmetic.
  The wide end of the old serial datapath was just as unwitnessed.
- **`carts/witness/bigclip.zol` closes that.** It is the same checker with tiles
  6,000 units wide, so adjacent vertices differ by more than 2^27 in view
  space, and the tiles cross all five planes at once. It is a suite claim
  now, so it is a standing gate.

The final form's own mutants are all killed:

| mutant (final form) | nearclip | bigclip |
|---|---|---|
| M1: the multiplier loses its high six bits | survives | **FAIL** (85,050 px) |
| M2: the distance loses its high 23 bits | **FAIL** | **FAIL** |
| M3: the product kept to 64 bits | survives | **FAIL** (81,635 px) |
| M4: the product kept to 72 bits | survives | **FAIL** (7 px, at frame 1) |

M4's margin is thin: products past 2^72 are rare even in bigclip.

## 11. The stack: B1 + B2 + B3

Branch `frontier/stack`, with B3 in its final form. Both routes cross
bit-equal on every frame.

| | build 105 | B1 | B1+B2 | **stack** | stack with the first-cut B3 |
|---|---:|---:|---:|---:|---:|
| brawl peak | 663,546 | 551,442 | 521,589 | **483,091** | 481,842 |
| brawl mean | — | 430,349 | 400,531 | **398,562** | 397,640 |
| tour peak | 686,836 | 543,552 | 516,473 | **488,429** | 482,273 |
| tour mean | — | 416,340 | 388,736 | **382,700** | 379,920 |
| frames over 480k (brawl / tour) | — | 144 / 286 | 10 / 48 | **1 / 37** | 1 / 22 |

- B2 and B3 are complementary: B3 lowers the clip-heavy frames, and B2
  lowers every frame.
- The stack's worst frame is 68% of the 720k frame and 75% of the ceiling.
- Giving up the radix-4 divide costs 1k at the brawl peak and 6k at the
  tour peak.

**Physical cost** (fit 44747007080):

| | build 105 | B1 | B1+B2 | B1+B3 | **stack** | first-cut stack |
|---|---:|---:|---:|---:|---:|---:|
| ALMs needed | 16,390 (89%) | 16,743 (91%) | 17,165 (93%) | 16,696 (90%) | **16,933 (92%)** | 17,286 (94%) |
| ALMs in final placement | 17,426 | 17,757 | 17,999 | 17,648 | **17,855** | 18,056 |
| combinational ALUTs | 26,336 | 26,575 | 26,886 | 26,549 | **26,397** | 27,139 |
| registers | 19,694 | 19,813 | 19,979 | 19,581 | **19,787** | 19,765 |
| DSP | 56 | 56 | 56 | 60 | **60** | 60 |
| M10K | 308 | 308 | 308 | 308 | **308** | 308 |
| core-clock setup slack, worst corner | +2.586 ns | +2.207 ns | +2.506 ns | +2.014 ns | **+2.468 ns** | +2.571 ns |

**Reading the table.**
- **The whole stack costs 543 ALMs** over build 105 and takes the worst
  frames from 664k / 687k to 483k / 488k.
- **Costs do not add cleanly.** B2 alone reads +422 ALMs over B1, but the
  stack is only +237 over B1+B3. The fitter packs differently as the
  design changes, so a fit says whether a configuration fits; it prices a
  single candidate only roughly.
- **The device is close to physically full.** Final placement uses 17,855
  of 18,480 ALMs. The 92% figure counts on about 900 ALMs the fitter
  estimates it could recover by packing more densely.

**Staged for glass** (each is build/pocket's cart with a different core):

| directory | core |
|---|---|
| build/pocket | build 105, the known-working one |
| build/frontier-b1 | B1 |
| build/frontier-b2 | B1 + B2 |
| build/frontier-b3 | B1 + B3 (final form) |
| build/frontier-stack | B1 + B2 + B3 (final form) |

## 12. The cost model on the stack

The same regression as §5 (1,420 frames, census against metered clocks),
on the final stack. Residual σ ≈ 13.9k, worst 78k.

| term | after B1 | on the stack |
|---|---:|---:|
| fixed | 117,065 | 97,175 |
| per submitted face | 80.1 | 70.0 |
| per drawn triangle | 30.4 | 43.6 |
| per covered pixel | 1.1 | 1.1 |

At TND's mix (2.34 faces and 172 covered pixels per drawn triangle), one
drawn triangle costs about **394 clocks**: 164 for its faces, 44 for
itself, 186 for its pixels.

| ceiling | clocks | drawn triangles it holds |
|---|---:|---:|
| 43.2 MHz, 90% | 648,000 | about 1,400 |
| 51.84 MHz, 90% (not closed) | 777,600 | about 1,730 |
| needed for 2,000 | about 885,000 | |

**What would close the gap to 2,000.**
- The clock alone is not enough: it reaches about 1,730.
- The remaining 14% has to come out of the per-triangle cost. The
  candidates are the projection divides (B6) and the clear (B4).
- The alternative is content that submits fewer faces per triangle drawn.
  Culling earlier would cut the 164-clock face share.
- All of this is extrapolation. C1 measures it.

## 13. B6: the radix-16 projection divider (rejected)

Every projected vertex pays three divides (w, x, y) of nine beats each on
one shared radix-4 divider: 55k clocks of the TND brawl's frame 226, in
band 0. A second radix-4 stage in the same beat makes it radix 16: five
beats a divide, and seven for the gradient ladder where it took thirteen.

- **Exact.** Crossed bit-equal on bunny, tex, nearclip, bigclip, lit and
  glow, and on the whole TND brawl route (521 frames).
- **Measured.** The brawl peak goes from 483,091 to 460,272, and the median
  from 405,868 to 382,519: about 23k on every frame.
- **Fitted** (run 44756570679, on top of the stack):

| | stack | stack + B6 |
|---|---:|---:|
| ALMs needed | 16,933 (92%) | **17,919 (97%)** |
| zseq combinational ALUTs | 9,205 | 11,143 |
| core-clock setup slack, worst corner | +2.468 ns | +1.960 ns |

- **Rejected.** 23k clocks is 5% of a frame. A thousand ALMs is more than
  everything else in the stack put together, and it takes the device to
  97%.
- **The estimate was wrong again, the same way.** I guessed about 100 ALMs
  for three more subtractors and a multiplexer; the clipper's radix-4
  divide was guessed at 200 and fitted at 1,019. Divider stages cost about
  a thousand ALMs each on this device, for reasons the reports kept so far
  do not show. The map report is the place to look before anyone tries a
  third.

The branch `exp/div16` holds it, for a device with room.

## 14. C1: the stress scene

**The method.** `TND_STRESS=n` is a local build flag (like `TND_OMIT`). It
lists n extra demons, each a render-only clone of a real one in its pose,
standing a stride beside it. No game state changes, so a route plays
identically and each frame compares one for one with the unstressed
build. The stressed brawl crosses bit-equal (300 frames).

**One extra demon** (measured on the stack, brawl route):

| | TND | TND + 1 demon | change |
|---|---:|---:|---:|
| objects listed (of 64) | 49–51 | **61–63** | +12 |
| faces submitted | 2,136 | 2,510 | +374 |
| vertices transformed (frame 359, of 2,048 cached) | 1,657 | 1,911 | +254 |
| drawn triangles (frame 359) | 933 | 1,128 | +195 |
| frame clocks, median over the route | — | — | **+32,254** |
| frame clocks, worst case | — | — | +44,755 (frame 359) |
| brawl peak | 483,091 | 513,075 | still under the 648k ceiling |

**What it shows.**
- **Geometry scales linearly, with no cliff.** One demon is about 32k
  clocks: 86 clocks per submitted face, 165 per drawn triangle. Demon
  triangles are small, so they cost less than the route average of 394.
- **On clocks alone there is room for about four more demons.** The
  ceiling has 135k of headroom at the stressed peak. That would put the
  fight near 1,900 drawn triangles.
- **Two structural limits bind first.**
  - **The object list holds 64.** The fight lists 49–51 and a demon is 12
    parts, so exactly one more fits. A second cannot be listed at all.
  - **The vertex cache holds 2,048.** The fight transforms 1,657 and a
    demon is 254, so the cache overflows midway through the second extra
    demon. Past that, an object is re-transformed in every band.
- **So the answer to the 2,000 question has changed shape.** After the
  stack, clocks are no longer what stops TND's combat scene from doubling.
  The object list and the vertex cache are. Both are memory, and block RAM
  is full (B8).

## 15. B5: the 51.84 MHz clock (fitted, and witnessed on the Pocket)

Branch `frontier/div6`. Six clocks a pixel where there were five: the
frame is 864,000 clocks where it was 720,000, and the 90% ceiling 777,600
where it was 648,000. Staged for glass in build/frontier-div6.

**The PLL.** The old notes said the faster clock "needs the second PLL",
and a first timing-only fit confirmed where that came from: with the core
moved to 51.84 MHz the fitter rejects the audio output's 12.282352 MHz as
illegal. One PLL does it at a different VCO, 51.84 × 23 = 1192.32 MHz:

| output | divider | frequency |
|---|---:|---|
| core | 23 | 51.84 MHz |
| dot clock | 138 | 8.64 MHz |
| audio | 97 | 12.291958 MHz: 0.033% from 12.288 (the 12.282352 it replaces is 0.046% off) |

**What followed the clock.**
- zeta_glass's DIV goes 5 → 6. Everything it times was already written in
  DIV: the dot strobe, the scanout's line bursts, and the audio strobe
  (180 × DIV = 1,080 clocks a sample).
- The budget gate's frame is 864,000 clocks.
- The PSRAM's latency is a clock count and needed no change. Its pins meet
  timing with about 5 ns to spare.

**Timing closure.** The CI's failing-fit testimony was changed to tally
every violated path by family (it printed three paths a corner). Each fit
then named the next layer:

| fit | worst setup slack | families it named | the fix |
|---|---:|---|---|
| 1 | −1.835 ns | the rasterizer's box test (218 paths) | the box extents take a register: one clock a triangle |
| | | the edge seed's multiply (574) | its operands take a register: no extra clocks |
| | | the scanout compositor's lerp (8) | the winning rectangle takes a register |
| 2 | −1.625 ns | the audio mixer's sixteen-way sum (800) | four partial sums registered; the sample lands a clock later |
| 3 | −0.595 ns | the vertex rotation (719) | the four products registered: six clocks a vertex |
| | | the blend into the tile's colour (37) | the colour to write takes a register |
| **4** | **+0.901 ns** | none | **every corner met** |

**The fit** (run 44783525113):

| | the stack at 43.2 MHz | B5 at 51.84 MHz |
|---|---:|---:|
| ALMs needed | 16,933 (92%) | 16,962 (92%) |
| DSP | 60 | 60 |
| setup slack, slow 85C / 0C | +2.468 ns worst | +0.901 / +0.954 ns |
| hold slack, worst (fast 0C) | — | +0.089 ns |

**Verification.**
- Every fix crossed bit-equal on the stress carts as it went in. The last
  set passes on glow, bunny, tex, lodspan, nearclip, bigclip, lit, fabric,
  vessel, banked and pickfloor.
- Audio: sample streams bit-equal on choir, voice, vessel, tnd, tex, pulse
  and band (40 frames each).
- The glass gate passes at six clocks a pixel (fade, tex, vessel).
- TND's brawl route crosses bit-equal, all 521 frames.

**What it buys TND** (brawl route, silicon meter):

| | the stack, 43.2 MHz | B5, 51.84 MHz |
|---|---:|---:|
| peak, clocks | 483,091 | 494,240 |
| the frame | 720,000 | 864,000 |
| peak as a share of the frame | 67% | **57%** |
| headroom under the 90% ceiling | 164,909 | **283,360** |

The pipeline registers cost about 11k clocks a frame. The clock gives
144k. By the stress scene's measure (§14, about 32k a demon) the headroom
is worth nearly four more demons than before, if the object list and the
vertex cache let them in.

**WITNESSED ON THE POCKET (2026-11-20).** The film, the shelf and TND ran
on the 51.84 MHz core with the save intact. The player's report: it
"plays a lot smoother", and the first SSS followed.
- The PSRAM pair holds at the faster clock, and the audio is right.
- **"Smoother" is a finding against the meter.** The brawl and tour routes
  showed no frame over the ceiling on the 43.2 MHz stack, so real play
  reaches heavier frames than either route does. The routes are scripted
  pads, and a player's fight is not. The meter is owed a route recorded
  from real play (the pad-log tape, `zeta sd witness --tape`), and until
  it has one, "no frames over the ceiling" describes the routes only.
- **(Later the same day: it got one, and this inference did not hold.
  See §18. Real play peaked 5% above the brawl route, nowhere near
  either clock's ceiling.)**

## 16. Past 51.84 MHz: where the clock stops today (measured, deferred)

Two timing-only fits of the unchanged RTL, to find the next wall
(`exp/div7-timing`, `exp/div8-timing`; nothing merged, nothing on glass).

| | clocks a pixel | frame, clocks | worst slow-corner setup | result |
|---|---:|---:|---:|---|
| 51.84 MHz (main) | 6 | 864,000 | +0.901 ns | closes |
| 60.48 MHz | 7 | 1,008,000 | −1.477 ns | fails |
| 69.12 MHz | 8 | 1,152,000 | −3.020 ns | fails |

Both fit in the same logic (16,977 and 16,974 ALMs, 92%), and the fast
corners pass with more than 2 ns to spare. The slow corners are the wall.

**What stands between here and 60.48 MHz** — three families:

| Worst | Paths | From → to | What it is |
|---:|---:|---|---|
| −1.477 ns | about 750 | program data memory → the sequencer's `nlev`, `fcached` | a block-RAM read used the same clock it arrives, through the level and fit logic |
| −1.134 ns | 32 | `cram0_dq`, `cram1_dq` pins → the burst reader's `r_data` | **the frame memory's own access time** |
| −1.088 ns | 16 | texture memory → `s2_col` | a block-RAM read into the texel's colour |

- The first and third are the kind §15 closed: register the read, pay a
  beat. The sequencer's is on the geometry pass, so the beat is paid per
  vertex and per object.
- **The second is not logic.** The PSRAM is constrained at 9.0 ns from
  its clock to valid data. At 60.48 MHz that leaves 7.5 ns of a 16.5 ns
  period for the board, the pin and the route. Closing it needs the
  capture moved (a phase-shifted clock, or a fast input register and a
  re-timed burst), and that is a change only glass can witness.

At 69.12 MHz the rasteriser's own arithmetic joins them (`gg_sel` → `gm`,
`cacc` → `rr0`, `eacc` → `px`), and the glass's line buffer. That is a
redesign of the pixel pipeline, not a round of registers.

**Disposition: deferred, not rejected.** 60.48 MHz is one round of
registers and one change to the frame memory's capture away, for a sixth
more clocks a frame. Nothing measured asks for them yet: TND's heaviest
scripted frame uses 58% of today's frame. The first tapes of real play
(§15's finding) decide whether this is worth its glass risk. 69.12 MHz
is rejected for this pipeline.

## 17. The device was fuller than its headline, and B9: the event list as memory

**The recorder's fit failed** (`platform/tape`, 01e4b1d): −0.184 ns in the
slow corners, six paths, all `cram0_dq` → `r_data`, the frame memory's
read capture. The recorder is 194 ALUTs and 191 registers. It should
have had room.

**It did not, and the headline hid it.** Quartus's "Logic utilization"
is not what is placed. It is *needed* = placed − recoverable by dense
packing + unavailable, and the middle term is a guess:

| Fit | placed (A) | recoverable (B) | headline |
|---|---:|---:|---:|
| main, 1cafa9c | 17,717 | 1,276 | 16,962 (92%) |
| + the recorder | 17,960 | 220 | 18,273 (99%) |

Placement grew by 243. The headline grew by 1,311: when the fitter had
to pack densely, most of the ALMs it had promised were not there (and
under timing pressure it duplicated logic: `zseq` went from 9,901 ALUTs
to 11,197 with its source unchanged). The device holds 18,480. Main was
96% placed while it read 92%.

**From here on a fit is quoted with both numbers.**

**A fix that did nothing.** `FAST_INPUT_REGISTER` on the 32 frame-memory
data pins, to take that path out of the fitter's hands. Quartus ignored
it (warning 176250) and the refit was identical to the picosecond; the
same on the 60.48 MHz experiment. The capture register sits inside
`cram_burst`'s state machine. Pinning it needs a dedicated register and
a re-timed burst: a glass change, not an assignment. Reverted.

**B9: the audio event list as two memories (fitted; not yet on glass).**
Looking for room in `zsnd` (2,400 ALMs, 3,669 registers) found that the
voices were not the cost. The event list, one array read at `1+2p` and
`2+2p` in the same clock, had never become a memory: the map report
lists `evm~N` as registers, with two wide multiplexers to read them. An
event's two words are read together and written apart, so each now has
its own MLAB (`evm0`, `evm1`).

| | main | B9 |
|---|---:|---:|
| `zsnd` registers | 3,669 | **1,133** |
| `zsnd` placed, ALMs | 2,827 | **1,592** |
| design placed (A) | 17,717 | **17,252** |
| headline | 16,962 | **16,318 (88%)** |
| worst slow-corner setup | +0.901 ns | +0.640 ns |

- No behaviour changes: lint at 111; choir, voice, band, pulse and
  vessel cross bit-equal for 40 frames, picture and sample stream (band,
  pulse and vessel drive events).
- `zseq` spread into the room (placed 6,627 → 7,156 with 680
  recoverable), so the design gave back 466 placed ALMs where `zsnd`
  alone gave 1,235.
- **WITNESSED ON THE POCKET (2026-11-20, build 106):** TND's sound is
  right, by ear, with the event list in its two memories. Build 106 is
  B9 plus the recorder: 17,212 ALMs placed (headline 16,968), worst
  slow-corner setup +0.795 ns.

**Still in block RAM for no reason:** the sixteen wave tables are 2,048
bits each and sit in sixteen M10K blocks (of 308, all used). One merged
table would need four. That is a serial mixer, and it is the next place
to look when block RAM is what is short.

## 18. The first tape of real play, costed (2026-11-20)

§15 ended on a debt: the meter had only scripted routes, the player had
felt 51.84 MHz "a lot smoother" where the routes showed no frame over the
ceiling at 43.2 MHz, and so "real play reaches heavier frames than either
route does". The recorder (build 106) paid the debt the same day. The
conclusion did not survive it.

**The session:** 3 m 33 s of TEAR NOT DEMON on the Pocket, launched from
the Pocket's menu, the film in front. 12,776 frames, 1,397 changes of the
pad. Replayed on the law from the save it started with, it leaves the
save the Pocket was left with and ends where the player quit, on the
title. (The save did not change in this session, so that gate was weak;
see PLATFORM.md.)

**Costed** on the RTL's own meter, every frame, in 54 parallel windows
each started from the law's state (`zeta profile`, 17 m 42 s; about two
hours serially):

| | scripted brawl | real play |
|---|---:|---:|
| frames | 521 | 12,776 |
| peak, clocks | 499,077 | **524,813** |
| peak, share of the frame | 58% | **61%** |
| median | 48% | 44% |
| frames over the 90% ceiling | 0 | **0** |
| frames over the frame | 0 | **0** |

- Real play's heaviest frame is 5% heavier than the script's. Its middle
  is lighter. 13 frames of 12,776 pass 500,000 clocks.
- The heaviest frames are geometry-bound, as brawl's are: in the fifty
  heaviest the rasteriser idles 165k clocks waiting on the sequencer and
  walks 170k.
- The film peaks at 48% of the frame.

**So the meter was right, and §15's inference was wrong.** No frame of
this session would have crossed the 43.2 MHz ceiling either (648,000;
none passes 525,000 here, and the counts at 43.2 MHz run about 11k
lower). The object list caps a fight at four demons, so the scripted
brawl was already near the worst a fight can be.

**"Smoother" is therefore unexplained.** It was a real report and it is
not dropped frames. What differed between the two cores on glass, besides
the clock's headroom, is everything §15 changed to close timing: the
dot-clock divider (five core clocks a pixel to six), the PLL plan, the
compositor's registered winner, and the audio's mix timing. None of
those is known to change pacing. The honest test is on hardware, varying
one thing: the 43.2 MHz core is kept (`build/pocket-stack-43.rbf_r`),
and the same cart can be played on both.

**What this session does not cover:** it is one session of three and a
half minutes. It is a floor on what play can cost, not a ceiling.

**The tape is not in the repo.** It was recorded on the song build,
whose theme is third-party and local; its cart sum names a file CI
cannot rebuild. The tape library that judges silicon changes must be
recorded on the committed cart.

## 19. Program memory in the SRAM, behind an instruction cache (planned, measured)

TND fills program memory: 8,151 of 8,192 words after P18. The player's
next asks (on-screen affordances, attack tokens, a crowd fought through as
a window over hundreds) do not fit, and "we've got to make deep games".
Block RAM is full (308 of 308 M10K), so IMEM cannot simply grow.

**Proposal:** the program lives in the Pocket's SRAM, the VM fetches through
a small instruction cache, and the 8,192-word IMEM in block RAM goes away.

**Measured first** (the law's own fetches, 2,400 frames of the player's
10m44s P18 session): a median of 24,316 instructions a frame, 45,118 at
the 99th percentile; 7,398 distinct words touched in all. A direct-mapped
cache simulated over those fetches, a word costing 6 clocks from the SRAM
(two halves, three clocks each, as the recorder runs it):

| cache | line | misses/frame (max) | stall, worst frame | of the frame |
|---:|---:|---:|---:|---:|
| 512 words | 4 | 1,371 | 35,646 | 4.1% |
| 1,024 words | 4 | 1,144 | 29,744 | 3.4% |
| 2,048 words | 4 | 971 | 25,246 | 2.9% |
| 4,096 words | 4 | 534 | 13,884 | 1.6% |

The heaviest real-play frame uses 61% of the frame (section 18). A
1,024-word cache costs at most 3.4% more and needs 4 M10K where IMEM holds
about 26: some 22 blocks come back for scene capacity.

**The shape:**
- `IMEM_WORDS` 8,192 to 32,768 (128 KiB of the SRAM's 256). The tape moves
  to the SRAM's top 64 KiB. PC and return addresses widen to 15 bits; the
  24-bit immediate already reaches.
- zvm fetches from a 1,024-word direct-mapped cache, 4-word lines; a miss
  stalls the VM while one line (eight 16-bit reads) is fetched.
- One SRAM controller in the console domain, arbitrating: a cache refill,
  then the loader's and the overlay mover's IMEM writes (which invalidate
  the cache), then the recorder.
- The law is unchanged in behaviour: a cache changes when an instruction
  arrives, never what it does. Machine 2 gets an SRAM model in the
  harness; the meter then counts the stalls.
- Costs to the format: the snapshot grows by 96 KiB of IMEM (157 to 255
  KiB, about 2.5 s at the Pocket's save rate); each cart file's IMEM
  section grows to the new size unless the file format learns to carry
  only the program's length.

**Gates, in order:** law and spec (every test, regen); machine 2 crossing
bit-equal with the cache in the loop; a CI fit; glass (boot, play, a tape
replayed exact, the recorder still writing).

**WITNESSED ON THE POCKET (2026-11-21, build 107).** Fitted with seed 3
(seed 7 missed the frame memory's pin path by 0.057 ns and a fast hold by
0.008; seeds 3 and 19 met every corner, 11 did not): 17,469 ALMs, 281 of
308 M10K -- IMEM gave back 27. On glass the player's verdict: "looks
good". The core booted from the Pocket's menu, the film played into TND,
the game ran with a main program of 8,181 words (past the old ceiling),
and the recorder -- now the SRAM's guest -- wrote a 4m29s tape, build 107,
carrying the staged cart's sum. On the desktop the cache cost TND's brawl
route 24k clocks at its peak (60% of the frame, from 57%), as the model
said.

## 20. Meshes drawn from the cart (experiment, the law only; exp/cart-mesh, 2026-11-22)

**What asked for it.** TND's enemies are to be the player's own body at
several sizes, the hardest of them a second full player. A full body is
2,969 words of a DMEM with about 11,700 to give, and its pose is 2,967
words of mover every frame it changes -- and layer 3 had 374 words free.
Every mesh is drawn from DMEM, so every posed body is COPIED there first.
But the pose bank already is the meshes, in a cart memory of four million
words that reaches the picture only through that copy.

**The amendment** (spec.OBJ_CART, flags bit 14). The object's mesh word is
the DMEM address of a five-word descriptor, and the mesh is read from the
cart's segment in three streams: vertices (16 bits a coordinate, shifted),
faces (one word each, shared by every pose and every body of the build),
colours (5:5:5, a half a face -- the baked shading, as it was). A pose is
two offsets written. Flat faces only; cull, outline and the object tint as
ever. In the house's terms it is the vertex walk given the window the
mover and the backdrop already have: a `cram_burst` front end, not an
engine.

**Proved in the law** (tests/test_cart_mesh.py): a mesh from the cart is
the same picture TO THE PIXEL as that mesh in DMEM -- five placements,
through the clipper, outlined, tinted; through the segment window; two
poses by offsets alone; and a descriptor or a stream outside its memory
draws nothing.

**TND on it** (TND_CARTMESH=1, layer 3, the law):

| | as it is | from the cart |
|---|---:|---:|
| DMEM free | 374 | 3,333 |
| a pose, words | 2,967 | 1,115 |
| the bank (663 poses), words of CRAM | 1,967,121 | 739,245 |
| mover requests a frame | 1 (2 with the song) | 0 |
| the picture, 461 frames of play | -- | a median of 3 pixels of 92,160 differ (worst 18): the vertices rounded to 16 bits |

And a SECOND full fighter (the rival: the same bank, his own two
descriptors and pose clock) costs eleven words of DMEM and four offsets a
frame: 3,322 free with both on the street.

**The program's page.** IMEM is 32,768 words; the cart's page was 16,384
by its own choice (a page-in is 16K words, a frame's work at the SRAM's
pace). The experiment's page is the whole of IMEM: the title, the fight,
the pause and back all run in the law. On the machine a page-in would be
about two frames, on the frames the pause comes and goes -- unmeasured.

**Not done: the silicon.** Nothing here is in zseq/zgpu. What it needs
there: the descriptor read, the three streams burst from the PSRAM before
the vertex walk (the mover moves up to 8,192 words in that gap today; two
full bodies are about 2,250), 16-bit sign-extend-and-shift on the way in,
and the face walk reading indices and colours from where the streams
landed. Its cost is unmeasured until it is fitted. With bodies out of
DMEM, the frame's 2,048-vertex store becomes the head-count's limit, and
DMEM (52 M10K) could give some of itself to it.

**How many fit** (2026-11-22). The sizes below the player, cut from the
archive's full-resolution body by its own pipeline (tear-charkit; the tier
files are local, build/tiers): the rival 459 vertices / 737 triangles (the
player's own), an elite 243 / 369, a common 172 / 252, the horde 109 / 150.

*On the silicon* (a cart that stands N of one size in ranks 3 to 11 units
before a lens like the game's, one more every four frames; static bodies
in DMEM standing in for the cart's, the same geometry):

| a body | inside the vertex store | past it |
|---|---:|---:|
| the rival (a second player, beside him) | about 6% of the frame | -- |
| an elite | 27,000 clocks, 2.9% | 69,000, 8% |
| a common | 18,000, 2.1% | 46,000, 5.3% |
| the horde | 11,500, 1.3% | 23,000, 2.7% |

About 75 clocks a triangle, near or far: setup, not fill. And the cliff is
the frame's 2,048-vertex store (zseq VB_CACHE): past it every further body
is re-transformed in each band and costs two to three times as much.

Layer 3's own frame is at most 12 objects of 64 and 1,012 vertices (median
766), peaking at 56% of the frame. So TODAY'S ceiling is about 1,000
vertices of enemies, any of: nine of the horde; six commons; four elites;
the rival and three commons; an elite, two commons and four of the horde
-- each about 68% of the frame by these costs. Three of those stand on the
street in the law (TND_CROWD, each body on its own clock in its own idle):
1,862 to 1,904 vertices a frame, 15 to 19 objects, 3,277 or more words of
DMEM still free.

With the store doubled (it is about 17 M10K; 27 are free -- unfitted), time
is the limit: to 90% of the frame, about twenty-six of the horde, or
sixteen commons, or the rival with two elites, four commons and ten of the
horde. Estimates from the per-body costs, not a metered scene; the cart's
streams' own fetch is not in them.

**The balance: the city as it is, items, and the UI** (2026-11-22; the
player: "I like the city how it is rn, but also more items, and room for
better ui and menu systems"). Metered on the silicon, layer 3, a walk
through the town (the lit city, the player, no enemies):

| | median | peak |
|---|---:|---:|
| the frame | 434,060 clocks (50%) | 532,879 (62%) |
| the clear | 97,674 (11.3%) | the same |
| the town in view | 225 vertices, 146 faces | 455 vertices, 302 faces |
| everything else from meshes (him, the ground, shadows, the key) | 541 vertices | 557 |
| display-list triangles | 1 | 1 (of 256) |

- **An item is all but free in time**: an eight-face thing, spinning, 594
  clocks (0.07% of a frame); forty of them 2.8%. What it spends is the
  vertex store (its vertices) and an object (of 64).
- **Text is the dear thing**: a display-list triangle is about 300 clocks
  whatever its size, a 3x5 character 6.8 of them -- 2,000 clocks, 0.23%
  of a frame. The list's 256 triangles are about 37 characters and 8% of
  a frame. A menu of two hundred characters does not exist in this
  primitive. What does: a full-screen plate from the cart (any picture,
  any amount of baked text, about 136,000 clocks against the clear's
  98,000), the compositor's four translucent rectangles at scanout (free),
  the list's 37 live characters over them, and a program page of its own
  (as the pause has).

The split this gives, keeping the city (per frame, at the WORST town frame):

| | the vertex store (2,048) | the frame |
|---|---:|---:|
| the city, the clear, the ground | 455 + ~90 | 56% |
| the player | 469 | 6% |
| items (a dozen or so) | 120 | 1.5% |
| the HUD in play (100 triangles: 15 characters and meters) | -- | 3.5% |
| the enemies | 916 | to 90%: 23% |

By vertices today: eight of the horde, or five commons, or the rival with
two commons and one of the horde -- about 78% of the frame at its peak.
With the store doubled the 23% is the limit: seventeen of the horde, or
eleven commons, or the rival with four commons and six of the horde.
(Sums of per-body costs, as before.)

The rest: DMEM keeps the city's 5,660 words and has about 3,300 free once
bodies are drawn from the cart (the HUD can have back the display list's
tail the game borrows for tables); the program's page is 32,768 against
the game's 16,300; the cart is about 2.7 M words of 4.06 M with the song
and is about 1.5 M with 16-bit poses -- room for the enemies' own pose
sets and for a plate (92,160 words) a menu screen.

**The silicon's shape for it** (planned 2026-11-22; none built). The
law's cart mesh is drawn from a STORE the silicon fills once a frame:

- *The store* (new block RAM, the law's CM_VMAX / CM_FMAX): vertices as
  the cart holds them, 1,536 x 3 x 16 bits; face indices 2,560 x 30;
  colours 2,560 x 15 -- about 20 M10K of the 27 free. Derived every frame
  from DMEM and the cart, so it is not machine state (spec.STATE is
  untouched; a resumed frame reloads it).
- *The loader* (zeta_top, at the movers' instant, after DMA, DMA2 and
  the overlay): walk the object list; for each OBJ_CART object read its
  five descriptor words, apply the law's refusals (the descriptor inside
  DMEM, nv / nf / shift, the three spans inside CRAM_WORDS through
  SEG_BASE, the store's running totals), give it a place in the store and
  burst its three streams there with the mover's own engine (a
  destination select beside dma_imem). Per object, kept for the frame:
  admitted?, nv, nf, shift, its vertex base and face base.
- *The sequencer* (zseq) reads a cart object's mesh through the port it
  has: one more bit beside rd_addr (and the object's index) says "this
  object's mesh, word k of [nv, nf, 3 words a vertex, 2 words a face]";
  an adapter serves it from the store -- a vertex half sign-extended and
  shifted, a face's index word, its colour widened to 24 bits -- in the
  same two states. In zseq: at S_OT1 an OBJ_CART object not admitted is
  skipped as an invalid mesh is; an admitted one takes mb_s = 0 and its
  gouraud / lit / texture / tint / blend bits are masked off. Nothing else
  in the walk, the bins, the vertex cache or the clipper changes.
- *Its time*: the streams for the balance above are about 5,000 words a
  frame beside the mover's 8,192 allowed today -- to be metered.
- *Proved by* the cross on a witness cart and on TND's cart-mesh build,
  then fitted (exp branch, CI). The larger vertex store is a second
  experiment, fitted alone.

**In the silicon** (2026-11-22; zmesh.v, the loader in zeta_top, rd_cart on
zseq -- as planned above). Proved on the simulation:

- `carts/witness/cartmesh.zol` (the lens turning; culled, outlined,
  object-tinted lumps; one through the near plane; two poses swapped by
  their offsets; a refused descriptor; a rank that overruns the store, and
  a small one after it; a DMEM mesh among them): 40 frames, law and
  silicon the same to the pixel.
- TND's cart-mesh build from a state by the key (the lock, shots, the
  boxer round it, aiming): 288 frames the same.
- bigclip, edged and cube: unchanged.

And the scenes METERED, not summed (the street from power-on, 111 frames;
the lit street's own open mismatch is the same 171 pixels a frame in every
one of these builds, the plain one included -- the cart's meshes add none):

| on the street | median | peak |
|---|---:|---:|
| layer 3 as it is (the body in DMEM, the mover) | 50% | 60% |
| the body from the cart, and the rival | 58% | 68% |
| ...the rival and three commons | 66% | 76% |
| ...an elite, two commons, four of the horde | 64% | 73% |
| ...nine of the horde | 63% | 72% |

(The sums above said +12% for each crowd; the meter says +12 to +16 over
the plain build, the streams' fetch and the loader's walk in it. A body
far out of view still costs its transform and its face walk: the game's
own view cull belongs on the enemies as it is on the town.)

**Fitted** (2026-11-22, four runs on CI; seed 3, the frontier's):

| run | what it said |
|---|---|
| 45058233664 | 99,937 ALMs, 541%: two of the store's memories were written from two statements in one block (a word's low half, then its high) and were built from registers -- 112,000 of them |
| 45063239914 | the logic is small (zmesh 242 ALUTs, 108 registers) but 320 M10K of 308: vertices as 4,610 halves and faces 2,562 deep do not pack |
| 45065195927 | placed -- 17,611 ALMs (95%), 299 M10K -- and a nanosecond over at both slow corners: the store's RAM -> its mux -> the lit normal's three multiplies -> `nlev` (a cart mesh is never lit; the path only existed) |
| 45067440312 | **PASS, every corner**: 17,761 ALMs placed of 18,480 (96%), 299 of 308 M10K |

| corner | setup | hold |
|---|---:|---:|
| slow 85C | +0.223 | +0.287 |
| slow 0C | +0.156 | +0.284 |
| fast 85C | +5.419 | +0.094 |
| fast 0C | +5.739 | +0.009 |

So drawing from the cart costs about 300 placed ALMs and 18 blocks over the
frontier's 17,469 and 281, and the margins are thin (the frontier's own
were +0.9 setup and +0.09 hold). The store is the block RAM's shape now --
2,048 vertices as 48-bit words, 2,048 faces -- and the law says the same
(spec.CM_VMAX, CM_FMAX). Nine blocks are left: the 2,048-vertex frame
store cannot be doubled beside this (it is about 17) without finding
blocks elsewhere. Not yet on glass.
