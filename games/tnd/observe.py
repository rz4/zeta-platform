"""observe.py -- what a tape of TEAR NOT DEMON shows, as numbers and frame ranges.

zeta/experience.py replays a tape on the law and reads the cells named here
after every frame; observe() turns that trace into the OBSERVED half of an
experiment record. Counts, rates and where in the tape they are -- nothing
about what the player wanted (docs/EXPERIENCE-IMPRINTING.md: an observation
is not an intention).

It reads what the build has: a cell a layer lacks is simply not measured.
"""
import numpy as np

PAD = {"up": 1, "down": 2, "left": 4, "right": 8, "a": 16, "b": 32, "x": 64, "y": 128, "l": 256, "r": 512,
       "start": 1024, "select": 2048}
MOVES = ("jab", "cross", "lead_hook", "rear_hook", "special", "lead_uppercut", "rear_uppercut", "gun", "gun_charged")
CELLS = ["px", "pz", "f_mv", "f_sty", "anim", "af", "f_py", "f_evf", "f_c3", "slow_on", "gun_draw", "knob_on", "t_spot",
         "lab_gh", "lab_si", "b_in", "p_hp"] + [f"e{k}_{c}" for k in range(7) for c in ("st", "hp")]
ARRAYS = ["lab_ey"]
STANCES = ("tank", "run", "boxer", "targeting")      # f_sty: 0 the tank, 1 the run (L twice), 2 the boxer (L), 3 targeting


def _pad_bits():
    try:
        from zeta import spec
        return {k: getattr(spec, "PAD_" + k.upper()) for k in PAD}
    except Exception:
        return PAD


def _press(held):
    return np.flatnonzero(held[1:] & ~held[:-1]) + 1


def _ranges(mask, least=1):
    """[first, last] frames of each run of a true mask, longest first"""
    edge = np.flatnonzero(np.diff(np.concatenate([[0], mask.astype(np.int8), [0]])))
    runs = [(int(a), int(b - 1)) for a, b in zip(edge[::2], edge[1::2]) if b - a >= least]
    return sorted(runs, key=lambda r: r[0] - r[1])


