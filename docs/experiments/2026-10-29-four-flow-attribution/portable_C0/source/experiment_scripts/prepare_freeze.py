"""Bind the auditable source ablation and a 20-case process-parallel wrapper."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

package = Path(__file__).resolve().parent
base = json.loads((package / "base_manifest.json").read_text(encoding="utf-8"))
reference = Path(base["source_root"])
path = package / "run_flow_study.py"
source = path.read_text(encoding="utf-8")
replacements = {
    '"""Paired flow study: NOA/formation transformation, straight road and lane drop."""': '"""Cooperative merge-only ablation: 20 lane-drop cases, four process jobs."""',
    'key: result[key]': 'key: result.get(key)',
    '"teleports",\n            )': '"teleports",\n                "safe",\n                "all_completed",\n            )',
    '    return record\n\n\ndef main': '    result = json.loads((path / "result.json").read_text(encoding="utf-8"))\n    if not result.get("safe") or not result.get("all_completed"):\n        raise RuntimeError(f"Unsafe or incomplete cooperative case retained: {path}")\n    return record\n\n\ndef main',
    'parser.add_argument("--jobs", type=int, default=1)': 'parser.add_argument("--jobs", type=int, default=4)\n    parser.add_argument("--equivalence-report", type=Path, default=ROOT / "straight_equivalence_report.json")',
    '    stamp = datetime.now(timezone.utc)': '    equivalent = json.loads(args.equivalence_report.read_text(encoding="utf-8"))["reuse_H_noa_straight"]\n    roads = [("lane_drop", ("cooperative",))]\n    if not equivalent:\n        roads.append(("straight3", ("cooperative",)))\n    stamp = datetime.now(timezone.utc)',
    'case_order="seed, flow, straight3:noa,transform; lane_drop:noa,formation,transform; declaration order"': 'case_order="seed, flow, lane_drop:cooperative; optional straight3:cooperative if actual short equivalence failed"',
    'case_count=5 * len(args.flows) * len(args.seeds)': 'case_count=len(roads) * len(args.flows) * len(args.seeds)',
    'cases_per_seed_flow="straight3:noa,transform; lane_drop:noa,formation,transform"': 'cases_per_seed_flow="lane_drop:cooperative" if equivalent else "lane_drop:cooperative;straight3:cooperative",\n        policy="cooperative_merge_only",\n        group_following=False,\n        layer_fill=False,\n        straight_delegation="complete current NOA decision",\n        reuse_H_noa_straight=equivalent,\n        equivalence_report=str(args.equivalence_report.resolve())',
    'for road, modes in [\n            ("straight3", ("noa", "transform")),\n            ("lane_drop", ("noa", "formation", "transform")),\n        ]': 'for road, modes in roads',
    '    except BaseException:\n': '    except BaseException as error:\n        write_json(base / "study_failure.json", dict(type=type(error).__name__, message=str(error)))\n',
}
for old, new in replacements.items():
    assert old in source, old
    source = source.replace(old, new)
path.write_text(source, encoding="utf-8")
ast.parse(source)


def named_nodes(path):
    return {getattr(n, "name", "MODES" if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MODES" for t in n.targets) else f"line{n.lineno}"): ast.dump(n, include_attributes=False) for n in ast.parse(path.read_text(encoding="utf-8")).body}


changes = {}
diffs = []
for relative, before in base["source_sha256"].items():
    old, new = reference / relative, package / relative
    assert hashlib.sha256(old.read_bytes()).hexdigest() == before
    if old.read_bytes() != new.read_bytes():
        a, b = named_nodes(old), named_nodes(new)
        changes[relative] = sorted(n for n in a.keys() | b.keys() if a.get(n) != b.get(n))
        diffs.extend(difflib.unified_diff(old.read_text(encoding="utf-8").splitlines(True), new.read_text(encoding="utf-8").splitlines(True), fromfile="H_frozen/"+relative, tofile="cooperative_only/"+relative))
assert set(changes) == {"noa/native_rules.py", "experiments/native_sumo.py"}, changes
assert changes["noa/native_rules.py"] == ["_decide"], changes
assert changes["experiments/native_sumo.py"] == ["MODES"], changes
(package / "source_diff.patch").write_text("".join(diffs), encoding="utf-8")
manifest = dict(label="cooperative: H cooperation and execution, no formation following or layer fill", source_parent=str(reference), source_sha256={name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in base["source_sha256"]}, H_source_sha256=base["source_sha256"], configs_sha256=base["configs_sha256"], changed_AST_nodes=changes, wrapper_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), tests=dict(red="20261029T022208125393Z_H-cooperative-ablation-red_7493b35a", red_failures=9, green="20261029T022257262254Z_H-cooperative-ablation-green_cdb704db", green_tests=9), main_source_write_policy="No writes; another authorized agent may install main concurrently")
(package / "freeze.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(freeze=str(package / "freeze.json"), changes=changes, source_sha256=manifest["source_sha256"])))
