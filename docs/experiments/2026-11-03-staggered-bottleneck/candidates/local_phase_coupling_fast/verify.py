"""Independently join J2fast's saved oracle, core, profile and real trace checks."""
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
BASE = ROOT / "tmp/staggered_bottleneck"
read = lambda p: json.loads(p.read_text())
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
meta = read(DOC / "source.json")
assert digest(Path(meta["rules_path"])) == meta["source_sha256"]
assert digest(BASE / "candidates/local_phase_coupling_physical/native_rules.py") == meta["parent_sha256"]
oracle = BASE / "J2fast_oracle_20261103"
saved = read(oracle / "source.json")
assert saved["saved_before_fast_source"] and saved["float_comparison"] == "float.hex"
assert digest(oracle / "oracle.jsonl.gz") == saved["oracle_sha256"]
reports = [read(oracle / f"verified_{i}.json") for i in (0, 2500, 5000, 7500)]
assert [(r["start"], r["checked"]) for r in reports] == [(i, 2500) for i in (0, 2500, 5000, 7500)]
assert all(r["source_sha256"] == meta["source_sha256"] and r["full_command_memory_float_hex_exact"] for r in reports)
core_path = DOC.parents[1] / "implementation/J2fast_core14_migrated.json"
core = read(core_path)
assert core["rules_sha256"] == meta["source_sha256"] and core["returncode"] == 0
assert len(core["collected_nodeids"]) == 225 and all(r["outcome"] == "passed" for r in core["reports"])
assert sum(r["report_type"] == "SubtestReport" for r in core["reports"]) == 37
assert core["applied_test_source_hashes"] == core["patched_test_source_hashes"]
assert all(digest(Path(p)) == h for p, h in core["immutable_file_hashes"].items())
profile = read(BASE / "J2fast_computational_profile_20261103/profile.json")
assert len(profile["records"]) == 6 and profile["protected_files_unchanged"]
assert all(digest(Path(p)) == h for p, h in profile["source_hashes"].items())
batch = BASE / "20261103_J2fast_equivalence30_2"
manifest, protocol = read(batch / "manifest.json"), read(batch / "protocol.json")
assert len(manifest) == 2 and all(r["safe"] and r["all_completed"] and r["seal_status"] == "verified" for r in manifest)
assert protocol["arguments"]["duration"] == 30 and not protocol["arguments"]["prune_raw"]
paths = {r["candidate"]: Path(r["run_dir"]) for r in manifest}
inputs = {name: read(path / "input.json") for name, path in paths.items()}
assert inputs["J2"]["source_sha256"].pop("noa/native_rules.py") == meta["parent_sha256"]
assert inputs["J2fast"]["source_sha256"].pop("noa/native_rules.py") == meta["source_sha256"]
assert inputs["J2"] == inputs["J2fast"]
exact_files = {}
for name in ("positions.jsonl.gz", "trips.json", "trips.jsonl.gz"):
    raw = [(gzip.decompress((p / name).read_bytes()) if name.endswith(".gz") else (p / name).read_bytes())
           for p in paths.values()]
    assert raw[0] == raw[1], name
    exact_files[name] = dict(bytes=len(raw[0]), sha256=hashlib.sha256(raw[0]).hexdigest())
    if name == "positions.jsonl.gz":
        frames = [json.loads(line) for line in raw[0].splitlines()]
result = dict(fast_sha256=meta["source_sha256"], parent_sha256=meta["parent_sha256"],
              oracle_cases=10000, exact_full_command_memory_decisions=30000, exact_safe_speeds=10000,
              core_tests=225, core_subtests=37, original_sources_tests_archives_unchanged=True,
              sumo_batch=str(batch), sumo_demand_s=30, sumo_cases=2, vehicles_per_case=59,
              input_only_rule_sha_different=True, exact_decompressed_files=exact_files,
              position_frames=len(frames), vehicle_frames=sum(len(f["states"]) for f in frames),
              sumo_not_a_formal_traffic_sample=True, raw_originals_retained=True)
target = DOC / "verification.json"
assert not target.exists()
target.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
