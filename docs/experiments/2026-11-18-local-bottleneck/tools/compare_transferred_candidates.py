"""Pair transform-only candidates against both shared-physics baselines."""

import argparse
import json
from pathlib import Path

from summarize_shared_physics import diff, extract_case, read_json, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--candidate", required=True, nargs="+", metavar="LABEL=MANIFEST")
    args = parser.parse_args()
    reference = {(row["flow"], row["seed"], row["mode"]): row
                 for row in read_json(args.baseline)["cases"] if row["profile"] == "transfer"}
    rows = []
    for spec in args.candidate:
        label, name = spec.split("=", 1)
        for row in read_json(Path(name)):
            assert row["verified"] and row["worker_exit"] == 0, row
            flow, seed = row["flow"], row["seed"]
            run = Path(row["run"])
            case, result, measured = extract_case(run)
            item = dict(candidate=label, flow=flow, seed=seed, run=str(run), **summary(result), metrics=measured)
            for mode in ("noa", "transform"):
                ref = reference[flow, seed, mode]
                ref_case = read_json(Path(ref["run"]) / "input.json")
                assert {k: v for k, v in case.items() if k not in ("case", "source_sha256")} == {
                    k: v for k, v in ref_case.items() if k not in ("case", "source_sha256")}
                assert {k: v for k, v in case["case"].items() if k != "mode"} == {
                    k: v for k, v in ref_case["case"].items() if k != "mode"}
                assert {part for part, sha in case["source_sha256"].items()
                        if sha != ref_case["source_sha256"][part]} == {"noa/native_rules.py"}
                item["minus_" + mode] = diff(measured, ref)
            rows.append(item)
            print(label, flow, seed, result["status"], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(sorted(rows, key=lambda r: (r["candidate"], r["flow"], r["seed"])),
                                      indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
