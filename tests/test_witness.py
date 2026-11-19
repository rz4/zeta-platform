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


def test_tnd_on_glass_is_frame_143_through_the_pockets_camera():
    """Captured with Menu+Start on 2026-11-19 (the Pocket writes PNG; kept
    here as a lossless PPM): the column cart (film ->
    shelf -> X) running TND untouched, the brute walking in. It is the
    law's frame 143 of TND to the pixel -- once the law's panel goes
    through the Pocket's RGB565 screenshot. Without that model it is not
    (green's low bits), so the model is held both ways."""
    # (TND now opens on its title: Start on frame 0, and the fight that
    # ran from frame 0 on glass runs from frame 1 -- its frame 143 is 144)
    cart = cabinet.load_cart(Path(__file__).parents[1] / "carts/tnd.zol")
    shot = witness.read_shot(GLASS / "tnd-wave-143.ppm")
    start = (0, [spec.PAD_START])
    assert witness.witness(cart, shot, 145, start, 144,
                           capture=witness.pocket_capture) == 0
    assert witness.witness(cart, shot, 145, start, 144) == 1
