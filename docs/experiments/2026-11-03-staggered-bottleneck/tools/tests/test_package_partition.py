"""Road partitions must preserve every planned member regardless of outcome."""
import copy
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


class RoadPartitionContracts(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE / "package_partition.py").is_file(), "road partition implementation is missing")
        import package_partition
        self.tool = package_partition
        self.tasks = [dict(candidate="TM", flow=1250, seed=seed, scenario=road, mode="noa", stage="heldout")
                      for road, seed in (("straight3", 31), ("straight3", 32), ("lane_drop", 31))]
        self.rows = [{**row, "status": "drained" if i != 1 else "error"} for i, row in enumerate(self.tasks)]

    def test_entire_road_is_accepted_even_with_a_failed_case(self):
        result = self.tool.audit_partition(dict(tasks=self.tasks), self.rows,
            dict(tasks=self.tasks[:2]), self.rows[:2], "straight3")
        self.assertEqual(result["full_plan_cases"], 3)
        self.assertEqual(result["partition_cases"], 2)

    def test_dropping_unsuccessful_planned_case_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "complete|partition"):
            self.tool.audit_partition(dict(tasks=self.tasks), self.rows,
                dict(tasks=self.tasks[:1]), self.rows[:1], "straight3")

    def test_changed_selected_task_is_rejected(self):
        changed = copy.deepcopy(self.tasks[:2])
        changed[0]["flow"] = 1500
        with self.assertRaisesRegex(ValueError, "partition|task"):
            self.tool.audit_partition(dict(tasks=self.tasks), self.rows,
                dict(tasks=changed), self.rows[:2], "straight3")


if __name__ == "__main__":
    unittest.main()
