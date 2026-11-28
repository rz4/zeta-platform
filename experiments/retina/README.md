# The retina, mocked against the law

2026-11-28. An experiment for `docs/ZETA-RECIPROCAL-DESIGN.md` section 4.2. **Not law, not silicon.**
`retina.py` calls the law's render unchanged, borrows its identity plane, and builds the proposed
record of each object a run at a time, as a flush would. Everything below is **[m] measured on the
law** at `4c308f6`, on the routes in `tools/tnd_meter.py` and idle or simple pads elsewhere.

    python3 experiments/retina/retina.py        # about four minutes

## What was asked

1. Does a record built a run at a time give the law's own count? (It must, or the shape is wrong.)
2. What does it cost? One run is one read-modify-write of one record.
3. Is the object list really short of room?
4. Does one candidate and one counter find an object's neighbour?

## What was found

**The cost: small.**

| cart | frames | runs a frame: median / max | most in a row | most in a band | deepest queue at 2 / 3 / 4 clocks an update |
|---|---:|---:|---:|---:|---:|
| seen | 120 | 259 / 293 | 7 | 122 | 2 / 2 / 2 |
| watched | 120 | 161 / 163 | 3 | 66 | 2 / 2 / 2 |
| edged | 120 | 295 / 302 | 7 | 120 | 2 / 2 / 2 |
| hall | 240 | 38 / 68 | 1 | 32 | 1 / 1 / 1 |
| vessel | 240 | 44 / 74 | 2 | 38 | 1 / 1 / 1 |
| tnd, brawl | 521 | 1,788 / 2,896 | 35 | 599 | 4 / 5 / 6 |
| tnd, tour | 901 | 1,817 / 3,015 | 40 | 633 | 7 / 9 / 10 |

- TND's busiest frame has 3,015 runs of objects in 92,160 pixels. At four clocks an update that is
  12,060 clocks, 1.7% of a frame, and it runs beside the flush, not after it.
- If the flush scanned a pixel a clock (it cannot be faster), updates of four clocks never queue more
  than ten deep. A sixteen-entry queue is enough on everything measured.
- The queue's depth is the one number here that depends on the scene. A cart of one-pixel stripes of
  alternating objects would need 320 runs a row; the law needs a rule for a full queue (stall the flush),
  and a witness for it.

**The answers: exact where they should be.**

| cart | most objects listed | frames with the list full | most seen at once | NBR by vote = the true most common | NBR by widest run = it | a majority existed | VIS wrong | BOX wrong |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| seen | 4 | 0 | 4 | 95.6% | 56.9% | 95.6% | 0 | 0 |
| watched | 6 | 0 | 2 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| edged | 4 | 0 | 4 | 100.0% | 99.8% | 75.0% | 0 | 0 |
| hall | 1 | 0 | 1 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| vessel | 5 | 0 | 2 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| tnd, brawl | 54 | 0 | 46 | 87.5% | 72.4% | 74.1% | 0 | 0 |
| tnd, tour | 62 | 0 | 54 | 88.4% | 75.5% | 74.1% | 0 | 0 |

- VIS built from runs equals `VIS_BASE` on every object of every frame: 0 wrong in 2,262 frames.
- BOX equals a search of the plane on every object of every frame.
- **TND lists 62 objects of 64 on the tour** and shows 54 at once. The list is two entries from full on
  a scripted route. The case for a longer list does not need arguing.

**The neighbour: not good enough as drafted.**

- One candidate and one counter names the object's true most common left neighbour 88% of the time in
  TND. In a quarter of cases no neighbour has a majority at all, and then the vote's answer is whatever
  survived.
- The second draft (the owner left of the object's widest run) is worse: 72-76%.
- So NBR, as one word, is right about seven times in eight where it matters most. That is not a percept
  a game can lean on. Either it gets two candidates, or it is redefined as something exact (the owner
  left of the box's first run), or it is dropped. **It should not go into the law as drafted.**

## Corrections to the design

- The design said identity is 6 bits. In the law it is already 7 bits of owner and 1 of outline
  (`gpu.render`: `own = idbuf & 0x7F`). 256 objects need 9 and 1.
- LUM as the sum of (r + 2g + b) / 4 over 5-bit channels fits the 22 bits the design gave it.

## Not measured

- Any silicon. The flush's real rate, the record RAM's read-modify-write, and the logic are untouched.
- FOV and LUM are computed and unexamined: nothing in the tree uses them yet, so there is nothing to
  hold them against but their own definition.
- Real play. The routes are scripts; the session tapes are not in the repository.
