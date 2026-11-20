"""deploy.py -- the last rung: an openFPGA core folder for a real Pocket.

`zeta deploy CART` refuses to ship anything unproven: it re-runs the cross
and the glass check first. Then it writes everything the Pocket needs onto
an SD-card tree:

    build/pocket/
      Platforms/zeta.json
      Cores/CleanRoom.Zeta/
        core.json video.json input.json data.json audio.json variants.json
        zeta.rbf_r                     (if a Quartus bitstream exists)

plus pocket/gen/cart_*.hex (the cart the bitstream bakes into BRAM via
ZETA_BAKE_CART) and honest instructions for the one step this machine
can't verify: the Quartus build against Analogue's core template.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import spec
from .silicon import ROOT, SIL, write_cart_hex

AUTHOR = "CleanRoom"
CORENAME = "Zeta"
VERSION = f"0.{spec.LOADER_BUILD}.0"   # the build the Pocket's core menu
                                       # shows: which bitstream is on the
                                       # card, readable without booting

METADATA = {
    "platform_ids": ["zeta"],
    "shortname": CORENAME,
    "description": "The Zeta fantasy console: .ZOL carts, cross-proven "
                   "bit-equal to the reference machine.",
    "author": AUTHOR,
    "url": "",
    "version": VERSION,
    "date_release": "2026-08-18",
}

MANIFESTS = {
    "core.json": {"core": {
        "magic": "APF_VER_1",
        "metadata": METADATA,
        "framework": {
            "target_product": "Analogue Pocket",
            "version_required": "1.1",
            "sleep_supported": False,
            "dock": {"supported": True, "analog_output": False},
            "hardware": {"link_port": False, "cartridge_adapter": -1},
        },
        "cores": [{"name": "default", "id": 0, "filename": "zeta.rbf_r"}],
    }},
    "video.json": {"video": {
        "magic": "APF_VER_1",
        "scaler_modes": [{"width": spec.W, "height": spec.H,
                          "aspect_w": 10, "aspect_h": 9,
                          "rotation": 0, "mirror": 0}],
    }},
    "audio.json": {"audio": {"magic": "APF_VER_1"}},
    # the cart slot: a fixed-name 32 KB image the OS streams over the
    # bridge at boot (cart_loader.v decodes 0x10000000 and 0x0). The .zbin
    # layout is 4096 IMEM words then 4096 DMEM words, little-endian --
    # written by write_zbin() below, replayed by the loader, proven by
    # deploy gate 3. required:false so a missing file still boots the
    # ZETA_BAKE_CART fallback (the zeta tree learned required:true can
    # stop a core loading outright).
    "data.json": {"data": {"magic": "APF_VER_1", "data_slots": [
        {"name": "Cart", "id": 1, "required": False, "parameters": "0x0",
         "filename": "cart.zbin", "address": "0x10000000"},
        # THE CARD (spec.SD_*): content the cart streams while it runs,
        # never part of the .zbin. card_apf.v claims bridge 0x2xxxxxxx for
        # it and accepts window writes ONLY while a request of ours is in
        # flight, so it does not matter whether APF also preloads this
        # slot at boot -- unasked-for words are ignored by construction.
        {"name": "Card", "id": 2, "required": False, "parameters": "0x0",
         "filename": "card.bin", "address": "0x20000000"},
        # THE TAPE (zeta/tape.py, pocket/zeta_tape.v): the session's pad
        # words. NONVOLATILE, so the OS itself reads the recorder's memory
        # at 0x30000000 and writes the file when the core exits -- the
        # recorder never asks for the card, which the game owns. The OS
        # also WRITES the old file at us on the way in; nothing claims
        # those writes. Staged blank at its full size (TAPE_FILE below),
        # because a save slot keeps the size it was loaded with.
        {"name": "Tape", "id": 3, "required": False, "parameters": "0x0",
         "nonvolatile": True, "filename": "tape.ztp",
         "address": "0x30000000", "size_maximum": "0x10000"}]}},
    # input/interact/variants: the minimal forms, byte-shape-matched to the
    # zeta3 core that actually booted on a real Pocket (archive/zeta3/dist)
    "input.json": {"input": {"magic": "APF_VER_1", "controllers": []}},
    "interact.json": {"interact": {"magic": "APF_VER_1",
                                   "variables": [], "messages": []}},
    "variants.json": {"variants": {"magic": "APF_VER_1", "variant_list": []}},
}

PLATFORM = {"platform": {
    "category": "Fantasy",
    "name": "Zeta",
    "year": 2026,
    "manufacturer": AUTHOR,
}}


def reverse_bits(data: bytes) -> bytes:
    """Quartus .rbf -> Pocket .rbf_r: every byte bit-reversed."""
    table = bytes(int(f"{b:08b}"[::-1], 2) for b in range(256))
    return data.translate(table)


def check_seam() -> None:
    """The boot-16 AND build-26 lesson, as a gate.

    A cart word crosses five modules on its way into memory, and every
    one of them declares the address port by hand. Verilog truncates a
    narrow declaration silently, and synthesis and Verilator disagree
    about over-wide drives, so a too-narrow port in the middle can pass
    every simulation and still fold memory on real hardware -- which is
    exactly what zeta_glass's 12-bit boot_addr did for ten bitstreams,
    hiding behind the identical bug in core_top that boot 16 already
    taught us to look for.

    So do not check a hand-listed seam. Scan EVERY declaration of the
    boot-path signals anywhere in the tree and demand they all agree.
    A new module on the path is then covered the day it is written."""
    import re

    sigs = {"boot_addr": None, "boot_data": None}
    decl = re.compile(
        r"^\s*(?:input|output|inout)?\s*(?:wire|reg)?\s*"
        r"\[(\d+):0\]\s*([A-Za-z_]\w*)\s*[,;)]", re.M)
    found: dict[str, dict[str, int]] = {k: {} for k in sigs}
    for path in sorted(ROOT.glob("**/*.v")):
        if "template/apf" in str(path) or "output_files" in str(path):
            continue                       # vendor code, not our path
        for m in decl.finditer(path.read_text()):
            hi, name = int(m.group(1)), m.group(2)
            if name in found:
                found[name][str(path.relative_to(ROOT))] = hi + 1
    # core_top joins them under its own names: check those too
    core = ROOT / "pocket/template/core/core_top.v"
    for m in decl.finditer(core.read_text()):
        hi, name = int(m.group(1)), m.group(2)
        if name == "cl_addr":
            found["boot_addr"][str(core.relative_to(ROOT)) + ":cl_addr"] = hi + 1
        if name == "cl_data":
            found["boot_data"][str(core.relative_to(ROOT)) + ":cl_data"] = hi + 1

    for sig, places in found.items():
        widths = set(places.values())
        if not places:
            raise SystemExit(f"seam check: no declaration of {sig} found")
        if len(widths) != 1:
            detail = "  ".join(f"{p}={w}b" for p, w in sorted(places.items()))
            raise SystemExit(
                f"SEAM MISMATCH on {sig}: {detail}\n"
                "A narrow port anywhere on the boot path folds memory on "
                "hardware while every simulation still passes (build 26).")
    print(f"seam check: boot path agrees across {len(found['boot_addr'])} "
          f"declarations")
    check_dangling()


# --------------------------------------------------------------------------
# the other half of the seam: a port that is DECLARED and never CONNECTED
# --------------------------------------------------------------------------
BOOT_PORTS = ("boot_we", "boot_kind", "boot_addr", "boot_data", "boot_done")


def _balanced(text: str, i: int) -> tuple[str, int]:
    """The parenthesised group starting at text[i] == '(', and its end."""
    depth, j = 0, i
    while j < len(text):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j
        j += 1
    return "", len(text)


def _sources() -> list[Path]:
    return [p for p in sorted(ROOT.glob("**/*.v"))
            if "template/apf" not in str(p) and "output_files" not in str(p)
            and "/gen/" not in str(p)]


def check_dangling() -> None:
    """A boot-path INPUT that is declared and left unconnected reads as
    zero, in Verilator and in Quartus alike, and says nothing.

    That is how hall.zol failed glass by exactly 55 pixels for as long as
    a backdrop cart existed. glass_sim.v wrapped zeta_glass and simply
    omitted `.boot_done`. boot_done is the loader's release verdict: the
    boot path banks CRAM words 63 at a time, a FULL bank flushes itself,
    and a PARTIAL one waits for a quiet line AND that signal. Held at
    zero it never came, so every cart's last N-mod-63 segment words
    stayed in the accumulator and read back as zeros -- 55 words for
    hall, 55 black pixels at the end of row 287. core_top.v drives it
    from cart_ready and zeta_sim.v ties it high, so the hardware was
    always right and cross could never see it. Nine hypotheses died
    against the machine before anyone audited the instrument.

    check_seam above proves the declarations AGREE. This proves they are
    WIRED. Same bug class, other half."""
    import re

    src = {p: p.read_text() for p in _sources()}
    mod_head = re.compile(r"\bmodule\s+(\w+)")
    inp = re.compile(r"\binput\s+(?:wire|reg)?\s*(?:\[[^\]]*\]\s*)?(\w+)")

    # which modules take which boot-path signals as inputs
    wants: dict[str, set[str]] = {}
    for text in src.values():
        for m in mod_head.finditer(text):
            k = text.find("(", m.end())
            if k < 0:
                continue
            ports, end = _balanced(text, k)
            if ports.lstrip().startswith("*") or "parameter" in ports[:40]:
                ports, _ = _balanced(text, text.find("(", end))   # skip #()
            need = {s for s in inp.findall(ports) if s in BOOT_PORTS}
            if need:
                wants.setdefault(m.group(1), set()).update(need)

    bad = []
    for name, need in sorted(wants.items()):
        inst = re.compile(r"\b" + name + r"\s+(?:#\s*\([^;]*?\)\s*)?(\w+)\s*\(")
        for path, text in src.items():
            for m in inst.finditer(text):
                k = text.index("(", m.end() - 1)
                conn, _ = _balanced(text, k)
                miss = sorted(s for s in need if f".{s}" not in conn)
                if miss:
                    where = (path.relative_to(ROOT)
                             if path.is_relative_to(ROOT) else path)
                    bad.append(f"{where}: {name} {m.group(1)} leaves "
                               f"{', '.join(miss)} dangling")
    if bad:
        raise SystemExit(
            "DANGLING BOOT PORT:\n  " + "\n  ".join(bad)
            + "\nAn unconnected input reads as zero and reports nothing. "
              "boot_done held low strands the loader's last partial bank "
              "of CRAM words (the hall.zol 55-pixel tail).")
    print(f"seam check: every boot-path input wired across "
          f"{len(wants)} modules")


# --------------------------------------------------------------------------
# THE BUILD NUMBER CANNOT BE FORGOTTEN AGAIN (spec.LOADER_BUILD's own lament:
# 93 shipped on five bitstreams; 92 is skipped to hide nothing). The stamp
# beside the bitstream records which sources it was compiled from AND under
# which build number. If the sources have moved and the number has not,
# packaging is refused before Quartus is even asked.
# --------------------------------------------------------------------------
def read_stamp(stamp: Path) -> tuple[str, int | None]:
    """(source hash, build) from the stamp; a pre-build-100 stamp carries
    no number and returns None for it."""
    if not stamp.exists():
        return "", None
    parts = stamp.read_text().split()
    if not parts:
        return "", None
    return parts[0], (int(parts[1]) if len(parts) > 1 else None)


def check_build_bump(have: str, have_build: int | None, want: str,
                     build: int) -> None:
    """Refuse RTL that changed since the last packaged bitstream without
    spec.LOADER_BUILD moving with it."""
    if have and have_build is not None and have != want \
            and have_build == build:
        raise SystemExit(
            f"REFUSED: the RTL has changed since build {have_build} was "
            f"packaged and spec.LOADER_BUILD still says {build}. A cart on "
            f"glass could not tell this bitstream from that one. Bump "
            f"LOADER_BUILD (and say what changed beside it) before "
            f"deploying.")


def write_zbin(cart: dict, path: Path) -> None:
    """The cart as the slot file: IMEM, then DMEM, then the CRAM segment
    if the cart has one -- 20480 resident words (80 KB) plus however many
    words of content the cart pages in with the mover. The tail is
    trimmed to the last word the cart actually uses, so a cart with no
    segment is byte-identical to what it was before capacity phase 2."""
    import struct

    imem = list(cart["imem"]) + [0] * (spec.IMEM_WORDS - len(cart["imem"]))
    dmem = [0] * spec.DMEM_WORDS
    for a, v in cart.get("dmem", {}).items():
        dmem[int(a)] = v & spec.WORD_MASK
    seg = cart.get("cram", {})
    cram = [0] * ((max(int(a) for a in seg) + 1) if seg else 0)
    for a, v in seg.items():
        cram[int(a)] = v & spec.WORD_MASK
    words = imem + dmem + cram
    path.write_bytes(struct.pack(f"<{len(words)}I", *words))


def read_zbin(path: Path, cards: Path | None = None) -> dict:
    """The slot file back as a cart: what is on the card IS what ran, so
    a tape is replayed against these bytes and not against a rebuild that
    might differ. `cards` is a folder of card*.bin (the save the session
    started with); None leaves the card blank."""
    import struct

    blob = Path(path).read_bytes()
    n = len(blob) // 4
    w = struct.unpack(f"<{n}I", blob[:4 * n])
    i, d = spec.IMEM_WORDS, spec.DMEM_WORDS
    cart = {"name": Path(path).stem, "imem": list(w[:i]),
            "dmem": {a: v for a, v in enumerate(w[i:i + d]) if v},
            "cram": {a: v for a, v in enumerate(w[i + d:]) if v},
            "sd": card_images(cards) if cards else {}}
    return cart


def card_slot(name: str) -> int | None:
    """card.bin is slot 2 (the manifest's Card), cardN.bin is slot N."""
    stem = Path(name).stem
    if Path(name).suffix != ".bin" or not stem.startswith("card"):
        return None
    tail = stem[4:]
    return 2 if tail == "" else int(tail) if tail.isdigit() else None


def card_images(where: Path) -> dict:
    """{slot: words} from a card file, or from every card*.bin in a folder."""
    import struct

    where = Path(where)
    files = [where] if where.is_file() else sorted(where.glob("card*.bin"))
    out = {}
    for f in files:
        slot = card_slot(f.name) if where.is_dir() else (card_slot(f.name) or 2)
        if slot is None:
            continue
        blob = f.read_bytes()
        out[slot] = list(struct.unpack(f"<{len(blob) // 4}I", blob[:len(blob) // 4 * 4]))
    return out


# ---- THE POCKET'S OWN MENU (docs/PLATFORM.md, phase 1) ----------------------
# The core loaded ONE fixed file, cart.zbin, and every game lived inside
# it behind an in-cart launcher. A game is a file now, and the Pocket's
# own browser chooses it:
#
#   required, no filename   the OS opens its browser in Assets/zeta/common,
#                           filtered to .zbin, when the core is launched
#   bit 0   user-reloadable: "load another" from the core's own menu
#   bit 8   ...by UNLOADING the core and restarting it, bitstream and all,
#           with the new file -- which is exactly a cold boot. cart_loader
#           holds the console in reset until a whole cart has arrived and
#           then latches, a path paid for on glass many times over; a
#           reload that is a cold boot asks nothing new of it.
#
# Nothing in the bitstream changes: this is the manifest, and how the card
# is laid out. The card slot is unchanged (one shared card.bin) until the
# per-game save file is proved on glass.
MENU_SLOT = {"name": "Game", "id": 1, "required": True,
             "parameters": "0x101", "extensions": ["zbin"],
             "address": "0x10000000"}


#: where the games and the card files live on the SD
ASSETS = "Assets/zeta/common"
#: where the OS keeps a nonvolatile slot's file, and how big the tape is
TAPE_FILE = "Saves/zeta/common/tape.ztp"
TAPE_BYTES = 0x10000


def stage_tape(out: Path) -> None:
    """A blank tape at full size, where the OS will look for it. A push
    never replaces one already on the card (sdcard.push): a session
    nobody has brought home yet may be on it."""
    p = out / TAPE_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(bytes(TAPE_BYTES))


def manifests(menu: bool = False) -> dict:
    """The core's definition files; with `menu`, the game is chosen in the
    Pocket's browser instead of being the fixed cart.zbin."""
    if not menu:
        return MANIFESTS
    out = json.loads(json.dumps(MANIFESTS))
    slots = out["data.json"]["data"]["data_slots"]
    assert slots[0]["filename"] == "cart.zbin"
    slots[0] = dict(MENU_SLOT)
    return out


def with_film(cart_path: Path, work: Path) -> Path:
    """The cart at `cart_path` behind the boot film: the machine's face,
    its logo, and then the game -- one cart, the film handing the machine
    over exactly as it always handed it to the shelf (carts/system/
    gen_face.py, FACE_LAUNCH). Needs the film's own source media, which
    is third-party and local."""
    import os
    from . import carts
    gen = carts.gen("face")
    out = work / f"{Path(cart_path).stem}.film.zol"
    env = dict(os.environ, FACE_LAUNCH=str(Path(cart_path).resolve()),
               FACE_OUT=str(out))
    r = subprocess.run([sys.executable, gen.name], cwd=gen.parent, env=env,
                       capture_output=True, text=True)
    if r.returncode or not out.is_file():
        raise SystemExit(f"the film would not take {cart_path}: "
                         f"{(r.stderr or r.stdout).strip()[-300:]}")
    return out


def stage_menu(out: Path, games: dict, core_from: Path,
               film: bool = True) -> list[Path]:
    """A card folder with one file a game. `games` is {title: cart path};
    the title is the name the Pocket's browser shows. The core -- its
    bitstream and images -- is copied from `core_from`, an existing staged
    folder, so a fit is never re-run to change what is on the card.

    With `film` (the default) every game opens on the boot film and its
    logo: the console's face is not lost by choosing the game in the
    Pocket's menu instead of on the shelf."""
    import tempfile
    from . import cabinet
    from . import silicon
    work = silicon.scratch("zeta-stage-")
    coredir = f"Cores/{AUTHOR}.{CORENAME}"
    if not (core_from / coredir / "zeta.rbf_r").is_file():
        raise SystemExit(f"{core_from} holds no staged core ({coredir}/zeta.rbf_r)")
    for sub in (coredir, "Platforms"):
        shutil.copytree(core_from / sub, out / sub, dirs_exist_ok=True)
    for name, doc in manifests(menu=True).items():
        (out / coredir / name).write_text(json.dumps(doc, indent=1))
    assets = out / "Assets/zeta/common"
    assets.mkdir(parents=True, exist_ok=True)
    for old in assets.glob("*.zbin"):            # what is staged IS the shelf
        old.unlink()
    stage_tape(out)
    written, card = [], {}
    for title, path in games.items():
        cart = cabinet.load_cart(with_film(path, work) if film else path)
        write_zbin(cart, assets / f"{title}.zbin")
        written.append(assets / f"{title}.zbin")
        for slot, img in cart.get("sd", {}).items():
            if int(slot) in card and card[int(slot)][1] != list(img):
                raise SystemExit(f"{title} and {card[int(slot)][0]} both use card "
                                 f"slot {slot}: one shared card file cannot serve both yet")
            card[int(slot)] = (title, list(img))
    for slot, (title, img) in sorted(card.items()):
        name = "card.bin" if slot == 2 else f"card{slot}.bin"
        (assets / name).write_bytes(b"".join(int(w).to_bytes(4, "little") for w in img))
    return written


def run(cart: dict, cart_name: str, out: Path | None = None) -> int:
    out = out or ROOT / "build/pocket"
    check_seam()

    # 1a. the fallback cart the bitstream bakes in (Quartus reads these)
    gen = ROOT / "pocket/gen"
    gen.mkdir(parents=True, exist_ok=True)
    write_cart_hex(cart, gen)
    # 1b. the REAL cart: the slot file the Pocket streams in at boot --
    # swapping games is now copying this one file, no Quartus involved
    assets_out = out / "Assets/zeta/common"
    assets_out.mkdir(parents=True, exist_ok=True)
    write_zbin(cart, assets_out / "cart.zbin")
    print(f"cart '{cart_name}' -> Assets/zeta/common/cart.zbin "
          f"(and baked as the bitstream's fallback)")
    # 1c. the CARD: a cart's .sd slot images become real files beside the
    # cart, which is the entire point -- this content never rides in the
    # .zbin and is not bounded by it
    for slot, img in sorted(cart.get("sd", {}).items(), key=lambda kv: int(kv[0])):
        blob = b"".join(int(w).to_bytes(4, "little") for w in img)
        name = "card.bin" if int(slot) == 2 else f"card{int(slot)}.bin"
        (assets_out / name).write_bytes(blob)
        print(f"card slot {slot} -> Assets/zeta/common/{name} "
              f"({len(img)} words)")

    stage_tape(out)
    # 2. the SD tree, byte-shape-matched to the zeta3 core that booted
    coredir = out / f"Cores/{AUTHOR}.{CORENAME}"
    coredir.mkdir(parents=True, exist_ok=True)
    (out / "Platforms/_images").mkdir(parents=True, exist_ok=True)
    (out / "Platforms/zeta.json").write_text(json.dumps(PLATFORM, indent=1))
    for name, doc in MANIFESTS.items():
        (coredir / name).write_text(json.dumps(doc, indent=1))
    assets = ROOT / "pocket/assets"
    shutil.copy(assets / "icon.bin", coredir / "icon.bin")
    shutil.copy(assets / "platform_image.bin",
                out / "Platforms/_images/zeta.bin")
    print(f"SD tree written to {out}")

    # 3. the bitstream. STALENESS IS THE WHOLE POINT HERE: this read
    # `if not rbf.exists()`, so once a bitstream existed the compile never
    # ran again -- and the gates above prove the RTL in the TREE while the
    # package carried the RTL from whenever Quartus last ran. Build 94
    # caught it: three gates green on a clipper the packaged bitstream did
    # not contain. On glass that reads as "the amendment does not work",
    # which is the most expensive possible way to be wrong. A gate that
    # proves one artifact while shipping another is not a gate.
    template = ROOT / "pocket/template"
    rbf = template / "output_files/ap_core.rbf"
    sources = [SIL / f for f in ("zvm.v", "zgpu.v", "zseq.v", "zsnd.v",
                                 "zeta_top.v")]
    sources += [ROOT / "pocket/zeta_glass.v", ROOT / "pocket/zeta_tape.v",
                ROOT / "silicon/gen/params.vh",
                template / "core/core_top.v", template / "ap_core.qsf"]
    # BY CONTENT, NOT BY CLOCK. The first version compared mtimes, and
    # `silicon/gen/params.vh` is REGENERATED from spec.py on every build --
    # same bytes, new timestamp -- so every deploy looked stale and every
    # deploy paid fifteen minutes of Quartus to rebuild an identical
    # bitstream. Worse, it left the tree in a confusing state: a fresh
    # .rbf beside a fit report from the previous run, because Quartus
    # skips the stages whose inputs did not really move.
    import hashlib
    h = hashlib.sha256()
    for p in sorted(sources):
        h.update(p.read_bytes() if p.exists() else b"")
    stamp = rbf.with_suffix(".srchash")
    want = h.hexdigest()
    have, have_build = read_stamp(stamp)
    check_build_bump(have, have_build, want, spec.LOADER_BUILD)
    stale = (not rbf.exists()) or have != want
    if stale and shutil.which("quartus_sh") and template.exists():
        why = "no bitstream yet" if not rbf.exists() else \
              "the RTL is newer than the bitstream"
        print(f"{why} -- running Quartus (~15 min)...")
        import subprocess
        # WHAT "IT WORKED" HAS TO MEAN. This asked `rbf.exists()`, which
        # is true of YESTERDAY'S bitstream -- so a failed compile printed
        # DONE, packaged silicon from a different design, and then wrote
        # the source stamp, marking the stale file as current so no later
        # deploy would rebuild it either. Caught by accident: build 98's
        # timing report came back byte-identical to the previous one, and
        # a report that has not moved after the design did is a report
        # that did not run.
        #
        # So: the exit code, AND a bitstream written after the compile
        # started, AND the flow's own verdict. Three, because the first
        # two would both have passed a fitter that failed at the very end
        # and left the file alone.
        started = time.time()
        r = subprocess.run(["quartus_sh", "--flow", "compile", "ap_core"],
                           cwd=template, capture_output=True, text=True)
        flow = template / "output_files" / "ap_core.flow.rpt"
        verdict = ""
        if flow.exists():
            for line in flow.read_text(errors="replace").splitlines():
                if "Flow Status" in line:
                    verdict = line.split(";")[2].strip() if ";" in line else line
                    break
        fresh = rbf.exists() and rbf.stat().st_mtime >= started
        if r.returncode != 0 or not fresh or "Successful" not in verdict:
            print(r.stdout[-3000:])
            raise SystemExit(
                f"Quartus compile FAILED -- exit {r.returncode}, flow "
                f"status {verdict!r}, bitstream "
                f"{'not rewritten' if not fresh else 'rewritten'}. "
                f"Nothing was packaged and the source stamp was left "
                f"alone, so the next deploy will try again.")
        # this bitstream IS these sources -- and this build number
        stamp.write_text(f"{want} {spec.LOADER_BUILD}\n")
    elif stale:
        raise SystemExit(
            f"REFUSED: {rbf} was not built from the RTL in the tree and "
            f"quartus_sh is not on PATH. Packaging it would ship silicon "
            f"the gates never saw.")
    if rbf.exists():
        (coredir / "zeta.rbf_r").write_bytes(reverse_bits(rbf.read_bytes()))
        print(f"bitstream reversed into {coredir / 'zeta.rbf_r'}")
        print("DONE: copy Platforms/, Cores/ and Assets/ from build/pocket/ "
              "onto the Pocket's SD card. Future cart swaps: only "
              "Assets/zeta/common/cart.zbin changes.")
    else:
        print(f"""\
NO BITSTREAM ({rbf} not found) and no quartus_sh on PATH. On a machine
with Quartus:  cd pocket/template && quartus_sh --flow compile ap_core
then re-run  zeta deploy {cart_name}  to reverse + package it.""")
    return 0
