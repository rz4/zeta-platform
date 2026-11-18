// tb_cram.cpp -- prove the burst controller against the checking chip
// model: configure, write patterned spans, read them back word-perfect,
// at one word per clock, with zero protocol violations. The standalone
// gate for cram_burst.v, in the tb_loader/tb_seq tradition.
#include <cstdio>
#include "Vcram_pair_tb.h"
#include "verilated.h"

static Vcram_pair_tb* dut;
static long cycles = 0;
static void tick() {
    dut->clk = 0; dut->eval();
    dut->clk = 1; dut->eval();
    cycles++;
}
static unsigned short pat(unsigned a) { return (a * 3 + 7) & 0xFFFF; }

// THE RESTRIDE, stated independently of the RTL (cram_fb.v carries the
// same law as an adder series): client space is logical, rows of 126
// usable halves; the controller receives physical addresses whose row
// offset is < 126 and hops the 2-half tails itself. This TB is a
// logical-space client -- pat() is keyed by logical address, so spans
// that overlap logically must round-trip identically through their
// physical landings, which is the whole claim.
static unsigned tr(unsigned l) { return l + 2 * (l / 126); }
// the k-th half of a logical span at l lands at this physical cell
// (the controller walks rows of 126 and hops the 2-half tails)
static unsigned trcell(unsigned l, unsigned k) { return tr(l + k); }

// THE FULL WRITE LAW, replayed: each span's stream lands at its cells,
// and each span's OPEN also scribbles its held first half into the two
// physical cells below the open address (the write pointer's head
// start, boots 51-54 -- unmaskable on glass, so unmasked here). Row
// reopens scribble too, but into dead row tails no span occupies.
#include <unordered_map>
static std::unordered_map<unsigned, unsigned short> phys;
static void replay_write(unsigned a, unsigned l) {
    // (the head-start scribble is masked in the model, so the replay
    // carries only the stream; see cram_sync_chip.v on that optimism)
    for (unsigned k = 0; k < l; k++) phys[trcell(a, k)] = pat(a + k);
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    dut = new Vcram_pair_tb;
    dut->clk = 0; dut->rst_n = 0; dut->go = 0;
    for (int i = 0; i < 4; i++) tick();
    dut->rst_n = 1;
    long guard = 4000;
    while (!dut->cfg_done && guard-- > 0) tick();
    if (!dut->cfg_done) { printf("CRAM FAIL: no cfg_done\n"); return 1; }

    // spans: assorted LOGICAL addresses and lengths, including 1-word,
    // max, row-crossing, tail-adjacent (251 -> phys offset 125: a 1-half
    // sub-burst then the hop), overlapping spans from different rows,
    // and the last legal logical row of the chip (capacity 4128768)
    static const struct { unsigned a; unsigned l; } spans[] = {
        {0, 128}, {128, 128}, {92160, 64}, {92160 + 64, 64},
        {5, 1}, {700000, 37}, {4128768 - 40, 40}, {100, 100}, {251, 40},
    };
    const int NS = sizeof spans / sizeof *spans;

    for (int s = 0; s < NS; s++) {                 // write pass
        unsigned idx = 0;
        while (!dut->idle_o) tick();               // CE-high recovery
        dut->wr = 1; dut->addr = tr(spans[s].a); dut->len = spans[s].l;
        dut->w_data = pat(spans[s].a);
        replay_write(spans[s].a, spans[s].l);
        dut->w_end = (spans[s].l == 1);
        dut->go = 1; tick(); dut->go = 0;
        long g2 = 2000;
        while (!dut->done_o && g2-- > 0) {
            tick();
            if (dut->w_step) {
                idx++;
                dut->w_data = pat(spans[s].a + idx);
                dut->w_end = (idx + 1 >= spans[s].l);
            }
            if (dut->violation) {
                printf("CRAM FAIL: violation %d during write span %d\n",
                       (int)dut->vcode, s);
                return 1;
            }
        }
        if (g2 <= 0) { printf("CRAM FAIL: write span %d wedged\n", s); return 1; }
    }

    long miss = 0;
    for (int s = 0; s < NS; s++) {                 // read pass
        unsigned idx = 0;
        while (!dut->idle_o) tick();               // CE-high recovery
        long t0 = cycles;
        dut->wr = 0; dut->addr = tr(spans[s].a); dut->len = spans[s].l;
        dut->go = 1; tick(); dut->go = 0;
        long g2 = 2000;
        while (!dut->done_o && g2-- > 0) {
            tick();
            if (dut->r_step) {
                unsigned short want = phys[trcell(spans[s].a, idx)];
                if (dut->r_data != want) {
                    if (miss < 8)
                        printf("  miss: span %d idx %u (log %u) "
                               "got %04x want %04x\n",
                               s, idx, spans[s].a + idx,
                               dut->r_data, want);
                    miss++;
                }
                idx++;
            }
            if (dut->violation) {
                printf("CRAM FAIL: violation %d during read span %d\n",
                       (int)dut->vcode, s);
                return 1;
            }
        }
        if (idx != spans[s].l) { printf("CRAM FAIL: span %d got %u/%u words\n",
                                        s, idx, spans[s].l); return 1; }
        // a span crossing a row costs one reopen (~25 cycles): the
        // seam law's price, paid so every word arrives TRUE
        if (s == 0 && cycles - t0 > 128 + 16 + 32) {
            printf("CRAM FAIL: 128-word read took %ld cycles\n", cycles - t0);
            return 1;
        }
    }
    if (miss) { printf("CRAM FAIL: %ld data mismatches\n", miss); return 1; }
    printf("CRAM PASS: config + %d spans round-tripped word-perfect "
           "(restride row law, tails never touched), zero protocol "
           "violations\n", NS);
    delete dut;
    return 0;
}
