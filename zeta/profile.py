"""THE PROFILE: what a recorded session cost, frame by frame, on the silicon.

The frame meter (zeta_top's stage counters, ZETA_CLK) is exact but slow:
the Verilated core runs a busy game at about two frames a second, so five
minutes of real play would take hours from power-on. The machine's whole
state between two frames is legislated, though (spec.STATE_*), and the
law replays a tape at thirty frames a second. So:

  1. the law replays the tape once, keeping a state image every `window`
     frames (cabinet.VirtualMachine.pack);
  2. each window is run on the silicon FROM ITS IMAGE
     (silicon.SiliconMachine(state=...)), all windows at once.

The picture and the sound after such a start are bit-equal to the law's
(tests/test_resume.py), and the work the machine does -- pixels walked,
triangles skipped -- is the uninterrupted run's exactly. The clock total
differs by tens of clocks in hundreds of thousands: the PSRAM model
stalls on a pseudo-random refresh (cram_sync_chip.v), and where its
sequence stands is the simulation's history, not the machine's state.
"""
from __future__ import annotations

import multiprocessing
import os
import shutil

from . import budget, cabinet, silicon

STAGES = ("clr", "walk", "idle", "stall", "seq", "blkd", "skp")
WINDOW = 240                    # frames a window: four seconds of play


def snapshots(cart: dict, pads, window: int = WINDOW):
    """Replay on the law; yield (first frame, state image, the card then)
    as each is reached. A boundary where a card request is in flight is
    refused by the law (spec.STATE); the window simply begins a frame or
    two later."""
    m = cabinet.VirtualMachine(cart)
    due = 0
    for f, p in enumerate(pads):
        if f >= due:
            try:
                yield f, m.pack(), {k: list(v) for k, v in m.vm.sd.items()}
                due = f + window
            except cabinet.StateBusy:
                pass
        m.frame(p)


def _spans(cart, pads, window):
    """(first, last, image, card) a window, each handed over as soon as
    the law has reached the NEXT one's start -- so the silicon is already
    costing the opening of a session while the law replays the rest."""
    held = None
    for f, st, sd in snapshots(cart, pads, window):
        if held:
            yield held[0], f, held[1], held[2]
        held = (f, st, sd)
    if held:
        yield held[0], len(pads), held[1], held[2]


def cost(cart: dict, pads, state: bytes | None = None, first: int = 0) -> list[dict]:
    """These pads on the silicon, from power-on or from a state image:
    one row a frame -- {'frame', 'clk', and the meter's stages}."""
    work = silicon.scratch("zeta-profile-")
    with open(work / "meter.txt", "wb") as err:
        s = silicon.SiliconMachine(cart, state=state, env={"ZETA_CLK": "1"}, stderr=err)
        for p in pads:
            s.frame(p)
        s.close()
    meter = (work / "meter.txt").read_text()
    shutil.rmtree(work, ignore_errors=True)     # a worker never reaches atexit
    rows = []
    for ln in meter.splitlines():
        if not ln.startswith("CLK "):
            continue
        kv = dict(x.split("=") for x in ln.split()[2:])
        rows.append({"frame": first + len(rows), "clk": int(ln.split()[1]),
                     **{k: int(kv[k]) for k in STAGES if k in kv}})
    if len(rows) != len(pads):
        raise SystemExit(f"the silicon metered {len(rows)} of {len(pads)} frames "
                         f"from frame {first}")
    return rows


_JOB = {}                       # the cart and the pads, shared with the workers by fork


def _window(args):
    first, last, state, sd = args
    cart = dict(_JOB["cart"], sd=sd)
    return cost(cart, _JOB["pads"][first:last], state if first else None, first)


def profile(cart: dict, pads, window: int = WINDOW, jobs: int | None = None,
            say=None) -> list[dict]:
    """Every frame of the session, costed on the silicon, in parallel."""
    pads = list(pads)
    silicon.build()                             # once, before the workers fork
    _JOB.update(cart=cart, pads=pads)
    n = -(-len(pads) // window)
    jobs = jobs or max(1, min(n, (os.cpu_count() or 2) - 1))   # one core is the law's
    rows: list[dict] = []
    if jobs <= 1 or n <= 1:
        for sp in _spans(cart, pads, window):
            rows += _window(sp)
    else:
        with multiprocessing.get_context("fork").Pool(jobs) as pool:
            for i, part in enumerate(pool.imap(_window, _spans(cart, pads, window))):
                rows += part
                if say:
                    say(i + 1, n)
    return rows


def report(rows: list[dict], top: int = 8) -> str:
    """Where the session stood against the frame: the peak, the middle,
    the frames over the ceiling, and the heaviest frames by stage."""
    frame, ceil = budget.FRAME_CLOCKS, int(budget.FRAME_CLOCKS * budget.CEILING)
    clks = sorted(r["clk"] for r in rows)
    over = [r for r in rows if r["clk"] > ceil]
    lost = [r for r in rows if r["clk"] > frame]
    out = [f"{len(rows):,} frames ({len(rows) / 60:.1f} s) on the silicon meter; "
           f"the frame is {frame:,} clocks, the ceiling {ceil:,}",
           f"  peak {clks[-1]:,} ({100 * clks[-1] / frame:.0f}%)   "
           f"median {clks[len(clks) // 2]:,} ({100 * clks[len(clks) // 2] / frame:.0f}%)   "
           f"99th {clks[int(len(clks) * 0.99) - 1 if len(clks) > 1 else 0]:,}",
           f"  over the ceiling: {len(over):,}   over the frame (a dropped frame): {len(lost):,}",
           "  share of the frame, by frames:"]
    for lo in range(0, 100, 10):
        n = sum(1 for c in clks if lo <= 100 * c / frame < lo + 10)
        if n:
            out.append(f"    {lo:3d}-{lo + 10:<3d}%  {n:6,}  {'#' * max(1, 50 * n // len(rows))}")
    n = sum(1 for c in clks if c >= frame)
    if n:
        out.append(f"    100%+     {n:6,}  {'#' * max(1, 50 * n // len(rows))}")
    out.append(f"  the {min(top, len(rows))} heaviest frames:")
    for r in sorted(rows, key=lambda r: -r["clk"])[:top]:
        out.append(f"    frame {r['frame']:6,}  {r['clk']:9,}  " +
                   "  ".join(f"{k} {r[k]:,}" for k in STAGES if k in r))
    return "\n".join(out)
