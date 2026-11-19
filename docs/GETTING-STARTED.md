# Getting started with Zeta

A practical guide for writing your first cart. You need this repo,
Python, and about an hour.

## 1. What you're building for

Zeta is a deterministic game console defined by one readable Python file
(`zeta/spec.py`, ~1,300 lines). The real numbers:

- **320×288 pixels, RGB555, at a locked 60 Hz.** Every frame is bounded
  at 720,000 clocks; the machine cannot dip and has no crash state.
- **4,096 instructions of program** (IMEM) and **16,384 32-bit words of
  game state** (DMEM). The VM may execute up to 65,536 instructions a
  frame (FUEL); running out is a lawful stop, not an error.
- **256 2D display-list triangles + 64 3D objects a frame**, PS1-style:
  integer edge functions, exact to the pixel, flat/Gouraud/textured/lit
  faces, fog, outlines, depth-composited pre-rendered backdrops.
- **16 sample-exact audio voices**, 800 samples a frame, wavetable.
- Content beyond DMEM pages in from an 8 MB cart segment (CRAM) and
  from SD-card data slots — megabytes of meshes, rooms, and music,
  moved a few thousand words a frame at legislated instants.

The same cart runs in a software cabinet on your desk, in a Verilated
model of the silicon, and on an Analogue Pocket — and the platform's
gates prove, bit for bit, that all three show the same pixels and play
the same samples. Determinism is the product: replays are pad logs,
netplay is pad words on a wire, and a speedrun verifies by checksum.

## 2. Install and first run

You need **Python 3.14**. Verilator is *not* required until you want to
run the silicon cross-check (section 5); the software cabinet is pure
Python + pygame.

```sh
cd zeta-platform
python3.14 -m venv .venv
.venv/bin/pip install "setuptools<81"
.venv/bin/pip install pytest numpy pygame pillow
./zeta-cli run carts/bounce.zol
```

(The exact pinned versions the gates run under are in
`infra/gates.Dockerfile`: numpy 2.5.3, pygame 2.6.1, pytest 9.1.1.
pygame has no prebuilt wheel for 3.14 and compiles from source, so you
need SDL2 development headers on Linux.)

A window opens: a blue square bouncing off the walls, nudgeable with
the arrow keys. That's `carts/bounce.zol` assembled on the fly and
running in the pygame cabinet at 60 fps. Useful variants:

```sh
./zeta-cli build carts/bounce.zol          # .zol -> .zc cart file
./zeta-cli run   carts/bounce.zol --scale 3
./zeta-cli dump  carts/bounce.zol -f 120 -a 0,60,119   # headless -> PPM
```

`zeta-cli` is a thin wrapper that runs `python -m zeta.cli` inside
`.venv`; `./zeta-cli --help` lists every command.

## 3. Your first cart

Carts are written in **.ZOL**, a small stack-machine assembly. The
entire grammar (from the docstring of `zeta/asm.py`, which is the
authority):

```
; comment                    anywhere
.const NAME value            name a number (usable in any argument)
.data ADDR v0 v1 ...         boot-time DMEM initialization
.cram OFF  v0 v1 ...         the CRAM segment (paged in with the mover)
.sd SLOT OFF v0 v1 ...       a data slot's file on the SD card
label:                       jump target
op [arg]                     one instruction
```

Arguments are decimal, `0x` hex, a `.const` name, or a label.

The frame contract, which is the whole programming model:

1. Each 1/60 s, the cabinet writes the frame counter into DMEM cell 0
   and the pad word into cell 1.
2. The VM runs your program **from PC 0 until `halt`** (or fuel runs
   out). There is no main loop — the machine is the loop. DMEM persists
   across frames; that persistence *is* your game state.
3. The GPU then reads the display list at DMEM 12288 and the object
   list at 14084 and paints the frame.

The instruction set is 26 ops on a 64-deep stack of signed 32-bit
words: `push/load/store` (and indirect `loadi/storei`), arithmetic
(`add sub mul mulq and or xor shl shr`), compares (`lt eq` — `lt` is
signed), stack shuffles (`dup drop swap over`), and control
(`jmp jz call ret halt`). Binary ops pop b then a and compute `a OP b`,
so `load X / push 5 / lt` asks "is X < 5". `mulq` is a Q16.16 fixed-
point multiply — all 3D coordinates are Q16.16 (65536 = one unit).

