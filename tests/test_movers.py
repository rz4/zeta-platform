# THE MOVERS' INSTANT reads every request as the program left it.
#
# The probe that found the seam, kept as its gate: one frame asks for an
# overlay of program A (draws blue) AND a one-word DMA that rewrites
# OVL_SRC to point at program B (draws green). Under the old law the
# overlay ran after the DMA and read the rewritten cell -- B, green --
# while the silicon had latched the request before the DMA and loaded
# A, blue. The two machines drew different programs from the same cart.
# The amendment (vm.py, REQUEST_CELLS) legislates the silicon's reading.

import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import asm, cabinet, spec  # noqa: E402

BLUE, GREEN = 0x0000FF, 0x00FF00


def _prog(rgb):
    return "\n".join(["push 1", "store 12288",
                      "push 40", "store 12289", "push 40", "store 12290",
                      "push 200", "store 12291", "push 40", "store 12292",
                      "push 40", "store 12293", "push 200", "store 12294",
                      f"push {rgb}", "store 12295", "halt", ""])


def _probe(tmp_path):
    words = {}
    for name, rgb in (("a", BLUE), ("b", GREEN)):
        (tmp_path / f"{name}.zol").write_text(_prog(rgb))
        words[name] = asm.assemble(tmp_path / f"{name}.zol")["imem"]
    boot = "\n".join([
        "load 0", "jz first", "halt", "first:",
        "push 100", f"store {spec.OVL_SRC}",       # the request: program A
        "push 0", f"store {spec.OVL_DST}",
        f"push {len(words['a'])}", f"store {spec.OVL_LEN}",
        "push 1", f"store {spec.OVL_GO}",
        "push 500", f"store {spec.DMA_SRC}",       # ...and a DMA that
        f"push {spec.OVL_SRC}", f"store {spec.DMA_DST}",   # rewrites it
        "push 1", f"store {spec.DMA_LEN}",
        "push 1", f"store {spec.DMA_GO}",
        "halt",
        ".cram 100 " + " ".join(map(str, words["a"])),
        ".cram 300 " + " ".join(map(str, words["b"])),
        ".cram 500 300", ""])
    (tmp_path / "probe.zol").write_text(boot)
    return cabinet.load_cart(tmp_path / "probe.zol")


def test_the_overlay_serves_the_request_the_program_made(tmp_path):
    m = cabinet.VirtualMachine(_probe(tmp_path))
    m.frame(0)
    m.frame(0)                                  # program A draws
    px = tuple(int(c) for c in m.framebuffer()[100, 60])
    assert px == (0, 0, 255), (
        f"the overlay loaded the DMA's rewrite, not the request: {px}")
    # ...and the DMA still LANDED: DMEM holds its write for later frames
    assert m.vm.dmem[spec.OVL_SRC] == 300


@pytest.mark.skipif(shutil.which("verilator") is None,
                    reason="verilator not installed")
def test_both_machines_agree(tmp_path):
    from zeta import silicon
    cart = _probe(tmp_path)
    v, s = cabinet.VirtualMachine(cart), silicon.SiliconMachine(cart)
    for f in range(3):
        v.frame(0)
        s.frame(0)
        assert np.array_equal(v.framebuffer(), s.framebuffer()), \
            f"the movers' instant reads requests differently at frame {f}"


# ---- spec.AU_RESET: the synth's cold start -----------------------------------
def _tone_cart(tmp_path, reset_on):
    """a pulse voice that sounds for a while, then (on frame reset_on, if
    any) asks for the cold start, then plays the same note again"""
    body = f"""
load 0
push 10
lt
jz later
push 99999
store {spec.AU_BASE}
push 15
store {spec.AU_BASE + 1}
halt
later:
load 0
push {reset_on}
eq
jz go
push 1
store {spec.AU_RESET}
go:
push 77777
store {spec.AU_BASE}
push 15
store {spec.AU_BASE + 1}
halt
"""
    pth = tmp_path / f"tone{reset_on}.zol"
    pth.write_text(body)
    return cabinet.VirtualMachine(cabinet.load_cart(pth))


def test_au_reset_is_a_cold_start(tmp_path):
    """Two machines with DIFFERENT histories (one ran an extra frame of a
    different pitch first) sound the same once both ask for the cold
    start -- and without it they do not. The cell clears itself."""
    a = _tone_cart(tmp_path, 12)
    b = _tone_cart(tmp_path, 12)
    b.vm.frame_no = 3                   # b skips 3 frames of the first tone
    for _ in range(12):
        a.frame(0)
    for _ in range(9):
        b.frame(0)
    a.frame(0)
    b.frame(0)                          # both: frame 12, the cold start
    assert np.array_equal(a.audio(), b.audio()), "the cold start left history"
    assert a.vm.dmem[spec.AU_RESET] == 0, "AU_RESET did not clear itself"
    c = _tone_cart(tmp_path, -1)        # (never asks)
    d = _tone_cart(tmp_path, -1)
    d.vm.frame_no = 3
    for _ in range(12):
        c.frame(0)
    for _ in range(9):
        d.frame(0)
    c.frame(0)
    d.frame(0)
    assert not np.array_equal(c.audio(), d.audio()), \
        "the witness cannot tell histories apart: it proves nothing"


@pytest.mark.skipif(shutil.which("verilator") is None,
                    reason="verilator not installed")
def test_au_reset_on_silicon(tmp_path):
    """Machine 2 resets its phases at the frame boundary the law resets
    at: every sample of every frame, through the cold start, bit-equal."""
    from zeta import silicon
    _tone_cart(tmp_path, 12)                    # writes tone12.zol
    cart = cabinet.load_cart(tmp_path / "tone12.zol")
    v, s = cabinet.VirtualMachine(cart), silicon.SiliconMachine(cart)
    for f in range(20):
        v.frame(0)
        s.frame(0)
        assert np.array_equal(v.audio(), s.audio()), f"audio diverges at {f}"
