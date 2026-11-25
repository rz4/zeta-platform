"""TND layer 14, the yard styled (TND-PORT P97): how a body takes a blow -- the fall by what put it down, a hook's
turn, the wall. The yard's own tests (tests/test_tnd_yard.py) are layer 13's, which is built as it was."""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import test_tnd_yard as Y13                                    # noqa: E402  (its room, its helpers)
from zeta import gpu, spec                                     # noqa: E402

CART = ROOT / "build" / "layer14" / "tnd.zol"
X, Yb, B, R, D = spec.PAD_X, spec.PAD_Y, spec.PAD_B, spec.PAD_R, spec.PAD_DOWN
pytestmark = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "falls_190.npz").is_file(), reason="tools/tnd_falls.py has not been run")


@pytest.fixture(scope="module")
def cart():
    if not CART.is_file() or CART.stat().st_mtime < Y13.GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="14")
        for k in ("TND_SONG", "TND_OUT", "TND_CROWD", "TND_CARTMESH", "TND_AT"):
            env.pop(k, None)
        subprocess.run([sys.executable, str(Y13.GEN)], check=True, env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    return CART


@pytest.fixture(autouse=True)
def no_paint(monkeypatch):
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)


def _before_him(cart, v0=0.0, u0=0.0, hp=None):
    """the elite a pace before him, the rest away"""
    y = Y13.Yard(cart)
    g = y.g
    y.who(3)
    for k in range(7):
        Y13._stand(y, k, 28.0 - k, -15.0)
    Y13._stand(y, 0, u0, v0 + 1.1)
    y.put(u0, v0, 256)
    for _ in range(5):
        g.step(0)
    if hp:
        g.d[g.syms["e0_hp"]] = hp
    return y, g


def _play(y, g, keys):
    """-> the frame it went down (or None), how far it went from where it stood, what was seen of it while held"""
    v0, down, struck = y.body(0), None, set()
    for i, q in enumerate(keys):
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
        if down is None and g.cell("e0_st") == 2:
            down = i
        if g.cell("e0_stun"):
            struck.add(g.cell("yard_struck"))
    v1 = y.body(0)
    return down, float(np.hypot(v1[0] - v0[0], v1[1] - v0[1])), struck


def test_a_body_goes_down_by_what_put_it_down(cart):
    """P97 ("hyperviolent is not just gore, its about making the fighting correagraphy be hyperviolent"): every body
    went down the one way, thrown back. Now a light blow or a round to the HEAD drops it where it stood (1), to the
    BODY folds it onto its knees and its face (2), to the LEGS cuts it down (3); a heavy blow throws it (0) as it
    did -- and what drops, folds or is cut down stays where it stood"""
    aim_low = [R] * 12 + [R | D] * 3 + [R] * 4 + [R | B] * 3 + [R] * 60
    for name, keys, want, hp in (("a jab, to its head", [X] * 3 + [0] * 60, 1, 1), ("a round, to its body", [B] * 3 + [0] * 60, 2, 1),
                                 ("a round, to its legs", aim_low, 3, 1), ("a charged round", [R | B] * 70 + [R] * 60, 0, None)):
        y, g = _before_him(cart, hp=hp)
        down, went, _ = _play(y, g, keys)
        assert down is not None, f"{name}: it did not go down"
        assert g.cell("yard_fall") == want, f"{name}: fell as {g.cell('yard_fall')}, not {want}"
        if want:
            assert went < 0.5, f"{name}: it went {went:.2f} from where it stood"
        else:
            assert went > 0.8, f"{name}: thrown, it went only {went:.2f}"


def test_a_hook_turns_it_and_a_jab_does_not(cart):
    """P97: a hook landed is a hook's reaction -- the head and shoulders turned away from the hand (2 the lead's,
    3 the rear's); a jab is the chin taken back, as it was"""
    y, g = _before_him(cart)
    assert _play(y, g, [Yb] * 3 + [0] * 50)[2] == {spec_move("lead_hook")}
    y, g = _before_him(cart)
    assert _play(y, g, [X] * 3 + [0] * 30)[2] == {0}


