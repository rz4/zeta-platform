# THE FIT, AS A GATE. Runs inside ghcr.io/rz4/zeta-quartus: assemble
# the cart, regenerate silicon/gen from spec.py, compile the Pocket
# template, then hold the result to the discipline the discovery tree
# paid for: QUOTE ALL FOUR CORNERS (the 24-page lesson: a core that
# works warm and glitches cold reads as random corruption), and print
# the resource ledger. Exit nonzero on any negative setup/hold slack,
# a failed flow, or a bitstream that did not move (a report that did
# not run is ALIEN.md's oldest bug).
#
# Usage: python3 infra/fit_ci.py [cart.zol]      (default carts/tear.zol)

import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from zeta import cabinet, deploy, silicon  # noqa: E402

cart_path = sys.argv[1] if len(sys.argv) > 1 else "carts/tear.zol"
cart = cabinet.load_cart(str(ROOT / cart_path))

# the inputs Quartus reads: the baked fallback cart and the law's numbers
gen = ROOT / "pocket/gen"
gen.mkdir(parents=True, exist_ok=True)
deploy.write_cart_hex(cart, gen)
sil_gen = ROOT / "silicon/gen"
sil_gen.mkdir(exist_ok=True)
(sil_gen / "params.vh").write_text(silicon.gen_params())
(sil_gen / "sinq_init.vh").write_text(silicon.gen_sinq())

template = ROOT / "pocket/template"
rbf = template / "output_files/ap_core.rbf"
started = time.time()
r = subprocess.run(["quartus_sh", "--flow", "compile", "ap_core"],
                   cwd=template, capture_output=True, text=True)
tail = (r.stdout + r.stderr)[-3000:]
if r.returncode != 0:
    print(tail)
    sys.exit(f"FIT FAIL: quartus_sh exited {r.returncode}")
if not rbf.exists() or rbf.stat().st_mtime < started:
    print(tail)
    sys.exit("FIT FAIL: the flow 'passed' but the bitstream did not move")

# the ledger
fitsum = (template / "output_files/ap_core.fit.summary").read_text()
for key in ("Logic utilization", "Total block memory bits",
            "Total RAM Blocks", "Total DSP Blocks", "Total PLLs"):
    for line in fitsum.splitlines():
        if key in line:
            print(line.strip())

# ALL FOUR CORNERS. ap_core.sta.rpt carries one summary per timing
# model; every worst-case setup/hold slack in every model must be met.
sta = (template / "output_files/ap_core.sta.rpt").read_text(errors="replace")
corners = re.findall(
    r";\s*(Slow|Fast) (\S+) (-?\d+C) Model (Setup|Hold)(?: '[^']*')? Summary"
    r".*?; (\S+)\s+; (-?[\d.]+)\s+;", sta, re.S)
if not corners:
    sys.exit("FIT FAIL: no corner summaries found in ap_core.sta.rpt -- "
             "the parse is broken, which is not the same as passing")
worst: dict[tuple, float] = {}
for model_speed, mv, temp, kind, _clk, slack in corners:
    k = (model_speed, mv, temp, kind)
    worst[k] = min(worst.get(k, 9e9), float(slack))
fail = False
print(f"\n{'corner':<28} {'type':<6} slack")
for (speed, mv, temp, kind), s in sorted(worst.items()):
    flag = "" if s >= 0 else "   <-- VIOLATED"
    if s < 0:
        fail = True
    print(f"{speed} {mv} {temp:<16} {kind:<6} {s:+.3f}{flag}")
if fail:
    sys.exit("FIT FAIL: a timing corner is violated. A fit quoted at one "
             "corner is not a fit.")

# Write the deploy stamp exactly as deploy.run would, so a packaging
# pass after this does not pay a second identical compile. Honest to
# write only here: the compile above was verified by exit code, flow,
# AND a bitstream that moved.
import hashlib  # noqa: E402

from zeta import spec  # noqa: E402

SIL = ROOT / "silicon"
srcs = [SIL / f for f in ("zvm.v", "zgpu.v", "zseq.v", "zsnd.v",
                          "zeta_top.v")]
srcs += [ROOT / "pocket/zeta_glass.v", ROOT / "silicon/gen/params.vh",
         template / "core/core_top.v", template / "ap_core.qsf"]
h = hashlib.sha256()
for p in sorted(srcs):
    h.update(p.read_bytes() if p.exists() else b"")
rbf.with_suffix(".srchash").write_text(f"{h.hexdigest()} "
                                       f"{spec.LOADER_BUILD}\n")

print(f"\nFIT PASS: {rbf.name} written, every corner met, "
      f"{time.time() - started:.0f}s")
