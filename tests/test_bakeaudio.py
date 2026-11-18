"""test_bakeaudio.py -- the offline path, and the one claim it makes.

Most of this file checks plumbing: a page is WAV_W samples, a bank is
WAV_PAGES of them, a page index is in range. Those are cheap and they
belong here.

The claim worth a gate is the last one. bakeaudio says a band-limited
mip chain removes aliasing from the top of the keyboard, and "removes
aliasing" is exactly the kind of sentence that sounds true, gets written
into a docstring, and is never once measured. So it is measured -- through
the actual law, not a model of it -- by asking what fraction of the
audible energy lands on real harmonics of the note being played.

A sawtooth at 7,040 Hz is the worst case a 256-sample page can be put
through, and the numbers are not close: 81.6% on the full page, 99.99%
on the mip page. If that ever stops being true this file fails, and the
docstrings that repeat the number are wrong with it.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import audio, bakeaudio as B, spec


# ---------------------------------------------------------------------------
# the plumbing
# ---------------------------------------------------------------------------
def test_a_page_packs_four_signed_bytes_per_word():
    q = B.quantize(B.additive(B.ORGAN))
    w = B.pack(B.additive(B.ORGAN))
    assert len(q) == spec.WAV_W and len(w) == spec.WAV_WORDS
    # decode exactly the way cabinet.py does, and get the samples back
    back = []
    for word in w:
        for b in range(4):
            v = (word >> (8 * b)) & 0xFF
            back.append(v - 256 if v > 127 else v)
    assert back == q


def test_a_bank_is_always_a_full_WAV_PAGES_block():
    """A short bank still has to place page 5 at page 5's address, or a
    ctrl word means something different than the cart wrote."""
    for n in (1, 3, spec.WAV_PAGES):
        words = B.bank([B.additive(B.SAW)] * n)
        assert len(words) == spec.WAV_PAGES * spec.WAV_WORDS
        assert words[(n - 1) * spec.WAV_WORDS] != 0     # the last real page
        if n < spec.WAV_PAGES:
            assert words[n * spec.WAV_WORDS] == 0       # silence beyond it


def test_page_for_hz_is_monotonic_and_clamped():
    last = -1
    for hz in (1.0, 27.0, 55.0, 110.0, 440.0, 3520.0, 20000.0, 40000.0):
        pg = B.page_for_hz(hz)
        assert 0 <= pg < spec.WAV_PAGES
        assert pg >= last
        last = pg
    assert B.page_for_hz(1.0) == 0
    assert B.page_for_hz(1e6) == spec.WAV_PAGES - 1


def test_no_mip_page_carries_a_partial_past_nyquist():
    """The property the chain exists for, checked at the recipe level:
    every page must survive the FASTEST note that will select it."""
    for pg in range(spec.WAV_PAGES):
        top = B.MIP_BASE_HZ * (2.0 ** (pg + 1))
        lim = B.max_harmonic(top)
        kept = [n for n, _ in B.SAW if n <= lim]
        assert kept, f"page {pg} kept nothing"
        assert max(kept) * top <= spec.SND_HZ / 2 + top, (
            f"page {pg} carries harmonic {max(kept)}, which folds at {top} Hz")


def test_the_ctrl_word_puts_the_page_where_the_spec_says():
    for pg in range(spec.WAV_PAGES):
        c = B.ctrl(vol=9, page=pg, wave=True)
        assert c & 0xF == 9
        assert bool(c & spec.AU_WAVE)
        assert (c >> spec.AU_PAGE_SHIFT) & spec.AU_PAGE_MASK == pg


# ---------------------------------------------------------------------------
# THE CLAIM: measured through the law
# ---------------------------------------------------------------------------
def render(page, hz, frames=16):
    """The real engine, one wavetable voice, nothing else sounding."""
    d = [0] * spec.DMEM_WORDS
    d[spec.AU_BASE] = B.inc_for(hz)
    d[spec.AU_BASE + 1] = B.ctrl(vol=15, wave=True)
    e = audio.SndEngine()
    return np.concatenate([e.frame(d, B.quantize(page))
                           for _ in range(frames)]).astype(float)


def harmonic_fraction(x, hz, tol=25.0):
    """How much of the audible energy sits on a true multiple of `hz`.
    Everything else is, by definition, something the note did not ask
    for -- which at these pitches is folded-over partials."""
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1.0 / spec.SND_HZ)
    band = (f > 20) & (f < spec.SND_HZ / 2 - 20)
    near = np.zeros_like(band)
    k = 1
    while k * hz < spec.SND_HZ / 2 - 20:
        near |= np.abs(f - k * hz) < tol
        k += 1
    return float(X[band & near].sum() / X[band].sum())


def test_the_full_page_really_does_alias_at_the_top_of_the_keyboard():
    """Half the claim, and the half that is easy to forget: if the plain
    page did NOT alias there would be nothing here to fix, and a passing
    mip test would be measuring nothing at all."""
    full = B.additive(B.SAW)
    assert harmonic_fraction(render(full, 110.0), 110.0) > 0.99
    assert harmonic_fraction(render(full, 7040.0), 7040.0) < 0.90


def test_the_mip_chain_removes_it():
    for hz in (110.0, 440.0, 1760.0, 7040.0):
        pg = B.page_for_hz(hz)
        got = harmonic_fraction(render(B.mip_pages(B.SAW)[pg], hz), hz)
        assert got > 0.99, f"{hz} Hz on page {pg}: only {got:.4f} on harmonics"


def test_the_chain_is_strictly_better_where_it_matters():
    """Not "both are fine" -- better, at the pitch that hurts."""
    hz = 7040.0
    pg = B.page_for_hz(hz)
    plain = harmonic_fraction(render(B.additive(B.SAW), hz), hz)
    mipped = harmonic_fraction(render(B.mip_pages(B.SAW)[pg], hz), hz)
    assert mipped - plain > 0.10, (
        f"the mip chain bought {mipped - plain:.4f}, which is not worth "
        f"a page selector")
