"""THE METER AS AN OBSERVER. The rank's wiring (TND-PORT P94), put on an OLDER commit's generator so that it pays the
meter and shows nothing: a tape then replays on that build exactly as it was played (read.py checks it, frame by
frame, against the build kept with the tape), and the meter reads the session that HAPPENED -- not his presses on
a later game.

    git show COMMIT:games/tnd/gen_tnd.py > OLD.py
    python3 experiments/rank/observe.py OLD.py games/tnd/_gen_obs_tmp.py
    TND_LAYER=13 TND_OUT=OBS.zol python3 games/tnd/_gen_obs_tmp.py && rm games/tnd/_gen_obs_tmp.py

(the routines are taken from the working tree's generator, so run it on the branch that has P94)"""
import sys
src, dst = sys.argv[1:3]
s = open(src).read()
cur = open("games/tnd/gen_tnd.py").read()
def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:80])
    s = s.replace(old, new)
has_bx = "YBX" in s
# cells
rep('''        YCON = cart.var("yard_struck_by")''', '''        YWAY, YSV, YLST, YLSL, YPV, YPS = (cart.var("yard_" + k_) for k_ in ("way", "way_worth", "way_stance", "lance_slide", "pay", "pay_stance"))
        YSVT = cart.data(Table([22, 18, 34, 46, 40]), "yard_worth_of")
        S_MULTY = cart.data(Table([20, 12, 4]), "s_mult_yard")
        L_YPAY, L_YWF, L_YWR = p.label("yardpay"), p.label("yardwayfist"), p.label("yardwayround")
        YCH, YPB = cart.var("yard_way_charged"), cart.var("yard_pay_blow")
        YCON = cart.var("yard_struck_by")''')
# the routines, as the branch has them
a = cur.index("            def yard_pay_emit(g_):"); b = cur.index("            yard_pay_emit(p)\n", a) + len("            yard_pay_emit(p)\n")
rt = cur[a:b]
if not has_bx:
    for ln in ('''                g_.load(YBX).emit(f"jz {yp}_wb")\n''', '''                g_.mark(f"{yp}_wb")\n'''):
        assert rt.count(ln) == 1; rt = rt.replace(ln, "")
    a2 = rt.index("                g_.load(YBX).push(BURST_SLAM)"); rt = rt[:a2] + rt[rt.index("\n", a2) + 1:]
rep('''            yard_ai_emit()
            yard_pose_emit()
''', '''            yard_ai_emit()
            yard_pose_emit()
''' + rt)
# a blow of theirs on him
rep('''            p.load(PHP).load(W["dmg"]).emit("sub").store(PHP)
            # P73 ("we have to make things feel epic and like damage is being done''', '''            p.load(PHP).load(W["dmg"]).emit("sub").store(PHP)
            p.load(SY["pts"]).push(int(round(0.45 * ONE))).emit("mulq").store(SY["pts"])
            p.set(SY["combo"], 0).set(YLST, 0)
            for i_ in range(5):
                p.set(int(S_REC) + i_, 255)
            # P73 ("we have to make things feel epic and like damage is being done''')
# a fist, or the run's body, on a body
rep('''                p.addi(F["stop"], 6).set(F["shake"], 12)
                p.mark(f"{fn_}_nk")
''', '''                p.addi(F["stop"], 6).set(F["shake"], 12)
                p.mark(f"{fn_}_nk")
                p.emit(f"call {L_YWF}")
''')
# a round on a body
rep('''                if YARD:
                    p.set(int(YZP) + e_["k"], 1)
                # (P44: a round into a body already DOWN does not stand it up to fall again)''', '''                if YARD:
                    p.set(int(YZP) + e_["k"], 1)
                    bf("hit")
                    p.emit("shr 4").push(1).emit("and").store(YCH)
                    p.emit(f"call {L_YWR}")
                # (P44: a round into a body already DOWN does not stand it up to fall again)''')
if has_bx:
    rep('''            p.set(YLN, 0).push(SLIDE_MIN + 1).load(F["spd"])''', '''            p.set(YLN, 0).set(YLSL, 30).push(SLIDE_MIN + 1).load(F["spd"])''')
    rep('''        p.mark(f"{rj}_bx")
        p.set(YBX, 0)
        p.mark(f"{rj}_bk")''', '''        p.mark(f"{rj}_bx")
        p.set(YBX, 0)
        p.mark(f"{rj}_bk")
        p.load(YLSL).emit(f"jz {rj}_ls")
        p.addi(YLSL, -1)
        p.mark(f"{rj}_ls")''')
rep('''p = Tee(p_main, q, pz)               # ...and from here, the shared frame''', '''if YARD:
    yard_pay_emit(q)
    yard_pay_emit(pz)
p = Tee(p_main, q, pz)               # ...and from here, the shared frame''')
open(dst, "w").write(s)
print("patched", src, "| the dive's bursts:", has_bx)
