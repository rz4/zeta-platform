"""test_heard.py -- spec.AUD_BASE against arithmetic, not against itself.

The tally sums |contribution| over a frame. A test that summed the
contributions a second way would be the same code twice; what makes
these checks worth having is that THREE OF THE FOUR OSCILLATORS HAVE A
CLOSED FORM, straight out of the spec and owing nothing to the mixer:

    pulse   out = +/- vol * 1024 every sample, whatever the duty
    noise   out = +/- vol * 1024 every sample, whatever the LFSR does
    wave    out = s8 * vol * 8, so a page of a constant s8 is constant

so a frame of any of them totals SAMPLES_PER_FRAME * that magnitude,
exactly, with no tolerance. The triangle is the one that genuinely
varies and is checked by its bounds instead.

The other half is TIMING, which is the part that was wrong. The number
being right does not mean it is readable at the right moment: held one
frame instead of two, every total here still matched to the unit and
heard.zol's bars stood a frame ahead of the sound that drew them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import audio, cabinet, spec

N = spec.SAMPLES_PER_FRAME


def _dmem():
    return [0] * spec.DMEM_WORDS


def _run(d, wav=None):
    e = audio.SndEngine()
    e.frame(d, wav)
    return e.heard


def test_a_pulse_totals_its_amplitude_every_sample():
    for ch, vol, duty in ((0, 9, 0), (0, 15, 3), (1, 4, 2)):
        d = _dmem()
        d[spec.AU_BASE + 2 * ch] = 123_456          # any pitch at all
        d[spec.AU_BASE + 2 * ch + 1] = vol | (duty << 4)
        heard = _run(d)
        assert heard[ch] == N * vol * 1024, (
            f"pulse ch{ch} vol {vol} duty {duty}: {heard[ch]} against "
            f"{N * vol * 1024}")


def test_the_noise_totals_its_amplitude_too():
    """The LFSR chooses the SIGN and never the magnitude."""
    d = _dmem()
    d[spec.AU_BASE + 6] = 200_000
    d[spec.AU_BASE + 7] = 12
    assert _run(d)[3] == N * 12 * 1024


def test_a_flat_wave_page_totals_the_page():
    d = _dmem()
    ch, vol = 5, 7
    d[spec.AU_BASE + 2 * ch] = 90_000
    d[spec.AU_BASE + 2 * ch + 1] = vol
    page = [127] * spec.WAV_W
    heard = _run(d, [page] * spec.AU_CHANNELS)
    assert heard[ch] == N * 127 * vol * 8


def test_the_triangle_lands_inside_its_own_bounds():
    """It sweeps -128..127, so it cannot reach the pulse's total and
    cannot be zero -- which is all that can be said without redoing the
    ramp, and is enough to catch a total that is stuck."""
    d = _dmem()
    d[spec.AU_BASE + 4] = 300_000
    d[spec.AU_BASE + 5] = 10
    t = _run(d)[2]
    assert 0 < t < N * 128 * 10 * 8


def test_silence_is_reported_as_silence():
    d = _dmem()
    d[spec.AU_BASE + 0] = 123_456            # a pitch, and no volume
    heard = _run(d)
    assert heard == [0] * spec.AU_CHANNELS, (
        "a voice at volume zero contributes nothing and must total "
        "nothing -- a running phase is not a sound")


def test_volume_is_linear_in_the_total():
    d = _dmem()
    d[spec.AU_BASE + 0] = 123_456
    d[spec.AU_BASE + 1] = 3
    lo = _run(d)[0]
    d[spec.AU_BASE + 1] = 12
    assert _run(d)[0] == 4 * lo


def test_the_cart_reads_it_TWO_frames_later():
    """THE CONTRACT, and the half that was wrong.

    VIS_BASE and the pick are finished when the DRAW is; a frame's SOUND
    is not. The machine's order is frame_go, draw, write the answers
    back, run the cart -- and at the instant it writes, only about a
    third of the current frame's samples have played. So the newest
    COMPLETE frame of audio is the one before last, on glass and in the
    cross alike, and the law holds these two frames to say so.
    """
    m = cabinet.VirtualMachine(
        cabinet.load_cart(Path(__file__).resolve().parents[1]
                          / "carts" / "heard.zol"))
    seen, produced = [], []
    for _ in range(12):
        m.frame(0)
        # READ AFTER, not before: the cabinet writes these cells at the
        # TOP of frame(), so before the call they still hold the last
        # frame's. Nothing between there and here writes them again, so
        # this is exactly what frame i's program was given.
        seen.append([m.vm.dmem[spec.AUD_BASE + c]
                     for c in range(spec.AU_CHANNELS)])
        produced.append(list(m.snd.heard))     # ...and what it then made
    assert any(produced), "the witness cart made no sound at all"
    for i in range(2, 12):
        assert seen[i] == produced[i - 2], (
            f"frame {i} could read {seen[i][:3]}, which is not frame "
            f"{i - 2}'s {produced[i - 2][:3]}")
    # ...and it is genuinely two, not one: the carts differ frame to frame
    assert any(seen[i] != produced[i - 1] for i in range(1, 12)), (
        "every frame produced the same totals, so this proves nothing "
        "about WHICH frame is being read")
