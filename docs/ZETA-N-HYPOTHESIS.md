# The Zeta-n hypothesis

Why this console is built the way it is, stated so that it can be tested
and so that a later session can tell what is established from what is
hoped. Written 2026-11-23 from the developer's proposal of that date; the
facts are this repository's, with their files.

## The hypothesis

- **H** is the fixed machine: the Analogue Pocket's Cyclone V
  (5CEBA4F23C8: 18,480 ALMs, 308 M10K blocks, 66 DSP blocks), its
  memories, its panel, its pad, its card.
- **Aₙ** is the architecture at generation n: the law (`zeta/spec.py`,
  `zeta/vm.py`, `zeta/gpu.py`) and the silicon that implements it
  (`silicon/`).
- **C(H, Aₙ)** is what a cart can do on it.

The hypothesis: by finding cheaper representations, schedules and
structures, **C(H, Aₙ₊₁) can exceed C(H, Aₙ) with H unchanged** -- and
some of those optimizations do not make an old operation faster but
expose an operation that did not exist.

It is a research hypothesis. It is not a claim that the frontier is
unbounded, and every generation must be free to answer "no, not this
one".

## How it has been worked

The same six steps, many times (the generations are the numbered
sections of `docs/ZETA0-FRONTIER.md`; the discipline is
`methods/README.md`):

1. a working, deterministic implementation -- the law in Python, the
   silicon in Verilog, **bit-equal** to it (`zeta cross`);
2. measure: the fit (`infra/fit_ci.py`, four timing corners), the frame
   meter (`zeta profile`, `zeta budget`), real play (`zeta sd tape`,
   `zeta replay`);
3. find what is wasted, repeated or carrying no information;
4. change the architecture while its contracts hold;
5. look at what became possible;
6. build that, and go round again.

## What is implemented, measured, hypothesised and proposed

### Implemented (in the law and the silicon, crossed)

Cases where an optimization left a **new primitive** behind. Each is in
the tree; none is offered as proof of the general claim.

| What was being saved | What it turned out to be | Where |
|---|---|---|
| a spare bit of the backdrop's plate word | the room's shadow mask, read per pixel | `zeta/spec.py` `BG_SHADOW` |
| the object-id and depth the rasteriser already keeps | PICK: which triangle owns a pixel, answered to the cart | `spec.PICK_X/Y/ID/Z` |
| the same id buffer | an outline round any object | `spec.OBJ_EDGE` |
| counts the scanout already makes | VIS: how much of each object reached the glass, returned to gameplay | `spec.VIS_BASE` |
| the mixer's own levels | AUD: what is sounding, returned to gameplay | `spec.AUD_BASE` |
| data memory the fighter's pose was copied into each frame | meshes drawn from the cart: a pose is two offsets, and a second and a seventh body fit | `spec.OBJ_CART`, `silicon/zmesh.v`, FRONTIER 20 |
| a body cut in two to fit the 256-vertex mesh | two halves posed apart: the gun held ready over any legs | `games/tnd/gen_tnd.py` (P43) |
| nothing stored for a world he is not in | a pack's place as a pure function of the clock; six bits for what he changed | `gen_tnd.py` (P41), `carts/witness/gen_fabric.py` |

### Measured (numbers this repository can reproduce)

- The core as fitted on 2026-11-23 (CI run 45100833653): 17,934 of
  18,480 ALMs (97%), 299 of 308 M10K, 60 of 66 DSP; worst setup
  +0.395 ns, worst hold +0.099 ns, four corners.
- A frame is 864,000 clocks at 60 Hz (`zeta/budget.py`
  `FRAME_CLOCKS`); the gate's ceiling is 90% of it. TEAR NOT DEMON's
  layers run at 47-67% at the median, 53-77% at the peak (TND-PORT
  P37-P42), on the silicon's own meter.
- Drawing bodies from the cart cut a pose from 2,967 words to 1,115 and
  the fighter's cost in data memory to ten words (FRONTIER 20).
- 35 witness carts, each crossed bit-equal against the law, each
  claim's own mutation checked (`zeta/suite.py`).
- Estimates against fits (`methods/ledger/ledger.tsv`): logic guesses
  ran from a third of what was fitted to ninety times it, which is why
  the method is "fit before pricing".

