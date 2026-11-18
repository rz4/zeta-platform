"""The fight, pinned: the AI beats an idle player; an aggressive player
beats the AI; rounds reset. Cells match carts/tear.zol's .const map."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import asm, spec, vm

CART = Path(__file__).parents[1] / "carts/tear.zol"
PX, EX, PH, EH, KO, WIN = 16, 17, 18, 19, 24, 25


def test_ai_beats_idle_player():
    m = vm.VM(asm.assemble(CART))
    for f in range(1500):
        m.frame(0)
        if m.dmem[KO]:
            break
    else:
        raise AssertionError("no KO in 1500 idle frames")
    assert m.dmem[WIN] == 2
    assert spec.s32(m.dmem[PH]) < 1


def test_aggressive_player_beats_ai():
    m = vm.VM(asm.assemble(CART))
    for f in range(3000):
        m.frame(spec.PAD_RIGHT | spec.PAD_A)   # crowd it and swing on cooldown
        if m.dmem[KO]:
            break
    else:
        raise AssertionError("no KO in 3000 aggressive frames")
    assert m.dmem[WIN] == 1
    assert spec.s32(m.dmem[EH]) < 1


def test_round_resets_after_ko():
    m = vm.VM(asm.assemble(CART))
    while not m.dmem[KO]:
        m.frame(0)
    while m.dmem[KO]:                          # ride out the freeze; the
        m.frame(0)                             # last tick is the reset frame
    assert m.dmem[PH] == 96 and m.dmem[EH] == 96
    assert m.dmem[PX] == 60 and m.dmem[EX] == 236
