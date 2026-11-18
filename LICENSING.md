# Licensing — the split, and why

Decided 2026-11-18. Three instruments, one per kind of thing:

## The code

    spec/, sdk/, methods/,     Apache-2.0        the root LICENSE file
    infra/, docs/, tests
    silicon/                   CERN-OHL-S-2.0    silicon/LICENSE

**Why Apache-2.0 for the contract and the SDK:** zero friction for
developers and studios, an explicit patent grant, and total clarity on
the one question a third party cares most about: **a cart you write
with this SDK is yours, outright.** A cart is your work expressed in
the machine's language, the way a program compiled by a compiler
belongs to its author — nothing in this repository's licensing reaches
into your game.

**Why CERN-OHL-S for the gateware:** the silicon is the machine's
body, and improvements to it stay open. Anyone may build, sell, or
embed Zeta hardware; a derived or modified design must be published
under the same terms. This is the legal echo of the family
constitution: the lineage cannot be enclosed.

## The name

The license permits forking the code; it cannot and does not protect
what "Zeta" MEANS. That is the job of the name policy: see
TRADEMARKS.md. In short — only an implementation that passes the
conformance suite, unmodified, may present itself as a Zeta. Forks are
welcome under any other name.

## Contributions

Contributions are accepted under the Developer Certificate of Origin
(DCO, developercertificate.org): sign your commits with
`git commit -s`. By contributing you license your contribution under
the file's governing license above. No CLA.
