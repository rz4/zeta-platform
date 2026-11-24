#!/usr/bin/env python3
"""bot.py -- THE MACHINE PLAYS ITS OWN COURSE (TND's park, layer 12; docs/TND-PORT.md P58).

The park's course is a function: a station a movement mode, its gaps the mode's
measured reach times a tightness. Whether a station can be cleared is a claim,
and this is its test: a player made of rules -- in the run, east down the
corridor -- reads what it stands on and what comes next from the machine's own
data memory, and presses what the mode asks for:

  a tap at a box's edge (TAP, STEPS, the PADS' straight line), from the floor
  onto an ENTRY; A held through the run-up and let go at the edge (LONG); a tap
  and a second press in the air (FLIP, DROP); a tap at the face and the flip at
  the top (FLIP UP); stood still on the entry until the slider or the lift
  comes, ridden, and walked off at the far end (SLIDE, LIFT).

It steers only where a station asks it to: toward the next pad's middle on
the PADS (in the air), and a little right off a WALL's entry -- there the tap,
then a kick at each wall touched, until he is over the chimney's cap.
It reports, a station at a time, cleared or not, and the streak the game
itself kept.

    python3 experiments/park/bot.py [CART.zol] [STATIONS] [--tape OUT.ztp]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import cabinet, gpu, spec  # noqa: E402

ONE = 65536
A, L, U = spec.PAD_A, spec.PAD_L, spec.PAD_UP
NAMES = ("TAP", "STEPS", "LONG", "FLIP", "FLIP UP", "PADS", "SLIDE", "LIFT", "DROP", "WALL")
INVALID = 0x7FFFFFFF
RW, K = 16, 24
R_Z0, R_Z1, R_INFO, R_DZ, R_TOP, R_AMP = 2, 3, 6, 13, 14, 5


def s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


class Park:
    def __init__(self, cart_path):
        self.text = Path(cart_path).read_text().splitlines()
        self.syms = {}
        for ln in self.text:
            if ln.startswith("; ") and " at " in ln and ":" in ln:
                name = ln[2:].split(":", 1)[0]
                try:
                    self.syms[name] = int(ln.rsplit(" at ", 1)[1])
                except ValueError:
                    pass
        self.m = cabinet.VirtualMachine(cabinet.load_cart(Path(cart_path)))
        self.d = self.m.vm.dmem
        self.pads = []
        self.step(spec.PAD_START)
        for _ in range(30):
            self.step(0)

    def step(self, pad):
        self.pads.append(pad)
        self.m.frame(pad)

    def cell(self, n, k=0):
        return s32(self.d[self.syms[n] + k])

    def rows(self):
        base = self.syms["park_rows"]
        out = []
        for r in range(K):
            w = [s32(self.d[base + r * RW + k]) for k in range(RW)]
            if w[R_Z0] == INVALID:
                continue
            info = w[R_INFO]
            out.append(dict(r=r, z0=(w[R_Z0] + w[R_DZ]) / ONE, z1=(w[R_Z1] + w[R_DZ]) / ONE, top=w[R_TOP] / ONE,
                            x0=w[0] / ONE, x1=w[1] / ONE,
                            motion=info & 3, role=(info >> 2) & 3, kind=(info >> 4) & 15, st=info >> 8,
                            dz=w[R_DZ] / ONE, amp=w[R_AMP] / ONE, lo=w[4] / ONE))
        return sorted(out, key=lambda b: (b["z0"], b["r"]))

    def u(self):
        return self.cell("pz") / ONE

    def py(self):
        return self.cell("f_py") / ONE


def play(cart_path, stations=12, say=print):
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    keep, gpu.render = gpu.render, (lambda *a, **k: blank)
    try:
        g = Park(cart_path)
        g.step(L)
        g.step(L)
        for _ in range(3):
            g.step(0)
        for _ in range(3):
            g.step(L)
        log, queue, frames, climbing, last_kick, was_air = [], [], 0, None, 0, False
        cleared_before = 0
        while frames < 60 * 60 * 4:
            frames += 1
            u, py, psi = g.u(), g.py(), g.cell("lab_si")
            rows = g.rows()
            on = next((b for b in rows if b["r"] == psi), None) if psi >= 0 and py == 0 else None
            ref = on["z1"] if on else u
            ahead = [b for b in rows if (on is None or b["r"] != on["r"]) and b["z1"] > ref + 0.05 and b["z0"] - ref < 40]
            nxt = ahead[0] if ahead else None
            pad = L | U
            steer = 0
            if py > 0 and nxt is not None and nxt["kind"] == 5 and not nxt["role"] & 1:   # (PADS: in the air, toward the pad's middle)
                tv_ = -64.0 - (nxt["x0"] + nxt["x1"]) / 2
                vv_ = -64.0 - g.cell("px") / ONE
                steer = spec.PAD_LEFT if tv_ > vv_ + 0.35 else spec.PAD_RIGHT if tv_ < vv_ - 0.35 else 0
            pad |= steer
            if climbing is not None and py > 0 and not queue and g.cell("wall_t") and len(g.pads) - last_kick > 5 \
                    and py + g.cell("lab_gh") / ONE < climbing + 0.3:   # (WALL: kick from wall to wall until over the cap)
                queue, last_kick = [0, 0, A, A], len(g.pads)
            if py == 0 and was_air:                           # (landed: the climb is over)
                climbing = None
            was_air = py > 0
            if queue:                                         # (a press under way: its frames, as scheduled)
                pad = (pad & ~A) | queue.pop(0)
            elif py == 0 and nxt is not None:
                kind = nxt["kind"]
                edge = (on["z1"] - u) if on else None
                tap = [A, A, A, 0, 0]
                vv = (-64.0 - g.cell("px") / ONE)
                if on and kind == 9 and on["role"] & 1:       # WALL: veer a little right; the tap; then the climb
                    yaw = g.cell("yaw") & 1023
                    yaw = yaw - 1024 if yaw > 512 else yaw
                    pad = L | U | (spec.PAD_RIGHT if yaw > -16 else 0)
                    if edge < 0.8:
                        queue = [A, A, A, 0, 0]
                        climbing = max(b["top"] for b in rows if b["st"] == nxt["st"] and b["role"] & 2)
                elif on and on["motion"] == 1:                # riding the slider: still, until it is at its far end
                    pad = L if on["dz"] < on["amp"] - 0.15 else L | U
                elif on and on["motion"] == 2:                # riding the lift: still, until it is at the top
                    pad = L if on["top"] < 3.95 else L | U
                elif on and nxt["motion"] == 1 and nxt["z0"] - on["z1"] > 0.05 and edge < 1.6:
                    pad = L                                   # (the slider is away: wait for it at the edge)
                elif on and nxt["motion"] == 2 and nxt["top"] > on["top"] + 0.25 and edge < 1.6:
                    pad = L                                   # (the lift is up: wait for it at the edge)
                elif on and nxt["motion"] in (1, 2):
                    pass                                      # (it is here: walk on)
                elif on and kind == 2 and on["role"] & 1 and nxt["z0"] - on["z1"] > 3.0:   # LONG: held, let go at the edge
                    if 0.3 < edge < 3.0:
                        pad |= A
                elif on and kind == 4 and nxt["top"] > on["top"] + 1.0:   # FLIP UP: the tap at the face, the flip on top
                    if edge < 0.8:
                        queue = tap[:3] + [0] * 8 + [A, A, A]
                elif on and nxt["z0"] - on["z1"] > 0.3 and edge < 0.8:    # a gap: the tap (it jumps on the release, three frames on)
                    queue = tap[:3] + ([0] * 9 + [A, A, A] if kind in (3, 8) and nxt["z0"] - on["z1"] > 4.0 else [0, 0])
                elif nxt["top"] > (on["top"] if on else 0) + 0.25 and nxt["z0"] - u < (1.6 if not on else 1.0):
                    queue = list(tap)                         # a step up (or the entry, from the floor)
                if queue:
                    pad = (pad & ~A) | queue.pop(0)
            g.step(pad)
            streak = g.cell("course_shown")
            if g.cell("park_done") > cleared_before - 1 and g.cell("park_done") >= 0 and g.cell("park_done") != (log[-1]["station"] if log else -1):
                st = g.cell("park_done")
                kind = next((b["kind"] for b in g.rows() if b["st"] == st), -1)
                log.append(dict(station=st, mode=NAMES[kind] if kind >= 0 else "?", frame=len(g.pads), streak=streak))
                say(f"  station {st:3d} {log[-1]['mode']:8s} cleared at frame {len(g.pads):6d}, streak {streak}")
            if g.cell("park_gen_n") > stations + 3 and log and log[-1]["station"] >= stations - 1:
                break
            if u > 16000 - 50:
                break
        return g, log
    finally:
        gpu.render = keep


def main():
    cart = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".zol") else str(ROOT / "build" / "layer12" / "tnd.zol")
    n = next((int(a) for a in sys.argv[1:] if a.isdigit()), 12)
    g, log = play(cart, n)
    print(json.dumps({"stations_cleared": len(log), "frames": len(g.pads), "best": g.cell("course_best"),
                      "reached_u": round(g.u(), 1)}, indent=1))


if __name__ == "__main__":
    main()
