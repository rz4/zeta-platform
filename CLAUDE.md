# Zeta: orientation for an agent working in this repository

Zeta is a console built clean-room on the Analogue Pocket's FPGA, and an
experiment: how much capability one fixed machine can be made to give,
and what is worth making with it. Two loops drive it. Read the document
for the loop you are about to touch before changing anything in it.

- **The machine's loop** -- measure, find the waste, change the
  architecture, see what became possible: `docs/ZETA-N-HYPOTHESIS.md`
  (the hypothesis, and what is established against what is hoped),
  `docs/ZETA0-FRONTIER.md` (the generations), `methods/README.md` (the
  discipline).
- **The player's loop** -- play on the Pocket, bring the tape home, read
  it, let the player turn knobs, change the game, play again:
  `docs/EXPERIENCE-IMPRINTING.md`, `experiments/README.md`.
- The flagship game and its history: `docs/TND-PORT.md`,
  `docs/TND-WORLD.md`, `games/tnd/IMPRINTS.md`.

## Contracts that hold

- **The law is the machine.** `zeta/spec.py`, `zeta/vm.py`,
  `zeta/gpu.py` say what every cart means; the silicon (`silicon/`) is
  bit-equal to them or it is wrong. Check with `zeta cross` and
  `zeta suite`. A new GPU feature needs a witness cart that fails when
  the feature is switched off, and one that sends it through the
  clipper.
- **Sixty frames, every frame.** A frame is 864,000 clocks; the worst
  frame counts, not the average (`zeta budget`, `zeta profile`).
- **Everything is deterministic.** A tape and its cart reproduce a
  session exactly. Do not add anything whose result depends on timing
  the law does not legislate.
- **The fit is real only at four corners**, on CI
  (`gh workflow run fit.yml --ref <branch>`). Estimate logic; count bits.
- **TEAR NOT DEMON is built in layers** (`TND_LAYER=n`), each judged on
  the Pocket. A change for one layer leaves every other layer and the
  full cart (`games/tnd/tnd.zol`) byte-identical. `TND_LAYER` 9 is not
  a layer: it is the default, the whole game.

## When reading a player's session

- Say what was **observed** (counts, frames), what you **suppose**, and
  what the player **said**, separately. A tape shows what was attempted,
  not what was wanted.
- The player's control design is his. Build what he said; where his
  words can be read two ways, ask rather than choose.
- One factor at a time where you can. Record what was turned down
  (`experiments/tnd/REJECTED.md`) as carefully as what was kept.
- A discovery becomes part of the game only when he says so; then give
  it an entry in `games/tnd/IMPRINTS.md` that names its source.

## When changing the machine

- Measure first; two failed fixes mean the instrument is the suspect.
- A capability is claimed when it is witnessed, crossed and fitted, and
  not before. Write down the generation that did not fit.
