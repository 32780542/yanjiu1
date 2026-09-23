"""Isolated selector for the simple local-formation TDD cycle."""

import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

if len(sys.argv) != 2 or sys.argv[1] not in {"rules", "controller", "harness", "all"}:
    raise SystemExit("usage: simple_formation_test_launcher.py rules|controller|harness|all")

names = {
    "rules": ("test_simple_formation_rules.SimpleFormationRuleTests",
              "test_layered_formation.LayeredFormationTests"),
    "controller": ("test_simple_formation_controller.SimpleFormationControllerTests",),
    "harness": ("test_simple_formation_harness.SimpleFormationHarnessTests",),
    "all": (
        "test_simple_formation_rules.SimpleFormationRuleTests",
        "test_layered_formation.LayeredFormationTests",
        "test_simple_formation_controller.SimpleFormationControllerTests",
        "test_simple_formation_harness.SimpleFormationHarnessTests",
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
