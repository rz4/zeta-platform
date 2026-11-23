"""TND's LAYER 5 (docs/TND-PORT.md P38; docs/TND-WORLD.md step 2): the world.

The generator's world (games/tnd/world.py) in the street: a key a gate, lying
at a dead end and taken with the jab -- several in hand at once, a pip each;
a gate that eats its own key and opens from either side; back doors bolted on
their deep side; hard ways, open streets the tree never had; bunkers, the
first under his feet at the start; an arrow that leads to the waymark by the
town's own tree; and the six enemies as the pack that holds the first hard
way, asleep until he comes.
A local build (TND_LAYER=5 -> build/layer5/tnd.zol); it needs the cart-mesh
core (frontier 20) on the machine.
"""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from zeta import cabinet, gpu, spec

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "games" / "tnd" / "gen_tnd.py"
CART = ROOT / "build" / "layer5" / "tnd.zol"
pytestmark = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "clips_190.npz").is_file(),
                                reason="the layer builds from the local tier files (build/tiers)")
sys.path.insert(0, str(ROOT / "games" / "tnd"))
import city  # noqa: E402
import world  # noqa: E402

U, X = spec.PAD_UP, spec.PAD_X
TILE = 16.0
C = city.generate(16, 666142)
W = world.generate(C)
PARENT = city._bfs(C.adj, C.start)[1]                # the arrow's tree: the town as generated
_px0, _py0 = C.plazas[0]
OXA, OYA = _px0 * TILE + 8, _py0 * TILE + 8
GATE = {}
for (_u, _v), _g in C.gates.items():
    if _g:
        GATE[_g] = (_u, _v) if C.district[_u] < C.district[_v] else (_v, _u)     # (near side, far side)
NG = len(GATE)
YAW_TO = {16: 256, 1: 0, -16: 768, -1: 512}          # the heading from a node to its neighbour


def xz(n):
    i, j = C.xy(n)
    return -(j * TILE - OYA), i * TILE - OXA


