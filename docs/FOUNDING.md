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

    0. fire escape        private mirror of zeta-sdk on GitHub (rz4),
                          build-101 committed as UNGATED      <- in progress
    1. this scaffold      README, FOUNDING, CI skeletons      <- this commit
    2. toolchain image    container: Python 3.14 + Verilator +
                          Quartus Prime Lite; the fit runs in CI
    3. migrate the law    spec/ + sdk/ from zeta-sdk, tests green in CI
    4. migrate silicon/   cross green in CI; gate build 101
    5. methods/ v1        claims schema, mutation enforcement, regen
                          gate, estimate ledger
    6. the glass queue    screenshot gate + requires-glass tagging
    7. LICENSE + docs     settle licensing BEFORE any third-party
                          contact; rewrite SDK docs for someone who
                          did not live through discovery
    8. the flagship       resurrect TEAR (archive/TND) or build the
                          arena -- the first cart with a goal, a fail
                          state and a player loop

## What this repo is not

Not the discovery tree's replacement as history — zeta-sdk's commit
log and docs (ALIEN.md, ZETA0.md, SEAMS.md, FAMILY.md, MYTHOS.md) are
the record of how the machine was found and stay canonical for that.
This repo is where the machine lives now.
