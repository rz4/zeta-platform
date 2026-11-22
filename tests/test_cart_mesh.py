"""THE CART MESH (spec.OBJ_CART; experiment, exp/cart-mesh -- the law only).

A mesh read from the cart's CRAM segment in three streams (16-bit vertices,
packed faces, 5:5:5 colours) is the SAME PICTURE, to the pixel, as that
mesh sitting in DMEM: only where it is read from has changed. A pose is a
new pair of offsets, and nothing is moved.
"""
import numpy as np
import pytest

from zeta import gpu, spec
from zeta.forge import ONE, Mesh

SHIFT = 2
DESC, MESH_AT, CART_AT = 200, 400, 5000


def _body(seed, nv=40, nf=60):
    """a lump of triangles about the origin: vertices on the 16-bit grid,
    colours on the 5-bit one, so both homes hold exactly the same mesh"""
    r = np.random.default_rng(seed)
    v16 = r.integers(-12000, 12000, (nv, 3))
    faces = [tuple(int(i) for i in r.choice(nv, 3, replace=False)) for _ in range(nf)]
    c15 = r.integers(1, 1 << 15, nf)
    return v16, faces, c15


def _halves(h):
    h = [int(x) & 0xFFFF for x in h] + [0]
    return [h[i] | h[i + 1] << 16 for i in range(0, len(h) - 1, 2)]


def _frame(v16, faces, c15, cart, at=(0, 0, 5), angles=0, flags=0, seg=0, poke=None, cam=(0, 0, 0, 0)):
    d = [0] * spec.DMEM_WORDS
    for c, v in zip((spec.CAM_X, spec.CAM_Y, spec.CAM_Z), cam[:3]):
        d[c] = int(v * ONE) & 0xFFFFFFFF
    d[spec.CAM_YAW] = cam[3]
    cram = np.zeros(CART_AT + 4096, np.int64)
    if cart:
        streams = (_halves(v16.reshape(-1)), [a | b << 10 | c << 20 for a, b, c in faces], _halves(c15))
        offs, at_ = [], CART_AT
        for w in streams:
            cram[at_ + seg:at_ + seg + len(w)] = w
            offs.append(at_)
            at_ += len(w)
        d[DESC:DESC + 5] = [len(v16) | len(faces) << 16, offs[0], offs[1], offs[2], SHIFT]
        d[spec.SEG_BASE] = seg
        mesh = DESC
        flags |= spec.OBJ_CART
    else:
        rgb = [(int(c) >> 10 & 31) << 19 | (int(c) >> 5 & 31) << 11 | (int(c) & 31) << 3 for c in c15]
        w = Mesh([int(x) << SHIFT for x in v16.reshape(-1)], [(a, b, c, k) for (a, b, c), k in zip(faces, rgb)]).words()
        d[MESH_AT:MESH_AT + len(w)] = [x & 0xFFFFFFFF for x in w]
        mesh = MESH_AT
    d[spec.OL_BASE] = 1
    d[spec.OL_BASE + 1:spec.OL_BASE + 7] = [mesh] + [int(v * ONE) & 0xFFFFFFFF for v in at] + [angles, flags]
    if poke:
        poke(d)
    return gpu.render(d, cram)


@pytest.mark.parametrize("seed,at,angles,flags,cam", [
    (1, (0, 0, 5), 0, 0, (0, 0, 0, 0)),
    (2, (0.4, -0.2, 3), 100 | 60 << 10 | 900 << 20, spec.OBJ_CULL, (0, 0, 0, 0)),
    (3, (0, 0, 0.9), 300, 0, (0, 0.2, 0, 0)),              # through the near plane: the clipper
    (4, (2, 0, 4), 700 | 40 << 10, spec.OBJ_EDGE | spec.OBJ_CULL, (1, 0.5, -1, 60)),
    (5, (-1, 0.3, 6), 5, spec.OBJ_OTINT | 20 << 27 | 9 << 22 | 31 << 17, (0, 0, 0, 1000)),
])
def test_a_mesh_from_the_cart_is_the_same_picture(seed, at, angles, flags, cam):
    body = _body(seed)
    a = _frame(*body, cart=False, at=at, angles=angles, flags=flags, cam=cam)
    b = _frame(*body, cart=True, at=at, angles=angles, flags=flags, cam=cam)
    empty = _frame(*body, cart=False, at=(0, 0, -50), cam=cam)
    assert (a != empty).any(), "the test drew nothing"
    assert np.array_equal(a, b), f"{int((a != b).any(2).sum())} pixels differ"


