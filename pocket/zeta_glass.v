// zeta_glass.v -- the video head: zeta_top turned into a 60 Hz pixel
// stream. This is the module the Analogue Pocket's core_top instantiates.
//
// Timing: 400x360 total, 320x288 active, one pixel every DIV clocks.
// At DIV=6 that wants clk = 400*360*60*6 = 51.84 MHz from the PLL
// (frontier B5; it was DIV=5 and 43.2 MHz through build 105 -- every
// clock count here is written in DIV, so the frame simply has 864,000
// clocks where it had 720,000, and the audio strobe 1,080 where 900).
//
// The framebuffer is DOUBLE-BUFFERED in the CRAM pair: each frame's
// VM+GPU work is kicked early in vblank (after the buffer swap applies)
// and may paint for the WHOLE frame -- ~700k clocks, five times the old
// vblank-only budget. Scanout reads the front buffer line by line (each
// line burst in during the previous line's blank); a frame that paints
// past the next vblank just holds the swap and the display repeats the
// previous frame -- the PS1's own behavior under load.
//
// On real hardware (EXT_CE=1) the dot strobe arrives on ce_in, edge-
// detected from the PLL's actual 8.64 MHz pixel-clock output, so rgb
// transitions sit at a fixed safe offset after each scaler sampling edge.
//
// `zeta glass` proves the stream: the de-gated pixels of a scanned frame
// must be bit-equal to the virtual machine's framebuffer for that frame.
`default_nettype none

module zeta_glass #(parameter DIV = 6, parameter EXT_CE = 0) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        core_en,   // cart complete: let the console run
    input  wire        ce_in,       // hardware dot strobe (EXT_CE=1 only)
    input  wire [15:0] pad,
    // cart boot passthrough (tie off when the cart is baked into BRAM)
    input  wire        boot_we,
    input  wire  [1:0] boot_kind,
    input  wire        boot_done,
    input  wire [22:0] boot_addr,
    input  wire [31:0] boot_data,
    // the pixel stream, valid on ce_pix
    output wire        ce_pix,
    output reg  [23:0] rgb,
    output reg         hs,
    output reg         vs,
    output reg         de,
    // sound: one signed 16-bit sample per strobe, exactly 48 kHz
    // (H_TOT*V_TOT*FPS*DIV / 48000 = 180*DIV clocks per sample, exact)
    output reg         snd_strobe,
    output wire signed [15:0] snd_sample,
    output wire        trapped,
    output wire        pad_stb,       // the tape's tap (zeta_tape.v)
    output wire [15:0] pad_word,
    output wire        boot_busy,
    // the program's SRAM (frontier 19) and its guest
    output wire [16:0] sram_a,
    output wire [15:0] sram_do,
    output wire        sram_doe,
    input  wire [15:0] sram_di,
    output wire        sram_oe_n,
    output wire        sram_we_n,
    input  wire        g_req,
    output wire        g_gnt,
    input  wire [16:0] g_a,
    input  wire [15:0] g_do,
    input  wire        g_doe,
    input  wire        g_oe_n,
    input  wire        g_we_n,
    // the CRAM chip pair (through to real pads, or sim chip models)
    input  wire        c0_wait,
    output wire [5:0]  c0_a,
    output wire [15:0] c0_dq_o,
    output wire        c0_dq_oe,
    input  wire [15:0] c0_dq_i,
    output wire c0_clk_en, c0_adv_n, c0_cre, c0_ce_n, c0_we_n, c0_oe_n,
    output wire c0_ce1_n,              // the second die (build 105)
    output wire c0_ub_n, c0_lb_n,
    input  wire        c1_wait,
    output wire [5:0]  c1_a,
    output wire [15:0] c1_dq_o,
    output wire        c1_dq_oe,
    input  wire [15:0] c1_dq_i,
    output wire c1_clk_en, c1_adv_n, c1_cre, c1_ce_n, c1_we_n, c1_oe_n,
    output wire c1_ce1_n,
    output wire c1_ub_n, c1_lb_n,
    // the card port, passed through to whoever owns the device: a
    // behavioral model in the sims, an APF adapter on the Pocket
    output wire        sd_req,
    output wire        sd_save,
    output wire        sd_sw_we,
    output wire [9:0]  sd_sw_a,
    output wire [31:0] sd_sw_d,
    output wire [15:0] sd_slot,
    output wire [31:0] sd_off,
    output wire [12:0] sd_len,
    input  wire        sd_we,
    input  wire [31:0] sd_data,
    input  wire        sd_done,
    input  wire [31:0] card_diag0,
    input  wire [31:0] card_diag1,
    input  wire [31:0] card_diag2
);
  localparam H_ACT = 320, H_FP = 8,  H_SYNC = 32, H_TOT = 400;
  localparam V_ACT = 288, V_FP = 3,  V_SYNC = 10, V_TOT = 360;

  reg [3:0] div;
  assign ce_pix = (EXT_CE != 0) ? ce_in : (div == DIV - 1);
  reg [8:0] hcnt, vcnt;

  // (h1,v1): the dot the counters move to on this ce; (h2,v2): the one after
  wire [8:0] h1 = (hcnt == H_TOT - 1) ? 9'd0 : hcnt + 1'b1;
  wire [8:0] v1 = (hcnt != H_TOT - 1) ? vcnt :
                  (vcnt == V_TOT - 1) ? 9'd0 : vcnt + 1'b1;
  wire [8:0] h2 = (h1 == H_TOT - 1) ? 9'd0 : h1 + 1'b1;
  wire [8:0] v2 = (h1 != H_TOT - 1) ? v1 :
                  (v1 == V_TOT - 1) ? 9'd0 : v1 + 1'b1;

  reg        start;                  // frame kick: early in vblank, after
  reg        kicked;                 // any pending buffer swap has applied
  reg  [9:0] px_addr;
  reg        line_req;
  reg  [8:0] line_no;
  wire [23:0] px_rgb;

  // ---- THE SCANOUT COMPOSITOR (spec.CO_BASE) --------------------------
  // Blending needs the destination pixel and the framebuffer lives in
  // external CRAM behind a WRITE path -- the paint side cannot read it
  // back. Here it can: the finished picture is already streaming past a
  // pixel per clock with its coordinates in hand. So the blend happens
  // on the way OUT and never touches CRAM at all, which is why cross
  // (framebuffers) is blind to it and glass (the scanned stream) is not.
  wire [415:0] co_flat;
  wire [2:0]   co_n = co_flat[2:0];
  wire [9:0] co_x0 [0:3];
  wire [9:0] co_x1 [0:3];
  wire [9:0] co_y0 [0:3];
  wire [9:0] co_y1 [0:3];
  wire [23:0] co_rgb [0:3];
  wire [4:0]  co_a  [0:3];
  genvar gc;
  generate for (gc = 0; gc < 4; gc = gc + 1) begin : coe
    wire [31:0] wx = co_flat[32*(1 + gc*3)     +: 32];
    wire [31:0] wy = co_flat[32*(2 + gc*3)     +: 32];
    wire [31:0] wc = co_flat[32*(3 + gc*3)     +: 32];
    assign co_x0[gc] = wx[9:0],   co_x1[gc] = wx[19:10];
    assign co_y0[gc] = wy[9:0],   co_y1[gc] = wy[19:10];
    assign co_rgb[gc] = wc[23:0];
    assign co_a[gc]  = (wc[28:24] > 5'd16) ? 5'd16 : wc[28:24];
  end endgenerate

  // (p*(16-a) + c*a) >> 4, written as (p<<4) + a*(c-p): FIVE CONDITIONAL
  // ADDS and no multiplier, the same shape fog's tmul uses, because the
  // DSPs have been 66/66 since the crown.
  function [4:0] blend5(input [4:0] p, input [4:0] c, input [4:0] a);
    reg signed [10:0] d, acc;
    begin
      d   = $signed({1'b0, c}) - $signed({1'b0, p});
      acc = $signed({2'b0, p, 4'b0});
      if (a[0]) acc = acc + d;
      if (a[1]) acc = acc + (d <<< 1);
      if (a[2]) acc = acc + (d <<< 2);
      if (a[3]) acc = acc + (d <<< 3);
      if (a[4]) acc = acc + (d <<< 4);
      blend5 = acc[8:4];
    end
  endfunction

  // LAST live rectangle wins -- they do not blend with each other. That
  // is what keeps this a priority mux and ONE lerp instead of a chain of
  // four, which is what meets timing at the pixel clock.
  wire [3:0] co_hit;
  generate for (gc = 0; gc < 4; gc = gc + 1) begin : cohit
    localparam [2:0] K = gc[2:0];    // a genvar is unsized and cannot go
                                     // in a concatenation; size it once
    assign co_hit[gc] = (co_n > K) && (co_a[gc] != 5'd0)
                        && (h1 >= {1'b0, co_x0[gc]})
                        && (h1 <= {1'b0, co_x1[gc]})
                        && (v1 >= {1'b0, co_y0[gc]})
                        && (v1 <= {1'b0, co_y1[gc]});
  end endgenerate
  wire [1:0] co_k = co_hit[3] ? 2'd3 : co_hit[2] ? 2'd2 :
                    co_hit[1] ? 2'd1 : 2'd0;
  wire       co_on = |co_hit;
  // THE WINNER, REGISTERED (frontier B5). At 51.84 MHz the four hit
  // compares, the priority select and the lerp's five adds ran 1.62 ns
  // over into rgb. Everything they read holds for the whole dot (DIV
  // clocks) and rgb samples on the NEXT ce_pix, so the winning
  // rectangle's colour and alpha can take a register here: settled by the
  // dot's second clock, sampled at its sixth.
  reg        co_on_r;
  reg [14:0] co_c_r;
  reg [4:0]  co_a_r;
  always @(posedge clk) begin
    co_on_r <= co_on;
    co_c_r  <= {co_rgb[co_k][23:19], co_rgb[co_k][15:11], co_rgb[co_k][7:3]};
    co_a_r  <= co_a[co_k];
  end
  wire [4:0] cr = blend5(px_rgb[23:19], co_c_r[14:10], co_a_r);
  wire [4:0] cg = blend5(px_rgb[15:11], co_c_r[9:5],   co_a_r);
  wire [4:0] cb = blend5(px_rgb[7:3],   co_c_r[4:0],   co_a_r);
  wire [23:0] px_out = co_on_r
      ? {cr, cr[4:2], cg, cg[4:2], cb, cb[4:2]} : px_rgb;

  // ---- GRADING (spec.GRADE_SRC), the last thing before the glass -------
  // 32 words, one per 5-bit level, each naming a full 24-bit output --
  // so the three channels get three independent curves and the panel
  // finally gets EIGHT bits instead of a 5-bit value stretched to fill
  // them. After the compositor, because this is the glass and not a
  // layer: a fade drawn there is part of the picture and gets graded
  // with everything else.
  //
  // The read is REGISTERED and that is free: px_rgb was prefetched on
  // the previous ce_pix and h1/v1 hold all the way through the window,
  // so px_out has been settled for four clocks by the time ce_pix
  // samples it. A combinational table would have been 768 flops and
  // three 32-to-1 muxes on a die already at 87%.
  // "MLAB" ALONE DID NOT TAKE: the fitter built three M10K blocks for
  // 768 bits (build 98's RAM summary). The save buffer learned the
  // form that does -- an asynchronous read has no defined
  // read-during-write behaviour, so Quartus wants the waiver.
  (* ramstyle = "no_rw_check, MLAB" *) reg [23:0] gtab [0:31];
  wire        gr_on, gr_we;
  wire [4:0]  gr_a;
  wire [23:0] gr_d;
  reg  [7:0]  gq_r, gq_g, gq_b;
  always @(posedge clk) begin
    if (gr_we) gtab[gr_a] <= gr_d;
    gq_r <= gtab[px_out[23:19]][23:16];
    gq_g <= gtab[px_out[15:11]][15:8];
    gq_b <= gtab[px_out[7:3]][7:0];
  end
  wire [23:0] px_final = gr_on ? {gq_r, gq_g, gq_b} : px_out;
  wire        line_rdy, swap_pending;
  wire        frame_done, busy;
  wire in_vblank = (vcnt >= V_ACT) && (vcnt < V_TOT - 1);

  localparam SND_DIV = 180 * DIV;
  reg [10:0] snd_ct;
  always @(posedge clk) begin
    snd_strobe <= 1'b0;
    if (!rst_n) snd_ct <= 0;
    else if (snd_ct == SND_DIV - 1) begin snd_ct <= 0; snd_strobe <= 1'b1; end
    else snd_ct <= snd_ct + 1'b1;
  end

  zeta_top u_top (
    .clk(clk), .rst_n(rst_n), .core_en(core_en),
    .start(start), .pad(pad),
    .boot_we(boot_we), .boot_kind(boot_kind),
    .boot_done(boot_done),
    .boot_addr(boot_addr), .boot_data(boot_data),
    .boot_busy(boot_busy),
    .sram_a(sram_a), .sram_do(sram_do), .sram_doe(sram_doe), .sram_di(sram_di),
    .sram_oe_n(sram_oe_n), .sram_we_n(sram_we_n),
    .g_req(g_req), .g_gnt(g_gnt), .g_a(g_a), .g_do(g_do), .g_doe(g_doe),
    .g_oe_n(g_oe_n), .g_we_n(g_we_n),
    .frame_done(frame_done), .trapped(trapped), .busy(busy),
    .pad_stb(pad_stb), .pad_word(pad_word),
    .snd_tick(snd_strobe), .snd_sample(snd_sample), .snd_busy(),
    .sd_req(sd_req), .sd_save(sd_save), .sd_sw_we(sd_sw_we),
    .sd_sw_a(sd_sw_a), .sd_sw_d(sd_sw_d),
    .sd_slot(sd_slot), .sd_off(sd_off), .sd_len(sd_len),
    .sd_we(sd_we), .sd_data(sd_data), .sd_done(sd_done),
    .card_diag0(card_diag0), .card_diag1(card_diag1),
    .card_diag2(card_diag2),
    .line_req(line_req), .line_no(line_no), .line_rdy(line_rdy),
    .px_addr(px_addr), .px_rgb(px_rgb), .co_flat(co_flat),
    .gr_on(gr_on), .gr_we(gr_we), .gr_a(gr_a), .gr_d(gr_d),
    .meter(),
    .swap_gate(in_vblank), .swap_pending(swap_pending),
    .c0_wait(c0_wait), .c1_wait(c1_wait),
    .c0_a(c0_a), .c0_dq_o(c0_dq_o), .c0_dq_oe(c0_dq_oe), .c0_dq_i(c0_dq_i),
    .c0_clk_en(c0_clk_en), .c0_adv_n(c0_adv_n), .c0_cre(c0_cre),
    .c0_ce_n(c0_ce_n), .c0_ce1_n(c0_ce1_n), .c0_we_n(c0_we_n), .c0_oe_n(c0_oe_n),
    .c0_ub_n(c0_ub_n), .c0_lb_n(c0_lb_n),
    .c1_a(c1_a), .c1_dq_o(c1_dq_o), .c1_dq_oe(c1_dq_oe), .c1_dq_i(c1_dq_i),
    .c1_clk_en(c1_clk_en), .c1_adv_n(c1_adv_n), .c1_cre(c1_cre),
    .c1_ce_n(c1_ce_n), .c1_ce1_n(c1_ce1_n), .c1_we_n(c1_we_n), .c1_oe_n(c1_oe_n),
    .c1_ub_n(c1_ub_n), .c1_lb_n(c1_lb_n));

  always @(posedge clk) begin
    start <= 1'b0;
    line_req <= 1'b0;
    if (!rst_n) begin
      div <= 0; hcnt <= 0; vcnt <= 0; kicked <= 1'b0;
      hs <= 0; vs <= 0; de <= 0; rgb <= 0; px_addr <= 0;
    end else begin
      div <= ce_pix ? 4'd0 : div + 1'b1;
      // the frame kick: once per vblank, held off until the buffer swap
      // has applied so no paint lands in the buffer being scanned
      if (in_vblank && !kicked && !swap_pending && !busy) begin
        start <= 1'b1;
        kicked <= 1'b1;
      end
      if (ce_pix) begin
        hcnt <= h1; vcnt <= v1;
        if (v1 == V_ACT && h1 == 0) kicked <= 1'b0;   // vblank begins: arm
        // px_rgb was prefetched for (h1,v1) on the previous ce; the line
        // itself was burst in from CRAM during the previous line's blank
        de  <= (h1 < H_ACT) && (v1 < V_ACT);
        rgb <= ((h1 < H_ACT) && (v1 < V_ACT)) ? px_final : 24'd0;
        hs  <= (h1 >= H_ACT + H_FP) && (h1 < H_ACT + H_FP + H_SYNC);
        vs  <= (v1 >= V_ACT + V_FP) && (v1 < V_ACT + V_FP + V_SYNC);
        px_addr <= {v2[0], h2};
        if (h1 == H_ACT) begin       // entering blank: fetch the next line
          if (v1 == V_TOT - 1) begin
            line_req <= 1'b1; line_no <= 9'd0;
          end else if (v1 < V_ACT - 1) begin
            line_req <= 1'b1; line_no <= v1[8:0] + 1'b1;
          end
        end
      end
    end
  end

  /* verilator lint_off UNUSEDSIGNAL */
  wire _u2 = line_rdy;               // deterministic 340-clock fill inside
  /* verilator lint_on UNUSEDSIGNAL */  // a 400-clock blank: timing by law

  /* verilator lint_off UNUSEDSIGNAL */
  wire _unused = frame_done | busy;
  /* verilator lint_on UNUSEDSIGNAL */

endmodule
`default_nettype wire
