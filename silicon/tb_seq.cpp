// tb_seq.cpp -- zseq alone against a C-modeled DMEM: feed it a dmem image,
// print every triangle it emits. `zeta`'s python side generates the image
// and diffs the stream against gpu.py's _geom -- the sequencer's own
// bit-equal harness, one level below the full-machine cross.
//
//   argv: dmem.hex (4096 lines)   stdout: one "x0 y0 x1 y1 x2 y2 rgb" per tri
#include <cstdio>
#include <cstdlib>
#include "Vzseq.h"
#include "verilated.h"

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    if (argc < 2) { fprintf(stderr, "usage: sim dmem.hex\n"); return 2; }
    static unsigned mem[4096];
    FILE* f = fopen(argv[1], "r");
    char line[64];
    unsigned n = 0;
    while (n < 4096 && fgets(line, sizeof line, f))
        mem[n++] = (unsigned)strtoul(line, nullptr, 16);
    fclose(f);

    Vzseq* dut = new Vzseq;
    dut->clk = 0; dut->rst_n = 0; dut->start = 0; dut->tri_rdy = 1;
    dut->rd_data = 0;
    for (int i = 0; i < 4; i++) { dut->clk = !dut->clk; dut->eval(); }
    dut->rst_n = 1;
    dut->start = 1;
    long guard = 4L * 1000 * 1000;
    unsigned q = 0;                       // the registered ext_rdata model
    while (guard-- > 0) {
        unsigned addr = dut->rd_addr & 4095;   // address BEFORE the edge
        dut->rd_data = q;
        dut->clk = 0; dut->eval();
        dut->clk = 1; dut->eval();
        dut->start = 0;
        q = mem[addr];                    // eq <= dmem[old addr]
        if (dut->tri_go)
            printf("%d %d %d %d %d %d %06X\n",
                   (int)dut->tx0, (int)dut->ty0, (int)dut->tx1,
                   (int)dut->ty1, (int)dut->tx2, (int)dut->ty2, dut->trgb);
        if (dut->done) { delete dut; return 0; }
    }
    fprintf(stderr, "zseq wedged\n");
    return 3;
}
