"""Independent frozen-GP2 pure-function review; no simulation or source edits."""
from dataclasses import asdict, replace
import gzip
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
CANDIDATES = ROOT / "tmp/staggered_bottleneck/candidates"
GP2 = CANDIDATES / "midflow_bound_real_gap_v2/native_rules.py"
S = CANDIDATES / "cth_priority_phase/native_rules.py"
GP = CANDIDATES / "midflow_bound_real_gap/native_rules.py"
ORACLE = ROOT / "tmp/staggered_bottleneck/J2fast_oracle_20261103/oracle.jsonl.gz"
EXPECTED_GP2 = "37306e86a8e0e1045763bf54ebb3adca60ebc489dde6925a61553240ad0195cc"
EXPECTED_S = "8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"
EXPECTED_ORACLE = "a24adc6bee09319fd1d71eb05c468be76bed54b41d9dd8e55caa43731fbe91f6"
TARGET = OUT / "review_gp2.json"
assert not TARGET.exists()
protected = [GP2, S, GP, ROOT / "variants/phase5g_pure_formation/noa/native_rules.py"]
before = {str(p): p.read_bytes() for p in protected}
sha = lambda raw: hashlib.sha256(raw).hexdigest()
assert sha(before[str(GP2)]) == EXPECTED_GP2
assert sha(before[str(S)]) == EXPECTED_S
assert sha(ORACLE.read_bytes()) == EXPECTED_ORACLE


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


r, s = load("independent_review_gp2", GP2), load("independent_review_frozen_s", S)


def exact(value):
    if hasattr(value, "__dataclass_fields__"):
        return exact(asdict(value))
    if isinstance(value, float):
        return {"hex": value.hex()}
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [exact(v) for v in value]
    return value


def car(track, x, lane=1, speed=20.):
    return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)


# Held preference precedes T; a newly selected shorter nominal T need not be
# the earliest *actual* admission. These are behavior contracts, not failures.
ego = car(0, 680., 2, 10.)
rows = (car(1, 590., speed=10.), car(2, 650.), car(3, 710.), car(4, 810.))
fresh = r._gap_plan(ego, rows, 1, None, 1000.)
held = r._gap_plan(ego, rows, 1, (3, 2), 1000.)
assert fresh[2:] == ((2, 1), 5.)
assert held[2] == (3, 2) and held[3] > 5.
fresh_output = r.decide(ego, rows, r.Memory(), "transform")
held_output = r.decide(ego, rows, r.Memory(gap=(3, 2)), "transform")
assert fresh_output[0].lane is None and held_output[0].lane == 1
assert r._clear(ego, rows, 1)
assert rows[1].x + 5.5 + r.HEADWAY * rows[1].speed - 2 <= ego.x
assert ego.x <= rows[2].x - 5.5 - r.HEADWAY * ego.speed + 2
interposed = (*rows, car(5, 690.))
assert r._gap_plan(ego, interposed, 1, (3, 2), 1000.)[2] != (3, 2)

# Relabel a noncurrent held gap, reorder observations and perturb fields that
# are not legitimate neighbor intent inputs. Full outputs must stay identical.
identity_checks = 0
label = lambda track: 701 - 23 * track
label_car = lambda c: replace(c, track=label(c.track))
expected_command = replace(held_output[0], reference=(
    label(held_output[0].reference) if held_output[0].reference is not None else None))
expected_memory = replace(held_output[1], gap=tuple(label(t) for t in held_output[1].gap))
for order in itertools.permutations(rows):
    changed = tuple(replace(label_car(c), pending_lane=(i % 3),
                            acceleration=5. - i, time=901. + i)
                    for i, c in enumerate(order))
    output = r.decide(label_car(ego), changed,
                      r.Memory(gap=tuple(label(t) for t in (3, 2))), "transform")
    assert exact(output) == exact((expected_command, expected_memory))
    identity_checks += 1
outside = (car(98, ego.x - 100.001, speed=0.), car(99, ego.x + 200.001, speed=0.))
assert exact(r.decide(ego, (*rows, *outside), r.Memory(gap=(3, 2)), "transform")) == exact(held_output)

