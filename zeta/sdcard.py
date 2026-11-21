# THE CARD FERRY. The Pocket has no remote programming path, so an SD
# card crossing a desk is the one physical step left in the loop. These
# commands shrink it to:
#
#   zeta sd push                  stage build/pocket/ onto the card
#   zeta sd shots                 pull the newest Menu+Start captures
#   zeta sd witness CART          pull the newest capture and hold it
#                                 against the law -- glass to verdict
#                                 in one line
#
# The card is found by its own anatomy: a mounted filesystem whose root
# holds Assets/ and Cores/ (the openFPGA layout). Memories/Screenshots/
# is where the Pocket keeps Menu+Start captures.

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGED = ROOT / "build" / "pocket"
MOUNT_ROOTS = ("/run/media", "/media", "/mnt")


def find_card(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit)
        if (p / "Assets").is_dir() and (p / "Cores").is_dir():
            return p
        raise SystemExit(f"{p} is mounted but does not look like a Pocket "
                         f"card (no Assets/ + Cores/ at its root)")
    seen = []
    for base in MOUNT_ROOTS:
        b = Path(base)
        if not b.is_dir():
            continue
        # /run/media/<user>/<label> and /media/<label> both occur
        for cand in list(b.iterdir()):
            for p in ([cand] + (list(cand.iterdir())
                                if cand.is_dir() else [])):
                try:
                    if (p / "Assets").is_dir() and (p / "Cores").is_dir():
                        return p
                    if p.is_dir() and any(p.iterdir()):
                        seen.append(str(p))
                except PermissionError:
                    continue
    raise SystemExit(
        "no Pocket card found under " + ", ".join(MOUNT_ROOTS)
        + (f" (mounted but not a Pocket: {', '.join(sorted(set(seen))[:6])})"
           if seen else "") + " -- mount the card or pass --card PATH")


TAPES = ROOT / "build" / "tapes"     # sessions and saves brought home
TAPE_NAME = "tape.ztp"              # deploy.TAPE_FILE's name (tested equal)


def saves_home(card: Path, out_dir: Path | None = None,
               stamp: str | None = None) -> list[Path]:
    """Copy the card's save files home, under the time of this visit.

    A replay needs the save its session STARTED with, and the card only
    ever holds the one it ended with. So every visit -- a push or a tape
    pull -- keeps what it finds: this visit's copy is the end of the
    session just played and the start of the next."""
    import time
    from . import deploy
    out_dir = out_dir or TAPES          # read NOW: a default argument is
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")   # bound once, at import
    src = card / deploy.ASSETS
    out = []
    for f in sorted(src.glob("card*.bin")):
        if deploy.card_slot(f.name) is None:
            continue
        dst = out_dir / f"{stamp}.{f.name}"
        last = sorted(out_dir.glob(f"*.{f.name}"))
        if last and last[-1].read_bytes() == f.read_bytes():
            out.append(last[-1])                # unchanged since the last visit
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        out.append(dst)
    return out


