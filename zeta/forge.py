"""forge.py -- one content path for every cart (docs/SDK.md).

`spec.py` is the law made executable for the MACHINE. This is the same
idea for CONTENT: resources that know their size but never their
address, a linker that assigns those addresses and cannot be fooled, and
a program builder that keeps ZOL visible while doing the clerical work.

The linker is the point. Before it, every cart hand-picked its DMEM map
(`GROUND_AT = 320` in five carts, `MESH_AT = 900` in three) and
hand-wrote its own `assert base + len <= next`. When fabric.zol's floor
grew, its sine table landed INSIDE the mesh's face data; both machines
skip corrupt indices identically, so the cross stayed green and the
symptom was missing tiles, mis-diagnosed twice as a clipping bug. A
linker cannot be fooled that way: overlap is impossible by construction
and every limit in spec.py is checked in one place.

    cart = Cart("flight")
    mesh = cart.data(Mesh(verts, faces, colors=cols))
    sines = cart.data(Table(sintab))
    p = cart.program()
    p.set(spec.CAM_Y, 24 * ONE)
    ...
    cart.write("carts/flight.zol")
"""
from __future__ import annotations

import math
from pathlib import Path

from . import spec

ONE = 65536


# ---------------------------------------------------------------------------
# 1. RESOURCES -- they know their size; they never know their address
# ---------------------------------------------------------------------------
class Resource:
    """Anything that serialises to a run of 32-bit words."""

    def words(self) -> list[int]:
        raise NotImplementedError

    def __len__(self) -> int:
        return len(self.words())

    def check(self) -> None:
        """Raise if the law forbids this resource. Called by the linker."""


class Table(Resource):
    """A plain run of words: sine tables, spirals, input tapes."""

    def __init__(self, values):
        self._w = [spec.s32(int(v)) & spec.WORD_MASK for v in values]

    def words(self):
        return list(self._w)


# --------------------------------------------------------------------------
# TEXT -- the first Tier-1 primitive, and the display list was free
# --------------------------------------------------------------------------
# PRIMITIVES.md audits three routes to text and rejects two: a font in the
# ONE resident texture page fits sixteen glyphs, and BG_SRC is full-screen
# with no sub-rectangle. What is left is the display list -- and every 3D
# cart in this tree uses ZERO of its 256 triangles, so the budget has been
# sitting there unspent since the machine could draw.
#
# A 3x5 glyph covers to 3.61 rectangles on average (measured over the
# alphabet), two triangles each: about THIRTY-FIVE characters on screen at
# once. That is a HUD and a prompt, not a dialogue box, and the doc says so
# plainly rather than discovering it in a game.
#
# The rectangles are baked to finished DISPLAY-LIST WORDS here, so a frame
# that does not change its text pays NOTHING. Only the frame that changes
# it runs the copy.
FONT3X5 = {c: g.split() for c, g in {
    "A": "010 101 111 101 101", "B": "110 101 110 101 110",
    "C": "011 100 100 100 011", "D": "110 101 101 101 110",
    "E": "111 100 110 100 111", "F": "111 100 110 100 100",
    "G": "011 100 101 101 011", "H": "101 101 111 101 101",
    "I": "111 010 010 010 111", "J": "001 001 001 101 010",
    "K": "101 101 110 101 101", "L": "100 100 100 100 111",
    "M": "101 111 111 101 101", "N": "110 101 101 101 101",
    "O": "010 101 101 101 010", "P": "110 101 110 100 100",
    "Q": "010 101 101 010 001", "R": "110 101 110 101 101",
    "S": "011 100 010 001 110", "T": "111 010 010 010 010",
    "U": "101 101 101 101 011", "V": "101 101 101 101 010",
    "W": "101 101 111 111 101", "X": "101 101 010 101 101",
    "Y": "101 101 010 010 010", "Z": "111 001 010 100 111",
    "0": "111 101 101 101 111", "1": "010 110 010 010 111",
    "2": "111 001 111 100 111", "3": "111 001 111 001 111",
    "4": "101 101 111 001 001", "5": "111 100 111 001 111",
    "6": "111 100 111 101 111", "7": "111 001 001 001 001",
    "8": "111 101 111 101 111", "9": "111 101 111 001 111",
    ".": "000 000 000 000 010", ":": "000 010 000 010 000",
    "-": "000 000 111 000 000", "!": "010 010 010 000 010",
    "?": "111 001 010 000 010", " ": "000 000 000 000 000",
}.items()}


