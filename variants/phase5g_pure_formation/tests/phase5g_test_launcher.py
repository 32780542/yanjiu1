"""Isolated selector for the Phase 5G lane-geometry TDD cycle."""

import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

if len(sys.argv) != 2 or sys.argv[1] not in {"lane", "controller", "cases", "harness", "all"}:
    raise SystemExit("usage: phase5g_test_launcher.py lane|controller|cases|harness|all")

names = {
    "lane": (
        "test_phase5g_lane.Phase5GGeometryTests",
        "test_phase5g_lane.Phase5GLaneValidationTests",
    ),
    "controller": ("test_phase5g_controller.Phase5GControllerTests",),
    "cases": (
        "test_phase5g_cases.Phase5GCaseTests",
        "test_phase5g_cases.Phase5GClockTests",
    ),
    "harness": (
        "test_phase5g_harness.Phase5GHarnessTests",
        "test_phase5g_harness.Phase5GCLITests",
    ),
    "all": (
        "test_phase5g_lane.Phase5GGeometryTests",
        "test_phase5g_lane.Phase5GLaneValidationTests",
        "test_phase5g_controller.Phase5GControllerTests",
        "test_phase5g_cases.Phase5GCaseTests",
        "test_phase5g_cases.Phase5GClockTests",
        "test_phase5g_harness.Phase5GHarnessTests",
        "test_phase5g_harness.Phase5GCLITests",
    ),
}
sys.path.insert(0, str(ROOT / "tests"))
suite = unittest.TestSuite(
    unittest.defaultTestLoader.loadTestsFromName(name) for name in names[sys.argv[1]]
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(
    0 if result.wasSuccessful() and result.testsRun and not result.skipped else 1
)
