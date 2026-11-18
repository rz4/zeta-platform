"""test_vessel.py -- the game's own gates, in the law.

The suite proves vessel on SILICON (cross, glass). These prove it as a
GAME: that the loop reaches its states and that the sounds actually
sound. Both halves are needed and the second is the one that was
missing -- the chime shipped SILENT to a real Pocket, was heard to be
missing by a person, and no gate in this tree could have told me,
because "the cart makes noise" was true the whole time. The air tick
was making it.

The bug was one token: `load chime; push 1; shr 1` shifts the pushed 1
rather than the volume, because `shr` takes an IMMEDIATE. It stored zero
and left chime orphaned on the stack. Every gate stayed green.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from zeta import cabinet, spec

ONE = 1 << 16
CART = Path(__file__).parents[1] / "carts/vessel.zol"


@pytest.fixture(scope="module")
def cart():
    return cabinet.load_cart(CART)


def cells(cart):
    """px and pz, found by their boot values rather than hard-coded --
    the forge assigns addresses and a test that pins them breaks on
    every re-link."""
    d0 = {int(k): v for k, v in (cart.get("dmem") or {}).items()}
    pz = next(a for a, v in d0.items() if v == int(6.0 * ONE))
    return pz - 1, pz


def test_the_chime_actually_sounds(cart):
    """Not "the cart has audio" -- THIS voice, at a volume above zero."""
    px, pz = cells(cart)
    m = cabinet.VirtualMachine(cart)
    m.frame(0)
    vols = set()
    for f in range(90):
        if f == 5:                       # stand on the key
            m.vm.dmem[px] = int(-2.2 * ONE) & spec.WORD_MASK
            m.vm.dmem[pz] = int(14.0 * ONE)
        m.frame(spec.PAD_A if f in (7, 8) else 0)
        vols.add(m.vm.dmem[spec.AU_BASE + 3] & 0xF)
    assert max(vols) > 0, "the key chime is silent"
    assert len(vols) > 4, f"the chime does not decay: volumes {sorted(vols)}"


def test_the_drone_is_a_pitch_a_speaker_can_move(cart):
    """55 Hz is correct on paper and inaudible on the hardware. The law
    cannot hear, so the gate checks the NUMBER a person's ear reported."""
    m = cabinet.VirtualMachine(cart)
    m.frame(0)
    inc = m.vm.dmem[spec.AU_BASE + 4]
    hz = inc * spec.SND_HZ / (1 << 24)
    assert 100 < hz < 400, f"the room drone sits at {hz:.0f} Hz"
    assert m.vm.dmem[spec.AU_BASE + 5] & 0xF >= 3, "the drone is too quiet"


def test_the_air_tick_is_sub_frame(cart):
    """The onset must land on different SAMPLES, not on the 60 Hz grid --
    the one thing here no console of either generation could do."""
    m = cabinet.VirtualMachine(cart)
    offs = []
    for _ in range(400):
        m.frame(0)
        d = m.vm.dmem
        for k in range(min(d[spec.AU_EV_BASE], spec.AU_EV_MAX)):
            if d[spec.AU_EV_BASE + 2 + 2 * k]:            # an attack
                offs.append(d[spec.AU_EV_BASE + 1 + 2 * k]
                            & spec.AU_EV_OFF_MASK)
    assert len(offs) >= 4, "no ticks"
    assert all(o < spec.SAMPLES_PER_FRAME for o in offs), \
        f"an event past the last sample never fires: {offs}"
    assert len(set(offs)) >= 4, f"ticks quantised to the frame: {offs}"


def test_the_air_runs_out_and_says_so(cart):
    """The fail state fires once, shows a message and fades."""
    m = cabinet.VirtualMachine(cart)
    for _ in range(60 * 50 + 40):
        m.frame(0)
    d = m.vm.dmem
    assert d[spec.DL_BASE] > 0, "no message when the air ran out"
    alpha = (d[spec.CO_BASE + 3] >> 24) & 0x1F
    assert alpha > 0, "no fade when the air ran out"


def test_a_billboard_does_not_turn_when_the_camera_does_not(cart):
    """THE HALO TURNED WITH THE PLAYER, and a person saw it before any
    gate did.

    The glow is a card that should face the camera. It was given the
    PLAYER's heading, on the assumption that the camera rides the
    player -- and in this cart it does not: the camera sits at the
    origin looking down the hall while the player's body walks away
    from it. So the card swung every time the player turned, for no
    reason at all.

    Nothing here could have caught it. cross was bit-equal the whole
    time, because both machines turned it. The suite was green, because
    the glow reached plenty of pixels. Both gates were asking whether
    the machines AGREE, and they did -- about the wrong picture.

    This asks the other question: if the camera did not move, nothing
    that exists to face the camera may have moved either."""
    m = cabinet.VirtualMachine(cart)
    m.frame(0)

    def camera():
        return [m.vm.dmem[k] for k in range(8, 12)]

    def billboard_yaws():
        d = m.vm.dmem
        n = min(d[spec.OL_BASE], spec.OL_MAX)
        return [d[spec.OL_BASE + 1 + k * spec.OL_STRIDE + 4]
                for k in range(n)
                if d[spec.OL_BASE + 1 + k * spec.OL_STRIDE + 5]
                & spec.OBJ_BLEND]

    def opaque_yaws():
        d = m.vm.dmem
        n = min(d[spec.OL_BASE], spec.OL_MAX)
        return [d[spec.OL_BASE + 1 + k * spec.OL_STRIDE + 4]
                for k in range(n)
                if not d[spec.OL_BASE + 1 + k * spec.OL_STRIDE + 5]
                & spec.OBJ_BLEND]

    cam0, yaw0 = camera(), billboard_yaws()
    turn0 = opaque_yaws()
    assert yaw0, "no blended objects -- this test is watching nothing"
    for _ in range(40):
        m.frame(spec.PAD_LEFT)
    # THE INSTRUMENT, CHECKED FIRST. A yaw test that passes because the
    # cart turns nothing at all is worth nothing, and would go on
    # passing after the bug came back. The player's body IS turning
    # here, read through the same cells by the same code -- so the
    # billboards holding still below is a fact about them.
    assert opaque_yaws() != turn0, (
        "nothing in this cart turned at all, so this test cannot tell a "
        "billboard that holds still from one that is never written")
    assert camera() == cam0, (
        "the camera moved, so this cart's billboards SHOULD track it and "
        "this test no longer describes the cart -- rewrite it, do not "
        "delete it")
    assert billboard_yaws() == yaw0, (
        f"a billboard turned {yaw0} -> {billboard_yaws()} while the "
        f"camera stood still")
