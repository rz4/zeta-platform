"""audio.py -- the Zeta sound engine, executable spec of silicon/zsnd.v.

One call per frame: latch the 8 register words at AU_BASE, synthesize
exactly SAMPLES_PER_FRAME 48 kHz samples per spec.py's integer recipe.
Channel phase and the noise LFSR persist across frames -- they are machine
state, like DMEM, and the cross holds the silicon's sample stream to this
one bit for bit.
"""
from __future__ import annotations

import numpy as np

from . import spec


class SndEngine:
    def __init__(self):
        self.phase = [0] * spec.AU_CHANNELS
        self.lfsr = 1

    def frame(self, dmem: list[int], wav=None) -> np.ndarray:
        """wav: the wave tables, the sampled field at 48 kHz. Either ONE
        page of WAV_W signed bytes shared by every channel, or a list of
        AU_CHANNELS such pages -- one per voice, already resolved from
        the bank by the cabinet (spec.WAV_PAGES). None means silence for
        any channel that asks for it, which is what an unloaded page
        holds anyway."""
        inc, vol, duty, wave = [], [], [], []
        for c in range(spec.AU_CHANNELS):
            inc.append(dmem[spec.AU_BASE + 2 * c] & 0xFFFFFF)
            ctrl = dmem[spec.AU_BASE + 2 * c + 1]
            vol.append(ctrl & 0xF)
            duty.append((ctrl >> 4) & 0x3)
            wave.append(bool(ctrl & spec.AU_WAVE))
        if wav is None:
            wv = [[0] * spec.WAV_W] * spec.AU_CHANNELS
        elif wav and isinstance(wav[0], (list, tuple, np.ndarray)):
            wv = wav                              # already one page a voice
        else:
            wv = [wav] * spec.AU_CHANNELS         # one page, shared
        out = np.empty(spec.SAMPLES_PER_FRAME, np.int16)
        ph, lfsr = self.phase, self.lfsr
        # ---- WHAT EACH VOICE WAS HEARD TO DO (spec.AUD_BASE) ----------
        # |contribution| summed over the frame, in the mixer's own units
        # -- before the >>2 and before the clamp, because those are
        # properties of the BUS and not of the voice. What the clamp took
        # is reported separately, below.
        acc = [0] * spec.AU_CHANNELS

        # ---- THE EVENT LIST (spec.AU_EV_BASE) --------------------------
        # The cart wrote a TIMELINE, not a value. Read it once, then walk
        # a pointer through it as the samples go by: at sample s every
        # event whose offset has been reached is applied, in list order,
        # BEFORE s is synthesized. That is what gives this machine
        # sub-frame envelopes without touching the frame contract.
        nev = dmem[spec.AU_EV_BASE]
        nev = nev if 0 <= nev <= spec.AU_EV_MAX else 0
        events = []
        for e in range(nev):
            w0 = dmem[spec.AU_EV_BASE + 1 + 2 * e]
            w1 = dmem[spec.AU_EV_BASE + 2 + 2 * e]
            events.append((w0 & spec.AU_EV_OFF_MASK,
                           (w0 >> spec.AU_EV_CH_SHIFT) & 0xF,
                           bool(w0 & spec.AU_EV_CTRL_BIT), w1))
        ev = 0

        for s in range(spec.SAMPLES_PER_FRAME):
            while ev < len(events) and events[ev][0] <= s:
                _, ch, is_ctrl, val = events[ev]
                if is_ctrl:
                    vol[ch] = val & 0xF
                    duty[ch] = (val >> 4) & 0x3
                    wave[ch] = bool(val & spec.AU_WAVE)
                else:
                    inc[ch] = val & 0xFFFFFF
                ev += 1
            mix = 0
            for c in (0, 1):                      # pulses
                ph[c] = (ph[c] + inc[c]) & 0xFFFFFF
                if wave[c]:                       # ...or the cart's table
                    t = wv[c][(ph[c] >> 16) & (spec.WAV_W - 1)] * vol[c] * 8
                else:
                    hi = (ph[c] >> 21) < spec.PULSE_DUTY[duty[c]]
                    t = vol[c] * 1024 if hi else -vol[c] * 1024
                mix += t
                acc[c] += abs(t)
            ph[2] = (ph[2] + inc[2]) & 0xFFFFFF   # triangle
            if wave[2]:
                t = wv[2][(ph[2] >> 16) & (spec.WAV_W - 1)] * vol[2] * 8
            else:
                tri = (ph[2] >> 15) & 0xFF
                if ph[2] & 0x800000:
                    tri ^= 0xFF
                t = (tri - 128) * vol[2] * 8
            mix += t
            acc[2] += abs(t)
            nph = ph[3] + inc[3]                  # noise: LFSR per wrap
            if nph > 0xFFFFFF:
                bit = (lfsr ^ (lfsr >> 1)) & 1
                lfsr = (lfsr >> 1) | (bit << 14)
            ph[3] = nph & 0xFFFFFF
            if wave[3]:                           # the phase still wraps
                t = wv[3][(ph[3] >> 16) & (spec.WAV_W - 1)] * vol[3] * 8
            else:
                t = vol[3] * 1024 if lfsr & 1 else -vol[3] * 1024
            mix += t
            acc[3] += abs(t)
            # ---- the twelve pure voices ------------------------------
            # No oscillator of their own: channels 4..15 read the wave
            # page always, which is what the sampled field is for. A
            # cart that never writes them leaves inc and vol at zero,
            # so they contribute exactly nothing and every older cart's
            # stream is unchanged to the bit.
            for c in range(spec.AU_TONE_CHANNELS, spec.AU_CHANNELS):
                ph[c] = (ph[c] + inc[c]) & 0xFFFFFF
                t = wv[c][(ph[c] >> 16) & (spec.WAV_W - 1)] * vol[c] * 8
                mix += t
                acc[c] += abs(t)
            # THE CLAMP (spec.AU_CLAMP): sixteen channels overflow int16
            # where four never could. Saturate rather than wrap -- a wrap
            # flips the sign of a loud frame, which is the worst noise an
            # audio path can make.
            v = mix >> 2
            out[s] = (-spec.AU_CLAMP - 1 if v < -spec.AU_CLAMP - 1
                      else spec.AU_CLAMP if v > spec.AU_CLAMP else v)
        # HANDED BACK, NOT WRITTEN. When these become readable is a
        # property of the MACHINE and not of the mixer -- see
        # cabinet.frame(), which holds them the two frames the silicon
        # holds them.
        self.heard = [min(v, spec.AUD_MAX) for v in acc]
        self.lfsr = lfsr
        return out
