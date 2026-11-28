# THE FIT, AS A GATE. Runs inside ghcr.io/rz4/zeta-quartus: assemble
# the cart, regenerate silicon/gen from spec.py, compile the Pocket
# template, then hold the result to the discipline the discovery tree
# paid for: QUOTE ALL FOUR CORNERS (the 24-page lesson: a core that
# works warm and glitches cold reads as random corruption), and print
# the resource ledger. Exit nonzero on any negative setup/hold slack,
# a failed flow, or a bitstream that did not move (a report that did
# not run is ALIEN.md's oldest bug).
#
# Usage: python3 infra/fit_ci.py [cart.zol]      (default games/tear/tear.zol)

import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from zeta import cabinet, deploy, silicon  # noqa: E402

cart_path = sys.argv[1] if len(sys.argv) > 1 else "games/tear/tear.zol"
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


def testimony():
    """WHAT RAN OUT, AND WHERE IT WENT. A flow that dies in the fitter
    says "can't fit design in device" and nothing else in its last 3,000
    characters; the reports say which resource, and synthesis has already
    counted every module and named every memory it did or did not infer.
    Print those, because a failed fit's reports are otherwise an artifact
    somebody has to be able to download."""
    out = template / "output_files"
    for name in ("ap_core.map.summary", "ap_core.fit.summary"):
        f = out / name
        if f.exists():
            print(f"---- {name} ----")
            print(f.read_text(errors="replace").strip())

    def section(report, title, keep=lambda l: True):
        f = out / report
        if not f.exists():
            return
        lines = f.read_text(errors="replace").splitlines()
        hits = [i for i, l in enumerate(lines) if l.startswith(";") and title in l]
        if not hits:
            return
        print(f"---- {report}: {title} ----")
        n = 0
        for l in lines[hits[-1]:]:
            if l.strip() == "" and n > 3:      # the table has ended
                break
            if n < 4 or keep(l):               # its heading, then what is ours
                print(l[:230])
            n += 1

    ours = lambda l: any(k in l for k in ("u_gpu", "u_seq", "u_top", "u_mesh",
                                          "zsnd", "zvm", "zimem", "u_core",
                                          "Compilation Hierarchy"))
    section("ap_core.map.rpt", "Analysis & Synthesis RAM Summary")
    section("ap_core.map.rpt", "Analysis & Synthesis Resource Utilization by Entity",
            keep=ours)
    section("ap_core.fit.rpt", "Fitter Resource Usage Summary")
    for rep in ("ap_core.fit.rpt", "ap_core.map.rpt"):
        f = out / rep
        if f.exists():
            errs = [l[:300] for l in f.read_text(errors="replace").splitlines()
                    if l.startswith("Error") or "requires" in l.lower()
                    and "but" in l.lower()]
            if errs:
                print(f"---- {rep}: errors ----")
                print("\n".join(errs[:40]))


if r.returncode != 0:
    print(tail)
    testimony()
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
    # NAME THE CULPRIT before failing: the worst paths at every corner
    print("\n---- the failing fit's testimony (infra/worst_paths.tcl) ----")
    w = subprocess.run(["quartus_sta", "-t", "../../infra/worst_paths.tcl"],
                       cwd=template, capture_output=True, text=True)
    # keep the PATH lines -- the first version of this filter kept only
    # the slacks and threw the node names away, which is a testimony
    # that says how badly something failed but not what
    keep = [l for l in (w.stdout + w.stderr).splitlines()
            if l.startswith("========") or "Path #" in l
            or "From Node" in l or "To Node" in l
            or "Slack" in l or "Error" in l]
    print("\n".join(keep[:120]))
    # THE FAMILIES. A failing clock fails in groups of paths that share a
    # cause, and 400 path lines hide them: tally the VIOLATED setup paths
    # by (from, to) with the bit indices and the hierarchy stripped.
    fam: dict[tuple, list] = {}
    cur = None
    for l in keep:
        m = re.search(r"Setup slack is (-?[\d.]+)", l)
        if m:
            cur = [float(m.group(1)), None, None]
        elif cur and "From Node" in l:
            cur[1] = l.split(":", 2)[-1].strip()
        elif cur and "To Node" in l:
            cur[2] = l.split(":", 2)[-1].strip()
            if cur[0] < 0:
                key = tuple(re.sub(r"\[\d+\]|_OTERM\d+|~\S+", "", n.split("u_top|")[-1])
                            for n in cur[1:])
                fam.setdefault(key, []).append(cur[0])
            cur = None
    if fam:
        print("\n---- violated setup paths by family (all corners) ----")
        for (a, b), v in sorted(fam.items(), key=lambda kv: min(kv[1])):
            print(f"{min(v):+.3f}  x{len(v):<4} {a}  ->  {b}")
    sys.exit("FIT FAIL: a timing corner is violated. A fit quoted at one "
             "corner is not a fit.")

# Write the deploy stamp exactly as deploy.run would, so a packaging
# pass after this does not pay a second identical compile. Honest to
# write only here: the compile above was verified by exit code, flow,
# AND a bitstream that moved.
import hashlib  # noqa: E402

from zeta import spec  # noqa: E402

SIL = ROOT / "silicon"
srcs = [SIL / f for f in ("zvm.v", "zimem.v", "zgpu.v", "zseq.v", "zmesh.v", "zsnd.v",
                          "zeta_top.v")]
srcs += [ROOT / "pocket/zeta_glass.v", ROOT / "pocket/zeta_tape.v",
         ROOT / "silicon/gen/params.vh",
         template / "core/core_top.v", template / "ap_core.qsf"]
h = hashlib.sha256()
for p in sorted(srcs):
    h.update(p.read_bytes() if p.exists() else b"")
rbf.with_suffix(".srchash").write_text(f"{h.hexdigest()} "
                                       f"{spec.LOADER_BUILD}\n")

print(f"\nFIT PASS: {rbf.name} written, every corner met, "
      f"{time.time() - started:.0f}s")
