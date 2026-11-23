"""experience.py -- a recorded session as an EXPERIMENT RECORD (docs/EXPERIENCE-IMPRINTING.md).

The loop this serves already ran by hand for a week of TEAR NOT DEMON:

    play on the Pocket -> the tape comes home on the card -> the law replays
    it and the game's own cells are read frame by frame -> a change is made
    and proved -> a new cart goes back on the card.

What it never had is a RECORD: which tape, of which cart, showed what, what
the player turned and said, what was changed for it, and what the next tape
showed. This module writes the part of that record a machine can vouch for:

    identity   the tape's own hash and header, the cart's sum, the commit and
               recipe the cart was built from, the replay format
    evidence   how many frames, and a hash of the law's whole data memory at
               the end of the replay -- so anyone with the tape and the cart
               can check they have reproduced THIS session
    knobs      every knob of the cart's tuner: where it began (its default),
               where it ended, the signed number of notches between, and how
               long the player left it at each value. The tuner is in the
               game, so a turn of a knob is on the tape like any other input:
               nothing extra is recorded and nothing can be misremembered.
    observed   what a game's own observer measures from the trace (TND's is
               games/tnd/observe.py): counts and frame ranges, no opinions.

The rest of a record -- what the player said, what the agent supposes, what
was changed, whether it was kept -- is written by people, beside these, in
the same file (experiments/README.md has the shape). This module does not
write it and does not guess it.

    python3 -m zeta.experience ingest TAPE --game G.zbin --symbols G.zol ...
    python3 -m zeta.experience compare A.json B.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

SCHEMA = "zeta-xp-1"
ROOT = Path(__file__).resolve().parents[1]


def symbols(zol_text: str) -> dict[str, tuple[int, int]]:
    """the forge's own comments: name -> (address, words)"""
    out = {}
    for line in zol_text.splitlines():
        if line.startswith("; ") and " words at " in line:
            name, rest = line[2:].split(": ", 1)
            n, at = rest.split(" words at ")
            if name not in out:                      # (the first of a name is the one the forge placed first)
                out[name] = (int(at), int(n))
    return out


class Trace:
    """one replay, frame by frame: the pad word, and the cells an observer asked for"""

    def __init__(self, pad, cols: dict, arrs: dict, meta: dict):
        self.pad, self._cols, self._arrs, self.meta = pad, cols, arrs, meta
        self.frames = len(pad)

    def col(self, name):
        return self._cols[name]

    def arr(self, name):
        return self._arrs[name]

    def has(self, name):
        return name in self._cols or name in self._arrs


def _s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


def replay(cart: dict, pads, sym: dict, cells=(), arrays=(), say=None) -> Trace:
    """the session again on the law, reading `cells` (one word each) and
    `arrays` (every word of each) after every frame. Nothing is painted."""
    from . import cabinet, gpu, spec
    missing = [n for n in list(cells) + list(arrays) if n not in sym]
    if missing:
        raise KeyError(f"the cart has no cell named {missing}")
    cols = {n: np.zeros(len(pads), np.int64) for n in cells}
    arrs = {n: np.zeros((len(pads), sym[n][1]), np.int64) for n in arrays}
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    keep, gpu.render = gpu.render, (lambda *a, **k: blank)
    t0 = time.time()
    try:
        m = cabinet.VirtualMachine(cart)
        for f, p in enumerate(pads):
            m.frame(p)
            d = m.vm.dmem
            for n in cells:
                cols[n][f] = _s32(d[sym[n][0]])
            for n in arrays:
                a, k = sym[n]
                arrs[n][f] = [_s32(v) for v in d[a:a + k]]
            if say and f % 20000 == 19999:
                say(f + 1, len(pads), time.time() - t0)
        end = hashlib.sha256(struct.pack(f"<{len(m.vm.dmem)}I", *[v & 0xFFFFFFFF for v in m.vm.dmem])).hexdigest()
    finally:
        gpu.render = keep
    return Trace(np.asarray(pads, np.int64), cols, arrs, {"end_state_sha256": end})


