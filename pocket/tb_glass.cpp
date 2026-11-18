// tb_glass.cpp -- scan the video head's actual pixel stream and hand it to
// `zeta glass` for the bit-equal comparison against the virtual machine.
//
//   argv:   imem.hex dmem.hex
//   stdout: ZW*ZH*3 bytes -- the de-gated pixels of the frame scanned out
//           after the 3rd vsync (i.e. the picture of VM frame 3)
//
// This is the last simulated stop before Quartus: what comes out of here
// is, dot for dot, what zeta_glass would feed the Pocket's scaler.
#include <cstdio>
#include <cstdlib>
#include "Vglass_sim.h"
#include "verilated.h"

static Vglass_sim* dut;
static void tick() {
    dut->clk = 0; dut->eval();
    dut->clk = 1; dut->eval();
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
        // the CRAM mirror path takes hundreds of cycles per word while
        // scanout runs -- firing blind drops words (the sparse-dot room)
        long g = 4L * 1000 * 1000;
        while (dut->boot_busy && g-- > 0) tick();
        if (g <= 0) { fprintf(stderr, "BOOT STUCK kind %d word %u\n",
                              kind, addr - 1); exit(4); }
    }
    dut->boot_we = 0;
    fclose(f);
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    if (argc < 3) { fprintf(stderr, "usage: sim imem.hex dmem.hex\n"); return 2; }
    dut = new Vglass_sim;
    dut->rst_n = 0; dut->pad = 0; dut->boot_we = 0; dut->core_en = 0;
    dut->boot_done = 0;                // the cart has not arrived yet
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
    // core_top.v raises cart_ready into BOTH core_en and boot_done, so
    // raise them together here. boot_done is what releases the boot
    // path's last PARTIAL bank of CRAM words: without it the segment's
    // final N-mod-63 words stay in the accumulator and read back as
    // zeros (hall.zol: 55 black pixels at the end of row 287). The
    // quiet timer that arms the flush is 256 clocks, and the first
    // compared frame is two vsyncs away, so it lands with room to spare.
    dut->boot_done = 1;
    dut->core_en = 1;
    for (int i = 0; i < 8; i++) tick();

    static unsigned char fbuf[ZW * ZH * 3];
    long collected = -1;               // -1: not yet armed
    int vs_seen = 0, prev_vs = 0;
    long guard = 40L * 1000 * 1000;
    while (guard-- > 0) {
        int ce = dut->ce_pix;
        tick();
        if (!ce) continue;             // rgb/de/vs only advance on ce
        if (dut->vs && !prev_vs) {
            vs_seen++;
            if (vs_seen == 3) collected = 0;   // scan after the 3rd vsync
        }
        prev_vs = dut->vs;
        if (collected >= 0 && collected < ZW * ZH && dut->de) {
            fbuf[collected * 3]     = (dut->rgb >> 16) & 0xFF;
            fbuf[collected * 3 + 1] = (dut->rgb >> 8) & 0xFF;
            fbuf[collected * 3 + 2] = dut->rgb & 0xFF;
            collected++;
        }
        if (dut->cram_violation) {
            fprintf(stderr, "CRAM VIOLATION during scanout\n");
            return 5;
        }
        if (collected == ZW * ZH) {
            fwrite(fbuf, 1, sizeof fbuf, stdout);
            fflush(stdout);
            delete dut;
            return 0;
        }
    }
    fprintf(stderr, "glass wedged: vs_seen=%d collected=%ld\n",
            vs_seen, collected);
    return 3;
}
