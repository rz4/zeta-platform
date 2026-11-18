// card_model.v -- the SD card, as the simulation sees it. NOT SYNTHESIZED.
//
// The companion of cram_sync_chip.v: where that one models the chip the
// console really talks to, this one models the device the console cannot
// carry inside itself. Machine 1 answers a card read from the cart's own
// .sd images (see zeta/asm.py); this gives machine 2 the same answers, so
// the cross can hold a streaming cart to the law bit for bit.
//
// The card is deliberately FAST here -- one word per cycle, no seeks, no
// gaps. That is not a claim about SD hardware; it is the point. The
// console's determinism does not come from the device being predictable,
// it comes from spec.SD_LATENCY: zeta_top holds the data until the frame
// the law says it may be seen, however early it arrived. Making the model
// as fast as possible is therefore the HARSHEST test of that mechanism,
// exactly as the cross firing audio ticks back to back is harsher than
// the 900-clock gaps of real glass.
//
// Slot images live at fixed strides in one flat memory so the harness can
// write them as a single hex file; reads past a slot's real length find
// the zeros the harness left there, which is the answer the law gives too.
`default_nettype none

module card_model (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        c_req,
    input  wire        c_save,        // a save sends words the OTHER way:
                                      // the model takes them and returns
                                      // nothing, so zcard stages nothing
    input  wire [15:0] c_slot,
    input  wire [31:0] c_off,
    input  wire [12:0] c_len,
    output reg         c_we,
    output reg  [31:0] c_data,
    output reg         c_done
);
  `include "params.vh"

  localparam SLOT_WORDS = SD_SIM_SLOT_WORDS;   // spec bounds the model
  localparam SLOTS = SD_SIM_SLOTS;

  reg [31:0] img [0:SLOTS*SLOT_WORDS-1];
  integer i;
  initial begin
    for (i = 0; i < SLOTS*SLOT_WORDS; i = i + 1) img[i] = 32'd0;
    $readmemh("cart_sd.hex", img);
  end

  reg [12:0] left;
  reg [31:0] cur;
  reg [15:0] cslot;
  reg        run;

  wire [31:0] addr = {29'd0, cslot[2:0]} * SLOT_WORDS + cur;

  always @(posedge clk) begin
    if (!rst_n) begin
      run <= 1'b0; c_we <= 1'b0; c_done <= 1'b0; left <= 13'd0;
    end else begin
      c_we <= 1'b0;
      c_done <= 1'b0;
      if (c_req) begin
        cslot <= c_slot; cur <= c_off;
        left <= c_save ? 13'd0 : c_len;   // a save returns no words --
        run  <= 1'b1;                     // only its completion
      end else if (run) begin
        if (left == 13'd0) begin
          run <= 1'b0;
          c_done <= 1'b1;
        end else begin
          c_we   <= 1'b1;
          c_data <= (cslot < SLOTS && addr < SLOTS*SLOT_WORDS)
                    ? img[addr] : 32'd0;
          cur    <= cur + 32'd1;
          left   <= left - 13'd1;
        end
      end
    end
  end

endmodule
`default_nettype wire
