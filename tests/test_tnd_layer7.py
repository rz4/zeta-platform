"""TND's LAYER 7 (docs/TND-PORT.md P40): the bunker is a door and rooms.

The player, of layer 6's hatch in the road: "the bunkers were more of doors
against a building, and an actual room you enter, in there we can have
training rooms with the items as objects you can practice melee and gunplay
... the hub room hold a desk with the map and inventory management. the prep
table". He begins inside: the HUB (the prep table, the way out), the RING
north of it (the six bodies, to fight), the RANGE east of it (items to shoot
and strike). They are nodes of the map past the town's north edge, so the
street's walk, walls, shots and lens are theirs. The jab at a bunker's door
is the way through it; out is back to the door he came in by.
A local build (TND_LAYER=7 -> build/layer7/tnd.zol); it needs the cart-mesh
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
CART = ROOT / "build" / "layer7" / "tnd.zol"
pytestmark = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "clips_190.npz").is_file(),
                                reason="the layer builds from the local tier files (build/tiers)")
sys.path.insert(0, str(ROOT / "games" / "tnd"))
import city  # noqa: E402
import world  # noqa: E402

U, D, LF, RT, A, B, X, Y, R, SEL = (spec.PAD_UP, spec.PAD_DOWN, spec.PAD_LEFT, spec.PAD_RIGHT, spec.PAD_A, spec.PAD_B,
                                    spec.PAD_X, spec.PAD_Y, spec.PAD_R, spec.PAD_SELECT)
TILE, FAC, HT = 16.0, 4.7, 8.0
C = city.generate(16, 666142)
W = world.generate(C)
_px0, _py0 = C.plazas[0]
OXA, OYA = _px0 * TILE + 8, _py0 * TILE + 8
HUB, RING, RANGE = 7 + 17 * 16, 7 + 18 * 16, 8 + 17 * 16
NORTH, EAST, SOUTH, WEST = 256, 0, 768, 512
NG = sum(1 for v in C.gates.values() if v)


def centre(n):
    return -((n // 16) * TILE - OYA), (n % 16) * TILE - OXA


def node_at(x, z):
    return int((z + OXA + 8) // TILE) + 16 * int((OYA + 8 - x) // TILE)


def local(n, x, z):
    """(east, north) of a zeta point from node n's centre"""
    cx, cz = centre(n)
    return z - cz, cx - x


@pytest.fixture(scope="module")
def text():
    if not CART.is_file() or CART.stat().st_mtime < max(GEN.stat().st_mtime, GEN.with_name("world.py").stat().st_mtime):
        env = dict(os.environ, TND_LAYER="7")
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

    def stand(self, n, east=0.0, north=0.0, yaw=NORTH):
        cx, cz = centre(n)
        self.put(cx - north, cz + east, yaw)

    def where(self, n):
        return local(n, *self.pos())

    def walk(self, frames):
        self.run(U, frames)
        self.run(0, 12)

    def jab(self):
        self.run(X, 3)
        self.run(0, 30)

    def enemy(self, k):
        return self.cell(f"e{k}_pos") / 65536, self.cell(f"e{k}_pos", 1) / 65536


def test_he_begins_inside_the_first_bunker_the_six_in_the_ring(text):
    g = Game(text)
    assert g.cell("b_in") == 1 and g.node() == HUB and g.cell("w_lastb") == 0
    assert g.cell("yaw") & 1023 == NORTH, "he does not face the room"
    assert g.cell("m_known") == 0b11, "the first bunker's survey is not his"
    for k in range(6):
        e, n = local(RING, *g.enemy(k))
        assert abs(e) < 3 and abs(n) < 3, f"enemy {k} is not in the ring: {e:.1f}, {n:.1f}"
    g.run(0, 300)
    assert g.cell("w_pack") == 0
    assert all(node_at(*g.enemy(k)) == RING for k in range(6)), "the six left the ring"