def tape(card: Path, out_dir: Path | None = None, cart=None) -> Path | None:
    """Bring the recorded session home: the tape the OS wrote when the
    core last exited, trimmed to the session and named by the time it was
    written; the save files beside it; and which game on the card it was.
    `cart` (a loaded cart) is checked against its header instead."""
    import time
    from . import deploy, tape as ztape
    out_dir = out_dir or TAPES
    src = card / deploy.TAPE_FILE
    if not src.is_file():
        print(f"no tape on the card ({deploy.TAPE_FILE})")
        return None
    blob = ztape.from_card(src.read_bytes())
    try:
        head, pads = ztape.decode(blob)
    except ValueError as e:
        print(f"the card's tape is blank or not a tape: {e}")
        return None
    # named by THIS desk's clock, like the saves beside it: the file's own
    # time is the Pocket's, which on first glass was a day behind, and a
    # tape must sort after the save its session started with
    stamp = time.strftime("%Y%m%d-%H%M%S")
    wrote = time.strftime("%Y-%m-%d %H:%M", time.localtime(src.stat().st_mtime))
    before = sorted(out_dir.glob("*.card.bin"))          # the save it started with
    after = saves_home(card, out_dir, stamp)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{stamp}.ztp"
    used = 4 * (ztape.HEADER_WORDS + head["runs"] + 1)
    dst.write_bytes(blob[:used])                     # the session, not the blank after it
    secs = len(pads) / 60
    print(f"  {dst}: {len(pads):,} frames ({int(secs // 60)}m{secs % 60:04.1f}s), "
          f"{head['runs']:,} runs, build {head['build']}, "
          f"cart sum {head['cart_sum']:#010x} (the Pocket wrote it {wrote}, by its clock)")
    if head["runs"] >= ztape.WORDS - ztape.HEADER_WORDS - 1:
        print("  THE TAPE IS FULL: the session ran on after it")
    if cart is not None:
        why = ztape.check(head, cart)
        print(f"  {'DOES NOT MATCH: ' + why if why else 'matches the cart given'}")
        return dst
    # which game was it? the card holds every game, and the sum names one
    game = None
    for z in sorted((card / deploy.ASSETS).glob("*.zbin")):
        if zbin_sum(z) == head["cart_sum"]:
            game = z
    if game is None:
        print("  no game on the card has that sum (restaged since it was played?)")
        return dst
    print(f"  the game: {game.name}")
    line = f"zeta replay {dst} \"{game}\""
    if before:
        line += f" --card {before[-1]}"
    slot2 = [a for a in after if a.name.endswith(".card.bin")]
    if slot2:
        line += f" --expect {slot2[-1]}"
    print(f"  again, on the desktop:  {line}")
    return dst


def zbin_sum(path: Path) -> int:
    """tape.cart_sum of a slot file: every word, added mod 2^32."""
    import numpy as np
    blob = Path(path).read_bytes()
    return int(np.frombuffer(blob[:len(blob) // 4 * 4], dtype="<u4").sum(dtype=np.uint64)) & 0xFFFFFFFF


def push(card: Path, staged: Path = STAGED) -> int:
    """Copy the staged SD layout onto the card, newest wins, and say
    exactly what moved. `zeta deploy` must have staged first."""
    if not staged.is_dir():
        raise SystemExit(f"{staged} does not exist -- run `zeta deploy` "
                         f"(or download the CI fit artifact) first")
    saves_home(card)                # the save the next session starts with
    copied = 0
    for src in sorted(staged.rglob("*")):
        if not src.is_file():
            continue
        dst = card / src.relative_to(staged)
        # THE CARD FILES ARE SAVES: a card*.bin already on the card is what
        # the games wrote there, and a push must never roll it back -- the
        # staged one is only the first-ever image (TND P14)
        if dst.exists() and dst.name.startswith("card") and dst.suffix == ".bin":
            print(f"  kept {dst.relative_to(card)} (a save lives there)")
            continue
        # ...and so is the tape: a session nobody has brought home yet may
        # be on it, and a re-staged blank is always the newer file
        if dst.exists() and dst.name == TAPE_NAME \
                and dst.stat().st_size == src.stat().st_size:
            continue
        # the SAME file -- its stamp, or failing that its bytes -- not merely
        # an equal-sized one with a newer date: a push back to an older build
        # (same size, older stamp) was skipped as "already current" and left
        # the newer game on the card
        if dst.exists() and dst.stat().st_size == src.stat().st_size \
                and (dst.stat().st_mtime == src.stat().st_mtime
                     or dst.read_bytes() == src.read_bytes()):
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  -> {dst.relative_to(card)}")
        copied += 1
    os.sync()                       # the card may be yanked next
    print(f"pushed {copied} file(s) to {card}" if copied
          else f"card already current with {staged}")
    return 0


def shots(card: Path, n: int = 1, out: Path | None = None) -> list[Path]:
    """The newest n captures from Memories/Screenshots, copied local."""
    src = card / "Memories" / "Screenshots"
    if not src.is_dir():
        raise SystemExit(f"{src} does not exist -- has Menu+Start been "
                         f"pressed on this card?")
    found = sorted(src.glob("*.png"), key=lambda p: p.stat().st_mtime,
                   reverse=True)[:n]
    if not found:
        raise SystemExit(f"no captures in {src}")
    out = out or (ROOT / "shots")
    out.mkdir(exist_ok=True)
    pulled = []
    for p in found:
        dst = out / p.name
        shutil.copy2(p, dst)
        print(f"  <- {dst}")
        pulled.append(dst)
    return pulled
