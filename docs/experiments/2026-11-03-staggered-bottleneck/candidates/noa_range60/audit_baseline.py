"""Read existing NOA40 and compute cutoff examples; no simulation."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
BATCH = ROOT / "tmp/staggered_bottleneck/20261103_validation31_NOA40"
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest = json.loads((BATCH / "manifest.json").read_text(encoding="utf-8"))
assert len(manifest) == 40
groups, originals = {}, {}
for row in manifest:
    path = Path(row["run_dir"])
    result = json.loads((path / "result.json").read_text(encoding="utf-8"))
    source = json.loads((path / "input.json").read_text(encoding="utf-8"))
    assert source["source_sha256"]["noa/native_rules.py"] == "65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317"
    assert result["safe"] and result["all_completed"]
    groups.setdefault((row["flow"], row["scenario"]), []).append(result)
    for name in ("result.json", "input.json"):
        originals[str(path / name)] = digest(path / name)
rows = []
for (flow, scenario), values in sorted(groups.items()):
    mean = lambda key: sum(v[key] for v in values) / len(values)
    rows.append(dict(flow=flow, scenario=scenario, cases=len(values), mean_entry_wait_s=mean("mean_entry_wait_s"),
                     max_case_mean_entry_wait_s=max(v["mean_entry_wait_s"] for v in values),
                     mean_travel_time_s=mean("mean_travel_time_s"), mean_system_time_s=mean("mean_system_time_s")))
target = OUT / "baseline31_entry_audit.csv"
assert not target.exists()
with target.open("w", encoding="utf-8", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
rules = {}
for name, candidate in (("NoA50", "local_phase_coupling_fast"), ("NoA60", "noa_range60")):
    path = ROOT / "tmp/staggered_bottleneck/candidates" / candidate / "native_rules.py"
    spec = importlib.util.spec_from_file_location("range_audit_" + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    rules[name] = module
examples = []
for speed in (15., 28.8):
    for gap in (49.999, 50.001, 55., 60.001):
        example = dict(ego_speed=28.8, front_speed=speed, front_gap=gap)
        for name, r in rules.items():
            ego, front = r.Vehicle(0, 100., 1.65, 28.8, 0), r.Vehicle(1, 100. + gap, 1.65, speed, 0)
            action, memory = r.decide(ego, (front,), r.Memory(), "noa", None)
            example[name] = dict(command_speed=action.speed, target=action.target_x, reference=action.reference,
                                 safe_speed=r.safe_speed(ego, (front,)), formation_state=action.formation_state)
        examples.append(example)
assert all(digest(Path(p)) == sha for p, sha in originals.items())
(OUT / "baseline31_entry_audit.json").write_text(json.dumps(dict(
    batch=str(BATCH), manifest_sha256=digest(BATCH / "manifest.json"), raw_file_sha256=originals,
    groups=rows, controller_only_cutoff_examples=examples, no_simulation=True), indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(existing_cases=40, groups=rows, examples=examples, no_simulation=True)))
