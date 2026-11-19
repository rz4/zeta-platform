# The card ferry, gated against a fake card -- including the mutations:
# a non-Pocket mount is refused, an unchanged card copies nothing, and
# a stale file on the card is replaced.

import time

import pytest

from zeta import sdcard


@pytest.fixture
def card(tmp_path):
    c = tmp_path / "card"
    (c / "Assets").mkdir(parents=True)
    (c / "Cores").mkdir()
    (c / "Memories" / "Screenshots").mkdir(parents=True)
    return c


@pytest.fixture
def staged(tmp_path):
    s = tmp_path / "staged"
    (s / "Cores" / "CleanRoom.Zeta").mkdir(parents=True)
    (s / "Cores" / "CleanRoom.Zeta" / "core.rbf_r").write_bytes(b"\x01" * 64)
    (s / "Assets" / "zeta" / "common").mkdir(parents=True)
    (s / "Assets" / "zeta" / "common" / "cart.zbin").write_bytes(b"\x02" * 32)
    return s


def test_find_card_accepts_a_pocket(card):
    assert sdcard.find_card(str(card)) == card


def test_find_card_refuses_a_bare_mount(tmp_path):
    (tmp_path / "music").mkdir()
    with pytest.raises(SystemExit):
        sdcard.find_card(str(tmp_path))


def test_push_copies_then_goes_quiet(card, staged):
    assert sdcard.push(card, staged) == 0
    rbf = card / "Cores" / "CleanRoom.Zeta" / "core.rbf_r"
    assert rbf.read_bytes() == b"\x01" * 64
    # second push: nothing newer, nothing copied (mtimes preserved)
    before = rbf.stat().st_mtime
    assert sdcard.push(card, staged) == 0
    assert rbf.stat().st_mtime == before


def test_push_replaces_a_stale_file(card, staged):
    sdcard.push(card, staged)
    src = staged / "Assets" / "zeta" / "common" / "cart.zbin"
    time.sleep(0.01)
    src.write_bytes(b"\x03" * 32)          # a new deploy
    sdcard.push(card, staged)
    dst = card / "Assets" / "zeta" / "common" / "cart.zbin"
    assert dst.read_bytes() == b"\x03" * 32


def test_shots_pulls_newest_first(card, tmp_path):
    shots = card / "Memories" / "Screenshots"
    old = shots / "old.png"; old.write_bytes(b"old")
    time.sleep(0.01)
    new = shots / "new.png"; new.write_bytes(b"new")
    out = tmp_path / "local"
    pulled = sdcard.shots(card, 1, out)
    assert [p.name for p in pulled] == ["new.png"]
    pulled = sdcard.shots(card, 2, out)
    assert {p.name for p in pulled} == {"new.png", "old.png"}


def test_shots_with_no_captures_fails(card):
    with pytest.raises(SystemExit):
        sdcard.shots(card, 1)
