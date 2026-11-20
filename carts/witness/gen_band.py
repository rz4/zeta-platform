#!/usr/bin/env python3
"""gen_band.py -- writes carts/witness/band.zol: eight instruments, not one.

Sixteen voices sharing a single wave page is a choir. Every channel had
the same timbre and a cart could vary only pitch and volume, which is the
audio side of the exact limit the texture pages closed for the rasterizer
-- "every object in a frame must share one image". It closes the same
way, because it is the same law: a bounded window over a table, and now
the window may sit in one of eight places.

WHAT IS RESIDENT HERE. Eight pages in one bank, all sounding at once:

  0 organ     soft odd partials -- the pad
  1 saw       twelve harmonics falling as 1/n -- the lead
  2 square    odd harmonics only -- hollow
  3 bell      1, 3, 7, 11 -- integer partials spaced to ring
  4 bass      fundamental with a little 2nd -- round and low
  5 pluck     six harmonics, bright, meant to be struck
  6 glass     almost no fundamental: 5th, 7th, 9th -- airy
  7 perc      thirty partials at scrambled phase -- a periodic noise

Channels 0..3 are the four oscillator channels holding a sustained chord
on pages 0..3, proving the bank reaches them too. Channels 4..11 are the
pure voices, one page each, struck by the event list.

AND THE PIECE. Each of the eight struck voices runs on its own PRIME
period -- 1051, 1279, 1601, 2003, 2503, 3001, 3517, 4001 samples -- none
of them a multiple of the 800-sample frame and none a multiple of each
other. So no two voices ever strike together twice, nothing lands on a
frame boundary, and the pattern's true period is the product of eight
primes: about 1.7e26 samples, which is some 10^14 years. The machine
cannot repeat itself before the stars go out.

Both new laws at once, and neither would be enough alone: eight timbres
is an ensemble, sample-exact triggering is a groove, and the two together
are an arrangement. 48 events a frame at the very most, against a cap of
64 -- the arithmetic is in EVENT_BUDGET below, checked at generation.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import carts as _carts                         # noqa: E402
_carts.on_path()                 # sibling generators, wherever they live

from zeta import spec                                    # noqa: E402
from zeta.forge import Cart, Table                       # noqa: E402

ROOT = 432.0                     # the clock made audible (see gen_choir)

# ---- the eight pages: (partial, amplitude) pairs --------------------------
TIMBRE = [
    [(1, 1.0), (3, .34), (5, .16), (7, .07)],                      # 0 organ
    [(n, 1.0 / n) for n in range(1, 13)],                          # 1 saw
    [(n, 1.0 / n) for n in range(1, 13, 2)],                       # 2 square
    [(1, 1.0), (3, .50), (7, .35), (11, .25)],                     # 3 bell
    [(1, 1.0), (2, .25), (3, .10)],                                # 4 bass
    [(1, 1.0), (2, .70), (3, .50), (4, .35), (5, .25), (6, .18)],  # 5 pluck
    [(1, .15), (5, .80), (7, .60), (9, .40)],                      # 6 glass
    [(n, .45) for n in range(1, 31)],                              # 7 perc
]
# page 7 only becomes a burst rather than a spike once its partials stop
# agreeing on where zero is; the phase is a closed form, not a random
# number, so the cart is byte-identical every time it is generated
PHASE = [lambda n: 0.0] * 7 + [lambda n: (n * n * 0.37) % 1.0]

# ---- the struck voices: channel 4..11, one page each ----------------------
STRUCK = [
    # page  ratio to ROOT     period (samples, prime)
    (4,     1 / 2,            4001),      # bass, slowest
    (5,     3 / 2,            1051),      # pluck, fastest
    (3,     2.0,              1601),      # bell
    (6,     3.0,              2503),      # glass
    (1,     9 / 8,            1279),      # saw
    (5,     5 / 3,            2003),      # pluck again, other pitch
    (3,     5 / 2,            3001),      # bell, high
    (7,     1.0,              3517),      # perc
]
DECAY = [15, 11, 8, 5, 3, 0]     # six steps, ending in silence
SPACING = 61                     # samples between steps (prime)
EVENT_BUDGET = len(STRUCK) * len(DECAY)          # 8 * 6 = 48

# ---- the sustained chord on the four oscillator channels ------------------
PAD = [(0, 1.0, 5), (1, 3 / 2, 4), (2, 5 / 4, 4), (3, 2.0, 3)]  # pg, ratio, vol


def inc_for(hz):
    return int(round(hz * (1 << 24) / spec.SND_HZ)) & 0xFFFFFF


def page_words(partials, phase):
    """One page: WAV_W signed bytes, four to a word, low byte first."""
    raw = []
    for i in range(spec.WAV_W):
        th = 2 * math.pi * i / spec.WAV_W
        v = sum(a * math.sin(n * th + 2 * math.pi * phase(n))
                for n, a in partials)
        raw.append(v)
    peak = max(abs(v) for v in raw) or 1.0
    out = [max(-127, min(127, int(round(v * 112 / peak)))) for v in raw]
    words = []
    for w in range(spec.WAV_WORDS):
        b = [out[4 * w + k] & 0xFF for k in range(4)]
        words.append(b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24))
    return words


def main():
    assert EVENT_BUDGET <= spec.AU_EV_MAX, (
        f"{len(STRUCK)} voices x {len(DECAY)} steps = {EVENT_BUDGET} events, "
        f"over the {spec.AU_EV_MAX} the frame can carry")
    assert len(TIMBRE) == spec.WAV_PAGES

    cart = Cart("band")
    # THE BANK: eight pages, consecutive, because WAV_SRC names the bank
    # and bits 10:8 of a ctrl word index into it
    bank = []
    for pg in range(spec.WAV_PAGES):
        bank += page_words(TIMBRE[pg], PHASE[pg])
    base = cart.data(Table(bank), "bank")

    pos = [cart.data(Table([(i * 977) % p]), f"pos{i}")
           for i, (_, _, p) in enumerate(STRUCK)]
    nev = cart.var("nev")
    evp = cart.var("evp")
    hit = cart.var("hit")

    p = cart.program()
    p.set(spec.WAV_SRC, int(base))
    p.set(nev, 0)
    p.set(evp, spec.AU_EV_BASE + 1)

    # the pad: four oscillator channels turned into wavetable voices, each
    # on its own page, volume straight from the register (no envelope)
    for ch, pg, ratio, vol in [(c, g, r, v) for c, (g, r, v) in enumerate(PAD)]:
        p.set(spec.AU_BASE + 2 * ch, inc_for(ROOT * ratio))
        p.set(spec.AU_BASE + 2 * ch + 1,
              vol | spec.AU_WAVE | (pg << spec.AU_PAGE_SHIFT))

    # the struck voices
    for i, (pg, ratio, period) in enumerate(STRUCK):
        ch = spec.AU_TONE_CHANNELS + i
        p.set(spec.AU_BASE + 2 * ch, inc_for(ROOT * ratio))
        # the register ctrl carries the PAGE and nothing else: volume is
        # the event list's business, and the page is not something an
        # event may touch (spec: a page is a load-time property)
        p.set(spec.AU_BASE + 2 * ch + 1, pg << spec.AU_PAGE_SHIFT)

        # count down to this voice's next strike, exactly as pulse.zol
        p.addi(int(pos[i]), -spec.SAMPLES_PER_FRAME)
        skip = p.label("nohit")
        p.load(int(pos[i])).push(0).emit("lt", f"jz {skip}")
        p.push(0).load(int(pos[i])).emit("sub").store(hit)
        p.addi(int(pos[i]), period)

        for k, vol in enumerate(DECAY):
            past = p.label("past")
            p.load(hit).push(k * SPACING).emit("add")
            p.push(spec.SAMPLES_PER_FRAME).emit("lt", f"jz {past}")
            p.load(hit).push(k * SPACING).emit("add")
            p.push((ch << spec.AU_EV_CH_SHIFT) | spec.AU_EV_CTRL_BIT)
            p.emit("or")
            p.load(evp).emit("storei")
            p.addi(evp, 1)
            p.push(vol).load(evp).emit("storei")
            p.addi(evp, 1)
            p.addi(nev, 1)
            p.mark(past)
        p.mark(skip)

    p.load(nev).store(spec.AU_EV_BASE)
    p.emit("halt")

    cart.write(HERE / "band.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
