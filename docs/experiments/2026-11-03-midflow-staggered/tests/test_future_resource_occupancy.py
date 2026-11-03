"""Future resource clearance is not present physical lane occupancy."""
from dataclasses import replace
import importlib.util
import os
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get("RULES_F", ROOT / "tmp/staggered_bottleneck/candidates/midflow_future_resources/native_rules.py"))
spec = importlib.util.spec_from_file_location("future_resource_occupancy_candidate", SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, vy=0.):
    return r.Vehicle(track, x, (lane+.5)*r.LANE_WIDTH, 28.8, lane, vy)


def scene(delta):
    ego = car(0, 702., 0)
    # Existing lateral motion makes the three rear lane0 cars ineligible to fill;
    # they remain actual vehicles counted in both physical and future load.
    rows = (car(1, 760., 0), car(2, 730., 0, .2), car(3, 690., 0, .2),
            car(4, 680., 0, .2), car(5, 745., 1), car(6, 655., 1),
            car(7, 715.+delta, 2))
    return ego, rows


class FutureResourceOccupancyTests(unittest.TestCase):
    def test_future_occupied_resource_three_to_seven_metres_is_not_free(self):
        for delta in (3., 4., 5., 6., 7.):
            ego, rows = scene(delta)
            with self.subTest(delta=delta):
                self.assertTrue(r._clear(ego, rows, 1))
                self.assertFalse(r._mandatory_priority(ego, rows, 1, 1000.))
                command, _ = r.decide(ego, rows, r.Memory(), "transform")
                self.assertIsNone(command.lane,
                                  "Future target715 is within existing8m clearance of lane2 future use")

    def test_projection_is_only_a_resource_vacancy_check(self):
        ego, rows = scene(5.)
        # Actual lane2 at720 neither occupies lane1 nor invalidates actual gap.
        ending = rows[-1]
        self.assertFalse(r._occupies(ending, 1))
        self.assertTrue(r._clear(ego, rows, 1))
        # If future accounting is not enabled the original physical filler stays.
        self.assertEqual(r._fill(ego, rows, 2), 1)


if __name__ == "__main__":
    unittest.main()
