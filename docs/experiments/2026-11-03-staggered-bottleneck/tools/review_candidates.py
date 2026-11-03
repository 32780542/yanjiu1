"""Independent, read-only AST and shadow-state review of frozen A/C/D rules."""
import argparse
import ast
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import types

REPO = Path(__file__).resolve().parents[4]
BASE = "177f7a32088fb69efcc94d9acb72863e7e00e787"
RULE = "variants/phase5g_pure_formation/noa/native_rules.py"
EXPECTED = {"gap_projection": ["_decide", "_join_speed", "_merge_target"],
            "continuous_phase": ["_fill", "_phase"], "effective_handoff": ["_make_room"]}
SEED = 202611030931


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def module(name, raw, filename):
    value = types.ModuleType(name)
    value.__file__ = str(filename)
    sys.modules[name] = value
    exec(compile(raw, str(filename), "exec"), value.__dict__)
    return value


def state(module, values, memory, track_map=None):
    track_map = track_map or {i: i for i in range(1000)}
    cars = [module.Vehicle(**{**row, "track": track_map[row["track"]]}) for row in values]
    private = dict(memory)
    if private["gap"] is not None:
        private["gap"] = tuple(track_map[v] if v is not None else None for v in private["gap"])
    return cars, module.Memory(**private)


def decision(module, values, memory, mode, drop_x, track_map=None, reverse=False, remote=False):
    cars, private = state(module, values, memory, track_map)
    rows = cars[1:]
    if reverse:
        rows.reverse()
    if remote:
        rows += [module.Vehicle(880001, cars[0].x - 1500, 1.65, 0, 0),
                 module.Vehicle(880002, cars[0].x + 1500, 8.25, 0, 2)]
    command, private = map(asdict, module.decide(cars[0], rows, private, mode, drop_x))
    if track_map:
        inverse = {value: key for key, value in track_map.items()}
        if command["reference"] is not None:
            command["reference"] = inverse[command["reference"]]
        if private["gap"] is not None:
            private["gap"] = tuple(inverse[v] if v is not None else None for v in private["gap"])
    return command, private


def scenes(count):
    rng = random.Random(SEED)
    for i in range(count):
        lane = rng.randrange(3)
        x = ([639.9, 640, 640.1, 999.9, 1000, 1000.1][i % 6]
             if i % 3 == 0 else rng.uniform(0, 1200))
        values = []
        for track in range(11):
            own_lane = lane if track == 0 else rng.randrange(3)
            values.append(dict(track=track, x=x if track == 0 else x + rng.uniform(-150, 250),
                y=(own_lane + .5) * 3.3 + rng.choice([0, 0, 0, -.25, .25]),
                speed=rng.uniform(0, 33.3), lane=own_lane, vy=rng.choice([0, 0, -.3, .3]),
                acceleration=rng.uniform(-8, 4), time=i * .1,
                pending_lane=rng.choice([None, None, 0, 1, 2]) if track == 0 else None))
        memory = dict(lane_target=rng.choice([None, None, 0, 1, 2]),
                      gap=rng.choice([None, (None, None), (1, 2), (999, 3), (None, 4)]),
                      joining=rng.choice([False, True]))
        labels = rng.sample(range(3000, 13000), 12)
        track_map = dict(zip([*range(11), 999], labels))
        yield values, memory, track_map, None if i % 5 == 0 else 1000.0


