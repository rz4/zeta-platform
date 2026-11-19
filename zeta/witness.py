# THE SCREENSHOT GATE (SEAMS 4): the witnessing ritual as a command.
#
# The Pocket's Menu+Start captures the panel at 320x288 -- that is
# panel(), compositor and grade included. Given that capture and the
# pad words that drove the session, machine 1 either reproduces the
# Pocket's pixels bit-for-bit or convicts the hardware. MYTHOS counts
# thirty-four witnessings by eye and phone photo; this makes the
# thirty-fifth a gate that can fail.
#
# THE TAPE (ALIEN F2), legislated here because the witness needs it:
# a text file, one pad word per line, line i driving frame i, read as
# int(line, 0) so decimal and 0x both work. A missing line is pad 0;
# blank lines and '#' comments are skipped. A cart that seeds from
# REG_FRAME must be replayed from the same launch frame (SEAMS 2), so
# the tape's first directive may be  @start N  to begin at frame N.

from pathlib import Path

import numpy as np

from . import cabinet, gpu, spec


def read_tape(path) -> tuple[int, list[int]]:
    """-> (start_frame, pad words). See the format note above."""
    start, pads = 0, []
    for raw in Path(path).read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("@start"):
            start = int(line.split()[1], 0)
            continue
        pads.append(int(line, 0) & 0xFFF)
    return start, pads


def read_shot(path) -> np.ndarray:
    """A Pocket capture as (H, W, 3) uint8. PPM is read directly; other
    formats go through pygame. An integer-scaled capture (the panel is
    1600x1440, five of ours) is accepted only if every block is uniform
    -- a resampled image is not a witness."""
    p = Path(path)
    if p.suffix.lower() == ".ppm":
        with open(p, "rb") as f:
            magic = f.readline().split()
            if magic[0] != b"P6":
                raise SystemExit(f"{path}: not a binary PPM")
            # header fields may share the first line or not
            fields = magic[1:]
            while len(fields) < 3:
                fields += f.readline().split()
            w, h = int(fields[0]), int(fields[1])
            img = np.frombuffer(f.read(w * h * 3), dtype=np.uint8)
            img = img.reshape(h, w, 3)
    else:
        import pygame
        surf = pygame.image.load(str(p))
        img = np.transpose(pygame.surfarray.array3d(surf), (1, 0, 2))
    h, w = img.shape[:2]
    if (w, h) == (spec.W, spec.H):
        return img
    if w % spec.W == 0 and h % spec.H == 0 and w // spec.W == h // spec.H:
        k = w // spec.W
        blocks = img.reshape(spec.H, k, spec.W, k, 3).swapaxes(1, 2)
        first = blocks[:, :, 0, 0, :]
        if not (blocks == first[:, :, None, None, :]).all():
            raise SystemExit(
                f"{path}: {w}x{h} is {k}x our panel but its blocks are "
                f"not uniform -- a filtered or resampled image cannot "
                f"witness anything. Capture with Menu+Start, or scale "
                f"with nearest-neighbour only.")
        return first.copy()
    raise SystemExit(
        f"{path}: {w}x{h} is not {spec.W}x{spec.H} or an integer "
        f"multiple of it")


def witness(cart: dict, shot: np.ndarray, frames: int,
            tape: tuple[int, list[int]] | None, exact_frame: int | None,
            save_diff: str | None = None) -> int:
    """Replay machine 1 and hold the capture against every panel (or
    one, with exact_frame). 0 = some frame matched to the pixel."""
    start, pads = tape if tape else (0, [])
    m = cabinet.VirtualMachine(cart)
    best = (None, 1 << 60, None)                      # frame, diff, panel
    lo = exact_frame if exact_frame is not None else 0
    hi = exact_frame if exact_frame is not None else frames - 1
    for f in range(hi + 1):
        pad = pads[f - start] if 0 <= f - start < len(pads) else 0
        m.frame(pad)
        if f < lo:
            continue
        panel = np.asarray(m.panel(), dtype=np.uint8)
        diff = int((panel != shot).any(axis=-1).sum())
        if diff == 0:
            print(f"WITNESS PASS: frame {f} matches the capture, "
                  f"all {spec.W * spec.H} pixels")
            return 0
        if diff < best[1]:
            best = (f, diff, panel)
    f, diff, panel = best
    ys, xs = np.nonzero((panel != shot).any(axis=-1))
    print(f"WITNESS FAIL: closest is frame {f}, {diff} pixels differ "
          f"(first at x={xs[0]}, y={ys[0]}: "
          f"law {tuple(int(v) for v in panel[ys[0], xs[0]])} vs "
          f"glass {tuple(int(v) for v in shot[ys[0], xs[0]])})")
    if save_diff:
        out = panel.copy()
        mask = (panel != shot).any(axis=-1)
        out[mask] = (255, 0, 255)
        gpu.write_ppm(out, save_diff)
        print(f"differing pixels marked magenta in {save_diff}")
    return 1
