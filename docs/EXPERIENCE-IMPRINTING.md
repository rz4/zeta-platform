# Experience imprinting

The second loop. `docs/ZETA-N-HYPOTHESIS.md` is about what the machine
can be made to do; this is about finding, with the player, what is worth
making it do -- and keeping what is found.

    play on the Pocket -> the tape comes home on the card -> the desk
    replays it and reads what happened -> the player turns knobs and says
    what he felt -> a change is made and proved -> a new cart goes back

The Pocket runs no model. The card is the exchange between the fixed
console and the desk, and that is the design, not a convenience: the
experience is always produced by the same machine it is judged on.

## What exists (2026-11-23)

| Piece | Where | State |
|---|---|---|
| The recorder: one pad word a frame, from power-on | `pocket/zeta_tape.v`, `zeta/tape.py` (ZTP0) | on the Pocket since build 106 |
| Bringing a tape home, naming its game by its sum | `zeta sd tape` (`zeta/sdcard.py`) | used every session |
| The session again, exactly, on the law | `zeta replay`, `tape.replay` | exact: every delay is legislated (`docs/PLATFORM.md`, Replays) |
| What it cost, frame by frame, on the silicon's meter | `zeta profile`, `zeta budget` | used |
| The knobs: SELECT held, the pad turns them, on the glass | `games/tnd/gen_tnd.py` (`KNOBS*`, the tuner) | pages for the base, layers 1-2, the lab |
| A turn of a knob is on the tape | (the tuner is in the game) | so knob history needs no second recorder |
| The game's own cells, read back from a replay | the forge's `; name: N words at A` comments | by hand until now |
| **An experiment record** | `zeta/experience.py`, `experiments/` | **new: first record `tnd-lab-0001`** |
| **A knob registry** | `games/tnd/axes.json` | **new: the lab's fifteen** |
| **An observer for the game** | `games/tnd/observe.py` | **new** |
| **Imprints and rejections** | `games/tnd/IMPRINTS.md`, `experiments/tnd/REJECTED.md` | **new, written from the record so far** |