def glyph_rects(ch):
    """A glyph as maximal rectangles, greedily. Fewer rectangles is fewer
    triangles is more characters on screen, and the greedy cover is within
    one rectangle of optimal on a shape this small."""
    rows = FONT3X5.get(ch.upper(), FONT3X5[" "])
    g = [[c == "1" for c in r] for r in rows]
    out = []
    for y in range(len(g)):
        for x in range(len(g[0])):
            if not g[y][x]:
                continue
            w = 0
            while x + w < len(g[0]) and g[y][x + w]:
                w += 1
            h = 1
            while y + h < len(g) and all(g[y + h][x + k] for k in range(w)):
                h += 1
            for dy in range(h):
                for dx in range(w):
                    g[y + dy][x + dx] = False
            out.append((x, y, w, h))
    return out


class Text(Resource):
    """A line of text, baked to finished display-list triangles.

    Placed with `cart.data(...)`, shown with `program.set_text(sym)`, which
    copies it over the display list. A cart that never changes its text
    never runs that copy.
    """

    def __init__(self, s, x, y, rgb=0xE6C010, scale=2, spacing=1):
        self.s, self.tris = s, []
        cx = x
        for ch in s.upper():
            for (rx, ry, rw, rh) in glyph_rects(ch):
                x0, y0 = cx + rx * scale, y + ry * scale
                x1, y1 = x0 + rw * scale, y0 + rh * scale
                # two triangles, wound the way the law's edge test accepts
                self.tris.append((x0, y0, x1, y0, x0, y1, rgb))
                self.tris.append((x1, y0, x1, y1, x0, y1, rgb))
            cx += (len(FONT3X5["A"][0]) + spacing) * scale

    def check(self):
        if len(self.tris) > spec.DL_MAX:
            raise ForgeError(
                f"text {self.s!r} is {len(self.tris)} triangles, DL_MAX is "
                f"{spec.DL_MAX} -- about {spec.DL_MAX // 8} characters fit")

    def words(self):
        w = [len(self.tris)]
        for t in self.tris:
            w += [spec.s32(int(v)) & spec.WORD_MASK for v in t]
        return w


class Mesh(Resource):
    """A GEOM mesh. The FLAGS FALL OUT OF THE TYPE -- a mesh with vertex
    colours is Gouraud, a mesh with uvs is textured -- so a mesh cannot
    be labelled wrong in the object list.

    verts:  flat [x,y,z, x,y,z, ...] in Q16.16
    faces:  [(a, b, c, rgb), ...]
    colors: one 0xRRGGBB per vertex, or None
    uvs:    one u | (v << 8) per vertex, or None
    """

    def __init__(self, verts, faces, colors=None, uvs=None):
        assert len(verts) % 3 == 0, "verts must be triples"
        assert not (colors and uvs), "a mesh is Gouraud or textured, not both"
        self.verts, self.faces = list(verts), list(faces)
        self.colors, self.uvs = colors, uvs

    @property
    def nv(self):
        return len(self.verts) // 3

    @property
    def flags(self):
        f = spec.OBJ_CULL
        if self.colors is not None:
            f |= spec.OBJ_GOURAUD
        if self.uvs is not None:
            f |= spec.OBJ_TEX
        return f

    def check(self):
        if self.nv > spec.MESH_NV_MAX:
            raise ForgeError(f"mesh has {self.nv} vertices, "
                             f"MESH_NV_MAX is {spec.MESH_NV_MAX}")
        # THE CAPACITY HALF OF THE FOUNDING BUG. The forge exists because
        # a resource overrun stayed invisible -- both machines skipped the
        # corrupt data identically, so the CROSS STAYED GREEN and the only
        # symptom was missing geometry, mis-diagnosed as clipping twice
        # (docs/SDK.md). This check was written for vertices and not for
        # FACES, so a 562-face mesh linked clean against a 512 cap and was
        # then dropped WHOLE by gpu.py and zseq.v alike -- the same bug in
        # the same shape, in the tool built to end it.
        if len(self.faces) > spec.MESH_NF_MAX:
            raise ForgeError(f"mesh has {len(self.faces)} faces, "
                             f"MESH_NF_MAX is {spec.MESH_NF_MAX} -- the "
                             f"machines would drop it whole and agree, so "
                             f"the cross cannot see this")
        for k, (a, b, c, _) in enumerate(self.faces):
            for i in (a, b, c):
                if not 0 <= i < self.nv:
                    raise ForgeError(f"face {k} indexes vertex {i} "
                                     f"of {self.nv}")
        per = self.colors if self.colors is not None else self.uvs
        if per is not None and len(per) != self.nv:
            raise ForgeError(f"{len(per)} per-vertex words for "
                             f"{self.nv} vertices")

    def words(self):
        w = [self.nv, len(self.faces)] + [spec.s32(int(v)) & spec.WORD_MASK
                                          for v in self.verts]
        per = self.colors if self.colors is not None else self.uvs
        if per is not None:
            w += [int(v) & spec.WORD_MASK for v in per]
        for a, b, c, rgb in self.faces:
            w += [a | (b << 10) | (c << 20), int(rgb) & spec.WORD_MASK]
        return w


