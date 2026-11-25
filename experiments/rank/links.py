"""FROM HERE, WHAT WAS HIS NEXT MOVE: a session's blows landed in order (read.py's OUT.npz) -- what followed what.

    python3 experiments/rank/links.py OUT.npz [OUT2.npz ...]"""
import sys, collections
import numpy as np
MV = ["jab", "cross", "lead hook", "rear hook", "haymaker", "lead uppercut", "rear uppercut", "gun", "charged"]
ST = {0: "tank", 1: "run", 2: "boxer", 3: "targeting"}; Z = ["head", "body", "legs", "?"]; RUNK = {9: "dive", 10: "slide", 11: "handspring", 12: "slam", 13: "lance"}
def runbody(w): return (w >> 8) & 3 == 1 and not (w >> 4) & 3 and (w & 15) >= 9 and not w & 0x1000
def kind(w): return "gun" if w & 0x1000 else ("run's body" if runbody(w) else "fist")
def sty(w): return ST[((w >> 8) & 3) % 3]
for f in sys.argv[1:]:
    z = np.load(f); seq = [(int(a), int(b)) for a, b in z["seq"]]; pts = z["pts"]; n = len(pts)
    same = sum(1 for (f0, w0), (f1, w1) in zip(seq, seq[1:]) if w0 == w1)
    samek = sum(1 for (f0, w0), (f1, w1) in zip(seq, seq[1:]) if kind(w0) == kind(w1))
    sames = sum(1 for (f0, w0), (f1, w1) in zip(seq, seq[1:]) if sty(w0) == sty(w1))
    runs = []; cur = 1
    for (f0, w0), (f1, w1) in zip(seq, seq[1:]):
        if w0 == w1: cur += 1
        else: runs.append(cur); cur = 1
    runs.append(cur)
    tr = collections.Counter((sty(w0) + " " + kind(w0), sty(w1) + " " + kind(w1)) for (f0, w0), (f1, w1) in zip(seq, seq[1:]) if (sty(w0), kind(w0)) != (sty(w1), kind(w1)) and f1 - f0 < 180)
    gaps = np.diff([f_ for f_, _ in seq])
    # five-blow windows: how many distinct ways, kinds, styles
    d5 = [len({w for _, w in seq[i:i + 5]}) for i in range(len(seq) - 4)]
    s5 = [len({sty(w) for _, w in seq[i:i + 5]}) for i in range(len(seq) - 4)]
    print(f"{f}: {len(seq)} blows landed in {n / 3600:.1f} min")
    print(f"  the next blow landed: the same way {100 * same / (len(seq) - 1):.0f}%, the same kind {100 * samek / (len(seq) - 1):.0f}%, the same style {100 * sames / (len(seq) - 1):.0f}%")
    print(f"  the same way in a row: median {int(np.median(runs))}, most {max(runs)}; in any five blows: {np.mean(d5):.1f} ways on average, all five different {100 * np.mean(np.array(d5) == 5):.0f}%, one style only {100 * np.mean(np.array(s5) == 1):.0f}%, all three styles {100 * np.mean(np.array(s5) == 3):.0f}%")
    cold = (np.clip(gaps - 120, 0, None).sum() + max(0, n - seq[-1][0] - 120) + max(0, seq[0][0] - 120)) / n
    print(f"  between blows landed: median {np.median(gaps) / 60:.1f} s; over 2 s (the meter cools hard) {100 * np.mean(gaps > 120):.0f}% of gaps -- {100 * cold:.0f}% of the session's frames are past two seconds since a blow landed")
    print("  what he went to, from one style-and-kind to another, within three seconds:")
    for (a, b), c in tr.most_common(8): print(f"     {c:4d}  {a} -> {b}")
