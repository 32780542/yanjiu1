"""Prove frozen LP0 equals S with longitudinal phase zero, in memory only."""
import ast
from collections import Counter
from dataclasses import asdict
import gzip
import hashlib
import importlib.util
import json
from math import isfinite
from pathlib import Path
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = ROOT / "tmp/staggered_bottleneck/candidates"
S_PATH = BASE / "cth_priority_phase/native_rules.py"
LP0_PATH = BASE / "phase_off_L/native_rules.py"
EXPECTED_S = "8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"
EXPECTED_LP0 = "64a134fee75ae628779b81e497fca1de6b095a2f1828493c573ee2dacc455eb4"
ORACLE = ROOT / "tmp/staggered_bottleneck/J2fast_oracle_20261103/oracle.jsonl.gz"
EXPECTED_ORACLE = "a24adc6bee09319fd1d71eb05c468be76bed54b41d9dd8e55caa43731fbe91f6"
TARGET = OUT / "LP0_S_phase_zero_equivalence.json"
assert not TARGET.exists(), "Keep earlier verification results immutable."

protected = [
    S_PATH, LP0_PATH, BASE / "local_vacancy_bridge/native_rules.py",
    BASE / "local_phase_velocity_damping/native_rules.py",
    ROOT / "variants/phase5g_pure_formation/noa/native_rules.py",
    OUT / "verify_LP0_M_phase_zero.py", OUT / "LP0_M_phase_zero_equivalence.json",
    OUT / "LP0_M_phase_zero_equivalence.md",
    OUT.parent / "candidates/phase_off_L/source.json",
    OUT.parent / "candidates/cth_priority_phase/source.json",
]
old_operation = ROOT / ("results/operations/"
    "20261103T064115772840Z_LP0-M-phase-zero-AST-and-6000-equivalence_9c111b61")
assert old_operation.is_dir()
protected.extend(p for p in sorted(old_operation.iterdir()) if p.is_file())
before = {str(p): p.read_bytes() for p in protected}
sha = lambda raw: hashlib.sha256(raw).hexdigest()
assert sha(before[str(S_PATH)]) == EXPECTED_S
assert sha(before[str(LP0_PATH)]) == EXPECTED_LP0
assert sha(before[str(ROOT / "variants/phase5g_pure_formation/noa/native_rules.py")]) == EXPECTED_S
assert sha(ORACLE.read_bytes()) == EXPECTED_ORACLE
s_source = before[str(S_PATH)].decode("utf-8")
lp0_source = before[str(LP0_PATH)].decode("utf-8")
phase = "phase_speed = max(-2.0, min(2.0, POSITION_GAIN * error))"
zero = "phase_speed = 0.0  # Longitudinal-phase ablation; geometric fill is retained."
gate_text = ("        if phase_speed * (following[0] - ego.speed) < 0.0:\n"
             "            phase_speed = 0.0\n")
assert s_source.count(phase) == 1 and s_source.count(gate_text) == 1
s0_source = s_source.replace(phase, zero)
assert s0_source.replace(gate_text, "") == lp0_source

# Validate the exact dominating assignment and exact, side-effect-free gate.
# No generic dead-code stripping is used: only this proved false If is removed.
s0_tree, lp0_tree = ast.parse(s0_source), ast.parse(lp0_source)
following = next(n for n in s0_tree.body
                 if isinstance(n, ast.FunctionDef) and n.name == "_following")
phase_stores = [n for n in ast.walk(following) if isinstance(n, ast.Name)
                and n.id == "phase_speed" and isinstance(n.ctx, ast.Store)]
assert len(phase_stores) == 2  # Dominating zero and the gated zero assignment.
zero_index, zero_node = next((i, n) for i, n in enumerate(following.body)
    if isinstance(n, ast.Assign) and len(n.targets) == 1
    and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "phase_speed")
assert type(zero_node.value.value) is float and zero_node.value.value.hex() == "0x0.0p+0"
body = following.body[zero_index + 1]
assert isinstance(body, ast.If)
assert ast.dump(body.test) == ast.dump(ast.parse("following[2] is not None", mode="eval").body)
gate = body.body[0]
expected_gate = ast.parse(gate_text.lstrip()).body[0]
assert ast.dump(gate) == ast.dump(expected_gate)
assert not [n for n in ast.walk(gate.test) if isinstance(n, (ast.Call, ast.NamedExpr))]
assert isinstance(gate.test, ast.Compare) and len(gate.test.ops) == 1
assert isinstance(gate.test.ops[0], ast.Lt)

