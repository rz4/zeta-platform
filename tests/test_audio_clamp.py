"""test_audio_clamp.py -- sixteen voices must saturate, not wrap.

Four channels peak at 4 x 15,360 = 61,440 into a >>2, which is 15,360 --
comfortably inside int16. The mix COULD have wrapped for years and never
did, so nothing legislated a clamp. Sixteen peak at 245,760, whose >>2 is
61,440, which is not: without saturation the loudest frame flips sign,
which is the ugliest noise an audio path can make.

carts/choir.zol cannot prove this and says so. Sixteen INDEPENDENT voices
rarely align -- each phase accumulator runs at its own rate, so making
their frequencies equal does not make their phases equal, and forcing a
mid-flight unison actually LOWERED its peak (30,420 -> 23,842). A cart is
the wrong instrument for a safety net.

So it is proven here, where the phases can be aligned on purpose.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import audio, spec


def dmem_with(vol, chans, hz=432.0):
    d = [0] * spec.DMEM_WORDS
    inc = int(round(hz * (1 << 24) / spec.SND_HZ))
    for c in range(chans):
        d[spec.AU_BASE + 2 * c] = inc
        d[spec.AU_BASE + 2 * c + 1] = vol | (
            spec.AU_WAVE if c < spec.AU_TONE_CHANNELS else 0)
    return d


def sine_page(amp=90):
    return [int(round(amp * np.sin(2 * np.pi * i / spec.WAV_W)))
            for i in range(spec.WAV_W)]


def test_four_channels_never_reach_the_clamp():
    """The reason it was safe to have no clamp for years -- and the
    reason adding one cannot change any existing cart's output."""
    out = audio.SndEngine().frame(dmem_with(15, 4), sine_page())
    assert int(np.abs(out).max()) < spec.AU_CLAMP


def test_sixteen_aligned_voices_saturate():
    """A fresh engine starts every phase at zero, so sixteen voices on
    one frequency really do align -- which is exactly the case the clamp
    exists for."""
    out = audio.SndEngine().frame(dmem_with(15, 16), sine_page())
    assert int((np.abs(out) >= spec.AU_CLAMP).sum()) > 0, \
        "sixteen aligned voices did not reach the ceiling"


def test_it_saturates_rather_than_wrapping():
    """The whole point. A wrap sends a loud POSITIVE peak to a large
    NEGATIVE sample; saturation holds it at the ceiling. Check the sign
    never inverts across the loudest region."""
    out = audio.SndEngine().frame(dmem_with(15, 16), sine_page())
    top = int(np.argmax(out))
    assert out[top] == spec.AU_CLAMP
    # the samples either side of the peak must also be positive: a wrap
    # would put a deep negative right beside the maximum
    lo, hi = max(0, top - 3), min(len(out), top + 4)
    assert (out[lo:hi] > 0).all(), f"sign inverted next to the peak: {out[lo:hi]}"


def test_the_clamp_is_symmetric():
    out = audio.SndEngine().frame(dmem_with(15, 16), sine_page())
    assert out.min() >= -spec.AU_CLAMP - 1
    assert out.max() <= spec.AU_CLAMP
