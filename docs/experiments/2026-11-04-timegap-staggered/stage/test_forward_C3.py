"""C3: new slot formation waits for an actually changing current front."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'docs/experiments/2026-11-04-timegap-staggered/stage/candidates/forward_gap_C3_200.py'))
spec = importlib.util.spec_from_file_location('forward_C3_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, **kw):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, 28.8, lane, **kw)


class C3FrontMotion(unittest.TestCase):
    def decide(self, ego, rows, memory=None):
        return r.decide(ego, rows, r.Memory() if memory is None else memory, 'transform', 1000.)

    def test_new_slot_waits_for_motion_or_off_center_front_then_rechecks(self):
        ego = car(1, 920., 1)
        anchor, rear = car(3, 960., 0), car(4, 850., 0)
        fronts = (car(2, 940., 1, vy=-.4),
                  r.Vehicle(2, 940., 1.5 * r.LANE_WIDTH + .2, 28.8, 1))
        for front in fronts:
            with self.subTest(vy=front.vy, y=front.y):
                command, memory = self.decide(ego, (front, anchor, rear))
                self.assertIsNone(command.lane)
                self.assertEqual(command.reference, front.track)
                settled = car(2, 940., 1)
                command, _ = self.decide(ego, (settled, anchor, rear), memory)
                self.assertEqual(command.lane, 0)
                self.assertEqual(command.reference, anchor.track)

    def test_already_held_own_slot_plan_continues(self):
        ego, front = car(1, 920., 1), car(2, 940., 1, vy=-.4)
        anchor, rear = car(3, 960., 0), car(4, 850., 0)
        memory = r.Memory(lane_target=0, front=anchor.track, transforming=True)
        command, _ = self.decide(ego, (front, anchor, rear), memory)
        self.assertEqual(command.lane, 0)
        self.assertEqual(command.reference, anchor.track)

    def test_necessary_two_to_one_ignores_this_new_formation_gate(self):
        ego, front = car(1, 900., 2), car(2, 920., 2, vy=-.4)
        command, _ = self.decide(ego, (front, car(3, 950., 1), car(4, 850., 1)))
        self.assertEqual(command.lane, 1)


def load_tests(loader, tests, pattern):
    import test_forward_C2 as shared
    shared.r = r
    tests.addTests(loader.loadTestsFromModule(shared))
    return tests


if __name__ == '__main__':
    unittest.main()
