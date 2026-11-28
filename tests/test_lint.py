"""test_lint.py -- a ratchet on Verilator's warnings.

WHY THIS EXISTS, precisely. Build 97 widened the texture page selector
from four bits to five, and widened the port at both ends -- zseq's
output and zgpu's input. It did not widen the WIRE BETWEEN THEM in
zeta_top.v, which stayed [3:0]. So pages 16..23 silently became 0..7,
and every one of them sampled a page that was already loaded and
therefore looked entirely plausible. It took a purpose-built cart, a
cross failure, an identity-plane query to find which object, and a
trace of the selector to reach a one-character declaration.

Verilator says so immediately. The build passes -Wno-lint, so nobody
hears it.

THE RATCHET RATHER THAN A CLEAN BILL. There are 108 warnings today,
almost all WIDTHEXPAND on deliberate zero-extension and over-wide
indices into smaller arrays, and chasing them to zero is a separate
job with its own risk. What matters is that the number never goes UP:
a new warning is a new width that somebody did not mean.

AND IT IS CHECKED AGAINST THE ACTUAL BUG, not assumed. Putting the
[3:0] back gives 110. The first guess -- that this was a TRUNCATION and
a WIDTHTRUNC ratchet would catch it -- was measured and was wrong: 18
either way. A narrow wire on a wide port reads as WIDTHEXPAND at both
instances, which is why the ratchet counts every class rather than the
one that sounded right.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SIL = ROOT / "silicon"

# Today's count. LOWER IT when warnings are fixed; think hard before
# raising it, and say in the commit which width was meant.
# 108 at build 97. 110 at 98 (spec.OBJ_LIT), and RAISED DELIBERATELY
# after accounting for every one of the two:
#   zeta_top WIDTHEXPAND 41 -> 44, three lines added to the dreq_addr
#     mux, which already warns once per line for all twenty of them --
#     the mux computes 15 bits and is assigned to 14, and that predates
#     this by a long way.
#   zseq WIDTHTRUNC 2 -> 1, a real 32-into-24 truncation that the
#     change REMOVED: `cb_r <= rd_data` became `cb_r <= vword`.
# The lighting block itself adds none. Counting by FILE AND CLASS is
# what makes that checkable -- a line diff is useless here, because
# inserting lines moves every warning after it.
# 111 at build 102 (SEG_BASE): one more arm on the dreq_addr mux, which
# warns once per line like its twenty siblings (15 bits assigned to 14,
# long predating this). The window adders and the double sweep add none.
# 116, AND THE FIVE BETWEEN WERE NEVER SEEN (2026-11-28). The count on
# exp/yard at 1401a7a, linted with its own generated parameters, is 116:
# five arrived after build 102 and nothing said so, because THIS TEST
# WAS PASSING ON NOTHING. It never wrote silicon/gen/params.vh; in a
# fresh checkout -- which is what CI is -- the include is missing,
# Verilator stops with an error, prints no warnings, and zero is not
# more than 111. A gate that cannot fail. It now generates the
# parameters itself and refuses a lint that did not run.
#   The gaze and the long list (spec.GAZE_BASE, spec.OLX_PTR) add none:
# 116 before them and 116 after, counted by file and class. One did
# appear on the way (the long list's cell as a new arm of dreq_addr) and
# was removed by joining the chain at its own width.
BASELINE = 116


@pytest.mark.skipif(shutil.which("verilator") is None,
                    reason="verilator not installed")
def test_no_new_width_warnings():
    from zeta import silicon
    (SIL / "gen").mkdir(exist_ok=True)
    (SIL / "gen" / "params.vh").write_text(silicon.gen_params())
    (SIL / "gen" / "sinq_init.vh").write_text(silicon.gen_sinq())
    r = subprocess.run(
        ["verilator", "--lint-only", "--top-module", "zeta_sim",
         "-I" + str(SIL / "gen")] + sorted(str(p) for p in SIL.glob("*.v")),
        capture_output=True, text=True, cwd=ROOT)
    errors = [l for l in r.stderr.splitlines() if l.startswith("%Error")
              and "Exiting due to" not in l]      # (its sign-off, not a fault)
    assert not errors, (
        "the lint did not run, so it counted nothing:\n    "
        + "\n    ".join(e[:160] for e in errors[:5]))
    lines = [l for l in r.stderr.splitlines() if l.startswith("%Warning")]
    n = len(lines)
    if n > BASELINE:
        fresh = "\n    ".join(l[:150] for l in lines[-(n - BASELINE) * 2:])
        pytest.fail(
            f"Verilator warnings rose {BASELINE} -> {n}. A new one is a "
            f"width somebody did not mean -- build 97 lost pages 16..23 "
            f"to exactly this, a [3:0] wire on a [4:0] port, and it "
            f"looked plausible because every aliased page was loaded.\n"
            f"    {fresh}")
    assert n <= BASELINE
