# The Zeta platform: direction and the first phase

Written 2026-11-20, after the graphics frontier and TND's feel pass
landed. This is the working plan. Each section says what exists, what
is proposed, and what is still unverified.

## The direction

The Pocket has PlayStation and Nintendo 64 cores now. They are museums:
they replay what was finished decades ago, flaws included, and can never
be otherwise. Zeta is a living console, designed together with its games.

Its product is exactness, not power: locked 60 Hz, instant, identical
every time. Because it is exact, it can keep changing, since every change
can be proven.

Everything below serves one loop:

1. Play on the Pocket.
2. Record the session as a replay.
3. Measure that replay on the desktop.
4. Change the game, the tools or the silicon.
5. Prove the change exactly.
6. Play again.

**What the direction rules out:**
- chasing polygon counts or texturing parity with those cores;
- building a visual editor before the command-line path works;
- adding hardware that a replay has not shown is needed.

## Where the other cores stand (November 2026)

| | PlayStation (GuardianSoul 0.5.10) | Nintendo 64 (MIRLO 64 0.9) | Zeta |
|---|---|---|---|
| Library | most games tried play | claims over 99% | one game |
| Frame rate | the originals' | the originals' | locked 60 Hz |
| Slowdown | "some games can still slow down in busy scenes" | about 97% of the chip's logic (per a guide) | worst TND frame 58% of budget, on scripted routes only |
| Save a state | up to ~30 s (about 2 MB) | 1–3 MB | **153 KiB: about 1.5 s at the same speed** (not yet built) |
| Wake from sleep | up to ~90 s | ~17 s | not yet built |
| Controls | DualShock mapped down | 9 buttons and a stick on 8 and a D-pad | designed for these buttons |

Sources: the two projects' READMEs and release notes, and the openFPGA
library listing, read on 2026-11-20. The Pocket writes save states at
about 0.1 MB/s for every core (the PlayStation core's own note).

## Phase 1: make it a console and close the loop

### 1. The repo: games apart from the machine's own carts (done)

56 carts sat in one folder. They are four different things, and now live
apart (`zeta/carts.py` finds any of them by name):

| Where | What | Count |
|---|---|---:|
| `carts/witness/` | one claim about the machine each, held by a gate | 30 |
| `carts/probes/` | questions asked of real hardware | 11 |
| `carts/examples/` | small carts to learn from and to cross against | 8 |
| `carts/system/` | the boot face, the film, the shelf | 3 |
| `games/<name>/` | a game: its generator and cart, in time its assets, tests and tapes | 4 |

Every command takes a cart by path or by name (`zeta cross tex`).

**Still to decide:** built game carts are committed as text (TND's is
15 MB). That suits witnesses, which are small and are evidence. For a
game it means megabytes of baked poses in every commit.

### 2. Launching from the Pocket's menu

**Today.** The core loads one fixed file, `cart.zbin`, and every game
lives inside it behind an in-cart launcher (the film, then the shelf).
Costs: all 11.9 MB loads on every start; shelved games cannot share a
save slot; nobody can drop a new game on the card; and the Pocket ties
sleep and save states to a loaded game.

**Proposed.** One file per game, chosen in the Pocket's own browser.
Analogue's slot rules allow it (data.json, read 2026-11-20):

| Slot | Settings | Effect |
|---|---|---|
| Game | `required: true`, `extensions: ["zbin"]`, parameters bit 0 (user-reloadable) and bit 9 (remember the choice) | the Pocket opens its browser when no game is chosen, and remembers the last one |
| Save | `nonvolatile: true`, parameters bit 2 (filename cloned from slot 0) | each game gets its own save file, named after it |

- The film stays as what plays when no game is chosen.
- The shelf survives as an ordinary cart, for curated collections.
- **Work:** the loader must accept a chosen file of any size and reset
  the machine cleanly on a reload; the card path must follow the
  per-game save file.
- **Unverified:** how a reload interacts with the loader's boot
  handshake, and whether bit 6 (reset around the load) is enough or a
  full core restart (bit 7) is needed. Only glass can say.

### 3. Sleep and save states

**What exists.** The snapshot is already law: `spec.STATE_*` defines the
machine's whole state between two frames, 157,028 bytes. The reference
machine saves and restores it, and `tests/test_rewind.py` witnesses every
field by mutation. The desktop cabinet rewinds with it today.

**What is missing.** The hardware hand-over. The core template already
carries Analogue's handshake (`savestate_start`, `savestate_load`, an
address and a size); Zeta reports "not supported".

- **Save:** freeze at a frame boundary, refuse while a card request is in
  flight (the law already says so), and expose the image through a bridge
  window for the Pocket to read.
