# The reciprocal machine: one retina, one field, one seal -- a design

**Status: a design. Nothing in it is built, crossed, fitted or even mocked.** Written 2026-11-28 as an
alternative A(n+1) on the same H (the Pocket's Cyclone V), in answer to "a design that pushes the console
to something unique, alien and above its competitors". It was written from outside: from `main` at
`4c308f6` (2026-11-20) and from the text of the Zeta-1 design, without the density experiments and without
the current silicon. The working name is a placeholder.

Every number is marked:

- **[r]** read from the repository at `4c308f6`;
- **[d]** taken from the Zeta-1 design document and not checked;
- **[a]** arithmetic done here from [r] or [d] figures;
- **[s]** supposed.

No ALM figure appears, because none would be a price. Storage is counted in bits, as the ledger asks.

## 1. The thesis

Zeta cannot out-draw the PlayStation and N64 cores on the same chip, and it does not need to. Those cores
are frozen: they can never perceive their own picture, never carry a world that computes while nobody
touches it, and never prove what happened. Zeta can do all three, exactly, and no other console of any
era does. This design spends the chip there.

It closes one loop in hardware:

    the glass --(the retina: what was shown, where, how brightly, beside what)--> the program
        ^                                                                            |
        |                                                                            v
    the picture <--(pages and plates aimed at the field)-- the field <--(deposits, rules)
                                                     (a lawful automaton in the idle 64 MB)

and seals every frame of it, so a session is evidence.

| front | Zeta-0 today | Zeta-1 as designed | this design |
|---|---|---|---|
| objects the world can name | 64 [r] | 64 (not raised) | 256 |
| what the world perceives of an object | pixels shown, 17 bits [r] | the same, a frame older when beside [d] | pixels shown, where on the glass, how many at the centre, how brightly, and beside what |
| a world that steps without the program | none | none | 65,536 cells a frame, by rule, wherever the cart aims it |
| world memory | 64 KB [r] | windows onto megabytes [d] | the same windows, onto a field that is alive |
| proof of a session | a tape recorded by build 106 [r] | the same | a seal a frame, kept by the machine where the cart cannot write |
| the picture | 2,048 cart-mesh faces [d] | 4,096, then about 6,000 [d] | 4,096; the Zeta-1 graphics stages remain available (section 7) |

## 2. What it stands on

1. Stages 0, 1 and 2 of the Zeta-1 design are taken whole: reclaim, one store, running beside. Stage 0 is
   the only measured part of either design [d].
2. Visibility is already counted from the identity plane at flush, not at commit, so it is a function of
   the finished picture and nothing else [r]. Every percept below keeps that property.
3. The first sensor cost 832 ALMs as registers and 812 rebuilt [r, the ledger]. State wants counting in
   bits and keeping in RAM. The retina below is 3 block RAMs [a].
4. The band's planes hold 59 blocks with about a third of their bits padding [d]. A band is 10,240 pixels
   [r]; colour, depth and a 6-bit identity are 37 bits a pixel, 379k bits of 604k held [a], which agrees.
   An 8-bit identity may therefore fit without a block. **To be counted, not assumed.**
5. The 64 MB SDRAM is tied off [d]. A word a clock in bursts is supposed throughout [d].
6. The frame is bounded at 720,000 clocks and its median use in real play is 44% [r]. The idle part is
   where a second, slower kind of computation can live, provided its result never depends on when it ran.
7. The link port's pins are already in the Pocket template [r]; the second pad is already law [r].

## 3. Principles (added to Zeta-1's)

- **A percept is a function of the finished picture.** Never of draw order, never of timing.
- **Time passes only where the cart points.** The field's cost is fixed by the window, not by the world.
- **Nothing here is on by default.** A cart that sets no new cell is unchanged to the bit.
- **The machine keeps the record, not the cart.** What proves a session is written where a cart cannot reach.
- **Pay in blocks, free logic first.** The retina must give back the old sensor's logic before the field
  engine asks for any.

## 4. The machine

### 4.1 The retina

At flush, the machine already scans each band's identity plane and counts pixels an object [r]. The scan
knows more than it keeps: where each run of pixels lies, what colour it shows, and which object's run
came just before it. The retina keeps that.

One record an object, in block RAM, updated a run at a time:

| percept | meaning | bits |
|---|---|---:|
| VIS | pixels of the object the glass shows (as today) | 17 |
| BOX | the smallest rectangle holding them: min x, max x, min y, max y | 36 |
| FOV | how many of them lie in the centre window (a cell sets the window) | 17 |
| LUM | the sum of their shown brightness, so LUM / VIS is how brightly it was seen | 22 |
| NBR | the object most often immediately to the left of its runs, with a count | 16 |

- 108 bits an object [a]; 256 objects are 27,648 bits, 3 block RAMs [a].
- NBR is the majority-vote candidate over the object's runs in scan order: one identity and one counter.
  It answers "what am I beside on the glass", which is also "what am I emerging from behind".
- The answers are written back at the next frame's start, four words an object, as VIS is now.
- The old VIS words stay at `VIS_BASE` for the first 64 objects, so existing carts read what they read.
- PICK grows from one watched pixel to eight [s]: each is one more compare at the flush.

What a cart can then know, exactly: whether the player could see a thing, whether it was at the centre of
the view or the edge, whether it was lit or lost in the dark, which pillar it was hiding behind.

### 4.2 Objects

- The list is 256 long. Identity is 8 bits wherever the commit pipeline carries it.
- The list and its answers move to new addresses; the old 64-entry list stays valid at its old place and
  means what it meant. Which a cart uses is a cell.
- Plates and cards (if Zeta-1's stage 4 pump is built) are objects in this list, so they are perceived
  like anything else. A still body drawn as an image is still seen by the world.
- The geometry pass reads the list once [d], so its length costs time only there.

### 4.3 The field

A second machine inside the first: a grid of cells in the SDRAM that steps by a rule the cart supplies.
The ancestor is the cellular automata machine of the 1980s, not any console.

**The world and the window.**
- The field is 1,024 x 1,024 cells of 16 bits: 2 MB of 64 [a].
- Each frame the machine steps one WINDOW of 256 x 256 cells, 65,536 cells [a], aimed by a cell.
- Cells outside the window do not change. A larger world costs nothing; this is the existing law of the
  pager, applied to simulation.

**A cell.**

| bits | name | what it is |
|---|---|---|
| 2:0 | matter | one of eight kinds; it moves |
| 10:3 | trace | a level 0..255 that belongs to the place: it spreads, fades and is added to |
| 15:11 | the cart's | untouched by the step |

**The step, in law.**
- *Matter* moves by blocks of 2 x 2 cells; the blocks' origin alternates each step. The four kinds in a
  block (12 bits) index a table the cart loads; the table answers with four kinds (12 bits) and two gate
  bits: "only on the coin" and "only where the block's trace is at or above FIELD_GATE".
  - The table is 4,096 x 14 bits, 6 block RAMs [a].
  - The coin is one bit of a shift register stepped a block in scan order, seeded by the session's seed.
  - Block rules conserve what they are written to conserve: sand, water, fire, growth, crowds.
- *Trace* becomes (4 x itself + its four neighbours) / 8, less FIELD_DECAY, floored at zero. A kind may
  emit trace (eight small cells: an ember warms its place).
- *Deposits*: before the step, a list of up to 256 (cell, amount or kind) entries from the program is
  applied in list order. This is how the retina reaches the field: the program reads what was seen and
  writes it into the world where it was seen.

**The time.** Reading and writing the window is about 131,000 clocks at a word a clock, 18% of a frame
[a]. It runs beside the geometry pass, which touches the PSRAM and DMEM but not the SDRAM, so in a dense
frame it costs nothing. The pass is held to at least the field's slot, so the field's time is a constant
the budget gate can see. FIELD_ROWS lets a cart step fewer rows a frame; zero is off.

**Reading it.** The program reads and writes field cells through the mover's far windows (Zeta-1, 4.6).

**Seeing it.** A texture page slot, or the pump, may be aimed at field cells instead of the image field.
Cells pass through a 256-entry colour table (kind and the top five bits of trace; 1 block [a]); a page's
smaller levels are every second texel of the one above. The ground can then *be* the simulation: scorch,
frost, growth and wear are drawn from the cells that compute them.

**What the trace is for.** It is the world's memory of attention and action. Where the player looked,
walked and fought is deposited and fades slowly; the gate bit lets matter change only where trace is high
or (with the kinds reversed) only where it is absent. A world that grows where it is unwatched is one
table entry.

### 4.4 The seal

- Each frame the machine folds into one 32-bit word, in the law's order: the pad words, every write to
  DMEM (address and value), and the answers it wrote back. That word is the frame's SEAL.
- Pad words and seals are appended to a tape in a part of the SDRAM the mover refuses to write.
  Eight bytes a frame is 1.7 MB an hour [a]; 16 MB holds nine hours [a].
- The tape leaves the Pocket as a file when the session ends. Any conforming machine replays it and
  either reproduces every seal or names the first frame that differs.
- On the link port, two Pockets exchange pad words and seals each frame. A divergence is caught on the
  frame it happens, on both machines.
- The program can read its own seal for the previous frame. It cannot write one.

This is "a run is a proof" made a property of the hardware, with no trust in the cart.

## 5. What changes in the law

| | today | this design | which carts |
|---|---|---|---|
| object list | 64 at `OL_BASE` | 256 at a new base; the old list still valid | carts that set the cell |
| identity | 6 bits | 8 bits | invisible |
| percepts | VIS: 64 words | + a 4-word record an object (BOX, FOV, LUM, NBR) | carts that read them |
| PICK | one pixel | up to eight | carts that list them |
| the field | -- | window, FIELD_ROWS, FIELD_GATE, FIELD_DECAY, the rule table, the colour table, the deposit list | carts that set FIELD_ROWS |
| page and pump sources | DMEM, the cart's segment (+ the image field [d]) | + field cells through the colour table | carts that aim one there |
| the seal | -- | one read-only cell; the tape | invisible unless read |
| texture pages resident | 20 [r] | 20: not reduced (see section 6) | none |

Unwritten SDRAM reads as zero by law: the machine clears the field and the tape at boot, or refuses reads
of what was never written. Which, the controller's cost decides.

## 6. The resources

**Block RAM**, from Zeta-1's own table after its stage 1 (304 held of 308 [d]):

| | blocks |
|---|---:|
| held after Zeta-1 stage 1 [d] | 304 |
| the planes repacked to their bits [d: about 17, against slower reads] | -17 |
| the retina's records [a] | +3 |
| the rule table [a] | +6 |
| the field's two row buffers [a] | +1 |
| the field's colour table [a] | +1 |
| the longer object list [s] | +2 |
| **held / free** | **300 / 8** |

- This closes only because three things in Zeta-1 are **not** taken: faces beyond 4,096, the 8,192-word
  instruction cache, and the image field's page windows as a reason to cut pages from 20 to 12.
- Keeping 20 pages keeps every existing textured cart's picture, which the family's law requires.
- It leans entirely on the plane repack, whose price in read time is unmeasured. If the repack fails, the
  field's table is the first thing to shrink (four kinds: under 1 block [a]).

**Logic** (286 ALMs free [d]). Unpriced. What should give: the old sensor's registers replaced by the
retina's RAM; the sound in turn and the overflow path [d]. What will take: the SDRAM's controller, the
field engine (a table lookup, a five-input add, two counters), the seal's fold, the run updater. The
controller is the same one Zeta-1's stage 4 needs; here it is proved on the smallest user first.

**DSP**: nothing asked.

**SDRAM**: the field 2 MB, the tape 16 MB, 46 MB left for Zeta-1's image field and far data [a].

## 7. The stages

Each ends as Zeta-1's do: witnessed by a cart that fails with the feature off, crossed, fitted at four
corners, judged on the Pocket. Each can be the last.

**R0 -- the base.** Zeta-1 stages 0, 1, 2 as designed, with one addition from review: stage 2 latches the
cells the *sound* reads as well as the picture's, and says when AUD is written back.

**R1 -- the retina and 256 objects.** No SDRAM. Gate: one witness a percept (a body crossing the centre
window; a body dimmed; a body passing behind a pillar and out the other side); existing carts' VIS words
identical. Gives: the world's sight, and it should return logic. If it does not return logic, stop here
and learn why before the field is attempted.

**R2 -- the controller, the tape, the seal.** The SDRAM's first use is the simplest: append-only bursts.
Gate: a tape recorded on the Pocket replays on the law seal for seal; a build with one mutated instruction
is convicted at the right frame; two linked Pockets agree for an hour.

**R3 -- the field.** Trace first (adds only), then matter (the table), then drawing it through a page.
Gate: witnesses for a deposit that spreads and fades to an exact frame; a block rule that conserves its
count over 100,000 steps; a window moved across the world with the cells behind it unchanged; a page
aimed at the field, crossed. Gives: the world that steps by itself.

**R4 -- the picture, as wanted.** Zeta-1's stage 3 (anchors and repeat) and stage 4's placed plates and
cards, now as perceived objects. Unchanged from that design; ordered here by the game's need.

## 8. Against the consoles

| | PlayStation and N64 cores on the Pocket | any shipped console | this design |
|---|---|---|---|
| triangles and textures | ahead | ahead from 1998 on | behind, by choice |
| locked 60 with a bound | no | rare | yes [r] |
| knows what it showed, to the pixel, in its contract | no | no (later machines can ask, inexactly and off the record) | yes, and where and how brightly |
| a world that computes beside the game, by rule | no | no | yes |
| a session that proves itself | no | no | yes |
| two machines provably in one world | no | no (netplay trusts, then repairs) | yes |
| can still change | no | no | yes, and each change is proved |

"Above" is claimed only on the last five rows. On the first it is behind and will stay behind.

## 9. What a game could do that none can now

For TND, as examples and not as a plan:

- A demon that moves only while no pixel of it is shown, decided by the machine and not by a guess.
- A demon that knows it was seen at the edge of the view but not at the centre, and acts on it.
- Fog and growth that thicken in the rooms the player has never looked into.
- A floor that keeps the fight: scorch and blood are cells, they spread and fade by rule, and they are
  what the floor is textured with.
- A Tyrant that reads the trace and learns which side of the hall the player favours.
- A second visit to a room that differs because of what the first visit left there.
- A run submitted as a tape that any Pocket can check.

## 10. What is his to decide

1. Whether the field is wanted at all. It is the largest and least certain part.
2. Whether pages stay at 20 (compatibility) or fall to 12 (blocks). This design assumes 20.
3. Whether 256 objects or 128. The retina's cost is the same shape either way.
4. Which percepts earn their bits. LUM and NBR are the speculative ones.
5. Whether the tape is kept by the machine (the seal) or stays a recorder's job.
6. The order of R3 and R4: the world or the picture first.

## 11. Looked at and left out

- **Rewind.** The picture feeds the world, so replaying forward from a saved moment means drawing every
  frame again: rewind would cost real time. A cart can still keep its own past through far windows.
- **Two retinas.** Two linked Pockets, each with its own camera on one world, each one's percepts sent to
  the other as inputs. It follows from the seal and the link and is the most alien thing in reach, but it
  needs the wire's capacity measured first.
- **A percept for every pixel of fog.** Whether a pixel fogged to the clear colour counts as seen is a
  question for the law of fog; LUM is offered instead and may not be enough.
- **A learning system in the machine.** The program has 262,144 instructions a frame [d] and the field
  has a table. That is enough for a world that adapts and remembers, not for one that learns in the
  sense the word is used elsewhere, and nothing here bears on consciousness.
- **The field as collision or height for bodies.** The program can read cells and decide; the machine
  does not.

## 12. What is weakest here

- No number in sections 4.3 or 6 has been measured, and the block arithmetic rests on a repack that is
  itself only proposed.
- The logic is unpriced, on a chip with 286 ALMs free. R1 is placed first because it is the one stage
  that should give logic back; if it does not, the rest does not fit.
- The field's time assumes the geometry pass leaves the SDRAM alone and that a burst is a word a clock.
- The author has not seen the current silicon, the density measurements, or `ZETA-N-HYPOTHESIS.md`.
