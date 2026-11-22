// zseq.v -- the frame sequencer: walks the display list, then transforms
// and projects every object in the object list, feeding the rasterizer one
// screen triangle at a time. This is the silicon half of spec.py's GEOM
// contract; zeta/gpu.py's _geom() is the behavior it is held bit-equal to.
//
//   per vertex: yaw-rotate (Q14 quarter-wave ROM, folded exactly as the
//   spec builds SIN_Q14), translate by (obj - cam), camera-rotate, near
//   reject, and a truncate-toward-zero projection divide. The GUARD
//   reject bounds every quotient to 13 bits, so each divide is one
//   precheck plus a 13-step loop -- ~45 cycles per vertex, overlapped
//   with the rasterizer's frame clear.
//
//   per face: three vertex-cache lookups, index/validity checks, optional
//   backface cull on the screen-area sign, then a rdy/go handshake into
//   the rasterizer. Painter's order throughout: DL triangles first, then
//   objects in list order, faces in mesh order.
`default_nettype none

module zseq (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,       // pulse: sequence one band
    input  wire [8:0]  tile_y0,     // first screen row this band owns
    input  wire        first_pass,  // band 0: MEASURE each object's span.
                                    // Later bands READ it and skip whole
                                    // objects that cannot touch them.
    input  wire [15:0] lod_flat,    // depth past which Gouraud goes flat
                                    // (0 = never). The far half of the
                                    // fog's bargain: interpolating colour
                                    // across a face about to be fogged
                                    // into one is the EXPENSIVE work --
                                    // four divider passes against one.
    output wire        m_skp,       // METER: a face the bin skipped
    output wire        m_act,       // METER: sequencing (not idle)
    output wire        m_blk,       // METER: ...and BLOCKED, holding a
                                    // triangle the rasterizer will not
                                    // take. m_act high with m_blk low is
                                    // the sequencer being the bottleneck;
                                    // both high is the rasterizer being it
    output reg         done,        // pulse
    // DMEM external read port (registered: data 2 states after address)
    output reg  [13:0] rd_addr,
    input  wire [31:0] rd_data,
    // spec.OBJ_CART (frontier 20): with rd_cart up, rd_addr is a word of
    // object rd_obj's mesh AS THE STORE HOLDS IT -- [nv, nf, 3 a vertex,
    // 2 a face], a DMEM mesh's own layout -- and zmesh answers on rd_data
    // in the same two states. cm_ok: the loader admitted this object.
    output reg         rd_cart,
    output wire [5:0]  rd_obj,
    input  wire        cm_ok,
    // ...and DMEM's own word, unmuxed, for the one long path a read feeds:
    // the lit normal's three multiplies. A cart mesh is never lit, so that
    // path need not wait for the store's answer (the first fit that placed
    // failed there: zmesh's RAM -> nlev, a nanosecond over).
    input  wire [31:0] rd_dmem,
    // triangle handshake to the rasterizer
    input  wire        tri_rdy,
    output reg         tri_go,
    output reg         seq_item,
    // THE WALK'S PLACES, NOT THE DRAWN ONES. A pick id is a face's
    // position in the walk "drawn or not" (gpu.py), and the law walks
    // every object because the law has no bands. When the object bin
    // skips a whole object on a later band, its faces still occupy their
    // places -- so the count is bumped by nf instead of pulsed nf times.
    output reg         seq_skip,
    output reg  [10:0] seq_skip_n,
    output reg         t_tex,       // the emitted item samples the page
    output reg  [14:0] t_tint,      // ...and modulates it by THIS, the
    output reg         t_tinton,    // face's own colour word, if OBJ_TINT
    output reg  [7:0]  t_oid,        // {edged, index+1}: which object owns
                                     // pixels this triangle commits, or
                                     // 0 for "nobody asked for an outline"
    output reg         t_otint,      // ...or by the OBJECT's, if OBJ_OTINT,
                                     // which lights untextured faces too
    input  wire signed [13:0] l_x, l_y, l_z,  // spec.OBJ_LIT: the light,
    input  wire [5:0]  l_amb,       // pre-scaled by the diffuse gain
    output reg  [4:0]  t_page,      // which texture page this samples
    output reg         t_add,       // BLEND_ADD: bits 30:29 of the same
                                    // word pick the mode
    output reg  [4:0]  t_alpha,     // OBJ_BLEND: the face's sixteenths,
    output reg         t_blend,     // from bits 28:24 of its colour word
    output reg         t_span,      // OBJ_LODSPAN: one mip level a row
                                    // a countable item begins: one pulse
                                    // per DL entry and per GEOM face
                                    // EXAMINED, drawn or not -- the pick
                                    // register's stable id stream
    output reg signed [35:0] tx0, ty0, tx1, ty1, tx2, ty2,
    output reg  [50:0] tc0,         // the three channel bases at vertex
                                    // A: {12'd0,r5}x3 for color faces,
                                    // {u5*w', v5*w', w'} for textured
                                    // (the crown's affine-legal trio)
    output reg signed [25:0] tcxr, tcyr,  // per-channel color gradients,
    output reg signed [25:0] tcxg, tcyg,  // CFP fixed point (all 0 for
    output reg signed [25:0] tcxb, tcyb,  // flat faces and DL triangles)
    output reg  [15:0] tz0,         // depth at vertex A (0 for DL)
    output reg signed [25:0] tzx,   // depth gradients, ZFP fixed point
    output reg signed [25:0] tzy    // (0 for DL)
);
  `include "params.vh"

  // ---- the quarter-wave sine ROM, folded per the spec ---------------------
  reg signed [15:0] sq [0:256];
  `include "sinq_init.vh"
  reg  [9:0]  areg;
  wire [1:0]  quad = areg[9:8];
  wire [8:0]  aeff = quad[0] ? (9'd256 - {1'b0, areg[7:0]})
                             : {1'b0, areg[7:0]};
  wire signed [15:0] araw = sq[aeff];
  wire signed [15:0] aval = quad[1] ? -araw : araw;

  // ---- the vertex cache: {w[16:0], valid, sx[15:0], sy[15:0], z[15:0]} ----
  // (the crown appends the projection reciprocal ABOVE the old word, so
  // every existing field extraction survives verbatim)
  // ---- THE TRANSFORMED-VERTEX BUFFER (roadmap 15, step 1.5 part two) ----
  // This was a 256-entry cache indexed by vertex index WITHIN the current
  // mesh, so it was invalidated per object -- fine when the frame walked
  // the object list once, useless once it walks it once per band. Every
  // band re-ran the projection, whose divide loop is ~34 cycles a vertex,
  // and that is where the +29%/+45% the object bin could not touch was.
  //
  // Now it is indexed GLOBALLY: object o's vertices live at obase_v[o]+i,
  // so band 0 transforms and later bands read what band 0 left. No copy
  // and no second memory -- the face path reads exactly as before, only
  // the address changed.
  //
  // 2,304 entries x 66 bits = 14.9 M10K, paid for by the 72 the shrink
  // freed. Slots 0..2047 are the per-frame cache (fabric's worst frame
  // needs 1,833); 2048..2303 are SCRATCH for an object that does not fit,
  // which then behaves exactly as it did before -- re-transformed every
  // band, correct but slow. Overflow degrades, it does not break.
  localparam VB_CACHE = 2048, VB_SCRATCH = 2048;
  // ...plus eight slots above the scratch for THE CLIPPER's own vertices
  // (CL_SLOT), so a clipped face and an overflowed object cannot collide
  // 72 AND NOT 66: bits 71:66 are spec.OBJ_LIT's LEVEL for this
  // vertex, PREPENDED so that every existing field keeps its place.
  (* ramstyle = "M10K" *) reg [71:0] vc [0:2311];
  reg [11:0] vc_wa, vc_ra;
  reg [71:0] vc_wd, vc_q;
  // VERTEX C, REGISTERED (build 101). At 51.84 MHz the worst path on
  // the die ran from this cache's read port through gx/gy, the area
  // multiply, cull_box and f_reject into the state register at S_FN:
  // 24.1 ns against 22.4. A RAM read feeding a multiply feeding a
  // compare feeding a decision is three things too many for one
  // cycle, so S_FT and S_CLFT now only LATCH the corner here and the
  // decision is made a cycle later from pc, the way pa and pb were
  // always registered. One clock a face; the law is unchanged.
  reg [71:0] pc;
  reg        vc_we;
  reg [11:0] vb_base;                // where this object's vertices start
  reg        vb_ok;                  // ...and whether they fit the cache
  reg [11:0] obase_v [0:OL_MAX-1];   // per object, remembered by band 0
  reg [OL_MAX-1:0] ocached;
  wire [11:0] vb_at = vb_ok ? vb_base : VB_SCRATCH[11:0];
  // the mesh's section bases, as WIRES: S_OCHK needs fbase in the same
  // cycle it assigns it, to jump straight to the faces on a later band
  wire [13:0] w_cbase = mb_s[13:0] + 14'd2 + {nv[9:0], 1'b0} + nv[9:0];
  wire [13:0] w_fbase = w_cbase + ((gour || texf) ? nv[9:0] : 10'd0);
  wire        vb_fits = ({1'b0, vb_base} + {2'd0, nv[10:0]})
                        <= {1'b0, VB_CACHE[11:0]};

  // ---- THE FACE-LEVEL BIN, REGISTERED ---------------------------------
  // Band 0 records each face's screen rows; later bands skip a face they
  // cannot touch before fetching it. A culled face is stored EMPTY, so
  // those are skipped too.
  //
  // THE READ IS REGISTERED, and that is not a detail. Written with a
  // combinational read this array was "uninferred due to asynchronous
  // read logic" -- 4,096 x 18 bits as 73,728 flip-flops and a 4,096-way
  // mux, on a device with ~32,000 ALMs. Block RAM reads are registered,
  // so the address is set one state early (S_FN, for the NEXT face; the
  // face loop always passes through it) and the answer is waiting at
  // S_FW. Same shape as the vertex cache above, which infers cleanly.
  //
  // Worth 4.4 points of frame time at nine bands (worst cart +10.6% ->
  // +6.2%) for 7.2 M10K. At TWO bands it was worth almost nothing --
  // 4.4 cycles a face -- because each face is examined once more per
  // band, so the bin's value scales with band count while its cost does
  // not.
  localparam FB_MAX = 4096;
  (* ramstyle = "M10K" *) reg [17:0] fbin [0:FB_MAX-1];
  reg [11:0] fb_ra, fb_wa;
  reg [17:0] fb_q, fb_wd;
  reg        fb_we;
  reg [11:0] fb_base;
  reg        fb_ok;
  reg [11:0] fbase_v [0:OL_MAX-1];
  // HOW MANY PLACES THIS OBJECT SPENDS IN THE WALK, remembered by band 0.
  // A later band that skips the object whole still owes them: the pick id
  // is a face's position in the walk "drawn or not", and the law walks
  // every object because the law has no bands. Recorded here because the
  // skip happens at S_OT1, BEFORE the mesh header is read -- rd_data
  // there is an object-list word, not nf, which is the mistake this
  // array exists to make impossible.
  reg [10:0] onf [0:OL_MAX-1];
  reg [OL_MAX-1:0] fcached;
  always @(posedge clk) begin
    if (fb_we) fbin[fb_wa] <= fb_wd;
    fb_q <= fbin[fb_ra];
  end
  wire        fb_skip = !first_pass && fb_ok
                     && ((fb_q[17:9] > fb_q[8:0])          // culled
                      || (fb_q[8:0] < tile_y0)             // above the band
                      || (fb_q[17:9] > tile_y1));          // below it
  wire        fb_fits = ({1'b0, fb_base} + {2'd0, nf[10:0]})
                        <= {1'b0, FB_MAX[12:0]};
  // the face's own verdict, named so the bin and the branch cannot drift
  wire        f_reject = !idx_ok || !pa[48] || !pb[48] || !pc[48]
                      || cull_box || (oflags[0] && (area[36] || area == 0));
  always @(posedge clk) begin
    if (vc_we) vc[vc_wa] <= vc_wd;
    vc_q <= vc[vc_ra];
  end

  // ---- per-frame / per-object state ---------------------------------------
  reg [8:0]  n_dl, t;
  reg [2:0]  wi, ci;
  reg [13:0] dl_a, obase, vbase, fbase, faddr, cbase;
  reg [6:0]  n_ol, o;      // 7 bits: OL_MAX is 64
  reg signed [31:0] cx, cy, cz;
  reg signed [15:0] s_c, c_c, s_o, c_o;
  reg signed [15:0] s_p, c_p, s_r, c_r;   // object pitch and roll
  reg signed [15:0] s_cp, c_cp;           // camera pitch (inverse baked)
  reg signed [15:0] s_cr, c_cr;           // ...and camera ROLL, the bank
  reg [1:0]  rpair;                       // the rotation pair: 0 (x,y)
                                          // roll, 1 (y,z) pitch, 2 (x,z)
  reg signed [31:0] mb_s, ox, oy, oz;
  reg [9:0]  oyaw, opit, orol;
  reg [31:0] oflags, nv, nf;
  assign rd_obj = o[5:0];
  reg signed [31:0] dxr, dyr, dzr;
  reg [8:0]  vi;
  reg [1:0]  vi3;
  reg signed [31:0] vx, vy, vz;
  reg [9:0]  fi;
  reg [31:0] fidx;
  reg [71:0] pa, pb;
  // ---- LIGHT ACROSS A SURFACE (spec.OBJ_LIT) -------------------------
  // A LIT MESH IS A GOURAUD MESH whose vertex word happens to be a
  // NORMAL. Everything downstream -- the layout, the clipper, the three
  // channel gradients, the fill -- is the path gouraud already built,
  // and the only new thing is the one wire that turns the word into a
  // colour as it comes off the mesh. So `gour` simply includes it.
  // spec.OBJ_CART: a cart mesh is FLAT -- its gouraud, lit, texture, face-
  // tint and blend bits are not read (gpu.py masks the same five)
  wire       cartf = oflags[14];
  wire       litf = oflags[13] && !cartf;
  wire       gour = (oflags[1] && !cartf) || litf;   // OBJ_GOURAUD: the mesh LAYOUT, which
                                    // decides what to fetch and must not
                                    // depend on a depth nobody knows yet
  reg        far;                   // this face is past LOD_FLAT: fetch
                                    // as usual, but skip the colour
                                    // gradients -- the expensive part
  wire       texf = oflags[2] && !cartf;   // OBJ_TEX: the block carries uv
  // OBJ_OTINT: the light is ONE WORD in the object slot rather than nf
  // words in the mesh, so an actor can be re-lit every frame from where
  // it is standing. The object wins over the face when both are set.
  // OBJ_EDGE: the identity plane's value for this object. Index + 1, so
  // that 0 is the clear, the backdrop, the display list and every
  // object that did not ask -- and two DIFFERENT outlined objects
  // touching is an edge with no special case.
  // EVERY object is recorded; the flag says only whether a line is
  // DRAWN. It was 0 for un-outlined objects, which conflated "nobody
  // asked" with "nothing here" and made spec.VIS_BASE impossible.
  wire [7:0] oidv = {oflags[7], o[6:0] + 7'd1};
  wire       otintf = oflags[6];
  wire [14:0] otintv = oflags[31:17];   // 5:5:5, R 31:27 G 26:22 B 21:17
  wire       tintf = oflags[3] && !cartf;  // OBJ_TINT: ...and the face's colour
                                    // word LIGHTS it instead of being
                                    // discarded, which is what a
                                    // textured face did until build 89
  // WHICH PAGE. Five bits for TEX_PAGES = 24, so a cart can name a
  // page that does not exist; it reads as 0, which every cart has.
  // Clamping to the last slot instead would show whatever that slot
  // happened to hold -- a bug that moves when unrelated code does.
  wire [4:0] pagesel = oflags[12:8];
  wire [4:0] pagef = (pagesel < TEX_PAGES[4:0]) ? pagesel : 5'd0;
                                    // sixteen were
                                    // resident now, and zero is what
                                    // every older cart says
  wire       blendf = oflags[5] && !cartf; // OBJ_BLEND: this object composites
                                    // against what is already there and
                                    // writes NO depth, so blended faces
                                    // cannot occlude each other and their
                                    // order is the cart's own
  wire       spanf = oflags[4];     // OBJ_LODSPAN: the level once per
                                    // span, not once per pixel
  reg [14:0] tint;
  reg [4:0]  f_alpha;               // this face's sixteenths
  reg        f_add;                 // ...and its blend MODE
                                    // words instead (u | v<<8, 5-bit
                                    // texel space -- a color channel's
                                    // exact width, by design)
  reg [23:0] ca_r, cb_r, cc_r;      // the three vertex colors of a face
  reg [23:0] frgb8;                 // ...and the face's own 8:8:8, kept
                                    // because a LIT vertex wears it
  // N.L, with L ALREADY SCALED BY THE DIFFUSE GAIN in zeta_top -- three
  // multiplies a frame instead of one a vertex, and exact rather than
  // approximate, because dif * max(0, N.L) == max(0, N.(L*dif)) for a
  // gain that cannot be negative.
  wire signed [7:0]  nn_x = rd_dmem[23:16];
  wire signed [7:0]  nn_y = rd_dmem[15:8];
  wire signed [7:0]  nn_z = rd_dmem[7:0];
  wire signed [23:0] ndot = $signed({{16{nn_x[7]}}, nn_x}) * $signed({{10{l_x[13]}}, l_x})
                          + $signed({{16{nn_y[7]}}, nn_y}) * $signed({{10{l_y[13]}}, l_y})
                          + $signed({{16{nn_z[7]}}, nn_z}) * $signed({{10{l_z[13]}}, l_z});
  wire        [23:0] nmag = ndot[23] ? 24'd0 : ndot;   // facing away = 0
  // NINE bits, not eight. The shifted dot saturates at 255 and the
  // ambient adds up to 32, and 287 in eight bits is 31 -- a vertex
  // pointing straight at the light coming back nearly BLACK. Sized to
  // the sum and not to either addend.
  wire        [8:0]  nsum = {1'b0, ((|nmag[23:22]) ? 8'd255 : nmag[21:14])}
                          + {3'd0, l_amb};
  wire        [5:0]  nlvl = (nsum > 9'd32) ? 6'd32 : nsum[5:0];
  // ch * lvl >> 5, and lvl maxes at 32, so 255 comes back as 255 exactly
  // and there is nothing to clamp
  function [7:0] dim(input [7:0] ch, input [5:0] lv);
    reg [13:0] m;
    begin m = ch * lv; dim = m[12:5]; end
  endfunction
  function [23:0] dim3(input [23:0] rgb, input [5:0] lv);
    dim3 = {dim(rgb[23:16], lv), dim(rgb[15:8], lv), dim(rgb[7:0], lv)};
  endfunction
  // THE DOT PRODUCT LIVES IN THE VERTEX STAGE, not here. Done per FACE
  // it put three 8x14 multiplies, two 24-bit adds, a saturate, an add
  // and a clamp on the same edge that latches the vertex colour, and
  // the fit came back at -4.478 ns at 85C and -5.409 at 0C -- nearly
  // 20% over, on a change costing 88 ALM. All depth, no area.
  //
  // A vertex's level does not depend on the FACE, so it is computed
  // once where the vertex is transformed -- a stage with slack -- and
  // rides the vertex cache in bits 71:66. What is left here is three
  // 8x6 multiplies and a shift.
  reg  [5:0]  nlev;                 // this vertex's level, cached
  reg  [5:0]  lc_r;                 // vertex c's level, beside cw_r
  // ONE dim3, NOT THREE. Written as vw_a/vw_b/vw_c it read well and
  // instantiated NINE multipliers -- three a wire, all live at once,
  // when only one of them is ever consumed on a clock. DSP went 48 to
  // 62 and the fitter gave up: "Can't fit design in device", at 91%
  // logic and 94% of both the RAM and the DSP.
  //
  // The three assignments happen in three different STATES, so the
  // state is what selects the level, and there is one multiplier set.
  wire [5:0]  lv_sel = (st == S_FLB) ? pa[71:66]
                     : (st == S_FT)  ? pb[71:66]
                     :                 lc_r;
  wire [23:0] vword = litf ? dim3(frgb8, lv_sel) : rd_data[23:0];
  reg [16:0] wv;                    // this vertex's w = 2^30 / vz
  reg [16:0] cw_r;                  // corner c's w, latched off the cache
  reg [11:0] wp_a, wp_b, wp_c;      // octave-normalized w' per corner
  reg [16:0] ua17, va17, ub17, vb17, uc17, vc17;  // u5*w', v5*w'
  wire [16:0] aw = pa[65:49], bw = pb[65:49];
  wire [16:0] wq_or = aw | bw | cw_r; // msb of the OR is msb of the max
  wire [4:0]  wmsb =
      wq_or[16] ? 5'd16 : wq_or[15] ? 5'd15 : wq_or[14] ? 5'd14 :
      wq_or[13] ? 5'd13 : wq_or[12] ? 5'd12 : wq_or[11] ? 5'd11 :
      wq_or[10] ? 5'd10 : wq_or[9]  ? 5'd9  : wq_or[8]  ? 5'd8  :
      wq_or[7]  ? 5'd7  : wq_or[6]  ? 5'd6  : wq_or[5]  ? 5'd5  :
      wq_or[4]  ? 5'd4  : wq_or[3]  ? 5'd3  : wq_or[2]  ? 5'd2  :
      wq_or[1]  ? 5'd1  : 5'd0;
  wire signed [5:0] wsh = {1'b0, wmsb} - 6'sd11;
  function [11:0] wnrm(input [16:0] w, input signed [5:0] sh);
    wnrm = (sh >= 0) ? w >> sh : w << (-sh);
  endfunction
  // u5*w' and v5*w' at 17 bits: both operands widened, or the products
  // land at the operands' width (12 bits) and the page reads one texel
  wire [16:0] mua = {12'd0, ca_r[4:0]}  * {5'd0, wp_a};
  wire [16:0] mva = {12'd0, ca_r[12:8]} * {5'd0, wp_a};
  wire [16:0] mub = {12'd0, cb_r[4:0]}  * {5'd0, wp_b};
  wire [16:0] mvb = {12'd0, cb_r[12:8]} * {5'd0, wp_b};
  wire [16:0] muc = {12'd0, cc_r[4:0]}  * {5'd0, wp_c};
  wire [16:0] mvc = {12'd0, cc_r[12:8]} * {5'd0, wp_c};

  // ---- rotate datapath (operands latched into rs/rc before each use) ------
  reg signed [15:0] rs, rc;
  wire signed [31:0] ra = (rpair == 2'd1) ? vy : vx;
  wire signed [31:0] rb = (rpair == 2'd0) ? vy : vz;
  // THE PRODUCTS, REGISTERED (frontier B5). At 51.84 MHz the pair select,
  // four 32x16 multiplies and the 48-bit sum ran 0.60 ns over into vz
  // (719 paths). The products take a register and each rotation two
  // beats: the first only multiplies (rph low), the second sums and
  // moves on. Six clocks a vertex, of a frame that has gained 144,000.
  reg signed [47:0] rp_ac, rp_bs, rp_as, rp_bc;
  reg               rph;
  always @(posedge clk) begin
    rp_ac <= ra * rc;  rp_bs <= rb * rs;
    rp_as <= ra * rs;  rp_bc <= rb * rc;
  end
  wire signed [47:0] rot_a = rp_ac - rp_bs;
  wire signed [47:0] rot_b = rp_as + rp_bc;

  // ---- divider: q = |n|<<8 / z, z >= ZNEAR; GUARD keeps q under 2^13 ------
  // Classic restoring shift-left form: the divisor stays put, the
  // remainder shifts -- one 32-bit compare/subtract per cycle, no barrel
  // shifter (the barrel-shift form was this design's first Fmax miss).
  // The precheck (dividend's high 27 bits >= divisor) is exactly
  // "quotient would need a 14th bit", which the GUARD forbids anyway.
  reg  [36:0] rem;
  reg  [24:0] low;
  reg  [35:0] dvs;
  reg  [25:0] q;
  reg  [4:0]  k;
  reg         sgn;
  wire [36:0] rsh  = {rem[35:0], low[24]};
  wire [37:0] rsub = {1'b0, rsh} - {2'b0, dvs};
  // ---- RADIX-4: the same quotient, half the beats ----------------------
  // Two bits a step instead of one. The invariant rem < dvs holds either
  // way, so shifting TWO makes rsh2 < 4*dvs and the digit is 0..3 -- one
  // compare against each of dvs, 2*dvs, 3*dvs, taken in parallel and
  // picked by a mux. Three subtractors where there was one; the loop
  // count halves.
  //
  // WIDTHS FROM THE RANGE, NOT FROM TODAY'S NUMBERS: dvs < 2^36, so
  // 3*dvs needs 38 bits and rsh2 = 4*rem + 2 bits reaches 2^38. Sizing
  // these to the 37 bits the radix-2 form uses would wrap silently and
  // produce a plausible picture.
  wire [37:0] rsh2 = {rem[35:0], low[24:23]};
  wire [37:0] dvs2 = {dvs, 1'b0};
  wire [37:0] dvs3 = dvs2 + {2'd0, dvs};
  wire [38:0] rs1  = {1'b0, rsh2} - {3'd0, dvs};
  wire [38:0] rs2  = {1'b0, rsh2} - {1'b0, dvs2};
  wire [38:0] rs3  = {1'b0, rsh2} - {1'b0, dvs3};
  wire [1:0]  dig  = !rs3[38] ? 2'd3 : !rs2[38] ? 2'd2 :
                     !rs1[38] ? 2'd1 : 2'd0;
  wire [37:0] rem4 = !rs3[38] ? rs3[37:0] : !rs2[38] ? rs2[37:0] :
                     !rs1[38] ? rs1[37:0] : rsh2;

  // THE ODD BIT. A quotient of 17 bits is eight radix-4 steps and ONE
  // radix-2 step, not nine radix-4 steps -- nine would make 18 and the
  // extra bit is not free to discard. Same for 25 = twelve and one.
  // Beats: 17 -> 9, 25 -> 13, which is where the projection and the
  // gradient ladder each spend their time.
  wire [31:0] nabx = vx[31] ? -vx : vx;
  wire [31:0] naby = vy[31] ? -vy : vy;
  reg signed [17:0] sxr;
  reg signed [15:0] sx16;
  reg [15:0] vz16;
  wire signed [17:0] qsgn = sgn ? -{1'd0, q[16:0]} : {1'd0, q[16:0]};

  // ---- face test: a and b from pa/pb, c straight off the cache port -------
  // cache word: [48]=vld [47:32]=sx [31:16]=sy [15:0]=z
  wire signed [16:0] ax = {pa[47], pa[47:32]}, ay = {pa[31], pa[31:16]};
  wire signed [16:0] bx = {pb[47], pb[47:32]}, by = {pb[31], pb[31:16]};
  wire signed [16:0] gx = {pc[47], pc[47:32]},
                     gy = {pc[31], pc[31:16]};
  wire signed [36:0] area = (bx - ax) * (gy - ay) - (by - ay) * (gx - ax);

  // THE FRUSTUM CULL. The guard band is +/-2048 PIXELS -- six screens
  // either side -- so a face far off to the left survives every check
  // and pays full setup, the whole gradient ladder included, to paint
  // nothing. Measured on the fabric: 928 of 1,385 faces, 67%. Six
  // comparisons against the screen box replace all of it, and the
  // rejection is PIXEL-EXACT by construction: a triangle whose bounding
  // box misses the screen cannot cover a pixel.
  localparam signed [16:0] SCR_W = ZW << SUB;   // from the law,
  localparam signed [16:0] SCR_H = ZH << SUB;   // never typed twice

  // ---- THE OBJECT BIN (roadmap 15, step 1.5) ----------------------------
  // The paint runs once per band, and without a bin every band re-walks
  // the WHOLE object list -- re-transforming every vertex and re-culling
  // every face. Measured at build 91: ~120,000 clocks per extra band,
  // linear, which makes 45 tiles 7.8x the frame budget.
  //
  // A full face-level bin wants a per-frame transformed-vertex buffer
  // (1,833 vertices worst case = 11.8 M10K) and cannot be afforded until
  // the shrink pays for it. THIS is the version that fits today: remember
  // each object's SCREEN-ROW SPAN as the first band computes it, then let
  // later bands skip whole objects that cannot touch them. 64 objects x 18
  // bits = 1,152 bits, which is nothing, and it skips an object's CULLED
  // faces too -- which is where the cost actually is (fabric submits 2,982
  // faces to rasterise 469).
  //
  // It is worth exactly as much as the content is spatially separated:
  // measured, 12% of fabric's faces sit in objects spanning both bands,
  // 0% of lodspan's and flight's, but 61-71% of orbit's and bunny's --
  // those are a few big objects and this cannot help them. The vertex
  // buffer is what helps them, later.
  reg [17:0] obin [0:OL_MAX-1];      // {first row, last row} per object
  reg [8:0]  o_lo, o_hi;             // accumulated across this object
  wire [8:0] tile_y1 = tile_y0 + TH[8:0] - 9'd1;
  wire [8:0] ob_lo = obin[o[5:0]][17:9];
  wire [8:0] ob_hi = obin[o[5:0]][8:0];
  wire       band_hit = (ob_lo <= ob_hi)          // drew anything at all
                     && (ob_hi >= tile_y0) && (ob_lo <= tile_y1);
  // this face's screen rows, clamped -- the accumulator's input
  wire signed [16:0] fy_mn = (ay < by) ? ((ay < gy) ? ay : gy)
                                       : ((by < gy) ? by : gy);
  wire signed [16:0] fy_mx = (ay > by) ? ((ay > gy) ? ay : gy)
                                       : ((by > gy) ? by : gy);
  wire signed [16:0] fy_mn_p = fy_mn >>> SUB;
  wire signed [16:0] fy_mx_p = fy_mx >>> SUB;
  wire [8:0] fy_lo = fy_mn_p[16] ? 9'd0
                   : (fy_mn_p > ZH - 1) ? (ZH[8:0] - 9'd1) : fy_mn_p[8:0];
  wire [8:0] fy_hi = fy_mx_p[16] ? 9'd0
                   : (fy_mx_p > ZH - 1) ? (ZH[8:0] - 9'd1) : fy_mx_p[8:0];
  wire cull_box = (ax[16] && bx[16] && gx[16])          // all left of 0
               || (ay[16] && by[16] && gy[16])          // all above 0
               || (ax >= SCR_W && bx >= SCR_W && gx >= SCR_W)
               || (ay >= SCR_H && by >= SCR_H && gy >= SCR_H);
  // gradient numerators (plane equation), computed over registered face
  // vertices; ZFP fixed point via << 8 into the dividend
  reg signed [16:0] fza, fzb, fzc;
  reg signed [17:0] e01x, e01y, e02x, e02y;   // (x1-x0) etc, registered
  reg               gph;              // 0: d/dx pass, 1: d/dy pass
  reg        [1:0]  gch;              // channel: 0=z, then 1=r 2=g 3=b
  // per-channel plane values at A,B,C: depth uses the cached z16; colors
  // pull the matching 5-bit field of the vertex-color words (>>3, the
  // same quantize the law applies)
  wire [4:0] c5a = (gch == 2'd1) ? ca_r[23:19] :
                   (gch == 2'd2) ? ca_r[15:11] : ca_r[7:3];
  wire [4:0] c5b = (gch == 2'd1) ? cb_r[23:19] :
                   (gch == 2'd2) ? cb_r[15:11] : cb_r[7:3];
  wire [4:0] c5c = (gch == 2'd1) ? cc_r[23:19] :
                   (gch == 2'd2) ? cc_r[15:11] : cc_r[7:3];
  // textured faces run u5*w', v5*w', w' through the SAME ladder -- 17-bit
  // values, 18-bit signed operands; |gnum| stays under 2^34 in 36 bits
  wire signed [17:0] fa_c = (gch == 2'd0) ? {fza[16], fza} :
      texf ? ((gch == 2'd1) ? {1'b0, ua17} :
              (gch == 2'd2) ? {1'b0, va17} : {6'd0, wp_a}) :
             {13'd0, c5a};
  wire signed [17:0] fb_c = (gch == 2'd0) ? {fzb[16], fzb} :
      texf ? ((gch == 2'd1) ? {1'b0, ub17} :
              (gch == 2'd2) ? {1'b0, vb17} : {6'd0, wp_b}) :
             {13'd0, c5b};
  wire signed [17:0] fc_c = (gch == 2'd0) ? {fzc[16], fzc} :
      texf ? ((gch == 2'd1) ? {1'b0, uc17} :
              (gch == 2'd2) ? {1'b0, vc17} : {6'd0, wp_c}) :
             {13'd0, c5c};
  // ---- THE GRADIENT NUMERATOR, SPLIT (roadmap 23, corrected) ---------
  // This was ONE state: vertex-cache data -> three selects -> two 18x18
  // multiplies -> a subtract. gnum_r already registered the OUTPUT (see
  // its comment), but the chain INTO it was still the machine's longest,
  // and the fitter named it every time slack got thin: vc's write-enable
  // register to tcyb/tcxb, -0.644 ns with the texture pages in.
  //
  // Now the two PRODUCTS are registered and the subtract happens the
  // state after. One extra state per quotient; up to eight quotients a
  // face, so ~8 cycles a face -- about 0.5% of frame on fabric, against
  // the ~2 MHz of Fmax it buys back.
  //
  // WIDTHS SPELLED OUT because 18x18 needs 36 and Verilog would size
  // this to 18 if either operand were left narrow.
  wire signed [35:0] gp_a = (gph ? (fc_c - fa_c) : (fb_c - fa_c))
                          * (gph ? e01x : e02y);
  wire signed [35:0] gp_b = (gph ? (fb_c - fa_c) : (fc_c - fa_c))
                          * (gph ? e02x : e01y);
  reg  signed [35:0] gm_a, gm_b;
  wire signed [35:0] gnum = gm_a - gm_b;
  wire       far_w = (lod_flat != 16'd0) && (pa[15:0] >= lod_flat);
  reg signed [35:0] gnum_r;         // registered: the multiply chain was
  wire [35:0] gabs = gnum_r[35] ? -gnum_r : gnum_r;   // the critical path
  reg signed [36:0] farea;
  wire [36:0] aabs = farea[36] ? -farea : farea;
  wire        gsgn = gnum_r[35] ^ farea[36];
  wire signed [25:0] qclamp =
      (q > 26'd16777216) ? 26'sd16777216 : $signed(q);
  wire signed [25:0] qfin = gsgn ? -qclamp : qclamp;
  wire idx_ok = ({22'd0, fidx[9:0]} < nv) && ({22'd0, fidx[19:10]} < nv) &&
                ({22'd0, fidx[29:20]} < nv);

  // ======================= THE CLIPPER (zeta/clip.py) =====================
  // The oldest player-visible defect: a face with any vertex the rasteriser
  // cannot address was dropped WHOLE, so the ground tile under the camera
  // vanished. Now it is cut against the five view-space planes instead,
  // Sutherland-Hodgman, in the law's own plane order.
  //
  // ONLY FACES THAT WERE BEING DROPPED TAKE THIS PATH, so nothing that
  // renders today can move: a face whose three vertices already project
  // inside the guard never meets any of it.
  //
  // WHERE THE VIEW COORDINATES COME FROM. The vertex cache stores PROJECTED
  // values -- the clipper needs view space, which is discarded one state
  // later. The roadmap's fork was "widen the cache (+96 bits) or
  // re-transform on demand", and it priced the cache against a 256-entry
  // array. That array is 2,304 entries now, so widening costs ~22 M10K of
  // the 63 free, while RE-TRANSFORM costs ~45 cycles on the 0.5-3% of faces
  // that clip and no memory at all. The arithmetic moved under the fork;
  // take the re-transform. The rotate chain (S_VW..S_R2C) is re-entered
  // with cl_xf set, which is the whole "second path" the fork feared and it
  // is four lines.
  localparam CL_SLOT = 2304;        // 8 cache slots for clipped vertices,
                                    // clear of VB_SCRATCH so an overflowed
                                    // object can still be clipped
  // MLAB: three sixteen-word tables were three M10K blocks (build 98),
  // and their reads below are asynchronous, which is what LUT RAM is.
  (* ramstyle = "no_rw_check, MLAB" *)
  reg signed [31:0] clx [0:15];     // two banks of 8: [0..7] and [8..15],
  (* ramstyle = "no_rw_check, MLAB" *)
  reg signed [31:0] cly [0:15];     // ping-ponged per plane. A triangle cut
  (* ramstyle = "no_rw_check, MLAB" *)
  reg signed [31:0] clz [0:15];     // by five planes is at most 3+5 = 8
  reg        [23:0] cla [0:15];     // vertices, so eight is the BOUND, not
                                    // a measurement -- attrs keep the
                                    // source word's layout so the existing
                                    // setup path reads them unchanged
  reg signed [49:0] cld [0:7];      // this plane's distance per vertex
  reg [3:0]  cl_n, cl_m;            // input / output vertex counts
  reg        cl_bk;                 // which bank is the input
  reg [2:0]  cl_i, cl_di, cl_vi, cl_t;
  reg [2:0]  cl_pl;                 // plane 0..4, the law's order
  reg [2:0]  cl_k;                  // which coordinate is being lerped
  reg        cl_on;                 // this face is being clipped
  reg        vinv_near;             // why the last vertex was invalidated:
                                    // 1 = behind the near plane, 0 = a
                                    // guard or int16 breach. See f_allnear.
  reg        cl_xf;                 // ...and the rotate chain is on loan
  reg        cl_prj;                // ...and so is the projection chain
  reg [9:0]  cl_idx;                // the vertex index being re-transformed
  reg [8:0]  cl_lo, cl_hi;          // union of the emitted rows, for the bin
  wire [3:0] cl_ib = {cl_bk, 3'd0};
  wire [3:0] cl_ob = {~cl_bk, 3'd0};
  wire [2:0] cl_nx = ({1'b0, cl_i} + 1'b1 == cl_n) ? 3'd0 : cl_i + 1'b1;
  // how many attribute channels ride along: the law interpolates exactly
  // the fields vattr() returns, and no more
  wire [2:0] cl_nk = texf ? 3'd5 : (gour ? 3'd6 : 3'd3);

  // ---- the plane, as constants -------------------------------------------
  // a and b are 0 or +/-F with F = 1<<12, so the xy term is a SHIFT; only
  // the z coefficient is a general constant, and it is multiplied in LOGIC
  // because the DSPs have been 66/66 since the crown.
  // ONE READ PORT, and this is the whole difference between fitting and
  // not. Written with a mux per use -- distances at cl_di, edge ends at
  // cl_i and cl_i+1, the projection at cl_vi, three attribute words in the
  // fan -- it was FIFTEEN 16-way muxes over 120-bit vertices and cost
  // 7,893 combinational ALUTs, 105% of the device. That is the FIFO diet's
  // lesson at a smaller scale: a register file read at many indices is
  // crossbar, and crossbar is the expensive thing. Now every read goes
  // through cl_ri and lands in a holder.
  reg [3:0] cl_ri;
  wire signed [31:0] rd_x = clx[cl_ri];
  wire signed [31:0] rd_y = cly[cl_ri];
  wire signed [31:0] rd_z = clz[cl_ri];
  wire        [23:0] rd_a = cla[cl_ri];
  reg signed [31:0] ha_x, ha_y, ha_z;    // the edge's two ends, held so
  reg        [23:0] ha_a;                // the lerp can read them without
  reg signed [31:0] hb_x, hb_y, hb_z;    // indexing anything
  reg        [23:0] hb_a;
  wire signed [31:0] dvx = rd_x, dvy = rd_y, dvz = rd_z;
  wire signed [31:0] dvxy = CLIP_ISY[cl_pl] ? dvy : dvx;
  wire signed [43:0] cl_xysh = {dvxy, 12'd0};        // v * (F = 1<<12)
  wire signed [44:0] cl_xy_w = !CLIP_XY[cl_pl] ? 45'sd0 :
      CLIP_NEG[cl_pl] ? -{cl_xysh[43], cl_xysh} : {cl_xysh[43], cl_xysh};
  // C*vz WITHOUT A MULTIPLIER, and this is not an optimisation -- a 17x32
  // multiply inferred THREE DSPs on a device whose 66 have all been spoken
  // for since the crown. The map report read 69/66 and the fit would have
  // failed; the multstyle attribute did not hold it back. Every plane
  // coefficient is a CONSTANT, exactly as clip.py's own header says, so
  // each is four hard-wired shifts:
  //     near    1      =  2^0
  //     left    35312  =  2^15 + 2^11 + 2^9 - 2^4
  //     right   30192  =  2^15 - 2^11 - 2^9 - 2^4
  //     bottom  35056  =  2^15 + 2^11 + 2^8 - 2^4
  //     top     30448  =  2^15 - 2^11 - 2^8 - 2^4
  // gen_params asserts those five sums against the law's own PLANES, so a
  // coefficient that moves fails at generation instead of quietly here.
  wire signed [49:0] vz50 = {{18{dvz[31]}}, dvz};
  wire signed [49:0] pz_n = vz50;
  wire signed [49:0] pz_l = (vz50<<<15) + (vz50<<<11) + (vz50<<<9) - (vz50<<<4);
  wire signed [49:0] pz_r = (vz50<<<15) - (vz50<<<11) - (vz50<<<9) - (vz50<<<4);
  wire signed [49:0] pz_b = (vz50<<<15) + (vz50<<<11) + (vz50<<<8) - (vz50<<<4);
  wire signed [49:0] pz_t = (vz50<<<15) - (vz50<<<11) - (vz50<<<8) - (vz50<<<4);
  wire signed [49:0] cl_pz_w =
      (cl_pl == 3'd0) ? pz_n : (cl_pl == 3'd1) ? pz_l :
      (cl_pl == 3'd2) ? pz_r : (cl_pl == 3'd3) ? pz_b : pz_t;
  reg signed [49:0] cl_pz;
  reg signed [44:0] cl_pxy;
  wire [15:0] znear_w = ZNEAR;
  wire signed [49:0] cl_dsum = cl_pz + {{5{cl_pxy[44]}}, cl_pxy}
      + ((cl_pl == 3'd0) ? -$signed({34'd0, znear_w}) : 50'sd0);

  // ---- the crossing: va + tdiv((vb-va)*da, da-db), exactly the law -------
  // Widths are the RANGE's, not today's measurements: view coordinates are
  // signed 32, the plane coefficients push a distance to 50 bits, so the
  // product reaches 82 and the divisor 51. The quotient cannot exceed the
  // coordinate difference itself (|da| <= |da-db| at any crossing), which
  // is what lets the divide skip straight to the low 33 bits.
  reg signed [49:0] cl_da;
  reg [49:0] cl_dam;                // |da|
  reg [50:0] cl_den;                // |da - db|
  reg        cl_sgn;                // sign of the quotient
  reg signed [31:0] cl_va;          // the coordinate being interpolated
  // THE CROSSING'S MULTIPLY (frontier B3). It was one bit a beat -- 33
  // beats of shift-and-add for EACH coordinate of EACH crossing -- written
  // when the device had no DSP to spare. It had ten (56 of 66), and the
  // band histogram put the price: 43,164 clocks of the TND brawl's frame
  // 226 (436 crossings x 3 coordinates x 33), all of it inside band 0,
  // where the rasterizer can only wait for the sequencer.
  //
  // ONE BEAT NOW: |vb-va| (33 bits) x |da| (50) as one product, taken
  // modulo 2^82 exactly as the 82-bit accumulator took it. Four DSP
  // blocks, and it fitted SMALLER than the serial form (zseq 9,376 ALUTs
  // against 9,403, 232 fewer registers).
  //
  // THE DIVIDE STAYS SERIAL, on evidence: a radix-4 form of it was built,
  // crossed and fitted (16 beats a coordinate saved) and cost between 300
  // and 2,000 ALUTs depending on the run, on a device 98% placed. The
  // multiply is two thirds of the gain for none of the price.
  reg [81:0] cl_mac;
  reg [32:0] cl_mul;
  reg        cl_dasg;               // sign(da) ^ sign(den), fixed per edge
  reg [51:0] cl_rem;
  reg [32:0] cl_low, cl_q;
  reg [5:0]  cl_ck;
  wire [51:0] cl_rsh  = {cl_rem[50:0], cl_low[32]};
  wire [52:0] cl_rsub = {1'b0, cl_rsh} - {2'b0, cl_den};
  wire signed [33:0] cl_qs = cl_sgn ? -{1'b0, cl_q} : {1'b0, cl_q};
  wire signed [31:0] cl_res = cl_va + cl_qs[31:0];
  // da - db in full width; at a crossing the two have opposite signs, so
  // this cannot cancel and |den| >= |da|
  wire signed [50:0] cl_dsub = {cld[cl_i][49], cld[cl_i]}
                             - {cld[cl_nx][49], cld[cl_nx]};
  // the coordinate this step is interpolating, off the HOLDERS -- a field
  // select, not an indexed lookup
  wire [3:0] cl_ai = {1'b0, cl_i}  | {cl_bk, 3'd0};
  wire [3:0] cl_bi = {1'b0, cl_nx} | {cl_bk, 3'd0};
  wire signed [31:0] cl_ca =
      (cl_k == 3'd0) ? ha_x : (cl_k == 3'd1) ? ha_y :
      (cl_k == 3'd2) ? ha_z :
      (cl_k == 3'd3) ? (texf ? {27'd0, ha_a[4:0]} : {24'd0, ha_a[23:16]}) :
      (cl_k == 3'd4) ? (texf ? {27'd0, ha_a[12:8]} : {24'd0, ha_a[15:8]}) :
                       {24'd0, ha_a[7:0]};
  wire signed [31:0] cl_cb =
      (cl_k == 3'd0) ? hb_x : (cl_k == 3'd1) ? hb_y :
      (cl_k == 3'd2) ? hb_z :
      (cl_k == 3'd3) ? (texf ? {27'd0, hb_a[4:0]} : {24'd0, hb_a[23:16]}) :
      (cl_k == 3'd4) ? (texf ? {27'd0, hb_a[12:8]} : {24'd0, hb_a[15:8]}) :
                       {24'd0, hb_a[7:0]};
  wire signed [32:0] cl_delta = {cl_cb[31], cl_cb} - {cl_ca[31], cl_ca};
  wire [32:0] cl_dmag = cl_delta[32] ? -cl_delta : cl_delta;
  // a clipped face's three source vertices, and their attribute words
  wire [9:0] cl_src = (cl_vi == 3'd0) ? fidx[9:0] :
                      (cl_vi == 3'd1) ? fidx[19:10] : fidx[29:20];
  wire [23:0] cl_att = (cl_vi == 3'd0) ? ca_r : (cl_vi == 3'd1) ? cb_r : cc_r;
  // ---- THE NEAR REJECT ---------------------------------------------------
  // The clipper is exact and it is not cheap, and most of what it is handed
  // is a face ENTIRELY BEHIND THE EYE, which it cuts against five planes in
  // order to produce nothing. Measured on the fabric: of ~1,540 faces
  // entering the clipper each frame, ~1,456 emit no triangle at all.
  //
  // Sutherland-Hodgman on a triangle whose three vertices are all outside
  // ONE half-space emits the empty polygon at that plane, and clip.py then
  // returns [] on its `len(poly) < 3` check before touching the other four.
  // So dropping such a face is not an approximation of the law -- it IS the
  // law, arrived at sooner. The near plane is tested FIRST there, which is
  // why one bit is enough.
  //
  // ONE BIT, NOT FIVE. A vertex can also be invalidated at the divider
  // guard (S_PCX/S_PCY, |q| >= 2^13) or at the int16 clamp (S_SX/S_SY), and
  // those are NOT the clipper's planes -- the guard is GUARD px, the law's
  // side planes are that inset by CLIP_MARGIN, and S_SY's y is inverted, so
  // a "vertex is outside the left plane" bit inferred from them is exact
  // only by luck of implication direction. The NEAR test is the same
  // comparison in both machines (vz < ZNEAR), so only that reason is
  // carried, in the otherwise-dead low bit of an invalid cache word.
  wire f_allnear = !pa[48] && !pb[48] && !pc[48]
                &&  pa[0]  &&  pb[0]  &&  pc[0];
  // THE CLIP TRIGGER, and it is exactly the law's: a face is cut when any
  // vertex failed to project, which is the same test that used to drop it.
  // ...minus the ones the clipper would only empty. Those fall through to
  // f_reject below, which already writes their empty bin entry.
  wire f_clip = idx_ok && (!pa[48] || !pb[48] || !pc[48]) && !f_allnear;

  localparam [6:0]     // 7 bits since the bank: at [5:0] the new
                       // states 64.. truncated silently to S_IDLE and
                       // the frame wedged with no error anywhere
    S_IDLE = 0,  S_DLN_W = 1,  S_DLN = 2,   S_DLT_W = 3,  S_DLT = 4,
    S_DLE = 5,   S_CAM_W = 6,  S_CAM = 7,   S_CT1 = 8,    S_CT2 = 9,
    S_OLN_W = 10, S_OLN = 11,  S_OBJ_W = 12, S_OBJ = 13,  S_OT1 = 14,
    S_OT2 = 15,  S_HD_W = 16,  S_HD0 = 17,  S_HD1 = 18,   S_OCHK = 19,
    S_VW = 20,   S_VC = 21,    S_R1 = 22,   S_ADD = 23,   S_R2 = 24,
    S_NEAR = 25, S_PCX = 26,   S_DX = 27,   S_SX = 28,    S_PCY = 29,
    S_DY = 30,   S_SY = 31,    S_VST = 32,  S_VINV = 33,  S_FW = 34,
    S_F0 = 35,   S_F1 = 36,    S_FLA = 37,  S_FLB = 38,   S_FT = 39,
    S_FE = 40,   S_FN = 41,    S_ONXT = 42, S_FIN = 43,
    S_GZ = 44,   S_GP = 45,    S_GD = 46,   S_GQ = 47,   S_GN = 48,
    S_CP_W = 49, S_CP = 50,    S_CP1 = 51,  S_CP2 = 52,
    S_OT2B = 53, S_OT3 = 54,   S_OT4 = 55,  S_OT5 = 56,   S_OT6 = 57,
    S_RR = 58,   S_RP = 59,    S_R2B = 60,  S_DW = 61,
    S_TW = 62,   S_TM = 63,
    // the 6-bit state register was exactly full at S_TM; the bank needs
    // five more (one fetch chain, one rotation) so it is 7 bits now
    S_CR_W = 64, S_CR = 65,   S_CR1 = 66,  S_CR2 = 67,  S_R2C = 68,
    // 69, not 64: 64 is S_CR_W. The list is not in numeric order
    // and a value picked without reading all of it collides in
    // silence -- the frame simply wedges, exactly as the note at
    // the top of this block says it did before.
    S_GN2 = 69,
    // THE CLIPPER. 70..87, and the highest previously used was 69 -- read
    // the whole list before picking, because a collision here does not
    // error, it wedges the frame in silence (S_TM = 63 and CAM_ROLL both
    // taught this).  st is 7 bits, so 127 is the ceiling.
    S_CLC = 70,   S_CLXA = 71,  S_CLXB = 72,  S_CLST = 73,
    S_CLP = 74,   S_CLD1 = 75,  S_CLD2 = 76,  S_CLE = 77,
    S_CLX0 = 78,  S_CLM0 = 79,  S_CLM = 80,   S_CLV0 = 81,
    S_CLDV = 82,  S_CLXS = 83,  S_CLN = 84,   S_CLPR = 85,
    S_CLPN = 86,  S_CLFA = 87,  S_CLFB = 88,  S_CLFC = 89,
    S_CLFD = 90,  S_CLFT = 91,  S_CLNX = 92,  S_CLDN = 93,
    // ...and the states that serialise the polygon reads through cl_ri
    S_CLE0 = 94,  S_CLE1 = 95,  S_CLE2 = 96,  S_CLPR0 = 97,
    // vertex c registered (build 101): 98 and 99, the highest so far
    S_FT2 = 98,   S_CLFT2 = 99;
  reg [6:0] st;
  // THE METER. S_DLE and S_FE are the only two states that hold a finished
  // triangle waiting on tri_rdy, so "active but not in one of those" is
  // the sequencer doing its own work and nothing else's.
  assign m_skp = (st == S_F0) && fb_skip;
  assign m_act = (st != S_IDLE);
  assign m_blk = ((st == S_DLE) || (st == S_FE)) && !tri_rdy;

  always @(posedge clk) begin
    done <= 1'b0;
    tri_go <= 1'b0;
    seq_item <= 1'b0;
    seq_skip <= 1'b0;
    vc_we <= 1'b0;
    fb_we <= 1'b0;
    if (!rst_n) begin           // (m_act/m_blk are assigned below the case)
      rd_cart <= 1'b0;
      rph <= 1'b0;
      st <= S_IDLE;
      cl_on <= 1'b0; cl_xf <= 1'b0; cl_prj <= 1'b0;
    end
    else case (st)
      // the clipper's three "chain on loan" flags are cleared at every band
      // start as well as at reset: a flag surviving a wedged frame would
      // route the NEXT frame's ordinary vertices into the clipper's states
      S_IDLE: if (start) begin
        rd_cart <= 1'b0;
        rd_addr <= DL_BASE[13:0];
        cl_on <= 1'b0; cl_xf <= 1'b0; cl_prj <= 1'b0;
        st <= S_DLN_W;
      end

      // ---- display list: n, then 7 words per triangle -------------------
      S_DLN_W: st <= S_DLN;
      S_DLN: begin
        n_dl <= (rd_data > DL_MAX) ? DL_MAX[8:0] : rd_data[8:0];
        t <= 0; wi <= 0; ci <= 0;
        dl_a <= DL_BASE[13:0] + 1'b1;
        rd_addr <= (rd_data == 0) ? CAM_X[13:0] : DL_BASE[13:0] + 1'b1;
        st <= (rd_data == 0) ? S_CAM_W : S_DLT_W;
      end
      S_DLT_W: st <= S_DLT;
      S_DLT: begin                    // x0 y0 x1 y1 x2 y2 rgb
        case (wi)
          3'd0: tx0 <= {rd_data, 4'b0};  3'd1: ty0 <= {rd_data, 4'b0};
          3'd2: tx1 <= {rd_data, 4'b0};  3'd3: ty1 <= {rd_data, 4'b0};
          3'd4: tx2 <= {rd_data, 4'b0};  3'd5: ty2 <= {rd_data, 4'b0};
          default: begin
            tc0 <= {12'd0, rd_data[23:19], 12'd0, rd_data[15:11],
                    12'd0, rd_data[7:3]};
            tcxr <= 26'sd0; tcyr <= 26'sd0;
            tcxg <= 26'sd0; tcyg <= 26'sd0;
            tcxb <= 26'sd0; tcyb <= 26'sd0;
            tz0 <= 16'd0; tzx <= 26'sd0; tzy <= 26'sd0;
            t_tex <= 1'b0; t_tinton <= 1'b0; t_span <= 1'b0;
            t_otint <= 1'b0; t_oid <= 8'd0;
            t_blend <= 1'b0; t_alpha <= 5'd0; t_page <= 5'd0;
            t_add <= 1'b0;
          end
        endcase
        if (wi == 6) begin seq_item <= 1'b1; st <= S_DLE; end
        else begin
          wi <= wi + 1'b1; rd_addr <= rd_addr + 1'b1; st <= S_DLT_W;
        end
      end
      S_DLE: if (tri_rdy) begin       // stalls here until the clear is done
        tri_go <= 1'b1;
        t <= t + 1'b1; wi <= 0; ci <= 0;
        dl_a <= dl_a + DL_STRIDE[13:0];
        if (t + 1'b1 == n_dl) begin
          rd_addr <= CAM_X[13:0]; st <= S_CAM_W;
        end else begin
          rd_addr <= dl_a + DL_STRIDE[13:0]; st <= S_DLT_W;
        end
      end

      // ---- camera: cells 8..11, then its two trig values ----------------
      S_CAM_W: st <= S_CAM;
      S_CAM: begin
        case (ci)
          3'd0: cx <= rd_data;
          3'd1: cy <= rd_data;
          3'd2: cz <= rd_data;
          default: ;                  // ci==3 is the yaw word, taken below
        endcase
        if (ci == 3) begin areg <= 10'd0 - rd_data[9:0]; st <= S_CT1; end
        else begin ci <= ci + 1'b1; rd_addr <= rd_addr + 1'b1; st <= S_CAM_W;
        end
      end
      S_CT1: begin s_c <= aval; areg <= areg + 10'd256; st <= S_CT2; end
      S_CT2: begin c_c <= aval; rd_addr <= CAM_PITCH[13:0]; st <= S_CP_W; end
      S_CP_W: st <= S_CP;
      S_CP: begin areg <= 10'd0 - rd_data[9:0]; st <= S_CP1; end
      S_CP1: begin s_cp <= aval; areg <= areg + 10'd256; st <= S_CP2; end
      S_CP2: begin c_cp <= aval; rd_addr <= CAM_ROLL[13:0]; st <= S_CR_W; end
      S_CR_W: st <= S_CR;
      S_CR: begin areg <= 10'd0 - rd_data[9:0]; st <= S_CR1; end
      S_CR1: begin s_cr <= aval; areg <= areg + 10'd256; st <= S_CR2; end
      S_CR2: begin c_cr <= aval; rd_addr <= OL_BASE[13:0]; st <= S_OLN_W; end
      S_OLN_W: st <= S_OLN;
      S_OLN: begin
        n_ol <= (rd_data > OL_MAX) ? OL_MAX[6:0] : rd_data[6:0];
        o <= 0; ci <= 0; vb_base <= 12'd0; vb_ok <= 1'b0;
        fb_base <= 12'd0; fb_ok <= 1'b0;
        obase <= OL_BASE[13:0] + 1'b1;
        rd_addr <= OL_BASE[13:0] + 1'b1;
        st <= (rd_data == 0) ? S_FIN : S_OBJ_W;
      end

      // ---- one object: 6 words, validation, trig, mesh header -----------
      S_OBJ_W: st <= S_OBJ;
      S_OBJ: begin
        case (ci)
          3'd0: mb_s <= rd_data;  3'd1: ox <= rd_data;
          3'd2: oy <= rd_data;    3'd3: oz <= rd_data;
          3'd4: begin
            oyaw <= rd_data[9:0];
            opit <= rd_data[19:10];
            orol <= rd_data[29:20];
          end
          default: oflags <= rd_data;
        endcase
        if (ci == 5) begin
          dxr <= ox - cx; dyr <= oy - cy; dzr <= oz - cz;
          o_lo <= 9'd511; o_hi <= 9'd0;   // empty: lo > hi, so a object
          st <= S_OT1;                    // that draws nothing is skipped
        end else begin
          ci <= ci + 1'b1; rd_addr <= rd_addr + 1'b1; st <= S_OBJ_W;
        end
      end
      S_OT1: begin
        areg <= oyaw;
        // THE SKIP: a later band that this object's measured span cannot
        // reach costs one state instead of a full mesh walk.
        if (mb_s[31] || mb_s >= DMEM_WORDS - 2 || (cartf && !cm_ok)) begin
          vb_ok <= 1'b0;                          // (a cart mesh the loader
          if (first_pass) onf[o[5:0]] <= 11'd0;   // refused: gpu.py continues too)
          st <= S_ONXT;
        end else if (!first_pass && !band_hit) begin
          // nf is on rd_data THIS cycle, which is why the bump can be
          // local: the skip and the count it owes happen together
          vb_ok <= 1'b0;
          seq_skip <= 1'b1; seq_skip_n <= onf[o[5:0]];
          st <= S_ONXT;
        end
        else begin
          // an admitted cart mesh: from here its mesh is the store's, read
          // as a DMEM mesh at address 0 would be
          if (cartf) begin mb_s <= 32'd0; rd_cart <= 1'b1; end
          st <= S_OT2;
        end
      end
      S_OT2: begin s_o <= aval; areg <= oyaw + 10'd256; st <= S_OT2B; end
      S_OT2B: begin c_o <= aval; areg <= opit; st <= S_OT3; end
      S_OT3: begin s_p <= aval; areg <= opit + 10'd256; st <= S_OT4; end
      S_OT4: begin c_p <= aval; areg <= orol; st <= S_OT5; end
      S_OT5: begin s_r <= aval; areg <= orol + 10'd256; st <= S_OT6; end
      S_OT6: begin c_r <= aval; rd_addr <= mb_s[13:0]; st <= S_HD_W; end
      S_HD_W: st <= S_HD0;
      S_HD0: begin
        nv <= rd_data;
        rd_addr <= mb_s[13:0] + 1'b1;
        st <= S_HD1;
      end
      S_HD1: st <= S_OCHK;
      S_OCHK: begin
        nf <= rd_data;
        if (nv > MESH_NV_MAX || rd_data > MESH_NF_MAX ||
            ({1'b0, mb_s[13:0]} + 15'd2 +
             {5'd0, nv[8:0], 1'b0} + {6'd0, nv[8:0]} +
             ((gour || texf) ? {6'd0, nv[8:0]} : 15'd0) +
             {4'd0, rd_data[9:0], 1'b0} > DMEM_WORDS[14:0]))
          begin
            vb_ok <= 1'b0;
            if (first_pass) onf[o[5:0]] <= 11'd0;  // the law skips it too
            st <= S_ONXT;
          end
        else begin
          if (first_pass) onf[o[5:0]] <= rd_data[10:0];
          vbase <= mb_s[13:0] + 2'd2;
          cbase <= w_cbase;
          fbase <= w_fbase;
          vi <= 0; vi3 <= 0;
          if (first_pass) begin
            // BAND 0 TRANSFORMS, and records where it put the vertices so
            // the other bands can find them. An object that will not fit
            // the cache is marked uncached and works out of the scratch
            // slots -- re-transformed every band, exactly as before.
            obase_v[o[5:0]] <= vb_base;
            ocached[o[5:0]] <= vb_fits;
            vb_ok <= vb_fits;
            fbase_v[o[5:0]] <= fb_base;
            fcached[o[5:0]] <= fb_fits;
            fb_ok <= fb_fits;
            rd_addr <= mb_s[13:0] + 2'd2;
            st <= (nv == 0) ? S_ONXT : S_VW;
          end else begin
            vb_base <= obase_v[o[5:0]];
            vb_ok   <= ocached[o[5:0]];
            fb_base <= fbase_v[o[5:0]];
            fb_ok   <= fcached[o[5:0]];
            fb_ra   <= fbase_v[o[5:0]];   // face 0, ready at S_FW
            if (ocached[o[5:0]]) begin
              // ALREADY TRANSFORMED. Straight to the faces -- this jump
              // is the whole point of the buffer: it skips the projection
              // divide, ~34 cycles a vertex, for every band after the
              // first.
              fi <= 0; faddr <= w_fbase; rd_addr <= w_fbase;
              st <= (rd_data == 0) ? S_ONXT : S_FW;
            end else begin
              rd_addr <= mb_s[13:0] + 2'd2;
              st <= (nv == 0) ? S_ONXT : S_VW;
            end
          end
        end
      end

      // ---- one vertex: read, rotate, translate, rotate, project ---------
      S_VW: st <= S_VC;
      S_VC: begin
        case (vi3)
          2'd0: vx <= rd_data;  2'd1: vy <= rd_data;
          2'd2: vz <= rd_data;
          // ---- spec.OBJ_LIT: A FOURTH READ, and only for a lit mesh.
          // The normal is not beside the position -- it is in the
          // per-vertex word block at cbase + i -- so it costs its own
          // address and its own two states. Two clocks a vertex, once
          // a frame, against three dot products a FACE if it were done
          // there instead: 128 of them for this sphere rather than 756,
          // and out of the path that was 4.5 ns over.
          default: nlev <= nlvl;
        endcase
        if (vi3 == 2 && litf) begin
          rd_addr <= cbase + {5'd0, vi[8:0]};
          vi3 <= 2'd3; st <= S_VW;
        end
        else if (vi3 == 2 || vi3 == 3) begin
          if (!litf) nlev <= 6'd0;
          rs <= s_r; rc <= c_r; rpair <= 2'd0; st <= S_RR;
        end
        else begin
          vi3 <= vi3 + 1'b1; rd_addr <= rd_addr + 1'b1; st <= S_VW;
        end
      end
      S_RR: begin                     // roll: (x,y)
        rph <= !rph;                  // beat one: the products only
        if (rph) begin
          vx <= rot_a[45:14]; vy <= rot_b[45:14];
          rs <= s_p; rc <= c_p; rpair <= 2'd1;
          st <= S_RP;
        end
      end
      S_RP: begin                     // pitch: (y,z)
        rph <= !rph;                  // beat one: the products only
        if (rph) begin
          vy <= rot_a[45:14]; vz <= rot_b[45:14];
          rs <= s_o; rc <= c_o; rpair <= 2'd2;
          st <= S_R1;
        end
      end
      S_R1: begin                     // yaw: (x,z)
        rph <= !rph;                  // beat one: the products only
        if (rph) begin
          vx <= rot_a[45:14]; vz <= rot_b[45:14];
          rs <= s_c; rc <= c_c;
          st <= S_ADD;
        end
      end
      S_ADD: begin
        vx <= vx + dxr; vy <= vy + dyr; vz <= vz + dzr;
        st <= S_R2;
      end
      S_R2: begin                     // camera yaw, then camera pitch
        rph <= !rph;                  // beat one: the products only
        if (rph) begin
          vx <= rot_a[45:14]; vz <= rot_b[45:14];
          rs <= s_cp; rc <= c_cp; rpair <= 2'd1;
          st <= S_R2B;
        end
      end
      S_R2B: begin                    // ...and finally the BANK, about
        rph <= !rph;                  // beat one: the products only
        if (rph) begin
          vy <= rot_a[45:14];           // the view axis, which is what makes
          vz <= rot_b[45:14];           // it a bank: rolling any earlier
          rs <= s_cr; rc <= c_cr;       // would tilt the axis the pitch then
          rpair <= 2'd0;                // turns about
          st <= S_R2C;
        end
      end
      S_R2C: begin
        rph <= !rph;                  // beat one: the products only
        if (rph) begin
          vx <= rot_a[45:14]; vy <= rot_b[45:14];
          // the clipper borrows this chain to recover VIEW space, which the
          // projection below is about to throw away
          st <= cl_xf ? S_CLST : S_NEAR;
        end
      end
      S_NEAR:
        if (vz < ZNEAR) begin vinv_near <= 1'b1; st <= S_VINV; end
        else begin
          dvs <= {5'd0, vz[30:0]};
          rem <= 37'd8192;            // the crown divide first: dividend
          low <= 25'd0;               // 2^30, head 2^30>>17, tail zero --
          q <= 0; k <= 5'd8;         // no precheck needed (8192 < ZNEAR)
          vz16 <= (|vz[30:23]) ? 16'hFFFF : vz[22:7];    // z >> ZSHIFT, sat
          st <= S_DW;
        end
      S_DW: begin                     // w = 2^30 / vz, the same datapath;
        q <= {q[24:0], ~rsub[37]};    // the exit cycle loads X's dividend
        if (k == 0) begin
          rem <= {10'd0, nabx[31:5]}; // dividend (|vx|<<12) bits [43:17]
          low <= {nabx[4:0], 12'd0, 8'd0};   // dividend bits [16:0], high
          sgn <= vx[31];
          st <= S_PCX;
        end else begin
          rem <= rem4[36:0];
          q   <= {q[23:0], dig};
          low <= {low[22:0], 2'b0};
          k <= k - 1'b1;
        end
      end
      S_PCX: begin                    // high part >= divisor: q needs an
        wv <= (q == 26'd0) ? 17'd1 : q[16:0];   // ...and w lands here
        if (rem >= {1'b0, dvs}) begin vinv_near <= 1'b0; st <= S_VINV; end
        else begin q <= 0; k <= 5'd8; st <= S_DX; end
      end
      S_DX: if (k == 0) begin           // the final RADIX-2 beat
        rem <= rsub[37] ? rsh : rsub[36:0];
        q <= {q[24:0], ~rsub[37]};
        low <= {low[23:0], 1'b0};
        st <= S_SX;
      end else begin
        rem <= rem4[36:0];
        q   <= {q[23:0], dig};
        low <= {low[22:0], 2'b0};
        k <= k - 1'b1;
      end
      S_SX: begin
        sxr = 18'sd2560 + qsgn;               // (W/2) << SUB
        if (sxr < -18'sd32768 || sxr > 18'sd32767)
          begin vinv_near <= 1'b0; st <= S_VINV; end
        else begin
          sx16 <= sxr[15:0];
          dvs <= {5'd0, vz[30:0]};
          rem <= {10'd0, naby[31:5]};
          low <= {naby[4:0], 12'd0, 8'd0};
          sgn <= vy[31];
          st <= S_PCY;
        end
      end
      S_PCY:
        if (rem >= {1'b0, dvs}) begin vinv_near <= 1'b0; st <= S_VINV; end
        else begin q <= 0; k <= 5'd8; st <= S_DY; end
      S_DY: if (k == 0) begin
        rem <= rsub[37] ? rsh : rsub[36:0];
        q <= {q[24:0], ~rsub[37]};
        low <= {low[23:0], 1'b0};
        st <= S_SY;
      end else begin
        rem <= rem4[36:0];
        q   <= {q[23:0], dig};
        low <= {low[22:0], 2'b0};
        k <= k - 1'b1;
      end
      S_SY: begin
        sxr = 18'sd2304 - qsgn;               // (H/2) << SUB
        if (sxr < -18'sd32768 || sxr > 18'sd32767)
          begin vinv_near <= 1'b0; st <= S_VINV; end
        else begin
          vc_we <= 1'b1;
          vc_wa <= cl_prj ? (CL_SLOT[11:0] + {9'd0, cl_vi})
                          : (vb_at + {4'd0, vi[7:0]});
          vc_wd <= {nlev, wv, 1'b1, sx16, sxr[15:0], vz16};
          st <= cl_prj ? S_CLPN : S_VST;
        end
      end
      S_VINV: begin
        // A CLIPPED VERTEX CANNOT LAND HERE, and that is CLIP_MARGIN's whole
        // job: Sutherland-Hodgman puts a new vertex exactly ON its plane,
        // the guard test is strict on the far side, and truncation pushes
        // outward -- so the law insets the four side planes by one pixel.
        // vz >= ZNEAR holds too, because truncation toward zero moves an
        // interpolated coordinate back toward the inside vertex. If this
        // ever fires for a clipped vertex the cross will say so loudly.
        vc_we <= 1'b1;
        vc_wa <= cl_prj ? (CL_SLOT[11:0] + {9'd0, cl_vi})
                        : (vb_at + {4'd0, vi[7:0]});
        vc_wd <= {71'd0, vinv_near};
        st <= cl_prj ? S_CLPN : S_VST;
      end
      S_VST: begin
        vi <= vi + 1'b1; vi3 <= 0;
        if ({23'd0, vi} + 1'b1 == nv) begin
          fi <= 0; faddr <= fbase; rd_addr <= fbase;
          fb_ra <= fb_base;             // face 0, ready at S_FW
          st <= (nf == 0) ? S_ONXT : S_FW;
        end else begin
          rd_addr <= vbase + {vi[8:0], 1'b0} + {2'd0, vi[8:0]} + 14'd3;
          st <= S_VW;
        end
      end

      // ---- one face: two words, three lookups, test, emit ---------------
      S_FW: begin seq_item <= 1'b1; st <= S_F0; end
      S_F0: begin                     // rd_data = index word
        fidx <= rd_data;
        vc_ra <= vb_at + {4'd0, rd_data[7:0]};   // vertex a
        rd_addr <= faddr + 1'b1;      // fetch rgb
        // THE BIN'S SKIP LANDS HERE, not at S_FW. fb_ra is set at S_FN,
        // so the memory reads it DURING S_FW and fb_q only settles at the
        // end of it -- at S_FW the answer is still the previous face's.
        // One state later it is this face's, and skipping here still
        // avoids the vertex lookups, the cull and the whole gradient
        // setup. (Registered reads cost a cycle of latency; that is the
        // price of not being 73,728 flip-flops.)
        st <= fb_skip ? S_FN : S_F1;
      end
      S_F1: begin                     // (gour: start streaming the three
        vc_ra <= vb_at + {4'd0, fidx[17:10]};    //  vertex colors, same path
        if (gour || texf)
          rd_addr <= cbase + {2'd0, fidx[9:0]};   //  2-state pipe)
        st <= S_FLA;
      end
      S_FLA: begin
        pa <= vc_q;
        // the face's rgb word is on rd_data in THIS state whatever the
        // mesh is; the else-branch below only reads it for flat faces,
        // so a textured face used to let it go by untouched
        tint <= {rd_data[23:19], rd_data[15:11], rd_data[7:3]};
        frgb8 <= rd_data[23:0];   // spec.OBJ_LIT wears this
        // the same word carries OBJ_BLEND's alpha in 28:24 -- clamped
        // here so 17..31 mean opaque rather than wrapping the lerp
        f_alpha <= (rd_data[28:24] > 5'd16) ? 5'd16 : rd_data[28:24];
        f_add   <= (rd_data[30:29] == 2'd1);   // mode 1 = BLEND_ADD
        vc_ra <= vb_at + {4'd0, fidx[27:20]};    // vertex c
        if (gour || texf) rd_addr <= cbase + {2'd0, fidx[19:10]};
        else                          // rgb word lands here; gour ignores
          tc0 <= {12'd0, rd_data[23:19], 12'd0, rd_data[15:11],
                  12'd0, rd_data[7:3]};
        st <= S_FLB;
      end
      S_FLB: begin
        pb <= vc_q;
        if (gour || texf) begin       // vertex a's word lands here --
          ca_r <= vword;               // and it IS the face's base value
          // ...AND SO IS tc0, which is the value the rasterizer starts
          // from. Left reading rd_data it painted the raw NORMAL as a
          // colour -- a blue-green ball, the vertex words shown as
          // themselves -- while ca_r/cb_r/cc_r carried the right
          // gradients around it. Two ways of saying the same vertex,
          // and only one of them had been told about the light.
          tc0 <= {12'd0, vword[23:19], 12'd0, vword[15:11],
                  12'd0, vword[7:3]};     // (textured: S_TM overwrites)
          rd_addr <= cbase + {2'd0, fidx[29:20]};
        end
        st <= S_FT;
      end
      S_FT: begin                     // vc_q = vertex c this cycle:
        pc <= vc_q;                   // latch it (see pc above)
        cb_r <= vword;                // vertex b's word lands THIS
        st <= S_FT2;                  // cycle, dimmed by pb's level
      end
      S_FT2:                          // pc = vertex c, registered
        // THE FACE-LEVEL BAND REJECT. Without it a later band pays the
        // full gradient setup -- the texture divides included -- for every
        // face of every object it touches, and then hands the rasterizer a
        // triangle whose box is empty. The face's rows are already known
        // here (fy_lo/fy_hi, computed for the object bin), so this costs
        // nothing and is exactly equivalent: a face outside the band
        // contributes no pixel to it either way.
        // seq_item has ALREADY pulsed at S_FW, so the pick register's item
        // count is unchanged -- it counts faces EXAMINED, and this face
        // still was.
        begin
        if (f_clip) begin
          // THE CLIPPER TAKES OVER, and only for a face that was being
          // DROPPED -- everything in the else below is the fast path,
          // untouched to the bit. A clipped face's screen rows are not
          // known until its triangles come out, so its bin entry is
          // deferred to S_CLDN and accumulated in cl_lo/cl_hi.
          cl_on <= 1'b1;                 // (cb_r was taken at S_FT)
          cl_lo <= 9'd511; cl_hi <= 9'd0;
          st <= S_CLC;
        end else begin
        // THE OBJECT'S SPAN IS MEASURED HERE, before the band reject --
        // it must cover every band the object reaches, not just this one,
        // or band 0 would record a span only band 0 can see and every
        // later band would skip the object wrongly.
        if (!f_reject) begin
          if (fy_lo < o_lo) o_lo <= fy_lo;
          if (fy_hi > o_hi) o_hi <= fy_hi;
        end
        if (first_pass && fb_ok) begin      // one entry per face examined
          fb_we <= 1'b1;
          fb_wa <= fb_base + {2'd0, fi};
          fb_wd <= f_reject ? {9'd511, 9'd0} : {fy_lo, fy_hi};
        end
        // AND BAND 0 REJECTS TOO. It used to carry `!first_pass`, so band
        // 0 set up and submitted every accepted face on the whole screen
        // and the rasterizer discarded the ones outside its band -- the
        // duplicated setup the meter finally located. Band 0 must WALK
        // everything (to fill the bins) but it need not DRAW everything.
        if (f_reject || fy_hi < tile_y0 || fy_lo > tile_y1)
          st <= S_FN;
        else begin
          tx0 <= {{19{ax[16]}}, ax}; ty0 <= {{19{ay[16]}}, ay};
          tx1 <= {{19{bx[16]}}, bx}; ty1 <= {{19{by[16]}}, by};
          tx2 <= {{19{gx[16]}}, gx}; ty2 <= {{19{gy[16]}}, gy};
          tz0 <= pa[15:0];
          far <= far_w;
          fza <= {1'b0, pa[15:0]}; fzb <= {1'b0, pb[15:0]};
          fzc <= {1'b0, pc[15:0]};     // (cb_r was taken at S_FT)
          if (!gour || far_w) begin   // flat, or far enough that flat is
            tcxr <= 26'sd0; tcyr <= 26'sd0;   // indistinguishable
            tcxg <= 26'sd0; tcyg <= 26'sd0;
            tcxb <= 26'sd0; tcyb <= 26'sd0;
          end
          if (0) begin
            tcxg <= 26'sd0; tcyg <= 26'sd0;
            tcxb <= 26'sd0; tcyb <= 26'sd0;
          end
          e01x <= bx - ax; e01y <= by - ay;
          e02x <= gx - ax; e02y <= gy - ay;
          farea <= area;
          cw_r <= pc[65:49];
          lc_r <= pc[71:66];    // ...and its LEVEL (spec.OBJ_LIT)
          st <= texf ? S_TW : S_GZ;
        end
        end
        end
      S_TW: begin                     // corner c's uv word lands HERE for
        // ...unless the clipper supplied it: a clipped vertex's attributes
        // are INTERPOLATED, not in DMEM, and were written at S_CLFC
        if (!cl_on) cc_r <= vword;            // (2 states after
        wp_a <= wnrm(aw, wsh);        // S_FLB); normalize all three w
        wp_b <= wnrm(bw, wsh);
        wp_c <= wnrm(cw_r, wsh);
        st <= S_TM;
      end
      S_TM: begin                     // the affine-legal trio per corner
        ua17 <= mua;  va17 <= mva;
        ub17 <= mub;  vb17 <= mvb;
        uc17 <= muc;  vc17 <= mvc;
        tc0 <= {mua, mva, {5'd0, wp_a}};
        st <= S_GZ;
      end
      S_GZ:                           // gradient setup: dzdx pass first
        if (farea == 0) begin
          t_tex <= texf; t_tinton <= tintf | otintf;
          t_otint <= otintf; t_tint <= otintf ? otintv : tint;
          t_oid <= oidv;
          t_span <= spanf;
          t_blend <= blendf; t_alpha <= f_alpha; t_page <= pagef;
          t_add <= f_add;
                                      // area 0 still samples corner a's
                                      // texel (the law's degenerate case)
          tzx <= 26'sd0; tzy <= 26'sd0;
          tcxr <= 26'sd0; tcyr <= 26'sd0;
          tcxg <= 26'sd0; tcyg <= 26'sd0;
          tcxb <= 26'sd0; tcyb <= 26'sd0;
          st <= S_FE;
        end else begin
          if (!cl_on) cc_r <= vword;            // vertex c's word lands here
          t_tex <= texf; t_tinton <= tintf | otintf;
          t_otint <= otintf; t_tint <= otintf ? otintv : tint;
          t_oid <= oidv;
          t_span <= spanf;
          t_blend <= blendf; t_alpha <= f_alpha; t_page <= pagef;
          t_add <= f_add;
          gph <= 1'b0;
          gch <= 2'd0;
          dvs <= aabs[35:0];
          st <= S_GN;
        end
      S_GP: begin                     // dividend = |gnum| << ZFP (44-bit):
        rem <= {18'd0, gabs[35:17]};  // head bits [43:25]
        low <= {gabs[16:0], 8'd0};    // bits [24:0]
        if ({18'd0, gabs[35:17]} >= {1'b0, dvs}) begin
          q <= 26'd16777216;          // steeper than ZGRAD_MAX: clamp
          st <= S_GQ;
        end else begin q <= 0; k <= 5'd12; st <= S_GD; end
      end
      S_GD: if (k == 0) begin
        rem <= rsub[37] ? rsh : rsub[36:0];
        q <= {q[24:0], ~rsub[37]};
        low <= {low[23:0], 1'b0};
        st <= S_GQ;
      end else begin
        rem <= rem4[36:0];
        q   <= {q[23:0], dig};
        low <= {low[22:0], 2'b0};
        k <= k - 1'b1;
      end
      S_GN:  begin gm_a <= gp_a; gm_b <= gp_b; st <= S_GN2; end
      S_GN2: begin gnum_r <= gnum; st <= S_GP; end
      S_GQ: begin                     // one quotient done: store by
        case ({gch, gph})             // channel and phase, then loop --
          3'b000: tzx  <= qfin;       // z, r, g, b; d/dx then d/dy each
          3'b001: tzy  <= qfin;
          3'b010: tcxr <= qfin;
          3'b011: tcyr <= qfin;
          3'b100: tcxg <= qfin;
          3'b101: tcyg <= qfin;
          3'b110: tcxb <= qfin;
          default: tcyb <= qfin;
        endcase
        if (!gph) begin gph <= 1'b1; st <= S_GN; end
        else if (((gour && !far) || texf) && gch != 2'd3) begin
          gch <= gch + 1'b1; gph <= 1'b0; st <= S_GN;
        end else st <= S_FE;
      end
      S_FE: if (tri_rdy) begin
        tri_go <= 1'b1;
        st <= cl_on ? S_CLNX : S_FN;   // a clipped face emits a FAN
      end
      S_FN: begin
        fi <= fi + 1'b1;
        fb_ra <= fb_base + {2'd0, fi} + 12'd1;   // NEXT face, registered

        faddr <= faddr + 2'd2;
        rd_addr <= faddr + 2'd2;
        st <= ({22'd0, fi} + 1'b1 == nf) ? S_ONXT : S_FW;
      end

      // ================= THE CLIPPER, state by state ===================
      S_CLC: begin                    // vertex c's attribute word lands here
        cc_r <= vword;
        cl_vi <= 3'd0;
        st <= S_CLXA;
      end
      // ---- recover view space by re-running the rotate chain -----------
      S_CLXA: begin                   // vertex cl_vi of this face, again
        rd_addr <= vbase + {3'd0, cl_src, 1'b0} + {4'd0, cl_src};
        vi3 <= 2'd0;
        cl_xf <= 1'b1;
        st <= S_VW;                   // ...and S_R2C hands it to S_CLST
      end
      S_CLST: begin
        clx[{1'b0, cl_vi}] <= vx;
        cly[{1'b0, cl_vi}] <= vy;
        clz[{1'b0, cl_vi}] <= vz;
        cla[{1'b0, cl_vi}] <= cl_att;
        if (cl_vi == 3'd2) begin      // bank A holds the whole triangle
          cl_xf <= 1'b0; cl_bk <= 1'b0;
          cl_n <= 4'd3; cl_pl <= 3'd0;
          st <= S_CLP;
        end else begin
          cl_vi <= cl_vi + 1'b1;
          st <= S_CLXA;
        end
      end
      // ---- Sutherland-Hodgman, one plane at a time ---------------------
      S_CLP:                          // the law tests this BEFORE each
        if (cl_n < 4'd3) st <= S_CLDN;          // plane, so an empty
        else begin                              // polygon short-circuits
          cl_di <= 3'd0; cl_m <= 4'd0;
          cl_ri <= {cl_bk, 3'd0};               // vertex 0, ready next state
          st <= S_CLD1;
        end
      S_CLD1: begin                   // a*vx + b*vy + c*vz + d, in two
        cl_pz <= cl_pz_w;             // beats so the shift chain is not
        cl_pxy <= cl_xy_w;            // in series with the adds
        st <= S_CLD2;
      end
      S_CLD2: begin
        cld[cl_di] <= cl_dsum;
        if ({1'b0, cl_di} + 1'b1 == cl_n) begin cl_i <= 3'd0; st <= S_CLE0; end
        else begin
          cl_di <= cl_di + 1'b1;
          cl_ri <= {cl_bk, 3'd0} | {1'b0, cl_di + 3'd1};
          st <= S_CLD1;
        end
      end
      // the edge's two ends, read one at a time into the holders
      S_CLE0: begin cl_ri <= cl_ai; st <= S_CLE1; end
      S_CLE1: begin
        ha_x <= rd_x; ha_y <= rd_y; ha_z <= rd_z; ha_a <= rd_a;
        cl_ri <= cl_bi; st <= S_CLE2;
      end
      S_CLE2: begin
        hb_x <= rd_x; hb_y <= rd_y; hb_z <= rd_z; hb_a <= rd_a;
        st <= S_CLE;
      end
      S_CLE: begin
        // the law emits vertex a when it is inside, THEN the crossing when
        // the edge changes side -- both can happen on one edge, in that
        // order, which is why cl_m may advance twice
        if (!cld[cl_i][49]) begin
          clx[cl_ob | {1'b0, cl_m[2:0]}] <= ha_x;
          cly[cl_ob | {1'b0, cl_m[2:0]}] <= ha_y;
          clz[cl_ob | {1'b0, cl_m[2:0]}] <= ha_z;
          cla[cl_ob | {1'b0, cl_m[2:0]}] <= ha_a;
          cl_m <= cl_m + 1'b1;
        end
        if (cld[cl_i][49] != cld[cl_nx][49]) st <= S_CLX0;
        else st <= S_CLN;
      end
      S_CLX0: begin                   // one crossing: |da|, |den|, signs
        cl_dam <= cld[cl_i][49] ? (~cld[cl_i][49:0] + 1'b1) : cld[cl_i][49:0];
        cl_den <= cl_dsub[50] ? (~cl_dsub[50:0] + 1'b1) : cl_dsub[50:0];
        cl_dasg <= cl_dsub[50] ^ cld[cl_i][49];
        cl_k <= 3'd0;
        st <= S_CLM0;
      end
      S_CLM0: begin                   // coordinate cl_k: |vb-va| * |da|
        cl_va  <= cl_ca;
        cl_mul <= cl_dmag;
        cl_sgn <= cl_dasg ^ cl_delta[32];
        st <= S_CLM;
      end
      S_CLM: begin                    // one beat: the product, mod 2^82
        cl_mac <= cl_mul * cl_dam;
        st <= S_CLV0;
      end
      S_CLV0: begin                   // THE DIVIDE SKIPS 49 BEATS. |q| can
        cl_rem <= {3'd0, cl_mac[81:33]};   // never exceed |vb-va| < 2^33,
        cl_low <= cl_mac[32:0];            // so the top 49 quotient bits
        cl_q   <= 33'd0;                   // are provably zero and the
        cl_ck  <= 6'd32;                   // preload is exact, not a guess
        st <= S_CLDV;
      end
      S_CLDV: begin                   // restoring divide, truncating --
        cl_q   <= {cl_q[31:0], ~cl_rsub[52]};       // spec.tdiv's magnitude
        cl_rem <= cl_rsub[52] ? cl_rsh : cl_rsub[51:0];
        cl_low <= {cl_low[31:0], 1'b0};
        if (cl_ck == 6'd0) st <= S_CLXS;
        else cl_ck <= cl_ck - 1'b1;
      end
      S_CLXS: begin                   // va + q, into the output vertex
        case (cl_k)
          3'd0: clx[cl_ob | {1'b0, cl_m[2:0]}] <= cl_res;
          3'd1: cly[cl_ob | {1'b0, cl_m[2:0]}] <= cl_res;
          3'd2: clz[cl_ob | {1'b0, cl_m[2:0]}] <= cl_res;
          3'd3: if (texf) cla[cl_ob | {1'b0, cl_m[2:0]}][4:0]   <= cl_res[4:0];
                else      cla[cl_ob | {1'b0, cl_m[2:0]}][23:16] <= cl_res[7:0];
          3'd4: if (texf) cla[cl_ob | {1'b0, cl_m[2:0]}][12:8]  <= cl_res[4:0];
                else      cla[cl_ob | {1'b0, cl_m[2:0]}][15:8]  <= cl_res[7:0];
          default:        cla[cl_ob | {1'b0, cl_m[2:0]}][7:0]   <= cl_res[7:0];
        endcase
        if ({1'b0, cl_k} + 1'b1 == {1'b0, cl_nk}) begin
          cl_m <= cl_m + 1'b1; st <= S_CLN;
        end else begin
          cl_k <= cl_k + 1'b1; st <= S_CLM0;
        end
      end
      S_CLN:                          // next edge, or next plane
        if ({1'b0, cl_i} + 1'b1 == cl_n) begin
          cl_n <= cl_m; cl_bk <= ~cl_bk;
          if (cl_pl == 3'd4) begin
            cl_vi <= 3'd0;
            st <= (cl_m < 4'd3) ? S_CLDN : S_CLPR0;
          end else begin
            cl_pl <= cl_pl + 1'b1;
            st <= S_CLP;
          end
        end else begin
          cl_i <= cl_i + 1'b1; st <= S_CLE0;
        end
      // ---- project the survivors through the ordinary chain ------------
      S_CLPR0: begin                  // cl_bk was flipped by S_CLN, so the
        cl_ri <= {cl_bk, 3'd0} | {1'b0, cl_vi};   // last plane's OUTPUT is
        st <= S_CLPR;                             // the input bank now
      end
      S_CLPR: begin
        vx <= rd_x; vy <= rd_y; vz <= rd_z;
        cl_prj <= 1'b1;
        st <= S_NEAR;
      end
      S_CLPN: begin
        cl_vi <= cl_vi + 1'b1;
        if ({1'b0, cl_vi} + 1'b1 == cl_n) begin
          cl_prj <= 1'b0; cl_t <= 3'd0; st <= S_CLFA;
        end else st <= S_CLPR0;
      end
      // ---- fan: v0 with each adjacent pair, through the setup path -----
      // the attributes come out of the CLIPPER, not DMEM -- read one a
      // state, through the same single port
      S_CLFA: begin
        vc_ra <= CL_SLOT[11:0];
        cl_ri <= {cl_bk, 3'd0};
        st <= S_CLFB;
      end
      S_CLFB: begin
        vc_ra <= CL_SLOT[11:0] + {9'd0, cl_t} + 12'd1;
        ca_r <= rd_a;
        cl_ri <= {cl_bk, 3'd0} | {1'b0, (cl_t + 3'd1)};
        st <= S_CLFC;
      end
      S_CLFC: begin
        pa <= vc_q;
        vc_ra <= CL_SLOT[11:0] + {9'd0, cl_t} + 12'd2;
        cb_r <= rd_a;
        cl_ri <= {cl_bk, 3'd0} | {1'b0, (cl_t + 3'd2)};
        st <= S_CLFD;
      end
      S_CLFD: begin pb <= vc_q; cc_r <= rd_a; st <= S_CLFT; end
      S_CLFT: begin pc <= vc_q; st <= S_CLFT2; end   // latch the corner
      S_CLFT2:                        // pc = the third corner, registered
        // the law culls and area-tests each FANNED PIECE, not the parent
        if (cull_box || (oflags[0] && (area[36] || area == 0)))
          st <= S_CLNX;
        else begin
          if (fy_lo < o_lo) o_lo <= fy_lo;
          if (fy_hi > o_hi) o_hi <= fy_hi;
          if (fy_lo < cl_lo) cl_lo <= fy_lo;
          if (fy_hi > cl_hi) cl_hi <= fy_hi;
          if (fy_hi < tile_y0 || fy_lo > tile_y1) st <= S_CLNX;
          else begin
            tx0 <= {{19{ax[16]}}, ax}; ty0 <= {{19{ay[16]}}, ay};
            tx1 <= {{19{bx[16]}}, bx}; ty1 <= {{19{by[16]}}, by};
            tx2 <= {{19{gx[16]}}, gx}; ty2 <= {{19{gy[16]}}, gy};
            tz0 <= pa[15:0];
            far <= far_w;
            fza <= {1'b0, pa[15:0]}; fzb <= {1'b0, pb[15:0]};
            fzc <= {1'b0, pc[15:0]};
            if (!gour || far_w) begin
              tcxr <= 26'sd0; tcyr <= 26'sd0;
              tcxg <= 26'sd0; tcyg <= 26'sd0;
              tcxb <= 26'sd0; tcyb <= 26'sd0;
            end
            e01x <= bx - ax; e01y <= by - ay;
            e02x <= gx - ax; e02y <= gy - ay;
            farea <= area;
            cw_r <= pc[65:49];
            lc_r <= pc[71:66];    // ...and its LEVEL (spec.OBJ_LIT)
            st <= texf ? S_TW : S_GZ;
          end
        end
      S_CLNX:                         // cl_n - 2 triangles in the fan
        if ({1'b0, cl_t} + 4'd1 == cl_n - 4'd2) st <= S_CLDN;
        else begin cl_t <= cl_t + 1'b1; st <= S_CLFA; end
      S_CLDN: begin
        // ONE bin entry per face, covering every triangle the clip
        // produced: a later band must not skip a face whose clipped
        // geometry reaches it, and must skip one whose does not
        if (first_pass && fb_ok) begin
          fb_we <= 1'b1;
          fb_wa <= fb_base + {2'd0, fi};
          fb_wd <= (cl_lo > cl_hi) ? {9'd511, 9'd0} : {cl_lo, cl_hi};
        end
        cl_on <= 1'b0;
        st <= S_FN;
      end

      S_ONXT: begin
        // Band 0 publishes what it measured. Later bands must NOT write:
        // they only saw the faces inside their own band, so re-storing
        // would narrow the span and make band 2 skip what band 1 drew.
        if (first_pass) obin[o[5:0]] <= {o_lo, o_hi};
        // the running base advances ONLY for an object band 0 really
        // cached: a rejected or overflowed one leaves vb_ok low above,
        // so its slots are never claimed and the next object gets them
        if (first_pass && vb_ok) vb_base <= vb_base + {1'd0, nv[10:0]};
        if (first_pass && fb_ok) fb_base <= fb_base + {1'd0, nf[10:0]};
        o <= o + 1'b1; ci <= 0;
        rd_cart <= 1'b0;                  // the next object's six words are DMEM's
        obase <= obase + OL_STRIDE[13:0];
        rd_addr <= obase + OL_STRIDE[13:0];
        st <= (o + 1'b1 == n_ol) ? S_FIN : S_OBJ_W;
      end
      S_FIN: begin done <= 1'b1; st <= S_IDLE; end
      default: st <= S_IDLE;
    endcase
  end

endmodule
`default_nettype wire
