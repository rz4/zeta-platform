// zvm.v -- the Zeta CPU in silicon. Its behavior is DEFINED by zeta/vm.py;
// every branch here mirrors a branch there, and `zeta cross` holds the two
// bit-equal. All constants come from params.vh, generated from zeta/spec.py
// -- this file owns no numbers.
//
// Memories are BLOCK-RAM SHAPED: IMEM and DMEM reads are synchronous
// (address at one edge, data after the next), so Quartus can map them.
// The stack lives in registers. Cost: one cycle per instruction, two for
// load/loadi. Fuel counts INSTRUCTIONS, exactly as vm.py counts them.
`default_nettype none

module zvm #(
    parameter PAW = 15                // program address width: spec.IMEM_BITS
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,        // pulse: run one frame from pc 0
    output reg         running,
    output reg         trapped,      // sticky: a trapped core skips frames
    // external DMEM port (boot writes, pad latch, GPU display-list reads);
    // reads are REGISTERED: data for ext_addr arrives after the next edge
    input  wire        ext_we,       // honored only while the VM is idle
    input  wire [13:0] ext_addr,
    input  wire [31:0] ext_wdata,
    output wire [31:0] ext_rdata,
    // THE PROGRAM IS IN THE SRAM (frontier 19): a miss asks zimem for its
    // line, and the refill arrives a word at a time
    output reg            ic_req,
    output reg  [PAW-1:2] ic_line,
    input  wire           ic_we,
    input  wire [1:0]     ic_wo,
    input  wire [31:0]    ic_wd,
    input  wire           ic_done,
    input  wire           ic_flush
);
  `include "params.vh"
  generate if (PAW != IMEM_BITS) begin : paw_check
    PAW_must_equal_IMEM_BITS_from_params_vh u_fail();   // (an elaboration error)
  end endgenerate

  // ---- THE INSTRUCTION CACHE (frontier 19) --------------------------------
  // 1,024 words, direct-mapped, four-word lines: 256 lines, a 5-bit tag
  // each. Measured on the law's own fetches over 2,400 frames of real play,
  // the worst frame missed 1,144 times -- 29,744 clocks, 3.4% of a frame.
  // A cache changes WHEN an instruction arrives, never what it does: the
  // cross holds the result bit-equal to vm.py, which has no cache at all.
  localparam CI = 10;                       // index bits: 1,024 words
  (* ramstyle = "M10K" *) reg [31:0] cdata [0:(1 << CI)-1];
  reg [PAW-CI-1:0] ctag [0:(1 << (CI-2))-1];
  reg [(1 << (CI-2))-1:0] cval;             // valid bits: flops, cleared at once
  reg [PAW-CI-1:0] tq;                      // the tag read beside iq
  reg              vq;                      // ...and its valid bit
  reg [PAW-1:0]    fa_r;                    // the address iq was fetched from
  wire hit = vq && (tq == fa_r[PAW-1:CI]);
  initial cval = {(1 << (CI-2)){1'b0}};
  reg [31:0] dmem [0:DMEM_WORDS-1];
`ifdef ZETA_BAKE_CART
  initial $readmemh("cart_dmem.hex", dmem);   // deploy bakes the cart in;
`endif                                        // sim boots over the port
  // ---- THE STACK DIET ----------------------------------------------------
  // The law's stack is 64 words deep, but a stack machine only ever touches
  // its top two: every op reads tos/nos and pushes or pops one (storei
  // pops two). Held as registers that was a 64x32 file with TWO write
  // ports (swap writes both tops), three write indices and two variable
  // read ports -- 2,048 flops and ~15,900 ALUTs of crossbar, 58% of the
  // whole machine for a VM this small. So the top two ARE registers, and
  // everything beneath them lives in one M10K, exactly the shape the paint
  // FIFO was cured into at boot 62.
  reg [31:0] t0, t1;                 // tos and nos themselves
  reg [31:0] sbody [0:STACK_MAX-1];  // stack[i] for i <= sp-3
  reg [31:0] sq;                     // the body's registered read
  reg        fwd_v;                  // ...forwarded when that read collided
  reg [31:0] fwd_d;                  // with the same cycle's push
  wire [31:0] below = fwd_v ? fwd_d : sq;
  reg [6:0]  sp;
  reg [IMEM_BITS-1:0] rstack [0:RSTACK_MAX-1];  // call/ret return addresses only;
  reg [4:0]  rsp;                      // resets every frame, like vm.py's rs
  reg [IMEM_BITS-1:0] pc;
  reg [16:0] fuel;   // sized to FUEL's RANGE, not to its value
  reg [31:0] iq;                     // fetched instruction
  reg [31:0] dq;                     // DMEM port A data (VM loads)
  reg [31:0] eq;                     // DMEM port B data (ext reads)
  reg        ld_replace;             // pending load: 1 = loadi (replace tos)
  assign ext_rdata = eq;

  localparam V_FETCH = 3'd0, V_EXEC = 3'd1, V_LOAD = 3'd2, V_ST2 = 3'd3,
             V_MISS = 3'd4;                 // waiting on a line from the SRAM
  reg [2:0] vst;

  wire [7:0]  op  = iq[31:24];
  wire signed [31:0] imm = {{8{iq[23]}}, iq[23:0]};
  wire signed [31:0] tos = t0;            // b of a binary op (popped first)
  wire signed [31:0] nos = t1;            // a
  wire signed [63:0] prod = nos * tos;    // operands extend to 64 bits
  wire imm_bad_addr = (imm < 0) || (imm >= DMEM_WORDS);
  wire tos_bad_addr = (tos < 0) || (tos >= DMEM_WORDS);
  wire imm_bad_sh   = (imm < 0) || (imm > 31);
  wire jz_taken = (op == OP_JZ) && (sp != 0) && (tos == 32'd0);
  wire ret_taken = (op == OP_RET) && (rsp != 0);
  wire [IMEM_BITS-1:0] rtgt = rstack[rsp - 1'b1];
  // vm.py checks 0 <= pc < IMEM_WORDS after every step: running off the end
  // of IMEM this instruction is a trap (its effects still apply, as there)
  wire pc_over = (pc == IMEM_WORDS[IMEM_BITS-1:0] - 1'b1) &&
                 !(op == OP_HALT || op == OP_JMP || jz_taken ||
                   op == OP_CALL || ret_taken);
  wire [IMEM_BITS-1:0] pc_seq = pc + 1'b1;

  // synchronous read addresses, presented combinationally, latched each edge
  wire [IMEM_BITS-1:0] fetch_addr = (vst == V_EXEC && op == OP_JMP) ? imm[IMEM_BITS-1:0] :
                           (vst == V_EXEC && op == OP_CALL) ? imm[IMEM_BITS-1:0] :
                           (vst == V_EXEC && jz_taken)     ? imm[IMEM_BITS-1:0] :
                           (vst == V_EXEC && ret_taken)    ? rtgt :
                           (vst == V_EXEC)                 ? pc_seq :
                                                             pc;
  wire [13:0] dread_addr = (op == OP_LOADI) ? tos[13:0] : imm[13:0];

  // This VM retires ONE INSTRUCTION PER CYCLE (vst sits in V_EXEC), so a
  // pop needs the word beneath nos on the very next edge -- the body read
  // must therefore be addressed from the sp this cycle is about to become,
  // not the one it has. That is the whole reason sp_nxt exists.
  wire binop = (op == OP_ADD) || (op == OP_SUB) || (op == OP_MUL) ||
               (op == OP_MULQ) || (op == OP_AND) || (op == OP_OR) ||
               (op == OP_XOR) || (op == OP_LT) || (op == OP_EQ);
  wire ex = running && (vst == V_EXEC) && (fuel != 0) && hit;
  wire do_push = ex && ((op == OP_PUSH && sp != STACK_MAX) ||
                        (op == OP_DUP  && sp != 0 && sp != STACK_MAX) ||
                        (op == OP_OVER && sp >= 2 && sp != STACK_MAX));
  wire do_lpush = running && (vst == V_LOAD) && !ld_replace;
  wire do_pop = (ex && ((op == OP_STORE  && !(imm_bad_addr || sp == 0)) ||
                        (op == OP_STOREI && !(sp < 2 || tos_bad_addr)) ||
                        (op == OP_DROP && sp != 0) ||
                        (op == OP_JZ   && sp != 0) ||
                        (binop && sp >= 2))) ||
                (running && (vst == V_ST2));   // storei's second pop
  wire [6:0] sp_nxt = (do_push || do_lpush) ? sp + 1'b1 :
                      do_pop                ? sp - 1'b1 : sp;
  wire [5:0] rd_i = sp_nxt[5:0] - 6'd3;
  wire       sb_we = do_push || do_lpush;
  wire [5:0] sb_wa = sp[5:0] - 6'd2;
  always @(posedge clk) begin
    if (sb_we) sbody[sb_wa] <= t1;      // the old nos sinks into the body
    sq    <= sbody[rd_i];
    fwd_v <= sb_we && (sb_wa == rd_i);  // a push always collides with the
    fwd_d <= t1;                        // read it makes necessary
  end

  `define TRAP begin trapped <= 1'b1; running <= 1'b0; vst <= V_FETCH; end

  // DMEM: Intel's two-process true-dual-port template, so it maps to M10K
  // (anything port-richer melts into a third of the FPGA as loose logic).
  // Port A is the VM's -- load/loadi read or store/storei write, never the
  // same cycle. Port B is the external port's -- GPU reads, boot/pad
  // writes, also never the same cycle by construction.
  wire st_store  = running && vst == V_EXEC && fuel != 0 && hit &&
                   op == OP_STORE  && !(imm_bad_addr || sp == 0);
  wire st_storei = running && vst == V_EXEC && fuel != 0 && hit &&
                   op == OP_STOREI && !(sp < 2 || tos_bad_addr);
  wire        a_we   = st_store || st_storei;
  wire [13:0] a_addr = a_we ? (st_store ? imm[13:0] : tos[13:0]) : dread_addr;
  wire [31:0] a_data = st_store ? tos : nos;
  always @(posedge clk) begin
    if (a_we) dmem[a_addr] <= a_data;
    else dq <= dmem[a_addr];
  end
  always @(posedge clk) begin
    if (ext_we && !running) dmem[ext_addr] <= ext_wdata;
    else eq <= dmem[ext_addr];
  end

  always @(posedge clk) begin
    // THE CACHE: a refill writes, the fetch reads (a simple dual port)
    if (ic_we) cdata[{ic_line[CI-1:2], ic_wo}] <= ic_wd;
    iq   <= cdata[fetch_addr[CI-1:0]];
    tq   <= ctag[fetch_addr[CI-1:2]];
    vq   <= cval[fetch_addr[CI-1:2]] && !(ic_we || ic_done || ic_flush);
    fa_r <= fetch_addr;
    if (ic_done) begin
      ctag[ic_line[CI-1:2]] <= ic_line[PAW-1:CI];
      cval[ic_line[CI-1:2]] <= 1'b1;
      ic_req <= 1'b0;
    end
    if (ic_flush) cval <= {(1 << (CI-2)){1'b0}};

    if (!rst_n) begin
      running <= 1'b0; trapped <= 1'b0; sp <= 0; pc <= 0; fuel <= 0;
      vst <= V_FETCH; ic_req <= 1'b0;
    end else if (start && !trapped && !running) begin
      running <= 1'b1; pc <= 0; sp <= 0; rsp <= 0; fuel <= FUEL[16:0];
      vst <= V_FETCH;                // one cycle to latch imem[0] into iq
    end else if (running) case (vst)
      V_FETCH: vst <= V_EXEC;
      V_MISS:  if (ic_done) vst <= V_FETCH;   // the line is in: fetch it again
      V_LOAD: begin                  // dq now holds the loaded word
        t0 <= dq;                    // (the body write rides do_lpush)
        if (!ld_replace) begin t1 <= t0; sp <= sp + 1'b1; end
        vst <= V_EXEC;               // iq refetched from the updated pc
      end
      V_ST2: begin                   // storei's second pop: the body read
        t0 <= t1;                    // issued last cycle is exactly the
        t1 <= below;                 // word it needs
        sp <= sp - 1'b1;
        vst <= V_EXEC;
      end
      default: begin                 // V_EXEC: one vm.py loop iteration
        if (fuel == 0) begin running <= 1'b0; vst <= V_FETCH; end
        else if (!hit) begin         // a miss: nothing happens, the line comes
          ic_req <= 1'b1; ic_line <= fa_r[PAW-1:2]; vst <= V_MISS;
        end
        else begin
          fuel <= fuel - 1'b1;
          pc <= pc_seq;
          if (pc_over) `TRAP
          case (op)
            OP_HALT: begin running <= 1'b0; vst <= V_FETCH; end
            OP_PUSH:
              if (sp == STACK_MAX) `TRAP
              else begin t0 <= imm; t1 <= t0; sp <= sp + 1'b1; end
            OP_LOAD:
              if (imm_bad_addr || sp == STACK_MAX) `TRAP
              else begin ld_replace <= 1'b0; vst <= V_LOAD; end
            OP_LOADI:
              if (sp == 0 || tos_bad_addr) `TRAP
              else begin ld_replace <= 1'b1; vst <= V_LOAD; end
            OP_STORE:                // the write itself rides DMEM port A
              if (imm_bad_addr || sp == 0) `TRAP
              else begin sp <= sp - 1'b1; t0 <= t1; t1 <= below; end
            OP_STOREI:               // pops two: one here, one in V_ST2
              if (sp < 2 || tos_bad_addr) `TRAP
              else begin
                sp <= sp - 1'b1; t0 <= t1; t1 <= below;
                vst <= V_ST2;
              end
            OP_ADD, OP_SUB, OP_MUL, OP_MULQ, OP_AND, OP_OR, OP_XOR,
            OP_LT, OP_EQ:
              if (sp < 2) `TRAP
              else begin
                case (op)            // the result IS the new tos, and the
                  OP_ADD:  t0 <= nos + tos;      // word beneath rises out
                  OP_SUB:  t0 <= nos - tos;      // of the body
                  OP_MUL:  t0 <= prod[31:0];
                  OP_MULQ: t0 <= prod[47:16];
                  OP_AND:  t0 <= nos & tos;
                  OP_OR:   t0 <= nos | tos;
                  OP_XOR:  t0 <= nos ^ tos;
                  OP_LT:   t0 <= (nos < tos) ? 32'd1 : 32'd0;
                  default: t0 <= (nos == tos) ? 32'd1 : 32'd0;
                endcase
                t1 <= below;
                sp <= sp - 1'b1;
              end
            OP_SHL:
              if (sp == 0 || imm_bad_sh) `TRAP
              else t0 <= tos << imm[4:0];
            OP_SHR:
              if (sp == 0 || imm_bad_sh) `TRAP
              else t0 <= tos >>> imm[4:0];
            OP_DUP:
              if (sp == 0 || sp == STACK_MAX) `TRAP
              else begin t1 <= t0; sp <= sp + 1'b1; end   // dup: t0 stays
            OP_DROP:
              if (sp == 0) `TRAP
              else begin sp <= sp - 1'b1; t0 <= t1; t1 <= below; end
            OP_SWAP:
              if (sp < 2) `TRAP
              else begin t0 <= t1; t1 <= t0; end   // swap: now free
            OP_OVER:
              if (sp < 2 || sp == STACK_MAX) `TRAP
              else begin t0 <= t1; t1 <= t0; sp <= sp + 1'b1; end
            OP_JMP:
              if (imm < 0 || imm >= IMEM_WORDS) `TRAP
              else pc <= imm[IMEM_BITS-1:0];
            OP_JZ:
              if (sp == 0) `TRAP
              else begin
                sp <= sp - 1'b1; t0 <= t1; t1 <= below;
                if (tos == 32'd0) begin
                  if (imm < 0 || imm >= IMEM_WORDS) `TRAP
                  else pc <= imm[IMEM_BITS-1:0];
                end
              end
            OP_CALL:
              if (rsp == RSTACK_MAX || imm < 0 || imm >= IMEM_WORDS) `TRAP
              else begin
                rstack[rsp[3:0]] <= pc_seq;
                rsp <= rsp + 1'b1;
                pc <= imm[IMEM_BITS-1:0];
              end
            OP_RET:                    // a stored address can only be out
              if (rsp == 0) `TRAP      // of range via a call at the last
              else begin               // IMEM word: vm.py's post-step pc
                rsp <= rsp - 1'b1;     // check trips there, so trap too
                if (rtgt >= IMEM_WORDS) `TRAP
                else pc <= rtgt;
              end
            default: `TRAP
          endcase
        end
      end
    endcase
  end

endmodule
`default_nettype wire