# For project-valid states, following[0] and ego.speed are finite in [0,33.3].
# Their subtraction is finite. IEEE binary64 multiplication by positive zero
# yields +0.0 or -0.0, neither strictly less than 0.0. There is no intervening
# write between the dominating assignment and the body/gate, and evaluating
# this arithmetic comparison has no externally visible state change.
for delta in (-33.3, -1.0, -5e-324, -0.0, 0.0, 5e-324, 1.0, 33.3):
    assert not 0.0 * delta < 0.0
body.body.pop(0)
assert ast.dump(s0_tree) == ast.dump(lp0_tree)

spec = importlib.util.spec_from_file_location("s_phase_zero_fixed_lp0", LP0_PATH)
lp0 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lp0
spec.loader.exec_module(lp0)
s0 = ModuleType("s_phase_zero_virtual_s0")
s0.__file__ = "<fixed S with phase_speed zero; gate retained; memory only>"
sys.modules[s0.__name__] = s0
exec(compile(s0_source, s0.__file__, "exec"), s0.__dict__)
assert lp0.MAX_SPEED == s0.MAX_SPEED == 33.3


def exact(value):
    if isinstance(value, float):
        return {"float_hex": value.hex()}
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact(v) for v in value]
    return value


checked = linked_commands = actual_reference_commands = 0
reason_counts = Counter()
with gzip.open(ORACLE, "rt", encoding="utf-8") as stream:
    for line in stream:
        if checked == 6000:
            break
        state = json.loads(line)["state"]
        a = [lp0.Vehicle(**c) for c in state["cars"]]
        b = [s0.Vehicle(**c) for c in state["cars"]]
        for c in b:
            assert all(isfinite(getattr(c, k)) for k in ("x", "y", "speed", "vy", "acceleration", "time"))
            assert 0.0 <= c.speed <= s0.MAX_SPEED and c.lane in (0, 1, 2)
        assert len({c.track for c in b}) == len(b)
        memory = dict(state["memory"])
        if memory["gap"] is not None:
            memory["gap"] = tuple(memory["gap"])
        for mode in ("noa", "formation", "transform"):
            x = lp0.decide(a[0], a[1:], lp0.Memory(**memory), mode, state["drop_x"])
            y = s0.decide(b[0], b[1:], s0.Memory(**memory), mode, state["drop_x"])
            assert exact(tuple(map(asdict, x))) == exact(tuple(map(asdict, y))), (checked, mode)
            linked_commands += x[0].formation_state
            actual_reference_commands += x[0].reference is not None
            reason_counts[x[0].reason] += 1
        assert lp0.safe_speed(a[0], a[1:]).hex() == s0.safe_speed(b[0], b[1:]).hex(), checked
        checked += 1
assert checked == 6000 and linked_commands > 0 and actual_reference_commands > 0
assert all(Path(p).read_bytes() == raw for p, raw in before.items())
assert sha(ORACLE.read_bytes()) == EXPECTED_ORACLE
result = dict(
    S_sha256=EXPECTED_S, LP0_sha256=EXPECTED_LP0,
    virtual_S_phase_zero_sha256=sha(s0_source.encode()),
    no_virtual_source_written=True, runtime_virtual_gate_retained=True,
    source_difference="only exact CTH-priority If; zeroed source minus If byte-identical to LP0",
    phase_speed_dominating_constant_zero=True, intervening_phase_speed_writes=0,
    guard_arithmetic_side_effect_free_for_valid_states=True,
    guard_false_reason="0.0 * finite delta is signed zero, and signed zero < 0.0 is False",
    guard_numeric_domain="finite ego.speed and following[0] in [0,33.3]",
    exact_redundant_if_nodes_removed=1, dead_error_stores_removed=0,
    whole_module_AST_identical_after_proved_gate_elimination=True,
    valid_states=checked, complete_command_memory_comparisons=checked * 3,
    float_hex_exact=True, safe_speed_comparisons=checked,
    linked_state_one_commands=linked_commands,
    actual_reference_commands=actual_reference_commands,
    command_reason_counts=dict(sorted(reason_counts.items())),
    modes=["noa", "formation", "transform"], oracle_sha256=EXPECTED_ORACLE,
    protected_sources_and_old_M_evidence_unchanged=True,
    protected_before_after_sha256={str(Path(p).relative_to(ROOT)): sha(raw) for p, raw in before.items()},
    attribution_scope="adopted longitudinal phase subsystem with CTH priority versus phase disabled; not isolated body-P effect",
    reuse_condition="same arrival tape, road, seed, physical parameters, and non-controller source; preserve LP0 provenance",
    no_simulation=True, no_git=True,
)
TARGET.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
