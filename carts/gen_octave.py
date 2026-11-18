#!/usr/bin/env python3
"""gen_octave.py -- writes carts/octave.zol: mip-maps, for sound.

A wave page is a bounded window walked by a phase accumulator. So is a
texture. Walk either one faster than its detail and the detail folds back
as noise -- shimmer on screen, ALIASING in sound -- and the answer is the
same in both places: keep several versions of the table, each holding
only the detail its rate can carry, and choose by rate.

The rasterizer has done this since the crown. This cart does it at 48 kHz.

WHAT YOU HEAR. A sawtooth climbs eight octaves, from 27.5 Hz to 7,040 Hz,
over about four seconds. Then it climbs again. The two sweeps are not the
same:

  GREEN  the voice reads the mip page for its pitch (bakeaudio.page_for_hz)
  RED    the voice reads page 0 always -- every harmonic, at every pitch

Page 0 is not a worse table. It is the RIGHT table for 27.5 Hz and holds
all 128 harmonics a 256-sample page can carry. Played at 7 kHz those
harmonics land at 14, 21, 28, 35 kHz... and everything past 24 kHz folds
back down to frequencies that are multiples of nothing. Measured through
the law (tests/test_bakeaudio.py): at 7,040 Hz the full page puts 18.4%
of its audible energy into inharmonic garbage, and the mip page puts
0.01%. The red sweep buzzes and goes sour at the top. The green one
stays a sawtooth all the way up.

That sourness is not hypothetical period detail -- it is why sampled
instruments of the era were avoided in their top octave. The fix costs
this machine NOTHING at runtime: the eight pages were already resident,
and all that changed is what was baked into them, offline, where the
arithmetic is free.

The bar across the bottom shows which of the eight pages is being read.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import bakeaudio as B, spec                    # noqa: E402
from zeta.forge import Cart, Table                       # noqa: E402

STEPS = 128                 # sweep resolution
FRAMES_PER_STEP = 2         # 256 frames a sweep, ~4.3 s
LOW_HZ = B.MIP_BASE_HZ + 0.5   # 27.5: the bottom of a piano, page 0
OCTAVES = 8
VOICE = spec.AU_TONE_CHANNELS  # channel 4: a pure voice, always a wavetable
VOL = 12

BAR_Y0, BAR_Y1 = 250, 274      # the page indicator
SLOT = spec.W // spec.WAV_PAGES


def color(p, addr, rgb, alpha=16):
    """rgb | alpha<<24 exceeds the 24-bit immediate, so it is assembled on
    the stack instead of asked for as a constant."""
    p.push(alpha).emit("shl 24").push(rgb).emit("or").store(addr)


def main():
    cart = Cart("octave")

    # THE BANK: one band-limited sawtooth per octave. Page 0 keeps all
    # 128 harmonics; page 7 keeps the three that survive up there.
    pages = B.mip_pages(B.SAW, base_hz=B.MIP_BASE_HZ)
    base = cart.data(Table(B.bank(pages)), "sawbank")

    hz = [LOW_HZ * (2.0 ** (OCTAVES * i / STEPS)) for i in range(STEPS)]
    incs = cart.data(Table([B.inc_for(f) for f in hz]), "incs")
    pgs = cart.data(Table([B.page_for_hz(f) for f in hz]), "pages")

    i = cart.var("i")
    pg = cart.var("pg")
    x0 = cart.var("x0")

    p = cart.program()
    p.set(spec.WAV_SRC, int(base))

    # i = (frame >> 1) & 127 -- where in the sweep we are
    p.load(spec.REG_FRAME).emit("shr 1").push(STEPS - 1).emit("and").store(i)

    # the pitch, from the table
    p.load(i).push(int(incs)).emit("add").emit("loadi")
    p.store(spec.AU_BASE + 2 * VOICE)

    # the page, from the table -- unless this is the RED sweep, which is
    # the whole comparison: same pitch, same voice, page 0 always
    p.load(i).push(int(pgs)).emit("add").emit("loadi").store(pg)
    plain = p.label("plain")
    done = p.label("mode_done")
    p.load(spec.REG_FRAME).emit("shr 8").push(1).emit("and")
    p.emit(f"jz {plain}")
    p.set(pg, 0)                       # RED: no mip chain
    p.mark(plain)
    p.mark(done)

    # ctrl: volume, and the page in bits 10:8
    p.load(pg).emit("shl 8").push(VOL).emit("or")
    p.store(spec.AU_BASE + 2 * VOICE + 1)

    # ---- the picture: which page is sounding ---------------------------
    # three rectangles (CO_MAX is 4): a dark bed, the lit slot, and a
    # mode band whose colour says which sweep this is
    p.set(spec.CO_BASE, 3)
    p.set(spec.CO_BASE + 1, 0 | (spec.W - 1) << 10)
    p.set(spec.CO_BASE + 2, BAR_Y0 | BAR_Y1 << 10)
    color(p, spec.CO_BASE + 3, 0x101010)

    # the lit slot: x0 = page * SLOT
    p.load(pg).push(SLOT).emit("mul").store(x0)
    p.load(x0).push(SLOT - 3).emit("add").emit("shl 10").load(x0).emit("or")
    p.store(spec.CO_BASE + 4)
    p.set(spec.CO_BASE + 5, (BAR_Y0 + 3) | (BAR_Y1 - 3) << 10)
    color(p, spec.CO_BASE + 6, 0xF0F0F0)

    # the mode band, in the colours of the opus
    p.set(spec.CO_BASE + 7, 0 | (spec.W - 1) << 10)
    p.set(spec.CO_BASE + 8, (BAR_Y1 + 4) | (BAR_Y1 + 10) << 10)
    green = p.label("green")
    tail = p.label("tail")
    p.load(spec.REG_FRAME).emit("shr 8").push(1).emit("and")
    p.emit(f"jz {green}")
    color(p, spec.CO_BASE + 9, 0xD02020)               # RED: page 0 always
    p.emit(f"jmp {tail}")
    p.mark(green)
    color(p, spec.CO_BASE + 9, 0x20C040)               # GREEN: mip chain
    p.mark(tail)
    p.emit("halt")

    cart.write(HERE / "octave.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
