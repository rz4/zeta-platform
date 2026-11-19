// zsnd.v -- the Zeta sound engine, defined by zeta/audio.py: two pulses,
// a triangle, a 15-bit LFSR noise, mixed >>2 into one signed 16-bit
// stream at 48 kHz. One sample per `tick`; the cross holds the stream
// bit-equal to the Python engine.
//
// The 8 register words arrive over the write port once per frame (zeta_top
// latches AU_BASE.. after the VM runs); phase and LFSR persist, exactly
// like the Python engine's state.
`default_nettype none

module zsnd (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        reg_we,
    input  wire [4:0]  reg_idx,      // word index into AU_BASE..+31
    input  wire [31:0] reg_data,
    input  wire        tick,         // one 48 kHz sample step
    input  wire        frame_go,     // pulse: a new frame's events begin
    input  wire        phase_rst,    // spec.AU_RESET: a one-clock pulse at the
                                     // latch -- the synth's cold start (phases
                                     // 0, LFSR 1), before this frame's samples
    input  wire        ev_we,        // the event list's load port
    input  wire [7:0]  ev_a,         // 0 = count, then two words each
    input  wire [31:0] ev_d,
    // THE WAVE BANK's load port. Each voice owns a private table, so the
    // bank is resolved by the LOADER, not here: zeta_top walks the eight
    // pages once per frame and writes each channel the one its ctrl word
    // asked for. Selecting at load time rather than at read time is what
    // makes eight pages cost nothing -- read-time selection would want
    // every page in every channel, sixteen times the RAM, to answer a
    // question that only changes on a frame boundary.
    input  wire        wav_we,       // one word (four signed samples)...
    input  wire [3:0]  wav_ch,       // ...into THIS channel's table
    input  wire [5:0]  wav_a,
    input  wire [31:0] wav_d,
    // ON GLASS the ticks are ~900 clocks apart and a whole frame's
    // events drain between them. In the CROSS they arrive back to back,
    // one per clock, so the driver must be told to wait -- otherwise a
    // tick lands while an event is still pending and the two machines
    // diverge. Exact, and free when a frame carries no events.
    output wire        busy,
    input  wire        aud_rd,       // THE MIXER AS A SENSOR: readback
    input  wire [3:0]  aud_a,        // (spec.AUD_BASE)
    output wire [23:0] aud_q,
    output reg signed [15:0] sample
);
  `include "params.vh"

  reg [23:0] ph  [0:AU_CHANNELS-1];
  reg [23:0] inc [0:AU_CHANNELS-1];
  reg [3:0]  vol [0:AU_CHANNELS-1];
  reg [1:0]  duty [0:1];
  reg [14:0] lfsr;
  // ---- THE EVENT LIST (spec.AU_EV_BASE) --------------------------------
  // The cart sends a TIMELINE once a frame instead of a value, and this
  // walks a pointer through it as the samples go by. Sub-frame envelopes
  // with the frame contract untouched: 800 samples, sample-exact, and
  // identical on the law forever.
  (* ramstyle = "MLAB" *) reg [31:0] evm [0:2*AU_EV_MAX];
  reg [6:0]  ev_n;                  // events this frame, 0..AU_EV_MAX
  reg [6:0]  ev_cnt;                // the count, staged until the list is in
  reg [6:0]  ev_p;                  // how many have fired
  reg [9:0]  ev_s;                  // sample index within the frame

  // THE LOAD, AND WHY THE COUNT IS ARMED LAST. The loader walks words
  // 0..2*AU_EV_MAX into evm, count first. Latching ev_n from that first
  // word made the list live while it was still being written: ev_due
  // reads evm[1], which at that instant still holds the PREVIOUS frame's
  // offset -- or, on the first frame that has any events at all, ZERO.
  // Zero is <= ev_s, so the whole list fired at once against blank data
  // and ev_p reached ev_n before a single real event had landed. The
  // frame went silent and every gate downstream was measuring an
  // already-drained pointer.
  //   So ev_n stays 0 for the whole load and is armed on the LAST word.
  // A list is either entirely present or entirely absent; there is no
  // instant at which a half-written timeline is playable.
  always @(posedge clk) if (ev_we) begin
    evm[ev_a] <= ev_d;
    if (ev_a == 8'd0)
      ev_cnt <= (ev_d > AU_EV_MAX) ? AU_EV_MAX[6:0] : ev_d[6:0];
    ev_n <= (ev_a == 2 * AU_EV_MAX) ? ev_cnt : 7'd0;
  end
  wire [31:0] ev_w0 = evm[1 + 2*ev_p[5:0]];
  wire [31:0] ev_w1 = evm[2 + 2*ev_p[5:0]];
  wire        ev_due = (ev_p < ev_n) && (ev_w0[9:0] <= ev_s);
  wire [3:0]  ev_ch  = ev_w0[AU_EV_CH_SHIFT+3:AU_EV_CH_SHIFT];
  wire        ev_ctl = ev_w0[14];
  // ---- THE MIXER AS A SENSOR (spec.AUD_BASE) --------------------------
  // One word a voice, holding the sum of |contribution| across the
  // frame's samples, in the mixer's own units -- before the >>2 and
  // before the clamp, because those belong to the BUS and not to the
  // voice. It is the other half of VIS_BASE, and the term that closes
  // Wn+1 = f(Wn, An, VIS, AUD).
  //
  // THE MIXER IS PARALLEL: all sixteen av[] exist on the same clock, so
  // sixteen accumulators would be sixteen adders and sixteen registers.
  // Instead one adder walks them, sixteen clocks a sample, which fits
  // because the ticks are ~900 clocks apart on glass.
  //
  // AND IT WALKS THE GAP BEFORE A TICK, NOT AFTER. av[] is computed
  // from the NEXT phase (p0 = ph + inc), so between tick k-1 and tick k
  // it holds exactly the contributions of the sample tick k is about to
  // emit -- stable, because ph only moves on a tick. Walking after the
  // tick instead would accumulate the following sample and put the
  // whole frame one sample out. Nothing needs latching either way.
  //
  // IN THE CROSS THE TICKS ARE BACK TO BACK, which is the same problem
  // the event list already has and takes the same answer: `busy` is
  // held while the walk runs and the harness waits the engine out. On
  // glass nothing waits, because the gap was always there.
  (* ramstyle = "MLAB" *) reg [23:0] amem [0:2*AU_CHANNELS-1];
  reg         abank;              // the half this frame is filling
  reg  [4:0]  wi;                 // 0..AU_CHANNELS; AU_CHANNELS is done
  reg         afresh;             // ...and whether this is a new frame
  wire        walking = (wi < AU_CHANNELS[4:0]);
  // the readback takes the port whenever it asks and the walk simply
  // waits, which costs nothing: av[] does not move between ticks, and
  // seventeen clocks of the ~900 available is not a shortage
  wire        aw_go = walking && !aud_rd && !ev_due;
  wire [4:0]  ar_a  = aud_rd ? {~abank, aud_a} : {abank, wi[3:0]};
  wire signed [15:0] asel = av[wi[3:0]];
  wire [15:0] amag = asel[15] ? (~asel + 16'd1) : asel;
  reg  [23:0] aq;
  reg  [4:0]  aw_a;
  reg         aw_e, afresh_r;
  reg  [15:0] amag_r;
  wire [24:0] asum = {1'b0, aq} + {9'd0, amag_r};
  // a whole frame peaks at 800 * 15,360 = 12,288,000 and the word holds
  // 16,777,215, so the saturate is a guard and not a behaviour
  wire [23:0] anew = afresh_r ? {8'd0, amag_r}
                   : asum[24] ? 24'hFFFFFF : asum[23:0];
  always @(posedge clk) begin
    aq       <= amem[ar_a];
    aw_a     <= {abank, wi[3:0]};
    amag_r   <= amag;
    aw_e     <= rst_n && aw_go;
    afresh_r <= afresh;
    if (rst_n && aw_e) amem[aw_a] <= anew;
    if (!rst_n) begin
      wi <= AU_CHANNELS[4:0]; abank <= 1'b0; afresh <= 1'b1;
    end else begin
      if (aw_go) wi <= wi + 5'd1;
      if (frame_go) begin
        afresh <= 1'b1; wi <= 5'd0;
      end else if (afresh && (reg_we || wav_we)) begin
        // FRAME_GO IS NOT THE END OF SETUP. It fires at I_GK, and the
        // frame's audio registers and wave pages are loaded well after
        // it -- so the walk it starts reads the PREVIOUS frame's vol
        // and the previous frame's tables. Measured: voices the law
        // called silent came back with thousands, because they had been
        // loud last frame and had not been zeroed yet.
        //
        // Rather than hunt for the exact clock setup ends, every walk
        // before the frame's FIRST TICK overwrites instead of adding
        // (afresh), which makes them idempotent -- so the walk is
        // simply started again each time anything under it moves, and
        // whichever one runs last is the one that counts.
        wi <= 5'd0;
      end else if (tick && !ev_due) begin
        // THE NEXT SAMPLE'S WALK -- but there is no next sample after
        // the frame's last tick, and starting one there put an 801st
        // set of contributions into a bank already finished. Measured
        // before the guard: choir's voice 0 read 5,616,208 against the
        // law's 5,608,928, one sample of a voice near full scale.
        if (ev_s != SAMPLES_PER_FRAME[9:0] - 10'd1) wi <= 5'd0;
        // the first tick's sample is already banked by the walk that
        // preceded it, so from here on the walks ADD
        if (ev_s == 10'd0) afresh <= 1'b0;
        // ---- AND THE BANK TURNS HERE, NOT AT frame_go ----------------
        // The frame's audio ENDS at its last sample; frame_go is much
        // later -- the top writes the pick, the pixel counts and these
        // counts, loads the audio registers and runs the whole VM
        // before it kicks the GPU. Flipping there meant the readback
        // read the bank before last, so the cart saw a frame that was
        // TWO old while the law's was one, and heard.zol's bars stood
        // a frame behind the sound: 6,555 pixels, and the totals
        // themselves matched perfectly the whole time.
        //
        // Turning it on the last sample also makes the stray ticks
        // between here and frame_go harmless: they land in the new
        // bank with afresh still set, so each simply overwrites, and
        // the walk that runs after the frame's registers are loaded
        // overwrites them all.
        if (ev_s == SAMPLES_PER_FRAME[9:0] - 10'd1) begin
          abank <= ~abank; afresh <= 1'b1;
        end
      end
    end
  end
  assign aud_q = aq;

  // the walk holds the harness the same way a pending event does
  assign busy = ev_due || walking;
  reg        wmode [0:AU_CHANNELS-1];   // ctrl bit 6 (channels 0..3 only:
                                        // 4..15 are voices unconditionally)

  // ---- THE VOICE: the sampled field at 48 kHz ---------------------------
  // The same primitive the rasterizer runs at 43.2 MHz -- an accumulator
  // indexing a bounded table -- and the page costs 2 Kbit, so each channel
  // simply gets its own copy and its own read port.
  //
  // The read is registered, so the address presented is always the one the
  // NEXT tick will want. On glass the ticks are 900 clocks apart and this
  // is trivially settled; in the cross they arrive back to back, one per
  // clock, and the answer must already be waiting. The `tick ? inc : 0`
  // term is what serves both: when a tick lands this very clock the phase
  // is about to advance, so the address skips an extra increment.

  // next phases (spec: advance, THEN synthesize from the new phase)
  // (in the cold-start clock the phase about to be advanced is ZERO: the
  // wave read below runs one sample ahead, so its address must already
  // come from the cold phase, or the first sample after a reset reads the
  // old one; and a tick landing in that same clock advances FROM the cold
  // state -- reset, then advance, then synthesize, the law's order)
  wire        cold = phase_rst;
  wire [23:0] p0 = (cold ? 24'd0 : ph[0]) + inc[0];
  wire [23:0] p1 = (cold ? 24'd0 : ph[1]) + inc[1];
  wire [23:0] p2 = (cold ? 24'd0 : ph[2]) + inc[2];
  wire [24:0] p3 = {1'b0, cold ? 24'd0 : ph[3]} + {1'b0, inc[3]};

  wire [23:0] pn [0:AU_CHANNELS-1];
  assign pn[0] = p0, pn[1] = p1, pn[2] = p2, pn[3] = p3[23:0];
  genvar gv;
  generate for (gv = AU_TONE_CHANNELS; gv < AU_CHANNELS; gv = gv + 1)
    begin : vph
      assign pn[gv] = (cold ? 24'd0 : ph[gv]) + inc[gv];
    end
  endgenerate
  genvar gw;
  generate for (gw = 0; gw < AU_CHANNELS; gw = gw + 1) begin : wch
    // MLAB, not M10K: 2 Kbit in a 10 Kbit block, four times over, is
    // four blocks this device cannot spare. LUT RAM is built from the
    // resource we still have plenty of.
    (* ramstyle = "MLAB" *) reg [31:0] mem [0:WAV_WORDS-1];
    reg [31:0] q;
    reg [1:0]  b;
    wire [23:0] na = pn[gw] + (tick ? inc[gw] : 24'd0);
    always @(posedge clk) begin
      if (wav_we && wav_ch == gw[3:0]) mem[wav_a] <= wav_d;
      q <= mem[na[23:18]];          // the word holding the next sample
      b <= na[17:16];               // ...and which byte of it
    end
    wire signed [7:0] smp = (b == 2'd0) ? q[7:0]   :
                            (b == 2'd1) ? q[15:8]  :
                            (b == 2'd2) ? q[23:16] : q[31:24];
  end endgenerate

  function [2:0] duty_th(input [1:0] d);
    duty_th = (d == 2'd0) ? 3'd1 : (d == 2'd1) ? 3'd2 :
              (d == 2'd2) ? 3'd4 : 3'd6;
  endfunction

  // SHIFT-AND-ADD, NOT A MULTIPLIER. Sixteen voices asked for seventeen
  // 8x4 products and Quartus obliged with seventeen DSP blocks -- on a
  // die whose DSPs have been 66/66 since the crown, that one change put
  // the fit eighteen over on its own. vol is FOUR BITS, so the product
  // is four conditional adds: exactly the shape fog's tmul already uses,
  // and the second time this project has answered a DSP overflow with a
  // trick already written down inside it.
  //   Sized to the RESULT, not the operands: 8-bit signed times 15
  // reaches -1,920, and every term below is a full 16 bits wide on
  // purpose. Three wrong pictures in this project came from forgetting
  // that Verilog does not do it for you.
  function signed [15:0] vmul(input signed [7:0] s, input [3:0] v);
    begin
      vmul = (v[0] ? {{8{s[7]}}, s}       : 16'sd0)
           + (v[1] ? {{7{s[7]}}, s, 1'b0} : 16'sd0)
           + (v[2] ? {{6{s[7]}}, s, 2'b0} : 16'sd0)
           + (v[3] ? {{5{s[7]}}, s, 3'b0} : 16'sd0);
    end
  endfunction

  // wave output shares the triangle's scale, so the mix still fits int16
  wire signed [15:0] wm0 = vmul(wch[0].smp, vol[0]);
  wire signed [15:0] wm1 = vmul(wch[1].smp, vol[1]);
  wire signed [15:0] wm2 = vmul(wch[2].smp, vol[2]);
  wire signed [15:0] wm3 = vmul(wch[3].smp, vol[3]);
  wire signed [15:0] a0 = wmode[0] ? (wm0 <<< 3)
                        : (p0[23:21] < duty_th(duty[0]))
                          ? {2'd0, vol[0], 10'd0} : -{2'd0, vol[0], 10'd0};
  wire signed [15:0] a1 = wmode[1] ? (wm1 <<< 3)
                        : (p1[23:21] < duty_th(duty[1]))
                          ? {2'd0, vol[1], 10'd0} : -{2'd0, vol[1], 10'd0};
  wire [7:0]  trw = p2[23] ? ~p2[22:15] : p2[22:15];
  wire signed [8:0]  trc = {1'b0, trw} - 9'sd128;
  // trc spans -128..127 exactly, so its low eight bits ARE the value
  wire signed [15:0] a2 = wmode[2] ? (wm2 <<< 3)
                                   : (vmul($signed(trc[7:0]), vol[2]) <<< 3);
  // the spec steps the LFSR first, then the sample reads it -- so the
  // wrap-sample must already hear the new bit
  wire [14:0] lcur  = cold ? 15'd1 : lfsr;
  wire [14:0] lnext = p3[24] ? {lcur[0] ^ lcur[1], lcur[14:1]} : lcur;
  wire signed [15:0] a3 = wmode[3] ? (wm3 <<< 3)
                        : lnext[0] ? {2'd0, vol[3], 10'd0}
                                   : -{2'd0, vol[3], 10'd0};
  // ---- the twelve pure voices, and THE CLAMP -------------------------
  // Channels 4..15 have no oscillator: they read the page always. A
  // cart that never writes them leaves inc and vol zero, so they add
  // exactly nothing and every older cart's stream is unchanged.
  wire signed [15:0] av [0:AU_CHANNELS-1];
  genvar gm;
  generate for (gm = AU_TONE_CHANNELS; gm < AU_CHANNELS; gm = gm + 1)
    begin : vmix
      assign av[gm] = vmul(wch[gm].smp, vol[gm]) <<< 3;
    end
  endgenerate
  assign av[0] = a0; assign av[1] = a1;
  assign av[2] = a2; assign av[3] = a3;
  // 22 bits: sixteen channels at +/-15,360 reach +/-245,760, which needs
  // 19 signed. Written wide on purpose -- a sum sized to its addends is
  // the same trap as a product sized to its operands.
  wire signed [21:0] mix = {{6{av[0][15]}}, av[0]}  + {{6{av[1][15]}}, av[1]}
                         + {{6{av[2][15]}}, av[2]}  + {{6{av[3][15]}}, av[3]}
                         + {{6{av[4][15]}}, av[4]}  + {{6{av[5][15]}}, av[5]}
                         + {{6{av[6][15]}}, av[6]}  + {{6{av[7][15]}}, av[7]}
                         + {{6{av[8][15]}}, av[8]}  + {{6{av[9][15]}}, av[9]}
                         + {{6{av[10][15]}}, av[10]} + {{6{av[11][15]}}, av[11]}
                         + {{6{av[12][15]}}, av[12]} + {{6{av[13][15]}}, av[13]}
                         + {{6{av[14][15]}}, av[14]} + {{6{av[15][15]}}, av[15]};
  wire signed [19:0] mix_s = mix[21:2];          // >> 2, as it always was
  wire signed [15:0] mix_c =
      (mix_s < -20'sd32768) ? -16'sd32768 :
      (mix_s >  20'sd32767) ?  16'sd32767 : mix_s[15:0];

  integer i;
  always @(posedge clk) begin
    if (!rst_n) begin
      for (i = 0; i < AU_CHANNELS; i = i + 1) begin
        ph[i] <= 0; inc[i] <= 0; vol[i] <= 0; wmode[i] <= 1'b0;
      end
      duty[0] <= 0; duty[1] <= 0;
      lfsr <= 15'd1;
      sample <= 0;
    end else begin
      if (reg_we) begin
        if (reg_idx[0]) begin
          vol[reg_idx[4:1]] <= reg_data[3:0];
          wmode[reg_idx[4:1]] <= reg_data[6];
          // duty belongs to the two pulses only
          if (reg_idx[4:1] < 4'd2) duty[reg_idx[1]] <= reg_data[5:4];
        end else
          inc[reg_idx[4:1]] <= reg_data[23:0];
      end
      // EVENTS FIRE BEFORE THE SAMPLE THEY ARE STAMPED FOR, one per
      // clock. On glass the ticks are ~900 clocks apart so a whole
      // frame's worth drains between them; in the cross they are back to
      // back, so `tick` is gated while any event is still due -- which is
      // what keeps the two machines bit-equal.
      if (phase_rst) begin                    // spec.AU_RESET (a tick in
        for (i = 0; i < AU_CHANNELS; i = i + 1)   // this clock overrides
          ph[i] <= 24'd0;                     // below, from the cold state)
        lfsr <= 15'd1;
      end
      if (frame_go) begin ev_p <= 7'd0; ev_s <= 10'd0; end
      else if (ev_due) begin
        ev_p <= ev_p + 7'd1;
        if (ev_ctl) begin
          vol[ev_ch] <= ev_w1[3:0];
          wmode[ev_ch] <= ev_w1[6];
          if (ev_ch < 4'd2) duty[ev_ch[0]] <= ev_w1[5:4];
        end else
          inc[ev_ch] <= ev_w1[23:0];
      end else if (tick) begin
        ev_s <= ev_s + 10'd1;
        ph[0] <= p0; ph[1] <= p1; ph[2] <= p2; ph[3] <= p3[23:0];
        for (i = AU_TONE_CHANNELS; i < AU_CHANNELS; i = i + 1)
          ph[i] <= pn[i];
        lfsr <= lnext;
        sample <= mix_c;            // >> 2 then saturate (spec.AU_CLAMP)
      end
    end
  end

endmodule
`default_nettype wire
