// tb_loader.cpp -- prove the bridge -> cart path before it exists in a
// bitstream: two free-running clocks at the real 74.25/43.2 ratio, 20480
// bridge writes of a known pattern (SPI-paced at the head and tail,
// physical-maximum bursts through the middle -- boot 17's lesson), a
// volley of FOREIGN low-window writes that must be ignored (boot 18's
// lesson), then the boot-port stream must reproduce every word at the
// right address, in the right memory, sign its delivery at LOADER_SIG,
// and raise cart_ready only after all of it.
#include <cstdio>
#include <cstring>
#include "Vcart_loader.h"
#include "verilated.h"

static Vcart_loader* dut;
static unsigned imem[4096], dmem[16384];
static bool seen_i[4096], seen_d[16384];
static long boots = 0, early_boots = 0;

// SIG, SIG2 and LOADER_BUILD come from spec.py via -CFLAGS: this proof
// owns no constants either
#define FOREIGN_AT 9000u           // cart word during which the foreign
#define FOREIGN_N  64u             // volley fires (AFTER the words it
                                   // would corrupt were delivered, so a
                                   // claimed write shows up as bad data)

// advance sim time; bclk toggles every 2 units, cclk every 4 (74.25 vs
// 43.2 MHz is ~1.7:1 -- 2:1 only widens the crossing margin under test)
static long simt = 0;
static void step() {
    simt++;
    if (simt % 2 == 0) { dut->bclk = !dut->bclk; dut->eval(); }
    if (simt % 4 == 0) {
        dut->cclk = !dut->cclk;
        dut->eval();
        if (dut->cclk && dut->boot_we) {           // sample after posedge
            boots++;
            if (!dut->cart_ready) early_boots++;   // expected: all of them
            unsigned a = dut->boot_addr;
            if (dut->boot_kind) { dmem[a] = dut->boot_data; seen_d[a] = 1; }
            else                { imem[a] = dut->boot_data; seen_i[a] = 1; }
        }
    }
}