class TexturePage(Resource):
    """A TEX_W x TEX_W page and its mip chain, two texels per word. The
    chain is generated here so no cart has to remember to."""

    def __init__(self, pixels):
        n = spec.TEX_W
        assert len(pixels) == n and all(len(r) == n for r in pixels), \
            f"a page is {n}x{n} RGB555 rows"
        self.pixels = pixels

    def words(self):
        levels = [self.pixels]
        while len(levels) < len(spec.TEX_MIP_OFF):
            prev = levels[-1]
            m = len(prev) // 2
            nxt = [[0] * m for _ in range(m)]
            for y in range(m):
                for x in range(m):
                    q = (prev[2*y][2*x], prev[2*y][2*x+1],
                         prev[2*y+1][2*x], prev[2*y+1][2*x+1])
                    t = 0
                    for sh in (10, 5, 0):
                        t |= (sum((v >> sh) & 31 for v in q) >> 2) << sh
                    nxt[y][x] = t
            levels.append(nxt)
        flat = [t for lv in levels for row in lv for t in row]
        flat += [0] * (spec.TEX_WORDS * 2 - len(flat))
        return [flat[i] | (flat[i + 1] << 16)
                for i in range(0, spec.TEX_WORDS * 2, 2)]


class WavePage(Resource):
    """WAV_W signed samples, four to a word."""

    def __init__(self, samples):
        assert len(samples) == spec.WAV_W, f"a page is {spec.WAV_W} samples"
        self.samples = [max(-128, min(127, int(s))) for s in samples]

    def words(self):
        return [sum((self.samples[w * 4 + b] & 0xFF) << (8 * b)
                    for b in range(4)) for w in range(spec.WAV_WORDS)]


class Plate(Resource):
    """A BG_SRC backdrop: colour in the low half, DEPTH in the high. The
    depth is what makes it a plate and not a picture -- live geometry
    occludes against it per pixel (docs/FLIGHT.md, the horizon plate)."""

    def __init__(self, color555, depth16, shadow=None):
        assert len(color555) == len(depth16) == spec.BG_WORDS, \
            f"a plate is {spec.BG_WORDS} pixels"
        assert shadow is None or len(shadow) == spec.BG_WORDS, \
            f"a shadow mask is {spec.BG_WORDS} pixels"
        self.color, self.depth = color555, depth16
        # THE ROOM AND ITS SHADOW ARE ONE RESOURCE. They could have been
        # two -- a plate and a table the cart indexes by position -- and
        # that would have cost no silicon at all. It would also have been
        # two things that can drift apart, which is the exact shape of
        # this tree's founding bug. Paging a new room now pages its
        # shadow, because they are the same words.
        self.shadow = shadow

    def words(self):
        sh = self.shadow or [0] * len(self.color)
        return [(int(c) & 0x7FFF) | (spec.BG_SHADOW if v else 0)
                | ((int(d) & 0xFFFF) << 16)
                for c, d, v in zip(self.color, self.depth, sh)]


class ForgeError(SystemExit):
    pass


# ---------------------------------------------------------------------------
# 2. THE LINKER -- law-aware, and the reason overlap cannot happen
# ---------------------------------------------------------------------------
class Sym(int):
    """An assigned address. It is an int, so it drops straight into ZOL,
    but it carries what it points at for error messages."""

    def __new__(cls, addr, name, length):
        s = super().__new__(cls, addr)
        s.name, s.length = name, length
        return s

    def __repr__(self):
        return f"<{self.name}@{int(self)}+{self.length}>"


