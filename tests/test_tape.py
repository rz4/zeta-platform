"""The tape: a session as its pad words (zeta/tape.py, docs/PLATFORM.md)."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import asm, carts, deploy, spec, tape  # noqa: E402


def _session():
    """Something a thumb would do: holds, taps, chords, a long stand."""
    pads = [0] * 37 + [spec.PAD_START] + [0] * 5
    pads += [spec.PAD_UP] * 90 + [spec.PAD_UP | spec.PAD_X] * 3 + [spec.PAD_UP] * 12
    pads += [spec.PAD_X, 0, spec.PAD_X, 0, 0, spec.PAD_Y] + [0] * 400
    return pads


def test_a_tape_is_its_pads_and_nothing_else():
    """Encode, decode: the same pad word on every frame, and as many runs
    as there were changes."""
    pads = _session()
    head, back = tape.decode(tape.encode(pads, cart_sum_=0x1234))
    assert back == pads
    assert head == {"build": spec.LOADER_BUILD, "cart_sum": 0x1234,
                    "runs": len(tape.runs(pads))}
    assert head["runs"] < 20, "a tape of runs should be far shorter than its frames"


def test_the_recorders_memory_ends_the_tape():
    """The recorder's memory starts as zeros and the run being held is
    rewritten in place every frame -- so a tape cut ANYWHERE after a whole
    run is a whole tape, and trailing zeros are just the end."""
    pads = _session()
    blob = tape.encode(pads)
    assert tape.decode(blob + bytes(4096))[1] == pads
    cut = blob[:4 * (tape.HEADER_WORDS + 5)]             # five runs in
    assert tape.decode(cut)[1] == [p for n, p in tape.runs(pads)[:5] for _ in range(n)]


def test_a_long_hold_is_more_than_one_run():
    """A run counts in sixteen bits; a pad held longer starts another."""
    pads = [spec.PAD_UP] * (tape.RUN_MAX + 10)
    r = tape.runs(pads)
    assert r == [(tape.RUN_MAX, spec.PAD_UP), (10, spec.PAD_UP)]
    assert tape.decode(tape.encode(pads))[1] == pads


def test_the_text_form_carries_the_same_session(tmp_path):
    pads = _session()
    tape.write_text(pads, tmp_path / "t.tape", note="a test")
    assert tape.read(tmp_path / "t.tape") == pads
    (tmp_path / "t.ztp").write_bytes(tape.encode(pads))
    assert tape.read(tmp_path / "t.ztp") == pads


def test_a_tape_knows_its_cart_and_its_machine(tmp_path):
    """The header's sum is every word of the cart as the loader sees them
    go by -- the .zbin's own words -- and a tape from another cart or
    another build says so."""
    cart = asm.assemble(carts.path("tear"))
    deploy.write_zbin(cart, tmp_path / "c.zbin")
    data = (tmp_path / "c.zbin").read_bytes()
    words = struct.unpack(f"<{len(data) // 4}I", data)
    assert tape.cart_sum(cart) == sum(words) & 0xFFFFFFFF
    head, _ = tape.decode(tape.encode([0, 1, 1], cart_sum_=tape.cart_sum(cart)))
    assert tape.check(head, cart) is None
    assert "cart" in tape.check(head, asm.assemble(carts.path("bounce")))
    old, _ = tape.decode(tape.encode([0], build=spec.LOADER_BUILD - 1))
    assert "build" in tape.check(old, cart)


def test_what_is_not_a_tape_is_refused():
    with pytest.raises(ValueError):
        tape.decode(b"\x00" * 64)
    with pytest.raises(ValueError):
        tape.decode(b"ZT")
