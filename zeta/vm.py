"""vm.py -- the Zeta virtual machine, executable spec of the silicon CPU.

One frame = run from PC 0 until HALT, or until FUEL is spent (a lawful stop:
the frame simply ends with the state as-is). DMEM persists across frames.
Anything a cart could observe -- wraparound, shift semantics, comparison
signedness -- is defined here in terms of spec.s32 and nothing else, so the
Verilog has exactly one behavior to match.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import spec
from .spec import s32


class Trap(Exception):
    """A cart bug the machine refuses to run past (bad opcode, stack abuse,
    out-of-range access). Silicon behavior is identical: trap = frozen core,
    obs_trapped high."""


class VM:
    """The machine's state: IMEM, DMEM, and the cart's CRAM segment. The
    mover (spec.DMA_*) is the only path between the last two, and it runs
    exactly once per frame at a legislated instant -- see dma()."""
    def __init__(self, cart: dict | str | Path):
        if not isinstance(cart, dict):
            cart = json.loads(Path(cart).read_text())
        self.imem = list(cart["imem"]) + [0] * (spec.IMEM_WORDS - len(cart["imem"]))
        self.dmem = [0] * spec.DMEM_WORDS
        for a, v in cart.get("dmem", {}).items():
            self.dmem[int(a)] = v & spec.WORD_MASK
        # the CRAM segment: sparse here, a real 8 MB of chip on the machine
        self.cram = dict(
            (int(a), v & spec.WORD_MASK) for a, v in cart.get("cram", {}).items())
        # the card: slot id -> the words of that slot's file. Sparse
        # here, a real file on the SD there; either way the law can
        # answer a read exactly, which is what keeps SD inside the cross.
        self.sd = dict(
            (int(k), [w & spec.WORD_MASK for w in v])
            for k, v in cart.get("sd", {}).items())
        self.sd_wait = 0                 # frames left on the request in
        self.sd_req = None               # flight, and what it asked for
        self.sd_snap = []                # a save's words, taken at latch
        self.sd_copied = 0               # words the console copied out
        self.sd_staged = 0               # words zcard has staged, and
        self.sd_counted = False          # whether THIS request is counted
        self.sd_lat = 0                  # the measured latency the silicon
                                         # reports: the law's card is ready
                                         # the instant it is asked, so this
                                         # is 1 from the first request on
        self.frame_no = 0
        self.trapped = False

    # ---- THE MOVERS' INSTANT reads every request as the PROGRAM left it --
    # Latched together before any mover runs, exactly as the silicon's
    # parameter sweep always has. Requests are READ from the latch; status
    # writes (each GO clearing) still land in DMEM after the movers, as
    # the silicon's I_DCLR/I_OCLR/I_CGO states do. A DMA that writes
    # another mover's request cells therefore changes DMEM for the next
    # frame but not the request being served this one. The law said the
    # opposite until a probe cart (tests/test_movers.py) DMA'd a new
    # OVL_SRC beside an overlay request and the two machines loaded
    # different programs: the law, the DMA's; the silicon, the cart's.
    # The silicon's reading is the one legislated -- a mover acts on what
    # was ASKED -- and it costs no logic.
    REQUEST_CELLS = (spec.DMA_SRC, spec.DMA_DST, spec.DMA_LEN, spec.DMA_GO,
                     spec.OVL_SRC, spec.OVL_DST, spec.OVL_LEN, spec.OVL_GO,
                     spec.SD_SLOT, spec.SD_OFF, spec.SD_DST, spec.SD_LEN,
                     spec.SD_GO, spec.SEG_BASE)

    def latch_requests(self) -> None:
        self._req = {a: self.dmem[a] for a in self.REQUEST_CELLS}

    def release_requests(self) -> None:
        self._req = None

    def _r(self):
        """Where requests are read: the latch inside the instant, DMEM
        for a caller that drives one mover by hand."""
        return getattr(self, "_req", None) or self.dmem

    def dma(self) -> None:
        """One legislated move, after the VM halts and before the GPU
        reads DMEM. A request that does not fit moves nothing -- and
        still clears DMA_GO, so a bad pointer cannot wedge the frame."""
        d, r = self.dmem, self._r()
        if not r[spec.DMA_GO]:
            return
        src, dst = s32(r[spec.DMA_SRC]), s32(r[spec.DMA_DST])
        n = s32(r[spec.DMA_LEN])
        d[spec.DMA_GO] = 0
        if not 0 < n <= spec.DMA_MAX:
            return
        eff = src + s32(r[spec.SEG_BASE])   # the segment window (SEG_BASE)
        if src < 0 or eff < 0 or eff + n > spec.CRAM_WORDS:
            return
        if dst < 0 or dst + n > spec.DMEM_WORDS:
            return
        for i in range(n):
            d[dst + i] = self.cram.get(eff + i, 0)

    def card_diag(self) -> None:
        """The counters. Words 0..2 count APF traffic, which machine 1 has
        none of -- those are zeros here and real only on glass. Word 3 is
        different: the MEASURED latency is kept by zeta_top, which the
        simulation runs too, so the law must model it or the cross fails
        the moment a cart asks for anything (it did, at frame 62). The
        law's card answers instantly, so the measurement is one frame."""
        # ...on the frame AFTER the latch, which is when zeta_top first
        # looks at the card again (sd_wait has been decremented by then)
        if (self.sd_req is not None and not self.sd_counted
                and self.sd_wait < spec.SD_LATENCY):
            self.sd_counted = True
            if not self.sd_req[4]:       # a save sends words OUT: zcard
                self.sd_staged = (       # stages nothing and the console
                    self.sd_staged + self.sd_req[3]) & 0xFFFF   # copies

            if self.sd_lat == 0:
                self.sd_lat = 1
        self.dmem[spec.CARD_DIAG + 0] = 0
        self.dmem[spec.CARD_DIAG + 1] = 0
        # word 2 is entirely card_apf's now (captured words, and what the
        # save fill wrote) -- APF traffic machine 1 does not have, so it
        # is zeros here and real only on glass
        self.dmem[spec.CARD_DIAG + 2] = 0
        # the console's own copy count rides in the same word
        self.dmem[spec.CARD_DIAG + 3] = (self.sd_copied << 8) | self.sd_lat

    def overlay(self) -> None:
        """One legislated code move, at the mover's instant. The VM has
        halted and the next frame starts at PC 0, so a cart can page in
        the program it is about to become without standing on it."""
        d, r = self.dmem, self._r()
        if not r[spec.OVL_GO]:
            return
        src, dst = s32(r[spec.OVL_SRC]), s32(r[spec.OVL_DST])
        n = s32(r[spec.OVL_LEN])
        d[spec.OVL_GO] = 0
        if not 0 < n <= spec.OVL_MAX:
            return
        eff = src + s32(r[spec.SEG_BASE])   # the segment window (SEG_BASE)
        if src < 0 or eff < 0 or eff + n > spec.CRAM_WORDS:
            return
        if dst < 0 or dst + n > spec.IMEM_WORDS:
            return
        for i in range(n):
            self.imem[dst + i] = self.cram.get(eff + i, 0)

    def card(self) -> None:
        """The legislated card step, at the mover's own instant. A request
        latched at the end of frame N lands at the end of frame
        N + SD_LATENCY -- always, whatever the card actually did."""
        d, r = self.dmem, self._r()
        if self.sd_req is not None:      # something already in flight:
            self.sd_wait -= 1            # land it when its time comes
            if self.sd_wait <= 0:
                slot, off, dst, n, save = self.sd_req
                if save:                 # ...or write it back: the slot
                    img = self.sd.setdefault(slot, [])   # image grows to
                    need = off + n                       # fit the write,
                    if len(img) < need:                  # zero filled
                        img.extend([0] * (need - len(img)))
                    for i, v in enumerate(self.sd_snap):
                        img[off + i] = v
                else:
                    img = self.sd.get(slot, [])
                    for i in range(n):
                        a = off + i
                        d[dst + i] = img[a] if 0 <= a < len(img) else 0
                if not save:             # ...nothing back into DMEM
                    self.sd_copied = (self.sd_copied + n) & 0xFF
                self.sd_req = None
                d[spec.SD_GO] = 0        # the cart's whole protocol: poll
            elif r[spec.SD_GO] == 0:     # a cart that cleared GO itself
                d[spec.SD_GO] = (spec.SD_SAVE if self.sd_req[4]
                                 else spec.SD_READ)   # cannot cancel
            return
        if not r[spec.SD_GO]:
            return
        go = s32(r[spec.SD_GO])
        slot = s32(r[spec.SD_SLOT])
        off, dst = s32(r[spec.SD_OFF]), s32(r[spec.SD_DST])
        n = s32(r[spec.SD_LEN])
        if go not in (spec.SD_READ, spec.SD_SAVE) or \
           not 0 < n <= spec.SD_MAX or slot < 0 or off < 0 or \
           dst < 0 or dst + n > spec.DMEM_WORDS:
            d[spec.SD_GO] = 0            # refused: nothing moves, and the
            return                       # machine cannot be wedged
        # a save SNAPSHOTS memory at the latch, not at the landing: the
        # console pushes the words to the card while it waits, so what
        # gets written is what the cart had when it asked
        self.sd_snap = ([d[dst + i] & spec.WORD_MASK for i in range(n)]
                        if go == spec.SD_SAVE else [])
        self.sd_req = (slot, off, dst, n, go == spec.SD_SAVE)
        self.sd_counted = False
        self.sd_wait = spec.SD_LATENCY

    def frame(self, pad: int, pad2: int = 0) -> None:
        if self.trapped:
            return
        d = self.dmem
        d[spec.REG_FRAME] = self.frame_no & spec.WORD_MASK
        d[spec.REG_PAD] = pad & 0xFFFF
        d[spec.REG_PAD2] = pad2 & 0xFFFF
        self.frame_no += 1
        pc, fuel, st, rs = 0, spec.FUEL, [], []
        push, pop = st.append, st.pop

        def adr(a):                      # every DMEM access is range-checked:
            if not 0 <= a < spec.DMEM_WORDS:   # no accidental Python negative
                raise Trap(f"DMEM address {a} out of range")   # indexing here
            return a

        def sh(n):
            if not 0 <= n < 32:
                raise Trap(f"shift by {n} is undefined")
            return n

        # FUEL, MADE OBSERVABLE. It was a local, so nothing outside this
        # loop could say how close a cart runs to the ceiling -- which
        # made the ceiling itself unmeasurable, and it was raised from
        # 16,384 to 65,536 on a census that could not see it. Reporting
        # it changes no behaviour and no gate; it makes the budget's
        # other half visible beside the clock's.
        self.fuel_left = fuel
        try:
            while fuel > 0:
                fuel -= 1
                self.fuel_left = fuel
                word = self.imem[pc]
                op, imm = word >> 24, word & 0xFFFFFF
                if imm & 0x800000:
                    imm -= 0x1000000
                pc += 1
                if op == 0x00: return                                   # halt
                elif op == 0x01: push(imm & spec.WORD_MASK)             # push
                elif op == 0x02: push(d[adr(imm)])                      # load
                elif op == 0x03: d[adr(imm)] = pop()                    # store
                elif op == 0x04: push(d[adr(pop())])                    # loadi
                elif op == 0x05: a = adr(pop()); d[a] = pop()           # storei
                elif op == 0x10: b, a = pop(), pop(); push((a + b) & spec.WORD_MASK)
                elif op == 0x11: b, a = pop(), pop(); push((a - b) & spec.WORD_MASK)
                elif op == 0x12: b, a = pop(), pop(); push((s32(a) * s32(b)) & spec.WORD_MASK)
                elif op == 0x13: b, a = pop(), pop(); push(((s32(a) * s32(b)) >> 16) & spec.WORD_MASK)
                elif op == 0x14: b, a = pop(), pop(); push(a & b)
                elif op == 0x15: b, a = pop(), pop(); push(a | b)
                elif op == 0x16: b, a = pop(), pop(); push(a ^ b)
                elif op == 0x17: push((pop() << sh(imm)) & spec.WORD_MASK)  # shl
                elif op == 0x18: push((s32(pop()) >> sh(imm)) & spec.WORD_MASK)  # shr
                elif op == 0x19: b, a = pop(), pop(); push(1 if s32(a) < s32(b) else 0)
                elif op == 0x1A: b, a = pop(), pop(); push(1 if a == b else 0)
                elif op == 0x20: push(st[-1])                           # dup
                elif op == 0x21: pop()                                  # drop
                elif op == 0x22: st[-1], st[-2] = st[-2], st[-1]        # swap
                elif op == 0x23: push(st[-2])                           # over
                elif op == 0x30: pc = imm                               # jmp
                elif op == 0x31:                                        # jz
                    if pop() == 0: pc = imm
                elif op == 0x32:                                        # call
                    if len(rs) == spec.RSTACK_MAX:
                        raise Trap(f"return stack overflow at pc {pc - 1}")
                    rs.append(pc); pc = imm
                elif op == 0x33:                                        # ret
                    if not rs:
                        raise Trap(f"return stack underflow at pc {pc - 1}")
                    pc = rs.pop()
                else:
                    raise Trap(f"bad opcode {op:#04x} at pc {pc - 1}")
                if len(st) > spec.STACK_MAX:
                    raise Trap(f"stack overflow at pc {pc - 1}")
                if not 0 <= pc < spec.IMEM_WORDS:
                    raise Trap(f"pc {pc} out of IMEM")
        except IndexError:
            self.trapped = True
            raise Trap(f"stack underflow or bad address near pc {pc - 1}")
        except Trap:
            self.trapped = True
            raise
