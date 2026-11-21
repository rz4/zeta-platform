// sram_model.v -- the Pocket's asynchronous SRAM, for simulation: 128K x 16,
// read whenever OE is low (combinational, as the part is), written on every
// clock WE is low (the controllers hold address and data through the pulse).
// Power-on contents are ZERO here; on glass they are whatever they are, and
// the loader writes every word of IMEM before the console runs.
`default_nettype none
module sram_model (
    input  wire        clk,
    input  wire [16:0] a,
    input  wire [15:0] d,
    input  wire        oe_n,
    input  wire        we_n,
    output wire [15:0] q
);
  reg [15:0] mem [0:(1 << 17) - 1];
  integer i;
  initial for (i = 0; i < (1 << 17); i = i + 1) mem[i] = 16'd0;
  always @(posedge clk) if (!we_n) mem[a] <= d;
  assign q = (!oe_n && we_n) ? mem[a] : 16'hDEAD;
endmodule
`default_nettype wire
