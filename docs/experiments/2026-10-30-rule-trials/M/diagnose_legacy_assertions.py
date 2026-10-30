"""Compare the three inherited failures under independent, unique module globals."""
import ast
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[4]
sources = {
    "baseline": subprocess.check_output([
        "git", "show", "8ed11d90ac457269b2175e20aec5ba1bbba8a318:variants/phase5g_pure_formation/noa/native_rules.py"
    ], cwd=ROOT),
    "candidate": (ROOT / "tmp/literature_trials/M/native_rules.py").read_bytes(),
}
modules = {}
for label, source in sources.items():
    name = "M_legacy_diagnosis_" + label
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(compile(source, name + ".py", "exec"), module.__dict__)
    modules[label] = module


def evaluate(r):
    def car(track, x, lane, speed=28.8):
        return r.Vehicle(track, x, (lane + 0.5) * 3.3, speed, lane)

    snapshots = {}
    ego = car(0, 154.827, 0)
    rows = [car(1, 329.59, 0), car(2, 106.27, 0), car(3, 147.81, 2), car(4, 190.27, 2)]
    command, memory = r.decide(ego, rows, r.Memory(joining=True), "formation", None)
    snapshots["joining"] = {"command": asdict(command), "memory": asdict(memory),
                             "following": r._following(ego, rows, 3), "fill": r._fill(ego, rows, 3)}
    ego = car(0, 700.0, 1)
    rows = [car(1, 715.0, 0), car(2, 685.0, 0), car(3, 655.0, 0)]
    command, memory = r.decide(ego, rows, r.Memory(), "transform")
    snapshots["heads"] = {"command": asdict(command), "memory": asdict(memory),
                           "following": r._following(ego, rows, 2, 640), "fill": r._fill(ego, rows, 2)}
    a, b = car(0, 682.365, 1, 0), car(1, 655.258, 0, 0)
    snapshots["negative_cycle"] = []
    for ego, other in ((a, b), (replace(b, track=0), replace(a, track=1))):
        command, memory = r.decide(ego, [other], r.Memory(), "transform")
        snapshots["negative_cycle"].append({"command": asdict(command), "memory": asdict(memory),
            "following": r._following(ego, [other], 2, 640), "fill": r._fill(ego, [other], 2)})
    return snapshots


def nodes(source):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(source).body
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


before, after = nodes(sources["baseline"]), nodes(sources["candidate"])
changed = [name for name in before if before[name] != after[name]]
added = sorted(set(after) - set(before))
assert changed == ["_fill"] and added == ["cf_speed"], (changed, added)
assert modules["baseline"].__dict__ is not modules["candidate"].__dict__
for name in before:
    if name.startswith("_") and callable(getattr(modules["candidate"], name)):
        assert getattr(modules["candidate"], name).__globals__ is modules["candidate"].__dict__
        assert getattr(modules["baseline"], name).__globals__ is modules["baseline"].__dict__
constants = [name for name in modules["baseline"].__dict__ if name.isupper()]
assert all(getattr(modules["baseline"], name) == getattr(modules["candidate"], name) for name in constants)
snapshots = {label: evaluate(r) for label, r in modules.items()}
assert snapshots["baseline"] == snapshots["candidate"], snapshots
result = {"changed_functions": changed, "added_functions": added,
          "constants_equal": constants, "module_globals_independent": True,
          "source_sha256": {label: hashlib.sha256(source).hexdigest() for label, source in sources.items()},
          "snapshots": snapshots,
          "conclusion": "All three inherited assertions fail identically before M; _fill returns None in each fixture."}
path = ROOT / "tmp/literature_trials/M/legacy_assertions.json"
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"equal_fixture_outputs": True, "changed_functions": changed,
                  "added_functions": added, "evidence": str(path)}))
