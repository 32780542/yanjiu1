from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research.common import ROOT,read_json


class LiveBridgeTests(unittest.TestCase):
    def test_dependency_failure_is_persisted_before_sumo_start(self):
        from experiments.phase2 import run_sumo
        from models.vehicle import VehicleModel,VehicleState,Actuation
        model=VehicleModel.from_config()
        steps=[model.advance(VehicleState(x_m=100,y_m=1.65,vx_mps=20),Actuation(0,0),.1,.01)]
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            path=Path(tmp)/'dependency_failure'
            with patch('experiments.phase2.lock_traci',side_effect=RuntimeError('bad dependency')):
                with self.assertRaisesRegex(RuntimeError,'bad dependency'):
                    run_sumo(path,model,steps,.1)
            failed=read_json(path/'validation.json')
            self.assertEqual(failed['status'],'failed')
            self.assertIn('traceback',failed)

    def test_real_sumo_cross_edge_and_both_sync_rates(self):
        from experiments.phase2 import run_sumo
        from models.vehicle import VehicleModel,VehicleState,Actuation
        model=VehicleModel.from_config()
        for dt in (.1,.05):
            state=VehicleState(x_m=994,y_m=1.65,vx_mps=20)
            steps=[]
            for _ in range(round(.4/dt)):
                step=model.advance(state,Actuation(.2,0),dt,.01)
                steps.append(step)
                state=step.final
            with self.subTest(dt=dt),tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
                report=run_sumo(Path(tmp)/'live',model,steps,dt)
                self.assertTrue(report['passed'],report)
                self.assertEqual(report['edge_ids'],['downstream','upstream'])
                self.assertLess(report['max_position_error_m'],1e-6)
                self.assertLess(report['max_interval_acceleration_error_mps2'],1e-6)
                self.assertEqual(report['teleport_starts'],0)

    def test_sumo_startup_failure_is_persisted(self):
        from experiments.phase2 import run_sumo
        from models.vehicle import VehicleModel,VehicleState,Actuation
        model=VehicleModel.from_config()
        steps=[model.advance(VehicleState(x_m=100,y_m=1.65,vx_mps=20),Actuation(0,0),.1,.01)]
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            path=Path(tmp)/'failure'
            with patch('experiments.phase2.binary',return_value=str(Path(tmp)/'missing_sumo.exe')):
                report=run_sumo(path,model,steps,.1)
            self.assertFalse(report['passed'])
            self.assertEqual(read_json(path/'validation.json')['status'],'failed')
            self.assertIn('traceback',report)
