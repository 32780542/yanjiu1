import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


class FinalPartitionContracts(unittest.TestCase):
    def fixture(self):
        rows=[dict(candidate="S",mode="transform",flow=flow,seed=61,scenario=road)
            for flow in (500.,1500.,2000.,2500.) for road in ("straight3","lane_drop")]
        return dict(tasks=rows),rows

    def test_road_low_group_is_complete(self):
        tool=importlib.import_module("package_final_partition")
        full,rows=self.fixture()
        selected=[r for r in rows if r["scenario"]=="lane_drop" and r["flow"]<=1500]
        result=tool.audit_partition(full,rows,dict(tasks=selected),selected,"lane_drop","low")
        self.assertEqual(result["partition_cases"],2)

    def test_omitted_member_rejected(self):
        tool=importlib.import_module("package_final_partition")
        full,rows=self.fixture()
        selected=[r for r in rows if r["scenario"]=="lane_drop" and r["flow"]>=2000][:-1]
        with self.assertRaises(ValueError):
            tool.audit_partition(full,rows,dict(tasks=selected),selected,"lane_drop","high")

    def test_cross_profile_member_rejected(self):
        tool=importlib.import_module("package_final_partition")
        full,rows=self.fixture()
        selected=[r for r in rows if r["scenario"]=="straight3"]
        with self.assertRaises(ValueError):
            tool.audit_partition(full,rows,dict(tasks=selected),selected,"straight3","low")


if __name__=="__main__":
    unittest.main()