@pytest.mark.parametrize("room,east,north,yaw,axis,limit", [
    (HUB, 0, 0, WEST, 0, -(FAC - 0.6)),            # the hub's west wall, the prep table's
    (HUB, 0, 0, SOUTH, 1, -(FAC - 0.6)),           # its south, where the way out is
    (RING, 0, 0, NORTH, 1, HT - 0.6),              # the ring: a whole tile, to 0.6 from its walls
    (RING, 0, 0, WEST, 0, -(HT - 0.6)),
    (RING, 0, 0, EAST, 0, HT - 0.6),
    (RING, 6, 0, SOUTH, 1, -(HT - 0.6)),           # ...its south wall beside the doorway
    (RANGE, 0, 0, EAST, 0, HT - 0.6),
    (RANGE, 0, 5, WEST, 0, -(HT - 0.6)),           # the range's west wall beside its doorway
    (RANGE, 0, 0, NORTH, 1, HT - 0.6),
])
def test_a_room_has_walls(text, room, east, north, yaw, axis, limit):
    g = Game(text)
    g.stand(room, east, north, yaw)
    g.walk(260)
    assert g.node() == room, "he walked out of the room through a wall"
    got = g.where(room)[axis]
    assert abs(got - limit) < 0.2, f"he stopped at {got:.2f}, not at the wall's {limit:.2f}"


def test_the_hub_opens_north_to_the_ring_and_east_to_the_range(text):
    g = Game(text)
    g.stand(HUB, 0, 0, NORTH)
    g.walk(200)
    assert g.node() == RING
    g.stand(HUB, 0, 0, EAST)
    g.walk(200)
    assert g.node() == RANGE
    g.stand(RING, 3.0, 0, SOUTH)                             # back through the doorway, off its middle
    g.walk(200)
    assert g.node() == HUB


