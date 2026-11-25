"""which words of data memory a session ever READS (the program, and the picture on sampled frames)"""
import sys, json; sys.path.insert(0, ".")
import numpy as np
from pathlib import Path
from zeta import deploy, tape as ztape, cabinet, spec, gpu, experience as X
zol, out = sys.argv[1], sys.argv[2]
sym = X.symbols(open(zol).read())
reads = bytearray(spec.DMEM_WORDS)
class Mem(list):
    def __getitem__(self, i):
        if i.__class__ is int: reads[i] = 1
        else:
            for k in range(*i.indices(len(self))): reads[k] = 1
        return list.__getitem__(self, i)
real = gpu.render
blank = np.zeros((spec.H, spec.W, 3), np.uint8)
frames = 0
for tp in sys.argv[3:]:
    header, pads = ztape.decode(open(tp, "rb").read())
    cart = cabinet.load_cart(Path(zol)); cart["sd"] = deploy.card_images("build/tapes/20261121-172911.card.bin")
    m = cabinet.VirtualMachine(cart); m.vm.dmem = Mem(m.vm.dmem)
    for f, p in enumerate(pads):
        gpu.render = real if f % 40 == 0 else (lambda *a, **k: blank)
        m.frame(p)
        if not isinstance(m.vm.dmem, Mem): m.vm.dmem = Mem(m.vm.dmem)
    frames += len(pads)
rows = []
for n, (a, w) in sym.items():
    if a + w <= 11700:
        rows.append((w - sum(reads[a:a + w]), w, n))
rows.sort(reverse=True)
named = sum(w for _, w, _ in rows); never = sum(x for x, _, _ in rows)
print(f"{frames} frames; named data {named} words; never read {never}")
for x, w, n in rows[:45]: print(f"  {n:22s} {x:5d} of {w:5d} never read")
json.dump({"frames": frames, "never": [[n, x, w] for x, w, n in rows if x]}, open(out, "w"), indent=0)
