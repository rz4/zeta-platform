// cram_sync_chip.v -- a protocol-CHECKING model of one Pocket CRAM chip in
// synchronous burst mode, in the zeta-ps15 tradition: it refuses on
// violations instead of being a BRAM with the right pin names. This model
// IS the sim-tier definition of the burst protocol cram_burst.v speaks;
// the hardware tier stays [assumed] until glass, exactly like i2s was.
//
// Checks: no burst before a CRE configuration write; ADV low for exactly
// one clock; the controller must not drive DQ while the chip drives read
// data (bus fight); every CE-low window bounded (tCEM); write data honors
// the latency window. Timing constants: the chip drives read word i at
// edge latch+LAT+i and samples write word i at edge latch+LAT+2+i -- the
// mirror of cram_burst.v's registered pipeline.
`default_nettype none

module cram_sync_chip #(
    parameter LAT = 5,
    parameter TCEM_MAX = 200,
    parameter ROFF = 2,     // reads stream from (address - ROFF): the
                            // boot-39 conviction, measured by paging
                            // from source word 100 and receiving word
                            // 99 -- coherent, exact, deterministic, on
                            // every read burst since the first glass.
                            // The scanline's historic one-pixel shift
                            // was this truth on the video face.
    parameter RDLY = 0,     // reads: the chip holds its FIRST datum this
                            // many extra cycles (retired by the ROFF
                            // conviction; kept as a temperament dial)
    parameter RECOV = 2,    // CE-high cycles the ADDRESS LATCH needs
                            // between bursts. Boot 4 met 2 and the
                            // model stopped there; boot 38's cramscope
                            // showed the mover's rapid-fire bursts
                            // reading STALE NEIGHBORHOODS -- the real
                            // latch needs more, and it fails
                            // BEHAVIORALLY (stale address), not loudly
    parameter WWAIT = 2,    // write bursts: cycles WAIT stays high after
                            // the open. The SLOTS always begin a fixed 2
                            // cycles after WAIT's fall -- that distance
                            // is WAIT's physical meaning; refresh and
                            // process slide the whole window together.
                            // Legacy timing == WWAIT 2. The boot-37
                            // probe showed real chips run a SHORTER
                            // window than legacy modeled, and a
                            // latency-counter-anchored controller
                            // commits its first beats twice there.
    parameter WROFF = 2     // THE WRITE LAW'S MIRROR (pageprobe, boots
                            // 51-53): the write pointer, like the read
                            // pointer, begins WROFF halves BEFORE the
                            // presented address. A controller that
                            // holds word 0 on the bus through the
                            // latency window (the boot-33 anti-float
                            // law) feeds the two early slots real
                            // data: every burst scribbles its held
                            // first half onto (addr-2, addr-1) -- the
                            // last word of whatever came before. Build
                            // 50 never saw it: pads, clears, and the
                            // restride's own skipped tails absorbed
                            // every scribble until banked went
                            // contiguous. Masking the early slots
                            // (UB/LB high) is the cure; masks ride
                            // WITH their beats through the commit
                            // pipeline, as on silicon.
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [5:0]  c_a,
    input  wire [15:0] dq_in,        // what the controller drives
    input  wire        dq_drive,     // controller's output enable
    output reg  [15:0] dq_out,       // what the chip drives back
    output reg         chip_drive,
    input  wire        c_adv_n,
    input  wire        c_cre,
    input  wire        c_ce_n,
    input  wire        c_we_n,
    input  wire        c_ub_n,
    input  wire        c_lb_n,
    /* verilator lint_off UNUSEDSIGNAL */
    input  wire        c_oe_n,
    /* verilator lint_on UNUSEDSIGNAL */
    output reg         wait_out,     // one-clock-lead WAIT, as configured
    output reg         violation,
    output reg  [3:0]  vcode
);
  reg [15:0] mem [0:4194303];        // 64 Mbit
  reg [15:0] bcr;
  reg        configured;
  reg [21:0] baddr;
  reg        bwrite;
  reg [8:0]  n;
  reg        bursting, prev_adv_low;
  // WAIT pacing: grants flow down a small pipeline so the read drive, the
  // controller's registered capture, and the write sample stay lockstep.
  reg [3:0]  lat_ct;
  reg        g1, g2;                 // grant delayed 1, 2 cycles
  localparam [21:0] WRO = WROFF;
  reg [8:0]  r_i, w_i;              // words driven / sampled so far
  reg        stalled;               // stall already inserted at this word
  reg [2:0]  ce_hi;                 // CE-high recovery counter, saturating
  reg [15:0] rlfsr;                 // pseudo-random hidden-refresh stalls
  wire       refresh_due = (rlfsr[8:0] == 9'h0A5);
  wire       masked = c_ub_n && c_lb_n;   // sampled at each commit edge
  // Boot 32: the first read datum reaches the bus one cycle earlier
  // (WAIT-relative) than boots 1-31 modeled -- read slots start at
  // lat_ct==1 like writes, with the write path's extra pipeline stage
  // (g2) keeping the boot-6 write-early alignment unchanged.
  reg  [3:0] wcnt;                  // cycles since the burst opened
  reg  [3:0] rdly_ct;               // first-read-datum hold remaining
  wire       in_data = bwrite ? (wcnt >= WWAIT[3:0] + 4'd2)
                              : (lat_ct <= 4'd1);
  // THE READ LAW, final form (boots 41-42, clean-RTL evidence only):
  // a read burst wraps WITHIN THE 128-HALF ROW of the requested
  // address, beginning ROFF positions before it (mod 128). A
  // row-aligned burst therefore delivers the row's LAST two halves
  // first; the historical one-pixel scanline shift was word 63
  // arriving at cell 0.
  wire [6:0]  rd_pos = baddr[6:0] - ROFF[6:0] + r_i[6:0];
  wire [21:0] next_r = {baddr[21:7], rd_pos};
  wire        row_edge = in_data && !stalled && (r_i != 0) &&
                         (next_r[6:0] == 7'd0);
  wire        grant = bursting && in_data && !wait_out;

  `define VIOL(c) begin violation <= 1'b1; vcode <= c; end

  always @(posedge clk) begin
    if (!rst_n) begin
      violation <= 0; vcode <= 0; configured <= 0;
      bursting <= 0; chip_drive <= 0; prev_adv_low <= 0;
      ce_hi <= 3'd7; rlfsr <= 16'hACE1;
    end else begin
      // CRE-high async write: the configuration
      if (c_cre && !c_ce_n && !c_we_n && dq_drive) begin
        if (c_a[3:2] != 2'b10) `VIOL(4'd1)     // not the BCR select
        bcr <= dq_in;
        configured <= 1'b1;
      end

      // free-running always: a frozen LFSR once parked on the magic value
      // and stalled a burst into tCEM violation
      rlfsr <= {rlfsr[14:0], rlfsr[15] ^ rlfsr[13] ^ rlfsr[12] ^ rlfsr[10]};
      if (c_ce_n && ce_hi != 3'd7) ce_hi <= ce_hi + 1'b1;
      if (!bursting) begin
        if (!c_ce_n && !c_adv_n && !c_cre) begin   // burst opens
          if (!configured) `VIOL(4'd2)
          if (ce_hi < 3'd2) `VIOL(4'd9)     // protocol floor, still loud
          if (!dq_drive) `VIOL(4'd3)               // low address on DQ
          if (ce_hi >= RECOV[2:0])
            baddr <= {c_a, dq_in};          // clean open
`ifdef ZCHIPDBG
          $fdisplay(32'h8000_0002, "OPEN a=%h wr=%b ce_hi=%0d",
                    {c_a, dq_in}, !c_we_n, ce_hi);
`endif
          // else: recovery too short for the real latch -- it keeps the
          // PREVIOUS burst's address and the burst reads/writes a stale
          // neighborhood, silently (the boot-38 cramscope syndrome)
          ce_hi <= 0;
          bwrite <= !c_we_n;
          n <= 0;
          lat_ct <= LAT[3:0];
          wait_out <= 1'b1;
          r_i <= 0; w_i <= 0; g1 <= 0; g2 <= 0; stalled <= 0;
          wcnt <= 0; rdly_ct <= RDLY[3:0];
          bursting <= 1'b1;
          prev_adv_low <= 1'b1;
        end
      end else begin
        if (c_ce_n) begin                          // burst closes
          // the commit window: an UNMASKED write still in the pipeline
          // when CE rises would latch a floating bus on the real chip
          if (bwrite && (g1 || g2) && !masked) `VIOL(4'd8)
          bursting <= 0; chip_drive <= 0; prev_adv_low <= 0;
          wait_out <= 0;
        end else begin
          if (!c_adv_n && prev_adv_low) `VIOL(4'd4)   // ADV held 2 clocks
          prev_adv_low <= !c_adv_n;
          n <= n + 1'b1;
          if (~&wcnt) wcnt <= wcnt + 4'd1;
          if ({23'd0, n} + 1 > TCEM_MAX) `VIOL(4'd5)  // tCEM window
          // WAIT generation: high through the latency, one-cycle pulse at
          // each internal 128-word row crossing (one-clock lead)
          if (lat_ct != 0) begin
            lat_ct <= lat_ct - 1'b1;
            wait_out <= bwrite ? (wcnt < WWAIT[3:0])
                               : (lat_ct > 4'd2 - RDLY[3:0]);
          end else begin
            // row crossings AND hidden refresh both stall the burst --
            // refresh at pseudo-random times, so the sim exercises the
            // jitter real chips produce
            wait_out <= row_edge || (refresh_due && !stalled);
            if (row_edge || refresh_due) stalled <= 1'b1;
          end
          // grants: transfer slots flowing down the pipeline
          g1 <= grant; g2 <= g1;
          // THE WRITE POINTER'S HEAD START (pageprobe, boots 51-54):
          // before the stream's first slot the chip commits the bus's
          // held value into the two cells BELOW the address. The masks
          // suppress it HERE; on glass build 53's masks were NULL --
          // either UB/LB are inert in burst mode or the real slot
          // timing raced the lift (silent write-WAIT). Modeling them
          // effective is a DOCUMENTED OPTIMISM, pending a write-window
          // probe; the PROVEN defense is geometric -- row-aligned opens
          // put every scribble in a dead tail, masks or no masks.
          if (bwrite && lat_ct != 0 && !masked &&
              wcnt == WWAIT[3:0])
            mem[baddr - WRO] <= dq_in;
          if (bwrite && lat_ct != 0 && !masked &&
              wcnt == WWAIT[3:0] + 4'd1)
            mem[baddr - WRO + 22'd1] <= dq_in;
          if (grant) begin
            if (!bwrite) begin
              if (dq_drive) `VIOL(4'd7)              // bus fight on read
              if (rdly_ct != 0) begin
                dq_out <= mem[baddr];                // first datum held
                rdly_ct <= rdly_ct - 4'd1;           // (r_i does not move)
              end else begin
                // the burst's first ROFF beats are PREAMBLE: on glass
                // their value is undefined bus residue (the silver of
                // boots 48-50, the mover's zeroed w63). 0xFFFF here so
                // any consumer of those beats is loudly, visibly wrong
                // in sim too -- the model once served wrapped row data
                // there, and the un-rotation was built on that fiction.
                dq_out <= ({23'd0, r_i} < ROFF) ? 16'hFFFF : mem[next_r];
                chip_drive <= 1'b1;
              end
            end
            if (bwrite || rdly_ct == 0) r_i <= r_i + 1'b1;
            if (!bwrite) chip_drive <= 1'b1;
            if (!row_edge) stalled <= 1'b0;
          end
          if (bwrite && g2 && !masked) begin
            if (!dq_drive) `VIOL(4'd6)               // write gap: the chip
            mem[baddr + {13'd0, w_i}] <= dq_in;      // would latch a
            w_i <= w_i + 1'b1;                       // floating bus here
`ifdef ZCHIPDBG
            if (baddr >= 22'h20000 && w_i < 9'd5)
              $fdisplay(32'h8000_0002,
                "COMMIT a=%h w_i=%0d d=%h n=%0d lat=%0d",
                baddr, w_i, dq_in, n, lat_ct);
`endif
          end
        end
      end
    end
  end

  /* verilator lint_off UNUSEDSIGNAL */
  wire _unused = &{1'b0, bcr};
  /* verilator lint_on UNUSEDSIGNAL */

endmodule
`default_nettype wire
