#!/usr/bin/env python3
"""scales.py -- ONE WORLD, THREE SCHEDULES: an experiment in ordering computation by scale.

The developer's note of 2026-11-23: organise memory, computation and updates
as a hierarchy S_k = R^k (he proposes R = 64), each scale with its own
resolution, working set and update rate; stagger them so no frame carries
them all; and measure it against the machine's ordinary scheduling "using
identical scenes and simulations": working set, words moved, worst-case
frame, and whether the output is the same.

THE WORLD. A torus 2^w units across holding N movers, each with a constant
velocity. The player walks it (the pad). A mover within TOUCH of him is
TAKEN: it stops for good and his score goes up (a permanent change, so a
schedule that misses one is wrong for ever after). Every mover within DRAW
of him is drawn. That is the whole law, and `Model` is it in numpy.

THE THREE SCHEDULES, each a cart built from this file:

  flat     every mover, every frame. How every cart on this machine is
           scheduled today.
  burst    scales, unstaggered: scale k's whole list is visited on the
           frames that are multiples of R^k. The average is the hierarchy's;
           the worst frame is the frame they all fall on.
  scaled   scales, staggered: scale k gets a FIXED number of visits every
           frame, B_k, and a cursor that walks its list.

WHY A COARSE SCALE IS ALLOWED TO BE LATE. A mover and the player close on
each other by at most VREL a frame. A mover that was farther than
DRAW + R^k * VREL when it was last looked at cannot be inside DRAW until
R^k frames have gone by. So scale k is exactly the movers that far away:
its radius grows as R^k because its period does. When one is visited it is
brought up to date in one step (x += dt * v: exact, the arithmetic wraps the
same way), and put in the scale its distance now asks for. Nothing is
approximated; the claim to test is that the picture and the state are
IDENTICAL to flat's, frame for frame.

The cart checks itself: `late` counts visits that came after their scale's
period, `over` a list that was full, `drop` an object the list had no room
for. All three must stay zero for a run to count.

    python3 experiments/scale/scales.py            the sweeps -> results.json and a table
    python3 experiments/scale/scales.py silicon    the worst frame in clocks, and law against silicon
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / "zeta" / "spec.py").is_file())
sys.path.insert(0, str(ROOT))
from zeta import cabinet, gpu, spec                      # noqa: E402
from zeta.forge import ONE, Cart, Mesh, Table            # noqa: E402

PV = ONE // 8                   # the player's speed, units a frame, each axis
VMAX = ONE // 32                # a mover's, each axis
VREL = PV + VMAX                # the most they close by in a frame
DRAW = 16 * ONE                 # a mover nearer than this (the larger of |dx|, |dz|) is drawn
TOUCH = 4 * ONE                  # ...nearer than this, taken
JUMP = 300 * ONE                # A: he is somewhere else at once. No schedule that trusts his speed survives it;
                                # it is here to measure how long the scales are wrong after one (the routes never press it)
M32 = 0xFFFFFFFF
BUILD = ROOT / "build" / "scales"


def plan(n, world_sh, r_sh):
    """the scales this world supports at ratio 2^r_sh: each one's inner
    radius, period, capacity and visits a frame"""
    half = 1 << (world_sh + 15)
    radius = []                                 # radius[j]: nearer than this belongs to scale <= j
    k = 1
    while DRAW + (VREL << (r_sh * k)) < half:
        radius.append(DRAW + (VREL << (r_sh * k)))
        k += 1
    if not radius:
        raise SystemExit(f"a world {1 << world_sh} units across has no room for a scale of period {1 << r_sh}")
    K = len(radius)
    dens = n / float(2 * half) ** 2
    area = [float(2 * r) ** 2 for r in radius] + [float(2 * half) ** 2]
    expect = [dens * (area[j] - (area[j - 1] if j else 0.0)) for j in range(K + 1)]
    cap = [min(n, max(32, int(4 * expect[0]) + 16))]
    cap += [min(n, int(3 * expect[j]) + 16) for j in range(1, K)] + [n]
    period = [1] + [1 << (r_sh * j) for j in range(1, K + 1)]
    visits = [0] + [math.ceil(1.25 * cap[j] / period[j]) for j in range(1, K + 1)]
    return {"K": K, "radius": radius, "period": period, "cap": cap, "visits": visits,
            "expect": [round(e, 1) for e in expect]}


def world(n, world_sh, seed=1):
    """N movers: where they start and how they go (never still)"""
    rng = np.random.default_rng(seed)
    bits = world_sh + 16
    x, z = (rng.integers(0, 1 << bits, n, dtype=np.int64) for _ in range(2))
    vx, vz = (rng.integers(-VMAX, VMAX + 1, n, dtype=np.int64) for _ in range(2))
    vz[(vx == 0) & (vz == 0)] = VMAX
    return x, z, vx, vz


def route(frames, seed=7):
    """a walk: a direction or two held for a while, a pause now and then"""
    rng = np.random.default_rng(seed)
    dirs = [spec.PAD_UP, spec.PAD_DOWN, spec.PAD_LEFT, spec.PAD_RIGHT, spec.PAD_UP | spec.PAD_RIGHT,
            spec.PAD_UP | spec.PAD_LEFT, spec.PAD_DOWN | spec.PAD_RIGHT, spec.PAD_DOWN | spec.PAD_LEFT, 0]
    pads = []
    while len(pads) < frames:
        pads += [int(dirs[rng.integers(0, len(dirs))])] * int(rng.integers(20, 200))
    return pads[:frames]


class Model:
    """the law of this world: every mover, every frame"""

    def __init__(self, n, world_sh, seed=1):
        self.x, self.z, self.vx, self.vz = world(n, world_sh, seed)
        self.bits = world_sh + 16
        self.taken = np.zeros(n, bool)
        self.px = self.pz = self.score = 0

    def rel(self, a, p):
        d = (a - p) & ((1 << self.bits) - 1)
        return np.where(d >= 1 << (self.bits - 1), d - (1 << self.bits), d)

    def frame(self, pad):
        self.px = (self.px + PV * (bool(pad & spec.PAD_RIGHT) - bool(pad & spec.PAD_LEFT))) & M32
        self.pz = (self.pz + PV * (bool(pad & spec.PAD_UP) - bool(pad & spec.PAD_DOWN))) & M32
        if pad & spec.PAD_A:
            self.px = (self.px + JUMP) & M32
        go = ~self.taken
        self.x = (self.x + self.vx * go) & M32
        self.z = (self.z + self.vz * go) & M32
        dx, dz = self.rel(self.x, self.px), self.rel(self.z, self.pz)
        ad = np.maximum(np.abs(dx), np.abs(dz))
        hit = go & (ad < TOUCH)
        self.taken |= hit
        self.score += int(hit.sum())
        near = np.flatnonzero(ad < DRAW)
        return sorted((bool(self.taken[i]), int(dx[i]), int(dz[i])) for i in near)


def _post(w, h, rgb):
    v, f = [], []
    hw, top = int(w * ONE / 2), int(h * ONE)
    for x, y, z in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)):
        v += [(-hw, hw)[x], (0, top)[y], (-hw, hw)[z]]
    for (a, b, c, d), s in (((0, 1, 2, 3), 1.0), ((5, 4, 7, 6), 0.55), ((4, 0, 3, 7), 0.75), ((1, 5, 6, 2), 0.75),
                            ((3, 2, 6, 7), 1.3)):
        col = sum(min(255, int(((rgb >> sh) & 255) * s)) << sh for sh in (16, 8, 0))
        f += [(a, c, b, col), (a, d, c, col)]
    return Mesh(v, f)


def build(mode, n, world_sh, r_sh=3, seed=1, out=None):
    """the cart, and where its cells are"""
    assert mode in ("flat", "burst", "scaled")
    P = plan(n, world_sh, r_sh)
    K, radius, cap = P["K"], P["radius"], P["cap"]
    x, z, vx, vz = world(n, world_sh, seed)
    sx = 16 - world_sh                                   # shl then shr by this: the short way round the torus
    cart = Cart(f"scales_{mode}_{n}")
    m_go, m_taken, m_him = (cart.data(m, nm) for m, nm in ((_post(0.7, 1.6, 0x3FB950), "m_go"),
                                                         (_post(0.9, 0.5, 0xD03030), "m_taken"),
                                                         (_post(0.5, 2.2, 0xE6E6E2), "m_him")))
    g = int(40 * ONE)
    m_floor = cart.data(Mesh([-g, 0, -g, g, 0, -g, g, 0, g, -g, 0, g], [(0, 2, 1, 0x26282C), (0, 3, 2, 0x26282C)]), "m_floor")
    flags = _post(1, 1, 0).flags
    words = []
    for i in range(n):
        words += [int(x[i]), int(z[i]), ((int(vx[i]) & 0xFFFF) << 16) | (int(vz[i]) & 0xFFFF), 0]
    ACT = cart.data(Table(words), "actors")
    PX, PZ, NOW, SCORE, LATE, OVER, DROP, NOBJ = (cart.var(k) for k in ("px", "pz", "now", "score", "late", "over", "drop", "nobj"))
    AI, AP, V, DX, DZ, AD, DT, CNT, MSEL = (cart.var(k) for k in ("ai", "ap", "v", "dx", "dz", "ad", "dt", "cnt", "msel"))
    LIST, LEN, CUR = [], [], []
    if mode != "flat":
        bits = world_sh + 16
        rel = lambda a: ((int(a) + (1 << (bits - 1))) & ((1 << bits) - 1)) - (1 << (bits - 1))    # noqa: E731
        start = [[] for _ in range(K + 1)]
        for i in range(n):
            d = max(abs(rel(x[i])), abs(rel(z[i])))
            start[next((j for j in range(K) if d < radius[j]), K)].append(i)
        for j in range(K + 1):
            assert len(start[j]) <= cap[j], f"scale {j} starts with {len(start[j])} of {cap[j]}"
            LIST.append(cart.data(Table(start[j] + [0] * (cap[j] - len(start[j]))), f"list{j}"))
            LEN.append(cart.data(Table([len(start[j])]), f"len{j}"))
            CUR.append(cart.var(f"cur{j}"))
    cart.boot(spec.CAM_Y, 11 * ONE)
    cart.boot(spec.CAM_Z, -17 * ONE)
    cart.boot(spec.CAM_PITCH, PITCH)
    p = cart.program()
    L_DIST, L_NEAR = p.label("dist"), p.label("near")

    def fld(k):
        p.load(AP)
        if k:
            p.push(k).emit("add")
        return p.emit("loadi")

    def setfld(k):                                       # (the value is on the stack)
        p.load(AP)
        if k:
            p.push(k).emit("add")
        return p.emit("storei")

    def actor():                                         # AI -> AP, V
        p.load(AI).emit("shl 2").push(int(ACT)).emit("add").store(AP)
        fld(2).store(V)

    def advance(by=None):                                # it goes its way: one frame, or `by` of them at once
        sk = p.label("still")
        p.load(V).emit(f"jz {sk}")
        for k, unpack in ((0, ("shr 16",)), (1, ("shl 16", "shr 16"))):
            fld(k).load(V).emit(*unpack)
            if by is not None:
                p.load(by).emit("mul")
            p.emit("add")
            setfld(k)
        p.mark(sk)

    def append(j):
        p.load(AI).load(LEN[j]).push(int(LIST[j])).emit("add", "storei")
        p.addi(LEN[j], 1)

    def insert(j):                                       # into scale j; a full list is counted, and the top one takes it
        if j == K:
            return append(K)
        full, done = p.label("full"), p.label("ins")
        p.load(LEN[j]).push(cap[j]).emit("lt", f"jz {full}")
        append(j)
        p.emit(f"jmp {done}")
        p.mark(full)
        p.addi(OVER, 1)
        append(K)
        p.mark(done)

    def remove(k, idx):                                  # the last of the list into its place
        p.load(LEN[k]).push(1).emit("sub", "dup").store(LEN[k])
        p.push(int(LIST[k])).emit("add", "loadi")
        p.load(idx).push(int(LIST[k])).emit("add", "storei")

    def replace(k, idx, top):
        """the mover at `idx` of scale k has its distance in AD: leave it, or move it to the scale that asks for it"""
        for j in list(range(0 if k else 1, K)) + [K]:
            nxt = p.label("band")
            if j < K:
                p.load(AD).push32(radius[j]).emit("lt", f"jz {nxt}")
            if j == k:
                p.addi(idx, 1)
            else:
                remove(k, idx)
                insert(j)
            p.emit(f"jmp {top}")
            p.mark(nxt)

    # ---- the frame ----
    p.addi(NOW, 1)
    for bit, cell, d in ((spec.PAD_RIGHT, PX, PV), (spec.PAD_LEFT, PX, -PV), (spec.PAD_UP, PZ, PV), (spec.PAD_DOWN, PZ, -PV)):
        sk = p.label("pad")
        p.load(spec.REG_PAD).push(bit).emit("and", f"jz {sk}")
        p.addi(cell, d)
        p.mark(sk)
    sk = p.label("jump")
    p.load(spec.REG_PAD).push(spec.PAD_A).emit("and", f"jz {sk}")
    p.load(PX).push32(JUMP).emit("add").store(PX)
    p.mark(sk)
    p.set(NOBJ, 0)
    p.object(NOBJ, int(m_floor), 0, 0, 0, 0, flags)
    p.object(NOBJ, int(m_him), 0, 0, 0, 0, flags)
    if mode == "flat":
        top, end = p.label("flat"), p.label("flatend")
        p.set(AI, 0)
        p.mark(top)
        p.load(AI).push(n).emit("lt", f"jz {end}")
        actor()
        advance()
        p.emit(f"call {L_DIST}", f"call {L_NEAR}")
        p.addi(AI, 1).emit(f"jmp {top}")
        p.mark(end)
    else:
        # scale 0: every one of them, every frame
        top, end, stay = p.label("s0"), p.label("s0end"), p.label("s0stay")
        p.set(CUR[0], 0)
        p.mark(top)
        p.load(CUR[0]).load(LEN[0]).emit("lt", f"jz {end}")
        p.load(CUR[0]).push(int(LIST[0])).emit("add", "loadi").store(AI)
        actor()
        advance()
        p.emit(f"call {L_DIST}")
        p.load(AD).push32(radius[0]).emit("lt", f"jz {stay}_out")
        p.emit(f"call {L_NEAR}")
        p.addi(CUR[0], 1).emit(f"jmp {top}")
        p.mark(f"{stay}_out")
        p.load(NOW)
        setfld(3)                                         # it is exact as of now, and goes out to its scale
        replace(0, CUR[0], top)
        p.mark(end)
        # the coarse scales
        for k in range(1, K + 1):
            top, end = p.label(f"s{k}"), p.label(f"s{k}end")
            if mode == "scaled":
                p.set(CNT, P["visits"][k])
            else:
                fire = p.label("fire")
                p.set(CNT, 0)
                p.load(NOW).push(P["period"][k] - 1).emit("and", f"jz {fire}", f"jmp {end}")
                p.mark(fire)
                p.load(LEN[k]).store(CNT).set(CUR[k], 0)
            p.mark(top)
            p.load(CNT).emit(f"jz {end}")
            p.addi(CNT, -1)
            p.load(LEN[k]).emit(f"jz {end}")
            wrap = p.label("wrap")
            p.load(CUR[k]).load(LEN[k]).emit("lt", f"jz {wrap}_w", f"jmp {wrap}")
            p.mark(f"{wrap}_w")
            p.set(CUR[k], 0)
            p.mark(wrap)
            p.load(CUR[k]).push(int(LIST[k])).emit("add", "loadi").store(AI)
            actor()
            p.load(NOW)
            fld(3).emit("sub").store(DT)
            ok = p.label("intime")
            p.push(P["period"][k]).load(DT).emit("lt", f"jz {ok}")
            p.addi(LATE, 1)
            p.mark(ok)
            advance(DT)
            p.load(NOW)
            setfld(3)
            p.emit(f"call {L_DIST}")
            replace(k, CUR[k], top)
            p.mark(end)
    p.load(NOBJ).store(spec.OL_BASE)
    p.emit("halt")

    # DIST: the mover at AP -> DX, DZ (the short way round), AD the larger of their sizes
    p.mark(L_DIST)
    for k, cell, him in ((0, DX, PX), (1, DZ, PZ)):
        fld(k).load(him).emit("sub", f"shl {sx}", f"shr {sx}", "dup").store(cell)
        pos = p.label("abs")
        p.emit("dup").push(0).emit("lt", f"jz {pos}")
        p.push(0).emit("swap", "sub")
        p.mark(pos)
        if k == 0:
            p.store(AD)
        else:
            keep, done = p.label("max"), p.label("maxd")
            p.emit("dup").load(AD).emit("lt", f"jz {keep}", "drop", f"jmp {done}")
            p.mark(keep)
            p.store(AD)
            p.mark(done)
    p.emit("ret")
    # NEAR: it is taken if he touches it; it is drawn if it is within DRAW
    p.mark(L_NEAR)
    nt, nd = p.label("notouch"), p.label("nodraw")
    p.load(V).emit(f"jz {nt}")
    p.load(AD).push(TOUCH).emit("lt", f"jz {nt}")
    p.push(0)
    setfld(2)
    p.set(V, 0).addi(SCORE, 1)
    p.mark(nt)
    p.load(AD).push32(DRAW).emit("lt", f"jz {nd}")
    room = p.label("room")
    p.load(NOBJ).push(spec.OL_MAX).emit("lt", f"jz {room}")
    go = p.label("which")
    p.set(MSEL, int(m_taken)).load(V).emit(f"jz {go}")
    p.set(MSEL, int(m_go))
    p.mark(go)
    p.object(NOBJ, [f"load {int(MSEL)}"], [f"load {int(DX)}"], 0, [f"load {int(DZ)}"], 0, flags)
    p.emit("ret")
    p.mark(room)
    p.addi(DROP, 1)
    p.mark(nd)
    p.emit("ret")

    BUILD.mkdir(parents=True, exist_ok=True)
    out = Path(out) if out else BUILD / f"{mode}_{n}_w{world_sh}_r{r_sh}.zol"
    cart.write(out)
    cells = {k: int(v) for k, v in (("px", PX), ("pz", PZ), ("now", NOW), ("score", SCORE), ("late", LATE), ("over", OVER),
                                    ("drop", DROP), ("actors", ACT), ("m_go", m_go), ("m_taken", m_taken))}
    cells["len"] = [int(a) for a in LEN]
    cells["list0"] = int(LIST[0]) if LIST else None
    return out, {"mode": mode, "n": n, "world_sh": world_sh, "r_sh": r_sh, "seed": seed, "plan": P, "cells": cells,
                 "program_words": len([ln for ln in p.lines() if ln and not ln.rstrip().endswith(":")])}


PITCH = 72                      # the lens looks down on him (set by eye: `python3 scales.py look`)


class _Touched(list):
    """data memory that counts what the program reads and writes"""
    on = False

    def reset(self):
        self.seen, self.moved = set(), 0

    def __getitem__(self, i):
        if self.on:
            self.seen.add(i)
            self.moved += 1
        return list.__getitem__(self, i)

    def __setitem__(self, i, v):
        if self.on:
            self.seen.add(i)
            self.moved += 1
        list.__setitem__(self, i, v)


def run(path, info, pads, paint=False, say=None):
    """the cart on the law, frame by frame, against the model: what it cost and whether it was right"""
    n, c, mode = info["n"], info["cells"], info["mode"]
    m = cabinet.VirtualMachine(cabinet.load_cart(path))
    mem = _Touched(m.vm.dmem)
    m.vm.dmem = mem
    inner = m.vm.frame

    def metered(*a, **k):
        mem.on = True
        try:
            return inner(*a, **k)
        finally:
            mem.on = False
    m.vm.frame = metered
    model = Model(n, info["world_sh"], info["seed"])
    blank = np.zeros((spec.H, spec.W, 3), np.uint8)
    keep = gpu.render
    if not paint:
        gpu.render = lambda *a, **k: blank
    fuel, ws, moved, lens, shots = [], [], [], [], []
    wrong_state = wrong_draw = overrun = 0
    first_wrong = None
    try:
        for f, pad in enumerate(pads):
            mem.reset()
            m.frame(pad)
            want = model.frame(pad)
            d = m.vm.dmem
            fuel.append(spec.FUEL - m.vm.fuel_left)
            overrun += m.vm.fuel_left == 0
            ws.append(len(mem.seen))
            moved.append(mem.moved)
            a = np.array(list.__getitem__(d, slice(c["actors"], c["actors"] + 4 * n)), np.int64).reshape(n, 4)
            v = a[:, 2]
            vx = ((v >> 16) ^ 0x8000) - 0x8000
            vz = ((v & 0xFFFF) ^ 0x8000) - 0x8000
            dt = 0
            if mode != "flat":                  # a coarse mover is exact as of its last visit; scale 0's are exact now
                dt = list.__getitem__(d, c["now"]) - a[:, 3]
                near = list.__getitem__(d, slice(c["list0"], c["list0"] + list.__getitem__(d, c["len"][0])))
                dt[near] = 0
            ok = (((a[:, 0] + vx * dt) & M32) == model.x).all() and (((a[:, 1] + vz * dt) & M32) == model.z).all() \
                and ((v == 0) == model.taken).all() and list.__getitem__(d, c["score"]) == model.score \
                and list.__getitem__(d, c["px"]) == model.px and list.__getitem__(d, c["pz"]) == model.pz
            nob = list.__getitem__(d, spec.OL_BASE)
            ol = [list.__getitem__(d, slice(spec.OL_BASE + 1 + i * spec.OL_STRIDE, spec.OL_BASE + 1 + (i + 1) * spec.OL_STRIDE))
                  for i in range(2, nob)]
            s32 = lambda q: q - (1 << 32) if q & (1 << 31) else q      # noqa: E731
            got = sorted((o[0] == c["m_taken"], s32(o[1]), s32(o[3])) for o in ol)
            same = got == want
            wrong_state += not ok
            wrong_draw += not same
            if first_wrong is None and not (ok and same):
                first_wrong = f
            if mode != "flat":
                lens.append([list.__getitem__(d, q) for q in c["len"]])
            if paint:
                shots.append(np.asarray(m.framebuffer()).copy())
            if say and f % 500 == 499:
                say(f + 1)
    finally:
        gpu.render = keep
    d = m.vm.dmem
    fuel, ws, moved = np.array(fuel), np.array(ws), np.array(moved)
    out = {"mode": mode, "n": n, "world": 1 << info["world_sh"], "ratio": 1 << info["r_sh"], "scales": info["plan"]["K"] + 1,
           "frames": len(pads), "instructions": {"median": int(np.median(fuel)), "worst": int(fuel.max()), "ceiling": spec.FUEL},
           "frames_out_of_instructions": int(overrun),
           "working_set_words": {"median": int(np.median(ws)), "worst": int(ws.max())},
           "words_moved": {"median": int(np.median(moved)), "worst": int(moved.max())},
           "frames_state_differs_from_the_law": int(wrong_state), "frames_drawn_set_differs": int(wrong_draw),
           "first_frame_wrong": first_wrong, "late": d[c["late"]], "over": d[c["over"]], "drop": d[c["drop"]],
           "taken": model.score, "program_words": info["program_words"]}
    if lens:
        ln = np.array(lens)
        out["list_lengths"] = {"median": [int(q) for q in np.median(ln, 0)], "worst": [int(q) for q in ln.max(0)],
                               "capacity": info["plan"]["cap"], "visits_a_frame": info["plan"]["visits"],
                               "period": info["plan"]["period"], "radius_units": [round(r / ONE, 1) for r in info["plan"]["radius"]]}
    return (out, shots) if paint else out


SIZES = ((128, 8), (512, 9), (2048, 10))        # movers, and the world's size as a power of two: the same density
FRAMES = 2200


def line(r):
    i, w, t = r["instructions"], r["working_set_words"], r["words_moved"]
    right = "RIGHT" if not (r["frames_state_differs_from_the_law"] or r["frames_drawn_set_differs"]) else \
        f"WRONG from frame {r['first_frame_wrong']}"
    return (f"{r['mode']:7s} N {r['n']:5d} world {r['world']:5d} R {r['ratio']:3d} scales {r['scales']} | instructions "
            f"{i['median']:6d} / {i['worst']:6d} | working set {w['median']:5d} / {w['worst']:5d} | moved {t['median']:6d} / "
            f"{t['worst']:6d} | out of fuel {r['frames_out_of_instructions']:4d} | late {r['late']} over {r['over']} drop "
            f"{r['drop']} | {right}")


def sweeps(frames=FRAMES):
    pads = route(frames)
    rows = []
    for n, w in SIZES:
        for mode in ("flat", "burst", "scaled"):
            rows.append(run(*build(mode, n, w, 3), pads))
            print(line(rows[-1]), flush=True)
    for r_sh in (2, 4, 6):                       # the ratio, at the largest world (3 is above)
        rows.append(run(*build("scaled", 2048, 10, r_sh), pads))
        print(line(rows[-1]), flush=True)
    (HERE / "results.json").write_text(json.dumps({"frames": frames, "pv": PV / ONE, "vmax": VMAX / ONE, "draw": DRAW / ONE,
                                                   "rows": rows}, indent=1) + "\n")


def silicon_rows(frames=140):
    """the worst frame in CLOCKS on the simulated hardware, and its picture against the law's"""
    from zeta import profile, silicon
    pads = route(frames)
    rows = []
    for mode, n, w in (("flat", 512, 9), ("burst", 512, 9), ("scaled", 512, 9), ("burst", 2048, 10), ("scaled", 2048, 10)):
        path, info = build(mode, n, w, 3)
        cart = cabinet.load_cart(path)
        law, si = cabinet.VirtualMachine(cart), silicon.SiliconMachine(cart)
        px = []
        for q in pads:
            law.frame(q)
            si.frame(q)
            px.append(int((np.asarray(law.framebuffer()) != np.asarray(si.framebuffer())).any(2).sum()))
        si.close()
        clk = np.array([r["clk"] for r in profile.cost(cart, pads)])
        rows.append({"mode": mode, "n": n, "frames": frames, "clocks": {"median": int(np.median(clk)), "worst": int(clk.max()),
                                                                     "frame": 864000},
                     "share_of_frame": {"median": round(float(np.median(clk)) / 8640, 1), "worst": round(float(clk.max()) / 8640, 1)},
                     "pixels_differing_law_vs_silicon": int(sum(px))})
        print(rows[-1], flush=True)
    (HERE / "results-silicon.json").write_text(json.dumps({"rows": rows}, indent=1) + "\n")