# DMEM the cart may not place content in: the low registers, the display
# list, the object list, and the high register block. Read from spec so
# the forge cannot drift from the law.
def _reserved():
    lo = max(spec.DMA_GO, spec.CAM_YAW, spec.BG_SRC, spec.PICK_Z) + 1
    regs = [v for n, v in vars(spec).items()
            if isinstance(v, int) and 12000 < v < spec.DMEM_WORDS
            and n.isupper() and not n.endswith("_WORDS")]
    # THE LOADER'S SIGNATURE MIRROR IS NOT A REGISTER AND SITS BELOW THE
    # THRESHOLD. LOADER_SIG2 is 11700; the filter above looks for the high
    # register block at 12000+, so those eight words sat INSIDE the
    # allocatable pool. The hardware loader rewrites them at every boot and
    # the VM does not, so the first cart whose content reached 11700 would
    # have gone cross-red on glass with nothing in the picture to say why --
    # and pose banks are the first content big enough to get there.
    # Reserved explicitly, from the law, rather than by a magic threshold.
    regs.append(spec.LOADER_SIG2)
    return lo, min(spec.DL_BASE, min(regs, default=spec.DL_BASE))


class Cart:
    """Holds resources, assigns their addresses, emits .zol."""

    def __init__(self, name, data_base=None):
        self.name = name
        lo, hi = _reserved()
        self._lo, self._hi = (data_base or lo), hi
        self._next = self._lo
        self._data: list[tuple[Sym, Resource]] = []
        self._cram: list[tuple[Sym, Resource]] = []
        self._sd: dict[int, list[tuple[Sym, Resource]]] = {}
        self._const: dict[str, int] = {}
        self._boot: dict[int, int] = {}
        self._prog: Program | None = None
        self._scratch = self._lo   # cart variables live below the content

    # ---- placement -------------------------------------------------------
    def data(self, res: Resource, name=None) -> Sym:
        """Place a resource in DMEM. The address is chosen; it cannot
        collide with anything already placed, nor with the law's
        reserved regions."""
        res.check()
        w = res.words()
        at = self._next
        if at + len(w) > self._hi:
            raise ForgeError(
                f"{self.name}: DMEM full -- {name or type(res).__name__} "
                f"needs {len(w)} words at {at}, and content must end by "
                f"{self._hi} (DL_BASE / the register block)")
        sym = Sym(at, name or type(res).__name__.lower(), len(w))
        self._next = at + len(w)
        self._data.append((sym, res))
        return sym

    def var(self, name, count=1) -> Sym:
        """A scratch cell (or run) for the program's own state. Taken
        from the same pool, so a variable cannot land on a mesh."""
        return self.data(Table([0] * count), name)

    def cram(self, res: Resource, name=None) -> Sym:
        """Place a resource in the cart's CRAM segment.

        Offset ZERO is never handed out: BG_SRC reads 0 as "no backdrop"
        (gpu.render: `if bg > 0`), so a plate landing at 0 is silently
        disabled -- the frame clears to flat colour and nothing says
        why. The first plate ever baked landed there."""
        res.check()
        w = res.words()
        # Offset ZERO is never handed out: BG_SRC reads 0 as "no
        # backdrop" (gpu.render: `if bg > 0`), so a plate there is
        # silently disabled and nothing says why. (Row alignment was
        # tried here as a fix for the backdrop's last scanline and is
        # NOT one -- CRAM_CART_BASE is itself 96 halves into a row, so
        # no offset can align a segment burst. See the roadmap.)
        at = 1 + sum(len(r.words()) for _, r in self._cram)
        if at + len(w) > spec.CRAM_WORDS:
            raise ForgeError(f"{self.name}: CRAM segment full at {at}")
        sym = Sym(at, name or "cram", len(w))
        self._cram.append((sym, res))
        return sym

    def sd(self, slot: int, res: Resource, name=None) -> Sym:
        res.check()
        w = res.words()
        img = self._sd.setdefault(slot, [])
        at = sum(len(r.words()) for _, r in img)
        sym = Sym(at, name or f"sd{slot}", len(w))
        img.append((sym, res))
        return sym

    def boot(self, addr, value):
        """Initialise a REGISTER cell at boot -- the camera, the fog, the
        page pointers. These live outside the content region by law, so
        they are recorded separately and can never be confused with an
        allocation."""
        a = int(addr)
        lo, hi = _reserved()
        if lo <= a < hi:
            raise ForgeError(
                f"{self.name}: boot({a}) is inside the CONTENT region "
                f"({lo}..{hi}) -- use cart.var() for cart state")
        self._boot[a] = spec.s32(int(value)) & spec.WORD_MASK
        return self

    def const(self, name, value):
        self._const[name] = int(value)
        return name

    _objb = None

    @property
    def _obj_base(self) -> Sym:
        """Scratch for the computed object-list address. Allocated on
        first use so a cart that never emits objects never pays."""
        if self._objb is None:
            self._objb = self.var("obj_base")
        return self._objb

    def program(self):
        self._prog = Program(self)
        return self._prog

    # ---- emission --------------------------------------------------------
    def lines(self) -> list[str]:
        out = [f"; {self.name}.zol -- GENERATED by the forge "
               f"(zeta/forge.py). Do not edit.",
               f"; addresses are ASSIGNED, not chosen: see docs/SDK.md",
               ""]
        for n, v in self._const.items():
            out.append(f".const {n} {v}")
        if self._const:
            out.append("")
        if self._boot:
            out.append("; boot state: the register cells")
            for a in sorted(self._boot):
                out.append(f".data {a} {spec.s32(self._boot[a])}")
            out.append("")
        for sym, res in self._data:
            w = res.words()
            out.append(f"; {sym.name}: {len(w)} words at {int(sym)}")
            for o in range(0, len(w), 12):
                vals = " ".join(str(spec.s32(v)) for v in w[o:o + 12])
                out.append(f".data {int(sym) + o} {vals}")
            out.append("")
        for sym, res in self._cram:
            w = res.words()
            for o in range(0, len(w), 12):
                vals = " ".join(str(spec.s32(v)) for v in w[o:o + 12])
                out.append(f".cram {int(sym) + o} {vals}")
        if self._cram:
            out.append("")
        for slot, img in sorted(self._sd.items()):
            for sym, res in img:
                w = res.words()
                for o in range(0, len(w), 12):
                    vals = " ".join(str(spec.s32(v)) for v in w[o:o + 12])
                    out.append(f".sd {slot} {int(sym) + o} {vals}")
            out.append("")
        if self._prog is not None:
            out += self._prog.lines()
        return out

    def write(self, path) -> Path:
        p = Path(path)
        p.write_text("\n".join(self.lines()) + "\n")
        return p

    def report(self) -> str:
        used = self._next - self._lo
        free = self._hi - self._next
        n = len(self._prog.lines()) if self._prog else 0
        return (f"{self.name}: {len(self._data)} resources, "
                f"{used} DMEM words used, {free} free "
                f"(content must end by {self._hi})")


