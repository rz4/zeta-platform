"""test_card.py -- the card's law (spec.SD_*).

SD is the one device whose real latency varies, and variable latency is
fatal to a machine whose whole claim is bit-equality. So the wait is
legislated rather than measured, and these tests pin the legislation:
WHEN the data lands, that a bad request cannot wedge the frame, and that
nothing -- not even the cart -- can talk the machine out of physics
already in flight.
"""
from pathlib import Path

import pytest

from zeta import asm, spec, vm


# a request latched during frame 0 lands during frame SD_LATENCY, which
# is the (SD_LATENCY + 1)'th call counting the latch frame itself
LANDED = spec.SD_LATENCY + 1


def run(src, frames, pad=0):
    p = Path(__file__).parent / "_card_tmp.zol"
    p.write_text(src)
    try:
        m = vm.VM(asm.assemble(p))
    finally:
        p.unlink(missing_ok=True)
    for _ in range(frames):
        m.frame(pad)
        m.dma()
        m.card()
    return m


REQ = """
.sd 3 0 1000 2000 3000 4000
push 3
store {slot}
push {off}
store {offc}
push 600
store {dst}
push {n}
store {lenc}
push 1
store {go}
halt
""".format(slot=spec.SD_SLOT, offc=spec.SD_OFF, dst=spec.SD_DST,
           lenc=spec.SD_LEN, go=spec.SD_GO, off=0, n=4)


def test_lands_exactly_on_the_legislated_frame():
    for f in range(1, LANDED):
        m = run(REQ, f)
        assert m.dmem[600:604] == [0, 0, 0, 0], f"early at frame {f}"
        assert m.dmem[spec.SD_GO] == 1, "GO must stay up while in flight"
    m = run(REQ, LANDED)
    assert m.dmem[600:604] == [1000, 2000, 3000, 4000]
    assert m.dmem[spec.SD_GO] == 0, "clearing GO is the whole protocol"


def test_reads_past_the_end_are_zeros_not_errors():
    src = REQ.replace(f"push 0\nstore {spec.SD_OFF}",
                      f"push 2\nstore {spec.SD_OFF}")
    m = run(src, LANDED)
    assert m.dmem[600:604] == [3000, 4000, 0, 0]


@pytest.mark.parametrize("bad,cell", [
    (0, spec.SD_LEN),                      # zero length
    (spec.SD_MAX + 1, spec.SD_LEN),        # past the ceiling
    (spec.DMEM_WORDS - 1, spec.SD_DST),    # lands off the end of memory
    (-1, spec.SD_SLOT),                    # no such slot
])
def test_a_bad_request_moves_nothing_and_still_clears_go(bad, cell):
    src = REQ.replace("push 1\nstore %d" % spec.SD_GO,
                      f"push {bad}\nstore {cell}\npush 1\nstore {spec.SD_GO}")
    m = run(src, 1)
    assert m.dmem[spec.SD_GO] == 0, "a refused request must not stay pending"
    m = run(src, spec.SD_LATENCY + 2)
    assert m.dmem[600:604] == [0, 0, 0, 0], "a refused request moved data"


def test_one_request_at_a_time():
    """The cart re-asks every frame; it must still land exactly once, on
    the frame the first request was owed -- not on a later one."""
    m = run(REQ, LANDED)
    assert m.dmem[600:604] == [1000, 2000, 3000, 4000]


def test_the_cart_cannot_cancel_physics_in_flight():
    """Issue on frame 0, then spend every later frame trying to call it
    off. The card does not negotiate."""
    src = f"""
.sd 3 0 1000 2000 3000 4000
load {spec.REG_FRAME}
jz issue
push 0
store {spec.SD_GO}
halt
issue:
push 3
store {spec.SD_SLOT}
push 0
store {spec.SD_OFF}
push 600
store {spec.SD_DST}
push 4
store {spec.SD_LEN}
push 1
store {spec.SD_GO}
halt
"""
    m = run(src, LANDED)
    assert m.dmem[600:604] == [1000, 2000, 3000, 4000], \
        "clearing GO must not cancel a transfer already under way"


