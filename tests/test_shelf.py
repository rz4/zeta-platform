# THE CROSS ACROSS A LAUNCH (SEAMS 2's gate): the shelf's handoff to a
# game must be bit-equal to the same game booted directly, from the
# launch frame on -- framebuffers and samples, the cross's own
# standard. REG_FRAME continues across a launch (the tape records the
# launch frame), so the direct machine starts its counter there.

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import cabinet, spec  # noqa: E402

ROOT = Path(__file__).parents[1]
PRESS = 10                      # A lands on this frame
HANDOFF = PRESS + 5             # 4 DMA frames + the OVL frame


def _launch():
    m = cabinet.VirtualMachine(cabinet.load_cart(ROOT / "carts/shelf.zol"))
    for f in range(HANDOFF):
        m.frame(spec.PAD_A if f == PRESS else 0)
    return m


def test_the_cross_across_the_launch():
    """240 frames of fighting after the handoff, both machines driven
    by the same pads: every framebuffer and every sample identical."""
    shelf = _launch()
    direct = cabinet.VirtualMachine(cabinet.load_cart(ROOT / "carts/tear.zol"))
    direct.vm.frame_no = HANDOFF
    for f in range(240):
        pad = spec.PAD_RIGHT | (spec.PAD_A if f % 9 == 0 else 0) \
            | (spec.PAD_B if f % 31 == 0 else 0)
        shelf.frame(pad)
        direct.frame(pad)
        assert np.array_equal(shelf.framebuffer(), direct.framebuffer()), \
            f"framebuffers diverge {f} frames after the launch"
        assert np.array_equal(shelf.audio(), direct.audio()), \
            f"audio diverges {f} frames after the launch"


def test_the_menu_stands_until_the_press():
    """No press, no launch: the shelf idles on its menu forever, and a
    HELD A from power-on is not a press."""
    m = cabinet.VirtualMachine(cabinet.load_cart(ROOT / "carts/shelf.zol"))
    for f in range(60):
        m.frame(spec.PAD_A)            # held from frame 0: never fresh
    assert m.vm.imem is not None
    # the menu text is still in the display list (nonzero triangle count
    # at DL_BASE and the launch cell never armed)
    assert m.vm.dmem[spec.DL_BASE] > 0
    la = [a for a in range(16, 48)]    # the launch var is a low cell;
    m2 = cabinet.VirtualMachine(cabinet.load_cart(ROOT / "carts/shelf.zol"))
    m2.frame(0)
    m2.frame(spec.PAD_A)               # up then down: THIS is a press
    assert any(m2.vm.dmem[a] != m.vm.dmem[a] for a in la), \
        "a fresh press changed nothing -- the launch never armed"


def test_the_handoff_is_the_game():
    """After the five frames, the machine IS tear: its program fights,
    its KO freezes, its reset restores -- on the shelf's own hardware."""
    m = _launch()
    for f in range(1500):
        m.frame(0)                     # idle player: the AI must win
        if m.vm.dmem[24]:              # KO
            break
    else:
        raise AssertionError("no KO: the launched game is not fighting")
    assert m.vm.dmem[25] == 2          # WIN: the machine


# ---- SEG_BASE: the segment window (the law's own unit witnesses) ----------
def _mini(tmp_path, body):
    p = tmp_path / "t.zol"
    p.write_text(body)
    return cabinet.VirtualMachine(cabinet.load_cart(p))


def test_seg_base_relocates_the_dma(tmp_path):
    """The same presented offset reads a different place through the
    window -- and reads the OLD place with the window at zero (the
    mutation half: a SEG_BASE the movers ignored would fail here)."""
    body = """
.cram 1 111 222 333
.cram 101 777 888 999
load 50
jz off
push 100
store 12262
off:
push 1
store 12
push 60
store 13
push 3
store 14
push 1
store 15
halt
"""
    m = _mini(tmp_path, body)            # cell 50 = 0: window stays 0
    m.frame(0)
    assert [m.vm.dmem[60 + i] for i in range(3)] == [111, 222, 333]
    m2 = _mini(tmp_path, body)
    m2.vm.dmem[50] = 1                   # arm the window: base 100
    m2.frame(0)
    assert [m2.vm.dmem[60 + i] for i in range(3)] == [777, 888, 999], \
        "the mover ignored SEG_BASE"


def test_bg_zero_is_still_no_backdrop(tmp_path):
    """BG_SRC == 0 means none, WHATEVER the window says -- the presented
    value keeps its old refusals."""
    m = _mini(tmp_path, "push 5000\nstore 12262\nhalt\n")
    m.frame(0)
    fb = m.framebuffer()
    m0 = _mini(tmp_path, "halt\n")
    m0.frame(0)
    assert np.array_equal(fb, m0.framebuffer())


def test_the_hall_launches_relocated():
    """Entry B: a game WITH a segment, shelved. Its plates live at the
    shelf's offsets, its DMEM image carries the baked base, and 120
    frames after the handoff it is bit-equal to a direct boot -- the
    relocation witness."""
    m = cabinet.VirtualMachine(cabinet.load_cart(ROOT / "carts/shelf.zol"))
    for f in range(HANDOFF):
        m.frame(spec.PAD_B if f == PRESS else 0)
    direct = cabinet.VirtualMachine(cabinet.load_cart(ROOT / "carts/hall.zol"))
    direct.vm.frame_no = HANDOFF
    saw_backdrop = False
    for f in range(120):
        m.frame(0)
        direct.frame(0)
        assert np.array_equal(m.framebuffer(), direct.framebuffer()), \
            f"the relocated hall diverges {f} frames after the launch"
        assert np.array_equal(m.audio(), direct.audio())
        if m.vm.dmem[spec.BG_SRC] > 0:
            saw_backdrop = True
    assert saw_backdrop, "hall never asked for its plate -- the witness " \
        "exercised nothing"


# ---- the silicon half: the cross across both launches ---------------------
import shutil

import pytest


@pytest.mark.skipif(shutil.which("verilator") is None,
                    reason="verilator not installed")
@pytest.mark.parametrize("name,btn", [("tear", "PAD_A"), ("hall", "PAD_B")])
def test_the_silicon_crosses_the_launch(name, btn):
    """Machine 2 through the whole handoff -- the DMA walk, the overlay,
    and (for hall) the backdrop pump reading through an armed window --
    bit-equal to machine 1 every frame. This is SEG_BASE's silicon
    witness: remove the add from either machine and this names the
    frame."""
    from zeta import silicon
    cart = cabinet.load_cart(ROOT / "carts/shelf.zol")
    v = cabinet.VirtualMachine(cart)
    s = silicon.SiliconMachine(cart)
    press = getattr(spec, btn)
    for f in range(75):
        pad = press if f == PRESS else 0
        v.frame(pad)
        s.frame(pad)
        assert np.array_equal(v.framebuffer(), s.framebuffer()), \
            f"{name}: machines diverge at frame {f}"
        assert np.array_equal(v.audio(), s.audio()), \
            f"{name}: audio diverges at frame {f}"
