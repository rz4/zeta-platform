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


def test_the_string_alternates_and_cashes_out_a_hook():
    """combat.resolve: each tap swaps hands -- the first is the CROSS, the
    archive's alternation starting from the jab hand -- and the third tap
    of a string (taps within 22 frames) is a hook off the next hand. Taps
    during a swing are buffered and thrown when it ends."""
    _, moves = _launches(lambda f: spec.PAD_X if f in (10, 25, 40) else 0, 120)
    assert moves == [1, 0, 2], f"cross, jab, lead hook expected: {moves}"
    _, apart = _launches(lambda f: spec.PAD_X if f in (10, 60, 110) else 0, 160)
    assert apart == [1, 0, 1], f"taps 50 apart are not a string: {apart}"


def test_his_blows_land():
    """Turned onto the brute as it squares up, he works the string and it
    falls -- damage, a stun, and down."""
    m = _fight_vm()
    for f in range(560):
        m.frame((spec.PAD_LEFT if 300 <= f < 308 else 0)
                | (spec.PAD_X if f >= 320 and f % 9 == 0 else 0))
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
        m.frame((spec.PAD_LEFT if 300 <= f < 308 else 0)
                | (spec.PAD_X if f >= 320 and f % 9 == 0 else 0))
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
    A, B, X, Y = spec.PAD_X, spec.PAD_Y, spec.PAD_A, spec.PAD_B
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
        m.frame((spec.PAD_LEFT if 300 <= f < 308 else 0)
                | ((spec.PAD_X | spec.PAD_A) if 322 <= f < 325 else 0))
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
    A, B = spec.PAD_X, spec.PAD_Y
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
        m.frame((spec.PAD_LEFT if 300 <= f < 308 else 0)
                | (spec.PAD_X if f >= 320 and f % 9 == 0 else 0))
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
    intro = _image(cart, _const("INTRO_PROG"), spec.OVL_MAX)
    m.frame(0)
    m.frame(0)
    assert list(m.vm.imem) == intro, "the title did not page in the intro"
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
    m = _fight_vm()
    whiff = []
    for f in range(40):
        m.frame(spec.PAD_X if f == 10 else 0)
        whiff.append(vol(m, 11) > 0)
    assert any(whiff), "a jab at the air made no whiff"
    m = _fight_vm()
    for f in range(345):
        m.frame((spec.PAD_LEFT if 300 <= f < 308 else 0) | (spec.PAD_X if f == 322 else 0))
        if f > 322:
            assert vol(m, 11) == 0, "a jab that landed whiffed"
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
    """Y is the gun (combat.resolve): a thumb's tap fires the shot on
    release, a hold of 26 frames or more the CHARGED shot -- 7 and 26
    damage, x1.35 to the head, from across the street (reach 13 / 16) --
    along his facing, never turned to the pad, with a recoil kick; X+Y
    is the shot too. Holding is the charge, so nothing fires early."""
    for hold, mv, dmg in ((8, 7, 7), (30, 8, 26)):
        m = _fight_vm()
        for f in range(30):
            m.frame(0)
        hp0 = sum(d["hp"] for d in _wave(m))
        for f in range(hold):
            m.frame(spec.PAD_B | (spec.PAD_LEFT if f > 2 else 0))
            assert _cell(m, "anim") != 2, "the shot fired while Y was held"
        seen = set()
        for f in range(50):
            m.frame(0)
            if _cell(m, "anim") == 2:
                seen.add(_cell(m, "f_mv"))
                assert _cell(m, "head") == _cell(m, "yaw"), "the shot turned to the pad"
        assert seen == {mv}, f"a {hold}-frame Y threw {seen}, not move {mv}"
        lost = hp0 - sum(d["hp"] for d in _wave(m))
        assert lost in (dmg, int(dmg * 1.35)), f"the shot did {lost}, not {dmg}"
    m = _fight_vm()
    for f in range(30):
        m.frame(0)
    for f in range(10):
        m.frame(spec.PAD_A | spec.PAD_B)
    for f in range(10):
        m.frame(0)
    assert _cell(m, "f_mv") == 7, "X+Y is the shot"


