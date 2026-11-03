"""Frozen single-mechanism diagnostics; these are not proposed production rules."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[4]
BASE = "177f7a32088fb69efcc94d9acb72863e7e00e787"
NAME = "variants/phase5g_pure_formation/noa/native_rules.py"
original = subprocess.check_output(["git", "show", BASE + ":" + NAME], cwd=REPO).decode("utf-8")
edits = {
    "NF": ("lane = _fill(ego, rows, 2 if preparing else lanes)", "lane = None  # diagnostic: no discretionary formation fill"),
    "NC": ('if preparing and mode == "transform":', 'if preparing and mode == "transform" and False:  # diagnostic: no cooperation'),
    "NP": ("phase_speed = max(-2.0, min(2.0, POSITION_GAIN * error))", "phase_speed = 0.0  # diagnostic: no cross-lane speed correction"),
    "NH": ("helper = max(options, key=lambda c: c.x) if options else None", "helper = None  # diagnostic: no middle-to-left helper"),
}
metadata = {}
for name, (old, new) in edits.items():
    assert original.count(old) == 1
    source = original.replace(old, new)
    compile(source, name + "/native_rules.py", "exec")
    target = REPO / "tmp/staggered_bottleneck/candidates" / name / "native_rules.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8", newline="\n")
    patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                        fromfile="a/" + NAME, tofile="b/" + NAME))
    folder = Path(__file__).resolve().parents[1] / "ablations" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
    metadata[name] = dict(base_commit=BASE, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                          rules_path=str(target), intervention=[old, new])
destination = Path(__file__).resolve().parents[1] / "ablations/source.json"
destination.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata))
