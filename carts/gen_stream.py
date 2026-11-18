#!/usr/bin/env python3
"""gen_stream.py -- writes carts/stream.zol: a recording, played back.

    python3 carts/gen_stream.py [seconds]      (default: the whole file)

The machine has no PCM channel. It has sixteen phase accumulators walking
256-sample tables, and this plays a record on them anyway.

HOW. The loader refills a voice's table once a frame, so a voice can
consume exactly WAV_W new samples per frame -- 256 * 60 = 15,360 Hz, the
page size times the frame rate, which is the ceiling for recorded sound
on this machine as built. Each frame the mover pages the next 64 words of
the song out of the cart's CRAM segment and into the table's DMEM home,
and the loader carries them the rest of the way. The song is 824,640
words, which is a smaller cart than the .mp3 it came from.

WHY IT NEEDS THE EVENT LIST. To walk the page exactly once a frame the
phase must advance 2^24 over 800 ticks, and 2^24/800 = 20,971.52 is not
an integer. With a single increment the phase wraps INSIDE the frame and
replays the frame's first sample at its end -- a click at 60 Hz, and one
that grows: 1 to 11 ticks wide over a 400-frame test, a third of a frame
by the end of this song. A short test would have blessed it.
  So the cart sends ONE EVENT per voice per frame (zeta/bakepcm.py's
inc_law): 385 ticks at 20,971, then 415 at 20,972, which totals exactly
2^24 - 1. The phase never wraps mid-frame and creeps back one part in
65,536 of a sample per frame -- 0.2 samples across the whole track.
Measured against the same 8-bit stream through an ideal zero-order hold:
24.4 dB for the hold, 25.2 dB for this.

EIGHT VOICES IN UNISON, and not for thickness. One voice at full volume
reaches 127*15*8 >> 2 = 3,810 of int16's 32,767 -- the mix headroom is
sized for sixteen channels, so any one of them is quiet by construction.
Eight voices fed the identical page with identical increments hold
identical phases, so they sum exactly 8x to 30,480: full scale, no
clipping, no filter. The channel count IS the volume control.

On screen: a progress bar, and a level meter reading the page the mover
delivered last frame.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import bakepcm as P, spec                      # noqa: E402
from zeta.forge import Cart, Table                       # noqa: E402

SRC = HERE.parent / "assets" / "set_it_off.mp3"
VOICES = list(range(spec.AU_TONE_CHANNELS,               # 4..11: the pure
                    spec.AU_TONE_CHANNELS + 8))          # voices, no flags
VOL = 15
TAPS = (0, 16, 32, 48)          # where the level meter samples the page

BAR_Y0, BAR_Y1 = 262, 272       # progress
LVL_Y0, LVL_Y1 = 246, 256       # level


def color(p, addr, rgb, alpha=16):
    """rgb | alpha<<24 is past the 24-bit immediate, so it is built on
    the stack rather than asked for as a constant."""
    p.push(alpha).emit("shl 24").push(rgb).emit("or").store(addr)


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else None
    words = P.stream(SRC, seconds=seconds)
    print("  ", P.report(words))

    inc_a, inc_b, split = P.inc_law()
    total = len(words)
    # progress bar scale: no divide in the VM, but mulq is (a*b)>>16, so
    # a reciprocal multiply does it. Rounded UP and clamped, so the bar
    # actually reaches the right-hand edge instead of stopping short.
    kx = -(-(spec.W * 65536) // total)

    cart = Cart("stream")
    song = cart.cram(Table(words), "song")
    page = cart.data(Table([0] * spec.WAV_WORDS), "page")
    ptr = cart.var("ptr")
    lvl = cart.var("lvl")
    tmp = cart.var("tmp")
    xw = cart.var("xw")

    p = cart.program()
    p.set(spec.WAV_SRC, int(page))

    # ---- the mover: this frame's 256 samples, CRAM -> the page --------
    # DMA lands after the VM halts and BEFORE the loader reads DMEM, so
    # the samples paged in here are the ones this frame will sound.
    p.load(ptr).push(int(song)).emit("add").store(spec.DMA_SRC)
    p.set(spec.DMA_DST, int(page))
    p.set(spec.DMA_LEN, spec.WAV_WORDS)
    p.set(spec.DMA_GO, 1)

    # ---- the level meter, before ptr moves ---------------------------
    # reads the page the mover delivered LAST frame -- which is what is
    # in DMEM while the program runs, and is honest about it
    p.set(lvl, 0)
    for w in TAPS:
        p.load(int(page) + w).push(0xFF).emit("and").store(tmp)
        neg, adone = p.label("neg"), p.label("adone")
        p.load(tmp).push(128).emit("lt", f"jz {neg}")     # signed byte ->
        p.emit(f"jmp {adone}")                            # magnitude
        p.mark(neg).push(256).load(tmp).emit("sub").store(tmp)
        p.mark(adone)
        keep = p.label("keep")
        p.load(lvl).load(tmp).emit("lt", f"jz {keep}")    # lvl = max(...)
        p.load(tmp).store(lvl)
        p.mark(keep)

    # ---- advance, and loop at the end --------------------------------
    p.addi(ptr, spec.WAV_WORDS)
    rewound = p.label("rewound")
    p.push(total - 1).load(ptr).emit("lt", f"jz {rewound}")
    p.set(ptr, 0)
    p.mark(rewound)

    # ---- the voices --------------------------------------------------
    for ch in VOICES:
        p.set(spec.AU_BASE + 2 * ch, inc_a)
        p.set(spec.AU_BASE + 2 * ch + 1, VOL)   # page 0; 4..11 are voices
                                                # unconditionally
    # one event each: switch to the second increment at the split
    p.set(spec.AU_EV_BASE, len(VOICES))
    for i, ch in enumerate(VOICES):
        p.set(spec.AU_EV_BASE + 1 + 2 * i,
              split | (ch << spec.AU_EV_CH_SHIFT))       # inc event
        p.set(spec.AU_EV_BASE + 2 + 2 * i, inc_b)

    # ---- the picture -------------------------------------------------
    p.set(spec.CO_BASE, 3)
    p.set(spec.CO_BASE + 1, 0 | (spec.W - 1) << 10)      # the bed
    p.set(spec.CO_BASE + 2, BAR_Y0 | BAR_Y1 << 10)
    color(p, spec.CO_BASE + 3, 0x101010)

    p.load(ptr).push(kx).emit("mulq").store(xw)          # progress fill
    clamped = p.label("clamped")
    p.load(xw).push(spec.W - 1).emit("lt", f"jz {clamped}")
    p.emit(f"jmp {clamped}_ok")
    p.mark(clamped).set(xw, spec.W - 1)
    p.mark(f"{clamped}_ok")
    p.load(xw).emit("shl 10").store(spec.CO_BASE + 4)    # x0 = 0
    p.set(spec.CO_BASE + 5, (BAR_Y0 + 2) | (BAR_Y1 - 2) << 10)
    color(p, spec.CO_BASE + 6, 0x20C040)

    # the level meter, centred: half-width is the peak byte, 0..128
    p.push(spec.W // 2).load(lvl).emit("sub").store(tmp)
    p.push(spec.W // 2).load(lvl).emit("add").emit("shl 10")
    p.load(tmp).emit("or").store(spec.CO_BASE + 7)
    p.set(spec.CO_BASE + 8, LVL_Y0 | LVL_Y1 << 10)
    color(p, spec.CO_BASE + 9, 0xE0E0E0)
    p.emit("halt")

    cart.write(HERE / "stream.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
