"""test_gaze.py -- spec.GAZE_BASE: eight pixels, answered at the flush.

THE ANSWERS ARE CHECKED AGAINST THINGS THAT DO NOT SHARE THEIR PATH.
The gaze reads the finished identity and depth planes; a test that read
the same planes to check it would pass a plane that is wrong in both
places (test_visible.py's lesson). So:

  the DEPTH is held against the pick register, which hears every commit
  to its one pixel as it happens and never looks at a finished plane;

  the OWNER is held against removal: take the named object out of the
  list and the pixel must change, take any other out and it must not.
  "Change" is its colour OR the depth the pick register hears there --
  the scene's cubes are one mesh, so an occluder leaves and the subject
  behind it shows the same colour (test_visible.py met this first).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import cabinet, carts, gpu, spec

CART = carts.path("gaze")
PIXELS = [(160, 20), (160, 158), (60, 180), (120, 180),
          (160, 180), (200, 180), (160, 205), (160, 270)]


def _machine(frames=12):
    m = cabinet.VirtualMachine(cabinet.load_cart(CART))
    for _ in range(frames):
        m.frame(0)
    return m


def _ask(m, pixels, n=None):
    """Render the machine's present scene with THIS list, hand back the
    picture and the eight answers."""
    d = list(m.vm.dmem)
    d[spec.GAZE_BASE] = len(pixels) if n is None else n
    for i, (x, y) in enumerate(pixels):
        d[spec.GAZE_BASE + 1 + i] = (y << 16) | x
    fb = np.asarray(gpu.render(d, m._cram, m._tex))
    return fb, [d[spec.GAZE_ANS + i] for i in range(spec.GAZE_MAX)], d


def test_the_depth_is_the_pick_registers_depth():
    m = _machine()
    _, ans, _ = _ask(m, PIXELS)
    for (x, y), a in zip(PIXELS, ans):
        d = list(m.vm.dmem)
        d[spec.PICK_X], d[spec.PICK_Y] = x, y
        gpu.render(d, m._cram, m._tex)
        assert a & 0xFFFF == d[spec.PICK_Z] & 0xFFFF, (
            f"pixel {(x, y)}: the gaze says depth {a & 0xFFFF}, the pick "
            f"register heard {d[spec.PICK_Z] & 0xFFFF}")


def test_the_owner_is_the_object_whose_removal_moves_the_pixel():
    m = _machine()
    here, ans, _ = _ask(m, PIXELS)
    n = m.vm.dmem[spec.OL_BASE]

    def heard(d, x, y):
        d[spec.PICK_X], d[spec.PICK_Y] = x, y
        fb = np.asarray(gpu.render(d, m._cram, m._tex))
        return fb, d[spec.PICK_Z]
    named = 0
    for (x, y), a in zip(PIXELS, ans):
        owner = a >> 16
        for k in range(n):
            d = list(m.vm.dmem)
            d[spec.OL_BASE + 1 + k * spec.OL_STRIDE] = 0      # nothing to walk
            gone, z_gone = heard(d, x, y)
            _, z_here = heard(list(m.vm.dmem), x, y)
            moved = bool((gone[y, x] != here[y, x]).any()) or z_gone != z_here
            assert moved == (owner == k + 1), (
                f"pixel {(x, y)}: the gaze names owner {owner}; removing "
                f"object {k} {'moved' if moved else 'did not move'} it")
        named += owner != 0
    assert named >= 4, f"the scene put objects under only {named} pixels"


def test_the_first_entry_out_of_order_ends_the_list():
    m = _machine()
    _, good, _ = _ask(m, PIXELS)
    bad = PIXELS[:4] + [(100, 180)] + PIXELS[5:]       # before the fourth
    _, ans, _ = _ask(m, bad)
    assert ans[:4] == good[:4]
    assert ans[4:] == [spec.GAZE_NONE] * 4, ans
    # the SAME pixel twice is not "strictly after" either
    _, ans, _ = _ask(m, PIXELS[:3] + [PIXELS[2]] + PIXELS[4:])
    assert ans[3:] == [spec.GAZE_NONE] * 5, ans


def test_a_pixel_off_the_glass_ends_the_list():
    m = _machine()
    for off in ((spec.W, 100), (10, spec.H)):
        _, ans, _ = _ask(m, [PIXELS[0], off, PIXELS[7]])
        assert ans[0] != spec.GAZE_NONE
        assert ans[1:] == [spec.GAZE_NONE] * 7, (off, ans)


def test_only_the_first_n_are_answered_and_n_is_clamped():
    m = _machine()
    _, full, _ = _ask(m, PIXELS)
    _, ans, _ = _ask(m, PIXELS, n=3)
    assert ans == full[:3] + [spec.GAZE_NONE] * 5
    _, ans, _ = _ask(m, PIXELS, n=1000)                 # more than there are
    assert ans == full


def test_a_cart_that_asks_nothing_has_nothing_written():
    """n = 0 is what every cart before this one holds. Its answer cells
    are its own, and the machine leaves them exactly as they were."""
    m = _machine()
    d = list(m.vm.dmem)
    d[spec.GAZE_BASE] = 0
    for i in range(spec.GAZE_MAX):
        d[spec.GAZE_ANS + i] = 0xC0FFEE00 + i
    gpu.render(d, m._cram, m._tex)
    assert [d[spec.GAZE_ANS + i] for i in range(spec.GAZE_MAX)] == \
        [0xC0FFEE00 + i for i in range(spec.GAZE_MAX)]


def test_the_gaze_changes_no_picture():
    m = _machine()
    with_, _, _ = _ask(m, PIXELS)
    without, _, _ = _ask(m, PIXELS, n=0)
    assert (with_ == without).all()


def test_no_cart_in_the_tree_already_lives_in_these_cells():
    """The cells were chosen as free. Hold that: no other cart's boot
    image writes them, so none of them changes meaning today."""
    lo, hi = spec.GAZE_BASE, spec.GAZE_ANS + spec.GAZE_MAX
    for name in carts.names():
        if name in ("gaze", "crowd"):       # the two that ask
            continue
        cart = cabinet.load_cart(carts.path(name))
        m = cabinet.VirtualMachine(cart)
        assert not any(m.vm.dmem[lo:hi]), f"{name} boots data into the gaze"