def spec_move(name):
    return {"lead_hook": 2, "rear_hook": 3}[name]


def test_the_wall_strikes_a_body_sent_into_it(cart):
    """P97: a body a blow sends along the floor into a wall, still moving, is STRUCK by the wall: one more off it,
    its chin back and held, the lens shaken -- and if that is the last of it, it folds off the wall. A jab sends
    nothing that far; in the open nothing strikes it"""
    def hits(keys, v0, hp=None):
        y, g = _before_him(cart, v0=v0, u0=-10.0, hp=hp)
        seen, last, shook = [], g.cell("e0_hp"), 0
        for q in keys:
            g.d[g.syms["p_hp"]] = 140
            g.step(q)
            if g.cell("e0_hp") != last:
                last = g.cell("e0_hp")
                seen.append((last, g.cell("yard_struck"), g.cell("e0_stun"), g.cell("f_shake")))
        return seen, g
    hook, jab = [Yb] * 3 + [0] * 70, [X] * 3 + [0] * 70
    by_wall, g = hits(hook, 13.7)
    assert len(by_wall) == 2 and by_wall[1][0] == by_wall[0][0] - 1, f"a hook by the wall: {by_wall}"
    assert by_wall[1][1] == 0 and by_wall[1][2] >= 20 and by_wall[1][3] >= 8, f"the wall's blow: {by_wall[1]}"
    assert g.cell("e0_st") == 1
    last, g = hits(hook, 13.7, hp=4)
    assert last[-1][0] == 0 and g.cell("e0_st") == 2 and g.cell("yard_fall") == 2, f"the wall took the last of it: {last}"
    assert len(hits(jab, 13.7)[0]) == 1, "a jab by the wall"
    assert len(hits(hook, 0.0)[0]) == 1, "a hook in the open"


# ---- P98: on a body that is down; rounds; bodies into bodies ---------------------------------------------------------
TRIP = [R] * 12 + [R | D] * 3 + [R] * 4 + [R | B] * 3 + [R] * 22      # R, the spot to its legs, a round: it is down


def _chosen_and_down(cart):
    """the elite before him, chosen (R held), its legs shot from under it: down, not out, and still his"""
    y, g = _before_him(cart)
    for q in TRIP:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
    assert g.cell("e0_st") == 2 and g.cell("e0_hp") > 0 and g.cell("locked") and not g.cell("yard_out"), \
        (g.cell("e0_st"), g.cell("e0_hp"), g.cell("locked"), g.cell("yard_out"))
    return y, g


def test_r_keeps_a_body_that_is_down_and_his_heel_is_for_it(cart):
    """P98, P99 ("the down stomp and ground gun execution should be only on targetted enemies"): the body he has
    chosen stays his when it goes down (R took only one that stood, and let it go as it fell). A jab at it there is
    the STOMP -- the jab's frames in the stomp's poses, his own bank's, after every pose the yard has; no step in;
    two off it; it bucks where it lies and is not stood up to fall again"""
    y, g = _chosen_and_down(cart)
    u0, hp, t0, poses, jolt = y.uv(), g.cell("e0_hp"), g.cell("e0_t"), set(), set()
    for q in [R | X] * 3 + [R] * 14:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
        if g.cell("anim") == 2 and g.cell("yard_stomp"):
            poses.add(g.cell("pose"))
        jolt.add(g.cell("yard_jolt"))
    assert poses and min(poses) >= 1362, f"his poses in the blow: {sorted(poses)[:4]}"
    assert g.cell("e0_hp") == hp - 2 and jolt >= {6, 3}, (g.cell("e0_hp"), hp, sorted(jolt))
    assert np.hypot(y.uv()[0] - u0[0], y.uv()[1] - u0[1]) < 0.05, "he stepped in"
    assert g.cell("e0_t") > t0, "it was stood up to fall again"


