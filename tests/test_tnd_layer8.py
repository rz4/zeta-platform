"""TND's LAYER 8 (docs/TND-PORT.md P41): the world persists.

The player, of the old memory fabric: "persistent worlds, having all the
enemies known over time, as part of the route optimizing". The town's enemies
are PACKS: where one is, is a function of the street's clock (a walk of
sixteen steps along its sector's streets); who of it is left is six bits he
alone changes; and the six bodies are worn by the nearest pack with anyone
left. They strike, one at a time, on a wind-up; he has health, and going down
wakes him in the bunker he last took, the world as he left it. A rest gives
every pack one of its missing back. Medicine lies in the street; a gate's
sector is ranked by the blows he took in it; a pack seen is on the map with
its walk; and the core ends the run with its time and rank.
A local build (TND_LAYER=8 -> build/layer8/tnd.zol); it needs the cart-mesh
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
CART = ROOT / "build" / "layer8" / "tnd.zol"
pytestmark = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "clips_190.npz").is_file(),
                                reason="the layer builds from the local tier files (build/tiers)")
sys.path.insert(0, str(ROOT / "games" / "tnd"))
import city  # noqa: E402
import world  # noqa: E402

U, A, B, X, R, L, SEL = spec.PAD_UP, spec.PAD_A, spec.PAD_B, spec.PAD_X, spec.PAD_R, spec.PAD_L, spec.PAD_SELECT
TILE = 16.0
C = city.generate(16, 666142)
W = world.generate(C)
_px0, _py0 = C.plazas[0]
OXA, OYA = _px0 * TILE + 8, _py0 * TILE + 8
HUB = 7 + 17 * 16
NPACK = len(C.order) + 1
FULL = [0b001100, 0b011100, 0b001110, 0b011110, 0b001101, 0b001111, 0b111111][:len(C.order) - 1] + [0b111111, 0b111111]
STEP = 512                                           # frames a step of a patrol
GATE = {}
for (_u, _v), _g in C.gates.items():
    if _g:
        GATE[_g] = (_u, _v) if C.district[_u] < C.district[_v] else (_v, _u)
YAW_TO = {16: 256, 1: 0, -16: 768, -1: 512}


def centre(n):
    return -((n // 16) * TILE - OYA), (n % 16) * TILE - OXA


def node_at(x, z):
    return int((z + OXA + 8) // TILE) + 16 * int((OYA + 8 - x) // TILE)


@pytest.fixture(scope="module")
def text():
    if not CART.is_file() or CART.stat().st_mtime < max(GEN.stat().st_mtime, GEN.with_name("world.py").stat().st_mtime):
        env = dict(os.environ, TND_LAYER="8")
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
    def __init__(self, text, outside=True):
        self.text = text
        self.m = cabinet.VirtualMachine(cabinet.load_cart(CART))
        self.m.frame(spec.PAD_START)
        self.d = self.m.vm.dmem
        self.run(0, 30)
        if outside:
            self.leave()

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

    def put(self, x, z, yaw=0):
        self.poke("px", round(x * 65536))
        self.poke("pz", round(z * 65536))
        for c in ("yaw", "head", "cam_yaw"):
            self.poke(c, yaw)
        self.run(0, 3)

    def leave(self):
        cx, cz = centre(HUB)
        self.put(cx + 2.0, cz, 768)
        self.run(0, 4)
        self.run(X, 3)
        self.run(0, 30)
        assert self.cell("b_in") == 0
        self.door = (*self.pos(), (self.cell("yaw") + 512) & 1023)       # where the bunker's door is in reach, facing it

    def enter(self):
        self.put(*self.door)
        self.run(0, 4)
        self.run(X, 3)
        self.run(0, 30)
        assert self.cell("b_in") == 1, "he did not get into the bunker"

    def clock(self):
        return self.cell("p_clkm") * 3600 + self.cell("p_clks") * 60 + self.cell("p_clkf")

    def alive(self):
        return [self.cell("p_alive", k) for k in range(NPACK)]

    def bodies(self):
        return [self.cell(f"e{k}_st") for k in range(6)]

    def pack_xz(self):
        return self.cell("p_plx") / 65536, self.cell("p_plz") / 65536

    def to_live_pack(self, off=5.0):
        x, z = self.pack_xz()
        self.put(x, z - off, 0)
        self.run(0, 30)


def patrol_xz(text_game, p, step, tick):
    """the law of a pack's place: between two nodes of its walk"""
    row = [text_game.cell("patrols", p * 16 + i) for i in range(16)]
    a, b = row[(step + 5 * p) & 15], row[(step + 5 * p + 1) & 15]
    (ax, az), (bx, bz) = centre(a), centre(b)
    return ax + (bx - ax) * tick / STEP, az + (bz - az) * tick / STEP


