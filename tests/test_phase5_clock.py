"""Same frozen observations and once-only physical integration for formation."""
from dataclasses import asdict
import importlib.util
import unittest

from models.kinematic import KinematicModel
from models.vehicle import VehicleState
from perception.road import VisibleRoad
from research.common import settings
from simulation.noa_clock import NoaClock


class FormationClockTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('simulation.formation_clock'), 'Missing phase5 clock')
        from simulation.formation_clock import FormationClock
        self.Clock = FormationClock
        self.model = KinematicModel.from_config()
        self.p = {**self.model.p, **settings('phase3'), 'formation_enabled':True}
        self.policy = {**self.model.p, **settings('phase4'), **settings('phase5'),
                       'formation_enabled':True, 'noa_target_speed_mps':5.}
        self.initial = {'a':VehicleState(x_m=300., y_m=1.65, vx_mps=5.),
                        'b':VehicleState(x_m=319., y_m=4.95, vx_mps=5.)}
        self.road = VisibleRoad((((0., 0.), (2000., 0.)), ((0., 6.6), (2000., 6.6))),
                                (((0., 3.3), (2000., 3.3)),))

    def clock(self, on=True, **kwargs):
        return self.Clock(self.initial, self.model, self.road, {**self.p, 'formation_enabled':on},
                          {**self.policy, 'formation_enabled':on}, tuple(self.initial), {}, **kwargs)

    def test_off_full_records_are_original_clock_identical(self):
        p = {**self.p, 'formation_enabled':False}
        policy = {**self.policy, 'formation_enabled':False}
        a, b = self.clock(False), NoaClock(self.initial, self.model, self.road, p, policy, tuple(self.initial), {})
        for _ in range(15):
            self.assertEqual(a.tick(), b.tick())

    def test_on_order_independent_frozen_inputs_and_single_integration(self):
        a, b = self.clock(), self.clock()
        for _ in range(15):
            x, y = a.tick(order=('a', 'b')), b.tick(order=('b', 'a'))
            self.assertEqual(x, y)
            self.assertEqual(len(x['steps']['a']['samples']), 10)
            self.assertAlmostEqual(x['inputs']['a']['observation']['neighbors'][0]['relative_x_m'],
                                   x['initial']['b']['x_m']-x['initial']['a']['x_m'])
            self.assertEqual(x['inputs']['a']['ego']['time_s'], x['inputs']['b']['ego']['time_s'])
            for key in self.initial:
                self.assertAlmostEqual(x['steps'][key]['final']['time_s']-x['initial'][key]['time_s'], .1)

    def test_refined_integrator_retains_one_control_commit(self):
        a = self.clock()
        a.integration_dt = .005
        record = a.tick()
        self.assertEqual(len(record['steps']['a']['samples']), 20)
        self.assertAlmostEqual(a.states['a'].time_s, .1)

    def test_communication_and_inconsistent_switches_rejected(self):
        with self.assertRaises(ValueError):
            self.Clock(self.initial, self.model, self.road, {**self.p, 'communication_enabled':True},
                       self.policy, tuple(self.initial), {})
        with self.assertRaises(ValueError):
            self.Clock(self.initial, self.model, self.road, self.p,
                       {**self.policy, 'formation_enabled':False}, tuple(self.initial), {})

    def test_controller_sampling_period_must_match_physical_clock(self):
        for on in (False, True):
            with self.assertRaisesRegex(ValueError, 'control.*period'):
                self.Clock(self.initial, self.model, self.road,
                           {**self.p, 'formation_enabled':on, 'control_sync_dt_s':.05, 'perception_dt_s':.05},
                           {**self.policy, 'formation_enabled':on}, tuple(self.initial), {})
        # Half-rate feedback changes its declared sampler, not gains/response.
        refined = self.Clock(self.initial, self.model, self.road,
                             {**self.p, 'control_sync_dt_s':.05, 'perception_dt_s':.05},
                             {**self.policy, 'control_sync_dt_s':.05}, tuple(self.initial), {})
        record = refined.tick()
        self.assertAlmostEqual(record['steps']['a']['final']['time_s'], .05)
        self.assertEqual(len(record['steps']['a']['samples']), 5)


if __name__ == '__main__':
    unittest.main()