def test_a_cart_with_no_card_is_unaffected():
    m = run("push 1\nstore %d\nhalt" % spec.SD_GO, LANDED + 2)
    assert m.dmem[spec.SD_GO] == 0
    assert not m.trapped


# ---- the save: a read with its arrow reversed ---------------------------

SAVE = """
.sd 3 0 1000 2000 3000 4000
load {frame}
jz issue
halt
issue:
push 7
store 700
push 8
store 701
push 3
store {slot}
push 1
store {offc}
push 700
store {dst}
push 2
store {lenc}
push {save}
store {go}
halt
""".format(frame=spec.REG_FRAME, slot=spec.SD_SLOT, offc=spec.SD_OFF,
           dst=spec.SD_DST, lenc=spec.SD_LEN, go=spec.SD_GO,
           save=spec.SD_SAVE)


def test_a_save_rewrites_the_slot_image():
    m = run(SAVE, LANDED)
    assert m.sd[3][:4] == [1000, 7, 8, 4000], "the save did not land"
    assert m.dmem[spec.SD_GO] == 0, "a completed save must clear GO"


def test_a_save_does_not_land_early():
    for f in range(1, LANDED):
        assert run(SAVE, f).sd[3][:4] == [1000, 2000, 3000, 4000], \
            f"the slot changed at frame {f}"


def test_a_save_past_the_end_grows_the_slot():
    src = SAVE.replace(f"push 1\nstore {spec.SD_OFF}",
                       f"push 6\nstore {spec.SD_OFF}")
    m = run(src, LANDED)
    assert m.sd[3] == [1000, 2000, 3000, 4000, 0, 0, 7, 8]


def test_an_unknown_direction_is_refused():
    src = SAVE.replace(f"push {spec.SD_SAVE}\nstore {spec.SD_GO}",
                       f"push 9\nstore {spec.SD_GO}")
    m = run(src, LANDED)
    assert m.dmem[spec.SD_GO] == 0
    assert m.sd[3][:4] == [1000, 2000, 3000, 4000], "a bad direction moved data"


def test_save_then_read_back_returns_what_was_written():
    src = f"""
.sd 3 0 1000 2000 3000 4000
load {spec.REG_FRAME}
push 1
eq
jz later
push 42
store 700
push 3
store {spec.SD_SLOT}
push 0
store {spec.SD_OFF}
push 700
store {spec.SD_DST}
push 1
store {spec.SD_LEN}
push {spec.SD_SAVE}
store {spec.SD_GO}
halt
later:
load {spec.REG_FRAME}
push {LANDED + 2}
eq
jz done
push 3
store {spec.SD_SLOT}
push 0
store {spec.SD_OFF}
push 800
store {spec.SD_DST}
push 1
store {spec.SD_LEN}
push {spec.SD_READ}
store {spec.SD_GO}
done:
halt
"""
    m = run(src, LANDED * 2 + 6)
    assert m.dmem[800] == 42, "the card did not remember what it was told"


def test_a_save_snapshots_memory_at_the_latch():
    """The cart overwrites the source on a LATER frame, while the transfer
    is still in flight. What lands is what it had when it asked."""
    src = f"""
.sd 3 0 1000 2000 3000 4000
load {spec.REG_FRAME}
jz issue
push 999
store 700
push 999
store 701
halt
issue:
push 7
store 700
push 8
store 701
push 3
store {spec.SD_SLOT}
push 1
store {spec.SD_OFF}
push 700
store {spec.SD_DST}
push 2
store {spec.SD_LEN}
push {spec.SD_SAVE}
store {spec.SD_GO}
halt
"""
    m = run(src, LANDED)
    assert m.dmem[700] == 999, "the cart failed to scribble"
    assert m.sd[3][:4] == [1000, 7, 8, 4000], \
        "the save took the scribble instead of the snapshot"
