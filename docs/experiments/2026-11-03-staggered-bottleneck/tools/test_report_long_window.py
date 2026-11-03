"""Small hand-computed boundary/incompleteness contracts, no simulator."""
import gzip
import json
import math
from pathlib import Path
import tempfile
import unittest
import report_long_window as report
import seal_case

class Contract(unittest.TestCase):
    def test_worker_timeout_does_not_imply_physical_failure(self):
        r=dict(status='starting',returncode=124,operation=dict(status='timeout',returncode=124))
        self.assertEqual(report.case_outcome(r),'worker_wallclock_timeout_physical_completion_unknown')
    def setUp(self):
        self.existing=seal_case.tools()[1].existing
        self.steps=[dict(time_s=99.9,end_s=100.1,n=2,low_speed_n=1,speed_sum_mps=6),dict(time_s=100.1,end_s=100.4,n=4,low_speed_n=2,speed_sum_mps=20),dict(time_s=100.4,end_s=100.5,n=1,low_speed_n=0,speed_sum_mps=10),dict(time_s=100.5,end_s=100.6,n=100,low_speed_n=100,speed_sum_mps=100)]
    def test_clipped_partial_intervals(self):
        r=report.derive(self.steps,{},100,100.5,True,self.existing)['extended_region_window']
        for k,v in dict(duration_s=.5,observed_duration_s=.5,vehicle_s=1.5,mean_n=3,density_veh_km_lane=5,mean_speed_mps=7.6/1.5,low_speed_vehicle_s=.7,low_speed_fraction=.7/1.5,max_simultaneous_low_speed=2).items():self.assertTrue(math.isclose(r[k],v,abs_tol=1e-10),k)
        self.assertTrue(r['window_complete'])
    def test_explicit_incomplete_never_fills(self):
        r=report.derive(self.steps,{},100,100.5,False,self.existing)
        self.assertFalse(r['window_complete']);self.assertIsNone(r['region_mean_speed_mps']);self.assertIsNone(r['region_low_speed_vehicle_s']);self.assertIsNone(r['flow_1000m_veh_h'])
    def test_missing_interval_never_fills(self):
        r=report.derive([self.steps[0],*self.steps[2:]],{},100,100.5,True,self.existing)
        self.assertFalse(r['window_complete']);self.assertIsNone(r['region_density_veh_km_lane'])
    def test_existing_gate_endpoints_are_closed(self):
        gates={(i,1000):t for i,t in enumerate([99.99,100,100.25,100.5,100.51])}
        self.assertEqual(report.count_crossings(gates,100,100.5),3)
    def test_linear_observed_bracket_only(self):
        with tempfile.TemporaryDirectory(prefix='long_window_contract_') as d:
            path=Path(d)/'gates.gz'
            with gzip.open(path,'wt') as f:f.write(json.dumps(['vehicle_index','gate_m','t0','x0','t1','x1'])+'\n'+json.dumps([0,1000,99.9,999,100.1,1001])+'\n')
            gates=report.read_gates(path);self.assertEqual(gates,{(0,1000):100.0});self.assertNotIn((1,1000),gates)
    def test_duplicate_gate_rejected(self):
        with tempfile.TemporaryDirectory(prefix='long_window_contract_') as d:
            path=Path(d)/'gates.gz'
            with gzip.open(path,'wt') as f:f.write(json.dumps(['vehicle_index','gate_m','t0','x0','t1','x1'])+'\n'+(json.dumps([0,1000,100,1000,100,1000])+'\n')*2)
            with self.assertRaisesRegex(ValueError,'duplicate'):report.read_gates(path)

if __name__=='__main__':unittest.main()
