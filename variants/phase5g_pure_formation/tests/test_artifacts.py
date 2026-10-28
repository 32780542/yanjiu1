"""Acceptance checks against generated artifacts and real SUMO output."""
import csv
import unittest
import xml.etree.ElementTree as ET
from research.common import ROOT, read_json


class ArtifactTests(unittest.TestCase):
    def test_smoke_exceptions_cannot_leave_previous_success(self):
        import json
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        from research import smoke
        for failure in ('start', 'wrong_dt'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
                local_root=__import__('pathlib').Path(tmp)
                out=local_root/'results/phase1/smoke'
                out.mkdir(parents=True)
                (out/'validation.json').write_text(json.dumps({'passed':True,'end_reason':'previous'}),encoding='utf-8')
                closed=[]
                conn=SimpleNamespace(getVersion=lambda:(22,'fake'),
                    simulation=SimpleNamespace(getDeltaT=lambda:.2),close=lambda:closed.append(True))
                def start(*args,**kwargs):
                    if failure=='start':
                        raise RuntimeError('injected startup failure')
                fake=SimpleNamespace(start=start,getConnection=lambda label:conn)
                with patch.object(smoke,'ROOT',local_root), patch.object(smoke,'lock_traci',return_value=fake):
                    with self.assertRaises(RuntimeError):
                        smoke.run_smoke()
                result=json.loads((out/'validation.json').read_text(encoding='utf-8'))
                self.assertFalse(result['passed'],'Old success must not survive a failed attempt')
                self.assertEqual(result['end_reason'],'exception')
                self.assertIn('error',result)
                if failure=='wrong_dt':
                    self.assertEqual(closed,[True])

    def test_recorded_arrivals_use_tripinfo_event_time(self):
        path=ROOT/'results/phase1/smoke/departures.csv'
        self.assertTrue(path.exists(), 'Run the small native smoke case before final acceptance tests')
        with path.open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertTrue(rows)
        for r in rows:
            self.assertAlmostEqual(float(r['arrival_s']),float(r['tripinfo_arrival_s']),places=7,
                                   msg='Arrival event time differs from authoritative tripinfo; avoid one-step bias')

    def test_every_vehicle_has_a_legal_retained_lane_transition(self):
        out=ROOT/'results/phase1/smoke'
        with (out/'departures.csv').open(encoding='utf-8',newline='') as f:
            departures=list(csv.DictReader(f))
        with (out/'transitions.csv').open(encoding='utf-8',newline='') as f:
            transitions=list(csv.DictReader(f))
        self.assertEqual({x['vehicle_id'] for x in departures},{x['vehicle_id'] for x in transitions})
        for r in transitions:
            self.assertIn((r['from_lane'],r['to_lane']),[('0','0'),('1','1')])
            self.assertLessEqual(float(r['x_before_m']),1000)
            self.assertGreaterEqual(float(r['x_after_m']),1000)
        for r in departures:
            if r['planned_depart_lane']=='2':
                self.assertEqual(r['upstream_merge_seen'],'True')

    def test_all_600s_demand_files_have_unique_sorted_full_lane_plans(self):
        manifest=read_json('results/phase1/demand_manifest.json')
        self.assertEqual(len(manifest['scenarios']),4)
        for s in manifest['scenarios']:
            q=s['q_per_lane_hour']
            route=ROOT/f'scenarios/cai2024/demand/q{q}_seed20260910.rou.xml'
            vehicles=ET.parse(route).getroot().findall('vehicle')
            self.assertEqual(len({x.get('id') for x in vehicles}),len(vehicles))
            self.assertEqual(s['realized_total'],len(vehicles))
            times=[float(v.get('depart')) for v in vehicles]
            self.assertEqual(times,sorted(times))
            self.assertTrue(all(0<=t<600 for t in times))
            self.assertEqual({v.get('departLane') for v in vehicles},{'0','1','2'})

    def test_stage_gate_results_are_explicit(self):
        for file in ['results/phase0/environment.json','results/phase0/mcp_probe.json',
                     'results/phase1/foundation_verification.json','results/phase1/smoke/validation.json']:
            self.assertTrue(read_json(file)['passed'],file)
        smoke=read_json('results/phase1/smoke/validation.json')
        self.assertEqual(smoke['run_id'],read_json('results/phase1/smoke/run_metadata.json')['run_id'])
        self.assertFalse(smoke['controller_implemented'])
        self.assertEqual(smoke['colliding_vehicle_reports'],0)
        self.assertEqual(smoke['teleport_starts'],0)
        self.assertEqual(smoke['uninserted']+smoke['unfinished'],0)
