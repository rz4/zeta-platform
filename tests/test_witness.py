# The screenshot gate, gated. The witness is proved live by mutation:
# a capture that matches must PASS, the same capture against the wrong
# cart or a damaged pixel must FAIL, and a filtered (non-uniform)
# upscale must be REFUSED -- a gate that cannot fail is not a gate.

from pathlib import Path

import numpy as np
import pytest

from zeta import cabinet, gpu, spec, witness


def _capture(cart_name: str, frame: int) -> np.ndarray:
    m = cabinet.VirtualMachine(cabinet.load_cart(f"carts/{cart_name}.zol"))
    for _ in range(frame + 1):
        m.frame(0)
    return np.asarray(m.panel(), dtype=np.uint8).copy()


@pytest.fixture(scope="module")
def shot():
    # graded.zol: the grading witness puts everything in frame one,
    # because glass scans three frames and no more (ALIEN.md) -- the
    # same property makes it the cheapest witness here.
    return _capture("graded", 1)


def test_a_true_capture_passes(shot):
    cart = cabinet.load_cart("carts/graded.zol")
    assert witness.witness(cart, shot, 4, None, None) == 0


def test_the_wrong_cart_fails(shot):
    cart = cabinet.load_cart("carts/bounce.zol")
    assert witness.witness(cart, shot, 4, None, None) == 1


def test_one_damaged_pixel_fails(shot):
    bad = shot.copy()
    bad[17, 230] ^= 0x08                   # one bit of one channel
    cart = cabinet.load_cart("carts/graded.zol")
    assert witness.witness(cart, bad, 4, None, None) == 1


def test_integer_upscale_is_accepted(tmp_path, shot):
    big = shot.repeat(5, axis=0).repeat(5, axis=1)   # the panel's own 5x
    p = tmp_path / "big.ppm"
    with open(p, "wb") as f:
        f.write(b"P6 %d %d 255\n" % (spec.W * 5, spec.H * 5))
        f.write(big.tobytes())
    back = witness.read_shot(p)
    assert (back == shot).all()


def test_filtered_upscale_is_refused(tmp_path, shot):
    big = shot.repeat(5, axis=0).repeat(5, axis=1).astype(np.int16)
    big[0, 1] += 1                         # one blurred sample
    p = tmp_path / "soft.ppm"
    with open(p, "wb") as f:
        f.write(b"P6 %d %d 255\n" % (spec.W * 5, spec.H * 5))
        f.write(big.clip(0, 255).astype(np.uint8).tobytes())
    with pytest.raises(SystemExit):
        witness.read_shot(p)


def test_the_tape_drives_the_replay(tmp_path):
    # the tape format's own witness: the same cart, driven differently,
    # must witness differently. fabric has tank controls, so pad vs no
    # pad is two different worlds by frame 40.
    cart = cabinet.load_cart("carts/fabric.zol")
    m = cabinet.VirtualMachine(cart)
    for _ in range(40):
        m.frame(spec.PAD_UP if hasattr(spec, "PAD_UP") else 1)
    driven = np.asarray(m.panel(), dtype=np.uint8).copy()

    tape = tmp_path / "walk.tape"
    pad = spec.PAD_UP if hasattr(spec, "PAD_UP") else 1
    tape.write_text("# forty frames of walking\n" + f"{pad}\n" * 40)
    start, pads = witness.read_tape(tape)
    assert start == 0 and len(pads) == 40 and pads[0] == pad

    assert witness.witness(cart, driven, 40, (start, pads), 39) == 0
    assert witness.witness(cart, driven, 40, None, 39) == 1


# ---- GLASS: a real Pocket capture, kept --------------------------------------
GLASS = Path(__file__).parent / "glass"


def test_the_pockets_camera_is_rgb565():
    """Captured with Menu+Start on 2026-11-19 (the Pocket writes PNG; kept
    as a lossless PPM): the column cart of commit 12a5f44 running TND
    untouched, the brute walking in -- the law's frame 143 to the pixel
    once the law's panel goes through the Pocket's RGB565 screenshot, and
    not without it (green's low bits). The law's own frame is kept beside
    it: the cart has moved on since (the aware markers stand in that
    opening now), and the camera's model must not depend on the cart.
    (The hardware-equals-law witness itself was that day's, at 12a5f44.)"""
    law = witness.read_shot(GLASS / "tnd-wave-143-law.ppm")
    shot = witness.read_shot(GLASS / "tnd-wave-143.ppm")
    assert (witness.pocket_capture(law) == shot).all(), "the camera model drifted"
    assert not (law == shot).all(), "the witness cannot tell 555 from 565"


def test_tnd_on_glass_today():
    """Captured with Menu+Start on 2026-11-19 from the build at fbe5bf4
    (core 0.103.0): Start, then nothing -- the wave arrived, the aware
    markers up. The law's frame 348 (the fight's 347) to the pixel through
    the Pocket's camera, and not without it. When the cart's opening
    changes on purpose, this is re-captured, not re-blessed."""
    cart = cabinet.load_cart(Path(__file__).parents[1] / "carts/tnd.zol")
    shot = witness.read_shot(GLASS / "tnd-aware-348.ppm")
    start = (0, [spec.PAD_START])
    assert witness.witness(cart, shot, 349, start, 348,
                           capture=witness.pocket_capture) == 0
    assert witness.witness(cart, shot, 349, start, 348) == 1
