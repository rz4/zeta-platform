// cram_pair_tb.v -- cram_burst wired to its checking chip model, exactly
// as one chip of the pair will be wired in core_top. tb_cram.cpp drives
// the span interface; the model polices the pins.
`default_nettype none

module cram_pair_tb (
    input  wire        clk,
    input  wire        rst_n,
    output wire        cfg_done,
    input  wire        go,
    input  wire        wr,
    input  wire [21:0] addr,
    input  wire [7:0]  len,
    input  wire        w_end,
    output wire        w_step,
    input  wire [15:0] w_data,
    output wire        r_step,
    output wire [15:0] r_data,
    output wire        done_o,
    output wire        idle_o,
    output wire        violation,
    output wire [3:0]  vcode
);
  wire [5:0]  a;
  wire [15:0] dq_o, dq_chip;
  wire        dq_oe, chip_drive;
  wire        adv_n, cre, ce_n, we_n, oe_n, ub_n, lb_n, clk_en;
  wire        wt;

  cram_burst u_ctl (
    .clk(clk), .rst_n(rst_n), .cfg_done(cfg_done),
    .swp_en(1'b0), .swp_k(4'd0),
    .go(go), .wr(wr), .addr(addr), .len(len), .w_end(w_end),
    .w_step(w_step), .w_take(), .w_data(w_data),
    .r_step(r_step), .r_data(r_data),
    .idle(idle_o), .done(done_o),
    .c_wait(wt),
    .c_a(a), .c_dq_o(dq_o), .c_dq_oe(dq_oe), .c_dq_i(dq_chip),
    .c_clk_en(clk_en), .c_adv_n(adv_n), .c_cre(cre),
    .c_ce_n(ce_n), .c_we_n(we_n), .c_oe_n(oe_n),
    .c_ub_n(ub_n), .c_lb_n(lb_n));

  cram_sync_chip u_chip (
    .clk(clk), .rst_n(rst_n),
    .c_a(a), .dq_in(dq_o), .dq_drive(dq_oe),
    .dq_out(dq_chip), .chip_drive(chip_drive),
    .c_adv_n(adv_n), .c_cre(cre), .c_ce_n(ce_n),
    .c_we_n(we_n), .c_ub_n(ub_n), .c_lb_n(lb_n),
    .c_oe_n(oe_n), .wait_out(wt),
    .violation(violation), .vcode(vcode));

  /* verilator lint_off UNUSEDSIGNAL */
  wire _u = &{1'b0, ub_n, lb_n, clk_en, chip_drive};
  /* verilator lint_on UNUSEDSIGNAL */

endmodule
`default_nettype wire
