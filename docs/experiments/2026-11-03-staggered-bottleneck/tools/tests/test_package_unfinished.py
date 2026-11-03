"""Unfinalized wall-clock timeouts preserve evidence without physical claims."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


class UnfinishedPackageContracts(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE / "package_unfinished.py").is_file(), "unfinished packaging implementation is missing")
        import package_unfinished
        self.tool = package_unfinished

    def test_wall_clock_timeout_is_not_physical_time_limit(self):
        row = dict(returncode=124, status="starting", seal_status="failed_raw_retained")
        self.assertEqual(self.tool.classify(row), "unverified_compute_timeout")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.tool.classify(dict(returncode=0, status="time_limit", seal_status="failed_raw_retained"))

    def test_raw_is_indexed_and_other_existing_files_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("input.json", "result.json", "worker.log", "positions.jsonl.gz", "events.jsonl.gz"):
                (root / name).write_bytes(b"original")
            stored, raw = self.tool.case_files(root)
            self.assertEqual({path.name for path in stored}, {"input.json", "result.json", "worker.log"})
            self.assertEqual({row["name"] for row in raw}, {"positions.jsonl.gz", "events.jsonl.gz"})
            self.assertTrue(all(row["bytes"] == 8 and row["included"] is False for row in raw))
            self.assertFalse((root / "trips.json").exists())

    def test_unknown_failed_case_cannot_be_relabelled_as_timeout(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.tool.classify(dict(returncode=1, status="error", seal_status="failed_raw_retained"))


if __name__ == "__main__":
    unittest.main()
