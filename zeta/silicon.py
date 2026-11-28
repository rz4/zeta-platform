"""silicon.py -- the bridge to the metal.

Three jobs, all downstream of spec.py:
  gen_params()      spec.py -> silicon/gen/params.vh (the RTL's only numbers)
  build()           Verilate the core once per source hash, cache the binary
  SiliconMachine    the running core behind cabinet.py's machine interface
                    (.frame(pad) / .framebuffer()) -- the pygame cabinet and
                    the cross cannot tell it from the Python machine, which
                    is the point.
"""
from __future__ import annotations

import atexit
import hashlib
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import clip, spec

ROOT = Path(__file__).resolve().parents[1]
SIL = ROOT / "silicon"
RTL = ["zvm.v", "zimem.v", "zseq.v", "zmesh.v", "zgpu.v", "zsnd.v", "zcard.v", "cram_burst.v",
       "cram_fb.v", "zeta_top.v"]


def gen_params() -> str:
    lines = [
        "// GENERATED from zeta/spec.py -- do not edit, edit spec.py",
        f"localparam ZW = {spec.W}, ZH = {spec.H};",
        f"localparam TH = {spec.TILE_H}, TROWS = {spec.TILE_ROWS};",
        f"localparam [23:0] CLEAR_RGB = 24'h{spec.CLEAR_RGB:06X};",
        f"localparam IMEM_WORDS = {spec.IMEM_WORDS}, DMEM_WORDS = {spec.DMEM_WORDS};",
        f"localparam IMEM_BITS = {spec.IMEM_BITS};",
        f"localparam FUEL = {spec.FUEL}, STACK_MAX = {spec.STACK_MAX}, "
        f"RSTACK_MAX = {spec.RSTACK_MAX};",
        f"localparam DL_BASE = {spec.DL_BASE}, DL_STRIDE = {spec.DL_STRIDE}, "
        f"DL_MAX = {spec.DL_MAX};",
        f"localparam REG_FRAME = {spec.REG_FRAME}, REG_PAD = {spec.REG_PAD};",
        f"localparam CAM_X = {spec.CAM_X}, CAM_PITCH = {spec.CAM_PITCH};",
        f"localparam CAM_ROLL = {spec.CAM_ROLL};",
        f"localparam CO_BASE = {spec.CO_BASE}, CO_MAX = {spec.CO_MAX};",
        f"localparam OL_BASE = {spec.OL_BASE}, OL_STRIDE = {spec.OL_STRIDE}, "
        f"OL_MAX = {spec.OL_MAX};",
        f"localparam MESH_NV_MAX = {spec.MESH_NV_MAX}, "
        f"MESH_NF_MAX = {spec.MESH_NF_MAX};",
        f"localparam ZNEAR = {spec.ZNEAR}, GUARD = {spec.GUARD};",
        f"localparam AU_BASE = {spec.AU_BASE}, AU_CHANNELS = {spec.AU_CHANNELS};",
        f"localparam AU_TONE_CHANNELS = {spec.AU_TONE_CHANNELS}, AU_CLAMP = {spec.AU_CLAMP};",
        f"localparam AU_EV_BASE = {spec.AU_EV_BASE}, AU_EV_MAX = {spec.AU_EV_MAX};",
        f"localparam AU_EV_CH_SHIFT = {spec.AU_EV_CH_SHIFT}, AU_EV_CTRL_BIT = {spec.AU_EV_CTRL_BIT};",
        f"localparam DMA_SRC = {spec.DMA_SRC}, DMA_GO = {spec.DMA_GO}, "
        f"DMA_MAX = {spec.DMA_MAX};",
        f"localparam SEG_BASE = {spec.SEG_BASE};",
        f"localparam TEX_SRC = {spec.TEX_SRC}, TEX_W = {spec.TEX_W};",
        f"localparam TEX_PAGE = {spec.TEX_PAGE}, TEX_PAGES = {spec.TEX_PAGES};",
        f"localparam WAV_SRC = {spec.WAV_SRC}, WAV_W = {spec.WAV_W}, "
        f"WAV_WORDS = {spec.WAV_WORDS};",
        f"localparam WAV_PAGES = {spec.WAV_PAGES}, "
        f"AU_PAGE_SHIFT = {spec.AU_PAGE_SHIFT};",
        f"localparam CARD_DIAG = {spec.CARD_DIAG};",
        f"localparam OVL_SRC = {spec.OVL_SRC}, OVL_DST = {spec.OVL_DST}, "
        f"OVL_LEN = {spec.OVL_LEN}, OVL_GO = {spec.OVL_GO}, "
        f"OVL_MAX = {spec.OVL_MAX};",
        f"localparam FOG_RGB = {spec.FOG_RGB}, FOG_NEAR = {spec.FOG_NEAR}, "
        f"FOG_SHIFT = {spec.FOG_SHIFT};",
        f"localparam LOD_FLAT = {spec.LOD_FLAT};",
        f"localparam GAZE_BASE = {spec.GAZE_BASE}, GAZE_MAX = {spec.GAZE_MAX}, "
        f"GAZE_ANS = {spec.GAZE_ANS};",
        f"localparam OLX_PTR = {spec.OLX_PTR}, OLX_MAX = {spec.OLX_MAX}, "
        f"VISX_BASE = {spec.VISX_BASE}, "
        f"OLX_LIM = {spec.DMEM_WORDS - 1 - spec.OLX_MAX * spec.OL_STRIDE};",
        f"localparam SD_SLOT = {spec.SD_SLOT}, SD_OFF = {spec.SD_OFF}, "
        f"SD_DST = {spec.SD_DST};",
        f"localparam SD_LEN = {spec.SD_LEN}, SD_GO = {spec.SD_GO}, "
        f"SD_MAX = {spec.SD_MAX}, SD_LATENCY = {spec.SD_LATENCY};",
        f"localparam SD_READ = {spec.SD_READ}, SD_SAVE = {spec.SD_SAVE};",
        f"localparam SD_SIM_SLOTS = {spec.SD_SIM_SLOTS}, "
        f"SD_SIM_SLOT_WORDS = {spec.SD_SIM_SLOT_WORDS};",
        "localparam [1151:0] RECIP_ROM_V = {"
        + ", ".join(f"9'd{v}" for v in reversed(spec.RECIP_ROM)) + "};",
        f"localparam PICK_X = {spec.PICK_X}, PICK_Y = {spec.PICK_Y}, "
        f"PICK_ID = {spec.PICK_ID}, PICK_Z = {spec.PICK_Z};",
        f"localparam PICK_SH = {spec.PICK_SH};",
        f"localparam EDGE_RGB = {spec.EDGE_RGB};",
        f"localparam TEX_STRIDE = {spec.TEX_STRIDE};",
        f"localparam VIS_BASE = {spec.VIS_BASE};",
        f"localparam AUD_BASE = {spec.AUD_BASE};",
        f"localparam AU_RESET = {spec.AU_RESET};",
        f"localparam DMA2_SRC = {spec.DMA2_SRC}, DMA2_GO = {spec.DMA2_GO};",
        f"localparam LIGHT_DIR = {spec.LIGHT_DIR}, LIGHT_AMB = {spec.LIGHT_AMB},"
        f" LIGHT_DIF = {spec.LIGHT_DIF};",
        f"localparam GRADE_SRC = {spec.GRADE_SRC}, "
        f"GRADE_WORDS = {spec.GRADE_WORDS};",
        f"localparam CRAM_CART_BASE = {spec.CRAM_CART_BASE}, "
        f"CRAM_WORDS = {spec.CRAM_WORDS};",
        f"localparam CMESH_WORDS = {spec.CMESH_WORDS}, CM_VMAX = {spec.CM_VMAX}, "
        f"CM_FMAX = {spec.CM_FMAX};",
        f"localparam LOADER_SIG = {spec.LOADER_SIG};",
        f"localparam LOADER_BUILD = {spec.LOADER_BUILD};",
        f"localparam LOADER_SIG2 = {spec.LOADER_SIG2};",
        f"localparam BG_SRC = {spec.BG_SRC}, BG_WORDS = {spec.BG_WORDS};",
        f"localparam SUB = {spec.SUB}, ZFAR = {spec.ZFAR};",
        f"localparam SND_HZ = {spec.SND_HZ};",
        f"localparam SAMPLES_PER_FRAME = {spec.SAMPLES_PER_FRAME};",
    ]
    # ---- THE CLIPPER's five planes, straight out of zeta/clip.py ---------
    # Emitted rather than typed so the two machines cannot drift, and
    # ASSERTED into the shape zseq implements: a and b are always 0 or
    # +/-F with F a power of two (so the xy term is a shift, not a
    # multiply), only c is a general constant, and only the near plane
    # carries a d. If the law ever leaves that shape this fails loudly
    # here instead of quietly in silicon.
    assert clip.F == 1 << 12, "zseq clips with a 12-bit shift; F moved"
    cz, hasxy, isy, neg = [], 0, 0, 0
    for p, (name, a, b, c, d) in enumerate(clip.PLANES):
        assert a in (0, clip.F, -clip.F) and b in (0, clip.F, -clip.F)
        assert not (a and b), f"plane {name} has both an x and a y term"
        assert 0 < c < (1 << 16), f"plane {name}'s z coefficient outgrew 16 bits"
        assert d == (-spec.ZNEAR if p == 0 else 0), f"plane {name}'s d moved"
        cz.append(c)
        if a or b:
            hasxy |= 1 << p
            if b:
                isy |= 1 << p
            if (a or b) < 0:
                neg |= 1 << p
    # zseq multiplies c*vz as FOUR HARD-WIRED SHIFTS per plane, because a
    # general 17x32 multiply inferred three DSPs on a device with none free
    # (map said 69/66). Assert the decomposition the RTL actually wires, so
    # a coefficient that moves fails HERE and loudly -- the same precedent
    # as the FOCAL/ZSHIFT assertion below.
    CZ_SHIFTS = ((15, 11, 9, -4), (15, -11, -9, -4),
                 (15, 11, 8, -4), (15, -11, -8, -4))
    assert cz[0] == 1, "zseq wires the near plane's z coefficient as 2^0"
    for c, terms in zip(cz[1:], CZ_SHIFTS):
        assert c == sum((1 << t) if t >= 0 else -(1 << -t) for t in terms), \
            f"zseq.v's shift decomposition disagrees with the law: c={c}"
    lines += [
        "localparam [79:0] CLIP_CZ = {"
        + ", ".join(f"16'd{c}" for c in reversed(cz)) + "};",
        f"localparam [4:0] CLIP_XY = 5'b{hasxy:05b}, "
        f"CLIP_ISY = 5'b{isy:05b}, CLIP_NEG = 5'b{neg:05b};",
        f"localparam CLIP_MARGIN = {clip.CLIP_MARGIN};",
    ]
    # zseq implements x*(FOCAL<<SUB) as x<<12 and z>>ZSHIFT as bit slices;
    # the law and those shifts must agree
    assert spec.FOCAL << spec.SUB == 4096 and spec.ZSHIFT == 7, \
        "zseq.v's shift-based projection constants disagree with the law"
    for name, (code, _) in spec.OPS.items():
        lines.append(f"localparam [7:0] OP_{name.upper()} = 8'h{code:02X};")
    return "\n".join(lines) + "\n"


