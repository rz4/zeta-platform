# The estimate ledger, schema-checked. The rule it encodes is the
# discovery tree's hardest-won: ESTIMATES ARE WORTH SOMETHING FOR LOGIC
# AND NOTHING FOR STORAGE -- anything that stores state gets its BITS
# counted, and a ledger row claiming storage without bit arithmetic is
# refused. New silicon work appends a row BEFORE it is built (the
# estimate) and completes it after (the measurement); the ledger is how
# the project knows what its own guesses are worth.

import csv
from pathlib import Path

LEDGER = (Path(__file__).resolve().parent.parent
          / "methods" / "ledger" / "ledger.tsv")
KINDS = {"logic", "storage", "mixed"}


def _rows():
    with open(LEDGER, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def test_schema():
    rows = _rows()
    assert rows, "the ledger is empty"
    for r in rows:
        assert r["kind"] in KINDS, f"{r['item']}: kind '{r['kind']}'"
        int(r["est_alm"]); int(r["measured_alm"])   # must parse
        assert r["note"].strip(), f"{r['item']}: a measurement needs a note"


def test_storage_rows_count_their_bits():
    for r in _rows():
        if r["kind"] in ("storage", "mixed"):
            assert r["bits"].strip(), (
                f"{r['item']}: a storage estimate with no bit count is "
                f"the exact mistake this ledger exists to prevent")


def test_the_rule_still_holds_in_the_data():
    # the ledger's own witness: if the historical record stops showing
    # storage estimates missing worse than logic ones, the rule should
    # be re-examined rather than recited.
    def miss(r):
        est, got = abs(int(r["est_alm"])), abs(int(r["measured_alm"]))
        return max(est, got) / max(1, min(est, got))
    rows = _rows()
    logic = [miss(r) for r in rows if r["kind"] == "logic"]
    storage = [miss(r) for r in rows if r["kind"] == "storage"]
    assert max(storage) > max(logic), (
        "storage estimates no longer miss worse than logic ones -- "
        "the count-the-bits rule has lost its evidence; re-derive it")
