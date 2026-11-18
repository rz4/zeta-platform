"""cabinet.py -- where a cart meets a player (or a test).

Two front ends over the same frame contract:
  run()  -- pygame window at 60 fps, keyboard latched into the pad word
  dump() -- headless: N frames, chosen ones written as PPM

Both take a `machine`: anything with .frame(pad) and .framebuffer() ->
(H, W, 3) uint8. VirtualMachine wraps vm.VM + gpu.render; the silicon
backend will wrap the Verilated core behind the same two methods, so the
cabinet -- and the player's experience -- is literally shared.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import gpu, spec, vm


class VirtualMachine:
    """The Python machine: VM for the game, gpu.render for the picture,
    audio.SndEngine for the 800 samples that go with each frame."""

    def __init__(self, cart):
        from . import audio
        self.vm = vm.VM(cart)
        self.snd = audio.SndEngine()
        # ---- WHEN A VOICE'S TOTAL BECOMES READABLE (spec.AUD_BASE) ----
        # TWO frames, not one, and the reason is physical rather than a
        # choice. The pick register and the pixel counts are finished
        # when the DRAW is finished, so the cart reads them one frame
        # later. A frame's SOUND is not finished when its draw is: the
        # draw takes about 220,000 of a frame's 720,000 clocks and the
        # samples keep coming for the rest of it. At the instant the
        # machine writes its answers back, the newest COMPLETE frame of
        # audio is the one before last -- on glass and in the cross
        # alike, for the same reason.
        #
        # Traced rather than assumed: the silicon's own order is
        # frame_go, draw, write back, run the cart -- so the readback
        # sits a whole frame ahead of the audio it is reporting. The law
        # held it one frame and heard.zol's bars stood a frame ahead of
        # the sound they were drawn from: 6,555 pixels, while the totals
        # themselves matched to the unit on every frame.
        self._heard = [[0] * spec.AU_CHANNELS, [0] * spec.AU_CHANNELS]
        self._audio = np.zeros(spec.SAMPLES_PER_FRAME, np.int16)
        # the CRAM segment densified once, for the backdrop's fast path
        self._cram = None
        # EIGHT PAGES, PERSISTENT. A page loaded on frame N is still there
        # on frame N+1: the cart fills its slots once at startup and then
        # just points objects at them. One slot is loaded per frame, from
        # TEX_SRC into TEX_PAGE.
        self._tex = np.zeros(spec.TEX_PAGES * spec.TEX_STRIDE, np.int64)
        self._wav = [[0] * spec.WAV_W       # one table per voice, resolved
                     for _ in range(spec.AU_CHANNELS)]   # from the bank
        if self.vm.cram:
            n = max(self.vm.cram) + 1
            self._cram = np.zeros(n, np.int64)
            for a, v in self.vm.cram.items():
                self._cram[a] = v

    def frame(self, pad: int) -> None:
        for c in range(spec.AU_CHANNELS):     # two frames old: see above
            self.vm.dmem[spec.AUD_BASE + c] = self._heard[0][c]
        self.vm.frame(pad)
        self.vm.dma()                  # after the program, before the paint
        self.vm.overlay()              # ...code, at the same instant
        self.vm.card()                 # ...and the card, at the same instant
        self.vm.card_diag()            # the counters the silicon keeps
        # the texture page: a bounded window, reloaded when the cart asks
        src = self.vm.dmem[spec.TEX_SRC]
        if src and src + spec.TEX_WORDS <= spec.DMEM_WORDS:
            words = np.array(self.vm.dmem[src:src + spec.TEX_WORDS],
                             np.int64)
            halves = np.empty(spec.TEX_WORDS * 2, np.int64)
            halves[0::2] = words & 0xFFFF
            halves[1::2] = (words >> 16) & 0xFFFF
            # NOT & (TEX_PAGES - 1): 24 is not a power of two, so the
            # mask that used to wrap now aliases. Out of range is 0.
            slot = spec.tex_page(self.vm.dmem[spec.TEX_PAGE])
            self._tex[slot * spec.TEX_STRIDE:
                      slot * spec.TEX_STRIDE + len(halves)] = halves
        # THE WAVE BANK: the same bounded window, at the other rate, and
        # now each voice may aim it somewhere different. The page is read
        # from the REGISTER ctrl word (spec: a page is a load-time
        # property; only vol/duty/wave move at the sample), and a channel
        # whose page would run past DMEM keeps the table it already had.
        wsrc = self.vm.dmem[spec.WAV_SRC]
        if wsrc:
            for c in range(spec.AU_CHANNELS):
                ctrl = self.vm.dmem[spec.AU_BASE + 2 * c + 1]
                pg = (ctrl >> spec.AU_PAGE_SHIFT) & spec.AU_PAGE_MASK
                a = wsrc + pg * spec.WAV_WORDS
                if a + spec.WAV_WORDS > spec.DMEM_WORDS:
                    continue
                page = []
                for w in self.vm.dmem[a:a + spec.WAV_WORDS]:
                    for b in range(4):
                        v = (w >> (8 * b)) & 0xFF
                        page.append(v - 256 if v > 127 else v)
                self._wav[c] = page
        self._audio = self.snd.frame(self.vm.dmem, self._wav)
        self._heard = [self._heard[1], self.snd.heard]
        # the paint happens EVERY frame, eagerly: render now writes the
        # pick register's answer back into DMEM (spec.PICK_*), so a
        # lazily skipped frame would skip the machine's answer and
        # diverge from silicon, which always paints
        self._fb = gpu.render(self.vm.dmem, self._cram, self._tex)
        self._panel = gpu.grade(
            gpu.compose(self._fb, self.vm.dmem), self.vm.dmem)

    def framebuffer(self) -> np.ndarray:
        return self._fb

    def panel(self):
        """What the SCREEN shows: the framebuffer with the scanout
        compositor applied. glass compares this; cross compares
        framebuffer(), because the compositor never touches CRAM."""
        return self._panel

    def audio(self) -> np.ndarray:
        return self._audio

    # ---- THE STATE (spec.STATE_*): rewind, Memories, the cross across time
    def snapshot(self) -> dict:
        """The machine's whole state between two frames, as spec.py
        legislates it. Copies, never views: a snapshot that aliased the
        live machine would rewind to wherever the machine had got to."""
        v = self.vm
        if v.sd_req is not None:
            raise StateBusy(
                f"a card request is in flight and lands in {v.sd_wait} "
                f"frame(s); a snapshot is refused until it does (spec.STATE)")
        return {
            "frame_no": v.frame_no,
            "trapped": v.trapped,
            "imem": list(v.imem),
            "dmem": list(v.dmem),
            "tex": self._tex.copy(),
            "wav": [list(p) for p in self._wav],
            "phase": list(self.snd.phase),
            "lfsr": self.snd.lfsr,
            "heard": [list(h) for h in self._heard],
            "diag": (v.sd_copied, v.sd_staged, int(v.sd_counted), v.sd_lat),
        }

    def restore(self, s: dict) -> None:
        """The inverse. The card is external and is not touched; an
        in-flight request cannot exist in a snapshot (see above), so
        none is restored."""
        v = self.vm
        v.frame_no = int(s["frame_no"])
        v.trapped = bool(s["trapped"])
        v.imem[:] = [int(w) & spec.WORD_MASK for w in s["imem"]]
        v.dmem[:] = [int(w) & spec.WORD_MASK for w in s["dmem"]]
        v.sd_req, v.sd_wait, v.sd_snap = None, 0, []
        v.sd_copied, v.sd_staged, counted, v.sd_lat = (int(x) for x in s["diag"])
        v.sd_counted = bool(counted)
        self._tex[:] = np.asarray(s["tex"], np.int64)
        self._wav = [[int(x) for x in p] for p in s["wav"]]
        self.snd.phase = [int(x) for x in s["phase"]]
        self.snd.lfsr = int(s["lfsr"])
        self._heard = [[int(x) for x in h] for h in s["heard"]]

    def pack(self) -> bytes:
        """The snapshot as an image: exactly spec.STATE_BYTES, in the
        layout spec.py names. What D2 hands the Pocket's OS."""
        s = self.snapshot()
        c0, c1, c2, c3 = s["diag"]
        head = np.array([spec.STATE_MAGIC, spec.LOADER_BUILD, s["frame_no"],
                         int(s["trapped"]), s["lfsr"], c0, c1, c2, c3],
                        dtype="<u4")
        parts = [
            head.tobytes(),
            np.array(s["imem"], dtype="<u4").tobytes(),
            np.array(s["dmem"], dtype="<u4").tobytes(),
            np.array(s["phase"], dtype="<u4").tobytes(),
            np.array(s["heard"][0] + s["heard"][1], dtype="<u4").tobytes(),
            np.asarray(s["tex"]).astype("<u2").tobytes(),
            np.array([x for p in s["wav"] for x in p], dtype="<i1").tobytes(),
        ]
        blob = b"".join(parts)
        assert len(blob) == spec.STATE_BYTES, (len(blob), spec.STATE_BYTES)
        return blob

    @staticmethod
    def unpack(blob: bytes) -> dict:
        """The image back into a snapshot dict, for restore()."""
        if len(blob) != spec.STATE_BYTES:
            raise ValueError(f"a state image is {spec.STATE_BYTES} bytes, "
                             f"not {len(blob)}")
        o = 0

        def take(n, dt):
            nonlocal o
            a = np.frombuffer(blob[o:o + n * np.dtype(dt).itemsize], dt)
            o += n * np.dtype(dt).itemsize
            return a
        head = take(9, "<u4")
        if int(head[0]) != spec.STATE_MAGIC:
            raise ValueError("not a Zeta state image (bad magic)")
        imem = take(spec.IMEM_WORDS, "<u4")
        dmem = take(spec.DMEM_WORDS, "<u4")
        phase = take(spec.AU_CHANNELS, "<u4")
        heard = take(2 * spec.AU_CHANNELS, "<u4")
        tex = take(spec.TEX_PAGES * spec.TEX_STRIDE, "<u2")
        wav = take(spec.AU_CHANNELS * spec.WAV_W, "<i1")
        n = spec.AU_CHANNELS
        return {
            "frame_no": int(head[2]), "trapped": bool(head[3]),
            "imem": imem.tolist(), "dmem": dmem.tolist(),
            "tex": tex.astype(np.int64),
            "wav": [wav[i * spec.WAV_W:(i + 1) * spec.WAV_W].tolist()
                    for i in range(n)],
            "phase": phase.tolist(), "lfsr": int(head[4]),
            "heard": [heard[:n].tolist(), heard[n:].tolist()],
            "diag": tuple(int(x) for x in head[5:9]),
        }


