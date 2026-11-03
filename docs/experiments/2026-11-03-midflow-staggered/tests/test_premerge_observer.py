"""V2-only contract: the observed merging car determines the map trigger."""
import unittest
from test_premerge_topology import car, r


class PremergeObserverTests(unittest.TestCase):
    def test_receiver_before_boundary_can_see_a_merger_already_preparing(self):
        ego = car(0, 630., 1)
        rows = (car(1, 660., 1), car(2, 645., 2), car(3, 645., 0))
        command, _ = r.decide(ego, rows, r.Memory(), "transform")
        self.assertIsNone(command.lane)
        self.assertEqual(command.reference, 2)
        self.assertAlmostEqual(command.target_x, 615.)
        self.assertLessEqual(command.speed, r._request(ego, 615., 28.8))


if __name__ == "__main__":
    unittest.main()
