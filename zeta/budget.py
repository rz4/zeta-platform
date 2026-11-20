"""budget.py -- the frame-budget gate.

THE GATE THIS TREE DID NOT HAVE. `lodspan.zol` costs 910,703 clocks
against a 720,000-clock frame -- 126.5% of the budget, so the picture it
draws cannot be drawn at 60 Hz -- and it is GREEN in all thirty-six gate
runs, because cross compares framebuffers and glass compares a scanned
stream and NEITHER CAN SEE TIME. The roadmap says so itself, twice, and
then files a frame-budget gate as "worth having" rather than building
it: "cross and glass cannot see a 50% frame-time regression, and no gate
currently can."

So a feature can halve the machine's speed and every gate stays green.
That is the hole, and this is the plug.

The meter is the silicon's own (zeta_top's `meter`, read out by the
ZETA_CLK line in server.cpp), so the number is what the hardware counted
and not a model of it. The build-91 cost model is 5-40% wrong on
build-94 silicon; this file never uses it.

EXCEPTIONS ARE WRITTEN DOWN, WITH A REASON. A cart over budget is not
automatically a bug -- lodspan is a DIAGNOSTIC that deliberately maxes
perspective-correct fill -- but it must be named here, or it is just a
regression nobody noticed.
"""
from __future__ import annotations

import os
import re
import struct
import subprocess
import tempfile
from pathlib import Path

from . import cabinet, silicon, spec

#: the frame, in core clocks: 51.84 MHz / 60 Hz, from the video law at
#: six clocks a pixel (frontier B5; 720,000 at five, through build 105)
FRAME_CLOCKS = 864_000

#: fail above this fraction of the frame. Not 100%: a cart that fits
#: only in the fast corner does not fit.
CEILING = 0.90

#: cart -> why it is allowed over. Every line here is a debt.
EXCEPTIONS = {
    "lodspan": (
        "a DIAGNOSTIC cart, not content: a tessellated 80-unit textured "
        "plane written to max the perspective-correct fill path and prove "
        "OBJ_LODSPAN's saving. It was over budget (114%) before the "
        "clipper and is over now. Re-author it as content or keep it "
        "here; it must not be silently green."),
}


def measure(cart_name: str, frames: int = 10, pad: int = 0) -> list[int]:
    """Clocks per frame, off the silicon's own meter."""
    sim = silicon.build()
    # A NAME or a PATH. Every other subcommand takes a path, so `budget
    # carts/lit.zol` is the natural thing to type, and it used to build
    # "carts/carts/lit.zol.zol" and die inside the measurement loop --
    # after the header had already printed.
    p = Path(cart_name)
    cart = cabinet.load_cart(p if p.suffix == ".zol"
                             else Path(f"carts/{cart_name}.zol"))
    work = Path(tempfile.mkdtemp(prefix="zeta-budget-"))
    # write_cart_hex returns None for a cart with no CRAM segment, and
    # str(None) on the command line is a file the sim cannot open --
    # which produced no meter rows and, until the line below was fixed,
    # a silent PASS. Filter them.
    paths = [p for p in silicon.write_cart_hex(cart, work) if p]
    env = dict(os.environ, ZETA_CLK="1")
    p = subprocess.Popen([str(sim), *[str(x) for x in paths]],
                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                         stderr=subprocess.PIPE, env=env)
    for _ in range(frames):
        p.stdin.write(struct.pack("<I", pad & 0xFFFF))
        p.stdin.flush()
    p.stdin.close()
    err = p.stderr.read().decode()
    p.wait()
    return [int(m.group(1))
            for m in (re.match(r"CLK (\d+)", l) for l in err.splitlines()) if m]


def run(carts=None, frames: int = 10) -> int:
    """Meter each cart and hold it to the ceiling. Returns a shell code."""
    from .suite import CLAIMS
    names = carts or sorted({c.cart for c in CLAIMS})
    limit = int(FRAME_CLOCKS * CEILING)
    print(f"the frame-budget gate: {len(names)} carts, ceiling "
          f"{limit:,} of {FRAME_CLOCKS:,} clocks ({CEILING:.0%})\n")
    bad, noted = [], []
    print(f"  {'cart':10} {'peak clk/f':>11} {'% frame':>8}  verdict")
    for n in names:
        clks = measure(n, frames)
        if len(clks) <= 2:
            # SILENCE IS NOT A PASS. A cart the meter cannot read is a
            # cart this gate did not check, and reporting that as "ok"
            # is the failure this whole file exists to prevent.
            print(f"  {n:10} {'--':>11} {'--':>8}  NO METER ROWS -- UNCHECKED")
            bad.append((n, -1, -1.0))
            continue
        peak = max(clks[2:])          # skip warm-up frames
        pct = 100 * peak / FRAME_CLOCKS
        if peak <= limit:
            verdict = "ok"
        elif n in EXCEPTIONS:
            verdict = "OVER (declared)"
            noted.append(n)
        else:
            verdict = "OVER -- NOT DECLARED"
            bad.append((n, peak, pct))
        print(f"  {n:10} {peak:11,} {pct:7.1f}%  {verdict}")
    for n in noted:
        print(f"\n  declared exception -- {n}:\n    {EXCEPTIONS[n]}")
    if bad:
        print("\nBUDGET FAIL:")
        for n, peak, pct in bad:
            if peak < 0:
                print(f"  {n}: the meter returned nothing -- UNCHECKED, "
                      f"which is not the same as fine")
            else:
                print(f"  {n}: {peak:,} clocks = {pct:.1f}% of the frame")
        print("Either make them fit, or add a line to budget.EXCEPTIONS "
              "saying why they are allowed to be a cart that cannot run.")
        return 1
    print(f"\nBUDGET PASS: every cart fits 60 Hz "
          f"({len(noted)} declared exception(s))")
    return 0
