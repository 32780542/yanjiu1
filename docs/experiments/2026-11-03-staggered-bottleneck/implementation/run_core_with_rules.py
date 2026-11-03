"""Inject a hash-pinned rules module, then run the historical 14-file selection."""
import argparse
import hashlib
import importlib
import importlib.util
from importlib.abc import Loader, MetaPathFinder
import json
from pathlib import Path
import re
import sys


REPO = Path(__file__).resolve().parents[4]
VARIANT = REPO / "variants/phase5g_pure_formation"
ORIGINAL = VARIANT / "results/operations/20261030T011348789879Z_literature-TM-final-core_219b48fd/started.json"
E_PATH = REPO / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py"
E_SHA = "04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274"
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def memory_test_patch(patch_path):
    """Apply unified hunks to strings, retaining each original test __file__."""
    result, current, source, output, pointer = {}, None, None, [], 0

    def finish():
        if current is not None:
            result[current] = "".join(output + source[pointer:])

    for line in patch_path.read_text(encoding="utf-8").splitlines(True):
        if line.startswith("--- "):
            finish()
            current, source, output, pointer = None, None, [], 0
        elif line.startswith("+++ b/"):
            current = (REPO / line[6:].strip()).resolve()
            assert current.parent == VARIANT / "tests"
            source = current.read_text(encoding="utf-8").splitlines(True)
        elif line.startswith("@@ "):
            start = int(re.match(r"@@ -(\d+)", line).group(1)) - 1
            assert start >= pointer
            output += source[pointer:start]
            pointer = start
        elif current is not None and line[:1] in (" ", "-"):
            assert source[pointer] == line[1:]
            if line[0] == " ":
                output.append(line[1:])
            pointer += 1
        elif current is not None and line.startswith("+"):
            output.append(line[1:])
    finish()
    evidence = json.loads(patch_path.with_name("test_migration_sources.json").read_text())
    assert len(result) == len(evidence) == 2
    for entry in evidence:
        path = (REPO / entry["path"]).resolve()
        assert digest(path) == entry["original_sha256"]
        assert hashlib.sha256(result[path].encode()).hexdigest() == entry["modified_text_sha256"]

    applied = {}

    class MemoryLoader(Loader):
        def __init__(self, path):
            self.path = path

        def create_module(self, spec):
            return None

        def exec_module(self, module):
            module.__file__ = str(self.path)
            exec(compile(result[self.path], str(self.path), "exec"), module.__dict__)
            applied[str(self.path)] = hashlib.sha256(result[self.path].encode()).hexdigest()

    class Finder(MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            for filename in result:
                if fullname.rsplit(".", 1)[-1] == filename.stem:
                    spec = importlib.util.spec_from_loader(fullname, MemoryLoader(filename), origin=str(filename))
                    spec.has_location = True
                    return spec

    return ({str(path): hashlib.sha256(value.encode()).hexdigest() for path, value in result.items()},
            Finder(), applied)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--rules", type=Path, default=E_PATH)
    parser.add_argument("--expected-sha", default=E_SHA)
    args = parser.parse_args()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    original = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    command = original["command"]
    assert command[:4] == ["python", "-B", "-m", "pytest"]
    files = [x for x in command[4:] if x.startswith("tests/")]
    assert len(files) == 14
    paths = [VARIANT / f for f in files]
    rules_path = args.rules.resolve()
    protected = [VARIANT / "tests/archived_rules_source.py",
                 REPO / "docs/experiments/2026-10-29-four-flow-attribution/portable_H/source/noa/native_rules.py",
                 REPO / "docs/experiments/2026-10-29-four-flow-attribution/portable_P/source/noa/native_rules.py",
                 REPO / "docs/experiments/2026-10-29-local-formation-state/evidence.tar.gz"]
    immutable = [VARIANT / "noa/native_rules.py", E_PATH, rules_path, *paths, *protected]
    before = {str(p): digest(p) for p in immutable}
    assert digest(E_PATH) == E_SHA and digest(rules_path) == args.expected_sha
    sys.path.insert(0, str(VARIANT))
    sys.path.insert(0, str(VARIANT / "tests"))
    package = importlib.import_module("noa")
    spec = importlib.util.spec_from_file_location("noa.native_rules", rules_path)
    rules = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = rules
    setattr(package, "native_rules", rules)
    spec.loader.exec_module(rules)
    patched, finder, applied = memory_test_patch(args.patch.resolve()) if args.patch else ({}, None, {})
    import pytest

    class Recorder:
        reports = []
        collected = []

        def pytest_configure(self, config):
            if finder is not None:
                sys.meta_path.insert(0, finder)

        def pytest_collection_finish(self, session):
            self.collected = [item.nodeid for item in session.items]

        def pytest_runtest_logreport(self, report):
            if report.when == "call" or report.failed:
                item = dict(nodeid=report.nodeid, when=report.when, outcome=report.outcome,
                            report_type=type(report).__name__)
                if report.failed:
                    item["longrepr"] = str(report.longrepr)
                self.reports.append(item)

    recorder = Recorder()
    arguments = [str(VARIANT / x) if x in files else x for x in command[4:]]
    arguments += ["--junitxml=" + str(args.report.with_suffix(".xml"))]
    if args.collect_only:
        arguments.append("--collect-only")
    result = pytest.main(arguments, plugins=[recorder])
    if patched:
        assert applied == patched, (applied, patched)
    after = {str(p): digest(p) for p in immutable}
    assert before == after
    metadata = dict(original_started_path=str(ORIGINAL), original_started_sha256=digest(ORIGINAL),
                    rules_path=str(rules_path), rules_sha256=args.expected_sha, selected_files=files,
                    immutable_file_hashes=before, physical_sources_or_tests_edited=False,
                    in_memory_test_patch=str(args.patch) if args.patch else None,
                    in_memory_patch_sha256=digest(args.patch) if args.patch else None,
                    patched_test_source_hashes=patched,
                    applied_test_source_hashes=applied, collected_nodeids=recorder.collected,
                    returncode=int(result), reports=recorder.reports)
    args.report.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(report=str(args.report), returncode=int(result), reports=len(recorder.reports))))
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
