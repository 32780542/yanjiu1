from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from research.common import ROOT


class ReplayTests(unittest.TestCase):
    def test_replay_checks_every_sample_command_and_diagnostic(self):
        from experiments.phase2 import save_trace,replay_trace
        from models.vehicle import VehicleModel,VehicleState,Actuation
        m=VehicleModel.from_config()
        initial=VehicleState(x_m=100,y_m=1.65,vx_mps=20)
        step=m.advance(initial,Actuation(.1,.001),.1,.01)
        meta={'parameters':dict(m.p),'initial':asdict(initial),'control_dt_s':.1,'dynamics_dt_s':.01,'intervals':1}
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            path=Path(tmp)/'trace.jsonl'
            save_trace(path,m,[step])
            text=path.read_text()
            self.assertTrue(replay_trace(meta,path)['passed'])
            for target in ('state','command','diagnostic','truncation'):
                record=json.loads(text)
                if target=='state':
                    record['samples'][3]['x_m']+=.001
                elif target=='command':
                    record['command']['acceleration_mps2']+=.1
                elif target=='diagnostic':
                    record['diagnostics'][0]['fy_front_N']+=1
                elif target=='truncation':
                    record['samples'].pop()
                path.write_text(json.dumps(record)+'\n')
                with self.subTest(target=target):
                    self.assertFalse(replay_trace(meta,path)['passed'])
            path.write_text('')
            self.assertFalse(replay_trace(meta,path)['passed'])

    def test_manifest_covers_all_active_dynamics_and_sync_sources(self):
        from research.common import code_manifest
        manifest=code_manifest()
        for path in ('models/vehicle.py','models/geometry.py','safety/geometry.py',
                     'simulation/external_bridge.py','experiments/phase2.py','configs/phase2.json'):
            self.assertIn(path,manifest)

    def test_phase2_parameters_are_in_registry(self):
        import csv
        from research.common import settings
        with (ROOT/'docs/parameter_registry.csv').open(encoding='utf-8-sig',newline='') as handle:
            rows=list(csv.DictReader(handle))
        actual={r['name']:json.loads(r['value']) for r in rows if r['layer']=='phase2'}
        self.assertEqual(actual,settings('phase2'))
