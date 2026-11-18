"""test_overlay.py -- the cart stops being 4,096 instructions.

An overlay pages CODE from the cart's CRAM segment into IMEM at the
mover's own instant. The safety is the frame model rather than a rule:
the VM has already halted when the move happens, and every frame begins
at PC 0, so a cart cannot overwrite the program it is standing on -- it
asks, its frame ends, and the next frame starts at zero in the new one.

These pin that: the move lands, it lands BETWEEN frames, a bad request
moves nothing and still clears GO, and -- the point of the whole thing --
a cart really can replace itself and keep running.
"""
from pathlib import Path

import pytest

from zeta import asm, spec, vm


def build(src, cram=None):
    p = Path(__file__).parent / "_ovl_tmp.zol"
    p.write_text(src)
    try:
        cart = asm.assemble(p)
    finally:
        p.unlink(missing_ok=True)
    if cram:
        cart["cram"] = {str(a): v for a, v in cram.items()}
    return vm.VM(cart)


def step(m, n, pad=0):
    for _ in range(n):
        m.frame(pad)
        m.dma()
        m.overlay()
        m.card()
    return m


# a one-instruction program: store 7 into cell 500, then halt
NEW_CODE = {0: (spec.OPS["push"][0] << 24) | 7,
            1: (spec.OPS["store"][0] << 24) | 500,
            2: (spec.OPS["halt"][0] << 24)}

ASK = """
push {src}
store {srcc}
push {dst}
store {dstc}
push {n}
store {lenc}
push 1
store {goc}
push 1
store 600
halt
""".format(srcc=spec.OVL_SRC, dstc=spec.OVL_DST, lenc=spec.OVL_LEN,
           goc=spec.OVL_GO, src=100, dst=0, n=3)


def test_the_overlay_lands_in_imem():
    m = build(ASK, cram={100 + k: v for k, v in NEW_CODE.items()})
    step(m, 1)
    assert m.imem[0] == NEW_CODE[0], "the code did not land"
    assert m.dmem[spec.OVL_GO] == 0, "a completed overlay must clear GO"


def test_a_cart_can_replace_itself_and_keep_running():
    """The whole point: frame 1 runs the ORIGINAL program, frame 2 runs
    the one it paged in."""
    m = build(ASK, cram={100 + k: v for k, v in NEW_CODE.items()})
    step(m, 1)
    assert m.dmem[600] == 1, "the original program did not run"
    assert m.dmem[500] == 0, "the new program ran too early"
    step(m, 1)
    assert m.dmem[500] == 7, "the paged-in program never ran"


def test_the_move_happens_after_the_vm_halts():
    """A cart standing on the code it replaces is safe by construction:
    the frame that asks completes in the OLD program."""
    m = build(ASK, cram={100 + k: v for k, v in NEW_CODE.items()})
    m.frame(0)
    assert m.imem[0] != NEW_CODE[0], "IMEM changed while the VM was running"
    m.dma()
    m.overlay()
    assert m.imem[0] == NEW_CODE[0]


@pytest.mark.parametrize("bad,cell", [
    (0, spec.OVL_LEN),                    # zero length
    (spec.OVL_MAX + 1, spec.OVL_LEN),     # past the ceiling
    (spec.IMEM_WORDS - 1, spec.OVL_DST),  # would land off the end of IMEM
    (-1, spec.OVL_SRC),                   # nonsense source
])
def test_a_bad_overlay_moves_nothing_and_clears_go(bad, cell):
    src = ASK.replace("push 1\nstore %d" % spec.OVL_GO,
                      f"push {bad}\nstore {cell}\npush 1\nstore {spec.OVL_GO}")
    m = build(src, cram={100 + k: v for k, v in NEW_CODE.items()})
    step(m, 1)
    assert m.dmem[spec.OVL_GO] == 0, "a refused overlay must not stay pending"
    assert m.imem[0] != NEW_CODE[0], "a refused overlay moved code"
    assert not m.trapped


def test_an_overlay_of_zero_is_simply_a_no_op():
    m = build("push 1\nstore %d\nhalt" % spec.OVL_GO)
    step(m, 2)
    assert m.dmem[spec.OVL_GO] == 0
    assert not m.trapped
