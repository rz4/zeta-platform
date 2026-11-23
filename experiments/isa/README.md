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

(Corrected below by the census: over ALL 16,109 frames of his session the
instruction worst was 54,898 and the clock worst 98% -- the ~27,000 and the
58-65% sampled too little. The conclusion about time held for play; the
outliers were the arc and the page swap, both since fixed.)

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

## The test, run (2026-11-23, branch exp/isa2)

Built: nine instructions in the law and the silicon (`pushh` and `ori` for a
32-bit constant; `abs`, `neg`, `mini`, `maxi`; `jnlt` and `jne`, a compare
with its branch), a witness cart (`carts/witness/isa2.zol`, 45 checks on
the edges against the first set's long way, a suite claim), and a forge
pass (`zeta.forge.isa2`) the lab and the reactor opt into (`TND_ISA`).

| | predicted | measured |
|---|---|---|
| the lab's program | 2,635 words back | **2,697 back** (29,015 -> 26,318) |
| the intro and pause programs | -- | 700 back each |
| his P55 session (16,109 frames) on both | the same game | same motion, same end-state hash |
| instructions a frame, median / worst | 4.8% fewer | 12,579 -> 11,939 / 54,898 -> 53,389 |
| law against simulated silicon | bit-equal | 333 and 217 frames, 0 pixels differ |
| every other cart and TND layer | unchanged | byte-identical |
| **the fit, four corners** | the core was at 97% | **fits: 18,194 of 18,480 ALMs (98%), worst setup slack +0.706 ns (slow, 85 C)** |

So the first step of the hypothesis's loop closed on real numbers: an
A(n+1) measured on A(n), predicted within 2.4%, built, crossed and fitted.
It cost 260 ALMs. The core now has 286 ALMs left -- the next generation
has to make room before it adds anything.

## The census: every component against its limit (`census.py`)

The same session, every frame (`census-lab.json`), plus the simulated
silicon's own frame meter (`zeta profile`, all 16,109 frames):

| component | median | worst | limit | worst share |
|---|---|---|---|---|
| objects | 19 | 29 in play (59 in the opening second) | 64 | 45% (92%) |
| display-list triangles | 1 | 146 | 256 | 57% |
| cart-mesh faces (the fighters) | 1,474 | 1,474 | 2,048 | 72% |
| cart-mesh vertices | 994 | 994 | 2,048 | 49% |
| VM instructions | 12,010 | 53,389 | 65,536 | **81%** |
| frame clocks | 51% | **98%** | 90% gate | **2 frames over** |
| program page (the game) | -- | 26,318 | 32,768 | 80% |
| data memory free | -- | 1,013 words | ~11,700 | 91% used |

Three findings the averages hid:

1. **The worst frames were not where the time goes.** The two frames past
   the 90% gate in 268 seconds (98% and 91%) ran under 10,500 instructions
   and drew an ordinary picture: they were the PAUSE opening and closing,
   each copying the whole 32,768-word program page to bring in a program
   of 10,400 (or 26,000). P57 copies the incoming program's own length:
   the pause opening 98% -> 64%, closing 91% -> 81%, the intro into the
   game 64% -> 54% (simulated silicon, the same frames of his session).
   Nothing in his session is now over the gate.
2. **The worst instruction frames were the landing arc.** 54,898 of 65,536
   in one frame, 40,000 of them the arc's walk testing every structure's
   four bounds at every step. The arc's tests now give up at the first
   failed bound, the north wall's line first: worst 53,389 -> 44,341,
   frames over 45,000 from 424 to 0, the marks identical frame for frame.
   What remains at the top is the opening seconds (the first 120 frames,
   the turn and the threading), not play.
3. **In play, nothing per frame is near its store.** Objects reach 29 of 64
   (59 only in the opening second, the intro's demons in pieces), the
   display list 146 of 256, the fighters' faces 1,474 of 2,048. What binds
   is what the cart HOLDS -- the program page and data memory -- and the
   ALMs to give the machine anything new.

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
