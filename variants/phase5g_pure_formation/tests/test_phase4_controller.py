"""Behavioral tests for the pure finite-observation NOA baseline."""
from dataclasses import asdict, replace
import importlib.util
import json
import math
import unittest

from models.kinematic import KinematicModel
from models.vehicle import VehicleState
from perception.contracts import ControlInput, EgoState, LocalMemory
from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
from perception.road import VisibleRoad
from research.common import settings


class NoaControllerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('noa'), 'Missing pure NOA controller package')
        from noa.controller import decide
        from noa.contracts import NoaMemory
        self.decide, self.Memory = decide, NoaMemory
        self.model = KinematicModel.from_config()
        self.p = {**self.model.p, **settings('phase4')}

    def road(self, shift=(0., 0.), end=None, lane_count=3):
        x, y = shift
        upper = lane_count*3.3
        boundaries = [((x-300., y), (x+1200., y))]
        markings = [((x-300., y+3.3*k), (x+1200., y+3.3*k)) for k in range(1, lane_count)]
        if end is None:
            boundaries += [((x-300., y+upper), (x+1200., y+upper))]
        else:
            boundaries += [((x-300., y+upper), (x+end, y+upper)),
                           ((x+end, y+upper), (x+end, y+upper-3.3)),
                           ((x+end, y+upper-3.3), (x+1200., y+upper-3.3))]
            markings[-1] = ((x-300., y+upper-3.3), (x+end, y+upper-3.3))
        return VisibleRoad(tuple(boundaries), tuple(markings))

    def control(self, ego=None, neighbors=(), road=None, memory=None):
        ego = ego or VehicleState(x_m=100., y_m=1.65, vx_mps=20.)
        sensor = IdealSensor({**self.model.p, **settings('phase3')}, road or self.road())
        frame = WorldFrame((TruthVehicle('ego', ego, 4., 1.8),) + tuple(
            TruthVehicle(str(i), state, 4., 1.8) for i, state in enumerate(neighbors)))
        control = sensor.sample('ego', frame)
        return replace(control, memory=memory or self.Memory((), 'CRUISE'))

    def test_cruise_has_immutable_json_reconstructable_own_memory(self):
        from noa.contracts import memory_from_dict
        control = self.control()
        decision = self.decide(control, self.p)
        self.assertEqual(decision.memory.own_behavior, 'CRUISE')
        self.assertEqual(decision.action.acceleration_mps2, 0.)
        self.assertAlmostEqual(decision.action.steering_rad, 0.)
        encoded = json.loads(json.dumps(asdict(decision), allow_nan=False))
        self.assertEqual(memory_from_dict(encoded['memory']), decision.memory)
        self.assertIsInstance(decision.memory, LocalMemory)

    def test_visible_slow_lead_changes_acceleration_and_close_hazard_brakes(self):
        clear = self.decide(self.control(), self.p)
        slow = VehicleState(x_m=140., y_m=1.65, vx_mps=10.)
        following = self.decide(self.control(neighbors=(slow,), road=self.road(lane_count=1)), self.p)
        self.assertLess(following.action.acceleration_mps2, clear.action.acceleration_mps2)
        stopped = replace(slow, x_m=113., vx_mps=0.)
        hazard = self.decide(self.control(neighbors=(stopped,)), self.p)
        self.assertEqual(hazard.memory.own_behavior, 'EMERGENCY')
        self.assertLessEqual(hazard.action.acceleration_mps2, -3.)

    def test_lane_keeping_steers_back_toward_observed_center(self):
        low = self.decide(self.control(ego=VehicleState(x_m=100, y_m=1.3, vx_mps=18)), self.p)
        high = self.decide(self.control(ego=VehicleState(x_m=100, y_m=2.0, vx_mps=18)), self.p)
        self.assertGreater(low.action.steering_rad, 0.)
        self.assertLess(high.action.steering_rad, 0.)

    def test_local_ids_and_neighbor_order_do_not_change_actions_or_diagnostics(self):
        n = (VehicleState(x_m=175., y_m=1.65, vx_mps=10.),
             VehicleState(x_m=60., y_m=4.95, vx_mps=30.))
        c = self.control(neighbors=n)
        altered = replace(c, observation=replace(c.observation, neighbors=tuple(
            replace(item, track_id=1000-i) for i, item in enumerate(reversed(c.observation.neighbors)))))
        a, b = self.decide(c, self.p), self.decide(altered, self.p)
        self.assertEqual(a.action, b.action)
        self.assertEqual(a.diagnostics, b.diagnostics)
        self.assertEqual(a.memory, b.memory)

    def test_clear_overtake_prepares_then_executes_persistent_bezier_plan(self):
        c = self.control(neighbors=(VehicleState(x_m=180., y_m=1.65, vx_mps=10.),))
        first = self.decide(c, self.p)
        self.assertEqual(first.memory.own_behavior, 'PREPARE_LC')
        self.assertIsNone(first.memory.plan)
        t = self.p['noa_prepare_duration_s']
        later = self.control(ego=VehicleState(time_s=t, x_m=100+20*t, y_m=1.65, vx_mps=20),
                             neighbors=(VehicleState(time_s=t, x_m=180+10*t, y_m=1.65, vx_mps=10),),
                             memory=first.memory)
        second = self.decide(later, self.p)
        self.assertEqual(second.memory.own_behavior, 'EXECUTE_LC')
        self.assertIsNotNone(second.memory.plan)
        self.assertGreater(second.memory.plan.y_target_m, second.memory.plan.y_start_m)
        self.assertEqual(second.memory.plan.start_s, t)
        from noa.contracts import memory_from_dict
        self.assertEqual(memory_from_dict(json.loads(json.dumps(asdict(second.memory)))), second.memory)

    def test_fast_rear_and_blocked_gap_reject_candidate(self):
        lead = VehicleState(x_m=180., y_m=1.65, vx_mps=10.)
        for rear in (VehicleState(x_m=60., y_m=4.95, vx_mps=30.),
                     VehicleState(x_m=105., y_m=4.95, vx_mps=20.)):
            decision = self.decide(self.control(neighbors=(lead, rear)), self.p)
            self.assertIsNone(decision.memory.plan)
            self.assertTrue(decision.diagnostics['candidate_rejections'])
            self.assertNotEqual(decision.memory.own_behavior, 'EXECUTE_LC')

    def test_terminating_lane_uses_observed_geometry_and_translates_with_road(self):
        a = self.control(ego=VehicleState(x_m=100., y_m=8.25, vx_mps=20.), road=self.road(end=240.))
        b = self.control(ego=VehicleState(x_m=237., y_m=28.25, vx_mps=20.),
                         road=self.road(shift=(137., 20.), end=240.))
        da, db = self.decide(a, self.p), self.decide(b, self.p)
        self.assertEqual(da.memory.own_behavior, 'PREPARE_LC')
        self.assertEqual(da.diagnostics['reason'], 'observed_lane_end')
        self.assertAlmostEqual(da.action.acceleration_mps2, db.action.acceleration_mps2)
        self.assertAlmostEqual(da.action.steering_rad, db.action.steering_rad)
        self.assertAlmostEqual(da.diagnostics['lane_end_distance_m'], db.diagnostics['lane_end_distance_m'])
        self.assertAlmostEqual(db.memory.target_y_m-da.memory.target_y_m, 20.)

    def test_road_outside_observation_does_not_trigger_a_merge(self):
        road = self.road(end=500.)
        d = self.decide(self.control(ego=VehicleState(x_m=100., y_m=8.25, vx_mps=20.), road=road), self.p)
        self.assertEqual(d.memory.own_behavior, 'CRUISE')
        self.assertIsNone(d.diagnostics['lane_end_distance_m'])

    def test_full_horizon_rejects_target_that_ends_before_lane_change_finishes(self):
        ego = VehicleState(x_m=100., y_m=4.95, vx_mps=20.)
        lead = VehicleState(x_m=180., y_m=4.95, vx_mps=10.)
        blocker = VehicleState(x_m=100., y_m=1.65, vx_mps=20.)
        d = self.decide(self.control(ego, (lead, blocker), self.road(end=175.)), self.p)
        self.assertIsNone(d.memory.plan)
        self.assertTrue(d.diagnostics['candidate_rejections'])

    def test_nonfinite_observations_and_parameters_are_rejected(self):
        c = self.control(neighbors=(VehicleState(x_m=140., y_m=1.65, vx_mps=10.),))
        with self.assertRaises(ValueError):
            self.decide(replace(c, ego=replace(c.ego, vx_mps=float('nan'))), self.p)
        bad = replace(c.observation.neighbors[0], relative_vx_mps=float('inf'))
        with self.assertRaises(ValueError):
            self.decide(replace(c, observation=replace(c.observation, neighbors=(bad,))), self.p)
        with self.assertRaises(ValueError):
            self.decide(c, {**self.p, 'noa_target_speed_mps':float('nan')})

    def test_stop_and_restart_command_responds_to_visible_release(self):
        ego = VehicleState(x_m=100., y_m=1.65, vx_mps=0.)
        lead = VehicleState(x_m=107., y_m=1.65, vx_mps=0.)
        held = self.decide(self.control(ego, (lead,), self.road(lane_count=1)), self.p)
        self.assertLessEqual(held.action.acceleration_mps2, 0.)
        released = self.decide(self.control(ego, (), self.road(lane_count=1), held.memory), self.p)
        self.assertGreater(released.action.acceleration_mps2, 0.)

    def rollout(self, initial, road, duration, neighbor_at):
        sensor = IdealSensor({**self.model.p, **settings('phase3')}, road)
        state, memory, records = initial, self.Memory((), 'CRUISE'), []
        for _ in range(round(duration/.1)):
            frame = WorldFrame((TruthVehicle('ego', state, 4., 1.8),)+tuple(
                TruthVehicle(str(i), n, 4., 1.8) for i, n in enumerate(neighbor_at(state.time_s))))
            control = sensor.sample('ego', frame)
            control = replace(control, memory=replace(memory, observation_history=control.memory.observation_history))
            decision = self.decide(control, self.p)
            step = self.model.advance(state, decision.action, .1, .01)
            records.append((state, decision, step))
            state, memory = step.final, decision.memory
        return state, memory, records

    def test_closed_loop_lane_change_completes_without_snapping_or_road_exit(self):
        from safety.geometry import RoadEnvelope
        from models.geometry import body_from_state
        initial = VehicleState(x_m=100., y_m=1.65, vx_mps=20.)
        final, memory, records = self.rollout(initial, self.road(), 12., lambda t: (
            VehicleState(time_s=t, x_m=180+10*t, y_m=1.65, vx_mps=10.),))
        self.assertGreaterEqual(memory.completed_lane_changes, 1)
        self.assertAlmostEqual(final.y_m, 4.95, delta=.2)
        road = RoadEnvelope(((0., 1200., 0., 9.9),))
        for initial, decision, step in records:
            previous = initial
            for sample in step.samples:
                self.assertTrue(road.contains(body_from_state(sample, self.p)))
                self.assertLessEqual(math.hypot(sample.x_m-previous.x_m, sample.y_m-previous.y_m), .334)
                previous = sample

    def test_closed_loop_clear_merge_completes_before_physical_endpoint(self):
        initial = VehicleState(x_m=100., y_m=8.25, vx_mps=18.)
        final, memory, records = self.rollout(initial, self.road(end=250.), 12., lambda t: ())
        self.assertTrue(any(d.memory.own_behavior == 'MERGE' for _, d, _ in records))
        self.assertGreaterEqual(memory.completed_lane_changes, 1)
        self.assertLess(final.y_m, 6.6-self.p['width_m']/2)
        for _, _, step in records:
            for state in step.samples:
                if state.x_m+self.p['length_m']/2 >= 250.:
                    self.assertLess(state.y_m+self.p['width_m']/2, 6.6)

    def test_execution_rechecks_a_new_blocker_without_replacing_reference(self):
        from models.bezier import QuadraticLaneChange
        plan = QuadraticLaneChange(0., 1.65, 4.95, 5., 20.)
        memory = self.Memory((), 'EXECUTE_LC', plan, 4.95, 0., 'slower_visible_lead')
        ego = VehicleState(time_s=1., x_m=120., y_m=1.9, vx_mps=20.)
        # At x128 the ego passes the lateral neighbor before its body enters
        # that lane; x160 obstructs the actual future swept path.
        blocker = VehicleState(time_s=1., x_m=160., y_m=4.95, vx_mps=0.)
        decision = self.decide(self.control(ego, (blocker,), memory=memory), self.p)
        self.assertEqual(decision.memory.plan, plan)
        self.assertEqual(decision.memory.own_behavior, 'EMERGENCY')
        self.assertFalse(decision.diagnostics['prediction']['safe'])
        self.assertLessEqual(decision.action.acceleration_mps2, -self.p['comfort_braking_mps2'])

    def test_execution_can_pass_side_vehicle_before_lateral_overlap(self):
        from models.bezier import QuadraticLaneChange
        plan=QuadraticLaneChange(0.,1.65,4.95,5.,20.)
        memory=self.Memory((), 'EXECUTE_LC', plan,4.95,0.,'slower_visible_lead')
        ego=VehicleState(time_s=1.,x_m=120.,y_m=1.9,vx_mps=20.)
        side=VehicleState(time_s=1.,x_m=128.,y_m=4.95,vx_mps=0.)
        decision=self.decide(self.control(ego,(side,),memory=memory),self.p)
        self.assertEqual(decision.memory.plan,plan)
        self.assertEqual(decision.memory.own_behavior,'EXECUTE_LC')
        self.assertTrue(decision.diagnostics['prediction']['safe'])

    def test_invalid_physical_limits_and_negative_prediction_margin_are_rejected(self):
        for name, value in (('min_accel_mps2', float('nan')), ('max_steering_rad', float('inf')),
                            ('noa_body_margin_m', -.1), ('noa_prediction_lateral_accel_bound_mps2', -.1),
                            ('behavior_dt_s', .53)):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.decide(self.control(), {**self.p, name:value})

    def test_observed_cut_in_affects_braking_before_current_lateral_overlap(self):
        ego = VehicleState(x_m=100., y_m=1.65, vx_mps=20.)
        cut = VehicleState(x_m=135., y_m=4.95, vx_mps=12., vy_mps=-2.)
        a = self.decide(self.control(ego, (cut,), self.road(lane_count=2)), self.p)
        b = self.decide(self.control(ego, (replace(cut, vy_mps=0.),), self.road(lane_count=2)), self.p)
        self.assertLess(a.action.acceleration_mps2, b.action.acceleration_mps2)

    def test_closed_loop_stops_behind_stationary_lead_then_restarts(self):
        initial = VehicleState(x_m=100., y_m=1.65, vx_mps=12.)
        def neighbors(t):
            x = 160. if t < 15. else 160.+10*(t-15.)
            v = 0. if t < 15. else 10.
            return (VehicleState(time_s=t, x_m=x, y_m=1.65, vx_mps=v),)
        final, _, records = self.rollout(initial, self.road(lane_count=1), 25., neighbors)
        self.assertLess(min(s.vx_mps for s, _, _ in records[:150]), .2)
        self.assertGreater(final.vx_mps, 2.)
        for _, _, step in records:
            for sample in step.samples:
                lead = neighbors(sample.time_s)[0]
                self.assertLess(sample.x_m+4., lead.x_m)
                self.assertGreaterEqual(sample.vx_mps, 0.)

    def test_blocked_merge_stops_before_boundary_without_starting_unsafe_plan(self):
        initial = VehicleState(x_m=100., y_m=8.25, vx_mps=15.)
        # Two isolated stopped cars leave a legal merge path after the front
        # car. Use a continuous closely spaced queue for a blocked-gap test.
        final, memory, records = self.rollout(initial, self.road(end=225.), 20., lambda t: tuple(
            VehicleState(time_s=t, x_m=float(x), y_m=4.95, vx_mps=0.) for x in range(80, 306, 5)))
        self.assertLess(final.x_m+self.p['length_m']/2, 225.)
        self.assertLess(final.vx_mps, 1.)
        self.assertEqual(memory.completed_lane_changes, 0)
        self.assertTrue(all(d.memory.plan is None for _, d, _ in records))

    def test_longitudinal_reachable_envelope_includes_hard_acceleration_extremes(self):
        from noa.prediction import MeasuredBody, distance_at, reachable_body
        body = MeasuredBody(120., 4.95, 10., 0., 0., 4., 1.8)
        for t in (0., .1, 1., 5.):
            predicted = reachable_body(body, t, self.p)
            xmin, xmax = predicted.x-predicted.length/2, predicted.x+predicted.length/2
            for acceleration in (self.p['min_accel_mps2'], 0., self.p['max_accel_mps2']):
                x = body.x+distance_at(body.vx, acceleration, t, self.p['max_speed_mps'])
                self.assertLessEqual(xmin, x-body.length/2)
                self.assertGreaterEqual(xmax, x+body.length/2)

    def test_existing_local_contract_and_explicit_r5_own_memory_schema(self):
        self.assertEqual(set(asdict(LocalMemory((), 'PROBE'))), {'observation_history', 'own_behavior'})
        self.assertEqual(set(asdict(self.Memory((), 'CRUISE'))) - set(asdict(LocalMemory((), 'PROBE'))),
                         {'plan', 'target_y_m', 'prepare_since_s', 'lane_change_reason',
                          'last_lc_end_s', 'completed_lane_changes',
                          'r5_rng_state','r5_draw_count','r5_phase','r5_deadline_s',
                          'r5_episode_signature','r5_clear_since_s','r5_last_time_s'})

    def test_policy_source_has_no_file_simulator_or_local_id_access(self):
        import ast
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]/'noa'
        for file in root.glob('*.py'):
            if file.name == 'contracts.py':
                continue  # Codec must reconstruct local IDs without using them for control.
            source = ast.parse(file.read_text(encoding='utf-8'))
            for node in ast.walk(source):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(n.name.split('.')[0] not in {'os','sys','pathlib','traci','sumolib','random'} for n in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or '').split('.')[0], {'research','simulation','experiments','traci'})
                if isinstance(node, ast.Attribute):
                    if node.attr == 'track_id' and file.name in {'simple_formation.py','simple_controller.py'}:
                        continue  # 本车传感标签用于跨帧关联；另有标签置换不变性测试。
                    self.assertNotIn(node.attr, {'track_id','hidden_type','future_plan','read_text','read_bytes','from_config'})
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {'open','eval','exec','__import__'})

    def test_speed_cap_zero_actual_acceleration_accounts_for_positive_actuator(self):
        # At the speed cap, observe() returns zero actual acceleration even if
        # the own drive actuator is still positive. The policy cannot treat it
        # as a zero actuator when screening a stop behind a stationary body.
        ego = VehicleState(x_m=100., y_m=1.65, vx_mps=self.p['max_speed_mps'], a_drive_mps2=2.)
        lead = VehicleState(x_m=260., y_m=1.65, vx_mps=0.)
        c = self.control(ego, (lead,), self.road(lane_count=1))
        self.assertEqual(c.ego.acceleration_mps2, 0.)
        decision = self.decide(c, self.p)
        self.assertEqual(decision.memory.own_behavior, 'EMERGENCY')
        self.assertEqual(decision.action.acceleration_mps2, self.p['min_accel_mps2'])

    def test_prediction_defers_capped_unknown_actuator_maneuver(self):
        from noa.prediction import verify_candidate
        from noa.road import reconstruct
        from models.bezier import QuadraticLaneChange
        ego = VehicleState(x_m=100., y_m=1.65, vx_mps=self.p['max_speed_mps'], a_drive_mps2=2.)
        c = self.control(ego)
        road = reconstruct(c.ego, c.observation.road, self.p)
        plan = QuadraticLaneChange(0., 1.65, 4.95, 5., ego.vx_mps)
        check = verify_candidate(c, plan, road, -3., self.p)
        self.assertFalse(check['safe'])
        self.assertEqual(check['reason'], 'own_actuator_unobservable_at_speed_cap')

    def test_prediction_defers_stopped_unknown_negative_actuator(self):
        from noa.prediction import verify_candidate
        from noa.road import reconstruct
        from models.bezier import QuadraticLaneChange
        ego = VehicleState(time_s=2., x_m=120., y_m=2.4, vx_mps=0., a_drive_mps2=-3.)
        c = self.control(ego)
        self.assertEqual(c.ego.acceleration_mps2, 0.)
        road = reconstruct(c.ego, c.observation.road, self.p)
        plan = QuadraticLaneChange(0., 1.65, 4.95, 5., 20.)
        check = verify_candidate(c, plan, road, 2., self.p)
        self.assertFalse(check['safe'])
        self.assertEqual(check['reason'], 'own_actuator_unobservable_at_stop')


if __name__ == '__main__':
    unittest.main()
