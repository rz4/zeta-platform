// cram_burst.v -- one Pocket CRAM (CellularRAM/PSRAM) chip in synchronous
// burst mode: 1 word per clock inside a burst, which is the entire reason
// the framebuffer can live off-die. One controller per chip; the two frame
// buffers split across the two chips, so paint (writes, back chip) and
// scanout (reads, front chip) never touch the same bus.
//
// Protocol (datasheet-derived, enforced in sim by cram_sync_chip.v, and
// [assumed] at the hardware tier until glass confirms it -- the same
// honesty tier i2s passed through):
//   reset:  CRE-high async write programs the BCR: synchronous burst,
//           continuous, latency LAT, WAIT asserted during latency.
//   burst:  CE low; ADV low for 1 clock with addr[21:16] on the A pins
//           and addr[15:0] on DQ; WE latched during ADV (low = write).
//           Data is paced by the chip's WAIT pin (configured for a
//           one-clock lead so it can be REGISTERED here): a cycle after
//           WAIT was high transfers nothing.
//   tCEM:   CE may stay low at most ~4 us -- the row law bounds every
//           CE-low window to ~126 data beats, well under it.
//
// THE ROW LAW (boots 41-50, the seam, final form): the chip never
// delivers the last word of a 128-half row in a continuous burst, and
// the first two beats of any burst are preamble (0xFFFF on glass). So
// this controller speaks only the agreed dialect: every span -- read OR
// write -- is served as sub-bursts that live inside one row's usable
// 126 halves, reopening on the next row past the tail. The RESTRIDE
// translation upstream (cram_fb.v) guarantees every span's open offset
// is < 126 and that logical space simply does not contain the tails;
// clients see one linear stream and never learn the row existed.
//
// Client interface: span-oriented. Present go with addr/len/write; stream
// len words (w_data on w_step for writes; r_data valid on r_step for
// reads). done pulses when the span closes. The span merger that turns
// pixel writes into spans lives upstream (cram_fb.v).
`default_nettype none

module cram_burst #(
    parameter LAT = 5                // latency clocks after ADV
) (
    input  wire        clk,
    input  wire        rst_n,
    output reg         cfg_done,     // BCR programmed, bursts welcome
    // the write-window probe (zeta_top.v): when armed, the early-window
    // mask lift is timed by K raw cycles from the open instead of the
    // raw-WAIT anchor -- K=0 legacy (no masks), 1..14 the sweep, 15
    // never lift. Disarmed = build-55 behavior exactly.
    input  wire        swp_en,
    input  wire [3:0]  swp_k,
    // span interface
    input  wire        go,           // pulse: start a span (needs idle)
    input  wire        wr,           // 1 = write span, 0 = read span
    input  wire [21:0] addr,         // half address, row offset < 126
    input  wire [7:0]  len,          // READS: halves, 1..255
    input  wire        w_end,        // WRITES: current word is the last
    output reg         w_step,       // write: word captured (registered)
    output wire        w_take,       // write: capturing THIS edge -- the
                                     // FIFO must pop on this, not w_step,
                                     // or its count lags and underflows
    input  wire [15:0] w_data,
    output reg         r_step,       // read: r_data is valid this cycle
    output reg  [15:0] r_data,
    output wire        idle,
    output reg         done,         // pulse: span finished
    // chip pins
    input  wire        c_wait,
    output reg  [5:0]  c_a,          // addr[21:16]
    output reg  [15:0] c_dq_o,
    output reg         c_dq_oe,
    input  wire [15:0] c_dq_i,
    output reg         c_clk_en,     // chip clock runs while enabled
    output reg         c_adv_n,
    output reg         c_cre,
    output reg         c_ce_n,
    output reg         c_we_n,
    output reg         c_oe_n,
    output reg         c_ub_n,
    output reg         c_lb_n
);
  // BCR value: sync burst, continuous burst, latency code for LAT,
  // WAIT during, full drive. Bit layout per the CellularRAM 1.5 family.
  // BCR, CellularRAM 1.5 layout: [15]=0, [14:13]=00 reserved,
  // [13:11] latency code, [10] WAIT polarity (1 = active high),
  // [8] WAIT config (1 = asserted one clock early, so it registers),
  // [3] burst wrap off, [2:0] = 111 continuous burst
  localparam [2:0]  LAT_M1 = LAT - 1;
  // boot 50's experiment: latency 4 -> 5. The row seam's signature --
  // last word swallowed, next row's first half doubled -- is an
  // internal prefetch missing the row turn by one stage. Continuous
  // bursts are seamless AT THE RATED LATENCY; we ran the minimum
  // code. One more stage, one variable, the whole stack unchanged.
  // (BCR[8] restored to 1: boot 49 proved it moot.)
  localparam [15:0] BCR = {2'b00, LAT_M1, 1'b1, 1'b0, 1'b1,
                           4'b0000, 1'b1, 3'b111};

  localparam S_RST = 4'd0, S_CFG1 = 4'd1, S_CFG2 = 4'd2, S_IDLE = 4'd3,
             S_ADV = 4'd4, S_LATW = 4'd5, S_RUN = 4'd6, S_END = 4'd7,
             S_NEXT = 4'd9, S_TAIL = 4'd10, S_WNEXT = 4'd11,
             S_RCV = 4'd8;
  reg [3:0]  st;
  reg [7:0]  left;
  reg [3:0]  latc;
  reg [7:0]  cfg_wait;
  reg        span_wr;
  reg        wait_seen;              // WAIT observed HIGH this burst: read
                                     // exits fire only on its falling edge
                                     // (boot 34) -- floor-gated exits raced
                                     // the chip's WAIT rise and captured
                                     // the bus keeper's residue as word 0
                                     // (the right-edge pixel creep at x=0)
  reg [1:0]  rskip;                  // the seam's preamble: every read
                                     // burst's first two beats are garbage
                                     // (0xFFFF on glass) and are discarded.
                                     // The un-rotation that once HELD them
                                     // as a rotated row tail (boots 42-47)
                                     // was the model's story, not the
                                     // chip's -- on glass those beats were
                                     // the silver wires. Demolished.
  // the span splitter, restride form: reads AND writes are served as
  // per-row sub-bursts over the row's 126 usable halves; at the row end
  // the cursor hops the 2-half tail the chip cannot deliver. Clients see
  // one linear stream at the translated address.
  reg [21:0] r_cur;
  reg [7:0]  r_rem;
  wire [7:0] row_left = 8'd126 - {1'b0, r_cur[6:0]};
  wire [7:0] sub_len  = (r_rem < row_left) ? r_rem : row_left;
  wire       sub_hop  = (({1'b0, r_cur[6:0]} + sub_len) == 8'd126);
  reg [14:0] w_row;                  // write side: the row being written
  reg        w_more;                 // row-forced end; the span continues
  reg [3:0]  wk_ct;                  // probe: cycles since the anchor
  reg        wanch;                  // the WAIT anchor fired this burst
  wire [3:0] k_use = swp_en ? swp_k : 4'd2;   // the measured constant
  wire [14:0] w_nrow = w_row + 15'd1;
  reg        wait_r;                 // registered WAIT: high = the coming
                                     // cycle transfers no data

  assign idle = (st == S_IDLE);
  assign w_take = (st == S_RUN) && span_wr && !wait_r;

  always @(posedge clk) begin
    done <= 1'b0;
    r_step <= 1'b0;
    w_step <= 1'b0;
    wait_r <= c_wait;
    // THE ANCHORED LIFT (the vernier on the WAIT-relative axis, boot
    // 60, under mover load): masks lift TWO beats behind the anchor
    // the chip's slot train itself rides. The window on glass is
    // exactly one step wide -- fat at 0-1, razor at 2, canaries dead
    // at 3 -- and steady under load, because refresh jitter moves the
    // anchor and the lift together (the counted lift of build 58
    // could not follow, and shattered banked). The knob remains: the
    // armed cart overrides K; K=15 never lifts (mask-efficacy check).
    if (span_wr && (st == S_ADV || st == S_LATW || st == S_RUN)) begin
      if (k_use != 4'd15) begin
        if (!wanch) begin
          if (st == S_LATW && !c_wait &&
              (wait_seen || latc <= 4'd2)) begin
            wanch <= 1'b1;
            if (k_use == 4'd0) begin
              c_ub_n <= 1'b0;
              c_lb_n <= 1'b0;
            end
          end
        end else begin
          if (wk_ct != 4'hF) wk_ct <= wk_ct + 4'd1;
          if (wk_ct == k_use - 4'd1) begin
            c_ub_n <= 1'b0;
            c_lb_n <= 1'b0;
          end
        end
      end
    end
    if (!rst_n) begin
      st <= S_RST; cfg_done <= 1'b0; cfg_wait <= 8'd200;
      c_ce_n <= 1'b1; c_adv_n <= 1'b1; c_cre <= 1'b0; c_we_n <= 1'b1;
      c_oe_n <= 1'b1; c_ub_n <= 1'b0; c_lb_n <= 1'b0;
      c_dq_oe <= 1'b0; c_clk_en <= 1'b0;
    end else case (st)
      S_RST:                          // power-up settle, then program BCR
        if (cfg_wait != 0) cfg_wait <= cfg_wait - 1'b1;
        else begin
          c_cre <= 1'b1;              // CRE-high ASYNC write of the BCR:
          c_a <= 6'b001000;           // A[19:18]=10 selects the BCR;
          c_dq_o <= BCR; c_dq_oe <= 1'b1;   // value on DQ (low addr bits)
          c_ce_n <= 1'b0; c_adv_n <= 1'b0; c_we_n <= 1'b0;
          cfg_wait <= 8'd6;           // ~140 ns write pulse, generous
          st <= S_CFG1;
        end
      S_CFG1: begin
        c_adv_n <= 1'b1;
        if (cfg_wait != 0) cfg_wait <= cfg_wait - 1'b1;
        else begin
          c_ce_n <= 1'b1; c_we_n <= 1'b1; c_cre <= 1'b0; c_dq_oe <= 1'b0;
          cfg_wait <= 8'd6;
          st <= S_CFG2;
        end
      end
      S_CFG2:
        if (cfg_wait != 0) cfg_wait <= cfg_wait - 1'b1;
        else begin cfg_done <= 1'b1; c_clk_en <= 1'b1; st <= S_IDLE; end
      S_IDLE:
        if (go) begin
          span_wr <= wr;
          if (wr) begin               // writes: sub-spans bounded at the
            left <= 8'd126 - {1'b0, addr[6:0]};   // row's usable end; the
            w_row <= addr[21:7];      // stream reopens past the tail
            w_more <= 1'b0;           // (S_WNEXT) if the client continues
            c_a <= addr[21:16];
            c_dq_o <= addr[15:0];
            c_dq_oe <= 1'b1;
            c_ce_n <= 1'b0; c_adv_n <= 1'b0;
            c_we_n <= 1'b0;
            c_oe_n <= 1'b1;
            // the scribble law (pageprobe, boots 51-54): the write
            // pointer starts 2 halves before the address and its early
            // slots commit the held word-0 onto the cells below. Masks
            // ride from the open through the early window (lifted in
            // S_LATW); on glass their effect is UNPROVEN (build 53:
            // null) -- the proven defense is geometry (row-aligned
            // opens scribble into dead tails). The masks stay as a
            // second line that sim can verify and glass cannot refute.
            c_ub_n <= 1'b1;
            c_lb_n <= 1'b1;
            wk_ct <= 4'd0;
            wanch <= 1'b0;
            latc <= LAT;
            wait_seen <= 1'b0;
            st <= S_ADV;
          end else begin              // reads go through the splitter
            r_cur <= addr; r_rem <= len;
            st <= S_NEXT;
          end
        end
      S_NEXT: begin                   // one legal sub-burst per chip row:
        left  <= sub_len;             // open at the cursor, discard the
        r_rem <= r_rem - sub_len;     // 2-beat preamble, stream at most
        c_a <= r_cur[21:16];          // to the row's usable end, and hop
        c_dq_o <= r_cur[15:0];        // the tail the chip cannot serve
        rskip <= 2'd2;
        r_cur <= r_cur + {14'd0, sub_len} + (sub_hop ? 22'd2 : 22'd0);
        c_dq_oe <= 1'b1;
        c_ce_n <= 1'b0; c_adv_n <= 1'b0;
        c_we_n <= 1'b1;
        c_oe_n <= 1'b1;
        c_ub_n <= 1'b0;
        c_lb_n <= 1'b0;
        latc <= LAT;
        wait_seen <= 1'b0;
        st <= S_ADV;
      end
      S_ADV: begin                    // one-clock address phase
        c_adv_n <= 1'b1;
        // writes: keep driving -- word 0 goes on the bus through the
        // latency window so the chip's first write slot (which comes one
        // clock EARLIER than a read's: no output register on the write
        // path) never samples a floating bus
        c_dq_oe <= span_wr;
        if (span_wr) c_dq_o <= w_data;
        // Boot 33: reads assert OE from the top of the latency window,
        // not two cycles before data. The word-0 capture slot is the
        // S_LATW exit cycle (boot 32 got the COUNT right -- the probe's
        // 256-word map is green everywhere but each burst's first word),
        // but with OE asserted only at latc==2 the chip's driver had one
        // cycle of turnaround and word 0 sampled the bus keeper's
        // residue: burst 1 read 0x0000 and was right by LUCK (its true
        // first half IS zero -- the address-phase residue of a 0x20000
        // open), bursts 2-4 read their address residue and went red.
        c_oe_n <= span_wr;
        st <= S_LATW;
      end
      S_LATW: begin                   // WAIT paces the start of data; the
        if (latc != 0) latc <= latc - 1'b1;   // LAT counter is only a floor
        if (span_wr) c_dq_o <= w_data;        // word 0 held on the bus

        // boot-verified: write slots DO begin one clock before read
        // slots (boot 7's symmetric revert broke the picture wholesale;
        // boot 6's write-early was the correct alignment)
        if (wait_r) wait_seen <= 1'b1;
        // Boot 37's probe (photographed, decoded): real WRITE bursts
        // committed their first beats twice -- the chip's write slots
        // open earlier than the latency floor when WAIT falls early
        // (refresh jitter makes the count vary). WAIT's fall is the
        // authority for the write start, exactly as boot 34 made it
        // for reads; the latc floor remains only for a WAIT that
        // never spoke.
        // Boot 38's cramscope + the RDLY confession: the chip's first
        // READ datum arrives when ITS WAIT says so, not when the
        // latency counter runs out -- a counter-timed capture reads the
        // first datum twice and the whole burst lands one half behind,
        // parity-scrambled (the mover's red map). WAIT's observed fall
        // anchors the read start now, floor only for a silent WAIT --
        // the same authority boots 32-34 gave the read EXIT and boot 38
        // gave the write start.
        // the wait_fell read exit was an UNPROVEN experiment that rode
        // into builds 39/40 and shifted the real chip's first capture
        // one cycle (the odd half -- the white backdrop). The read exit
        // returns to boot-32/34's glass-proven form; only the discard
        // is new.
        if (!wait_r && (span_wr
              ? (wait_seen || latc <= 4'd2)
              : ((latc <= 4'd1) && (wait_seen || latc == 4'd0)))) begin
          st <= S_RUN;
          // Boot 32 (the segment probe's photographed bytes, twice): the
          // chip's first READ datum is already on the bus during this
          // exit cycle, one WAIT-relative cycle before boots 1-31
          // believed. Capturing only from S_RUN lost it -- every read
          // burst delivered words 1..N and the mover paired halves
          // {hi(i-1),lo(i)}. On the framebuffer path the same slip was
          // an invisible one-pixel line shift. Capture word 0 here.
          if (!span_wr) begin
            if (rskip != 2'd0) rskip <= rskip - 2'd1;
            else begin
              r_data <= c_dq_i; r_step <= 1'b1;
              left <= left - 1'b1;
              if (left == 8'd1) begin latc <= 4'd3; st <= S_TAIL; end
            end
          end
        end
      end
      S_RUN: if (!wait_r) begin       // a WAITed cycle transfers nothing
        if (span_wr) begin            // capture the show-ahead head, then
          c_dq_o <= w_data; c_dq_oe <= 1'b1; c_we_n <= 1'b0;
          w_step <= 1'b1;             // pop it for the next capture
          if (w_end || left == 8'd1) begin
            w_more <= !w_end;         // row-forced end: reopen past the
            latc <= 4'd2; st <= S_END;   // tail and keep streaming
          end
          left <= left - 1'b1;
        end else begin
          if (rskip != 2'd0) rskip <= rskip - 2'd1;
          else begin
            r_data <= c_dq_i; r_step <= 1'b1;
            left <= left - 1'b1;
            if (left == 8'd1) begin latc <= 4'd3; st <= S_TAIL; end
          end
        end
      end
      S_TAIL:                         // ignored streaming beats: the
        if (!wait_r) begin            // burst overruns into the seam's
          if (latc != 0) latc <= latc - 1'b1;   // territory; nothing
          else begin latc <= 4'd2; st <= S_END; end   // captured there
        end
      S_WNEXT: begin                  // write reopen past the row tail:
        left  <= 8'd126;              // the client's stream continues on
        w_row <= w_nrow;              // the next row's first usable half
        w_more <= 1'b0;
        c_a <= w_nrow[14:9];
        c_dq_o <= {w_nrow[8:0], 7'd0};
        c_dq_oe <= 1'b1;
        c_ce_n <= 1'b0; c_adv_n <= 1'b0;
        c_we_n <= 1'b0;
        c_oe_n <= 1'b1;
        c_ub_n <= 1'b1;
        c_lb_n <= 1'b1;
        wk_ct <= 4'd0;
        wanch <= 1'b0;                // masked early window, as at S_IDLE
                                      // (and the reopen's scribble lands
                                      // in a dead tail regardless)
        latc <= LAT;
        wait_seen <= 1'b0;
        st <= S_ADV;
      end
      S_END: begin                    // the burst keeps clocking while CE
        c_ub_n <= 1'b1;               // is low, so MASK the trailing
        c_lb_n <= 1'b1;               // cycles (UB/LB gate writes per
        if (latc != 0) latc <= latc - 1'b1;   // word) with CE, WE and the
        else begin                    // final data word held through the
          c_ce_n <= 1'b1;             // chip's commit pipeline --
          c_we_n <= 1'b1;             // releasing early latched a
          c_oe_n <= 1'b1;             // FLOATING bus: the rainbow
          c_dq_oe <= 1'b0;            // wireframe of the second boot
          if (span_wr ? !w_more : (r_rem == 8'd0))
            done <= 1'b1;             // only the FINAL sub-burst
                                      // completes the client's span
          // (build 52 tried longer write close/recovery here against
          // the scribble: NULL on glass, evicted -- the mechanism was
          // never timing)
          latc <= 4'd2;               // minimum CE-high recovery: back-to-
          st <= S_RCV;                // back bursts corrupted the address
        end                           // latch of boot 4's short spans
      end
      S_RCV:                          // CE stays high through recovery
        if (latc != 0) latc <= latc - 1'b1;
        else st <= span_wr ? (w_more ? S_WNEXT : S_IDLE)
                           : (r_rem != 8'd0 ? S_NEXT : S_IDLE);
      default: st <= S_IDLE;
    endcase
  end

endmodule
`default_nettype wire
