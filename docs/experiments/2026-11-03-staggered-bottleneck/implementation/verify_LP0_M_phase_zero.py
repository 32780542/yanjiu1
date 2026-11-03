"""Prove fixed LP0 equals M with phase speed zero; no candidate or trial."""
import ast
from dataclasses import asdict
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = ROOT / "tmp/staggered_bottleneck/candidates"
M_PATH = BASE / "local_phase_velocity_damping/native_rules.py"
LP0_PATH = BASE / "phase_off_L/native_rules.py"
EXPECTED_M = "a286110cf2e14904152b63c9a66f960496f5f7f04ab0097b8d7ed00353db4762"
EXPECTED_LP0 = "64a134fee75ae628779b81e497fca1de6b095a2f1828493c573ee2dacc455eb4"
protected = [M_PATH, LP0_PATH, BASE / "local_vacancy_bridge/native_rules.py",
             ROOT / "variants/phase5g_pure_formation/noa/native_rules.py"]
before = {str(p): p.read_bytes() for p in protected}
sha = lambda raw: hashlib.sha256(raw).hexdigest()
assert sha(before[str(M_PATH)]) == EXPECTED_M and sha(before[str(LP0_PATH)]) == EXPECTED_LP0
m_source, lp0_source = before[str(M_PATH)].decode("utf-8"), before[str(LP0_PATH)].decode("utf-8")
old_phase = "phase_speed = max(-2.0, min(2.0, POSITION_GAIN * error))"
zero_phase = "phase_speed = 0.0  # Longitudinal-phase ablation; geometric fill is retained."
assert m_source.count(old_phase) == 1
m0_source = m_source.replace(old_phase, zero_phase)
m_error = "error += (difference + (peer.speed - ego.speed) / POSITION_GAIN) / max(1, pair_lanes - 1)"
l_error = "error += difference / max(1, pair_lanes - 1)"
assert m0_source.count(m_error) == 1 and m0_source.replace(m_error, l_error) == lp0_source
following = next(n for n in ast.parse(m0_source).body if isinstance(n, ast.FunctionDef) and n.name == "_following")
assert not [n for n in ast.walk(following) if isinstance(n, ast.Name) and n.id == "error" and isinstance(n.ctx, ast.Load)]
phase = next(n for n in ast.walk(following) if isinstance(n, ast.Assign) and any(
    isinstance(t, ast.Name) and t.id == "phase_speed" for t in n.targets))
assert isinstance(phase.value, ast.Constant) and phase.value.value == 0.0


class StripDeadError(ast.NodeTransformer):
    def visit_Assign(self, node):
        if any(isinstance(t, ast.Name) and t.id == "error" for t in node.targets):
            return None
        return self.generic_visit(node)

    def visit_AugAssign(self, node):
        return None if isinstance(node.target, ast.Name) and node.target.id == "error" else self.generic_visit(node)


assert ast.dump(StripDeadError().visit(ast.parse(m0_source))) == ast.dump(StripDeadError().visit(ast.parse(lp0_source)))
spec = importlib.util.spec_from_file_location("phase_zero_fixed_lp0", LP0_PATH)
lp0 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lp0
spec.loader.exec_module(lp0)
m0 = ModuleType("phase_zero_virtual_m0")
m0.__file__ = "<fixed M with phase_speed zero; in memory only>"
sys.modules[m0.__name__] = m0
exec(compile(m0_source, m0.__file__, "exec"), m0.__dict__)


def exact(value):
    if isinstance(value, float):
        return {"float_hex": value.hex()}
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact(v) for v in value]
    return value


oracle = ROOT / "tmp/staggered_bottleneck/J2fast_oracle_20261103/oracle.jsonl.gz"
assert sha(oracle.read_bytes()) == "a24adc6bee09319fd1d71eb05c468be76bed54b41d9dd8e55caa43731fbe91f6"
checked, linked_commands = 0, 0
with gzip.open(oracle, "rt", encoding="utf-8") as stream:
    for line in stream:
        if checked == 6000:
            break
        state = json.loads(line)["state"]
        memory = dict(state["memory"])
        if memory["gap"] is not None:
            memory["gap"] = tuple(memory["gap"])
        a, b = [lp0.Vehicle(**c) for c in state["cars"]], [m0.Vehicle(**c) for c in state["cars"]]
        for mode in ("noa", "formation", "transform"):
            x = lp0.decide(a[0], a[1:], lp0.Memory(**memory), mode, state["drop_x"])
            y = m0.decide(b[0], b[1:], m0.Memory(**memory), mode, state["drop_x"])
            assert exact(tuple(map(asdict, x))) == exact(tuple(map(asdict, y))), (checked, mode)
            linked_commands += x[0].formation_state
        assert lp0.safe_speed(a[0], a[1:]).hex() == m0.safe_speed(b[0], b[1:]).hex()
        checked += 1
assert checked == 6000
assert all(Path(p).read_bytes() == raw for p, raw in before.items())
result = dict(M_sha256=EXPECTED_M, LP0_sha256=EXPECTED_LP0, virtual_M_phase_zero_sha256=sha(m0_source.encode()),
              no_virtual_source_written=True, source_difference="only dead error AugAssign RHS",
              phase_speed_constant_zero=True, error_has_no_explicit_load_after_ablation=True,
              AST_identical_after_removing_dead_error_stores=True, states=checked, complete_command_memory_comparisons=checked*3,
              float_hex_exact=True, safe_speed_comparisons=checked, linked_state_one_commands=linked_commands,
              modes=["noa", "formation", "transform"], protected_sources_unchanged=True,
              scope="LP0 equals phase-zero M, not phase-zero MN; N release is not in LP0",
              no_simulation=True, oracle_sha256=sha(oracle.read_bytes()))
target = OUT / "LP0_M_phase_zero_equivalence.json"
assert not target.exists()
target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
