import importlib.util
from pathlib import Path
import sys
import unittest

TOOLS=Path(__file__).resolve().parents[1]/"tools"
sys.path.insert(0,str(TOOLS))


class MatchedContracts(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location("report_matched_attribution",TOOLS/"report_matched_attribution.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def row(self,candidate,seed=31,mode="transform"):
        return dict(candidate=candidate,seed=seed,flow=2250.,scenario="lane_drop",mode=mode)

    def test_duplicate_planned_identity_rejected(self):
        module=self.module()
        with self.assertRaises(ValueError):
            module.select_pairs([self.row("M"),self.row("M"),self.row("G0")],"M/transform=G0/transform")

    def test_intersection_records_unmatched(self):
        pairs,coverage=self.module().select_pairs([self.row("M"),self.row("M",32),self.row("G0"),self.row("G0",33)],"M/transform=G0/transform")
        self.assertEqual(len(pairs),1)
        self.assertEqual([key[1] for key in coverage["target_only"]],[32])
        self.assertEqual([key[1] for key in coverage["reference_only"]],[33])

    def test_mode_is_explicit_not_assumed_noa(self):
        rows=[self.row("G0"),self.row("G0N"),self.row("G0N",mode="noa")]
        pairs,coverage=self.module().select_pairs(rows,"G0N/transform=G0/transform")
        self.assertEqual(pairs[0][0]["candidate"],"G0")
        self.assertEqual(pairs[0][1]["mode"],"transform")
        self.assertEqual(coverage["common"],1)


if __name__=="__main__":
    unittest.main()
