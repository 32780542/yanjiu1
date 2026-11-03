"""Process failure evidence must not be relabelled as a timeout."""
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))


class FollowupFailureContracts(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE/"package_failed_followup.py").is_file(),"followup failure wrapper is missing")
        import package_failed_followup
        self.tool=package_failed_followup

    def test_failed_operation_is_not_a_timeout(self):
        row=dict(status="starting",returncode=4294967295)
        execution=dict(status="failed",returncode=3221225477,elapsed_s=350.531,timeout_s=1200.)
        self.assertEqual(self.tool.failure_kind(row,execution),"unverified_execution_failure")

    def test_only_recorded_timeout_is_called_compute_timeout(self):
        row=dict(status="starting",returncode=124)
        execution=dict(status="timeout",returncode=124)
        self.assertEqual(self.tool.failure_kind(row,execution),"unverified_compute_timeout")

    def test_finalized_result_cannot_be_labelled_unfinalized(self):
        with self.assertRaises(ValueError):
            self.tool.failure_kind(dict(status="drained",returncode=1),dict(status="failed",returncode=1))


if __name__=="__main__":
    unittest.main()