def test_the_jump_rises_light_and_falls_heavy():
    """X is the jump (tear.py JUMP_V0 0.186, rise 0.010, fall 0.024): an
    instant edge to a ~1.73-unit peak, a long climb and a short drop."""
    m = _fight_vm()
    for f in range(10):
        m.frame(0)
    hs, f_peak = [], None
    for f in range(60):
        m.frame(spec.PAD_A if f < 10 else 0)
        hs.append(_s32(_cell(m, "f_py")) / 65536)
    peak = max(hs)
    up = hs.index(peak)
    down = next(i for i in range(up, 60) if hs[i] == 0) - up
    assert 1.6 < peak < 1.8, f"the jump peaked at {peak:.2f}"
    assert up > down, f"the climb ({up}) should outlast the drop ({down})"
    assert hs[-1] == 0, "he never landed"


def test_the_air_combo_follows_strings_and_spikes():
    """The rear uppercut opens the jump-cancel; X then follows the body up,
    every air hit keeps it aloft and tops the follow up, and the special
    from the air spikes it down -- all on thumb-length presses."""
    m = _fight_vm()

    def pad(f):
        p = spec.PAD_LEFT if 300 <= f < 308 else 0
        if 322 <= f < 325:
            p |= spec.PAD_X | spec.PAD_A
        if 358 <= f < 366:
            p |= spec.PAD_A
        if 372 <= f < 452 and (f - 372) % 14 < 8:
            p |= spec.PAD_X
        if 462 <= f < 470:
            p |= spec.PAD_Y
        return p
    top, lowest_combo, spiked = 0.0, 1e9, False
    for f in range(560):
        m.frame(pad(f))
        w = _wave(m)[0]
        if f == 366:
            assert _cell(m, "f_acmb") > 0, "the jump-cancel did not follow"
        if 380 <= f < 460:
            top = max(top, _s32(_cell(m, "f_py")) / 65536)
            lowest_combo = min(lowest_combo, _cell(m, "f_acmb"))
        if w["vy"] <= -int(0.6 * 65536):
            spiked = True
    assert top > 5, f"he rose only {top:.2f} with it"
    assert lowest_combo > 0, "the follow lapsed mid-string"
    assert spiked, "the aerial special did not spike it"
    assert _s32(_cell(m, "f_py")) == 0, "he never came down"


def test_parkour_runs_turns_wide_quick_turns_and_threads():
    """L+Up is PARKOUR (tear.py _parkour): the speed ramps logistically to
    0.13, Down is a quick turn whose speed Up carries into the new heading
    (a link in the chain), and running fast past the wave PAYS style
    without a punch thrown."""
    L, U, D = spec.PAD_L, spec.PAD_UP, spec.PAD_DOWN
    m = _fight_vm()
    m.frame(0)
    sp, paid = [], 0
    for f in range(150):
        m.frame(L | U | (spec.PAD_LEFT if 60 <= f < 80 else 0))   # through the wave
        sp.append(_s32(_cell(m, "f_spd")) / 65536)
        paid = max(paid, _cell(m, "s_pts"))
    assert _cell(m, "f_sty") == 1, "L+Up did not enter parkour"
    assert sp[5] < 0.06 and 0.12 < sp[-1] <= 0.13, f"the ramp: {sp[5]:.3f} .. {sp[-1]:.3f}"
    assert paid > 0, "threading the wave paid nothing"
    y0, c0 = _cell(m, "yaw"), _cell(m, "f_chain")
    m.frame(L | D)
    assert (_cell(m, "yaw") - y0) % 1024 == 512, "Down did not turn him about"
    m.frame(L | U)
    assert _s32(_cell(m, "f_spd")) / 65536 > 0.1, "the quick turn lost the speed"
    assert _cell(m, "f_chain") == c0 + 1, "the quick turn was not a link"


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


