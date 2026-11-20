"""THE TAPE: a session as the pad words that drove it (docs/PLATFORM.md).

Every delay in the machine is legislated, so a cart, the save file it
started with and one pad word a frame reconstruct a session exactly. One
small file then serves three people: the player (ghosts, shared runs),
the developer (a bug that reproduces every time) and the hardware
designer (costs measured on real play instead of scripted routes).

TWO FORMS, one content.

  TEXT   witness.read_tape's: one pad word a line, line i driving frame i,
         '#' comments, an optional  @start N. What people read and edit.

  ZTP0   what the Pocket's recorder leaves in its memory, and what the
         OS writes to the card when the core exits. Little-endian 32-bit
         words:

             0   'ZTP0'
             1   LOADER_BUILD      the machine that recorded it
             2   the cart's sum    every word the loader delivered, added
                                   mod 2^32 -- which cart this was
             3   0                 reserved
             4+  runs              frames << 16 | pad -- "this pad word,
                                   held this many frames", 1..65,535

         A run of zero frames ends the tape, and so does the end of the
         file: the recorder's memory starts as zeros. THE RUN BEING HELD
         IS WRITTEN EVERY FRAME, in place, so the tape is whole at every
         instant -- there is no "finish" step for a power switch to beat.

`encode` is the reference recorder: the silicon's image must equal it,
word for word, for the same pads.
"""
from __future__ import annotations

import struct
from pathlib import Path

from . import spec

MAGIC = 0x5A545030              # 'ZTP0'
HEADER_WORDS = 4
RUN_MAX = 0xFFFF
PAD_MASK = 0xFFFF
#: the recorder's memory: the Pocket's SRAM, 128K x 16 bits
WORDS = (1 << 17) * 16 // 32


def cart_sum(cart: dict) -> int:
    """The sum of every word of the cart as deploy.write_zbin lays it out
    (IMEM, DMEM, then the segment) -- what the loader can add up as the
    words go by. Padding is zeros and adds nothing."""
    total = sum(int(w) for w in cart["imem"])
    total += sum(int(v) & spec.WORD_MASK for v in cart.get("dmem", {}).values())
    total += sum(int(v) & spec.WORD_MASK for v in cart.get("cram", {}).values())
    return total & 0xFFFFFFFF


def runs(pads) -> list[tuple[int, int]]:
    """Pad words as (frames, pad) runs, none longer than RUN_MAX."""
    out: list[list[int]] = []
    for p in pads:
        p &= PAD_MASK
        if out and out[-1][1] == p and out[-1][0] < RUN_MAX:
            out[-1][0] += 1
        else:
            out.append([1, p])
    return [(n, p) for n, p in out]


def encode(pads, cart_sum_: int = 0, build: int | None = None) -> bytes:
    """The ZTP0 image the recorder holds after these pads."""
    words = [MAGIC, spec.LOADER_BUILD if build is None else build,
             cart_sum_ & 0xFFFFFFFF, 0]
    words += [(n << 16) | p for n, p in runs(pads)]
    if len(words) > WORDS:
        raise ValueError(f"{len(words) - HEADER_WORDS} runs do not fit the "
                         f"recorder's {WORDS - HEADER_WORDS}")
    return struct.pack(f"<{len(words)}I", *words)


def decode(blob: bytes) -> tuple[dict, list[int]]:
    """-> ({'build', 'cart_sum', 'runs'}, pad words, one a frame)."""
    n = len(blob) // 4
    if n < HEADER_WORDS:
        raise ValueError("too short to be a tape")
    words = struct.unpack(f"<{n}I", blob[:4 * n])
    if words[0] != MAGIC:
        raise ValueError(f"not a ZTP0 tape (magic {words[0]:#010x})")
    pads: list[int] = []
    count = 0
    for w in words[HEADER_WORDS:]:
        frames = w >> 16
        if frames == 0:
            break
        pads += [w & PAD_MASK] * frames
        count += 1
    return {"build": words[1], "cart_sum": words[2], "runs": count}, pads


def read(path) -> list[int]:
    """Pad words from either form: a ZTP0 file, or the text tape."""
    blob = Path(path).read_bytes()
    if len(blob) >= 4 and struct.unpack("<I", blob[:4])[0] == MAGIC:
        return decode(blob)[1]
    from . import witness
    start, pads = witness.read_tape(path)
    if start:
        raise ValueError(f"{path} starts at frame {start}: a replay needs "
                         f"the session from its first frame")
    return pads


def write_text(pads, path, note: str = "") -> None:
    """The text form, with runs commented so a person can find their way."""
    lines = [f"# {note}"] if note else []
    f = 0
    for n, p in runs(pads):
        lines.append(f"# frame {f}: {p:#06x} for {n}")
        lines += [f"{p:#06x}"] * n
        f += n
    Path(path).write_text("\n".join(lines) + "\n")


def check(header: dict, cart: dict) -> str | None:
    """Why this tape should not be trusted against this cart, or None."""
    if header["build"] != spec.LOADER_BUILD:
        return (f"recorded on build {header['build']}, and this is "
                f"{spec.LOADER_BUILD}")
    want = cart_sum(cart)
    if header["cart_sum"] not in (0, want):
        return (f"recorded against a cart summing {header['cart_sum']:#010x}; "
                f"this one sums {want:#010x}")
    return None
