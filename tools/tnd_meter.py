# THE TND FRAME METER: where a frame's clocks go, on the silicon's own
# counters, over a fixed route -- and, law-side, which objects walked the
# pixels. Both found today's budget wins (docs/TND-PORT.md, "the frame,
# measured"); neither is a gate. The budget gate (zeta budget) measures
# ten idle frames; a free-camera game needs ROUTES.
#
#   python3 tools/tnd_meter.py silicon games/tnd/tnd.zol brawl
#       per frame: CLK and the meter's stages (zeta_top.v, roadmap 15):
#       clr / walk / idle (rasteriser STARVED: the sequencer is the
#       bottleneck) / stall / seq / blkd (sequencer BLOCKED: the
#       rasteriser is). Prints peak, median, frames over the ceiling.
#   python3 tools/tnd_meter.py walk games/tnd/tnd.zol tour 890
#       the rasteriser's WALK -- every pixel of every triangle's bounding
#       box, one clock each for a flat face -- attributed to objects, by
#       re-rendering that frame through the law's own _fill. Within 3% of
#       the silicon's walk counter where checked (486k against 500k).
#
# Routes (pads by frame):
#   street  the P2 route: turn, walk an arm, sweep, jab
#   brawl   stand while the wave closes in, turn a full circle among
#           them, jab
#   tour    down an arm, back across the crossing, into a corner, spin
#   intro   no input from power-on: the attract intro's flight (P8)

import collections
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import budget, cabinet, gpu, silicon, spec  # noqa: E402

ROUTES = {"street": 241, "brawl": 521, "tour": 901,     # (+ the title's frame)
          "intro": 420}                                 # power-on, no input: P8


def pad(route, f):
    """frame 0 presses Start (TND opens on its title); the route's frame f
    is the machine's f + 1"""
    if route == "intro":
        return 0                    # the title pages in the intro and it plays
    if f == 0:
        return spec.PAD_START
    f -= 1
    if route == "brawl":
        if f < 340:
            return 0
        if f < 426:
            return spec.PAD_LEFT
        return spec.PAD_X if f % 20 == 0 else 0
    if route == "tour":
        for end, p in ((500, spec.PAD_UP), (543, spec.PAD_LEFT),
                       (700, spec.PAD_UP), (720, spec.PAD_RIGHT),
                       (820, spec.PAD_UP)):
            if f < end:
                return p
        return spec.PAD_LEFT
    if f < 20:
        return 0
    if f < 52:
        return spec.PAD_LEFT
    if f < 150:
        return spec.PAD_UP
    if f < 200:
        return spec.PAD_RIGHT | spec.PAD_UP
    return spec.PAD_X if f % 20 == 0 else 0


def on_silicon(path, route):
    sim = silicon.build()
    work = Path(tempfile.mkdtemp(prefix="tnd-meter-"))
    hexes = [p for p in silicon.write_cart_hex(cabinet.load_cart(path), work) if p]
    proc = subprocess.Popen([str(sim), *map(str, hexes)], stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            env=dict(os.environ, ZETA_CLK="1"))
    for f in range(ROUTES[route]):
        proc.stdin.write(struct.pack("<I", pad(route, f)))
    proc.stdin.close()
    rows = [ln for ln in proc.stderr.read().decode().splitlines()
            if ln.startswith("CLK ")]
    proc.wait()
    return [dict(clk=int(ln.split()[1]),
                 **{k: int(v) for k, v in (kv.split("=") for kv in ln.split()[2:])})
            for ln in rows]


def walk_by_object(path, route, frame):
    spans = [(int(m.group(3)), int(m.group(3)) + int(m.group(2)), m.group(1))
             for m in re.finditer(r"^; (\S+): (\d+) words at (\d+)",
                                  Path(path).read_text(), re.M)]

    def owner(mb):                  # the resource a mesh lives inside
        return next((n for a, b, n in spans if a <= mb < b), f"mesh@{mb}")
    acc = collections.Counter()
    orig = gpu._fill

    def fill(fb, zbuf, x0, y0, x1, y1, x2, y2, *a, **k):
        lx = max(min(x0, x1, x2) >> spec.SUB, 0)
        hx = min(max(x0, x1, x2) >> spec.SUB, spec.W - 1)
        ly = max(min(y0, y1, y2) >> spec.SUB, 0)
        hy = min(max(y0, y1, y2) >> spec.SUB, spec.H - 1)
        if lx <= hx and ly <= hy:
            acc[(k.get("oid", 0) & 0x7F) - 1] += (hx - lx + 1) * (hy - ly + 1)
        return orig(fb, zbuf, x0, y0, x1, y1, x2, y2, *a, **k)
    m = cabinet.VirtualMachine(cabinet.load_cart(path))
    for f in range(frame + 1):
        gpu._fill = fill if f == frame else orig
        m.frame(pad(route, f))
    gpu._fill = orig
    d, out = m.vm.dmem, collections.Counter()
    for k, v in acc.items():
        mb = d[spec.OL_BASE + 1 + k * spec.OL_STRIDE] if k >= 0 else None
        name = "display list" if k < 0 else owner(mb)
        out[re.sub(r"^(demon\d)_.*|^(street)\d+_\d+", r"\1\2", name)] += v
    return out


if __name__ == "__main__":
    mode, path, route = sys.argv[1:4]
    if mode == "silicon":
        rows = on_silicon(path, route)
        clk = sorted(r["clk"] for r in rows)
        ceil = budget.FRAME_CLOCKS * budget.CEILING
        peak = max(range(len(rows)), key=lambda i: rows[i]["clk"])
        print(f"{Path(path).stem} on {route}: peak {clk[-1]:,} (frame {peak}) "
              f"median {clk[len(clk) // 2]:,}; over the ceiling: "
              f"{sum(c > ceil for c in clk)} of {len(clk)}")
        print("  at the peak:", {k: v for k, v in rows[peak].items()
                                 if k in ("clr", "walk", "idle", "stall", "seq", "blkd")})
        if len(sys.argv) > 4:
            json.dump(rows, open(sys.argv[4], "w"))
    else:
        w = walk_by_object(path, route, int(sys.argv[4]))
        print(f"walk {sum(w.values()):,} at {route} frame {sys.argv[4]}")
        for k, v in w.most_common():
            print(f"  {k:16s} {v:>8,}")