What does not exist: knobs that survive power-off (each session starts
at the cart's defaults; where the player left them is only on the tape);
an axis that moves several knobs together; the save across sittings; any
automatic step from a record to a change.

## A replay is evidence of what was attempted

With the game's cells beside the pad, a tape shows more than buttons:
presses during a recovery, the same approach made again and again, a
button held for half a minute, a knob turned down and left there, where
the player stood for ninety seconds and what he did there.

Three kinds of statement, never mixed:

- **Observed** -- a count, a rate, a frame range. "Y was pressed with B
  held 20 times, all in slowed time." A machine can vouch for it;
  `observe.py` writes only these.
- **Supposed** -- what it might mean, with the alternatives. "He may be
  looking for a heavy blow out of the gun's stance; or it may be the
  nearest button."
- **Said** -- the player's own words. These outrank both.

A tape cannot prove frustration, enjoyment or intent. Two cases from
this tree, kept as warnings:

- Twenty-four of twenty-nine minutes in the range and two in the ring
  read as a preference. It was a bug: the ring's dummies came back in
  the street, and the ring was empty (TND-PORT P41b).
- "Scripted routes undersample play" was inferred from a feeling of
  smoothness; the first real tape refuted it (PLATFORM, Replays).

When the reading matters and is uncertain, ask the player.

## The knobs

A knob is the player's way of saying which direction, and how far.

- Each has a **stable id**, a plain account of what it is, a
  **default**, a **step**, bounds, a unit, what **turning it up means**,
  and the mechanics it moves (`games/tnd/axes.json`).
- A setting is a **signed number of notches from the default**. Up is a
  direction on that axis, not "better". Nothing here assumes the
  maximum of anything is wanted.
- The registry carries a `mapping_version`. Changing what an id moves is
  a new version, never a quiet new meaning.
- Today an axis is one knob and the knobs are mechanical ones (weight,
  knock, lift). Axes of *experience* -- commitment, aggression,
  forgiveness -- that move several mechanics together are proposed. They
  should be introduced one at a time, from something a tape showed.

## An experiment

1. A pattern in one or more tapes, with its frames.
2. More than one reading of it, where there is more than one.
3. One axis, or one change, proposed.
4. The player chooses direction and size (a knob on the glass), or says
   it in words.
5. One controlled variant. One factor where that is possible.
6. Proof: the game's tests; the cross against the silicon; the frame
   budget; every other layer byte-identical.
7. A cart, and a new session on the same machine.
8. The next tape against the baseline, with the same observer
   (`python3 -m zeta.experience compare A.json B.json`).
9. Kept, revised or rejected -- by the player.

People adapt, and novelty wears off: a second session differs from a
first for reasons that are not the change. Same seed, same cart and a
paired replay isolate the mechanics; they do not isolate the person.

## The record (`experiments/`)

One file an experiment, `zeta-xp-1`. The machine writes its half; people
write theirs beside it, and a re-ingest keeps theirs.

| Part | Written by | Holds |
|---|---|---|
| `machine` | `zeta.experience ingest` | the tape's hash and header, the cart's sum, the commit and recipe it was built from, the backend |
| `evidence` | the same | frames, and a hash of the law's whole data memory at the end of the replay |
| `knobs` | the same | per knob: default, final, signed notches, frames at each value, each change |
| `observed` | the game's observer | counts, rates, frame ranges |
| `human` | a person | what the player said, in his words; which knobs he chose |
| `agent` | the agent | observations with frames, readings and alternatives, what is proposed, how sure |
| `result` | a person | the commits, what was proved, what it cost, the next record, and the verdict |

No framebuffer is stored: the tape and the cart reproduce every pixel.
The tape itself stays in `build/tapes/` on the desk; the record carries
its SHA-256. (Whether tapes are published with the repository is the
player's decision and has not been made.)

## Imprints, and what was turned down

An **imprint** is a discovery promoted into the game: a mechanic, a
rule, an encounter, a camera move. `games/tnd/IMPRINTS.md` lists them,
each with its statement, its status, the experiment or session it came
from, and where it is held in code and tests -- so the reason for a
design decision can be found from the decision.

- **validated**: the player judged it on the Pocket and said so.
- **adopted**: he specified it and plays with it; no verdict in words.
- **candidate**: built, not yet played.

`experiments/tnd/REJECTED.md` is the other half: what was tried and
turned down, with his words. A rejected region of the space is knowledge
too, and it keeps the same idea from being proposed twice.

The aim is not to tune the game toward one sequence of inputs. It is to
widen the set of interesting situations it can produce -- with
challenge, variety, surprise and consequence kept.

## The two loops

A wanted experience can ask for geometry, poses or memory movement the
machine does not have: that is a requirement on the architecture, and it
goes through that loop's gates. An architectural change can make a kind
of play possible that was not: that is a candidate here, and it goes
through the player. Neither overrides the other: a hardware change is
not an improvement because it measures well, and a gameplay change is
not one because it was cheap.

## The first record

`experiments/tnd/tnd-lab-0001.json`: 32 minutes of the lab on the
Pocket. Observed: long jab strings never missed; the pass (Y with B
held) twenty times, all in slowed time; the lift knob at 1.0 for 22
minutes and then at 0 for ten, after bodies went 6.5 units up. Said: the
string should be four and a miss, the gun held ready, the lens on the
juggled body. Changed: TND-PORT P43.

`experiments/tnd/tnd-lab-0002.json`: the comparison -- 38 minutes of
P43's lab, the same observer (`python3 -m zeta.experience compare`).
The cap held (highest body 2.28 units against 6.47) and he left every
knob but `who` alone; five or more jabs in a row still landed twenty
times, so "the fifth should miss" is not yet met. He has not spoken of
the session, so nothing in it is judged: the loop has gone round once
on the machine's side and is waiting on its other half.
