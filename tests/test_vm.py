"""ISA semantics pinned as tests -- the same cases the silicon cross reruns."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from zeta import asm, gpu, spec, vm


def machine(src: str, tmp_path) -> vm.VM:
    f = tmp_path / "t.zol"
    f.write_text(src)
    return vm.VM(asm.assemble(f))


def run1(src: str, tmp_path, pad: int = 0) -> vm.VM:
    m = machine(src, tmp_path)
    m.frame(pad)
    return m


def test_arith_wraps_32bit(tmp_path):
    m = run1("push 0x7FFFFF\nshl 8\npush 0x7FFFFF\nshl 8\nadd\nstore 16\nhalt",
             tmp_path)
    assert m.dmem[16] == (0x7FFFFF00 * 2) & spec.WORD_MASK


def test_lt_is_signed(tmp_path):
    m = run1("push -1\npush 0\nlt\nstore 16\nhalt", tmp_path)
    assert m.dmem[16] == 1        # -1 < 0, not 0xFFFFFFFF < 0


def test_shr_is_arithmetic(tmp_path):
    m = run1("push -8\nshr 1\nstore 16\nhalt", tmp_path)
    assert spec.s32(m.dmem[16]) == -4


def test_mulq_q16(tmp_path):
    # 1.5 * 2.5 = 3.75 in Q16.16
    m = run1("push 0x18000\npush 0x28000\nmulq\nstore 16\nhalt", tmp_path)
    assert m.dmem[16] == 0x3C000


def test_fuel_stops_lawfully(tmp_path):
    m = run1("spin:\njmp spin", tmp_path)      # never halts; fuel ends it
    assert not m.trapped


def test_stack_underflow_traps(tmp_path):
    with pytest.raises(vm.Trap):
        run1("add\nhalt", tmp_path)


def test_pad_reaches_cell1(tmp_path):
    m = run1("halt", tmp_path, pad=spec.PAD_A | spec.PAD_UP)
    assert m.dmem[spec.REG_PAD] == spec.PAD_A | spec.PAD_UP


def test_bounce_cart_300_frames(tmp_path):
    cart = asm.assemble(Path(__file__).parents[1] / "carts/examples/bounce.zol")
    m = vm.VM(cart)
    xs = set()
    for f in range(300):
        m.frame(0)
        xs.add(m.dmem[16])
        assert 0 <= spec.s32(m.dmem[16]) <= 280
        assert 0 <= spec.s32(m.dmem[17]) <= 248
    assert len(xs) > 50                        # it actually moves
    fb = gpu.render(m.dmem)
    assert (fb == spec.display_rgb(0x33AAFF)).all(axis=2).sum() > 1500  # square is lit