def test_the_jab_at_the_door_is_the_way_out_and_back_in(text):
    g = Game(text)
    g.stand(HUB, 0, -2.0, SOUTH)
    g.run(0, 5)
    assert g.cell("ctx_near") == 2 and g.cell("b_itk") == 2
    g.jab()
    b0 = W.bunkers[0]
    assert g.cell("b_in") == 0 and g.node() == b0, "the way out did not lead to the bunker he was in"
    hx, hz = (-((W.hard[0][0] // 16) * TILE - OYA), (W.hard[0][0] % 16) * TILE - OXA)
    assert all(abs(g.enemy(k)[0] - hx) < 3 and abs(g.enemy(k)[1] - hz) < 3 for k in range(6)), "the six are not back at their hard way"
    out = g.pos()
    g.walk(120)                                              # (he faces the street: he can walk off)
    assert np.hypot(*np.subtract(g.pos(), out)) > 3, "out of the door, he faces a wall"
    g.put(*out, (g.cell("yaw") + 512) & 1023)                # round, and to the door again
    g.run(0, 5)
    assert g.cell("ctx_near") == 2 and g.cell("b_itk") == 2 and g.cell("b_tdt") == 0
    g.jab()
    assert g.cell("b_in") == 1 and g.node() == HUB


def test_out_is_by_the_door_he_came_in(text):
    g = Game(text)
    g.poke("b_in", 0)
    b2 = W.bunkers[2]
    tree = city._bfs(C.adj, C.start)[1]
    street = next(m for m in C.adj[b2] if m == tree[b2] or tree[m] == b2)
    wall = b2 - (street - b2)                                # the wall facing its street
    cx, cz = centre(b2)
    step = {16: (-1, 0), -16: (1, 0), 1: (0, 1), -1: (0, -1)}[wall - b2]      # zeta (x, z) a unit toward the wall
    g.put(cx + step[0] * 2.5, cz + step[1] * 2.5, {16: NORTH, -16: SOUTH, 1: EAST, -1: WEST}[wall - b2])
    g.run(0, 5)
    assert g.cell("ctx_near") == 2 and g.cell("b_tdt") == 2, "the third bunker has no door on the wall facing its street"
    known = g.cell("m_known")
    g.jab()
    assert g.cell("b_in") == 1 and g.cell("w_lastb") == 2 and g.node() == HUB
    s = C.district[b2]
    assert g.cell("m_known") == known | 1 << s | 1 << min(s + 1, len(C.order) - 1), "its survey is not his"
    g.stand(HUB, 0, -2.0, SOUTH)
    g.run(0, 5)
    g.jab()
    assert g.cell("b_in") == 0 and g.node() == b2


def test_the_map_is_the_prep_tables(text):
    g = Game(text)
    g.run(SEL, 4)                                            # across the room from it: the knobs
    assert g.cell("m_on") == 0 and g.cell("knob_on") == 1
    g.run(0, 4)
    g.stand(HUB, -2.0, 0.0, WEST)
    g.run(0, 4)
    assert g.cell("b_desk") == 1
    signs = g.d[spec.DL_BASE]
    g.run(SEL, 2)
    g.run(0, 4)
    assert g.cell("m_on") == 1 and g.cell("m_cx") + 16 * g.cell("m_cy") == W.bunkers[0], "the cursor is not on his bunker"
    g.run(SEL, 2)
    g.run(0, 6)
    assert g.cell("m_on") == 0
    g.stand(HUB, 3.0, 0.0, WEST)
    g.run(0, 4)
    assert g.cell("b_desk") == 0 and g.d[spec.DL_BASE] == signs - 2, "the map's sign is not the table's alone"


def test_b_shuts_the_map_and_fires_nothing(text):
    """(his tape: B five times in the map, and nothing)"""
    g = Game(text)
    g.stand(HUB, -2.0, 0.0, WEST)
    g.run(SEL, 2)
    g.run(0, 4)
    assert g.cell("m_on") == 1
    shots = g.cell("gun_shots")
    g.run(B, 20)                                             # shut with B, the thumb still on it
    assert g.cell("m_on") == 0
    g.run(0, 30)
    assert g.cell("gun_shots") == shots and g.cell("bul_next") == 0, "the B that shut the map fired the gun"
    g.run(B, 3)                                              # ...and B is the gun again after
    g.run(0, 30)
    assert g.cell("gun_shots") != shots or g.cell("gun_reload") > 0 or g.cell("bul_next") != 0


def test_the_ranges_items_are_struck_not_taken(text):
    g = Game(text)
    cx, cz = centre(RANGE)
    g.put(cx - (-0.4), cz + 6.4 - 0.9, EAST)                 # the middle item, a step short of it
    g.run(0, 5)
    assert g.cell("w_k5") == NG + 1 and g.cell("key_held") == 0
    assert g.cell("ctx_near") == 0, "one of the range's items offered itself to be taken"
    g.run(X, 3)
    g.run(0, 14)
    assert g.cell("key_hit") > 0, "the jab did not ring it"
    g.run(0, 60)
    assert g.cell("w_keys") == 0 and g.cell("w_taken") == 0 and g.cell("w_k5") == NG + 1


def test_a_round_meets_a_rooms_wall_and_a_body_in_the_ring(text):
    g = Game(text)
    g.stand(RING, 0, -6.0, NORTH)
    g.run(R, 20)
    assert g.cell("t_ok") == 1 and 0 <= g.cell("t_sel") < 6, "the lock found no body in the ring"
    k = g.cell("t_sel")
    hp = g.cell(f"e{k}_hp")
    g.run(R | B, 4)
    g.run(R, 40)
    assert g.cell(f"e{k}_hp") < hp, "a locked round did not land on the ring's body"


def test_no_arrow_in_the_rooms_and_his_plan_waits_outside(text):
    g = Game(text)
    g.poke("m_wp", W.keys[1])
    g.poke("m_wn", 1)
    g.run(0, 5)
    assert g.cell("ct_k") == 8, "the arrow points inside the bunker"
    g.stand(HUB, 0, -2.0, SOUTH)
    g.run(0, 5)
    g.jab()
    g.run(0, 5)
    assert g.cell("b_in") == 0 and g.cell("ct_k") < 8 and g.cell("w_wayn") == W.keys[1]
