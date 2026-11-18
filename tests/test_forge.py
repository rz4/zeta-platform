"""test_forge.py -- the linker cannot be fooled the way a human can.

The forge exists because of one bug. fabric.zol's floor grew, its sine
table landed INSIDE the mesh's face data, and both machines skipped the
corrupt indices identically -- so the CROSS STAYED GREEN and the only
symptom was bands of missing tiles, mis-diagnosed as near-plane clipping
twice before the player said "it shows up in the front view".

Hand-written carts guard that with `assert base + len <= next`, once per
cart, written by whoever remembered. These tests pin the property
itself: no two resources can overlap, nothing can land on a reserved
region, and every limit in spec.py is enforced in one place.
"""
import pytest

from zeta import asm, forge, spec, vm
from zeta.forge import Cart, ForgeError, Mesh, Plate, Table, TexturePage


def tri(nv=3, colors=None, uvs=None):
    return Mesh([0, 0, 0] * nv, [(0, 1, 2, 0xFFFFFF)],
                colors=colors, uvs=uvs)


# --------------------------------------------------------------------------
# the bug class the forge was built to kill
# --------------------------------------------------------------------------
def test_placed_resources_never_overlap():
    c = Cart("t")
    syms = [c.data(Table(range(k * 7 + 1)), f"r{k}") for k in range(30)]
    spans = sorted((int(s), int(s) + s.length) for s in syms)
    for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
        assert a1 <= b0, f"resource at {a0}..{a1} overlaps {b0}..{b1}"


def test_content_never_lands_on_a_reserved_region():
    c = Cart("t")
    lo, hi = forge._reserved()
    for k in range(40):
        s = c.data(Table(range(50)), f"r{k}")
        assert int(s) >= lo, "content landed on the low registers"
        assert int(s) + s.length <= hi, "content reached the DL/register block"


def test_a_cart_that_overruns_dmem_fails_loudly():
    c = Cart("t")
    with pytest.raises(ForgeError) as e:
        for _ in range(400):
            c.data(Table(range(64)))
    assert "DMEM full" in str(e.value)


def test_scratch_variables_come_from_the_same_pool():
    """A cart variable cannot land on a mesh, which is the other half of
    the same bug -- fabric.zol's cells were hand-numbered 16..38."""
    c = Cart("t")
    m = c.data(tri(), "mesh")
    v = c.var("state")
    assert not (int(m) <= int(v) < int(m) + m.length)


def test_cram_never_hands_out_offset_zero():
    """BG_SRC reads 0 as "no backdrop" (gpu.render: `if bg > 0`), so a
    plate placed at CRAM 0 is silently disabled -- the frame clears to
    flat colour and nothing says why. The first plate ever baked landed
    there."""
    c = Cart("t")
    first = c.cram(Table(range(10)), "plate")
    assert int(first) > 0, "a resource at CRAM 0 can never be a backdrop"


# --------------------------------------------------------------------------
# the law, enforced once instead of per cart
# --------------------------------------------------------------------------
def test_a_mesh_over_the_vertex_cap_is_refused():
    with pytest.raises(ForgeError) as e:
        Cart("t").data(tri(spec.MESH_NV_MAX + 1))
    assert str(spec.MESH_NV_MAX) in str(e.value)


def test_a_face_indexing_a_missing_vertex_is_refused():
    with pytest.raises(ForgeError):
        Cart("t").data(Mesh([0, 0, 0], [(0, 9, 2, 0)]))


def test_wrong_number_of_vertex_colours_is_refused():
    with pytest.raises(ForgeError):
        Cart("t").data(Mesh([0, 0, 0] * 3, [(0, 1, 2, 0)], colors=[1, 2]))


def test_boot_refuses_to_write_into_the_content_region():
    c = Cart("t")
    lo, _ = forge._reserved()
    with pytest.raises(ForgeError) as e:
        c.boot(lo + 10, 1)
    assert "CONTENT region" in str(e.value)
    c.boot(spec.CAM_Y, 5)          # a register cell is fine
    c.boot(spec.FOG_SHIFT, 8)


# --------------------------------------------------------------------------
# resources: the flags fall out of the type, so a mesh cannot be mislabelled
# --------------------------------------------------------------------------
def test_flags_follow_the_data():
    assert tri().flags == spec.OBJ_CULL
    assert tri(colors=[1, 2, 3]).flags == spec.OBJ_CULL | spec.OBJ_GOURAUD
    assert tri(uvs=[1, 2, 3]).flags == spec.OBJ_CULL | spec.OBJ_TEX


def test_a_mesh_cannot_be_both_gouraud_and_textured():
    with pytest.raises(AssertionError):
        Mesh([0, 0, 0] * 3, [(0, 1, 2, 0)], colors=[1, 2, 3], uvs=[1, 2, 3])