- **One architecture, filled** (TND's lab, P42-P56, `experiments/isa/`):
  seventeen commits of new capability with the law and the silicon
  unchanged. What binds is PROGRAM SPACE (28,916 of 32,768 words), not
  time (frame peak 58-65%, instructions about 27,000 of 65,536). Five
  spelled-out idioms as instructions would give back 2,635 words (9.1%)
  and only 4.8% of the instructions: a prediction for A(n+1), not yet
  tested.

### The limits met so far (evidence against "always")

- Doubling the frame's vertex cache wants about 17 M10K; 9 are free
  beside the mesh store. It does not fit.
- The cart-mesh store failed three fits before it was reshaped to
  2,048 x 2,048 (FRONTIER 20).
- The older `zeta-ps15` tree's "memory fabric" measured 20 M10K on its
  own; this core has no room for it as hardware.
- Timing closed at +0.1 ns hold. There is no slack to spend carelessly.

### Hypothesis (not established)

- That optimization keeps revealing primitives rather than only speed.
- That the capability frontier of this one part is still far from where
  the design stands.
- That player-driven requirements (below) and architectural
  optimization drive each other usefully.

### Proposed (not built)

- **Zeta-n**: successive generations Aₙ recorded as such, each with its
  capability list, its resource table and its witnesses, so that
  C(H, Aₙ₊₁) > C(H, Aₙ) is a comparison between two written things.
- A stream table for this core (next section).

## The machine as bounded streams

Everything the console does is a stream with a rate, a burst, a phase in
the frame, a latency, a store and a deadline. What this repository
actually uses to reason about them:

- **The frame's deadline**: 864,000 clocks. Averages do not count; the
  budget gate takes the worst frame of a route (`zeta budget`).
- **The frame meter**: the silicon's own stage counters, read per frame
  -- `clr`, `walk`, `idle`, `stall`, `seq`, `blkd`, `skp`
  (`zeta/profile.py` `STAGES`). `zeta profile` costs a whole recorded
  session by replaying it on the law and running windows of it on the
  simulated hardware from the law's state images.
- **Stores with stated capacities**: 2,048 vertices and 2,048 faces a
  frame in the mesh store, 64 objects, 256 display-list triangles, the
  program page, data memory. A request past a store is refused in a
  legislated way, never undefined (`tests/test_cart_mesh.py`).
- **Legislated latency** where the world is variable: a card transfer
  lands `spec.SD_LATENCY` frames after it is asked for, on both
  machines, so memory never depends on how fast a card was.

**On "Smith" analysis.** This repository has no Smith table and no
Smith chart. They are in the two older trees, and they are not the
electrical chart:

- `zeta/docs/CANON.md` section 2 calls the machine's state of knowledge
  "the Smith plot"; `zeta/src/zeta/cli/plot.py` draws it. It is a polar
  plot with **one sector a resource** and **radius = 1 - derate**, where
  the derate is the measured fraction of an arithmetic budget that
  survives in the fitted machine. The centre is a perfect match; the
  edge is the worst case, and a missing measurement is drawn AT the
  edge. Measured points are solid and assumed ones dashed. The canon's
  own caution: "the chart rejects reliably and confirms nothing; every
  interior point is a hypothesis until fitted."
- `zeta-ps15/smith/table.json` is the ledger behind it: rows of two
  kinds never added together -- `rate` (cycles a frame against a fuel
  budget) and `area` (ALMs, M10K, DSP from a real fit) -- each with its
  provenance (measured, assumed, open).

The equivalent here is spread over `zeta budget`, `zeta profile`, the
fit reports and the tables in FRONTIER. Bringing a single stream table
back -- rate rows and area rows, provenance on each, the chart drawn
from it -- is proposed, not done.

## How to hold this hypothesis while working

- A capability claim needs a witness cart and its mutation
  (`methods/README.md`, law 1) and, if it costs logic, a fit at four
  corners. Until then it is a proposal.
- Record the generation that said no as carefully as the one that said
  yes.
- The second loop -- what players do with the machine -- is
  `docs/EXPERIENCE-IMPRINTING.md`. A requirement that comes from play
  enters this loop as a requirement, and is measured like any other.
