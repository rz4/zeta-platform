// zgpu.v -- the Zeta rasterizer in silicon, defined by zeta/gpu.py's
// _fill(): SUBPIXEL vertices sampled at pixel centers, and a per-face
// DEPTH test against an on-die z-buffer -- the two precision laws that
// separate this machine from the PS1 it grew out of. Bit-equal to the
// Python spec, enforced by the cross.
//
// zseq feeds screen triangles (36-bit subpixel coordinates: a 32-bit DL
// coordinate shifted by SUB fits exactly) over a rdy/go handshake. One
// `start` clears frame and depth (one pixel per cycle); the walk runs a
// two-stage pipeline: stage 1 covers the pixel and reads its depth,
// stage 2 depth-tests and commits framebuffer and depth together.
`default_nettype none

module zgpu (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,       // pulse: clear, then accept triangles
    input  wire        flush_go,     // pulse: the FRAME's last band --
                                     // its clear never comes, so it
                                     // needs a standalone pass
    input  wire        first_band,   // nothing to flush behind this one
    output wire        flush_busy,
    input  wire [8:0]  tile_y0,     // first screen row this pass owns; the
                                    // depth plane covers TH rows from here
                                    // and nothing outside is touched
    input  wire        blit_mode,   // this frame clears to an IMAGE: the
                                    // backdrop (spec.BG_SRC) -- the same
                                    // clear pipeline, fed by a stream
    input  wire        blit_we,     // a backdrop word is presented
    input  wire [31:0] blit_word,   // {z16, 1'b?, rgb555}
    output wire        blit_take,   // ...and consumed this cycle
    input  wire        stall,       // freeze: the write FIFO needs a beat
    output wire [2:0]  m_st,        // METER (roadmap 15): this unit's
                                    // state, so zeta_top can time each
                                    // phase without reaching inside it
    output wire        rdy,         // cleared and idle: tri_go welcome
    input  wire        tri_go,
    input  wire signed [35:0] tx0, ty0, tx1, ty1, tx2, ty2,
    input  wire [50:0] tc0,         // the three channel bases at vertex
                                    // A, 17 bits each: {r5,g5,b5} for
                                    // color faces, {u5*w', v5*w', w'}
                                    // for textured (the crown's trio)
    input  wire signed [25:0] tcxr, tcyr,  // per-channel color gradients,
    input  wire signed [25:0] tcxg, tcyg,  // CFP fixed point -- zero for
    input  wire signed [25:0] tcxb, tcyb,  // flat faces, so flat is just
                                           // the degenerate case
    input  wire [15:0] tz0,         // depth at vertex A (0 for DL)
    input  wire signed [25:0] tzx,  // depth gradients, ZFP fixed point
    input  wire signed [25:0] tzy,
    // framebuffer writes (gutter-strided rows: ZW+1 words each)
    output wire        fb_we,
    output wire [16:0] fb_waddr,
    output wire [14:0] fb_wdata,
    // the pick register's tap (spec.PICK_*): every depth-buffer commit,
    // mirrored the cycle it lands -- clear/backdrop flagged, triangle
    // commits carrying the paint-order id the sequencer counted
    input  wire [15:0] tri_id,
    input  wire        t_tex,       // this triangle samples the page
    input  wire [14:0] t_tint,      // ...and is LIT by this, per face
    input  wire        t_tinton,
    input  wire  [7:0] t_oid,       // {edged, index+1}
    input  wire  [5:0] vis_a,       // THE SENSOR's readout port
    output wire [16:0] vis_q,       // (spec.VIS_BASE)
    input  wire [14:0] edge_rgb,    // ...and the colour an edge is drawn
    input  wire        t_otint,     // ...and OBJ_OTINT lights flat faces
    input  wire        t_span,      // OBJ_LODSPAN
    input  wire [4:0]  t_page,      // which of the TEX_PAGES pages
    input  wire        t_blend,     // OBJ_BLEND: composite, no depth
    input  wire [4:0]  t_alpha,     // ...in sixteenths, 16 = opaque
    input  wire        t_add,       // ...ADDITIVELY, if BLEND_ADD
    // ---- FOG (spec.FOG_*): the z-buffer already knows the distance ----
    input  wire [14:0] fog_rgb,     // what distance fades toward, 555
    input  wire [15:0] fog_near,    // where it begins
    input  wire [4:0]  fog_shift,   // 0 = off; else how fast it thickens
    input  wire        tex_we,      // the page's load port (one texel)
    input  wire [14:0] tex_a,
    input  wire [14:0] tex_d,
    output wire        zw_we,
    output wire [16:0] zw_addr,
    output wire [15:0] zw_data,
    output wire        zw_clr,
    output wire        zw_sh,      // THE SPARE BIT (spec.BG_SHADOW):
                                   // the plate's shadow mask at this
                                   // cleared pixel, for the pick tap
    output wire [15:0] zw_tri
);
  `include "params.vh"

  localparam S_IDLE = 3'd0, S_CLR = 3'd1, S_WAIT = 3'd2, S_WALK = 3'd3,
             S_FLUSH = 3'd4;
  reg [2:0]  st;
  reg [16:0] fl;                    // flush cursor, band-local
  reg [16:0] fl_a;                  // ...and where it lands in CRAM
  reg        fl_v;
  // THE FLUSH RIDES THE CLEAR. A separate pass per band cost one whole
  // extra screen of cycles (+93,929 on cube = exactly one (ZW+2)*ZH
  // loop). It is avoidable: the clear already reads cmem one cycle
  // ahead of writing it through the s1 pipeline, so ONE loop hands the
  // previous band's pixel to CRAM while laying this band's clear value
  // down behind it. One extra pass per FRAME instead of per band.
  //
  // Three things had to be true and each was found the hard way:
  //   - the band base is captured when the CLEAR ends, not in S_WAIT
  //     (S_WAIT runs on after zeta_top advances tpass, so a capture
  //     there latched the NEXT band's base and every band flushed to
  //     the wrong rows);
  //   - only the frame's LAST band flushes standalone;
  //   - rdy must mean DRAINED (see above), or the clear starts reading
  //     cmem while the previous band's last writes are still in flight.
  reg [16:0] pv_base;               // CRAM base of the band being flushed
  reg        fl_arm;                // ...and whether there is one
  reg [16:0] clr;
  reg [8:0]  ccol;                  // column within the row during clear:
                                    // backdrop words fill 0..ZW-1, the two
                                    // gutter cells always take clear/ZFAR
  wire       bpix = blit_mode && (ccol < ZW[8:0]);
  wire       cadv = (st == S_CLR) && (!bpix || blit_we);
  assign     blit_take = bpix && blit_we && !stall && (st == S_CLR);
  reg signed [35:0] v [0:5];        // x0 y0 x1 y1 x2 y2, subpixel
  reg [50:0] c0;
  reg [15:0] fz0;
  reg signed [25:0] fzx, fzy;
  // THE HOLD FIX (build 102). zseq's tzy fed fzy register-to-register
  // across the module boundary, and the fitter PACKED fzy into the depth
  // multiplier's DSP input register -- a fixed site it cannot pad with
  // routing delay -- so at the fast corners the data arrived too early:
  // hold -0.073 ns at 0C, five bits of the bus violating. Same class as
  // discovery's s2_z -> zmem. The multiplier now takes fzy through an
  // AND with zarm: set when a triangle latches, cleared after the plane
  // products are taken, so it is 1 at the only beat zpy0 captures (nine
  // or more after the latch) and the product is UNCHANGED -- but fzy no
  // longer touches the DSP directly, so it cannot be packed there, and
  // the path to zpy0 runs through the whole multiplier. zarm is set by
  // its own sequence rather than derived from zpy0's enable, so
  // synthesis cannot prove the AND redundant and remove it.
  reg               zarm;
  wire signed [25:0] fzy_m = fzy & {26{zarm}};
  reg signed [25:0] fcx [0:2], fcy [0:2];   // r, g, b color gradients
  reg [8:0]  px, py, lx, hx, hy;    // walk cursor and clamped box (pixels);
                                    // lx: THIS row's anchor (see the walk)
  // ---- THE SPAN WALK (frontier B1) ---------------------------------------
  // The box walk stepped every pixel of every row from the box's left edge
  // to its right, and the census (tools/geo_census.py) put the cost: at
  // the TND brawl's peak frame 366,232 walked pixels for 162,834 covered
  // -- the walk landed on its triangle 0.44 of the time. A triangle is
  // CONVEX, so a row's coverage is one interval; the walk now visits that
  // interval and little else:
  //   START  each row begins at the ANCHOR, the previous row's first
  //          covered pixel (the box corner on the first row)
  //   SEEKL  covered there, and covered to its left: step left, drawing
  //          nothing, until the left neighbour is not -- then draw
  //   SEEKR  not covered there: step right; the first covered pixel
  //          draws at once (everything left of it was not covered)
  //   DRAW   left to right; the first uncovered pixel ENDS THE ROW
  // EXACT BY CONSTRUCTION: every pixel is still visited by stepping the
  // same accumulators by the same adds (a left step is the right step's
  // inverse, and int64 wrap commutes), each covered pixel commits exactly
  // once, left to right, rows top to bottom -- the order the law and the
  // span-level rule (OBJ_LODSPAN: the level from a row's FIRST covered
  // pixel) both read. Seek steps run no texture ladder at all.
  // An UNCOVERED anchor does not say which way the row's coverage lies --
  // a sliver leaning left, or the narrowing rows above a bottom vertex,
  // can sit wholly LEFT of the last row's left end -- but each failing
  // edge does: its function improves in the direction its x step points,
  // given the triangle's orientation (the sign of e0 + e1 + e2, which is
  // constant: twice the area). Failing edges that disagree, or one that
  // no x step can fix, mean the row holds nothing.
  //   SEEKLU  not covered, coverage to the left: step left until covered,
  //           then SEEKL on to the interval's left end
  // A degenerate triangle (zero area) keeps its anchor at the box's left
  // edge: every row seeks right from there.
  localparam [2:0] W_START = 3'd0, W_SEEKL = 3'd1, W_SEEKR = 3'd2, W_DRAW = 3'd3,
                   W_SEEKLU = 3'd4;
  reg [2:0]  wph;                   // the walk's phase in this row
  reg        ori_p, ori_n;          // orientation: positive, negative area
  reg [8:0]  bxl;                   // the box's left edge (seeks stop there)
  // FOUR BITS, and the width is deliberate: the sequence now runs 10 down
  // to 0 and a count a parameter drives never gets its width by luck
  // (the localparam [5:0] that wedged a frame in silence, build 90).
  reg [3:0]  boxing;                // 11: the extents, 10: box, 9..4: edge
                                    // seed, 2,1: planes
  integer i;

  function signed [35:0] min3(input signed [35:0] a, b, c);
    min3 = (a < b) ? ((a < c) ? a : c) : ((b < c) ? b : c);
  endfunction
  function signed [35:0] max3(input signed [35:0] a, b, c);
    max3 = (a > b) ? ((a > c) ? a : c) : ((b > c) ? b : c);
  endfunction

  // clamped pixel bounding box: subpixel min/max, arithmetic >> SUB --
  // exactly gpu.py's lo/hi
  wire signed [35:0] mnx = min3(v[0], v[2], v[4]) >>> SUB;
  wire signed [35:0] mxx = max3(v[0], v[2], v[4]) >>> SUB;
  wire signed [35:0] mny = min3(v[1], v[3], v[5]) >>> SUB;
  wire signed [35:0] mxy = max3(v[1], v[3], v[5]) >>> SUB;
  // THE EXTENTS, REGISTERED (frontier B5). At 51.84 MHz the worst path on
  // the die ran from the just-latched vertices through min3/max3, the
  // clamp, and the empty-box compare into the state register: 1.76 ns
  // over 19.29. Two compares and a decision are a cycle; four are not. So
  // the first beat (boxing 11) only takes the extents, and the box and its
  // verdict are made a beat later from these -- one clock a triangle, the
  // law unchanged.
  reg signed [35:0] bmnx, bmxx, bmny, bmxy;
  wire signed [35:0] lox = (bmnx < 0) ? 36'sd0 : bmnx;
  wire signed [35:0] hix = (bmxx > ZW - 1) ? ZW - 1 : bmxx;
  // THE TILE (roadmap 15, step 1): the box is clamped to the BAND of
  // rows this pass owns, so the depth plane only has to exist for that
  // band -- which is where 61% of this device's block memory was going.
  // Bands are FULL WIDTH on purpose: a triangle row is then either
  // wholly inside the tile or wholly outside, never split, so OBJ_LODSPAN
  // (which holds one mip across a row from its first covered pixel)
  // cannot pick a different level either side of a seam. Clamping the
  // walk is only safe while that holds; the moment tiles divide rows
  // (step 2), coverage has to be masked AFTER the span arithmetic
  // instead. gpu.py carries both forms -- see its `clip`/`naive_clip`.
  // (band_lo/band_hi, NOT ty0/ty1 -- those are already this module's
  //  triangle vertex-Y inputs, and shadowing them would compile)
  wire signed [35:0] band_lo = {27'd0, tile_y0};
  wire signed [35:0] band_hi = band_lo + TH - 1;
  wire signed [35:0] loy = (bmny < band_lo) ? band_lo : bmny;
  wire signed [35:0] hiy = (bmxy > band_hi) ? band_hi : bmxy;
  wire box_empty = (lox > hix) || (loy > hiy);

  // depth plane: z at the walk start point, then exact incremental
  // accumulation (+= gradient << SUB per step) -- addition-only, so it
  // equals the law's multiply form bit for bit. Setup is spread over two
  // boxing phases (products, then the sum) off the REGISTERED cursor --
  // the single-cycle version missed timing by half a nanosecond.
  wire signed [17:0] zdx = sx[17:0] - v[0][17:0];
  wire signed [17:0] zdy = sy[17:0] - v[1][17:0];
  reg signed [43:0] zpx0, zpy0;
  reg signed [45:0] zacc, zrow;
  wire [15:0] zsmp = zacc[45] ? 16'd0 :
                     (|zacc[44:24]) ? 16'hFFFF : zacc[23:8];
  // color planes: three clones of the depth interpolator (same CFP=8
  // fixed point, same clamped gradients), sampled clipped to 0..31
  reg signed [43:0] cpx0 [0:2], cpy0 [0:2];
  reg signed [45:0] cacc [0:2], crow [0:2];
  wire [4:0] csmp [0:2];
  genvar gc;
  generate for (gc = 0; gc < 3; gc = gc + 1) begin : csamp
    assign csmp[gc] = cacc[gc][45] ? 5'd0 :
                      (|cacc[gc][44:13]) ? 5'd31 : cacc[gc][12:8];
  end endgenerate

  // ---- THE CROWN: per-pixel perspective recovery ------------------------
  // The channels carry u*w', v*w', w' -- affine-legal -- so each pixel
  // must divide to get back true u,v. One divide per pixel is impossible
  // in one beat, so a textured pixel takes SEVEN, each a single small
  // operation: seed, Newton, scale, shift, gradient-LOD, sample. Flat and
  // Gouraud pixels are untouched at one beat. The rate is content's
  // problem; the picture is the law's.
  reg [3:0]  tph;
  reg [19:0] wcl, nn;
  reg [4:0]  emsb;
  reg [8:0]  rr0;
  reg [28:0] tt;
  reg [15:0] rr1;
  // U AND V TOGETHER, through TWO multipliers. It was one, and the
  // ladder spent four beats on it -- multiply u, shift it home,
  // multiply v, shift it home -- because there was nothing to spend.
  // Stage 3 freed nineteen DSP blocks and this is what an idle
  // multiplier is FOR: not a second feature, the same feature in
  // fewer beats. Two beats become one, twice.
  reg signed [43:0] praw_u, praw_v;
  reg [12:0] ucfp0, ucfp1;
  reg [40:0] gm;                     // the running gradient maximum
  reg        cov_r;                  // covered, LATCHED on beat 0: the
                                     // edge functions are 37-bit products,
                                     // and gating the ladder on them live
                                     // put that whole tree in the crown's
                                     // clock-enable (-2.233 ns, boot 69b)
  reg [1:0]  plod;
  wire signed [45:0] pw = cacc[2];
  wire [19:0] wc_c = pw[45] ? 20'd256 :               // clip(w, 256,
                     (|pw[44:20]) ? 20'hFFFFF :       //      2^20 - 1)
                     (pw[19:0] < 20'd256) ? 20'd256 : pw[19:0];
  wire [4:0] e_c = wc_c[19] ? 5'd19 : wc_c[18] ? 5'd18 : wc_c[17] ? 5'd17 :
                   wc_c[16] ? 5'd16 : wc_c[15] ? 5'd15 : wc_c[14] ? 5'd14 :
                   wc_c[13] ? 5'd13 : wc_c[12] ? 5'd12 : wc_c[11] ? 5'd11 :
                   wc_c[10] ? 5'd10 : wc_c[9]  ? 5'd9  : 5'd8;
  wire [19:0] n_c = wc_c << (5'd19 - e_c);
  wire [6:0]  rom_i = n_c[18:12];
  // the products, WIDENED: a Verilog multiply takes the width of its
  // operands, not of its result -- the 38-bit Newton product evaluated
  // at 29 bits is how the first crown came out a single flat texel
  wire [29:0] r0n = {21'd0, rr0} * {10'd0, nn};
  wire [37:0] r0t = {29'd0, rr0} * {9'd0, tt};
  wire [8:0]  rom_c = RECIP_ROM_V[{3'd0, rom_i} * 9 +: 9];
  function signed [26:0] pclip(input signed [45:0] v);   // clip to +-2^26
    pclip = v[45] ? ((v < -46'sd67108864) ? -27'sd67108864 : v[26:0])
                  : ((v > 46'sd67108863) ? 27'sd67108863 : v[26:0]);
  endfunction
  function [12:0] uclip(input signed [43:0] v);          // clip to 0..8191
    uclip = v[43] ? 13'd0 : (|v[43:13]) ? 13'd8191 : v[12:0];
  endfunction
  // TWO scale multiplies, u and v on the same beat -- it was one, muxed
  // by tph, and the ladder paid two extra beats for the muxing.
  wire signed [43:0] pmul_u = pclip(cacc[0]) * $signed({1'b0, rr1})
                            + (44'sd1 <<< (emsb + 5'd6));
  wire signed [43:0] pmul_v = pclip(cacc[1]) * $signed({1'b0, rr1})
                            + (44'sd1 <<< (emsb + 5'd6));
  wire signed [43:0] psh_u = praw_u >>> (emsb + 5'd7);
  wire signed [43:0] psh_v = praw_v >>> (emsb + 5'd7);
  // the LOD by the quotient rule (thresholds multiplied through by W),
  // ONE term per beat through ONE multiplier: four beats, a running max.
  // Packed into a single beat this was the whole timing violation --
  // four multiplies, four absolutes and a max tree between two flops.
  wire [12:0] ua_sel = (tph <= 4'd8) ? ucfp0 : ucfp1;
  wire signed [25:0] gg_sel = (tph == 4'd7 || tph == 4'd9) ? fcx[2] : fcy[2];
  wire signed [25:0] gb_sel = (tph == 4'd7) ? fcx[0] :
                              (tph == 4'd8) ? fcy[0] :
                              (tph == 4'd9) ? fcx[1] : fcy[1];
  wire signed [40:0] gterm = {{7{gb_sel[25]}}, gb_sel, 8'd0}
                             - $signed({28'd0, ua_sel})
                               * {{15{gg_sel[25]}}, gg_sel};
  wire [40:0] gabs41 = gterm[40] ? -gterm : gterm;
  wire [40:0] gmax_n = (tph == 4'd7 || gabs41 > gm) ? gabs41 : gm;
  wire [1:0] lod_c = {1'b0, gm >= {16'd0, wcl, 5'd0}}
                   + {1'b0, gm >= {15'd0, wcl, 6'd0}}
                   + {1'b0, gm >= {14'd0, wcl, 7'd0}};
  wire [4:0] u5 = ucfp0[12:8], v5 = ucfp1[12:8];
  wire [10:0] tex_addr = (plod == 2'd0) ? {1'b0, v5, u5} :
                         (plod == 2'd1) ? (11'd1024 + {3'd0, v5[4:1],
                                                       u5[4:1]}) :
                         (plod == 2'd2) ? (11'd1280 + {5'd0, v5[4:2],
                                                       u5[4:2]}) :
                                          (11'd1344 + {7'd0, v5[4:3],
                                                       u5[4:3]});
  // an uncovered pixel writes nothing, so it owes no texel: it pays beat
  // 0, then leaves -- roughly half of any bounding box, skipped

  // edge functions at the PIXEL CENTER ((p << SUB) + HALF): 37-bit exact
  // differences, 64-bit wrapping products -- numpy int64's own domain
  wire signed [36:0] sx = $signed({24'd0, px, 1'b1, {(SUB - 1){1'b0}}});
  wire signed [36:0] sy = $signed({24'd0, py, 1'b1, {(SUB - 1){1'b0}}});
  wire signed [36:0] d01x = {v[2][35], v[2]} - {v[0][35], v[0]};
  wire signed [36:0] d01y = {v[3][35], v[3]} - {v[1][35], v[1]};
  wire signed [36:0] d12x = {v[4][35], v[4]} - {v[2][35], v[2]};
  wire signed [36:0] d12y = {v[5][35], v[5]} - {v[3][35], v[3]};
  wire signed [36:0] d20x = {v[0][35], v[0]} - {v[4][35], v[4]};
  wire signed [36:0] d20y = {v[1][35], v[1]} - {v[5][35], v[5]};
  wire signed [36:0] f0x = sx - {v[0][35], v[0]};
  wire signed [36:0] f0y = sy - {v[1][35], v[1]};
  wire signed [36:0] f1x = sx - {v[2][35], v[2]};
  wire signed [36:0] f1y = sy - {v[3][35], v[3]};
  wire signed [36:0] f2x = sx - {v[4][35], v[4]};
  wire signed [36:0] f2y = sy - {v[5][35], v[5]};
  // ---- THE EDGE FUNCTIONS, STEPPED (roadmap GEN6 stage 3) --------------
  // These were six 37x37 products evaluated AT EVERY WALKED PIXEL, and the
  // only thing done with them is a sign test. The fitter attributed the
  // cost exactly -- zgpu Mult4..Mult9, four blocks each, TWENTY-FOUR of
  // the device's sixty-six -- and "the DSPs have been 66/66 since the
  // crown" is quoted in this tree as the reason three separate per-pixel
  // features had to be shaped around it.
  //
  // An edge function is AFFINE in (x, y): stepping x by one pixel adds
  // -d_iy << SUB, stepping y by one row adds +d_ix << SUB, and both are
  // shifts of registers the face setup already holds. So the products are
  // needed ONCE PER TRIANGLE, at the box corner, and one multiplier
  // sequenced over six phases does that.
  //
  // EXACTNESS IS THE TRAP AND IT IS NOT THE ARITHMETIC. gpu.py evaluates
  // these in numpy int64, which WRAPS, and this file assigned a 74-bit
  // product to a 64-bit wire, which truncates to match. Addition commutes
  // with that modulus, so an accumulator gives the identical answer --
  // PROVIDED it is exactly 64 bits and wraps. Widening it "to be safe"
  // breaks bit-equality on precisely the wide guard-band triangles the
  // risk names.
  reg signed [63:0] eacc [0:2];     // the edge at THIS pixel
  reg signed [63:0] erow [0:2];     // ...and at the start of this row
  reg signed [63:0] eseed [0:2];    // the corner value, being built
  // TWO holding registers, and the reason is the fitter's: with one, the
  // phase that produced the second product ALSO subtracted it, so the
  // path ran py -> sy -> f (a 37-bit subtract) -> a 37x37 multiply -> a
  // 64-bit subtract, all in one cycle. STA named it exactly: py[4] ->
  // eseed[2][60], the worst path in the device. Now the multiply's output
  // only ever reaches a register, and the subtract reads two registers.
  reg signed [63:0] emac, emac2;    // the shared multiplier's two terms
  wire signed [36:0] emA =
      (boxing == 4'd9) ? d01x : (boxing == 4'd8) ? d01y :
      (boxing == 4'd7) ? d12x : (boxing == 4'd6) ? d12y :
      (boxing == 4'd5) ? d20x : d20y;
  wire signed [36:0] emB =
      (boxing == 4'd9) ? f0y : (boxing == 4'd8) ? f0x :
      (boxing == 4'd7) ? f1y : (boxing == 4'd6) ? f1x :
      (boxing == 4'd5) ? f2y : f2x;
  // THE OPERANDS, REGISTERED (frontier B5). At 51.84 MHz the phase select,
  // the operand muxes and the 37x37 multiply together ran 1.53 ns over
  // (574 paths, boxing -> emac2). The muxes now feed registers and the
  // multiply reads them a beat later; the schedule had a beat to give --
  // the last one only subtracted -- so the seed takes the same seven.
  reg signed [36:0] emA_r, emB_r;
  wire signed [63:0] emP = emA_r * emB_r;
  // the steps: shifts of the same differences, sign-extended to the
  // accumulator's exact width
  wire signed [63:0] edx0 = {{23{d01y[36]}}, d01y, {SUB{1'b0}}};
  wire signed [63:0] edx1 = {{23{d12y[36]}}, d12y, {SUB{1'b0}}};
  wire signed [63:0] edx2 = {{23{d20y[36]}}, d20y, {SUB{1'b0}}};
  wire signed [63:0] edy0 = {{23{d01x[36]}}, d01x, {SUB{1'b0}}};
  wire signed [63:0] edy1 = {{23{d12x[36]}}, d12x, {SUB{1'b0}}};
  wire signed [63:0] edy2 = {{23{d20x[36]}}, d20x, {SUB{1'b0}}};
  wire covered = ((eacc[0] >= 0) && (eacc[1] >= 0) && (eacc[2] >= 0)) ||
                 ((eacc[0] <= 0) && (eacc[1] <= 0) && (eacc[2] <= 0));
  // frontier B1: the LEFT neighbour's coverage, one step back (x - 1 adds
  // +edx), so a seek never has to step out and back again
  wire signed [63:0] eL0 = eacc[0] + edx0;
  wire signed [63:0] eL1 = eacc[1] + edx1;
  wire signed [63:0] eL2 = eacc[2] + edx2;
  wire covered_l = ((eL0 >= 0) && (eL1 >= 0) && (eL2 >= 0)) ||
                   ((eL0 <= 0) && (eL1 <= 0) && (eL2 <= 0));
  wire seek_left = (wph == W_START || wph == W_SEEKL || wph == W_SEEKLU)
                   && covered_l && (px > bxl);
  wire commit    = covered && !seek_left;   // (SEEKR / DRAW: covered commits)
  // at an uncovered pixel, which way each failing edge wants: right if its
  // value grows stepping right (a right step adds -edx: edx's sign is d_y's)
  wire f0 = ori_p ? (eacc[0] < 0) : (eacc[0] > 0);
  wire f1 = ori_p ? (eacc[1] < 0) : (eacc[1] > 0);
  wire f2 = ori_p ? (eacc[2] < 0) : (eacc[2] > 0);
  wire r0 = ori_p ? (d01y < 0) : (d01y > 0);
  wire r1 = ori_p ? (d12y < 0) : (d12y > 0);
  wire r2 = ori_p ? (d20y < 0) : (d20y > 0);
  wire l0 = ori_p ? (d01y > 0) : (d01y < 0);
  wire l1 = ori_p ? (d12y > 0) : (d12y < 0);
  wire l2 = ori_p ? (d20y > 0) : (d20y < 0);
  wire want_r = (f0 && r0) || (f1 && r1) || (f2 && r2);
  wire want_l = (f0 && l0) || (f1 && l1) || (f2 && l2);
  wire stuck  = (f0 && !r0 && !l0) || (f1 && !r1 && !l1) || (f2 && !r2 && !l2);
  wire degen  = !ori_p && !ori_n;
  wire dir_r  = degen || (want_r && !want_l && !stuck);
  wire dir_l  = !degen && want_l && !want_r && !stuck;
  // (frontier B1: a pixel the walk does not COMMIT owes no ladder at all;
  // the span walk's seeks pass over pixels without committing them)
  wire tdone = !ttex || !commit || (tph == 4'd1 && !cov_r) || (tph == 4'd12);
  // the next row starts from the anchor -- or, when this very pixel is the
  // row's first AND its last, from here
  wire use_cur = commit && (wph != W_DRAW) && !degen;
  wire signed [63:0] rb0 = use_cur ? eacc[0] : erow[0];
  wire signed [63:0] rb1 = use_cur ? eacc[1] : erow[1];
  wire signed [63:0] rb2 = use_cur ? eacc[2] : erow[2];
  wire signed [45:0] rbz = use_cur ? zacc : zrow;
  wire [8:0]         rbx = use_cur ? px : lx;

  assign m_st = st;
  assign flush_busy = (st == S_FLUSH);
  // RDY MEANS DRAINED, not merely "stopped walking". The commit runs a
  // two-stage pipeline, so when the walk's box is exhausted there are
  // still pixels in flight that have not reached cmem. Reporting ready
  // then let the next band's clear begin READING cmem before the last
  // writes landed -- a handful of wrong pixels a band, always
  // walk-written, never clear-written, which is exactly the shape of
  // the race. Costs one cycle a band and nothing else.
  assign rdy = (st == S_WAIT) && !s1_v && !s1_clr;   // accepting a tri writes nothing --
                                 // always safe; only walking freezes

  // ---- the depth buffer, gutter-strided like the framebuffer ------------
  // ---- THE BAND'S COLOUR, ON DIE (roadmap 15, step 4) ------------------
  // Blending needs the destination pixel, and the framebuffer lives in
  // CRAM behind a WRITE path -- the paint side has never been able to
  // read it back. That is the whole reason transparency was restricted
  // to rectangles at scanout (13b), and it is the one axis where this
  // machine sits behind a 1994 console.
  //
  // A BAND is small enough to hold. 322x32 x 15 bits = 154,560 bits,
  // about 15 of the 118 M10K blocks the shrink returned. Every write --
  // clear, backdrop, opaque face, and later a blended one -- lands here
  // at the band-local address; the whole band goes out to CRAM in one
  // pass when it closes.
  //
  // THIS STEP ADDS NO BLENDING. It moves the writes on die and flushes
  // them, and the picture must not change by a pixel. Blending is a
  // read-modify-write on top, once cross says the move itself is exact.
  (* ramstyle = "M10K" *) reg [14:0] cmem [0:(ZW + 2) * TH - 1];
  // THE IDENTITY PLANE (spec.OBJ_EDGE): who owns each pixel of this
  // band. Written where the depth is written -- only by OPAQUE faces,
  // for the same reason: a blended face is a veil, and outlining the
  // veil would draw a line around the glass instead of the thing.
  (* ramstyle = "M10K" *) reg [7:0] idmem [0:(ZW + 2) * TH - 1];
  // ...and ONE ROW of it, delayed. The band is already walked pixel by
  // pixel on its way out (the previous band's flush rides the next
  // band's clear), and that walk is continuous in SCREEN order across
  // the whole frame -- so a line ZW+2 deep hands back the pixel one row
  // up, band boundaries included, for no clocks and one MLAB.
  (* ramstyle = "MLAB" *) reg [7:0] iprev [0:ZW + 1];
  reg [7:0]  iq, iq_l, iq_u;        // this pixel, its left, its up
  reg [8:0]  ip;                    // the delay line's pointer
  reg [8:0]  fcol, wcol;            // the column, walking and delayed
  reg        wrow0;                 // ...and whether this is screen row 0
  // SCREEN ROW 0 HAS NOTHING ABOVE IT, and the delay line at that point
  // holds the tail of the previous FRAME. The law declines the same
  // comparison, so both machines decline it together.
  wire frow0_w = (st == S_FLUSH) ? (tile_base == 17'd0 && fl < (ZW + 2))
                                 : (pv_base  == 17'd0 && clr < (ZW + 2));
  wire [8:0] wcol_w = (st == S_FLUSH) ? fcol : ccol;
  wire iadv = (st == S_FLUSH) || ((st == S_CLR) && cadv);
  reg [14:0] cq;

  // ONE BAND of depth, not a screen: (ZW+2)*TH instead of (ZW+2)*ZH.
  // This array was 61% of the device's block memory; at TH=144 it is
  // half that, and the shrink funds everything queued behind it.
  reg [15:0] zmem [0:(ZW + 2) * TH - 1];
  reg [15:0] zq;

  // ---- two-stage commit pipeline ----------------------------------------
  // stage 1 (walk/clear cycle): cover the pixel, read its stored depth;
  // stage 2: depth test, commit framebuffer and depth writes together
  // rows are ZW+2 words since boot 35: the chip commits TWO trailing
  // beats per write burst (the edge instrument's 2px columns and the
  // x=319 -> next-row-x=0 bleed, witnessed), so the gutter is two words
  // wide and both land in dead storage whatever the mask pipeline does
  // TWO ADDRESSES, and they are no longer the same number. The FRAMEBUFFER
  // is still the whole screen (colour goes to CRAM as it always did), so
  // its address stays global; the depth plane is one band, so its index is
  // band-local. Before the tile these were one wire, and s1_a drove both.
  wire [16:0] tile_base = {8'd0, tile_y0} * (ZW[16:0] + 17'd2);
  wire [16:0] walk_addr = {8'd0, py} * (ZW[16:0] + 17'd2) + {8'd0, px};
  wire [16:0] zwalk     = walk_addr - tile_base;
  reg        s1_v, s1_clr;
  reg        ttex;                   // latched with the id below
  reg [14:0] ttint;
  reg        tspan;
  reg [14:0] tpage_base;   // spec.TEX_STRIDE * page, resolved ONCE
  reg        tblend;
  reg [4:0]  talpha;
  reg        tadd;
  reg        lod_dirty;   // this span still owes a level
  reg        ttinton;
  reg        totint;
  reg [7:0]  toid;
  // EIGHT PAGES + THEIR MIP CHAINS, 2,048 texels of stride each (1,360
  // used; a power-of-two stride makes the page index a concatenation
  // instead of a multiply, and this die has no multiplier to spare).
  // 8 x 2,048 x 15 = 245,760 bits, ~24 of the M10K blocks the tile
  // returned. One resident page was the most generation-typical limit
  // this machine had -- N64 fought a 4 KB texture cache for the same
  // reason its games look muddy.
  // THE PAGE STRIDE IS THE PAGE (spec.TEX_STRIDE). It was 2048 because
  // {page, addr} is free and a multiply is not -- and that convenience
  // held 8.1 M10K blocks of nothing, a third of the texture memory.
  // 1360 = 1024 + 256 + 64 + 16, so the multiply is four shifts and
  // three adds on a THREE-BIT page number.
  (* ramstyle = "M10K" *) reg [14:0] tmem [0:TEX_PAGES*TEX_STRIDE-1];
  // ...AND IT IS RESOLVED PER TRIANGLE, NOT PER PIXEL. The page latches
  // once at tri_go; putting the four-term add in the per-pixel address
  // cost 0.715 ns of setup for seven M10K blocks, which is the wrong way
  // round on a die where TIMING is the governing constraint. Registered
  // here, the pixel path is one 14-bit add.
  function [14:0] tbase(input [4:0] pg);
    tbase = {pg, 10'd0} + {2'd0, pg, 8'd0} + {4'd0, pg, 6'd0}
          + {6'd0, pg, 4'd0};
  endfunction
                                     // sampled through the color
                                     // interpolators' own 5-bit clamped
                                     // outputs -- u is the red channel,
                                     // v is the green channel
  reg [14:0] tq;
  reg        s1_tex;
  reg [15:0] tcur;                   // the id, LATCHED at tri_go: zseq
                                     // begins examining the next item
                                     // while this walk still runs, so a
                                     // live-sampled tag drifts +1 on the
                                     // walk's tail (the cross caught it)
  reg [15:0] s1_t;                   // ...riding the stall-gated stage
  reg [16:0] s1_a;                   // framebuffer: whole screen
  reg [16:0] s1_za;                  // depth: this band only
  reg [14:0] s1_d;
  reg [14:0] s1_tintv;
  reg        s1_tinton;
  reg        s1_otint;
  reg        s1_sh;      // the plate's shadow bit, riding the z write
  reg [7:0]  s1_oid, s2_oid;   // ...and the owner, riding beside it
  reg        s2_clr;
  reg        s1_blend;
  reg [4:0]  s1_alpha;
  reg        s1_add;
  reg        s2_v, s2_blend;
  reg [16:0] s2_za;
  reg [15:0] s2_z;
  reg [14:0] s2_col, s2_dst;
  reg [4:0]  s2_alpha;
  reg        s2_add;
  reg [15:0] s1_z;
  wire [14:0] clear555 = {CLEAR_RGB[23:19], CLEAR_RGB[15:11],
                          CLEAR_RGB[7:3]};
  // The blend is in SIXTEENTHS, so it is shifts and adds -- not thrift
  // for its own sake: every DSP on this die has been spoken for since the
  // crown, and a multiplier-free fog is the only kind still affordable.
  // Never applied to a clear or backdrop pixel: those are pre-rendered
  // content that already holds whatever air their author wanted, and
  // fogging a photograph is just haze.
  wire [16:0] fg_d = {1'b0, s1_z} - {1'b0, fog_near};
  // A VARIABLE shift, not a multiply, was the DSP thief: Quartus builds
  // barrel shifters out of DSP blocks, and this one cost nine of them on
  // a die with none to spare. Seventeen fixed shifts behind a mux is pure
  // logic and exactly as correct.
  wire [15:0] fg_r = fg_d[15:0];
  wire [15:0] fg_s = fg_d[16] ? 16'd0 :
      (fog_shift == 5'd0)  ? fg_r        : (fog_shift == 5'd1)  ? {1'b0,  fg_r[15:1]} :
      (fog_shift == 5'd2)  ? {2'b0,  fg_r[15:2]}  : (fog_shift == 5'd3)  ? {3'b0,  fg_r[15:3]} :
      (fog_shift == 5'd4)  ? {4'b0,  fg_r[15:4]}  : (fog_shift == 5'd5)  ? {5'b0,  fg_r[15:5]} :
      (fog_shift == 5'd6)  ? {6'b0,  fg_r[15:6]}  : (fog_shift == 5'd7)  ? {7'b0,  fg_r[15:7]} :
      (fog_shift == 5'd8)  ? {8'b0,  fg_r[15:8]}  : (fog_shift == 5'd9)  ? {9'b0,  fg_r[15:9]} :
      (fog_shift == 5'd10) ? {10'b0, fg_r[15:10]} : (fog_shift == 5'd11) ? {11'b0, fg_r[15:11]} :
      (fog_shift == 5'd12) ? {12'b0, fg_r[15:12]} : (fog_shift == 5'd13) ? {13'b0, fg_r[15:13]} :
      (fog_shift == 5'd14) ? {14'b0, fg_r[15:14]} : (fog_shift == 5'd15) ? {15'b0, fg_r[15]} :
                                                    16'd0;
  wire [4:0]  fg_t = (|fg_s[15:5]) ? 5'd16 :
                     (fg_s[4:0] > 5'd16) ? 5'd16 : fg_s[4:0];
  wire        fg_on = (fog_shift != 5'd0) && !s1_clr;
  // THE TINT: a textured pixel is LIT by its face's colour word instead
  // of replacing it. texel * (tint+1) >> 5, per 5-bit channel -- the +1
  // is what makes a tint of 31 pass the texel through EXACTLY rather
  // than darkening white to 30. Five conditional adds and one more, the
  // same shape fog's tmul already uses. Written when the DSPs were 66/66
  // and a multiply here would not fit; build 96 freed nineteen, so this
  // COULD now be a DSP -- it stays in logic because zero DSPs is still
  // cheaper than one, not because it has to.
  function [4:0] tmod(input [4:0] a, input [4:0] b);
    reg [10:0] p;
    begin
      p = {6'd0, a};                       // the +1 of (b+1)
      if (b[0]) p = p + {6'd0, a};
      if (b[1]) p = p + {5'd0, a, 1'b0};
      if (b[2]) p = p + {4'd0, a, 2'b0};
      if (b[3]) p = p + {3'd0, a, 3'b0};
      if (b[4]) p = p + {2'd0, a, 4'b0};
      tmod = p[9:5];
    end
  endfunction
  // OBJ_OTINT lights the UNTEXTURED branch too -- which is what actors
  // in this machine are made of. The source is muxed BEFORE the tint
  // rather than after, so one set of tmods serves both branches: the
  // flag costs three multiplexers, not three more multipliers.
  wire [14:0] tsrc = s1_tex ? tq : s1_d;
  wire        tlit = s1_tex ? s1_tinton : s1_otint;
  wire [14:0] tsrc_lit = {tmod(tsrc[14:10], s1_tintv[14:10]),
                          tmod(tsrc[9:5],   s1_tintv[9:5]),
                          tmod(tsrc[4:0],   s1_tintv[4:0])};
  wire [14:0] wq_raw = tlit ? tsrc_lit : tsrc;
  // c*(16-t) + f*t is 16c + t*(f-c): ONE multiply per channel, not two.
  // Written the first way it took 78 of the 66 DSPs this die has -- the
  // algebra is not a flourish, it is the difference between fitting and
  // not. multstyle keeps even these three in logic, because zero DSPs
  // are free and have been since the crown.
  wire signed [6:0]  fdif_10 = $signed({2'b0, fog_rgb[14:10]})
                             - $signed({2'b0, wq_raw[14:10]});
  wire signed [6:0]  fdif_5  = $signed({2'b0, fog_rgb[9:5]})
                             - $signed({2'b0, wq_raw[9:5]});
  wire signed [6:0]  fdif_0  = $signed({2'b0, fog_rgb[4:0]})
                             - $signed({2'b0, wq_raw[4:0]});
  // t is five bits, so t*(f-c) is five conditional adds. Written as a
  // multiply it was three more DSP blocks on a die that has had none
  // free since the crown; written this way it is guaranteed logic, and
  // no fitter has to be trusted to balance it away.
  function signed [12:0] tmul(input signed [6:0] d, input [4:0] t);
    begin
      tmul = (t[0] ? {{6{d[6]}}, d}        : 13'sd0)
           + (t[1] ? {{5{d[6]}}, d, 1'b0}  : 13'sd0)
           + (t[2] ? {{4{d[6]}}, d, 2'b0}  : 13'sd0)
           + (t[3] ? {{3{d[6]}}, d, 3'b0}  : 13'sd0)
           + (t[4] ? {{2{d[6]}}, d, 4'b0}  : 13'sd0);
    end
  endfunction
  wire signed [12:0] fmul_10 = tmul(fdif_10, fg_t);
  wire signed [12:0] fmul_5  = tmul(fdif_5,  fg_t);
  wire signed [12:0] fmul_0  = tmul(fdif_0,  fg_t);
  wire signed [12:0] facc_10 = ($signed({2'b0, wq_raw[14:10]}) <<< 4)
                             + fmul_10;
  wire signed [12:0] facc_5  = ($signed({2'b0, wq_raw[9:5]}) <<< 4)
                             + fmul_5;
  wire signed [12:0] facc_0  = ($signed({2'b0, wq_raw[4:0]}) <<< 4)
                             + fmul_0;
  wire [14:0] wq_fog = {facc_10[8:4], facc_5[8:4], facc_0[8:4]};

  wire        s2_pass  = s1_clr || (s1_v && s1_z <= zq);
  reg        wq_we;
  reg [16:0] wq_a;
  reg [14:0] wq_d;
  always @(posedge clk) if (tri_go) begin
    tcur <= tri_id;
    ttex <= t_tex;
    ttint <= t_tint;
    tspan <= t_span;
    tpage_base <= tbase(t_page);
    tblend <= t_blend;
    talpha <= t_alpha;
    tadd   <= t_add;
    ttinton <= t_tinton;
    totint  <= t_otint;
    toid    <= t_oid;
  end
  always @(posedge clk) if (tex_we) tmem[tex_a] <= tex_d;   // tex_a is
                                    // {slot, texel}, driven by zeta_top
  always @(posedge clk) if (!stall) begin
    s1_clr <= rst_n && (st == S_CLR) && cadv;
    s1_v   <= rst_n && (st == S_WALK) && (boxing == 0) && commit
                    && tdone;
    s1_a   <= (st == S_CLR) ? (clr + tile_base) : walk_addr;
    s1_za  <= (st == S_CLR) ? clr : zwalk;
    s1_d   <= (st == S_CLR) ? (bpix ? blit_word[14:0] : clear555)
                            : {csmp[0], csmp[1], csmp[2]};
    s1_z   <= (st == S_CLR) ? (bpix ? blit_word[31:16] : ZFAR[15:0])
                            : zsmp;
    // Bit 15 was read by nothing until now. It rides out on the same
    // beat as the depth it was baked beside, and only during the clear:
    // where the room's sun falls does not change because an actor walked
    // in front of it.
    s1_sh  <= (st == S_CLR) && bpix && blit_word[15];
    s1_oid <= (st == S_CLR) ? 8'd0 : toid;
    s1_t   <= tcur;
    s1_tex <= (st == S_WALK) && ttex;
    s1_tinton <= (st == S_WALK) && ttinton;
    s1_otint  <= (st == S_WALK) && totint;
    s1_blend  <= (st == S_WALK) && tblend;
    s1_alpha  <= talpha;
    s1_add    <= tadd;
    s1_tintv  <= ttint;
    tq     <= tmem[tpage_base + {4'd0, tex_addr}];
    zq     <= zmem[(st == S_CLR) ? clr : zwalk];
    // ---- A THIRD COMMIT STAGE, and the blend is why ------------------
    // The chain tmem -> texel -> tint(tmod) -> fog(tmul) -> blend(tmul)
    // -> cmem is TWO conditional-add multipliers in series behind a
    // texture fetch, and it missed the clock by 2.227 ns -- the fitter
    // named the path exactly (tmem write-enable to cmem data-in). So the
    // post-fog colour is REGISTERED here and the blend happens a cycle
    // later, which splits the two multipliers across cycles.
    //
    // Safe because the walk visits each pixel of a triangle exactly
    // once: consecutive commits are always different addresses, so
    // nothing reads a pixel this stage has not yet written. The depth
    // DECISION still happens at s2 (s2_pass, off s1_z vs zq); only the
    // write moves, so the pick tap and the fog are untouched.
    s2_v     <= s2_pass && !stall;
    s2_za    <= s1_za;
    s2_z     <= s1_z;
    s2_col   <= fg_on ? wq_fog : wq_raw;
    s2_blend <= s1_blend;
    s2_alpha <= s1_alpha;
    s2_add   <= s1_add;
    s2_oid   <= s1_oid;
    s2_clr   <= s1_clr;
    s2_dst   <= cq;
    // BOTH WRITES AT STAGE 3, and the alternative was measured. Keeping
    // depth at stage 2 fixes hold (+0.038) but drops Fmax to 42.23 MHz,
    // BELOW the 43.2 the video law fixes exactly -- trading a 5 ps hold
    // violation for a 1 MHz setup shortfall, which is the worse of the
    // two by a wide margin. So: both at stage 3.
    //   depth at s3:  Fmax 44.86,  hold -0.005
    //   depth at s2:  Fmax 42.23,  hold +0.038
    // The residual -0.005 is on s2_z -> zmem datain, a register feeding
    // memory with no logic between. Seeds moved it the wrong way and
    // OPTIMIZE_HOLD_TIMING could not route around it. It is five
    // picoseconds in the FAST corner and it is a KNOWN, RECORDED
    // violation, not an oversight -- the honest fix is to shorten the
    // s2_pass compare so depth can sit at stage 2 without costing Fmax,
    // and that is zseq/zgpu work for its own build.
    // THE BLEND-ORDER LAW (spec.py): a blended face tests depth and
    // writes NONE, so blended faces cannot occlude each other and their
    // composite order is exactly the display-list order the cart chose.
    if (s2_v) begin
      if (!s2_blend) begin
        zmem[s2_za]  <= s2_z;
        idmem[s2_za] <= s2_clr ? 8'd0 : s2_oid;   // the clear owns nobody
      end
      cmem[s2_za] <= s2_blend ? bl_out : s2_col;
    end
    // reading the OLD band while the clear writes the new one behind it,
    // plus one standalone pass for the last band of the frame
    // ADDRESS AND DATA MUST BE SAMPLED FROM THE SAME CYCLE. cq lands one
    // cycle after the read is issued, so the address that goes with it is
    // the one the read used -- clr, NOT a delayed copy of clr. A `cl_d`
    // here put the address one behind the data and scattered a handful of
    // pixels a band into neighbouring rows. The S_FLUSH path opposite has
    // always used `fl` directly; the two must mirror each other.
    // ONE MUXED READ serves both jobs: the flush owns this port during
    // S_CLR and S_FLUSH, the blend during S_WALK, and those never
    // overlap. Issued with the same address the s1 stage latches, so the
    // destination pixel is waiting exactly when the commit needs it.
    if (!stall) cq <= cmem[(st == S_FLUSH) ? fl
                         : (st == S_WALK)  ? zwalk : clr];
    // THE OUTLINE, riding the same walk (spec.OBJ_EDGE). iq is this
    // pixel's owner, iq_l the one to its left (a single register, because
    // the walk is left to right) and iq_u the one above, out of a delay
    // line ZW+2 deep. The line is fed with iq rather than the fresh read
    // so that all three land on the same cycle as cq.
    // ONLY WHILE THE WALK IS ACTUALLY READING OUT. This block has state,
    // and clocking it through S_WALK and S_WAIT shifted the delay line by
    // however many cycles the triangles happened to take -- which put the
    // "pixel above" at the FIRST ROW OF EVERY BAND somewhere else
    // entirely, and drew 164 edges the law does not, in rows 160 and 192
    // and nowhere between. The colour read above it is stateless and did
    // not care; this does.
    if (!stall && iadv) begin
      iq   <= idmem[(st == S_FLUSH) ? fl : clr];
      iq_l <= iq;
      iq_u <= iprev[ip];
      iprev[ip] <= iq;
      // ZW+1 ENTRIES, NOT ZW+2. The line is fed with `iq`, which is
      // already one pixel behind the read, so the stage the register
      // itself contributes makes the total delay ZW+2 -- the row stride.
      // At ZW+2 entries it was ZW+3, one column too far back, and that
      // shows up only where an edge runs nearly HORIZONTAL: eight pixels
      // on a diagonal, out of fifteen thousand.
      ip   <= (ip == ZW[8:0]) ? 9'd0 : ip + 9'd1;
      wcol  <= wcol_w;
      wrow0 <= frow0_w;
    end
    fl_v <= !stall && ((st == S_FLUSH)
                    || ((st == S_CLR) && cadv && fl_arm));
    fl_a <= (st == S_FLUSH) ? (fl + tile_base) : (clr + pv_base);
  end
  // CRAM sees only the flush now. Nothing else writes the framebuffer.
  // THE BLEND IS THE FOG'S OWN ARITHMETIC, and reuses its adder.
  //   dst*(16-a) + src*a  ==  (dst << 4) + a*(src - dst)
  // which is exactly the shape wq_fog already computes, so tmul above --
  // five conditional adds -- serves both. Written as a real multiply it
  // cost THREE MORE DSP BLOCKS on a die that has had none free since the
  // crown: synthesis reported 79 of 66. That is the same reason the fog
  // was made multiplier-free, recorded three inches up this file, and I
  // still had to be told by the fitter.
  //
  // (The first version also sized the multiply to its 5-bit operands,
  // so `d * (16-a)` -- which needs nine bits -- wrapped, and cross
  // failed on 12,442 pixels. Both problems vanish with tmul.)
  wire signed [6:0] bd_10 = $signed({2'b0, s2_col[14:10]})
                          - $signed({2'b0, s2_dst[14:10]});
  wire signed [6:0] bd_5  = $signed({2'b0, s2_col[9:5]})
                          - $signed({2'b0, s2_dst[9:5]});
  wire signed [6:0] bd_0  = $signed({2'b0, s2_col[4:0]})
                          - $signed({2'b0, s2_dst[4:0]});
  // BLEND_ADD (spec.BLEND_MODE_SHIFT) rides the SAME multiply. Both
  // modes are dst*16 + M*a; the only difference is whether M is
  // (src - dst) or src, so the mode costs three multiplexers and not a
  // second blender -- the same trick OBJ_OTINT used one stage earlier.
  //
  // What it buys is the one thing the lerp cannot fake. A lerp can only
  // move a pixel TOWARD the source colour, so it can darken a bright
  // pixel and can never brighten one; additive is how a pixel ends up
  // brighter than either operand, which is what makes a glow read as
  // EMITTED rather than painted over.
  wire signed [6:0] bm_10 = s2_add ? $signed({2'b0, s2_col[14:10]}) : bd_10;
  wire signed [6:0] bm_5  = s2_add ? $signed({2'b0, s2_col[9:5]})   : bd_5;
  wire signed [6:0] bm_0  = s2_add ? $signed({2'b0, s2_col[4:0]})   : bd_0;
  wire signed [12:0] bacc_10 = ($signed({2'b0, s2_dst[14:10]}) <<< 4)
                             + tmul(bm_10, s2_alpha);
  wire signed [12:0] bacc_5  = ($signed({2'b0, s2_dst[9:5]}) <<< 4)
                             + tmul(bm_5,  s2_alpha);
  wire signed [12:0] bacc_0  = ($signed({2'b0, s2_dst[4:0]}) <<< 4)
                             + tmul(bm_0,  s2_alpha);
  // The lerp lands in [0, 496] and never needed this; additive reaches
  // 992, so bit 9 is the overflow and the clamp is what stops a bright
  // glow from wrapping to black. bsat is EXACTLY a[8:4] whenever the
  // value fits, so mode 0 is bit-identical to what shipped.
  function [4:0] bsat(input signed [12:0] a);
    bsat = a[12]         ? 5'd0  :
           (|a[12:9])    ? 5'd31 : a[8:4];
  endfunction
  wire [14:0] bl_out = {bsat(bacc_10), bsat(bacc_5), bsat(bacc_0)};

  // ---- THE PANEL AS A SENSOR (spec.VIS_BASE) --------------------------
  // The flush names an owner a clock, and counting them is a read, an
  // add and a write at one address. The first version got that in ONE
  // beat from a LUTRAM with a combinational read -- no hazard, no
  // forwarding, correct on the first try, and it cost 832 ALM, because
  // it wanted TWO async read ports (the counting one and the readback
  // one) and Quartus cannot make those from MLABs. It built 64 x 17
  // FLOPS and two 64-way muxes: 89% of the die to 93%.
  //
  // This is the same tally out of ONE M10K, ~70 ALM, and the whole cost
  // of that is the hazard the combinational read did not have.
  //
  // THE PORT IS SHARED, not duplicated. Counting happens during the
  // bands; the readback happens after the last one, in the frame's
  // setup states, so the two never want the port on the same clock.
  // When neither does, it serves the readback, which is free.
  //
  // THE HAZARD IS EXACTLY ONE DEEP, and it is worth writing down why,
  // because "add more forwarding until it works" is how this goes
  // wrong. A read issued on clock c returns memory as of BEFORE clock
  // c's write. The write in flight on clock c belongs to the pixel
  // BEFORE the one being read. So a read can miss exactly one write --
  // the immediately preceding pixel's -- and misses it only when that
  // pixel had the SAME owner. Which, on a span, is almost every pixel.
  // Two back is already visible in the memory, so a second stage would
  // be dead logic.
  //
  // Counted at FLUSH and not at commit, so what comes out is FINAL
  // visibility: what the panel showed, not what an object won before
  // something else drew over it. 17 bits holds a whole screen (92,160)
  // and a pixel is flushed once, so it cannot wrap.
  //
  // The zeroing walk rides the FIRST band's clear, where fl_arm is low
  // and nothing is being counted -- 64 clocks inside 10,304.
  (* ramstyle = "M10K" *) reg [16:0] vmem [0:OL_MAX - 1];
  reg  [6:0]  vclr;
  wire        vzero = !vclr[6];             // OL_MAX == 64
  // !stall, AND NOT MERELY fl_v. fb_we is a REQUEST that is HELD until
  // the CRAM write FIFO takes it -- address and data sit unchanged for
  // as long as the stall lasts. The framebuffer never noticed, because
  // writing the same word twice is writing it once. A COUNTER NOTICES:
  // measured, 92,736 real pixels arrived as 98,306 asserted beats, one
  // stall running fourteen clocks long. Count acceptances, not requests.
  wire        vhit  = fl_v && !stall && (iq[6:0] != 7'd0);
  // owner 1..OL_MAX becomes index 0..OL_MAX-1, and owner OL_MAX wraps
  // to OL_MAX-1 through the same subtract, which is the right answer
  wire [5:0]  a_sel = vzero ? vclr[5:0]
                    : vhit  ? (iq[5:0] - 6'd1)
                    :         vis_a;
  reg  [16:0] vq;                   // what came back, one clock later
  reg  [5:0]  b_sel;   reg b_hit;   // ...and whose it is
  reg  [5:0]  p_sel;   reg p_hit;   // the write still in flight
  reg  [16:0] p_val;
  wire [16:0] b_cur = (p_hit && (p_sel == b_sel)) ? p_val : vq;
  wire [16:0] b_val = b_cur + 17'd1;
  wire        vwe   = vzero || b_hit;
  wire [5:0]  vwa   = vzero ? vclr[5:0] : b_sel;
  wire [16:0] vwd   = vzero ? 17'd0     : b_val;
  always @(posedge clk) begin
    vq    <= vmem[a_sel];
    b_sel <= a_sel;
    b_hit <= rst_n && vhit;
    p_sel <= b_sel;
    p_hit <= rst_n && b_hit;
    p_val <= b_val;
    if (!rst_n) vclr <= 7'd0;
    else if (start && first_band) vclr <= 7'd0;
    else if (vzero) vclr <= vclr + 7'd1;
    if (rst_n && vwe) vmem[vwa] <= vwd;
  end
  assign vis_q = vq;

  assign fb_we    = fl_v;
  assign fb_waddr = fl_a;
  // THE OUTLINE. A pixel is an edge when its owner differs from the
  // owner to its left or above -- nothing else. Two outlined objects
  // meeting is an edge; an outlined object against the room is an edge;
  // the room against itself is not, because 0 equals 0.
  // THE OWNERS MUST DIFFER **AND** ONE MUST HAVE ASKED (bit 7).
  wire edge_hit = ((wcol != 9'd0) && (iq[6:0] != iq_l[6:0])
                                  && (iq[7] || iq_l[7]))
               || (!wrow0        && (iq[6:0] != iq_u[6:0])
                                  && (iq[7] || iq_u[7]));
  assign fb_wdata = edge_hit ? edge_rgb : cq;
  assign zw_we    = s2_pass && !stall;
  assign zw_addr  = s1_a;
  assign zw_data  = s1_z;
  assign zw_clr   = s1_clr;
  assign zw_sh    = s1_sh;
  assign zw_tri   = s1_t;

  always @(posedge clk) begin
    if (!rst_n) st <= S_IDLE;
    else case (st)
      S_IDLE: if (start) begin
        clr <= 0; ccol <= 0; st <= S_CLR; fl_arm <= !first_band;
      end
      S_CLR: if (!stall && cadv) begin  // rows are ZW+2 words: the double
        clr <= clr + 1'b1;              // gutter soaks BOTH trailing commits
        ccol <= (ccol == ZW[8:0] + 9'd1) ? 9'd0 : ccol + 9'd1;
        if (clr == (ZW + 2) * TH - 1) begin
          st <= S_WAIT;                                // one band's worth
          pv_base <= tile_base;      // captured HERE, not in S_WAIT
        end
      end
      S_FLUSH: if (!stall) begin       // the band goes out, a word a clock
        fl <= fl + 1'b1;
        fcol <= (fcol == ZW[8:0] + 9'd1) ? 9'd0 : fcol + 9'd1;
        if (fl == (ZW + 2) * TH - 1) st <= S_WAIT;
      end
      S_WAIT: begin                   // producing nothing: never freezes
        if (start) begin
          clr <= 0; ccol <= 0; st <= S_CLR; fl_arm <= !first_band;
        end
        else if (flush_go) begin fl <= 0; fcol <= 9'd0; st <= S_FLUSH; end
        else if (tri_go) begin
          v[0] <= tx0; v[1] <= ty0; v[2] <= tx1;
          v[3] <= ty1; v[4] <= tx2; v[5] <= ty2;
          c0 <= tc0;
          fcx[0] <= tcxr; fcy[0] <= tcyr;
          fcx[1] <= tcxg; fcy[1] <= tcyg;
          fcx[2] <= tcxb; fcy[2] <= tcyb;
          fz0 <= tz0; fzx <= tzx; fzy <= tzy;
          zarm <= 1'b1;                      // see THE HOLD FIX
          boxing <= 4'd11;
          st <= S_WALK;
        end
      end
      default: if (!stall) begin      // S_WALK
        if (boxing == 4'd11) begin    // the extents of the just-latched
          boxing <= 4'd10;            // vertices, and nothing else
          bmnx <= mnx; bmxx <= mxx; bmny <= mny; bmxy <= mxy;
        end else if (boxing == 4'd10) begin   // the box, from the extents
          boxing <= 4'd9;
          px <= lox[8:0]; py <= loy[8:0]; lx <= lox[8:0]; tph <= 4'd0;
          bxl <= lox[8:0]; wph <= W_START;
          lod_dirty <= 1'b1;          // a new triangle owes a level
          hx <= hix[8:0]; hy <= hiy[8:0];
          if (box_empty) st <= S_WAIT;
        end else if (boxing >= 4'd3) begin   // the edge seed, one product a
          boxing <= (boxing == 4'd3) ? 4'd2 : boxing - 4'd1;
          emA_r <= emA; emB_r <= emB;        // the NEXT beat's operands
          case (boxing)                      // phase through one multiplier
            4'd8: emac  <= emP;                        // d01x*f0y
            4'd7: emac2 <= emP;                        // d01y*f0x
            4'd6: begin eseed[0] <= emac - emac2; emac <= emP; end
            4'd5: emac2 <= emP;
            4'd4: begin eseed[1] <= emac - emac2; emac <= emP; end
            4'd3: emac2 <= emP;
            default: ;                                 // boxing == 9: operands only
          endcase
        end else if (boxing == 4'd2) begin   // plane products (depth and
          eseed[2] <= emac - emac2;          // (...and the third seed's sum)
          boxing <= 4'd1;                    // colors), off the registered
          zpx0 <= zdx * fzx;                 // cursor
          zpy0 <= zdy * fzy_m;               // fzy, unpackable (HOLD FIX)
          for (i = 0; i < 3; i = i + 1) begin
            cpx0[i] <= zdx * fcx[i];
            cpy0[i] <= zdy * fcy[i];
          end
        end else if (boxing == 4'd1) begin   // values at the start corner
          boxing <= 4'd0;
          zarm <= 1'b0;                      // products taken (HOLD FIX)
          for (i = 0; i < 3; i = i + 1) begin
            eacc[i] <= eseed[i]; erow[i] <= eseed[i];
          end
          ori_p <= (eseed[0] + eseed[1] + eseed[2]) > 0;   // the area's sign
          ori_n <= (eseed[0] + eseed[1] + eseed[2]) < 0;
          zacc <= {fz0, 8'd0} + {{2{zpx0[43]}}, zpx0}
                              + {{2{zpy0[43]}}, zpy0};
          zrow <= {fz0, 8'd0} + {{2{zpx0[43]}}, zpx0}
                              + {{2{zpy0[43]}}, zpy0};
          for (i = 0; i < 3; i = i + 1) begin
            // base + HALF: the sampler rounds to nearest instead of
            // flooring -- sub-quantum phase noise stops scintillating
            // one-texel features (the brick-line jitter, boot 66)
            cacc[i] <= {21'd0, c0[50 - 17*i -: 17], 1'b1, 7'd0}
                       + {{2{cpx0[i][43]}}, cpx0[i]}
                       + {{2{cpy0[i][43]}}, cpy0[i]};
            crow[i] <= {21'd0, c0[50 - 17*i -: 17], 1'b1, 7'd0}
                       + {{2{cpx0[i][43]}}, cpx0[i]}
                       + {{2{cpy0[i][43]}}, cpy0[i]};
          end
        end else if (!tdone) begin    // the crown's ladder, one small
          tph <= tph + 1'b1;          // operation per beat
          case (tph)
            4'd0: begin wcl <= wc_c; emsb <= e_c; nn <= n_c;
                        rr0 <= rom_c; cov_r <= covered; end
            4'd1: tt <= 30'h2000_0000 - r0n;         // 2^29 - r0*n
            4'd2: rr1 <= r0t >> 22;                  // one Newton step
            4'd3: begin praw_u <= pmul_u;            // u AND v, one beat
                        praw_v <= pmul_v; end
            // BEAT 4 IS THE FORK NOW, and it was beat 6. Beats 7..11 are
            // the four gradient maxima and the level they pick -- five
            // of the thirteen, spent per pixel. In span mode the row's
            // first covered pixel pays them and the rest of the span
            // jumps straight to the commit.
            4'd4: begin
              ucfp0 <= uclip(psh_u);                 // ...both shifted
              ucfp1 <= uclip(psh_v);                 //    home together
              tph <= (tspan && !lod_dirty) ? 4'd12 : 4'd7;
            end
            4'd7, 4'd8, 4'd9, 4'd10: gm <= gmax_n;   // the four gradients
            default: begin plod <= lod_c; lod_dirty <= 1'b0; end
                                        // 11: the level, gm now complete
                                        // (12 is the commit beat itself)
          endcase
        end else if ((commit && px == hx) ||
                     (!covered && (wph == W_DRAW ||
                       ((wph == W_SEEKR || (wph == W_START && dir_r)) && px == hx) ||
                       ((wph == W_SEEKLU || (wph == W_START && dir_l)) && px == bxl) ||
                       (wph == W_START && !dir_r && !dir_l)))) begin
          // THE ROW ENDS: its last pixel drew; its coverage ran out (the
          // early exit); a seek reached the box's edge finding nothing; or
          // its failing edges say it holds nothing. The next row starts at
          // the anchor, one row down.
          px <= rbx; tph <= 4'd0; wph <= W_START;
          if (use_cur) lx <= px;
          lod_dirty <= 1'b1;          // ...and so does every new row
          zrow <= rbz + {{16{fzy[25]}}, fzy, 4'd0};
          zacc <= rbz + {{16{fzy[25]}}, fzy, 4'd0};
          erow[0] <= rb0 + edy0;  eacc[0] <= rb0 + edy0;
          erow[1] <= rb1 + edy1;  eacc[1] <= rb1 + edy1;
          erow[2] <= rb2 + edy2;  eacc[2] <= rb2 + edy2;
          for (i = 0; i < 3; i = i + 1) begin
            crow[i] <= (use_cur ? cacc[i] : crow[i]) + {{16{fcy[i][25]}}, fcy[i], 4'd0};
            cacc[i] <= (use_cur ? cacc[i] : crow[i]) + {{16{fcy[i][25]}}, fcy[i], 4'd0};
          end
          if (py == hy) st <= S_WAIT;
          else py <= py + 1'b1;
        end else if (seek_left || (!covered &&
                     (wph == W_SEEKLU || (wph == W_START && dir_l)))) begin
          // one step back, drawing nothing: SEEKL over the interval to its
          // left end, or SEEKLU over the uncovered gap to its right end
          px <= px - 1'b1; tph <= 4'd0; wph <= covered ? W_SEEKL : W_SEEKLU;
          zacc <= zacc - {{16{fzx[25]}}, fzx, 4'd0};
          eacc[0] <= eacc[0] + edx0;
          eacc[1] <= eacc[1] + edx1;
          eacc[2] <= eacc[2] + edx2;
          for (i = 0; i < 3; i = i + 1)
            cacc[i] <= cacc[i] - {{16{fcx[i][25]}}, fcx[i], 4'd0};
        end else begin                 // one step right (SEEKR, or DRAW)
          if (use_cur) begin           // this row's first pixel: the anchor
            lx <= px;
            erow[0] <= eacc[0]; erow[1] <= eacc[1]; erow[2] <= eacc[2];
            zrow <= zacc;
            for (i = 0; i < 3; i = i + 1) crow[i] <= cacc[i];
          end
          wph <= commit ? W_DRAW : W_SEEKR;
          px <= px + 1'b1; tph <= 4'd0;
          zacc <= zacc + {{16{fzx[25]}}, fzx, 4'd0};
          eacc[0] <= eacc[0] - edx0;
          eacc[1] <= eacc[1] - edx1;
          eacc[2] <= eacc[2] - edx2;
          for (i = 0; i < 3; i = i + 1)
            cacc[i] <= cacc[i] + {{16{fcx[i][25]}}, fcx[i], 4'd0};
        end
      end
    endcase
  end

endmodule
`default_nettype wire
