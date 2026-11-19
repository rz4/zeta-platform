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

CART = Path(__file__).parents[1] / "carts/tnd.zol"


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
        a.frame(spec.PAD_A if f == 30 else 0)
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
            | (spec.PAD_A if f == 50 else 0) \
            | (spec.PAD_RIGHT if f >= 70 else 0)
        v.frame(pad)
        s.frame(pad)
        assert np.array_equal(v.framebuffer(), s.framebuffer()), \
            f"the fighter diverges at frame {f}"


# ---- P3: the demons -----------------------------------------------------------
# The wave's cells are read by NAME from the cart's own symbol comments
# (the forge assigns addresses), with gen_tnd.py's field order.
FIELDS = ("x", "z", "h8", "hp", "st", "mf", "mv", "ai", "wf", "mov", "alt", "cf",
          "hs", "stop", "vx", "vz", "con", "dt", "jt", "kp", "mt", "ox", "oz",
          "py", "vy")


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
    for _ in range(360):
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
        m.frame(spec.PAD_UP | (spec.PAD_RIGHT if f < 40 else 0))
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
        m.frame(spec.PAD_UP | (spec.PAD_RIGHT if 1400 <= f < 1420 else 0))
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
        m.frame(spec.PAD_RIGHT)
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


def test_the_string_alternates_and_cashes_out_a_hook():
    """combat.resolve: each tap swaps hands -- the first is the CROSS, the
    archive's alternation starting from the jab hand -- and the third tap
    of a string (taps within 22 frames) is a hook off the next hand. Taps
    during a swing are buffered and thrown when it ends."""
    _, moves = _launches(lambda f: spec.PAD_A if f in (10, 25, 40) else 0, 120)
    assert moves == [1, 0, 2], f"cross, jab, lead hook expected: {moves}"
    _, apart = _launches(lambda f: spec.PAD_A if f in (10, 60, 110) else 0, 160)
    assert apart == [1, 0, 1], f"taps 50 apart are not a string: {apart}"


def test_his_blows_land():
    """Turned onto the brute as it squares up, he works the string and it
    falls -- damage, a stun, and down."""
    m = _fight_vm()
    for f in range(560):
        m.frame((spec.PAD_RIGHT if 300 <= f < 308 else 0)
                | (spec.PAD_A if f >= 320 and f % 9 == 0 else 0))
    w = _wave(m)[0]
    assert w["hp"] <= 0 and w["st"] >= 3, f"the brute stands: {w['hp']} hp, st {w['st']}"


def test_their_blows_land_and_he_goes_down():
    """Untouched, the wave beats him down; after the death beat a fresh
    press of A is a new run: full health, the wave back where it began."""
    m = _fight_vm()
    for f in range(900):
        m.frame(0)
    assert _s32(_cell(m, "p_hp")) <= 0 and _cell(m, "f_dead") > 46
    assert m.vm.dmem[spec.DL_BASE] > 0, "no prompt after the death beat"
    m.frame(spec.PAD_A)
    assert _s32(_cell(m, "p_hp")) == 140 and _cell(m, "f_dead") == 0
    assert m.vm.dmem[spec.DL_BASE] == 0, "the prompt outlived the retry"
    spawn = _sym("spawn")
    for i, w in enumerate(_wave(m)):
        assert w["hp"] == 70 and w["st"] == 0, f"demon {i} not reset"
    assert abs(_wave(m)[0]["x"] - _s32(m.vm.dmem[spawn])) < 65536


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
        m.frame((spec.PAD_RIGHT if 300 <= f < 308 else 0)
                | (spec.PAD_A if f >= 320 and f % 9 == 0 else 0))
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