def knob_record(trace: Trace, axes: list[dict]) -> list[dict]:
    """each knob: its default, where the session left it, the signed notches
    between, and the frames it sat at each value"""
    vals, notch = trace.arr("knobs"), trace.arr("knob_n")
    boot = int(np.argmax((vals != 0).any(1)))        # the first frame the table is loaded
    out = []
    for i, ax in enumerate(axes):
        v = vals[boot:, i]
        dwell = {}
        for x, c in zip(*np.unique(v, return_counts=True)):
            dwell[str(int(x))] = int(c)
        changes = [(int(f) + boot, int(v[f])) for f in np.flatnonzero(np.diff(v)) + 1]
        out.append({"axis": ax["id"], "knob": ax["knob"], "index": i, "default": int(v[0]), "final": int(v[-1]),
                    "signed_notches": int(notch[-1, i] - notch[boot, i]), "step": ax["step"], "unit": ax["unit"],
                    "dwell_frames": dwell, "changes": changes[:200], "changes_total": len(changes)})
    return out


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def ingest(tape_path, game_path, symbols_path, axes_path=None, observer_path=None, card_path=None,
           built_at=None, recipe=None, xp_id=None, say=None) -> dict:
    from . import cabinet, deploy, spec
    from . import tape as ztape
    tape_path, game_path = Path(tape_path), Path(game_path)
    blob = tape_path.read_bytes()
    header, pads = ztape.decode(blob) if blob[:4] == struct.pack("<I", ztape.MAGIC) else ({}, ztape.read(tape_path))
    cart = deploy.read_zbin(game_path) if game_path.suffix == ".zbin" else cabinet.load_cart(game_path)
    if card_path:
        cart["sd"] = deploy.card_images(Path(card_path))
    why = ztape.check(header, cart) if header else None
    if why:
        raise SystemExit(f"this tape is not of this game: {why}")
    sym = symbols(Path(symbols_path).read_text())
    axes = json.loads(Path(axes_path).read_text())["axes"] if axes_path else []
    obs = None
    if observer_path:
        sp = importlib.util.spec_from_file_location("xp_observer", observer_path)
        obs = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(obs)
    cells = list(getattr(obs, "CELLS", ()))
    arrays = list(getattr(obs, "ARRAYS", ())) + (["knobs", "knob_n"] if axes else [])
    cells = [c for c in cells if c in sym]
    arrays = [a for a in dict.fromkeys(arrays) if a in sym]
    trace = replay(cart, pads, sym, cells, arrays, say)
    rec = {
        "schema": SCHEMA,
        "id": xp_id or tape_path.stem,
        "machine": {
            "tape": {"file": tape_path.name, "sha256": hashlib.sha256(blob).hexdigest(), "format": "ZTP0",
                     "loader_build": header.get("build"), "cart_sum": f"{header.get('cart_sum', 0):#010x}",
                     "runs": header.get("runs")},
            "cart": {"file": game_path.name, "sum": f"{ztape.cart_sum(cart):#010x}", "built_at_commit": built_at,
                     "recipe": recipe, "symbols_sha256": hashlib.sha256(Path(symbols_path).read_bytes()).hexdigest()},
            "card_at_start": Path(card_path).name if card_path else None,
            "backend": "law (zeta.cabinet.VirtualMachine)", "spec_loader_build": spec.LOADER_BUILD,
            "ingested_at_commit": _git("rev-parse", "--short", "HEAD"),
        },
        "evidence": {"frames": int(trace.frames), "seconds": round(trace.frames / 60, 1),
                     "end_state_sha256": trace.meta["end_state_sha256"],
                     "reproduce": f"python3 -m zeta.experience ingest {tape_path.name} --game {game_path.name} --symbols ..."},
        "knobs": knob_record(trace, axes) if axes and trace.has("knobs") else [],
        "observed": obs.observe(trace) if obs else {},
    }
    return rec


def _flat(d, pre=""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from _flat(v, f"{pre}{k}.")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            yield pre + k, v


def compare(a: dict, b: dict) -> list[tuple[str, float, float]]:
    """every number both records' observers measured, side by side: (name,
    in a, in b). Rates are comparable; counts are per session, so read them
    against each session's length."""
    fa, fb = dict(_flat(a.get("observed", {}))), dict(_flat(b.get("observed", {})))
    return [(k, fa[k], fb[k]) for k in fa if k in fb]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="zeta.experience", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest", help="a tape and its cart -> the machine's half of an experiment record")
    p.add_argument("tape")
    p.add_argument("--game", required=True, help="the cart the session was played on (.zbin from the card, or .zol)")
    p.add_argument("--symbols", required=True, help="the same build's .zol: its comments name the cells")
    p.add_argument("--axes", help="the game's knob registry (games/tnd/axes.json)")
    p.add_argument("--observer", help="the game's observer (games/tnd/observe.py)")
    p.add_argument("--card", help="the save the session began with")
    p.add_argument("--built-at", help="the commit the cart was built from")
    p.add_argument("--recipe", help="how it was built (its environment and command)")
    p.add_argument("--id")
    p.add_argument("--out", required=True)
    p = sub.add_parser("compare", help="two records' measured numbers, side by side")
    p.add_argument("a")
    p.add_argument("b")
    args = ap.parse_args(argv)
    if args.cmd == "ingest":
        rec = ingest(args.tape, args.game, args.symbols, args.axes, args.observer, args.card, args.built_at, args.recipe,
                     args.id, say=lambda f, n, s: print(f"  frame {f:,} of {n:,} ({s:.0f} s)", flush=True))
        out = Path(args.out)
        if out.exists():                              # the people's half is kept: only the machine's is rewritten
            old = json.loads(out.read_text())
            rec = {**{k: v for k, v in old.items() if k not in rec}, **rec}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rec, indent=1) + "\n")
        print(f"{out}: {rec['evidence']['frames']:,} frames, end state {rec['evidence']['end_state_sha256'][:16]}..., "
              f"{sum(1 for k in rec['knobs'] if k['changes_total'])} knob(s) turned")
        return 0
    a, b = (json.loads(Path(x).read_text()) for x in (args.a, args.b))
    print(f"{a['id']} ({a['evidence']['seconds']} s)   vs   {b['id']} ({b['evidence']['seconds']} s)")
    for k, x, y in compare(a, b):
        print(f"  {k:48s} {x:>12.3f} {y:>12.3f}   {y - x:+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
