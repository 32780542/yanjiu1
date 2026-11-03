"""Road knowledge is distinct from a temporary observed lane-change relation."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'docs/experiments/2026-11-04-timegap-staggered/stage/candidates/forward_gap_C5R_200.py'))
spec = importlib.util.spec_from_file_location('road_C5_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, **kw):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, 28.8, lane, **kw)


class C5RoadKnowledge(unittest.TestCase):
    def decide(self, ego, rows, memory=None, drop=None):
        return r.decide(ego, rows, r.Memory() if memory is None else memory, 'transform', drop)

    def test_motion_receiving_ends_without_permanently_forbidding_lane_two(self):
        ego, moving = car(1, 880., 1), car(2, 895., 2, vy=-.4)
        command, memory = self.decide(ego, (moving, car(3, 930., 1)))
        self.assertEqual(command.reference, moving.track)
        later = car(1, 900., 1)
        command, _ = self.decide(later, (car(2, 929., 1), car(3, 964., 1),
                                       car(4, 939., 2), car(5, 800., 2)), memory)
        self.assertEqual(command.lane, 2)
        self.assertEqual(command.reference, 4)

    def test_remote_motion_does_not_project_another_stationary_lane_two_car(self):
        ego, stationary = car(1, 880., 1), car(2, 895., 2)
        actual, remote = car(3, 930., 1), car(4, 1020., 2, vy=-.4)
        command, _ = self.decide(ego, (stationary, actual, remote))
        self.assertEqual(command.reference, actual.track)

    def test_known_road_forbids_two_but_own_pending_finishes_without_road_knowledge(self):
        ego = car(1, 900., 1)
        rows = (car(2, 929., 1), car(3, 939., 2), car(4, 800., 2))
        command, _ = self.decide(ego, rows, drop=1000.)
        self.assertNotEqual(command.lane, 2)
        own_pending = car(1, 900., 2, pending_lane=1)
        command, _ = self.decide(own_pending, (car(2, 950., 1), car(3, 850., 1)))
        self.assertEqual(command.lane, 1)
        follower, moving_front = car(1, 880., 2), car(2, 910., 2, vy=-.4)
        command, memory = self.decide(follower, (moving_front, car(3, 950., 1), car(4, 800., 1)))
        self.assertEqual(command.lane, 1)
        command, _ = self.decide(car(1, 900., 2),
                                 (car(2, 940., 1), car(3, 980., 1), car(4, 800., 1)), memory)
        self.assertEqual(command.lane, 1)


if __name__ == '__main__':
    unittest.main()
