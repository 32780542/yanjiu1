"""C10 uses one actual vacancy proposal for reception and lane-one insertion."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get('FORWARD_RULES', ROOT / 'tmp/staggered_bottleneck/candidates/20261104_forward_gap_C10_200/native_rules.py'))
spec = importlib.util.spec_from_file_location('forward_C10_under_test', SOURCE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def car(track, x, lane, speed=28.8, **kw):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane, **kw)


class C10SharedProposal(unittest.TestCase):
    def decide(self, ego, rows, memory=None, drop=1000.):
        return r.decide(ego, rows, r.Memory() if memory is None else memory, 'transform', drop)

    def test_free_heads_and_invalid_peer_proposals_do_not_reserve_a_gap(self):
        receiver, peer = car(1, 880., 0), car(2, 902., 1)
        cases = ((car(3, 934., 0),),
                 (car(4, 920., 1),),
                 (car(3, 954., 0), car(4, 920., 1)))
        for rows in cases:
            with self.subTest(rows=[c.track for c in rows]):
                command, _ = self.decide(receiver, (peer, *rows))
                self.assertNotEqual(command.reference, peer.track)
        moving = car(2, 902., 1, vy=-.4)
        command, _ = self.decide(receiver, (moving, car(3, 934., 0)), drop=None)
        self.assertEqual(command.reference, moving.track)

    def test_only_receiver_rear_deficit_is_opened_then_peer_uses_the_same_slot(self):
        receiver, peer = car(1, 880., 0), car(2, 902., 1)
        ahead, peer_front = car(3, 934., 0), car(4, 920., 1)
        command, _ = self.decide(receiver, (peer, ahead, peer_front))
        self.assertEqual(command.reference, peer.track)
        self.assertAlmostEqual(command.target_x, peer.x - r._entry_spacing(receiver.speed))
        peer_command, _ = self.decide(peer, (receiver, ahead, peer_front))
        self.assertIsNone(peer_command.lane)
        opened = car(1, 873., 0)
        peer_command, _ = self.decide(peer, (opened, ahead, peer_front))
        self.assertEqual(peer_command.lane, 0)
        self.assertAlmostEqual(peer_command.target_x, ahead.x - r._entry_spacing(peer.speed))
        too_close = car(1, 898.5, 0)
        command, _ = self.decide(too_close, (peer, ahead, peer_front))
        self.assertNotEqual(command.reference, peer.track)

    def test_peer_prepares_and_then_inserts_without_a_crowded_speed_proxy(self):
        peer, peer_front = car(1, 900., 1), car(2, 940., 1)
        ahead, rear = car(3, 934., 0, 0.), car(4, 870., 0, 0.)
        rows = (peer_front, ahead, rear)
        self.assertGreater(peer_front.x - peer.x, r._entry_spacing(peer.speed))
        self.assertGreaterEqual(r._following(peer, rows)[0], r.CRUISE)
        command, memory = self.decide(peer, rows)
        self.assertIsNone(command.lane)
        self.assertEqual(command.reference, ahead.track)
        self.assertEqual(memory.lane_target, 0)
        slowed = car(1, 900., 1, 10.)
        command, _ = self.decide(slowed, rows, memory)
        self.assertEqual(command.lane, 0)


def load_tests(loader, tests, pattern):
    import test_forward_C9 as shared
    shared.r = r
    superseded = {'test_known_front_space_opens_rear_gap_only_with_current_safe_corridor',
                  'test_unknown_needs_actual_motion_and_empty_front_interval_must_be_visible'}

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
