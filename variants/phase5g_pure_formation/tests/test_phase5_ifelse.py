"""Integrated B reference-rule tests, preserving A physical/safety mechanisms."""
from dataclasses import replace
import unittest
import test_phase5_controller as fixtures
from research.common import settings


class IfElseFormationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.FormationTests()
        self.f.setUp()
        self.p = self.f.p

    def test_frozen_workspace_declares_one_of_two_predeclared_enums(self):
        self.assertIn(settings('phase5').get('formation_reference_rule'), ('front_first', 'corner_first'))

    def acquired(self, neighbors):
        memory = self.f.Memory((), 'CRUISE')
        for i in range(11):
            d = self.f.decide(self.f.control(time=i/10, memory=memory, neighbors=neighbors), self.p)
            memory = d.memory
        return d

    def test_front_first_selects_direct_front_instead_of_lower_cost_corner(self):
        self.p['formation_reference_rule'] = 'front_first'
        d = self.acquired(((55., 1.65, 5.), (15., 4.95, 5.)))
        self.assertAlmostEqual(d.diagnostics['formation']['target_error_m'], 25.)
        self.assertEqual(d.diagnostics['formation']['selection_rule'], 'nearest_front')

    def test_corner_first_is_the_only_second_predeclared_order(self):
        self.p['formation_reference_rule'] = 'corner_first'
        d = self.acquired(((55., 1.65, 5.), (15., 4.95, 5.)))
        self.assertAlmostEqual(d.diagnostics['formation']['target_error_m'], 0.)
        self.assertEqual(d.diagnostics['formation']['selection_rule'], 'nearest_forward_corner')

    def test_side_and_rear_occupancy_never_become_references(self):
        d = self.f.ready(neighbors=((4., 4.95, 5.), (-30., 1.65, 5.)))
        self.assertIsNone(d.memory.reference_signature)
        self.assertEqual(d.diagnostics['formation']['region_counts']['L'], 1)
        self.assertEqual(d.diagnostics['formation']['region_counts']['B'], 1)

    def test_symmetric_forward_corners_do_not_receive_left_or_id_priority(self):
        d = self.f.ready(neighbors=((19., 1.65, 5.), (19., 8.25, 5.)), y=4.95)
        self.assertIsNone(d.memory.reference_signature)
        self.assertEqual(d.diagnostics['formation']['selection_rule'], 'ambiguous_forward_corner')

    def test_eight_region_diagnostics_use_visible_road_lanes(self):
        neighbors = ((20., 4.95, 5.), (-20., 4.95, 5.), (0., 8.25, 5.), (0., 1.65, 5.),
                     (20., 8.25, 5.), (20., 1.65, 5.), (-20., 8.25, 5.), (-20., 1.65, 5.))
        d = self.f.decide(self.f.control(neighbors=neighbors, y=4.95), self.p)
        self.assertEqual(d.diagnostics['formation']['region_counts'],
                         {'F':1, 'B':1, 'L':1, 'R':1, 'FL':1, 'FR':1, 'BL':1, 'BR':1, 'X':0})

    def test_held_visible_forward_reference_precedes_new_better_front(self):
        d = self.f.ready(neighbors=((34., 4.95, 5.),))
        for i in range(21, 34):
            d = self.f.decide(self.f.control(time=i/10, memory=d.memory,
                                  neighbors=((34., 4.95, 5.), (30., 1.65, 5.))), self.p)
        self.assertAlmostEqual(d.diagnostics['formation']['target_error_m'], 19.)
        self.assertEqual(d.diagnostics['formation']['selection_rule'], 'hold_visible_forward_reference')

    def test_unsupported_rule_is_rejected_when_enabled(self):
        with self.assertRaises(ValueError):
            self.f.decide(self.f.control(), {**self.p, 'formation_reference_rule':'adaptive_try_until_success'})


if __name__ == '__main__':
    unittest.main()
