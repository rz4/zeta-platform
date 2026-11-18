"""asm.py -- the .ZOL assembler. Text in, cart out. The whole grammar:

    ; comment                    anywhere
    .const NAME value            name a number (usable in any argument)
    .data ADDR v0 v1 ...         boot-time DMEM initialization
    .cram OFF  v0 v1 ...         the CRAM segment: content the cart pages
                                 in with the mover (see spec.DMA_*)
    .sd SLOT OFF v0 v1 ...       a data slot's file: content the cart
                                 pages in from the CARD (see spec.SD_*).
                                 This is the only section that does NOT
                                 ride in the .zbin -- it is a separate
                                 file on the SD, which is the point.
    label:                       jump target
    op [arg]                     one instruction from spec.OPS

Arguments are decimal, 0x hex, a .const name, or a label. A cart is JSON:
{"name", "imem", "dmem", "cram"} -- readable with your eyes, loadable by
both the virtual machine and the silicon boot ROM generator.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import spec


class AsmError(SystemExit):
    def __init__(self, path, line_no, msg):
        super().__init__(f"{path}:{line_no}: {msg}")


def assemble(path: str | Path) -> dict:
    path = Path(path)
    consts: dict[str, int] = {}
    labels: dict[str, int] = {}
    dmem: dict[int, int] = {}
    cram: dict[int, int] = {}
    sd: dict[int, dict[int, int]] = {}
    prog: list[tuple[int, str, str | None]] = []  # (line_no, op, arg)

    def value(tok: str, line_no: int) -> int:
        if tok in consts:
            return consts[tok]
        try:
            return int(tok, 0)
        except ValueError:
            raise AsmError(path, line_no, f"not a number or .const: {tok!r}")

    # pass 1: collect labels at instruction addresses
    for line_no, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        tok = line.split()
        if tok[0] == ".const":
            consts[tok[1]] = value(tok[2], line_no)
        elif tok[0] == ".data":
            addr = value(tok[1], line_no)
            for i, t in enumerate(tok[2:]):
                dmem[addr + i] = spec.s32(value(t, line_no)) & spec.WORD_MASK
        elif tok[0] == ".cram":
            off = value(tok[1], line_no)
            for i, t in enumerate(tok[2:]):
                if not 0 <= off + i < spec.CRAM_WORDS:
                    raise AsmError(path, line_no,
                                   f"cram offset {off + i} out of range")
                cram[off + i] = spec.s32(value(t, line_no)) & spec.WORD_MASK
        elif tok[0] == ".sd":
            slot = value(tok[1], line_no)
            off = value(tok[2], line_no)
            if slot < 0:
                raise AsmError(path, line_no, f"bad slot {slot}")
            img = sd.setdefault(slot, {})
            for i, t in enumerate(tok[3:]):
                img[off + i] = spec.s32(value(t, line_no)) & spec.WORD_MASK
        elif tok[0].endswith(":"):
            labels[tok[0][:-1]] = len(prog)
        else:
            if tok[0] not in spec.OPS:
                raise AsmError(path, line_no, f"unknown op {tok[0]!r}")
            prog.append((line_no, tok[0], tok[1] if len(tok) > 1 else None))

    # pass 2: encode
    imem = []
    for line_no, op, arg in prog:
        code, takes_imm = spec.OPS[op]
        imm = 0
        if takes_imm:
            if arg is None:
                raise AsmError(path, line_no, f"{op} needs an argument")
            imm = labels[arg] if arg in labels else value(arg, line_no)
            # 24 bits, signed or raw: 0x800000..0xFFFFFF encodes fine but
            # arrives sign-extended (harmless for colors, which use bits 23:0)
            if not -(1 << 23) <= imm < (1 << 24):
                raise AsmError(path, line_no, f"immediate {imm} exceeds 24 bits")
        elif arg is not None:
            raise AsmError(path, line_no, f"{op} takes no argument")
        imem.append((code << 24) | (imm & 0xFFFFFF))

    if len(imem) > spec.IMEM_WORDS:
        raise AsmError(path, 0, f"cart is {len(imem)} words; IMEM holds {spec.IMEM_WORDS}")
    return {"name": path.stem, "imem": imem,
            "dmem": {str(a): v for a, v in sorted(dmem.items())},
            "cram": {str(a): v for a, v in sorted(cram.items())},
            # each slot as a dense list: the card serves zeros past the end
            "sd": {str(k): [img.get(i, 0) for i in range(max(img) + 1)]
                   for k, img in sorted(sd.items()) if img}}


def build(src: str | Path, out: str | Path | None = None) -> Path:
    src = Path(src)
    out = Path(out) if out else src.with_suffix(".zc")
    cart = assemble(src)
    out.write_text(json.dumps(cart, indent=1))
    print(f"built {out}  ({len(cart['imem'])}/{spec.IMEM_WORDS} words)")
    return out
