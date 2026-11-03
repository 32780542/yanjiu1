"""C8: longitudinal formation and one-way triggered contraction."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'docs/experiments/2026-11-04-timegap-staggered/stage/candidates/forward_gap_C8_200.py'))
spec = importlib.util.spec_from_file_location('forward_C8_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, **kw):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, 28.8, lane, **kw)


class C8OneWay(unittest.TestCase):
    def decide(self, ego, rows, memory=None, mode='transform', drop=1000.):
        return r.decide(ego, rows, r.Memory() if memory is None else memory, mode, drop)

    def test_ordinary_formation_and_untriggered_transform_do_not_change_lanes(self):
        ego = car(1, 920., 1)
        rows = (car(2, 940., 1), car(3, 950.08, 0), car(4, 850., 0))
        for mode in ('formation', 'transform'):
            with self.subTest(mode=mode):
                command, _ = self.decide(ego, rows, mode=mode, drop=None)
                self.assertIsNone(command.lane)

    def test_lane_zero_never_returns_to_one_for_a_real_slot(self):
        ego = car(1, 920., 0)
        rows = (car(2, 940., 0), car(3, 950.08, 1), car(4, 850., 1))
        command, _ = self.decide(ego, rows)
        self.assertIsNone(command.lane)

    def test_triggered_left_slot_and_two_step_ending_contraction_remain(self):
        ego = car(1, 920., 1)
        rows = (car(2, 940., 1), car(3, 950.08, 0), car(4, 850., 0))
        for trigger in ('road', 'motion', 'own_plan'):
            with self.subTest(trigger=trigger):
                seen = rows + (car(5, 1010., 2, vy=-.4),) if trigger == 'motion' else rows
                memory = r.Memory(lane_target=0, front=3) if trigger == 'own_plan' else r.Memory()
                command, _ = self.decide(ego, seen, memory, drop=1000. if trigger == 'road' else None)
                self.assertEqual(command.lane, 0)
        ending = car(1, 900., 2)
        command, memory = self.decide(ending, (car(2, 950., 1), car(3, 850., 1)))
        self.assertEqual(command.lane, 1)
        command, _ = self.decide(ego, rows, memory)
        self.assertEqual(command.lane, 0)


def load_tests(loader, tests, pattern):
    import test_forward_C7 as shared
    shared.r = r

    def cases(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                yield from cases(item)
            else:
                yield item

    for case in cases(loader.loadTestsFromModule(shared)):
        if case._testMethodName != 'test_motion_receiving_ends_without_permanently_forbidding_lane_two':
            tests.addTest(case)
    return tests


if __name__ == '__main__':
    unittest.main()