def test_the_streams_are_read_through_the_segment_window():
    body = _body(7)
    assert np.array_equal(_frame(*body, cart=True), _frame(*body, cart=True, seg=1000))


def test_a_pose_is_two_offsets_and_nothing_moved():
    """two poses of one body in the cart, one face stream between them:
    the descriptor's VSRC and CSRC choose, and each is that pose in DMEM"""
    v_a, faces, c_a = _body(11)
    v_b, _, c_b = _body(12)
    cram = np.zeros(CART_AT + 4096, np.int64)
    at_, off = CART_AT, {}
    for name, w in (("f", [a | b << 10 | c << 20 for a, b, c in faces]), ("va", _halves(v_a.reshape(-1))),
                    ("ca", _halves(c_a)), ("vb", _halves(v_b.reshape(-1))), ("cb", _halves(c_b))):
        cram[at_:at_ + len(w)] = w
        off[name] = at_
        at_ += len(w)
    for v16, c15, vk, ck in ((v_a, c_a, "va", "ca"), (v_b, c_b, "vb", "cb")):
        d = [0] * spec.DMEM_WORDS
        d[DESC:DESC + 5] = [len(v16) | len(faces) << 16, off[vk], off["f"], off[ck], SHIFT]
        d[spec.OL_BASE] = 1
        d[spec.OL_BASE + 1:spec.OL_BASE + 7] = [DESC, 0, 0, 5 * ONE, 0, spec.OBJ_CART]
        assert np.array_equal(gpu.render(d, cram), _frame(v16, faces, c15, cart=False))


@pytest.mark.parametrize("poke", [
    lambda d: d.__setitem__(DESC + 1, spec.CRAM_WORDS),           # the vertices past the cart
    lambda d: d.__setitem__(DESC + 2, -5),                        # the faces before it
    lambda d: d.__setitem__(DESC, (spec.MESH_NV_MAX + 1) | 4 << 16),   # too many vertices
    lambda d: d.__setitem__(DESC + 4, 16),                        # no such shift
    lambda d: d.__setitem__(spec.OL_BASE + 1, spec.DMEM_WORDS - 3),    # the descriptor off the end
])
def test_a_cart_mesh_outside_its_memory_draws_nothing(poke):
    body = _body(9)
    empty = _frame(*body, cart=False, at=(0, 0, -50))
    assert np.array_equal(_frame(*body, cart=True, poke=poke), empty)


def test_the_store_admits_in_list_order_and_a_mesh_that_will_not_fit_draws_nothing():
    """spec.CM_VMAX / CM_FMAX: seven lumps of 250 vertices are 1,750 -- the
    seventh does not fit the store's 1,536 and is not drawn; a small one
    AFTER it still is (the one refused took no room)."""
    big = _body(21, nv=250, nf=120)
    small = _body(22, nv=20, nf=30)
    cram = np.zeros(CART_AT + 8192, np.int64)
    at_, descs = CART_AT, []
    for v16, faces, c15 in (big, small):
        offs = []
        for w in (_halves(v16.reshape(-1)), [a | b << 10 | c << 20 for a, b, c in faces], _halves(c15)):
            cram[at_:at_ + len(w)] = w
            offs.append(at_)
            at_ += len(w)
        descs.append([len(v16) | len(faces) << 16, offs[0], offs[1], offs[2], SHIFT])

    def frame(which):
        d = [0] * spec.DMEM_WORDS
        d[DESC:DESC + 5], d[DESC + 5:DESC + 10] = descs
        d[spec.OL_BASE] = len(which)
        for k, (desc, x) in enumerate(which):
            b = spec.OL_BASE + 1 + k * spec.OL_STRIDE
            d[b:b + 6] = [desc, int(x * ONE) & 0xFFFFFFFF, 0, 6 * ONE, 0, spec.OBJ_CART]
        return gpu.render(d, cram)
    six = [(DESC, -2.5 + k) for k in range(6)]
    assert spec.CM_VMAX // 250 == 6
    with_seventh = frame(six + [(DESC, 3.5)])
    assert np.array_equal(with_seventh, frame(six)), "the mesh past the store was drawn"
    and_small = frame(six + [(DESC, 3.5), (DESC + 5, 3.5)])
    assert np.array_equal(and_small, frame(six + [(DESC + 5, 3.5)])) and (and_small != with_seventh).any()


def test_a_stream_the_cart_never_carried_reads_as_zeros():
    v16, faces, c15 = _body(31)
    short = _frame(v16, faces, c15, cart=True, poke=lambda d: d.__setitem__(DESC + 3, CART_AT + 5000))
    black = _frame(v16, faces, np.zeros_like(c15), cart=True)
    assert np.array_equal(short, black)
