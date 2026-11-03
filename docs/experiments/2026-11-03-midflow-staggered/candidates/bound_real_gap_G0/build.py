"""Matched nonformation control of GP2; ordinary following and overtaking remain."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
PARENT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_v2/native_rules.py"
OUT = ROOT / "tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_G0/native_rules.py"
raw = PARENT.read_bytes()
assert hashlib.sha256(raw).hexdigest() == "37306e86a8e0e1045763bf54ebb3adca60ebc489dde6925a61553240ad0195cc" and not OUT.exists()
original = raw.decode("utf-8")
source = original
start = source.index("    speed, target, reference, formation_state = (", source.index("def _decide("))
end = source.index("\n    def action(", start)
source = source[:start] + ("    speed, target, reference, _ = _front_following(ego, rows)\n"
                          "    formation_state = 0\n") + source[end:]
start = source.index("    if organized and not memory.joining:")
end = source.index('    if mode == "noa":', start)
source = source[:start] + source[end:]
source = source.replace('    if mode == "noa":\n', '    if mode in ("noa", "transform"):\n')
old_reason = ('    reason = (\n'
              '        "join_follow" if memory.joining else "formation_follow" if organized else "normal_follow"\n'
              '    )\n')
assert source.count(old_reason) == 1
source = source.replace(old_reason, '    reason = "join_follow" if memory.joining else "normal_follow"\n')
changed = [a.name for a, b in zip(ast.parse(original).body, ast.parse(source).body) if ast.dump(a) != ast.dump(b)]
assert changed == ["_decide"]
compile(source, str(OUT), "exec")
OUT.parent.mkdir(parents=True)
OUT.write_text(source, encoding="utf-8", newline="\n")
(DOC / "native_rules.patch").write_text("".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
    fromfile="GP2/noa/native_rules.py", tofile="GP2_G0/noa/native_rules.py")), encoding="utf-8", newline="\n")
meta = dict(parent_sha256=hashlib.sha256(raw).hexdigest(), source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            changed_functions=changed, lines=len(source.splitlines()), ordinary_overtaking_retained=True,
            staggered_phase_and_free_fill_removed=True, own_formation_state=0,
            same_planner_admission_execution_and_physics=True, path=str(OUT))
(DOC / "source.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
print(json.dumps(meta))
