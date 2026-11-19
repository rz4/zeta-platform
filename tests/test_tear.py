"""The fight, pinned: the AI beats an idle player; an aggressive player
beats the AI; rounds reset. Cells match carts/tear.zol's .const map."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import asm, spec, vm

CART = Path(__file__).parents[1] / "carts/tear.zol"
PX, EX, PH, EH, KO, WIN = 16, 17, 18, 19, 24, 25


def test_ai_beats_idle_player():
    m = vm.VM(asm.assemble(CART))
    for f in range(1500):
        m.frame(0)
        if m.dmem[KO]:
            break
    else:
        raise AssertionError("no KO in 1500 idle frames")
    assert m.dmem[WIN] == 2
    assert spec.s32(m.dmem[PH]) < 1


def test_aggressive_player_beats_ai():
    m = vm.VM(asm.assemble(CART))
    for f in range(3000):
        m.frame(spec.PAD_RIGHT | spec.PAD_A)   # crowd it and swing on cooldown
        if m.dmem[KO]:
            break
    else:
        raise AssertionError("no KO in 3000 aggressive frames")
    assert m.dmem[WIN] == 1
    assert spec.s32(m.dmem[EH]) < 1


def test_round_resets_after_ko():
    m = vm.VM(asm.assemble(CART))
    while not m.dmem[KO]:
        m.frame(0)
    while m.dmem[KO]:                          # ride out the freeze; the
        m.frame(0)                             # last tick is the reset frame
    assert m.dmem[PH] == 96 and m.dmem[EH] == 96
    assert m.dmem[PX] == 60 and m.dmem[EX] == 236


# ---- stage 1 (FLAGSHIP.md): the triangle, hitstop, the buffer -------------
PP, EP, PMV, EMV, PBUF, HST = 20, 21, 31, 32, 33, 35


def test_block_beats_jab():
    """Holding away with free hands: a jab NEVER lands clean -- only
    2-point chip (and the heavy's 20, which is the triangle's other leg)."""
    m = vm.VM(asm.assemble(CART))
    deltas = set()
    last = 96
    for f in range(1500):
        m.frame(spec.PAD_LEFT)                 # back is LEFT while enemy
        ph = spec.s32(m.dmem[PH])              # is to the right
        if ph != last:
            deltas.add(last - ph)
            last = ph
        if m.dmem[KO]:
            break
    assert 2 in deltas, f"no chip damage ever happened: {deltas}"
    assert 8 not in deltas, (
        f"a jab landed clean on a blocking player: {deltas}")


def test_jab_interrupts_heavy():
    """The heavy's 14-frame wind-up is jab-bait: a jab landed during it
    cancels the move, and the heavy never comes out."""
    m = vm.VM(asm.assemble(CART))
    for f in range(4000):
        m.frame(0)
        if m.dmem[EMV] == 2 and m.dmem[EP] == 26 \
                and spec.s32(m.dmem[28]) < 52:   # ADX: in jab reach
            break
    else:
        raise AssertionError("the enemy never began a heavy in reach")
    ph_before, eh_before = m.dmem[PH], m.dmem[EH]
    m.frame(spec.PAD_A)                        # the jab: 4 frames of startup
    for _ in range(5):
        m.frame(0)
    assert m.dmem[EMV] == 0 and m.dmem[EP] == 0, "the heavy was not cancelled"
    assert m.dmem[EH] == eh_before - 8, "the interrupting jab did not land"
    for _ in range(30):                        # the cancelled heavy must
        m.frame(0)                             # never deal its damage
        if m.dmem[EMV]:
            break
    assert m.dmem[PH] == ph_before, "a cancelled heavy still hit"


def test_hitstop_freezes_the_world_once():
    """A connect freezes both fighters for 6 frames, and the frozen
    active frame does NOT re-land the hit when the stop lets go."""
    m = vm.VM(asm.assemble(CART))
    for f in range(600):                       # walk in, jab until one lands
        m.frame(spec.PAD_RIGHT | spec.PAD_A)
        if m.dmem[HST]:
            break
    else:
        raise AssertionError("no hit ever connected")
    assert m.dmem[HST] == 6
    eh = m.dmem[EH]
    px = m.dmem[PX]
    for _ in range(5):                         # held RIGHT moves nobody
        m.frame(spec.PAD_RIGHT)                # while the world is stopped
        assert m.dmem[PX] == px
    m.frame(0)                                 # the stop lets go...
    m.frame(0)
    assert m.dmem[EH] == eh, "the frozen active frame re-landed the hit"


def test_the_buffer_fires_when_the_hands_free():
    """A press made mid-move starts its move the frame the hands open."""
    m = vm.VM(asm.assemble(CART))
    m.frame(spec.PAD_A)                        # jab: PP 14, out of reach
    assert m.dmem[PP] == 14 and m.dmem[PMV] == 1
    for _ in range(6):
        m.frame(0)
    m.frame(spec.PAD_B)                        # buffered mid-recovery
    assert m.dmem[PBUF] == 2
    while m.dmem[PP]:
        m.frame(0)
    m.frame(0)                                 # first free frame: it fires
    assert m.dmem[PMV] == 2 and m.dmem[PP] == 26, \
        "the buffered heavy did not fire"
    assert m.dmem[PBUF] == 0
