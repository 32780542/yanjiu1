"""Read-only E/NC equivalence and F local-policy shadow review; no simulation."""
import argparse
import ast
import copy
import json
from pathlib import Path
import subprocess

import review_candidates as shared


def definitions(raw):
    return {node.name: node for node in ast.parse(raw).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--states", type=int, default=2000)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    root = shared.REPO / "tmp/staggered_bottleneck/candidates"
    paths = {name: root / name / "native_rules.py" for name in ("NC", "direct_gap", "local_oneway_relief")}
    raw = {name: path.read_bytes() for name, path in paths.items()}
    production_before = (shared.REPO / shared.RULE).read_bytes()
    baseline_raw = subprocess.check_output(["git", "show", shared.BASE + ":" + shared.RULE], cwd=shared.REPO)
    assert production_before == baseline_raw
    modules = {name: shared.module("direct_review_" + name, data, paths[name]) for name, data in raw.items()}
    tm = shared.module("direct_review_TM", baseline_raw, shared.BASE)
    e, nc, f = (modules[name] for name in ("direct_gap", "NC", "local_oneway_relief"))
    e_defs, nc_defs = definitions(raw["direct_gap"]), definitions(raw["NC"])
    removed = sorted(nc_defs.keys() - e_defs.keys())
    assert removed == ["_make_room", "_receiving", "_receiving_distance"]
    assert not e_defs.keys() - nc_defs.keys()
    for name in e_defs:
        if name != "_decide":
            assert ast.dump(e_defs[name]) == ast.dump(nc_defs[name]), name
    stripped = copy.deepcopy(nc_defs["_decide"])
    unreachable = [node for node in stripped.body if isinstance(node, ast.If)
                   and ast.unparse(node.test) == "preparing and mode == 'transform' and False"]
    assert len(unreachable) == 1
    stripped.body.remove(unreachable[0])
    assert ast.dump(stripped) == ast.dump(e_defs["_decide"]), "E differs beyond NC's unreachable block deletion"
    f_structure = shared.structure(raw["local_oneway_relief"], raw["direct_gap"])
    assert f_structure["changed_definitions"] == ["_decide"]
    for name in ("direct_gap", "local_oneway_relief"):
        metadata = json.loads((shared.REPO / "docs/experiments/2026-11-03-staggered-bottleneck/candidates" / name / "source.json").read_bytes())
        assert metadata["source_sha256"] == shared.digest(raw[name])
    counts = dict(e_nc_all_modes_exact=0, e_tm_noa_exact=0, e_tm_formation_exact=0,
                  f_e_noa_formation_exact=0, f_e_outside_preparation_exact=0,
                  f_e_straight3_exact=0, f_relabel_order_exact=0, f_remote_exact=0,
                  f_changed_transform_shadows=0, local_relief_outputs=0)
    for index, (values, memory, labels, drop) in enumerate(shared.scenes(args.states)):
        for mode in ("noa", "formation", "transform"):
            assert shared.decision(e, values, memory, mode, drop) == shared.decision(nc, values, memory, mode, drop), ("E/NC", mode)
            counts["e_nc_all_modes_exact"] += 1
            actual = shared.decision(f, values, memory, mode, drop)
            assert shared.decision(f, values, memory, mode, drop, labels, reverse=True) == actual
            counts["f_relabel_order_exact"] += 1
            assert shared.decision(f, values, memory, mode, drop, remote=True) == actual
            counts["f_remote_exact"] += 1
            assert shared.decision(f, values, memory, mode, None) == shared.decision(e, values, memory, mode, None)
            counts["f_e_straight3_exact"] += 1
            outside = copy.deepcopy(values)
            shift = (639.9 if index % 2 else 1000.0) - values[0]["x"]
            for car in outside:
                car["x"] += shift
            assert shared.decision(f, outside, memory, mode, 1000.0) == shared.decision(e, outside, memory, mode, 1000.0)
            counts["f_e_outside_preparation_exact"] += 1
            if mode in ("noa", "formation"):
                assert actual == shared.decision(e, values, memory, mode, drop)
                counts["f_e_noa_formation_exact"] += 1
                assert shared.decision(e, values, memory, mode, drop) == shared.decision(tm, values, memory, mode, drop)
                counts["e_tm_noa_exact" if mode == "noa" else "e_tm_formation_exact"] += 1
        command, private = shared.decision(f, values, memory, "transform", drop)
        counts["f_changed_transform_shadows"] += (command, private) != shared.decision(e, values, memory, "transform", drop)
        if command["reason"] == "local_relief":
            cars, _ = shared.state(f, values, memory)
            ego = cars[0]
            rows = tuple(c for c in cars[1:] if -100 <= c.x - ego.x <= 200)
            window = [c for c in (ego, *rows) if ego.x - 60 <= c.x <= ego.x + 30]
            assert ego.lane == 1 and drop is not None and drop - 360 <= ego.x < drop
            assert sum(1 if c.lane in (1, 2) else -1 for c in window) >= 2
            assert f._clear(ego, rows, 0) and command["lane"] == 0
            counts["local_relief_outputs"] += 1
    assert all(path.read_bytes() == raw[name] for name, path in paths.items())
    assert (shared.REPO / shared.RULE).read_bytes() == production_before
    report = dict(base_commit=shared.BASE, states=args.states, random_seed=shared.SEED, exact_equality=True,
        production_before_sha256=shared.digest(production_before), production_after_sha256=shared.digest((shared.REPO / shared.RULE).read_bytes()),
        candidate_sha256={name: shared.digest(data) for name, data in raw.items()},
        E=dict(removed_functions=removed, nc_decide_after_removing_false_block_ast_equal=True),
        F=f_structure, **counts, driver_sha256=shared.digest(Path(__file__).read_bytes()),
        shared_driver_sha256=shared.digest(Path(shared.__file__).read_bytes()),
        limits=["Finite shadow states are not exhaustive or a SUMO efficiency/safety proof.",
                "Relief outputs reuse observed clearance; no guarantee other cars accept any intention.",
                "Previously committed lane changes retain the parent's execution logic before the new branch."])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(args.output), **counts)), flush=True)


if __name__ == "__main__":
    main()
