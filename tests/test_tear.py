"""The fight, pinned: the AI beats an idle player; an aggressive player
beats the AI; rounds reset. Cells match games/tear/tear.zol's .const map."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import asm, spec, vm

CART = Path(__file__).parents[1] / "games/tear/tear.zol"
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


# ---- stage 2: the second pad takes the red fighter ------------------------
P2ON = 36


def test_pad2_silences_the_ai():
    """One press on pad 2 and the machine's soul is out: the red
    fighter stops swinging on its cadence and obeys the second human --
    permanently. The machine does not take the controller back."""
    m = vm.VM(asm.assemble(CART))
    m.frame(0, spec.PAD_LEFT)                  # one press: latched
    assert m.dmem[P2ON] == 1
    for f in range(400):                       # P2 walks in, never attacks
        m.frame(0, spec.PAD_LEFT)
        assert m.dmem[EP] == 0, "the AI swung while a human held the pad"
    assert m.dmem[PH] == 96                    # nobody ever got hit
    assert spec.s32(m.dmem[EX]) <= 60 + 24     # and the body obeyed


def test_pad2_fights_and_wins():
    """The second human beats an idle player with their own hands."""
    m = vm.VM(asm.assemble(CART))
    for f in range(3000):
        m.frame(0, spec.PAD_LEFT | spec.PAD_A)
        if m.dmem[KO]:
            break
    else:
        raise AssertionError("no KO in 3000 frames of P2 aggression")
    assert m.dmem[WIN] == 2


def test_pad2_blocks_the_jab():
    """The guard works for the red fighter too: P1's jab never lands
    clean on a blocking P2 -- the triangle is symmetric."""
    m = vm.VM(asm.assemble(CART))
    deltas = set()
    last = 96
    for f in range(2600):
        # P1 walks in jabbing; P2 holds away (RIGHT, enemy on the right --
        # which also walks the red fighter to the wall first)
        m.frame(spec.PAD_RIGHT | spec.PAD_A, spec.PAD_RIGHT)
        eh = spec.s32(m.dmem[EH])
        if eh != last:
            deltas.add(last - eh)
            last = eh
        if m.dmem[KO]:
            break
    assert 2 in deltas, f"no chip ever happened: {deltas}"
    assert 8 not in deltas, f"a jab landed clean through P2's guard: {deltas}"


def test_two_idle_humans_draw_on_time():
    """With the AI gone and both humans idle, nobody can win -- so the
    ROUND CLOCK must end it: a dead-even minute is a gray draw, 90
    frames of banner, and no pip for anyone. (Before stage 3 this
    stalemate lasted forever, which was the test's old premise.)"""
    m = vm.VM(asm.assemble(CART))
    m.frame(0, spec.PAD_A)                     # human latched: AI gone
    while not m.dmem[KO]:
        m.frame(0)
        assert m.dmem[0] < 5000, "the clock never ended the stalemate"
    assert m.dmem[KO] == 90 and m.dmem[25] == 0      # WIN: a draw
    assert m.dmem[PH] == 96 and m.dmem[EH] == 96     # nobody was touched
    assert m.dmem[41] == 0 and m.dmem[42] == 0       # and nobody scored


# ---- stage 3: the match -----------------------------------------------------
PRW, ERW, RT = 41, 42, 43


def _play_round(m, pad1=0, pad2=0, limit=5000):
    while not m.dmem[KO]:
        m.frame(pad1, pad2)
        limit -= 1
        assert limit > 0, "no round verdict"
    ko = m.dmem[KO]
    while m.dmem[KO]:
        m.frame(0)
    return ko


def test_two_rounds_take_the_match_and_reset_it():
    """Best of three: the second round win freezes long (the results
    screen), and the NEXT reset clears the score. One round is 120."""
    m = vm.VM(asm.assemble(CART))
    ko1 = _play_round(m)                       # idle player loses round 1
    assert ko1 == 120 and m.dmem[ERW] == 1 and m.dmem[PRW] == 0
    ko2 = _play_round(m)                       # ...and the match
    assert ko2 == 300, "the match point did not hold the results screen"
    assert m.dmem[ERW] == 0 and m.dmem[PRW] == 0, "the match did not reset"
    assert m.dmem[PH] == 96 and m.dmem[EH] == 96


def test_timeout_goes_to_the_health_lead():
    """Stall the clock: both humans idle (pad 2 latched, the AI gone),
    the player lands one jab, and the round must go to the lead on
    points when the minute dies."""
    m = vm.VM(asm.assemble(CART))
    m.frame(0, spec.PAD_LEFT)                  # latch P2: nobody attacks now
    for f in range(300):                       # P2 walks into range
        m.frame(0, spec.PAD_LEFT)
        if spec.s32(m.dmem[28]) < 52:
            break
    m.frame(spec.PAD_A)                        # one jab
    for _ in range(20):
        m.frame(0)
    assert spec.s32(m.dmem[EH]) == 88, "the one jab did not land"
    guard = 4000
    while not m.dmem[KO] and guard:
        m.frame(0)
        guard -= 1
    assert guard, "the clock never decided"
    assert m.dmem[RT] == 0
    assert m.dmem[WIN] == 1 and m.dmem[PRW] == 1, \
        "the health lead did not take the timed-out round"


def test_hitstop_pauses_the_clock():
    """The connect freezes the world, and the world includes the clock."""
    m = vm.VM(asm.assemble(CART))
    for f in range(600):
        m.frame(spec.PAD_RIGHT | spec.PAD_A)
        if m.dmem[35]:                         # HST
            break
    else:
        raise AssertionError("no hit connected")
    rt = m.dmem[RT]
    while m.dmem[35]:
        m.frame(0)
        assert m.dmem[RT] == rt, "the clock ran during hitstop"
