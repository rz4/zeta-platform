// zeta_sim.v -- zeta_top with its CRAM pair attached as protocol-checking
// models: the whole machine the frame server drives. A violation here is
// a bus that would have glitched on the real chips.
`default_nettype none

module zeta_sim #(
    parameter WWAIT = 2,
    parameter RECOV = 2,
    parameter RDLY = 0,
    parameter ROFF = 2
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        core_en,
    input  wire        start,
    input  wire [15:0] pad,
    input  wire        boot_we,
    input  wire  [1:0] boot_kind,
    input  wire [22:0] boot_addr,
    input  wire [31:0] boot_data,
    output wire        frame_done,
    output wire        trapped,
    output wire        busy,
    output wire        boot_busy,
    input  wire        snd_tick,
    output wire signed [15:0] snd_sample,
    input  wire        line_req,
    input  wire [8:0]  line_no,
    output wire        line_rdy,
    input  wire [9:0]  px_addr,
    output wire [23:0] px_rgb,
    output wire        cram_violation,
    output wire        snd_busy,
    output wire [287:0] meter        // METER: per-stage paint cycles
);
  wire [5:0]  a0, a1;
  wire [15:0] dqo0, dqo1, dqi0, dqi1;
  wire oe0, oe1, cd0, cd1;
  wire ck0, adv0, cre0, ce0, we0, roe0, ub0, lb0;
  wire ck1, adv1, cre1, ce1, we1, roe1, ub1, lb1;
  wire ce0b, cd0a, cd0b, wt0a, wt0b, v0a, v0b;
  wire [15:0] dqi0a, dqi0b;
  wire [3:0] vc0a, vc0b;
  wire ce1b, cd1a, cd1b, wt1a, wt1b, v1a, v1b;
  wire [15:0] dqi1a, dqi1b;
  wire [3:0] vc1a, vc1b;
  wire v0, v1;
  wire wt0, wt1;
  wire [3:0] vc0, vc1;
  assign cram_violation = v0 | v1;

  wire        sd_req, sd_we, sd_done, sd_save;
  wire [15:0] sd_slot;
  wire [31:0] sd_off, sd_data;
  wire [12:0] sd_len;
  card_model u_card_model (
    .clk(clk), .rst_n(rst_n),
    .c_req(sd_req), .c_save(sd_save), .c_slot(sd_slot), .c_off(sd_off), .c_len(sd_len),
    .c_we(sd_we), .c_data(sd_data), .c_done(sd_done));

  zeta_top u_top (
    .clk(clk), .rst_n(rst_n), .core_en(core_en), .start(start), .pad(pad),
    .boot_we(boot_we), .boot_kind(boot_kind), .boot_done(1'b1),
    .boot_addr(boot_addr), .boot_data(boot_data),
    .frame_done(frame_done), .trapped(trapped), .busy(busy),
    .boot_busy(boot_busy),
    .snd_tick(snd_tick), .snd_sample(snd_sample), .snd_busy(snd_busy),
    .sd_req(sd_req), .sd_save(sd_save), .sd_sw_we(), .sd_sw_a(),
    .sd_sw_d(), .sd_slot(sd_slot), .sd_off(sd_off),
    .sd_len(sd_len),
    .sd_we(sd_we), .sd_data(sd_data), .sd_done(sd_done),
    .card_diag0(32'd0), .card_diag1(32'd0), .card_diag2(32'd0),
    .line_req(line_req), .line_no(line_no), .line_rdy(line_rdy),
    .px_addr(px_addr), .px_rgb(px_rgb),
    .meter(meter),
    .swap_gate(1'b1), .swap_pending(),
    .c0_wait(wt0), .c1_wait(wt1),
    .c0_a(a0), .c0_dq_o(dqo0), .c0_dq_oe(oe0), .c0_dq_i(dqi0),
    .c0_clk_en(ck0), .c0_adv_n(adv0), .c0_cre(cre0),
    .c0_ce_n(ce0), .c0_ce1_n(ce0b), .c0_we_n(we0), .c0_oe_n(roe0),
    .c0_ub_n(ub0), .c0_lb_n(lb0),
    .c1_a(a1), .c1_dq_o(dqo1), .c1_dq_oe(oe1), .c1_dq_i(dqi1),
    .c1_clk_en(ck1), .c1_adv_n(adv1), .c1_cre(cre1),
    .c1_ce_n(ce1), .c1_ce1_n(ce1b), .c1_we_n(we1), .c1_oe_n(roe1),
    .c1_ub_n(ub1), .c1_lb_n(lb1));

  // die 1 of chip 0 (build 105): the same bus, its own enable
  cram_sync_chip #(.WWAIT(WWAIT), .RECOV(RECOV), .RDLY(RDLY), .ROFF(ROFF)) u_chip0 (
    .clk(clk), .rst_n(rst_n),
    .c_a(a0), .dq_in(dqo0), .dq_drive(oe0),
    .dq_out(dqi0a), .chip_drive(cd0a),
    .c_adv_n(adv0), .c_cre(cre0), .c_ce_n(ce0),
    .c_we_n(we0), .c_ub_n(ub0), .c_lb_n(lb0),
    .c_oe_n(roe0), .wait_out(wt0a),
    .violation(v0a), .vcode(vc0a));

  cram_sync_chip #(.WWAIT(WWAIT), .RECOV(RECOV), .RDLY(RDLY), .ROFF(ROFF)) u_chip0b (
    .clk(clk), .rst_n(rst_n),
    .c_a(a0), .dq_in(dqo0), .dq_drive(oe0),
    .dq_out(dqi0b), .chip_drive(cd0b),
    .c_adv_n(adv0), .c_cre(cre0), .c_ce_n(ce0b),
    .c_we_n(we0), .c_ub_n(ub0), .c_lb_n(lb0),
    .c_oe_n(roe0), .wait_out(wt0b),
    .violation(v0b), .vcode(vc0b));
  assign dqi0 = cd0b ? dqi0b : dqi0a;
  assign cd0  = cd0a | cd0b;
  assign wt0  = ce0b ? wt0a : wt0b;      // the enabled die's WAIT
  assign v0   = v0a | v0b;
  assign vc0  = vc0a | vc0b;

  // die 1 of chip 1 (build 105): the same bus, its own enable
  cram_sync_chip #(.WWAIT(WWAIT), .RECOV(RECOV), .RDLY(RDLY), .ROFF(ROFF)) u_chip1 (
    .clk(clk), .rst_n(rst_n),
    .c_a(a1), .dq_in(dqo1), .dq_drive(oe1),
    .dq_out(dqi1a), .chip_drive(cd1a),
    .c_adv_n(adv1), .c_cre(cre1), .c_ce_n(ce1),
    .c_we_n(we1), .c_ub_n(ub1), .c_lb_n(lb1),
    .c_oe_n(roe1), .wait_out(wt1a),
    .violation(v1a), .vcode(vc1a));

  cram_sync_chip #(.WWAIT(WWAIT), .RECOV(RECOV), .RDLY(RDLY), .ROFF(ROFF)) u_chip1b (
    .clk(clk), .rst_n(rst_n),
    .c_a(a1), .dq_in(dqo1), .dq_drive(oe1),
    .dq_out(dqi1b), .chip_drive(cd1b),
    .c_adv_n(adv1), .c_cre(cre1), .c_ce_n(ce1b),
    .c_we_n(we1), .c_ub_n(ub1), .c_lb_n(lb1),
    .c_oe_n(roe1), .wait_out(wt1b),
    .violation(v1b), .vcode(vc1b));
  assign dqi1 = cd1b ? dqi1b : dqi1a;
  assign cd1  = cd1a | cd1b;
  assign wt1  = ce1b ? wt1a : wt1b;      // the enabled die's WAIT
  assign v1   = v1a | v1b;
  assign vc1  = vc1a | vc1b;

  /* verilator lint_off UNUSEDSIGNAL */
  wire _u = &{1'b0, vc0, vc1, cd0, cd1, ck0, ck1};
  /* verilator lint_on UNUSEDSIGNAL */

endmodule
`default_nettype wire
