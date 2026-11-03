"""Portable real-gap balance contracts; only the installed controller is used."""
from dataclasses import replace
import itertools
import unittest

from noa import native_rules as r


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


def receiving_scene():
    return car(0, 625., 1), (car(1, 640., 0), car(2, 640., 2), car(3, 670., 2))


class LocalFormationBalanceTests(unittest.TestCase):
    def test_visible_future_resources_make_a_strictly_reducing_real_gap_transfer(self):
        ego, rows = receiving_scene()
        self.assertLess(ego.x, 640.)
        actual = [sum(c.lane == lane for c in (ego, *rows)) for lane in range(3)]
        self.assertEqual(actual, [1, 1, 2])
        future = [actual[0], actual[1] + actual[2]]
        self.assertEqual(future, [1, 3])
        self.assertLess(sum(n*n for n in (2, 2)), sum(n*n for n in future))
        command, memory = r.decide(ego, rows, r.Memory(), 'transform')
        self.assertEqual((command.lane, command.reason), (0, 'fill_layer'))
        self.assertEqual(command.target_x, 625.)
        self.assertEqual(memory.gap, (1, None))
        # Without the transform future-resource map there is no source surplus.
        self.assertIsNone(r.decide(ego, rows, r.Memory(), 'formation')[0].lane)

    def test_measured_y_and_vy_count_once_in_the_arriving_resource(self):
        ego, rows = receiving_scene()
        examples = ((1, 4.75, -.2, 0, None), (0, 1.85, .2, None, 0))
        for lane, y, vy, stationary_choice, moving_choice in examples:
            with self.subTest(lane=lane, vy=vy):
                moving = replace(car(4, 580., lane), y=y, vy=vy)
                stationary = replace(moving, vy=0.)
                self.assertEqual(r.decide(ego, (*rows, stationary), r.Memory(), 'transform')[0].lane,
                                 stationary_choice)
                self.assertEqual(r.decide(ego, (*rows, moving), r.Memory(), 'transform')[0].lane,
                                 moving_choice)
                fake_requests = tuple(replace(c, pending_lane=2) for c in (*rows, moving))
                self.assertEqual(r.decide(ego, fake_requests, r.Memory(), 'transform'),
                                 r.decide(ego, (*rows, moving), r.Memory(), 'transform'))

    def test_lateral_offset_cannot_make_the_candidate_its_own_gap_member(self):
        ego, rows = receiving_scene()
        ego = replace(ego, y=3.3)
        self.assertTrue(r._occupies(ego, 0))
        command, memory = r.decide(ego, rows, r.Memory(), 'transform')
        self.assertEqual((command.lane, command.reason), (0, 'fill_layer'))
        self.assertEqual(command.target_x, rows[0].x - 15.)
        self.assertEqual(memory.gap, (rows[0].track, None))
        self.assertNotIn(ego.track, memory.gap)

    def test_balanced_real_groups_have_no_strictly_reducing_transfer(self):
        for spacing, mode in itertools.product((24., 45.), ('formation', 'transform')):
            with self.subTest(spacing=spacing, mode=mode):
                ego = car(0, 500., 1)
                points = ((500.+spacing/2, 0), (500.-spacing/2, 0),
                          (500.+spacing/2, 2), (500.-spacing/2, 2), (500.-spacing, 1))
                rows = tuple(car(i+1, x, lane) for i, (x, lane) in enumerate(points))
                self.assertIsNone(r.decide(ego, rows, r.Memory(), mode, None)[0].lane)

    def test_labels_order_private_fields_and_outside_perception_do_not_assign_a_winner(self):
        ego, rows = receiving_scene()
        command, memory = r.decide(ego, rows, r.Memory(), 'transform')
        label = lambda c: replace(c, track=701-23*c.track)
        for order in itertools.permutations(rows):
            changed = tuple(replace(label(c), pending_lane=2, acceleration=-100., time=500.) for c in order)
            actual, held = r.decide(label(ego), changed, r.Memory(), 'transform')
            self.assertEqual(actual, command)
            self.assertEqual(held.gap, tuple(None if t is None else 701-23*t for t in memory.gap))
        outside = (car(90, ego.x-100.01, 2, 0.), car(91, ego.x+200.01, 0, 0.))
        self.assertEqual(r.decide(ego, (*rows, *outside), r.Memory(), 'transform'), (command, memory))

    def test_noa_reports_legal_zero_and_preserves_the_original_hard_safety_cap(self):
        ego, front = car(0, 100., 0, 33.3), car(1, 108., 0, 0.)
        command, _ = r.decide(ego, (front,), r.Memory(), 'noa', None)
        self.assertEqual(command.formation_state, 0)
        self.assertIsInstance(command.formation_state, int)
        self.assertEqual(command.speed.hex(),
                         min(r._front_following(ego, (front,))[0], r.safe_speed(ego, (front,))).hex())
        self.assertEqual(command.speed.hex(), r.safe_speed(ego, (front,)).hex())


if __name__ == '__main__':
    unittest.main()
