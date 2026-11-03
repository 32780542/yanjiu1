"""Build only E's requested diagnostic toggles; no production/E writes."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import review_candidates as shared

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parents[1]
PARENT = REPO / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py"
EXPECTED = "04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274"
FILL = ("lane = _fill(ego, rows, 2 if preparing else lanes)",
        "lane = None  # diagnostic ENF: disable discretionary formation fill")
PHASE = ("phase_speed = max(-2.0, min(2.0, POSITION_GAIN * error))",
         "phase_speed = 0.0  # diagnostic ENP: disable cross-lane head speed correction")
PLAN = {"ENF": [FILL], "ENP": [PHASE], "ENB": [FILL, PHASE]}
production = REPO / "variants/phase5g_pure_formation/noa/native_rules.py"
original_production = production.read_bytes()
original = PARENT.read_bytes()
assert hashlib.sha256(original).hexdigest() == EXPECTED
text = original.decode("utf-8")
parent = shared.module("E_formation_ablation_parent", original, PARENT)
for old, new in (FILL, PHASE):
    assert text.count(old) == 1 and new not in text


def definitions(raw):
    return {n.name: ast.dump(n) for n in ast.parse(raw).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


for name, edits in PLAN.items():
    target = REPO / "tmp/staggered_bottleneck/candidates" / name / "native_rules.py"
    folder = HERE / "ablations" / name
    assert not target.exists() and not folder.exists(), (target, folder)
    source = text
    for old, new in edits:
        source = source.replace(old, new)
    restored = source
    for old, new in reversed(edits):
        restored = restored.replace(new, old)
    assert restored.encode("utf-8") == original
    compile(source, str(target), "exec")
    before, after = definitions(text), definitions(source)
    changed = sorted(k for k in before if before[k] != after[k])
    expected_functions = sorted((["_decide"] if FILL in edits else []) + (["_following"] if PHASE in edits else []))
    assert before.keys() == after.keys() and changed == expected_functions
    candidate = shared.module("E_formation_ablation_" + name, source.encode(), target)
    checks = dict(noa_exact=0, flag_exact_same_physical_frame=0, no_fill_outputs=0)
    for values, memory, labels, drop in shared.scenes(1000):
        assert shared.decision(candidate, values, memory, "noa", drop) == shared.decision(parent, values, memory, "noa", drop)
        checks["noa_exact"] += 1
        actual, _ = shared.decision(candidate, values, memory, "transform", drop)
        reference, _ = shared.decision(parent, values, memory, "transform", drop)
        assert actual["formation_state"] == reference["formation_state"]
        checks["flag_exact_same_physical_frame"] += 1
        if FILL in edits:
            assert actual["reason"] != "fill_layer"
            checks["no_fill_outputs"] += 1
    patch = "".join(difflib.unified_diff(text.splitlines(True), source.splitlines(True),
                        fromfile="a/E/native_rules.py", tofile="b/" + name + "/native_rules.py"))
    target.parent.mkdir(parents=True, exist_ok=False)
    target.write_text(source, encoding="utf-8", newline="\n")
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
    metadata = dict(parent="E/direct_gap", parent_source=str(PARENT), parent_sha256=EXPECTED,
        source_sha256=hashlib.sha256(source.encode()).hexdigest(), rules_path=str(target),
        interventions=edits, changed_definitions=changed, compile_passed=True, inverse_reconstruction_exact=True,
        random_scene_seed=shared.SEED, shadow_checks=checks,
        patch_sha256=hashlib.sha256(patch.encode()).hexdigest(),
        limits=["Finite shadow scenes are not exhaustive behavior, safety, or efficiency proof.",
                "ENP disables only cross-lane head speed correction; phase coordinates used by fill still remain.",
                "Direct 0/1 output is unchanged on the same physical frame; evolved trajectories and participation may differ."])
    (folder / "source.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    (folder / "README.md").write_text("# " + name + "：E上的形成消融\n\n"
        + "仅用于因果诊断，不作为生产候选。父源码SHA：`" + EXPECTED + "`。\n\n"
        + "\n".join("- `" + old + "` → `" + new + "`" for old, new in edits)
        + "\n\n保留NOA、实际前车CTH、安全、必要合流、原0/1及未关闭的组织行为。ENP保留用于匹配/补位的相位坐标，仅禁止队首速度修正。"
        + "1000个影子状态NOA精确相同、同物理帧0/1相同；不能据此宣称交通效果或形成几何。\n", encoding="utf-8")
    print(json.dumps(dict(candidate=name, source_sha256=metadata["source_sha256"], checks=checks)), flush=True)
assert PARENT.read_bytes() == original and production.read_bytes() == original_production