def test_the_clock_runs_in_the_street_and_nowhere_else(text):
    g = Game(text, outside=False)
    g.run(0, 200)
    assert g.clock() == 0, "the clock ran in the bunker"
    g.leave()
    t0 = g.clock()
    g.run(0, 150)
    assert g.clock() == t0 + 150, "the street's clock is not a frame a frame"
    g.run(B, 100)                                            # (a button held: time slowed -- the clock is the glass's)
    assert g.clock() == t0 + 250


def test_a_patrol_walks_its_streets_and_is_the_same_walk_every_time(text):
    g = Game(text)
    for p in range(NPACK):
        row = [g.cell("patrols", p * 16 + i) for i in range(16)]
        for a, b in zip(row, row[1:] + row[:1]):
            assert a == b or b in C.adj[a], f"pack {p} steps from {a} to {b}, which is no street"
        assert all(C.district[n] == C.district[row[0]] for n in row) and not set(row) & set(W.bunkers)
    seen = []
    for frames in (60, 400, 700):
        g.run(0, frames)
        t = g.clock()
        live = g.cell("p_live")
        want = patrol_xz(g, live, t // STEP, t % STEP)
        got = g.pack_xz()
        assert abs(got[0] - want[0]) < 0.1 and abs(got[1] - want[1]) < 0.1, f"pack {live} is at {got}, the clock says {want}"
        seen.append(got)
    assert len({(round(x, 1), round(z, 1)) for x, z in seen}) > 1, "the patrol did not move"


def test_the_nearest_pack_with_anyone_left_wears_the_bodies(text):
    g = Game(text)
    live = g.cell("p_live")
    assert live == 0 and g.alive() == FULL, "outside the first bunker the first sector's pack is not the live one"
    assert g.bodies() == [FULL[0] >> k & 1 for k in range(6)], "the bodies are not who that pack is"
    g.poke("p_alive", 0, 0)                                  # nobody left of it: the next nearest takes them
    for k in range(6):
        g.poke(f"e{k}_st", 0)
    g.run(0, 3)
    nxt = g.cell("p_live")
    assert nxt != 0 and g.bodies() == [FULL[nxt] >> k & 1 for k in range(6)]


def test_a_body_down_stays_down_and_a_rest_gives_one_back(text):
    g = Game(text)
    g.to_live_pack()
    assert g.cell("w_pack") == 1 and g.cell("p_seen") & 1, "by the pack, it did not wake (or was not seen)"
    k = next(k for k in range(6) if g.bodies()[k] == 1)
    g.poke(f"e{k}_hp", 0)
    g.poke(f"e{k}_st", 2)
    g.run(0, 400)                                            # (layer 4's bodies were up again in 150)
    assert g.bodies()[k] == 2 and not g.alive()[0] >> k & 1, "a body down in the street got up, or was not written down"
    g.poke("p_alive", 0b100000, 7)                           # (and a pack far away, missing five)
    hp = 55
    g.poke("p_hp", hp)
    g.enter()
    assert g.cell("p_hp") == 140, "a rest did not make him whole"
    assert g.alive()[0] == FULL[0], "a rest did not give the pack its one back"
    assert bin(g.alive()[7]).count("1") == 2, "a rest gave a pack more than one back"


def test_they_strike_one_at_a_time_on_a_wind_up_and_distance_saves_him(text):
    g = Game(text)
    g.to_live_pack(off=4.0)
    hp, blows, blinked = g.cell("p_hp"), [], False
    for f in range(700):
        g.m.frame(0)
        t, atk = g.cell("p_atkt"), g.cell("p_atk")
        if 26 <= t < 70 and g.cell(f"e{atk}_fl") > 0:
            blinked = True
        if g.cell("p_hp") < hp:
            blows.append((f, hp - g.cell("p_hp"), atk))
            hp = g.cell("p_hp")
    assert len(blows) >= 4 and blinked, f"standing among them he was struck {len(blows)} times (a wind-up blinked: {blinked})"
    assert all(d == 12 for _, d, _ in blows), "a horde body's blow is not twelve"
    assert all(b[0] - a[0] > 60 for a, b in zip(blows, blows[1:])), "two blows landed together: they do not take turns"
    assert len({k for _, _, k in blows}) == 2, "only one of the two ever struck"
    # the same wind-up, and he steps out of reach before it lands
    g2 = Game(text)
    g2.to_live_pack(off=4.0)
    hp2 = g2.cell("p_hp")
    for f in range(400):
        g2.m.frame(0)
        if g2.cell("p_atkt") == 40:                          # mid wind-up: away
            x, z = g2.pos()
            g2.poke("px", round((x + 9.0) * 65536))
            break
    g2.run(0, 40)
    assert g2.cell("p_hp") == hp2, "a blow landed on a man who was not there"


def test_a_blow_of_his_takes_its_turn_away(text):
    g = Game(text)
    g.to_live_pack(off=4.0)
    for f in range(400):
        g.m.frame(0)
        if g.cell("p_atkt") == 40:
            break
    atk = g.cell("p_atk")
    g.poke(f"e{atk}_stun", 30)                               # (what a round or a fist does to it)
    hp = g.cell("p_hp")
    g.run(0, 6)
    assert g.cell("p_atk") != atk or g.cell("p_atkt") < 6, "held by a blow, it kept its wind-up"
    g.run(0, 20)
    assert g.cell("p_hp") == hp


def test_down_he_wakes_in_his_bunker_and_the_world_is_as_he_left_it(text):
    g = Game(text)
    g.poke("w_keys", 0b101)
    g.poke("w_taken", 0b101)
    g.poke("w_opened", 0b1)
    g.poke("m_wn", 1)
    g.to_live_pack(off=4.0)
    g.poke("p_hp", 5)
    for f in range(400):
        g.m.frame(0)
        if g.cell("f_dead"):
            break
    assert g.cell("f_dead"), "five health among them, and he never went down"
    t = g.clock()
    g.run(0, 70)
    assert g.clock() == t, "the clock ran while he lay there"
    g.run(A, 3)
    g.run(0, 20)
    assert g.cell("f_dead") == 0 and g.cell("b_in") == 1 and node_at(*g.pos()) == HUB, "he did not wake in the bunker"
    assert g.cell("p_hp") == 140
    assert (g.cell("w_keys"), g.cell("w_taken"), g.cell("w_opened"), g.cell("m_wn")) == (0b101, 0b101, 0b1, 1), \
        "going down cost him his keys, a door or his plan"


def test_medicine_is_found_carried_taken_and_stashed(text):
    g = Game(text)
    assert (g.cell("p_meds"), g.cell("p_stash")) == (0, 1)
    mx, mz = g.cell("meds", 0) / 65536, g.cell("meds", 1) / 65536
    g.put(mx, mz - 0.4, 0)
    g.run(0, 6)
    assert g.cell("p_meds") == 1 and g.cell("p_medtk") == 1, "walking onto the medicine did not take it"
    g.run(0, 30)
    assert g.cell("p_meds") == 1, "it was taken twice"
    signs = g.d[spec.DL_BASE]
    g.poke("p_hp", 40)
    g.run(SEL, 2)
    g.run(0, 6)
    assert g.cell("p_hp") == 110 and g.cell("p_meds") == 0 and g.cell("knob_on") == 0
    assert g.d[spec.DL_BASE] == signs - 1, "the medicine in hand is not a pip"
    g.run(SEL, 2)                                            # none left: nothing
    g.run(0, 6)
    assert g.cell("p_hp") == 110
    # the stash, at the prep table
    g2 = Game(text, outside=False)
    cx, cz = centre(HUB)
    g2.put(cx, cz - 2.0, 512)
    g2.run(0, 4)
    g2.run(SEL, 2)
    g2.run(0, 4)
    assert g2.cell("m_on") == 1
    g2.run(R, 2)
    g2.run(0, 4)
    assert (g2.cell("p_meds"), g2.cell("p_stash")) == (1, 0), "R at the table did not take the stash's medicine"
    g2.run(R, 2)
    g2.run(0, 4)
    assert (g2.cell("p_meds"), g2.cell("p_stash")) == (1, 0)
    g2.run(L, 2)
    g2.run(0, 4)
    assert (g2.cell("p_meds"), g2.cell("p_stash")) == (0, 1), "L did not put it back"
    assert g2.d[spec.DL_BASE] > 20, "the map shows no words (the clock, the medicine)"


@pytest.mark.parametrize("blows,rank", [(0, 0), (1, 1), (3, 2), (4, 3)])
def test_a_gate_opened_wears_its_sectors_rank(text, blows, rank):
    g = Game(text)
    a, b = GATE[2]
    g.poke("w_keys", 0b10)
    g.poke("p_sech", blows)
    g.put(*centre(a), YAW_TO[b - a])
    g.run(U, 60)
    g.run(0, 12)
    g.run(X, 3)
    g.run(0, 30)
    assert g.cell("w_opened") == 0b10
    assert g.cell("p_grank") == rank << 2 and g.cell("p_sech") == 0


def test_a_pack_seen_is_on_the_map_with_its_walk(text):
    g = Game(text, outside=False)
    cx, cz = centre(HUB)

    def map_objects():
        g.put(cx, cz - 2.0, 512)
        g.run(0, 4)
        g.run(SEL, 2)
        g.run(0, 4)
        ol, you = spec.OL_BASE + 1, g.sym("mk_you")          # (he blinks on the map: not counted)
        n = sum(1 for k in range(g.d[spec.OL_BASE]) if g.d[ol + k * spec.OL_STRIDE] != you)
        g.run(SEL, 2)
        g.run(0, 6)
        return n
    none = map_objects()
    g.poke("p_seen", 0b11)                                   # two packs seen: each its walk and its mark
    assert map_objects() == none + 4
    g.poke("p_alive", 0, 1)                                  # one of them with nobody left: its walk only
    assert map_objects() == none + 3


def test_the_core_ends_the_run_with_its_time_and_rank(text):
    g = Game(text)
    g.poke("p_clkm", 3)
    g.poke("p_clks", 7)
    g.put(*centre(C.core), 0)
    g.run(0, 6)
    assert g.cell("p_end") == 1 and g.d[spec.OL_BASE] == 0 and g.d[spec.DL_BASE] > 20
    clk = g.sym("str_clock")
    d0 = g.d[clk + 1] - 0                                    # the glyphs of 03 07
    assert [g.d[clk + i] - (g.d[clk + 1]) for i in (1, 2, 3, 4)] == [0, 3, 0, 7], "the end's clock does not read 03:07"
    t = g.clock()
    at = g.pos()
    g.run(U, 60)
    assert g.clock() == t and g.pos() == at, "the run is over and the clock or the street went on"
    assert g.d[g.sym("str_one") + 1] == 4, "three minutes seven is not an S against this world's par"
