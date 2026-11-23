"""TND's LAYER 6 (docs/TND-PORT.md P39; docs/TND-WORLD.md step 3): the
bunker's map, and his waymarks.

On a bunker's hatch SELECT opens the map and the street stops: the town from
above, the sectors he knows (the one he stands in; from a hatch, the next
along), what lies in them, and a cursor. A puts a waymark under it or takes
one off, four at most, in order; Y clears the plan. In the street the arrow
leads to the first of them -- no plan, no arrow -- by the streets that are
open NOW, hard ways and drawn bolts among them; reaching it takes it off.
A local build (TND_LAYER=6 -> build/layer6/tnd.zol); it needs the cart-mesh
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
CART = ROOT / "build" / "layer6" / "tnd.zol"
pytestmark = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "clips_190.npz").is_file(),
                                reason="the layer builds from the local tier files (build/tiers)")
sys.path.insert(0, str(ROOT / "games" / "tnd"))
import city  # noqa: E402
import world  # noqa: E402

U, D, LF, RT, A, X, Y, SEL = (spec.PAD_UP, spec.PAD_DOWN, spec.PAD_LEFT, spec.PAD_RIGHT, spec.PAD_A, spec.PAD_X,
                              spec.PAD_Y, spec.PAD_SELECT)
TILE = 16.0
C = city.generate(16, 666142)
W = world.generate(C)
PARENT = city._bfs(C.adj, C.start)[1]
_px0, _py0 = C.plazas[0]
OXA, OYA = _px0 * TILE + 8, _py0 * TILE + 8
GATE = {}
for (_u, _v), _g in C.gates.items():
    if _g:
        GATE[_g] = (_u, _v) if C.district[_u] < C.district[_v] else (_v, _u)
NG = len(GATE)
STEP = (16, 1, -16, -1)                              # N E S W, in node numbers
YAW_TO = {16: 256, 1: 0, -16: 768, -1: 512}


def xz(n):
    i, j = C.xy(n)
    return -(j * TILE - OYA), i * TILE - OXA


def node_at(x, z):
    return int((z + OXA + 8) // TILE) + 16 * int((OYA + 8 - x) // TILE)


def open_streets(opened=0):
    """the town's streets as they stand: the tree's and the plazas', less the
    gates still shut; the hard ways; the back doors whose bolts are drawn"""
    adj = [set(a) for a in C.adj]
    for g, (a, b) in GATE.items():
        if not opened >> (g - 1) & 1:
            adj[a].discard(b)
            adj[b].discard(a)
    for a, b in W.hard:
        adj[a].add(b)
        adj[b].add(a)
    for i, (a, b) in enumerate(W.back):
        if opened >> (NG + i) & 1:
            adj[a].add(b)
            adj[b].add(a)
    return adj


def far_from(t, adj):
    dist, q = {t: 0}, [t]
    for v in q:
        for m in adj[v]:
            if m not in dist:
                dist[m] = dist[v] + 1
                q.append(m)
    return dist


@pytest.fixture(scope="module")
def text():
    if not CART.is_file() or CART.stat().st_mtime < max(GEN.stat().st_mtime, GEN.with_name("world.py").stat().st_mtime):
        env = dict(os.environ, TND_LAYER="6")
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

    def tap(self, pad):
        self.run(pad, 2)
        self.run(0, 3)

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

    def plan(self, *nodes):
        for k, n in enumerate(nodes):
            self.poke("m_wp", n, k)
        self.poke("m_wn", len(nodes))

    def waymarks(self):
        return [self.cell("m_wp", k) for k in range(self.cell("m_wn"))]

    def cursor(self):
        return self.cell("m_cx") + 16 * self.cell("m_cy")

    def cursor_to(self, n):
        for _ in range(40):
            cx, cy = self.cell("m_cx"), self.cell("m_cy")
            if (cx, cy) == C.xy(n):
                return
            self.tap(RT if cx < n % 16 else LF if cx > n % 16 else U if cy < n // 16 else D)
        raise AssertionError("the cursor never got there")


def test_no_plan_no_arrow_and_the_hatch_shows_the_maps_sign(text):
    g = Game(text)
    assert g.cell("m_wn") == 0 and g.cell("ct_k") == 8, "with no waymark of his the arrow still points"
    on = g.d[spec.DL_BASE]
    g.put(xz(C.start)[0], xz(C.start)[1] - 6, 512)            # off the hatch
    g.run(0, 3)
    assert g.d[spec.DL_BASE] == on - 2, "the map's sign is not the hatch's alone"


def test_select_on_a_hatch_opens_the_map_and_the_street_stops(text):
    g = Game(text)
    g.tap(SEL)
    assert g.cell("m_on") == 1 and g.cursor() == C.start
    assert g.cell("m_known") == 0b11, "from the first hatch he does not know his sector and the next"
    assert g.d[spec.DL_BASE] == 0 and g.d[spec.FOG_SHIFT] == 0
    at, frames = g.pos(), g.cell("anim")
    g.run(U, 40)                                             # (the pad is the cursor's: he does not walk)
    assert g.pos() == at and g.cell("m_cy") == 15
    g.run(SEL, 12)                                           # shut, and the thumb still on it
    assert g.cell("m_on") == 0 and g.cell("knob_on") == 0, "shutting the map opened the knobs"
    g.run(0, 3)
    assert g.d[spec.FOG_SHIFT] == 10 and g.d[spec.DL_BASE] >= 3, "the street did not come back as it was"
    g.run(U, 30)
    assert g.pos() != at


def test_off_a_hatch_select_is_still_the_knobs(text):
    g = Game(text)
    g.put(xz(C.start)[0], xz(C.start)[1] - 6, 512)
    g.run(SEL, 5)
    assert g.cell("m_on") == 0 and g.cell("knob_on") == 1


def test_the_cursor_steps_runs_when_held_and_stops_at_the_edge(text):
    g = Game(text)
    g.tap(SEL)
    cx, cy = C.xy(C.start)
    g.tap(D)
    assert (g.cell("m_cx"), g.cell("m_cy")) == (cx, cy - 1)
    g.tap(RT)
    assert (g.cell("m_cx"), g.cell("m_cy")) == (cx + 1, cy - 1)
    g.run(LF, 11)
    assert g.cell("m_cx") == cx, "held eleven frames, it ran already"
    g.run(LF, 60)
    assert g.cell("m_cx") == 0, "held, the cursor did not run to the edge and stop"
    g.run(U, 80)
    assert g.cell("m_cy") == 15


def test_a_waymark_goes_where_he_knows_the_town_four_at_most_in_order(text):
    g = Game(text)
    g.tap(SEL)
    known = [n for n in range(256) if C.district[n] <= 1]
    unknown = next(n for n in range(256) if C.district[n] == 3)
    g.cursor_to(unknown)
    g.tap(A)
    assert g.waymarks() == [], "a waymark was put where he does not know the town"
    plan = [W.keys[1], GATE[1][0], known[5], known[9]]
    for n in plan:
        g.cursor_to(n)
        g.tap(A)
    assert g.waymarks() == plan
    g.cursor_to(known[14])
    g.tap(A)
    assert g.waymarks() == plan, "a fifth waymark"
    g.cursor_to(plan[1])                                     # A on one of his takes it off; the rest move up
    g.tap(A)
    assert g.waymarks() == [plan[0], plan[2], plan[3]]
    g.tap(Y)
    assert g.waymarks() == []


def _check_route(g, t, opened, sample):
    adj = open_streets(opened)
    dist = far_from(t, adj)
    for n in sample:
        if C.plaza[n] >= 0 or n == t:
            continue
        g.plan(t)
        g.at_node(n)
        assert g.cell("w_wayn") == t and g.cell("ct_k") < 8, f"at {n}, no arrow for the waymark at {t}"
        m = n + STEP[g.cell("ct_c")]
        if n in dist:
            assert m in adj[n] and dist[m] == dist[n] - 1, \
                f"at node {n} the arrow leaves toward {m}: not a shortest open way to {t} ({dist[n]} streets)"
        else:                                                # (no open way: the tree's, to the gate in it)
            up, v = [], t
            while v >= 0:
                up.append(v)
                v = PARENT[v]
            assert m == (up[up.index(n) - 1] if n in up else PARENT[n])


def test_the_arrow_goes_by_the_streets_that_are_open(text):
    g = Game(text)
    rng = np.random.default_rng(11)
    sample = [int(v) for v in rng.choice(256, 14, replace=False)]
    _check_route(g, W.keys[1], 0, sample)
    frm, to = W.hard[0]                                      # a hard way IS a way: one street, not the tree's long one
    g.plan(to)
    g.at_node(frm)
    assert frm + STEP[g.cell("ct_c")] == to, "the arrow does not take the hard way to a waymark at its far end"
    _check_route(g, to, 0, sample)


def test_a_bolt_drawn_is_a_way_from_then_on(text):
    g = Game(text)
    deep, near = W.back[0]
    g.plan(deep)
    g.at_node(near)
    assert near + STEP[g.cell("ct_c")] != deep, "the arrow led through a bolted door"
    g.plan()
    g.at_node(deep, toward=near)
    g.run(U, 60)
    g.run(0, 12)
    g.run(X, 3)
    g.run(0, 30)
    assert g.cell("w_opened") == 1 << NG
    g.plan(deep)
    g.at_node(near)
    assert near + STEP[g.cell("ct_c")] == deep, "the bolt is drawn and the arrow still goes the long way"


def test_reaching_a_waymark_takes_it_off_and_the_next_is_first(text):
    g = Game(text)
    a, b = W.hard[1]
    g.plan(a, b, C.core)
    g.at_node(a)
    assert g.waymarks() == [b, C.core]
    assert a + STEP[g.cell("ct_c")] == b
    g.at_node(b)
    g.at_node(C.core)
    assert g.waymarks() == [] and g.cell("ct_k") == 8, "the plan done, the arrow still points"


def test_the_map_lists_the_sectors_he_knows_and_what_lies_in_them(text):
    g = Game(text)
    g.tap(SEL)
    two = g.d[spec.OL_BASE]
    g.poke("m_known", (1 << len(C.order)) - 1)
    g.run(0, 2)
    all_ = g.d[spec.OL_BASE]
    assert all_ > two + 12 and all_ <= spec.OL_MAX, f"{two} objects for two sectors, {all_} for the town"
    g.poke("w_taken", 0b111111)                              # every key taken: six markers fewer
    g.poke("w_opened", (1 << NG) - 1)                        # every gate open: six more
    g.run(0, 2)
    assert g.d[spec.OL_BASE] == all_ - 2 * NG
