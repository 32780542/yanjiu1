from dataclasses import replace
import importlib.util
import unittest
from unittest.mock import Mock


class MultiClockTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('simulation.multi_vehicle'), 'Phase 3 multi-vehicle clock missing')
        from models.vehicle import VehicleModel, VehicleState, Actuation
        from perception.road import VisibleRoad
        from research.common import settings
        from simulation.multi_vehicle import MultiVehicleClock, FleetBridge
        self.Clock, self.Bridge = MultiVehicleClock, FleetBridge
        self.model, self.State, self.Action = VehicleModel.from_config(), VehicleState, Actuation
        self.p = {**dict(self.model.p), **settings('phase3')}
        self.initial = {'a': self.State(x_m=300, y_m=1.65, vx_mps=20),
                        'b': self.State(x_m=330, y_m=1.65, vx_mps=15),
                        'c': self.State(x_m=330, y_m=4.95, vx_mps=20)}
        self.road = VisibleRoad((), ())

    def test_every_control_input_uses_same_frozen_frame_and_order_is_irrelevant(self):
        a = self.Clock(self.initial, self.model, self.road, self.p)
        b = self.Clock(dict(reversed(list(self.initial.items()))), self.model, self.road, self.p)
        for _ in range(3):
            x, y = a.tick(order=('a','b','c')), b.tick(order=('c','b','a'))
            self.assertEqual(x, y)
            self.assertEqual(a.states, b.states)
            times = {i['ego']['time_s'] for i in x['inputs'].values()}
            self.assertEqual(len(times), 1)
            self.assertEqual(x['inputs']['a']['observation']['neighbors'][0]['relative_x_m'],
                             x['initial']['b']['x_m']-x['initial']['a']['x_m'])
        with self.assertRaises(TypeError):
            a.states['a'] = self.initial['b']

    def test_missing_duplicate_vehicle_order_and_mixed_clock_rejected(self):
        for order in (('a','b'), ('a','b','b'), ('a','b','c','x')):
            with self.assertRaises(ValueError):
                self.Clock(self.initial,self.model,self.road,self.p).tick(order=order)
        with self.assertRaises(ValueError):
            self.Clock({**self.initial,'b':replace(self.initial['b'],time_s=.1)},self.model,self.road,self.p)
        with self.assertRaises(ValueError):
            self.Clock(self.initial,self.model,self.road,{**self.p,'perception_dt_s':.2})

    def fake_connection(self):
        from models.geometry import to_sumo_pose
        c = Mock()
        c.simulation.getDeltaT.return_value = .1
        c.simulation.getTime.side_effect = lambda: c.test_time
        c.test_time = .2
        c.poses = {k:to_sumo_pose(s,4.) for k,s in self.initial.items()}
        c.pending, c.speeds, c.old_speeds = {}, {k:s.vx_mps for k,s in self.initial.items()}, {}
        c.vehicle.getPosition.side_effect = lambda k:c.poses[k][:2]
        c.vehicle.getAngle.side_effect = lambda k:c.poses[k][2]
        c.vehicle.getSpeed.side_effect = lambda k:c.speeds[k]
        c.vehicle.getAcceleration.side_effect = lambda k:(c.speeds[k]-c.old_speeds.get(k,c.speeds[k]))/.1
        c.vehicle.getRoadID.return_value = 'upstream'
        c.vehicle.getLaneID.return_value = 'upstream_0'
        c.vehicle.getLaneIndex.return_value = 0
        c.simulation.getCollidingVehiclesNumber.return_value = 0
        c.simulation.getStartingTeleportNumber.return_value = 0
        def speed(k,v):
            c.old_speeds[k],c.speeds[k] = c.speeds[k],v
        def move(k,edge,lane,x,y,angle,keepRoute):
            c.pending[k] = (x,y,angle)
        def step():
            self.assertEqual(set(c.pending),set(self.initial), 'All endpoints queued before world advance')
            c.poses.update(c.pending)
            c.pending.clear()
            c.test_time += .1
        c.vehicle.setSpeed.side_effect,c.vehicle.moveToXY.side_effect,c.simulationStep.side_effect = speed,move,step
        return c

    def test_fleet_submits_every_endpoint_before_exactly_one_sumo_step(self):
        c = self.fake_connection()
        bridge = self.Bridge(c,self.initial,self.model,.1)
        clock = self.Clock(self.initial,self.model,self.road,self.p)
        for _ in range(3):
            record = clock.tick(bridge=bridge)
            self.assertTrue(all(r['passed'] for r in record['readback'].values()))
        self.assertEqual(c.simulationStep.call_count,3)
        self.assertEqual(c.vehicle.moveToXY.call_count,9)
        self.assertAlmostEqual(c.test_time,.5)

    def test_corruption_is_rejected_before_any_commit_and_extra_native_step_detected(self):
        for mode in ('missing', 'duplicate', 'teleport', 'external_step'):
            c = self.fake_connection()
            bridge = self.Bridge(c,self.initial,self.model,.1)
            steps = {k:self.model.advance(s,self.Action(0,0),.1,.01) for k,s in self.initial.items()}
            if mode == 'missing':
                del steps['b']
            elif mode == 'duplicate':
                steps['b'] = self.model.advance(steps['b'].final,self.Action(0,0),.1,.01)
            elif mode == 'teleport':
                steps['b'] = replace(steps['b'],final=replace(steps['b'].final,x_m=900))
            else:
                c.test_time += .1
            with self.assertRaises((ValueError, RuntimeError)):
                bridge.synchronize(steps)
            self.assertEqual(c.simulationStep.call_count,0)
            self.assertEqual(c.vehicle.moveToXY.call_count,0)

    def test_readback_failure_poisoning_prevents_retry_or_hidden_recovery(self):
        c = self.fake_connection()
        bridge = self.Bridge(c,self.initial,self.model,.1)
        clock = self.Clock(self.initial,self.model,self.road,self.p)
        original = c.simulationStep.side_effect
        def corrupt():
            original()
            c.poses['b'] = (999,1.65,90)
        c.simulationStep.side_effect = corrupt
        with self.assertRaises(RuntimeError):
            clock.tick(bridge=bridge)
        self.assertEqual(clock.states,self.initial)
        self.assertEqual(clock.last_record['status'],'failed')
        with self.assertRaises(RuntimeError):
            clock.tick(bridge=bridge)
        self.assertEqual(c.simulationStep.call_count,1)

    def test_failed_precommit_and_partial_postcommit_keep_current_readback_evidence(self):
        for mode in ('precommit','postcommit'):
            c = self.fake_connection()
            bridge = self.Bridge(c,self.initial,self.model,.1)
            clock = self.Clock(self.initial,self.model,self.road,self.p)
            clock.tick(bridge=bridge)
            if mode == 'precommit':
                c.test_time += .1
            else:
                original = c.vehicle.getPosition.side_effect
                def position(key):
                    if key == 'b' and c.test_time > .35:
                        raise RuntimeError('injected unavailable vehicle b')
                    return original(key)
                c.vehicle.getPosition.side_effect = position
            with self.assertRaises(RuntimeError):
                clock.tick(bridge=bridge)
            reports = clock.last_record['readback']
            self.assertEqual(clock.last_record['readback_phase'],mode)
            self.assertAlmostEqual(reports['a']['sumo_time_s'],.4)
            if mode == 'precommit':
                self.assertFalse(reports['a']['passed'])
                self.assertAlmostEqual(reports['a']['time_error_s'],.1)
            else:
                self.assertIn('injected unavailable',reports['b']['errors'][0])
                self.assertFalse(reports['b']['passed'])
                self.assertEqual(reports['c']['status'],'not_read')

    def test_initialization_failure_exposes_partial_bootstrap_readbacks(self):
        c = self.fake_connection()
        c.poses['b'] = (999,1.65,90)
        with self.assertRaises(RuntimeError) as caught:
            self.Bridge(c,self.initial,self.model,.1)
        reports = getattr(caught.exception,'fleet_initial_reports',{})
        self.assertIn('a',reports)
        self.assertTrue(reports['a']['passed'])
        self.assertFalse(reports['b']['passed'])
        self.assertEqual(reports['b']['front_x_m'],999)
        self.assertEqual(reports['c']['status'],'not_read')
