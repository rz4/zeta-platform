"""The .zbin cart image, pinned: exactly what cart_loader.v replays."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import asm, deploy, spec


def test_zbin_layout(tmp_path):
    cart = asm.assemble(Path(__file__).parents[1] / "games/tear/tear.zol")
    out = tmp_path / "cart.zbin"
    deploy.write_zbin(cart, out)
    data = out.read_bytes()
    assert len(data) == (spec.IMEM_WORDS + spec.DMEM_WORDS) * 4   # 32 KB
    words = struct.unpack(f"<{spec.IMEM_WORDS + spec.DMEM_WORDS}I", data)
    assert list(words[:len(cart["imem"])]) == cart["imem"]
    assert words[len(cart["imem"])] == 0                          # padding
    for a, v in cart["dmem"].items():
        assert words[spec.IMEM_WORDS + int(a)] == v & spec.WORD_MASK


# --------------------------------------------------------------------------
# the instrument, audited
# --------------------------------------------------------------------------
def test_no_boot_path_input_is_left_dangling():
    """glass_sim.v wrapped zeta_glass and omitted `.boot_done`. An
    unconnected input reads as zero and says nothing, so the loader's
    release verdict never came, the last PARTIAL bank of CRAM words
    never flushed, and hall.zol failed glass by exactly 55 black pixels
    -- 92161 mod 63 -- at the end of row 287. cross tied the signal high
    and passed; the hardware drove it from cart_ready and was always
    right. Only the instrument was wrong."""
    deploy.check_dangling()


def test_the_dangling_check_can_actually_fail(tmp_path, monkeypatch):
    """A gate that cannot fail is not a gate (the fade.zol lesson)."""
    src = deploy.ROOT / "pocket/glass_sim.v"
    hurt = tmp_path / "glass_sim.v"
    hurt.write_text(src.read_text().replace(".boot_done(boot_done),", ""))
    real = deploy._sources()          # capture BEFORE patching, or the
    monkeypatch.setattr(              # replacement calls itself forever
        deploy, "_sources",
        lambda: [p for p in real if p != src] + [hurt])
    with pytest.raises(SystemExit) as e:
        deploy.check_dangling()
    assert "boot_done" in str(e.value)


# --------------------------------------------------------------------------
# the build number cannot be forgotten again
# --------------------------------------------------------------------------
def test_rtl_that_moved_without_a_bump_is_refused(tmp_path):
    """spec.LOADER_BUILD's own history: 93 shipped on five bitstreams. The
    stamp beside the bitstream now carries the build it was packaged
    under, and a changed source hash with an unchanged number refuses."""
    stamp = tmp_path / "ap_core.srchash"
    stamp.write_text("aaaa 100\n")
    have, build = deploy.read_stamp(stamp)
    assert (have, build) == ("aaaa", 100)
    with pytest.raises(SystemExit) as e:
        deploy.check_build_bump(have, build, "bbbb", 100)
    assert "LOADER_BUILD" in str(e.value)
    deploy.check_build_bump(have, build, "bbbb", 101)     # bumped: fine
    deploy.check_build_bump(have, build, "aaaa", 100)     # unchanged: fine
    # a stamp from before build 100 carries no number and cannot judge
    stamp.write_text("aaaa\n")
    have, build = deploy.read_stamp(stamp)
    assert build is None
    deploy.check_build_bump(have, build, "bbbb", 100)
