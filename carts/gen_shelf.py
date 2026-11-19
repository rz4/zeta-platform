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

from zeta import spec                                        # noqa: E402
from zeta.forge import Cart, Table, Text                     # noqa: E402

HERE = Path(__file__).parent
cart = Cart("shelf")

# NESTING. The shelf may itself run inside a window -- the boot film
# launches it through one. Two consequences, both handled below: the
# game's window is the shelf's window PLUS the game's base, and the
# shelf's window must be RESTORED at the top of every launch step,
# because the game's DMEM image lands block by block and the block
# carrying SEG_BASE (holding the game's 0) arrives at step 2. At top
# level the window is 0 either way, which is why nothing caught this
# until a shelf ran inside one.

TEAR_P, TEAR_D, TEAR_S = cart.shelve(HERE / "tear.zol")
HALL_P, HALL_D, HALL_S = cart.shelve(HERE / "hall.zol")
TND_P, TND_D, TND_S = cart.shelve(HERE / "tnd.zol")

# ---- the menu: one merged text table, copied over the DL once -------------
lines = [Text("ZETA", 118, 60, rgb=0xE6C010, scale=4),
         Text("A  TEAR", 112, 120, rgb=0x3399FF, scale=3),
         Text("B  HALL", 112, 160, rgb=0xEE4444, scale=3),
         Text("X  TND", 112, 200, rgb=0xE8E8E8, scale=3)]
tris = [t for ln in lines for t in ln.tris]
menu = cart.data(Table([len(tris)] + [w for t in tris for w in t]), "menu")

L = cart.var("launch")          # 0 = menu; 1..4 = the step to run
M = cart.var("drawn")           # the menu is copied once, not per frame
PV = cart.var("prevpad")        # a FRESH press launches, a held one waits
GD = cart.var("game_dmem")      # the chosen game's image bases, latched
GP = cart.var("game_prog")      # at the press so the steps need no menu
GS = cart.var("game_seg")       # ...and its segment base, written into
                                # SEG_BASE on the final frame only
SV = cart.var("saved_window")   # the shelf's OWN window, saved at the
                                # press and restored every step
for v in (L, GD, GP, GS, SV):   # the launch's state must outlive every
    assert int(v) < 4096, (     # block but the last, which lands dmem
        f"launch cell {int(v)} would be overwritten mid-launch")   # 0..4095

p = cart.program()
menu_l = p.label("menu")
steps_l = p.label("steps")
drawn_l = p.label("drawn")
pads_l = p.label("pads")
try_b_l = p.label("tryb")
arm_a_l = p.label("arma")
arm_b_l = p.label("armb")
try_x_l = p.label("tryx")
arm_x_l = p.label("armx")
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
p.load(spec.SEG_BASE).store(SV)
p.push(int(TEAR_D)).store(GD)
p.push(int(TEAR_P)).store(GP)
p.push(int(TEAR_S)).store(GS)
p.set(L, 1)
p.emit(f"jmp {done_l}")
p.mark(try_b_l)
p.emit("load 1", f"push {spec.PAD_B}", "and", f"jz {try_x_l}")
p.load(PV).emit(f"push {spec.PAD_B}", "and", f"jz {arm_b_l}")
p.emit(f"jmp {done_l}")
p.mark(try_x_l)
p.emit("load 1", f"push {spec.PAD_X}", "and", f"jz {done_l}")
p.load(PV).emit(f"push {spec.PAD_X}", "and", f"jz {arm_x_l}")
p.emit(f"jmp {done_l}")
p.mark(arm_x_l)
p.load(spec.SEG_BASE).store(SV)
p.push(int(TND_D)).store(GD)
p.push(int(TND_P)).store(GP)
p.push(int(TND_S)).store(GS)
p.set(L, 1)
p.emit(f"jmp {done_l}")
p.mark(arm_b_l)
p.load(spec.SEG_BASE).store(SV)
p.push(int(HALL_D)).store(GD)
p.push(int(HALL_P)).store(GP)
p.push(int(HALL_S)).store(GS)
p.set(L, 1)
p.mark(done_l)
p.emit("load 1").store(PV)
p.emit("halt")

# ---- the launch steps -----------------------------------------------------
p.mark(steps_l)
p.load(SV).store(spec.SEG_BASE)        # the window, restored (NESTING)
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
p.load(SV).load(GS).emit("add").store(spec.SEG_BASE)   # nests: the
p.emit("halt")                         # game's window is inside ours
p.mark(more_l)
p.addi(L, 1)
p.emit("halt")

out = cart.write(HERE / "shelf.zol")
print(cart.report())
