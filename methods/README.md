# methods — the discipline as code

The discovery tree's most durable product was not the machine; it was
the method. This directory turns that method from prose into tooling.
The source texts are zeta-sdk's ALIEN.md (the ledger), MYTHOS.md (the
witnessing protocol) and ROADMAP.md (the rules). The laws to encode:

1. **Witness by mutation.** Every claim gets a cart that witnesses it,
   and the witness is proved live by switching the feature off in the
   law and watching the gate fail. A witness whose mutation run does
   not fail IS a failure. (The shade.zol lesson: a feature that works,
   measured as doing nothing.)
2. **Count bits for state, estimate ALMs for logic.** Four-for-four in
   discovery: repack −50/−37, radix-4 400/131, triangle queue
   100/9,231, sensor 150/832. Storage estimates must be bit counts;
   the schema refuses a cost table whose storage row has no bit
   arithmetic behind it. Corollary: wide muxes are where logic
   guesses run low.
3. **Instrument before inference.** Two failed orthogonal fixes means
   the testbench is the suspect. Identical results across a deliberate
   variation is a broken instrument, not a null result. The instrument
   lied first, twice, in discovery — and said so.
4. **Quote all four corners.** The 24-page texture fit passed at 85C
   and failed at 0C: a core that works warm and glitches cold. A fit
   report with one corner is not a fit report.
5. **A cost written as an absolute is read as a rate.** Label which it
   is. The cliff is not the slope.
6. **Gates must be able to fail.** A gate that cannot fail is not a
   gate. Stubs in CI fail loudly; they never pass vacuously.

Planned contents (FOUNDING step 5):

    claims/        one file per claim: statement, witness cart,
                   mutation, requires-glass flag, status
    ledger/        estimate-vs-measured records, schema-checked
    gaterunner/    runs a claim's witness AND its mutation, refuses
                   a green witness whose mutation stayed green
