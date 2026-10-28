"""Isolated selector for the Phase 5F TDD cycles."""

import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

if len(sys.argv) != 2 or sys.argv[1] not in {"math", "controller", "harness", "all"}:
    raise SystemExit("usage: phase5f_test_launcher.py math|controller|harness|all")

names = {
    "math": ("test_phase5f_low_speed.Phase5FLowSpeedMathTests",),
    "controller": ("test_phase5f_low_speed.Phase5FControllerTests",),
    "harness": ("test_phase5f_harness.Phase5FHarnessTests",),
    "all": (
        "test_phase5f_low_speed.Phase5FLowSpeedMathTests",
        "test_phase5f_low_speed.Phase5FControllerTests",
        "test_phase5f_harness.Phase5FHarnessTests",
    ),
}
sys.path.insert(0, str(ROOT / "tests"))
suite = unittest.TestSuite(
    unittest.defaultTestLoader.loadTestsFromName(name) for name in names[sys.argv[1]]
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() and result.testsRun else 1)
