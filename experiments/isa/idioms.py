#!/usr/bin/env python3
"""idioms.py -- WHAT THE INSTRUCTION SET MAKES A CART SPELL OUT: a probe of the Zeta-n hypothesis.

The machine (zeta/vm.py) has 24 instructions and no divide, no absolute
value, no min or max, no negate, no compare-and-branch, and an immediate of
24 bits. A cart spells each of those out in several instructions. This reads
the program a cart actually runs -- out of a running machine, after its page
is loaded -- finds each spelled-out idiom, and counts it two ways:

  WORDS         how much of the program page it takes (the page is 32,768;
                TEAR NOT DEMON's lab is at 29,011 of it -- the binding limit)
  INSTRUCTIONS  how many times its instructions are executed a frame, over a
                stretch of the player's own session (the frame's ceiling is
                65,536; the lab's worst is about 27,000)

and so what one more generation of the instruction set -- these idioms as
single instructions -- would give back, if the machine's area allowed it.
It is a PREDICTION about A(n+1) made on A(n). The test is to build it.

    python3 experiments/isa/idioms.py CART.zol [TAPE.ztp CARD.bin FRAMES]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import cabinet, deploy, gpu, spec, vm as zvm  # noqa: E402
from zeta import tape as ztape  # noqa: E402

NAME = {code: op for op, (code, _) in spec.OPS.items()}


def decode(word):
    op, imm = word >> 24, word & 0xFFFFFF
    if imm & 0x800000:
        imm -= 0x1000000
    return NAME.get(op, "?"), imm


def the_page(m):
    """the game's own program, as the machine runs it (after the page is in)"""
    prog = [decode(w) for w in m.vm.imem]
    while prog and prog[-1] == ("halt", 0):
        prog.pop()
    return prog


def idioms(prog):
    """[(name, start, length, saved_words)] -- each spelled-out idiom, longest first, none overlapping"""
    found, used = [], set()

    def take(name, i, n, save):
        if any(j in used for j in range(i, i + n)):
            return False
        used.update(range(i, i + n))
        found.append((name, i, n, save))
        return True

    P = len(prog)
    for i in range(P):
        def at(k, op, imm=None):
            return i + k < P and prog[i + k][0] == op and (imm is None or prog[i + k][1] == imm)
        # the wide constant: push b0, (shl 8, push b, or) x3 -- 10 words for one 32-bit number
        if at(0, "push") and all(at(1 + 3 * k, "shl", 8) and at(2 + 3 * k, "push") and at(3 + 3 * k, "or") for k in range(3)):
            take("wide constant", i, 10, 8)            # (a push of a high half: 2 words)
        # abs: dup, push 0, lt, jz T, push 0, swap, sub   T = i + 7
        if at(0, "dup") and at(1, "push", 0) and at(2, "lt") and at(3, "jz", i + 7) and at(4, "push", 0) and at(5, "swap") and at(6, "sub"):
            take("abs", i, 7, 6)
        # min with a constant: dup, push K, swap, lt, jz T, drop, push K   T = i + 7
        if at(0, "dup") and at(1, "push") and at(2, "swap") and at(3, "lt") and at(4, "jz", i + 7) and at(5, "drop") and at(6, "push", prog[i + 1][1] if i + 1 < P else None):
            take("min/max", i, 7, 6)
        # max with a constant: dup, push K, lt, jz T, drop, push K   T = i + 6
        if at(0, "dup") and at(1, "push") and at(2, "lt") and at(3, "jz", i + 6) and at(4, "drop") and at(5, "push", prog[i + 1][1] if i + 1 < P else None):
            take("min/max", i, 6, 5)
    for i in range(P):
        def at(k, op, imm=None):
            return i + k < P and prog[i + k][0] == op and (imm is None or prog[i + k][1] == imm)
        if at(0, "push", 0) and at(1, "swap") and at(2, "sub"):
            take("negate", i, 3, 2)
        if at(0, "lt") and at(1, "jz"):
            take("compare and branch", i, 2, 1)
        elif at(0, "eq") and at(1, "jz"):
            take("compare and branch", i, 2, 1)
    return found