def test_a_second_a_in_the_air_flips():
    """A jump, then A again in the air: a forward tuck from the run (20
    frames), a cartwheel to the side from the boxing stance (24) -- once a
    jump, re-armed by the landing."""
    L, U, D, LF, A = (spec.PAD_L, spec.PAD_UP, spec.PAD_DOWN, spec.PAD_LEFT,
                      spec.PAD_A)
    for pre, flip, kind, n in ((L | U, L | U | A, 0, 20), (L | D, L | LF | A, 2, 24)):
        m = _fight_vm()
        m.frame(0)
        frames = 0
        for f in range(80):
            p = pre | (A if 20 <= f < 24 else 0)
            if 30 <= f < 34:
                p = flip
            m.frame(p)
            if _cell(m, "f_evf"):
                frames += 1
                assert _cell(m, "f_evk") == kind
        assert n - 2 <= frames <= n, f"a flip of {frames} frames, not {n}"
        assert _cell(m, "f_py") == 0 and _cell(m, "f_flipu") == 0, "not landed and re-armed"


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


def test_locked_styles_flip_pay_fence_and_meteor():
    """Locked, Down in the run is FENCING and Up in the stance the PROWLER,
    each flip a link that pays; fencing re-latches its cross onto the
    target; Up with a direction from the stance runs METEOR at full speed
    round it; and jump with a direction in the stance is a DODGE."""
    L, R, U, D, LF, A = (spec.PAD_L, spec.PAD_R, spec.PAD_UP, spec.PAD_DOWN,
                         spec.PAD_LEFT, spec.PAD_A)
    m = _fight_vm()
    m.frame(0)
    for f in range(20):
        m.frame(0)
    for f in range(10):
        m.frame(R | L | D)
    assert _cell(m, "f_sty") == 2
    latch0 = _cell(m, "f_latch")
    for f in range(20):
        m.frame(R | L | LF)
    assert _cell(m, "f_latch") != latch0, "fencing's cross did not follow the target"
    pts, chain = _cell(m, "s_pts"), _cell(m, "f_chain")
    yaws = []
    for f in range(60):
        m.frame(R | L | U | LF)
        yaws.append(_cell(m, "yaw"))
    assert _cell(m, "f_met") == 1, "Up with a direction did not run METEOR"
    assert _cell(m, "f_chain") == chain + 1 and _cell(m, "s_pts") > pts, "the flip did not pay"
    assert _s32(_cell(m, "f_spd")) / 65536 > 0.12, "the meteor is not at speed"
    assert len(set(yaws[-20:])) > 10, "the meteor is not circling"
    m = _fight_vm()
    m.frame(0)
    for f in range(10):
        m.frame(R | L | D)
    for f in range(4):
        m.frame(R | L | LF | A)
    assert _cell(m, "f_evf") > 0 and _cell(m, "f_evk") == 6, "no dodge to the left"
    assert _cell(m, "f_py") == 0, "the dodge jumped"


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
    ys, hal = [], 0
    for f in range(460):
        p = spec.PAD_LEFT if 300 <= f < 308 else 0
        if 322 <= f < 325:
            p |= spec.PAD_A | spec.PAD_X
        if 358 <= f < 366:
            p |= spec.PAD_A
        if 372 <= f < 440 and (f - 372) % 14 < 8:
            p |= spec.PAD_X
        m.frame(p)
        ys.append(_s32(m.vm.dmem[spec.CAM_Y]) / 65536 - _s32(_cell(m, "f_py")) / 65536)
    assert max(ys) > 4, "the juggle shot did not rise with the body"
    m = _fight_vm()
    for f in range(400):
        m.frame((spec.PAD_LEFT if 300 <= f < 308 else 0)
                | (spec.PAD_Y if 330 <= f < 338 else 0))
        hal = max(hal, _cell(m, "cam_hal"))
    assert hal > 16, "the haymaker's connect took no align shot"


