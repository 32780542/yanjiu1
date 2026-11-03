"""New explicitly labelled short-window flow accounting, never the old [100,600) metric."""
import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RUNS = ROOT / "tmp/staggered_bottleneck/diagnostic2500_20261103"


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


crossing_rows, window_rows, summaries = [], [], []
hashes, inputs = {}, []
for mode in ("transform", "noa", "formation"):
    case = next((RUNS / mode).glob("20*"))
    inp = json.loads((case / "input.json").read_text())
    inputs.append(inp["arrivals"])
    result = json.loads((case / "result.json").read_text())
    previous = None
    crossed = set()
    with gzip.open(case / "diagnostic.jsonl.gz", "rt") as f:
        for line in f:
            frame = json.loads(line)
            if previous is not None:
                for k in set(frame["states"]) & set(previous["states"]):
                    a, b = previous["states"][k], frame["states"][k]
                    for gate in (640, 1000, 1100):
                        if (k, gate) not in crossed and a["x"] < gate <= b["x"]:
                            time = previous["time_s"] + (gate - a["x"]) / (b["x"] - a["x"]) * (frame["time_s"] - previous["time_s"])
                            crossed.add((k, gate))
                            crossing_rows.append(dict(mode=mode, vehicle_id=k, gate_m=gate, crossing_s=time, observed_lane=b["lane"]))
            previous = frame
    for gate in (640, 1000, 1100):
        for start, end in ((60, 120), (120, 180), (180, 240), (240, 300), (300, 360)):
            count = sum(r["mode"] == mode and r["gate_m"] == gate and start <= r["crossing_s"] < end for r in crossing_rows)
            full = result["actual_end_s"] >= end
            # Earlier drainage guarantees the remainder of the window is empty.
            assert result["all_completed"]
            window_rows.append(dict(mode=mode, gate_m=gate, start_s=start, end_s=end, count=count,
                observed_flow_veh_h=count * 3600 / (end-start), simulation_reached_window_end=full,
                note="Drained-early remainder is zero; finite-window flow, not capacity"))
    reasons = list(csv.DictReader((OUT / (mode + "_reasons.csv")).open(encoding="utf-8-sig")))
    trips = json.loads((case / "trips.json").read_text())
    recomputed_tt = sum(r["exited_s"] - r["entered_s"] for r in trips) / len(trips)
    assert abs(recomputed_tt - result["mean_travel_time_s"]) < 1e-8
    row = dict(mode=mode, requested=result["requested"], completed=result["completed"],
        actual_request_total_veh_h=result["requested"] / 180 * 3600,
        mean_tt_s=result["mean_travel_time_s"], mean_system_time_s=result["mean_system_time_s"],
        mean_entry_wait_s=result["mean_entry_wait_s"], end_s=result["actual_end_s"],
        all_route_low5_vehicle_s=sum(float(r["low5_vehicle_s"]) for r in reasons),
        lane_changes=result["lane_changes"], lane_change_completions=result["lane_change_completions"],
        native_lane_requests=result["execution"]["native_lane_requests"],
        local_guard_rejections=result["execution"].get("local_lane_guard_rejected", 0),
        collisions=result["collisions"], teleports=result["teleports"])
    summaries.append(row)
    for name in ("input.json", "result.json", "trips.json", "diagnostic.jsonl.gz"):
        path = case / name
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
assert inputs[0] == inputs[1] == inputs[2]
write_csv("crossings.csv", crossing_rows)
write_csv("crossing_windows.csv", window_rows)
write_csv("summary.csv", summaries)
manifest = dict(same_arrivals_all_three=True, case_count=3, source_rules_sha256="65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317", source_hashes=hashes)
(OUT / "verification.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
print(json.dumps(dict(cases=3, crossing_records=len(crossing_rows), windows=len(window_rows), same_arrivals=True)))
