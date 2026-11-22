// zmesh.v -- THE CART MESH'S STORE (spec.OBJ_CART; frontier 20).
//
// A cart mesh is three streams in the cart: 16-bit vertices, packed face
// indices, 5:5:5 face colours. The loader (zeta_top, at the movers'
// instant) bursts each admitted object's streams HERE, once a frame, and
// the sequencer then reads that object's mesh through the port it always
// had: with rd_cart up, rd_addr is not a DMEM address but a word of
//
//     [ nv, nf, 3 words a vertex ..., 2 words a face ... ]
//
// for object rd_obj -- the very layout a DMEM mesh has -- and this module
// answers in the same two states: a vertex half sign-extended and shifted,
// a face's index word, its colour widened to the 24 bits a flat face has
// always carried. So nothing in the walk, the bins, the vertex cache or
// the clipper knows the difference.
//
// The store is DERIVED every frame from DMEM and the cart; it is not
// machine state. Its size is law (spec.CM_VMAX, CM_FMAX).
`default_nettype none

module zmesh (
    input  wire        clk,
    // ---- the loader's side ------------------------------------------------
    input  wire        ld_new,      // pulse: a new frame's walk (the store is empty)
    input  wire        ld_obj,      // pulse: object ld_o's verdict
    input  wire [5:0]  ld_o,
    input  wire        ld_ok,       // admitted -- its place is the cursors'
    input  wire [8:0]  ld_nv,       // 0..256
    input  wire [9:0]  ld_nf,       // 0..512
    input  wire [3:0]  ld_sh,
    input  wire [1:0]  ld_sel,      // the stream arriving: 1 vertices, 2 faces, 3 colours
    input  wire        ld_we,       // one cart word of it (never on consecutive clocks)
    input  wire [31:0] ld_word,
    // ---- the sequencer's side ---------------------------------------------
    input  wire [5:0]  rd_obj,
    input  wire [13:0] rd_addr,
    output wire        cm_ok,
    output wire [31:0] rd_data
);
  `include "params.vh"

  // THE SHAPES ARE THE BLOCK RAM'S. A Cyclone V block is 2,048 x 5 bits, and
  // every memory here is exactly 2,048 deep: a vertex is ONE 48-bit word
  // (ten blocks), a face's three indices 25 bits (five), its colour 15
  // (three). The first cut kept vertices as 4,610 halves and faces 2,562
  // deep, and those depths cost 39 blocks -- 320 of the device's 308.
  //   A face index is 8 bits here because MESH_NV_MAX is 256; an index the
  // cart wrote past that is one the law skips the face for (a >= nv), so
  // the 25th bit remembers it and the word read back says 1023.
  (* ramstyle = "M10K, no_rw_check" *) reg [47:0] vmem [0:CM_VMAX - 1];
  (* ramstyle = "M10K, no_rw_check" *) reg [24:0] fmem [0:CM_FMAX - 1];
  (* ramstyle = "M10K, no_rw_check" *) reg [14:0] cmem [0:CM_FMAX - 1];

  // per object: {ok, sh[3:0], nv3[9:0], nv[8:0], nf[9:0], vb[10:0], fb[10:0]}
  (* ramstyle = "MLAB, no_rw_check" *) reg [55:0] tab [0:63];
  reg [11:0] v_top, f_top;                // the store's fill (one bit past, for the sums)
  reg [10:0] v_w, f_w, c_w;               // each stream's cursor
  reg [10:0] c_end;                       // ...and where this object's colours stop
  reg        hi_p;                        // a word's high half, owed next clock
  reg        hi_c;                        // ...to the colours rather than the vertices
  reg [15:0] hi_d;
  reg [1:0]  vph;                         // which of x, y, z the next half is
  reg [31:0] vxy;
  wire [9:0] ld_nv3 = {ld_nv, 1'b0} + {1'b0, ld_nv};

  // ONE WRITE PORT A MEMORY, said as one statement each. (Written from two
  // places in one block -- a word's low half and, a clock later, its high
  // -- Quartus built two of these out of registers: 112,000 of them, 541%
  // of the device. The two halves never share a clock.)
  wire        v_lo = ld_we && ld_sel == 2'd1;
  wire        c_lo = ld_we && ld_sel == 2'd3;
  wire        v_hf = v_lo || (hi_p && !hi_c);          // a vertex half this clock
  wire        c_hf = c_lo || (hi_p && hi_c);           // a colour
  wire        f_we = ld_we && ld_sel == 2'd2;
  wire [15:0] hw   = hi_p ? hi_d : ld_word[15:0];
  wire        v_we = v_hf && vph == 2'd2;              // its z: the vertex is whole
  wire        c_we = c_hf && c_w != c_end;             // (an odd count's pad is not one)
  wire        f_bad = |{ld_word[29:28], ld_word[19:18], ld_word[9:8]};
  always @(posedge clk) if (v_we) vmem[v_w] <= {hw, vxy};
  always @(posedge clk) if (c_we) cmem[c_w] <= hw[14:0];
  always @(posedge clk) if (f_we) fmem[f_w] <= {f_bad, ld_word[27:20], ld_word[17:10], ld_word[7:0]};

  always @(posedge clk) begin
    hi_p <= v_lo || c_lo;
    hi_c <= c_lo;
    if (v_lo || c_lo) hi_d <= ld_word[31:16];
    if (ld_new) begin v_top <= 12'd0; f_top <= 12'd0; end
    if (ld_obj) begin
      tab[ld_o] <= {ld_ok, ld_sh, ld_nv3, ld_nv, ld_nf, v_top[10:0], f_top[10:0]};
      if (ld_ok) begin
        v_w <= v_top[10:0]; f_w <= f_top[10:0]; c_w <= f_top[10:0];
        c_end <= f_top[10:0] + {1'b0, ld_nf};
        vph <= 2'd0;
        v_top <= v_top + {3'd0, ld_nv};
        f_top <= f_top + {2'd0, ld_nf};
      end
    end
    if (v_hf) begin
      if (vph == 2'd0) vxy[15:0] <= hw;
      if (vph == 2'd1) vxy[31:16] <= hw;
      vph <= (vph == 2'd2) ? 2'd0 : vph + 2'd1;
    end
    if (v_we) v_w <= v_w + 11'd1;
    if (c_we) c_w <= c_w + 11'd1;
    if (f_we) f_w <= f_w + 11'd1;
  end

  // ---- the read: address decoded this clock, the RAMs answer the next ----
  wire [55:0] te    = tab[rd_obj];
  wire        t_ok  = te[55];
  wire [3:0]  t_sh  = te[54:51];
  wire [9:0]  t_nv3 = te[50:41];
  wire [8:0]  t_nv  = te[40:32];
  wire [9:0]  t_nf  = te[31:22];
  wire [10:0] t_vb  = te[21:11];
  wire [10:0] t_fb  = te[10:0];
  assign cm_ok = t_ok;

  wire [13:0] k   = rd_addr - 14'd2;                  // word within the vertices
  wire        inv = (rd_addr >= 14'd2) && (k < {4'd0, t_nv3});
  wire [13:0] fa  = k - {4'd0, t_nv3};                // word within the faces
  // which vertex, which of its three: k / 3 as (k * 683) >> 11, exact below
  // 2,048 (k is under 768) -- the machine has no divider to spare here
  wire [20:0] k683 = {k[9:0], 9'd0} + {2'd0, k[9:0], 7'd0} + {4'd0, k[9:0], 5'd0}
                   + {6'd0, k[9:0], 3'd0} + {8'd0, k[9:0], 1'd0} + {9'd0, k[9:0]};
  wire [9:0]  vi  = k683[20:11];
  wire [1:0]  vcp = k[1:0] - {vi[0], 1'b0} - vi[1:0];       // k - 3 vi, mod 4
  wire [10:0] v_ra = t_vb + {1'b0, vi};
  wire [10:0] f_ra = t_fb + fa[11:1];
  reg  [47:0] vq;
  reg  [24:0] fq;
  reg  [14:0] cq;
  reg  [1:0]  q_hdr;                                  // 1: nv, 2: nf
  reg         q_v, q_odd;
  reg  [1:0]  q_c;
  reg  [3:0]  q_sh;
  reg  [8:0]  q_nv;
  reg  [9:0]  q_nf;
  always @(posedge clk) vq <= vmem[v_ra];
  always @(posedge clk) fq <= fmem[f_ra];
  always @(posedge clk) cq <= cmem[f_ra];
  always @(posedge clk) begin
    q_hdr <= (rd_addr == 14'd0) ? 2'd1 : (rd_addr == 14'd1) ? 2'd2 : 2'd0;
    q_v <= inv; q_odd <= fa[0]; q_c <= vcp;
    q_sh <= t_sh; q_nv <= t_nv; q_nf <= t_nf;
  end
  wire [15:0] vh = (q_c == 2'd0) ? vq[15:0] : (q_c == 2'd1) ? vq[31:16] : vq[47:32];
  wire signed [31:0] vext = {{16{vh[15]}}, vh};
  wire [31:0] fword = fq[24] ? 32'h3FFFFFFF
                             : {2'd0, 2'd0, fq[23:16], 2'd0, fq[15:8], 2'd0, fq[7:0]};
  assign rd_data = (q_hdr == 2'd1) ? {23'd0, q_nv} :
                   (q_hdr == 2'd2) ? {22'd0, q_nf} :
                   q_v             ? (vext <<< q_sh) :
                   q_odd           ? {8'd0, cq[14:10], 3'd0, cq[9:5], 3'd0, cq[4:0], 3'd0}
                                   : fword;
endmodule
`default_nettype wire
