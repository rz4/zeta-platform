"""THE SILICON STARTS FROM THE LAW'S STATE (spec.STATE_*).

tests/test_rewind.py holds the law to its own snapshot. This holds the
silicon to it: hand the Verilated core a state image taken at frame N and
it continues bit-equal to the law -- picture and every sample -- so the
legislated state is ALL of the state, on the RTL too. zeta/profile.py
costs a tape in parallel windows on that; the Pocket's save-state
hand-over must reach the same fields.
"""
import shutil
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zeta import cabinet, carts, profile, silicon, spec  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("verilator") is None,
                                reason="verilator not installed")


def _pad(f):
    return 1 if (f // 20) % 2 else 0


def _resume(name, at, more, mutate=None, both=None):
    """-> the first frame after `at` where the silicon, started from the
    law's image there, differs from the law (None: never in `more`).
    `both` edits the image for both machines; `mutate` for the silicon's
    copy alone."""
    cart = cabinet.load_cart(carts.path(name))
    m = cabinet.VirtualMachine(cart)
    for f in range(at):
        m.frame(_pad(f))
    blob = m.pack()
    if both:
        blob = bytes(both(bytearray(blob)))
        m.restore(cabinet.VirtualMachine.unpack(blob))
    if mutate:
        blob = mutate(bytearray(blob))
    s = silicon.SiliconMachine(
        dict(cart, sd={k: list(v) for k, v in m.vm.sd.items()}), state=bytes(blob))
    try:
        for f in range(at, at + more):
            m.frame(_pad(f))
            s.frame(_pad(f))
            if not (np.array_equal(m.framebuffer(), s.framebuffer())
                    and np.array_equal(m.audio(), s.audio())):
                return f
    finally:
        s.close()
    return None


# the law's own list (tests/test_rewind.py CARTS), and the carts that add
# what it lacks: events (band), the card's counters (save), a full scene
@pytest.mark.parametrize("name,at", [
    ("tear", 20), ("bunny", 12), ("voice", 20), ("pages", 30), ("overlay", 125),
    ("fade", 20), ("heard", 33), ("shade", 12), ("tex", 25), ("choir", 30),
    ("band", 40), ("save", 70), ("vessel", 45)])
def test_the_silicon_continues_from_the_laws_state(name, at):
    assert _resume(name, at, 12) is None


# where each field sits in the image (cabinet.VirtualMachine.pack)
_HEAD = 4 * 9
_MEM = _HEAD + 4 * (spec.IMEM_WORDS + spec.DMEM_WORDS)
_PHASE = _MEM
_HEARD = _PHASE + 4 * spec.AU_CHANNELS
_TEX = _HEARD + 4 * 2 * spec.AU_CHANNELS
_WAV = _TEX + 2 * spec.TEX_PAGES * spec.TEX_STRIDE


def _zero(lo, hi):
    def f(b):
        b[lo:hi] = bytes(hi - lo)
        return b
    return f


@pytest.mark.parametrize("field,name,at,lo,hi", [
    ("the frame counter", "shade", 12, 8, 12),      # REG_FRAME drives the slide
    ("the phases", "voice", 20, _PHASE, _HEARD),    # a voice mid-cycle
    ("the heard ring", "heard", 33, _HEARD, _TEX),
    ("the texture pages", "pages", 30, _TEX, _WAV),  # loaded at startup, kept
    ("IMEM", "bunny", 12, _HEAD, _HEAD + 4 * spec.IMEM_WORDS),
    ("DMEM", "bunny", 12, _HEAD + 4 * spec.IMEM_WORDS, _MEM),
])
def test_every_field_of_the_image_reaches_the_silicon(field, name, at, lo, hi):
    """Mutation: blank one field of the image and the silicon no longer
    continues as the law does. A loader that skipped the field -- or a
    cart that never needed it -- would pass the test above and fail here."""
    assert _resume(name, at, 12, _zero(lo, hi)) is not None, \
        f"{field} was blanked in the image and nothing noticed"


def test_a_session_costed_in_windows_is_the_session_costed_whole():
    """profile.profile against one uninterrupted run: the machine's WORK
    is identical frame for frame (pixels walked, triangles skipped), and
    the clock total agrees to a part in a thousand -- the remainder is the
    PSRAM model's pseudo-random refresh, which is not machine state."""
    cart = cabinet.load_cart(carts.path("vessel"))
    pads = [_pad(f) for f in range(60)]
    whole = profile.cost(cart, pads)
    parts = profile.profile(cart, pads, window=20, jobs=3)
    assert [r["frame"] for r in parts] == list(range(60))
    for a, b in zip(whole, parts):
        assert (a["walk"], a["skp"]) == (b["walk"], b["skp"]), (a, b)
        assert abs(a["clk"] - b["clk"]) <= max(64, a["clk"] // 1000), (a, b)
    assert "heaviest" in profile.report(parts)


_WAV_SRC = _HEAD + 4 * (spec.IMEM_WORDS + spec.WAV_SRC)


def test_a_kept_wave_page_reaches_the_silicon():
    """Every sound cart in the repo reloads its wave pages each frame, so
    blanking them in an image shows nothing -- on the law either
    (tests/test_rewind.py has no wave mutation). The state says a page is
    KEPT when nothing reloads it. So stop the reload in the image itself
    (WAV_SRC = 0, for both machines): the silicon still continues as the
    law does, on the pages the image carried, and no longer does once
    those are blanked."""
    stop = _zero(_WAV_SRC, _WAV_SRC + 4)
    assert _resume("voice", 20, 8, both=stop) is None
    assert _resume("voice", 20, 8, both=stop,
                   mutate=_zero(_WAV, spec.STATE_BYTES)) is not None
