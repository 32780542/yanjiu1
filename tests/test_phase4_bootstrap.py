"""Live regressions for installing dense prescribed initial states."""
from pathlib import Path
import tempfile
import unittest

from research.common import ROOT, settings, read_json
from models.kinematic import KinematicModel, kinematic_state
from models.vehicle import VehicleState, Actuation


class Phase4BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.model = KinematicModel.from_config()
        self.p = {**self.model.p, **settings('phase3'), **settings('phase4_experiments')}

    def test_dense_prescribed_queue_initializes_and_advances(self):
        from experiments.phase4_bootstrap import bootstrap
        from experiments.phase4_cases import cases
        from simulation.noa_clock import NoaClock
        from perception.road import VisibleRoad
        case = next(c for c in cases(self.model.p) if c['name'] == 'merge_no_gap')
        initial = {k:VehicleState(**s) for k,s in case['initial'].items()}
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            path = Path(tmp)
            with (path/'stdout.log').open('w') as stream:
                conn, bridge = bootstrap(path, initial, self.model, self.p, stream)
                try:
                    self.assertEqual(set(conn.vehicle.getIDList()), set(initial))
                    self.assertTrue(all(r['passed'] for r in bridge.initial_reports.values()))
                    clock = NoaClock(initial, self.model, VisibleRoad.from_net('scenarios/cai2024/bottleneck.net.xml'),
                                     self.p, {**self.model.p, **settings('phase4')}, case['controlled'], case['scripts'])
                    for _ in range(3):
                        clock.tick(bridge)
                    self.assertEqual(bridge.advances, 3)
                    self.assertEqual(conn.simulation.getCollidingVehiclesNumber(), 0)
                    self.assertEqual(read_json(path/'bootstrap.json')['excluded_initialization_steps'], 2)
                finally:
                    conn.close()

    def test_true_physical_collision_still_terminates_bridge(self):
        from experiments.phase4_bootstrap import bootstrap
        from simulation.external_bridge import SynchronizationError
        initial = {'rear':kinematic_state(self.model.p, x_m=300, y_m=1.65, vx_mps=20),
                   'front':kinematic_state(self.model.p, x_m=310, y_m=1.65, vx_mps=0)}
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            path = Path(tmp)
            with (path/'stdout.log').open('w') as stream:
                conn, bridge = bootstrap(path, initial, self.model, self.p, stream)
                try:
                    current = initial
                    with self.assertRaises(SynchronizationError):
                        for _ in range(8):
                            steps = {k:self.model.advance(s, Actuation(0, 0), .1, .01) for k,s in current.items()}
                            bridge.synchronize(steps)
                            current = {k:s.final for k,s in steps.items()}
                    self.assertTrue(bridge.failed)
                    self.assertGreater(conn.simulation.getCollidingVehiclesNumber(), 0)
                finally:
                    conn.close()

    def test_cross_edge_and_lateral_offset_initial_readback(self):
        from experiments.phase4_bootstrap import bootstrap
        initial = {'up':kinematic_state(self.model.p, x_m=990, y_m=1.8, vx_mps=18),
                   'down':kinematic_state(self.model.p, x_m=1030, y_m=4.84, vx_mps=15)}
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            path = Path(tmp)
            with (path/'stdout.log').open('w') as stream:
                conn, bridge = bootstrap(path, initial, self.model, self.p, stream)
                try:
                    self.assertEqual({r['edge_id'] for r in bridge.initial_reports.values()}, {'upstream', 'downstream'})
                    self.assertTrue(all(r['position_error_m'] < 1e-8 for r in bridge.initial_reports.values()))
                finally:
                    conn.close()
