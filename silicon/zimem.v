// zimem.v -- PROGRAM MEMORY IN THE SRAM (docs/ZETA0-FRONTIER.md, 19).
//
// The program used to live in 8,192 words of block RAM inside zvm. Block RAM
// ran out (308 of 308 M10K) while TND still wanted room, so the program now
// lives in the Pocket's asynchronous SRAM -- 128K x 16, of which IMEM takes
// the low 64K half-words (IMEM_WORDS 32-bit words, word w at halves 2w and
// 2w + 1) -- and zvm fetches through a small cache. This module is the
// SRAM's one master for the console:
//
//   REFILL  zvm missed: read the four words of line `ic_line` (eight halves)
//           and hand them over one word at a time (ic_we / ic_wo / ic_wd),
//           then ic_done for a cycle. The VM stalls while it waits.
//   WRITE   the loader's boot words and the overlay mover's copies land here
//           (prog_we / prog_addr / prog_wdata). prog_busy holds the writer
//           off while a write is in flight; every write also invalidates the
//           whole cache (ic_flush), which is cheap -- writes come at boot and
//           on the frames an overlay pages in, never while the VM runs.
//   PASS    otherwise the SRAM is offered to a guest (the Pocket's tape
//           recorder) through g_*: the guest asks, is granted, drives its own
//           access and lets go. The console never waits on the guest: a
//           refill or a write is taken at the next access boundary.
//
// TIMING is the recorder's, measured on glass at build 106: a write holds
// address and data five clocks with WE low for two; a read samples after
// three. A word is two halves; a line is eight.
`default_nettype none

module zimem #(
    parameter PAW = 15                 // program address width (IMEM_BITS)
) (
    input  wire           clk,
    // ---- zvm's cache ----
    input  wire           ic_req,      // a line is wanted (held until ic_done)
    input  wire [PAW-1:2] ic_line,
    output reg            ic_we,       // one word of the refill
    output reg  [1:0]     ic_wo,       // ...at this offset in the line
    output reg  [31:0]    ic_wd,
    output reg            ic_done,     // the line is complete (one cycle)
    output reg            ic_flush,    // every line invalid (one cycle)
    // ---- the writers: boot, and the overlay mover ----
    input  wire           prog_we,
    input  wire [PAW-1:0] prog_addr,
    input  wire [31:0]    prog_wdata,
    output wire           prog_busy,   // hold prog_we until this falls
    // ---- a guest (the tape recorder): ask, be granted, let go ----
    input  wire           g_req,
    output wire           g_gnt,
    input  wire [16:0]    g_a,
    input  wire [15:0]    g_do,
    input  wire           g_doe,
    input  wire           g_oe_n,
    input  wire           g_we_n,
    // ---- the SRAM ----
    output wire [16:0]    sram_a,
    output wire [15:0]    sram_do,
    output wire           sram_doe,
    input  wire [15:0]    sram_di,
    output wire           sram_oe_n,
    output wire           sram_we_n
);
  localparam [2:0] S_IDLE = 3'd0, S_READ = 3'd1, S_WRITE = 3'd2, S_GUEST = 3'd3;
  reg [2:0]  st = S_IDLE;
  reg [3:0]  half = 4'd0;              // which half of the line / the word
  reg [2:0]  ph = 3'd0;                // the access's own beats
  reg [16:0] a = 17'd0;
  reg [15:0] dout = 16'd0;
  reg        doe = 1'b0, oe_n = 1'b1, we_n = 1'b1;
  reg [15:0] lo = 16'd0;
  // a write is taken whole: address and data held while it lands
  reg        w_pend = 1'b0;
  reg [PAW-1:0] w_addr = {PAW{1'b0}};
  reg [31:0] w_data = 32'd0;
  // busy from the very cycle a write is offered: the loader emits a word on
  // a clock edge and decides the next one on the following edge, before a
  // registered busy could rise -- and that second word would be dropped
  assign prog_busy = w_pend || prog_we;

  initial begin
    ic_we = 1'b0; ic_wo = 2'd0; ic_wd = 32'd0; ic_done = 1'b0; ic_flush = 1'b0;
  end

  wire guest = (st == S_GUEST);
  assign g_gnt     = guest;
  assign sram_a    = guest ? g_a    : a;
  assign sram_do   = guest ? g_do   : dout;
  assign sram_doe  = guest ? g_doe  : doe;
  assign sram_oe_n = guest ? g_oe_n : oe_n;
  assign sram_we_n = guest ? g_we_n : we_n;

  always @(posedge clk) begin
    ic_we <= 1'b0; ic_done <= 1'b0; ic_flush <= 1'b0;
    if (prog_we && !w_pend) begin
      w_pend <= 1'b1; w_addr <= prog_addr; w_data <= prog_wdata;
    end
    case (st)
      S_IDLE: begin
        oe_n <= 1'b1; we_n <= 1'b1; doe <= 1'b0; half <= 4'd0; ph <= 3'd0;
        if (ic_req && !ic_done) st <= S_READ;     // (not the line just done:
                                                  // zvm lets go a cycle late)
        else if (w_pend)  st <= S_WRITE;
        else if (g_req)   st <= S_GUEST;
      end
      // eight halves, three beats each: the line's words low half first
      S_READ: begin
        a <= {{(17 - PAW - 1){1'b0}}, ic_line, half[2:0]};
        doe <= 1'b0; we_n <= 1'b1; oe_n <= 1'b0;
        ph <= ph + 3'd1;
        if (ph == 3'd3) begin
          ph <= 3'd0;
          if (!half[0]) lo <= sram_di;
          else begin
            ic_we <= 1'b1; ic_wo <= half[2:1]; ic_wd <= {sram_di, lo};
          end
          if (half == 4'd7) begin
            oe_n <= 1'b1; ic_done <= 1'b1; st <= S_IDLE;
          end else half <= half + 4'd1;
        end
      end
      // two halves, five beats each, WE low for the middle two
      S_WRITE: begin
        a <= {{(17 - PAW - 1){1'b0}}, w_addr, half[0]};
        dout <= half[0] ? w_data[31:16] : w_data[15:0];
        doe <= 1'b1; oe_n <= 1'b1;
        we_n <= !(ph == 3'd1 || ph == 3'd2);
        ph <= ph + 3'd1;
        if (ph == 3'd4) begin
          ph <= 3'd0;
          if (half[0]) begin
            doe <= 1'b0; w_pend <= 1'b0; ic_flush <= 1'b1; st <= S_IDLE;
          end else half <= 4'd1;
        end
      end
      // the guest drives; the console's own work waits only for its letting go
      default: if (!g_req) st <= S_IDLE;
    endcase
  end
endmodule
`default_nettype wire
