# The failing fit's testimony: the worst setup AND hold paths at every
# timing corner, printed to stdout so the CI log carries them. Run from
# pocket/template:  quartus_sta -t ../../infra/worst_paths.tcl
# Written after build 102 failed hold at both fast corners and the job
# could not say which path -- a gate that fails without naming the
# culprit sends the next person to guess, and guessing at hold is how
# discovery learned "seeds made it worse".

project_open ap_core
create_timing_netlist
read_sdc
update_timing_netlist

foreach_in_collection op [get_available_operating_conditions] {
    set_operating_conditions $op
    update_timing_netlist
    set name [get_operating_conditions_info $op -display_name]
    puts "\n======== $name : HOLD (worst 8) ========"
    report_timing -hold -npaths 8 -detail summary -stdout
    # 400, NOT 3. Three paths name one culprit; a clock change fails in
    # FAMILIES, and three at a time is one fit per family (frontier B5).
    # fit_ci.py tallies these by endpoint family.
    puts "\n======== $name : SETUP (worst 400) ========"
    report_timing -setup -npaths 400 -detail summary -stdout
}

delete_timing_netlist
project_close
