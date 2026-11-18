`timescale 1ns/10ps
// Carried into build 3 (zeta3) from build 2 as the "clock derivation"
// working artifact -- see zeta-build3-aperture-down-plan.md's seed
// list. outclk_0/outclk_1 are the confirmed-on-silicon 12.288 MHz
// pixel-clock pair, unchanged.
//
// outclk_2 history from build 2 (see git history for the original of
// this comment, preserved there): retargeted from an unused
// ~133.12 MHz leftover to 24.576 MHz to drive a raster module, and
// confirmed working on real hardware at that frequency. A same-day
// attempt to push to ~32 MHz, justified only by an isolated single-
// module timing probe, showed genuine negative setup slack once
// quartus_sta ran on the full core_top.v/ap_core build -- "Fitter
// Status: Successful" means placed-and-routed, not timing-clean; those
// are different tools (quartus_fit vs quartus_sta) and the isolated
// probe missed the real critical path (CDC synchronizers, the SDRAM/
// scanout arbiter). Lesson carried forward: an isolated-module probe
// is a cheap filter for "does this have any chance," never a
// substitute for a full-system quartus_sta.
//
// 2026-07-17, build 3 task 2: "fastest clock we can hold" probe.
// core_top.v drives a real free-running LFSR from outclk_2 into user1
// (not a stub) so quartus_sta's Fmax Summary reflects genuine placed-
// and-routed critical path, applying the lesson above -- not an
// isolated-module guess. Swept 100 MHz -> 500 MHz -> ~800 MHz as the
// PLL's own output_clock_frequency target (Quartus itself rejects
// off-grid values and reports the nearest legal one, e.g. requesting
// "500 MHz" gets corrected to "497663959 Hz"); at every point up
// through ~800 MHz the Fmax Summary's "Restricted Fmax" pinned at the
// same 580.05 MHz (worst-case Slow 1100mV 85C corner), tagged "limit
// due to minimum period restriction (tmin)". That is a device/speed-
// grade fabric ceiling for 5CEBA4F23C8 (register minimum toggle
// period), not a function of the requested clock, the PLL's own VCO
// range, or anything the current (trivial) logic does -- so ~580 MHz
// [sim] is the honest answer to "how fast can any register-to-
// register path in this fabric go," today, with today's near-empty
// design, pre-silicon. It is not a usable target for real datapath
// work: build 2's own history two paragraphs up shows real logic
// (CDC synchronizers, arbiters, actual raster critical paths) collapses
// the achievable frequency to a small fraction of the fabric ceiling
// long before tmin becomes relevant, and that number can only come
// from a full-system quartus_sta on the real datapath once it exists,
// re-measured at every stage's admission per the aperture-down plan's
// admission rule. Left parked at 24.576 MHz (2x the confirmed pixel
// clock, matching build 2's own last hardware-confirmed non-pixel
// number) as a sane, unused-for-now default.
//
// 2026-07-17, build 3 task 5: outclk_3 wired to core_top.v as
// clk_psram, zeta_s1_scanout.v's PSRAM-domain clock (hardware/vendor/
// psram.sv's confirmed working rate, ~133.12 MHz -- see zeta_psram.v's
// header). Retargeted from the original ~133.12 MHz leftover to the
// nearest value Quartus accepts once actually routed
// ("133412560 Hz", ~133.41 MHz -- unused PLL outputs tolerate
// off-grid targets that Quartus rejects once wired to real logic).
// Running slightly faster than the vendor core's CLOCK_SPEED=133.12
// parameter it assumes is safe, not a compromise: the same "a higher
// assumed clock only ever adds real-time margin" reasoning
// zeta_psram.v's own header gives, just the mirror case (real clock
// faster than assumed, instead of assumed faster than real). Still
// [sim] tier until confirmed on real Pocket hardware. outclk_4 remains
// unwired at its original ~133.12 MHz, untouched.
module  mf_pllbase_0002(

	// interface 'refclk'
	input wire refclk,

	// interface 'reset'
	input wire rst,

	// interface 'outclk0'
	output wire outclk_0,

	// interface 'outclk1'
	output wire outclk_1,

	// interface 'outclk2'
	output wire outclk_2,

	// interface 'outclk3'
	output wire outclk_3,

	// interface 'outclk4'
	output wire outclk_4,

	// interface 'locked'
	output wire locked
);

	altera_pll #(
		.fractional_vco_multiplier("true"),
		.reference_clock_frequency("74.25 MHz"),
		.operation_mode("normal"),
		.number_of_clocks(5),
		.output_clock_frequency0("43.200000 MHz"),
		.phase_shift0("0 ps"),
		.duty_cycle0(50),
		.output_clock_frequency1("8.640000 MHz"),
		.phase_shift1("0 ps"),
		.duty_cycle1(50),
		.output_clock_frequency2("8.640000 MHz"),
		.phase_shift2("28935 ps"),
		.duty_cycle2(50),
		.output_clock_frequency3("12282352 Hz"),
		.phase_shift3("0 ps"), // async domain, crossed via explicit synchronizers -- phase doesn't matter
		.duty_cycle3(50),
		.output_clock_frequency4("133.119990 MHz"),
		.phase_shift4("5634 ps"),
		.duty_cycle4(50),
		.output_clock_frequency5("0 MHz"),
		.phase_shift5("0 ps"),
		.duty_cycle5(50),
		.output_clock_frequency6("0 MHz"),
		.phase_shift6("0 ps"),
		.duty_cycle6(50),
		.output_clock_frequency7("0 MHz"),
		.phase_shift7("0 ps"),
		.duty_cycle7(50),
		.output_clock_frequency8("0 MHz"),
		.phase_shift8("0 ps"),
		.duty_cycle8(50),
		.output_clock_frequency9("0 MHz"),
		.phase_shift9("0 ps"),
		.duty_cycle9(50),
		.output_clock_frequency10("0 MHz"),
		.phase_shift10("0 ps"),
		.duty_cycle10(50),
		.output_clock_frequency11("0 MHz"),
		.phase_shift11("0 ps"),
		.duty_cycle11(50),
		.output_clock_frequency12("0 MHz"),
		.phase_shift12("0 ps"),
		.duty_cycle12(50),
		.output_clock_frequency13("0 MHz"),
		.phase_shift13("0 ps"),
		.duty_cycle13(50),
		.output_clock_frequency14("0 MHz"),
		.phase_shift14("0 ps"),
		.duty_cycle14(50),
		.output_clock_frequency15("0 MHz"),
		.phase_shift15("0 ps"),
		.duty_cycle15(50),
		.output_clock_frequency16("0 MHz"),
		.phase_shift16("0 ps"),
		.duty_cycle16(50),
		.output_clock_frequency17("0 MHz"),
		.phase_shift17("0 ps"),
		.duty_cycle17(50),
		.pll_type("General"),
		.pll_subtype("General")
	) altera_pll_i (
		.rst	(rst),
		.outclk	({outclk_4, outclk_3, outclk_2, outclk_1, outclk_0}),
		.locked	(locked),
		.fboutclk	( ),
		.fbclk	(1'b0),
		.refclk	(refclk)
	);
endmodule

