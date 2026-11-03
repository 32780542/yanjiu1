"""C12/P12 preserve an established forward chain across a real leader replacement."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'tmp/staggered_bottleneck/candidates/20261104_C12_200/native_rules.py'))
spec = importlib.util.spec_from_file_location('C12_chain_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x):
    return r.Vehicle(track, x, .5 * r.LANE_WIDTH, 28.8, 0)


class ChainContinuity(unittest.TestCase):
    def test_established_chain_adopts_the_current_real_front_after_replacement(self):
        ego = car(0, 0.)
        for rows in ((car(2, 100.), car(3, 80.)), (car(3, 80.),), (car(2, -10.), car(3, 80.))):
            with self.subTest(tracks=[c.track for c in rows]):
                command, memory = r.decide(ego, rows, r.Memory(front=2), 'formation', None)
                self.assertEqual(command.reference, 3)
                self.assertEqual(memory.front, 3)
                self.assertGreater(command.speed, r.CRUISE)

    def test_no_actual_front_releases_chain_and_next_fresh_eighty_does_not_join(self):
        ego = car(0, 0.)
        for rows in ((), (car(2, -10.),)):
            with self.subTest(tracks=[c.track for c in rows]):
                command, memory = r.decide(ego, rows, r.Memory(front=2), 'formation', None)
                self.assertIsNone(command.reference)
                self.assertIsNone(memory.front)
                command, memory = r.decide(ego, (car(3, 80.),), memory, 'formation', None)
                self.assertIsNone(command.reference)
                self.assertIsNone(memory.front)
                self.assertAlmostEqual(command.speed, r.CRUISE)


def load_tests(loader, tests, pattern):
    import test_C11_relations as shared
    shared.r = r
    for case in loader.loadTestsFromTestCase(shared.EstablishedLeader):
        if case._testMethodName != 'test_changed_missing_or_behind_leaders_release_the_old_relation':
            tests.addTest(case)
    return tests


if __name__ == '__main__':
    unittest.main()
