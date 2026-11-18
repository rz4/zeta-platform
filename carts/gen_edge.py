#!/usr/bin/env python3
"""gen_edge.py -- writes carts/edge.zol: the right-edge bleed instrument.

Draws NOTHING but a one-pixel-wide column in eight distinct color
bands, and lets the pad place it:

    boot / B : column at x = 319 (the suspect)
    A        : column at x = 318 (control: one left)
    UP       : column at x = 316 (control: burst-tail distance)
    DOWN     : column at x = 0   (control: does the LEFT edge bleed
                                  anywhere?)

If the bleed is the scanout keeper (pixel (y,0) showing (y-1,319)),
the left edge shows the bands shifted DOWN one row, only in the 319
position. If it shows them at the same row, it is a same-row wrap. If
318/316 also bleed, it is span-tail behavior, not row-end. Colors name
rows: top band red, then orange, yellow, green, cyan, blue, magenta,
white.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zeta import spec                          # noqa: E402

BANDS = [0xE02020, 0xE08020, 0xE0E020, 0x20C020,
         0x20C0C0, 0x2040E0, 0xC020C0, 0xE0E0E0]
X_CELL = 16
DL = spec.DL_BASE


def main():
    P = [".const PAD 1", f".const X {X_CELL}",
         f".data {X_CELL} 319", ""]
    P += ["; pick the column with the pad",
          "load PAD", "push 16", "and", "jz n_a",
          "push 318", "store X", "n_a:",
          "load PAD", "push 32", "and", "jz n_b",
          "push 319", "store X", "n_b:",
          "load PAD", "push 1", "and", "jz n_u",
          "push 316", "store X", "n_u:",
          "load PAD", "push 2", "and", "jz n_d",
          "push 0", "store X", "n_d:"]
    # eight band quads, two triangles each: x..x+1, y0..y1
    t = 0
    for i, col in enumerate(BANDS):
        y0, y1 = i * 36, (i + 1) * 36
        a = DL + 1 + t * 7
        P += ["load X", f"store {a}", f"push {y0}", f"store {a+1}",
              "load X", "push 1", "add", f"store {a+2}",
              f"push {y0}", f"store {a+3}",
              "load X", f"store {a+4}", f"push {y1}", f"store {a+5}",
              f"push {col}", f"store {a+6}"]
        t += 1
        a = DL + 1 + t * 7
        P += ["load X", "push 1", "add", f"store {a}",
              f"push {y0}", f"store {a+1}",
              "load X", "push 1", "add", f"store {a+2}",
              f"push {y1}", f"store {a+3}",
              "load X", f"store {a+4}", f"push {y1}", f"store {a+5}",
              f"push {col}", f"store {a+6}"]
        t += 1
    P += [f"push {t}", f"store {DL}", "halt"]
    head = ["; edge.zol -- right-edge bleed instrument (see gen_edge.py)",
            "; GENERATED -- edit gen_edge.py, not this."]
    (HERE / "edge.zol").write_text("\n".join(head + P))
    print(f"wrote edge.zol: {t} triangles, 8 bands")


if __name__ == "__main__":
    main()
