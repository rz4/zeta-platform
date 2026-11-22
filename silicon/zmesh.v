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

  localparam VH = CM_VMAX * 3 + 2;        // vertex HALVES (+2: an odd stream's pad)
  localparam FN = CM_FMAX + 2;

  (* ramstyle = "M10K, no_rw_check" *) reg [15:0] vmem [0:VH - 1];
  (* ramstyle = "M10K, no_rw_check" *) reg [29:0] fmem [0:FN - 1];
  (* ramstyle = "M10K, no_rw_check" *) reg [14:0] cmem [0:FN - 1];

  // per object: {ok, sh[3:0], nv3[9:0], nv[8:0], nf[9:0], vb[12:0], fb[11:0]}
  (* ramstyle = "MLAB, no_rw_check" *) reg [58:0] tab [0:63];
  reg [12:0] v_top, v_w;                  // the store's fill, and the stream's cursor
  reg [11:0] f_top, f_w, c_w;
  reg        hi_p;                        // a word's high half, owed next clock
  reg        hi_c;                        // ...to the colours rather than the vertices
  reg [15:0] hi_d;
  wire [9:0] ld_nv3 = {ld_nv, 1'b0} + {1'b0, ld_nv};

  always @(posedge clk) begin
    hi_p <= 1'b0;
    if (ld_new) begin v_top <= 13'd0; f_top <= 12'd0; end
    if (ld_obj) begin
      tab[ld_o] <= {ld_ok, ld_sh, ld_nv3, ld_nv, ld_nf, v_top, f_top};
      if (ld_ok) begin
        v_w <= v_top; f_w <= f_top; c_w <= f_top;
        v_top <= v_top + {3'd0, ld_nv3};
        f_top <= f_top + {2'd0, ld_nf};
      end
    end
    if (ld_we) case (ld_sel)
      2'd1: begin vmem[v_w] <= ld_word[15:0]; v_w <= v_w + 13'd1;
                  hi_p <= 1'b1; hi_c <= 1'b0; hi_d <= ld_word[31:16]; end
      2'd2: begin fmem[f_w] <= ld_word[29:0]; f_w <= f_w + 12'd1; end
      2'd3: begin cmem[c_w] <= ld_word[14:0]; c_w <= c_w + 12'd1;
                  hi_p <= 1'b1; hi_c <= 1'b1; hi_d <= ld_word[31:16]; end
      default: ;
    endcase
    if (hi_p) begin
      if (hi_c) begin cmem[c_w] <= hi_d[14:0]; c_w <= c_w + 12'd1; end
      else      begin vmem[v_w] <= hi_d;       v_w <= v_w + 13'd1; end
    end
  end

  // ---- the read: address decoded this clock, the RAMs answer the next ----
  wire [58:0] te    = tab[rd_obj];
  wire        t_ok  = te[58];
  wire [3:0]  t_sh  = te[57:54];
  wire [9:0]  t_nv3 = te[53:44];
  wire [8:0]  t_nv  = te[43:35];
  wire [9:0]  t_nf  = te[34:25];
  wire [12:0] t_vb  = te[24:12];
  wire [11:0] t_fb  = te[11:0];
  assign cm_ok = t_ok;

  wire [13:0] k   = rd_addr - 14'd2;                  // word within the vertices
  wire        inv = (rd_addr >= 14'd2) && (k < {4'd0, t_nv3});
  wire [13:0] fa  = k - {4'd0, t_nv3};                // word within the faces
  reg  [15:0] vq;
  reg  [29:0] fq;
  reg  [14:0] cq;
  reg  [1:0]  q_hdr;                                  // 1: nv, 2: nf
  reg         q_v, q_odd;
  reg  [3:0]  q_sh;
  reg  [8:0]  q_nv;
  reg  [9:0]  q_nf;
  always @(posedge clk) begin
    vq <= vmem[t_vb + k[12:0]];
    fq <= fmem[t_fb + fa[12:1]];
    cq <= cmem[t_fb + fa[12:1]];
    q_hdr <= (rd_addr == 14'd0) ? 2'd1 : (rd_addr == 14'd1) ? 2'd2 : 2'd0;
    q_v <= inv; q_odd <= fa[0];
    q_sh <= t_sh; q_nv <= t_nv; q_nf <= t_nf;
  end
  wire signed [31:0] vext = {{16{vq[15]}}, vq};
  assign rd_data = (q_hdr == 2'd1) ? {23'd0, q_nv} :
                   (q_hdr == 2'd2) ? {22'd0, q_nf} :
                   q_v             ? (vext <<< q_sh) :
                   q_odd           ? {8'd0, cq[14:10], 3'd0, cq[9:5], 3'd0, cq[4:0], 3'd0}
                                   : {2'd0, fq};
endmodule
`default_nettype wire