def test_the_gun_goes_down_to_the_body_he_has_chosen(cart):
    """P98, P99: the spot on a chosen body that is DOWN is the body on the floor -- he hinges over it, and the round
    lands on it where it lies"""
    y, g = _chosen_and_down(cart)
    hp, bend = g.cell("e0_hp"), []
    for q in [R | B] * 12 + [R] * 10:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
        bend.append(g.cell("aim_bend"))
    assert max(bend) > 90, f"his bend at most {max(bend)}"
    assert g.cell("e0_hp") < hp, "the round did not land on it"


def test_unchosen_a_body_that_lies_is_not_stomped_or_shot_down_at(cart):
    """P99: with nothing chosen, X over a body that lies is the jab and the gun is level, as they were"""
    y, g = _before_him(cart, hp=1)
    for q in [X] * 3 + [0] * 40:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
    assert g.cell("e0_st") == 2
    stomp, bend = set(), []
    for q in [X] * 3 + [0] * 22 + [B] * 14 + [0] * 20:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
        stomp.add(g.cell("yard_stomp"))
        bend.append(abs(g.cell("aim_bend")))
    assert stomp == {0} and max(bend) < 20, (sorted(stomp), max(bend))


def test_a_shot_after_a_stomp_is_the_guns_own_pose(cart):
    """P99 (the player, P98 on glass: "visual bug on the gun firing"; his tape: his pose in a shot 1,479 to 1,484 of a
    bank of 1,397): whether a blow was the stomp was asked on the swing's first frame by its count, and a shot from
    a gun already up begins some frames in -- the last stomp's answer stood. Every pose of a shot is the gun's"""
    y, g = _chosen_and_down(cart)
    for q in [R | X] * 3 + [R] * 25:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
    worst = 0
    for q in ([B] * 14 + [0] * 30) * 2:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
        worst = max(worst, g.cell("pose"), g.cell("aim_upose"))
    assert worst < 1362, f"a pose of the shot was {worst}"


def test_out_is_not_down(cart):
    """P99 ("it would be good to have a death animation and spawn the enemy at its origin, that way we can tell the
    difference of when they are down or out"): a body with something left is DOWN -- its own colour, up again where
    it lies. One with nothing left is OUT: dark from the blow, one last spasm when its fall is done, let go by R,
    and after its count it is at its MARK, standing, whole"""
    y, g = _chosen_and_down(cart)                # down, not out
    place = y.body(0)
    for _ in range(200):
        g.d[g.syms["p_hp"]] = 140
        g.step(R)
        if g.cell("e0_st") == 1:
            break
    assert g.cell("e0_st") == 1 and not g.cell("yard_out") and np.hypot(y.body(0)[0] - place[0], y.body(0)[1] - place[1]) < 0.3, \
        "down, it did not get up where it lay"
    y, g = _before_him(cart)                     # out: a charged round takes all of it, and throws it from its mark
    mark = y.body(0)
    spasm, frames, lay = False, 0, None
    for q in [R | B] * 70 + [R] * 300:
        g.d[g.syms["p_hp"]] = 140
        g.step(q)
        if g.cell("e0_st") == 2:
            frames += 1
            lay = y.body(0)
            # (dark, and let go, once the world moves again: the blow's own stop comes first)
            assert frames < 24 or g.cell("yard_out") & spec.OBJ_OTINT, "out, it is not dark"
            assert not (g.cell("locked") and frames > 24), "R kept a body that was out"
            spasm |= g.cell("yard_jolt") > 0
        elif frames:
            break
    assert spasm and 100 < frames < 170, (spasm, frames)
    assert np.hypot(lay[0] - mark[0], lay[1] - mark[1]) > 0.5, "it was not thrown from its mark"
    assert g.cell("e0_st") == 1 and g.cell("e0_hp") == 8 and not g.cell("yard_out")
    assert np.hypot(y.body(0)[0] - mark[0], y.body(0)[1] - mark[1]) < 0.01, f"it is at {y.body(0)}, its mark {mark}"


