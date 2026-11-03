"""Independent D1 frozen-source contracts; no Git, simulation, or source edits."""
import ast
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
BASE = ROOT / "tmp/staggered_bottleneck/candidates"
D1 = BASE / "midflow_real_gap_balance_v1/native_rules.py"
S = BASE / "cth_priority_phase/native_rules.py"
MAIN_TEST = ROOT / "docs/experiments/2026-11-03-midflow-staggered/tests/test_real_gap_balance.py"
SELF_TEST = MAIN_TEST.with_name("test_real_gap_balance_self_exclusion.py")
EXPECTED_D1 = "2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a"
EXPECTED_S = "8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"
TARGET = OUT / "review_d1.json"
assert not TARGET.exists()
protected = [D1, S, MAIN_TEST, SELF_TEST]
before = {str(p): p.read_bytes() for p in protected}
sha = lambda raw: hashlib.sha256(raw).hexdigest()
assert sha(before[str(D1)]) == EXPECTED_D1
assert sha(before[str(S)]) == EXPECTED_S


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def exact(value):
    if hasattr(value, "__dataclass_fields__"):
        return exact(asdict(value))
    if isinstance(value, float):
        return {"hex": value.hex()}
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact(v) for v in value]
    return value


r = load("review_frozen_D1", D1)
s = load("review_frozen_D1_S_oracle", S)
old_nodes = {n.name: n for n in ast.parse(before[str(S)]).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
new_nodes = {n.name: n for n in ast.parse(before[str(D1)]).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
assert old_nodes.keys() == new_nodes.keys()
assert sorted(k for k in old_nodes if ast.dump(old_nodes[k]) != ast.dump(new_nodes[k])) == ["_decide", "_fill"]
for name in ("response_cost", "cf_cached"):
    old = next(n for n in old_nodes["_fill"].body if isinstance(n, ast.FunctionDef) and n.name == name)
    new = next(n for n in new_nodes["_fill"].body if isinstance(n, ast.FunctionDef) and n.name == name)
    assert ast.dump(old) == ast.dump(new)

# Reuse every original assertion, replacing only the Git transport for an
# already-frozen identical S byte stream. Neither original test is changed.
main_source = before[str(MAIN_TEST)].decode("utf8")
git_fetch = "RAW=subprocess.check_output(['git','show',BLOB],cwd=ROOT)"
assert main_source.count(git_fetch) == 1
main_source = main_source.replace(git_fetch, "RAW=Path(" + repr(str(S)) + ").read_bytes()")
main = types.ModuleType("test_real_gap_balance")
main.__file__ = str(MAIN_TEST)
sys.modules[main.__name__] = main
import os
os.environ["RULES_D"] = str(D1)
os.environ["RULES_D_SELF"] = str(D1)
exec(compile(main_source, str(MAIN_TEST) + "<frozen-S read transport>", "exec"), main.__dict__)
self_test = types.ModuleType("review_D1_self_exclusion_original")
self_test.__file__ = str(SELF_TEST)
sys.modules[self_test.__name__] = self_test
exec(compile(before[str(SELF_TEST)].decode("utf8"), str(SELF_TEST), "exec"), self_test.__dict__)
suite = unittest.TestSuite([
    unittest.defaultTestLoader.loadTestsFromModule(main),
    unittest.defaultTestLoader.loadTestsFromModule(self_test),
])
primary = unittest.TextTestRunner(verbosity=2).run(suite)
assert primary.wasSuccessful() and primary.testsRun == 11


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


# A winner can be vetoed by the unchanged mandatory priority. A second
# locally feasible candidate is not automatically promoted after that veto.
cars = (car(0, 700., 0), car(1, 670., 0), car(2, 640., 0), car(3, 700., 2))
veto_witness = []
for ego in cars[:2]:
    rows = tuple(c for c in cars if c.track != ego.track)
    local = r._fill(ego, rows, 2, True)
    command, memory = r.decide(ego, rows, r.Memory(), "transform")
    assert r._clear(ego, rows, 1) and command.lane is None
    veto_witness.append(dict(ego=asdict(ego), local_fill=local,
        mandatory_priority=r._mandatory_priority(ego, rows, 1, 1000.),
        command=asdict(command), memory=asdict(memory)))
assert veto_witness[0]["local_fill"] == 1 and veto_witness[0]["mandatory_priority"]
assert veto_witness[1]["local_fill"] is None and not veto_witness[1]["mandatory_priority"]

# Independently fuzz labels, rows ordering, non-observable neighbor request
# fields, perception boundaries, hard safety, and actual fill target binding.
rng = random.Random(202611032150)
identity_checks = perception_checks = binding_checks = 0
original_merge = r._merge_target
calls = []


def observed_merge(ego, visible, lane, held=None):
    visible = tuple(visible)
    result = original_merge(ego, visible, lane, held)
    calls.append((ego.track, lane, result, any(c.track == ego.track for c in visible)))
    return result


for index in range(700):
    ego = car(0, rng.uniform(560., 950.), rng.randrange(3), rng.uniform(5., 33.3))
    rows = tuple(replace(car(j + 1, ego.x + rng.uniform(-95., 180.), rng.randrange(3), rng.uniform(5., 33.3)),
                         vy=rng.choice((0., 0., -.2, .2)),
                         y=(rng.randrange(3)+.5)*r.LANE_WIDTH)
                 for j in range(rng.randrange(3, 13)))
    memory = r.Memory(rng.choice((None, None, 0, 1, 2)),
                      rng.choice((None, (1, None), (2, 1))), rng.choice((False, True)))
    mode, drop = rng.choice(("formation", "transform")), rng.choice((None, 1000.))
    calls.clear()
    r._merge_target = observed_merge
    try:
        original = r.decide(ego, rows, memory, mode, drop)
    finally:
        r._merge_target = original_merge
    if original[0].reason == "fill_layer":
        matching = [c for c in calls if c[0] == ego.track and c[1] == original[0].lane]
        assert len(matching) >= 2 and all(not c[3] for c in matching)
        assert matching[0][2] == matching[-1][2]
        assert matching[0][2][0] == original[0].target_x
        assert matching[0][2][2] == original[1].gap
        binding_checks += 1
    assert original[0].speed <= r.safe_speed(ego, rows)
    label = lambda track: 10001 - 29 * track
    mapped_rows = list(replace(c, track=label(c.track), pending_lane=rng.choice((None, 0, 1, 2)),
                               acceleration=rng.uniform(-10., 5.), time=rng.uniform(0., 1200.)) for c in rows)
    rng.shuffle(mapped_rows)
    mapped_memory = replace(memory, gap=(tuple(None if t is None else label(t) for t in memory.gap)
                                         if memory.gap is not None else None))
    changed = r.decide(replace(ego, track=label(ego.track)), tuple(mapped_rows), mapped_memory, mode, drop)
    expected_command = replace(original[0], reference=(label(original[0].reference)
                                                      if original[0].reference is not None else None))
    expected_memory = replace(original[1], gap=(tuple(None if t is None else label(t) for t in original[1].gap)
                                                if original[1].gap is not None else None))
    assert exact(changed) == exact((expected_command, expected_memory)), (index, "identity")
    identity_checks += 1
    outside = (car(100, ego.x - 100.001, 2), car(101, ego.x + 200.001, 0))
    assert exact(r.decide(ego, (*rows, *outside), memory, mode, drop)) == exact(original)
    perception_checks += 1
assert binding_checks > 0
assert all(Path(p).read_bytes() == raw for p, raw in before.items())
result = dict(
    D1_sha256=EXPECTED_D1, frozen_S_sha256=EXPECTED_S,
    original_contract_tests=primary.testsRun, original_contracts_passed=True,
    original_tests_unchanged=True, Git_transport_replaced_in_memory_with_identical_frozen_S=True,
    core_AST_changes_only=["_fill", "_decide"], public_response_cost_AST_equal=True,
    identity_and_neighbor_private_field_checks=identity_checks,
    outside_perception_checks=perception_checks,
    actual_new_fill_same_gap_bindings=binding_checks,
    winner_veto_witness=dict(cars=[asdict(c) for c in cars], counts=[3, 1],
        hypothetical_delta_Phi=-2, outputs=veto_witness,
        scope="unchanged priority can veto the selected winner; no automatic next-winner promotion"),
    protected_sources_and_tests_unchanged=True, production_not_used_as_S_oracle=True,
    no_simulation=True, no_git=True,
)
TARGET.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
print(json.dumps(result))
