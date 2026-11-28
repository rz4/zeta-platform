"""test_dmem_map.py -- no two legislated regions may overlap.

The forge stops a CART from placing two resources on top of each other.
Nothing stopped SPEC.PY from doing it, and it did: when OL_MAX rose from
16 to 64 (build 89) the object list grew to 14084..14468, straight
through AU_BASE at 14184. Object 16's entry spans 14181..14186, so a
cart with seventeen objects overwrote its own audio registers.

It survived three builds because fabric.zol -- the only cart with many
objects -- peaks at exactly SIXTEEN, whose last entry ends at 14180.
Four words short. Every gate was green.

The arithmetic in that amendment's own comment was "DMEM above the list
is 2,203 words free and 64 objects want 385" -- correct against the TOP
of memory, and blind to what sat in between. That is the shape of the
bug this file exists to catch: a region sized against the wrong
neighbour.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import spec


def regions():
    """Every legislated DMEM region: (name, first, count)."""
    r = [
        ("display list", spec.DL_BASE, 1 + spec.DL_MAX * spec.DL_STRIDE),
        ("object list", spec.OL_BASE, 1 + spec.OL_MAX * spec.OL_STRIDE),
        ("audio registers", spec.AU_BASE, 2 * spec.AU_CHANNELS),
        ("audio events", spec.AU_EV_BASE, 1 + 2 * spec.AU_EV_MAX),
        # THE RETURNS. Both went in as MULTI-WORD regions and neither was
        # listed here when it landed -- VIS_BASE took 64 words in build
        # 94 and this file did not know, which is exactly the blindness
        # it was written for. A region that is not listed is a region
        # nothing checks.
        ("visible pixels", spec.VIS_BASE, spec.OL_MAX),
        ("heard amplitude", spec.AUD_BASE, spec.AU_CHANNELS),
        ("the gaze", spec.GAZE_BASE, 1 + 2 * spec.GAZE_MAX),
        ("the long list's pointer", spec.OLX_PTR, 1),
        ("the long list's counts", spec.VISX_BASE, spec.OLX_MAX - spec.OL_MAX),
        ("compositor", spec.CO_BASE, 1 + spec.CO_MAX * spec.CO_STRIDE),
        ("card diag", spec.CARD_DIAG, 4),
        ("loader signature", spec.LOADER_SIG, spec.LOADER_SIG_WORDS),
        ("loader mirror", spec.LOADER_SIG2, spec.LOADER_SIG_WORDS),
    ]
    for name in ("PICK_X", "PICK_Y", "PICK_ID", "PICK_Z", "CAM_PITCH",
                 "CAM_X", "CAM_Y", "CAM_Z", "CAM_YAW", "CAM_ROLL",
                 "DMA_SRC", "DMA_DST", "DMA_LEN", "DMA_GO",
                 "DMA2_SRC", "DMA2_DST", "DMA2_LEN", "DMA2_GO",
                 "OVL_SRC", "OVL_DST", "OVL_LEN", "OVL_GO",
                 "FOG_RGB", "FOG_NEAR", "FOG_SHIFT", "LOD_FLAT",
                 "SD_SLOT", "SD_OFF", "SD_DST", "SD_LEN", "SD_GO",
                 "WAV_SRC", "TEX_SRC", "TEX_PAGE", "BG_SRC",
                 "REG_FRAME", "REG_PAD",
                 "PICK_SH", "EDGE_RGB", "GRADE_SRC", "AU_RESET", "SEG_BASE"):
        r.append((name, getattr(spec, name), 1))
    return r


def test_no_two_legislated_regions_overlap():
    rs = sorted(regions(), key=lambda t: t[1])
    bad = []
    for (an, aa, ac), (bn, ba, bc) in zip(rs, rs[1:]):
        if aa + ac > ba:
            bad.append(f"{an} [{aa}..{aa + ac - 1}] overruns "
                       f"{bn} [{ba}..{ba + bc - 1}]")
    assert not bad, ("legislated DMEM regions collide:\n  "
                     + "\n  ".join(bad))


def test_every_region_fits_in_dmem():
    for name, base, count in regions():
        assert base + count <= spec.DMEM_WORDS, \
            f"{name} runs to {base + count - 1}, past DMEM"


def test_the_object_list_can_actually_hold_OL_MAX_objects():
    """The cap that matters is the one the NEXT region imposes, not the
    one the top of memory imposes -- which is exactly the mistake."""
    last = spec.OL_BASE + 1 + spec.OL_MAX * spec.OL_STRIDE - 1
    nxt = min(b for n, b, c in regions()
              if b > spec.OL_BASE and n != "object list")
    assert last < nxt, (
        f"OL_MAX={spec.OL_MAX} needs up to word {last}, but the next "
        f"legislated region starts at {nxt}: a cart with enough objects "
        f"would write through it")
