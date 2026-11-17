"""Audit matched NOA and spacing-only transform under transferred IDM physics."""

import argparse
import json
from pathlib import Path
from statistics import mean

from summarize_shared_physics import diff, extract_case, read_json, summary


def records(batch, mode):
    plan = read_json(batch / "protocol.json")["tasks"]
    executed = {row["seed"]: row for row in read_json(batch / "manifest.json")}
    assert all(row["mode"] == mode and row["flow"] == 2000 for row in plan)
    assert len(executed) == len(plan) and set(executed) == {row["seed"] for row in plan}
    return executed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("noa_batch", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("transform_batches", type=Path, nargs="+")
    args = parser.parse_args()
    noa = records(args.noa_batch, "noa")
    transform = {}
    for batch in args.transform_batches:
        rows = records(batch, "transform")
        assert not (set(rows) & set(transform))
        transform.update(rows)
    assert set(noa) == set(transform)
    comparisons = []
    for seed in sorted(noa):
        row = dict(seed=seed, flow=2000, noa_worker=noa[seed], transform_worker=transform[seed], eligible=False)
        if all(r["verified"] and r["worker_exit"] == 0 for r in (noa[seed], transform[seed])):
            controls, control_result, control_metrics = extract_case(Path(noa[seed]["run"]))
            candidate, candidate_result, candidate_metrics = extract_case(Path(transform[seed]["run"]))
            assert {k: v for k, v in controls.items() if k not in ("case", "source_sha256")} == {
                k: v for k, v in candidate.items() if k not in ("case", "source_sha256")}
            assert {k: v for k, v in controls["case"].items() if k != "mode"} == {
                k: v for k, v in candidate["case"].items() if k != "mode"}
            assert {k for k, v in controls["source_sha256"].items() if v != candidate["source_sha256"][k]} == {
                "noa/native_rules.py"}
            eligible = all(r["safe"] and r["all_completed"] for r in (control_result, candidate_result))
            row.update(noa={**summary(control_result), **control_metrics},
                       transform={**summary(candidate_result), **candidate_metrics},
                       noa_rules_sha256=controls["source_sha256"]["noa/native_rules.py"],
                       transform_rules_sha256=candidate["source_sha256"]["noa/native_rules.py"],
                       eligible=eligible, delta=diff(candidate_metrics, control_metrics) if eligible else None)
        comparisons.append(row)
        print(seed, row["eligible"], flush=True)
    means = None
    if all(r["eligible"] for r in comparisons):
        means = {k: mean(r["delta"][k] for r in comparisons)
                 for k in comparisons[0]["delta"] if all(r["delta"][k] is not None for r in comparisons)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(pairs=comparisons, equal_seed_deltas=means), indent=2,
                                      allow_nan=False) + "\n", encoding="utf-8")
    return int(means is None)


if __name__ == "__main__":
    raise SystemExit(main())
