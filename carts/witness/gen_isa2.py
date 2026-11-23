#!/usr/bin/env python3
"""gen_isa2.py -- writes carts/witness/isa2.zol: THE SECOND INSTRUCTION SET, EVERY EDGE.

ISA generation 2 (experiments/isa/: the idioms TEAR NOT DEMON's lab spelled
out, made instructions): pushh and ori (a 32-bit constant in two words), abs,
neg, mini, maxi (with a constant), jnlt and jne (a compare and its branch).

Each instruction is run on the values where it could go wrong -- the most
negative word, zero, the immediate's own extremes, both ways of every branch
-- and its answer is checked against the answer the FIRST instruction set
computes the long way (the law's own arithmetic, at build time). A failed
check sets its bit. The glass is one rectangle: GREEN when every check
passes; else red, its green and blue the failed checks' bits. So the cross
sees any instruction the silicon does differently, and a machine without
the second set traps at its first new instruction and draws nothing. (The
rectangle is two triangles of the display list: the frame itself, which is
what the cross compares -- the compositor's rectangles come after it.)

Run me after changing anything: python3 carts/witness/gen_isa2.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import spec                                    # noqa: E402
from zeta.forge import Cart                              # noqa: E402

M = 0xFFFFFFFF
IMIN, IMAX = -(1 << 23), (1 << 23) - 1


def s32(v):
    v &= M
    return v - (1 << 32) if v & (1 << 31) else v


def main():
    cart = Cart("isa2")
    fail, k = cart.var("fail"), cart.var("k")
    p = cart.program()
    p.set(fail, 0)
    checks = []

    def check(ops, want):
        """run ops (leaving one word), compare with want, the old way"""
        n = len(checks)
        checks.append(want)
        ok = p.label("ok")
        p.emit(*ops)
        p.push32(want & M).emit("eq", f"jz {ok}_bad", f"jmp {ok}")
        p.mark(f"{ok}_bad")
        p.load(fail).push32(1 << (n % 31)).emit("or").store(fail)
        p.mark(ok)

    # pushh / ori: constants the first set needs ten words for
    for v in (0x89ABCDEF, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0x00000100, 0x12345600):
        check((f"pushh {(v >> 8) & 0xFFFFFF}", f"ori {v & 0xFF}"), v)
    check(("push -1", "ori 0"), M)                                 # (ori keeps what is there)
    # abs / neg
    for v in (-5, 7, 0, -(1 << 31), (1 << 31) - 1, -1):
        check((*push(v), "abs"), abs(v) if v != -(1 << 31) else v)
        check((*push(v), "neg"), -v if v != -(1 << 31) else v)
    # mini / maxi, at the immediate's own ends
    for v, c in ((-3, 2), (10, 2), (2, 2), (-(1 << 31), IMIN), ((1 << 31) - 1, IMAX), (5, IMIN), (-5, IMAX)):
        check((*push(v), f"mini {c}"), min(v, c))
        check((*push(v), f"maxi {c}"), max(v, c))
    # jnlt / jne: both ways each, signed; the result word is which way it went
    for a, b in ((1, 2), (2, 2), (3, 2), (-1, 1), (1, -1), (-(1 << 31), (1 << 31) - 1)):
        for op, taken in (("jnlt", not (a < b)), ("jne", a != b)):
            j = p.label("j")
            check((*push(a), *push(b), f"{op} {j}_t", "push 0", f"jmp {j}_e", f"{j}_t:", "push 1", f"{j}_e:"), int(taken))
    assert len(checks) <= 64
    # the glass: one rectangle -- green, or red with the failures in green and blue
    col = cart.var("col")
    p.load(fail).emit(f"jz {k}_ok")
    p.push32(0xFF0000).load(fail).push(0xFFFF).emit("and", "or").store(col).emit(f"jmp {k}_d")
    p.mark(f"{k}_ok")
    p.push32(0x00C040).store(col)
    p.mark(f"{k}_d")
    W1, H1 = spec.W - 1, spec.H - 1
    p.set(spec.DL_BASE, 2)
    for t, tri in enumerate(((0, 0, W1, 0, W1, H1), (0, 0, W1, H1, 0, H1))):
        b = spec.DL_BASE + 1 + t * spec.DL_STRIDE
        for i, v in enumerate(tri):
            p.set(b + i, v)
        p.load(col).store(b + 6)
    p.emit("halt")
    cart.write(HERE / "isa2.zol")
    print(cart.report(), f"| {len(checks)} checks")


def push(v):
    """the first set's way to push a word (the forge's push32), as ops"""
    v &= M
    sv = s32(v)
    if -(1 << 23) <= sv < (1 << 23):
        return (f"push {sv}",)
    parts = [(v >> 24) & 0xFF, (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF]
    out = [f"push {parts[0]}"]
    for b in parts[1:]:
        out += ["shl 8", f"push {b}", "or"]
    return tuple(out)


if __name__ == "__main__":
    main()
