# The park: a course that is a field (TND layer 12, P58)

The player, 2026-11-23: "i think what we need is a platforming lab, to test
out all the movement modes. you should be creative to push the zeta
hypothesis" -- then "make the world insanely large and packed with
activities to push the limits ... make it fun to platform, his running jump
felt a bit low before" -- and "we want to be able to have strong platforming
capability".

## The probe of the hypothesis

The census (`experiments/isa/`) found the program page the binding store of
the filled lab. The lab's seven structures are CODE: each is written into
every test that asks about the room -- what holds him up, what puts him out,
the landing arc's probe and its support, the lens, the arena, the drawing.

| | structures | program words they cost | each |
|---|---|---|---|
| the lab (P57, ISA 2) | 7 | 3,115 (26,274 against 23,159 without them) | 445 |
| the park (P58) | unbounded: 3 lanes x 14 kinds x every station | 4,541 (27,700) | 0 |

The park's course is a FUNCTION of a station's number and lane: which kind,
how tight, its boxes' gaps the measured reach of the move it tests times a
tightness (0.70 for the fourteen that teach, then rising to 0.94). It is
unfolded, a station a frame, into a ring of 56 rows in data memory as he
runs; the 8 rows nearest him are copied into a WINDOW, and every test asks
the window. So the code is the same size for ten stations or ten thousand,
and a frame's work is bounded by the window, not the course. The corridor is
16,000 units each way (28 minutes of running east).

It is the window law (`docs/ZETA-N-HYPOTHESIS.md`) in the cart, and the
architecture change the hypothesis is about -- made in software on A(n): the
same machine, a different organization of its stores, and a capability (a
world of any length) that the old organization could not hold at all.

What it costs, over the bot's 97-second run (5,825 frames):

| | the lab (P57) | the park (P58) | limit |
|---|---|---|---|
| VM instructions a frame, median / worst | 12,010 / 44,341 | 27,109 / 50,474 | 65,536 |
| objects, worst | 29 | 53 (drawing stops at 60) | 64 |
| cart-mesh faces, worst | 1,474 | 1,794 | 2,048 |
| data memory free | 1,013 | 248 | -- |
| frame clocks (simulated silicon), median / peak | 51% / 98% (a page swap; 64% since P57) | 60% / 83% | 90% gate |
| law against simulated silicon | -- | 600 frames, 0 pixels differ | bit-equal |

Time went from a fifth of the frame to two-fifths (the ring's 56 rows are
moved and drawn by a loop each frame); data memory is now the tightest
store. The next generation's question is which of those two to spend.

## The stations

Fourteen kinds, each a template of boxes (and orbs). Tops are coloured by
what the station asks: green a plain jump, red a power move (held, flipped),
yellow a mover, black a wall.

| kind | asks for |
|---|---|
| TAP | taps across gaps of the tap's reach |
| STEPS | tap jumps up, a step at a time |
| LONG | A held through the run-up, let go at the edge |
| FLIP | a tap and the flip across a flip's reach |
| FLIP UP | a tap and the flip up onto a top no jump reaches |
| PADS | small pads a tap apart, a little either side |
| SLIDE | waiting for the slider, riding it across |
| LIFT | waiting for the lift, riding it up |
| DROP | up a stair, a flip down and out |
| WALL | a chimney: kick from wall to wall up to a cap above any flip |
| HIGH | a path at 3.0 up: steps, then taps across |
| CHAIN | tap, flip, tap |
| RIDES | slider to lift to a 4.0 ledge (the lift is half a turn from the slider: down as it arrives) |
| TOWER | two flip-ups |

ORBS hang over the gaps and above the hard tops; touched, one is taken and
counted. The HUD shows the streak (stations cleared without touching the
floor between an entry and its last box) and the orbs.

## The movement, in the park only

- the run's tap leaves at 0.235 (was 0.189): 1.28 up, 3.71 far (`reach.py`)
- COYOTE: six frames off an edge, A is still the ground's (the run jumps on
  A's release; a press begun at an edge was cancelled as he ran off it --
  the bot walked off every box until it pressed early)
- a BUFFER: A in the air with the flip spent is kept eight frames
- six wall kicks an air (was two), for the chimneys

## The bot

`bot.py` plays with rules and the real controls, reading the machine's own
memory for what it stands on and what comes next. It cleared 31 stations in
a row in 97 seconds (every kind, then random ones at rising tightness) and
took 38 orbs. Each station it clears is a claim checked: the course can be
done. On the way it found five bugs in the course and one in the game (the
P55 push-out ran before the arena, so a structure in the air was never a wall
touched -- in the park it runs on the ground only).

    python3 experiments/park/bot.py [CART.zol] [STATIONS]
    python3 experiments/park/reach.py [CART.zol]
