// server.cpp -- the silicon frame server: the Verilated zeta_top behind the
// exact protocol the pygame cabinet speaks.
//
//   argv:   imem.hex dmem.hex [cram.hex]   (8-hex-digit words, one per
//           line; the third is the cart's CRAM segment, if it has one)
//   stdin:  4 bytes LE               the pad word for the coming frame
//   stdout: ZW*ZH*3 bytes            the frame, raw RGB
//           then 800*2 bytes         the frame's 48 kHz samples, LE int16
//
// ZW/ZH arrive as -D flags from zeta/silicon.py, which reads spec.py --
// the single source of truth, as everywhere.
#include <cstdio>
#include <cstdlib>
#include "Vzeta_sim.h"
#include "Vzeta_sim___024root.h"   // (ZDBGMEM's peeks, and ZETA_SEQHIST's)
#include "verilated.h"

static Vzeta_sim* dut;
// THE FRAME METER. Enabled by the ZETA_CLK environment variable rather
// than a compile-time define, so ONE cached build serves both the gates
// and the measurement -- and so no gate's behaviour can depend on it.
// Every clock the machine spends between `start` and `frame_done` is a
// clock of the 720,000 the 60 Hz contract allows (43.2 MHz = 400*360*60*5).
static long g_clk = 0;
static void tick() {
    dut->clk = 0; dut->eval();
    dut->clk = 1; dut->eval();
    g_clk++;
}

static void boot(const char* path, int kind) {
    FILE* f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(2); }
    char line[64];
    unsigned addr = 0;
    while (fgets(line, sizeof line, f)) {
        dut->boot_kind = kind;
        dut->boot_addr = addr++;
        dut->boot_data = (unsigned)strtoul(line, nullptr, 16);
        dut->boot_we = 1;
        tick();
        dut->boot_we = 0;
        // a segment word becomes two CRAM halves (mirrored to both
        // chips); wait them out exactly as the real loader does
        long g = 40000;
        while (dut->boot_busy && g-- > 0) tick();
        if (g <= 0) { fprintf(stderr, "BOOT STUCK at %s word %u\n",
                              path, addr - 1); exit(4); }
    }
    dut->boot_we = 0;
    fclose(f);
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    if (argc < 3) { fprintf(stderr, "usage: sim imem.hex dmem.hex\n"); return 2; }
    dut = new Vzeta_sim;
    dut->rst_n = 0; dut->start = 0; dut->boot_we = 0; dut->core_en = 0;
    for (int i = 0; i < 4; i++) tick();
    dut->rst_n = 1; tick();
    // the hardware holds the CONSOLE in reset until the cart is complete,
    // while CRAM and its boot path stay awake -- boot exactly that way, or
    // a segment write that only works out of reset passes here and fails
    // on glass (build 29)
    dut->core_en = 0;
    boot(argv[1], 0);
    boot(argv[2], 1);
    if (argc > 3) boot(argv[3], 2);      // the CRAM segment
    dut->core_en = 1;                    // cart complete: run
    for (int i = 0; i < 8; i++) tick();
#ifdef ZDBGMEM
    // peeks take LOGICAL half addresses; the restride translation
    // (cram_fb.v's law) maps them to where the fabric really put them
    auto tr = [](unsigned l) { return l + 2 * (l / 126); };
    for (unsigned a = 0x2007C; a < 0x20084; a++)
        fprintf(stderr, "PB2 a=%05x c0=%04x c1=%04x\n", a,
                dut->rootp->zeta_sim__DOT__u_chip0__DOT__mem[tr(a)],
                dut->rootp->zeta_sim__DOT__u_chip1__DOT__mem[tr(a)]);
    for (unsigned a = 0x20020; a < 0x20028; a++)
        fprintf(stderr, "POSTBOOT a=%05x c0=%04x c1=%04x\n", a,
                dut->rootp->zeta_sim__DOT__u_chip0__DOT__mem[tr(a)],
                dut->rootp->zeta_sim__DOT__u_chip1__DOT__mem[tr(a)]);