def test_a_texture_page_carries_its_own_mip_chain():
    page = [[0x7FFF] * spec.TEX_W for _ in range(spec.TEX_W)]
    w = TexturePage(page).words()
    assert len(w) == spec.TEX_WORDS
    # every mip level of an all-white page is still white
    for off in spec.TEX_MIP_OFF:
        assert (w[off // 2] & 0xFFFF) == 0x7FFF or off == 0


def test_a_plate_puts_depth_in_the_high_half():
    n = spec.BG_WORDS
    w = Plate([0x1234] * n, [0xABCD] * n).words()
    assert w[0] & 0xFFFF == 0x1234
    assert (w[0] >> 16) & 0xFFFF == 0xABCD


# --------------------------------------------------------------------------
# the program: labels unique by construction
# --------------------------------------------------------------------------
def test_labels_are_unique_however_often_a_helper_is_emitted():
    c = Cart("t")
    v = c.var("x")
    p = c.program()
    for _ in range(5):
        p.clamp(v, -10, 10)                 # emits two labels each time
        p.toward_zero(v, 1)
    marks = [ln[:-1] for ln in p.lines() if ln.endswith(":")]
    assert len(marks) == len(set(marks)), f"duplicate labels: {marks}"


# --------------------------------------------------------------------------
# end to end: what the forge writes, the assembler reads and the VM runs
# --------------------------------------------------------------------------
def test_a_forged_cart_assembles_and_runs(tmp_path):
    c = Cart("smoke")
    m = c.data(tri(colors=[0xFF0000, 0x00FF00, 0x0000FF]), "tri")
    n = c.var("n")
    c.boot(spec.CAM_Z, -4 * forge.ONE)
    p = c.program()
    p.set(n, 0)
    p.object(n, int(m), 0, 0, 0, 0, spec.OBJ_CULL | spec.OBJ_GOURAUD)
    p.load(n).store(spec.OL_BASE)
    p.emit("halt")
    path = c.write(tmp_path / "smoke.zol")

    machine = vm.VM(asm.assemble(path))
    for _ in range(3):
        machine.frame(0)
        machine.dma()
        machine.overlay()
        machine.card()
    assert not machine.trapped
    assert machine.dmem[spec.OL_BASE] == 1
    assert machine.dmem[spec.CAM_Z] == spec.s32(-4 * forge.ONE) & spec.WORD_MASK


def test_the_build_is_deterministic(tmp_path):
    """Same inputs, same cart -- or the gates below it mean nothing."""
    def build():
        c = Cart("d")
        c.data(tri(), "a")
        c.data(forge.sine_table(), "b")
        p = c.program()
        p.set(c.var("v"), 3)
        p.emit("halt")
        return c.lines()
    assert build() == build()


# --------------------------------------------------------------------------
# the founding bug class, both halves
# --------------------------------------------------------------------------
def test_a_mesh_over_the_face_cap_is_refused():
    """THE CAPACITY HALF. check() enforced MESH_NV_MAX and not
    MESH_NF_MAX, so an oversized mesh linked clean and was then dropped
    WHOLE and IDENTICALLY by gpu.py and zseq.v -- which is precisely the
    shape the cross gate cannot see. The forge exists to end this."""
    verts = [v for i in range(8) for v in (i << 16, 0, i << 16)]
    faces = [(0, 1, 2, 0xFFFFFF)] * (spec.MESH_NF_MAX + 1)
    with pytest.raises(forge.ForgeError, match="MESH_NF_MAX"):
        forge.Mesh(verts, faces).check()
    # and one exactly at the cap still links
    forge.Mesh(verts, faces[:spec.MESH_NF_MAX]).check()


def test_the_loader_signature_mirror_is_not_allocatable():
    """LOADER_SIG2 is 11700 and _reserved() looked for registers above
    12000, so those eight words were in the content pool. Hardware
    rewrites them every boot and the VM does not: a cross that goes red
    on glass with nothing in the picture to say why."""
    lo, hi = forge._reserved()
    assert hi <= spec.LOADER_SIG2, (
        f"content pool runs to {hi}, over the loader's mirror at "
        f"{spec.LOADER_SIG2}")


def test_a_cart_filling_the_pool_never_reaches_the_mirror():
    """The property, not the arithmetic: allocate until the forge says
    stop, then check nothing landed on the loader's cells."""
    c = Cart("full")
    lo, hi = forge._reserved()
    placed = []
    try:
        for k in range(64):
            placed.append(c.data(forge.Table([0] * 256), f"t{k}"))
    except forge.ForgeError:
        pass
    assert placed, "the pool refused even one table"
    for s in placed:
        assert not (int(s) <= spec.LOADER_SIG2 < int(s) + s.length), \
            f"resource {s.name} covers LOADER_SIG2"


# --------------------------------------------------------------------------
# TEXT -- Tier-1 primitive #1, in the display list nothing was using
# --------------------------------------------------------------------------
def test_a_glyph_covers_to_few_rectangles():
    """The whole viability of display-list text is the cover: at 3.61
    rectangles a glyph, 256 triangles is about 35 characters. If a change
    to the font pushes that up, text silently stops fitting."""
    n = [len(forge.glyph_rects(c)) for c in forge.FONT3X5 if c != " "]
    assert max(n) <= 6
    assert sum(n) / len(n) < 4.0


def test_text_refuses_to_overflow_the_display_list():
    forge.Text("SHORT", 0, 0).check()
    with pytest.raises(forge.ForgeError, match="DL_MAX"):
        forge.Text("X" * 200, 0, 0).check()


def test_text_actually_draws(tmp_path):
    """Not 'the words are in DMEM' -- PIXELS. The display list is the one
    budget every 3D cart leaves at zero, so this is also the proof that
    the path from a baked resource to a lit pixel works at all."""
    from zeta import gpu, vm as vmod
    c = Cart("t")
    sym = c.data(forge.Text("ZETA", 40, 120, rgb=0xE6C010), "m")
    p = c.program()
    p.set_text(sym)
    p.emit("halt")
    m = vmod.VM(asm.assemble(c.write(tmp_path / "t.zol")))
    for _ in range(2):
        m.frame(0)
    assert m.dmem[spec.DL_BASE] > 0, "the copy wrote no triangles"
    fb = gpu.render(m.dmem)
    lit = (fb == spec.display_rgb(0xE6C010)).all(axis=2).sum()
    assert lit > 100, f"text drew {lit} pixels"
    # and hiding it is one store
    p2 = c.program()
    assert "12288" in " ".join(p2.hide_text()._out)