- **Load:** accept the image through the same window and resume.
- **Sleep and wake** are the same two steps with the Pocket's own timing.
- **Cost:** read paths into memories that today are only written from the
  bridge. Logic unmeasured; it gets a fit before a number.
- **The gate** is the one the rewind test names: save on glass, load on
  the reference machine, continue, and compare.

### 4. Replays

A replay is the cart's identity, the save file's starting contents, and
one pad word a frame. Every delay in the machine is legislated, so that
is enough to reconstruct a session exactly.

| Who | What it gives them |
|---|---|
| The player | ghosts, shareable runs, rewind |
| The developer | a bug report that reproduces every time |
| The hardware designer | costs measured on real play |

**Why it is urgent.** The frame meter has only two scripted routes. On
them the 43.2 MHz build dropped no frames; on the Pocket the player felt
51.84 MHz "a lot smoother". Real play is heavier than the scripts, and
the meter cannot see it until it has tapes.

- **Exists:** the desktop replays pad tapes (`zeta sd witness --tape`).
- **Missing:** an on-device recorder. It must be passive, write to its
  own file, and never compete with the game's own card requests.
- **First version:** record from power-on only. Recording from a save
  state follows section 3.
- **Then:** `zeta profile <tape>` costs every recorded frame on the RTL,
  and any silicon change is judged on the whole tape library.

### 5. One toolkit

Getting a build onto the card today takes three generators run with
environment flags, a one-off packing script, hand-copied core files and a
push with a custom path. Profiling uses tools with one game's name in
them plus scratch scripts.

| Command | Does | Replaces |
|---|---|---|
| a project file per game | names its sources, assets and build variants | `TND_SONG`, `TND_OMIT`, `TND_STRESS`, `TND_OUT` |
| `zeta build <game>` | generates and links every cart the game needs | running `gen_tnd`, `gen_shelf`, `gen_face` in order |
| `zeta stage <game> --core <fit>` | makes a card folder from a cart and a core | hand-copying `.rbf_r` files and calling the packer |
| `zeta push` | copies, verifies and ejects | the four-step card routine |
| `zeta profile <cart>` | frame cost by stage and by band | `tools/tnd_meter.py`, the band histogram |
| `zeta inspect <cart>` | program and data memory by section | the scratch memory map that found 629 words |
| `zeta verify <cart>` | cross and glass, on routes or tapes | `tools/route_cross.py` |

### 6. A language people already know

A game today is Python that emits stack operations by hand:

```python
p.load(F["py"]).load(dslot(i, "py")).emit("sub", "dup", "mulq")
p.push(CLEAR2).emit("lt", f"jz {over}")
```

which means `if (player.py - demon.py) ** 2 < CLEAR2:`.

**Proposed:** a restricted subset of Python, compiled ahead of time to
ZOL. ZOL stays as the assembly underneath, and the VM and the cart
format do not change.

- Only what the machine can do: integers, fixed-point numbers, fixed
  tables, plain functions, bounded loops. Anything dynamic is a compile
  error.
- No recursion, so every function's variables get fixed cells, and the
  compiler overlaps the cells of functions that never run together.
  That is the scratch sharing TND does by hand.
- Every function reports its size in words and its worst-case fuel.
- Existing hand-emitted code keeps working beside it.

**The risk is code size.** Program memory is the scarcest thing in the
machine. Before committing, compile a few real TND routines and compare
their word counts with the hand-written ones.

**Not yet decided:** whether the syntax is restricted Python or
purpose-built.

## Phase 2: more room to express (after phase 1)

| Lever | Why | State |
|---|---|---|
| Game memory | TND had 41 program words and 6 data words free; a two-word save needed the HUD's triangle count re-proved | **Audited (the core template):** the Pocket's SRAM (asynchronous, 128K x 16 bits, 256 KiB) and SDRAM (64 MB) are wired to the core and tied off unused. Program memory today is 32 KiB in 97 block-RAM blocks; in the SRAM it could be eight times larger and give the blocks back. The VM is about 5% of a frame, so slower memory is affordable. The SRAM's speed is **not yet measured**. |
| Scene capacity | the object list (64) and vertex cache (2,048) bind before the clock does | needs block RAM, which is full; freed by moving program memory out |
| The sensors | VIS, AUD and PICK are built and barely used by any game | no silicon needed |
| Texturing | a textured pixel costs 7–12 clocks against 1 flat | not yet measured where the beats go |
| Audio mixer | sixteen parallel voices, about 2,600 ALMs | a serial mixer might return a thousand; **unmeasured** |

## Phase 3: prove it

- TND with its feel finished (done for now, on the Pocket 2026-11-20).
- A fresh target built with the new tools. That is the test that they
  work for something other than the game they grew up with.
- Only then, other people.
