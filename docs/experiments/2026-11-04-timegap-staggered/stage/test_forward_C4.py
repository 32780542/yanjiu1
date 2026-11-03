"""C4: a formation slot preserves half an entry pitch behind the current front."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'docs/experiments/2026-11-04-timegap-staggered/stage/candidates/forward_gap_C4_200.py'))
spec = importlib.util.spec_from_file_location('forward_C4_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, speed=28.8, **kw):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane, **kw)


class C4HalfSpacing(unittest.TestCase):
    def decide(self, ego, rows, memory=None):
        return r.decide(ego, rows, r.Memory() if memory is None else memory, 'transform', 1000.)

    def test_large_bypass_is_rejected_even_when_front_just_settled(self):
        ego, current = car(1, 920., 1), car(2, 940., 1)
        anchor, rear = car(3, 965., 0), car(4, 850., 0)
        for memory in (r.Memory(), r.Memory(lane_target=0, front=3, transforming=True)):
            with self.subTest(preparing=memory.lane_target):
                command, _ = self.decide(ego, (current, anchor, rear), memory)
                self.assertIsNone(command.lane)
                self.assertEqual(command.reference, current.track)

    def test_real_small_slot_corrections_preserve_cruise_and_low_speed_entry(self):
        cases = ((920., 940., 950.08, 850., 28.8),
                 (80., 90., 96.2, 60., 0.))
        for x, current_x, anchor_x, rear_x, speed in cases:
            with self.subTest(speed=speed):
                ego, current = car(1, x, 1, speed), car(2, current_x, 1, speed)
                anchor, rear = car(3, anchor_x, 0, speed), car(4, rear_x, 0, speed)
                ending_behind = car(5, x - 50., 2, speed)
                command, _ = self.decide(ego, (current, anchor, rear, ending_behind),
                                         r.Memory(transforming=True))
                d = max(r.desired_spacing(speed), 2 * r.CLEARANCE)
                self.assertEqual(command.lane, 0)
                self.assertEqual(command.reference, anchor.track)
                self.assertAlmostEqual(command.target_x, anchor.x - d)
                self.assertLessEqual(command.target_x, current.x - d / 2)
                self.assertNotAlmostEqual(command.target_x, (anchor.x + rear.x) / 2)

    def test_submitted_execution_and_necessary_merge_are_not_replanned(self):
        executing = car(1, 920., 1, pending_lane=0)
        rows = (car(2, 940., 1), car(3, 965., 0), car(4, 850., 0))
        command, _ = self.decide(executing, rows, r.Memory(lane_target=0, front=3, transforming=True))
        self.assertEqual(command.lane, 0)
        ending = car(1, 920., 2)
        rows = (car(2, 940., 2), car(3, 965., 1), car(4, 850., 1))
        command, _ = self.decide(ending, rows)
        self.assertEqual(command.lane, 1)


def load_tests(loader, tests, pattern):
    import test_forward_C2 as shared
    shared.r = r
    superseded = {
        'test_former_ending_vehicle_uses_the_same_real_slot_as_any_receiver',
        'test_entry_pitch_is_twice_eight_at_low_speed',
        'test_real_vacancy_is_front_minus_d_not_gap_midpoint',
        'test_slot_can_be_approached_until_the_predicted_corridor_is_clear',
    }

    def cases(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                yield from cases(item)
            else:
                yield item

    for case in cases(loader.loadTestsFromModule(shared)):
        if case._testMethodName not in superseded:
            tests.addTest(case)
    return tests


if __name__ == '__main__':
    unittest.main()
