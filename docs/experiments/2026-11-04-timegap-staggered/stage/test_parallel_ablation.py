"""Parallel geometry ablation; all other C8 rules remain unchanged."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'tmp/staggered_bottleneck/candidates/20261104_parallel_200/native_rules.py'))
spec = importlib.util.spec_from_file_location('parallel_ablation_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, 28.8, lane)


class ParallelGeometry(unittest.TestCase):
    def test_same_x_across_lanes_has_zero_phase_error(self):
        ego, peer = car(1, 900., 0), car(2, 900., 1)
        self.assertAlmostEqual(r._pair_error(ego, peer, 3)[0], 0.)

    def test_vacancy_progress_is_measured_toward_zero_offset_current_front(self):
        ego, current = car(1, 920., 1), car(2, 940., 1)
        anchor, rear = car(3, 965., 0), car(4, 850., 0)
        rows = (current, anchor, rear)
        vacancy = r._vacancy(ego, rows, 0)
        self.assertIsNotNone(vacancy)
        self.assertLess(abs(vacancy[1] - current.x), abs(ego.x - current.x))
        command, _ = r.decide(ego, rows, r.Memory(), 'transform', 1000.)
        self.assertEqual(command.lane, 0)


if __name__ == '__main__':
    unittest.main()
