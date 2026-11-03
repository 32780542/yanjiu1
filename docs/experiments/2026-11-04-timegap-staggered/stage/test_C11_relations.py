"""C11/P11: establish ordinary leaders locally, retain only the selected relation."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'tmp/staggered_bottleneck/candidates/20261104_C11_200/native_rules.py'))
spec = importlib.util.spec_from_file_location('C11_relations_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, **kw):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, 28.8, lane, **kw)


class EstablishedLeader(unittest.TestCase):
    def decide(self, ego, rows, memory=None, mode='formation', drop=None):
        return r.decide(ego, rows, r.Memory() if memory is None else memory, mode, drop)

    def test_fresh_eighty_meter_car_does_not_accelerate_into_a_new_queue(self):
        command, memory = self.decide(car(1, 0., 0), (car(2, 80., 0),))
        self.assertAlmostEqual(command.speed, r.CRUISE)
        self.assertIsNone(command.reference)
        self.assertIsNone(memory.front)

    def test_local_leader_is_saved_then_an_eighty_meter_gap_stays_connected(self):
        ego = car(1, 0., 0)
        _, memory = self.decide(ego, (car(2, 40., 0),))
        self.assertEqual(memory.front, 2)
        command, memory = self.decide(ego, (car(2, 80., 0),), memory)
        self.assertEqual(command.reference, 2)
        self.assertEqual(memory.front, 2)
        self.assertGreater(command.speed, r.CRUISE)
        self.assertAlmostEqual(command.target_x, 80. - r.desired_spacing(ego.speed))

    def test_changed_missing_or_behind_leaders_release_the_old_relation(self):
        ego = car(1, 0., 0)
        cases = ((car(2, 100., 0), car(3, 80., 0)), (car(2, -10., 0),), ())
        for rows in cases:
            with self.subTest(tracks=[c.track for c in rows]):
                command, memory = self.decide(ego, rows, r.Memory(front=2))
                self.assertIsNone(command.reference)
                self.assertIsNone(memory.front)
        command, memory = self.decide(ego, (car(3, 40., 0),), r.Memory(front=2))
        self.assertEqual(command.reference, 3)
        self.assertEqual(memory.front, 3)

    def test_slot_anchor_and_pending_keep_priority_over_ordinary_reference(self):
        receiver, ending = car(1, 800., 1), car(2, 880., 2)
        command, memory = self.decide(receiver, (ending, car(3, 920., 1)),
                                      mode='transform', drop=1000.)
        self.assertEqual(command.reference, ending.track)
        self.assertEqual(memory.front, ending.track)
        self.assertAlmostEqual(command.target_x, ending.x - r._entry_spacing(receiver.speed))
        ego = car(1, 920., 1)
        rows = (car(2, 940., 1), car(3, 950.08, 0), car(4, 850., 0))
        command, memory = self.decide(ego, rows, mode='transform', drop=1000.)
        self.assertEqual(command.lane, 0)
        self.assertEqual(command.reference, 3)
        self.assertEqual(memory.front, 3)
        pending = car(1, 920., 1, pending_lane=0)
        rows = (car(2, 940., 1), car(3, 1000., 0), car(4, 850., 0))
        command, memory = self.decide(pending, rows, memory, mode='transform', drop=1000.)
        self.assertEqual(command.lane, 0)
        self.assertEqual(command.reference, 3)
        self.assertEqual(memory.front, 3)
        self.assertAlmostEqual(command.target_x, 1000. - r._entry_spacing(pending.speed))


if __name__ == '__main__':
    unittest.main()
