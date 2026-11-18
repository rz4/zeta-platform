"""test_registry.py -- the object flags word is a shared resource, and
nothing has ever guarded it.

Six features carry a bit here (CULL, GOURAUD, TEX, TINT, LODSPAN,
BLEND, OTINT, EDGE), the page selector owns 11:8, OBJ_OTINT's
light owns 31:17, and FIVE bits are free.
Those free bits are the cheapest expansion surface on the machine --
which is exactly why a design review of four independent programs
produced two that claimed the SAME ones, with nothing in the tree to
notice. This file is the notice.

It is deliberately mechanical: it derives what is claimed from spec.py
rather than from a list kept beside it, because a registry maintained by
hand is a registry that drifts from the law it describes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import spec

PAGE_MASK = spec.OBJ_PAGE_MASK << spec.OBJ_PAGE_SHIFT

# Names that are POSITIONS, not masks. OBJ_OTINT_SHIFT = 17 would read as
# bits 0 and 4 -- i.e. as a collision with CULL and LODSPAN -- and that is
# the exact shape of mistake this file exists to catch, so the list of
# things exempt from the reading has to be kept honest.
SELECTORS = ("OBJ_PAGE_SHIFT", "OBJ_PAGE_MASK", "OBJ_OTINT_SHIFT")


def claimed():
    """bit -> the OBJ_* constant that owns it, straight out of the law."""
    owners = {}
    for name, v in sorted(vars(spec).items()):
        if not (name.startswith("OBJ_") and isinstance(v, int)):
            continue
        if name in SELECTORS:
            continue
        for b in range(32):
            if v & (1 << b):
                owners.setdefault(b, []).append(name)
    for b in range(spec.OBJ_PAGE_SHIFT,
                   spec.OBJ_PAGE_SHIFT + spec.OBJ_PAGE_MASK.bit_length()):
        owners.setdefault(b, []).append("OBJ_PAGE")
    for b in range(spec.OBJ_OTINT_SHIFT, 32):       # the 5:5:5 tint FIELD
        owners.setdefault(b, []).append("OBJ_OTINT_TINT")
    return owners


def test_no_two_object_flags_share_a_bit():
    for bit, owners in claimed().items():
        assert len(owners) == 1, f"bit {bit} is claimed by {owners}"


def test_the_page_selector_does_not_overlap_a_flag():
    flags = 0
    for name, v in vars(spec).items():
        if name.startswith("OBJ_") and isinstance(v, int) \
                and name not in SELECTORS:
            flags |= v
    assert flags & PAGE_MASK == 0, (
        f"a flag overlaps the page selector at bits "
        f"{spec.OBJ_PAGE_SHIFT}..{spec.OBJ_PAGE_SHIFT + 2}")


def test_the_free_bits_are_written_down():
    """Not a constraint -- a LEDGER. It fails when the free set changes,
    so a new flag has to be declared here on the way in and cannot be
    claimed twice by two builds that never met."""
    free = sorted(set(range(32)) - set(claimed()))
    # bit 6 and 31:17 went to OBJ_OTINT in build 97 (stage 4a): the
    # flag, and the 15 bits of 5:5:5 light it reads.
    # bit 7 went to OBJ_EDGE in build 100 -- outlines from the identity
    # plane. SIX left, and they are the last cheap expansion this word
    # has: a feature needing a VALUE rather than a bit must look at the
    # `angles` word instead.
    # bit 11 went to the PAGE SELECTOR in build 105, when TEX_PAGES rose
    # 8 -> 16 and the selector had to grow from 10:8 to 11:8. FIVE left.
    # bit 12 went to the same selector in build 97, when TEX_PAGES rose
    # 16 -> 24 -- which is 34 M10K to 51, and 32 pages would have been
    # 68 against 29 blocks free. FOUR left, and they really are the last
    # of them.
    # bit 13 went to OBJ_LIT in build 98: a vertex word read as a
    # NORMAL rather than a colour, so light can vary across a surface.
    # THREE left.
    assert free == list(range(14, 17)), (
        f"the free object-flag bits moved to {free}. If a feature "
        f"claimed one, say so here; if one was released, say that.")
    assert len(free) == 3
