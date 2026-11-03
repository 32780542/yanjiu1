"""Reconstruct only the effective-handoff gate from its immutable Git baseline."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[5]
BASE = "177f7a32088fb69efcc94d9acb72863e7e00e787"
NAME = "variants/phase5g_pure_formation/noa/native_rules.py"
production_before = (REPO / NAME).read_bytes()
original = subprocess.check_output(["git", "show", BASE + ":" + NAME], cwd=REPO).decode("utf-8")
old = """        if c.lane == 1 and c.track != anchor.track and anchor.x - 30.0 <= c.x <= anchor.x + 15.0
    ]
    helper = max(options, key=lambda c: c.x) if options else None"""
new = """        if c.lane == 1 and c.track != anchor.track and anchor.x - 30.0 <= c.x <= anchor.x + 15.0
        and not _clear(head, all_rows, 1)
        and _clear(c, all_rows, 0)
        and _clear(head, tuple(other for other in all_rows if other.track != c.track), 1)
    ]
    helper = max(options, key=lambda c: c.x) if options else None"""
assert original.count(old) == 1
source = original.replace(old, new)
destination = REPO / "tmp/staggered_bottleneck/candidates/effective_handoff/native_rules.py"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(source, encoding="utf-8", newline="\n")
patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                    fromfile="a/" + NAME, tofile="b/" + NAME))
Path(__file__).with_name("native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
assert production_before == (REPO / NAME).read_bytes()
metadata = dict(base_commit=BASE, baseline_sha256=hashlib.sha256(original.encode()).hexdigest(),
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                changed_functions=["_make_room"], production_unchanged=True,
                noa_control_unchanged=True, rules_path=str(destination))
Path(__file__).with_name("source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata))
