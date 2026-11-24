import sys; sys.path.insert(0, "experiments/park"); sys.path.insert(0, ".")
import numpy as np
from PIL import Image, ImageDraw
import bot
from zeta import gpu, spec
ONE = 65536
gpu.render = lambda *a, **k: np.zeros((spec.H, spec.W, 3), np.uint8)
g = bot.Park(bot.ROOT / "build/layer13/tnd.zol")
for _ in range(5): g.step(0)
HX = g.cell("px") / ONE - 8.5; HZ = g.cell("pz") / ONE
rows = g.rows()
print(sorted(rows[0].keys()))
K = 14; W, H = 64 * K + 40, 32 * K + 40
im = Image.new("RGB", (W, H), (236, 236, 230)); dr = ImageDraw.Draw(im)
def P(u, v): return 20 + (u + 32) * K, 20 + (16 - v) * K
dr.rectangle([P(-32, 16), P(32, -16)], outline=(60, 60, 60), width=2)
dr.rectangle([P(-6.5, 5.5), P(6.5, -5.5)], outline=(170, 170, 170))
cols = {0: (60, 190, 110), 1: (214, 58, 54), 2: (236, 196, 64), 3: (40, 40, 44), 4: (60, 110, 214)}
for r in rows:
    u0, u1 = r["z0"] - HZ, r["z1"] - HZ; v0, v1 = HX - r["x1"], HX - r["x0"]
    if r["motion"] == 3:
        cu, cv = P((u0 + u1) / 2, (v0 + v1) / 2); dr.ellipse([cu - 4, cv - 4, cu + 4, cv + 4], fill=(255, 214, 40), outline=(120, 90, 0))
        continue
    dr.rectangle([P(u0, v1), P(u1, v0)], fill=cols.get(r["kind"], (128, 128, 128)), outline=(20, 20, 20))
    cu, cv = P((u0 + u1) / 2, (v0 + v1) / 2)
    if u1 - u0 > 1.2 and v1 - v0 > 1.0: dr.text((cu - 9, cv - 5), f"{r['top']:.1f}", fill=(255, 255, 255) if r["kind"] in (1, 3, 4) else (0, 0, 0))
    if r["motion"] == 1: dr.line([P(u1, (v0 + v1) / 2), P(u1 + 8, (v0 + v1) / 2)], fill=(150, 110, 0), width=3)
for k in range(7):
    a = g.syms[f"e{k}_pos"]; u, v = bot.s32(g.d[a + 1]) / ONE - HZ, HX - bot.s32(g.d[a]) / ONE
    cu, cv = P(u, v); dr.ellipse([cu - 5, cv - 5, cu + 5, cv + 5], fill=(200, 120, 90), outline=(0, 0, 0)); dr.text((cu + 6, cv - 6), "EC1234D"[k], fill=(0, 0, 0))
cu, cv = P(0, -8.5); dr.polygon([(cu, cv - 7), (cu - 5, cv + 5), (cu + 5, cv + 5)], fill=(0, 0, 0))
im.save(sys.argv[1]); print(len(rows), "rows")
