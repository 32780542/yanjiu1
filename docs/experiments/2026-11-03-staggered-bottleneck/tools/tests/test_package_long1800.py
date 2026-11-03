import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


class LongPlanContracts(unittest.TestCase):
    def records(self):
        return [dict(seal_status="verified",status="drained",returncode=0) for _ in range(2)]+[
            dict(seal_status="failed_raw_retained",status="starting",returncode=124) for _ in range(2)]

    def test_original_four_plan_accepts_both_outcomes(self):
        tool=importlib.import_module("package_long1800")
        for candidate in ("L","M","N","Q"):
            self.assertIsNone(tool.validate_plan("20261103_long1800_"+candidate+"4",self.records()))

    def test_missing_timeout_cannot_be_filtered(self):
        with self.assertRaises(ValueError):
            importlib.import_module("package_long1800").validate_plan("20261103_long1800_L4",self.records()[:-1])

    def test_physical_limit_cannot_be_called_compute_timeout(self):
        rows=self.records()
        rows[-1]["status"]="time_limit"
        with self.assertRaises(ValueError):
            importlib.import_module("package_long1800").validate_plan("20261103_long1800_L4",rows)


if __name__=="__main__":
    unittest.main()
