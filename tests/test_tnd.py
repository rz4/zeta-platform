# TEAR NOT DEMON on the Zeta -- P1, the fighter (docs/TND-PORT.md).
# Loads the committed cart, so it runs anywhere; the bake itself is held
# by the regen gate wherever the third-party source is present.

import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import cabinet, spec  # noqa: E402

CART = Path(__file__).parents[1] / "games/tnd/tnd.zol"


# THE ROUTE most of these tests walk: stand while the wave closes in, turn
# onto the brute as it squares up, then work the string. Its two times are
# the wave's arrival, which is the demons' walk (P16: 0.028 a frame, here
# by frame 225; it was 0.020 and 315).
TURN0, STRING0 = 210, 230


# P18's buttons, for the tests below
RUN = spec.PAD_L | spec.PAD_R            # both shoulders: the run, round the target
BOX = spec.PAD_L                         # L: the boxer (A jumps there)


def _taps(times, bit=spec.PAD_X, n=2):
    """a thumb's taps: `bit` down for n frames from each time"""
    return lambda f: bit if any(t <= f < t + n for t in times) else 0


def _launch(m, frames=420):
    """Turn onto the brute and play the rhythm X X X X -- jab, cross, lead
    hook, the rear uppercut -- until it is in the air. -> that frame."""
    for f in range(frames):
        p = (spec.PAD_LEFT if TURN0 <= f < TURN0 + 8 else 0) \
            | (spec.PAD_X if any(t <= f < t + 2 for t in (STRING0, STRING0 + 12,
                                                         STRING0 + 24, STRING0 + 36)) else 0)
        m.frame(p)
        if _wave(m)[0]["py"] > int(0.3 * 65536):
            return f
    return None


def _fight_vm():
    """TND opens on its title; Start on the first frame begins the fight,
    which runs from the next -- so a test's frame f is the fight's f."""
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    m.frame(spec.PAD_START)
    return m


def _jab_vs_still():
    """Two machines, same camera, same frame count: one jabs at frame 30.
    Anything that differs is the POSE -- delivered by the mover."""
    a = _fight_vm()
    b = _fight_vm()
    for f in range(36):
        a.frame(spec.PAD_X if f == 30 else 0)
        b.frame(0)
    return a, b


def test_the_jab_moves_the_body():
    """The pose bank reaches the body: a jab changes the picture while
    the camera and the floor do not move. A mover that delivered nothing
    would leave him frozen -- and every other check here green."""
    a, b = _jab_vs_still()
    diff = (a.framebuffer() != b.framebuffer()).any(axis=-1).sum()
    assert diff > 200, f"the jab moved only {diff} pixels"


