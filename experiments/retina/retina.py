"""retina.py -- a mock of the retina (docs/ZETA-RECIPROCAL-DESIGN.md, 4.2).

NOT LAW. A first draft of one, run beside the law without touching it:
the law's own render is called unchanged and its identity plane is
borrowed on the way out.

Every percept here is a function of two finished things and nothing
else -- the identity plane and the painted frame -- taken in scan
order, a RUN at a time (a run is a maximal stretch of one row owned by
one object). That is the shape the silicon's flush already has, and the
question this file exists to answer is what that shape costs:

    how many runs are there, a row, a band and a frame?

because one run is one read-modify-write of one record.

    python3 experiments/retina/retina.py            # the table in README.md
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from zeta import cabinet, carts, gpu, spec  # noqa: E402

# ---- the draft law -------------------------------------------------------
FOV = (80, 72, 240, 216)        # x0, y0, x1, y1: the middle quarter of the glass
BAND_H = spec.TILE_H            # 32 rows


def lum5(fb):
    """A pixel's shown brightness, 0..31: (r + 2g + b) / 4 of the 5-bit
    channels. One add and a shift; 92,160 pixels of it are 22 bits."""
    c = fb.astype(np.int64) >> 3
    return (c[..., 0] + 2 * c[..., 1] + c[..., 2]) >> 2


def runs_of(own):
    """Every run of the plane in scan order: (y, x0, x1_exclusive, owner)."""
    out = []
    for y in range(own.shape[0]):
        row = own[y]
        cut = np.flatnonzero(row[1:] != row[:-1]) + 1
        xs = np.concatenate(([0], cut, [row.size]))
        for a, b in zip(xs[:-1], xs[1:]):
            out.append((y, int(a), int(b), int(row[a])))
    return out


def percepts(own, fb, n_obj=spec.OL_MAX):
    """The record of every object, built a run at a time.

    VIS  pixels shown                         (the law's count, again)
    BOX  min x, max x, min y, max y of them
    FOV  how many lie inside the FOV window
    LUM  the sum of their brightness
    NBR  the owner most often immediately LEFT of the object's runs, by
         the majority vote: one candidate and one counter. Owner 0 is
         the room (the clear, the plate, the display list).
    """
    L = lum5(fb)
    Lc = np.concatenate((np.zeros((L.shape[0], 1), np.int64),
                         np.cumsum(L, axis=1)), axis=1)
    rec = [dict(vis=0, box=None, fov=0, lum=0, nbr=None, nbr_n=0, runs=0,
                wide=0, wide_nbr=None)
           for _ in range(n_obj + 1)]
    fx0, fy0, fx1, fy1 = FOV
    left = {}                                   # exact tallies, to judge the vote
    rs = runs_of(own)
    for y, a, b, k in rs:
        if k == 0:
            continue
        r = rec[k]
        r["runs"] += 1
        r["vis"] += b - a
        bx = r["box"]
        r["box"] = (a, b - 1, y, y) if bx is None else \
            (min(bx[0], a), max(bx[1], b - 1), bx[2], y)
        if fy0 <= y < fy1:
            r["fov"] += max(0, min(b, fx1) - max(a, fx0))
        r["lum"] += int(Lc[y, b] - Lc[y, a])
        if a > 0:                               # nothing is left of x = 0
            nb = int(own[y, a - 1])
            left.setdefault(k, {}).setdefault(nb, 0)
            left[k][nb] += 1
            if b - a > r["wide"]:               # NBR, second draft: the owner
                r["wide"], r["wide_nbr"] = b - a, nb   # left of the WIDEST run
            if r["nbr_n"] == 0:
                r["nbr"], r["nbr_n"] = nb, 1
            elif r["nbr"] == nb:
                r["nbr_n"] += 1
            else:
                r["nbr_n"] -= 1
    return rec, rs, left


def backlog(rs, cost):
    """The deepest queue of pending record updates, if the flush scans a
    pixel a clock (the fastest it could) and one update takes `cost`
    clocks. A run's update is queued when the run ENDS."""
    deep = q = 0
    t_free = 0
    pend = []
    for y, a, b, k in rs:
        if k == 0:
            continue
        t = y * spec.W + b                     # the clock the run ends on
        pend = [e for e in pend if e > t]      # those finished by now
        start = max(t, pend[-1] if pend else 0)
        pend.append(start + cost)
        deep = max(deep, len(pend))
    return deep


# ---- borrowing the plane -------------------------------------------------
class Tap:
    """Wraps gpu._geom so the identity plane of the last render is kept.
    The law is called exactly as it is; nothing it computes is changed."""

    def __init__(self):
        self.plane = None
        self._geom = gpu._geom

    def __enter__(self):
        def geom(*a, **k):
            self._geom(*a, **k)
            self.plane = k.get("idbuf", a[8] if len(a) > 8 else None)
        gpu._geom = geom
        return self

    def __exit__(self, *exc):
        gpu._geom = self._geom


# ---- the survey ----------------------------------------------------------
def survey(name, pads, frames):
    m = cabinet.VirtualMachine(cabinet.load_cart(carts.path(name)))
    S = dict(frames=0, runs=[], row_max=0, band_max=0, objs=0,
             vote_ok=0, vote_n=0, vote_major=0, wrong_vis=0, wrong_box=0,
             wide_ok=0, q2=0, q3=0, q4=0, listed=0, full=0)
    with Tap() as tap:
        for f in range(frames):
            m.frame(pads(f))
            if tap.plane is None:
                continue
            own = tap.plane & 0x7F
            fb = np.asarray(m.framebuffer())
            rec, rs, left = percepts(own, fb)
            S["frames"] += 1
            n = min(m.vm.dmem[spec.OL_BASE], spec.OL_MAX)
            S["objs"] = max(S["objs"], sum(1 for r in rec if r["vis"]))
            S["listed"] = max(S["listed"], m.vm.dmem[spec.OL_BASE])
            S["full"] += m.vm.dmem[spec.OL_BASE] >= spec.OL_MAX
            for c in (2, 3, 4):
                S[f"q{c}"] = max(S[f"q{c}"], backlog(rs, c))
            # the mock's VIS must be the law's, to the unit
            for k in range(n):
                if rec[k + 1]["vis"] != m.vm.dmem[spec.VIS_BASE + k]:
                    S["wrong_vis"] += 1
            # ...and its box what a search of the plane finds
            for k in range(1, spec.OL_MAX + 1):
                if rec[k]["vis"]:
                    ys, xs = np.nonzero(own == k)
                    if rec[k]["box"] != (xs.min(), xs.max(), ys.min(), ys.max()):
                        S["wrong_box"] += 1
            obj_runs = [r for r in rs if r[3]]
            S["runs"].append(len(obj_runs))
            per_row = np.bincount([r[0] for r in obj_runs], minlength=spec.H)
            S["row_max"] = max(S["row_max"], int(per_row.max()))
            per_band = per_row.reshape(-1, BAND_H).sum(axis=1)
            S["band_max"] = max(S["band_max"], int(per_band.max()))
            # how good is one candidate and one counter?
            for k, tally in left.items():
                best = max(tally.values())
                tot = sum(tally.values())
                S["vote_n"] += 1
                S["vote_ok"] += tally.get(rec[k]["nbr"], 0) == best
                S["vote_major"] += 2 * best > tot
                S["wide_ok"] += tally.get(rec[k]["wide_nbr"], 0) == best
    return S


def _routes():
    import tnd_meter
    return [
        ("seen", lambda f: 0, 120),
        ("watched", lambda f: 0, 120),
        ("edged", lambda f: 0, 120),
        ("hall", lambda f: spec.PAD_UP if f % 90 < 60 else spec.PAD_LEFT, 240),
        ("vessel", lambda f: spec.PAD_UP if f % 90 < 60 else spec.PAD_RIGHT, 240),
        ("tnd", lambda f: tnd_meter.pad("brawl", f), tnd_meter.ROUTES["brawl"]),
        ("tnd", lambda f: tnd_meter.pad("tour", f), tnd_meter.ROUTES["tour"]),
    ]


def main():
    labels = ["seen", "watched", "edged", "hall", "vessel",
              "tnd, brawl", "tnd, tour"]
    rows = [(l, survey(n, p, f)) for l, (n, p, f) in zip(labels, _routes())]
    print("THE COST: one run is one update of one record\n")
    print("| cart | frames | runs a frame: median / max | most in a row "
          "| most in a band | deepest queue at 2 / 3 / 4 clocks an update |")
    print("|---|---:|---:|---:|---:|---:|")
    for label, S in rows:
        r = np.array(S["runs"]) if S["runs"] else np.array([0])
        print(f"| {label} | {S['frames']} | {int(np.median(r)):,} / "
              f"{int(r.max()):,} | {S['row_max']} | {S['band_max']:,} | "
              f"{S['q2']} / {S['q3']} / {S['q4']} |")
    print("\nTHE LIST AND THE ANSWERS\n")
    print("| cart | most objects listed | frames with the list full "
          "| most seen at once | NBR by vote = the true most common "
          "| NBR by widest run = it | a majority existed | VIS wrong | BOX wrong |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for label, S in rows:
        vn = max(S["vote_n"], 1)
        print(f"| {label} | {S['listed']} | {S['full']} | {S['objs']} | "
              f"{100 * S['vote_ok'] / vn:.1f}% | {100 * S['wide_ok'] / vn:.1f}% | "
              f"{100 * S['vote_major'] / vn:.1f}% | {S['wrong_vis']} | "
              f"{S['wrong_box']} |")


if __name__ == "__main__":
    main()
