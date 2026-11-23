"""TND's lab, P46 (docs/TND-PORT.md): WHERE IT LANDS.

The player, 2026-11-23: "use the zeta see where the hits and shots land. make
the damagae and reaction to the hit be based on where it lands. also the gun
shooting needs to be made more sleak and sexy. a gun in hand with the aim at
an angle when lookuing up and down. The goal is to make it easier to land the
shot where it needs to either punch or gunshot."

A body is three parts by the height a fist or a round meets it at, above its
own feet. The spot chosen under the lock is a height ON the target; his upper
half bends at the waist to it; the round flies the line from his hand to it.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_tnd_lab import B, CLONE, D, R, U, X, Y, Game, no_paint, pytestmark, text  # noqa: E402,F401

HEAD, BODY, LEGS = 0, 1, 2
ONE = 65536


def locked(text, gap=4.0, spot=BODY):
    g = Game(text)
    g.at_the_clone(gap)
    g.run(R, 12)
    assert g.cell("locked") == 1 and g.cell("t_sel") == CLONE
    for _ in range(abs(spot - BODY)):
        g.run(R | (U if spot < BODY else D), 2)
        g.run(R, 2)
    assert g.cell("t_spot") == spot
    return g


@pytest.mark.parametrize("spot,height,took,held", [(HEAD, 1.30, 2, 24), (BODY, 0.95, 1, 12), (LEGS, 0.40, 1, 36)])
def test_a_locked_round_lands_on_the_spot_and_does_what_that_part_does(text, spot, height, took, held):
    g = locked(text, 4.0, spot)
    hp = g.cell("e6_hp")
    g.run(R | B, 6)
    assert abs(g.cell("aim_tgt_y") - round(height * ONE)) < 300
    ys, stun = set(), 0
    for _ in range(30):
        g.run(R, 1)
        ys |= {g.cell(f"bul{i}_y") for i in (0, 1) if g.cell(f"bul{i}_rem") > 0}
        stun = max(stun, g.cell("e6_stun"))
    assert ys and all(abs(y - round(height * ONE)) < 300 for y in ys), "the round did not fly to the spot's height"
    assert g.cell("aim_zone") == spot
    assert hp - g.cell("e6_hp") == took and abs(stun - held) <= 2, f"it took {hp - g.cell('e6_hp')} and was held {stun}"


def test_the_round_flies_the_line_from_his_hand(text):
    g = locked(text, 6.0, HEAD)
    g.run(R | B, 12)
    hand = g.cell("aim_hand", 1)
    assert g.cell("aim_hand_on") == 1
    g.run(R, 2)
    slot = next(i for i in (0, 1) if g.cell(f"bul{i}_rem") > 0)
    want = (g.cell(f"bul{slot}_y") - hand) / g.cell("ray_len")
    assert abs(g.cell("aim_slope", slot) / ONE - want) < 0.01, "the slope is not rise over run"
    assert 0.02 < g.cell("aim_slope", slot) / ONE < 0.2


def test_a_round_with_no_lock_goes_level_from_his_hand_and_meets_the_body(text):
    g = Game(text)
    g.at_the_clone(4.0)
    hp = g.cell("e6_hp")
    g.run(B, 6)
    g.run(0, 30)
    assert hp - g.cell("e6_hp") == 1 and g.cell("aim_zone") == BODY
    over = Game(text)                                         # the same round, the body thrown two units up: it passes under
    over.at_the_clone(4.0)
    over.poke("lab_ey", 2 * ONE, CLONE)
    over.poke("lab_evy", int(0.1 * ONE), CLONE)
    hp = over.cell("e6_hp")
    over.run(B, 6)
    over.run(0, 8)
    assert over.cell("e6_hp") == hp, "a level round struck a body whose feet were over it"


def test_locked_the_round_follows_a_body_into_the_air(text):
    g = locked(text, 4.0, BODY)
    g.poke("lab_ey", 2 * ONE, CLONE)
    g.poke("lab_evy", int(0.1 * ONE), CLONE)
    hp = g.cell("e6_hp")
    g.run(R | B, 6)
    assert g.cell("aim_tgt_y") > 2.5 * ONE
    g.run(R, 8)
    assert hp - g.cell("e6_hp") >= 1, "the locked round did not reach the thrown body"


def test_his_waist_bends_to_the_spot(text):
    for spot, bend in ((HEAD, -16), (BODY, 0), (LEGS, 84)):   # his fists
        g = locked(text, 2.0, spot)
        g.run(R, 30)
        assert g.cell("aim_bend") == bend
    up, down = locked(text, 3.0, HEAD), locked(text, 3.0, LEGS)   # the gun: the slope from his hand
    up.run(R | B, 30)
    down.run(R | B, 30)
    assert up.cell("aim_bend") < -8 and down.cell("aim_bend") > 30
    assert down.cell("aim_hand", 1) < up.cell("aim_hand", 1) - int(0.15 * ONE), "his hand did not go down with his aim"
    free = Game(text)
    free.at_the_clone(3.0)
    free.run(B, 30)
    assert free.cell("aim_bend") == 0 and free.cell("aim_hand_on") == 1
    free.run(0, 40)
    assert free.cell("aim_hand_on") == 0, "the gun is still in his hand with B up"


def test_a_fist_does_what_the_part_it_meets_does(text):
    def blow(spot, pads, move):
        g = Game(text)
        g.at_the_clone()
        g.run(R, 12)
        for _ in range(abs(spot - BODY)):
            g.run(R | (U if spot < BODY else D), 2)
            g.run(R, 2)
        g.run(R, 24)
        hp, lean = g.cell("e6_hp"), 0
        for pad, n in pads:
            g.run(R | pad, n)
        zone = fy = None
        for _ in range(40):
            before = g.cell("e6_hp")
            g.run(R, 1)
            lean = max(lean, g.cell("lab_tilt", CLONE))
            if g.cell("e6_hp") < before and g.cell("f_mv") == move:
                zone, fy = g.cell("aim_zone"), g.cell("f_fy") / ONE
        return zone, fy, hp - g.cell("e6_hp"), lean
    zone, fy, took, lean_head = blow(BODY, [(Y, 3)], 2)       # the lead hook as it was drawn: at the head
    assert zone == HEAD and fy > 1.18 and took == 3
    zone, fy, took, lean_body = blow(LEGS, [(Y, 3)], 2)       # ...bent low: into the body
    assert zone == BODY and 0.70 < fy < 1.18 and took == 2
    assert lean_head > lean_body + 20, "the head did not snap back"
    assert blow(BODY, [(X, 3)], 0)[::2] == (HEAD, 1), "a jab at the head is not one"


def test_a_charged_round_at_the_legs_takes_them_from_under_it_and_it_gets_up_with_what_it_had(text):
    g = locked(text, 4.0, LEGS)
    hp = g.cell("e6_hp")
    g.run(R | B, 30)
    down = False
    for _ in range(40):
        g.run(R, 1)
        down |= g.cell("e6_st") == 2
    assert down, "it kept its feet"
    left = g.cell("e6_hp")
    assert 0 < left < hp
    g.run(0, 60)
    assert g.cell("e6_st") == 1 and g.cell("e6_hp") == left, "it got up healed"


# ---- P47: the lock's mark is a red outline; a locked round always lands ----

def test_the_locks_mark_is_a_red_outline_and_nothing_more(text):
    from zeta import spec
    g = locked(text, 4.0, HEAD)
    g.run(R | B, 20)                                          # (slowed: the sight is drawn too)
    assert g.d[spec.EDGE_RGB] == 0xE01818
    aware = g.sym("aware")
    n = g.d[spec.OL_BASE]
    rows = [g.d[spec.OL_BASE + 1 + i * spec.OL_STRIDE: spec.OL_BASE + 1 + (i + 1) * spec.OL_STRIDE] for i in range(n)]
    assert all(r[0] != aware for r in rows), "the diamond is still drawn"
    assert sum(1 for r in rows if r[5] & spec.OBJ_EDGE) == 2, "the clone's two halves are not the outlined ones"
    assert abs(g.cell("lab_dot", 2)) * 2 < abs(g.cell("dot_m", 2)), "the point where it will land is no smaller"
    lasers = {g.sym(f"lab_laser{k}") for k in range(7)}
    assert not any(r[0] == g.sym("bead_m") for r in rows) and any(r[0] in lasers for r in rows), "the sight is not the laser"


@pytest.mark.parametrize("spot,took", [(HEAD, 2), (LEGS, 1)])
def test_a_locked_round_lands_wherever_the_body_has_got_to(text, spot, took):
    g = locked(text, 6.0, spot)
    hp = g.cell("e6_hp")
    g.run(R | B, 6)
    for _ in range(8):
        g.run(R, 1)
        if any(g.cell(f"bul{i}_rem") > 0 for i in (0, 1)):
            break
    assert any(g.cell(f"bul{i}_rem") > 0 for i in (0, 1)), "no round is in the air"
    g.poke("lab_ey", int(1.4 * ONE), CLONE)                   # it is thrown up under the round
    g.poke("lab_evy", int(0.05 * ONE), CLONE)
    g.run(R, 12)
    assert hp - g.cell("e6_hp") == took and g.cell("aim_zone") == spot, "a round fired locked did not land on what he chose"
    assert g.cell("spark", 1) > int(1.5 * ONE), "its burst is not on the body where the body now is"


def test_the_laser_runs_from_his_hand_to_where_the_round_will_land(text):
    """P47: "are we able to do a laser sight? like a line to the target?" -- laid from pieces, in running time too"""
    from zeta import spec
    for spot in (HEAD, LEGS):
        g = locked(text, 5.0, spot)
        g.run(R | B, 5)
        assert g.cell("slow_on") == 0, "the test means to look in running time"
        g.run(R | B, 1)
        n = g.d[spec.OL_BASE]
        rows = [g.d[spec.OL_BASE + 1 + i * spec.OL_STRIDE: spec.OL_BASE + 1 + (i + 1) * spec.OL_STRIDE] for i in range(n)]
        length = {g.sym(f"lab_laser{k}"): 8.0 / 2 ** k for k in range(7)}
        beam = [(r, length[r[0]]) for r in rows if r[0] in length]
        assert beam, "no laser"
        s32 = lambda v: v - (1 << 32) if v & (1 << 31) else v      # noqa: E731
        first, (last, last_len) = beam[0][0], beam[-1]
        hand = [g.cell("aim_hand", k) for k in range(3)]
        assert all(abs(s32(first[1 + k]) - hand[k]) < 2000 for k in range(3)), "the laser does not begin at his hand"
        run = sum(ln for _, ln in beam)
        assert abs(run - g.cell("ray_len") / ONE) < 0.2 + 0.02 * run, f"the laser is {run} long; the line {g.cell('ray_len') / ONE}"
        ys = [s32(r[2]) for r, _ in beam]
        assert (ys == sorted(ys)) if spot == HEAD else (ys == sorted(ys, reverse=True)), "the laser does not climb to the head or fall to the knee"
        end_y = ys[-1] + (g.cell("aim_tgt_y") - hand[1]) * last_len / (g.cell("ray_len") / ONE) / 1
        assert abs(end_y - g.cell("aim_tgt_y")) < int(0.08 * ONE), "the laser does not end on the spot"