# ---------------------------------------------------------------------------
# 3. THE PROGRAM -- ZOL stays visible; only the clerical work goes
# ---------------------------------------------------------------------------
class Program:
    """Emits ZOL. Labels are unique BY CONSTRUCTION, which is why
    gen_fabric.py's mark_scan needed a `tag` argument and this does not."""

    def __init__(self, cart: Cart):
        self.cart = cart
        self._out: list[str] = []
        self._n = 0

    # ---- the raw floor ---------------------------------------------------
    def emit(self, *ops):
        for o in ops:
            self._out.append(o)
        return self

    def label(self, base) -> str:
        self._n += 1
        return f"{base}_{self._n}"

    def mark(self, name):
        self._out.append(f"{name}:")
        return self

    # ---- the small vocabulary every cart repeats --------------------------
    def push(self, v):
        return self.emit(f"push {int(v)}")

    def push32(self, v):
        """Push ANY 32-bit constant.

        `push` carries a SIGNED 24-bit immediate -- the VM sign-extends
        when bit 23 is set -- so `push 0xFFFFFF` pushes MINUS ONE, and
        every colour with red >= 0x80 is silently negative. Mesh colours
        never hit this because `.data` takes full 32-bit words; the first
        cart to push a colour AT RUNTIME (fade.zol) did, and spent an
        afternoon looking like a compositor bug.

        Values that fit go through as one push; the rest are built from
        12-bit halves, which cannot set bit 23."""
        v = int(v) & 0xFFFFFFFF
        sv = v - (1 << 32) if v & (1 << 31) else v
        if -(1 << 23) <= sv < (1 << 23):
            return self.emit(f"push {sv}")
        parts = [(v >> 24) & 0xFF, (v >> 16) & 0xFF,
                 (v >> 8) & 0xFF, v & 0xFF]
        self.emit(f"push {parts[0]}")
        for b in parts[1:]:
            self.emit("shl 8", f"push {b}", "or")
        return self

    def load(self, a):
        return self.emit(f"load {int(a)}")

    def store(self, a):
        return self.emit(f"store {int(a)}")

    def set(self, addr, value):
        return self.push(value).store(addr)

    def addi(self, addr, delta):
        """cell += delta"""
        return self.load(addr).push(abs(int(delta))).emit(
            "add" if delta >= 0 else "sub").store(addr)

    def clamp(self, addr, lo, hi):
        """The console says no, in four lines instead of eight."""
        a, b = self.label("clo"), self.label("chi")
        return (self.load(addr).push(lo).emit("lt").emit(f"jz {a}")
                .push(lo).store(addr).mark(a)
                .push(hi).load(addr).emit("lt").emit(f"jz {b}")
                .push(hi).store(addr).mark(b))

    def if_no_pad(self, bits, body):
        """Run `body` when NONE of `bits` are held -- the self-centring
        shape (wings level, stick returns) that every vehicle needs."""
        skip = self.label("nopad")
        self.emit("load 1", f"push {int(bits)}", "and")
        run = self.label("run")
        self.emit(f"jz {run}", f"jmp {skip}").mark(run)
        body(self)
        return self.mark(skip)

    def toward_zero(self, addr, step):
        """Decay a signed cell toward 0 by `step`, never past it."""
        done, neg = self.label("tz"), self.label("tzneg")
        self.load(addr).emit(f"jz {done}")
        self.load(addr).push(0).emit("lt", f"jz {neg}")
        self.addi(addr, step).emit(f"jmp {done}")
        self.mark(neg).addi(addr, -step)
        return self.mark(done)

    def if_pad(self, bits, body):
        """Run `body` when any of `bits` are held."""
        skip = self.label("pad")
        self.emit("load 1", f"push {int(bits)}", "and", f"jz {skip}")
        body(self)
        return self.mark(skip)

    # ---- the scanout compositor (spec.CO_BASE) ---------------------------
    def rect(self, k, x0, y0, x1, y1, rgb, alpha):
        """Write compositor entry k. Bounds are INCLUSIVE; alpha is in
        sixteenths (0 hides the entry without removing it). `alpha` may
        be a callable that leaves the value on the stack.

        rgb goes through push32 because the immediate is SIGNED 24 bits
        -- a plain `push 0xFFFFFF` pushes MINUS ONE and lights every
        alpha bit, which is a whole afternoon if you meet it inside a
        cart instead of here."""
        if not 0 <= k < spec.CO_MAX:
            raise ForgeError(f"compositor entry {k}, CO_MAX is {spec.CO_MAX}")
        b = spec.CO_BASE + 1 + k * spec.CO_STRIDE
        self.set(b, (int(x0) & 0x3FF) | ((int(x1) & 0x3FF) << 10))
        self.set(b + 1, (int(y0) & 0x3FF) | ((int(y1) & 0x3FF) << 10))
        if callable(alpha):
            alpha(self)
        else:
            self.push(int(alpha))
        return self.emit("shl 24").push32(rgb).emit("or").store(b + 2)

    def rects_off(self):
        """Every entry invisible, count live. Carts want this at the top
        of a frame so an overlay cannot outlive the thing that set it."""
        for k in range(spec.CO_MAX):
            self.set(spec.CO_BASE + 1 + k * spec.CO_STRIDE + 2, 0)
        return self.set(spec.CO_BASE, spec.CO_MAX)

    # ---- scenes and timers: the structure above a frame ------------------
    # PRIMITIVES.md Tier-1 #6. Overlays already make a cart BECOME another
    # program between frames; what was missing is the small structure above
    # it -- a mode cell, a countdown, "do this in N frames". Cutscenes,
    # respawns, menus, doors and death are all this one thing, and every
    # cart that has wanted any of them has written its own.
    def if_eq(self, cell, value, body):
        """The scene dispatcher: run `body` when cell == value."""
        skip = self.label("ne")
        self.load(cell).push(int(value)).emit("eq", f"jz {skip}")
        body(self)
        return self.mark(skip)

    def if_zero(self, cell, body):
        return self.if_eq(cell, 0, body)

    def if_nonzero(self, cell, body):
        skip = self.label("z")
        self.load(cell).emit(f"jz {skip}")
        body(self)
        return self.mark(skip)

    def countdown(self, cell):
        """A frame timer: one less, never past zero. Pair with on_zero."""
        skip = self.label("tick")
        self.load(cell).emit(f"jz {skip}")
        self.addi(cell, -1)
        return self.mark(skip)

    def on_zero(self, cell, body):
        """Run `body` on the ONE frame a countdown spends its last tick,
        then zero the cell so it cannot fire again. A timer that re-fires
        every frame once it expires is the shape of bug that makes a
        respawn loop forever, so firing once is the whole contract."""
        skip = self.label("oz")
        self.load(cell).emit(f"jz {skip}")     # already spent
        self.load(cell).push(1).emit("eq", f"jz {skip}")
        self.set(cell, 0)
        body(self)
        return self.mark(skip)

    # ---- input: a level is not an edge -----------------------------------
    def pad_edges(self, prev, pressed, released=None):
        """REG_PAD is a LEVEL. Every cart that wants "on press" reinvents
        the previous-state cell (fabric.zol calls it PREVA). Compute it
        once: `pressed` gets the newly-down bits, `released` the newly-up,
        and `prev` carries the state."""
        self.load(spec.REG_PAD).load(prev).emit("xor")
        self.load(spec.REG_PAD).emit("and").store(pressed)
        if released is not None:
            self.load(spec.REG_PAD).load(prev).emit("xor")
            self.load(prev).emit("and").store(released)
        return self.load(spec.REG_PAD).store(prev)

    def set_text(self, sym, n_words=None):
        """Copy a baked Text over the display list.

        RUN IT ONLY WHEN THE TEXT CHANGES. The display list is ordinary
        DMEM and nothing else writes it, so the words stay put frame after
        frame -- a HUD that does not change costs zero instructions, and a
        prompt costs this copy once, on the frame it appears.
        """
        src = self.cart.var(self.label("txsrc"))
        dst = self.cart.var(self.label("txdst"))
        cnt = self.cart.var(self.label("txcnt"))
        top = self.label("tx")
        end = self.label("txe")
        # words = 1 + triangles * DL_STRIDE, and the count is the table's
        # own first word so the cart never repeats a number the baker knows
        self.push(int(sym)).store(src)
        self.push(spec.DL_BASE).store(dst)
        if n_words is None:
            self.push(int(sym)).emit("loadi")
            self.push(spec.DL_STRIDE).emit("mul").push(1).emit("add")
        else:
            self.push(int(n_words))
        self.store(cnt)
        self.mark(top)
        self.load(cnt).emit(f"jz {end}")
        self.load(src).emit("loadi")          # value
        self.load(dst).emit("storei")         # ...to the display list
        self.addi(src, 1)
        self.addi(dst, 1)
        self.addi(cnt, -1)
        self.emit(f"jmp {top}")
        self.mark(end)
        return self

    def hide_text(self):
        """One store: the display list draws nothing. The triangles stay
        where they are, so showing it again is one store too."""
        return self.set(spec.DL_BASE, 0)

    def if_bit(self, cell, bits, body):
        """Run `body` when any of `bits` are set in `cell` -- the shape
        that reads an edge word computed by pad_edges."""
        skip = self.label("bit")
        self.load(cell).push(int(bits)).emit("and", f"jz {skip}")
        body(self)
        return self.mark(skip)

    def object(self, n_cell, mesh_sym, x, y, z, angles, flags):
        """Write object N of the list, then N += 1. Written ONCE here;
        it existed three times across gen_fabric, gen_flight and
        gen_lodspan before the forge."""
        base = self.cart._obj_base
        self.load(n_cell).push(spec.OL_STRIDE).emit("mul")
        self.push(spec.OL_BASE + 1).emit("add").store(base)
        for k, ops in enumerate((mesh_sym, x, y, z, angles, flags)):
            if callable(ops):
                ops(self)
            elif isinstance(ops, (list, tuple)):
                self.emit(*ops)
            else:
                self.push(ops)
            self.load(base).push(k).emit("add").emit("storei")
        return self.addi(n_cell, 1)

    def lines(self):
        return list(self._out)


def sine_table(n=128, step=8, scale=1.0):
    """The table every cart that moves has rebuilt for itself."""
    return Table([int(round(math.sin(i * step * math.tau / 1024)
                            * ONE * scale)) for i in range(n)])
