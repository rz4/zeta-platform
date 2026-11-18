// cram_fb.v -- the double-buffered framebuffer in the Pocket's CRAM pair.
// Buffer 0 lives entirely in chip 0, buffer 1 in chip 1, so painting (the
// back chip) and scanout (the front chip) never share a bus.
//
//   write side: pixel writes stream into a FIFO; the merger turns every
//   sequential run into one open-ended burst (the frame clear becomes
//   back-to-back 128-word bursts). wr_stall freezes the producer with
//   headroom to spare; wr_idle reports the paint fully committed.
//
//   read side: a line server bursts one 320-word display line into a
//   two-line BRAM (128+128+64); px_addr = {line parity, x} reads it back
//   one pixel per clock. The video head asks for line L during line L-1.
//
//   swap: requested at frame end, applied only when swap_gate is high and
//   both engines are quiet -- the sim ties the gate high (a frame call is
//   atomic), the video head raises it at vblank so a scanned frame is
//   never flipped mid-picture.
`default_nettype none

module cram_fb (
    input  wire        clk,
    input  wire        rst_n,
    output wire        ready,
    // write client (the rasterizer)
    input  wire        wr_we,
    input  wire [16:0] wr_addr,
    input  wire [14:0] wr_data,
    output wire        wr_stall,
    output wire        wr_idle,
    // line reads (front buffer)
    input  wire        line_req,
    input  wire [8:0]  line_no,
    output reg         line_rdy,
    input  wire [9:0]  px_addr,      // {line parity, x}
    output reg  [14:0] px_q,
    // the cart's CRAM segment: written once at boot, read by the mover.
    // Both use CHIP 0 only, and only while the paint FIFO is quiet -- the
    // mover runs in the gap between the program halting and the paint
    // starting, which the video head places inside vblank, when neither
    // engine wants the bus.
    input  wire        boot_done,       // the loader's RELEASE verdict
                                        // (cart_ready): only then
                                        // may a PARTIAL bank flush on
                                        // quiet -- a mid-stream bridge
                                        // gap (the OS's 4K read pauses)
                                        // must WAIT, not rotate, or the
                                        // row alignment that armors the
                                        // scribble law breaks for every
                                        // bank after (boot 54's glass)
    input  wire        swp_en,          // the write-window probe's knob
    input  wire [3:0]  swp_k,           // (see zeta_top.v)
    input  wire        ld_we,           // boot: one segment WORD (32b),
    input  wire [21:0] ld_addr,         // half-addr of its low half
    input  wire [31:0] ld_data,
    output wire        ld_busy,
    input  wire        dma_go,          // mover/pump: burst read
    input  wire        dma_chip1,       // 0: chip0 (the mover's proven
                                        // home); 1: ride the BACK chip
                                        // (the pump: never meets scanout)
    input  wire [21:0] dma_addr,
    input  wire [7:0]  dma_len,
    output wire        fb_front,        // which chip scanout owns
    output wire        dma_ack,         // the burst was accepted
    output wire        dma_step,        // one 16-bit word this clock
    output wire [15:0] dma_data,
    output wire        dma_done,
    // swap
    input  wire        swap_req,
    input  wire        swap_gate,
    output wire        swap_pending,
    // chip pins, one bundle per buffer
    input  wire        c0_wait,
    output wire [5:0]  c0_a,
    output wire [15:0] c0_dq_o,
    output wire        c0_dq_oe,
    input  wire [15:0] c0_dq_i,
    output wire c0_clk_en, c0_adv_n, c0_cre, c0_ce_n, c0_we_n, c0_oe_n,
    output wire c0_ub_n, c0_lb_n,
    input  wire        c1_wait,
    output wire [5:0]  c1_a,
    output wire [15:0] c1_dq_o,
    output wire        c1_dq_oe,
    input  wire [15:0] c1_dq_i,
    output wire c1_clk_en, c1_adv_n, c1_cre, c1_ce_n, c1_we_n, c1_oe_n,
    output wire c1_ub_n, c1_lb_n
);
  reg front;                         // buffer being scanned; ~front painted

  // ---- THE RESTRIDE ----------------------------------------------------
  // The seam law (boots 41-50): the chip never delivers the last word of
  // a 128-half row in a continuous burst, no configuration moves it, and
  // every burst's first two beats are preamble (0xFFFF on glass). So the
  // machine stops pretending: CRAM's client space is LOGICAL -- rows of
  // 126 usable halves laid end to end -- and this translation, applied
  // ONCE at every registered address latch below, is the entire bridge:
  //     phys = logical + 2 * floor(logical / 126)
  // Every reader and writer skips the row tails in lockstep; the mover's
  // holes, the silver scanout wires, and the eternal serrations were all
  // the same absence, and they all end here. Costs 1/64 of CRAM. The
  // divide-by-63 is the 2^6-1 reciprocal series with three correction
  // rungs, verified exhaustively over the whole 22-bit space.
  function automatic [21:0] tr(input [21:0] l);
    reg [20:0] w;
    reg [15:0] q;
    reg [8:0]  r;
    begin
      w = l[21:1];                   // /126 = /2, then /63
      q = {1'b0, w[20:6]} + {7'd0, w[20:12]} + {13'd0, w[20:18]};
      r = w[8:0] - {q[2:0], 6'd0} + q[8:0];   // W - 63q, exact mod 512
      q = q + ((r >= 9'd189) ? 16'd3 : (r >= 9'd126) ? 16'd2 :
               (r >= 9'd63)  ? 16'd1 : 16'd0);
      tr = l + {5'd0, q, 1'b0};      // +2 halves per skipped tail word
    end
  endfunction

  // ---- write FIFO: BRAM body + two-entry show-ahead shadow -------------
  // The merger must see the head AND the next entry combinationally,
  // which once forced the whole 512-word queue into REGISTERS -- ~4,000
  // ALMs, a fifth of the device (the skid lesson at 4x the depth,
  // named by the boot-61 resource audit). The body now lives in one
  // M10K; h0/h1 are the visible shadow, kept full by a show-ahead read
  // with write-forwarding for the empty-body corner. The shadow holds
  // min(fcount, 2) entries ALWAYS -- every branch below preserves it.
  reg [31:0] fbody [0:511];          // the body (BRAM)
  reg [8:0]  fwp;                    // body write pointer
  reg [8:0]  fbp;                    // body read pointer (next to fetch)
  reg [31:0] fb_ram;                 // show-ahead: the entry at fbp
  reg        fb_fwd;                 // ...unless it was written this
  reg [31:0] fb_fwd_d;               // cycle (empty-body corner)
  reg [31:0] h0, h1;                 // the merger's window
  reg [9:0]  fcount;
  wire       fempty = (fcount == 0);
  assign     wr_stall = (fcount >= 10'd500);
  wire       fpush = wr_we && !wr_stall;
  wire [16:0] h_addr = h0[31:15];
  wire [14:0] h_data = h0[14:0];
  wire        run_on = (fcount > 1) && (h1[31:15] == h_addr + 17'd1);
  wire        fpop  = w_take;        // merger pops only when !fempty
  wire [9:0]  f_aft = fcount - {9'd0, fpop};   // occupancy after the pop
  wire        bpush = fpush && (f_aft >= 10'd2);      // body-bound push
  wire        bpop  = fpop && (fcount >= 10'd3);      // h1 refill due
  wire [8:0]  nfbp  = bpop ? fbp + 9'd1 : fbp;        // next fetch addr
  wire [31:0] f_in  = {wr_addr, wr_data};
  wire [31:0] fb_q  = fb_fwd ? fb_fwd_d : fb_ram;
  always @(posedge clk) begin
    if (bpush) fbody[fwp] <= f_in;
    fb_ram   <= fbody[nfbp];
    fb_fwd   <= bpush && (fwp == nfbp);
    fb_fwd_d <= f_in;
  end

  // ---- the two chip controllers ----------------------------------------
  wire cfg0, cfg1, idle0, idle1, done0, done1, wstep0, wstep1;
  wire wtake0, wtake1;
  wire rstep0, rstep1;
  wire [15:0] rdat0, rdat1;
  assign ready = cfg0 && cfg1;

  // engine-side signals, routed to whichever chip owns the role
  reg         wgo, lgo;
  reg  [21:0] laddr;
  reg  [21:0] w_taddr;               // the paint run's translated start,
                                     // latched with wgo (head is frozen
                                     // until the burst takes it)
  reg  [7:0]  llen;
  // paint owns the back chip (= !front) -- but ONLY when the segment
  // client isn't borrowing it: an ungated take popped the write FIFO
  // once per mirrored boot half, underflowing fcount into a permanent
  // garbage drain (the banked wedge; room escaped because 184320 boot
  // halves happen to be an exact multiple of the 512-deep FIFO)
  wire        w_take = front ? (wtake0 && !seg0) : (wtake1 && !seg1);
  wire        w_done = front ? (done0 && !seg0) : (done1 && !seg1);
  /* verilator lint_off UNUSEDSIGNAL */
  wire        _wstep_unused = front ? wstep0 : wstep1;
  /* verilator lint_on UNUSEDSIGNAL */
  wire        w_cidl = front ? (idle0 && !seg0) : (idle1 && !seg1);
  // the line server owns only ITS OWN bursts: when the seg client holds
  // chip 0, rstep0/done0 belong to the pump -- the ungated mux let the
  // line buffer swallow SEGMENT halves as pixels whenever a backdrop
  // burst overlapped a scanline fill (the room cart's dotted scanout:
  // room-image bytes at the beat pattern of 128-half pump bursts against
  // 322-word lines, glass-only because the cross reads lines between
  // frames)
  reg         seg_busy, seg_c, seg_both;   // the seg client's burst state:
                                           // declared here because the
                                           // line demux below reads them.
                                           // seg_both: a mirror flush is
                                           // writing BOTH chips at once
  wire        seg0 = seg_busy && (seg_both || !seg_c);
  wire        seg1 = seg_busy && (seg_both ||  seg_c);
  wire        r_step = front ? (rstep1 && !seg1) : (rstep0 && !seg0);
  wire [15:0] r_data = front ? rdat1 : rdat0;
  wire        r_done = front ? (done1 && !seg1) : (done0 && !seg0);
  wire        r_cidl = front ? (idle1 && !seg1) : (idle0 && !seg0);

  // ---- the segment client ----------------------------------------------
  // Boot words MIRROR onto both chips (the pump must find the segment
  // wherever the back buffer is). One ld_we pulse hands over a whole
  // 32-bit word; sequential words fill one of TWO ping-pong banks while
  // the other bank flushes to BOTH chips in parallel (identical data,
  // independent takes). Fill and flush overlap, so sustained delivery
  // is bounded by the faster of the two -- the serialized, blocking
  // flush of build 36 capped the drain near 8 MB/s and the bridge can
  // burst past that.
  reg        seg_wr;
  reg [21:0] seg_addr;
  reg [7:0]  seg_len;
  reg [31:0] cb0c0 [0:63];             // bank 0, chip0's copy (BRAM)
  reg [31:0] cb0c1 [0:63];             // bank 0, chip1's copy
  reg [31:0] cb1c0 [0:63];             // bank 1, chip0's copy
  reg [31:0] cb1c1 [0:63];             // bank 1, chip1's copy
  reg        fbank;                    // bank now filling
  reg [6:0]  fcnt;                     // words held there (0..63:
                                     // one LOGICAL ROW per bank, so
                                     // every flush opens at a phys
                                     // row base and the write
                                     // pointer's head start lands in
                                     // the dead tail -- the scribble
                                     // law's geometric cure)
  reg [21:0] fbase;                    // half-addr of its word 0
  reg [7:0]  cqt;                      // quiet clocks since last word
  reg        pendv;                    // side latch: discontiguous word
  reg [21:0] penda;
  reg [31:0] pendd;
  reg        xarm;                     // a rotated bank awaits its flush
  reg        xbank;
  reg [6:0]  xlen;                     // words in the flushing bank
  reg [21:0] xbase;
  reg [7:0]  crd0, crd1;               // per-chip HALF stream index
  reg        xd0, xd1;                 // per-chip done latches
  assign     fb_front = front;
  // the pump rides the SCANOUT chip: scanout only borrows it ~20% of
  // each line, so segment bursts fit the gaps -- while the paint chip
  // is saturated by the very clear the pump is feeding. The mover keeps
  // chip0, its proven home. A target on the scan chip needs line
  // quiet; a target on the paint chip needs the write path drained.
  // dma_go is a one-clock pulse from the machine; LATCH it. Serving it
  // only if acceptable in that same cycle silently dropped the mover's
  // request whenever the boot tail-flush still owned the client, and a
  // lost request is a frame that never finishes.
  reg        dma_pend;
  reg        dma_c1_l;
  reg [21:0] dma_addr_l;
  reg [7:0]  dma_len_l;
  wire       tgt_c    = dma_c1_l ? front : 1'b0;
  wire       tgt_idle = tgt_c ? idle1 : idle0;
  wire       tgt_scan = (tgt_c == front);       // riding the scanout chip
  // acc_* are comb accept-eligibility WITHOUT the wgo term: the write
  // server yields to them the same cycle (no swallowed-pulse race, and
  // no circular wait -- an ineligible seg request blocks nothing)
  wire       cfree0 = idle0 && ((front == 1'b0)
                          ? !(line_req || lgo || lbusy)
                          : (fempty && !wbusy));
  wire       cfree1 = idle1 && ((front == 1'b1)
                          ? !(line_req || lgo || lbusy)
                          : (fempty && !wbusy));
  wire       acc_ld  = xarm && !seg_busy && cfree0 && cfree1;
  wire       acc_dma = dma_pend && !seg_busy && !xarm &&
                       tgt_idle &&
                       (tgt_scan ? !(line_req || lgo || lbusy)
                                 : (fempty && !wbusy));
  // ONE shared translator for every non-line site, muxed by the branch
  // that can fire this cycle (the six per-site instances of build 51's
  // first fit were 60 ALMs over the device; per-block sharing was still
  // 4 LABs over): the seg accepts and the paint issue are mutually
  // exclusive by the arbitration itself -- wgo's issue term carries
  // !acc_ld && !acc_dma -- so one operand mux serves all three
  wire [21:0] seg_tr = tr(acc_ld ? xbase :
                          acc_dma ? dma_addr_l : {5'd0, h_addr});
  assign ld_busy  = ld_we || pendv || (fcnt == 7'd63);
  assign dma_ack  = acc_dma && !wgo;
  assign dma_step = seg_busy && !seg_wr && (seg_c ? rstep1 : rstep0);
  assign dma_data = seg_c ? rdat1 : rdat0;
  assign dma_done = seg_busy && !seg_wr && (seg_c ? done1 : done0);
  reg seg_go;

  wire go0   = seg0 ? seg_go : (front ? wgo : lgo);
  wire go1   = seg1 ? seg_go : (front ? lgo : wgo);
  wire wr0   = seg0 ? seg_wr : front;
  wire wr1   = seg1 ? seg_wr : !front;
  wire [21:0] adr0 = seg0 ? seg_addr : (front ? w_taddr : laddr);
  wire [21:0] adr1 = seg1 ? seg_addr : (front ? laddr : w_taddr);
  wire [7:0]  len0 = seg0 ? seg_len : llen;
  wire [7:0]  len1 = seg1 ? seg_len : llen;
  wire [15:0] dat0 = seg0 ? (crd0[0] ? cq0[31:16] : cq0[15:0])
                          : {1'b0, h_data};
  wire [15:0] dat1 = seg1 ? (crd1[0] ? cq1[31:16] : cq1[15:0])
                          : {1'b0, h_data};
  wire        wend0 = ({1'b0, crd0} >= seg_len - 8'd1);
  wire        wend1 = ({1'b0, crd1} >= seg_len - 8'd1);
  wire        take0 = seg0 && seg_wr && wtake0;
  wire        take1 = seg1 && seg_wr && wtake1;
  // word prefetch, FWFT at half granularity: cqN always holds the word
  // containing chip N's next half. Fill writes go to the FILLING bank,
  // these reads to the FLUSHING bank -- never the same RAM. One
  // registered read PER ARRAY, bank-muxed AFTER: a read that selects
  // between two arrays in one expression uninfers both into registers
  // (build 37's first fitter overflow).
  wire [5:0]  pfa0 = (take0 ? crd0 + 8'd1 : crd0) >> 1;
  wire [5:0]  pfa1 = (take1 ? crd1 + 8'd1 : crd1) >> 1;
  reg [31:0] q0a, q0b, q1a, q1b;
  always @(posedge clk) begin
    q0a <= cb0c0[pfa0]; q0b <= cb1c0[pfa0];
    q1a <= cb0c1[pfa1]; q1b <= cb1c1[pfa1];
  end
  wire [31:0] cq0 = xbank ? q0b : q0a;
  wire [31:0] cq1 = xbank ? q1b : q1a;
  // fill writes: one word per pulse into both chip-copies of the bank
  wire        ldpush = ld_we && !pendv &&
                      (fcnt == 7'd0 || (fcnt != 7'd63 &&
                       ld_addr == fbase + {14'd0, fcnt, 1'b0}));
  wire [5:0]  fwa   = (fcnt == 7'd0) ? 6'd0 : fcnt[5:0];
  wire        pmove = !xarm && !(seg_busy && seg_both) && pendv &&
                      fcnt == 7'd0;    // side latch into a fresh bank
  always @(posedge clk) begin
    if (ldpush || pmove) begin
      if (fbank) begin
        cb1c0[ldpush ? fwa : 6'd0] <= ldpush ? ld_data : pendd;
        cb1c1[ldpush ? fwa : 6'd0] <= ldpush ? ld_data : pendd;
      end else begin
        cb0c0[ldpush ? fwa : 6'd0] <= ldpush ? ld_data : pendd;
        cb0c1[ldpush ? fwa : 6'd0] <= ldpush ? ld_data : pendd;
      end
    end
  end

  always @(posedge clk) begin
    seg_go <= 1'b0;
    if (!rst_n) begin
      seg_busy <= 1'b0; seg_both <= 1'b0; fcnt <= 7'd0; fbank <= 1'b0;
      cqt <= 8'd0; pendv <= 1'b0; xarm <= 1'b0; dma_pend <= 1'b0;
    end else begin
      if (dma_go) begin
        dma_pend <= 1'b1; dma_c1_l <= dma_chip1;
        dma_addr_l <= dma_addr; dma_len_l <= dma_len;
      end
      if (ld_we) begin                 // one pulse: take the word
        if (ldpush) begin
          if (fcnt == 7'd0) fbase <= ld_addr;
          fcnt <= fcnt + 7'd1;
        end else begin                 // full or an address break
          pendv <= 1'b1; penda <= ld_addr; pendd <= ld_data;
        end
      end else if (pmove) begin
        fbase <= penda; fcnt <= 7'd1; pendv <= 1'b0;
      end
      cqt <= (ld_we || fcnt == 7'd0) ? 8'd0
             : cqt + {7'd0, cqt != 8'hFF};
      // rotate: hand the filled bank to the flush side when it is full,
      // broken, or gone quiet -- filling continues in the other bank
      if (!xarm && !(seg_busy && seg_both) && fcnt != 7'd0 &&
          (fcnt == 7'd63 || pendv || (cqt == 8'hFF && boot_done))) begin
`ifdef ZROTDBG
        if (fcnt != 7'd63)
          $fdisplay(32'h8000_0002, "ROT partial len=%0d base=%h full=%b pendv=%b quiet=%b done=%b",
                    fcnt, fbase, fcnt == 7'd63, pendv, cqt == 8'hFF, boot_done);
`endif
        xarm <= 1'b1; xbank <= fbank; xlen <= fcnt; xbase <= fbase;
        fbank <= ~fbank; fcnt <= 7'd0;
      end
      if (take0) crd0 <= crd0 + 8'd1;
      if (take1) crd1 <= crd1 + 8'd1;
      if (!seg_busy) begin
        if (acc_ld && !wgo) begin      // both chips, in parallel
          seg_busy <= 1'b1; seg_both <= 1'b1; seg_wr <= 1'b1;
          seg_go <= 1'b1; xarm <= 1'b0;
          seg_addr <= seg_tr; seg_len <= {xlen, 1'b0};
          crd0 <= 8'd0; crd1 <= 8'd0; xd0 <= 1'b0; xd1 <= 1'b0;
        end else if (acc_dma && !wgo) begin
          seg_busy <= 1'b1; seg_both <= 1'b0; seg_wr <= 1'b0;
          seg_go <= 1'b1;
          seg_c    <= tgt_c;
          seg_addr <= seg_tr; seg_len <= dma_len_l;
          dma_pend <= 1'b0;
        end
      end else if (seg_both) begin     // wait for BOTH chips to finish
        if (done0) xd0 <= 1'b1;
        if (done1) xd1 <= 1'b1;
        if ((xd0 || done0) && (xd1 || done1)) begin
          seg_busy <= 1'b0; seg_both <= 1'b0;
        end
      end else if (seg_c ? done1 : done0) seg_busy <= 1'b0;
    end
  end
  cram_burst u_c0 (
    .clk(clk), .rst_n(rst_n), .cfg_done(cfg0),
    .swp_en(swp_en), .swp_k(swp_k),
    .go(go0), .wr(wr0), .addr(adr0), .len(len0),
    .w_end(seg0 ? (seg_wr ? wend0 : 1'b1) : !run_on),
    .w_step(wstep0), .w_take(wtake0), .w_data(dat0),
    .r_step(rstep0), .r_data(rdat0), .idle(idle0), .done(done0),
    .c_wait(c0_wait), .c_a(c0_a), .c_dq_o(c0_dq_o), .c_dq_oe(c0_dq_oe), .c_dq_i(c0_dq_i),
    .c_clk_en(c0_clk_en), .c_adv_n(c0_adv_n), .c_cre(c0_cre),
    .c_ce_n(c0_ce_n), .c_we_n(c0_we_n), .c_oe_n(c0_oe_n),
    .c_ub_n(c0_ub_n), .c_lb_n(c0_lb_n));

  cram_burst u_c1 (
    .clk(clk), .rst_n(rst_n), .cfg_done(cfg1),
    .swp_en(swp_en), .swp_k(swp_k),
    .go(go1), .wr(wr1), .addr(adr1), .len(len1),
    .w_end(seg1 ? (seg_wr ? wend1 : 1'b1) : !run_on),
    .w_step(wstep1), .w_take(wtake1), .w_data(dat1),
    .r_step(rstep1), .r_data(rdat1), .idle(idle1), .done(done1),
    .c_wait(c1_wait), .c_a(c1_a), .c_dq_o(c1_dq_o), .c_dq_oe(c1_dq_oe), .c_dq_i(c1_dq_i),
    .c_clk_en(c1_clk_en), .c_adv_n(c1_adv_n), .c_cre(c1_cre),
    .c_ce_n(c1_ce_n), .c_we_n(c1_we_n), .c_oe_n(c1_oe_n),
    .c_ub_n(c1_ub_n), .c_lb_n(c1_lb_n));

  // ---- write engine: pop runs into bursts -------------------------------
  reg wbusy;
  assign wr_idle = fempty && !wbusy && w_cidl;
  always @(posedge clk) begin
    wgo <= 1'b0;
    if (!rst_n) begin
      fwp <= 0; fbp <= 0; fcount <= 0; wbusy <= 0;
    end else begin
      if (bpush) fwp <= fwp + 9'd1;
      if (bpop)  fbp <= fbp + 9'd1;
      fcount <= f_aft + {9'd0, fpush};
      // the shadow invariant: h0/h1 hold min(fcount, 2) entries; a
      // push routes to wherever the post-pop occupancy says
      if (fpop) begin
        h0 <= (fpush && f_aft == 10'd0) ? f_in : h1;
        if (fcount >= 10'd3)              h1 <= fb_q;
        else if (fpush && f_aft == 10'd1) h1 <= f_in;
      end else begin
        if (fpush && fcount == 10'd0)      h0 <= f_in;
        else if (fpush && fcount == 10'd1) h1 <= f_in;
      end
      if (!wbusy) begin
        if (!fempty && w_cidl && ready && !lgo && !acc_ld && !acc_dma) begin
          wgo <= 1'b1; wbusy <= 1'b1;
          w_taddr <= seg_tr;       // operand mux: neither acc fires here
        end
      end else if (w_done) wbusy <= 1'b0;
    end
  end

  // ---- line server: 320 words as 128+128+64 into the line BRAM ---------
  reg [14:0] lb [0:1023];      // {parity, x[8:0]}: indexed sparse, 1 M10K
  always @(posedge clk) px_q <= lb[px_addr];
  reg [1:0]  lseg;
  reg [8:0]  lfx;
  // the line server's one translator: operand muxed by the fetch leg
  wire [21:0] l_log = {5'd0, lbase} + (lseg == 2'd1 ? 22'd128 :
                                       lseg == 2'd2 ? 22'd256 : 22'd0);
  wire [21:0] l_tr  = tr(l_log);
  reg        lln0;                   // parity of the line being filled
  reg        lbusy;
  reg        ldone;                  // latched r_done (survives S_RCV)
  reg [16:0] lbase;
  always @(posedge clk) begin
    lgo <= 1'b0;
    line_rdy <= 1'b0;
    if (!rst_n) begin
      lbusy <= 0; lseg <= 0;
    end else begin
      if (r_step) begin
        lb[{lln0, lfx}] <= r_data[14:0];
        lfx <= lfx + 1'b1;
      end
      if (r_done) ldone <= 1'b1;     // done pulses during CE recovery;
      if (line_req) begin            // the next go must wait for idle
        lln0 <= line_no[0];
        lbase <= {line_no, 8'd0} + {2'd0, line_no, 6'd0}
                 + {7'd0, line_no, 1'b0};  // *322: double-gutter rows
                                           // (two trailing commits per
                                           // write burst, boot 35)
        lfx <= 0; lseg <= 0; lbusy <= 1'b1; ldone <= 1'b0;
      end else if (lbusy && !lgo &&
                    !(front ? seg1 : seg0)) begin
        if (lseg == 2'd0 && r_cidl && !wgo) begin
          laddr <= l_tr; llen <= 8'd128;
          lgo <= 1'b1; lseg <= 2'd1;
        end else if (lseg == 2'd1 && ldone && r_cidl) begin
          laddr <= l_tr; llen <= 8'd128;
          lgo <= 1'b1; lseg <= 2'd2; ldone <= 1'b0;
        end else if (lseg == 2'd2 && ldone && r_cidl) begin
          laddr <= l_tr; llen <= 8'd64;
          lgo <= 1'b1; lseg <= 2'd3; ldone <= 1'b0;
        end else if (lseg == 2'd3 && ldone) begin
          line_rdy <= 1'b1; lbusy <= 1'b0; lseg <= 2'd0; ldone <= 1'b0;
        end
      end
    end
  end

  // ---- swap: requested at frame end, applied when quiet + gated ---------
  reg pend;
  assign swap_pending = pend;
  always @(posedge clk) begin
    if (!rst_n) begin front <= 1'b0; pend <= 1'b0; end
    else begin
      if (swap_req) pend <= 1'b1;
      if (pend && swap_gate && wr_idle && !lbusy && r_cidl) begin
        front <= ~front;
        pend <= 1'b0;
      end
    end
  end

endmodule
`default_nettype wire
