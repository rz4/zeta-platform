#!/usr/bin/env python3
"""gen_pickfloor.py -- writes carts/witness/pickfloor.zol: the pick register, aimed
at a triangle that WAITED.

pick.zol starts its crosshair on the bunny. The bunny's faces are small
and arrive one at a time, so the rasterizer takes each the moment it is
offered -- and a triangle's id, read at that moment, is the same whether
it travelled WITH the triangle or was read off the sequencer's counter.

Frontier B2 put a queue between the sequencer and the rasterizer, and the
id has to ride in it: a triangle submitted while the rasterizer is busy
is drawn later, when the sequencer's counter has moved on. The mutant
that reads the counter live passed pick, watched, vessel and banked.

The floor is what waits. It is the first mesh in the list, so every band
offers its triangles while the rasterizer is still CLEARING, and they sit
in the queue behind the clear. This cart is pick.zol with the crosshair
started on the floor at (160, 250): the live-counter mutant fails it at
once, and so would any future handoff that forgets whose id it carries.

Derived from the committed pick.zol (two data words differ), so the two
cannot drift apart.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
WX, WY = 23, 24                 # gen_pick.py's crosshair cells
AT = (160, 250)                 # on the floor, below the bunny


def main():
    src = (HERE / "pick.zol").read_text()
    for cell, was, now in ((WX, 160, AT[0]), (WY, 140, AT[1])):
        line = f".data {cell} {was}\n"
        assert src.count(line) == 1, line
        src = src.replace(line, f".data {cell} {now}\n")
    head = "; pick.zol -- the pick register demo (see gen_pick.py)\n"
    assert src.startswith(head)
    src = ("; pickfloor.zol -- pick.zol aimed at the floor (see "
           "gen_pickfloor.py)\n") + src[len(head):]
    src = src.replace("; GENERATED -- edit gen_pick.py, not this.",
                      "; GENERATED -- edit gen_pickfloor.py, not this.")
    (HERE / "pickfloor.zol").write_text(src)
    print(f"wrote pickfloor.zol: pick.zol with the crosshair at {AT}")


if __name__ == "__main__":
    main()
