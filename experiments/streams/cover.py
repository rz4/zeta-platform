"""which program words each style of play runs, over his session; and how often the pose changes"""
import sys, pickle; sys.path.insert(0, ".")
import numpy as np
from zeta import deploy, tape as ztape, cabinet, spec, gpu, experience as X
zol, tape_, out = sys.argv[1], sys.argv[2], sys.argv[3]
sym = {k: v[0] for k, v in X.symbols(open(zol).read()).items()}
header, pads = ztape.decode(open(tape_, "rb").read())
if len(sys.argv) > 4: pads = pads[:int(sys.argv[4])]
cart = cabinet.load_cart(zol); cart["sd"] = deploy.card_images("build/tapes/20261121-172911.card.bin")
gpu.render = lambda *a, **k: np.zeros((spec.H, spec.W, 3), np.uint8)
m = cabinet.VirtualMachine(cart); d = m.vm.dmem
hits = bytearray(spec.IMEM_WORDS)
class Cov(list):
    def __getitem__(self, i):
        if i.__class__ is int: hits[i] = 1
        return list.__getitem__(self, i)
m.vm.imem = Cov(m.vm.imem)
progs = {}      # signature -> [frames, {key: bytearray}]
rows = []
for f, p in enumerate(pads):
    sig = hash(tuple(list.__getitem__(m.vm.imem, slice(0, 48))))
    m.frame(p)
    if not isinstance(m.vm.imem, Cov): m.vm.imem = Cov(m.vm.imem)
    sty, lock, slow, fight = d[sym["f_sty"]], d[sym["locked"]], d[sym["slow_on"]], d[sym["yard_fight"]]
    pr = progs.setdefault(sig, [0, {}])
    pr[0] += 1
    cov = pr[1].setdefault(sty, bytearray(spec.IMEM_WORDS))
    idx = np.flatnonzero(np.frombuffer(hits, np.uint8))
    for i in idx: cov[i] = 1; hits[i] = 0
    rows.append((sig, sty, lock, slow, d[sym["pose"]], spec.FUEL - m.vm.fuel_left, len(idx)))
    if f % 10000 == 0: print(f, flush=True)
pickle.dump({"progs": {k: (v[0], {s: bytes(b) for s, b in v[1].items()}) for k, v in progs.items()}, "rows": rows}, open(out, "wb"))
print("done", len(rows))
