// tb_tape.cpp -- the recorder against the reference: zeta_tape.v with a
// model SRAM, driven by a script on stdin, its tape read back the way the
// bridge reads it and printed for tests/test_tape.py to compare with
// zeta/tape.py's encode().
//
//   B kind addr data   one word from the loader (hex)
//   R                  release the console (cart_ready)
//   P pad [gap]        one frame's pad latch, then `gap` idle clocks
//                      (default 300; 0 presses the next frame's latch
//                      against this one's accesses)
//   D n                read tape words 0..n-1 through the bridge port
//   F                  the collection has begun: freeze
//   Q                  what the recorder asked of the SRAM: accesses, and
//                      the shortest write pulse and address hold seen
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include "Vzeta_tape.h"
#include "verilated.h"

static Vzeta_tape* dut;
static uint16_t mem[1 << 17];
static long n_wr = 0, n_rd = 0, min_pulse = 1 << 30, min_hold = 1 << 30;
static long pulse = 0, since_we = -1;
static uint32_t last_a = 0;
static bool was_we = false;

static void tick() {
    // the SRAM, asynchronous: drives while OE is low and it is not written
    dut->sram_di = (!dut->sram_oe_n && dut->sram_we_n) ? mem[dut->sram_a & 0x1FFFF] : 0xDEAD;
    dut->clk = 0; dut->eval();
    dut->clk = 1; dut->eval();
    bool we = !dut->sram_we_n;
    if (we) {
        if (!dut->sram_doe) { fprintf(stderr, "WE low with the bus not driven\n"); exit(2); }
        if (was_we && (dut->sram_a != last_a)) { fprintf(stderr, "address moved under WE\n"); exit(2); }
        mem[dut->sram_a & 0x1FFFF] = dut->sram_do;
        pulse++;
    } else {
        if (was_we) { n_wr++; if (pulse < min_pulse) min_pulse = pulse; pulse = 0; since_we = 0; }
        else if (since_we >= 0) {
            if (dut->sram_a != last_a && dut->sram_doe) {       // the next write's address arrives
                if (since_we < min_hold) min_hold = since_we; since_we = -1;
            } else since_we++;
        }
    }
    if (!dut->sram_oe_n && !dut->sram_we_n) { fprintf(stderr, "OE and WE low together\n"); exit(2); }
    was_we = we; last_a = dut->sram_a;
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    dut = new Vzeta_tape;
    for (auto& w : mem) w = 0xA5A5;             // a part that powers up dirty
    dut->run = 0; dut->boot_we = 0; dut->pad_stb = 0; dut->rd_req = 0; dut->freeze = 0;
    dut->g_gnt = 1;                             // (the console never holds it here)
    for (int i = 0; i < 8; i++) tick();
    char line[256];
    while (fgets(line, sizeof line, stdin)) {
        unsigned a, b, c;
        if (line[0] == 'B' && sscanf(line + 1, "%x %x %x", &a, &b, &c) == 3) {
            dut->boot_we = 1; dut->boot_kind = a; dut->boot_addr = b; dut->boot_data = c;
            tick(); dut->boot_we = 0;
        } else if (line[0] == 'R') {
            dut->run = 1; for (int i = 0; i < 100; i++) tick();
        } else if (line[0] == 'P') {
            int n = sscanf(line + 1, "%x %u", &a, &b);
            dut->pad_stb = 1; dut->pad_word = a; tick(); dut->pad_stb = 0;
            for (unsigned i = 0; i < (n == 2 ? b : 300); i++) tick();
        } else if (line[0] == 'D' && sscanf(line + 1, "%u", &a) == 1) {
            for (int i = 0; i < 80; i++) tick();
            for (unsigned w = 0; w < a; w++) {
                int ack = dut->rd_ack;
                dut->rd_addr = w; dut->rd_req = !dut->rd_req;
                int guard = 200;
                while (dut->rd_ack == ack && guard-- > 0) { tick(); if (!dut->sram_oe_n) n_rd++; }
                if (guard <= 0) { fprintf(stderr, "read %u never answered\n", w); return 2; }
                printf("%08x\n", dut->rd_data);
            }
        } else if (line[0] == 'F') {
            dut->freeze = 1; for (int i = 0; i < 8; i++) tick();
        } else if (line[0] == 'Q') {
            printf("Q writes %ld min_pulse %ld min_hold %ld\n", n_wr, min_pulse, min_hold);
        }
    }
    delete dut;
    return 0;
}
