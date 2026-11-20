// cart_loader.v -- the APF bridge -> cart memory path: what makes the
// .zbin ON THE CARD the game that runs, instead of whatever Quartus baked.
//
// The Pocket's OS pushes the data slot's file at the core as ordinary
// bridge writes in the clk_74a domain. This module claims the 128 KB
// window at 0x10000000 THAT data.json DECLARES -- and nothing else --
// crosses each word into the console clock domain, and replays it on
// zeta_top's boot port: words 0..IMEM_WORDS-1 -> IMEM, then DMEM_WORDS of
// DMEM, then the CRAM segment --
// exactly the cart.zbin layout zeta deploy writes.
//
// Two hardware truths are built in, each paid for on glass:
//
//  * The crossing is a 128-deep gray-coded ASYNC FIFO, not a toggle
//    handshake (boot 17). The firmware streams large files in fast
//    bursts, and a toggle flipping twice inside one sync window is a
//    net no-change -- words silently vanished. The FIFO holds a full
//    512-byte block arriving at the bridge's physical maximum and
//    drains one word per console clock; SD-sector gaps do the rest.
//
//  * The old decode ALSO claimed a low window at 0x00000000 ("in case
//    the firmware defaults there" -- inherited paranoia). Boot 18's
//    probe cart found DMEM words 0..4095 arriving as pure zeros, and
//    those are exactly bridge bytes 0x4000..0x7FFF in that low window.
//    The slot file goes where data.json says; claim nothing else.
//
// The signature is written ONCE, while the console is still in reset.
// It used to be rewritten every 24 ms so that no corruption could hide
// it -- necessary while the 12-bit boot_addr in zeta_glass was folding
// memory, actively harmful afterwards: those writes take the external
// DMEM port, which zeta_top gives priority over the geometry
// sequencer's reads, so every refresh corrupted one word mid-frame and
// showed up as an occasional flickering triangle. A loader must touch
// nothing once the game is running. For the same reason `booted`
// latches: no late bridge write can reset a running console or scribble
// on its memory.
//
// This module SIGNS ITS OWN DELIVERY: after the last word it
// writes six words at LOADER_SIG (see spec.py) reporting what the
// bridge actually did -- words accepted, how many landed in the
// suspect range, how many carried zeros, and how many writes appeared
// in the no-longer-claimed low window. The console reports its own
// boot on screen instead of us inferring it from artifacts.
//
// Build 22/23 named the last one. Two carts, two different corruptions:
// the probe (whose first frame runs ~6000 instructions) lost one
// contiguous 16 KB, while the parts-bunny (whose frames are ~50
// instructions) lost scattered pieces of its mesh. That is the shape of
// delivery CONTINUING WHILE THE VM RUNS: zvm's external port drops
// writes whenever the VM holds the memory, so whatever arrives during a
// frame evaporates, and how much depends on how long that cart's frames
// are. The OS's gaps between SD reads are longer than any quiet window
// worth waiting for, so no timer can tell "paused" from "finished".
//
// Stop guessing: we know exactly how many words a cart is. Hold the
// console in reset until ALL of them have arrived. A timer only decides
// the no-file case, where the baked fallback boots instead.
//
// Boot 20 named the one before: dataslot_allcomplete is ALREADY HIGH at
// boot -- nothing has been requested yet, so "all slots complete" is
// trivially true -- so releasing on it signs an empty machine and starts
// the console BEFORE the OS pushes a single word. The file then lands in
// a RUNNING machine, where zvm's external port ignores writes while the
// VM holds the memory, and the VM's first frame is long: a whole
// contiguous chunk of the cart evaporates, which is exactly the hole the
// probe found. Release therefore requires that words ACTUALLY ARRIVED --
// and if any word shows up after release, the console goes straight back
// into reset until the bus settles again. A restarted frame 0 is
// invisible; a half-loaded cart is not.
//
// Boot 19 added a third truth: allcomplete is NOT the last word. The
// console came out of reset (core_top gates its reset on cart_ready)
// while the OS was still pushing, so late words hit a RUNNING machine,
// where zvm's external port ignores writes -- holes in the middle of a
// cart that the file and the fallback both contain. Release now waits
// for allcomplete AND a QUIET BRIDGE: no write into our window for
// 2^QUIET_LOG console clocks (~12 ms), with a 2^TMO_LOG backstop so a
// chatty bus can never brick the boot.
//
// The console is held in reset until `cart_ready` (allcomplete, a quiet
// bridge, a drained FIFO, and the signature): boots clean into the
// loaded cart, or into the baked fallback if no file was delivered.
`default_nettype none

module cart_loader #(
    parameter QUIET_LOG = 19,      // ~12 ms of silence means "done"
    parameter TMO_LOG   = 26       // ~1.6 s backstop, never brick
) (
    // bridge side (clk_74a)
    input  wire        bclk,
    input  wire        brst_n,
    input  wire [31:0] bridge_addr,
    input  wire        bridge_wr,
    input  wire [31:0] bridge_wr_data,
    input  wire        dataslot_allcomplete,
    // console side (clk_zeta)
    input  wire        cclk,
    input  wire        boot_busy,     // a segment word is still draining
                                      // into CRAM: hold the next one
    input  wire        apply_cart,    // 0: watch and count, write nothing
                                      // but the signature (the console
                                      // boots from the baked cart) -- how
                                      // the delivery counters get read on
                                      // real hardware at all
    output reg         boot_we,
    output reg   [1:0] boot_kind,     // 0 IMEM, 1 DMEM, 2 CRAM segment
    output reg  [22:0] boot_addr,
    output reg  [31:0] boot_data,
    output reg         cart_ready
);
  `include "params.vh"

  wire in_hi  = (bridge_addr[31:28] == 4'h1) &&      // 0x10000000: ours
                (bridge_addr[27:25] == 3'd0);          // 32 MB of window
                                                       // (build 105: the
                                                       // second dies)
  wire in_lo  = (bridge_addr[31:17] == 15'd0);       // 0x00000000: NOT
  wire hit    = bridge_wr && in_hi;
  wire lo_hit = bridge_wr && in_lo;

  // the cart is IMEM, then DMEM, then however many words of CRAM segment
  // the game carries -- so the window is now 16 MB, not 128 KB
  wire [22:0] widx  = bridge_addr[24:2];
  wire [22:0] dsub  = widx - IMEM_WORDS[22:0];
  wire [22:0] csub  = widx - (IMEM_WORDS[22:0] + DMEM_WORDS[22:0]);
  wire [1:0]  wkind = (widx < IMEM_WORDS[22:0])                  ? 2'd0 :
                      (widx < IMEM_WORDS[22:0] + DMEM_WORDS[22:0]) ? 2'd1
                                                                   : 2'd2;
  wire [22:0] waddr = (wkind == 2'd0) ? widx :
                      (wkind == 2'd1) ? dsub : csub;
  wire        w_dlo = (wkind == 2'd1) && (dsub < 23'd4096);
  wire        w_zer = (bridge_wr_data == 32'd0);     // zeros ANYWHERE

  function [11:0] gray(input [11:0] b); gray = b ^ (b >> 1); endfunction

  // ---- write side (bclk): capture into the FIFO, and count -------------
  // 2048 deep since build 37: the segment drain tops out near 8.6 MB/s
  // (the mirror writes both chips), and 512 words of skid was a thin
  // margin against the bridge's bursts once carts carry megabyte tails
  reg [56:0] fifo [0:2047];            // {kind[1:0], addr[22:0], data}
  reg [11:0] wptr;                     // binary, one spare bit for wrap
  reg [11:0] wgray;
  reg [15:0] n_hi, n_dlo, n_zero, n_lo, last_lo;    // saturating
  reg        got_any;
  reg        got_all;              // the WHOLE cart is in: release
  // "the whole cart is in" means the resident image; a CRAM segment is
  // extra and arrives after it
  localparam [15:0] CART_WORDS = IMEM_WORDS[15:0] + DMEM_WORDS[15:0];
  always @(posedge bclk) begin
    if (!brst_n) begin
      wptr <= 12'd0; wgray <= 12'd0; got_any <= 1'b0;
      got_all <= 1'b0;
      n_hi <= 16'd0; n_dlo <= 16'd0; n_zero <= 16'd0;
      n_lo <= 16'd0; last_lo <= 16'd0;
    end else begin
      if (hit) begin
        fifo[wptr[10:0]] <= {wkind, waddr, bridge_wr_data};
        wptr  <= wptr + 12'd1;
        wgray <= gray(wptr + 12'd1);
        if (~&n_hi)            n_hi   <= n_hi + 16'd1;
        if (w_dlo && ~&n_dlo)  n_dlo  <= n_dlo + 16'd1;
        if (w_zer && ~&n_zero) n_zero <= n_zero + 16'd1;
      end
      if (hit) got_any <= 1'b1;        // level flag: the OS really spoke
      if (hit && n_hi == CART_WORDS - 16'd1) got_all <= 1'b1;
      if (lo_hit) begin                // observed, deliberately ignored
        if (~&n_lo) n_lo <= n_lo + 16'd1;
        last_lo <= {1'b0, widx};
      end
    end
  end

  // ---- is the bridge still talking to us? ------------------------------
  reg act_t = 1'b0;                // toggles on every write we would take
  always @(posedge bclk) if (hit) act_t <= ~act_t;

  // ---- read side (cclk): drain, wait for silence, then sign ------------
  // The counters cross domains unsynchronized on purpose: they are
  // static long before allcomplete propagates through three flops (the
  // bridge is quiet by then), and they are diagnostics, not machine
  // state any gate depends on.
  reg [11:0] wg1 = 12'd0, wg2 = 12'd0, rptr = 12'd0;
  reg [2:0] as = 3'd0, ac = 3'd0, gs = 3'd0, fs = 3'd0;
  reg [15:0] n_late  = 16'd0;      // words that arrived after boot
                                   // and were deliberately ignored
  reg [15:0] n_out   = 16'd0;      // words actually replayed: n_hi
                                   // minus this is FIFO loss
  reg        emitting = 1'b0;
  reg        booted   = 1'b0;      // the console has started
  reg [3:0] sigi = 4'd0;
  reg       sig_done = 1'b0;
  reg [QUIET_LOG-1:0] quiet = 0;   // console clocks since the last write
  reg [TMO_LOG-1:0]   since = 0;   // console clocks since power-up
  wire      fifo_empty = (gray(rptr) == wg2);
  wire      have_data = gs[2];     // the OS has actually delivered
  wire      have_all  = fs[2];     // ...all of it: the only sure signal
  // drained: nothing left in the FIFO and the CRAM boot path idle. The
  // quiet timer alone signed early once the coalescer stalled the pop
  // for ~300 clocks per flush: the segment tail was still in the FIFO
  // when booted latched, and every word of it was discarded as "late"
  // (build 36 on glass: banked's bunny pages from a truncated segment)
  wire      drained = fifo_empty && !boot_busy;
  wire      settled = have_all ? (quiet > 10'd200 && drained)
                    : (&since);                     // else: no file, fall
                                                    // back to the baked cart
  always @(posedge cclk) begin
    wg1 <= wgray; wg2 <= wg1;
    as  <= {as[1:0], dataslot_allcomplete};
    ac  <= {ac[1:0], act_t};
    gs  <= {gs[1:0], got_any};
    fs  <= {fs[1:0], got_all};
    if (~&since) since <= since + 1'b1;
    if (ac[2] != ac[1]) quiet <= 0;          // a word just arrived
    else if (~&quiet)   quiet <= quiet + 1'b1;
    if (sig_done) booted <= 1'b1;            // latched: from here on this
                                             // module touches nothing
    boot_we <= 1'b0;
    if (!fifo_empty && !boot_busy) begin   // cart words first, always --
                                           // but never faster than CRAM
      {boot_kind, boot_addr, boot_data} <= fifo[rptr[10:0]];
      boot_we <= apply_cart && !booted;      // counted either way; never
                                             // applied once the game runs
      if (booted && ~&n_late) n_late <= n_late + 16'd1;
      rptr    <= rptr + 12'd1;
      if (~&n_out) n_out <= n_out + 16'd1;   // the OTHER end
    end else if (emitting) begin             // sixteen words of testimony
      boot_we   <= 1'b1;                     // (both copies), written ONCE
                                             // while the console is still
                                             // in reset -- see below
      boot_kind <= 2'd1;
      boot_addr <= {9'd0, (sigi[3] ? LOADER_SIG2[13:0] : LOADER_SIG[13:0])
                          + {11'd0, sigi[2:0]}};
      case (sigi[2:0])
        3'd0:    boot_data <= 32'h5A455441;       // 'ZETA'
        3'd1:    boot_data <= {16'd0, n_hi};
        3'd2:    boot_data <= {16'd0, n_out};
        3'd3:    boot_data <= {16'd0, n_zero};
        3'd4:    boot_data <= {16'd0, n_lo};
        3'd5:    boot_data <= {16'd0, n_late};
        3'd6:    boot_data <= {16'd0, since[TMO_LOG-1:TMO_LOG-16]};
        default: boot_data <= LOADER_BUILD;   // WHICH core is running
      endcase
      if (sigi == 4'd15) begin
        emitting <= 1'b0; sig_done <= 1'b1;
      end else sigi <= sigi + 4'd1;
    end else if (as[2] && settled && !sig_done) begin
      emitting <= 1'b1;                      // the one and only emission
      sigi     <= 4'd0;
    end
    cart_ready <= sig_done;            // every word above lands first
  end

endmodule
`default_nettype wire
