"""The SND contract, pinned: waveform shapes, mixing, state persistence."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import audio, spec


def dmem_with(**regs):
    d = [0] * spec.DMEM_WORDS
    for k, v in regs.items():
        d[int(k[1:])] = v
    return d


def test_silence():
    e = audio.SndEngine()
    assert not e.frame([0] * spec.DMEM_WORDS).any()


def test_pulse_shape():
    # inc 2^19: 32-sample period; duty 2 -> 50%; vol 5 -> +/-5120 (>>2 1280)
    e = audio.SndEngine()
    d = dmem_with(**{f"a{spec.AU_BASE}": 1 << 19,
                     f"a{spec.AU_BASE + 1}": (2 << 4) | 5})
    s = e.frame(d)
    assert set(np.unique(s)) == {-1280, 1280}
    assert (s[:8] == 1280).all() and (s[20:28] == -1280).all()
    assert abs(int(s.astype(np.int64).mean())) < 200      # ~50% duty


def test_triangle_ramps_and_persists():
    e = audio.SndEngine()
    d = dmem_with(**{f"a{spec.AU_BASE + 4}": 1 << 16,
                     f"a{spec.AU_BASE + 5}": 15})
    a = e.frame(d)
    b = e.frame(d)
    assert a.min() < -3500 and a.max() > 3500       # full swing (>>2 of
    assert abs(int(a[1]) - int(a[0])) < 200         # +/-15360), and smooth
    assert not np.array_equal(a[:100], b[:100])     # phase carried over


def test_noise_is_deterministic():
    e1, e2 = audio.SndEngine(), audio.SndEngine()
    d = dmem_with(**{f"a{spec.AU_BASE + 6}": 0x600000,
                     f"a{spec.AU_BASE + 7}": 15})
    a, b = e1.frame(d), e2.frame(d)
    assert np.array_equal(a, b)
    assert len(np.unique(a)) == 2 and abs(int(a[0])) == 3840


def test_mix_is_sum_shifted():
    e = audio.SndEngine()
    d = dmem_with(**{f"a{spec.AU_BASE}": 1 << 19,
                     f"a{spec.AU_BASE + 1}": (2 << 4) | 15,
                     f"a{spec.AU_BASE + 2}": 1 << 19,
                     f"a{spec.AU_BASE + 3}": (2 << 4) | 15})
    s = e.frame(d)
    assert set(np.unique(s)) == {-7680, 7680}       # 2 * 15*1024 >> 2