Here is a minimal complete cart — a square that slides right and wraps:

```
; slide.zol -- a moving square in ~20 instructions.

.const X 16                ; cells 0..15 are the machine's; 16 up is yours
.const COLOR 0xFF8800

.data 16 40                ; x starts at 40

load X                     ; x = (x + 1), wrapped at 280
push 1
add
store X
load X
push 280
lt                         ; x < 280 ?
jz wrap
jmp draw
wrap:
push 0
store X
draw:
push 1                     ; display list at 12288: count, then
store 12288                ; 7 words per triangle: x0 y0 x1 y1 x2 y2 rgb
load X
store 12289                ; (x, 100)
push 100
store 12290
load X
push 40
add
store 12291                ; (x+40, 100)
push 100
store 12292
load X
store 12293                ; (x, 140)
push 140
store 12294
push COLOR
store 12295
halt
```

Save it as `carts/slide.zol` and `./zeta-cli run carts/slide.zol`.

Read `carts/bounce.zol` next: it is the same shape grown to a full
game loop — velocity state, signed compares for wall reflection, pad
bits (`UP=1 DOWN=2 LEFT=4 RIGHT=8`, then A/B/X/Y/L/R/Start/Select), and
a two-triangle quad. One gotcha worth knowing early: `push` carries a
*signed 24-bit* immediate, so pushing a color with red ≥ 0x80 at
runtime goes negative. `.const` and `.data` take full words; for
runtime colors build the value in halves (the forge's `push32` does
this for you).

Where things live in DMEM (all defined once, in `spec.py`):

| cells | meaning |
|---|---|
| 0, 1 | frame counter, pad word (written by the machine) |
| 2–5 | the pick register: ask which triangle owns a pixel |
| 6, 8–11, 12287 | camera: pitch, x y z (Q16.16), yaw, roll |
| 7 | BG_SRC: pre-rendered backdrop plate in CRAM |
| 12–15 | the mover: DMA from CRAM into DMEM |
| **16–12287** | **yours** |
| 12288+ | display list (256 tris max, 7 words each) |
| 14084+ | object list (64 objects, 6 words each) |
| 14480+ | audio voice registers (16 voices) |
| 14656+, 14720+ | VIS / AUD readback: pixels shown and sound heard |

## 4. The forge: generating carts from Python

Hand-writing `.data` blocks for an 81-vertex ground mesh is nobody's
idea of fun, so most real carts are *generated*. Two levels:

**Plain generator scripts** (`carts/gen_*.py`) compute the data and
write a `.zol` file — `carts/gen_cube.py` is the canonical example: it
builds a checkered ground plane and a cube as mesh words, emits them as
`.data` lines, and appends a hand-written ZOL program. The output is
still ordinary ZOL you can read.

**The forge** (`zeta/forge.py`) is the supported API and adds the thing
generator scripts kept getting wrong: a **linker**. Resources know
their size but never pick their address; the `Cart` object assigns
addresses, so content can never overlap and every limit in `spec.py`
is checked in one place. (Before it existed, a growing mesh silently
landed on top of a sine table and the bug was mis-diagnosed twice.)

```python
from zeta import forge, spec
from zeta.forge import Cart, Mesh, Table, ONE   # ONE = 65536, Q16.16

cart = Cart("mygame")
mesh  = cart.data(Mesh(verts, faces, colors=cols))  # address assigned
sines = cart.data(forge.sine_table())
x     = cart.var("x")                  # a scratch cell for your state

cart.boot(spec.CAM_Y, 1 * ONE)         # register cells, set at boot

p = cart.program()
p.addi(x, 1)                           # emits ZOL; labels unique
p.if_pad(spec.PAD_A, lambda: p.set(x, 0))
p.object(n_cell, mesh, x=x, y=0, z=2 * ONE, angles=0, flags=spec.OBJ_CULL)
p.emit("halt")
cart.write("carts/mygame.zol")
print(cart.report())                   # words used, words free
```

Resource types: `Mesh` (flags fall out of the constructor — `colors=`
implies Gouraud, `uvs=` implies textured), `TexturePage`, `WavePage`,
`Plate` (a pre-rendered backdrop: color + depth + optional shadow
mask), `Table`, and `Text` (3×5 glyphs baked to display-list words).
`cart.cram()` and `cart.sd(slot, ...)` place resources in the paged
tiers instead of resident DMEM.