def gen_sinq() -> str:
    """The quarter-wave ROM, emitted from the same table the law folds."""
    lines = ["// GENERATED from zeta/spec.py SIN_QUARTER -- do not edit",
             "initial begin"]
    for i, v in enumerate(spec.SIN_QUARTER):
        lines.append(f"  sq[{i}] = {'-' if v < 0 else ''}16'sd{abs(v)};")
    lines.append("end")
    return "\n".join(lines) + "\n"


KEEP_BUILDS = 3          # sim trees to leave behind, newest first


def _prune(tmp: Path, keep: int = KEEP_BUILDS) -> None:
    """Delete all but the newest few cached builds.

    EACH ONE IS ABOUT 200 MB and the tag is a hash of the RTL, so every
    edit makes a new one and none of them is ever collected. They
    accumulated to 28 across one session and filled /tmp three separate
    times, each time as a `cannot write PCH file: Disk quota exceeded`
    in the middle of something else -- once mid-deploy, which cost a
    fit. Keeping a few means the common case (flipping between two
    versions) still hits the cache.
    """
    for pat in ("zeta-sdk-sim-*", "zeta-sdk-glass-*"):
        old = sorted(tmp.glob(pat), key=lambda q: q.stat().st_mtime,
                     reverse=True)[keep:]
        for q in old:
            shutil.rmtree(q, ignore_errors=True)


