"""Extract regional braking, observed headway and real lateral starts from sealed raw.

Read-only simulation inputs. Output directory must be new. Evaluation sees the
whole recorded frame; none of its values are returned to the controller.
"""
import argparse
from bisect import bisect_right
from collections import defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean

CRUISE, WIDTH, LANE_WIDTH = 28.8, 1.8, 3.3
HEADWAY = (30 - 4 - 1.5) / CRUISE
BOUNDS = (0, 100, 600, 640, 700, 800, 900, 1000, 1100, 1200.001)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_csv(path, rows):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def quantile(values, q):
    if not values:
        return None
    values.sort()
    x = (len(values) - 1) * q
    i = int(x)
    return values[i] + (values[min(i + 1, len(values) - 1)] - values[i]) * (x - i)


def region(x):
    i = max(0, min(len(BOUNDS) - 2, bisect_right(BOUNDS, x) - 1))
    return f"{BOUNDS[i]}_{round(BOUNDS[i + 1])}"


def analyze_case(folder, output, window):
    record = read(folder / "case_record.json")
    assert record.get("seal_status") == "verified", "unsealed case: " + str(folder)
    run = Path(record["run_dir"])
    result, trips = read(run / "result.json"), read(run / "trips.json")
    assert result["status"] != "starting"
    raw = run / "positions.jsonl.gz"
    seal = read(folder / "evidence/seal.json")
    assert raw.stat().st_size == seal["originals"][raw.name]["bytes"]
    digest = sha(raw)
    assert digest == seal["originals"][raw.name]["sha256"]
    ident = dict(candidate=record["candidate"], mode=record["mode"], flow=record["flow"],
                 seed=record["seed"], scenario=record["scenario"])
    start_lane = {t["vehicle_id"]: t["lane"] for t in trips}
    merges = []
    merge_by_vehicle = defaultdict(list)
    for trip in trips:
        for completion in trip["lane_completion_events"]:
            if (completion["from_lane"], completion["to_lane"]) != (2, 1):
                continue
            event = dict(**ident, vehicle_id=trip["vehicle_id"], initial_lane=trip["lane"],
                         request_s=completion["requested_s"], complete_s=completion["time_s"],
                         complete_x=completion["x"], request_x=None, request_speed=None,
                         lateral_start_s=None, lateral_start_x=None, lateral_start_speed=None,
                         min_speed_during_merge=None, min_acceleration_during_merge=None,
                         target_front_gap_at_request_m=None, target_rear_gap_at_request_m=None,
                         target_rear_vehicle=None, target_rear_speed_at_request=None,
                         target_rear_cth_residual_at_request_m=None,
                         target_rear_min_speed_through_complete_plus2=None,
                         target_rear_min_acceleration_through_complete_plus2=None)
            merges.append(event)
            merge_by_vehicle[trip["vehicle_id"]].append(event)
    accum = defaultdict(lambda: defaultdict(float))
    gaps, headways, residuals = defaultdict(list), defaultdict(list), defaultdict(list)
    previous, old_time, frames = None, None, 0

    def integrate_merge_windows(states, t0, t1):
        for event in merges:
            if t1 <= event["request_s"] or t0 >= event["complete_s"] + 5:
                continue
            intervals = (("merge", event["request_s"], event["complete_s"]),
                         ("post0_2", event["complete_s"], event["complete_s"] + 2),
                         ("post2_5", event["complete_s"] + 2, event["complete_s"] + 5),
                         ("through_post5", event["request_s"], event["complete_s"] + 5))
            for role, vehicle in (("entrant", event["vehicle_id"]), ("receiver", event["target_rear_vehicle"])):
                state = states.get(vehicle)
                if state is None:
                    continue
                v, a = state[2:4]
                for label, lo, hi in intervals:
                    dt = max(0, min(t1, hi) - max(t0, lo))
                    if not dt:
                        continue
                    prefix = role + "_" + label + "_"
                    values = dict(observed_s=dt, negative_acceleration_integral_mps=max(0, -a) * dt,
                                  acceleration_square_integral_m2ps3=a * a * dt,
                                  positive_speed_deficit_s=max(0, 1 - v / CRUISE) * dt,
                                  hard_brake_s=(a <= -6) * dt, strong_brake_s=(a <= -3) * dt)
                    for field, value in values.items():
                        event[prefix + field] = event.get(prefix + field, 0.0) + value
                    event[prefix + "min_acceleration_mps2"] = min(event.get(prefix + "min_acceleration_mps2", a), a)
                    event[prefix + "min_speed_mps"] = min(event.get(prefix + "min_speed_mps", v), v)

    def accumulate(states, time_s, dt):
        if not window[0] <= time_s < window[1]:
            return
        dt = min(dt, window[1] - time_s)
        ordered = sorted(states.items(), key=lambda kv: (kv[1][0], kv[1][1]))
        corridors = [[(key, s) for key, s in ordered if abs(s[1] - (lane + .5) * LANE_WIDTH) <
                      LANE_WIDTH / 2 + WIDTH / 2] for lane in range(3)]
        xs = [[s[0] for _, s in lane] for lane in corridors]
        for vehicle, s in states.items():
            x, y, v, a = s
            lane = max(0, min(2, int(y / LANE_WIDTH)))
            keys = [(region(x), "all", -1), (region(x), "physical_lane", lane),
                    (region(x), "initial_lane", start_lane[vehicle])]
            front = next(((other, fs) for other, fs in corridors[lane][bisect_right(xs[lane], x):]
                          if other != vehicle and fs[0] - x <= 200), None)
            for group in keys:
                row = accum[group]
                row["vehicle_s"] += dt
                row["speed_integral_m"] += v * dt
                row["positive_speed_deficit_s"] += max(0, 1 - v / CRUISE) * dt
                row["brake_vehicle_s_a_lt_minus0p1"] += (a < -.1) * dt
                row["strong_brake_vehicle_s_a_le_minus3"] += (a <= -3) * dt
                row["hard_brake_vehicle_s_a_le_minus6"] += (a <= -6) * dt
                row["low_speed_vehicle_s_v_lt5"] += (v < 5) * dt
                row["negative_acceleration_integral_mps"] += max(0, -a) * dt
                row["min_speed_mps"] = min(row.get("min_speed_mps", v), v)
                row["min_acceleration_mps2"] = min(row.get("min_acceleration_mps2", a), a)
                if front is not None:
                    gap = front[1][0] - x
                    row["front_observed_vehicle_s"] += dt
                    row["cth_deficit_vehicle_s"] += (gap < 5.5 + HEADWAY * v) * dt
                    gaps[group].append(gap)
                    residuals[group].append(gap - 5.5 - HEADWAY * v)
                    if v > .1:
                        headways[group].append(gap / v)

    with gzip.open(raw, "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            t, states = frame["time_s"], frame["states"]
            if old_time is not None:
                assert 0 < t - old_time < .100001, "missing/duplicate frame"
                accumulate(previous, old_time, t - old_time)
                integrate_merge_windows(previous, old_time, t)
            for vehicle, events in merge_by_vehicle.items():
                s = states.get(vehicle)
                if s is None:
                    continue
                for event in events:
                    if abs(t - event["request_s"]) < 1e-7:
                        event["request_x"], event["request_speed"] = s[0], s[2]
                        target = [(other, fs) for other, fs in states.items() if other != vehicle and
                                  abs(fs[1] - 4.95) < LANE_WIDTH / 2 + WIDTH / 2]
                        front = min(((other, fs) for other, fs in target if 0 < fs[0] - s[0] <= 200),
                                    key=lambda kv: kv[1][0], default=None)
                        rear = max(((other, fs) for other, fs in target if 0 <= s[0] - fs[0] <= 100),
                                   key=lambda kv: kv[1][0], default=None)
                        if front:
                            event["target_front_gap_at_request_m"] = front[1][0] - s[0]
                        if rear:
                            event["target_rear_vehicle"] = rear[0]
                            event["target_rear_gap_at_request_m"] = s[0] - rear[1][0]
                            event["target_rear_speed_at_request"] = rear[1][2]
                            event["target_rear_cth_residual_at_request_m"] = s[0] - rear[1][0] - 5.5 - HEADWAY * rear[1][2]
                    if event["request_s"] - 1e-7 <= t <= event["complete_s"] + 2 + 1e-7:
                        rear_state = states.get(event["target_rear_vehicle"])
                        if rear_state:
                            for field, value in (("target_rear_min_speed_through_complete_plus2", rear_state[2]),
                                                 ("target_rear_min_acceleration_through_complete_plus2", rear_state[3])):
                                event[field] = min(event[field] if event[field] is not None else value, value)
                    if event["request_s"] - 1e-7 <= t <= event["complete_s"] + 1e-7:
                        if abs(s[1] - 8.25) > 1e-6 and event["lateral_start_s"] is None:
                            event["lateral_start_s"], event["lateral_start_x"], event["lateral_start_speed"] = t, s[0], s[2]
                        event["min_speed_during_merge"] = min(event["min_speed_during_merge"] if
                                                                 event["min_speed_during_merge"] is not None else s[2], s[2])
                        event["min_acceleration_during_merge"] = min(event["min_acceleration_during_merge"] if
                                                                        event["min_acceleration_during_merge"] is not None else s[3], s[3])
            previous, old_time, frames = states, t, frames + 1
    rows = []
    for group, value in sorted(accum.items()):
        r, group_type, lane = group
        rows.append(dict(**ident, region=r, group_type=group_type, lane=lane, **value,
                         mean_speed_mps=value["speed_integral_m"] / value["vehicle_s"],
                         observed_front_gap_p05_m=quantile(gaps[group], .05),
                         observed_front_gap_p50_m=quantile(gaps[group], .5),
                         observed_front_gap_p95_m=quantile(gaps[group], .95),
                         observed_headway_p05_s=quantile(headways[group], .05),
                         observed_headway_p50_s=quantile(headways[group], .5),
                         cth_residual_p05_m=quantile(residuals[group], .05),
                         cth_residual_p50_m=quantile(residuals[group], .5)))
    name = folder.name
    assert all(e["request_x"] is not None and e["lateral_start_x"] is not None for e in merges), "unobserved request/start"
    event_checks, event_max_error = 0, 0.0
    for event in merges:
        for role in ("entrant", "receiver"):
            if role + "_through_post5_observed_s" not in event:
                continue
            for metric in ("observed_s", "negative_acceleration_integral_mps", "acceleration_square_integral_m2ps3",
                           "positive_speed_deficit_s", "hard_brake_s", "strong_brake_s"):
                total = event[role + "_through_post5_" + metric]
                parts = sum(event.get(role + "_" + w + "_" + metric, 0.0) for w in ("merge", "post0_2", "post2_5"))
                error = abs(parts - total)
                event_max_error = max(event_max_error, error)
                event_checks += 1
                assert error < 1e-6 and total >= 0, "event integral conservation failure"
            for w in ("merge", "post0_2", "post2_5", "through_post5"):
                prefix = role + "_" + w + "_"
                if prefix + "observed_s" in event:
                    assert event[prefix + "hard_brake_s"] <= event[prefix + "strong_brake_s"] + 1e-8
                    assert event[prefix + "strong_brake_s"] <= event[prefix + "observed_s"] + 1e-8
    metadata = read(folder / "evidence" / seal["traffic_metadata"])
    ledger_dir = (folder / "evidence" / seal["traffic_metadata"]).parent
    expected = dict(vehicle_s=0.0, speed_integral_m=0.0, low_speed_vehicle_s=0.0)
    observed_duration_s = 0.0
    with gzip.open(ledger_dir / "region_steps.jsonl.gz", "rt", encoding="utf-8") as stream:
        next(stream)
        for line in stream:
            t0, t1, n, low_n, speed_sum = json.loads(line)
            dt = max(0, min(t1, window[1]) - max(t0, window[0]))
            observed_duration_s += dt
            expected["vehicle_s"] += n * dt
            expected["speed_integral_m"] += speed_sum * dt
            expected["low_speed_vehicle_s"] += low_n * dt
    retained_region = [r for r in rows if r["group_type"] == "all" and r["region"] in ("800_900", "900_1000")]
    vehicle_s = sum(r["vehicle_s"] for r in retained_region)
    recomputed = dict(vehicle_s=vehicle_s,
                      speed_integral_m=sum(r["speed_integral_m"] for r in retained_region),
                      low_speed_vehicle_s=sum(r["low_speed_vehicle_s_v_lt5"] for r in retained_region))
    errors = {k: abs(recomputed[k] - expected[k]) for k in recomputed}
    assert max(errors.values()) < 1e-6, "independent region ledger disagreement"
    write_csv(output / (name + "_regions.csv"), rows)
    write_csv(output / (name + "_merges.csv"), merges)
    info = dict(**ident, case_dir=str(run), positions_sha256=digest, positions_bytes=raw.stat().st_size,
                analysis_script_sha256=sha(Path(__file__)), seal_sha256=sha(folder / "evidence/seal.json"),
                event_integral_invariant_checks=event_checks, event_integral_max_absolute_error=event_max_error,
                frames=frames, events=len(merges), all_complete=result["all_completed"], safe=result["safe"],
                window_s=list(window), observed_duration_s=observed_duration_s,
                window_complete=abs(observed_duration_s - (window[1] - window[0])) < 1e-6,
                independent_region_ledger_absolute_errors=errors,
                limitations=[f"Region metrics use [{window[0]},{window[1]}) left-held measured samples; no terminal extrapolation.",
                             "Event integrals use full recorded requests: [request,complete), [complete,complete+2), [complete+2,complete+5), and [request,complete+5). Observed_s exposes any vehicle exit censoring.",
                             "Event-associated receiver histories may overlap across merges and must not be summed as unique network exposure; regional metrics count each vehicle-frame once.",
                             "Strong/hard thresholds -3/-6 m/s2 are explicit diagnostic labels, not SUMO emergency events.",
                             "Lateral start is first 0.1s measured sample >1e-6m from source lane2 center after recorded native request.",
                             "Front gaps are front-to-front positions within 200m in ego nominal physical corridor; straddling neighbors are included.",
                             "Headway percentiles use samples with own speed >0.1m/s; absolute gap statistics include stopped cars."])
    (output / (name + "_provenance.json")).write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(**ident, frames=frames, merge_events=len(merges), output=str(output)), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--case", type=Path, action="append", help="case wrapper containing verified case_record.json")
    selection.add_argument("--batch", type=Path, help="completed batch with manifest.json; no recursive search")
    parser.add_argument("--expected-cases", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--window-start", type=float, default=100.0)
    parser.add_argument("--window-end", type=float, default=600.0)
    args = parser.parse_args()
    assert 0 <= args.window_start < args.window_end
    if args.batch:
        records = read(args.batch / "manifest.json")
        assert args.expected_cases is not None and len(records) == args.expected_cases, "batch not fully sealed"
        folders = [Path(r["case_output"]) for r in records]
        assert len(set(folders)) == len(folders), "duplicate batch records"
    else:
        folders = args.case
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "audit_raw_midflow_source.py").write_bytes(Path(__file__).read_bytes())
    for folder in folders:
        analyze_case(folder.resolve(), args.output.resolve(), (args.window_start, args.window_end))
