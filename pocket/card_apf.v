// card_apf.v -- the card's other half: APF's target_dataslot_read turned
// into the plain fetch port zcard.v already knows how to drink from.
//
// This is the ONLY part of the console that cannot be proven by the
// cross. Machine 1 has no SD; the simulation answers card reads from the
// cart's own .sd images through card_model.v. What lives here is the
// real device's protocol, and its proof is glass.
//
// Two things are inherited rather than invented, both paid for by
// cart_loader.v at boots 17-23 and quoted in its comments:
//
//  * The crossing is a gray-coded ASYNC FIFO, not a toggle handshake.
//    "The firmware streams large files in fast bursts, and a toggle
//    flipping twice inside one sync window is a net no-change -- words
//    silently vanished."
//
//  * Nothing is trusted to arrive quietly. Window writes are accepted
//    ONLY while a request of ours is in flight, so a data slot that APF
//    decides to preload at boot cannot inject words nobody asked for.
//
// Ordering that matters: APF raises done when the FILE is read, but the
// last words may still be in the FIFO. c_done is therefore held back
// until done has been seen AND the FIFO has drained -- zcard sets its
// ready flag on c_done, and a ready that outran its own data would hand
// the console a short transfer that still looked complete.
`default_nettype none

module card_apf #(
    parameter [3:0] WINDOW = 4'h2      // bridge 0x2xxxxxxx is the card's
) (
    // ---- bridge domain (clk_74a) ----
    input  wire        bclk,
    input  wire        brst_n,
    input  wire [31:0] bridge_addr,
    input  wire        bridge_wr,
    input  wire [31:0] bridge_wr_data,
    input  wire        bridge_rd,
    output reg         ds_read,        // rising-edge triggered command
    output reg  [15:0] ds_id,
    output reg  [31:0] ds_slotoffset,
    output reg  [31:0] ds_bridgeaddr,
    output reg  [31:0] ds_length,
    input  wire        ds_done,
    output wire        ds_write,      // the same command, arrow reversed
    output wire [31:0] rd_data,       // what APF reads back out of us
    input  wire        ds_ack,
    input  wire  [2:0] ds_err,
    output reg  [31:0] diag0,        // the card signs its own delivery:
    output reg  [31:0] diag1,        // see spec.CARD_DIAG
    output reg  [31:0] diag2,
    // ---- console domain (clk_zeta) ----
    input  wire        cclk,
    input  wire        crst_n,
    input  wire        c_req,
    input  wire        c_save,        // this request writes the card
    input  wire        sw_we,         // the console filling the save
    input  wire [9:0]  sw_a,          // buffer, in its own clock domain,
    input  wire [31:0] sw_d,          // BEFORE the command goes out
    input  wire [15:0] c_slot,
    input  wire [31:0] c_off,          // words
    input  wire [12:0] c_len,          // words
    output wire        c_we,
    output wire [31:0] c_data,
    output reg         c_done
);
  function [10:0] gray(input [10:0] b); gray = b ^ (b >> 1); endfunction

  // ---- console -> bridge: the request ----------------------------------
  // The parameters are registered a cycle BEFORE the toggle moves, so
  // they are provably stable by the time the far side can see the edge.
  // THE SAVE BUFFER. APF pulls a save out of us through bridge READS,
  // and core_top's read path is a combinational mux -- there is no cycle
  // to spare for a registered memory. MLAB reads are asynchronous, so
  // this answers in the same cycle. It also removes the whole clock
  // crossing: the console fills this in its own domain and the command
  // only goes out afterwards, so nobody is writing while APF reads.
  // "MLAB" alone is not enough: an asynchronous read has no defined
  // read-during-write behaviour, so Quartus refuses to infer memory and
  // builds 32,768 FLIP-FLOPS instead -- 146% of the device. no_rw_check
  // waives the semantics we never rely on: the console fills this buffer
  // and only THEN issues the command, so nothing reads while it writes.
  // M10K, NOT MLAB, since the read below became REGISTERED: the
  // asynchronous read was the whole reason for LUT RAM, and it went
  // when the card came back one word early. As MLABs this buffer was
  // 977 ALM -- 64 LABs of LUT RAM and a 312-ALM read mux, the largest
  // single block of logic outside the datapath -- for what four M10K
  // hold (build 98's fitter ledger). Dual-clock: written on cclk,
  // read on bclk, the loader FIFO's own shape.
  //   [assumed] until glass: the save path is the one thing no sim
  // proves. A boot with save.zol (read 111, save 112, power-cycle,
  // read 114) is the witness.
  (* ramstyle = "M10K" *) reg [31:0] sbuf [0:1023];
  always @(posedge cclk) if (sw_we) sbuf[sw_a] <= sw_d;
  // what the FILL actually put in the first two slots. The card came back
  // holding words 1,2,3 and a zero; registering the read changed nothing,
  // so the shift is either here or in what APF asks for -- and these two
  // bytes say which, without another round of reading code.
  reg [7:0] w0_l;
  reg [7:0] n_rd;              // in-window reads: 4 means APF asked
                              // for exactly the words we offered
  always @(posedge cclk) if (sw_we && sw_a == 10'd0) w0_l <= sw_d[7:0];
  // sbuf[0] holds 111 and the card comes back starting at 222, so APF is
  // reading from word ONE. Stop guessing why: latch the low byte of the
  // FIRST address it actually presents to our window. 00 means it starts
  // where we told it to and the fault is elsewhere; 04 means it begins a
  // word in, and the fix is arithmetic.
  reg [7:0] first_ra;
  reg       ra_seen;
  // REGISTERED, and the card said why: served combinationally, the file
  // came back holding words 1,2,3 and a zero instead of 0,1,2,3. APF
  // samples bridge_rd_data the cycle AFTER it presents the address, by
  // which time the address has moved on -- so an immediate answer is
  // always one word early, and the last sample reads a slot never
  // written. One flop puts every word back under its own address.
  reg [31:0] rd_q;
  always @(posedge bclk) rd_q <= sbuf[bridge_addr[11:2]];
  assign rd_data = rd_q;

  reg        q_save;
  reg [15:0] q_slot;
  reg [31:0] q_off;
  reg [12:0] q_len;
  reg        q_armed, req_tog;
  always @(posedge cclk) begin
    if (!crst_n) begin
      q_armed <= 1'b0; req_tog <= 1'b0; q_save <= 1'b0;
      q_slot <= 16'd0; q_off <= 32'd0; q_len <= 13'd0;
    end else begin
      q_armed <= 1'b0;
      if (c_req) begin
        q_slot <= c_slot; q_off <= c_off; q_len <= c_len;
        q_save <= c_save;
        q_armed <= 1'b1;                       // ...toggle next cycle
      end else if (q_armed) req_tog <= ~req_tog;
    end
  end

  reg rt1, rt2, rt3;
  always @(posedge bclk) begin
    if (!brst_n) begin rt1 <= 1'b0; rt2 <= 1'b0; rt3 <= 1'b0; end
    else begin rt1 <= req_tog; rt2 <= rt1; rt3 <= rt2; end
  end
  wire new_req = rt3 ^ rt2;

  // ---- bridge side: issue the command, capture the words ---------------
  wire in_win = (bridge_addr[31:28] == WINDOW);
  reg        inflight;
  // Quartus never recognised this as memory on its own -- not inferred,
  // not even listed as uninferred -- and it came out as 32,987 flops,
  // 105% over the device. Told directly, it is one M10K.
  (* ramstyle = "M10K" *) reg [31:0] fifo [0:511];
  reg [10:0] wptr, wgray;
  reg        done_b;                   // APF says the file has been read
  reg        is_save;                  // ...or written
  reg [7:0]  n_read, n_ack, n_done;    // what the OS actually did
  reg [2:0]  err_l;
  reg [15:0] n_win, n_any, n_cap;
  reg        ack_1, done_1, saw_ack;
  reg        wr_pulse;
  assign     ds_write = wr_pulse;

  always @(posedge bclk) begin
    if (!brst_n) begin
      ds_read <= 1'b0; wr_pulse <= 1'b0; is_save <= 1'b0;
      inflight <= 1'b0; done_b <= 1'b0;
      wptr <= 11'd0; wgray <= 11'd0;
      n_read <= 8'd0; n_ack <= 8'd0; n_done <= 8'd0; err_l <= 3'd0;
      n_win <= 16'd0; n_any <= 16'd0; n_cap <= 16'd0;
      first_ra <= 8'd0; ra_seen <= 1'b0; n_rd <= 8'd0;
      ack_1 <= 1'b0; done_1 <= 1'b0; saw_ack <= 1'b0;
      diag0 <= 32'd0; diag1 <= 32'd0; diag2 <= 32'd0;
      ds_id <= 16'd0; ds_slotoffset <= 32'd0;
      ds_bridgeaddr <= 32'd0; ds_length <= 32'd0;
    end else begin
      ds_read <= 1'b0;
      wr_pulse <= 1'b0;
      // every bridge write, and every one aimed at our window, counted
      // WITHOUT the inflight gate -- a write that arrives when we did not
      // ask is exactly the thing worth knowing about
      if (bridge_rd && in_win) begin
        if (~&n_rd) n_rd <= n_rd + 8'd1;
        if (!ra_seen) begin
          first_ra <= bridge_addr[7:0];
          ra_seen  <= 1'b1;
        end
      end
      if (bridge_wr) begin
        if (~&n_any) n_any <= n_any + 16'd1;
        if (in_win && ~&n_win) n_win <= n_win + 16'd1;
      end
      ack_1  <= ds_ack;
      done_1 <= ds_done;
      if (ds_ack && !ack_1 && ~&n_ack) n_ack <= n_ack + 8'd1;
      if (ds_done && !done_1) begin
        if (~&n_done) n_done <= n_done + 8'd1;
        err_l <= ds_err;             // the OS's own verdict on the command
      end
      diag0 <= {5'd0, err_l, n_done, n_ack, n_read};
      diag1 <= {n_any, n_win};
      diag2 <= {first_ra, w0_l, n_rd, n_cap[7:0]};
      if (new_req) begin
        if (~&n_read) n_read <= n_read + 8'd1;
        saw_ack <= 1'b0;
        ra_seen <= 1'b0;               // per REQUEST, not per lifetime:
                                       // the first in-window read after
                                       // reset may be nobody's business                       // slot offsets and lengths
        ds_id         <= q_slot;               // are BYTES on this side
        ds_slotoffset <= {q_off[29:0], 2'b00};
        ds_bridgeaddr <= {WINDOW, 28'd0};
        ds_length     <= {17'd0, q_len, 2'b00};
        ds_read       <= !q_save;      // read the card, or write it
        wr_pulse      <= q_save;
        is_save       <= q_save;
        inflight      <= 1'b1;
        done_b        <= 1'b0;
      end
      // words only count while WE asked for them: a slot APF chooses to
      // preload cannot inject anything
      if (fifo_we) begin
        if (~&n_cap) n_cap <= n_cap + 16'd1;
        wptr  <= wptr + 11'd1;
        wgray <= gray(wptr + 11'd1);
      end
      // ds_done is a LEVEL -- "asserted upon command finish UNTIL NEXT
      // COMMAND IS ISSUED" -- so it is still high from the previous
      // command when the next inflight is set. Clearing on the level
      // dropped every word of every request after the first: they were
      // counted (n_win is ungated) and never captured. Take the RISING
      // EDGE, and only after the OS has acknowledged THIS command.
      if (ds_ack && !ack_1) saw_ack <= 1'b1;
      if (inflight && saw_ack && ds_done && !done_1) begin
        inflight <= 1'b0;
        saw_ack  <= 1'b0;
        done_b   <= 1'b1;
      end
    end
  end

  // ---- the RAM itself: ONE always block per port, and nothing else in
  // them. Written with the ports folded into the surrounding logic, this
  // FIFO was not recognised as memory at all -- 32,986 registers, and the
  // design missed the device by 105%. cart_loader.v gets away with a
  // fatter write block; this template is the one that always works.
  wire fifo_we = inflight && bridge_wr && in_win;
  // words actually CAPTURED, against n_win's ungated count: the two
  // disagreeing is the whole story of a dropped transfer
  reg [31:0] fifo_q;
  always @(posedge bclk) if (fifo_we) fifo[wptr[8:0]] <= bridge_wr_data;
  always @(posedge cclk) fifo_q <= fifo[rptr[8:0]];
  assign c_data = fifo_q;              // valid the cycle c_we is high
  // c_we IS pop_d, not a register of it. fifo_q holds the popped word
  // during the very cycle pop_d is high, so registering c_we again made
  // the flag lag its own data: zcard stored the NEXT word each time and
  // the last pulse captured a slot never written. The copy ran, wrote
  // what it was handed, and the landed word read zero.

  // ---- bridge -> console: the words, then the completion ---------------
  reg [10:0] wg1 = 11'd0, wg2 = 11'd0, rptr = 11'd0;
  reg        db1 = 1'b0, db2 = 1'b0, pop_d = 1'b0;
  reg        told = 1'b1;              // c_done is one pulse, not a level
  wire       empty = (gray(rptr) == wg2);

  always @(posedge cclk) begin
    wg1 <= wgray; wg2 <= wg1;          // gray: one bit changes per step,
    db1 <= done_b; db2 <= db1;         // so a torn sample is still a
    c_done <= 1'b0;                    // legal neighbour
    if (c_req) told <= 1'b0;           // a fresh request owes a completion
    pop_d <= 1'b0;
    if (!empty) begin                  // address now, data next cycle --
      rptr  <= rptr + 11'd1;           // so the write pulse follows it
      pop_d <= 1'b1;
    end else if (db2 && !told) begin   // drained AND finished: only now
      c_done <= 1'b1;                  // may zcard call itself ready
      told   <= 1'b1;
    end
  end
  assign c_we = pop_d;
  initial begin c_done = 1'b0; end

endmodule
`default_nettype wire
