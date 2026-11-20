#!/usr/bin/env python3
"""gen_choir.py -- writes carts/witness/choir.zol: sixteen voices.

Four channels was the last axis where this machine sat behind every
console on the table: PS1 had 24, Saturn 32, N64 about twenty. Four means
a melody, a bass, a drum and one effect -- and the effect steals from the
music every time it fires.

Sixteen now. Channels 0..3 keep their oscillators (two pulses, a
triangle, a noise LFSR); channels 4..15 are VOICES ONLY and read the wave
page always, which is what the sampled field is for. Every cart written
before this wrote 0..3 and is bit-identical.

THE CLAMP, and what this cart does NOT do. Sixteen channels can sum to
245,760, whose >>2 is 61,440 -- outside int16, where four channels'
15,360 never was. So the mix saturates (spec.AU_CLAMP) instead of
wrapping, because a wrap flips the sign of a loud frame and shrieks.
  This cart ramps one voice to sixteen and back and PEAKS AROUND 21,000,
comfortably inside the ceiling. That is not a weak demo, it is the
measurement: sixteen INDEPENDENT voices rarely align, because each phase
accumulator has been running at its own rate and converging their
frequencies does not converge their phases. Forcing them to unison
mid-flight made the peak LOWER, not higher (30,420 -> 23,842), which is
the same fact from the other side.
  So the clamp is a safety net that a real cart seldom touches, and the
place to prove it is a unit test that aligns the phases deliberately --
tests/test_audio_clamp.py -- not a cart contrived to shriek.

The chord is alchemical A = 432 Hz and its just intervals, because that
tuning is the machine's own clock made audible: one cycle of 432 Hz is
exactly 100,000 core clocks (43.2 MHz = 400*360*60*5, the video law's own
arithmetic). Sixteen voices on that root are the clock in sixteen parts.
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

ROOT = 432.0
# just intonation on the root, four octaves of it -- sixteen voices
RATIOS = [1/2, 5/8, 3/4, 9/10, 1, 9/8, 5/4, 4/3,
          3/2, 5/3, 15/8, 2, 9/4, 5/2, 3, 4]


def inc_for(hz):
    """Phase increment: the wave page is WAV_W samples per cycle and the
    phase is 24-bit, so one cycle is 2^24 >> ... -- exactly as the law
    says, integer only."""
    return int(round(hz * (1 << 24) / spec.SND_HZ)) & 0xFFFFFF


def wave_page():
    """A soft organ: fundamental plus a few odd partials, baked here
    rather than synthesised at runtime. Offline is where the quality
    lives -- this is the audio side of the backdrop's bargain."""
    out = []
    for i in range(spec.WAV_W):
        th = 2 * math.pi * i / spec.WAV_W
        v = (math.sin(th) + 0.34 * math.sin(3 * th)
             + 0.16 * math.sin(5 * th) + 0.07 * math.sin(7 * th))
        out.append(max(-127, min(127, int(round(v * 92)))))
    # four signed bytes per word, low byte first (spec.WAV_WORDS)
    words = []
    for w in range(spec.WAV_WORDS):
        b = [out[4 * w + k] & 0xFF for k in range(4)]
        words.append(b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24))
    return words


def main():
    cart = Cart("choir")
    page = cart.data(Table(wave_page()), "organ")
    n = cart.var("n")

    p = cart.program()
    # the page, once: WAV_SRC is read every frame and re-copied, which is
    # cheap and means a cart never has to remember whether it loaded
    p.set(spec.WAV_SRC, int(page))

    # how many voices are sounding: 0..15 and back, ~11 s a lap
    p.load(spec.REG_FRAME).emit("shr 5").push(31).emit("and").store(n)
    hi = p.label("ramp_hi")
    done = p.label("ramp_done")
    p.load(n).push(16).emit("lt", f"jz {hi}")
    p.emit(f"jmp {done}")
    p.mark(hi).push(31).load(n).emit("sub").store(n)
    p.mark(done)

    for c, r in enumerate(RATIOS):
        base = spec.AU_BASE + 2 * c
        p.set(base, inc_for(ROOT * r))
        # ctrl: volume 9, and AU_WAVE for the four that have oscillators
        # (4..15 need no flag -- they are voices unconditionally)
        vol = 13 | (spec.AU_WAVE if c < spec.AU_TONE_CHANNELS else 0)
        if c == 0:
            p.set(base + 1, vol)          # voice 0 always sounds
        else:
            # this voice is on only once the ramp has reached it
            on = p.label("von")
            off = p.label("voff")
            p.load(n).push(c).emit("lt", f"jz {on}")
            p.set(base + 1, 0).emit(f"jmp {off}")
            p.mark(on).set(base + 1, vol)
            p.mark(off)
    p.emit("halt")

    cart.write(HERE / "choir.zol")
    print(cart.report())


if __name__ == "__main__":
    main()
