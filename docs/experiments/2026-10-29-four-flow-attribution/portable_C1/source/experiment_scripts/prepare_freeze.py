"""Freeze C1's single C0-to-C1 guard change without touching earlier cohorts."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
C0 = PACKAGE.parent / "H_cooperative_ablation"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def nodes(path):
    return {getattr(node, "name", f"line{node.lineno}"): ast.dump(node, include_attributes=False)
            for node in ast.parse(path.read_text(encoding="utf-8")).body}


c0 = read(C0 / "freeze.json")
base = read(PACKAGE / "base_manifest.json")
changed = {}
for name, expected in c0["source_sha256"].items():
    assert sha(C0 / name) == expected
    if (PACKAGE / name).read_bytes() != (C0 / name).read_bytes():
        before, after = nodes(C0 / name), nodes(PACKAGE / name)
        changed[name] = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
assert changed == {"noa/native_rules.py": ["_decide"]}, changed
old = (C0 / "noa/native_rules.py").read_bytes()
new = (PACKAGE / "noa/native_rules.py").read_bytes()
assert new == old.replace(b'if mode in ("noa", "cooperative"):', b'if mode == "noa":')
for name, expected in c0["configs_sha256"].items():
    assert sha(PACKAGE / name) == sha(C0 / name) == expected
for name, expected in read(PACKAGE / "analysis_source/freeze.json")["source_sha256"].items():
    assert sha(PACKAGE / "analysis_source" / name) == sha(C0 / "analysis_source" / name) == expected
for name in ("_following", "_fill", "_make_room", "_receiving", "_merge_target", "_join_speed"):
    assert nodes(PACKAGE / "noa/native_rules.py")[name] == nodes(Path(base["source_root"]) / "noa/native_rules.py")[name]
def straight_branch(path):
    decide = next(n for n in ast.parse(path.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name == "_decide")
    return ast.dump(decide.body[2], include_attributes=False)
assert straight_branch(C0 / "noa/native_rules.py") == straight_branch(PACKAGE / "noa/native_rules.py")
inheritance = dict(label="C1 straight proof inherited from C0; no new short simulations",
    reuse_H_noa_straight=True, C0_report=str(C0 / "straight_equivalence_report.json"),
    C0_report_sha256=sha(C0 / "straight_equivalence_report.json"),
    copied_report_sha256=sha(PACKAGE / "straight_equivalence_report.json"),
    complete_straight_delegation_AST_identical=True, NOA_overtake_guard_truth_unchanged=True)
assert inheritance["C0_report_sha256"] == inheritance["copied_report_sha256"]
(PACKAGE / "straight_equivalence_inheritance.json").write_text(json.dumps(inheritance, indent=2) + "\n", encoding="utf-8")
diff = "".join(difflib.unified_diff(old.decode().splitlines(True), new.decode().splitlines(True),
                                   fromfile="C0/noa/native_rules.py", tofile="C1/noa/native_rules.py"))
(PACKAGE / "source_diff_C0_C1.patch").write_text(diff, encoding="utf-8")
h_before = (Path(base["source_root"]) / "noa/native_rules.py").read_text(encoding="utf-8")
(PACKAGE / "source_diff.patch").write_text("".join(difflib.unified_diff(h_before.splitlines(True), new.decode().splitlines(True), fromfile="H/noa/native_rules.py", tofile="C1/noa/native_rules.py")), encoding="utf-8")
manifest = dict(label="C1 strict formation ablation", source_parent=str(C0), C0_source_sha256=c0["source_sha256"],
    source_sha256={name: sha(PACKAGE / name) for name in c0["source_sha256"]},
    H_source_sha256=base["source_sha256"], H_source_root=base["source_root"],
    configs_sha256=c0["configs_sha256"], changed_AST_nodes=c0["changed_AST_nodes"],
    C0_to_C1_changed_AST_nodes=changed, C0_to_C1_change="Only _decide normal-overtake guard: cooperative removed; NOA retains it",
    normal_overtake=False, mode="cooperative", group_following=False, layer_fill=False,
    engine_enum_exact_C0=True, helper_receiving_merge_join_functions_exact_H=True,
    straight_equivalence_inheritance=inheritance, wrapper_sha256=sha(PACKAGE / "run_flow_study.py"),
    tests=dict(red="20261029T030315478767Z_C1-strict-formation-red_66c672e0", red_failures=1,
               green="20261029T030333367524Z_C1-strict-formation-green_8eb7b997", green_tests=13),
    evaluator_source_exact_C0=True, C0_freeze_sha256=sha(C0 / "freeze.json"))
(PACKAGE / "freeze.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest))