class StateBusy(RuntimeError):
    """A snapshot asked for while a card request is in flight."""


def load_cart(path: str | Path) -> dict:
    """Accept .zol (assemble in memory) or .zc (prebuilt)."""
    path = Path(path)
    if path.suffix == ".zol":
        from . import asm
        return asm.assemble(path)
    return json.loads(path.read_text())


# Keyboard -> Pocket pad, Dvorak home position: .oeu is the d-pad (ESDF
# shape), chtn the face diamond (c on top = X, h left = Y, t bottom = B,
# n right = A), a / space the shoulders, esc / enter start & select.
# Arrows work too. Tab toggles the HUD; close the window to quit.
REWIND_FRAMES = 120           # two seconds of ring, ~17 MB of state

PAD_KEYS = [  # (pygame key name, pad bit)
    ("K_PERIOD", spec.PAD_UP), ("K_o", spec.PAD_LEFT),
    ("K_e", spec.PAD_DOWN), ("K_u", spec.PAD_RIGHT),
    ("K_UP", spec.PAD_UP), ("K_LEFT", spec.PAD_LEFT),
    ("K_DOWN", spec.PAD_DOWN), ("K_RIGHT", spec.PAD_RIGHT),
    ("K_c", spec.PAD_X), ("K_h", spec.PAD_Y),
    ("K_t", spec.PAD_B), ("K_n", spec.PAD_A),
    ("K_a", spec.PAD_L), ("K_SPACE", spec.PAD_R),
    ("K_ESCAPE", spec.PAD_START), ("K_RETURN", spec.PAD_SELECT),
]
INDICATORS = [("UP", spec.PAD_UP), ("DN", spec.PAD_DOWN),
              ("LT", spec.PAD_LEFT), ("RT", spec.PAD_RIGHT),
              ("A", spec.PAD_A), ("B", spec.PAD_B),
              ("X", spec.PAD_X), ("Y", spec.PAD_Y),
              ("L", spec.PAD_L), ("R", spec.PAD_R),
              ("ST", spec.PAD_START), ("SEL", spec.PAD_SELECT)]
