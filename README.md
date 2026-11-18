# Zeta

A console held to a readable law.

Zeta is a deterministic game console: a ~1,300-line Python specification
(`spec.py`) **is** the machine, and every implementation — the software
cabinet, the Verilated silicon, the FPGA on real glass — is held to it
bit-for-bit, frame-for-frame, by gates that can fail. From that one
commitment, everything unusual follows:

- **A run is a proof.** A session is a seed plus pad words; any machine
  reproduces it bit-for-bit or convicts it. Speedruns verify by
  checksum. A tournament result is a theorem.
- **Sixty is a theorem, not a target.** Every frame is bounded at
  720,000 clocks by law. The machine has no crash state.
- **Nothing ever loads.** Content arrives at a legislated instant;
  world-step cost is independent of world size (measured: 256× the
  world, the same cost to the word).
- **The machine perceives its own output.** How many pixels of each
  object were shown (VIS) and how much of each voice was heard (AUD)
  feed back into the next tick.
- **Netplay is pad words on a wire.** Divergence is not a bug to debug;
  it is a gate failure with an exact location.

**Zeta-0**, the first generation, lives in the Analogue Pocket's window:
320×288 at a locked 60, ~2,000 exact subpixel triangles a frame,
path-traced rooms whose depth and shadow light the live actors, 16
sample-exact voices. Gen-5.5 muscle, 2003–2005 technique, and four
properties no console of any era can express. The family constitution
(seed vs. rings, `CART_GEN`, the cross-across-generations gate) binds
every future Zeta-N to run every Zeta-0 cart identically — not
compatibly, identically — and proves it.

## This repository

This is the enterprise foundation for the Zeta platform — the contract,
the gates, and the method, extracted from the discovery tree
(`zeta-sdk`, 2026-08, build ~101). It exists so that:

1. development runs in the cloud, not on one desktop;
2. the spec is a versioned, published **contract** third parties can
   build against;
3. the project's method — witness-by-mutation, the estimate ledger,
   instrument-before-inference — is enforced by tooling, not prose;
4. glass testing is a batched verification queue, not a bottleneck.

See `docs/FOUNDING.md` for the plan and current status.

## Status

Scaffold. The discovery tree is being migrated; nothing here is
authoritative yet.

## License

Apache-2.0, except `silicon/` which is CERN-OHL-S-2.0 — see
`LICENSING.md` for the split and why, and `TRADEMARKS.md` for what the
name Zeta requires. The short version for game developers: **a cart
you write with this SDK is yours, outright.**
