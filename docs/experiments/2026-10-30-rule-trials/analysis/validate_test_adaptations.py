"""Pure rule/state checks with a chosen rules module injected only in memory."""
import argparse
import hashlib
import importlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
VARIANT = ROOT / "variants/phase5g_pure_formation"
NAMES = ["test_native_rules.NativeRulesTests", "test_head_group_rules.E11RulesTests",
         "test_common_pair.CommonPairHeadTests", "test_formation_state.LocalFormationStateTests",
         "test_formation_state.FormationStateStatisticsTests",
         "test_formation_state.StateOnlyChangeTests.test_control_and_memory_match_frozen_P_across_local_states"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--rules", type=Path)
    source.add_argument("--published-base", action="store_true")
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sys.path[:0] = [str(VARIANT), str(VARIANT / "tests")]
    import noa
    if args.published_base:
        from archived_rules_source import ARCHIVE, SOURCE_SHA256, load_state_enabled_base
        rules = load_state_enabled_base("validation")
        rules.__spec__ = importlib.util.spec_from_loader("noa.native_rules", loader=None)
        source_path, source_sha = str(ARCHIVE), SOURCE_SHA256
    else:
        spec = importlib.util.spec_from_file_location("noa.native_rules", args.rules.resolve())
        rules = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = rules
        spec.loader.exec_module(rules)
        source_path = str(args.rules.resolve())
        source_sha = hashlib.sha256(args.rules.read_bytes()).hexdigest()
    sys.modules["noa.native_rules"] = rules
    noa.native_rules = rules
    suite = unittest.defaultTestLoader.loadTestsFromNames(NAMES)
    ending = importlib.import_module("test_ending_pair_scope")
    for name in sorted(dir(ending)):
        if name.startswith("test_"):
            suite.addTest(unittest.FunctionTestCase(getattr(ending, name)))
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    summary = dict(label=args.label, rules=source_path, rules_sha256=source_sha,
                   tests_run=result.testsRun, simulation_tests_excluded=True,
                   failures=[dict(test=test.id(), detail=detail) for test, detail in result.failures],
                   errors=[dict(test=test.id(), detail=detail) for test, detail in result.errors])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(label=args.label, tests=result.testsRun, failures=len(result.failures),
                          errors=len(result.errors), output=str(args.output.resolve()))))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
