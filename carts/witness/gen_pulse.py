#!/usr/bin/env python3
"""gen_pulse.py -- writes carts/witness/pulse.zol: a beat that ignores the frame.

The thing no console of either generation could do.

Every machine on the comparison table controls its audio at the FRAME
rate. PS1's SPU had hardware ADSR precisely because 60 Hz control over a
44.1 kHz engine cannot express an attack; N64 burned CPU in software for
the same reason. And on all of them a note begins on a frame boundary,
because that is the only instant a program exists.

Zeta sends a TIMELINE instead (spec.AU_EV_BASE). The cart still runs once
a frame -- the frame contract is untouched -- but what it writes is a list
of (sample offset, channel, value) events, and the engine applies each one
at its exact sample before synthesizing it. 800 samples a frame, exactly,
bit-identical on the law and on glass forever.

So this cart puts its hits on a period of 1,003 SAMPLES. Not 800, not a
divisor of it, not anything the frame grid can express: a 47.86 Hz pulse
that lands on a different sample offset every single frame and never
repeats against the video clock. Each hit is a hard attack and an
eight-step decay, all inside one frame, which at 60 Hz control would be a
single instantaneous click.

Listen for what is NOT there: no flam, no jitter, no note landing early or
late because the frame rounded it. The groove is sample-exact because the
machine is sample-exact, and that is a property no console shipped.
"""
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

PERIOD = 1003            # samples between hits -- deliberately coprime
                         # with the 800-sample frame
DECAY = [15, 12, 9, 7, 5, 3, 2, 0]      # volume, one step per SPACING
SPACING = 46             # samples between decay steps
VOICES = 3               # three drums at different pitches
PITCH = [110.0, 220.0, 73.0]
OFFSET = [0, 3011, 5017]   # each voice's own phase in the pattern


def inc_for(hz):
    return int(round(hz * (1 << 24) / spec.SND_HZ)) & 0xFFFFFF


def click_page():
    """A short bright waveform -- a struck body rather than a tone. The
    page is baked here, offline, which is where quality is free."""
    import math
    out = []
    for i in range(spec.WAV_W):
        th = 2 * math.pi * i / spec.WAV_W
        v = (math.sin(th) + 0.6 * math.sin(2 * th) + 0.45 * math.sin(3 * th)
             + 0.3 * math.sin(5 * th) + 0.2 * math.sin(9 * th))
        out.append(max(-127, min(127, int(round(v * 46)))))
    words = []
    for w in range(spec.WAV_WORDS):
        b = [out[4 * w + k] & 0xFF for k in range(4)]
        words.append(b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24))
    return words


def main():
    cart = Cart("pulse")
    page = cart.data(Table(click_page()), "click")

    pos = [cart.data(Table([OFFSET[v]]), f"pos{v}") for v in range(VOICES)]
    nev = cart.var("nev")
    evp = cart.var("evp")
    hit = cart.var("hit")

    p = cart.program()
    p.set(spec.WAV_SRC, int(page))
    p.set(nev, 0)
    p.set(evp, spec.AU_EV_BASE + 1)

    for v in range(VOICES):
        # pitch is constant; only the envelope is automated
        p.set(spec.AU_BASE + 2 * v, inc_for(PITCH[v]))

        # pos counts samples until this voice's next hit. Advance it by a
        # frame; if it went past, the hit falls THIS frame, at exactly
        # (800 - pos) samples in -- which is a different offset each time
        # because PERIOD and 800 share no factor.
        p.addi(int(pos[v]), -spec.SAMPLES_PER_FRAME)
        skip = p.label("nohit")
        p.load(int(pos[v])).push(0).emit("lt", f"jz {skip}")

        # hit offset within the frame = -pos  (pos is negative here)
        p.push(0).load(int(pos[v])).emit("sub").store(hit)
        p.addi(int(pos[v]), PERIOD)

        for k, vol in enumerate(DECAY):
            past = p.label("past")
            # offset = hit + k*SPACING, emitted only if inside the frame
            p.load(hit).push(k * SPACING).emit("add")
            p.push(spec.SAMPLES_PER_FRAME).emit("lt", f"jz {past}")
            # w0 = offset | channel<<10 | CTRL
            p.load(hit).push(k * SPACING).emit("add")
            p.push((v << spec.AU_EV_CH_SHIFT) | spec.AU_EV_CTRL_BIT)
            p.emit("or")
            p.load(evp).emit("storei")
            p.addi(evp, 1)
            # w1 = the volume (channels 0..2 are tone channels: AU_WAVE
            # makes them read the page instead of their oscillator)
            p.push(vol | spec.AU_WAVE).load(evp).emit("storei")
            p.addi(evp, 1)
            p.addi(nev, 1)
            p.mark(past)
        p.mark(skip)

    p.load(nev).store(spec.AU_EV_BASE)
    p.emit("halt")

    cart.write(HERE / "pulse.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
