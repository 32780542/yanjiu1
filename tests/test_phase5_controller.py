"""Behavioral evidence for local-only longitudinal formation control."""
from dataclasses import asdict, replace
import importlib.util
import json
import unittest

from models.kinematic import KinematicModel
from models.vehicle import VehicleState
from noa.contracts import NoaMemory
from noa.controller import decide as baseline
from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
from perception.road import VisibleRoad
from research.common import settings


def road():
    return VisibleRoad((((-300., 0.), (2000., 0.)), ((-300., 9.9), (2000., 9.9))),
                       (((-300., 3.3), (2000., 3.3)), ((-300., 6.6), (2000., 6.6))))


class FormationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('noa.formation'), 'Missing phase5 controller')
        from noa.formation import FormationMemory, decide
        self.Memory, self.decide = FormationMemory, decide
        self.model = KinematicModel.from_config()
        self.p = {**self.model.p, **settings('phase4'), **settings('phase5'),
                  'formation_enabled':True, 'noa_target_speed_mps':5.}

    def control(self, time=0., memory=None, neighbors=((19., 4.95, 5.),), speed=5., y=1.65):
        e = VehicleState(time_s=time, x_m=100.+time*speed, y_m=y, vx_mps=speed)
        targets = tuple(TruthVehicle(str(i), VehicleState(time_s=time, x_m=e.x_m+x,
                            y_m=ny, vx_mps=v), 4., 1.8) for i, (x, ny, v) in enumerate(neighbors))
        sensor = IdealSensor({**self.model.p, **settings('phase3')}, road())
        c = sensor.sample('ego', WorldFrame((TruthVehicle('ego', e, 4., 1.8),)+targets))
        return replace(c, memory=memory or self.Memory((), 'CRUISE'))

    def ready(self, **kwargs):
        d = self.decide(self.control(**kwargs), self.p)
        for i in range(1, 21):
            d = self.decide(self.control(time=i/10, memory=d.memory, **kwargs), self.p)
        return d

    def test_off_is_exact_baseline_even_with_formation_memory(self):
        c = self.control()
        expected = baseline(replace(c, memory=NoaMemory((), 'CRUISE')), self.p)
        self.assertEqual(self.decide(c, {**self.p, 'formation_enabled':False}), expected)

    def test_forward_reference_requires_one_second_and_smooth_activation(self):
        d = self.decide(self.control(), self.p)
        self.assertIsNone(d.memory.reference_signature)
        for i in range(1, 10):
            d = self.decide(self.control(time=i/10, memory=d.memory), self.p)
            self.assertEqual(d.diagnostics['formation']['applied_increment_mps2'], 0.)
        d = self.decide(self.control(time=1., memory=d.memory), self.p)
        self.assertIsNotNone(d.memory.reference_signature)
        self.assertGreater(d.memory.formation_weight, 0.)
        self.assertLessEqual(d.memory.formation_weight, .1+1e-9)
        self.assertAlmostEqual(d.diagnostics['formation']['target_error_m'], 4.)
        d = self.ready()
        self.assertAlmostEqual(d.memory.formation_weight, 1.)
        self.assertGreater(d.diagnostics['formation']['applied_increment_mps2'], 0.)
        self.assertLessEqual(d.diagnostics['formation']['applied_increment_mps2'], .5)

    def test_no_rear_remote_lane_fast_or_laterally_unstable_reference(self):
        for neighbors in (((-20., 4.95, 5.),), ((19., 8.25, 5.),), ((19., 4.95, 9.),), ()):
            d = self.ready(neighbors=neighbors)
            self.assertIsNone(d.memory.reference_signature)
            self.assertEqual(d.diagnostics['formation']['applied_increment_mps2'], 0.)
        c = self.control()
        n = replace(c.observation.neighbors[0], relative_vy_mps=.21)
        d = self.decide(replace(c, observation=replace(c.observation, neighbors=(n,))), self.p)
        self.assertIsNone(d.memory.candidate_signature)

    def test_same_lane_uses_thirty_metre_target(self):
        d = self.ready(neighbors=((34., 1.65, 5.),))
        self.assertAlmostEqual(d.diagnostics['formation']['target_error_m'], 4.)

    def test_ids_and_order_only_associate_and_never_assign_priority(self):
        a, b = self.Memory((), 'CRUISE'), self.Memory((), 'CRUISE')
        for i in range(21):
            c = self.control(time=i/10, memory=a, neighbors=((19., 4.95, 5.), (40., 1.65, 5.)))
            altered = replace(c, memory=b, observation=replace(c.observation, neighbors=tuple(
                replace(n, track_id=901-n.track_id) for n in reversed(c.observation.neighbors))))
            da, db = self.decide(c, self.p), self.decide(altered, self.p)
            self.assertEqual(da.action, db.action)
            for k in ('target_error_m', 'applied_increment_mps2', 'conflict_residual_m'):
                self.assertEqual(da.diagnostics['formation'][k], db.diagnostics['formation'][k])
            a, b = da.memory, db.memory

    def test_loss_decays_only_cached_increment_then_requires_reacquisition(self):
        d = self.ready()
        previous = d.diagnostics['formation']['applied_increment_mps2']
        for i in range(1, 11):
            d = self.decide(self.control(time=2.+i/10, memory=d.memory, neighbors=()), self.p)
            self.assertLessEqual(abs(d.diagnostics['formation']['applied_increment_mps2']), abs(previous)+1e-12)
            previous = d.diagnostics['formation']['applied_increment_mps2']
            self.assertIsNone(d.diagnostics['formation']['target_error_m'])
        self.assertAlmostEqual(d.memory.formation_weight, 0.)
        self.assertIsNone(d.memory.reference_signature)
        d = self.decide(self.control(time=3.1, memory=d.memory), self.p)
        self.assertEqual(d.diagnostics['formation']['applied_increment_mps2'], 0.)
        for i in range(32, 52):
            d = self.decide(self.control(time=i/10, memory=d.memory), self.p)
        self.assertGreater(d.diagnostics['formation']['applied_increment_mps2'], 0.)

    def test_json_restoration_is_decision_identical(self):
        from noa.formation import memory_from_dict
        d = self.ready()
        memory = memory_from_dict(json.loads(json.dumps(asdict(d.memory), allow_nan=False)))
        self.assertEqual(memory, d.memory)
        self.assertEqual(self.decide(self.control(time=2.1, memory=d.memory), self.p),
                         self.decide(self.control(time=2.1, memory=memory), self.p))

    def test_hazard_or_noa_maneuver_immediately_disables_increment(self):
        d = self.ready()
        for neighbors in (((6., 1.65, 0.), (19., 4.95, 5.)), ((16., 1.65, 2.), (19., 4.95, 5.))):
            c = self.control(time=2.1, memory=d.memory, neighbors=neighbors)
            a, b = self.decide(c, self.p), baseline(c, self.p)
            self.assertEqual(a.action, b.action)
            self.assertEqual(a.diagnostics['formation']['applied_increment_mps2'], 0.)

    def test_existing_prediction_can_reject_increment_without_relaxation(self):
        d = self.ready(neighbors=((29., 1.65, 5.), (19., 4.95, 5.)))
        f = d.diagnostics['formation']
        self.assertIsNotNone(f['prediction'])
        self.assertFalse(f['prediction']['safe'])
        self.assertEqual(f['applied_increment_mps2'], 0.)
        self.assertEqual(f['reason'], 'safety_rejected')

    def test_conflicting_visible_references_reduce_weight(self):
        consistent = self.ready(neighbors=((19., 4.95, 5.), (34., 1.65, 5.)))
        conflict = self.ready(neighbors=((19., 4.95, 5.), (42., 1.65, 5.)))
        self.assertGreater(conflict.diagnostics['formation']['conflict_residual_m'],
                           consistent.diagnostics['formation']['conflict_residual_m'])
        self.assertLess(conflict.memory.formation_weight, consistent.memory.formation_weight)

    def test_invalid_parameter_and_nonmonotonic_memory_are_rejected(self):
        for key, value in (('formation_kp_per_s2', float('nan')), ('formation_fade_s', 0.)):
            with self.assertRaises(ValueError):
                self.decide(self.control(), {**self.p, key:value})
        d = self.ready()
        with self.assertRaises(ValueError):
            self.decide(self.control(time=1., memory=d.memory), self.p)

    def test_stability_requires_consecutive_observations(self):
        d = self.decide(self.control(), self.p)
        d = self.decide(self.control(time=2., memory=d.memory), self.p)
        self.assertIsNone(d.memory.reference_signature)
        self.assertEqual(d.diagnostics['formation']['applied_increment_mps2'], 0.)

    def test_new_reference_cannot_use_previous_reference_stability(self):
        memory = self.Memory((), 'CRUISE')
        for i in range(10):
            c = self.control(time=i/10, memory=memory)
            d = self.decide(c, self.p)
            memory = d.memory
        c = self.control(time=1., memory=memory)
        changed = replace(c, observation=replace(c.observation, neighbors=tuple(
            replace(n, relative_x_m=n.relative_x_m+1.) for n in c.observation.neighbors)))
        d = self.decide(changed, self.p)
        self.assertIsNone(d.memory.reference_signature)
        self.assertEqual(d.memory.candidate_since_s, 1.)

    def test_formation_waits_five_seconds_after_noa_lane_change(self):
        memory = replace(self.Memory((), 'CRUISE'), last_lc_end_s=0.)
        for i in range(50):
            d = self.decide(self.control(time=i/10, memory=memory), self.p)
            self.assertEqual(d.diagnostics['formation']['applied_increment_mps2'], 0.)
            memory = d.memory
        d = self.decide(self.control(time=5., memory=memory), self.p)
        self.assertIsNotNone(d.memory.candidate_signature)
        self.assertIsNone(d.memory.reference_signature)

    def test_equal_physical_cost_ties_use_geometry_not_label_rank(self):
        neighbors = ((19., 1.65, 5.), (19., 8.25, 5.))
        memory_a, memory_b = self.Memory((), 'CRUISE'), self.Memory((), 'CRUISE')
        for i in range(21):
            c = self.control(time=i/10, memory=memory_a, neighbors=neighbors, y=4.95)
            altered = replace(c, memory=memory_b, observation=replace(c.observation, neighbors=tuple(
                replace(n, track_id=900-n.track_id) for n in reversed(c.observation.neighbors))))
            a, b = self.decide(c, self.p), self.decide(altered, self.p)
            self.assertEqual(a.action, b.action)
            memory_a, memory_b = a.memory, b.memory
        self.assertEqual(memory_b.reference_signature, memory_a.reference_signature)

    def test_ambiguous_physical_association_cannot_accumulate_stability(self):
        d = self.decide(self.control(), self.p)
        for i in range(1, 21):
            c = self.control(time=i/10, memory=d.memory)
            item = c.observation.neighbors[0]
            # Two visible records could both be the old reference; neither gets
            # label priority. Deliberate duplicate observations test ambiguity.
            c = replace(c, observation=replace(c.observation,
                        neighbors=(item, replace(item, track_id=item.track_id+100))))
            d = self.decide(c, self.p)
            self.assertIsNone(d.memory.reference_signature)
            self.assertEqual(d.diagnostics['formation']['applied_increment_mps2'], 0.)


if __name__ == '__main__':
    unittest.main()
