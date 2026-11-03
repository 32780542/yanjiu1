"""Read-only frozen GP function calls on recorded local observations.

No physics advances, control commands, feedback to an evaluator or log edits.
Existence uses held=None; current containing pair feasibility uses that one real
pair as a separate query. These queries never assert the private held choice.
"""
import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def diagnose(module, ego, rows, ids):
    plan = module._gap_plan(ego, rows, 1, None, 1000.0)
    ordered = sorted((c for c in rows if module._occupies(c, 1)), key=lambda c: (c.x, c.y, c.speed, c.vy))
    front = min((c for c in ordered if c.x > ego.x), key=lambda c: c.x, default=None)
    rear = max((c for c in ordered if c.x <= ego.x), key=lambda c: c.x, default=None)
    gap = (front.track if front else None, rear.track if rear else None)
    fg, rg = front.x - ego.x if front else None, ego.x - rear.x if rear else None
    front_residual = fg - module.LENGTH - module.STANDSTILL - module.HEADWAY * ego.speed if front else None
    rear_residual = rg - module.LENGTH - module.STANDSTILL - module.HEADWAY * rear.speed if rear else None
    compatible = (front_residual is None or front_residual >= -1e-8) and (rear_residual is None or rear_residual >= -1e-8)
    low = rear.x + module.LENGTH + module.STANDSTILL + module.HEADWAY * rear.speed if rear else -float("inf")
    high = front.x - module.LENGTH - module.STANDSTILL - module.HEADWAY * ego.speed if front else float("inf")
    compatible_exact = low <= ego.x <= high
    compatible2 = low - 2.0 <= ego.x <= high + 2.0
    current = module._gap_plan(ego, rows, 1, gap, 1000.0) if plan is not None and front and rear else None
    containing_feasible = current is not None and current[2] == gap
    by_track = {c.track: c for c in rows}
    plan_contains = False
    if plan is not None:
        pf, pr = (by_track[k] for k in plan[2])
        plan_contains = pr.x <= ego.x <= pf.x
    return dict(plan_exists=plan is not None, horizon_expired=(1000 - ego.x) / module.CRUISE - 1 <= 0,
                current_front=ids.get(front.track) if front else None, current_rear=ids.get(rear.track) if rear else None,
                current_pair_both_real=bool(front and rear), current_front_gap_m=fg, current_rear_gap_m=rg,
                current_front_cth_residual_m=front_residual, current_rear_cth_residual_m=rear_residual,
                current_cth_compatible=compatible, current_cth_exact_window=compatible_exact,
                current_cth_with_2m_band=compatible2,
                current_pair_nominally_feasible=containing_feasible,
                free_minenergy_pair_contains_ego=plan_contains,
                free_plan_T_s=plan[3] if plan else None,
                free_plan_front=ids.get(plan[2][0]) if plan else None,
                free_plan_rear=ids.get(plan[2][1]) if plan else None)


