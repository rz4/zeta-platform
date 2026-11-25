"""A SESSION AS IT WAS PLAYED, READ THROUGH THE RANK'S METER: the tape on its own build with the meter added as an
observer (observe.py) -- checked, frame by frame, against the build kept with the tape (his place, his height, his
health, his style, every body's place and health).

    python3 experiments/rank/read.py OBS.zol TAPE.yard.zol TAPE.ztp OUT.npz

OUT.npz: `pts` (the meter, x16, every frame) and `seq` (frame, way) for every paid blow. A WAY is one word:
0x1000 a round | style << 8 | part << 4 | (a fist's move; or a round's charged 1, from the air 2); the run's body
blows are 0x109 the dive, 0x10A the slide, 0x10B the handspring, 0x10C the slam, 0x10D the lance."""
import sys, collections; sys.path.insert(0, ".")
import numpy as np
from zeta import deploy, tape as ztape, cabinet, spec, gpu, experience as X
from zeta.spec import s32
obs, orig, tp, out = sys.argv[1:5]
gpu.render = lambda *a, **k: np.zeros((spec.H, spec.W, 3), np.uint8)
def machine(zol):
    sym = {k: v[0] for k, v in X.symbols(open(zol).read()).items()}
    cart = cabinet.load_cart(zol); cart["sd"] = deploy.card_images("build/tapes/20261121-172911.card.bin")
    m = cabinet.VirtualMachine(cart)
    return m, m.vm.dmem, sym
m, d, sym = machine(obs)
m0, d0, sym0 = machine(orig)
MOTION = ["px", "pz", "f_py", "p_hp", "f_sty"] + [f"e{k}_hp" for k in range(7)]
POS = [f"e{k}_pos" for k in range(7)]
def motion(dd, sy):
    return [dd[sy[n]] for n in MOTION] + [dd[sy[n] + i] for n in POS for i in range(3)]
MV = ["jab", "cross", "lead hook", "rear hook", "haymaker", "lead uppercut", "rear uppercut", "gun", "charged"]
ST = {0: "tank", 1: "run", 2: "boxer", 3: "targeting"}; Z = ["head", "body", "legs", "?"]; RUNK = {9: "dive", 10: "slide", 11: "handspring", 12: "slam", 13: "lance"}
def name(w):
    st = ST[(w >> 8) & 3]
    if w & 0x1000: return f"{st}: a round at the {Z[(w >> 4) & 3]}" + (", charged" if w & 1 else "") + (", from the air" if w & 2 else "")
    if (w >> 8) & 3 == 1 and not (w >> 4) & 3 and (w & 15) >= 9: return "run: the " + RUNK.get(w & 15, "?")
    return f"{st}: {MV[w & 15] if (w & 15) < 9 else '?'} to the {Z[(w >> 4) & 3]}"
def kind(w):
    return "gun" if w & 0x1000 else ("run's body" if (w >> 8) & 3 == 1 and not (w >> 4) & 3 and (w & 15) >= 9 else "fist")
header, pads = ztape.decode(open(tp, "rb").read())
rank_frames = collections.Counter(); ways = collections.Counter(); stale = collections.Counter(); sty_frames = collections.Counter(); sty_pay = collections.Counter(); kinds = collections.Counter()
links = pays = taken = 0; diverged = None; prev_rp = 0; prev_hp = None; pts = np.zeros(len(pads), np.int32); seq = []
for f, p in enumerate(pads):
    rec = [d[sym["s_recent"] + i] for i in range(5)]; lst = s32(d[sym["yard_way_stance"]])
    m.frame(p); m0.frame(p)
    if diverged is None and motion(d, sym) != motion(d0, sym0): diverged = f
    rk, rp, hp = s32(d[sym["s_rank"]]), s32(d[sym["s_rp"]]), s32(d[sym["p_hp"]])
    rank_frames[rk] += 1; pts[f] = s32(d[sym["s_pts"]]); sty_frames[d[sym["f_sty"]] & 3] += 1
    if rp != prev_rp:
        w = s32(d[sym["yard_way"]]); pays += 1; ways[name(w)] += 1; stale[min(3, rec.count(w))] += 1; kinds[kind(w)] += 1
        st = ((w >> 8) & 3) % 3; sty_pay[st] += 1; seq.append((f, w))
        if lst and lst != st + 1: links += 1
    if prev_hp is not None and hp < prev_hp: taken += 1
    prev_rp, prev_hp = rp, hp
n = len(pads); R = "D C B A S SS SSS".split()
print(f"{tp}: {n} frames ({n / 3600:.1f} min); motion against the tape's own build: " + ("the same, every frame" if diverged is None else f"DIVERGED at frame {diverged}"))
print(f"blows landed {pays} ({pays / (n / 3600):.1f} a minute), of them SPENT (a way three times in his last five: paid nothing) {stale[3]}; blows taken {taken}; most points {pts.max() / 16:.0f}; median {np.median(pts) / 16:.0f}")
print("time at each rank: " + ", ".join(f"{R[k]} {100 * v / n:.1f}%" for k, v in sorted(rank_frames.items())))
print("time in each style: " + ", ".join(f"{ST[k]} {100 * v / n:.0f}%" for k, v in sorted(sty_frames.items())) + " | blows landed by style: " + ", ".join(f"{ST[k]} {100 * v / max(1, pays):.0f}%" for k, v in sorted(sty_pay.items())))
print("blows landed by kind: " + ", ".join(f"{k} {100 * v / max(1, pays):.0f}%" for k, v in kinds.most_common()))
print("a landed blow's way, in the last five already: " + ", ".join(f"{('fresh', 'once', 'twice', 'three times or more')[k]} {100 * v / max(1, pays):.0f}%" for k, v in sorted(stale.items())) + f" | from another style than the last: {100 * links / max(1, pays):.0f}%")
print("the ways, by how often (of %d distinct):" % len(ways))
for k, v in ways.most_common(16): print(f"   {v:5d}  {100 * v / max(1, pays):4.1f}%  {k}")
np.savez_compressed(out, pts=pts, seq=np.array(seq, np.int64).reshape(-1, 2))
