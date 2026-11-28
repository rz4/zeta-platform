// zeta_top.v -- the whole console: zvm + zgpu + framebuffer, sequenced per
// spec.py's frame contract. One `start` pulse = one frame:
//   latch frame counter and pad into DMEM -> run the VM -> paint the frame.
// A trapped VM (a cart bug) skips straight to painting, frozen, exactly as
// vm.py's frame() returns early -- the last good state stays on screen.
`default_nettype none

module zeta_top (
    input  wire        clk,
    input  wire        rst_n,          // the machine: CRAM and its boot
                                       // path stay alive through loading
    input  wire        core_en,        // the CONSOLE: held off until the
                                       // cart is complete. Split because
                                       // the segment arrives while the
                                       // console is still held, and the
                                       // CRAM writer must be awake for it
                                       // (build 29: it was not, so the
                                       // segment never landed and neither
                                       // paged object rendered)
    input  wire        start,
    input  wire [15:0] pad,
    // boot: stream the cart in before the first frame
    input  wire        boot_we,
    input  wire  [1:0] boot_kind,    // 0 IMEM, 1 DMEM, 2 CRAM segment
    input  wire        boot_done,   // the whole cart has arrived:
                                    // partial seg banks may flush
    input  wire [22:0] boot_addr,
    input  wire [31:0] boot_data,
    output reg         frame_done,   // 1-cycle pulse
    output wire        trapped,
    // THE TAPE'S TAP (pocket/zeta_tape.v): the pad word of this frame, at
    // the instant it is written to REG_PAD -- what a replay must feed back
    output wire        pad_stb,
    output wire [15:0] pad_word,
    output reg         busy,
    output wire        boot_busy,      // hold the loader: a segment word
                                       // is still going into CRAM
    // THE PROGRAM'S SRAM (frontier 19, silicon/zimem.v): the console is its
    // master; a guest (the Pocket's tape recorder) borrows it through g_*
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
    // sound: one sample per tick, from registers latched each frame
    input  wire        snd_tick,
    // the card port: a behavioral model in simulation, an APF adapter on
    // the Pocket -- the seam that keeps SD inside the cross
    output wire        sd_req,
    output wire        sd_save,      // this request writes the card
    output reg         sd_sw_we,     // ...and these carry the words to
    output reg  [9:0]  sd_sw_a,      // save, read out of DMEM at the
    output reg  [31:0] sd_sw_d,      // LATCH, before the command goes
    output wire [15:0] sd_slot,
    output wire [31:0] sd_off,
    output wire [12:0] sd_len,
    input  wire        sd_we,
    input  wire [31:0] sd_data,
    input  wire        sd_done,
    input  wire [31:0] card_diag0,   // the card's own counters, written
    input  wire [31:0] card_diag1,   // into DMEM each frame (CARD_DIAG)
    input  wire [31:0] card_diag2,
    output wire        snd_busy,   // events still pending this sample
    output wire signed [15:0] snd_sample,
    // framebuffer line access (the CRAM front buffer): request a line,
    // wait for line_rdy, then read pixels at {line parity, x}; px_rgb is
    // REGISTERED (valid the cycle after px_addr)
    input  wire        line_req,
    input  wire [8:0]  line_no,
    output wire        line_rdy,
    input  wire [9:0]  px_addr,
    output wire [23:0] px_rgb,
    input  wire        swap_gate,    // level: buffer flip allowed (sim: 1)
    output wire        swap_pending, // a frame kick must wait this out
    // the CRAM chip pair
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
    output wire c1_ub_n, c1_lb_n
,
    // GRADING (spec.GRADE_SRC): the video head's curve, written a level
    // at a time once per frame. The table lives THERE and not here,
    // because 32 words of registers on a bus is 1,024 flops and one
    // MLAB read at pixel rate is not.
    output reg         gr_on,    // ...and whether the curve is live
    output reg         gr_we,
    output reg  [4:0]  gr_a,
    output reg  [23:0] gr_d,
    output wire [415:0] co_flat,  // the compositor block,
                                  // for the video head
    output wire [287:0] meter     // METER: {evfire,evload,skp,blkd,seq,stall,idle,walk,clr}
);
  `include "params.vh"

  localparam I_IDLE = 6'd0, I_WF = 6'd1, I_WP = 6'd2, I_VK = 6'd3,
             I_VW = 6'd4, I_GK = 6'd5, I_GW = 6'd6, I_AUW = 6'd7,
             I_AUC = 6'd8, I_FIN = 6'd9,
             // the mover: read the four request cells, then stream the
             // segment into DMEM, all before the paint starts
             I_DRD = 6'd10, I_DCK = 6'd11, I_DBURST = 6'd12,
             I_DWAIT = 6'd13, I_DCLR = 6'd14, I_PW = 6'd15,
             // the texture page loader: 512 words -> 1024 texels,
             // after the mover, before the paint (spec.TEX_SRC)
             I_TXC = 6'd16, I_TXC2 = 6'd17, I_TXR = 6'd18,
             I_TXW = 6'd19, I_TXD = 6'd20, I_TXD2 = 6'd21,
             // the wave page loader: WAV_WORDS words, latched with the
             // audio registers so page and pitch land in one instant
             I_WVC = 6'd22, I_WVC2 = 6'd23, I_WVR = 6'd24,
             I_WVW = 6'd25, I_WVD = 6'd26,
             // the card: evaluated at the mover's own instant, then
             // copied out of staging when the legislated frame arrives
             I_CARD = 6'd27, I_CGO = 6'd28, I_CCLR = 6'd29,
             I_CRD = 6'd30, I_CWR = 6'd31, I_CWR2 = 6'd32,
             I_CDG = 6'd33, I_CDG2 = 6'd34, I_CDG3 = 6'd35,
             I_CDG4 = 6'd36, I_CSV = 6'd37, I_CSV2 = 6'd38,
             I_OVL = 6'd39, I_OCLR = 6'd40,
             // reading TEX_PAGE: which slot the next page load fills
             I_TXP = 6'd41, I_TXP2 = 6'd42, I_TXP3 = 6'd43,
             // the audio event list: count then two words each
             I_EVW = 6'd44, I_EVC = 6'd45,
             I_WVN = 6'd46,         // next voice's page (checked: 0..45
             // GRADING (spec.GRADE_SRC): read the pointer, then walk
             // GRADE_WORDS levels into the video head's table. Same
             // shape as the event list: present, wait, commit.
             I_GRP = 6'd47, I_GRR = 6'd48, I_GRR2 = 6'd49,
             I_GRW = 6'd50, I_GRC = 6'd51,
             I_VIS = 6'd52, I_AUD = 6'd53,    // (0..46 were taken)
             I_ARW = 6'd54, I_ARC = 6'd55, I_ARZ = 6'd56,   // spec.AU_RESET
             I_D2 = 6'd57,                    // spec.DMA2_*: the second request
             // spec.OBJ_CART (frontier 20): the cart mesh's loader
             I_ML = 6'd58, I_MRD = 6'd59, I_MCK = 6'd60, I_MCHK = 6'd61,
             I_MSTR = 6'd62, I_MNX = 6'd63;
                                    // were taken, and a duplicate here
                                    // wedges the frame in silence)
  localparam [13:0] A_FRAME = REG_FRAME, A_PAD = REG_PAD;

  reg [5:0]  st;
  reg [4:0]  aui;        // 32 audio words now, not 8
  reg [7:0]  evi;        // 1 + 2*AU_EV_MAX event words
  reg [13:0] g_addr;     // the grade table's walk
  reg [5:0]  gi;
  reg        ev_we;
  reg [7:0] ev_a;  reg [31:0] ev_d;
  reg [13:0] au_addr;
  reg [31:0] frame_no;
  reg [15:0] pad_l;
  assign pad_stb  = (st == I_WP);
  assign pad_word = pad_l;

  wire        vm_running;
  wire [31:0] dl_data;
  wire [13:0] seq_addr;
  wire        seq_done, gpu_rdy;
  wire        tri_go;
  wire        seq_item;
  wire        seq_skip;
  wire [10:0] seq_skip_n;
  wire        t_tex, t_tinton, t_otint, t_span, t_blend, t_add;
  wire  [9:0] t_oid;
  wire [16:0] vis_q;
  reg   [9:0] visi;          // spec.VIS_BASE: the readback walk
  // ---- THE LONG LIST (spec.OLX_PTR) -------------------------------------
  // One cell says where the object list is. The verdict is on the POINTER
  // alone -- nonzero, and low enough that the longest list still ends
  // inside DMEM -- so it is known before a single object is read, and the
  // sequencer and the cart-mesh loader are simply handed a base.
  reg  [31:0] d_olx;
  wire        ol_long = (d_olx[31:14] == 18'd0) && (d_olx[13:0] != 14'd0)
                     && (d_olx[13:0] <= OLX_LIM[13:0]);
  wire [13:0] ol_base = ol_long ? d_olx[13:0] : OL_BASE[13:0];
  // ---- THE GAZE (spec.GAZE_BASE) ----------------------------------------
  // The list is judged HERE, as its words come off DMEM in the request
  // sweep, by the law's own rule: on the glass and strictly after the
  // entry before it, or the list ends. What reaches zgpu is already the
  // accepted list, in order, and its length.
  reg         gz_on;         // the cart asked (n != 0): answers are written
  reg   [3:0] gz_cnt;        // n as asked, clamped to GAZE_MAX
  reg   [3:0] gz_n;          // entries accepted so far
  reg         gz_cut;        // ...and whether the list has ended
  reg  [17:0] gz_last;       // the last accepted {y, x}
  reg         gz_we;
  reg   [2:0] gz_wa;
  reg  [17:0] gz_wd;
  wire [24:0] gz_q;
  wire  [3:0] gz_i   = dsel[3:0] - 4'd12;        // dsel 44..51 -> 0..7
  wire [17:0] gz_yx  = {dl_data[24:16], dl_data[8:0]};
  wire        gz_ok  = !gz_cut && (gz_i < gz_cnt)
                    && (dl_data[15:0]  < 16'd320)
                    && (dl_data[31:16] < 16'd288)
                    && (gz_n == 4'd0 || gz_yx > gz_last);
  // THE READBACK WALK (I_VIS), 520 beats: beat b presents object b's
  // tally and writes object b-1's, for objects 0..510; then eight beats
  // for the gaze's answers. Objects past the 64th go to VISX_BASE, and
  // only while the long list is on.
  wire        gz_beat = visi[9];                 // beats 512..519
  wire  [2:0] gz_ra   = visi[2:0];
  wire [31:0] gz_word = ({1'b0, gz_ra} < gz_n) ? {7'd0, gz_q}
                                               : 32'hFFFFFFFF;
  wire        vx_beat = (visi > OL_MAX[9:0]);    // an object past the 64th
  wire        vis_wr  = gz_beat ? gz_on
                      : (visi != 10'd0) && (!vx_beat || ol_long);
  reg   [4:0] audi;          // spec.AUD_BASE: and the other one
  // ---- THE LIGHT (spec.OBJ_LIT) ------------------------------------
  // Read once a frame with the rest of the register block. The
  // DIRECTION is handed to zseq ALREADY SCALED BY THE DIFFUSE GAIN,
  // which costs three multiplies a frame and takes one out of the
  // per-vertex chain -- and is exact, not an approximation:
  //     dif * max(0, N.L)  ==  max(0, N.(L*dif))   for dif >= 0
  // so the shift and the clamp that follow are unchanged.
  reg  [23:0] l_dir;
  reg   [5:0] l_amb, l_dif;
  function signed [13:0] lscale(input [7:0] c, input [5:0] g);
    lscale = $signed({{6{c[7]}}, c}) * $signed({1'b0, g});
  endfunction
  // REGISTERED, not wires. As combinational they put a multiply here
  // feeding a multiply in zseq's dot product with a module boundary in
  // between and nothing to break the chain. They move once a frame; a
  // register costs 42 flops and buys the whole path.
  reg signed [13:0] lx, ly, lz;
  always @(posedge clk) begin
    lx <= lscale(l_dir[23:16], l_dif);
    ly <= lscale(l_dir[15:8],  l_dif);
    lz <= lscale(l_dir[7:0],   l_dif);
  end
  wire [23:0] aud_q;
  wire        zw_sh;
  wire [4:0]  t_alpha;
  wire [4:0]  t_page;   // five bits: TEX_PAGES is 24
  wire [14:0] t_tint;
  wire signed [35:0] tx0, ty0, tx1, ty1, tx2, ty2;
  wire [50:0] tc0;
  wire signed [25:0] tcxr, tcyr, tcxg, tcyg, tcxb, tcyb;
  wire [15:0] tz0;
  wire signed [25:0] tzx, tzy;
  reg         seq_ran;               // latched seq_done for this frame
  reg         gpu_flushed;           // this band's colour has gone out
  // ---- the mover (spec.DMA_*): CRAM segment -> DMEM, once a frame -----
  reg [5:0]  dsel;                   // which request cell we are reading
  reg        swept2;                 // the sweep runs TWICE a frame: once
                                     // before the movers (their params),
                                     // once after (what the paint sees).
                                     // The law's paint reads DMEM after
                                     // the movers' instant, so a launch
                                     // that DMAs into register cells --
                                     // BG_SRC in a shelved game's image
                                     // -- must reach the pump THIS frame.
                                     // One sweep read stale registers for
                                     // 101 builds and nothing could tell,
                                     // because nothing had ever moved a
                                     // register cell with the mover.
                                     // (6 bits since the compositor:
                                     //  21..33 latch its block)
  reg [31:0] d_src, d_dst, d_len, d_go, d_bg;
  reg [31:0] d_seg;              // SEG_BASE: the segment window, added to
                                 // every presented CRAM offset (DMA, OVL,
                                 // the pump). Fetched with the params.
  // ---- the write-window probe (an instrument, not law): a cart that
  // writes 0x5EEB to the high half of DMEM[11789] arms a mask-lift
  // KNOB swept by the frame counter (K = frame[9:6], ~1 s per step,
  // 16-step cycle). Cart and core derive K from the same counter, so
  // the screen can label what the silicon is doing. Normal carts
  // leave the cell zero and get build-55 behavior exactly.
  reg [31:0] d_wp;
  reg [3:0]  k_lat;
  // ---- the pick register (spec.PICK_*): watch one pixel through the
  // paint; answer with the visible owner's paint-order id and depth
  reg [31:0] d_px, d_py;
  reg [13:0] t_src;                  // the page image's DMEM base
  reg [9:0]  t_i;                    // word cursor, 0..679
  // spec.TEX_STRIDE: the page stride is the PAGE, not the next power
  // of two, so the loader multiplies where it used to concatenate.
  // 1360 = 1024 + 256 + 64 + 16, on a three-bit slot.
  // TEX_STRIDE * slot, one bit wider now: 16 x 1360 = 21,760 needs 15.
  wire [14:0] tslot_base = {t_slot, 10'd0} + {2'd0, t_slot, 8'd0}
                         + {4'd0, t_slot, 6'd0} + {6'd0, t_slot, 4'd0};
  reg        tex_we;
  reg [31:0] s_slot, s_off, s_dst, s_len, s_go;   // the card's request
  reg [31:0] o_src, o_dst, o_len, o_go;           // the overlay's
  reg [31:0] co_reg [0:12];   // the compositor block, latched
  assign co_flat = {co_reg[12], co_reg[11], co_reg[10], co_reg[9],
                    co_reg[8],  co_reg[7],  co_reg[6],  co_reg[5],
                    co_reg[4],  co_reg[3],  co_reg[2],  co_reg[1],
                    co_reg[0]};
                                     // once a frame like the AU regs
  reg [31:0] f_rgb, f_near, f_shift, f_lod;       // and the fog's
  reg [31:0] e_rgb;                               // OBJ_EDGE's colour
  reg        dma_imem;               // this burst lands in IMEM, not DMEM
  reg        dma_ret;                // ...and returns to the overlay path
  // spec.DMA2_*: the second request, latched with the rest and then
  // loaded into d_* so the SAME engine (and req_ok) serves it
  reg [31:0] m2_src, m2_dst, m2_len, m2_go;
  reg        dma_two;                // the engine is serving request 2
  // ---- THE CART MESH'S LOADER (spec.OBJ_CART; frontier 20) ---------------
  // After the second sweep -- DMEM is what the paint will see -- walk the
  // object list. A cart object's five descriptor words are read, the
  // law's refusals applied (gpu.py _cart_mesh, in its order), and an
  // admitted one's three streams are burst into zmesh's store by the
  // mover's own engine: dma_mesh says the words are the store's, not
  // DMEM's. Every object gets a verdict, so the store's table is never
  // stale for an object the sequencer will ask about.
  reg [9:0]  ml_o, ml_n;             // the object in hand, and how many
  reg [2:0]  msel;                   // which word of it is being read
  reg [13:0] ml_e;                   // its first word in the list
  reg [31:0] ml_mesh;
  reg [31:0] ml_d0, ml_d1, ml_d2, ml_d3, ml_d4;
  reg [12:0] ml_uv;                  // vertices admitted this frame
  reg [12:0] ml_uf;                  // ...and faces
  reg [2:0]  ml_str;                 // the stream in hand: 1 v, 2 f, 3 c (4: done)
  reg [1:0]  dma_mesh;               // this burst lands in the store
  reg        ml_new, ml_obj, ml_okr;
  wire [15:0] ml_nv = ml_d0[15:0];
  wire [15:0] ml_nf = ml_d0[31:16];
  wire [31:0] ml_vw = ({22'd0, ml_nv[8:0], 1'b0} + {23'd0, ml_nv[8:0]} + 32'd1) >> 1;
  wire [31:0] ml_fw = {22'd0, ml_nf[9:0]};
  wire [31:0] ml_cw = ({22'd0, ml_nf[9:0]} + 32'd1) >> 1;
  wire [31:0] ml_e1 = ml_d1 + d_seg, ml_e2 = ml_d2 + d_seg, ml_e3 = ml_d3 + d_seg;
  wire       ml_valid = (ml_nv <= MESH_NV_MAX) && (ml_nf <= MESH_NF_MAX) &&
                        (ml_d4[31:4] == 28'd0) &&
                        !ml_d1[31] && !ml_e1[31] && (ml_e1 + ml_vw <= CRAM_WORDS) &&
                        !ml_d2[31] && !ml_e2[31] && (ml_e2 + ml_fw <= CRAM_WORDS) &&
                        !ml_d3[31] && !ml_e3[31] && (ml_e3 + ml_cw <= CRAM_WORDS) &&
                        ({1'b0, ml_uv} + {5'd0, ml_nv[8:0]} <= CM_VMAX) &&
                        ({1'b0, ml_uf} + {4'd0, ml_nf[9:0]} <= CM_FMAX);
  wire [31:0] ml_eff = (ml_str == 3'd1) ? ml_e1 : (ml_str == 3'd2) ? ml_e2 : ml_e3;
  wire [31:0] ml_len = (ml_str == 3'd1) ? ml_vw : (ml_str == 3'd2) ? ml_fw : ml_cw;
  wire [13:0] ml_addr = (msel == 3'd0) ? ol_base :
                        (msel == 3'd1) ? ml_e :
                        (msel == 3'd2) ? ml_e + 14'd5 :
                                         ml_mesh[13:0] + {11'd0, msel} - 14'd3;
  wire [31:0] mesh_q;                // zmesh's answer to the sequencer
  wire        seq_cart, cm_ok;
  wire [8:0]  seq_obj;
  reg [15:0] c_slot_r;               // ...latched, so a cart rewriting
  reg [31:0] c_off_r;                // the cells mid-flight changes
  reg [13:0] c_dst_r;                // nothing
  reg [12:0] c_len_r;
  reg [5:0]  c_wait;                 // frames left, the legislated wait
  reg [7:0]  c_age;                  // frames since this request was
  reg [7:0]  c_lat;                  // latched; and the MEASURED latency
  reg        c_seen;                 // of the last one to actually land
  reg [7:0]  n_copy;                 // words the CONSOLE wrote into DMEM
  reg        c_save_r;               // this request writes the card
  reg [12:0] c_j;                    // the save cursor
  reg        c_busy;
  reg [12:0] c_i;                    // the copy cursor
  reg        card_we;
  reg [13:0] w_src;                  // the wave BANK's DMEM base
  reg [5:0]  w_i;                    // word cursor, 0..WAV_WORDS-1
  reg [3:0]  w_ch;                   // which voice is being filled
  reg [2:0]  wpg [0:AU_CHANNELS-1];  // each voice's chosen page, latched
  reg        wav_we;                 // from its ctrl word during I_AUC
  // spec.AU_RESET, read after the event list: a ONE-CLOCK pulse into the
  // engine, before any of this frame's samples (they tick after the latch)
  reg        au_rst;
  reg [3:0]  wav_ch;
  reg [5:0]  wav_a;
  reg [31:0] wav_d;
  // pg * WAV_WORDS: a 3-bit operand against the 14-bit parameter, so the
  // product is 14 bits wide and its largest value (7 * 64 = 448) fits.
  // Widths are sized to OPERANDS in Verilog, never to results -- three
  // separate pictures in this project have been wrong for forgetting it.
  wire [13:0] w_off = wpg[w_ch] * WAV_WORDS[13:0];
  wire [16:0] w_end = {3'd0, w_src} + {3'd0, w_off} + WAV_WORDS[16:0];
  wire        w_bad = w_end > DMEM_WORDS[16:0];   // this voice keeps its own
  reg [14:0] tex_a;        // slot*TEX_STRIDE + texel
  reg [4:0]  t_slot;   // TEX_PAGES pages
  reg [14:0] tex_d;
  reg        watch_en;
  reg [16:0] watch_addr;
  reg [15:0] tri_ctr, cur_tri;
  // ---- THE TRIANGLE QUEUE (frontier B2) ----------------------------------
  // zseq handed zgpu one triangle at a time through a one-deep register,
  // so each waited on the other: with B1 in, the sequencer's state
  // histogram against the rasterizer's state (ZETA_SEQHIST) showed the
  // sequencer finishing ONE triangle and then sitting out every band's
  // clear -- 97,538 clocks of the TND brawl's frame 466, 94,468 of frame
  // 226 -- and the two taking turns for the rest (213k of holding against
  // 246k of starving at 226). A queue lets the sequencer work THROUGH the
  // clear and the long walks, and the rasterizer drain it through the
  // clipper's long thinks.
  //
  // NOTHING THE LAW READS CHANGES: the same triangles, in the same order,
  // each with everything zgpu latches at tri_go (and the pick register's
  // id, cur_tri, captured at the sequencer's own tri_go as it always was).
  // The rasterizer sees the handshake it saw before -- rdy observed, go
  // one clock later -- from the queue's head instead of zseq.
  //
  // 546 BITS AN ENTRY, COUNTED (216 vertices, 51 + 156 colour, 68 depth,
  // 16 id, 39 flags): as flip-flops a 2-deep queue is ~550 ALMs. As MLAB
  // it is 28 MLABs, 32 deep for the same price -- and M10K is 308 of 308,
  // so it MUST say MLAB (verify in the map report).
  localparam TQ_W = 548;
`ifndef TQ_LG
`define TQ_LG 5
`endif
  localparam TQ_LG = `TQ_LG;          // log2 of the depth (5: one MLAB deep)
  wire [TQ_W-1:0] tq_in;
  (* ramstyle = "MLAB, no_rw_check" *) reg [TQ_W-1:0] tq_mem [0:(1 << TQ_LG) - 1];
  reg  [TQ_W-1:0] tq_out;             // the head, held for zgpu
  reg  [TQ_LG:0] tq_wp, tq_rp;        // one wrap bit each
  reg         tq_go;                  // zgpu's tri_go
  wire [TQ_LG:0] tq_n  = tq_wp - tq_rp;
  wire        tq_empty = (tq_wp == tq_rp);
  // zseq sees ready at t and writes at t+1: keep one slot in hand, so a
  // write already in flight can never land on a full queue
  wire        tq_rdy   = (tq_n < (1 << TQ_LG) - 1);
  wire        gpu_rdy_w;
  wire        tq_pop   = gpu_rdy_w && !tq_empty && !tq_go;
  always @(posedge clk) begin
    if (tri_go) tq_mem[tq_wp[TQ_LG-1:0]] <= tq_in;
    if (tq_pop) tq_out <= tq_mem[tq_rp[TQ_LG-1:0]];
    if (!core_rst_n || st == I_GK) begin   // every band starts empty
      tq_wp <= 0; tq_rp <= 0; tq_go <= 1'b0;
    end else begin
      if (tri_go) tq_wp <= tq_wp + 1'b1;
      if (tq_pop) tq_rp <= tq_rp + 1'b1;
      tq_go <= tq_pop;
    end
  end
  // the band is painted when the rasterizer is idle AND nothing is queued
  // or in flight toward it
  assign gpu_rdy = gpu_rdy_w && tq_empty && !tq_go && !tri_go;
  wire signed [35:0] qx0, qy0, qx1, qy1, qx2, qy2;
  wire [50:0] qc0;
  wire signed [25:0] qcxr, qcyr, qcxg, qcyg, qcxb, qcyb;
  wire [15:0] qz0;
  wire signed [25:0] qzx, qzy;
  wire [15:0] q_tri;
  wire        q_tex, q_tinton, q_otint, q_span, q_blend, q_add;
  wire [14:0] q_tint;
  wire [9:0]  q_oid;
  wire [4:0]  q_alpha, q_page;
  assign tq_in = {tx0, ty0, tx1, ty1, tx2, ty2, tc0,
                  tcxr, tcyr, tcxg, tcyg, tcxb, tcyb, tz0, tzx, tzy,
                  cur_tri, t_tex, t_tint, t_tinton, t_otint, t_span,
                  t_blend, t_add, t_oid, t_alpha, t_page};
  assign {qx0, qy0, qx1, qy1, qx2, qy2, qc0,
          qcxr, qcyr, qcxg, qcyg, qcxb, qcyb, qz0, qzx, qzy,
          q_tri, q_tex, q_tint, q_tinton, q_otint, q_span,
          q_blend, q_add, q_oid, q_alpha, q_page} = tq_out;
  reg [31:0] pick_id;
  reg [15:0] pick_z;
  reg        pick_sh;
  reg [1:0]  pws;                    // which result cell writes at I_PW
  wire        zw_we, zw_clr;
  wire [16:0] zw_addr;
  wire [15:0] zw_data, zw_tri;
  wire       sweep_en = (d_wp[31:16] == 16'h5EEB);
  // fine mode: bit 15 of the low half holds K at the cart's own value
  // (dpad-stepped at typing speed) instead of the timer sweep
  wire [3:0] k_eff = d_wp[15] ? d_wp[3:0] : k_lat;
  // ---- the backdrop pump: the room streamed into zgpu's clear ---------
  // THE TILE, step 1: the paint runs once per BAND of TH rows. zseq needs
  // no change at all for this -- it walks the object list from the top on
  // every `start`, so re-pulsing start is the whole replay mechanism.
  // ---- THE PER-STAGE METER (roadmap 15) --------------------------------
  // The band penalty did not track face count -- lodspan has a quarter of
  // fabric's faces and thirty-five times the cost -- and three hypotheses
  // died against measurement. So stop guessing and count: where does a
  // band's time actually go? Six counters, reset at the frame's first
  // band, read out by the ZETA_CLK meter in server.cpp.
  //   m_clr   rasterizer clearing (per band, so TROWS x a partial screen)
  //   m_walk  rasterizer walking a triangle
  //   m_idle  rasterizer in S_WAIT: STARVED, nothing to draw
  //   m_stall rasterizer frozen by the write FIFO
  //   m_seq   sequencer working
  //   m_blkd  sequencer holding a triangle the rasterizer will not take
  // Starved high => sequencer-bound. Blocked high => rasterizer-bound.
  wire [2:0] gpu_m_st;
  wire       gpu_flush_busy;
  reg        gpu_flush_go;
  wire       seq_m_act, seq_m_blk, seq_m_skp;
  reg [31:0] m_clr, m_walk, m_idle, m_stall, m_seq, m_blkd, m_skp;
  reg [31:0] m_evload, m_evfire;
  // SIX BITS, NOT FOUR. At TILE_H=16 there are 18 bands and `TROWS[3:0]`
  // silently truncated 18 to 2: the frame painted two bands, called itself
  // done, and every gate would have compared a two-ninths picture. Nine
  // bands fit in four bits and hid it completely. This machine has been
  // here before (`localparam [5:0]` and the wedged frame); widths on a
  // count that a parameter drives are never left to fit by luck.
  reg [5:0]  tpass;                  // which band is being painted
  localparam BAND_WORDS = ZW * TH;   // backdrop words one band consumes
  // WIDTHS SPELLED OUT. A Verilog multiply is sized to its OPERANDS, not
  // its result, and a silent truncation here would paint a plausible
  // picture from the wrong half of the backdrop. Both products are
  // written wide enough on purpose: 9 bits holds (TROWS-1)*TH = 144, and
  // 22 bits holds (TROWS-1)*2*BAND_WORDS = 92,160 half-addresses.
  wire [8:0]  tile_y0   = {3'd0, tpass} * TH[8:0];
  wire [22:0] band_half = {17'd0, tpass} * (2 * BAND_WORDS);
  reg        blit_on;                // this frame clears to the image
  reg        b_run;                  // pump active
  reg        b_infl;                 // a burst is in flight
  reg [17:0] b_left;                 // cart words still to stream
  reg [31:0] b_lo;                   // low half awaiting its partner
  reg        b_hi;
  // the skid: a burst may land while zgpu is stalled by the write FIFO.
  // BRAM with a one-word prefetch (sk_q) -- as a register file the
  // 128x32 array plus its async mux cost ~250 LABs and build 36 blew
  // the device by exactly that order. sk_n counts a cycle late (sk_wd)
  // so the prefetch never reads the word the RAM is committing.
  reg [31:0] skid [0:127];
  reg [31:0] sk_q;
  reg [7:0]  sk_w, sk_r;
  reg        sk_wd;                  // write landed last cycle
  reg [7:0]  sk_n;
  wire       skid_room = (sk_n <= 8'd64);
  wire       blit_we_w = (sk_n != 8'd0);
  wire       blit_take;
  reg [22:0] dma_addr;               // CRAM half-word cursor (23 bits:
                                     // two dies a chip, build 105)
  reg [IMEM_BITS-1:0] dma_dst;       // DMEM word cursor -- or IMEM's, for an
                                     // overlay: as wide as IMEM (frontier 19)
  reg [31:0] dma_left;               // cart words still to move
  reg [7:0]  dma_len;
  reg        dma_go, dma_hi;
  reg [7:0]  bh;                     // halves accepted this burst
  reg        d_fin;                  // latched dma_done: the
                                     // burst's end is a pulse
  reg [15:0] dma_lo;                 // low half, waiting for its partner
  reg        dma_we;                 // a whole 32-bit word is ready
  reg [31:0] dma_word;
  wire       dma_step, dma_done, dma_ack;
  always @(posedge clk)
    sk_q <= skid[blit_take ? sk_r[6:0] + 7'd1 : sk_r[6:0]];
  wire [15:0] dma_data;
  // THE SEGMENT WINDOW (SEG_BASE): every presented CRAM offset is read
  // as offset + d_seg. The presented value keeps its old refusals (a
  // negative source, BG_SRC == 0); the BOUNDS move to the effective.
  wire [31:0] eff_dma = d_src + d_seg;
  wire [31:0] eff_ovl = o_src + d_seg;
  wire [31:0] eff_bg  = d_bg  + d_seg;
  wire       req_ok = (d_len != 0) && (d_len <= DMA_MAX) &&
                      !d_src[31] && !d_dst[31] && !eff_dma[31] &&
                      (eff_dma + d_len <= CRAM_WORDS) &&
                      (d_dst + d_len <= DMEM_WORDS);
  wire        gfb_we;
  wire [16:0] gfb_a;
  wire [14:0] gfb_d;
  wire        fb_ready, fb_stall, fb_widle;
  wire [14:0] px_q;

  // the VM's external DMEM port: boot writes, then the cabinet's two latch
  // writes, then GPU display-list reads -- never concurrent by construction
  wire        boot_dmem = boot_we && (boot_kind == 2'd1);
  wire        boot_cram = boot_we && (boot_kind == 2'd2);
  // a segment word crosses in ONE pulse, 32 bits wide -- the halving
  // now happens inside cram_fb's flush stream. The old two-pulse split
  // cost ~6 clocks per word and capped delivery near 8 MB/s; the
  // bridge can burst past that.
  reg         bc_we;
  reg  [22:0] bc_addr;
  reg  [31:0] bc_data;
  wire        boot_cram_we   = bc_we;
  wire [22:0] boot_cram_addr = CRAM_CART_BASE[22:0] + {bc_addr[21:0], 1'b0};
  wire [31:0] boot_cram_data = bc_data;
  wire        boot_cram_busy;
  assign      boot_busy = boot_cram || bc_we || boot_cram_busy || prog_busy;
  always @(posedge clk) begin
    bc_we <= 1'b0;
    if (rst_n && boot_cram) begin
      bc_addr <= boot_addr; bc_data <= boot_data; bc_we <= 1'b1;
    end
  end
  wire        ext_we    = boot_dmem || st == I_WF || st == I_WP ||
                          (dma_we && !dma_imem && dma_mesh == 2'd0) || st == I_DCLR ||
                          st == I_OCLR || st == I_PW ||
                          card_we || st == I_CCLR || st == I_CGO ||
                          st == I_CDG || st == I_CDG2 || st == I_CDG3 ||
                          st == I_CDG4 || (st == I_VIS && vis_wr)
                          || (st == I_AUD && audi != 5'd0) || st == I_ARZ;
  wire [13:0] ext_addr  = boot_dmem   ? boot_addr[13:0] :
                          (st == I_VIS)
                              ? (gz_beat ? (GAZE_ANS[13:0] + {11'd0, gz_ra})
                                 : vx_beat ? (VISX_BASE[13:0] + {4'd0, visi}
                                              - 14'd1 - OL_MAX[13:0])
                                 : (VIS_BASE[13:0] + {4'd0, visi} - 14'd1)) :
                          (st == I_AUD)
                              ? (AUD_BASE[13:0] + {9'd0, audi} - 14'd1) :
                          (st == I_WF) ? A_FRAME :
                          (st == I_WP) ? A_PAD :
                          (dma_we && dma_mesh == 2'd0) ? dma_dst[13:0] :
                          (st == I_MRD || st == I_MCK) ? ml_addr :
                          (st == I_DCLR) ? (dma_two ? DMA2_GO[13:0]
                                                    : DMA_GO[13:0]) :
                          (st == I_OCLR) ? OVL_GO[13:0] :
                          card_we ? c_dst_r + {1'b0, c_i} :
                          (st == I_CCLR || st == I_CGO) ? SD_GO[13:0] :
                          (st == I_CDG)  ? CARD_DIAG[13:0] :
                          (st == I_CDG2) ? CARD_DIAG[13:0] + 14'd1 :
                          (st == I_CDG3) ? CARD_DIAG[13:0] + 14'd2 :
                          (st == I_CDG4) ? CARD_DIAG[13:0] + 14'd3 :
                          (st == I_PW)   ? ((pws == 2'd0) ? PICK_ID[13:0]
                                          :  (pws == 2'd1) ? PICK_Z[13:0]
                                          :                  PICK_SH[13:0]) :
                          (st == I_DRD || st == I_DCK) ? dreq_addr :
                          (st == I_TXP || st == I_TXP2) ? TEX_PAGE[13:0] :
                          (st == I_TXC || st == I_TXC2) ? TEX_SRC[13:0] :
                          (st == I_TXW || st == I_TXD) ? t_src + {4'd0, t_i} :
                          (st == I_CSV || st == I_CSV2)
                              ? c_dst_r + {1'b0, c_j} :
                          (st == I_WVC || st == I_WVC2) ? WAV_SRC[13:0] :
                          (st == I_WVW || st == I_WVD)
                              ? w_src + w_off + {8'd0, w_i} :
                          (st == I_ARW || st == I_ARC || st == I_ARZ)
                              ? AU_RESET[13:0] :
                          (st == I_GRP || st == I_GRR) ? GRADE_SRC[13:0] :
                          (st == I_GRW || st == I_GRC) ? g_addr :
                          (st == I_AUW || st == I_AUC ||
                           st == I_EVW || st == I_EVC) ? au_addr : seq_addr;
  // 21.. walks the compositor block straight through, one cell a state,
  // instead of thirteen more lines of mux: the block is contiguous by law
  wire [13:0] dreq_cell;             // (the chain below, named so the
                                     // long list's cell joins it at ONE
                                     // width: the lint ratchet's catch)
  wire [13:0] dreq_addr = (dsel == 6'd52) ? OLX_PTR[13:0] : dreq_cell;
  assign      dreq_cell = (dsel >= 6'd43)
                            ? (GAZE_BASE[13:0] + {8'd0, dsel} - 14'd43) :
                          (dsel >= 6'd39)
                            ? (DMA2_SRC[13:0] + {8'd0, dsel} - 14'd39) :
                          (dsel == 6'd38) ? SEG_BASE[13:0] :
                          (dsel == 6'd37) ? LIGHT_DIF[13:0] :
                          (dsel == 6'd36) ? LIGHT_AMB[13:0] :
                          (dsel == 6'd35) ? LIGHT_DIR[13:0] :
                          (dsel == 6'd34) ? EDGE_RGB[13:0] :
                          (dsel >= 6'd21)
                            ? (CO_BASE[13:0] + {8'd0, dsel} - 14'd21) :
                          (dsel == 6'd20) ? LOD_FLAT[13:0] :
                          (dsel == 6'd19) ? FOG_SHIFT[13:0] :
                          (dsel == 6'd18) ? FOG_NEAR[13:0] :
                          (dsel == 6'd17) ? FOG_RGB[13:0] :
                          (dsel == 6'd16) ? OVL_GO[13:0] :
                          (dsel == 6'd15) ? OVL_LEN[13:0] :
                          (dsel == 6'd14) ? OVL_DST[13:0] :
                          (dsel == 6'd13) ? OVL_SRC[13:0] :
                          (dsel == 6'd12) ? SD_GO[13:0] :
                          (dsel == 6'd11) ? SD_LEN[13:0] :
                          (dsel == 6'd10) ? SD_DST[13:0] :
                          (dsel == 6'd9)  ? SD_OFF[13:0] :
                          (dsel == 6'd8)  ? SD_SLOT[13:0] :
                          (dsel == 6'd7) ? PICK_Y[13:0] :
                          (dsel == 6'd6) ? PICK_X[13:0] :
                          (dsel == 6'd5) ? 14'd11789 :
                          (dsel == 6'd4) ? BG_SRC[13:0]
                                          : DMA_SRC[13:0] + {9'd0, dsel};
  wire [31:0] ext_wdata = (st == I_VIS) ? (gz_beat ? gz_word : {15'd0, vis_q}) :
                          (st == I_AUD) ? { 8'd0, aud_q} :
                          boot_dmem   ? boot_data :
                          dma_we       ? dma_word :
                          (st == I_DCLR || st == I_ARZ) ? 32'd0 :
                          (st == I_OCLR) ? 32'd0 :
                          card_we ? card_q :
                          (st == I_CCLR) ? 32'd0 :
                          (st == I_CGO)  ? 32'd1 :
                          (st == I_CDG)  ? card_diag0 :
                          (st == I_CDG2) ? card_diag1 :
                          (st == I_CDG3) ? card_diag2 :   // the crossing
                                          // is proven; this half now
                                          // carries what the SAVE fill
                                          // wrote (card_apf's w0/w1)
                          (st == I_CDG4) ? {16'd0, n_copy, c_lat} :
                          (st == I_PW)   ? ((pws == 2'd0) ? pick_id
                                          :  (pws == 2'd1) ? {16'd0, pick_z}
                                          :                  {31'd0, pick_sh}) :
                          (st == I_WF) ? frame_no : {16'd0, pad_l};

  wire core_rst_n = rst_n && core_en;

  // ---- THE PROGRAM, IN THE SRAM (frontier 19) ----------------------------
  // The loader's words go straight to zimem (the loader waits on boot_busy).
  // An overlay arrives from CRAM in 64-word bursts far faster than the
  // SRAM takes it, so its words queue in OFIFO and drain one at a time;
  // the mover asks for its next burst only once the queue is empty.
  wire        ic_req, ic_we, ic_done, ic_flush;
  wire [IMEM_BITS-1:2] ic_line;
  wire [1:0]  ic_wo;
  wire [31:0] ic_wd;
  wire        prog_busy;
  (* ramstyle = "MLAB, no_rw_check" *) reg [31:0] ofifo [0:63];
  reg  [6:0]  of_w = 7'd0, of_r = 7'd0;
  reg  [IMEM_BITS-1:0] od_addr;      // where the next queued word lands
  reg         od_we = 1'b0;          // a drained word, offered to zimem
  reg         od_g = 1'b0;           // ...and the cycle after (zimem's busy
  reg  [31:0] od_data;               // rises then: no second offer)
  wire        of_empty = (of_w == of_r);
  always @(posedge clk) begin
    od_we <= 1'b0;
    od_g  <= od_we;
    if (dma_we && dma_imem) begin
      ofifo[of_w[5:0]] <= dma_word;
      of_w <= of_w + 7'd1;
    end
    if (!of_empty && !prog_busy && !od_we && !od_g) begin
      od_data <= ofifo[of_r[5:0]];
      od_we   <= 1'b1;
      of_r    <= of_r + 7'd1;
    end
    if (od_we) od_addr <= od_addr + 1'b1;
    if (st == I_OVL) od_addr <= o_dst[IMEM_BITS-1:0];
  end
  wire boot_prog = boot_we && (boot_kind == 2'd0);
  zimem #(.PAW(IMEM_BITS)) u_imem (
    .clk(clk),
    .ic_req(ic_req), .ic_line(ic_line), .ic_we(ic_we), .ic_wo(ic_wo),
    .ic_wd(ic_wd), .ic_done(ic_done), .ic_flush(ic_flush),
    .prog_we(boot_prog || od_we),
    .prog_addr(od_we ? od_addr : boot_addr[IMEM_BITS-1:0]),
    .prog_wdata(od_we ? od_data : boot_data),
    .prog_busy(prog_busy),
    .g_req(g_req), .g_gnt(g_gnt), .g_a(g_a), .g_do(g_do), .g_doe(g_doe),
    .g_oe_n(g_oe_n), .g_we_n(g_we_n),
    .sram_a(sram_a), .sram_do(sram_do), .sram_doe(sram_doe), .sram_di(sram_di),
    .sram_oe_n(sram_oe_n), .sram_we_n(sram_we_n));

  zvm #(.PAW(IMEM_BITS)) u_vm (
    .clk(clk), .rst_n(core_rst_n),
    .start(st == I_VK), .running(vm_running), .trapped(trapped),
    .ext_we(ext_we), .ext_addr(ext_addr), .ext_wdata(ext_wdata),
    .ext_rdata(dl_data),
    .ic_req(ic_req), .ic_line(ic_line), .ic_we(ic_we), .ic_wo(ic_wo),
    .ic_wd(ic_wd), .ic_done(ic_done), .ic_flush(ic_flush));

  zmesh u_mesh (
    .clk(clk),
    .ld_new(ml_new), .ld_obj(ml_obj), .ld_o(ml_o[8:0]), .ld_ok(ml_okr),
    .ld_nv(ml_nv[8:0]), .ld_nf(ml_nf[9:0]), .ld_sh(ml_d4[3:0]),
    .ld_sel(dma_mesh), .ld_we(dma_we && dma_mesh != 2'd0), .ld_word(dma_word),
    .rd_obj(seq_obj), .rd_addr(seq_addr), .cm_ok(cm_ok), .rd_data(mesh_q));

  zseq u_seq (
    .clk(clk), .rst_n(core_rst_n),
    .start(st == I_GK), .done(seq_done),
    .m_act(seq_m_act), .m_blk(seq_m_blk), .m_skp(seq_m_skp),
    .tile_y0(tile_y0), .first_pass(tpass == 6'd0),
    .rd_addr(seq_addr), .rd_data(seq_cart ? mesh_q : dl_data),
    .rd_cart(seq_cart), .rd_obj(seq_obj), .cm_ok(cm_ok), .rd_dmem(dl_data),
    .ol_base(ol_base), .ol_long(ol_long),
    .lod_flat((f_lod[31] || f_lod > 32'hFFFF) ? 16'd0 : f_lod[15:0]),
    .tri_rdy(tq_rdy), .tri_go(tri_go), .seq_item(seq_item), .seq_skip(seq_skip),
    .seq_skip_n(seq_skip_n),
    .t_tex(t_tex), .t_tint(t_tint), .t_tinton(t_tinton), .t_otint(t_otint), .t_span(t_span),
    .t_blend(t_blend), .t_add(t_add), .t_oid(t_oid),
    .l_x(lx), .l_y(ly), .l_z(lz), .l_amb(l_amb),
    .t_alpha(t_alpha), .t_page(t_page),
    .tx0(tx0), .ty0(ty0), .tx1(tx1), .ty1(ty1), .tx2(tx2), .ty2(ty2),
    .tc0(tc0), .tcxr(tcxr), .tcyr(tcyr), .tcxg(tcxg), .tcyg(tcyg),
    .tcxb(tcxb), .tcyb(tcyb), .tz0(tz0), .tzx(tzx), .tzy(tzy));

  zgpu u_gpu (
    .clk(clk), .rst_n(core_rst_n),
    .start(st == I_GK), .tile_y0(tile_y0), .rdy(gpu_rdy_w), .stall(fb_stall),
    .flush_go(gpu_flush_go), .flush_busy(gpu_flush_busy),
    .first_band(tpass == 6'd0),
    .m_st(gpu_m_st),
    .blit_mode(blit_on), .blit_we(blit_we_w),
    .blit_word(sk_q), .blit_take(blit_take),
    .tri_go(tq_go),                      // from the queue's head (B2)
    .tx0(qx0), .ty0(qy0), .tx1(qx1), .ty1(qy1), .tx2(qx2), .ty2(qy2),
    .tc0(qc0), .tcxr(qcxr), .tcyr(qcyr), .tcxg(qcxg), .tcyg(qcyg),
    .tcxb(qcxb), .tcyb(qcyb), .tz0(qz0), .tzx(qzx), .tzy(qzy),
    .fb_we(gfb_we), .fb_waddr(gfb_a), .fb_wdata(gfb_d),
    .tri_id(q_tri), .t_tex(q_tex), .t_tint(q_tint), .t_tinton(q_tinton), .t_otint(q_otint), .t_span(q_span),
    .vis_a(visi[8:0]), .vis_q(vis_q),
    .gz_we(gz_we), .gz_wa(gz_wa), .gz_wd(gz_wd), .gz_n(gz_n),
    .gz_ra(gz_ra), .gz_q(gz_q),
    .t_blend(q_blend), .t_add(q_add), .t_oid(q_oid),
    .t_alpha(q_alpha), .t_page(q_page),
    .fog_rgb({f_rgb[23:19], f_rgb[15:11], f_rgb[7:3]}),
    .edge_rgb({e_rgb[23:19], e_rgb[15:11], e_rgb[7:3]}),
    .fog_near(f_near[15:0]),
    .fog_shift((f_shift[31] || f_shift > 32'd16) ? 5'd0 : f_shift[4:0]),
    .tex_we(tex_we), .tex_a(tex_a), .tex_d(tex_d),
    .zw_we(zw_we), .zw_addr(zw_addr), .zw_data(zw_data),
    .zw_clr(zw_clr), .zw_sh(zw_sh), .zw_tri(zw_tri));

  wire        req_ok_sd = (s_go == SD_READ[31:0] || s_go == SD_SAVE[31:0])
                          && !(s_len == 32'd0 || s_len > SD_MAX[31:0] ||
                               s_slot[31] || s_off[31] || s_dst[31] ||
                               s_dst + s_len > DMEM_WORDS[31:0]);
  // a save must hand its words over BEFORE the command goes out, so the
  // request pulse waits until the buffer is filled (state I_CSV)
  wire        card_req = ((st == I_CARD) && !c_busy && (s_go != 32'd0)
                          && req_ok_sd && (s_go != SD_SAVE[31:0]))
                       || (st == I_CSV2 && c_j == c_len_r);
  assign      sd_save = c_save_r;
  wire        card_ready;
  wire [15:0] card_nstage;
  wire [31:0] card_q;
  zcard u_card (
    .clk(clk), .rst_n(rst_n),
    .req(card_req), .slot(s_slot[15:0]), .off(s_off),
    .len(s_len[12:0]),
    .ready(card_ready), .n_stage(card_nstage), .raddr(c_i), .rdata(card_q),
    .c_req(sd_req), .c_slot(sd_slot), .c_off(sd_off), .c_len(sd_len),
    .c_we(sd_we), .c_data(sd_data), .c_done(sd_done));

  zsnd u_snd (
    .clk(clk), .rst_n(core_rst_n),
    .reg_we(st == I_AUC), .reg_idx(aui), .reg_data(dl_data),
    .tick(snd_tick), .sample(snd_sample), .busy(snd_busy),
    .aud_rd(st == I_AUD), .aud_a(audi[3:0]), .aud_q(aud_q),
    .frame_go(st == I_GK && tpass == 6'd0),
    .phase_rst(au_rst),
    .ev_we(ev_we), .ev_a(ev_a), .ev_d(ev_d),
    .wav_we(wav_we), .wav_ch(wav_ch), .wav_a(wav_a), .wav_d(wav_d));

  cram_fb u_fb (
    .clk(clk), .rst_n(rst_n), .ready(fb_ready),
    .wr_we(gfb_we), .wr_addr(gfb_a), .wr_data(gfb_d),
    .wr_stall(fb_stall), .wr_idle(fb_widle),
    .line_req(line_req), .line_no(line_no), .line_rdy(line_rdy),
    .px_addr(px_addr), .px_q(px_q),
    .ld_we(boot_cram_we), .ld_addr(boot_cram_addr), .boot_done(boot_done),
    .swp_en(sweep_en), .swp_k(k_eff),
    .ld_data(boot_cram_data), .ld_busy(boot_cram_busy),
    .dma_go(dma_go), .dma_chip1(b_run), .dma_addr(dma_addr),
    .dma_len(dma_len),
    .dma_ack(dma_ack), .dma_step(dma_step), .dma_data(dma_data),
    .dma_done(dma_done), .fb_front(),
    .swap_req(st == I_FIN), .swap_gate(swap_gate),
    .swap_pending(swap_pending),
    .c0_wait(c0_wait), .c1_wait(c1_wait),
    .c0_a(c0_a), .c0_dq_o(c0_dq_o), .c0_dq_oe(c0_dq_oe), .c0_dq_i(c0_dq_i),
    .c0_clk_en(c0_clk_en), .c0_adv_n(c0_adv_n), .c0_cre(c0_cre),
    .c0_ce_n(c0_ce_n), .c0_ce1_n(c0_ce1_n), .c0_we_n(c0_we_n), .c0_oe_n(c0_oe_n),
    .c0_ub_n(c0_ub_n), .c0_lb_n(c0_lb_n),
    .c1_a(c1_a), .c1_dq_o(c1_dq_o), .c1_dq_oe(c1_dq_oe), .c1_dq_i(c1_dq_i),
    .c1_clk_en(c1_clk_en), .c1_adv_n(c1_adv_n), .c1_cre(c1_cre),
    .c1_ce_n(c1_ce_n), .c1_ce1_n(c1_ce1_n), .c1_we_n(c1_we_n), .c1_oe_n(c1_oe_n),
    .c1_ub_n(c1_ub_n), .c1_lb_n(c1_lb_n));
  assign px_rgb = {px_q[14:10], px_q[14:12],     // 555 -> 888 replication,
                   px_q[9:5],   px_q[9:7],       // exactly display_rgb()
                   px_q[4:0],   px_q[4:2]};

  always @(posedge clk) begin
    frame_done <= 1'b0;
    gpu_flush_go <= 1'b0;   // one-clock pulse
    dma_go <= 1'b0;                     // one-clock request
    dma_we <= 1'b0;                     // one-clock DMEM write
    ml_new <= 1'b0;                     // one-clock words to zmesh
    ml_obj <= 1'b0;
    tex_we <= 1'b0;
    gz_we  <= 1'b0;
    ev_we <= 1'b0;
    gr_we <= 1'b0;
    wav_we <= 1'b0;
    card_we <= 1'b0;
    sd_sw_we <= 1'b0;
    if (card_we && ~&n_copy) n_copy <= n_copy + 8'd1;
    if (!core_rst_n) begin
      st <= I_IDLE; frame_no <= 0; busy <= 1'b0;
      dma_mesh <= 2'd0;
      dma_hi <= 1'b0; d_fin <= 1'b0; tpass <= 6'd0; au_rst <= 1'b0;
      m_clr <= 0; m_walk <= 0; m_idle <= 0;
      m_stall <= 0; m_seq <= 0; m_blkd <= 0; m_skp <= 0;
    end else begin
      // THE METER TICKS ONLY DURING THE PAINT, and zeroes at the frame's
      // first band so each frame's numbers stand alone.
      au_rst <= 1'b0;                     // a pulse: I_ARC raises it
      if (st == I_GK && tpass == 6'd0) begin
        m_clr <= 0; m_walk <= 0; m_idle <= 0;
        m_stall <= 0; m_seq <= 0; m_blkd <= 0; m_skp <= 0;
        m_evload <= 0;   // m_evfire is a RUNNING total: the audio
                         // ticks happen after frame_done, so a
                         // per-frame counter is zeroed before it
                         // can ever be read
      end else if (st == I_GK || st == I_GW) begin
        if (gpu_m_st == 2'd1) m_clr   <= m_clr   + 32'd1;
        if (gpu_m_st == 2'd3) m_walk  <= m_walk  + 32'd1;
        if (gpu_m_st == 2'd2) m_idle  <= m_idle  + 32'd1;
        if (fb_stall)         m_stall <= m_stall + 32'd1;
        if (seq_m_act)        m_seq   <= m_seq   + 32'd1;
        if (seq_m_blk)        m_blkd  <= m_blkd  + 32'd1;
        if (seq_m_skp)        m_skp   <= m_skp   + 32'd1;
      end
      if (ev_we)        m_evload <= m_evload + 32'd1;
      if (snd_busy) m_evfire <= m_evfire + 32'd1;
      // the mover's data path runs alongside the states below: CRAM
      // hands over 16 bits at a time, DMEM takes 32
      // boot 45: the pairing accepts EXACTLY dma_len halves per burst
      // and drops boundary strays -- w63 was landing an extra
      // {h128,h128} pair at every burst handoff while the words on
      // either side stayed perfect: not the chip, the LISTENER.
      if (dma_step && !b_run && st == I_DWAIT && bh != dma_len) begin
        bh <= bh + 8'd1;
        if (!dma_hi) begin dma_lo <= dma_data; dma_hi <= 1'b1; end
        else begin
          dma_word <= {dma_data, dma_lo};
          dma_we   <= 1'b1;
          dma_hi   <= 1'b0;
        end
      end
      // ---- the pump's half of the stream: pairs into the skid ---------
      if (dma_step && b_run) begin
        if (!b_hi) begin b_lo <= {16'd0, dma_data}; b_hi <= 1'b1; end
        else begin
          skid[sk_w[6:0]] <= {dma_data, b_lo[15:0]};
          sk_w <= sk_w + 8'd1;
          b_hi <= 1'b0;
        end
      end
      sk_wd <= dma_step && b_run && b_hi;
      sk_n  <= sk_n + {7'd0, sk_wd} - {7'd0, blit_take};
      if (blit_take) sk_r <= sk_r + 8'd1;
      if (b_run) begin
        // !dma_ack: re-pulsing in the ack cycle latched a GHOST request
        // (b_infl lands a cycle late) which fired after the stream ended
        // and hosed DMEM's zero page through the mover's pairing path
        if (!b_infl && !dma_ack && b_left != 18'd0 && skid_room) begin
          dma_len <= 8'd128;            // 64 words; cram_burst's splitter
          dma_go  <= 1'b1;              // makes any span legal (boot 42)
        end
        if (dma_ack)  b_infl <= 1'b1;
        if (dma_done && b_infl) begin
          b_infl   <= 1'b0;
          dma_addr <= dma_addr + 23'd128;
          b_left   <= b_left - 18'd64;
        end
        if (b_left == 18'd0 && sk_n == 8'd0) b_run <= 1'b0;
      end
      // ---- the pick register's ear: every z commit, one compare ----
      if (seq_item) begin
        cur_tri <= tri_ctr;
        tri_ctr <= tri_ctr + 16'd1;
      end else if (seq_skip) begin
        // an object the band bin skipped still spent its places in the
        // walk -- the law counted them, so the silicon must too
        tri_ctr <= tri_ctr + {5'd0, seq_skip_n};
      end
      if (zw_we && watch_en && zw_addr == watch_addr) begin
        pick_z  <= zw_data;
        pick_id <= zw_clr ? 32'hFFFFFFFF : {16'd0, zw_tri};
        // ...and the plate's own answer, taken ONLY on the clear. The
        // ear was already here; it simply had nothing to hear.
        if (zw_clr) pick_sh <= zw_sh;
      end
      if (dma_we) begin                 // one cart word committed
        dma_dst  <= dma_dst + 1'b1;
        dma_left <= dma_left - 1'b1;
      end
      // THE MOVER'S CURSOR, AND ONLY THE MOVER'S. This was ungated, and
      // dma_addr is SHARED with the backdrop pump -- so a pump burst
      // completing one cycle after a band re-armed added dma_len halves
      // to the address the arm had just written, and that band streamed
      // from 64 words too far into the plate. Measured: the silicon's
      // band 1 is the law's band 1 rolled by exactly -64 words, 99.4%
      // identical, which is one burst precisely.
      //   It needed a backdrop AND two objects with different meshes to
      // show, because that is what moves the sequencer's per-band timing
      // enough to land a done on the wrong side of the arm -- so every
      // single-object backdrop cart in the tree (hall, room) missed it.
      //   The pump advances its own cursor under b_infl below; b_run says
      // which engine owns dma_addr, and the two are disjoint by
      // construction (the mover runs before the paint, the pump during).
      if (dma_done && !b_run) begin
        dma_addr <= dma_addr + {14'd0, dma_len};
        d_fin    <= 1'b1;
      end else if (dma_done) begin
        d_fin    <= 1'b1;
      end
      case (st)
      I_IDLE: if (start && fb_ready) begin   // wait out the chip config
        busy <= 1'b1; pad_l <= pad;
        st <= trapped ? I_GK : I_WF;      // vm.py: trapped frame() is a no-op
      end
      I_WF: begin st <= I_WP;             // dmem[REG_FRAME] <= frame_no
        k_lat <= frame_no[9:6];           // the cart sees this same
      end                                 // number: K stays in sync
      I_WP: begin frame_no <= frame_no + 1'b1; st <= I_VK; end  // dmem[REG_PAD]
      I_VK: st <= I_VW;                   // vm start pulse
      I_VW: if (!vm_running) begin        // halt, fuel out, or trap:
        dsel <= 3'd0; swept2 <= 1'b0;     // first the mover, then render
        dma_two <= 1'b0;
        st <= I_DRD;
      end
      I_DRD: st <= I_DCK;                 // request cell dsel presented
      I_DCK: begin                        // ...and readable this cycle
        case (dsel)
          4'd0: d_src <= dl_data;
          4'd1: d_dst <= dl_data;
          4'd2: d_len <= dl_data;
          4'd3: d_go <= dl_data;
          4'd4: d_bg <= dl_data;            // the backdrop source
          4'd5: d_wp <= dl_data;            // the probe cell
          4'd6: d_px <= dl_data;            // the watched pixel
          4'd7: d_py <= dl_data;
          4'd8: s_slot <= dl_data;          // ...and the card's five
          4'd9: s_off <= dl_data;
          4'd10: s_dst <= dl_data;
          4'd11: s_len <= dl_data;
          4'd12: s_go <= dl_data;
          5'd13: o_src <= dl_data;         // ...and the overlay's four
          5'd14: o_dst <= dl_data;
          5'd15: o_len <= dl_data;
          5'd16: o_go <= dl_data;
          5'd17: f_rgb <= dl_data;         // ...and the fog's three
          5'd18: f_near <= dl_data;
          6'd19: f_shift <= dl_data;
          6'd20: f_lod <= dl_data;
          6'd34: e_rgb <= dl_data;         // ...and the outline's colour
          6'd35: l_dir <= dl_data[23:0];   // ...and the light's three
          6'd36: l_amb <= (dl_data[31:0] > 32) ? 6'd32 : dl_data[5:0];
          6'd37: l_dif <= (dl_data[31:0] > 32) ? 6'd32 : dl_data[5:0];
          6'd38: d_seg <= dl_data;         // ...and the segment window
          6'd39: m2_src <= dl_data;        // ...and the second request
          6'd40: m2_dst <= dl_data;
          6'd41: m2_len <= dl_data;
          6'd42: m2_go  <= dl_data;
          // ---- the gaze: n, then eight words, judged as they arrive ----
          6'd43: begin
            gz_on  <= (dl_data != 32'd0);
            gz_cnt <= (dl_data > 32'd8) ? 4'd8 : dl_data[3:0];
            gz_n   <= 4'd0;
            gz_cut <= 1'b0;
          end
          6'd52: d_olx <= dl_data;         // ...and where the list is
          6'd44, 6'd45, 6'd46, 6'd47, 6'd48, 6'd49, 6'd50, 6'd51:
            if (gz_ok) begin
              gz_we <= 1'b1; gz_wa <= gz_n[2:0]; gz_wd <= gz_yx;
              gz_last <= gz_yx;
              gz_n <= gz_n + 4'd1;
            end else gz_cut <= 1'b1;
          default: co_reg[dsel - 6'd21] <= dl_data;
        endcase
        if (dsel == 6'd52) st <= swept2 ? I_ML : I_DCLR;   // (frontier 20: the
                                          // cart meshes, once DMEM is final)
        else begin dsel <= dsel + 1'b1; st <= I_DRD; end
      end
      I_DCLR:                             // GO clears whether or not the
        if (d_go == 0) st <= dma_two ? I_OVL : I_D2;   // request was
        else if (!req_ok) st <= dma_two ? I_OVL : I_D2; // usable (spec)
        else begin
          dma_addr <= CRAM_CART_BASE[22:0] + {eff_dma[21:0], 1'b0};
          dma_dst  <= {{(IMEM_BITS - 14){1'b0}}, d_dst[13:0]};
          dma_left <= d_len;
          dma_hi   <= 1'b0;
          dma_imem <= 1'b0;
          dma_ret  <= 1'b0;
          st <= I_DBURST;
        end
      I_DBURST: if (!dma_imem || (of_empty && !prog_busy && !od_we && !od_g)) begin
                                          // (an overlay: once its queue drains)
                                          // 64 words per request; the
        bh <= 8'd0;                       // fresh half-count per burst
        dma_len <= (dma_left >= 32'd64)   // splitter serves it legally
                   ? 8'd128 : {dma_left[6:0], 1'b0};
        dma_go  <= 1'b1;
        d_fin   <= 1'b0;
        st <= I_DWAIT;
      end
      I_DWAIT: if (d_fin && !dma_hi && !dma_we) begin
        d_fin <= 1'b0;                    // every half of this burst is
        st <= (dma_left == 0) ? (dma_mesh != 2'd0 ? I_MSTR :
                                 dma_ret ? I_OCLR : dma_two ? I_OVL : I_D2)
                              : I_DBURST;           // landed now
        if (dma_left == 0 && dma_mesh != 2'd0) ml_str <= ml_str + 3'd1;
      end
      // ---- the cart mesh's loader (see its registers, above) ----------
      I_ML: begin
        ml_o <= 10'd0; ml_uv <= 13'd0; ml_uf <= 13'd0; msel <= 3'd0;
        ml_e <= ol_base + 14'd1; ml_new <= 1'b1; dma_mesh <= 2'd0;
        st <= I_MRD;
      end
      I_MRD: st <= I_MCK;                 // the word presented
      I_MCK: begin                        // ...and readable this cycle
        st <= I_MRD;
        case (msel)
          3'd0: begin
            ml_n <= ol_long
                    ? ((dl_data > OLX_MAX) ? OLX_MAX[9:0] : dl_data[9:0])
                    : ((dl_data > OL_MAX)  ? OL_MAX[9:0]  : dl_data[9:0]);
            msel <= 3'd1;
            if (dl_data == 32'd0) st <= I_TXP;
          end
          3'd1: begin ml_mesh <= dl_data; msel <= 3'd2; end
          3'd2:                           // its flags: a cart mesh, its
            if (dl_data[14] && !ml_mesh[31] &&         // descriptor in DMEM?
                ml_mesh <= DMEM_WORDS - CMESH_WORDS) msel <= 3'd3;
            else begin ml_obj <= 1'b1; ml_okr <= 1'b0; st <= I_MNX; end
          3'd3: begin ml_d0 <= dl_data; msel <= 3'd4; end
          3'd4: begin ml_d1 <= dl_data; msel <= 3'd5; end
          3'd5: begin ml_d2 <= dl_data; msel <= 3'd6; end
          3'd6: begin ml_d3 <= dl_data; msel <= 3'd7; end
          default: begin ml_d4 <= dl_data; st <= I_MCHK; end
        endcase
      end
      I_MCHK: begin                       // the verdict (gpu.py _cart_mesh)
        ml_obj <= 1'b1; ml_okr <= ml_valid;
        if (ml_valid) begin
          ml_uv <= ml_uv + {4'd0, ml_nv[8:0]};
          ml_uf <= ml_uf + {3'd0, ml_nf[9:0]};
          ml_str <= 3'd1;
          st <= I_MSTR;
        end else st <= I_MNX;
      end
      I_MSTR:                             // its streams, one burst run each
        if (ml_str == 3'd4) begin dma_mesh <= 2'd0; st <= I_MNX; end
        else if (ml_len == 32'd0) ml_str <= ml_str + 3'd1;
        else begin
          dma_addr <= CRAM_CART_BASE[22:0] + {ml_eff[21:0], 1'b0};
          dma_left <= ml_len;
          dma_hi   <= 1'b0;
          dma_imem <= 1'b0;
          dma_ret  <= 1'b0;
          dma_mesh <= ml_str[1:0];
          st <= I_DBURST;
        end
      I_MNX: begin
        ml_o <= ml_o + 10'd1; ml_e <= ml_e + OL_STRIDE[13:0]; msel <= 3'd1;
        st <= (ml_o + 10'd1 == ml_n) ? I_TXP : I_MRD;
      end
      // ---- the second request (spec.DMA2_*): the same engine, again --
      I_D2: begin
        d_src <= m2_src; d_dst <= m2_dst; d_len <= m2_len; d_go <= m2_go;
        dma_two <= 1'b1;
        st <= I_DCLR;
      end
      // ---- overlays: the same burst, into PROGRAM space ---------------
      // Safe by the frame model, not by a rule: the VM has halted and the
      // next frame starts at PC 0, so a cart cannot overwrite the code it
      // is standing on.
      I_OVL:
        if (o_go == 32'd0) st <= I_CARD;
        else if (o_len == 32'd0 || o_len > OVL_MAX[31:0] || o_src[31] ||
                 o_dst[31] || eff_ovl[31] ||
                 eff_ovl + o_len > CRAM_WORDS[31:0] ||
                 o_dst + o_len > IMEM_WORDS[31:0]) st <= I_OCLR;
        else begin
          dma_addr <= CRAM_CART_BASE[22:0] + {eff_ovl[21:0], 1'b0};
          dma_dst  <= o_dst[IMEM_BITS-1:0];
          dma_left <= o_len;
          dma_hi   <= 1'b0;
          dma_imem <= 1'b1;
          dma_ret  <= 1'b1;
          st <= I_DBURST;
        end
      I_OCLR: if (of_empty && !prog_busy && !od_we && !od_g) begin
        dma_imem <= 1'b0; st <= I_CARD;  // (the last queued word has landed)
      end

      // ---- the card, at the mover's instant (spec.SD_*) ---------------
      // The wait is counted in FRAMES here, which is the whole of the
      // determinism: the staging buffer may have been full for ages, but
      // nothing is visible to the cart until the frame the law names.
      I_CARD:
        if (c_busy) begin
          if (~&c_age) c_age <= c_age + 8'd1;
          if (card_ready && !c_seen) begin   // the card finished HERE --
            c_seen <= 1'b1;                  // whatever the law says the
            c_lat  <= c_age + 8'd1;          // deadline is
          end
          if (c_wait == 6'd1) begin       // this is the frame it lands,
            c_i <= 13'd0;                 // and it lands whatever is in
            c_busy <= c_save_r ? 1'b0 : c_busy;
            st <= c_save_r ? I_CCLR : I_CRD;   // a save has nothing to
          end else begin                       // copy back -- see I_CRD
            c_wait <= c_wait - 6'd1;
            st <= (s_go == 32'd0) ? I_CGO : I_CDG;
          end
        end else if (s_go == 32'd0) st <= I_CDG;
        else if (!req_ok_sd) st <= I_CCLR;
        else begin                        // latched: a cart rewriting the
          c_age    <= 8'd0;               // cells now changes nothing
          c_seen   <= 1'b0;
          c_slot_r <= s_slot[15:0];
          c_off_r  <= s_off;
          c_dst_r  <= s_dst[13:0];
          c_len_r  <= s_len[12:0];
          c_busy   <= 1'b1;
          c_save_r <= (s_go == SD_SAVE[31:0]);
          c_wait   <= SD_LATENCY[5:0];
          c_j      <= 13'd0;
          st <= (s_go == SD_SAVE[31:0]) ? I_CSV : I_CDG;
        end
      I_CGO: st <= I_CDG;                 // re-assert GO: the cart does
                                          // not get to cancel physics
      I_CCLR: st <= I_CDG;                // refused: GO cleared, no move
      // the counters, every frame, so a probe cart can say WHERE a card
      // read stops instead of us inferring it from a colour
      // a save reads DMEM at the LATCH and hands each word to the card's
      // buffer, so what lands is what the cart had when it asked -- a
      // cart that scribbles over the source mid-flight cannot corrupt it
      I_CSV: st <= I_CSV2;              // registered-read wait
      I_CSV2: begin
        if (c_j != c_len_r) begin
          sd_sw_we <= 1'b1;
          // APF asks for word 0 (measured: its first address IS the one
          // we give it) and captures the slot ABOVE it -- stable across
          // both a combinational and a registered read, so this is the
          // bridge's own pipelining, not ours. Fill one slot up and every
          // word lands under the address that fetches it.
          sd_sw_a  <= c_j[9:0] + 10'd1;
          sd_sw_d  <= dl_data;
          c_j <= c_j + 13'd1;
          st <= I_CSV;
        end else st <= I_CDG;           // filled: card_req fires here
      end
      I_CDG: st <= I_CDG2;
      I_CDG2: st <= I_CDG3;
      I_CDG3: st <= I_CDG4;
      I_CDG4: begin                       // the movers are done: sweep
        swept2 <= 1'b1;                   // again so the paint sees what
        dsel <= 6'd0;                     // they left, not what they found
        st <= I_DRD;
      end
      // The legislated frame has come, so the data lands -- ready or not.
      //
      // This state used to wait on card_ready, on the reasoning that a
      // slow card should stretch the frame rather than hand over short
      // data. That reasoning built an UNBOUNDED WAIT ON AN EXTERNAL
      // DEVICE into the frame machine: on glass the first card request
      // never completed, frame_done never fired, and the console showed
      // black forever. No simulation could catch it -- card_model.v
      // always completes, so the model that made the timing test harsh
      // also made failure impossible to reach.
      //
      // The law lands at frame N + SD_LATENCY unconditionally, and now so
      // does this. A card that misses the deadline yields wrong pixels,
      // which spec.py already names as a fault to find on glass. Wrong
      // pixels can be seen and debugged; a hung console cannot.
      I_CRD: st <= I_CWR;                 // (card_ready is diagnostic now)
      I_CWR: begin                        // ...and commit it to DMEM
        card_we <= 1'b1;
        st <= I_CWR2;
      end
      I_CWR2: begin
        c_i <= c_i + 13'd1;
        if (c_i + 13'd1 == c_len_r) begin
          c_busy <= 1'b0;
          st <= I_CCLR;                   // landed: clear GO, the protocol
        end else st <= I_CWR;
      end
      I_TXP: st <= I_TXP2;              // present TEX_PAGE
      I_TXP2: st <= I_TXP3;
      I_TXP3: begin                     // which slot this load fills
        // out of range reads as page 0 (spec.tex_page): TEX_PAGES is
        // 24 and the field holds 0..31, so this cannot just mask
        t_slot <= (dl_data[4:0] < TEX_PAGES[4:0]) ? dl_data[4:0] : 5'd0;
                                        // every cart that
        st <= I_TXC;                    // never heard of pages says 0
      end
      I_TXC: st <= I_TXC2;              // present TEX_SRC
      I_TXC2: st <= I_TXR;
      I_TXR:
        if (dl_data == 32'd0 || dl_data[31] ||
            dl_data[30:0] + 31'd680 > DMEM_WORDS[30:0]) st <= I_GK;
        else begin
          t_src <= dl_data[13:0]; t_i <= 10'd0; st <= I_TXW;
        end
      I_TXW: st <= I_TXD;               // registered-read wait
      I_TXD: begin                      // low texel this cycle...
        tex_we <= 1'b1; tex_a <= tslot_base + {4'd0, t_i, 1'b0};
        tex_d <= dl_data[14:0];
        st <= I_TXD2;
      end
      I_TXD2: begin                     // ...high texel the next
        tex_we <= 1'b1; tex_a <= tslot_base + {4'd0, t_i, 1'b1};
        tex_d <= dl_data[30:16];
        t_i <= t_i + 10'd1;
        st <= (t_i == 10'd679) ? I_GK : I_TXW;
      end
      I_GK: begin
        seq_ran <= 1'b0; gpu_flushed <= 1'b0;
        watch_en <= !d_px[31] && !d_py[31] &&
                    (d_px < 32'd320) && (d_py < 32'd288);
        watch_addr <= {d_py[8:0], 8'd0} + {2'd0, d_py[8:0], 6'd0}
                      + {7'd0, d_py[8:0], 1'b0} + {8'd0, d_px[8:0]};
        // tri_ctr DOES reset per band: each band replays the identical
        // submission sequence, so a triangle's index is the same number
        // whichever band it lands in -- which is exactly what PICK_ID
        // means. The pick ANSWER must not reset, though: the watched
        // pixel lives in one band only, and zeroing this on the second
        // pass would throw away a hit the first pass found.
        tri_ctr <= 16'd0; cur_tri <= 16'd0;
        if (tpass == 6'd0) begin
          pick_id <= 32'hFFFFFFFF; pick_z <= 16'hFFFF; pick_sh <= 1'b0;
        end
        // the backdrop: valid source arms the pump for this frame's clear
        blit_on <= 1'b0;
        b_run   <= 1'b0;
        if (!d_bg[31] && d_bg != 32'd0 && !eff_bg[31] &&
            eff_bg + BG_WORDS <= CRAM_WORDS) begin
          blit_on  <= 1'b1;
          b_run    <= 1'b1;
          b_infl   <= 1'b0;
          b_hi     <= 1'b0;
          sk_w     <= 8'd0; sk_r <= 8'd0;
          sk_n     <= 8'd0; sk_wd <= 1'b0;
          // one band's slice of the backdrop, at its own offset: the
          // pump streams row-major, so band p starts p*BAND_WORDS in
          b_left   <= BAND_WORDS[17:0];
          dma_addr <= CRAM_CART_BASE[22:0] + {eff_bg[21:0], 1'b0} + band_half;
        end
        st <= I_GW;
      end
      I_GW: begin                         // band painted when the sequencer
        if (seq_done) seq_ran <= 1'b1;    // is done AND its last triangle
        // THE BAND'S COLOUR LIVES ON DIE NOW, so a finished band has to be
        // streamed to CRAM before the next one overwrites the buffer.
        // Only the frame's LAST band flushes standalone; every other
        // band's colour rides out on the next band's clear.
        if ((seq_ran || seq_done) && gpu_rdy && fb_widle && !gpu_flushed
            && tpass == TROWS[5:0] - 6'd1)
          begin gpu_flush_go <= 1'b1; gpu_flushed <= 1'b1; end
        else if ((seq_ran || seq_done) && !gpu_flush_go && !gpu_flush_busy
                 && gpu_rdy && fb_widle
                 && (tpass != TROWS[5:0] - 6'd1 || gpu_flushed)) begin
          gpu_flushed <= 1'b0;
          if (tpass != TROWS[5:0] - 6'd1) begin
            tpass <= tpass + 6'd1;        // the next band: I_GK re-pulses
            st <= I_GK;                   // start, and zseq walks the same
          end else begin                  // object list again from the top
            tpass <= 6'd0;                // ready for the next FRAME -- the
            aui <= 0;                     // one place this is cleared, so
            au_addr <= AU_BASE[13:0];     // the three paths INTO I_GK do
            pws <= 2'd0; st <= I_PW;      // not each need to remember
          end
        end
      end
      I_AUW: st <= I_AUC;                 // registered-read wait
      I_AUC: begin                        // one AU word into the engine
        // the odd words are ctrl: bits 10:8 name this voice's page. Read
        // HERE, from the register, and never from an event -- a page is
        // 2 Kbit copied between frames, not a value a sample can change.
        if (aui[0]) wpg[aui[4:1]] <=
            dl_data[AU_PAGE_SHIFT + 2 : AU_PAGE_SHIFT];
        aui <= aui + 1'b1;
        au_addr <= au_addr + 1'b1;
        if (aui == 5'd31) begin
          evi <= 8'd0; au_addr <= AU_EV_BASE[13:0]; st <= I_EVW;
        end else st <= I_AUW;
      end
      I_EVW: st <= I_EVC;                 // registered-read wait
      I_EVC: begin                        // one event word into the engine
        ev_we <= 1'b1; ev_a <= evi; ev_d <= dl_data;
        evi <= evi + 8'd1;
        au_addr <= au_addr + 1'b1;
        st <= (evi == 2 * AU_EV_MAX) ? I_ARW : I_EVW;
      end
      I_ARW: st <= I_ARC;                 // registered-read wait
      I_ARC: if (dl_data != 32'd0) begin  // a cold start asked for
               au_rst <= 1'b1; st <= I_ARZ;
             end else st <= I_GRP;
      I_ARZ: st <= I_GRP;                 // ...and the cell cleared
      I_PW:                             // the pick's answer, THREE cells
        if (pws != 2'd2) pws <= pws + 2'd1;   // PICK_ID, PICK_Z, PICK_SH
        else begin visi <= 10'd0; st <= I_VIS; end
      // ---- THE SENSOR'S ANSWER (spec.VIS_BASE) -----------------------
      // OL_MAX cells, one an object, straight out of the rasterizer's
      // own tally. A frame late by construction -- the count is not
      // finished until the last band is, same as the pick.
      // ONE CLOCK BEHIND ITS ADDRESS. The tally moved off a LUTRAM
      // with a combinational read onto an M10K with a registered one
      // (832 ALM to ~70), so visi PRESENTS an address on its clock and
      // the word arrives on the next. It therefore runs 0..OL_MAX --
      // one more beat than there are cells -- writing cell visi-1 on
      // every beat but the first.
      I_VIS: begin
        visi <= visi + 10'd1;
        // 512 beats for the tallies, then GAZE_MAX for the gaze's answers
        if (visi == 10'd511 + GAZE_MAX[9:0]) begin
          audi <= 5'd0; st <= I_AUD;
        end
      end
      // ---- THE MIXER'S ANSWER (spec.AUD_BASE) ------------------------
      // One word a voice, and a frame late for the same reason as the
      // pick and the pixel count: the total is not finished until the
      // frame's last sample is. It reads the bank the mixer is NOT
      // filling, so nothing has to be timed against the audio clock.
      I_AUD: begin
        audi <= audi + 5'd1;
        if (audi == AU_CHANNELS[4:0]) st <= I_AUW;
      end
      // ---- THE GRADE TABLE (spec.GRADE_SRC) --------------------------
      // 0 or a pointer that would run past DMEM leaves the table alone
      // and the glass ungraded, which is what every cart written before
      // this one does without knowing it.
      I_GRP: st <= I_GRR;
      I_GRR: st <= I_GRR2;
      I_GRR2:
        if (dl_data == 32'd0 || dl_data[31]
            || dl_data[13:0] > (DMEM_WORDS[13:0] - GRADE_WORDS[13:0]))
          begin gr_on <= 1'b0; st <= I_WVC; end
        else begin
          gr_on <= 1'b1;
          g_addr <= dl_data[13:0]; gi <= 6'd0; st <= I_GRW;
        end
      I_GRW: st <= I_GRC;               // registered-read wait
      I_GRC: begin                      // one level into the video head
        gr_we <= 1'b1; gr_a <= gi[4:0]; gr_d <= dl_data[23:0];
        gi <= gi + 6'd1;
        g_addr <= g_addr + 1'b1;
        st <= (gi == GRADE_WORDS[5:0] - 6'd1) ? I_WVC : I_GRW;
      end
      I_WVC: st <= I_WVC2;              // present WAV_SRC
      I_WVC2: st <= I_WVR;
      I_WVR:                            // 0 or negative: the whole bank
        if (dl_data == 32'd0 || dl_data[31]) st <= I_FIN;
        else begin w_src <= dl_data[13:0]; w_ch <= 4'd0; st <= I_WVN; end
      I_WVN: begin                      // this voice's page, or skip it
        w_i <= 6'd0;
        if (w_bad) begin                // past DMEM: keep what it had,
          w_ch <= w_ch + 4'd1;          // exactly WAV_SRC's old rule,
          st <= (w_ch == AU_CHANNELS[3:0] - 4'd1) ? I_FIN : I_WVN;
        end else st <= I_WVW;
      end
      I_WVW: st <= I_WVD;               // registered-read wait
      I_WVD: begin                      // one word: four signed samples
        wav_we <= 1'b1; wav_ch <= w_ch; wav_a <= w_i; wav_d <= dl_data;
        w_i <= w_i + 6'd1;
        if (w_i == WAV_WORDS[5:0] - 6'd1) begin
          w_ch <= w_ch + 4'd1;
          st <= (w_ch == AU_CHANNELS[3:0] - 4'd1) ? I_FIN : I_WVN;
        end else st <= I_WVW;
      end
      I_FIN: begin frame_done <= 1'b1; busy <= 1'b0; st <= I_IDLE; end
      default: st <= I_IDLE;
      endcase
    end
  end

  assign meter = {m_evfire, m_evload, m_skp, m_blkd, m_seq, m_stall, m_idle, m_walk, m_clr};
endmodule
`default_nettype wire