# CTH position compatibility + the old 8m corridor check do not assert low
# rear braking. This static full-insertion counterfactual is not a prediction
# of actual lateral motion, a collision result, or a traffic simulation.
slow_ego = car(0, 730., 2, 10.)
rear, front = car(1, 709.48), car(2, 850., speed=28.8)
admitted = r.decide(slow_ego, (rear, front), r.Memory(), "transform")
assert admitted[0].lane == 1 and r._clear(slow_ego, (rear, front), 1)
rear_limit = r.safe_speed(rear, (replace(slow_ego, lane=1, y=1.5*r.LANE_WIDTH), front))
assert rear_limit < rear.speed - r.BRAKING * .1

# Scope and the no-resource fallback are compared to the frozen S source,
# not mutable production or the previous GP implementation.
scope_checks = target0_checks = fallback_checks = states = 0
with gzip.open(ORACLE, "rt", encoding="utf8") as stream:
    for line in stream:
        if states == 600:
            break
        state = json.loads(line)["state"]
        memory_data = dict(state["memory"])
        if memory_data["gap"] is not None:
            memory_data["gap"] = tuple(memory_data["gap"])
        a = [r.Vehicle(**c) for c in state["cars"]]
        b = [s.Vehicle(**c) for c in state["cars"]]
        for mode, drop in (("noa", None), ("noa", 1000.), ("formation", None),
                           ("formation", 1000.), ("transform", None)):
            actual = r.decide(a[0], a[1:], r.Memory(**memory_data), mode, drop)
            expected = s.decide(b[0], b[1:], s.Memory(**memory_data), mode, drop)
            assert exact(actual) == exact(expected), (states, mode, drop)
            scope_checks += 1
        if a[0].lane == 1:
            ae, be = replace(a[0], pending_lane=None), replace(b[0], pending_lane=None)
            actual = r.decide(ae, a[1:], r.Memory(lane_target=0), "transform")
            expected = s.decide(be, b[1:], s.Memory(lane_target=0), "transform")
            assert exact(actual) == exact(expected), (states, "target0")
            target0_checks += 1
        if a[0].lane == 2 and a[0].x >= 640.:
            visible = tuple(c for c in a[1:] if -100. <= c.x-a[0].x <= 200.)
            if r._gap_plan(a[0], visible, 1, memory_data["gap"], 1000.) is None:
                for target in (None, 1):
                    data = dict(memory_data, lane_target=target)
                    actual = r.decide(a[0], a[1:], r.Memory(**data), "transform")
                    expected = s.decide(b[0], b[1:], s.Memory(**data), "transform")
                    assert exact(actual) == exact(expected), (states, "no_resource", target)
                    fallback_checks += 1
        states += 1
assert states == 600 and target0_checks > 0 and fallback_checks > 0
assert all(Path(p).read_bytes() == raw for p, raw in before.items())
assert sha(ORACLE.read_bytes()) == EXPECTED_ORACLE
result = dict(
    GP2_sha256=EXPECTED_GP2, frozen_S_sha256=EXPECTED_S, oracle_sha256=EXPECTED_ORACLE,
    pure_function_only=True, no_simulation=True, no_git=True,
    states=states, complete_scope_hex_comparisons=scope_checks,
    active_target0_hex_comparisons=target0_checks,
    no_resource_complete_S_hex_comparisons=fallback_checks,
    held_relabel_permutation_private_field_checks=identity_checks,
    outside_perception_noninterference=True, interposed_vehicle_invalidates_held_pair=True,
    protected_sources_unchanged=True,
    behavior_boundaries={
        "shortest_nominal_T_not_earliest_current_admission": dict(
            ego=asdict(ego), rows=[asdict(c) for c in rows],
            fresh_plan=fresh, held_plan=held,
            fresh_output=[asdict(x) for x in fresh_output],
            current_pair_held_output=[asdict(x) for x in held_output]),
        "current_CTH_band_not_rear_braking_guarantee": dict(
            ego=asdict(slow_ego), rows=[asdict(rear), asdict(front)],
            output=[asdict(x) for x in admitted],
            rear_safe_speed_static_full_insertion=rear_limit,
            scope="static counterfactual; actual lateral trajectory is not simulated"),
    },
)
TARGET.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
print(json.dumps(result))
