# Founding plan — from primordial soup to platform

Written 2026-11-18. The discovery tree (`zeta-sdk`, Aug 2026, 251
commits in ten days, builds 0–101) proved the machine and the method.
This repository is the enterprise foundation built from it. The driver
is practical: synthesis was heavy enough to destabilize the development
desktop, and the project's only copy lived on that machine.

## The four boundaries

One repo, four hard boundaries. The spec's version is the only thing
that crosses them.

    spec/       THE CONTRACT. spec.py + the law (vm, gpu, audio as
                executable specification) + the conformance suite.
                Versioned, published. FAMILY.md's constitution lives
                here: the seed (constitutional, eternal) vs. the rings
                (per-generation LIMITS[gen]), CART_GEN, and spec0
                frozen as the goldens of every future generation.
    silicon/    ONE IMPLEMENTATION of the contract (Zeta-0: the
                Pocket's Cyclone V). Held to spec/ by the cross gate.
                Zeta-1 (MiSTer-class) will be a sibling, not a fork.
    sdk/        THE PRODUCT for developers: forge, asm, cabinet
                (pygame, thousands of fps, no hardware needed).
                A third party's whole dev loop lives here.
    methods/    THE DISCIPLINE AS CODE. Claims as structured files;
                the gate runner that enforces witness-by-mutation
                (a witness whose mutation run does not fail is itself
                a failure); the estimate ledger schema (count bits
                for state, estimate ALMs for logic); the regen gate
                (ROADMAP item 25: generators must reproduce their
                carts).

## CI stages, mapped to the gates that already exist

    stage         discovery-tree ancestor        runs on
    law           pytest tests/ (166 tests)      every push
    regen         item 25 (new)                  every push
    lint-ratchet  tests/test_lint.py             every push
    cross         zeta cross, Verilator          every push (per-cart matrix)
    soak          F1 (100k ticks, 1200-frame     nightly
                  cross)
    fit           Quartus Prime Lite, ALL FOUR   nightly + on silicon/ change
                  CORNERS quoted (the 24-page
                  lesson), ALM/M10K/DSP ledger
    glass         SEAMS 4 screenshot gate        batched queue, manual;
                                                 claims tagged requires-glass

The first pipeline run has a named job: **gate build 101** (the
registered vertex C, committed UNGATED at the end of discovery) —
cross every cart, fit at 43.2 and DIV=6, quote all four corners,
meter the one-clock-per-face cost against the 144,000 clocks the
clock raise buys.

## The glass queue

Glass is the one serial resource. Three moves:

1. The screenshot gate (SEAMS 4): `zeta witness shot.png` + the tape
   reproduces the Pocket's pixels on machine 1 or convicts the
   hardware. A witnessing becomes a photo upload.
2. Claims carry a `requires-glass` attribute; CI is green without
   them; a weekly session burns down the queue.
3. Machine 2.5: a MiSTer-class Cyclone V board, USB-programmable,
   automatable — continuous silicon testing AND Zeta-1's future
   window in one purchase. The Pocket remains the final witness.

## Sequence

    0. fire escape        DONE 2026-11-18. zeta-sdk private on GitHub,
                          build-101 committed as UNGATED.
    1. this scaffold      DONE 2026-11-18.
    2. toolchain image    gates image DONE (ghcr.io/rz4/zeta-gates,
                          pinned, validated); the quartus image build
                          remains (one-time, ~15 GB, see infra/).
    3. migrate the law    DONE 2026-11-18, flat layout (the
    4. migrate silicon/   four-boundary refactor is future work).
                          233 tests green in CI; `zeta suite --gate
                          both` green in CI -- every claim, both
                          machines, witnessed, on every push.
    5. methods/ v1        regen gate DONE (and it caught gen_shade and
                          gen_bootprobe drifting on its first run,
                          beyond the known gen_room). Estimate ledger
                          DONE: methods/ledger/ledger.tsv, schema-
                          checked, storage rows must count their bits.
                          Claims-as-files and mutation enforcement
                          remain (the suite's --witness-only is the
                          seed).
    6. the glass queue    SCREENSHOT GATE DONE: `zeta witness` holds a
                          Pocket Menu+Start capture against the law's
                          panel() -- frame search or exact, integer
                          upscales accepted only if uniform, and the
                          PAD-LOG TAPE FORMAT legislated with it (one
                          word a line, @start N). Six tests prove it
                          by mutation. requires-glass claim tagging
                          remains.
    7. LICENSE            DONE 2026-11-18. SDK docs DONE:
                          docs/GETTING-STARTED.md, written for someone
                          who did not live through discovery, every
                          number verified against spec.py.
    8. the flagship       DECIDED: TEAR. docs/FLAGSHIP.md -- tear.zol
                          already has a goal, a fail state and a loop
                          (the only cart that does, with balance
                          pinned by replay tests); the July TND
                          archive is the design quarry; the staged
                          plan is nearly all content. Biggest gap:
                          decision depth (one move, no block, no
                          second pad).
    9. gate build 101     cross HALF DONE: the migrated tree includes
                          build 101 and the CI suite passes on it.
                          The fit waits on the quartus image, which
                          waits on a human browser download (Intel
                          gates the installer): drop
                          QuartusLiteSetup-25.1std.0.1129-linux.run
                          and cyclonev-25.1std.0.1129.qdz into
                          infra/quartus-dist/ and build per infra/.

## What this repo is not

Not the discovery tree's replacement as history — zeta-sdk's commit
log and docs (ALIEN.md, ZETA0.md, SEAMS.md, FAMILY.md, MYTHOS.md) are
the record of how the machine was found and stay canonical for that.
This repo is where the machine lives now.
