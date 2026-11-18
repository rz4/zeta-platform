#
# user core constraints
#
# put your clock groups in here as well as any net assignments
#

# clk_core_12288 (confirmed-tier core clock), clk_experiment (the
# fastest-clock probe, see core_top.v's header), and clk_psram
# (outclk_3, zeta_s1_scanout.v's PSRAM-domain clock -- crossed into
# clk_core_12288 via explicit synchronizers in that module, not
# implicit timing analysis) don't share a functional relationship with
# each other or with the board clocks, so every PLL output group is
# asynchronous to every other -- same reasoning build 2's
# core_constraints.sdc gave for its own clock groups.
set_clock_groups -asynchronous \
 -group { bridge_spiclk } \
 -group { clk_74a } \
 -group { clk_74b } \
 -group { ic|mp1|mf_pllbase_inst|altera_pll_i|general[0].gpll~PLL_OUTPUT_COUNTER|divclk } \
 -group { ic|mp1|mf_pllbase_inst|altera_pll_i|general[1].gpll~PLL_OUTPUT_COUNTER|divclk } \
 -group { ic|mp1|mf_pllbase_inst|altera_pll_i|general[2].gpll~PLL_OUTPUT_COUNTER|divclk } \
 -group { ic|mp1|mf_pllbase_inst|altera_pll_i|general[3].gpll~PLL_OUTPUT_COUNTER|divclk }


# -- the CRAM interface: constrained, not lucky (boot-11 lesson) ------------
# Chip clocks mirror the 43.2 MHz core clock at the pads. Outputs must
# reach the chip 4 ns before its edge (setup) and hold 2 ns after it;
# read data arrives up to 9 ns after the chip edge (CellularRAM-class
# numbers, conservative at this speed).
create_generated_clock -name cram0_clk \
 -source [get_pins {ic|mp1|mf_pllbase_inst|altera_pll_i|general[0].gpll~PLL_OUTPUT_COUNTER|divclk}] \
 [get_ports {cram0_clk}]
create_generated_clock -name cram1_clk \
 -source [get_pins {ic|mp1|mf_pllbase_inst|altera_pll_i|general[0].gpll~PLL_OUTPUT_COUNTER|divclk}] \
 [get_ports {cram1_clk}]
set_output_delay -clock cram0_clk -max 4.0 [get_ports {cram0_a[*] cram0_adv_n cram0_ce0_n cram0_we_n cram0_oe_n cram0_ub_n cram0_lb_n cram0_cre cram0_dq[*]}]
set_output_delay -clock cram0_clk -min -2.0 [get_ports {cram0_a[*] cram0_adv_n cram0_ce0_n cram0_we_n cram0_oe_n cram0_ub_n cram0_lb_n cram0_cre cram0_dq[*]}]
set_output_delay -clock cram1_clk -max 4.0 [get_ports {cram1_a[*] cram1_adv_n cram1_ce0_n cram1_we_n cram1_oe_n cram1_ub_n cram1_lb_n cram1_cre cram1_dq[*]}]
set_output_delay -clock cram1_clk -min -2.0 [get_ports {cram1_a[*] cram1_adv_n cram1_ce0_n cram1_we_n cram1_oe_n cram1_ub_n cram1_lb_n cram1_cre cram1_dq[*]}]
set_input_delay -clock cram0_clk -max 9.0 [get_ports {cram0_dq[*]}]
set_input_delay -clock cram0_clk -min 2.0 [get_ports {cram0_dq[*]}]
set_input_delay -clock cram1_clk -max 9.0 [get_ports {cram1_dq[*]}]
set_input_delay -clock cram1_clk -min 2.0 [get_ports {cram1_dq[*]}]