def test_a_rounds_jolt_is_its_own_and_takes_a_side_each(cart):
    """P98 (a distinct jolt for each round): a round's reaction is not a fist's -- 4 and 5 high, 6 and 7 low -- and
    rounds landing one after another throw the body one way, then the other"""
    y, g = _before_him(cart, hp=99)
    kinds = []
    for q in ([B] * 3 + [0] * 20) * 4:
        g.d[g.syms["p_hp"]] = 140
        was = g.cell("e0_hp")
        g.step(q)
        if g.cell("e0_hp") < was:
            kinds.append(g.cell("yard_struck"))
    assert len(kinds) >= 3 and all(4 <= k <= 7 for k in kinds), kinds
    assert all(a != b for a, b in zip(kinds, kinds[1:])), f"the same side twice running: {kinds}"


def test_a_body_thrown_into_another_takes_it_off_its_feet(cart):
    """P98 (bodies thrown into each other): the elite, thrown by a charged round into one of the horde standing a
    pace behind it -- that one takes one, is cut down, and has some of the throw; standing clear, nothing"""
    def thrown(v_other):
        y, g = _before_him(cart)
        Y13._stand(y, 3, 0.0, v_other)
        hp, down = g.cell("e3_hp"), 0
        for q in [R | B] * 70 + [R] * 60:
            g.d[g.syms["p_hp"]] = 140
            g.step(q)
            down |= g.cell("e3_st") == 2
        return hp - g.cell("e3_hp"), down, g.cell("yard_fall", 3), y.body(3)[1] - v_other
    took, down, fall, moved = thrown(1.3)
    assert took == 1 and down and fall == 3 and moved > 0.05, (took, down, fall, moved)
    assert thrown(4.5)[:2] == (0, 0), "a body standing clear of the throw"


# ---- P100: layer 15, the palace ---------------------------------------------------------------------------------------
PALACE = ROOT / "build" / "layer15" / "tnd.zol"


