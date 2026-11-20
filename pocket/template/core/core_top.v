//
// User core top-level
//
// Instantiated by the real top-level: apf_top
//

`default_nettype none

module core_top (

//
// physical connections
//

///////////////////////////////////////////////////
// clock inputs 74.25mhz. not phase aligned, so treat these domains as asynchronous

input   wire            clk_74a, // mainclk1
input   wire            clk_74b, // mainclk1 

///////////////////////////////////////////////////
// cartridge interface
// switches between 3.3v and 5v mechanically
// output enable for multibit translators controlled by pic32

// GBA AD[15:8]
inout   wire    [7:0]   cart_tran_bank2,
output  wire            cart_tran_bank2_dir,

// GBA AD[7:0]
inout   wire    [7:0]   cart_tran_bank3,
output  wire            cart_tran_bank3_dir,

// GBA A[23:16]
inout   wire    [7:0]   cart_tran_bank1,
output  wire            cart_tran_bank1_dir,

// GBA [7] PHI#
// GBA [6] WR#
// GBA [5] RD#
// GBA [4] CS1#/CS#
//     [3:0] unwired
inout   wire    [7:4]   cart_tran_bank0,
output  wire            cart_tran_bank0_dir,

// GBA CS2#/RES#
inout   wire            cart_tran_pin30,
output  wire            cart_tran_pin30_dir,
// when GBC cart is inserted, this signal when low or weak will pull GBC /RES low with a special circuit
// the goal is that when unconfigured, the FPGA weak pullups won't interfere.
// thus, if GBC cart is inserted, FPGA must drive this high in order to let the level translators
// and general IO drive this pin.
output  wire            cart_pin30_pwroff_reset,

// GBA IRQ/DRQ
inout   wire            cart_tran_pin31,
output  wire            cart_tran_pin31_dir,

// infrared
input   wire            port_ir_rx,
output  wire            port_ir_tx,
output  wire            port_ir_rx_disable, 

// GBA link port
inout   wire            port_tran_si,
output  wire            port_tran_si_dir,
inout   wire            port_tran_so,
output  wire            port_tran_so_dir,
inout   wire            port_tran_sck,
output  wire            port_tran_sck_dir,
inout   wire            port_tran_sd,
output  wire            port_tran_sd_dir,
 
///////////////////////////////////////////////////
// cellular psram 0 and 1, two chips (64mbit x2 dual die per chip)

output  wire    [21:16] cram0_a,
inout   wire    [15:0]  cram0_dq,
input   wire            cram0_wait,
output  wire            cram0_clk,
output  wire            cram0_adv_n,
output  wire            cram0_cre,
output  wire            cram0_ce0_n,
output  wire            cram0_ce1_n,
output  wire            cram0_oe_n,
output  wire            cram0_we_n,
output  wire            cram0_ub_n,
output  wire            cram0_lb_n,

output  wire    [21:16] cram1_a,
inout   wire    [15:0]  cram1_dq,
input   wire            cram1_wait,
output  wire            cram1_clk,
output  wire            cram1_adv_n,
output  wire            cram1_cre,
output  wire            cram1_ce0_n,
output  wire            cram1_ce1_n,
output  wire            cram1_oe_n,
output  wire            cram1_we_n,
output  wire            cram1_ub_n,
output  wire            cram1_lb_n,

///////////////////////////////////////////////////
// sdram, 512mbit 16bit

output  wire    [12:0]  dram_a,
output  wire    [1:0]   dram_ba,
inout   wire    [15:0]  dram_dq,
output  wire    [1:0]   dram_dqm,
output  wire            dram_clk,
output  wire            dram_cke,
output  wire            dram_ras_n,
output  wire            dram_cas_n,
output  wire            dram_we_n,

///////////////////////////////////////////////////
// sram, 1mbit 16bit

output  wire    [16:0]  sram_a,
inout   wire    [15:0]  sram_dq,
output  wire            sram_oe_n,
output  wire            sram_we_n,
output  wire            sram_ub_n,
output  wire            sram_lb_n,

///////////////////////////////////////////////////
// vblank driven by dock for sync in a certain mode

input   wire            vblank,

///////////////////////////////////////////////////
// i/o to 6515D breakout usb uart

output  wire            dbg_tx,
input   wire            dbg_rx,

///////////////////////////////////////////////////
// i/o pads near jtag connector user can solder to

output  wire            user1,
input   wire            user2,

///////////////////////////////////////////////////
// RFU internal i2c bus 

inout   wire            aux_sda,
output  wire            aux_scl,

///////////////////////////////////////////////////
// RFU, do not use
output  wire            vpll_feed,


//
// logical connections
//

///////////////////////////////////////////////////
// video, audio output to scaler
output  wire    [23:0]  video_rgb,
output  wire            video_rgb_clock,
output  wire            video_rgb_clock_90,
output  wire            video_de,
output  wire            video_skip,
output  wire            video_vs,
output  wire            video_hs,
    
output  wire            audio_mclk,
input   wire            audio_adc,
output  wire            audio_dac,
output  wire            audio_lrck,

///////////////////////////////////////////////////
// bridge bus connection
// synchronous to clk_74a
output  wire            bridge_endian_little,
input   wire    [31:0]  bridge_addr,
input   wire            bridge_rd,
output  reg     [31:0]  bridge_rd_data,
input   wire            bridge_wr,
input   wire    [31:0]  bridge_wr_data,

///////////////////////////////////////////////////
// controller data
// 
// key bitmap:
//   [0]    dpad_up
//   [1]    dpad_down
//   [2]    dpad_left
//   [3]    dpad_right
//   [4]    face_a
//   [5]    face_b
//   [6]    face_x
//   [7]    face_y
//   [8]    trig_l1
//   [9]    trig_r1
//   [10]   trig_l2
//   [11]   trig_r2
//   [12]   trig_l3
//   [13]   trig_r3
//   [14]   face_select
//   [15]   face_start
//   [31:28] type
// joy values - unsigned
//   [ 7: 0] lstick_x
//   [15: 8] lstick_y
//   [23:16] rstick_x
//   [31:24] rstick_y
// trigger values - unsigned
//   [ 7: 0] ltrig
//   [15: 8] rtrig
//
input   wire    [31:0]  cont1_key,
input   wire    [31:0]  cont2_key,
input   wire    [31:0]  cont3_key,
input   wire    [31:0]  cont4_key,
input   wire    [31:0]  cont1_joy,
input   wire    [31:0]  cont2_joy,
input   wire    [31:0]  cont3_joy,
input   wire    [31:0]  cont4_joy,
input   wire    [15:0]  cont1_trig,
input   wire    [15:0]  cont2_trig,
input   wire    [15:0]  cont3_trig,
input   wire    [15:0]  cont4_trig
    
);

// not using the IR port, so turn off both the LED, and
// disable the receive circuit to save power
assign port_ir_tx = 0;
assign port_ir_rx_disable = 1;

// bridge endianness: tells the framework how to byte-pack data it
// writes into this core's bridge-addressable memory (dataslot
// delivery, zeta_dataslot_loader.v) so a 32-bit word read back here
// lines up correctly. Left at the vendor template's own default (0,
// big-endian) until this task, since nothing was actually wired to
// bridge_wr before real cartridge loading needed it -- but PicoRV32
// and this whole toolchain (riscv64-elf-gcc -mabi=ilp32, every .bin
// this project builds) are little-endian, RV32IM's native convention.
// Left at 0 through the first real-hardware dataslot-loading test
// (result: core loaded, but drew a uniform solid-color field instead
// of the expected triangle -- consistent with, though not confirmed
// as, every delivered instruction word being byte-swapped). Fixed to
// 1 here; the next hardware test is what actually confirms it.
assign bridge_endian_little = 1;

// cart is unused, so set all level translators accordingly
// directions are 0:IN, 1:OUT
assign cart_tran_bank3 = 8'hzz;
assign cart_tran_bank3_dir = 1'b0;
assign cart_tran_bank2 = 8'hzz;
assign cart_tran_bank2_dir = 1'b0;
assign cart_tran_bank1 = 8'hzz;
assign cart_tran_bank1_dir = 1'b0;
assign cart_tran_bank0 = 4'hf;
assign cart_tran_bank0_dir = 1'b1;
assign cart_tran_pin30 = 1'b0;      // reset or cs2, we let the hw control it by itself
assign cart_tran_pin30_dir = 1'bz;
assign cart_pin30_pwroff_reset = 1'b0;  // hardware can control this
assign cart_tran_pin31 = 1'bz;      // input
assign cart_tran_pin31_dir = 1'b0;  // input

// link port is unused, set to input only to be safe
// each bit may be bidirectional in some applications
assign port_tran_so = 1'bz;
assign port_tran_so_dir = 1'b0;     // SO is output only
assign port_tran_si = 1'bz;
assign port_tran_si_dir = 1'b0;     // SI is input only
assign port_tran_sck = 1'bz;
assign port_tran_sck_dir = 1'b0;    // clock direction can change
assign port_tran_sd = 1'bz;
assign port_tran_sd_dir = 1'b0;     // SD is input and not used

// cram0_* is tied off further down (M0-scoped core has no WRAM/CPU
// client yet -- DAG nodes B1/B4).
//
// cram1_* is tied off further down too (2026-07-16 bin-storage
// revert): it briefly carried zeta_m1_frame.v's bin-coverage storage
// via zeta_psram.v (D4 plan Phase 0), reverted back to a single packed
// on-chip BRAM array after a real Quartus build measured a 4.5x
// regression from paying CRAM1's request/response latency on every
// bin access -- see zeta_m1_frame.v's own header.

// dram_* pins are driven by zeta_sdram_phy below -- no tie-off here.

// THE SRAM: the tape (zeta_tape.v, below). Both byte lanes, always.
wire [16:0] tape_sram_a;
wire [15:0] tape_sram_do;
wire        tape_sram_doe, tape_sram_oe_n, tape_sram_we_n;
assign sram_a = tape_sram_a;
assign sram_dq = tape_sram_doe ? tape_sram_do : {16{1'bZ}};
assign sram_oe_n  = tape_sram_oe_n;
assign sram_we_n  = tape_sram_we_n;
assign sram_ub_n  = 0;
assign sram_lb_n  = 0;

assign dbg_tx = 1'bZ;
assign aux_scl = 1'bZ;
assign vpll_feed = 1'bZ;


// for bridge write data, we just broadcast it to all bus devices
// for bridge read data, we have to mux it
// add your own devices here
always @(*) begin
    casex(bridge_addr)
    default: begin
        bridge_rd_data <= 0;
    end
    32'h10xxxxxx: begin
        // example
        // bridge_rd_data <= example_device_data;
        bridge_rd_data <= 0;
    end
    32'h3xxxxxxx: begin
        // THE TAPE: the word fetched a read AGO (see tape_rd below);
        // word 0 is the magic and needs no fetch
        bridge_rd_data <= (bridge_addr[15:2] == 14'd0) ? 32'h5A545030
                                                       : tape_rd_data;
    end
    32'h2xxxxxxx: begin
        // THE SAVE: APF reads the words back out of card_apf's buffer.
        // MLAB reads are asynchronous, so this answers in the same cycle
        // the address arrives, which is all this combinational mux gives.
        bridge_rd_data <= card_rd_data;
    end
    32'hF8xxxxxx: begin
        bridge_rd_data <= cmd_bridge_rd_data;
    end
    endcase
end


//
// host/target command handler
//
    wire            reset_n;                // driven by host commands, can be used as core-wide reset
    wire    [31:0]  cmd_bridge_rd_data;
    
// bridge host commands
// synchronous to clk_74a
    wire            status_boot_done = pll_core_locked_s; 
    wire            status_setup_done = pll_core_locked_s; // rising edge triggers a target command
    wire            status_running = reset_n; // we are running as soon as reset_n goes high

    wire            dataslot_requestread;
    wire    [15:0]  dataslot_requestread_id;
    wire            dataslot_requestread_ack = 1;
    wire            dataslot_requestread_ok = 1;

    wire            dataslot_requestwrite;
    wire    [15:0]  dataslot_requestwrite_id;
    wire    [31:0]  dataslot_requestwrite_size;
    wire            dataslot_requestwrite_ack = 1;
    wire            dataslot_requestwrite_ok = 1;

    wire            dataslot_update;
    wire    [15:0]  dataslot_update_id;
    wire    [31:0]  dataslot_update_size;
    
    wire            dataslot_allcomplete;

    wire     [31:0] rtc_epoch_seconds;
    wire     [31:0] rtc_date_bcd;
    wire     [31:0] rtc_time_bcd;
    wire            rtc_valid;

    wire            savestate_supported;
    wire    [31:0]  savestate_addr;
    wire    [31:0]  savestate_size;
    wire    [31:0]  savestate_maxloadsize;

    wire            savestate_start;
    wire            savestate_start_ack;
    wire            savestate_start_busy;
    wire            savestate_start_ok;
    wire            savestate_start_err;

    wire            savestate_load;
    wire            savestate_load_ack;
    wire            savestate_load_busy;
    wire            savestate_load_ok;
    wire            savestate_load_err;
    
    wire            osnotify_inmenu;

// bridge target commands
// synchronous to clk_74a

    wire            target_dataslot_read;       // driven by card_apf
    wire            target_dataslot_write = target_dataslot_write_w;
    wire            target_dataslot_write_w;
    reg             target_dataslot_getfile;    // require additional param/resp structs to be mapped
    reg             target_dataslot_openfile;   // require additional param/resp structs to be mapped
    
    wire            target_dataslot_ack;        
    wire            target_dataslot_done;
    wire    [2:0]   target_dataslot_err;

    wire    [15:0]  target_dataslot_id;         // ...and these four
    wire    [31:0]  target_dataslot_slotoffset;
    wire    [31:0]  target_dataslot_bridgeaddr;
    wire    [31:0]  target_dataslot_length;
    
    wire    [31:0]  target_buffer_param_struct; // to be mapped/implemented when using some Target commands
    wire    [31:0]  target_buffer_resp_struct;  // to be mapped/implemented when using some Target commands
    
// bridge data slot access
// synchronous to clk_74a

    wire    [9:0]   datatable_addr;
    wire            datatable_wren;
    wire    [31:0]  datatable_data;
    wire    [31:0]  datatable_q;

core_bridge_cmd icb (

    .clk                ( clk_74a ),
    .reset_n            ( reset_n ),

    .bridge_endian_little   ( bridge_endian_little ),
    .bridge_addr            ( bridge_addr ),
    .bridge_rd              ( bridge_rd ),
    .bridge_rd_data         ( cmd_bridge_rd_data ),
    .bridge_wr              ( bridge_wr ),
    .bridge_wr_data         ( bridge_wr_data ),
    
    .status_boot_done       ( status_boot_done ),
    .status_setup_done      ( status_setup_done ),
    .status_running         ( status_running ),

    .dataslot_requestread       ( dataslot_requestread ),
    .dataslot_requestread_id    ( dataslot_requestread_id ),
    .dataslot_requestread_ack   ( dataslot_requestread_ack ),
    .dataslot_requestread_ok    ( dataslot_requestread_ok ),

    .dataslot_requestwrite      ( dataslot_requestwrite ),
    .dataslot_requestwrite_id   ( dataslot_requestwrite_id ),
    .dataslot_requestwrite_size ( dataslot_requestwrite_size ),
    .dataslot_requestwrite_ack  ( dataslot_requestwrite_ack ),
    .dataslot_requestwrite_ok   ( dataslot_requestwrite_ok ),

    .dataslot_update            ( dataslot_update ),
    .dataslot_update_id         ( dataslot_update_id ),
    .dataslot_update_size       ( dataslot_update_size ),
    
    .dataslot_allcomplete   ( dataslot_allcomplete ),

    .rtc_epoch_seconds      ( rtc_epoch_seconds ),
    .rtc_date_bcd           ( rtc_date_bcd ),
    .rtc_time_bcd           ( rtc_time_bcd ),
    .rtc_valid              ( rtc_valid ),
    
    .savestate_supported    ( savestate_supported ),
    .savestate_addr         ( savestate_addr ),
    .savestate_size         ( savestate_size ),
    .savestate_maxloadsize  ( savestate_maxloadsize ),

    .savestate_start        ( savestate_start ),
    .savestate_start_ack    ( savestate_start_ack ),
    .savestate_start_busy   ( savestate_start_busy ),
    .savestate_start_ok     ( savestate_start_ok ),
    .savestate_start_err    ( savestate_start_err ),

    .savestate_load         ( savestate_load ),
    .savestate_load_ack     ( savestate_load_ack ),
    .savestate_load_busy    ( savestate_load_busy ),
    .savestate_load_ok      ( savestate_load_ok ),
    .savestate_load_err     ( savestate_load_err ),

    .osnotify_inmenu        ( osnotify_inmenu ),
    
    .target_dataslot_read       ( target_dataslot_read ),
    .target_dataslot_write      ( target_dataslot_write ),
    .target_dataslot_getfile    ( target_dataslot_getfile ),
    .target_dataslot_openfile   ( target_dataslot_openfile ),
    
    .target_dataslot_ack        ( target_dataslot_ack ),
    .target_dataslot_done       ( target_dataslot_done ),
    .target_dataslot_err        ( target_dataslot_err ),

    .target_dataslot_id         ( target_dataslot_id ),
    .target_dataslot_slotoffset ( target_dataslot_slotoffset ),
    .target_dataslot_bridgeaddr ( target_dataslot_bridgeaddr ),
    .target_dataslot_length     ( target_dataslot_length ),

    .target_buffer_param_struct ( target_buffer_param_struct ),
    .target_buffer_resp_struct  ( target_buffer_resp_struct ),
    
    .datatable_addr         ( datatable_addr ),
    .datatable_wren         ( datatable_wren ),
    .datatable_data         ( datatable_data ),
    .datatable_q            ( datatable_q )

);
////////////////////////////////////////////////////////////////////////////////////////

// ZETA -- the vendor-neutral console (zeta-sdk: silicon/ + pocket/
// zeta_glass.v), instantiated behind the real APF contract. Everything
// above this line is Analogue's template. The console itself is proven
// before it gets here: `zeta cross` (framebuffers) and `zeta glass`
// (this module's own pixel stream) are both bit-equal gates.
//
// Clocks: clk_zeta (51.84 MHz) runs the whole console, 6 clocks per dot.
// clk_dot / clk_dot_90 (8.64 MHz) are what the APF scaler samples RGB on;
// the console's dot strobe is edge-detected FROM clk_dot inside the
// clk_zeta domain, so rgb always transitions at a fixed, safe offset
// after the sampling edge. (zeta-ps15's first real-glass symptom was a
// floating pixel clock -- horizontal lines and rainbow noise. Never again.)

wire clk_zeta, clk_dot, clk_dot_90;
wire pll_core_locked;
wire reset_n_zeta;
wire pll_core_locked_s;              // the bridge's boot/setup status above
synch_3 s01(pll_core_locked, reset_n_zeta, clk_zeta);
synch_3 s02(pll_core_locked, pll_core_locked_s, clk_74a);

wire clk_audio;                     // 12.288 MHz = 256 * 48 kHz

mf_pllbase mp1 (
    .refclk   ( clk_74a ),
    .rst      ( 0 ),
    .outclk_0 ( clk_zeta ),
    .outclk_1 ( clk_dot ),
    .outclk_2 ( clk_dot_90 ),
    .outclk_3 ( clk_audio ),
    .locked   ( pll_core_locked )
);

reg [2:0] dot_ph;
always @(posedge clk_zeta) dot_ph <= {dot_ph[1:0], clk_dot};
wire ce_dot = dot_ph[1] & ~dot_ph[2];

// APF pad bits -> spec.py pad bits: dirs, ABXY, L, R already line up;
// start is APF bit 15 -> ours bit 10, select APF bit 14 -> ours bit 11
wire [15:0] zeta_pad = {4'b0, cont1_key[14], cont1_key[15],
                        cont1_key[9:8], cont1_key[7:4], cont1_key[3:0]};

wire [23:0] zeta_rgb;
wire zeta_hs, zeta_vs, zeta_de;

// The cart on the SD card, streamed over the APF bridge into the boot
// port while the console is held in reset; the ZETA_BAKE_CART image is
// only the fallback for a missing file. cart_loader.v holds the proof
// harness pointer -- `zeta deploy` gate 3 runs it.
// SLOT_LOAD: 1 loads the cart from the data slot, 0 boots purely from
// the cart baked into this bitstream. Held at 0 for builds 25-26 while
// the delivery path was corrupting memory -- which turned out to be
// zeta_glass declaring boot_addr 12 bits wide, folding all 16K of DMEM
// into the first 4096 words. Every simulation passed because Verilator
// does not mask over-wide drives on top-level input ports the way
// synthesis does. Back to 1 now, with deploy's seam check scanning
// every declaration in the tree so no module on this path can be
// narrow again.
localparam SLOT_LOAD = 1;
wire        cl_we, cart_ready;
wire [1:0]  cl_kind;      // 0 IMEM, 1 DMEM, 2 CRAM segment
// With SLOT_LOAD = 0 the loader still watches the bridge and signs its
// count into the reserved cells -- the console boots from the baked
// cart, so a probe cart baked in can READ those counters. That is the
// measurement nine hardware rounds could never take.
wire        cart_ready_eff = SLOT_LOAD ? cart_ready : 1'b1;
wire [22:0] cl_addr;      // 23 bits since the second dies (build 105); this
wire [31:0] cl_data;
wire        cl_busy;      // a segment word is still going into CRAM      // wire truncating silently was boot 16's black
                          // screen -- core_top is the one layer the sims
                          // don't wrap, so widths here get checked by eye

cart_loader u_cart (
    .bclk(clk_74a), .brst_n(pll_core_locked_s),
    .bridge_addr(bridge_addr), .bridge_wr(bridge_wr),
    .bridge_wr_data(bridge_wr_data),
    .dataslot_allcomplete(dataslot_allcomplete),
    .cclk(clk_zeta), .apply_cart(SLOT_LOAD[0]), .boot_busy(cl_busy),
    .boot_we(cl_we), .boot_kind(cl_kind),
    .boot_addr(cl_addr), .boot_data(cl_data),
    .cart_ready(cart_ready));

wire [15:0] cram0_dq_o, cram1_dq_o;
wire        cram0_oe,   cram1_oe;
wire        c0_clk_en,  c1_clk_en;

// ---- THE TAPE (pocket/zeta_tape.v): the session's pad words, recorded
// into the SRAM and read out by the OS as a nonvolatile slot at
// 0x30000000 when the core exits (data.json, slot 3).
//
// THE BRIDGE DOES NOT WAIT. io_bridge_peripheral samples a device's read
// data four of its clocks after the address lands, and only THEN raises
// bridge_rd -- so a memory that needs a dozen console clocks to answer
// cannot answer the address it is shown. The OS reads a slot in order,
// though, so each read strobe fetches the NEXT word: by the time the
// bridge asks for it (an SPI word later, microseconds) it is waiting.
// Word 0 is the magic, a constant, and starts the chain. The first read
// also freezes the recorder: a tape that grew under the reader would be
// read with a frame missing from its middle.
wire        tape_pad_stb;
wire [15:0] tape_pad_word;
wire [31:0] tape_rd_data;
reg         tape_rd_req = 1'b0;
reg  [13:0] tape_rd_addr = 14'd0;
reg         tape_freeze = 1'b0;
always @(posedge clk_74a) begin
    if (bridge_rd && bridge_addr[31:28] == 4'h3) begin
        tape_rd_addr <= bridge_addr[15:2] + 14'd1;
        tape_rd_req  <= ~tape_rd_req;
        tape_freeze  <= 1'b1;
    end
end
zeta_tape #(.LOG_WORDS(14)) u_tape (
    .clk(clk_zeta), .run(cart_ready_eff),
    .boot_we(cl_we), .boot_kind(cl_kind),
    .boot_addr(cl_addr), .boot_data(cl_data),
    .pad_stb(tape_pad_stb), .pad_word(tape_pad_word),
    .freeze(tape_freeze),
    .rd_req(tape_rd_req), .rd_addr(tape_rd_addr),
    .rd_data(tape_rd_data), .rd_ack(),
    .sram_a(tape_sram_a), .sram_do(tape_sram_do), .sram_doe(tape_sram_doe),
    .sram_di(sram_dq),
    .sram_oe_n(tape_sram_oe_n), .sram_we_n(tape_sram_we_n));

zeta_glass #(.EXT_CE(1)) u_zeta (
    // the machine wakes with the PLL; the CONSOLE waits for a complete
    // cart. Split so CRAM and its boot path are alive while the segment
    // is still arriving -- build 29 held them in reset and the segment
    // never landed.
    .clk(clk_zeta), .rst_n(reset_n_zeta), .core_en(cart_ready_eff),
    .ce_in(ce_dot), .pad(zeta_pad),
    .boot_we(cl_we), .boot_kind(cl_kind),
    .boot_addr(cl_addr), .boot_data(cl_data), .boot_busy(cl_busy),
    .boot_done(cart_ready),
    .ce_pix(), .rgb(zeta_rgb),
    .hs(zeta_hs), .vs(zeta_vs), .de(zeta_de),
    .snd_strobe(), .snd_sample(zeta_snd),
    .trapped(),
    .pad_stb(tape_pad_stb), .pad_word(tape_pad_word),
    .c0_wait(cram0_wait), .c1_wait(cram1_wait),
    .c0_a(cram0_a), .c0_dq_o(cram0_dq_o), .c0_dq_oe(cram0_oe),
    .c0_dq_i(cram0_dq),
    .c0_clk_en(c0_clk_en), .c0_adv_n(cram0_adv_n), .c0_cre(cram0_cre),
    .c0_ce_n(cram0_ce0_n), .c0_ce1_n(cram0_ce1_n), .c0_we_n(cram0_we_n), .c0_oe_n(cram0_oe_n),
    .c0_ub_n(cram0_ub_n), .c0_lb_n(cram0_lb_n),
    .c1_a(cram1_a), .c1_dq_o(cram1_dq_o), .c1_dq_oe(cram1_oe),
    .c1_dq_i(cram1_dq),
    .c1_clk_en(c1_clk_en), .c1_adv_n(cram1_adv_n), .c1_cre(cram1_cre),
    .c1_ce_n(cram1_ce0_n), .c1_ce1_n(cram1_ce1_n), .c1_we_n(cram1_we_n), .c1_oe_n(cram1_oe_n),
    .c1_ub_n(cram1_ub_n), .c1_lb_n(cram1_lb_n),
    // the card, through card_apf.v: the one path in this console that
    // the cross cannot prove, because machine 1 has no SD
    .sd_we(sd_we), .sd_data(sd_data), .sd_done(sd_done),
    .sd_req(sd_req), .sd_save(sd_save), .sd_sw_we(sd_sw_we),
    .sd_sw_a(sd_sw_a), .sd_sw_d(sd_sw_d),
    .sd_slot(sd_slot), .sd_off(sd_off), .sd_len(sd_len),
    .card_diag0(card_diag0), .card_diag1(card_diag1),
    .card_diag2(card_diag2));

wire [31:0] card_diag0, card_diag1, card_diag2;
wire        sd_req, sd_we, sd_done, sd_save, sd_sw_we;
wire [9:0]  sd_sw_a;
wire [31:0] sd_sw_d, card_rd_data;
wire [15:0] sd_slot;
wire [31:0] sd_off, sd_data;
wire [12:0] sd_len;

card_apf u_card_apf (
    .bclk(clk_74a), .brst_n(reset_n),
    .bridge_addr(bridge_addr), .bridge_wr(bridge_wr),
    .bridge_wr_data(bridge_wr_data),
    .ds_read(target_dataslot_read), .ds_id(target_dataslot_id),
    .ds_slotoffset(target_dataslot_slotoffset),
    .ds_bridgeaddr(target_dataslot_bridgeaddr),
    .ds_length(target_dataslot_length),
    .ds_write(target_dataslot_write_w), .rd_data(card_rd_data),
    .ds_done(target_dataslot_done), .ds_ack(target_dataslot_ack),
    .ds_err(target_dataslot_err),
    .diag0(card_diag0), .diag1(card_diag1), .diag2(card_diag2),
    .cclk(clk_zeta), .crst_n(reset_n_zeta),
    .c_req(sd_req), .c_save(sd_save), .sw_we(sd_sw_we),
    .sw_a(sd_sw_a), .sw_d(sd_sw_d),
    .c_slot(sd_slot), .c_off(sd_off), .c_len(sd_len),
    .c_we(sd_we), .c_data(sd_data), .c_done(sd_done));

// the CRAM chips clock IN PHASE with the core, FREE-RUNNING: boot 11
// taught that gating the clock through fabric logic makes its delay a
// per-fit dice roll -- three builds worked, the fourth shredded spans
// with address-phase corruption. A straight net plus the SDC
// constraints below turns the interface from lucky into designed.
// (Async-mode CFG ignores CLK, so free-running is safe from reset.)
assign cram0_clk = clk_zeta;
assign cram1_clk = clk_zeta;
/* verilator lint_off UNUSEDSIGNAL */
wire _cram_clken_unused = c0_clk_en & c1_clk_en;
/* verilator lint_on UNUSEDSIGNAL */
assign cram0_dq = cram0_oe ? cram0_dq_o : 16'hZZZZ;
assign cram1_dq = cram1_oe ? cram1_dq_o : 16'hZZZZ;
// (the second dies: driven by cram_burst since build 105)

wire signed [15:0] zeta_snd;

assign video_rgb_clock    = clk_dot;
assign video_rgb_clock_90 = clk_dot_90;
assign video_skip         = 1'b0;
assign video_rgb = zeta_rgb;
assign video_de  = zeta_de;
assign video_hs  = zeta_hs;
assign video_vs  = zeta_vs;

// audio: i2s per the APF convention -- [assumed]: no worked example on
// disk drives these pins, so this block is the one thing only glass can
// confirm. mclk 12.288 MHz, sclk = mclk/4 (3.072 MHz), lrck = sclk/64
// (48 kHz, low = left), 16 bits MSB-first after the standard one-bit
// i2s delay, same sample both channels. The sample bus crosses from
// clk_zeta on two flops -- it is quasi-static for ~900 core clocks, and
// audio is jitter-tolerant where video was not.
reg [1:0]  aud_div;
reg [5:0]  aud_slot;
reg [16:0] aud_sh;
reg [15:0] aud_m0, aud_m1;
always @(posedge clk_audio) begin
    aud_div <= aud_div + 1'b1;
    aud_m0 <= zeta_snd;
    aud_m1 <= aud_m0;
    if (aud_div == 2'd3) begin      // one sclk period per 4 mclk
        aud_slot <= aud_slot + 1'b1;
        if (aud_slot[4:0] == 5'd31) aud_sh <= {1'b0, aud_m1};
        else aud_sh <= {aud_sh[15:0], 1'b0};
    end
end
assign audio_mclk = clk_audio;
assign audio_lrck = aud_slot[5];
assign audio_dac  = aud_sh[16];

assign dram_a = 'h0;
assign dram_ba = 'h0;
assign dram_dq = {16{1'bZ}};
assign dram_dqm = 2'b11;
assign dram_clk = 1'b0;
assign dram_cke = 1'b0;
assign dram_ras_n = 1'b1;
assign dram_cas_n = 1'b1;
assign dram_we_n = 1'b1;

assign user1 = 1'b0;

endmodule
