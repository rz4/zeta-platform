"""test_suite.py -- the standing gate's own gate.

The suite exists because hall.zol's delivery path had no standing
proof. That failure mode is recursive: a coverage table nobody checks
rots exactly the way the coverage did, and a rotted table is worse than
none, because it REPORTS proof it does not have.

So two things are pinned here. Every claim must still be witnessed by
its cart -- that is the table staying honest as the carts change. And a
witness must be able to say NO -- that is the table being a gate at all
(carts/fade.zol once passed glass with the compositor doing literally
nothing, which is the whole reason witnesses exist).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import asm, spec, suite


def test_every_claim_is_witnessed_by_its_cart():
    """~7 s of machine 1, and worth it: this is what fails the day a
    cart drifts off the feature it is supposed to be proving."""
    bad = suite.check_witnesses()
    assert not bad, "claims no longer witnessed:\n  " + "\n  ".join(bad)


def test_a_witness_can_say_no():
    """cube.zol draws geometry and nothing else -- so the compositor,
    texture, backdrop and audio witnesses must all REFUSE it. A witness
    that passes anything you hand it proves nothing about the cart it
    was written for."""
    o = suite.Observed(asm.assemble(suite._cart_path("cube")))
    refused = {c.cart: c.witness(o) for c in suite.CLAIMS
               if c.cart in ("fade", "tex", "hall", "voice", "overlay")}
    assert not any(refused.values()), \
        f"these witnesses accepted a plain geometry cart: {refused}"


def test_the_table_covers_the_features_that_have_registers():
    """A subsystem with a register in spec.py and no line in the table
    is a subsystem nothing gates -- which is exactly how the backdrop
    went unproven. Not every feature can be found this way, but the
    ones with their own control register can."""
    covered = " ".join(c.proves.lower() for c in suite.CLAIMS)
    for reg, word in ((spec.BG_SRC, "backdrop"), (spec.CO_BASE, "compositor"),
                      (spec.TEX_SRC, "textur"), (spec.OVL_GO, "overlay"),
                      (spec.DMA_GO, "mover"), (spec.LOD_FLAT, "lod_flat")):
        assert word in covered, f"no claim mentions {word} (register {reg})"


def test_claims_name_real_carts():
    for c in suite.CLAIMS:
        assert suite._cart_path(c.cart).exists(), f"{c.cart}.zol is missing"
