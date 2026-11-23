"""The experiment record's machine half (zeta/experience.py; docs/EXPERIENCE-IMPRINTING.md).

A tape and its cart give a record anyone can reproduce: the same frames, the
same end state, the same history of the knobs -- and a tape of another cart is
refused. The knob registry (games/tnd/axes.json) is the lab's tuner, knob for
knob.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from zeta import cabinet, experience, spec
from zeta import tape as ztape

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "games" / "tnd" / "gen_tnd.py"
LAB = ROOT / "build" / "layer10" / "tnd.zol"
AXES = ROOT / "games" / "tnd" / "axes.json"
OBSERVER = ROOT / "games" / "tnd" / "observe.py"
WITNESS = ROOT / "carts" / "witness" / "litclip.zol"
lab = pytest.mark.skipif(not (ROOT / "build" / "tiers" / "clips_190.npz").is_file(),
                         reason="the lab builds from the local tier files (build/tiers)")
SEL, U, D, RT, X, Y, B = (spec.PAD_SELECT, spec.PAD_UP, spec.PAD_DOWN, spec.PAD_RIGHT, spec.PAD_X, spec.PAD_Y, spec.PAD_B)


def _tape(tmp_path, cart_path, pads, name="t.ztp"):
    cart = cabinet.load_cart(cart_path)
    p = tmp_path / name
    p.write_bytes(ztape.encode(pads, ztape.cart_sum(cart), spec.LOADER_BUILD))
    return p


@pytest.fixture(scope="module")
def lab_cart():
    if not LAB.is_file() or LAB.stat().st_mtime < GEN.stat().st_mtime:
        env = dict(os.environ, TND_LAYER="10")
        for k in ("TND_SONG", "TND_OUT", "TND_CROWD", "TND_CARTMESH", "TND_AT"):
            env.pop(k, None)
        subprocess.run([sys.executable, str(GEN)], check=True, env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    return LAB


def test_the_forges_comments_name_the_cells():
    sym = experience.symbols("; knobs: 15 words at 9351\n; px: 1 words at 8120\nload 1\n; knobs: 3 words at 1\n")
    assert sym == {"knobs": (9351, 15), "px": (8120, 1)}


def test_a_record_is_the_same_record_twice_and_names_its_tape_and_cart(tmp_path):
    pads = [0] * 30 + [spec.PAD_RIGHT] * 20 + [0] * 10
    t = _tape(tmp_path, WITNESS, pads)
    a = experience.ingest(t, WITNESS, WITNESS, built_at="abc1234", recipe="python3 carts/witness/gen_litclip.py")
    b = experience.ingest(t, WITNESS, WITNESS)
    assert a["schema"] == "zeta-xp-1" and a["evidence"]["frames"] == 60
    assert a["evidence"]["end_state_sha256"] == b["evidence"]["end_state_sha256"], "the same tape gave two end states"
    assert len(a["machine"]["tape"]["sha256"]) == 64 and a["machine"]["cart"]["built_at_commit"] == "abc1234"
    assert a["machine"]["tape"]["cart_sum"] == a["machine"]["cart"]["sum"]
    c = experience.ingest(_tape(tmp_path, WITNESS, pads[:-1] + [spec.PAD_LEFT], "u.ztp"), WITNESS, WITNESS)
    assert c["machine"]["tape"]["sha256"] != a["machine"]["tape"]["sha256"]


def test_a_tape_of_another_cart_is_refused(tmp_path):
    t = _tape(tmp_path, ROOT / "carts" / "witness" / "cartmesh.zol", [0] * 10)
    with pytest.raises(SystemExit):
        experience.ingest(t, WITNESS, WITNESS)


def test_the_peoples_half_survives_a_second_ingest(tmp_path):
    t = _tape(tmp_path, WITNESS, [0] * 12)
    out = tmp_path / "x.json"
    args = ["ingest", str(t), "--game", str(WITNESS), "--symbols", str(WITNESS), "--out", str(out)]
    assert experience.main(args) == 0
    rec = json.loads(out.read_text())
    rec["human"] = {"said": ["more of that"]}
    rec["result"] = {"verdict": "kept"}
    out.write_text(json.dumps(rec))
    assert experience.main(args) == 0
    again = json.loads(out.read_text())
    assert again["human"] == {"said": ["more of that"]} and again["result"] == {"verdict": "kept"}
    assert again["evidence"] == rec["evidence"]


@lab
def test_the_registry_is_the_labs_tuner_knob_for_knob(lab_cart):
    axes = json.loads(AXES.read_text())["axes"]
    sym = experience.symbols(lab_cart.read_text())
    assert sym["knobs"][1] == len(axes) == sym["knob_n"][1], "the registry and the cart's tuner are not the same length"
    assert len({a["id"] for a in axes}) == len(axes)
    t = experience.replay(cabinet.load_cart(lab_cart), [spec.PAD_START] + [0] * 40, sym, arrays=["knobs"])
    assert [int(v) for v in t.arr("knobs")[-1]] == [a["default"] for a in axes], "a registry default is not the cart's"
    for a in axes:
        assert a["min"] <= a["default"] <= a["max"] and a["step"] > 0 and a["what"] and a["positive_means"]


@lab
def test_a_turned_knob_is_on_the_tape_as_signed_notches(lab_cart, tmp_path):
    """SELECT held, Right to the weight knob, Down twice; then to the lift, Up
    three: the record says -2 and +3, where each began, and how long each stood"""
    tap = lambda b: [SEL | b] * 2 + [SEL] * 3
    pads = ([spec.PAD_START] + [0] * 40 + [SEL] * 3 + tap(RT) + tap(D) + tap(D) + tap(RT) + tap(RT) + tap(U) * 3 + [0] * 30
            + [X] * 3 + [0] * 12 + [Y] * 3 + [0] * 40)
    t = _tape(tmp_path, lab_cart, pads)
    rec = experience.ingest(t, lab_cart, lab_cart, AXES, OBSERVER)
    k = {x["knob"]: x for x in rec["knobs"]}
    assert (k["weight"]["signed_notches"], k["lift"]["signed_notches"]) == (-2, 3)
    assert k["weight"]["final"] == k["weight"]["default"] - 2 * k["weight"]["step"]
    assert k["lift"]["final"] == k["lift"]["default"] + 3 * k["lift"]["step"]
    assert k["knock"]["signed_notches"] == 0 and k["knock"]["changes_total"] == 0
    assert sum(k["weight"]["dwell_frames"].values()) == sum(k["lift"]["dwell_frames"].values())
    assert k["weight"]["axis"] == "tnd.lab.weight"
    o = rec["observed"]
    assert o["blows"]["thrown"] == 2 and o["blows"]["by_move"] == {"jab": 1, "lead_hook": 1}
    assert o["tuner_open_minutes"] > 0


@lab
def test_two_records_compare_number_for_number(lab_cart, tmp_path):
    jab = [X] * 3 + [0] * 12
    a = experience.ingest(_tape(tmp_path, lab_cart, [spec.PAD_START] + [0] * 40 + jab * 2 + [0] * 30, "a.ztp"), lab_cart, lab_cart,
                          AXES, OBSERVER)
    b = experience.ingest(_tape(tmp_path, lab_cart, [spec.PAD_START] + [0] * 40 + jab * 5 + [0] * 30, "b.ztp"), lab_cart, lab_cart,
                          AXES, OBSERVER)
    rows = {k: (x, y) for k, x, y in experience.compare(a, b)}
    assert rows["blows.thrown"] == (2, 5)