def case(folder, output, window):
    record = read(folder / "case_record.json")
    assert record.get("seal_status") == "verified"
    run = Path(record["run_dir"])
    source = run / "source/noa/native_rules.py"
    result, trips = read(run / "result.json"), read(run / "trips.json")
    assert sha(source) == result["source_sha256"]["noa/native_rules.py"]
    spec = importlib.util.spec_from_file_location("frozen_gap_audit", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert hasattr(module, "_gap_plan")
    seal = read(folder / "evidence/seal.json")
    raw = run / "positions.jsonl.gz"
    assert sha(raw) == seal["originals"][raw.name]["sha256"]
    ident = {k: record[k] for k in ("candidate", "flow", "seed", "scenario", "mode")}
    # Actual recorded lane transitions avoid ambiguous exact-border y rounding.
    lanes = {t["vehicle_id"]: t["lane"] for t in trips}
    ids = {t["vehicle_id"]: i + 1 for i, t in enumerate(trips)}
    reverse = {v: k for k, v in ids.items()}
    transitions, requests, completions = defaultdict(list), defaultdict(list), defaultdict(list)
    events = []
    for trip in trips:
        for e in trip["lane_events"]:
            transitions[round(e["time_s"] * 10)].append((trip["vehicle_id"], e["to_lane"]))
        for e in trip["lane_completion_events"]:
            if (e["from_lane"], e["to_lane"]) == (2, 1):
                event = dict(vehicle_id=trip["vehicle_id"], request_s=e["requested_s"], complete_s=e["time_s"], started=False)
                events.append(event)
                requests[round(e["requested_s"] * 10)].append(event)
                completions[round(e["time_s"] * 10)].append(event)
    stats, stages, previous, old_time, active = defaultdict(lambda: defaultdict(float)), [], {}, None, []
    for line in gzip.open(raw, "rt", encoding="utf-8"):
        frame = json.loads(line)
        now, states = frame["time_s"], frame["states"]
        tick = round(now * 10)
        for vehicle, lane in transitions.get(tick, ()):
            lanes[vehicle] = lane
        vehicles = {key: module.Vehicle(ids[key], s[0], s[1], s[2], lanes[key],
                    (s[1] - previous[key][1]) / (now - old_time) if old_time is not None and key in previous else 0,
                    s[3], now) for key, s in states.items()}

        def local(ego):
            return tuple(c for c in vehicles.values() if c.track != ego.track and -100 <= c.x - ego.x <= 200)

        if window[0] <= now < window[1]:
            for ego in vehicles.values():
                if ego.lane != 2 or not 640 <= ego.x <= 1000 or abs(ego.vy) > 1e-7 or abs(ego.y - 8.25) > 1e-6:
                    continue
                f = diagnose(module, ego, local(ego), reverse)
                region = "640_700" if ego.x < 700 else "700_800" if ego.x < 800 else "800_900" if ego.x < 900 else "900_1000_inclusive"
                r = stats[region]
                r["stationary_lane2_vehicle_s"] += .1
                for key in ("plan_exists", "horizon_expired", "current_cth_compatible", "current_cth_exact_window", "current_cth_with_2m_band", "current_pair_both_real", "current_pair_nominally_feasible", "free_minenergy_pair_contains_ego"):
                    r[key + "_vehicle_s"] += int(f[key]) * .1
                r["no_plan_vehicle_s"] += (not f["plan_exists"]) * .1
                r["current_cth_and_nominally_feasible_vehicle_s"] += (f["current_cth_compatible"] and f["current_pair_nominally_feasible"]) * .1
                r["current_cth_band2_and_nominally_feasible_vehicle_s"] += (f["current_cth_with_2m_band"] and f["current_pair_nominally_feasible"]) * .1
                r["current_cth_exact_and_nominally_feasible_vehicle_s"] += (f["current_cth_exact_window"] and f["current_pair_nominally_feasible"]) * .1
        for event in requests.get(tick, ()):
            ego = vehicles.get(event["vehicle_id"])
            if ego is None or ego.x < 640:
                continue
            f = diagnose(module, ego, local(ego), reverse)
            stages.append(dict(**ident, vehicle_id=event["vehicle_id"], request_s=event["request_s"], stage="request", time_s=now,
                               x=ego.x, speed=ego.speed, **f))
            event["request_pair"] = f["current_front"], f["current_rear"]
            active.append(event)
        for event in active:
            ego = vehicles.get(event["vehicle_id"])
            if not event["started"] and ego is not None and abs(ego.y - 8.25) > 1e-6:
                event["started"] = True
                f = diagnose(module, ego, local(ego), reverse)
                stages.append(dict(**ident, vehicle_id=event["vehicle_id"], request_s=event["request_s"], stage="lateral_start", time_s=now,
                                   x=ego.x, speed=ego.speed, same_pair_as_request=(f["current_front"], f["current_rear"]) == event["request_pair"], **f))
        active = [e for e in active if now < e["complete_s"]]
        previous, old_time = states, now
    write_csv(output / (folder.name + "_availability.csv"), [dict(**ident, region=k, **v) for k, v in stats.items()])
    write_csv(output / (folder.name + "_stages.csv"), stages)
    metadata = dict(**ident, source_sha256=sha(source), positions_sha256=seal["originals"][raw.name]["sha256"],
                    window_s=list(window), action_reasons=result["action_reasons"], execution=result["execution"],
                    stage_rows=len(stages), limitations=[
                    "Held=None existence is independent of private memory; inferred current containing pair is not asserted to equal private held except admission enforces containment.",
                    "Availability is all stationary lane2 preparation samples in the stated complete 0.1s window, not all controller calls or all lane1 fill calls.",
                    "Lateral velocity is measured-y finite difference; same frozen executor validated against 35523 diagnostic samples with maximum 7.99e-14 error. Actual lane comes from original trip transition times.",
                    "Actual stage CTH uses measured own and rear speeds; nominal endpoint feasibility does not prove actual constant-speed future behavior."])
    metadata["cth_columns"] = {"current_cth_compatible": "residual >= -1e-8 m numeric strictness", "current_cth_exact_window": "low<=x<=high, zero physical band", "current_cth_with_2m_band": "low-2<=x<=high+2, native GP2 band arithmetic"}
    (output / (folder.name + "_provenance.json")).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(**ident, stages=len(stages), output=str(output))), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--expected-cases", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--window-start", type=float, default=30)
    parser.add_argument("--window-end", type=float, default=180)
    args = parser.parse_args()
    records = read(args.batch / "manifest.json")
    assert len(records) == args.expected_cases
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "audit_gap_planner_source.py").write_bytes(Path(__file__).read_bytes())
    for record in records:
        case(Path(record["case_output"]), args.output, (args.window_start, args.window_end))
