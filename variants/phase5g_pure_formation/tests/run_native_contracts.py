"""Run the installed native contract modules sequentially from any cwd."""
from pathlib import Path
import sys
import unittest

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TESTS))

if __name__ == '__main__':
    names = sys.argv[1:]
    if not names:
        raise SystemExit('Pass explicit test module names; no old-stage discovery.')
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not outcome.wasSuccessful())