#endif

    static unsigned char fbuf[ZW * ZH * 3];
    unsigned char pb[4];
    while (fread(pb, 1, 4, stdin) == 4) {
        dut->pad = pb[0] | (pb[1] << 8);
        static const bool meter = getenv("ZETA_CLK") != nullptr;
        long clk0 = g_clk;
        dut->start = 1; tick(); dut->start = 0;
        long guard = 50L * 1000 * 1000;
        // THE SEQUENCER'S STATE HISTOGRAM (frontier phase A): which of
        // zseq's states each clock of the frame was spent in, sampled here
        // in the harness -- no RTL counter, so nothing in the bitstream
        static const bool seqhist = getenv("ZETA_SEQHIST") != nullptr;
        static unsigned long hist[128], hold[16];
        if (seqhist) for (int i = 0; i < 128; i++) hist[i] = 0;
        if (seqhist) for (int i = 0; i < 16; i++) hold[i] = 0;
        while (!dut->frame_done && guard-- > 0) {
            tick();
            if (seqhist) {
                unsigned q = dut->rootp->zeta_sim__DOT__u_top__DOT__u_seq__DOT__st & 127;
                hist[q]++;
                // a hold (S_DLE 5, S_FE 40) against the rasterizer's state:
                // WHAT the held triangle is waiting behind
                unsigned g = dut->rootp->zeta_sim__DOT__u_top__DOT__u_gpu__DOT__st & 7;
                if (q == 5) hold[g]++;
                if (q == 40) hold[8 + g]++;
            }
        }
        if (seqhist) {
            fprintf(stderr, "SEQ");
            for (int i = 0; i < 128; i++) if (hist[i]) fprintf(stderr, " %d:%lu", i, hist[i]);
            fprintf(stderr, "\n");
            // gpu states: 0 idle, 1 clr, 2 wait, 3 walk, 4 flush
            fprintf(stderr, "HOLD dle");
            for (int i = 0; i < 8; i++) fprintf(stderr, " %lu", hold[i]);
            fprintf(stderr, " fe");
            for (int i = 0; i < 8; i++) fprintf(stderr, " %lu", hold[8 + i]);
            fprintf(stderr, "\n");
        }
        if (guard <= 0) { fprintf(stderr, "frame wedged\n"); return 3; }
        if (meter) {
            // meter is {blkd,seq,stall,idle,walk,clr}, six 32-bit fields
            const unsigned* m = (const unsigned*)&dut->meter;
            fprintf(stderr, "CLK %ld clr=%u walk=%u idle=%u stall=%u "
                            "seq=%u blkd=%u skp=%u evload=%u evfire=%u\n", g_clk - clk0,
                    m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
        }
#ifdef ZDBGMEM
        {
            static int fn = 0;
            fprintf(stderr, "SEGWORDS f%d w63=%08x w64=%08x w0=%08x w1=%08x\n", fn,
                dut->rootp->zeta_sim__DOT__u_top__DOT__u_vm__DOT__dmem[15616+63],
                dut->rootp->zeta_sim__DOT__u_top__DOT__u_vm__DOT__dmem[15616+64],
                dut->rootp->zeta_sim__DOT__u_top__DOT__u_vm__DOT__dmem[15616+0],
                dut->rootp->zeta_sim__DOT__u_top__DOT__u_vm__DOT__dmem[15616+1]);
            fprintf(stderr, "F%d fb0=%04x,%04x fb1=%04x,%04x "
                    "c1seg=%04x,%04x,%04x,%04x blit_on=%d "
                    "front=%d bleft=%d\n", fn++,
                    dut->rootp->zeta_sim__DOT__u_chip0__DOT__mem[0],
                    dut->rootp->zeta_sim__DOT__u_chip0__DOT__mem[1],
                    dut->rootp->zeta_sim__DOT__u_chip1__DOT__mem[0],
                    dut->rootp->zeta_sim__DOT__u_chip1__DOT__mem[1],
                    dut->rootp->zeta_sim__DOT__u_chip1__DOT__mem[0x20020 + 2 * (0x20020 / 126)],
                    dut->rootp->zeta_sim__DOT__u_chip1__DOT__mem[0x20021 + 2 * (0x20021 / 126)],
                    dut->rootp->zeta_sim__DOT__u_chip1__DOT__mem[0x20022 + 2 * (0x20022 / 126)],
                    dut->rootp->zeta_sim__DOT__u_chip1__DOT__mem[0x20023 + 2 * (0x20023 / 126)],
                    (int)dut->rootp->zeta_sim__DOT__u_top__DOT__blit_on,
                    (int)dut->rootp->zeta_sim__DOT__u_top__DOT__u_fb__DOT__front,
                    (int)dut->rootp->zeta_sim__DOT__u_top__DOT__b_left);
        }
#endif
        for (int y = 0; y < ZH; y++) {         // line-buffered readout
            dut->line_no = y;
            dut->line_req = 1; tick(); dut->line_req = 0;
            long lg = 4000;
            while (!dut->line_rdy && lg-- > 0) tick();
            if (lg <= 0) { fprintf(stderr, "line %d wedged\n", y); return 4; }
            for (int x = 0; x < ZW; x++) {
                dut->px_addr = ((y & 1) << 9) | x;
                tick();                    // registered read: one edge
                unsigned rgb = dut->px_rgb;
                int i = y * ZW + x;
                fbuf[3 * i]     = (rgb >> 16) & 0xFF;
                fbuf[3 * i + 1] = (rgb >> 8) & 0xFF;
                fbuf[3 * i + 2] = rgb & 0xFF;
            }
        }
        if (dut->cram_violation) { fprintf(stderr, "CRAM VIOLATION\n"); return 5; }
        fwrite(fbuf, 1, sizeof fbuf, stdout);
        static unsigned char abuf[800 * 2];
        for (int s = 0; s < 800; s++) {          // one tick per sample
            // THE EVENT LIST needs clocks. On glass the ticks are ~900
            // apart and a whole frame's events drain between them; here
            // they were back to back, so wait the engine out. Free when
            // a frame carries no events, which is most of them.
            long eg = 1000;
            while (dut->snd_busy && eg-- > 0) tick();
            dut->snd_tick = 1; tick(); dut->snd_tick = 0;
            unsigned v = dut->snd_sample & 0xFFFF;
            abuf[2 * s] = v & 0xFF;
            abuf[2 * s + 1] = (v >> 8) & 0xFF;
        }
        fwrite(abuf, 1, sizeof abuf, stdout);
        fflush(stdout);
    }
    delete dut;
    return 0;
}
