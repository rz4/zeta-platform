// tb_loaderglass.cpp -- stream a .zbin through the bridge at physical
// pace and prove the machine that boots from it. Two free-running
// clocks (74.25 MHz bridge, 43.2 MHz core) with no phase relationship,
// bridge writes in 128-word SD-block bursts with short gaps, and no
// waiting on anything the real OS can't see. Reports FIFO high-water
// and drops (occupancy read straight out of the model), then scans one
// frame after the 3rd vsync and writes it to stdout as raw RGB.
//
// usage: sim cart.zbin > frame.raw
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "Vloaderglass_sim.h"
#include "Vloaderglass_sim___024root.h"
#include "verilated.h"

#ifndef ZW
#define ZW 320
#endif
#ifndef ZH
#define ZH 288
#endif

static Vloaderglass_sim* dut;

// two independent clocks: half-periods in picoseconds
static const long long BHALF = 6734;    // 74.25 MHz
static const long long CHALF = 11574;   // 43.2 MHz
static long long tb = 0, tc = 0;        // next edge times
static int bv = 0, cv = 0;

static unsigned hw_mark = 0;            // FIFO high-water (words)
static long dropped = 0;

static long n_we[3] = {0, 0, 0};        // boot_we pulses seen, per kind
static int last_toggled_b = 0;          // which clock the step moved
static void step() {                    // advance to the earliest edge
    if (tb <= tc) {
        bv ^= 1; dut->bclk = bv; tb += BHALF;
        last_toggled_b = 1;
    } else {
        last_toggled_b = 0;
        cv ^= 1; dut->clk = cv; tc += CHALF;
        if (cv) {                       // cclk rising edge: sample the port
            if (dut->rootp->loaderglass_sim__DOT__cl_we) {
                int k = dut->rootp->loaderglass_sim__DOT__cl_kind;
                if (k < 3) n_we[k]++;
            }
        }
    }
    dut->eval();
}

