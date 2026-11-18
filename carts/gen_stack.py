#!/usr/bin/env python3
"""gen_stack.py -- writes carts/stack.zol: the stack diet's proof.

The diet (boot 70) put the top two stack cells in registers and every
word beneath them in an M10K, so the ONE thing the existing carts never
did is now the thing that matters: live at depth. A cart that never
pushes past three cells would exercise none of the body, none of the
spill, and none of storei's two-pop path -- and would pass while the
machine was wrong.

So this cart runs a long, deterministic, depth-tracked scramble: every
op the law defines, exercised at depths from 1 to 60, with pushes that
spill into the body and pops that pull back out of it, storei and loadi
threaded throughout (storei is the only op that pops TWICE, and the only
one that needed a state of its own). The emitter tracks the depth as it
writes, so nothing here ever traps -- a trapped cart would agree on both
machines while proving nothing.

The result is folded into four accumulators, and those drive both the
COORDINATES and the colors of four triangles: any divergence in any op
at any depth moves geometry, and the cross sees it.
"""
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import spec                                    # noqa: E402

SCRATCH = 200                  # 200..263: storei/loadi's playground
ACC = 300                      # four accumulators
DL = spec.DL_BASE
N_OPS = 1400                   # well inside FUEL (16384)
DEEP = 60                      # how deep the scramble is allowed to go

BIN = ["add", "sub", "mul", "mulq", "and", "or", "xor", "lt", "eq"]


def emit(rng):
    """A depth-tracked scramble. Returns (lines, ops_used)."""
    out, d, used = [], 0, set()

    def push(tok):
        out.append(tok)

    push("load 0")             # the frame counter: the picture must move
    d += 1
    used.add("load")

    # WAVES: climb to the brim, drain to the floor, again -- so every
    # depth from 1 to 60 is crossed many times in both directions. A
    # random walk drifts and never leaves the shallows (it topped out at
    # 14), which would leave the body's deep addresses and the index
    # wrap at sp-2/sp-3 completely untested.
    grow = ["push", "push", "dup", "over", "load", "loadi"]
    shrink = BIN + BIN + ["drop", "store", "storei"]
    neutral = ["swap", "shl", "shr"]
    up = True
    while len(out) < N_OPS:
        if up and d >= DEEP:
            up = False
        elif not up and d <= 1:
            up = True
        if d >= 62:                          # never touch STACK_MAX: a trap
            choice = rng.choice(shrink)      # would agree on both machines
        else:                                # while proving nothing
            choice = rng.choice((grow if up else shrink) + neutral)

        if choice == "push":
            push(f"push {rng.randint(-40000, 40000)}")
            d += 1
        elif choice == "dup" and d >= 1:
            push("dup")
            d += 1
        elif choice == "over" and d >= 2:
            push("over")
            d += 1
        elif choice == "swap" and d >= 2:
            push("swap")
        elif choice in ("shl", "shr") and d >= 1:
            push(f"{choice} {rng.randint(0, 31)}")
        elif choice == "load":
            push(f"load {rng.randrange(SCRATCH, SCRATCH + 64)}")
            d += 1
        elif choice == "loadi":
            push(f"push {rng.randrange(SCRATCH, SCRATCH + 64)}")
            push("loadi")
            d += 1
        elif choice == "store" and d >= 1:
            push(f"store {rng.randrange(SCRATCH, SCRATCH + 64)}")
            d -= 1
        elif choice == "storei" and d >= 1:
            # push the address, then storei pops BOTH it and the value:
            # the two-pop path, the diet's riskiest state
            push(f"push {rng.randrange(SCRATCH, SCRATCH + 64)}")
            push("storei")
            d -= 1
        elif choice in BIN and d >= 2:
            push(choice)
            d -= 1
        else:
            continue
        used.add(choice)

    # ---- collapse whatever is left into four accumulators ----------------
    while d < 5:                            # the scramble may end shallow;
        out.append("dup" if d >= 1 else "push 12345")    # four accumulators
        d += 1                                           # need four cells
    for k in range(4):
        while d > 4 - k:
            out.append("add")
            d -= 1
        out.append(f"store {ACC + k}")
        d -= 1
    while d > 0:
        out.append("drop")
        d -= 1
    return out, used


def tri(a, x_off, y_off):
    """Four triangles whose CORNERS come from the accumulators, so a wrong
    result anywhere moves geometry instead of merely tinting it."""
    o = []
    o += [f"load {a}", "push 127", "and", f"push {x_off}", "add",
          "store 190"]                      # x0
    o += [f"load {a}", "shr 7", "push 127", "and", f"push {y_off}", "add",
          "store 191"]                      # y0
    return o


def build():
    rng = random.Random(70)                 # the boot this proves
    body, used = emit(rng)
    lines = [
        "; stack.zol -- GENERATED by gen_stack.py, do not edit",
        "; the stack diet's proof: every op, at depth, through the body",
        "",
        f".data {ACC} 0 0 0 0",
        f".data {SCRATCH} " + " ".join(str((i * 7919) % 30011)
                                       for i in range(64)),
        "",
    ]
    lines += body
    # ---- the display list: coordinates AND colors from the accumulators --
    lines.append(f"push 4")
    lines.append(f"store {DL}")
    for k in range(4):
        a = ACC + k
        base = DL + 1 + k * spec.DL_STRIDE
        xo, yo = 20 + 70 * (k % 2), 20 + 130 * (k // 2)
        lines += tri(a, xo, yo)
        lines += ["load 190", f"store {base}",
                  "load 191", f"store {base + 1}",
                  "load 190", "push 56", "add", f"store {base + 2}",
                  "load 191", f"store {base + 3}",
                  "load 190", f"store {base + 4}",
                  "load 191", "push 56", "add", f"store {base + 5}",
                  f"load {a}", "push 0xFFFFFF", "and", f"store {base + 6}"]
    lines.append("halt")
    return lines, used


if __name__ == "__main__":
    lines, used = build()
    out = HERE / "stack.zol"
    out.write_text("\n".join(lines) + "\n")
    n = sum(1 for ln in lines if ln and not ln.startswith((";", ".")))
    print(f"wrote {out.name}: {n} instructions, ops exercised: "
          f"{len(used)} kinds -> {' '.join(sorted(used))}")
