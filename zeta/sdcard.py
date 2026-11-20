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


def push(card: Path, staged: Path = STAGED) -> int:
    """Copy the staged SD layout onto the card, newest wins, and say
    exactly what moved. `zeta deploy` must have staged first."""
    if not staged.is_dir():
        raise SystemExit(f"{staged} does not exist -- run `zeta deploy` "
                         f"(or download the CI fit artifact) first")
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
        if dst.exists() and dst.stat().st_size == src.stat().st_size \
                and dst.stat().st_mtime >= src.stat().st_mtime:
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
