"""bakeaudio.py -- the offline path: quality baked before the cart ships.

The console synthesizes with integers, sixteen phase accumulators and a
shift. That is the whole runtime cost and it is not going to change. But
WHAT those accumulators walk is decided here, in floating point, on a
workstation, with as much arithmetic as anyone cares to spend -- and the
machine pays nothing for it, because a table is a table.

This is the same bargain the backdrop struck for pictures and the mip
chain struck for textures, and it is the reason a 43.2 MHz console can
sound like something that costs more.

  pack        float samples -> the packed signed bytes a page holds
  additive    partials -> one cycle of a waveform
  bank        pages -> the consecutive block WAV_SRC points at

---- MIP-MAPS FOR AUDIO -------------------------------------------------

The interesting one. A wave page is a bounded window walked by a phase
accumulator -- the field law, at 48 kHz instead of 43.2 MHz. The
rasterizer's version of that primitive has a known failure: walk the
table faster than its detail and the detail folds back as noise. On
screen that is shimmer, and the answer is a mip chain. In sound it is
ALIASING, and it is the same answer.

A 256-sample page can hold 128 harmonics. Play it at 3,456 Hz and every
harmonic above the 6th is past Nyquist, so it folds down and lands at
frequencies that are not multiples of anything -- inharmonic, buzzing,
and unmistakably cheap. This is audible on real hardware of the period:
sampled instruments went sour in their top octave and everybody simply
avoided writing high parts.

So bake one page per octave, each holding only the harmonics that octave
can carry: mip_pages() returns WAV_PAGES of them and page_for_hz() says
which to use. The cart picks a page when it picks a pitch -- both are
frame-rate decisions, which is exactly what the page selector is
(spec: a page is a load-time property) -- and the top octave comes out
clean, because the partials that would have folded were never there.

The cost on silicon is zero. The pages were already resident; this only
decides what to put in them.
"""
from __future__ import annotations

import math

from . import spec

#: the lowest note the mip chain is baked for -- an octave below the
#: 27.5 Hz bottom of a piano, so a whole keyboard sits inside the chain
MIP_BASE_HZ = 27.0


def quantize(samples, peak: int = 112) -> list[int]:
    """WAV_W floats -> the WAV_W signed bytes the machine actually walks.
    Normalized to `peak` so a quiet recipe and a loud one arrive at the
    mixer with the same authority; the volume field is where loudness is
    decided, not the table."""
    if len(samples) != spec.WAV_W:
        raise ValueError(f"a page is {spec.WAV_W} samples, got {len(samples)}")
    top = max(abs(float(v)) for v in samples) or 1.0
    return [max(-127, min(127, int(round(float(v) * peak / top))))
            for v in samples]


def pack(samples, peak: int = 112) -> list[int]:
    """WAV_W floats -> WAV_WORDS words, four signed bytes each, low byte
    first: the form a cart's data table takes."""
    q = quantize(samples, peak)
    return [q[4 * w] & 0xFF | (q[4 * w + 1] & 0xFF) << 8
            | (q[4 * w + 2] & 0xFF) << 16 | (q[4 * w + 3] & 0xFF) << 24
            for w in range(spec.WAV_WORDS)]


def additive(partials, phase=None) -> list[float]:
    """One cycle from (harmonic, amplitude) pairs. `phase(n)` gives each
    partial a starting phase in turns -- the difference between a spike
    and a burst, and the only thing that makes a periodic table sound
    like noise."""
    ph = phase or (lambda n: 0.0)
    return [sum(a * math.sin(n * (2 * math.pi * i / spec.WAV_W)
                             + 2 * math.pi * ph(n))
                for n, a in partials)
            for i in range(spec.WAV_W)]


def max_harmonic(hz: float) -> int:
    """The highest partial that still fits below Nyquist at this pitch.
    Above it a partial does not disappear -- it folds down and lands
    somewhere inharmonic, which is the whole problem."""
    if hz <= 0:
        return spec.WAV_W // 2
    return max(1, min(spec.WAV_W // 2, int((spec.SND_HZ / 2) / hz)))


def page_for_hz(hz: float, base_hz: float = MIP_BASE_HZ) -> int:
    """Which page of a mip bank a note at `hz` should walk. One page per
    octave upward from base_hz, clamped at both ends -- the audio twin
    of choosing a mip level by how fast the walk crosses the texels."""
    if hz <= base_hz:
        return 0
    return max(0, min(spec.WAV_PAGES - 1,
                      int(math.log(hz / base_hz, 2.0))))


def mip_pages(partials, base_hz: float = MIP_BASE_HZ, phase=None):
    """WAV_PAGES float pages of one instrument, each band-limited to the
    octave that will play it.

    The top of each octave sets the limit, not the bottom: a page is
    chosen for the whole octave, so it must stay clean at the fastest
    walk that will use it."""
    out = []
    for pg in range(spec.WAV_PAGES):
        top = base_hz * (2.0 ** (pg + 1))       # fastest note on this page
        lim = max_harmonic(top)
        kept = [(n, a) for n, a in partials if n <= lim] or [(1, 1.0)]
        out.append(additive(kept, phase))
    return out


def bank(pages, peak: int = 112) -> list[int]:
    """Pages -> the consecutive DMEM block WAV_SRC names. Pages may be
    float lists or already-packed word lists; short banks are padded with
    silence so page indices always mean what the cart wrote."""
    if len(pages) > spec.WAV_PAGES:
        raise ValueError(f"a bank holds {spec.WAV_PAGES} pages, "
                         f"got {len(pages)}")
    words: list[int] = []
    for p in pages:
        if len(p) == spec.WAV_WORDS and all(isinstance(v, int) for v in p):
            words += list(p)                    # already packed
        else:
            words += pack(p, peak)
    words += [0] * ((spec.WAV_PAGES - len(pages)) * spec.WAV_WORDS)
    assert len(words) == spec.WAV_PAGES * spec.WAV_WORDS
    return words


def inc_for(hz: float) -> int:
    """The phase increment a channel needs to sound at `hz`. One place,
    because every generator was rounding it by hand."""
    return int(round(hz * (1 << 24) / spec.SND_HZ)) & 0xFFFFFF


def ctrl(vol: int = 0, page: int = 0, wave: bool = False,
         duty: int = 0) -> int:
    """A channel's register ctrl word. Assembled here so a cart never has
    to remember which bits the page lives in."""
    return ((vol & 0xF) | ((duty & 3) << 4)
            | (spec.AU_WAVE if wave else 0)
            | ((page & spec.AU_PAGE_MASK) << spec.AU_PAGE_SHIFT))


# ---- the classic recipes, so a cart states an instrument, not a sum ------
SAW = [(n, 1.0 / n) for n in range(1, spec.WAV_W // 2 + 1)]
SQUARE = [(n, 1.0 / n) for n in range(1, spec.WAV_W // 2 + 1, 2)]
TRIANGLE = [(n, (1.0 / (n * n)) * (1 if (n // 2) % 2 == 0 else -1))
            for n in range(1, spec.WAV_W // 2 + 1, 2)]
ORGAN = [(1, 1.0), (3, .34), (5, .16), (7, .07)]
BELL = [(1, 1.0), (3, .50), (7, .35), (11, .25)]
PLUCK = [(n, 1.0 / (n * n)) for n in range(1, 17)]
