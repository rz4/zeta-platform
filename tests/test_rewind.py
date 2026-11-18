"""test_rewind.py -- THE REWIND GATE (docs/ZETA0.md, POCKET.md D1).

A snapshot is the machine's whole state between two frames, legislated
in spec.py (spec.STATE_*). Restore it and the machine must continue
BIT-EQUAL to a machine that was never interrupted: the framebuffer, the
panel, and every one of the frame's 800 samples. That is the law's half
of Memories -- the cabinet gets rewind from it today, the Pocket when the
head learns to hand the image over, and the cross across time (save on
glass, load on the law, continue) is this same comparison with the
snapshot carried between machines.

EVERY FIELD IS WITNESSED BY MUTATION. A snapshot that quietly omitted the
audio phases would pass on every silent cart, so each field is paired
with a cart on which zeroing that field breaks the continuation. A gate
that cannot fail is not a gate (the fade.zol rule).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import asm, cabinet, spec  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def machine(name):
    return cabinet.VirtualMachine(asm.assemble(ROOT / f"carts/{name}.zol"))


def pad_at(i):
    """A pad script with edges in it, so carts that act on buttons act."""
    return ((i * 7) & 0x0FFF) if (i % 5) else 0


def observe(m, frames, start):
    """(framebuffer, panel, audio) for each of the next `frames`."""
    out = []
    for i in range(start, start + frames):
        m.frame(pad_at(i))
        out.append((m.framebuffer().copy(), m.panel().copy(),
                    m.audio().copy()))
    return out


def same(a, b):
    return all(np.array_equal(x, y) for p, q in zip(a, b) for x, y in zip(p, q))


# the carts that exercise each kind of state, and how long they need to
# reach it (overlay.zol swaps its program at frame 120)
CARTS = [("tear", 20, 10), ("bunny", 12, 8), ("voice", 20, 10),
         ("pages", 30, 8), ("overlay", 125, 8), ("fade", 20, 8),
         ("heard", 30, 8), ("shade", 12, 6)]


@pytest.mark.parametrize("name,before,after", CARTS)
def test_restore_continues_bit_equal(name, before, after):
    m = machine(name)
    observe(m, before, 0)
    s = m.snapshot()
    first = observe(m, after, before)
    m.restore(s)
    again = observe(m, after, before)
    assert same(first, again), f"{name}: the rewound machine diverged"
    # ...and the snapshot itself changed nothing: a machine that was
    # never interrupted sees the same frames
    u = machine(name)
    observe(u, before, 0)
    assert same(first, observe(u, after, before)), \
        f"{name}: taking the snapshot perturbed the machine"


@pytest.mark.parametrize("name,before,after", CARTS[:4])
def test_the_image_round_trips(name, before, after):
    m = machine(name)
    observe(m, before, 0)
    blob = m.pack()
    assert len(blob) == spec.STATE_BYTES
    first = observe(m, after, before)
    n = cabinet.VirtualMachine(asm.assemble(ROOT / f"carts/{name}.zol"))
    n.restore(cabinet.VirtualMachine.unpack(blob))   # a DIFFERENT machine
    assert same(first, observe(n, after, before)), \
        f"{name}: the image did not carry the state to a fresh machine"


# ---------------------------------------------------------------------------
# the witnesses: each field, on a cart where losing it shows
# ---------------------------------------------------------------------------
def zero(s, field):
    t = dict(s)
    if field == "tex":
        t["tex"] = np.zeros_like(s["tex"])
    elif field in ("phase",):
        t[field] = [0] * len(s[field])
    elif field == "heard":
        t["heard"] = [[0] * spec.AU_CHANNELS, [0] * spec.AU_CHANNELS]
    elif field == "imem":
        t["imem"] = [0] * spec.IMEM_WORDS          # 0 is HALT: an empty program
    elif field == "imem0":                         # the program the cart BOOTED
        t["imem"] = list(s["imem0"])               # with, not the one it became
    elif field == "dmem":
        t["dmem"] = [0] * spec.DMEM_WORDS
    elif field == "frame_no":
        t["frame_no"] = 0
    else:
        raise KeyError(field)
    return t


MUTATIONS = [("phase", "voice", 20, 6),      # a wavetable voice mid-cycle
             ("tex", "pages", 30, 4),        # pages loaded at startup, kept
             ("imem", "bunny", 12, 4),       # the program that turns it
             ("imem0", "overlay", 125, 4),   # the program the cart BECAME at
                                             # frame 120, against the one it
                                             # booted with: IMEM is state
             ("dmem", "bunny", 12, 4),       # the game itself
             ("heard", "heard", 30, 3),      # the two-frame AUD ring
             ("frame_no", "shade", 12, 4)]   # REG_FRAME alone drives the slide


@pytest.mark.parametrize("field,name,before,after", MUTATIONS)
def test_every_field_is_load_bearing(field, name, before, after):
    cart = asm.assemble(ROOT / f"carts/{name}.zol")
    m = cabinet.VirtualMachine(cart)
    observe(m, before, 0)
    s = m.snapshot()
    s["imem0"] = list(cart["imem"]) + [0] * (spec.IMEM_WORDS - len(cart["imem"]))
    first = observe(m, after, before)
    m.restore(zero(s, field))
    assert not same(first, observe(m, after, before)), \
        f"{field}: zeroing it changed nothing on {name} -- the witness is blind"


# ---------------------------------------------------------------------------
# the card rule
# ---------------------------------------------------------------------------
def test_a_snapshot_waits_for_the_card():
    m = machine("bunny")
    observe(m, 3, 0)
    d = m.vm.dmem
    d[spec.SD_SLOT], d[spec.SD_OFF], d[spec.SD_DST] = 0, 0, spec.USER_BASE
    d[spec.SD_LEN], d[spec.SD_GO] = 4, spec.SD_READ
    m.vm.card()                                   # latched: in flight
    with pytest.raises(cabinet.StateBusy):
        m.snapshot()
    observe(m, spec.SD_LATENCY, 3)                # it lands
    m.snapshot()                                  # and the refusal ends