def silicon_window(first=506, frames=12):
    """the frame every scale falls on (frame 512 at ratio 8), in clocks: the law walks to `first`, and the
    simulated hardware takes the next `frames` from the law's own state"""
    from zeta import profile
    pads = route(first + frames)
    rows = []
    for mode, n, w in (("flat", 512, 9), ("burst", 512, 9), ("scaled", 512, 9), ("burst", 2048, 10), ("scaled", 2048, 10)):
        path, info = build(mode, n, w, 3)
        cart = cabinet.load_cart(path)
        law = cabinet.VirtualMachine(cart)
        keep, gpu.render = gpu.render, (lambda *a, **k: np.zeros((spec.H, spec.W, 3), np.uint8))
        try:
            for q in pads[:first]:
                law.frame(q)
        finally:
            gpu.render = keep
        clk = np.array([r["clk"] for r in profile.cost(cart, pads[first:], state=law.pack(), first=first)])
        rows.append({"mode": mode, "n": n, "frames": [first, first + frames], "clocks_worst": int(clk.max()),
                     "share_of_frame_worst": round(float(clk.max()) / 8640, 1), "at_frame": first + int(np.argmax(clk)),
                     "clocks": [int(c) for c in clk]})
        print(rows[-1], flush=True)
    (HERE / "results-silicon-window.json").write_text(json.dumps({"rows": rows}, indent=1) + "\n")


if __name__ == "__main__":
    if sys.argv[1:2] == ["silicon"]:
        silicon_rows()
    elif sys.argv[1:2] == ["window"]:
        silicon_window()
    elif sys.argv[1:2] == ["look"]:
        from PIL import Image
        path, info = build("scaled", 2048, 10, 3)
        r, shots = run(path, info, route(240), paint=True)
        Image.fromarray(shots[-1]).resize((spec.W * 2, spec.H * 2), Image.NEAREST).save(BUILD / "look.png")
        print(line(r), BUILD / "look.png")
    else:
        sweeps()