static void bridge_write(unsigned addr, unsigned data) {
    dut->bridge_addr = addr;
    dut->bridge_wr_data = data;
    dut->bridge_wr = 1;
    for (int i = 0; i < 4; i++) step();   // one full bclk cycle (bclk
    dut->bridge_wr = 0;                   // toggles every 2 sim units)
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    dut = new Vcart_loader;
    dut->bclk = 0; dut->cclk = 0; dut->brst_n = 0;
    dut->bridge_wr = 0; dut->dataslot_allcomplete = 0;
    dut->apply_cart = 1;              // the proof always applies the cart
    dut->boot_busy = 0;               // CRAM never back-pressures here
    for (int i = 0; i < 64; i++) step();
    dut->brst_n = 1;

    // THE BOOT-20 CONDITION: the Pocket asserts allcomplete before it has
    // pushed anything (nothing was requested yet, so every slot is
    // trivially complete), and then goes quiet for a while. A loader that
    // releases on allcomplete alone signs an empty machine here and lets
    // the console run over the top of the delivery that follows.
    dut->dataslot_allcomplete = 1;
    for (int i = 0; i < 8000; i++) step();        // long silence first

    for (unsigned w = 0; w < 20480; w++) {
        // the firmware's own housekeeping, mid-burst: zeros aimed at the
        // low window, at exactly the bridge offsets that used to decode
        // into DMEM 0..63. Fired AFTER those words were legitimately
        // delivered, so if the loader still claimed them the data check
        // below would see zeros. It must not.
        if (w >= FOREIGN_AT && w < FOREIGN_AT + FOREIGN_N)
            bridge_write(0x4000u + (w - FOREIGN_AT) * 4, 0);

        bridge_write(0x10000000u + w * 4, 0xA5000000u + w * 3u);

        // boot 17's lesson: words 512..16895 arrive back-to-back (next
        // write on the very next bclk, the bridge's physical maximum) in
        // 128-word blocks with a short SD-sector gap between blocks; the
        // head and tail keep SPI pacing so both regimes stay covered.
        // the OS pauses to read the next block off the SD card: a gap
        // far longer than any "the bus went quiet" window. Releasing here
        // is what lost words to a running VM (builds 19-23), so the
        // loader must hold reset straight through it.
        if (w == 10000) {
            for (int i = 0; i < 30000; i++) step();
            if (dut->cart_ready) {
                printf("LOADER FAIL: released during a delivery gap\n");
                return 1;
            }
        }
        bool burst = (w >= 512 && w < 16896);
        if (!burst)                    for (int i = 0; i < 62; i++) step();
        else if ((w & 127) == 127)     for (int i = 0; i < 600; i++) step();
        // else: no gap at all -- the next word slams in immediately
    }
    // the release waits for a QUIET bridge (boot 19) and for words to
    // have actually arrived (boot 20), so idle out the quiet timer
    for (int i = 0; i < 40000 && !dut->cart_ready; i++) step();

    long miss = 0, bad = 0;
    for (unsigned w = 0; w < 20480; w++) {
        unsigned d = w - 4096;
        if (w >= 4096 && d >= SIG && d < SIG + 8) continue;   // signed over
        if (w >= 4096 && d >= SIG2 && d < SIG2 + 8) continue;
        bool seen = (w < 4096) ? seen_i[w] : seen_d[d];
        unsigned got = (w < 4096) ? imem[w] : dmem[d];
        if (!seen) miss++;
        else if (got != 0xA5000000u + w * 3u) bad++;
    }
    // the signature: what the loader says the bridge did to it
    const unsigned want[8] = {0x5A455441u, 20480u, 20480u, 0u,
                              FOREIGN_N, 0u,        // no re-arm yet
                              0xFFFFFFFFu,          // elapsed: any nonzero
                              LOADER_BUILD};
    const char* nm[8] = {"magic", "accepted", "replayed", "zeros",
                         "foreign_seen", "late_ignored", "elapsed", "build"};
    long sigbad = 0;
    for (int copy = 0; copy < 2; copy++)
    for (int i = 0; i < 8; i++) {
        unsigned base = copy ? SIG2 : SIG;
        if (i == 6) {                       // elapsed is a measurement
            if (dmem[base + 6] == 0) {
                printf("SIG MISMATCH elapsed: never counted\n");
                sigbad++;
            }
            continue;
        }
        if (dmem[base + i] != want[i]) {
            printf("SIG%d MISMATCH %s: got %u want %u\n",
                   copy, nm[i], dmem[base + i], want[i]);
            sigbad++;
        }
    }
    if (miss || bad || sigbad || boots != 20496 || !dut->cart_ready ||
        early_boots != 20496) {
        printf("LOADER FAIL: boots=%ld (want 20496) miss=%ld bad=%ld "
               "sig=%ld ready=%d early=%ld\n",
               boots, miss, bad, sigbad, (int)dut->cart_ready, early_boots);
        return 1;
    }
    // A LATE WORD: the OS pushes one more after the console started. It
    // must be IGNORED -- no reset, no write. A loader that touches a
    // running machine corrupts whatever the sequencer was reading, which
    // is what the periodic signature refresh did (visible as occasional
    // flickering triangles on glass).
    unsigned before = imem[100];
    bool dropped = false;
    bridge_write(0x10000000u + 100 * 4, 0xDEADBEEFu);
    for (int i = 0; i < 2000; i++) { step(); if (!dut->cart_ready) dropped = true; }
    if (dropped || !dut->cart_ready || imem[100] != before) {
        printf("LOADER FAIL (late word): reset=%d ready=%d word=%08X "
               "(was %08X)\n", (int)dropped, (int)dut->cart_ready,
               imem[100], before);
        return 1;
    }

    printf("LOADER PASS: 20480 bridge words -> 4096 IMEM + 16384 DMEM, "
           "every word intact across the clock crossing; %u foreign "
           "low-window writes ignored; delivery signed at %u; "
           "cart_ready withheld through an early allcomplete, and a late "
           "word ignored without touching the running machine\n",
           FOREIGN_N, SIG);
    delete dut;
    return 0;
}