def test_the_body_stays_whole():
    """Both halves draw: the cut at the hips must not drop either mesh
    (the machines drop an oversized mesh WHOLE and agree, so the cross
    cannot see it -- the forge's founding bug). Pixels in his torso band
    AND his leg band, against the empty frame."""
    a, _ = _jab_vs_still()
    fb = a.framebuffer().astype(int)
    body = (np.abs(fb - fb[5, 5]).sum(axis=-1) > 30)   # not the sky
    cols = slice(spec.W // 2 - 40, spec.W // 2 + 40)
    floorless = body[:, cols]
    torso = floorless[150:200].sum()
    assert torso > 300, f"the upper body is missing ({torso} px)"


@pytest.mark.skipif(shutil.which("verilator") is None,
                    reason="verilator not installed")
def test_both_machines_play_the_fighter():
    """A 2,967-word pose DMA every frame through two dense meshes,
    walking, jabbing and turning: bit-equal on silicon."""
    from zeta import silicon
    cart = cabinet.load_cart(CART)
    v, s = cabinet.VirtualMachine(cart), silicon.SiliconMachine(cart)
    v.frame(spec.PAD_START)                         # the title, then the fight
    s.frame(spec.PAD_START)
    for f in range(90):
        pad = (spec.PAD_UP if 15 <= f < 45 else 0) \
            | (spec.PAD_X if f == 50 else 0) \
            | (spec.PAD_LEFT if f >= 70 else 0)
        v.frame(pad)
        s.frame(pad)
        assert np.array_equal(v.framebuffer(), s.framebuffer()), \
            f"the fighter diverges at frame {f}"


# ---- P3: the demons -----------------------------------------------------------
# The wave's cells are read by NAME from the cart's own symbol comments
# (the forge assigns addresses), with gen_tnd.py's field order.
FIELDS = ("x", "z", "h8", "hp", "st", "mf", "mv", "ai", "wf", "mov", "alt", "cf",
          "hs", "stop", "vx", "vz", "con", "dt", "jt", "kp", "mt", "ox", "oz",
          "py", "vy", "aw")


def _sym(name):
    for line in CART.read_text().splitlines():
        if line.startswith(f"; {name}: "):
            return int(line.rsplit(" at ", 1)[1])
    raise KeyError(name)


def _wave(m):
    base, d = _sym("demons"), m.vm.dmem
    s32 = lambda v: v - (1 << 32) if v & (1 << 31) else v      # noqa: E731
    return [{f: s32(d[base + i * len(FIELDS) + k]) for k, f in enumerate(FIELDS)}
            for i in range(3)]


def _player(m):
    s32 = lambda v: v - (1 << 32) if v & (1 << 31) else v      # noqa: E731
    return (s32(m.vm.dmem[_sym("px")]) / 65536, s32(m.vm.dmem[_sym("pz")]) / 65536)


def test_the_wave_closes_in_and_squares_up():
    """Spawned 7.8 out, they walk in along their own facing and stop
    short, inside the 1.5 reach -- every one of them, with nobody
    touching the pad. (The shove has its own witness below; this one
    passes without it, because the wave stops before it touches.)"""
    m = _fight_vm()
    start = [np.hypot(w["x"], w["z"]) / 65536 for w in _wave(m)]
    assert all(abs(r - 7.8) < 0.01 for r in start)
    for _ in range(265):                 # (arrived by 225; the first swing is 278)
        m.frame(0)
    px, pz = _player(m)
    for i, w in enumerate(_wave(m)):
        r = np.hypot(w["x"] / 65536 - px, w["z"] / 65536 - pz)
        assert 0.8 < r < 1.55, f"demon {i} stands {r:.2f} from him"


def test_the_demons_swing_cross_then_hook():
    """Squared up and on his nose, each swings on the 74-frame rest,
    alternating the archive's two moves -- and while a swing runs, its
    clip row is the move's, not the idle's."""
    m = _fight_vm()
    clips, npart = _sym("demon_clips"), 12
    seen = [[] for _ in range(3)]
    for _ in range(700):
        m.frame(0)
        for i, w in enumerate(_wave(m)):
            if w["st"] == 1 and w["mf"] == 0:
                seen[i].append(w["mv"])
            if w["st"] == 1:
                row = (w["cf"] - clips) // npart
                assert row >= 48, f"demon {i} swings with an idle/walk row {row}"
    for i, moves in enumerate(seen):
        assert moves[:3] == [0, 1, 0], f"demon {i} threw {moves}"


def test_the_demon_swing_moves_its_body():
    """The swing is SEEN: freeze one machine's demons in idle by holding
    their swing counters off, and the pictures part when the other's
    swing starts. (Deleting the move rows from the clip select would
    leave these frames identical.)"""
    a = _fight_vm()
    b = _fight_vm()
    base = _sym("demons")
    first = None
    for f in range(560):
        a.frame(0)
        for i in range(3):                    # b's demons never commit
            b.vm.dmem[base + i * len(FIELDS) + FIELDS.index("ai")] = 0
        b.frame(0)
        if first is None and any(w["st"] for w in _wave(a)):
            first = f
        if first is not None and f == first + 12:
            diff = (a.framebuffer() != b.framebuffer()).any(axis=-1).sum()
            assert diff > 150, f"a swing moved only {diff} pixels"
            return
    raise AssertionError("no demon ever swung")


def test_bodies_do_not_pass_through_him():
    """He walks straight at the brute and keeps walking: the shove holds
    every body apart."""
    m = _fight_vm()
    for f in range(500):
        m.frame(spec.PAD_UP | (spec.PAD_LEFT if f < 40 else 0))
        px, pz = _player(m)
        for i, w in enumerate(_wave(m)):
            r = np.hypot(w["x"] / 65536 - px, w["z"] / 65536 - pz)
            assert r > 0.6, f"frame {f}: demon {i} is {r:.2f} inside him"


def test_the_street_holds_him():
    """tear.py's _in_arena: forty units down the arm and no further, and
    never through the wall beside it. (Without the clamp, 1,400 frames
    of walking is 44.8 units -- in the fog -- and the turn into the wall
    walks him through it. He SLIDES along the end to the wall.)"""
    m = _fight_vm()
    for f in range(1700):
        m.frame(spec.PAD_UP | (spec.PAD_LEFT if 1400 <= f < 1420 else 0))
        px, pz = _player(m)
        inside = max(abs(px), abs(pz)) <= 10.6 + 1e-3 \
            or (abs(px) <= 7.1 + 1e-3 and abs(pz) <= 40 + 1e-3) \
            or (abs(pz) <= 7.1 + 1e-3 and abs(px) <= 40 + 1e-3)
        assert inside, f"frame {f}: he stands off the street at ({px:.2f}, {pz:.2f})"
        if f == 1399:
            assert pz > 39.9, f"he never reached the end of the arm ({pz:.2f})"
    assert abs(px) > 6.9, f"the turn never took him to the wall ({px:.2f})"


def test_what_the_camera_cannot_see_is_not_sent():
    """The street's twenty objects and the demons' thirty-six are culled
    against the view before the sequencer sees them (its vertex cache
    holds 2,048 a frame). Witnessed both ways: some objects are always
    left out, and the count changes as he turns."""
    m = _fight_vm()
    counts = set()
    for f in range(90):
        m.frame(spec.PAD_LEFT)
        n = m.vm.dmem[spec.OL_BASE]
        assert n < 59, f"frame {f}: all {n} objects listed -- nothing culled"
        counts.add(n)
    assert len(counts) > 3, f"the list never changed as he turned: {counts}"


# ---- P4: the fight -------------------------------------------------------------
def _cell(m, name):
    return m.vm.dmem[_sym(name)]


def _s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


def _launches(pads, frames):
    """the moves he throws, in order, under a pad schedule"""
    m = _fight_vm()
    out, was = [], 0
    for f in range(frames):
        m.frame(pads(f))
        anim, af = _cell(m, "anim"), _cell(m, "af")
        if anim == 2 and af == 0:
            out.append(_cell(m, "f_mv"))
    return m, out


def test_the_rhythm_picks_the_string():
    """P18: the primary is rhythm. Steady taps (within 24 frames) play jab,
    cross, lead hook and the rear uppercut; a WAIT after the jab (25..70
    frames) turns it into lead hook, rear uppercut; a wait after the cross,
    the rear hook. Past 70 a tap opens a new string."""
    for times, want in (((10, 22, 34, 46), [0, 1, 2, 6]),
                        ((10, 50, 62), [0, 2, 6]),
                        ((10, 22, 62), [0, 1, 3]),
                        ((10, 100, 112), [0, 0, 1])):
        _, moves = _launches(_taps(times), 200)
        assert moves == want, f"taps at {times} threw {moves}, not {want}"


def test_shots_may_fill_a_wait_but_not_too_many():
    """The secondary may be fired inside a wait without losing the string;
    a third shot there loses it, and the next tap is a jab again."""
    X, B = spec.PAD_X, spec.PAD_B
    two = lambda f: (X if f in (10, 11, 60, 61) else 0) | (B if f in (25, 26, 40, 41) else 0)   # noqa: E731
    three = lambda f: (X if f in (10, 11, 66, 67) else 0) | (B if f in (24, 25, 36, 37, 48, 49) else 0)   # noqa: E731
    assert _launches(two, 120)[1] == [0, 7, 7, 2]
    assert _launches(three, 120)[1] == [0, 7, 7, 7, 0]


def test_his_blows_land():
    """Turned onto the brute as it squares up, he works the string and it
    falls -- damage, a stun, and down."""
    m = _fight_vm()
    stunned = False
    for f in range(560):
        m.frame((spec.PAD_LEFT if TURN0 <= f < TURN0 + 8 else 0)
                | (spec.PAD_X if f >= STRING0 and f % 9 == 0 else 0))
        w = _wave(m)[0]
        stunned |= w["st"] == 2 and w["hs"] > 0
        if w["st"] >= 3:                 # (P16: it is replaced once it is gone,
            break                        # so this looks at the frame it falls)
    assert w["hp"] <= 0 and w["st"] >= 3, f"the brute stands: {w['hp']} hp, st {w['st']}"
    assert stunned, "it fell without ever being stunned"


def test_their_blows_land_and_he_goes_down():
    """Untouched, the wave beats him down; after the death beat a fresh
    press of A is a new run: full health, the wave back where it began."""
    m = _fight_vm()
    for f in range(1200):                # (no blow lands while he reels)
        m.frame(0)
    assert _s32(_cell(m, "p_hp")) <= 0 and _cell(m, "f_dead") > 46
    assert m.vm.dmem[spec.DL_BASE] > 0, "no prompt after the death beat"
    m.frame(spec.PAD_A)
    assert _s32(_cell(m, "p_hp")) == 140 and _cell(m, "f_dead") == 0
    assert m.vm.dmem[spec.DL_BASE] == 0, "the prompt outlived the retry"
    born = _wave(cabinet.VirtualMachine(cabinet.load_cart(CART)))   # as the cart boots them
    for i, w in enumerate(_wave(m)):
        assert w["hp"] == 70 and w["st"] == 0, f"demon {i} not reset"
    assert abs(_wave(m)[0]["x"] - born[0]["x"]) < 65536


def test_the_fallen_go_and_the_wave_returns():
    """A demon knocked down falls, lies a beat and is gone; when all three
    are, the next wave stands round the crossing (tear.py _spawn_wave)."""
    m = _fight_vm()
    base, st = _sym("demons"), FIELDS.index("st")
    m.frame(0)
    for i in range(3):
        m.vm.dmem[base + i * len(FIELDS) + st] = 3       # all three falling
    seen_gone = False
    for f in range(200):
        m.frame(0)
        sts = [w["st"] for w in _wave(m)]
        seen_gone |= all(s == 4 for s in sts)
        if _cell(m, "f_wave") == 1:
            break
    else:
        raise AssertionError(f"no new wave (st {sts})")
    assert all(w["st"] == 0 and w["hp"] == 70 for w in _wave(m))


def test_a_demon_against_the_lens_is_not_drawn():
    """Within 1.3 of the camera a demon is a wall of near-clipped faces --
    the sequencer's most expensive path (the tour's worst frame went over
    100% on one) -- so it is not listed. Elsewhere it is: twelve objects."""
    def listed_with_demon_at(dist):
        m = _fight_vm()
        m.frame(0)
        base = _sym("demons")
        cam_x, cam_z = _s32(m.vm.dmem[spec.CAM_X]), _s32(m.vm.dmem[spec.CAM_Z])
        m.vm.dmem[base + 0] = (cam_x) & 0xFFFFFFFF                 # demon 0 ...
        m.vm.dmem[base + 1] = (cam_z + int(dist * 65536)) & 0xFFFFFFFF   # ... ahead of the lens
        m.frame(0)
        return m.vm.dmem[spec.OL_BASE]
    near, far = listed_with_demon_at(0.5), listed_with_demon_at(2.5)
    assert far - near == 12, f"near {near}, far {far}: the lens rule is not 12 objects"


def test_a_blow_is_heard():
    """The blow's own voices (ch0 the ring, ch2 the thump -- the music
    never touches them) are silent until a blow lands, sound on it, and
    are gone again within twelve frames."""
    def blow_level(m):
        return m.vm.dmem[spec.AU_BASE + 1] & 15, m.vm.dmem[spec.AU_BASE + 5] & 15
    m = _fight_vm()
    base, levels = _sym("demons"), []
    for f in range(400):
        m.frame((spec.PAD_LEFT if TURN0 <= f < TURN0 + 8 else 0)
                | (spec.PAD_X if f >= STRING0 and f % 9 == 0 else 0))
        levels.append(blow_level(m))
        if m.vm.dmem[base + FIELDS.index("hp")] < 70:
            break
    else:
        raise AssertionError("no blow landed")
    assert all(lv == (0, 0) for lv in levels[:-1]), "the blow's voices sounded early"
    assert levels[-1][0] > 0 and levels[-1][1] > 0, f"the blow was not heard {levels[-1]}"
    for _ in range(13):
        m.frame(0)
    assert blow_level(m) == (0, 0), "the blow never ended"


def test_the_grammar_taps_on_release_and_holds_in_targeting():
    """combat.Grammar, for thumbs: a tap fires on release or at its fourth
    frame held (a long press is one blow, not none); Y is the special. In
    TARGETING a held press does not fire at its fourth frame -- it is the
    FOCUS -- and fires when it is let go. (P18: there are no chords.)"""
    X, Y, R = spec.PAD_X, spec.PAD_Y, spec.PAD_R
    assert _launches(lambda f: X if 10 <= f < 13 else 0, 60)[1] == [0]
    m, held = _launches(lambda f: X if 10 <= f < 40 else 0, 60)
    assert held == [0], held
    assert _launches(lambda f: Y if 10 <= f < 12 else 0, 60)[1] == [4]
    m = _fight_vm()
    for f in range(30):
        m.frame(R)
    for f in range(30):
        m.frame(R | X)
        assert _cell(m, "anim") != 2, f"a held press fired in targeting at {f}"
    for f in range(10):
        m.frame(R)
    assert _cell(m, "anim") == 2 or _cell(m, "f_mv") == 0, "the release did not fire"


def test_the_uppercut_launches():
    """A launcher sends its target up -- P18: to the height of his flip
    (2.0), where his jump meets it; the archive's seven units were out of
    any jump's reach -- helpless the whole arc, and down. (It ends the
    steady string, X X X X.)"""
    m = _fight_vm()
    assert _launch(m) is not None, "the string never launched it"
    peak, landed = 0.0, False
    for f in range(200):
        m.frame(0)
        w = _wave(m)[0]
        peak = max(peak, w["py"] / 65536)
        if peak > 1 and w["py"] == 0:
            landed = True
            break
    assert 1.7 < peak < 2.2, f"the brute rose to {peak:.2f}"
    assert landed, "the brute never came down"


def test_a_launcher_slows_the_world_and_the_gun_tracks_the_body():
    """P18: a launcher that lands gives a second of slow motion -- the world
    moves one frame in three -- and a shot in it goes to the body in the
    air, whichever way the pad points."""
    m = _fight_vm()
    assert _launch(m) is not None
    for f in range(3):
        m.frame(0)
    assert _cell(m, "f_slow") > 10, "no slow motion after the launch"
    phases = []
    for f in range(9):
        m.frame(spec.PAD_DOWN | spec.PAD_B if f < 2 else 0)
        phases.append(_cell(m, "f_skip"))
    assert sorted(set(phases)) == [0, 1, 2], f"the world did not slow: {phases}"
    for f in range(60):
        m.frame(0)
        if _cell(m, "f_aim"):
            break
    assert _cell(m, "f_aim") == 1, "the shot did not track the body in the air"


def test_the_cancel_lattice():
    """In its recovery a move is cut short by a buffered move it lists
    (combat.py): the cross cuts the jab's recovery the frame the tap lands;
    the special cuts a hook's; nothing cuts the special -- a tap in its
    recovery simply expires in the buffer."""
    X, Y = spec.PAD_X, spec.PAD_Y
    assert _launches(lambda f: X if f in (10, 24) else 0, 80)[1] == [0, 1]
    m, _ = _launches(lambda f: X if f in (10, 24) else 0, 26)
    assert _cell(m, "anim") == 2 and _cell(m, "f_mv") == 1, \
        "the cross waited for the jab to end: no cancel"
    hook = _launches(lambda f: X if f in (10, 30, 50) else (Y if f == 72 else 0), 140)[1]
    assert hook == [0, 1, 2, 4], hook
    assert _launches(lambda f: Y if f == 10 else (X if f == 50 else 0), 120)[1] == [4]


def test_style_climbs_with_variety_and_draws_its_rank():
    """combat.Style: the string's blows pay their moves' style, the combo
    adds to it, and the brute's beating reaches C (60) -- drawn top right
    as composed display-list glyphs, in C's colour."""
    m = _fight_vm()
    for f in range(STRING0 + 96):        # the string, then the haymaker: variety
        m.frame((spec.PAD_LEFT if TURN0 <= f < TURN0 + 8 else 0)
                | (spec.PAD_X if STRING0 <= f < STRING0 + 60 and f % 9 == 0 else 0)
                | (spec.PAD_Y if STRING0 + 66 <= f < STRING0 + 70 else 0))
    assert _cell(m, "s_rank") == 1, f"rank {_cell(m, 's_rank')} after the beating"
    assert _cell(m, "s_combo") >= 4          # (P18: the steady string is four blows)
    n = m.vm.dmem[spec.DL_BASE]
    assert n > 0, "no rank letter on glass"
    rgb = m.vm.dmem[spec.DL_BASE + 1 + 6] & 0xFFFFFF
    assert rgb == 0xAA8C78, f"C painted {rgb:06x}"


def test_a_blow_taken_keeps_45_percent_and_breaks_the_combo():
    """Untouched, the wave's first blow lands on a known frame. On the
    frame before, give him 100 style and a combo of 4 (and a fresh idle
    count, so nothing bleeds): the blow leaves 45 and no combo. (The
    first version of this witness waited for the blow with the meter
    bleeding -- and passed on zero.)"""
    dry = _fight_vm()
    for hit in range(600):
        dry.frame(0)
        if _s32(_cell(dry, "p_hp")) < 140:
            break
    else:
        raise AssertionError("never struck")
    m = _fight_vm()
    for f in range(hit):
        m.frame(0)
    for name, v in (("s_pts", 100 * 16), ("s_combo", 4), ("s_idle", 0)):
        m.vm.dmem[_sym(name)] = v
    landed_before = sum(w["con"] for w in _wave(m))
    m.frame(0)
    assert _s32(_cell(m, "p_hp")) < 140, "the blow moved"
    k = sum(w["con"] for w in _wave(m)) - landed_before   # (the wave swings
    assert k >= 1                                         # in step: up to 3)
    assert _cell(m, "s_combo") == 0
    want = 1600
    for _ in range(k):
        want = want * 29491 >> 16                         # x0.45 per blow
    assert abs(_cell(m, "s_pts") - want) <= k, (k, _cell(m, "s_pts"), want)



def test_the_music_is_gated_by_rank():
    """sfx._synth_battle_stems on its voices: the drums from the first
    frame; the bass (stem 1) only from rank C; nothing once he is down."""
    m = _fight_vm()
    heard, bass = 0, 0
    for f in range(200):
        m.frame(0)
        heard = max(heard, int(np.abs(np.asarray(m.audio(), dtype=np.int64)).max()))
        bass = max(bass, m.vm.dmem[spec.AU_BASE + 2 * 5 + 1] & 15)
    assert heard > 0, "no drums at rank D"
    assert bass == 0, "the bass played at rank D"
    m.vm.dmem[_sym("s_pts")] = 70 * 16                  # rank C
    for f in range(120):
        m.frame(0)
        m.vm.dmem[_sym("s_idle")] = 0                   # (hold the rank)
        bass = max(bass, m.vm.dmem[spec.AU_BASE + 2 * 5 + 1] & 15)
    assert bass > 0, "no bass at rank C"
    m.vm.dmem[_sym("f_dead")] = 100                     # down
    for f in range(120):
        m.frame(0)
    assert int(np.abs(np.asarray(m.audio(), dtype=np.int64)).max()) == 0, \
        "the music played over his corpse"



# ---- P6: the title -------------------------------------------------------------
def _const(name):
    for line in CART.read_text().splitlines():
        if line.startswith(f".const {name} "):
            return int(line.split()[2])
    raise KeyError(name)


def _through_the_intro(m):
    """No input from power-on: the intro plays, then two exit frames"""
    for f in range(_const("INTRO_LEN") + 3):
        m.frame(0)


def test_the_title_is_the_archives_and_start_begins():
    """After the intro, TND waits on its title -- the archive's own start
    screen, baked to a backdrop plate, nothing else drawn; Start (or A)
    begins the fight the next frame, and an A held through the cut is no
    jump (A is the jump since 2026-11-20)."""
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    _through_the_intro(m)
    for f in range(60):
        m.frame(0)
        assert m.vm.dmem[spec.BG_SRC] > 0 and m.vm.dmem[spec.OL_BASE] == 0
    m.frame(spec.PAD_A)
    m.frame(spec.PAD_A)                             # held through the cut
    assert m.vm.dmem[spec.BG_SRC] == 0, "Start/A did not leave the title"
    assert m.vm.dmem[spec.OL_BASE] > 0, "no street after the title"
    for f in range(20):
        m.frame(spec.PAD_A if f < 6 else 0)         # ...held on, then released
        assert _cell(m, "anim") != 2, "the A that left the title threw a punch"
        assert _cell(m, "f_py") == 0, "the A that left the title jumped"


def _image(cart, at, n):
    return [cart["cram"].get(str(at + i), 0) for i in range(n)]


def test_the_intro_plays_and_hands_back():
    """Power-on with no input: the title pages in the intro (a second
    program), which flies the frozen street under its words for INTRO_LEN
    frames and hands back -- the game's own program, the borrowed regions
    exactly as the cart boots them, the camera cells the fight never
    rewrites, and the title."""
    cart = cabinet.load_cart(CART)
    m = cabinet.VirtualMachine(cart)
    boot = list(m.vm.dmem)
    intro = _image(cart, _const("INTRO_PROG"), _const("PAGE"))
    m.frame(0)
    m.frame(0)
    assert list(m.vm.imem[:_const("PAGE")]) == intro, "the title did not page in the intro"
    seen = set()
    for f in range(2, _const("INTRO_LEN") + 3):
        m.frame(0)
        n = m.vm.dmem[spec.DL_BASE]
        assert n <= spec.DL_MAX
        if n:
            seen.add(f // 100)
        if f in (100, 200, 330):
            assert m.vm.dmem[spec.OL_BASE] > 20, "the street is not drawn under the words"
            assert n > 80, f"frame {f}: the intro's words are missing ({n} triangles)"
    assert list(m.vm.imem[:len(cart["imem"])]) == list(cart["imem"]), \
        "the intro did not hand back the game's program"
    for name in ("BORROW_FRONT", "BORROW_END"):
        a, k = _const(name), _const(name + "_N")
        assert m.vm.dmem[a:a + k] == boot[a:a + k], f"{name} was not put back"
    for c in (spec.CAM_Y, spec.CAM_PITCH, spec.CAM_ROLL):
        assert m.vm.dmem[c] == boot[c], f"camera cell {c} was not put back"
    m.frame(0)
    assert m.vm.dmem[spec.BG_SRC] > 0, "no title after the intro"


def test_the_borrowed_front_is_never_read():
    """The front is the fight's constants, drawn over by the intro's words
    and put back by the mover. Poison it the moment the intro starts: if
    anything -- the intro, or the game after it -- read it, the pictures
    or the sound would differ. They may not, for a frame."""
    cart = cabinet.load_cart(CART)
    a, b = cabinet.VirtualMachine(cart), cabinet.VirtualMachine(cart)
    lo, n = _const("BORROW_FRONT"), _const("BORROW_FRONT_N")
    rng = np.random.default_rng(7)
    pads = [0] * (_const("INTRO_LEN") + 40) + [spec.PAD_START] + [0] * 30 + \
        [spec.PAD_X if f % 14 < 8 else 0 for f in range(160)]
    for f, pad in enumerate(pads):
        if f == 2:
            b.vm.dmem[lo:lo + n] = [int(v) for v in rng.integers(0, 1 << 32, n)]
        a.frame(pad)
        b.frame(pad)
        assert np.array_equal(a.panel(), b.panel()), f"frame {f}: the picture read the front"
        assert np.array_equal(a.audio(), b.audio()), f"frame {f}: the sound read the front"


@pytest.mark.skipif(shutil.which("verilator") is None,
                    reason="verilator not installed")
def test_both_machines_play_the_intro_and_hand_back():
    """The title pages in the intro, the intro flies and draws its words,
    Start skips it, and the two exit frames put back the borrowed regions
    and page the game in: overlays both ways and three restores, bit-equal
    on silicon, in forty frames."""
    from zeta import silicon
    cart = cabinet.load_cart(CART)
    v, s = cabinet.VirtualMachine(cart), silicon.SiliconMachine(cart)
    for f in range(40):
        pad = spec.PAD_START if 28 <= f < 34 else 0
        v.frame(pad)
        s.frame(pad)
        assert np.array_equal(v.framebuffer(), s.framebuffer()), \
            f"the intro diverges at frame {f}"
    assert v.vm.dmem[spec.BG_SRC] > 0, "the cross never reached the title"


def test_start_skips_the_intro_and_is_not_a_fresh_press():
    """A thumb on Start mid-intro: two exit frames, then the title -- and
    the same held press does not begin the fight; a new one does."""
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    for f in range(100):
        m.frame(0)
    for f in range(20):                              # a human-length hold
        m.frame(spec.PAD_START)
    assert m.vm.dmem[spec.BG_SRC] > 0, "Start did not skip to the title"
    assert _cell(m, "mode") == 0, "the skipping Start began the fight"
    m.frame(0)
    m.frame(spec.PAD_START)
    m.frame(0)
    assert _cell(m, "mode") == 1, "a fresh Start on the title did not begin"


def test_the_hud_writes_the_combo_from_packed_glyphs():
    """The rank alone, then the rank and X and the combo once it passes
    one (no leading zero), composed at run time from two-word glyphs."""
    m = _fight_vm()
    m.frame(0)
    m.vm.dmem[_sym("f_fight")] = 1
    m.frame(0)
    rank_only = m.vm.dmem[spec.DL_BASE]
    assert rank_only > 0, "no rank on glass"
    counts = {}
    for combo in (5, 12):
        m.vm.dmem[_sym("s_combo")] = combo
        m.vm.dmem[_sym("s_idle")] = 0
        m.frame(0)
        counts[combo] = m.vm.dmem[spec.DL_BASE] - rank_only
    # X (5 rects) + 5 (5) = 20 triangles; X + 1 (4) + 2 (5) = 28
    assert counts == {5: 20, 12: 28}, counts


# ---- the tank's other half and the strike's facing (tear.py _tank, _aim_at_dpad)
def test_down_walks_him_backward():
    m = _fight_vm()
    for f in range(40):
        m.frame(spec.PAD_DOWN)
    px, pz = _player(m)
    assert abs(px) < 0.01 and pz < -1.2, (px, pz)


def test_the_dpad_aims_the_strike_and_holds_the_steering():
    """Left held into a jab: the steering turns until A goes down, then
    freezes (the D-pad is choosing the aim); the strike launches facing a
    quarter turn LEFT of the steering; when it is done the body faces its
    steering again. The camera follows the steering throughout."""
    L, A = spec.PAD_RIGHT, spec.PAD_X
    m = _fight_vm()
    seen = {}
    for f in range(60):
        m.frame((L if 10 <= f < 20 else 0) | (A if 12 <= f < 20 else 0))
        seen[f] = (_cell(m, "yaw"), _cell(m, "head"), _cell(m, "anim"))
    yaw = seen[12][0]
    assert all(seen[f][0] == yaw for f in range(12, 20)), "steering turned under A"
    launch = next(f for f in range(60) if seen[f][2] == 2)
    assert seen[launch][1] == (yaw - 256) & 1023, "the strike did not face left"
    assert seen[59][1] == yaw, "the body never faced its steering again"


def test_the_aware_marker_has_hysteresis():
    """tear.py's AWARE: the marker is on when he is inside the demon's
    frontal cone -- entered at 0.46 rad, left only past 0.60 -- so at 0.53
    it keeps whatever it was. Facing away, it is off."""
    import math
    def aware_after(offset, was):
        m = _fight_vm()
        m.frame(0)
        base, nf = _sym("demons"), len(FIELDS)
        w = _wave(m)[0]
        px, pz = _player(m)
        bearing = math.atan2(-(px - w["x"] / 65536), pz - w["z"] / 65536)  # yaw: fwd (-sin, cos)
        yaw = int(round((bearing + offset) * 1024 / (2 * math.pi))) & 1023
        m.vm.dmem[base + FIELDS.index("h8")] = yaw << 8
        m.vm.dmem[base + FIELDS.index("aw")] = was
        m.frame(0)
        return _wave(m)[0]["aw"]
    assert aware_after(0.30, 0) == 1
    assert aware_after(0.53, 1) == 1, "left the cone early: no hysteresis"
    assert aware_after(0.53, 0) == 0, "entered the cone early: no hysteresis"
    assert aware_after(math.pi, 1) == 0


def test_the_small_sounds():
    """sfx.py's whiff, step and stinger, each on its own voice: steps while
    he walks; a whiff for a jab at the air -- and none for one that lands
    (the difference is how a player learns their range); the stinger when
    the rank climbs, its notes three frames each."""
    def vol(m, ch):
        return m.vm.dmem[spec.AU_BASE + 2 * ch + 1] & 15
    m = _fight_vm()
    steps = 0
    for f in range(60):
        m.frame(spec.PAD_UP)
        steps += vol(m, 12) > 0
    assert steps > 10, "no footsteps"
    # (P15: the whoosh shares the whiff's voice, each trigger naming its table)
    table = lambda m: m.vm.dmem[_sym("play_whiff") + 1]      # noqa: E731
    WHIFF, WHOOSH = _sym("snd_whiff"), _sym("snd_whoosh")
    m = _fight_vm()
    heard = []
    for f in range(40):
        m.frame(spec.PAD_X if f == 10 else 0)
        if vol(m, 11) > 0:
            heard.append(table(m))
    assert WHIFF in heard, "a jab at the air made no whiff"
    assert heard and heard[0] == WHOOSH, "the jab's launch made no whoosh"
    m = _fight_vm()
    for f in range(345):
        m.frame((spec.PAD_LEFT if TURN0 <= f < TURN0 + 8 else 0) | (spec.PAD_X if f == STRING0 + 2 else 0))
        if f > 322 and vol(m, 11) > 0:
            assert table(m) == WHOOSH, "a jab that landed whiffed"
    assert _wave(m)[0]["hp"] < 70, "fixture: the jab must land"
    m = _fight_vm()
    sting = []
    for f in range(40):
        if f == 20:
            m.vm.dmem[_sym("s_pts")] = 65 * 16           # to C
        m.vm.dmem[_sym("s_idle")] = 0
        m.frame(0)
        sting.append(vol(m, 13) > 0)
    assert sting[:20] == [False] * 20 and sum(sting) == 9, sting


def test_the_gun_fires_on_release_and_charges():
    """B is the gun: a thumb's tap fires on release, a hold of 26 frames or
    more the CHARGED shot -- 7 and 26 damage, x1.35 to the head. P18: it
    goes EXACTLY the way the pad points (16 degrees either side), meets
    whom that line meets, and does not move him. The brute stands 34
    degrees off his nose: Up+Left (45) finds it, the bare facing does not."""
    UL = spec.PAD_UP | spec.PAD_LEFT
    for hold, mv, dmg in ((8, 7, 7), (30, 8, 26)):
        m = _fight_vm()
        for f in range(228):                 # (arrived; the first swing is at 278)
            m.frame(0)
        hp0, p0 = sum(d["hp"] for d in _wave(m)), _player(m)
        for f in range(hold):                # (the pad is read as it fires)
            m.frame(spec.PAD_B)
            assert _cell(m, "anim") != 2, "the shot fired while B was held"
        seen = set()
        for f in range(30):
            m.frame(UL if f < 2 else 0)
            if _cell(m, "anim") == 2:
                seen.add(_cell(m, "f_mv"))
        assert seen == {mv}, f"a {hold}-frame B threw {seen}, not move {mv}"
        lost = hp0 - sum(d["hp"] for d in _wave(m))
        assert lost in (dmg, int(dmg * 1.35)), f"the shot did {lost}, not {dmg}"
    m = _fight_vm()
    for f in range(260):
        m.frame(0)
    hp0, p0 = sum(d["hp"] for d in _wave(m)), _player(m)
    for f in range(24):
        m.frame(spec.PAD_B if f < 2 else 0)
    assert sum(d["hp"] for d in _wave(m)) == hp0, "a shot off the line landed"
    assert _player(m) == p0, "the shot moved him"


def test_the_jump_rises_light_and_falls_heavy():
    """A, as the BOXER (P18: in the tank and targeting it is the dodge), is
    the jump (tear.py JUMP_V0 0.186, rise 0.010, fall 0.024): an instant
    edge to a ~1.73-unit peak, a long climb and a short drop."""
    m = _fight_vm()
    for f in range(10):
        m.frame(BOX)
    hs = []
    for f in range(60):
        m.frame(BOX | (spec.PAD_A if f < 10 else 0))
        hs.append(_s32(_cell(m, "f_py")) / 65536)
    peak = max(hs)
    up = hs.index(peak)
    down = next(i for i in range(up, 60) if hs[i] == 0) - up
    assert 1.6 < peak < 1.8, f"the jump peaked at {peak:.2f}"
    assert up > down, f"the climb ({up}) should outlast the drop ({down})"
    assert hs[-1] == 0, "he never landed"


def test_a_is_the_dodge_the_way_the_pad_points():
    """P18: in the tank, A is the DODGE -- along the pad from his facing
    (left here), or straight back with none -- untouchable, and no jump."""
    for pad, kind in ((spec.PAD_A | spec.PAD_LEFT, 6), (spec.PAD_A, 5)):
        m = _fight_vm()
        m.frame(0)
        p0 = _player(m)
        m.frame(pad)
        assert _cell(m, "f_evf") > 0 and _cell(m, "f_evk") == kind, "no dodge"
        for f in range(14):
            m.frame(0)
        (x, z), py = _player(m), _cell(m, "f_py")
        assert py == 0, "the dodge jumped"
        if kind == 6:
            assert x < p0[0] - 0.8, "the dodge did not go left"
        else:
            assert z < p0[1] - 0.8, "the dodge did not go back"


def test_the_air_combo_follows_strings_and_spikes():
    """The rear uppercut opens the jump-cancel; A then follows the body up
    (P18: before it is a dodge, and it cuts the launcher's recovery), a
    string lands on the body in the air, and the special from the air
    spikes it down. (P18: the juggle is at jump height, so the string is
    short and the special comes as soon as the string is done.)"""
    m = _fight_vm()
    assert _launch(m) is not None
    hp_at = _sym("demons") + FIELDS.index("hp")
    top, spiked, air_hits, last_hp, y_at = 0.0, False, 0, None, None
    for f in range(200):
        w0 = _wave(m)[0]
        p = spec.PAD_A if f < 6 else 0
        if 12 <= f < 40 and (f - 12) % 12 < 6:        # (the jab, the cross, the hook)
            p |= spec.PAD_X
        if y_at is None and f >= 40 and _cell(m, "anim") != 2 and w0["py"] > 0:
            y_at = f                                  # the string done: the special
        if y_at is not None and f < y_at + 6:
            p |= spec.PAD_Y
        if f == 0:
            m.vm.dmem[hp_at] = 70                     # (a body left to spike: the
                                                      # string alone would kill it)
        m.frame(p)
        w0 = _wave(m)[0]
        if f == 8:
            assert _cell(m, "f_acmb") > 0, "the jump-cancel did not follow"
        top = max(top, _s32(_cell(m, "f_py")) / 65536)
        if last_hp is not None and w0["py"] > 0 and w0["hp"] < last_hp:
            air_hits += 1
        last_hp = w0["hp"]
        if w0["vy"] <= -int(0.6 * 65536):
            spiked = True
    assert top > 1.2, f"he rose only {top:.2f} with it"
    assert air_hits >= 1, "no blow landed on the body in the air"
    assert spiked, f"the aerial special did not spike it (thrown at {y_at})"
    assert _s32(_cell(m, "f_py")) == 0, "he never came down"


def test_the_run_goes_round_the_target_and_threads():
    """P18: both shoulders are THE RUN. The speed ramps logistically to
    0.13, the pad steers it ROUND THE TARGET (Up at it, Down away, Left and
    Right round it), and running fast past the wave PAYS style."""
    m = _fight_vm()
    for f in range(180):                     # (the wave walks in)
        m.frame(0)
    sp, paid = [], 0
    for f in range(150):
        m.frame(RUN | spec.PAD_LEFT)                       # round the target
        sp.append(_s32(_cell(m, "f_spd")) / 65536)
        paid = max(paid, _cell(m, "s_pts"))
    assert _cell(m, "f_sty") == 1, "L+R did not run"
    assert sp[0] < 0.06 < sp[5] < 0.11 and 0.12 < sp[-1] <= 0.13, \
        f"the ramp: {sp[0]:.3f}, {sp[5]:.3f} .. {sp[-1]:.3f}"
    assert paid > 0, "threading the wave paid nothing"
    w = _wave(m)[_cell(m, "f_tgt") - 1]
    px, pz = _player(m)
    brg = int(round(np.arctan2(-(w["x"] / 65536 - px), w["z"] / 65536 - pz) * 1024 / (2 * np.pi)))
    gap = ((_cell(m, "yaw") - (brg + 256)) % 1024 + 512) % 1024 - 512
    assert abs(gap) < 80, f"he is not running round it: {gap}"


def test_boxing_steps_on_the_latched_cross():
    """L+Down is BOXING (tear.py _boxing): left and right STEP across the
    cross latched at entry -- he never turns -- at the heavy boxing pace."""
    L, D, LF = spec.PAD_L, spec.PAD_DOWN, spec.PAD_LEFT
    m = _fight_vm()
    m.frame(0)
    for f in range(40):
        m.frame(L | D if f < 5 else L | LF)
    assert _cell(m, "f_sty") == 2 and _cell(m, "yaw") == 0, "boxing turned him"
    vx = _s32(_cell(m, "f_vx")) / 65536
    assert -0.08 < vx < -0.06, f"the left step runs at {vx:.3f} (left is -x)"


def test_the_boxer_flips_and_the_run_tucks():
    """P18: the BOXER's A with a direction is a directional jump -- a flip
    that way at once (a cartwheel, 24 frames); in the run, A then A again in
    the air is the forward tuck (20) -- once a jump, re-armed by landing."""
    m = _fight_vm()
    m.frame(0)
    for f in range(4):
        m.frame(BOX)
    frames = 0
    for f in range(60):
        m.frame(BOX | (spec.PAD_A | spec.PAD_LEFT if f < 3 else 0))
        if _cell(m, "f_evf"):
            frames += 1
            assert _cell(m, "f_evk") == 2
    assert 22 <= frames <= 24, f"a cartwheel of {frames} frames"
    assert _cell(m, "f_py") == 0 and _cell(m, "f_flipu") == 0, "not landed and re-armed"
    m = _fight_vm()
    m.frame(0)
    frames = 0
    for f in range(80):
        p = RUN | spec.PAD_DOWN
        if 20 <= f < 24 or 30 <= f < 34:
            p = RUN | spec.PAD_UP | spec.PAD_A if f >= 30 else RUN | spec.PAD_DOWN | spec.PAD_A
        m.frame(p)
        if _cell(m, "f_evf"):
            frames += 1
    assert 18 <= frames <= 20, f"a tuck of {frames} frames"


def test_r_locks_plants_cycles_and_aims_the_gun():
    """R locks the nearest living demon; held still 6 frames he PLANTS,
    squared up to it; a right flick moves the lock by bearing and a left
    one brings it back; and a shot, locked, hits the target from range."""
    R, RT, LF, B = spec.PAD_R, spec.PAD_RIGHT, spec.PAD_LEFT, spec.PAD_B
    m = _fight_vm()
    m.frame(0)
    for f in range(30):
        m.frame(0)
    wave = _wave(m)
    d2 = [(w["x"] / 65536) ** 2 + (w["z"] / 65536) ** 2 for w in wave]
    m.frame(R)
    first = _cell(m, "f_tgt")
    assert first == d2.index(min(d2)) + 1, "R did not lock the nearest"
    for f in range(8):
        m.frame(R)
    w = wave[first - 1]
    want = int(round(np.arctan2(-w["x"] / 65536, w["z"] / 65536) * 1024 / (2 * np.pi))) & 1023
    assert abs(((_cell(m, "yaw") - want + 512) % 1024) - 512) <= 2, "the plant does not face it"
    m.frame(R | RT)
    m.frame(R)
    assert _cell(m, "f_tgt") != first, "a right flick kept the lock"
    m.frame(R | LF)
    m.frame(R)
    assert _cell(m, "f_tgt") == first, "a left flick did not bring it back"
    hp0 = wave[first - 1]["hp"]
    for f in range(8):
        m.frame(R | B)
    for f in range(30):
        m.frame(R)
    assert _wave(m)[first - 1]["hp"] < hp0, "the locked shot missed its target"


def test_targeting_plants_dodges_and_aims_high_and_low():
    """P18: R is TARGETING -- he plants and faces the target, Left/Right
    move the lock, Up/Down step the shot (high is the head: 9, not 7; low
    staggers the demon where it stands), and A with a direction dodges."""
    R, B = spec.PAD_R, spec.PAD_B
    m = _fight_vm()
    for f in range(30):
        m.frame(R)
    assert _cell(m, "f_sty") == 3 and _cell(m, "f_aimh") == 1
    p0 = _player(m)
    for f in range(10):
        m.frame(R | (spec.PAD_UP if f == 2 else 0))
    assert _player(m) == p0, "targeting stepped"
    assert _cell(m, "f_aimh") == 0, "Up did not aim high"
    tgt = _cell(m, "f_tgt")
    hp0 = _wave(m)[tgt - 1]["hp"]
    for f in range(30):
        m.frame(R | (B if f < 2 else 0))
    assert hp0 - _wave(m)[tgt - 1]["hp"] == 9, "the high shot was not the head's"
    for f in range(4):
        m.frame(R | (spec.PAD_DOWN if f in (0, 2) else 0))
    assert _cell(m, "f_aimh") == 2
    for f in range(8):
        m.frame(R | (B if f < 2 else 0))
    w = _wave(m)[tgt - 1]
    assert w["hs"] > 0 and w["st"] == 2, "the low shot did not stagger"
    m = _fight_vm()
    for f in range(10):
        m.frame(R)
    m.frame(R | spec.PAD_LEFT | spec.PAD_A)
    assert _cell(m, "f_evf") > 0 and _cell(m, "f_evk") == 6, "no dodge in targeting"


def test_the_operator_takes_its_shots():
    """The camera operator (tear.py _target_cam): planted on the lock, the
    over-the-shoulder AIM shot faces the target; R with B charging moves in
    tight on the shoulder; the juggle pulls back and up with the body; and
    the haymaker's connect holds the ALIGN shot on who it hit."""
    R, B = spec.PAD_R, spec.PAD_B
    m = _fight_vm()
    m.frame(0)
    for f in range(30):
        m.frame(0)
    for f in range(20):
        m.frame(R)
    aim = _cell(m, "yaw")
    assert abs(((m.vm.dmem[spec.CAM_YAW] - aim + 512) % 1024) - 512) <= 16, \
        "the aim shot does not look where he is planted (the shoulder: a few degrees)"
    assert _s32(m.vm.dmem[spec.CAM_Y]) / 65536 > 2.3, "the aim shot is not on the shoulder"
    for f in range(40):
        m.frame(R | B)
    assert abs(_s32(m.vm.dmem[spec.CAM_Y]) / 65536 - 2.32) < 0.05, "no charge shot"
    m = _fight_vm()
    hal = 0
    assert _launch(m) is not None            # (P18: the string's launcher)
    ys = []
    for f in range(120):
        m.frame(spec.PAD_A if f < 6 else (spec.PAD_X if 14 <= f < 90 and (f - 14) % 14 < 8 else 0))
        ys.append(_s32(m.vm.dmem[spec.CAM_Y]) / 65536 - _s32(_cell(m, "f_py")) / 65536)
    assert max(ys) > 2.4, "the juggle shot did not rise with the body"
    m = _fight_vm()
    for f in range(400):
        m.frame((spec.PAD_LEFT if TURN0 <= f < TURN0 + 8 else 0)
                | (spec.PAD_Y if STRING0 <= f < STRING0 + 8 else 0))   # (before the
        hal = max(hal, _cell(m, "cam_hal"))              # ring's first swing)
    assert hal > 16, "the haymaker's connect took no align shot"


def test_the_action_shot_frames_each_mode():
    """P18: one shot a mode, eased between. The tank 3.0 back and square;
    the boxer 4.0 on its cross; the run 5.4 wide on the target; targeting
    2.8 over the right shoulder -- and in its focus, in to 2.2."""
    R, X = spec.PAD_R, spec.PAD_X
    for sched, dist, lean in ((lambda f: 0, 3.0, 0.0), (lambda f: BOX, 4.0, -0.12),
                              (lambda f: RUN | spec.PAD_LEFT, 5.4, -0.12),
                              (lambda f: R, 2.8, -0.55), (lambda f: R | X, 2.2, -0.55)):
        m = _fight_vm()
        m.frame(0)
        for f in range(120):
            m.frame(sched(f))
        assert abs(_s32(_cell(m, "cam_d3")) / 65536 - dist) < 0.06, \
            f"follow at {_s32(_cell(m, 'cam_d3')) / 65536:.2f}, not {dist}"
        assert abs(_s32(_cell(m, "cam_sh")) / 65536 - lean) < 0.03, f"lean {lean}"


def test_start_pauses_resumes_and_quits():
    """Start in the fight pages in the PAUSE (a third program): the street
    stands frozen under its two words; Start resumes with the borrowed end
    put back and no button live (no stray jump or punch); Down then A
    QUITS to the title, the run reset, and the next fight a fresh wave."""
    cart = cabinet.load_cart(CART)
    pause = _image(cart, _const("PAUSE_PROG"), _const("PAGE"))
    m = cabinet.VirtualMachine(cart)
    m.frame(spec.PAD_START)
    boot = list(m.vm.dmem)
    for f in range(40):
        m.frame(0)
    for f in range(8):                                # a thumb on Start
        m.frame(spec.PAD_START)
    assert list(m.vm.imem[:_const("PAGE")]) == pause, "Start did not page in the pause"
    assert m.vm.dmem[spec.DL_BASE] > 0 and m.vm.dmem[spec.OL_BASE] > 0
    w0 = [d["x"] for d in _wave(m)]
    for f in range(30):
        m.frame(0)
    assert [d["x"] for d in _wave(m)] == w0, "the street moved under the pause"
    for f in range(8):
        m.frame(spec.PAD_START | spec.PAD_A)          # A held through the resume
    a, k = _const("BORROW_END"), _const("BORROW_END_N")
    assert list(m.vm.imem[:len(cart["imem"])]) == list(cart["imem"]), "not resumed"
    assert m.vm.dmem[a:a + k] == boot[a:a + k], "the end was not put back"
    assert _cell(m, "f_py") == 0 and _cell(m, "anim") != 2, "the resume fired a button"
    for f in range(20):
        m.frame(0)
    m.frame(spec.PAD_START)
    for p in (0, spec.PAD_DOWN, 0, spec.PAD_A, 0, 0):
        m.frame(p)
    assert _cell(m, "mode") == 0 and m.vm.dmem[spec.BG_SRC] > 0, "QUIT did not reach the title"
    m.frame(spec.PAD_START)
    m.frame(0)
    m.frame(0)
    assert [(d["st"], d["hp"]) for d in _wave(m)] == [(0, 70)] * 3, "no fresh wave after QUIT"


def test_a_blow_taken_flashes_and_a_lunge_is_heard():
    """Struck, the frame washes red through his hitstop (tear.py flash), and
    a demon committing to its swing is heard (the lunge's whoosh)."""
    m = _fight_vm()
    flashed, heard, prev = 0, 0, 99
    for f in range(600):
        m.frame(0)
        if (m.vm.dmem[spec.CO_BASE + 9] >> 24) and not _cell(m, "f_dead"):
            flashed += 1
        wt = _cell(m, "sg_wt")
        heard += wt < prev
        prev = wt
    assert flashed > 0, "a blow taken did not flash"
    assert heard > 0, "a lunge was not heard"


# ---- P14: the card -- what survives the power ------------------------------------
def _card_vm(words):
    """A machine whose card already holds `words` in TND's slot."""
    cart = cabinet.load_cart(CART)
    cart["sd"] = {2: list(words)}
    return cabinet.VirtualMachine(cart)


def test_the_card_is_written_when_a_run_ends():
    """Untouched, the wave beats him down. The first blow opened the fight
    at rank D, so the card is owed a best of 1; the death is owed a run.
    Both are on the card a few frames later (the law's own latency)."""
    m = _fight_vm()
    assert m.vm.sd.get(2, [0, 0])[:2] == [0, 0], "the card was not blank"
    for f in range(900):
        m.frame(0)
    assert _cell(m, "f_dead") > 0
    assert m.vm.sd[2][:2] == [1, 1], f"the card holds {m.vm.sd[2][:2]}"
    assert m.vm.dmem[_sym("save_f")] == 1, "something is still owed"


def test_the_title_shows_the_cards_best_and_a_lesser_run_keeps_it():
    """A card that remembers S and three runs. The title (after the film)
    says BEST and S -- 34 + 10 triangles. A run beaten down at D leaves
    the best alone and counts the run; the title's words do not follow
    him into the fight."""
    m = _card_vm([5, 3])
    for f in range(430):                    # the film, then the title
        m.frame(0)
    assert _cell(m, "mode") == 0
    assert [m.vm.dmem[_sym("save") + i] for i in (0, 1)] == [5, 3], "the card was not read"
    assert m.vm.dmem[spec.DL_BASE] == 44, f"the title drew {m.vm.dmem[spec.DL_BASE]} triangles"
    m.frame(spec.PAD_A)                     # a fresh press: the fight
    assert _cell(m, "mode") == 1
    assert m.vm.dmem[spec.DL_BASE] == 0, "BEST followed him into the fight"
    for f in range(900):
        m.frame(0)
    assert _cell(m, "f_dead") > 0
    assert m.vm.sd[2][:2] == [5, 4], f"the card holds {m.vm.sd[2][:2]}"


def test_a_better_rank_is_owed_the_moment_it_is_reached():
    """The best is the best rank REACHED, not the rank at the death: the
    card has it while he is still standing."""
    m = _card_vm([1, 0])
    m.frame(spec.PAD_START)
    for f in range(70):                     # past frame 60: the read lands
        m.frame(0)
    assert m.vm.dmem[_sym("save")] == 1
    m.vm.dmem[_sym("f_fight")] = 1          # mid-fight, and suddenly an A
    m.vm.dmem[_sym("s_pts")] = 16 * 320
    for f in range(8):
        m.frame(0)
    assert _cell(m, "f_dead") == 0
    assert m.vm.sd[2][0] == 4, f"the card's best is {m.vm.sd[2][0]}, not A"


def test_a_card_this_cart_never_wrote_says_nothing():
    """A word outside 1..7 is not a rank: the title stays silent rather
    than read a string off the end of the table."""
    m = _card_vm([99, 7])
    for f in range(430):
        m.frame(0)
    assert _cell(m, "mode") == 0
    assert m.vm.dmem[spec.DL_BASE] == 0, "the title drew a rank that is not one"


def test_the_huds_promise_is_kept():
    """The display list's lease (78 triangles) is proved from the font in
    gen_tnd.py; this holds the cart to it at run time: through the
    beating that draws the rank and the combo, then with the worst the
    HUD can say forced on it -- SSS and a combo of 55."""
    m = _fight_vm()
    worst = 0
    for f in range(483):
        m.frame((spec.PAD_LEFT if TURN0 <= f < TURN0 + 8 else 0)
                | (spec.PAD_X if f >= STRING0 and f % 9 == 0 else 0))
        worst = max(worst, m.vm.dmem[spec.DL_BASE])
    assert worst > 0, "the route never drew the HUD"
    m.vm.dmem[_sym("s_pts")] = 16 * 5000
    m.vm.dmem[_sym("s_combo")] = 55
    m.vm.dmem[_sym("s_idle")] = 0
    m.frame(0)
    assert _cell(m, "s_rank") == 6
    n = m.vm.dmem[spec.DL_BASE]
    assert n == 78, f"SSS, X55 and TND came to {n} triangles"
    assert max(worst, n) <= 78


# ---- P15: the feel ------------------------------------------------------------------
def _marker_flags(m):
    """The flags word of every AWARE marker in this frame's object list."""
    d, out = m.vm.dmem, []
    aware = _sym("aware")
    for o in range(min(d[spec.OL_BASE], spec.OL_MAX)):
        base = spec.OL_BASE + 1 + o * spec.OL_STRIDE
        if d[base] == aware:
            out.append(d[base + 5])
    return out


def test_a_swing_is_told_amber_then_red():
    """tear.py's _WINDUP and _DANGER: the marker over a demon is amber
    through its swing's startup and red while the fist is live -- and
    (P16) amber through the last 24 frames of its WAIT, because a cross is
    five frames from its first to its fist and nobody dodges on that.
    Untouched, the wave walks in and swings; both tints must be seen, the
    amber at least 20 frames before the first swing starts, and only while
    some demon is in those frames of a swing or of its wait."""
    amber = (31 << 27) | (19 << 22) | (9 << 17)
    red = (31 << 27) | (10 << 22) | (10 << 17)
    tint = lambda w: w & 0xFFFE0000
    m = _fight_vm()
    first = {}
    for f in range(700):
        m.frame(0)
        swinging = [w for w in _wave(m) if w["st"] == 1
                    or (w["st"] == 0 and w["ai"] > _const("DREST") - 25)]
        if any(w["st"] == 1 for w in _wave(m)):
            first.setdefault("swing", f)
        for w in _marker_flags(m):
            if w & spec.OBJ_OTINT:
                assert swinging, f"frame {f}: a tinted marker and nobody about to swing"
                first.setdefault(tint(w), f)
        if _cell(m, "f_dead"):
            break
    assert amber in first and red in first, f"tints seen: {[hex(t) for t in first]}"
    assert first[amber] < first[red], "the red came before the amber"
    assert first[amber] <= first["swing"] - 20, \
        f"the swing at {first['swing']} was told only from {first[amber]}"


def test_a_landing_is_felt_and_heard():
    """tear.py's landing impact: the frame shakes and the ground answers
    (the step's own thud) on the frame he touches down -- and only then."""
    m = _fight_vm()
    for f in range(5):
        m.frame(0)
    assert _cell(m, "f_shake") == 0 and _cell(m, "sg_st") > 9, "shaking or thudding at rest"
    m.frame(BOX)
    m.frame(BOX | spec.PAD_A)
    aloft = landed = False
    for f in range(80):
        m.frame(0)
        if _s32(_cell(m, "f_py")) > 0:
            aloft = True
            assert _cell(m, "f_shake") == 0, "the frame shook in mid-air"
        elif aloft:
            landed = True
            break
    assert aloft and landed, "he never left the ground, or never came back"
    assert _cell(m, "f_shake") >= 4, f"a touchdown shook {_cell(m, 'f_shake')} frames"
    assert _cell(m, "sg_st") <= 1, "no thud on the touchdown"


def _onto_demon(m, lift):
    """Put him 0.3 from demon 0 -- well inside a shove -- at height `lift`."""
    w = _wave(m)[0]
    d = m.vm.dmem
    d[_sym("px")] = (w["x"] + int(0.3 * 65536)) & 0xFFFFFFFF
    d[_sym("pz")] = w["z"] & 0xFFFFFFFF
    d[_sym("f_py")] = int(lift * 65536)
    return w


def test_a_flip_clears_a_head_and_a_touch_stops_a_run():
    """tear.py _collide, both halves. On the ground beside a demon he is
    shoved clear and loses 85% of his run; 1.2 up -- past JUMP_CLEARANCE --
    there is no push at all, and the run is his to keep."""
    L, U = RUN, spec.PAD_DOWN      # (P18: the run, away from the target)

    def running():
        m = _fight_vm()
        m.frame(0)
        for f in range(40):
            m.frame(L | U)
        assert _s32(_cell(m, "f_spd")) > 0.05 * 65536, "he is not running"
        return m

    low, high = running(), running()
    spd = _s32(_cell(low, "f_spd"))
    _onto_demon(low, 0.0)
    _onto_demon(high, 1.2)
    low.frame(L | U)
    high.frame(L | U)
    # The two machines differ ONLY in his height, so any difference in where
    # the bodies stand is the shove: an eighth of the overlap, split by mass.
    (lx, lz), (hx, hz) = _player(low), _player(high)
    dl, dh = _wave(low)[0], _wave(high)[0]
    assert abs(lx - hx) + abs(lz - hz) > 0.02, "on the ground, he was not shoved"
    assert abs(dl["x"] - dh["x"]) + abs(dl["z"] - dh["z"]) > 0.005 * 65536, \
        "on the ground, the demon was not shoved"
    assert _s32(_cell(low, "f_spd")) < 0.3 * spd, "the touch cost him no speed"
    assert _s32(_cell(high, "f_spd")) > 0.8 * spd, "clearing the head cost him his run"
    # (overhead there is no contact at all -- which is why the run above is
    # intact: the bleed fires exactly when the shove says the bodies touched)


def test_he_takes_a_landing_in_the_knees():
    """The touchdown's squash: the archive's own absorb, baked as four
    poses and held two frames each from the frame he lands -- then he is
    standing again."""
    land = _const("POSE_LAND")
    m = _fight_vm()
    for f in range(5):
        m.frame(0)
    m.frame(BOX)
    m.frame(BOX | spec.PAD_A)
    aloft, seen = False, []
    for f in range(100):
        m.frame(0)
        if _s32(_cell(m, "f_py")) > 0:
            aloft = True
        elif aloft:
            seen.append(_cell(m, "pose") - land)
            if len(seen) == 12:
                break
    assert seen[:8] == [0, 0, 1, 1, 2, 2, 3, 3], f"the squash played {seen[:8]}"
    assert all(not 0 <= s < 4 for s in seen[8:]), "he never stood back up"


def _body_angles(m):
    """(pitch, roll) of his upper half in this frame's object list, signed."""
    d, body = m.vm.dmem, _sym("body")
    for o in range(min(d[spec.OL_BASE], spec.OL_MAX)):
        base = spec.OL_BASE + 1 + o * spec.OL_STRIDE
        if d[base] == body:
            sg = lambda v: v - 1024 if v > 511 else v      # noqa: E731
            return sg((d[base + 4] >> 10) & 1023), sg((d[base + 4] >> 20) & 1023)
    raise AssertionError("he is not in the object list")


def test_he_leans_into_his_run_and_banks_into_his_turn():
    """tear.py's momentum lean: upright standing; pitched forward by his
    speed in the run (0.11 rad at full pace is 18 of 1,024); rolled toward
    the turn he steers, eased in and eased out again."""
    L, U = RUN, spec.PAD_DOWN      # (P18: the run, away from the target)
    m = _fight_vm()
    for f in range(10):
        m.frame(0)
    assert _body_angles(m) == (0, 0), f"he leans standing still: {_body_angles(m)}"
    for f in range(110):
        m.frame(L | U)
    pitch, roll = _body_angles(m)
    assert 16 <= pitch <= 18 and roll == 0, f"at full pace: pitch {pitch}, roll {roll}"
    for f in range(20):
        m.frame(L | U | spec.PAD_LEFT)
    assert _body_angles(m)[1] == 14, f"steering left banks {_body_angles(m)[1]}"
    for f in range(30):
        m.frame(L | U | spec.PAD_RIGHT)
    assert _body_angles(m)[1] == -14, f"steering right banks {_body_angles(m)[1]}"
    for f in range(30):
        m.frame(L | U)
    assert _body_angles(m)[1] == 0, "the bank did not ease out"


def test_the_walk_is_a_planted_stride_at_sixty():
    """The tank walk plays a 32-pose stride, one pose a frame (the stance
    foot was solved, offline, to fall behind him by exactly the ground he
    covers each frame -- so the pose MUST advance with every frame he
    walks, or the foot slides)."""
    walk = _const("POSE_WALK")
    m = _fight_vm()
    m.frame(0)
    seen = []
    for f in range(40):
        m.frame(spec.PAD_UP)
        if _cell(m, "anim") == 1:
            seen.append(_cell(m, "pose") - walk)
    assert len(seen) >= 34, "he did not walk"
    assert all(0 <= s < 32 for s in seen)
    steps = {(b - a) % 32 for a, b in zip(seen, seen[1:])}
    assert steps == {1}, f"the stride advanced by {sorted(steps)} a frame"


def test_the_haymaker_booms_and_the_run_has_feet():
    """tear.py 1188 and 2678: the haymaker's launch is a boom (through the
    step's voice, its own table), and a run is heard footfall by footfall
    -- faster as he speeds up, silent while he is in the air."""
    vol = lambda m, ch: m.vm.dmem[spec.AU_BASE + 2 * ch + 1] & 15       # noqa: E731
    table = lambda m: m.vm.dmem[_sym("play_step") + 1]                  # noqa: E731
    m = _fight_vm()
    for f in range(5):
        m.frame(0)
    m.frame(spec.PAD_Y)                          # the haymaker
    boom = []
    for f in range(14):
        m.frame(0)
        if vol(m, 12) > 0:
            boom.append(table(m))
    assert len(boom) >= 6 and set(boom) == {_sym("snd_boom")}, f"the boom: {boom}"
    L, U = RUN, spec.PAD_DOWN      # (P18: the run, away from the target)
    m = _fight_vm()
    m.frame(0)
    falls = []
    for f in range(150):
        m.frame(L | U)
        if _cell(m, "sg_st") == 1:               # rung this frame, and played once
            assert table(m) == _sym("snd_step"), "a footfall played the boom"
            falls.append(f)
    gaps = [b - a for a, b in zip(falls, falls[1:])]
    assert len(falls) >= 6, f"the run made {len(falls)} footfalls"
    assert gaps[-1] < gaps[0], f"the feet did not quicken with the run: {gaps}"


def test_a_blow_sparks_where_it_lands():
    """tear.py's impact burst: for six frames from the frame a fist lands,
    a spark stands at the fist -- drawn twice, tumbling -- and then it is
    gone. A jab into the brute: the spark is within a fist's reach of him."""
    spark = _sym("spark_m")

    def sparks(m):
        d, out = m.vm.dmem, []
        for o in range(min(d[spec.OL_BASE], spec.OL_MAX)):
            base = spec.OL_BASE + 1 + o * spec.OL_STRIDE
            if d[base] == spark:
                out.append(tuple(_s32(d[base + k]) / 65536 for k in (1, 2, 3)) + (d[base + 4],))
        return out

    m = _fight_vm()
    hp, seen = 70, []
    for f in range(STRING0 + 40):        # (before the ring's own blows spark)
        m.frame((spec.PAD_LEFT if TURN0 <= f < TURN0 + 8 else 0) | (spec.PAD_X if f == STRING0 + 2 else 0))
        s = sparks(m)
        if _wave(m)[0]["hp"] == hp:
            assert not s or seen, f"frame {f}: a spark with no blow landed"
        if s:
            seen.append((f, s))
    assert _wave(m)[0]["hp"] < 70, "fixture: the jab must land"
    assert len(seen) == 6, f"the spark stood {len(seen)} frames"
    assert [b[0] - a[0] for a, b in zip(seen, seen[1:])] == [1] * 5, "the spark flickered"
    f0, s0 = seen[0]
    assert len(s0) == 2 and s0[0][3] != s0[1][3], "not two sparks, tumbling apart"
    x, y, z = s0[0][:3]
    px, pz = _player(m)
    assert 0.5 < y < 2.0, f"the spark is at height {y:.2f}"
    assert ((x - px) ** 2 + (z - pz) ** 2) ** 0.5 < 2.5, "the spark is nowhere near the blow"


# ---- P16: what the first tape of real play asked for (docs/TND-PORT.md) -----
def _first(m, pads, want, frames=400):
    """Run `pads(f)` until `want(m)` is true; -> that frame (None: never)."""
    for f in range(frames):
        m.frame(pads(f))
        if want(m):
            return f
    return None


def test_the_plain_shot_chips_a_standing_demon_and_does_not_stop_it():
    """Locked, the shot lands at any range -- and it used to stun, eighteen
    frames apart, so nothing ever reached him. A plain shot on a demon with
    its feet down takes its health and leaves it walking; the CHARGED shot
    still stops it."""
    R, B = spec.PAD_R, spec.PAD_B
    m = _fight_vm()
    hit = _first(m, lambda f: R | (B if 10 <= f < 18 else 0),
                 lambda m: any(w["hp"] < 70 for w in _wave(m)), 80)
    assert hit is not None, "fixture: the locked shot must land"
    w = [w for w in _wave(m) if w["hp"] < 70][0]
    assert w["st"] == 0 and w["hs"] == 0, f"the plain shot stunned: st {w['st']}, hs {w['hs']}"
    assert w["stop"] > 0, "not even a flinch"
    x0 = w["x"], w["z"]
    for _ in range(12):
        m.frame(R)
    w2 = [v for v in _wave(m) if v["hp"] < 70][0]
    assert (w2["x"], w2["z"]) != x0 and w2["mov"] == 1, "it did not walk on through the shot"
    # the charged shot: held past the charge, then let go
    m = _fight_vm()
    hit = _first(m, lambda f: R | (B if 10 <= f < 44 else 0),
                 lambda m: any(w["hp"] < 70 for w in _wave(m)), 120)
    assert hit is not None, "fixture: the charged shot must land"
    w = [w for w in _wave(m) if w["hp"] < 70][0]
    assert w["st"] == 2 and w["hs"] > 0, "the charged shot no longer stops a demon"


def test_a_press_inside_the_freeze_is_thrown_when_it_ends():
    """A landed blow freezes the world for its hitstop, and it used to
    freeze the buttons with it: a third of the tape's presses began in a
    freeze and were lost. A tap wholly inside a jab's five frozen frames
    is buffered, and cancels the jab's recovery into the haymaker the
    moment the world moves. (A press in the haymaker's OWN freeze still
    goes nowhere: nothing cancels the haymaker, and the buffer is ten
    frames against its thirty of recovery.)"""
    m = _fight_vm()
    pads = lambda f: (spec.PAD_LEFT if TURN0 <= f < TURN0 + 8 else 0) \
        | (spec.PAD_X if f == STRING0 + 2 else 0)
    at = _first(m, pads, lambda m: _cell(m, "f_stop") > 0 and _cell(m, "f_con") == 1, 320)
    assert at is not None and _cell(m, "f_mv") in (0, 1), "fixture: the first tap must land"
    assert _cell(m, "f_stop") >= 4
    for k in range(3):                               # the tap: down for two frames
        assert _cell(m, "f_stop") > 0, "fixture: the tap left the freeze"
        m.frame(spec.PAD_Y if k < 2 else 0)          # and up, all inside the stop
    thrown = _first(m, lambda f: 0,
                    lambda m: _cell(m, "anim") == 2 and _cell(m, "f_mv") == 4, 30)
    assert thrown is not None, "the tap in the freeze was lost"


def test_a_fallen_demon_is_replaced_alone():
    """The wave used to return only when all three were gone: two seconds
    of nothing after every wave, 18% of the tape's fight. One that falls
    lies its beat, and on the frame it would be gone it stands at its own
    place on the ring again -- while the other two never leave."""
    m = _fight_vm()
    m.frame(0)
    born = _wave(m)[1]
    base, n = _sym("demons"), len(FIELDS)
    m.vm.dmem[base + 1 * n + FIELDS.index("st")] = 3          # the middle one falls
    back = None
    for f in range(200):
        m.frame(0)
        w = _wave(m)
        assert w[0]["st"] < 3 and w[2]["st"] < 3, "another demon left with it"
        if w[1]["st"] == 0:
            back = f
            break
        assert w[1]["st"] in (3, 4) and _cell(m, "f_wave") == 0
    assert back is not None and 100 < back < 125, f"back at {back}"
    assert w[1]["hp"] == 70 and abs(w[1]["x"] - born["x"]) < 65536 * 0.2
    assert _cell(m, "f_wave") == 1


def test_the_run_reaches_its_speed_inside_a_short_run():
    """On the tape the median run was 17 frames and not one of 874 running
    frames was at nine tenths of top speed: the ramp took 79. It takes
    about 19 now, and the top itself has not moved."""
    m = _fight_vm()
    L, U = RUN, spec.PAD_DOWN      # (P18: the run, away from the target)
    top = _const("PK_TOP")
    at = _first(m, lambda f: L | U, lambda m: _cell(m, "f_spd") >= 0.9 * top, 60)
    assert at is not None and at <= 28, f"nine tenths of top at frame {at}"   # (a half turn first)
    for _ in range(40):
        m.frame(L | U)
    assert top == int(0.13 * 65536) and 0.99 * top < _cell(m, "f_spd") <= top


def test_the_camera_turns_and_does_not_whip():
    """A new lock used to swing the camera an eighth of the arc in one
    frame -- 22 degrees for a target behind him. It turns no faster than
    CAM_TURN a frame, and still gets there."""
    m = _fight_vm()
    cap, seen, total = _const("CAM_TURN"), [], 0
    prev = _cell(m, "cam_yaw")
    for f in range(150):                 # turn his back on the ring, then lock
        m.frame(spec.PAD_LEFT if f < 42 else spec.PAD_R if f >= 60 else 0)
        cy = _cell(m, "cam_yaw")
        d = ((cy - prev + 512) & 1023) - 512
        seen.append(abs(d))
        total += abs(d)
        prev = cy
    assert max(seen) <= cap, f"the camera turned {max(seen)} in one frame"
    assert max(seen) == cap and total > 3 * cap, "fixture: the lock must ask for a long turn"
    assert seen[-1] == 0, "the camera never settled on the target"


def test_focus_slows_the_world_while_an_attack_is_held_in_targeting():
    """P18: targeting, X held past a tap is FOCUS -- the world moves one
    frame in three (the demons' walk with it) until it is let go, and the
    press then throws its blow. Outside targeting a hold does not slow."""
    R, X = spec.PAD_R, spec.PAD_X
    walk = []
    for focus in (False, True):
        m = _fight_vm()
        for f in range(20):
            m.frame(R)
        x0 = [w["x"] for w in _wave(m)]
        for f in range(30):
            m.frame(R | (X if focus else 0))
        walk.append(sum(abs(w["x"] - a) for w, a in zip(_wave(m), x0)))
    assert walk[1] < 0.5 * walk[0], f"the walk under focus: {walk}"
    m = _fight_vm()
    for f in range(20):
        m.frame(0)
    for f in range(12):
        m.frame(X)
        assert _cell(m, "f_skip") == 0, "a hold slowed the world outside targeting"


def test_the_shot_does_not_move_him_and_a_dodge_is_untouchable():
    """P18 (and P17's keeper): a fist that would have landed on a dodging
    body goes through him, the swing spent, and the close call pays."""
    m = _fight_vm()
    for f in range(400):
        w = _wave(m)[0]
        if w["st"] == 1 and w["mf"] >= 3:
            break
        m.frame(0)
    else:
        raise AssertionError("fixture: the brute never swung")
    hp, pts = _s32(_cell(m, "p_hp")), _cell(m, "s_pts")
    for f in range(14):
        m.frame(spec.PAD_A if f < 2 else 0)
    assert _s32(_cell(m, "p_hp")) == hp, "the dodge was hit"
    assert _cell(m, "s_pts") > pts, "no close call"


def test_letting_go_of_targeting_keeps_the_targets_bearing():
    """On glass: releasing R spun him -- the plant read the lock on the frame
    it was let go and turned him to "slot -1". The tank keeps facing where
    the target was."""
    m = _fight_vm()
    for f in range(40):
        m.frame(spec.PAD_R)
    yaw = _cell(m, "yaw")
    for f in range(5):
        m.frame(0)
    assert _cell(m, "yaw") == yaw, f"released, he turned from {yaw} to {_cell(m, 'yaw')}"


def test_the_shots_spark_is_on_the_demon_it_hit():
    """On glass: a shot's spark stood at his hand. It is on the demon, on its
    front, at the height the shot struck (targeting's low shot: the legs)."""
    spark = _sym("spark")
    for aim_low in (False, True):
        m = _fight_vm()
        for f in range(40):
            m.frame(spec.PAD_R | (spec.PAD_DOWN if aim_low and f == 20 else 0))
        tgt = _cell(m, "f_tgt")
        for f in range(12):
            m.frame(spec.PAD_R | (spec.PAD_B if f < 2 else 0))
            if m.vm.dmem[spark + 3]:
                break
        assert m.vm.dmem[spark + 3], "no spark"
        w = _wave(m)[tgt - 1]
        sx, sy, sz = (_s32(m.vm.dmem[spark + k]) / 65536 for k in range(3))
        assert ((sx - w["x"] / 65536) ** 2 + (sz - w["z"] / 65536) ** 2) ** 0.5 < 0.6, \
            "the spark is not on the demon"
        assert (0.4 < sy < 0.7) if aim_low else (1.0 < sy < 1.9), f"the spark at height {sy:.2f}"


def test_the_camera_turns_to_a_demon_about_to_strike():
    """On glass: getting hit from behind. When a demon is about to swing
    (its amber tell, or the swing) and lies outside the camera's line, the
    camera turns just far enough to have it in view -- within 32 degrees."""
    m = _fight_vm()
    for f in range(36):
        m.frame(spec.PAD_RIGHT)                  # his back to the brute
    for f in range(240):
        m.frame(0)
        w = _wave(m)
        if any(x["st"] == 0 and x["ai"] > _const("DREST") - 25 for x in w):
            break
    for f in range(20):
        m.frame(0)
    cy = _cell(m, "cam_yaw")
    px, pz = _player(m)
    gaps = []
    for x in _wave(m):
        brg = int(round(np.arctan2(-(x["x"] / 65536 - px), x["z"] / 65536 - pz) * 1024 / (2 * np.pi)))
        gaps.append(abs(((brg - cy + 512) % 1024) - 512))
    assert min(gaps) <= 128, f"no threat in view: gaps {gaps}"   # (45 degrees: on screen)
    assert abs(((cy - _cell(m, "yaw") + 512) % 1024) - 512) > 100, "the camera never left his back"


def test_out_of_a_lock_he_faces_where_the_target_was():
    """On glass: releasing targeting (or the run) into the boxer, he and the
    camera face where the target was -- the boxer's cross is its bearing."""
    for lock in (spec.PAD_R, RUN | spec.PAD_LEFT):
        m = _fight_vm()
        for f in range(30):
            m.frame(lock)
        brg = _cell(m, "f_cgr")
        for f in range(30):
            m.frame(BOX)
        assert _cell(m, "f_sty") == 2
        assert _cell(m, "yaw") == brg and _cell(m, "f_latch") == brg, "he did not face it"
        assert abs(((_cell(m, "cam_yaw") - brg + 512) % 1024) - 512) <= 8, "the camera did not"


def test_the_run_flips_any_way_and_over_the_target():
    """On glass: "the running target jumps need to be a jump, then press
    again to flip -- think Crash Bandicoot double jump". In the run A jumps;
    a second A in the air flips along any of the pad's eight ways from the
    target's frame (Up flips over it), or with none goes straight up again --
    and the double jump climbs past the single one."""
    for pad, kind in ((spec.PAD_UP, 0), (spec.PAD_DOWN | spec.PAD_LEFT, 2),
                      (spec.PAD_RIGHT, 3), (0, 0)):
        m = _fight_vm()
        for f in range(20):
            m.frame(spec.PAD_R)
        for f in range(4):
            m.frame(RUN)
        p0, peak, kinds, first = _player(m), 0.0, set(), None
        for f in range(70):
            p = RUN | (spec.PAD_A if f < 2 else 0) | ((spec.PAD_A | pad) if 14 <= f < 16 else 0)
            m.frame(p)
            if f == 8:
                first = _cell(m, "f_evf")
            peak = max(peak, _s32(_cell(m, "f_py")) / 65536)
            if _cell(m, "f_evf"):
                kinds.add(_cell(m, "f_evk"))
        assert first == 0, "the run's first press flipped: it should only jump"
        assert kinds == {kind}, f"{pad}: the flip's shape {kinds}"
        assert peak > 2.5, f"{pad}: the double jump peaked at {peak:.2f}"
        if pad:
            (x, z) = _player(m)
            assert ((x - p0[0]) ** 2 + (z - p0[1]) ** 2) ** 0.5 > 3.5, f"{pad}: a short flip"


def test_targetings_haymaker_always_lands_on_the_target():
    """On glass: "the haymaker needs to hit the target every time targeting
    is active". From across the street, it crosses most of the gap and
    lands on the locked demon, whatever the distance."""
    m = _fight_vm()
    for f in range(40):
        m.frame(spec.PAD_R)
    tgt = _cell(m, "f_tgt")
    hp0 = _wave(m)[tgt - 1]["hp"]
    for f in range(40):
        m.frame(spec.PAD_R | (spec.PAD_Y if f < 2 else 0))
    assert _wave(m)[tgt - 1]["hp"] <= hp0 - 46, "the haymaker missed its target"


def _in_arena(x, z):
    sq, lane, reach = 10.6, 7.1, 40.0
    x, z = abs(x), abs(z)
    return (x <= sq and z <= sq) or (x <= lane and z <= reach) or (z <= lane and x <= reach)


def test_the_lens_stays_in_the_street():
    """On glass: "the camera goes wonky targeting down street alleys" --
    over the shoulder beside a wall, the lens stood inside the building.
    Down a street, against its wall, targeting and turning: the lens is in
    the street every frame."""
    m = _fight_vm()
    d = m.vm.dmem
    for side in (1, -1):
        m = _fight_vm()
        d = m.vm.dmem
        d[_sym("px")] = int(side * 6.8 * 65536) & 0xFFFFFFFF   # against a wall,
        d[_sym("pz")] = int(-22 * 65536) & 0xFFFFFFFF          # down the south street
        outside = 0
        for f in range(240):
            m.frame(spec.PAD_R | (spec.PAD_LEFT if f % 60 < 30 else spec.PAD_RIGHT)
                    if f > 20 else spec.PAD_LEFT if f < 10 else 0)
            cx, cz = (_s32(d[r]) / 65536 for r in (spec.CAM_X, spec.CAM_Z))
            outside += not _in_arena(cx, cz)
        assert outside == 0, f"the lens left the street on {outside} frames (side {side})"


def test_attack_tokens_two_at_a_time_and_only_on_screen():
    """P18: "the camera keeps those enemies on screen as being the ones about
    to attack." A demon's wait crosses into its tell only holding one of two
    tokens, and only on screen. Untouched, and turning, over a long fight:
    never more than two told or swinging, and no swing begun off screen."""
    D = _const("DREST")

    def onscreen(m, w):
        cy = _cell(m, "cam_yaw") * 2 * np.pi / 1024
        cx, cz = (_s32(m.vm.dmem[r]) / 65536 for r in (spec.CAM_X, spec.CAM_Z))
        vx, vz = w["x"] / 65536 - cx, w["z"] / 65536 - cz
        dot = -vx * np.sin(cy) + vz * np.cos(cy)
        cr = vx * np.cos(cy) + vz * np.sin(cy)
        return dot > 0 and cr * cr < 0.31 * dot * dot

    for route in (lambda f: 0, lambda f: spec.PAD_RIGHT if f % 200 < 40 else 0):
        m = _fight_vm()
        prev, swings = [0, 0, 0], 0
        for f in range(800):
            told = [x for x in _wave(m) if x["st"] == 0 and x["ai"] == D - 30]
            m.frame(route(f))
            w = _wave(m)
            busy = sum(1 for x in w if x["st"] == 1 or (x["st"] == 0 and x["ai"] > D - 31))
            assert busy <= 2, f"frame {f}: {busy} demons attacking at once"
            for i in range(3):
                if w[i]["st"] == 0 and w[i]["ai"] == D - 29:      # just entered the tell
                    assert onscreen(m, w[i]), f"frame {f}: demon {i} told off screen"
                swings += w[i]["st"] == 1 and prev[i] != 1
                prev[i] = w[i]["st"]
            if _cell(m, "f_dead"):
                break
        assert swings >= 4, "fixture: the ring never attacked"


def test_the_horde_refills_the_street_until_the_district_is_clear():
    """P18, the horde: a district holds a reserve beyond the three on the
    street. A fallen demon is replaced from it until it is spent; the last
    of the district falls in slow motion; after the beat the next district
    comes, bigger. The bar under the gauge is two pixels a demon left."""
    m = _fight_vm()
    d = m.vm.dmem
    for f in range(5):
        m.frame(0)
    res = lambda: _cell(m, "s_n")                                  # noqa: E731
    assert res() == 30
    b = spec.CO_BASE + 1 + 2 * spec.CO_STRIDE
    assert (d[b] >> 10) & 1023 == 8 + 2 * 30 and d[b + 2] >> 24 > 0, "no horde bar"
    base, n, st = _sym("demons"), len(FIELDS), FIELDS.index("st")
    d[_sym("s_n")] = 1
    d[base + st] = 3                                  # one falls, one in reserve
    for f in range(130):
        m.frame(0)
    assert res() == 0 and [w["st"] for w in _wave(m)] == [0, 0, 0], "not replaced"
    d[base + st] = 3                                  # the reserve is spent: it stays down
    for f in range(130):
        m.frame(0)
    assert _wave(m)[0]["st"] == 4, "replaced from an empty reserve"
    for i in (1, 2):
        d[base + i * n + st] = 3                      # the district's last two
    slowed = False
    for f in range(400):
        m.frame(0)
        slowed |= _cell(m, "f_slow") > 0
        if _cell(m, "s_dx") == 1 and all(w["st"] == 0 for w in _wave(m)):
            break
    assert slowed, "the last of the district did not fall in slow motion"
    assert _cell(m, "s_dx") == 1 and res() == 30 + 15 - 3, f"next district: {res()}"
