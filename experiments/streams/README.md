# streams -- what a frame, a body and a program word cost (2026-11-24)

A probe of `docs/ZETA-N-HYPOTHESIS.md` from the yard (TND layer 13). The
player asked whether programs can be streamed, whether baked poses can be
streamed for livelier bodies, and whether detail should follow distance.
Everything here is measured on the law or the simulated silicon unless it
says otherwise. Nothing in the machine was changed.

    python3 experiments/streams/ablate.py            # a frame with parts taken away
    python3 experiments/streams/lodcost.py OUT.json  # one body, by faces and distance
    python3 experiments/streams/ovlcost.py           # program words moved in from the cart
    python3 experiments/streams/cover.py CART.zol TAPE.ztp OUT.pkl   # program words run, by style

(Run from the repository's root with `build/layer13/tnd.zol` built.)

## A yard frame, taken apart

In the ring, the elite and the double on him; the frame is 57% of 864,000
clocks. The same state image with parts removed:

| part | clocks | of a frame | bound by |
|---|---|---|---|
| the clear | 116,360 | 13.5% | fixed |
| the room, 420 faces from data memory | 118,155 | 13.7% | the rasteriser (pixels) |
| bodies and boxes from the cart, 1,885 faces | 154,345 | 17.9% | the sequencer (~78 clocks a face; the rasteriser idles) |
| the program, 29,608 instructions | 105,948 | 12.3% | 3.58 clocks an instruction |
| the HUD | ~50 | 0% | |

- An empty room is 27% of the frame: the clear writes every pixel and the
  room writes every pixel again.
- The eight heaviest frames of a random minute (peak 88.0%) are bound by
  the rasteriser: 283,000-480,000 clocks of walk against a median of
  151,000. Median frames and peak frames have different causes.

## One body, by faces and distance

| faces | at 2.5 | at 5 | at 10 | at 20 |
|---|---|---|---|---|
| 150 | 13,073 | 12,952 | 12,064 | 11,504 |
| 252 | 20,638 | 20,582 | 19,189 | 19,027 |
| 369 | 29,054 | 28,577 | 27,237 | 26,905 |

Clocks over the same frame without it. About 73 clocks a face; distance
moves it by less than a tenth.

His session of P75 (59,381 frames): all cart faces a frame, median 1,897,
most 2,018 of 2,048. The store binds before the clock. Replayed under
other rules (the bodies stood where the present rule put them, so these
are estimates): bodies past 6 units from the lens at 150 faces, median
1,596; the nearest at his own 737, past the store in 71% of frames; the
nearest within 5 at 737 and all others at 150, past it in 13%. (737 is
extrapolated from the three tiers.)

## Program words moved in from the cart

13.27 clocks a word at 1,000, 4,000, 8,000, 16,000 and 29,000 words: a
thousand words is 1.5% of a frame, the whole game program 44.5%. The
words land after the frame's program halts; the next frame runs them.

## Program words run, by style (`cold-yard-p75.json`)

Of the game's 29,005 words, 10,090 (35%) never ran in sixteen and a half
minutes. Only the run 1,366; only a fight style 3,760; all three 13,010.
He changed style at a median of 0.7 seconds. By their labels the words
that never ran are mostly the whole game's machinery that the layer still
builds (the knob menu, the city's nodes, the opening's jumps, the leash,
the prowler), read from a line or two at each label and not confirmed
line by line.

## Poses

766 of his poses are 854,090 words; the yard's cart is 2,124,022 of
4,063,248. A pose is drawn from the cart by offset. The card delivers
1,024 words in four frames and only into data memory. His pose changed
on 55% of frames; 580 of the 766 were shown.

## What was done with it (TND P77)

`forge.reach` drops what no path from word 0 reaches, and the yard's game
is told the hall is off the city's map. 29,211 words -> 25,351, data
memory identical every frame over his session's presses. Two city
pieces no title can list are carried as nothing: data memory 11 words
free -> 1,521.

`dcover.py` (which data-memory words a session reads): of 11,673 named
words a minute's play never reads 4,795; the largest are four of the
city's nine pieces (2,776 words) and most of its map. The other pieces
can be listed at the title (two cannot: see above).

    python3 experiments/streams/dcover.py CART.zol OUT.json TAPE.ztp [TAPE...]

## Supposed, not established

- Streaming by style of play is the wrong cut; by scene is the right one.
- A clear that lays down the floor's colour and depth would give back
  most of the room's 14%. It needs logic; 286 ALMs are free. Not estimated.
- A tier of about 500 faces for the nearest body would fit the store. Not
  baked, not measured.