static void bedge() {                   // to the next RISING bridge edge
    // exit ONLY on a step that toggled bclk high -- exiting whenever
    // bclk merely sat high let cclk steps eat write windows and this
    // harness silently dropped 37% of its own bridge writes
    do { step(); } while (!(last_toggled_b && bv));
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    if (argc < 2) { fprintf(stderr, "usage: sim cart.zbin\n"); return 2; }
    FILE* f = fopen(argv[1], "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", argv[1]); return 2; }
    std::vector<unsigned> words;
    unsigned w;
    while (fread(&w, 4, 1, f) == 1) words.push_back(w);
    fclose(f);
    fprintf(stderr, "streaming %zu words\n", words.size());

    dut = new Vloaderglass_sim;
    dut->brst_n = 0; dut->rst_n = 0; dut->bridge_wr = 0;
    dut->dataslot_allcomplete = 0; dut->pad = 0;
    for (int i = 0; i < 64; i++) step();
    dut->brst_n = 1; dut->rst_n = 1;
    for (int i = 0; i < 64; i++) step();

    // the OS streams the file: 128-word bursts (one SD block), one
    // write per 2 bridge clocks inside a burst, ~8 us between blocks.
    // Track FIFO occupancy from the model's own pointers.
    for (size_t i = 0; i < words.size(); i++) {
        bedge();
        dut->bridge_addr = 0x10000000u + 4u * (unsigned)i;
        dut->bridge_wr_data = words[i];
        dut->bridge_wr = 1;
        unsigned wp = dut->rootp->loaderglass_sim__DOT__u_cart__DOT__wptr;
        unsigned rp = dut->rootp->loaderglass_sim__DOT__u_cart__DOT__rptr;
        unsigned occ = (wp - rp) & 0xFFF;
        if (occ > hw_mark) hw_mark = occ;
        if (occ >= 2048) dropped++;     // a write into a full FIFO
        bedge();
        dut->bridge_wr = 0;
        static int spacing = getenv("LG_SPACE") ? atoi(getenv("LG_SPACE")) : 4;
        for (int s2 = 0; s2 < spacing; s2++) bedge();   // pace knob
        if ((i % 1024) == 1023)         // 4K read-chunk gap: the REAL
            for (int g = 0; g < 6000; g++) bedge();  // OS pauses ~40 us
                                        // here -- LONGER than any core
                                        // quiet window (boot 54's glass:
                                        // a mid-bank gap rotated a
                                        // partial flush and broke the
                                        // row alignment forever after)
        else if ((i % 128) == 127)      // SD-block gap
            for (int g = 0; g < 594; g++) bedge();   // ~4 us
    }
    dut->dataslot_allcomplete = 1;
    fprintf(stderr, "streamed; FIFO high-water %u, writes-at-full %ld\n",
            hw_mark, dropped);

    // wait for the loader to release the console
    long long guard = 400LL * 1000 * 1000;
    while (!dut->cart_ready && guard-- > 0) step();
    if (guard <= 0) { fprintf(stderr, "cart_ready NEVER ROSE\n"); return 3; }
    fprintf(stderr, "cart_ready after release; trapped=%d\n", (int)dut->trapped);
    fprintf(stderr, "boot_we pulses: kind0=%ld kind1=%ld kind2=%ld\n",
            n_we[0], n_we[1], n_we[2]);

    // the segment as it truly sits in CRAM, against the streamed truth
    {
        auto tr = [](unsigned l) { return l + 2 * (l / 126); };
        const unsigned SEGW = 20480;        // kind-2 words start here
        const unsigned BASE = 131040;       // logical half-addr of word 0
        long segbad = 0;
        for (size_t i = 0; SEGW + i < words.size(); i++) {
            unsigned p = tr(BASE + 2 * (unsigned)i);
            unsigned lo = dut->rootp->loaderglass_sim__DOT__u_chip0__DOT__mem[p];
            unsigned hi = dut->rootp->loaderglass_sim__DOT__u_chip0__DOT__mem[tr(BASE + 2 * (unsigned)i + 1)];
            unsigned got = lo | (hi << 16);
            if (got != words[SEGW + i]) {
                if (segbad < 6)
                    fprintf(stderr, "SEG MISS word %zu: got %08x want %08x\n",
                            i, got, words[SEGW + i]);
                segbad++;
            }
        }
        fprintf(stderr, "segment check: %ld bad of %zu\n",
                segbad, words.size() - SEGW);
    }
    fprintf(stderr, "loader: n_hi=%u n_out=%u rptr=%u wptr=%u\n",
            (unsigned)dut->rootp->loaderglass_sim__DOT__u_cart__DOT__n_hi,
            (unsigned)dut->rootp->loaderglass_sim__DOT__u_cart__DOT__n_out,
            (unsigned)dut->rootp->loaderglass_sim__DOT__u_cart__DOT__rptr,
            (unsigned)dut->rootp->loaderglass_sim__DOT__u_cart__DOT__wptr);
    {
        FILE* hf = fopen(getenv("LG_IMEM") ? getenv("LG_IMEM") : "/dev/null", "r");
        unsigned expw = 0; int bad = 0, checked = 0; char line[64];
        for (int i = 0; hf && fgets(line, sizeof line, hf); i++) {
            expw = (unsigned)strtoul(line, nullptr, 16);
            unsigned got = dut->rootp->
                loaderglass_sim__DOT__u_glass__DOT__u_top__DOT__u_vm__DOT__imem[i];
            if (got != expw && bad < 5)
                fprintf(stderr, "IMEM[%d] got %08x want %08x\n", i, got, expw);
            if (got != expw) bad++;
            checked++;
        }
        if (hf) { fclose(hf); fprintf(stderr, "IMEM: %d/%d bad\n", bad, checked); }
    }

    // scan the frame after the 3rd vsync
    static unsigned char fb[ZH][ZW][3];
    int vs_seen = 0, prev_vs = dut->vs;
    int x = 0, y = -1, prev_de = 0, collecting = 0, done_px = 0;
    guard = 800LL * 1000 * 1000;
    while (guard-- > 0) {
        int pc = cv;
        step();
        if (!(dut->clk && cv && !pc)) continue;   // core rising edges only
        if (!dut->ce_pix) continue;
        if (dut->vs && !prev_vs) {
            vs_seen++;
            if (vs_seen == 3) { collecting = 1; y = -1; done_px = 0; }
            else if (vs_seen > 3 && collecting) break;
        }
        prev_vs = dut->vs;
        if (collecting) {
            if (dut->de && !prev_de) { y++; x = 0; }
            if (dut->de && y >= 0 && y < ZH && x < ZW) {
                fb[y][x][0] = (dut->rgb >> 16) & 0xFF;
                fb[y][x][1] = (dut->rgb >> 8) & 0xFF;
                fb[y][x][2] = dut->rgb & 0xFF;
                x++; done_px++;
            }
            prev_de = dut->de;
        }
    }
    fprintf(stderr, "scanned %d px across %d rows\n", done_px, y + 1);
    fwrite(fb, 1, sizeof fb, stdout);
    return 0;
}