@pytest.fixture(scope="module")
def palace():
    if not PALACE.is_file() or PALACE.stat().st_mtime < Y13.GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="15")
        for k in ("TND_SONG", "TND_OUT", "TND_CROWD", "TND_CARTMESH", "TND_AT"):
            env.pop(k, None)
        subprocess.run([sys.executable, str(Y13.GEN)], check=True, env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    return PALACE


def test_the_palaces_floors(palace):
    """P100 ("im thinkig bloody palace kind of like dmc" -- "when last enemy dies the floor resets, a blinding white
    light, and more enemies are added"): the first floor stands two up and they come for him; what is out is gone;
    with the last one gone the glass goes white and the next floor stands one more, to all seven"""
    sys.path.insert(0, str(ROOT / "experiments" / "park"))
    import bot
    g = bot.Park(palace)
    for _ in range(8):
        g.step(0)
    up = lambda: [g.cell(f"e{k}_st") for k in range(7)]
    assert g.cell("palace_floor") == 1 and sum(up()) == 2, (g.cell("palace_floor"), up())
    hp = g.cell("p_hp")
    for _ in range(900):
        g.step(0)
    assert g.cell("p_hp") < hp, "nobody came for him in fifteen seconds"
    for floor in range(2, 9):
        for k in range(7):                       # (everybody on the floor, put out)
            if g.cell(f"e{k}_st"):
                g.d[g.syms[f"e{k}_hp"]], g.d[g.syms[f"e{k}_st"]], g.d[g.syms[f"e{k}_t"]] = 0, 2, 0
        white = 0
        for _ in range(200):
            g.d[g.syms["p_hp"]] = 140
            g.step(0)
            white = max(white, g.d[spec.CO_BASE + 1 + 3 * spec.CO_STRIDE + 2] >> 24)
            if g.cell("palace_floor") == floor and not g.cell("palace_light"):
                break
        assert g.cell("palace_floor") == floor and sum(1 for s_ in up() if s_) == min(floor + 1, 7), (floor, g.cell("palace_floor"), up())
        assert white == 16, f"the light at its most {white} of 16"


def _palace_bot(palace):
    sys.path.insert(0, str(ROOT / "experiments" / "park"))
    import bot
    g = bot.Park(palace)
    for _ in range(8):
        g.step(0)
    return g


def _clear_floor(g):
    floor = g.cell("palace_floor")
    for k in range(7):
        if g.cell(f"e{k}_st"):
            g.d[g.syms[f"e{k}_hp"]], g.d[g.syms[f"e{k}_st"]], g.d[g.syms[f"e{k}_t"]] = 0, 2, 0
    for _ in range(200):
        g.d[g.syms["p_hp"]] = 140
        g.step(0)
        if g.cell("palace_floor") == floor + 1 and not g.cell("palace_light"):
            return


def _die(g):
    """he stands with nothing left until something strikes him, and lies past the beat"""
    for _ in range(1800):
        g.d[g.syms["p_hp"]] = min(g.cell("p_hp"), 1)
        g.step(0)
        if g.cell("f_dead") > 50:
            return
    raise AssertionError("nobody struck him down in half a minute")


def test_past_the_sixth_floor_they_are_quicker_and_tougher(palace):
    """P101 ("a combo of both"): from the seventh floor every size is quicker, its tell and its wait shorter, and every
    body a quarter of its whole tougher a floor; a new run begins from the rows as they were"""
    g = _palace_bot(palace)
    a = g.syms["yard_sizes"]
    row0 = [g.d[a + i] for i in range(28)]
    for _ in range(9):
        _clear_floor(g)
    assert g.cell("palace_floor") == 10
    assert g.d[a] > row0[0] and g.d[a + 1] < row0[1] and g.d[a + 2] < row0[2], (row0[:3], [g.d[a + i] for i in range(3)])
    whole = dict(enumerate([8, 5, 3, 3, 3, 3, 12]))
    hp = [g.cell(f"e{k}_hp") for k in range(7)]
    assert all(h > whole[k] for k, h in enumerate(hp)), hp
    _die(g)
    for i in range(80):
        g.step(spec.PAD_A if i % 10 < 3 else 0)
    assert g.cell("palace_floor") == 1 and g.cell("palace_best") == 10
    assert [g.d[a + i] for i in range(28)] == row0, "a new run did not begin from the rows as they were"


def test_dying_shows_the_floor_and_a_new_run_begins(palace):
    """P101 ("a score upon death"): down past the beat the glass says FLOOR and the floor he reached; A is a new run
    from the first floor, his health whole, the meter at nothing"""
    g = _palace_bot(palace)
    _clear_floor(g)
    _clear_floor(g)
    _die(g)
    assert g.cell("f_dead") > 46
    seen = [g.d[spec.DL_BASE]]
    assert seen[0] >= 2 * 18, f"the death screen drew {seen[0]} triangles"
    for i in range(60):
        g.step(spec.PAD_A if i % 10 < 3 else 0)
    assert g.cell("f_dead") == 0 and g.cell("palace_floor") == 1 and g.cell("p_hp") == 140 and g.cell("s_pts") == 0


def test_the_palace_pays_the_rank(palace):
    """P101: the rank (exp/rank's P94) is the palace's: a blow that lands pays the meter"""
    g = _palace_bot(palace)
    paid = 0
    for i in range(900):
        g.d[g.syms["p_hp"]] = 140
        g.step(spec.PAD_X if (i // 4) % 6 == 0 else 0)
        paid = max(paid, g.cell("s_pts"))
    assert paid > 0, "nothing paid the meter in fifteen seconds of jabs"
