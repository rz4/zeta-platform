"""bakepcm.py -- recorded sound, streamed through the wavetable path.

The machine has no PCM channel. It has sixteen phase accumulators walking
256-sample tables, and that is all it has ever had. This module streams
a recording through them anyway, and the arithmetic that makes it work is
worth stating precisely because it very nearly does not.

THE RATE. A voice's table is WAV_W samples and the loader refills it once
a frame, so a voice can consume exactly WAV_W new samples per frame and
not one more:

    PCM_HZ = WAV_W * FPS = 256 * 60 = 15,360 Hz

That is the ceiling for recorded audio on this machine as built. It is
not a tuning choice; it is the page size times the frame rate.

THE PROBLEM, AND WHY THE OBVIOUS VERSION BUZZES. To walk the page once
per frame the phase must advance exactly 2^24 over SAMPLES_PER_FRAME
ticks, and 2^24 / 800 = 20,971.52 IS NOT AN INTEGER. Round it up and the
phase overshoots by 384 a frame, so it wraps just BEFORE the frame ends
and replays the frame's first sample at its end. Round it down and it
wraps just after the next frame begins. Either way there is a
discontinuity once per frame -- at 60 Hz, which is precisely where the
ear is least willing to forgive one.
  Worse, it grows. Measured over 400 frames the wrap sat 1 to 11 ticks
from the frame edge; extrapolated across this file's 12,884 frames it
reaches 236 ticks, a third of the frame. A single increment cannot
stream a song, and a short test would have said it could.

THE FIX IS THE EVENT LIST. inc is a value an event may re-aim at any
sample, so use TWO of them in one frame and choose the split so the total
advance is exact:

    n_a * inc_a + n_b * (inc_a + 1) = 2^24 - 1      (see inc_law below)

For 800 samples that is 385 ticks at 20,971 then 415 at 20,972 -- ONE
event per voice per frame. The phase then lands one unit short of a full
pass every frame, so it never wraps inside a frame and creeps back by
1/65536 of a sample per frame: 0.2 samples across this entire track.
  Measured against the same 8-bit stream reconstructed by an ideal
zero-order hold: 24.4 dB for the hold, 25.2 dB for this. The machine is
not approximating the ideal here. It is slightly beating it, because a
phase accumulator distributes its hold lengths better than floor() does.

WHAT IT COSTS. 8-bit samples at 15,360 Hz is 3,840 words a second, so
this file's 3 minutes 35 is 824,594 words -- a CRAM segment smaller than
the .mp3 it came from, and about 84% of the 983,056 the segment can
address. Four minutes 16 is the ceiling. Above that a cart wants the SD
card, which the mover already reaches.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import spec

#: what a page-per-frame voice can consume: the page size times the frame
#: rate, and nothing about it is adjustable from up here
PCM_HZ = spec.WAV_W * spec.FPS


def inc_law(samples_per_frame: int = spec.SAMPLES_PER_FRAME):
    """(inc_a, inc_b, split) -- the two increments and where to switch.

    Derived, never written down: `2**24 // spf` is only 20,971 because
    spf is 800 today, and a constant that is right for one value of a
    parameter is a latent bug in the shape this project keeps finding.

    The target is 2^24 - 1 rather than 2^24 so the phase ends the frame
    at the LAST sample rather than wrapping onto the first. One unit a
    frame is a 1/65536-sample creep; a wrap is a click."""
    target = (1 << 24) - 1
    inc_a = target // samples_per_frame
    n_b = target - samples_per_frame * inc_a        # how many need the +1
    return inc_a, inc_a + 1, samples_per_frame - n_b


def decode(path, seconds: float | None = None, start: float = 0.0,
           gain: float = 1.0) -> bytes:
    """Any audio file -> signed 8-bit mono at PCM_HZ, via ffmpeg.

    ffmpeg's resampler does the band-limiting, which matters for the same
    reason the mip chain does (bakeaudio.mip_pages): everything above
    PCM_HZ/2 does not vanish, it folds down and lands somewhere
    inharmonic."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("bakepcm needs ffmpeg on PATH to decode")
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if start:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(path)]
    if seconds:
        cmd += ["-t", str(seconds)]
    if gain != 1.0:
        cmd += ["-af", f"volume={gain}"]
    cmd += ["-ac", "1", "-ar", str(PCM_HZ), "-f", "s8", "-acodec", "pcm_s8",
            "-"]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    if not out:
        raise RuntimeError(f"ffmpeg decoded nothing from {path}")
    return out


def pack(samples: bytes) -> list[int]:
    """Signed bytes -> words, four per word low byte first: the exact
    layout a wave page already uses, so the loader needs no new idea.

    Padded to a whole number of FRAMES, not merely of words -- the
    stream is consumed a page per frame and a partial final page would
    have the voice walk into whatever followed it."""
    per = spec.WAV_WORDS * 4
    n = (len(samples) + per - 1) // per * per
    b = bytes(samples) + b"\0" * (n - len(samples))
    return [b[i] | b[i + 1] << 8 | b[i + 2] << 16 | b[i + 3] << 24
            for i in range(0, n, 4)]


def stream(path, seconds=None, start=0.0, gain=1.0) -> list[int]:
    """The whole path: a file on disk to the words a cart carries."""
    return pack(decode(path, seconds, start, gain))


def report(words: list[int]) -> str:
    frames = len(words) // spec.WAV_WORDS
    ceil = (spec.CRAM_WORDS - spec.CRAM_CART_BASE // 2)
    return (f"{len(words):,} words = {frames:,} frames = "
            f"{frames / spec.FPS:.1f} s at {PCM_HZ:,} Hz 8-bit mono "
            f"({100 * len(words) / ceil:.0f}% of the CRAM segment)")