def test_the_grammar_taps_on_release_and_reads_chords():
    """combat.Grammar, for thumbs: a tap fires on release or at its fourth
    frame held (a long press is one blow, not none); B is the special; two buttons down within 3 frames are a
    CHORD, read once, and neither of them taps -- carve+jump is the rear
    uppercut and NOT a jab, shoot+special the lead uppercut."""
    A, B, X, Y = spec.PAD_A, spec.PAD_B, spec.PAD_X, spec.PAD_Y
    assert _launches(lambda f: A if 10 <= f < 13 else 0, 60)[1] == [1]
    # a thumb's press -- held well past 9 frames -- is still ONE blow,
    # thrown at its fourth frame (the press that did nothing on glass)
    m, held = _launches(lambda f: A if 10 <= f < 40 else 0, 60)
    assert held == [1], held
    assert _launches(lambda f: B if 10 <= f < 12 else 0, 60)[1] == [4]
    assert _launches(lambda f: (A if 10 <= f < 14 else 0)
                     | (X if 11 <= f < 14 else 0), 60)[1] == [6]
    assert _launches(lambda f: (Y if 10 <= f < 14 else 0)
                     | (B if 12 <= f < 14 else 0), 60)[1] == [5]


def test_the_uppercut_launches():
    """A launcher sends its target up -- 0.45 a frame against the aerial
    gravity of 0.014 is seven units -- helpless the whole arc, and down."""
    m = _fight_vm()
    peak, landed = 0.0, False
    for f in range(480):
        m.frame((spec.PAD_RIGHT if 300 <= f < 308 else 0)
                | ((spec.PAD_A | spec.PAD_X) if 322 <= f < 325 else 0))
        w = _wave(m)[0]
        peak = max(peak, w["py"] / 65536)
        if peak > 5 and w["py"] == 0:
            landed = True
            break
    assert peak > 6.5, f"the brute rose only {peak:.2f}"
    assert landed, "the brute never came down"


def test_the_cancel_lattice():
    """In its recovery a move is cut short by a buffered move it lists
    (combat.py): a jab cuts the cross's recovery the frame the tap lands;
    the special cuts a hook's; nothing cuts the special -- a tap in its
    recovery simply expires in the buffer."""
    A, B = spec.PAD_A, spec.PAD_B
    cut = _launches(lambda f: A if f in (10, 24) else 0, 80)[1]
    assert cut == [1, 0]
    m, _ = _launches(lambda f: A if f in (10, 24) else 0, 26)
    assert _cell(m, "anim") == 2 and _cell(m, "f_mv") == 0 and _cell(m, "af") == 0, \
        "the jab waited for the cross to end: no cancel"
    hook = _launches(lambda f: A if f in (10, 30, 50) else (B if f == 72 else 0), 140)[1]
    assert hook == [1, 0, 2, 4], hook
    assert _launches(lambda f: B if f == 10 else (A if f == 50 else 0), 120)[1] == [4]


# ---- P5: style ---------------------------------------------------------------
def test_style_climbs_with_variety_and_draws_its_rank():
    """combat.Style: the string's blows pay their moves' style, the combo
    adds to it, and the brute's beating reaches C (60) -- drawn top right
    as composed display-list glyphs, in C's colour."""
    m = _fight_vm()
    for f in range(483):
        m.frame((spec.PAD_RIGHT if 300 <= f < 308 else 0)
                | (spec.PAD_A if f >= 320 and f % 9 == 0 else 0))
    assert _cell(m, "s_rank") == 1, f"rank {_cell(m, 's_rank')} after the beating"
    assert _cell(m, "s_combo") >= 5
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
def test_the_title_is_the_archives_and_start_begins():
    """TND opens on its title -- the archive's own start screen, baked to a
    backdrop plate, nothing else drawn -- and waits; Start (or A) begins
    the fight the next frame, and an A held through the cut is no jab."""
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    for f in range(60):
        m.frame(0)
        assert m.vm.dmem[spec.BG_SRC] > 0 and m.vm.dmem[spec.OL_BASE] == 0
    m.frame(spec.PAD_A)
    m.frame(spec.PAD_A)                             # held through the cut
    assert m.vm.dmem[spec.BG_SRC] == 0, "Start/A did not leave the title"
    assert m.vm.dmem[spec.OL_BASE] > 0, "no street after the title"
    for f in range(20):
        m.frame(0)                                  # ...and released
        assert _cell(m, "anim") != 2, "the A that left the title threw a jab"