def profile(cart, pads, first=0):
    """how many times each address runs, over these frames of the session (the law, unpainted)"""
    blank = __import__("numpy").zeros((spec.H, spec.W, 3), "uint8")
    keep, gpu.render = gpu.render, (lambda *a, **k: blank)
    counts = Counter()
    real_frame = zvm.VM.frame

    def counted(self, pad, pad2=0):                  # (a copy of the law's loop that also counts each address)
        if self.trapped:
            return
        d = self.dmem
        d[spec.REG_FRAME] = self.frame_no & spec.WORD_MASK
        d[spec.REG_PAD] = pad & 0xFFFF
        d[spec.REG_PAD2] = pad2 & 0xFFFF
        self.frame_no += 1
        pc, fuel, st, rs = 0, spec.FUEL, [], []
        push, pop = st.append, st.pop
        s32 = spec.s32
        M = spec.WORD_MASK
        im = self.imem
        while fuel > 0:
            fuel -= 1
            counts[pc] += 1
            w = im[pc]
            op, imm = w >> 24, w & 0xFFFFFF
            if imm & 0x800000:
                imm -= 0x1000000
            pc += 1
            if op == 0x00: break
            elif op == 0x01: push(imm & M)
            elif op == 0x02: push(d[imm])
            elif op == 0x03: d[imm] = pop()
            elif op == 0x04: push(d[pop()])
            elif op == 0x05: a = pop(); d[a] = pop()
            elif op == 0x10: b, a = pop(), pop(); push((a + b) & M)
            elif op == 0x11: b, a = pop(), pop(); push((a - b) & M)
            elif op == 0x12: b, a = pop(), pop(); push((s32(a) * s32(b)) & M)
            elif op == 0x13: b, a = pop(), pop(); push(((s32(a) * s32(b)) >> 16) & M)
            elif op == 0x14: b, a = pop(), pop(); push(a & b)
            elif op == 0x15: b, a = pop(), pop(); push(a | b)
            elif op == 0x16: b, a = pop(), pop(); push(a ^ b)
            elif op == 0x17: push((pop() << imm) & M)
            elif op == 0x18: push((s32(pop()) >> imm) & M)
            elif op == 0x19: b, a = pop(), pop(); push(1 if s32(a) < s32(b) else 0)
            elif op == 0x1A: b, a = pop(), pop(); push(1 if a == b else 0)
            elif op == 0x20: push(st[-1])
            elif op == 0x21: pop()
            elif op == 0x22: st[-1], st[-2] = st[-2], st[-1]
            elif op == 0x23: push(st[-2])
            elif op == 0x30: pc = imm
            elif op == 0x31:
                if pop() == 0: pc = imm
            elif op == 0x32: rs.append(pc); pc = imm
            elif op == 0x33: pc = rs.pop()
        self.fuel_left = fuel
    zvm.VM.frame = counted
    try:
        m = cabinet.VirtualMachine(cart)
        for k, p in enumerate(pads):
            if k == first:
                counts.clear()
            m.frame(p)
    finally:
        zvm.VM.frame = real_frame
        gpu.render = keep
    return m, counts, len(pads) - first


def main():
    zol = Path(sys.argv[1])
    cart = cabinet.load_cart(zol)
    if len(sys.argv) > 2:
        header, pads = ztape.decode(Path(sys.argv[2]).read_bytes())
        cart["sd"] = deploy.card_images(Path(sys.argv[3]))
        n = int(sys.argv[4])
        pads = pads[:n]
    else:
        pads = [spec.PAD_START] + [0] * 60
    m, counts, frames = profile(cart, pads, first=min(60, len(pads) // 2))
    prog = the_page(m)
    found = idioms(prog)
    calls = Counter(imm for op, imm in prog if op == "call")
    words, runs = Counter(), Counter()
    for name, i, n, save in found:
        words[name] += save
        runs[name] += sum(counts[i + k] for k in range(n)) - counts[i]            # (the instructions it would not run)
    total_run = sum(counts.values())
    rows = {name: {"places": sum(1 for f in found if f[0] == name), "words_back": words[name],
                   "instructions_back_a_frame": round(runs[name] / frames)} for name in words}
    # divide: the cart's own (QDIV) -- a call and its ~18-step loop, against one instruction
    qdiv = [a for a, c in calls.items() if c >= 5]
    out = {"cart": zol.name, "program_words": len(prog), "page": 32768, "frames_profiled": frames,
           "instructions_a_frame": round(total_run / frames), "idioms": rows,
           "words_back_total": sum(words.values()),
           "instructions_back_a_frame_total": round(sum(runs.values()) / frames),
           "most_called": sorted(((c, a) for a, c in calls.items()), reverse=True)[:6]}
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