The forge deliberately does **not** hide ZOL: the output is a readable
`.zol` file, because the fuel budget is a hard ceiling and you need to
be able to count instructions. There is also `./zeta-cli mesh foo.obj`
to bake an .obj model into ready-made `.data` blocks.

## 5. The ladder: build → run → budget → cross → deploy

The platform's promise is that **a cart which passes the gates runs
bit-identically on real hardware**. The gates are how that stops being
a slogan:

- `./zeta-cli build cart.zol` — assemble. Catches grammar errors,
  oversized immediates, carts bigger than IMEM.
- `./zeta-cli run cart.zol` — play it in the cabinet. This is your
  inner loop; iterate here.
- `./zeta-cli budget cart.zc` — the frame-budget gate: runs the cart
  on the Verilated silicon and reads the hardware's own clock meter.
  A frame is 720,000 clocks; this is the only gate that can see time,
  because a too-slow frame still produces the *correct* pixels.
- `./zeta-cli cross cart.zol -f 120` — runs the cart in the Python VM
  and in the Verilated silicon side by side and demands the
  framebuffers **and** audio streams be bit-equal every frame. Any
  divergence dumps both frames and names the exact frame. This needs
  **Verilator** (the gates image pins 5.052) and a C++ toolchain.
- `./zeta-cli glass cart.zol` — one stage closer to the panel: the
  actual scanned-out pixel stream must equal a complete VM frame.
- `./zeta-cli suite` — the standing gate: every suite cart through
  cross and glass.
- `./zeta-cli deploy cart.zol` — runs cross, glass, and a loader check,
  then packages an openFPGA core for the Analogue Pocket.

Why bother, as a game developer? Because determinism is a *feature of
your game* here: state snapshots, rewind, replay files that are
kilobytes of pad words, and netplay with provably identical screens
all fall out of it — but only if your cart actually behaves identically
on all three machines, and cross is what proves it does. You don't
need Verilator on day one; you need it before you ship.

The pinned environment for all of this is `infra/gates.Dockerfile`
(image `ghcr.io/rz4/zeta-gates`), which runs headless under
`SDL_VIDEODRIVER=dummy` — the whole ladder works in CI.

## 6. The machine's shape

Zeta's constraints pick a design identity; work with it.

**Good at:** small, exact, authored spaces. Fixed-camera rooms where a
pre-rendered backdrop (with real per-pixel depth, shadow, and color
grading) occludes a few live, lit actors. 3D dioramas where the pick
register is your cursor and examine ray. Arcade flight and corridors —
the camera has all three axes. Rhythm and timing games: audio is
sample-exact and the frame is law, so frame-perfect play is a property
of the machine, not of your code. Anything that benefits from provable
runs: daily seeds, leaderboards that cannot be cheated, rollback
netplay.

**Bad at:** crowds and ragdolls (64 objects, ~1–2k faces a frame, and
a hard fuel ceiling on simulation). Open vistas (fog and LOD exist
precisely so distance can end; the world streams in room-sized pieces,
it is not resident). Text-heavy games: the only text path is 3×5
glyphs built from display-list rectangles — roughly 35 characters on
screen at once. That is a HUD and a prompt, not a dialogue box.

The useful instinct: the display list is your 2D/HUD plane, the object
list is your scene, the backdrop is your art budget, DMEM is your RAM,
and everything bigger lives in CRAM or on the card and is *paged*, a
bounded number of words per frame, at instants the law defines.

## 7. Where to go next

- `zeta/spec.py` — read it top to bottom once. It is the console
  manual: every register, limit, and pipeline stage, with the reasoning
  written next to the number.
- `zeta/asm.py` and `zeta/forge.py` — the two docstrings are the
  language reference and the content-pipeline reference.
- `carts/` — a graded curriculum in working code: `bounce.zol` (2D,
  pad, state), `gen_cube.py` (first 3D), `gen_tex.py` (textures),
  `gen_lit.py` (per-vertex light), `gen_room.py` / `gen_hall.py`
  (backdrop plates), `gen_voice.py` / `gen_choir.py` (audio),
  `gen_stream.py` / `gen_save.py` (the SD card), `gen_overlay.py`
  (programs bigger than IMEM).
- `./zeta-cli suite` — when it is green, everything above is not
  documentation, it is a theorem about your checkout.

A cart you write with this SDK is yours, outright (`LICENSING.md`).
