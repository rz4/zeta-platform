"""Where the carts live.

The repo keeps four kinds of cart that are not games, and games apart:

    carts/witness/    one claim about the machine each, held by a gate
                      (zeta/suite.py) -- part of the machine's proof
    carts/probes/     questions asked of real hardware; answered, they
                      are history
    carts/examples/   small carts to learn from and to cross against
    carts/system/     what the console itself shows: the boot face, the
                      film, the shelf
    games/<name>/     a game: its generator, its cart, and in time its
                      assets, tests and tapes

Everything else finds a cart BY NAME through here, so a cart can move
between kinds -- a probe that earns a claim becomes a witness -- without
a path changing anywhere.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("witness", "probes", "examples", "system")


def dirs() -> list[Path]:
    """Every directory that holds carts, in a fixed order."""
    out = [ROOT / "carts" / k for k in KINDS]
    games = ROOT / "games"
    if games.is_dir():
        out += sorted(d for d in games.iterdir() if d.is_dir())
    return [d for d in out if d.is_dir()]


def path(name: str) -> Path:
    """The cart called `name` (no extension), wherever it lives."""
    name = Path(name).stem
    hits = [d / f"{name}.zol" for d in dirs() if (d / f"{name}.zol").is_file()]
    if not hits:
        raise KeyError(f"no cart called {name!r} under carts/ or games/")
    if len(hits) > 1:
        raise KeyError(f"two carts called {name!r}: {', '.join(map(str, hits))}")
    return hits[0]


def gen(name: str) -> Path:
    """The generator that writes the cart called `name`."""
    name = Path(name).stem
    hits = [d / f"gen_{name}.py" for d in dirs() if (d / f"gen_{name}.py").is_file()]
    if len(hits) != 1:
        raise KeyError(f"{len(hits)} generators called gen_{name}.py")
    return hits[0]


def resolve(arg) -> Path:
    """A command-line argument as a cart: a path that exists, or a name."""
    p = Path(arg)
    return p if p.is_file() else path(p.stem)


def kind(name: str) -> str:
    """'witness', 'probes', 'examples', 'system' or 'game'."""
    d = path(name).parent
    return d.name if d.parent.name == "carts" else "game"


def names(kinds=None) -> list[str]:
    """Every cart's name, optionally only of the given kinds."""
    out = []
    for d in dirs():
        k = d.name if d.parent.name == "carts" else "game"
        if kinds is None or k in kinds:
            out += sorted(z.stem for z in d.glob("*.zol"))
    return out


def generators() -> list[Path]:
    """Every generator that has a cart beside it."""
    return [g for d in dirs() for g in sorted(d.glob("gen_*.py"))
            if (d / f"{g.stem[4:]}.zol").is_file()]


def on_path() -> None:
    """Put every cart directory on sys.path: generators share helpers
    (gen_cube's meshes, gen_hall's scene) and import each other by name."""
    for d in dirs():
        if str(d) not in sys.path:
            sys.path.append(str(d))
