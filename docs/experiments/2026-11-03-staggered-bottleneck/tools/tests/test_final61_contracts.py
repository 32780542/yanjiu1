import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


class FinalLockContracts(unittest.TestCase):
    def cases(self):
        return [dict(candidate=candidate,mode=mode,flow=flow,seed=seed,scenario=road,rules_sha256=sha)
            for candidate,mode,sha in (("TM","noa","65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317"),
                ("S","transform","8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"))
            for flow in (500.,750.,1000.,1250.,1500.,2000.,2250.,2500.)
            for seed in range(61,66) for road in ("straight3","lane_drop")]

    def test_complete_source_locked_matrix(self):
        result=importlib.import_module("review_final61_S160").audit_locked_cases(self.cases())
        self.assertEqual(result["cases"],160)

    def test_changed_rule_rejected(self):
        rows=self.cases()
        rows[-1]["rules_sha256"]="changed"
        with self.assertRaises(AssertionError):
            importlib.import_module("review_final61_S160").audit_locked_cases(rows)

    def test_duplicate_replacing_missing_plan_rejected(self):
        rows=self.cases()
        rows[-1]=rows[-2]
        with self.assertRaises(AssertionError):
            importlib.import_module("review_final61_S160").audit_locked_cases(rows)


if __name__=="__main__":
    unittest.main()
