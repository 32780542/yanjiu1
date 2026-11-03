"""C10b: an absent hard front can coexist with a real slot and soft phase target."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'tmp/staggered_bottleneck/candidates/20261104_forward_gap_C10b_200/native_rules.py'))
spec = importlib.util.spec_from_file_location('forward_C10b_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


class C10bAbsentFront(unittest.TestCase):
    def test_phase_target_and_real_vacancy_without_a_hard_front_continue_formation(self):
        def car(track, x, lane):
            return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, 28.8, lane)

        ego = car(1, 900., 1)
        rows = (car(2, 920., 0), car(3, 840., 0))
        self.assertIsNone(r._queue_front(ego, rows, True))
        formed = r._following(ego, rows)
        vacancy = r._vacancy(ego, rows, 0)
        self.assertIsNotNone(formed[1])
        self.assertIsNotNone(vacancy)
        self.assertLessEqual(vacancy[1], formed[1])
        command, _ = r.decide(ego, rows, r.Memory(), 'transform', 1000.)
        self.assertIsNone(command.lane)
        self.assertIsNone(command.reference)
        self.assertAlmostEqual(command.target_x, formed[1])
        self.assertAlmostEqual(command.speed, formed[0])


def load_tests(loader, tests, pattern):
    import test_forward_C10 as shared
    shared.r = r
    tests.addTests(loader.loadTestsFromModule(shared))
    return tests


if __name__ == '__main__':
    unittest.main()
