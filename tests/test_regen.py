# THE REGEN GATE -- ROADMAP item 25, finally closed.
#
# Generators drift from their carts and nothing checks it: gen_room.py
# was known-broken for months while room.zol kept passing gates, because
# the committed cart is what the machines run and the generator is what
# a human edits. This gate runs every generator and demands it reproduce
# its committed cart byte-for-byte.
#
# The exception table is legislated, measured, and ratcheted BOTH WAYS
# like the lint count: a generator listed here must still be broken for
# its stated reason -- one that quietly starts passing is a table entry
# nothing tests, and the gate fails until the entry is removed.

import subprocess
import sys
from pathlib import Path

import pytest

CARTS = Path(__file__).resolve().parent.parent / "carts"
TIMEOUT = 180  # seconds; the SLOW set is excluded below, not raced

# Generators the gate must SKIP, each with the measured reason.
SKIP = {
    "bunny":   "reads assets/ (gitignored source media) and takes argv",
    "hall":    "SLOW: path-traces its plate for minutes (ROADMAP item 25's own note)",
    "vessel":  "SLOW: path-traces its plate for minutes",
    "stream":  "takes argv: bakes PCM from a source file not in the tree",
    "banked":  "takes argv",
    "orbit":   "takes argv",
    "pageprobe": "takes argv",
    "pick":    "takes argv",
}

# Generators that are EXPECTED TO DRIFT from their committed cart --
# known-broken, kept visible. The gate verifies they STILL drift: an
# entry that starts matching must be removed from this table.
EXPECTED_DRIFT = {
    "room": "known-broken since before the SDK migration (ROADMAP item 25)",
    "shade": "the baker changed under it (E1, the Fibonacci sphere) and the "
             "plate was never rebaked; the committed cart is the one "
             "witnessed on the Pocket. Rebake deliberately, re-witness, and "
             "commit the pair.",
    "bootprobe": ".data 278/280 regenerate as 0 against a committed 3028548 "
                 "-- the generator embeds an environment-dependent value and "
                 "is not deterministic across machines. Seed or delete it.",
}


# Generators that read third-party source media, which lives in the
# gitignored root assets/ -- gated wherever the media is present (a dev
# machine), skipped where it legally cannot be (CI). The film matters
# more than most: it now carries the shelf, so a TEAR change that is
# not regenerated through gen_shelf AND gen_face ships a stale column.
NEEDS_ASSET = {
    "face": CARTS.parent / "assets" / "ps1low-poly-grey-alien.zip",
    # TND's boxer, frozen from the archive by tools/tnd_extract.py
    "tnd": CARTS.parent / "assets" / "tnd" / "boxer.npz",
}


def _gens():
    for g in sorted(CARTS.glob("gen_*.py")):
        name = g.stem[len("gen_"):]
        if (CARTS / f"{name}.zol").exists():
            yield name


def _regen(name: str) -> tuple[int, bytes, bytes, str]:
    """Run gen_<name>.py, return (rc, original, regenerated, stderr tail).

    The generator writes carts/<name>.zol in place; the original bytes
    are restored afterwards no matter what, so the gate never leaves the
    tree dirty.
    """
    cart = CARTS / f"{name}.zol"
    original = cart.read_bytes()
    try:
        r = subprocess.run(
            [sys.executable, f"gen_{name}.py"], cwd=CARTS,
            capture_output=True, text=True, timeout=TIMEOUT)
        regenerated = cart.read_bytes()
        return r.returncode, original, regenerated, r.stderr[-400:]
    finally:
        cart.write_bytes(original)


@pytest.mark.parametrize("name", [n for n in _gens()
                                  if n not in SKIP and n not in EXPECTED_DRIFT])
def test_generator_reproduces_its_cart(name):
    if name in NEEDS_ASSET and not NEEDS_ASSET[name].exists():
        pytest.skip(f"{NEEDS_ASSET[name].name} absent (third-party media)")
    rc, original, regenerated, err = _regen(name)
    assert rc == 0, f"gen_{name}.py exited {rc}: {err}"
    assert regenerated == original, (
        f"gen_{name}.py no longer reproduces carts/{name}.zol -- the "
        f"generator and the cart have drifted. Decide which is right, "
        f"regenerate or fix, and commit the pair together.")


@pytest.mark.parametrize("name", sorted(EXPECTED_DRIFT))
def test_expected_drift_still_drifts(name):
    # the both-ways ratchet: a known-broken generator that starts
    # matching is a stale table entry, and stale tables are how item 25
    # happened in the first place.
    rc, original, regenerated, err = _regen(name)
    still_broken = rc != 0 or regenerated != original
    assert still_broken, (
        f"gen_{name}.py now reproduces its cart -- remove it from "
        f"EXPECTED_DRIFT so the real gate covers it.")


def test_every_skip_names_a_real_generator():
    known = set(_gens())
    for name in list(SKIP) + list(EXPECTED_DRIFT):
        assert name in known, f"table entry '{name}' has no gen/cart pair"
