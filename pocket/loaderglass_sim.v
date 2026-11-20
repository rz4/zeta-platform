// loaderglass_sim.v -- the WHOLE delivery path as hardware runs it:
// APF bridge writes -> cart_loader (74 MHz domain, gray FIFO) ->
// zeta_glass's boot port (core domain) -> the machine, with the CRAM
// pair attached as checking models. This is the gate that was missing
// when build 36 shipped: loader_check proves the loader alone,
// glass_check boots politely through the ports -- neither streams a
// segment through the loader at bridge pace against the real
// boot_busy. Exactly core_top's wiring, minus real pads.
`default_nettype none

module loaderglass_sim (
    // bridge side, its own clock like clk_74a
    input  wire        bclk,
    input  wire        brst_n,
    input  wire [31:0] bridge_addr,
    input  wire        bridge_wr,
    input  wire [31:0] bridge_wr_data,
    input  wire        dataslot_allcomplete,
    // console side
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] pad,
    output wire        cart_ready,
    output wire        ce_pix,
    output wire [23:0] rgb,
    output wire        hs, vs, de,
    output wire        trapped,
    output wire        cram_violation
);
  wire        cl_we, cl_busy;
  wire [1:0]  cl_kind;
  wire [22:0] cl_addr;
  wire [31:0] cl_data;

  cart_loader u_cart (
    .bclk(bclk), .brst_n(brst_n),
    .bridge_addr(bridge_addr), .bridge_wr(bridge_wr),
    .bridge_wr_data(bridge_wr_data),
    .dataslot_allcomplete(dataslot_allcomplete),
    .cclk(clk), .apply_cart(1'b1), .boot_busy(cl_busy),
    .boot_we(cl_we), .boot_kind(cl_kind),
    .boot_addr(cl_addr), .boot_data(cl_data),
    .cart_ready(cart_ready));

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

  zeta_glass u_glass (
    .clk(clk), .rst_n(rst_n), .core_en(cart_ready), .ce_in(1'b0),
    .pad(pad),
    .boot_we(cl_we), .boot_kind(cl_kind),
    .boot_addr(cl_addr), .boot_data(cl_data),
    .boot_done(cart_ready),
    .ce_pix(ce_pix), .rgb(rgb), .hs(hs), .vs(vs), .de(de),
    .snd_strobe(), .snd_sample(), .trapped(trapped),
    .boot_busy(cl_busy),
    .c0_wait(wt0), .c1_wait(wt1),
    .c0_a(a0), .c0_dq_o(dqo0), .c0_dq_oe(oe0), .c0_dq_i(dqi0),
    .c0_clk_en(ck0), .c0_adv_n(adv0), .c0_cre(cre0),
    .c0_ce_n(ce0), .c0_ce1_n(ce0b), .c0_we_n(we0), .c0_oe_n(roe0),
    .c0_ub_n(ub0), .c0_lb_n(lb0),
    .c1_a(a1), .c1_dq_o(dqo1), .c1_dq_oe(oe1), .c1_dq_i(dqi1),
    .c1_clk_en(ck1), .c1_adv_n(adv1), .c1_cre(cre1),
    .c1_ce_n(ce1), .c1_ce1_n(ce1b), .c1_we_n(we1), .c1_oe_n(roe1),
    .c1_ub_n(ub1), .c1_lb_n(lb1),
    .sd_req(sd_req), .sd_save(sd_save), .sd_sw_we(), .sd_sw_a(),
    .sd_sw_d(), .sd_slot(sd_slot), .sd_off(sd_off),
    .sd_len(sd_len),
    .sd_we(sd_we), .sd_data(sd_data), .sd_done(sd_done),
    .card_diag0(32'd0), .card_diag1(32'd0), .card_diag2(32'd0)
  );

  // die 1 of chip 0 (build 105): the same bus, its own enable
  cram_sync_chip u_chip0 (
    .clk(clk), .rst_n(rst_n),
    .c_a(a0), .dq_in(dqo0), .dq_drive(oe0),
    .dq_out(dqi0a), .chip_drive(cd0a),
    .c_adv_n(adv0), .c_cre(cre0), .c_ce_n(ce0),
    .c_we_n(we0), .c_ub_n(ub0), .c_lb_n(lb0),
    .c_oe_n(roe0), .wait_out(wt0a),
    .violation(v0a), .vcode(vc0a));

  cram_sync_chip u_chip0b (
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
  cram_sync_chip u_chip1 (
    .clk(clk), .rst_n(rst_n),
    .c_a(a1), .dq_in(dqo1), .dq_drive(oe1),
    .dq_out(dqi1a), .chip_drive(cd1a),
    .c_adv_n(adv1), .c_cre(cre1), .c_ce_n(ce1),
    .c_we_n(we1), .c_ub_n(ub1), .c_lb_n(lb1),
    .c_oe_n(roe1), .wait_out(wt1a),
    .violation(v1a), .vcode(vc1a));

  cram_sync_chip u_chip1b (
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
endmodule