def build() -> Path:
    params = gen_params()
    gen = SIL / "gen"
    gen.mkdir(exist_ok=True)
    (gen / "params.vh").write_text(params)
    (gen / "sinq_init.vh").write_text(gen_sinq())
    blob = params + gen_sinq()
    blob += "".join((SIL / f).read_text() for f in RTL)
    blob += (SIL / "zeta_sim.v").read_text()
    blob += (SIL / "cram_sync_chip.v").read_text()
    blob += (SIL / "card_model.v").read_text()
    blob += (SIL / "sram_model.v").read_text()
    blob += (SIL / "server.cpp").read_text()
    tag = hashlib.sha256(blob.encode()).hexdigest()[:12]
    out = Path(tempfile.gettempdir()) / f"zeta-sdk-sim-{tag}"
    sim = out / "sim"
    if sim.exists():
        return sim
    _prune(out.parent)
    print("building the silicon simulation (one-time, ~30 s)...")
    cmd = ["verilator", "--cc", "--exe", "--build", "-O2", "-Wno-lint",
           "--top-module", "zeta_sim", "-Mdir", str(out), "-o", "sim",
           "-I" + str(gen),
           "-CFLAGS", f"-DZW={spec.W} -DZH={spec.H} -O2 "
                      f"-DZ_IMEM={spec.IMEM_WORDS} -DZ_DMEM={spec.DMEM_WORDS} "
                      f"-DZ_TEX={spec.TEX_PAGES * spec.TEX_STRIDE} "
                      f"-DZ_AUD={spec.AUD_BASE}",
           str(SIL / "zeta_sim.v"), str(SIL / "cram_sync_chip.v"),
           str(SIL / "card_model.v"), str(SIL / "sram_model.v"),
           *[str(SIL / f) for f in RTL], str(SIL / "server.cpp")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not sim.exists():
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        raise SystemExit("silicon build failed")
    return sim


def write_cart_hex(cart: dict, work: Path):
    """The cart as the memory images every silicon build boots from --
    IMEM, DMEM, and the CRAM segment if the cart carries one."""
    imem = list(cart["imem"]) + [0] * (spec.IMEM_WORDS - len(cart["imem"]))
    dmem = [0] * spec.DMEM_WORDS
    for a, v in cart.get("dmem", {}).items():
        dmem[int(a)] = v & spec.WORD_MASK
    ip, dp = work / "cart_imem.hex", work / "cart_dmem.hex"
    ip.write_text("\n".join(f"{w:08X}" for w in imem) + "\n")
    dp.write_text("\n".join(f"{w:08X}" for w in dmem) + "\n")
    # the card, as the models see it: slots at a fixed stride, zero
    # filled, so a read past a slot's end finds the same zeros the law
    # gives (card_model.v)
    # ALWAYS written, even for a cart with no card: card_model.v reads it
    # at time zero and a missing file takes the whole simulation down with
    # it -- which looks exactly like a broken picture, and cost a bisect
    # to find.
    sd = cart.get("sd", {})
    n_sim = spec.SD_SIM_SLOTS * spec.SD_SIM_SLOT_WORDS
    flat = [0] * n_sim
    for k, img in sd.items():
        k = int(k)
        if not 0 <= k < spec.SD_SIM_SLOTS:
            raise SystemExit(
                f"cart uses card slot {k}; the modelled card holds slots "
                f"0..{spec.SD_SIM_SLOTS - 1} (spec.SD_SIM_SLOTS)")
        if len(img) > spec.SD_SIM_SLOT_WORDS:
            raise SystemExit(
                f"card slot {k} is {len(img)} words; the modelled card "
                f"holds {spec.SD_SIM_SLOT_WORDS} (spec.SD_SIM_SLOT_WORDS)")
        for i, v in enumerate(img):
            flat[k * spec.SD_SIM_SLOT_WORDS + i] = v & spec.WORD_MASK
    (work / "cart_sd.hex").write_text(
        "\n".join(f"{w:08X}" for w in flat) + "\n")

    seg = cart.get("cram", {})
    cp = None
    if seg:
        cram = [0] * (max(int(a) for a in seg) + 1)
        for a, v in seg.items():
            cram[int(a)] = v & spec.WORD_MASK
        cp = work / "cart_cram.hex"
        cp.write_text("\n".join(f"{w:08X}" for w in cram) + "\n")
    return ip, dp, cp


def build_glass() -> Path:
    """Verilate the video head (pocket/zeta_glass.v + core) once per hash."""
    params = gen_params()
    gen = SIL / "gen"
    gen.mkdir(exist_ok=True)
    (gen / "params.vh").write_text(params)
    (gen / "sinq_init.vh").write_text(gen_sinq())
    pocket = ROOT / "pocket"
    srcs = [pocket / "glass_sim.v", pocket / "zeta_glass.v",
            SIL / "cram_sync_chip.v", SIL / "card_model.v", SIL / "sram_model.v",
            *(SIL / f for f in RTL)]
    blob = params + gen_sinq() + "".join(p.read_text() for p in srcs)
    blob += (pocket / "tb_glass.cpp").read_text()
    tag = hashlib.sha256(blob.encode()).hexdigest()[:12]
    out = Path(tempfile.gettempdir()) / f"zeta-sdk-glass-{tag}"
    sim = out / "sim"
    if sim.exists():
        return sim
    _prune(out.parent)
    print("building the video-head simulation (one-time, ~30 s)...")
    cmd = ["verilator", "--cc", "--exe", "--build", "-O2", "-Wno-lint",
           "--top-module", "glass_sim", "-Mdir", str(out), "-o", "sim",
           "-I" + str(gen),
           "-CFLAGS", f"-DZW={spec.W} -DZH={spec.H} -O2",
           *[str(p) for p in srcs], str(pocket / "tb_glass.cpp")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not sim.exists():
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        raise SystemExit("video-head build failed")
    return sim


def cram_check() -> int:
    """Verilate and run the CRAM burst-controller proof (tb_cram)."""
    srcs = [SIL / f for f in
            ("cram_pair_tb.v", "cram_burst.v", "cram_sync_chip.v")]
    blob = "".join(p.read_text() for p in srcs)
    blob += (SIL / "tb_cram.cpp").read_text()
    tag = hashlib.sha256(blob.encode()).hexdigest()[:12]
    out = Path(tempfile.gettempdir()) / f"zeta-sdk-cram-{tag}"
    sim = out / "sim"
    if not sim.exists():
        cmd = ["verilator", "--cc", "--exe", "--build", "-O2", "-Wno-lint",
               "--top-module", "cram_pair_tb", "-Mdir", str(out), "-o", "sim",
               *[str(p) for p in srcs], str(SIL / "tb_cram.cpp")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if not sim.exists():
            print(r.stderr[-1500:])
            raise SystemExit("cram testbench build failed")
    r = subprocess.run([str(sim)], capture_output=True, text=True)
    print(r.stdout.strip())
    return r.returncode


def loader_check() -> int:
    """Verilate and run the bridge->cart loader proof (pocket/tb_loader)."""
    pocket = ROOT / "pocket"
    build()                      # cart_loader.v includes params.vh too
    blob = (pocket / "cart_loader.v").read_text()
    blob += (pocket / "tb_loader.cpp").read_text()
    blob += (SIL / "gen" / "params.vh").read_text()
    tag = hashlib.sha256(blob.encode()).hexdigest()[:12]
    out = Path(tempfile.gettempdir()) / f"zeta-sdk-loader-{tag}"
    sim = out / "sim"
    if not sim.exists():
        cmd = ["verilator", "--cc", "--exe", "--build", "-O2", "-Wno-lint",
               "--top-module", "cart_loader", "-Mdir", str(out), "-o", "sim",
               "-I" + str(SIL / "gen"),
               # the release timers are legislated in real console clocks;
               # scale them down so the proof runs in seconds
               "-GQUIET_LOG=8", "-GTMO_LOG=20",
               "-CFLAGS", f"-DSIG={spec.LOADER_SIG} "
                          f"-DSIG2={spec.LOADER_SIG2} "
                          f"-DLOADER_BUILD={spec.LOADER_BUILD} "
                          f"-DZ_IMEM={spec.IMEM_WORDS} -O2",
               str(pocket / "cart_loader.v"), str(pocket / "tb_loader.cpp")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if not sim.exists():
            print(r.stderr[-1500:])
            raise SystemExit("loader testbench build failed")
    r = subprocess.run([str(sim)], capture_output=True, text=True)
    print(r.stdout.strip())
    return r.returncode


def tape_sim() -> Path:
    """Verilate the recorder's proof (pocket/tb_tape.cpp) and return it."""
    pocket = ROOT / "pocket"
    build()                      # zeta_tape.v includes params.vh
    blob = (pocket / "zeta_tape.v").read_text()
    blob += (pocket / "tb_tape.cpp").read_text()
    blob += (SIL / "gen" / "params.vh").read_text()
    tag = hashlib.sha256(blob.encode()).hexdigest()[:12]
    out = Path(tempfile.gettempdir()) / f"zeta-sdk-tape-{tag}"
    sim = out / "sim"
    if not sim.exists():
        cmd = ["verilator", "--cc", "--exe", "--build", "-O2", "-Wno-lint",
               "--top-module", "zeta_tape", "-Mdir", str(out), "-o", "sim",
               "-I" + str(SIL / "gen"), "-CFLAGS", "-O2",
               str(pocket / "zeta_tape.v"), str(pocket / "tb_tape.cpp")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if not sim.exists():
            print(r.stderr[-1500:])
            raise SystemExit("tape testbench build failed")
    return sim


def scratch(prefix: str) -> Path:
    """A work folder that does not outlive the process that made it.

    Every run on the silicon writes its cart as hex first -- tens of
    megabytes for a game with a segment -- and for months nothing removed
    them: 513 folders and 3 GB of a 7.8 GB tmpfs, found when a profile of
    one real session filled the user's quota and took the shell down with
    it. Long-lived callers (SiliconMachine, profile.cost) also remove
    theirs as soon as they are done: a pool's workers never reach atexit."""
    p = Path(tempfile.mkdtemp(prefix=prefix))
    atexit.register(shutil.rmtree, p, True)
    return p


class SiliconMachine:
    """The Verilated core, one frame per .frame() call, per the contract."""

    def __init__(self, cart: dict, state: bytes | None = None,
                 env: dict | None = None, stderr=None):
        """`state` is a ZSS0 image (cabinet.VirtualMachine.pack): the
        silicon begins there instead of at power-on. The cart still boots
        first, for its CRAM segment and its card -- pass the card as the
        session had left it (cart["sd"] = machine.vm.sd)."""
        sim = build()
        work = self._work = scratch("zeta-cart-")
        ip, dp, cp = write_cart_hex(cart, work)
        env = dict(os.environ, **(env or {}))
        if state is not None:
            (work / "state.zss").write_bytes(state)
            env["ZETA_STATE"] = str(work / "state.zss")
        self.proc = subprocess.Popen(
            [str(sim), str(ip), str(dp)] + ([str(cp)] if cp else []),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
            cwd=work, env=env)
        self._fb = np.zeros((spec.H, spec.W, 3), np.uint8)
        self._audio = np.zeros(spec.SAMPLES_PER_FRAME, np.int16)

    def frame(self, pad: int, pad2: int = 0) -> None:
        if pad2:
            # REG_PAD2 is law-first (spec.py): the silicon latch does not
            # exist yet, so a driven pad 2 here would silently diverge
            # from machine 1. Loud beats wrong.
            raise NotImplementedError(
                "pad2 reached SiliconMachine before the silicon latch "
                "build -- see spec.REG_PAD2")
        self.proc.stdin.write(struct.pack("<I", pad & 0xFFFF))
        self.proc.stdin.flush()
        n = spec.W * spec.H * 3
        na = spec.SAMPLES_PER_FRAME * 2
        data = self.proc.stdout.read(n + na)
        if len(data) < n + na:
            raise SystemExit("the silicon frame server died mid-frame")
        self._fb = np.frombuffer(data[:n], np.uint8).reshape(
            spec.H, spec.W, 3)
        self._audio = np.frombuffer(data[n:], np.int16)

    def framebuffer(self) -> np.ndarray:
        return self._fb

    def audio(self) -> np.ndarray:
        return self._audio

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.stdin.close()
            self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self._work, ignore_errors=True)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
