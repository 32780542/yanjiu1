"""C6 restores mode semantics and replaces traffic gain by phase-error progress."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'docs/experiments/2026-11-04-timegap-staggered/stage/candidates/forward_gap_C6_200.py'))
spec = importlib.util.spec_from_file_location('forward_C6_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, speed=28.8, **kw):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane, **kw)


class C6MethodBehavior(unittest.TestCase):
    def decide(self, ego, rows, mode='transform', drop=1000., memory=None):
        return r.decide(ego, rows, r.Memory() if memory is None else memory, mode, drop)[0]

    def test_modes_differ_for_virtual_receiving_and_unknown_guidance(self):
        with self.subTest(case='virtual_receiving'):
            ego, ending, actual = car(1, 880., 1), car(2, 895., 2), car(3, 930., 1)
            ordinary = self.decide(ego, (ending, actual), mode='formation')
            transform = self.decide(ego, (ending, actual))
            self.assertEqual(ordinary.reference, actual.track)
            self.assertEqual(transform.reference, ending.track)
        with self.subTest(case='unknown_guidance'):
            ego, moving = car(1, 880., 2), car(2, 910., 2, vy=-.4)
            rows = (moving, car(3, 800., 1))
            ordinary = self.decide(ego, rows, mode='formation', drop=None)
            transform = self.decide(ego, rows, drop=None)
            self.assertIsNone(ordinary.lane)
            self.assertEqual(transform.lane, 1)
        with self.subTest(case='known_formation_merge'):
            ego = car(1, 900., 2)
            ordinary = self.decide(ego, (car(2, 950., 1), car(3, 850., 1)), mode='formation')
            self.assertEqual(ordinary.lane, 1)

    def test_geometry_rejects_bypass_but_preserves_improving_overshoot(self):
        with self.subTest(case='worsening_bypass'):
            ego, current = car(1, 920., 1), car(2, 940., 1)
            rows = (current, car(3, 965., 0), car(4, 850., 0))
            for memory in (r.Memory(), r.Memory(lane_target=0, front=3)):
                with self.subTest(preparing=memory.lane_target):
                    command = self.decide(ego, rows, memory=memory)
                    self.assertIsNone(command.lane)
            pending = car(1, 920., 1, pending_lane=0)
            command = self.decide(pending, rows, memory=r.Memory(lane_target=0, front=3))
            self.assertEqual(command.lane, 0)
        with self.subTest(case='improving_overshoot_of_q'):
            ego, current = car(1, 1496., 1), car(2, 1527.99, 1, 26.)
            anchor = car(3, 1548.98, 0, 26.)
            command = self.decide(ego, (current, anchor, car(4, 1450., 0, 26.)))
            self.assertEqual(command.lane, 0)
            self.assertAlmostEqual(command.target_x, 1519.)
            q = current.x - r._entry_spacing(ego.speed) / 2
            self.assertGreater(command.target_x, q)
            self.assertLess(abs(command.target_x - q), abs(ego.x - q))

    def test_geometric_progress_does_not_also_require_old_cth_progress(self):
        ego, current = car(1, 900., 1), car(2, 940., 1, 20.)
        anchor = car(3, 938.98, 0, 20.)
        command = self.decide(ego, (current, anchor, car(4, 850., 0, 20.)))
        self.assertEqual(command.lane, 0)
        self.assertAlmostEqual(command.target_x, 909.)
        self.assertLess(command.target_x, current.x - r.desired_spacing(ego.speed))


def load_tests(loader, tests, pattern):
    import test_road_information_C5 as shared
    shared.r = r
    tests.addTests(loader.loadTestsFromTestCase(shared.C5RoadKnowledge))
    return tests


if __name__ == '__main__':
    unittest.main()
