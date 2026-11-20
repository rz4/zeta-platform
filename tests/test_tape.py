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


# --------------------------------------------------------------------------
# the recorder (pocket/zeta_tape.v) against the reference encoder
# --------------------------------------------------------------------------
import shutil       # noqa: E402
import subprocess   # noqa: E402

needs_verilator = pytest.mark.skipif(shutil.which("verilator") is None,
                                     reason="verilator not installed")


def _record(script: str) -> tuple[list[int], dict]:
    from zeta import silicon
    r = subprocess.run([str(silicon.tape_sim())], input=script,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-400:]
    words = [int(l, 16) for l in r.stdout.split("\n") if len(l) == 8]
    q = [l.split() for l in r.stdout.split("\n") if l.startswith("Q ")]
    stats = {q[-1][i]: int(q[-1][i + 1]) for i in range(1, len(q[-1]), 2)} if q else {}
    return words, stats


def _cart_script(cart) -> str:
    """The loader's delivery: every word of the cart, then the signature
    it writes about itself (which the sum must NOT include)."""
    out = [f"B 0 {a:x} {w:x}" for a, w in enumerate(cart["imem"])]
    out += [f"B 1 {int(a):x} {v & spec.WORD_MASK:x}" for a, v in cart.get("dmem", {}).items()]
    out += [f"B 2 {int(a):x} {v & spec.WORD_MASK:x}" for a, v in cart.get("cram", {}).items()]
    out += [f"B 1 {spec.LOADER_SIG + i:x} {0xC0FFEE00 + i:x}" for i in range(6)]
    out += [f"B 1 {spec.LOADER_SIG2 + i:x} {0xC0FFEE00 + i:x}" for i in range(6)]
    return "\n".join(out) + "\n"


@needs_verilator
def test_the_recorder_writes_the_reference_tape():
    """The silicon's image IS encode()'s, word for word: the header (with
    the cart's sum, the loader's own signature left out), every run, and
    the zero that ends it -- in an SRAM that powered up dirty."""
    cart = asm.assemble(carts.path("tear"))
    pads = _session()
    script = _cart_script(cart) + "R\n" + "".join(f"P {p:x}\n" for p in pads)
    want = tape.encode(pads, tape.cart_sum(cart))
    n = len(want) // 4 + 1
    words, stats = _record(script + f"D {n}\nQ\n")
    assert struct.pack(f"<{n - 1}I", *words[:-1]) == want
    assert words[-1] >> 16 == 0, "the tape does not end where the session did"
    head, back = tape.decode(struct.pack(f"<{n}I", *words))
    assert back == pads and tape.check(head, cart) is None
    # the SRAM is unmeasured on glass: the recorder must stay slow with it
    assert stats["min_pulse"] >= 2 and stats["min_hold"] >= 1, stats


@needs_verilator
def test_the_tape_is_whole_at_every_instant():
    """Read back after EVERY frame of a busy stretch: each time, the tape
    decodes to exactly the session so far. There is no finish step."""
    pads = [0, 0, 16, 16, 0, 64, 64, 64, 80, 0, 0, 1, 1, 1, 1, 0]
    script, upto = "R\n", []
    for i, p in enumerate(pads):
        script += f"P {p:x}\nD {tape.HEADER_WORDS + len(tape.runs(pads[:i + 1])) + 1}\n"
        upto.append(tape.HEADER_WORDS + len(tape.runs(pads[:i + 1])) + 1)
    words, _ = _record(script)
    at = 0
    for i, n in enumerate(upto):
        chunk = words[at:at + n]
        at += n
        assert tape.decode(struct.pack(f"<{n}I", *chunk))[1] == pads[:i + 1], \
            f"after frame {i} the tape read {chunk}"


@needs_verilator
def test_a_frame_pressed_against_the_last_is_not_lost():
    """Two latches three clocks apart -- far closer than frames ever are
    -- while the recorder is mid-access: both are on the tape."""
    pads = [1, 2, 2, 4]
    script = "R\n" + f"P {pads[0]:x} 3\nP {pads[1]:x} 300\nP {pads[2]:x} 3\nP {pads[3]:x} 300\nD 9\n"
    words, _ = _record(script)
    assert tape.decode(struct.pack("<9I", *words))[1] == pads


@needs_verilator
def test_a_tape_being_collected_stops_growing():
    """Once the OS starts reading the tape out, nothing more is recorded:
    each word is fetched a read ahead of the bridge, and a tape still
    growing would be read with a frame missing from its middle."""
    pads = [1, 1, 2]
    script = "R\n" + "".join(f"P {p:x}\n" for p in pads) + "F\nP 4\nP 4\nP 8\nD 8\n"
    words, _ = _record(script)
    assert tape.decode(struct.pack("<8I", *words))[1] == pads


def test_the_tape_comes_home_from_the_card(tmp_path, capsys):
    """zeta sd tape: the file the OS wrote, trimmed to the session, named
    by when it was written, and checked against the cart it claims."""
    from zeta import sdcard
    cart = asm.assemble(carts.path("tear"))
    pads = _session()
    card = tmp_path / "card"
    f = card / deploy.TAPE_FILE
    f.parent.mkdir(parents=True)
    f.write_bytes(tape.encode(pads, tape.cart_sum(cart)).ljust(deploy.TAPE_BYTES, b"\0"))
    got = sdcard.tape(card, tmp_path / "tapes", cart)
    assert got is not None and tape.read(got) == pads
    assert got.stat().st_size < 200, "the blank after the session came home too"
    assert "matches the cart" in capsys.readouterr().out
    f.write_bytes(bytes(deploy.TAPE_BYTES))                 # a blank tape
    assert sdcard.tape(card, tmp_path / "tapes") is None


def test_the_manifest_declares_the_tape_and_staging_lays_it(tmp_path):
    slots = deploy.manifests()["data.json"]["data"]["data_slots"]
    t = [s for s in slots if s["name"] == "Tape"][0]
    assert t["nonvolatile"] is True and t["address"] == "0x30000000"
    assert int(t["size_maximum"], 16) == deploy.TAPE_BYTES == 4 * tape.WORDS
    assert deploy.manifests(menu=True)["data.json"]["data"]["data_slots"][-1] == t
    deploy.stage_tape(tmp_path)
    assert (tmp_path / deploy.TAPE_FILE).read_bytes() == bytes(deploy.TAPE_BYTES)