LEGEND = ".OEU=DPAD C=X H=Y T=B N=A A=L SPC=R ESC=ST ENT=SEL TAB=HUD [=REWIND F5/F9=SAVE/LOAD"

# 3x5 pixel font -- this pygame build ships without its font module, so the
# HUD brings its own. Rows top to bottom, 3 bits each.
FONT = {c: g.split() for c, g in {
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
    "=": "000 111 000 111 000", "/": "001 001 010 100 100",
    "-": "000 000 111 000 000", " ": "000 000 000 000 000",
}.items()}


def draw_text(surf, x, y, text, color, px=2):
    import pygame
    for ch in text.upper():
        for ry, row in enumerate(FONT.get(ch, FONT[" "])):
            for rx, bit in enumerate(row):
                if bit == "1":
                    pygame.draw.rect(
                        surf, color, (x + rx * px, y + ry * px, px, px))
        x += 4 * px


def run(machine, name: str, scale: int = 2) -> int:
    import time

    import pygame
    try:                              # sound is best-effort on a desktop:
        pygame.mixer.pre_init(spec.SND_HZ, -16, 1, 1024)   # this pygame
    except Exception:                 # build may lack the mixer module
        pass                          # entirely (it also lacks fonts)
    pygame.init()
    try:
        screen = pygame.display.set_mode((spec.W * scale, spec.H * scale))
    except pygame.error as exc:
        print(f"REFUSED: no display ({exc})")
        return 1
    try:
        pygame.mixer.init(spec.SND_HZ, -16, 1, 1024)
        voice = pygame.mixer.Channel(0)
    except Exception:
        voice = None
        print("note: no audio device/mixer -- running silent")
    pygame.display.set_caption(f"Zeta — {name}")
    keys_by_bit = [(getattr(pygame, k), b) for k, b in PAD_KEYS]
    clock = pygame.time.Clock()
    running, frames, hud = True, 0, True
    frame_ms = []                    # rolling cost of machine.frame + render
    # ---- REWIND (spec.STATE): the console-level rewind CONSOLE.md
    # promises, on machine 1 today. Every frame's state goes into a ring
    # two seconds deep; hold [ and the machine walks back through it a
    # frame a tick, showing each frame as it was; let go and play resumes
    # from there, the frames past it discarded -- a true rewind, not a
    # replay. F5 keeps one snapshot aside, F9 returns to it. The silicon
    # machine has no snapshot yet (D2/D3); the keys do nothing there.
    from collections import deque
    can_rewind = hasattr(machine, "snapshot")
    ring: deque = deque(maxlen=REWIND_FRAMES)
    kept = None
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_TAB:
                hud = not hud
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F5 \
                    and can_rewind:
                try:
                    kept = (machine.snapshot(), machine.panel().copy())
                except StateBusy:
                    pass
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F9 \
                    and can_rewind and kept is not None:
                machine.restore(kept[0])
                ring.clear()
        pressed = pygame.key.get_pressed()
        pad = 0
        for key, bit in keys_by_bit:
            if pressed[key]:
                pad |= bit
        t0 = time.perf_counter()
        if can_rewind and pressed[pygame.K_LEFTBRACKET] and ring:
            state, shown = ring.pop()         # one frame back, and show it
            machine.restore(state)
            fb = shown
        else:
            machine.frame(pad)
            fb = machine.framebuffer()
            if voice is not None and hasattr(machine, "audio"):
                snd = pygame.mixer.Sound(buffer=machine.audio().tobytes())
                if voice.get_queue() is None:  # keep at most one queued
                    voice.queue(snd) if voice.get_busy() else voice.play(snd)
            if can_rewind:
                try:
                    ring.append((machine.snapshot(), fb.copy()))
                except StateBusy:             # a card request in flight:
                    pass                      # this frame has no entry
        frame_ms.append((time.perf_counter() - t0) * 1000)
        del frame_ms[:-30]
        surf = pygame.image.frombuffer(fb.tobytes(), (spec.W, spec.H), "RGB")
        screen.blit(pygame.transform.scale(surf, screen.get_size()), (0, 0))
        if hud:                      # bottom edge: game HUDs live at the top
            ms = sum(frame_ms) / len(frame_ms)
            top = screen.get_height() - 44
            panel = pygame.Surface((screen.get_width(), 44), pygame.SRCALPHA)
            panel.fill((0, 0, 0, 170))
            screen.blit(panel, (0, top))
            draw_text(screen, 6, top + 4,
                      f"{name}  {clock.get_fps():5.1f}/60 FPS  "
                      f"{ms:5.1f} MS/FRAME  F{frames}", (120, 255, 160))
            draw_text(screen, 6, top + 18, LEGEND, (150, 160, 180))
            x = 6
            for label, bit in INDICATORS:
                lit = pad & bit
                draw_text(screen, x, top + 32, label,
                          (90, 255, 120) if lit else (80, 88, 104))
                x += (len(label) + 1) * 8
        pygame.display.flip()
        frames += 1
        clock.tick(spec.FPS)
    pygame.quit()
    return 0


def dump(machine, frames: int, dumps: set[int], prefix: str,
         pad_fn=None) -> None:
    """Headless frames; pad_fn(frame_no) supplies input (default: none)."""
    for f in range(frames):
        machine.frame(pad_fn(f) if pad_fn else 0)
        if f in dumps:
            fb = machine.framebuffer()
            path = f"{prefix}_{f}.ppm"
            gpu.write_ppm(fb, path)
            print(f"dumped {path}")
