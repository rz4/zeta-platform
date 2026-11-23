# Probing the Zeta-n hypothesis with this session's work

The question (the developer, 2026-11-23): can everything so far probe the
hypothesis that C(H, A(n+1)) can exceed C(H, A(n)) with the machine H
unchanged? `docs/ZETA-N-HYPOTHESIS.md` states it.

## What the session is evidence of, and what it is not

Seventeen commits (P42 to P56) added a fighting lab, a reactor, aim by
zone, a laser, exact dodges, a parkour run, a walked landing arc, a course
clock -- and changed NOTHING in the law or the silicon. So they say nothing
directly about A(n+1). They measure C(H, A(n)): how much one architecture
holds, and **which resource binds first**. That is what the hypothesis needs
before it can make a prediction worth testing.

| resource | the lab, P42 | the lab, P56 | its limit |
|---|---|---|---|
| program words | 23,172 | 28,916 | 32,768 (the page) |
| data memory free | -- | 1,013 words | -- |
| frame clocks, worst (simulated silicon) | 59% | 58-65% | 90% (the gate) |
| VM instructions a frame, worst | -- | ~27,000 | 65,536 |

Time is not binding: a third of the frame and over half the instructions
are free. **Program space is**: 88% used, and every feature since P42 took
some of it. Data memory is next.

## The probe: what one instruction-set generation would give back

`idioms.py` reads the program the machine actually runs and counts the
places a cart spells out an operation the instruction set lacks, and how
often those run over 2,340 frames of the player's own session
(`results-lab.json`):

| idiom | places | words back | instructions back a frame |
|---|---|---|---|
| compare and branch (`lt`/`eq` then `jz`) | 1,029 | 1,029 | 275 |
| a 32-bit constant (10 words) | 83 | 664 | 200 |
| min / max with a constant | 77 | 426 | 75 |
| absolute value | 72 | 432 | 45 |
| negate | 42 | 84 | 71 |
| **total** | | **2,635 (9.1% of the program)** | **666 (4.8%)** |

The prediction: an A(n+1) with these five as instructions gives this cart
back 2,635 words -- the free page goes from 3,852 to 6,487 words, 68% more
room for game -- and saves almost nothing in time, which is not what binds.
So the hypothesis, applied with measurements rather than taste, points at
CODE DENSITY, not speed: the optimization worth making is the one that
relieves the binding resource.

Also read off the same session, and NOT the next step: the landing arc and
the lens's draw-in are one operation done in software -- where does this
path meet the world's boxes -- at about 7,400 instructions a frame. A
world-space query unit (PICK's twin, in the world rather than on the glass)
is a primitive this work has revealed; but it buys time, and time is not
binding. It waits until it is.

## What would make it a test

1. Add the five instructions to the law (`zeta/spec.py`, `zeta/vm.py`) and
   the silicon, each with a witness cart that fails without it.
2. The forge emits them; every cart built before stays byte-identical in
   behaviour (the cross, the suite, TND's layers), and the lab's program
   shrinks by the predicted 2,635 words (or the prediction was wrong).
3. Fit at four corners on CI. The core is at 97% of its ALMs: if the
   decode does not fit, that is the generation that said no -- record it,
   and first find the area (the hypothesis's own mechanism: an
   optimization elsewhere has to make the room).
4. Spend the freed page on something that did not fit before, and play it.
