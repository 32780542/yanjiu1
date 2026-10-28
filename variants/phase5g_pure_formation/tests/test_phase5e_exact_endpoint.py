"""Phase 5E regression tests for the conservative-speed upper endpoint."""
import unittest

from experiments.phase5_r5 import parameters
from noa.controller import _comfortable_speed, _stop_distance


class ExactFeasibleEndpointTests(unittest.TestCase):
    def setUp(self):
        _, _, self.p = parameters(False)

    def required(self, speed):
        return (_stop_distance(speed, 0., self.p['comfort_braking_mps2'], self.p)
                + speed / self.p['noa_speed_gain_per_s'])

    def test_exactly_feasible_upper_is_returned_exactly(self):
        upper = min(self.p['noa_target_speed_mps'], self.p['max_speed_mps'])
        self.assertEqual(_comfortable_speed(self.required(upper), self.p, 0.), upper)

    def test_infeasible_upper_retains_conservative_lower_solution(self):
        upper = min(self.p['noa_target_speed_mps'], self.p['max_speed_mps'])
        distance = self.required(upper) - 1e-6
        result = _comfortable_speed(distance, self.p, 0.)
        self.assertLess(result, upper)
        self.assertLessEqual(self.required(result), distance)

    def test_phase5e_plan_is_a_bound_experiment_input(self):
        from experiments.phase5_r5 import INPUTS
        self.assertIn('docs/phase5e_exact_endpoint_plan.md', INPUTS)


if __name__ == '__main__':
    unittest.main()
