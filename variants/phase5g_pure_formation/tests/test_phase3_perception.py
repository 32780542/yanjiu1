from dataclasses import asdict, replace
import importlib.util
import json
import math
import unittest


class IdealPerceptionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('perception.ideal'), 'Phase 3 adapter missing')
        from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
        from perception.road import VisibleRoad
        from models.vehicle import VehicleState
        from research.common import settings
        self.Sensor, self.Truth, self.Frame = IdealSensor, TruthVehicle, WorldFrame
        self.State = VehicleState
        self.p = {**settings('no_comm_main'), **settings('phase3')}
        self.road = VisibleRoad((), ())

    def car(self, key, x, y=0, **kw):
        return self.Truth(key, self.State(x_m=x, y_m=y, **kw), 4., 1.8)

    def sample(self, cars, sensor=None):
        return (sensor or self.Sensor(self.p, self.road)).sample('ego', self.Frame(tuple(cars)))

    def test_rectangle_includes_all_four_edges_excludes_outside_and_no_occlusion(self):
        cars = [self.car('ego', 300), self.car('front', 500), self.car('rear', 200),
                self.car('left', 300, 50), self.car('right', 300, -50),
                self.car('blocking', 320), self.car('behind_blocker', 340),
                self.car('outf', 500.000001), self.car('outr', 199.999999),
                self.car('outy', 300, 50.000001)]
        inp = self.sample(cars)
        self.assertEqual(len(inp.observation.neighbors), 6)
        self.assertEqual({(n.relative_x_m, n.relative_y_m) for n in inp.observation.neighbors},
                         {(200, 0), (-100, 0), (0, 50), (0, -50), (20, 0), (40, 0)})
        self.assertTrue(all(n.measurement_time_s == 0 for n in inp.observation.neighbors))

    def test_rotation_and_velocity_are_world_vectors_rotated_to_ego_axes(self):
        a = self.car('ego', 300, 10, heading_rad=math.pi/2, vx_mps=10, vy_mps=2)
        b = self.car('b', 297, 30, heading_rad=0, vx_mps=7, vy_mps=1)
        n = self.sample([a, b]).observation.neighbors[0]
        self.assertAlmostEqual(n.relative_x_m, 20)
        self.assertAlmostEqual(n.relative_y_m, 3)
        self.assertAlmostEqual(n.relative_vx_mps, -9)
        self.assertAlmostEqual(n.relative_vy_mps, -9)
        self.assertAlmostEqual(n.relative_heading_rad, -math.pi/2)

    def test_rotated_corner_and_side_road_survive_roundoff_but_real_outside_does_not(self):
        from perception.road import VisibleRoad
        road = VisibleRoad(((((250,200)),((250,210))),), ())
        own = self.car('ego',300,10,heading_rad=math.pi/2)
        corner = self.car('corner',250,210)
        outside = self.car('outside',250-1e-6,210)
        inp = self.sample([own,corner,outside],self.Sensor(self.p,road))
        self.assertEqual(len(inp.observation.neighbors),1)
        self.assertAlmostEqual(inp.observation.neighbors[0].relative_y_m,50)
        self.assertEqual(len(inp.observation.road.boundary_polylines_m),1)

    def test_cross_edge_parallel_and_mid_lane_change_use_continuous_position(self):
        cars = [self.car('ego', 990, 1.65), self.car('downstream_0_NOA', 1010, 1.65),
                self.car('parallel', 990, 4.95), self.car('changing', 998, 3.217, vy_mps=.4)]
        obs = self.sample(cars).observation
        self.assertEqual(len(obs.neighbors), 3)
        n = next(n for n in obs.neighbors if n.relative_vy_mps == .4)
        self.assertAlmostEqual(n.relative_y_m, 1.567)

    def test_local_tracks_exit_reenter_new_number_and_memory_expires_without_truth_refresh(self):
        sensor = self.Sensor(self.p, self.road)
        inp = self.sample([self.car('ego', 300), self.car('b', 330)], sensor)
        old = inp.observation.neighbors[0].track_id
        inp = self.sample([self.car('ego', 300, time_s=.1), self.car('b', 330, time_s=.1)], sensor)
        self.assertEqual(inp.observation.neighbors[0].track_id, old)
        inp = self.sample([self.car('ego', 300, time_s=.2), self.car('b', 800, time_s=.2)], sensor)
        self.assertEqual(inp.observation.neighbors, ())
        self.assertEqual(inp.memory.observation_history[-1].neighbors[0].relative_x_m, 30)
        inp = self.sample([self.car('ego', 300, time_s=.3), self.car('b', 330, time_s=.3)], sensor)
        self.assertNotEqual(inp.observation.neighbors[0].track_id, old)
        for i in range(4, 20):
            inp = self.sample([self.car('ego', 300, time_s=i*.1)], sensor)
        self.assertTrue(all(o.time_s >= inp.ego.time_s-self.p['memory_horizon_s']-1e-9
                            for o in inp.memory.observation_history))
        self.assertTrue(all(not o.neighbors for o in inp.memory.observation_history))

    def test_mixed_time_duplicate_key_repeat_time_and_nonfinite_rejected(self):
        for cars in ([self.car('ego', 300), self.car('b', 330, time_s=.1)],
                     [self.car('ego', 300), self.car('ego', 330)],
                     [self.car('ego', 300), self.car('b', math.nan)]):
            with self.assertRaises(ValueError):
                self.sample(cars)
        sensor = self.Sensor(self.p, self.road)
        self.sample([self.car('ego', 300)], sensor)
        with self.assertRaises(ValueError):
            self.sample([self.car('ego', 300)], sensor)

    def test_hidden_id_type_plan_outside_and_iteration_order_do_not_change_input_or_action(self):
        from perception.probe import probe_action
        base = [self.car('ego', 300, vx_mps=20), self.car('NOA_001', 330, vx_mps=15), self.car('HDV_2', 360, 3.3)]
        other = [replace(base[2], key='z', hidden_type='NOA', future_plan=('brake',)),
                 self.car('outside', 900, vx_mps=33), base[0],
                 replace(base[1], key='aaa', hidden_type='HDV', future_plan=('accelerate',))]
        a, b = self.sample(base), self.sample(other)
        self.assertEqual(a, b)
        self.assertEqual(probe_action(a, self.p), probe_action(b, self.p))
        encoded = json.dumps(asdict(b))
        for word in ('NOA_001', 'HDV_2', 'hidden_type', 'future_plan', 'outside', 'aaa'):
            self.assertNotIn(word, encoded)
        clear = self.sample([base[0]])
        self.assertNotEqual(probe_action(a, self.p), probe_action(clear, self.p), 'Non-vacuous action audit')

    def test_probe_is_invariant_to_track_label_and_absolute_position(self):
        from perception.probe import probe_action
        inp = self.sample([self.car('ego', 300, vx_mps=20), self.car('b', 330, vx_mps=15)])
        n = replace(inp.observation.neighbors[0], track_id=999)
        moved = replace(inp, ego=replace(inp.ego, x_m=1000, y_m=500),
                        observation=replace(inp.observation, neighbors=(n,)))
        self.assertEqual(probe_action(inp, self.p), probe_action(moved, self.p))

    def test_road_clipping_hides_future_drop_until_inclusive_boundary(self):
        from perception.road import VisibleRoad
        road = VisibleRoad.from_net('scenarios/cai2024/bottleneck.net.xml')
        before = self.sample([self.car('ego', 799, 1.65)], self.Sensor(self.p, road)).observation.road
        visible = self.sample([self.car('ego', 800, 1.65)], self.Sensor(self.p, road)).observation.road
        self.assertFalse(any(abs(a[0]-b[0]) < 1e-8 for a,b in before.boundary_polylines_m))
        self.assertTrue(any(a[0] == b[0] == 200 for a,b in visible.boundary_polylines_m))
        for heading in (0, .2, math.pi/2):
            r = self.sample([self.car('ego', 900, 4.95, heading_rad=heading)], self.Sensor(self.p, road)).observation.road
            for line in r.boundary_polylines_m+r.marking_polylines_m:
                for x,y in line:
                    self.assertTrue(-100-1e-9 <= x <= 200+1e-9 and abs(y) <= 50+1e-9)
        altered = VisibleRoad((((0,0),(1500,0)), ((0,9.9),(1400,9.9))),
                              (((0,3.3),(1400,3.3)), ((0,6.6),(1400,6.6))))
        far = self.sample([self.car('ego', 500, 1.65)], self.Sensor(self.p, road))
        alt = self.sample([self.car('ego', 500, 1.65)], self.Sensor(self.p, altered))
        self.assertEqual(far, alt)