def node_at(x, z):
    return int((z + OXA + 8) // TILE) + 16 * int((OYA + 8 - x) // TILE)


@pytest.fixture(scope="module")
def text():
    if not CART.is_file() or CART.stat().st_mtime < max(GEN.stat().st_mtime, GEN.with_name("world.py").stat().st_mtime):
        env = dict(os.environ, TND_LAYER="5")
        for k in ("TND_SONG", "TND_OUT", "TND_CROWD", "TND_CARTMESH", "TND_AT"):
            env.pop(k, None)
        subprocess.run([sys.executable, str(GEN)], check=True, env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    return CART.read_text().splitlines()


@pytest.fixture(autouse=True)
def no_paint(monkeypatch):
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    monkeypatch.setattr(gpu, "render", lambda *a, **k: blank)


def _s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


class Game:
    def __init__(self, text):
        self.text = text
        self.m = cabinet.VirtualMachine(cabinet.load_cart(CART))
        self.m.frame(spec.PAD_START)
        self.d = self.m.vm.dmem
        self.run(0, 30)

    def sym(self, n):
        return next(int(l.rsplit(" at ", 1)[1]) for l in self.text if l.startswith(f"; {n}: "))

    def cell(self, n, k=0):
        return _s32(self.d[self.sym(n) + k])

    def poke(self, n, v, k=0):
        self.d[self.sym(n) + k] = int(v) & 0xFFFFFFFF

    def run(self, pad, n):
        for _ in range(n):
            self.m.frame(pad)

    def pos(self):
        return self.cell("px") / 65536, self.cell("pz") / 65536

    def node(self):
        return node_at(*self.pos())

    def put(self, x, z, yaw):
        self.poke("px", round(x * 65536))
        self.poke("pz", round(z * 65536))
        for c in ("yaw", "head", "cam_yaw"):
            self.poke(c, yaw)
        self.run(0, 3)

    def at_node(self, n, toward=None):
        self.put(*xz(n), YAW_TO[toward - n] if toward is not None else 0)

    def jab(self):
        self.run(X, 3)
        self.run(0, 30)

    def walk(self, frames):
        self.run(U, frames)
        self.run(0, 12)

    def tris(self):
        return self.d[spec.DL_BASE]


def test_he_starts_in_a_bunker_and_the_arrow_leads_to_the_first_key(text):
    g = Game(text)
    assert W.bunkers[0] == C.start and g.node() == C.start
    assert g.cell("w_lastb") == 0 and g.cell("w_bestb") == 0, "he does not stand on the first bunker's hatch"
    assert (g.cell("w_keys"), g.cell("w_taken"), g.cell("w_opened")) == (0, 0, 0)
    assert g.cell("w_wayn") == W.keys[1], "the waymark is not the first gate's key"
    assert g.cell("w_item") == 1


def test_a_key_is_taken_with_the_jab_and_several_are_carried(text):
    g = Game(text)
    n0 = g.tris()
    for k, gate in enumerate((1, 3)):
        kx, kz = xz(W.keys[gate])
        g.put(kx, kz - 1.0, 0)
        assert g.cell("ctx_near") == 1 and g.cell("w_k5") == gate - 1 and g.cell("key_held") == 0
        g.jab()
        assert g.cell("w_keys") >> (gate - 1) & 1 and g.cell("w_taken") >> (gate - 1) & 1
        assert g.tris() == n0 + k + 1, "a key in hand is not a pip on the glass"
        assert g.cell("w_k5") != gate - 1, "a key taken is still lying there"
    assert g.cell("w_keys") == 0b101
    g.run(0, 60)
    assert g.tris() == n0 + 2, "the pips pile up from frame to frame"


def test_a_gate_wants_its_own_key_and_eats_it(text):
    g = Game(text)
    a, b = GATE[1]
    g.poke("w_keys", 0b10)                                   # the second gate's key only
    g.at_node(a, toward=b)
    g.walk(60)
    assert g.cell("w_d5") == 0 and g.cell("key_held") == 1 and g.cell("ctx_near") == 0, "a gate offered itself to the wrong key"
    g.jab()
    g.walk(200)
    assert g.cell("w_opened") == 0 and g.node() == a, "the gate opened without its key"
    g.poke("w_keys", 0b11)
    g.at_node(a, toward=b)
    g.walk(60)
    assert g.cell("ctx_near") == 2 and g.cell("w_wayn") == a, "the key in hand, the waymark is not the gate"
    g.jab()
    assert g.cell("w_opened") == 1 and g.cell("w_keys") == 0b10, "the gate did not take its key (and only its own)"
    g.walk(260)
    assert g.node() == b, "the gate is open and he cannot walk through"
    assert g.cell("w_wayn") in (W.keys[2], GATE[2][0])


def test_a_jab_in_the_middle_of_a_string_still_opens_the_gate(text):
    """(his first tape: fourteen jabs in ten seconds at gate 5, its key in
    hand, and it opened only when he stopped punching)"""
    g = Game(text)
    a, b = GATE[1]
    g.poke("w_keys", 0b1)
    g.at_node(a, toward=b)
    for _ in range(12):                                      # mashing, on the way to it
        g.run(U | X, 3)
        g.run(U, 6)
    assert g.cell("w_opened") == 1, "a jab thrown mid-string did not open the gate it reached"


def test_a_gate_opens_from_its_far_side_too(text):
    """(a hard way can bring him round behind one)"""
    g = Game(text)
    a, b = GATE[2]
    g.poke("w_keys", 0b10)
    g.at_node(b, toward=a)
    g.walk(60)
    assert g.cell("w_d5") == 1 and g.cell("ctx_near") == 2
    g.jab()
    assert g.cell("w_opened") == 0b10
    g.walk(260)
    assert g.node() == a


def test_a_back_door_opens_only_from_its_bolts_side_and_stays_open(text):
    g = Game(text)
    deep, near = W.back[0]
    d = NG                                                   # (the doors: the gates, then the bolts)
    g.at_node(near, toward=deep)
    g.walk(60)
    assert g.cell("w_d5") == d and g.cell("w_dcan") == 0 and g.cell("ctx_near") == 0
    g.jab()
    g.walk(200)
    assert g.cell("w_opened") == 0 and g.node() == near, "a bolt was drawn from the wrong side"
    g.at_node(deep, toward=near)
    g.walk(60)
    assert g.cell("ctx_near") == 2
    g.jab()
    assert g.cell("w_opened") == 1 << d and g.cell("w_keys") == 0
    g.walk(260)
    assert g.node() == near
    g.at_node(near, toward=deep)                             # ...and back the other way, for good
    g.walk(320)
    assert g.node() == deep


def test_a_hard_way_is_an_open_street_past_a_gate(text):
    g = Game(text)
    for frm, to in W.hard:
        assert to not in PARENT[frm:frm + 1] and frm != PARENT[to], "the hard way was the tree's own street"
        g.at_node(frm, toward=to)
        g.walk(330)
        assert g.node() == to, f"the hard way {frm} -> {to} is not open"
        assert g.cell("w_opened") == 0


def _hop(n, t):
    """the tree's next node from n toward t"""
    up, v = [], t
    while v >= 0:
        up.append(v)
        v = PARENT[v]
    if n in up:
        return up[up.index(n) - 1]
    return PARENT[n]


def test_the_arrow_goes_by_the_tree_to_the_waymark(text):
    g = Game(text)
    rng = np.random.default_rng(5)
    for n in [int(v) for v in rng.choice(256, 24, replace=False)]:
        if C.plaza[n] >= 0:
            continue
        g.at_node(n)
        t = g.cell("w_wayn")
        sector = C.district[n]
        want = next((W.keys[k] for k in sorted(GATE) if k - 1 >= sector), C.core)
        assert t == want, f"at node {n} (sector {sector}) the waymark is {t}, not the next gate's key {want}"
        if n == t:
            assert g.cell("ct_k") == 8, "at the waymark the arrow still points"
            continue
        side = g.cell("ct_c")
        assert n + (16, 1, -16, -1)[side] == _hop(n, t), f"at node {n} the arrow leaves by side {side}, not toward {_hop(n, t)}"
        assert g.cell("ct_k") < 8


def test_every_gate_open_the_arrow_leads_to_the_core(text):
    g = Game(text)
    g.poke("w_opened", (1 << NG) - 1)
    g.at_node(C.start)
    assert g.cell("w_wayn") == C.core


def test_the_pack_holds_the_hard_way_asleep_until_he_comes(text):
    g = Game(text)
    hx, hz = xz(W.hard[0][0])
    assert g.cell("w_pack") == 0
    home = [(g.cell(f"e{k}_pos") / 65536, g.cell(f"e{k}_pos", 1) / 65536) for k in range(6)]
    assert all(abs(x - hx) < 3 and abs(z - hz) < 3 for x, z in home), "the pack does not begin at its hard way"
    g.run(0, 200)
    assert home == [(g.cell(f"e{k}_pos") / 65536, g.cell(f"e{k}_pos", 1) / 65536) for k in range(6)], "asleep, it wandered"
    g.put(hx, hz - 7, 0)
    g.run(0, 300)
    assert g.cell("w_pack") == 1
    px, pz = g.pos()
    near = [np.hypot(g.cell(f"e{k}_pos") / 65536 - px, g.cell(f"e{k}_pos", 1) / 65536 - pz) for k in range(6)]
    assert max(near) < 3.2, f"awake, the pack did not come to him: {near}"
    g.put(hx, hz - 40, 0)                                    # (two blocks gone: it goes home)
    g.run(0, 5)
    assert g.cell("w_pack") == 0


def test_every_world_drawn_can_be_finished():
    for seed in range(1, 13):
        w = world.generate(city.generate(16, seed))
        gates = sum(1 for v in w.city.gates.values() if v)
        assert len(w.keys) == gates and w.par_safe > 0 and 0 < w.par_hard <= w.par_safe, seed
