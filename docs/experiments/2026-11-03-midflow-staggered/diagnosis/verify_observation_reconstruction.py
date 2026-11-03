"""Calibrate raw x/y/v/a + recorded lane-event reconstruction against diagnostics."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(folder, output):
    trips = json.loads((folder / "trips.json").read_text(encoding="utf-8"))
    lanes = {t["vehicle_id"]: t["lane"] for t in trips}
    transitions = defaultdict(list)
    for t in trips:
        for e in t["lane_events"]:
            transitions[round(e["time_s"] * 10)].append((t["vehicle_id"], e["to_lane"]))
    previous, old_time, samples, differences, lane_bad, simple_lane_bad, max_error = {}, None, 0, 0, 0, 0, 0.0
    with gzip.open(folder / "positions.jsonl.gz", "rt") as raw, gzip.open(folder / "diagnostic.jsonl.gz", "rt") as diagnostic:
        for line in diagnostic:
            d, p = json.loads(line), json.loads(next(raw))
            assert d["time_s"] == p["time_s"] and d["states"].keys() == p["states"].keys()
            now = d["time_s"]
            for key, lane in transitions[round(now * 10)]:
                lanes[key] = lane
            for key, state in d["states"].items():
                assert p["states"][key] == [state[k] for k in ("x", "y", "speed", "acceleration")]
                samples += 1
                lane_bad += lanes[key] != state["lane"]
                simple_lane_bad += max(0, min(2, int(state["y"] / 3.3))) != state["lane"]
                if key in previous:
                    error = abs((state["y"] - previous[key]["y"]) / (now - old_time) - state["vy"])
                    max_error = max(max_error, error)
                    differences += 1
            previous, old_time = d["states"], now
        assert next(raw, None) is None
    assert lane_bad == 0 and max_error < 1e-7
    report = dict(run_dir=str(folder.resolve()), source="Existing full S geometric demo; no simulation",
                  raw_diagnostic_samples=samples, lateral_velocity_differences=differences,
                  max_abs_vy_error=max_error, event_replayed_lane_mismatches=lane_bad,
                  naive_y_rounding_lane_mismatches=simple_lane_bad,
                  sha256={name: sha(folder / name) for name in ("positions.jsonl.gz", "diagnostic.jsonl.gz", "trips.json")})
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.run, args.output)
