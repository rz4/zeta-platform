// zcard.v -- the card's staging buffer: what makes SD content arrive
// without ever touching a memory the running game is holding.
//
// cart_loader.v names the hazard in its own comments, paid for on glass
// at boots 22/23: "zvm's external port drops writes whenever the VM holds
// the memory, so whatever arrives during a frame evaporates". A card that
// streamed straight into DMEM would lose exactly as much of its transfer
// as the cart's frames are long. So nothing streams into DMEM. Words land
// HERE, in a buffer nobody else is holding, and the console copies them
// out in one legislated instant when it knows the memory is its own --
// the same instant the mover uses, for the same reason.
//
// The card port (c_*) is a seam, not a protocol: in simulation a
// behavioral model drives it from the cart's own slot images, and on the
// Pocket an APF adapter drives it from target_dataslot_read. Both fill
// the same buffer through the same handshake, so the cross proves the
// console's half and the glass proves the card's half.
//
// This module deliberately does NOT know about SD_LATENCY. It fills as
// fast as the card allows; zeta_top holds the result until the frame the
// law says it may be seen. Determinism is legislated up there, where the
// frames are counted -- here we only fetch.
`default_nettype none

module zcard (
    input  wire        clk,
    input  wire        rst_n,
    // the console's request: one pulse, parameters valid with it
    input  wire        req,
    input  wire [15:0] slot,
    input  wire [31:0] off,          // WORD offset into the slot's file
    input  wire [12:0] len,          // words, 1..SD_MAX
    output reg         ready,        // every word of this request is here
    output reg  [15:0] n_stage,       // words that crossed INTO the
                                      // console domain and were stored --
                                      // against card_apf's capture count,
                                      // this brackets the crossing itself
    // the staging read port: the console's copy, one word per cycle
    input  wire [12:0] raddr,
    output reg  [31:0] rdata,
    // the card port -- sim model or APF adapter
    output reg         c_req,
    output reg  [15:0] c_slot,
    output reg  [31:0] c_off,
    output reg  [12:0] c_len,
    input  wire        c_we,          // one word presented
    input  wire [31:0] c_data,
    input  wire        c_done         // ...and that was the last of them
);
  `include "params.vh"

  reg [31:0] stage [0:SD_MAX-1];
  reg [12:0] wp;                      // where the next arriving word goes

  always @(posedge clk) begin
    if (c_we) stage[wp] <= c_data;
    rdata <= stage[raddr];
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      ready <= 1'b0; c_req <= 1'b0; wp <= 13'd0; n_stage <= 16'd0;
      c_slot <= 16'd0; c_off <= 32'd0; c_len <= 13'd0;
    end else begin
      c_req <= 1'b0;                  // one-cycle request pulse
      if (req) begin                  // a new request supersedes anything
        ready  <= 1'b0;               // still in flight: the console only
        wp     <= 13'd0;              // ever has one outstanding (spec)
        c_slot <= slot;
        c_off  <= off;
        c_len  <= len;
        c_req  <= 1'b1;
      end else begin
        if (c_we) begin
          wp <= wp + 13'd1;
          if (~&n_stage) n_stage <= n_stage + 16'd1;
        end
        if (c_done) ready <= 1'b1;
      end
    end
  end

endmodule
`default_nettype wire