def observe(t):
    P = _pad_bits()
    pad, F = t.pad, t.frames
    held = {k: (pad & v) != 0 for k, v in P.items()}
    mins = F / 3600
    out = {"minutes": round(mins, 2)}
    out["buttons"] = {k: {"presses": int(len(_press(h))), "held_share": round(float(h.mean()), 3)} for k, h in held.items()
                      if k in ("a", "b", "x", "y", "l", "r", "select")}
    out["held_together_share"] = {f"{a}+{b}": round(float((held[a] & held[b]).mean()), 3)
                                  for a, b in (("l", "r"), ("b", "r"), ("y", "b"), ("x", "a"), ("l", "a"))}
    if t.has("slow_on"):
        out["slowed_share"] = round(float((t.col("slow_on") != 0).mean()), 3)
    if t.has("f_sty"):
        s = t.col("f_sty")
        out["stance_share"] = {n: round(float((s == k).mean()), 3) for k, n in enumerate(STANCES)}
    if not (t.has("anim") and t.has("f_mv") and t.has("af")):
        return out
    anim, mv, af = t.col("anim"), t.col("f_mv"), t.col("af")
    start = np.flatnonzero((anim[1:] == 2) & ((anim[:-1] != 2) | (af[1:] < af[:-1]))) + 1      # a blow begins
    out["blows"] = {"thrown": int(len(start)), "a_minute": round(len(start) / mins, 1),
                    "by_move": {MOVES[k]: int((mv[start] == k).sum()) for k in range(len(MOVES)) if (mv[start] == k).any()}}
    if t.has("slow_on"):
        out["blows"]["begun_in_slowed_time_share"] = round(float((t.col("slow_on")[start] != 0).mean()), 3) if len(start) else 0
    bodies = [k for k in range(7) if t.has(f"e{k}_hp")]
    if bodies:
        hp = np.stack([t.col(f"e{k}_hp") for k in bodies], 1)
        st = np.stack([t.col(f"e{k}_st") for k in bodies], 1)
        hit = np.flatnonzero((np.diff(hp, axis=0) < 0).any(1)) + 1
        out["bodies"] = {"blows_landed": int(len(hit)), "landed_a_minute": round(len(hit) / mins, 1),
                         "put_down": int(((st[1:] == 2) & (st[:-1] == 1)).sum())}
        # JAB STRINGS: presses of the jab less than half a second apart; how many of a string's landed before one missed
        jabs = start[np.isin(mv[start], (0, 1))]
        strings = np.split(jabs, np.flatnonzero(np.diff(jabs) > 30) + 1) if len(jabs) else []
        by, long_ = {}, []
        for s in strings:
            landed = [bool(((hit >= f) & (hit < f + 14)).any()) for f in s]
            if not len(s) or not landed[0]:
                continue
            run = next((i for i, ok in enumerate(landed) if not ok), len(landed))
            by.setdefault(min(len(s), 8), []).append(run)
            if run >= 5:
                long_.append([int(s[0]), int(s[-1]), int(run)])
        out["jab_strings"] = {"that_began_with_a_hit": int(sum(len(v) for v in by.values())),
                              "mean_landed_in_a_row_by_length": {str(k): round(float(np.mean(v)), 2) for k, v in sorted(by.items())},
                              "five_or_more_in_a_row": {"count": len(long_), "frames": sorted(long_, key=lambda r: -r[2])[:8]}}
        if t.has("lab_ey"):
            ey = t.arr("lab_ey") / 65536
            up = ey.max(1)
            out["bodies"]["highest_thrown"] = round(float(up.max()), 2)
            out["bodies"]["frames_one_was_above_half_a_unit"] = int((up > 0.5).sum())
            out["bodies"]["above_three_units"] = {"frames": int((up > 3.0).sum()), "ranges": [list(r) for r in _ranges(up > 3.0)[:6]]}
            out["bodies"]["struck_in_the_air"] = int((up[np.clip(hit - 1, 0, F - 1)] > 0.05).sum())
    # THE PASS: Y pressed with B down (or let go within 8 frames), and B pressed with Y down
    def recent(h, f, n=8):
        return bool(h[max(0, f - n):f + 1].any())
    y_on_b = [int(f) for f in _press(held["y"]) if recent(held["b"], f)]
    b_on_y = [int(f) for f in _press(held["b"]) if recent(held["y"], f)]
    x_on_a = [int(f) for f in _press(held["x"]) if recent(held["a"], f)]
    out["passes"] = {"y_with_b_held": {"count": len(y_on_b), "frames": y_on_b[:40]},
                     "b_with_y_held": {"count": len(b_on_y)}, "x_with_a_held": {"count": len(x_on_a)}}
    if t.has("slow_on") and y_on_b:
        out["passes"]["y_with_b_held"]["in_slowed_time"] = int((t.col("slow_on")[y_on_b] != 0).sum())
    if t.has("f_sty") and y_on_b:
        s = t.col("f_sty")[y_on_b]
        out["passes"]["y_with_b_held"]["stance"] = {n: int((s == k).sum()) for k, n in enumerate(STANCES)}
    if t.has("f_py"):
        py = t.col("f_py")
        out["jumps"] = int(((py[1:] > 0) & (py[:-1] == 0)).sum())
    if t.has("f_evf"):
        e = t.col("f_evf")
        out["dodges_and_flips"] = int(((e[1:] > 0) & (e[:-1] == 0)).sum())
    if t.has("lab_si"):
        si = t.col("lab_si")
        out["structures"] = {"minutes_on_one": round(float((si >= 0).mean() * mins), 2),
                             "frames_on_each": {str(int(k)): int(v) for k, v in zip(*np.unique(si[si >= 0], return_counts=True))},
                             "highest_stood": round(float(t.col("lab_gh").max() / 65536), 2)}
    if t.has("knob_on"):
        out["tuner_open_minutes"] = round(float((t.col("knob_on") != 0).mean() * mins), 2)
    if t.has("gun_draw") and held["b"].any():
        b = held["b"]
        out["b_held"] = {"share": round(float(b.mean()), 3),
                         "of_which": {n: round(float((b & m).sum() / b.sum()), 3) for n, m in
                                      (("standing", anim == 0), ("walking", anim == 1), ("running", anim == 5))}}
    return out