def structure(raw, baseline):
    tree, old = ast.parse(raw), ast.parse(baseline)
    definitions = lambda root: {node.name: ast.dump(node, include_attributes=False) for node in root.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    after, before = definitions(tree), definitions(old)
    changed = sorted(key for key in after.keys() | before.keys() if after.get(key) != before.get(key))
    residue = lambda root: [ast.dump(node, include_attributes=False) for node in root.body
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    assert residue(tree) == residue(old), "module constants/imports/global statements changed"
    assert set(after) == set(before), "definitions added/removed"
    functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    keys = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "key":
                continue
            key = functions.get(keyword.value.id, keyword.value) if isinstance(keyword.value, ast.Name) else keyword.value
            assert not any(isinstance(part, ast.Attribute) and part.attr == "track" for part in ast.walk(key)), "track priority key"
            keys.append(ast.unparse(keyword.value))
    return dict(changed_definitions=changed, module_globals_and_imports_unchanged=True,
                class_and_memory_definitions_unchanged=all(key not in ("Vehicle", "Command", "Memory") for key in changed),
                ordering_keys=keys, track_in_ordering_key=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--states", type=int, default=2000)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists")
    baseline_raw = subprocess.check_output(["git", "show", BASE + ":" + RULE], cwd=REPO)
    production_before = (REPO / RULE).read_bytes()
    assert production_before == baseline_raw, "production differs from pinned TM"
    baseline = module("independent_review_tm", baseline_raw, BASE + ":" + RULE)
    cases = list(scenes(args.states))
    report = dict(base_commit=BASE, baseline_sha256=digest(baseline_raw), states=args.states,
                  random_seed=SEED, exact_equality=True, candidates={})
    for name, expected in EXPECTED.items():
        path = REPO / "tmp/staggered_bottleneck/candidates" / name / "native_rules.py"
        if not path.is_file():
            continue
        raw = path.read_bytes()
        candidate = module("independent_review_" + name, raw, path)
        checks = structure(raw, baseline_raw)
        assert checks["changed_definitions"] == expected, (name, checks["changed_definitions"])
        metadata = json.loads((REPO / "docs/experiments/2026-11-03-staggered-bottleneck/candidates" / name / "source.json").read_bytes())
        assert metadata["source_sha256"] == digest(raw), "candidate metadata hash mismatch"
        counts = dict(noa_exact=0, straight3_exact=0, relabel_order_exact=0, remote_exact=0,
                      changed_transform_shadows=0, effective_helpers_checked=0)
        for values, memory, labels, drop in cases:
            assert decision(candidate, values, memory, "noa", drop) == decision(baseline, values, memory, "noa", drop), (name, "NOA")
            counts["noa_exact"] += 1
            for mode in ("noa", "formation", "transform"):
                original = decision(candidate, values, memory, mode, drop)
                assert decision(candidate, values, memory, mode, drop, labels, reverse=True) == original, (name, "track/order", mode)
                counts["relabel_order_exact"] += 1
                assert decision(candidate, values, memory, mode, drop, remote=True) == original, (name, "remote", mode)
                counts["remote_exact"] += 1
                if name in ("continuous_phase", "effective_handoff"):
                    assert decision(candidate, values, memory, mode, None) == decision(baseline, values, memory, mode, None), (name, "straight3", mode)
                    counts["straight3_exact"] += 1
            counts["changed_transform_shadows"] += decision(candidate, values, memory, "transform", drop) != decision(baseline, values, memory, "transform", drop)
            if name == "effective_handoff":
                cars, _ = state(candidate, values, memory)
                head, helper = candidate._make_room(cars[0], cars[1:])
                if helper is not None:
                    assert not candidate._clear(head, cars, 1)
                    assert candidate._clear(helper, cars, 0)
                    assert candidate._clear(head, tuple(c for c in cars if c.track != helper.track), 1)
                    counts["effective_helpers_checked"] += 1
        if name == "continuous_phase":
            assert [candidate._phase(i, 3) for i in range(3)] == [0, 15, 0]
            assert [candidate._phase(i, 2) for i in range(2)] == [0, 15]
            checks["physical_lane_offsets_3_then_2"] = [[0, 15, 0], [0, 15]]
        assert path.read_bytes() == raw, "candidate changed during review"
        report["candidates"][name] = dict(source_path=str(path), sha256=digest(raw), **checks, **counts)
        print(json.dumps(dict(candidate=name, **counts)), flush=True)
    production_after = (REPO / RULE).read_bytes()
    assert production_after == production_before, "production changed during review"
    report.update(production_before_sha256=digest(production_before), production_after_sha256=digest(production_after),
                  production_unchanged=True, driver_sha256=digest(Path(__file__).read_bytes()),
                  limits=["Shadow states are algebraic checks, not SUMO rollouts or efficiency/safety certification.",
                          "Random physical states are finite and include boundary/moving/pending/private-memory cases, but are not exhaustive.",
                          "Track IDs are relabeled and neighbor order reversed; physically exact ties are not generated."])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(args.output), candidates=len(report["candidates"]), production_unchanged=True)))


if __name__ == "__main__":
    main()
