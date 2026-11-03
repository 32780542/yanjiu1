"""NOA sensitivity pairs only shared plans and enforces recorded invariants."""
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))


class NoaSensitivityContracts(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE/"report_noa_sensitivity.py").is_file(),"NOA sensitivity implementation is missing")
        import report_noa_sensitivity
        self.tool=report_noa_sensitivity

    def case(self,flow=2250,candidate="TM",value=50.):
        return dict(candidate=candidate,mode="noa",flow=flow,seed=31,scenario="lane_drop",protocol_verified=True,
            evidence_verified=True,_run=dict(candidate=candidate,flow_veh_h_lane=flow,seed=31,scenario="lane_drop",
            case_dir=candidate,attribution_eligible=True,source_sha256={"rule":candidate},rules_sha256=candidate,
            demand_sha256="same",parameters_sha256="same",nonrule_source_sha256="same",
            mean_system_time_s=value,region_low_speed_vehicle_s=None))

    def test_unmatched_extra_baseline_flows_are_not_fabricated_pairs(self):
        base=[self.case(flow) for flow in (1250,2000,2250,2500)]
        target=[self.case(flow,"NOA60") for flow in (2250,2500)]
        shared,left,right=self.tool.common_plan(base,target)
        self.assertEqual(len(shared),2)
        self.assertEqual({key[0] for key in left},{1250,2000})
        self.assertFalse(right)

    def test_nonrule_source_mismatch_is_ineligible(self):
        base,target=self.case(),self.case(candidate="NOA60",value=49.)
        target["_run"]["nonrule_source_sha256"]="other"
        pair=self.tool.pair_noa(base,target)
        self.assertFalse(pair["pair_eligible"])
        self.assertIn("nonrule_source_sha256_mismatch",pair["rejection_reasons"])
        self.assertIsNone(pair["delta_mean_system_time_s"])

    def test_same_mode_raw_delta_and_missing_window_stay_visible(self):
        pair=self.tool.pair_noa(self.case(),self.case(candidate="NOA60",value=49.))
        self.assertTrue(pair["pair_eligible"])
        self.assertEqual(pair["delta_mean_system_time_s"],-1)
        self.assertIsNone(pair["delta_region_low_speed_vehicle_s"])


if __name__=="__main__":
    unittest.main()
