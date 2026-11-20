"""cli.py -- the `zeta` command, the SDK's front door.

    zeta build games/mine/mine.zol       .zol -> .zc cart
    zeta run   mine                      play it (pygame, 60 fps)
    zeta dump  mine -f 120 -a 0,60,119   headless frames -> PPM
    zeta cross mine                      virtual vs silicon, bit-exact

A cart is named by its PATH or just its NAME: zeta/carts.py knows where
every cart lives (carts/witness, carts/probes, carts/examples,
carts/system, games/<name>).

`run` and `dump` take either .zol (assembled on the fly) or .zc.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="zeta", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build", help=".zol -> .zc")
    p.add_argument("src")
    p.add_argument("-o", "--out")

    p = sub.add_parser("run", help="play a cart in the pygame cabinet")
    p.add_argument("cart")
    p.add_argument("--scale", type=int, default=2)
    p.add_argument("--backend", choices=("virtual", "silicon"), default="virtual")

    p = sub.add_parser("dump", help="headless frames to PPM")
    p.add_argument("cart")
    p.add_argument("-f", "--frames", type=int, default=60)
    p.add_argument("-a", "--at", default="0", help="comma list of frames to dump")
    p.add_argument("-o", "--prefix", default="frame")

    p = sub.add_parser("cross", help="virtual vs silicon bit-exact check")
    p.add_argument("cart")
    p.add_argument("-f", "--frames", type=int, default=60)

    p = sub.add_parser("glass", help="video head: scanned pixels vs virtual")
    p.add_argument("cart")

    p = sub.add_parser("witness",
                       help="the screenshot gate: a Pocket capture vs the law")
    p.add_argument("cart")
    p.add_argument("shot", help="Menu+Start capture (PNG/PPM, 1x or integer scale)")
    p.add_argument("-f", "--frames", type=int, default=600,
                   help="search this many frames for the match")
    p.add_argument("--at", type=int, default=None,
                   help="the exact frame instead of a search")
    p.add_argument("--tape", default=None,
                   help="pad-log tape driving the replay (one word a line)")
    p.add_argument("--diff", default=None,
                   help="write the closest frame with differing pixels marked")

    p = sub.add_parser("sd", help="the card ferry: push the build, pull shots")
    p.add_argument("action", choices=("push", "shots", "witness", "tape"))
    p.add_argument("cart", nargs="?", default=None,
                   help="witness only: the cart the capture came from")
    p.add_argument("--card", default=None, help="card mountpoint (default: find it)")
    p.add_argument("--staged", default=None,
                   help="push: the staged folder (default: build/pocket)")
    p.add_argument("-n", type=int, default=1, help="shots: how many, newest first")
    p.add_argument("-f", "--frames", type=int, default=600,
                   help="witness: search this many frames")
    p.add_argument("--tape", default=None, help="witness: pad-log tape")
    p.add_argument("--diff", default=None, help="witness: write marked diff PPM")

    p = sub.add_parser("replay", help="a recorded session again, on the "
                                      "reference machine")
    p.add_argument("tape", help="a .ztp from the Pocket, or a text tape")
    p.add_argument("game", help="what it was played on: the .zbin from the "
                                "card (exact), or a cart by name or path")
    p.add_argument("--card", default=None,
                   help="the save the session started with (a card*.bin, "
                        "or a folder of them); blank if not given")
    p.add_argument("--expect", default=None,
                   help="the save the Pocket was left with: the replay "
                        "must write the same words")
    p.add_argument("--shot", default=None, help="write the last frame here (.ppm)")

    p = sub.add_parser("profile", help="what a recorded session cost, frame "
                                       "by frame, on the silicon meter")
    p.add_argument("tape", help="a .ztp from the Pocket, or a text tape")
    p.add_argument("game", help="the .zbin from the card, or a cart by name or path")
    p.add_argument("--card", default=None, help="the save the session started with")
    p.add_argument("--window", type=int, default=240,
                   help="frames a window (each starts from the law's state)")
    p.add_argument("-j", "--jobs", type=int, default=None)
    p.add_argument("--csv", default=None, help="write every frame's row here")

    p = sub.add_parser("stage", help="a card folder: one file a game, "
                                     "chosen in the Pocket's own menu")
    p.add_argument("games", nargs="+", metavar="[TITLE=]CART",
                   help="a cart by name or path; TITLE is what the "
                        "Pocket's browser shows (default: the cart's name)")
    p.add_argument("--core", default="build/pocket",
                   help="a staged folder to take the core from")
    p.add_argument("--out", default="build/menu")
    p.add_argument("--no-film", action="store_true",
                   help="boot straight into each game, without the film")

    p = sub.add_parser("budget", help="the frame-budget gate: does it fit 60?")
    p.add_argument("carts", nargs="*", help="default: every suite cart")
    p.add_argument("-f", "--frames", type=int, default=10)

    p = sub.add_parser("suite", help="the standing gate: every subsystem")
    p.add_argument("--gate", choices=("glass", "cross", "both"),
                   default="both")
    p.add_argument("-f", "--frames", type=int, default=120,
                   help="cross frames per cart")
    p.add_argument("-j", "--jobs", type=int, default=8)
    p.add_argument("--witness-only", action="store_true",
                   help="machine 1 only: does each cart exercise its claim?")
    p.add_argument("--glass-queue", action="store_true",
                   help="which claims have never been seen on the real "
                        "panel (burn down with: sd push, Menu+Start, "
                        "sd witness)")

    p = sub.add_parser("deploy", help="package an openFPGA core for the Pocket")
    p.add_argument("cart")
    p.add_argument("-o", "--out")

    p = sub.add_parser("mesh", help="bake an .obj into GEOM .data blocks")
    p.add_argument("obj")
    p.add_argument("--base", type=int, default=32)
    p.add_argument("--height", type=float, default=1.0)
    p.add_argument("--tint", default="D2C8BE", help="hex base color")
    p.add_argument("--words", type=int, default=1400, help="DMEM budget")

    args = ap.parse_args(argv)

    if args.cmd == "build":
        from . import asm
        asm.build(args.src, args.out)
        return 0

    if args.cmd == "budget":
        from . import budget
        return budget.run(args.carts or None, args.frames)

    if args.cmd == "suite":
        from . import suite
        if args.glass_queue:
            return suite.glass_queue()
        if args.witness_only:
            bad = suite.check_witnesses()
            for b in bad:
                print(f"  {b}")
            print(f"{len(suite.CLAIMS) - len(bad)}/{len(suite.CLAIMS)} "
                  f"carts witness their own claim")
            return 1 if bad else 0
        gates = ("glass", "cross") if args.gate == "both" else (args.gate,)
        return suite.run(gates, frames=args.frames, jobs=args.jobs)

    if args.cmd == "mesh":
        from . import meshtool
        tint = tuple(int(args.tint[i:i + 2], 16) for i in (0, 2, 4))
        verts, faces = meshtool.load_obj(args.obj)
        blocks = meshtool.bake(verts, faces, tint=tint, height=args.height,
                               max_words=args.words)
        lines, bases, total = meshtool.data_lines(blocks, args.base)
        print("\n".join(lines))
        print(f"; {total} words, chunk base(s) {bases} -- point your "
              f"object-list entries here")
        return 0

    if args.cmd == "replay":
        import struct
        import time
        from . import cabinet, carts, deploy, tape as ztape
        if args.game.endswith(".zbin"):
            cart = deploy.read_zbin(Path(args.game))
        else:
            cart = cabinet.load_cart(carts.resolve(args.game))
        if args.card:
            cart["sd"] = deploy.card_images(Path(args.card))
        blob = Path(args.tape).read_bytes()
        pads = ztape.read(args.tape)
        if blob[:4] == struct.pack("<I", ztape.MAGIC):
            why = ztape.check(ztape.decode(blob)[0], cart)
            if why:
                print(f"NOT THIS GAME: {why}")
                return 1
        t0 = time.time()

        def each(f, m):
            if f % 600 == 599:
                print(f"  frame {f + 1:,} of {len(pads):,} "
                      f"({(f + 1) / (time.time() - t0):.0f} a second)", flush=True)
        m = ztape.replay(cart, pads, each)
        print(f"replayed {len(pads):,} frames; the machine "
              f"{'TRAPPED' if getattr(m.vm, 'trapped', False) else 'ran clean'}")
        for slot, img in sorted(m.vm.sd.items()):
            print(f"  card slot {slot}: {len(img)} words  "
                  f"{' '.join(f'{w:08x}' for w in img[:8])}")
        if args.shot:
            from . import gpu
            gpu.write_ppm(m.framebuffer(), args.shot)
            print(f"  last frame: {args.shot}")
        if args.expect:
            want = deploy.card_images(Path(args.expect))
            bad = 0
            for slot, img in sorted(want.items()):
                got = list(m.vm.sd.get(slot, []))
                n = max(len(got), len(img))
                a = got + [0] * (n - len(got))
                b = list(img) + [0] * (n - len(img))
                diff = [i for i in range(n) if a[i] != b[i]]
                bad += len(diff)
                print(f"  slot {slot}: " + ("the save the Pocket wrote, word for word"
                      if not diff else f"{len(diff)} word(s) differ, first at {diff[0]}: "
                      f"replay {a[diff[0]]:08x}, Pocket {b[diff[0]]:08x}"))
            print("REPLAY PASS" if not bad else "REPLAY FAIL: the desktop's session "
                  "is not the Pocket's (a different starting save, or a divergence)")
            return 1 if bad else 0
        return 0

    if args.cmd == "profile":
        import time
        from . import cabinet, carts, deploy, profile, tape as ztape
        if args.game.endswith(".zbin"):
            cart = deploy.read_zbin(Path(args.game))
        else:
            cart = cabinet.load_cart(carts.resolve(args.game))
        if args.card:
            cart["sd"] = deploy.card_images(Path(args.card))
        pads = ztape.read(args.tape)
        t0 = time.time()
        rows = profile.profile(
            cart, pads, args.window, args.jobs,
            say=lambda i, n: print(f"  window {i} of {n} ({time.time() - t0:.0f} s)",
                                   flush=True))
        print(profile.report(rows))
        if args.csv:
            keys = ["frame", "clk", *profile.STAGES]
            Path(args.csv).write_text("\n".join(
                [",".join(keys)] + [",".join(str(r.get(k, "")) for k in keys)
                                    for r in rows]) + "\n")
            print(f"  every frame: {args.csv}")
        return 0

    if args.cmd == "stage":
        from . import carts, deploy
        games = {}
        for g in args.games:
            title, _, ref = g.rpartition("=")
            path = carts.resolve(ref)
            games[title or path.stem] = path
        for f in deploy.stage_menu(Path(args.out), games, Path(args.core),
                                   film=not args.no_film):
            print(f"  {f.name:28s} {f.stat().st_size:>10,} bytes")
        print(f"staged {len(games)} game(s) in {args.out}: "
              f"zeta sd push --staged {args.out}")
        return 0

    if args.cmd == "sd":
        from . import sdcard
        card = sdcard.find_card(args.card)
        if args.action == "push":
            return (sdcard.push(card, Path(args.staged)) if args.staged
                    else sdcard.push(card))
        if args.action == "shots":
            sdcard.shots(card, args.n)
            return 0
        if args.action == "tape":       # the recorded session, brought home
            from . import cabinet, carts
            cart = cabinet.load_cart(carts.resolve(args.cart)) if args.cart else None
            return 0 if sdcard.tape(card, cart=cart) else 1
        # witness: the newest capture, straight into the gate
        if not args.cart:
            raise SystemExit("zeta sd witness CART -- name the cart the "
                             "capture came from")
        from . import cabinet, carts, witness as wit
        shot_path = sdcard.shots(card, 1)[0]
        tape = wit.read_tape(args.tape) if args.tape else None
        return wit.witness(cabinet.load_cart(carts.resolve(args.cart)),
                           wit.read_shot(shot_path), args.frames,
                           tape, None, args.diff,
                           capture=wit.capture_for(shot_path))

    from . import cabinet, carts
    args.cart = str(carts.resolve(args.cart))    # a path, or just a name
    cart = cabinet.load_cart(args.cart)
    name = Path(args.cart).stem

    if args.cmd == "run":
        if args.backend == "silicon":
            from . import silicon
            machine = silicon.SiliconMachine(cart)
        else:
            machine = cabinet.VirtualMachine(cart)
        return cabinet.run(machine, f"{name} [{args.backend}]", args.scale)

    if args.cmd == "dump":
        dumps = {int(t) for t in args.at.split(",")}
        cabinet.dump(cabinet.VirtualMachine(cart), args.frames, dumps, args.prefix)
        return 0

    if args.cmd == "witness":
        from . import witness as wit
        tape = wit.read_tape(args.tape) if args.tape else None
        shot = wit.read_shot(args.shot)
        return wit.witness(cart, shot, args.frames, tape, args.at, args.diff,
                           capture=wit.capture_for(args.shot))

    if args.cmd == "cross":
        import numpy as np
        from . import gpu, silicon
        virt = cabinet.VirtualMachine(cart)
        sil = silicon.SiliconMachine(cart)
        for f in range(args.frames):
            pad = (f >> 2) & 0x1F         # deterministic wiggle: 4 dirs + A
            virt.frame(pad)
            sil.frame(pad)
            a, b = virt.framebuffer(), sil.framebuffer()
            if not np.array_equal(a, b):
                n = int((a != b).any(axis=2).sum())
                gpu.write_ppm(a, f"cross_virtual_{f}.ppm")
                gpu.write_ppm(b, f"cross_silicon_{f}.ppm")
                print(f"CROSS FAIL at frame {f}: {n} pixels differ "
                      f"(dumped cross_*_{f}.ppm)")
                return 1
            if not np.array_equal(virt.audio(), sil.audio()):
                d = int((virt.audio() != sil.audio()).sum())
                print(f"CROSS FAIL at frame {f}: {d} audio samples differ")
                return 1
        sil.close()
        print(f"CROSS PASS: {args.frames} frames, virtual and silicon "
              f"framebuffers AND sample streams bit-equal ({spec_str()})")
        return 1 if args.frames == 0 else 0

    if args.cmd == "glass":
        return glass_check(cart)

    if args.cmd == "deploy":
        from . import deploy, silicon
        print("deploy gate 1/3: cross")
        if main(["cross", args.cart, "-f", "120"]) != 0:
            return 1
        print("deploy gate 2/3: glass")
        if glass_check(cart) != 0:
            return 1
        print("deploy gate 3/3: loader")
        if silicon.loader_check() != 0:
            return 1
        return deploy.run(cart, name, Path(args.out) if args.out else None)
    return 0


def glass_check(cart: dict) -> int:
    """The scanned-out pixel stream must equal the virtual frame, bit for
    bit -- the same contract as cross, one stage closer to the panel."""
    import subprocess
    import tempfile

    import numpy as np

    from . import cabinet, gpu, silicon, spec
    sim = silicon.build_glass()
    work = Path(tempfile.mkdtemp(prefix="zeta-glass-"))
    ip, dp, cp = silicon.write_cart_hex(cart, work)
    r = subprocess.run([str(sim), str(ip), str(dp)] + ([str(cp)] if cp else []),
                       capture_output=True, cwd=work)
    n = spec.W * spec.H * 3
    if len(r.stdout) != n:
        print(r.stderr.decode()[-500:])
        print("GLASS FAIL: no full frame scanned out")
        return 1
    scanned = np.frombuffer(r.stdout, np.uint8).reshape(spec.H, spec.W, 3)
    # The display is double-buffered: a frame that paints past vblank
    # holds its swap, so the scan after vsync 3 legally shows VM frame 3
    # (paint fit in vblank) or frame 2 (it ran long). The invariant is
    # that the panel shows a COMPLETE frame, bit-equal to the machine --
    # never a torn or corrupted one.
    # the cabinet is the lawful reference: it runs the mover and hands
    # the CRAM segment to render -- raw vm+render here silently dropped
    # the backdrop and failed every blit cart against a bare clear
    m = cabinet.VirtualMachine(cart)
    goldens = {}
    for n in (1, 2, 3):
        m.frame(0)
        if n >= 2:
            # PANEL, not framebuffer: the scanout compositor blends on the
            # way out and never touches CRAM, so this gate -- the one that
            # models scanout -- is the one that sees it. cross compares
            # framebuffers and is correctly blind (spec.CO_BASE).
            goldens[n] = m.panel()
    for n, golden in goldens.items():
        if np.array_equal(scanned, golden):
            lag = "in vblank" if n == 3 else "held one frame (long paint)"
            print(f"GLASS PASS: scanned frame bit-equal to VM frame {n} "
                  f"-- swap {lag} (60 Hz, 400x360 total, 320x288 active)")
            return 0
    diff = int((scanned != goldens[3]).any(axis=2).sum())
    gpu.write_ppm(scanned, "glass_scanned.ppm")
    gpu.write_ppm(goldens[3], "glass_golden.ppm")
    print(f"GLASS FAIL: matches no complete VM frame "
          f"({diff} px vs frame 3; dumped glass_*.ppm)")
    return 1


def spec_str() -> str:
    from . import spec
    return f"{spec.W}x{spec.H}x24"


if __name__ == "__main__":
    raise SystemExit(main())
