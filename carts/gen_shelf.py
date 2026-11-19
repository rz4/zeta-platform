# gen_shelf.py -- THE SHELL (SLICE stage 3, SEAMS 2): the library cart.
#
# The shelf holds each game's images in its own CRAM segment -- the
# PROGRAM (4096 words, zero-padded), the whole INITIAL DMEM (16384
# words), and, for a game that has one, its SEGMENT -- shows a menu,
# and on a fresh press launches the chosen game with the movers: four
# DMA frames walk the DMEM image in DESCENDING blocks (so the shelf's
# own state in low cells survives until the last step), and the last
# frame rides OVL_* beside the final block, so the instant the shelf's
# program is overwritten is the instant the game's world is complete.
# The next frame is the game, from PC 0, bit-for-bit.
#
# RELOCATION (spec.SEG_BASE): a game's resources assume its segment
# starts at offset 0. The shelf knows where it actually put them, and
# writes that base into SEG_BASE on the LAUNCH'S FINAL FRAME -- during
# the VM's run, before that frame's movers fire -- so the game wakes
# with the window armed and needs no code and no knowledge. The base
# must NOT ride in the shipped DMEM image: the image lands block by
# block, the block carrying cell 12262 arrives on step 2, and a window
# armed mid-launch relocates the launch's own remaining steps. That
# bug shipped for exactly one test run.
#
# Launch timeline (a fresh press on frame F):
#   F      latched: LAUNCH = 1, the game's bases in GD/GP
#   F+1    DMA dmem[12288..16383]        (the menu vanishes here)
#   F+2    DMA dmem[8192..12287]
#   F+3    DMA dmem[4096..8191]
#   F+4    DMA dmem[0..4095]  +  OVL program
#   F+5    the game's first frame (REG_FRAME continues -- a tape
#          records the launch frame, SEAMS 2)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zeta import asm, spec                                   # noqa: E402
from zeta.forge import Cart, Table, Text                     # noqa: E402

HERE = Path(__file__).parent
cart = Cart("shelf")


def shelve(name: str):
    """Assemble a game and place its images; return (prog, dmem, base).
    A game's segment, if any, is placed first; its base is returned for
    the launch to write, never baked into the image (see above)."""
    g = asm.assemble(HERE / f"{name}.zol")
    assert not g["sd"], f"{name} uses the card -- SLOT_BASE is not law yet"
    dmem_img = [0] * spec.DMEM_WORDS
    for a, v in g["dmem"].items():
        dmem_img[int(a)] = v
    assert dmem_img[spec.SEG_BASE] == 0, \
        f"{name} sets SEG_BASE in .data; it cannot be shelved"
    base = 0
    if g["cram"]:
        top = max(int(a) for a in g["cram"])
        seg_img = [0] * (top + 1)
        for a, v in g["cram"].items():
            seg_img[int(a)] = v
        base = int(cart.cram(Table(seg_img), f"{name}_seg"))
    prog_img = list(g["imem"]) + [0] * (spec.IMEM_WORDS - len(g["imem"]))
    prog = cart.cram(Table(prog_img), f"{name}_prog")
    dmem = cart.cram(Table(dmem_img), f"{name}_dmem")
    return prog, dmem, base


TEAR_P, TEAR_D, TEAR_S = shelve("tear")
HALL_P, HALL_D, HALL_S = shelve("hall")

# ---- the menu: one merged text table, copied over the DL once -------------
lines = [Text("ZETA", 118, 80, rgb=0xE6C010, scale=4),
         Text("A  TEAR", 112, 150, rgb=0x3399FF, scale=3),
         Text("B  HALL", 112, 190, rgb=0xEE4444, scale=3)]
tris = [t for ln in lines for t in ln.tris]
menu = cart.data(Table([len(tris)] + [w for t in tris for w in t]), "menu")

L = cart.var("launch")          # 0 = menu; 1..4 = the step to run
M = cart.var("drawn")           # the menu is copied once, not per frame
PV = cart.var("prevpad")        # a FRESH press launches, a held one waits
GD = cart.var("game_dmem")      # the chosen game's image bases, latched
GP = cart.var("game_prog")      # at the press so the steps need no menu
GS = cart.var("game_seg")       # ...and its segment base, written into
                                # SEG_BASE on the final frame only

p = cart.program()
menu_l = p.label("menu")
steps_l = p.label("steps")
drawn_l = p.label("drawn")
pads_l = p.label("pads")
try_b_l = p.label("tryb")
arm_a_l = p.label("arma")
arm_b_l = p.label("armb")
done_l = p.label("done")
more_l = p.label("more")

p.load(L).emit(f"jz {menu_l}", f"jmp {steps_l}")

# ---- the menu frame -------------------------------------------------------
p.mark(menu_l)
p.load(M).emit(f"jz {drawn_l}", f"jmp {pads_l}")
p.mark(drawn_l)
p.set_text(menu, n_words=1 + len(tris) * spec.DL_STRIDE)
p.set(M, 1)
p.mark(pads_l)
p.emit("load 1", f"push {spec.PAD_A}", "and", f"jz {try_b_l}")
p.load(PV).emit(f"push {spec.PAD_A}", "and", f"jz {arm_a_l}")
p.emit(f"jmp {try_b_l}")                           # held, not fresh
p.mark(arm_a_l)
p.push(int(TEAR_D)).store(GD)
p.push(int(TEAR_P)).store(GP)
p.push(int(TEAR_S)).store(GS)
p.set(L, 1)
p.emit(f"jmp {done_l}")
p.mark(try_b_l)
p.emit("load 1", f"push {spec.PAD_B}", "and", f"jz {done_l}")
p.load(PV).emit(f"push {spec.PAD_B}", "and", f"jz {arm_b_l}")
p.emit(f"jmp {done_l}")
p.mark(arm_b_l)
p.push(int(HALL_D)).store(GD)
p.push(int(HALL_P)).store(GP)
p.push(int(HALL_S)).store(GS)
p.set(L, 1)
p.mark(done_l)
p.emit("load 1").store(PV)
p.emit("halt")

# ---- the launch steps -----------------------------------------------------
p.mark(steps_l)
# dst = 16384 - L*4096 ; src = GD + dst ; one block a frame
p.push(16384).load(L).push(4096).emit("mul", "sub")
p.emit("dup").store(spec.DMA_DST)
p.load(GD).emit("add").store(spec.DMA_SRC)
p.push(spec.DMA_MAX).store(spec.DMA_LEN)
p.set(spec.DMA_GO, 1)
p.load(L).push(4).emit("eq", f"jz {more_l}")
# the last block: the program rides the same instant, and the window is
# armed HERE -- which means THIS frame's own movers read through it too,
# so the final frame presents PRE-COMPENSATED offsets: presented + the
# window = the truth. (The segment sits below the images, so the
# compensated values stay positive; for a segmentless game GS is 0 and
# nothing moves.)
p.load(GD).load(GS).emit("sub").store(spec.DMA_SRC)   # dst is 0 here
p.load(GP).load(GS).emit("sub").store(spec.OVL_SRC)
p.set(spec.OVL_DST, 0)
p.push(spec.OVL_MAX).store(spec.OVL_LEN)
p.set(spec.OVL_GO, 1)
p.load(GS).store(spec.SEG_BASE)
p.emit("halt")
p.mark(more_l)
p.addi(L, 1)
p.emit("halt")

out = cart.write(HERE / "shelf.zol")
print(cart.report())
