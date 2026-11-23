# Ordering computation by scale: one world, three schedules

The developer's note of 2026-11-23: arrange memory, computation and
updates as a hierarchy of scales S_k = R^k (he proposes R = 64), each
with its own working set and update rate, phase-staggered so that no
frame carries them all; then compare it with the machine's ordinary
scheduling on identical scenes -- working set, words moved, worst
frame, and whether the output is the same.

This is that comparison, as small as it could be made. Everything here
is a CART: nothing in the law or the silicon was changed, and nothing
was fitted.

    python3 experiments/scale/scales.py            # the sweeps  -> results.json
    python3 experiments/scale/scales.py silicon    # clocks, and law against silicon -> results-silicon.json
    python3 experiments/scale/scales.py window     # the frame all scales fall on -> results-silicon-window.json
    python3 -m pytest tests/test_scale_order.py

## The world and the three schedules

A torus holding N movers of constant velocity; the player walks it. A
mover within 4 units of him is TAKEN (it stops for good: a permanent
change, so a schedule that misses one is wrong ever after); every mover
within 16 units is drawn. `Model` in `scales.py` is that law in numpy,
and every cart is checked against it every frame: each mover's place,
which are taken, the score, and the set of things drawn.

- **flat**: every mover, every frame. How every cart on this machine is
  scheduled today.
- **burst**: scales, unstaggered. Scale k's whole list is visited on
  frames that are multiples of R^k.
- **scaled**: scales, staggered. Scale k gets a fixed number of visits
  EVERY frame and a cursor that walks its list.

Why a coarse scale may be late: a mover and the player close by at most
VREL a frame (here 5/32 of a unit). One that was farther than
16 + R^k x VREL when last visited cannot be drawn or touched for R^k
frames. So scale k IS the movers that far away -- its radius grows as
R^k because its period does -- and when one is visited it is brought up
to date in one multiply (x += dt x v), exactly. Nothing is approximated.
The cart counts its own failures: `late` (a visit after its period),
`over` (a list that was full), `drop` (no room in the object list).

## Measured (2,200 frames of one walk; instructions a frame, of a ceiling of 65,536)

The same density at three sizes, ratio 8 (four scales):

| schedule | movers | world | median | worst | working set, worst (words) | words moved, worst | frames out of instructions | late | against the law |
|---|---|---|---|---|---|---|---|---|---|
| flat | 128 | 256 | 11,613 | 11,803 | 436 | 4,298 | 0 | 0 | same |
| burst | 128 | 256 | 292 | 16,809 | 727 | 6,866 | 0 | 0 | same |
| scaled | 128 | 256 | 1,245 | 1,790 | 110 | 725 | 0 | 0 | same |
| flat | 512 | 512 | 45,937 | 46,078 | 1,588 | 16,767 | 0 | 0 | same |
| burst | 512 | 512 | 417 | 63,849 | 2,634 | 26,137 | 0 | 0 | same |
| scaled | 512 | 512 | 1,703 | 2,062 | 123 | 853 | 0 | 0 | same |
| flat | 2,048 | 1,024 | 65,536 | 65,536 | 2,232 | 23,868 | 2,200 | 0 | **wrong from frame 0** |
| burst | 2,048 | 1,024 | 591 | 65,536 | 2,704 | 26,801 | 4 | 18 | **wrong from frame 511** |
| scaled | 2,048 | 1,024 | 2,273 | 2,605 | 160 | 1,079 | 0 | 0 | same |

The ratio, at 2,048 movers (staggered; all four are the same world as the law):

| R | scales | scale radii (units) | visits a frame, per coarse scale | median | worst | working set, worst |
|---|---|---|---|---|---|---|
| 4 | 6 | 16.6, 18.5, 26.0, 56.0, 176.0 | 6, 2, 2, 4, 3 | 2,300 | 3,120 | 154 |
| 8 | 4 | 17.2, 26.0, 96.0 | 4, 5, 5 | 2,273 | 2,605 | 160 |
| 16 | 3 | 18.5, 56.0 | 7, 10 | 2,629 | 3,053 | 178 |
| 64 | 2 | 26.0 | 40 | 5,471 | 6,024 | 310 |

In clocks, on the simulated hardware (a frame is 864,000; the worst
includes frame 512, where at ratio 8 every scale falls together):

| schedule | movers | median | worst | pixels differing, law against silicon (140 frames) |
|---|---|---|---|---|
| flat | 512 | 28.6% | 28.9% | 0 |
| burst | 512 | 21.8% | 32.0% | 0 |
| scaled | 512 | 22.0% | 22.6% | 0 |
| burst | 2,048 | 22.0% | 32.4% | 0 |
| scaled | 2,048 | 22.2% | 22.9% | 0 |

## What it says

1. **The output is the same.** The staggered schedule is the law's world
   frame for frame at every size and every ratio tried, and the law and
   the silicon agree on its picture.
2. **Sixteen times the world cost it 1.46 times the worst frame**
   (1,790 -> 2,605 instructions), and its working set went from 110
   words to 160. Flat grows with the world (3.9 times for 4 times) and
   at 2,048 movers cannot run at all: it is out of instructions every
   frame and wrong from the first.
3. **Staggering is the whole of it.** The burst has the lowest median
   and a worst frame WORSE than flat's (16,809 against 11,803; 63,849
   against 46,078), because bringing a mover up to date costs more than
   stepping it. At 2,048 it runs out on the frames the scales share,
   its visits come late, and its world is wrong from frame 511.
4. **Eight, not sixty-four, for this world.** The radius of scale k is
   16 + R^k x VREL. At 64 the second scale would begin 656 units out,
   past the half-world of 512, so there are only two scales and the
   coarse one needs 40 visits a frame: 2.3 times the worst frame of
   ratio 8. The ratio is not free to choose: it is tied to how fast
   things close and how big the world is. 64 fits what changes in TIME
   and does not move (TEAR NOT DEMON's packs already step once in 512
   frames, in closed form).
5. **On this machine the gain is instructions and working set, not
   clocks.** An instruction costs about 1.3 clocks; the whole ceiling of
   65,536 is about a tenth of a frame, and this scene's drawing was
   22%. The frame's clocks are spent drawing. Ordering the SIMULATION
   by scale lifts the ceiling on logic; the clock budget would be moved
   by ordering GEOMETRY the same way. Not tried.

## The limits, measured

- **A jump.** The scales trust his speed. One frame in which he is 300
  units away (`A`): the drawn set was wrong for 158 and 261 frames on
  two walks (the bound is the top scale's period, 512), and on a third
  a mover that should have been taken in that window was not -- the
  world was wrong from then on. Flat does not care. Any real use needs
  a legislated way through a cut (a door, a fade that lasts a sweep).
- **Memory binds before computation.** A mover is 4 words; 2,048 of
  them are 8,192 of about 11,600 words of data memory. The scheduler
  would carry 64 times more for one more scale; the memory will not.
  The next scale has to live off data memory (the card), which is the
  note's "memory hierarchy sharing the same scale structure". Not built.
- **The near set is real work**: about 150 instructions a visit, every
  frame, for everything in reach. No schedule removes it.
- Movers here do not act on each other. Things that do would have to
  share a scale.

## Proposed next (not done)

- The top scale on the card: a 512-frame period is long beside the
  card's legislated 4-frame latency, so a block of movers could be
  fetched, brought up to date and put back inside its own budget.
- The same bands for geometry (which detail is drawn), where the clocks
  are.
- TEAR NOT DEMON's persistent packs as scales 2 and 3 of one schedule.
