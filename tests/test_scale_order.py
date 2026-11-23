"""The scale-ordered schedule (experiments/scale/scales.py): the same world as
every-mover-every-frame, frame for frame, at a fraction of the worst frame --
and wrong, for a bounded while, when its one assumption is broken."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "scale"))
import scales as S                                       # noqa: E402
from zeta import spec                                    # noqa: E402

FRAMES = 1200


@pytest.fixture(scope="module")
def small():
    pads = S.route(FRAMES)
    return {mode: S.run(*S.build(mode, 128, 8, 3), pads) for mode in ("flat", "burst", "scaled")}


def right(r):
    return not (r["frames_state_differs_from_the_law"] or r["frames_drawn_set_differs"])


def test_all_three_schedules_are_the_same_world(small):
    for mode, r in small.items():
        assert right(r), f"{mode} left the law at frame {r['first_frame_wrong']}"
        assert (r["late"], r["over"], r["drop"]) == (0, 0, 0), mode
    assert small["flat"]["taken"] > 0, "the route never touched a mover: the test proves nothing about a permanent change"


def test_the_staggered_worst_frame_is_a_fraction_of_flat_and_of_the_burst(small):
    flat, burst, scaled = (small[k]["instructions"]["worst"] for k in ("flat", "burst", "scaled"))
    assert scaled * 4 < flat and scaled * 4 < burst
    assert small["scaled"]["working_set_words"]["worst"] * 3 < small["flat"]["working_set_words"]["worst"]


def test_the_burst_saves_the_average_and_not_the_worst_frame(small):
    assert small["burst"]["instructions"]["median"] < small["scaled"]["instructions"]["median"]
    assert small["burst"]["instructions"]["worst"] > small["flat"]["instructions"]["worst"] // 2


def test_sixteen_times_the_world_costs_the_staggered_schedule_under_twice():
    pads = S.route(700)
    small_, big = (S.run(*S.build("scaled", n, w, 3), pads) for n, w in ((128, 8), (2048, 10)))
    assert right(big) and (big["late"], big["over"], big["drop"]) == (0, 0, 0) and big["taken"] > 0
    assert big["instructions"]["worst"] < 2 * small_["instructions"]["worst"]
    flat = S.run(*S.build("flat", 2048, 10, 3), pads[:6])
    assert flat["frames_out_of_instructions"] == 6, "every mover every frame fits the machine at 2,048 after all"


def test_a_jump_breaks_it_for_a_period_or_for_good():
    """the limit, measured: the scales trust his speed. One frame of A (he is 300 units away at once) and the
    drawn set is wrong until the coarse cursors have been round -- at most the top scale's period. If a mover
    should have been TAKEN in that window, it is not, and the world is wrong from then on. Flat does not care."""
    path, info = S.build("scaled", 2048, 10, 3)
    top = info["plan"]["period"][-1]

    def jumped(seed, cart=(path, info)):
        pads = S.route(1400, seed)
        pads[100] |= spec.PAD_A
        return S.run(*cart, pads)
    assert right(jumped(8, S.build("flat", 128, 8, 3)))
    healed = jumped(8)
    assert healed["first_frame_wrong"] == 100 and healed["frames_state_differs_from_the_law"] == 0
    assert 0 < healed["frames_drawn_set_differs"] <= top
    for_good = jumped(7)                                  # this route lands him on a mover inside the window
    assert for_good["frames_state_differs_from_the_law"] == 1400 - 100
