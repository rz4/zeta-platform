// zeta_tape.v -- THE RECORDER: a session as its pad words, in the SRAM.
//
// Every delay in the machine is legislated, so a cart, the save file it
// started with and one pad word a frame reconstruct a session exactly
// (zeta/tape.py). This module writes that tape while the game runs, into
// the Pocket's SRAM -- 256 KiB wired to the core and tied off since the
// first build -- and answers the bridge when the OS reads it back as a
// nonvolatile slot on the way out.
//
// IT NEVER TOUCHES THE GAME'S CARD. The card is one channel with a
// legislated latency (spec.SD_LATENCY); a recorder that shared it could
// delay a game's own request, and then the session being recorded would
// not be the session that would have happened. The tape goes out by a
// different door: the OS reads this memory when the core exits.
//
// THE IMAGE is zeta/tape.py's ZTP0, word for word (encode() there is the
// reference): four header words, then runs, frames << 16 | pad. A 32-bit
// word w lives in SRAM words 2w (low half) and 2w + 1 (high half).
//
// WHOLE AT EVERY INSTANT. The run being held is rewritten in place each
// frame -- one half-word, its count -- and a new run writes the zero that
// ends the tape BEFORE itself (see NEW below). So there is no
// "finish" step: whenever the OS reads, or the power goes, what is there
// is a valid tape of everything up to the last frame.
//
// THE SRAM'S FIRST USE, and deliberately a slow one. Nothing about the
// part's speed has been measured on glass, so a write holds its address
// and data for five console clocks with WE low for two in the middle
// (39 ns at 51.84 MHz), and a read waits three clocks before it samples.
// The recorder needs a handful of accesses a frame out of 864,000 clocks.
// What this learns about the part is what program memory will need to
// know before it moves in.
`default_nettype none

module zeta_tape #(
    parameter LOG_WORDS = 14            // 2^14 32-bit words: 64 KiB of tape
) (
    input  wire        clk,             // the console clock
    input  wire        run,             // low while the cart loads
    // what the loader delivers, for the cart's sum
    input  wire        boot_we,
    input  wire [1:0]  boot_kind,       // 0 IMEM, 1 DMEM, 2 the segment
    input  wire [22:0] boot_addr,
    input  wire [31:0] boot_data,
    // the frame's pad word, as the machine latches it into REG_PAD
    input  wire        pad_stb,
    input  wire [15:0] pad_word,
    // THE COLLECTION HAS BEGUN (the OS is reading the tape out): record
    // nothing more. The bridge samples a core's read data four of ITS
    // clocks after the address lands -- far too soon for this memory --
    // so core_top fetches each word a read AHEAD, and a tape that was
    // still growing would be read with one frame missing from its
    // middle, which shifts every pad after it. Asynchronous; level.
    input  wire        freeze,
    // the bridge's read of tape word rd_addr: a toggle in, a toggle back
    input  wire        rd_req,
    input  wire [LOG_WORDS-1:0] rd_addr,
    output reg  [31:0] rd_data,
    output reg         rd_ack,
    // the SRAM (both byte lanes always)
    output reg  [16:0] sram_a,
    output reg  [15:0] sram_do,
    output reg         sram_doe,
    input  wire [15:0] sram_di,
    output reg         sram_oe_n,
    output reg         sram_we_n
);
  `include "params.vh"

  localparam [31:0] MAGIC = 32'h5A545030;                 // 'ZTP0'
  localparam [LOG_WORDS-1:0] FIRST = 4;                   // after the header
  localparam [LOG_WORDS-1:0] LAST  = {LOG_WORDS{1'b1}};   // the final word

  // ---- the cart's sum: every word the loader delivers, except the
  // signature it writes about itself (two reserved DMEM windows that the
  // file holds as zeros). Never reset by the cart's own reset: it has to
  // survive the load it is summing. A reload is a full restart of the
  // core (deploy.MENU_SLOT), which starts this at zero again.
  reg [31:0] csum;
  initial csum = 32'd0;
  wire sig_w = (boot_kind == 2'd1) &&
               ((boot_addr >= LOADER_SIG  && boot_addr < LOADER_SIG  + 8) ||
                (boot_addr >= LOADER_SIG2 && boot_addr < LOADER_SIG2 + 8));
  always @(posedge clk) if (boot_we && !sig_w) csum <= csum + boot_data;

  // ---- what there is to do, as half-word accesses ----------------------
  //   HEAD  the four header words and the zero that ends an empty tape
  //   NEW   a run begins: the zero AFTER it first, then the run itself --
  //         in that order, so a tape read between the two writes still
  //         ends where it did
  //   HOLD  the held run's count
  //   READ  both halves of one word, for the bridge
  localparam [2:0] J_IDLE = 3'd0, J_HEAD = 3'd1, J_NEW = 3'd2,
                   J_HOLD = 3'd3, J_READ = 3'd4;
  reg [2:0]  job;
  reg [3:0]  step;                    // which half-word of the job
  reg [2:0]  ph;                      // the access's own beats
  reg        headed;                  // the header is down
  reg        full;                    // the tape reached its last word
  reg        first;                   // no run has begun yet
  reg [LOG_WORDS-1:0] idx;            // the held run's word
  reg [15:0] cur_pad, cur_n;
  reg        pend_pad;                // a frame arrived mid-access
  reg [15:0] pend_word;
  reg [2:0]  fz_s;                    // freeze, synchronised
  reg [2:0]  rq_s;                    // rd_req, synchronised
  reg        pend_rd;
  reg [15:0] rd_lo;

  initial begin
    job = J_IDLE; step = 0; ph = 0; headed = 0; full = 0; first = 1;
    idx = 0; cur_pad = 0; cur_n = 0; pend_pad = 0; pend_word = 0;
    rq_s = 0; fz_s = 0; pend_rd = 0; rd_ack = 0; rd_data = 0; rd_lo = 0;
    sram_a = 0; sram_do = 0; sram_doe = 0; sram_oe_n = 1; sram_we_n = 1;
  end

  // the half-word a job's step writes: {address, data}
  wire [LOG_WORDS-1:0] nxt = idx + 1'b1;
  reg [16:0] wa;
  reg [15:0] wd;
  reg [3:0]  last_step;
  always @(*) begin
    wa = 17'd0; wd = 16'd0; last_step = 4'd0;
    case (job)
      J_HEAD: begin
        last_step = 4'd9;
        wa = {13'd0, step};
        case (step)
          4'd0: wd = MAGIC[15:0];         4'd1: wd = MAGIC[31:16];
          4'd2: wd = LOADER_BUILD[15:0];  4'd3: wd = 16'd0;
          4'd4: wd = csum[15:0];          4'd5: wd = csum[31:16];
          default: wd = 16'd0;            // reserved, and the tape's end
        endcase
      end
      J_NEW: begin
        last_step = 4'd3;
        case (step)
          4'd0: begin wa = {{(16 - LOG_WORDS){1'b0}}, nxt, 1'b0}; wd = 16'd0; end   // the end,
          4'd1: begin wa = {{(16 - LOG_WORDS){1'b0}}, nxt, 1'b1}; wd = 16'd0; end   // moved on
          4'd2: begin wa = {{(16 - LOG_WORDS){1'b0}}, idx, 1'b0}; wd = cur_pad; end
          default: begin wa = {{(16 - LOG_WORDS){1'b0}}, idx, 1'b1}; wd = 16'd1; end
        endcase
        // (17 bits hold {idx, half} for any LOG_WORDS up to 16)
      end
      J_HOLD: begin
        last_step = 4'd0;
        wa = {{(16 - LOG_WORDS){1'b0}}, idx, 1'b1}; wd = cur_n;
      end
      default: ;
    endcase
  end

  wire rq_edge = rq_s[2] ^ rq_s[1];

  always @(posedge clk) begin
    rq_s <= {rq_s[1:0], rd_req};
    fz_s <= {fz_s[1:0], freeze};
    if (rq_edge) pend_rd <= 1'b1;
    if (pad_stb && run && !fz_s[2]) begin pend_pad <= 1'b1; pend_word <= pad_word; end

    case (job)
      J_IDLE: begin
        sram_we_n <= 1'b1; sram_oe_n <= 1'b1; sram_doe <= 1'b0;
        step <= 4'd0; ph <= 3'd0;
        if (run && !headed) job <= J_HEAD;
        else if (pend_pad && headed && !full) begin
          pend_pad <= pad_stb && run && !fz_s[2];   // (one arriving this very clock stays)
          if (first || pend_word != cur_pad || cur_n == 16'hFFFF) begin
            // a new run -- unless there is no word left to end the tape in
            if (!first && idx == LAST - 1'b1) full <= 1'b1;
            else begin
              idx <= first ? FIRST : idx + 1'b1;
              first <= 1'b0;
              cur_pad <= pend_word; cur_n <= 16'd1;
              job <= J_NEW;
            end
          end else begin
            cur_n <= cur_n + 16'd1;
            job <= J_HOLD;
          end
        end
        else if (pend_rd) begin pend_rd <= rq_edge; job <= J_READ; end
      end

      J_READ: begin                     // low half, then high: 3 beats each
        sram_doe <= 1'b0; sram_we_n <= 1'b1; sram_oe_n <= 1'b0;
        sram_a <= {{(16 - LOG_WORDS){1'b0}}, rd_addr, step[0]};
        ph <= ph + 3'd1;
        if (ph == 3'd3) begin
          ph <= 3'd0;
          if (!step[0]) begin rd_lo <= sram_di; step <= 4'd1; end
          else begin
            rd_data <= {sram_di, rd_lo};
            rd_ack <= ~rd_ack;
            sram_oe_n <= 1'b1;
            job <= J_IDLE;
          end
        end
      end

      default: begin                    // a write: five beats a half-word
        sram_oe_n <= 1'b1;
        sram_a <= wa; sram_do <= wd; sram_doe <= 1'b1;
        sram_we_n <= !(ph == 3'd1 || ph == 3'd2);    // low for beats 2 and 3
        ph <= ph + 3'd1;
        if (ph == 3'd4) begin
          ph <= 3'd0;
          if (step == last_step) begin
            if (job == J_HEAD) headed <= 1'b1;
            job <= J_IDLE;
          end else step <= step + 4'd1;
        end
      end
    endcase
  end
endmodule
`default_nettype wire