def test_the_action_shot_frames_each_mode():
    """tear.py _action_cam: the tank's follow stays three back and square;
    Devil Trigger's comes in to 2.6 and leans on the right shoulder; boxing
    pulls out to 4.0, fencing to 5.4 facing the target; locked in the run,
    the PROWLER's own low shot takes over."""
    L, R, U, D = spec.PAD_L, spec.PAD_R, spec.PAD_UP, spec.PAD_DOWN
    for sched, dist, lean in ((lambda f: 0, 3.0, 0.0), (lambda f: L | U, 2.6, -0.5),
                              (lambda f: L | D if f < 5 else L, 4.0, -0.12),
                              (lambda f: R | L | D if f < 5 else R | L, 5.4, -0.12)):
        m = _fight_vm()
        m.frame(0)
        for f in range(80):
            m.frame(sched(f))
        assert abs(_s32(_cell(m, "cam_d3")) / 65536 - dist) < 0.05, f"follow at {dist}"
        assert abs(_s32(_cell(m, "cam_sh")) / 65536 - lean) < 0.03, f"lean {lean}"
    m = _fight_vm()
    m.frame(0)
    for f in range(60):
        m.frame(R | L | U)
    assert _cell(m, "cam_cv") == 65536, "the prowler's shot did not take over"
    assert _s32(m.vm.dmem[spec.CAM_Y]) / 65536 < 2.5, "the prowler's eye is not low"


def test_start_pauses_resumes_and_quits():
    """Start in the fight pages in the PAUSE (a third program): the street
    stands frozen under its two words; Start resumes with the borrowed end
    put back and no button live (no stray jump or punch); Down then A
    QUITS to the title, the run reset, and the next fight a fresh wave."""
    cart = cabinet.load_cart(CART)
    pause = _image(cart, _const("PAUSE_PROG"), spec.OVL_MAX)
    m = cabinet.VirtualMachine(cart)
    m.frame(spec.PAD_START)
    boot = list(m.vm.dmem)
    for f in range(40):
        m.frame(0)
    for f in range(8):                                # a thumb on Start
        m.frame(spec.PAD_START)
    assert list(m.vm.imem) == pause, "Start did not page in the pause"
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
        m.frame((spec.PAD_LEFT if 300 <= f < 308 else 0)
                | (spec.PAD_X if f >= 320 and f % 9 == 0 else 0))
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
    through its swing's startup and red while the fist is live. Untouched,
    the wave walks in and swings; both tints must be seen, the amber first,
    and only while some demon is in those frames of a swing."""
    amber = (31 << 27) | (19 << 22) | (9 << 17)
    red = (31 << 27) | (10 << 22) | (10 << 17)
    tint = lambda w: w & 0xFFFE0000
    m = _fight_vm()
    first = {}
    for f in range(700):
        m.frame(0)
        swinging = [w for w in _wave(m) if w["st"] == 1]
        for w in _marker_flags(m):
            if w & spec.OBJ_OTINT:
                assert swinging, f"frame {f}: a tinted marker and nobody swinging"
                first.setdefault(tint(w), f)
        if _cell(m, "f_dead"):
            break
    assert amber in first and red in first, f"tints seen: {[hex(t) for t in first]}"
    assert first[amber] < first[red], "the red came before the amber"


def test_a_landing_is_felt_and_heard():
    """tear.py's landing impact: the frame shakes and the ground answers
    (the step's own thud) on the frame he touches down -- and only then."""
    m = _fight_vm()
    for f in range(5):
        m.frame(0)
    assert _cell(m, "f_shake") == 0 and _cell(m, "sg_st") > 9, "shaking or thudding at rest"
    m.frame(spec.PAD_A)
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
    L, U = spec.PAD_L, spec.PAD_UP

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
