"""Actual 10 s same-tape C0/H-NOA checks; no controller replacement or patching."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

package = Path(__file__).resolve().parent
base = json.loads((package / "base_manifest.json").read_text(encoding="utf-8"))
freeze = json.loads((package / "freeze.json").read_text(encoding="utf-8"))
reference = Path(base["source_root"])
output = package / "straight_equivalence"
output.mkdir(exist_ok=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(flow, mode, owner):
    label = f"q{flow}_{mode}"
    args = [sys.executable, "-B", str(owner / "run_native_flow.py"), "--mode", mode, "--seed", "1", "--flow", str(flow), "--scenario", "straight3", "--duration", "10", "--max-time", "310", "--output-base", str(output / label)]
    completed = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    (output / (label + ".stdout.log")).write_text(completed.stdout, encoding="utf-8")
    (output / (label + ".stderr.log")).write_text(completed.stderr, encoding="utf-8")
    assert completed.returncode == 0, (label, completed.stderr[-2000:])
    case = Path(json.loads(completed.stdout.strip().splitlines()[-1])["run_dir"])
    result = json.loads((case / "result.json").read_text(encoding="utf-8"))
    expected = freeze["source_sha256"] if mode == "cooperative" else base["source_sha256"]
    assert result["source_sha256"] == expected
    assert result["mode"] == mode and result["safe"] and result["all_completed"]
    return case


rows = []
for flow in (500, 1500):
    c0 = run(flow, "cooperative", package)
    noa = run(flow, "noa", reference)
    comparisons = {}
    for name, decompress in (("native.rou.xml", False), ("trips.json", False), ("positions.jsonl.gz", True)):
        left = gzip.decompress((c0 / name).read_bytes()) if decompress else (c0 / name).read_bytes()
        right = gzip.decompress((noa / name).read_bytes()) if decompress else (noa / name).read_bytes()
        comparisons[name] = dict(strict_equal=left == right, cooperative_sha256=digest(left), H_noa_sha256=digest(right), decompressed=decompress)
    row = dict(flow=flow, seed=1, duration_s=10, cooperative_case=str(c0), H_noa_case=str(noa), comparisons=comparisons, strict_equal=all(x["strict_equal"] for x in comparisons.values()))
    rows.append(row)
    (package / "straight_equivalence_report.json").write_text(json.dumps(dict(rows=rows, reuse_H_noa_straight=len(rows) == 2 and all(x["strict_equal"] for x in rows)), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(row), flush=True)
assert all(hashlib.sha256((reference / name).read_bytes()).hexdigest() == sha for name, sha in base["source_sha256"].items())
print(json.dumps(dict(report=str(package / "straight_equivalence_report.json"), reuse_H_noa_straight=all(x["strict_equal"] for x in rows))), flush=True)
