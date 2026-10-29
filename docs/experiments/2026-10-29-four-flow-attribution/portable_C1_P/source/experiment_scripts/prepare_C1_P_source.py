"""Copy only the root-authorized frozen P release for the seed6–10 strict ablation."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "tmp/common_pair_P_release"
DEST = ROOT / "tmp/common_pair_P_strict_ablation"
OLD_C1 = ROOT / "tmp/H_strict_formation_ablation"

def read(path): return json.loads(path.read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

anchor = read(ROOT / "tmp/P_analysis_expected.json")
freeze = read(RELEASE / "freeze.json")
assert sha(RELEASE / "freeze.json") == anchor["release_freeze_sha256"]
assert freeze["source_sha256"] == anchor["source_sha256"]
assert freeze["source_sha256"]["noa/native_rules.py"] == "8d112d79dce42b68fc4aba986aa52b5241c3ee4e8b6d8061cd04b80bcdb75864"
DEST.mkdir()
for name, expected in freeze["source_sha256"].items():
    assert sha(RELEASE / name) == expected
    target = DEST / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RELEASE / name, target)
for name in ("noa", "experiments", "research"):
    shutil.copy2(RELEASE / name / "__init__.py", DEST / name / "__init__.py")
shutil.copytree(RELEASE / "configs", DEST / "configs")
shutil.copytree(OLD_C1 / "analysis_source", DEST / "analysis_source")
for name in ("run_flow_study.py", "straight_equivalence_report.json"):
    shutil.copy2(OLD_C1 / name, DEST / name)
base = dict(source_root=str(RELEASE), source_sha256=freeze["source_sha256"],
            configs_sha256={str(p.relative_to(RELEASE)).replace("\\", "/"): sha(p) for p in sorted((RELEASE / "configs").glob("*.json"))},
            wrapper_sha256=freeze["wrapper_sha256"], source_policy="P heldout seeds6–10", seeds=[6,7,8,9,10],
            original_C1_H_root=str(OLD_C1), original_C1_H_freeze_sha256=sha(OLD_C1 / "freeze.json"))
(DEST / "base_manifest.json").write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(copied_source=str(DEST), source_P_rules=freeze["source_sha256"]["noa/native_rules.py"], simulation_started=False)))
