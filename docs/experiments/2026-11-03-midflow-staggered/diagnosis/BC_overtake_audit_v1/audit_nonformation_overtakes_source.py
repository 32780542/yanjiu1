"""Original trigger counts plus observed ordinary-overtake predicates, read-only.

Trips retain latest native submission, not each private intention start. Predicate
checks at that timestamp are qualifications, never reconstructed reason logs.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import importlib.util
import json
from pathlib import Path
import sys
from audit_raw_midflow import read, sha, write_csv


def zone(x):
    return "0_100" if x < 100 else "100_600" if x < 600 else "600_640" if x < 640 else "640_800" if x < 800 else "800_1000" if x < 1000 else "1000_exit"


def analyze(folder, output):
    record = read(folder / "case_record.json")
    assert record.get("seal_status") == "verified" and record["candidate"] in ("BC", "G0")
    run = Path(record["run_dir"])
    trips, result, seal = read(run / "trips.json"), read(run / "result.json"), read(folder / "evidence/seal.json")
    assert sha(run / "positions.jsonl.gz") == seal["originals"]["positions.jsonl.gz"]["sha256"]
    source = run / "source/noa/native_rules.py"
    assert sha(source) == result["source_sha256"]["noa/native_rules.py"]
    spec = importlib.util.spec_from_file_location("frozen_overtake_audit", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    ident = {k: record[k] for k in ("candidate", "flow", "seed", "scenario", "mode")}
    ids = {t["vehicle_id"]: i + 1 for i, t in enumerate(trips)}
    lanes = {t["vehicle_id"]: t["lane"] for t in trips}
    transitions, requests = defaultdict(list), defaultdict(list)
    spatial, types = Counter(), Counter()
    for t in trips:
        for e in t["lane_events"]:
            transitions[round(e["time_s"] * 10)].append((t["vehicle_id"], e["to_lane"]))
            spatial[zone(e["x"]), e["from_lane"], e["to_lane"]] += 1
            types[f"{e['from_lane']}->{e['to_lane']}"] += 1
        for e in t["lane_completion_events"]:
            requests[round(e["requested_s"] * 10)].append(dict(vehicle_id=t["vehicle_id"], **e))
    assert dict(types) == result["lane_transitions"] and sum(types.values()) == result["lane_changes"]
    rows, previous, old_time = [], {}, None
    for line in gzip.open(run / "positions.jsonl.gz", "rt", encoding="utf-8"):
        frame = json.loads(line)
        now, states = frame["time_s"], frame["states"]
        tick = round(now * 10)
        for key, lane in transitions[tick]:
            lanes[key] = lane
        if requests.get(tick):
            cars = {key: module.Vehicle(ids[key], s[0], s[1], s[2], lanes[key],
                         (s[1] - previous[key][1]) / (now - old_time) if key in previous else 0.0, s[3], now)
                    for key, s in states.items()}
            for event in requests[tick]:
                ego = cars[event["vehicle_id"]]
                local = tuple(c for c in cars.values() if c.track != ego.track and -100 <= c.x - ego.x <= 200)
                front = min((c for c in local if c.lane == ego.lane and c.x > ego.x), key=lambda c: c.x, default=None)
                preparing = ego.x >= 640 and (ego.x < 1000 or ego.lane == 2)
                count = 2 if ego.x >= 1000 else 3
                slow = front is not None and ego.speed < module.CRUISE - 2 and front.speed < module.CRUISE - 2
                options = [lane for lane in (ego.lane - 1, ego.lane + 1) if 0 <= lane < count
                           and not (preparing and lane == 2) and not module._mandatory_priority(ego, local, lane, 1000)
                           and module._clear(ego, local, lane)]
                def distance(lane):
                    return min((c.x - ego.x for c in local if c.lane == lane and c.x > ego.x), default=200.0)
                best = max(options, key=distance) if options else None
                advantage = distance(best) - (front.x - ego.x) if best is not None and front else None
                rows.append(dict(**ident, vehicle_id=event["vehicle_id"], requested_s=event["requested_s"],
                                 from_lane=event["from_lane"], to_lane=event["to_lane"], request_x=ego.x, request_zone=zone(ego.x),
                                 ending_to1_after640=event["from_lane"] == 2 and event["to_lane"] == 1 and ego.x >= 640,
                                 ego_speed=ego.speed, front_speed=front.speed if front else None,
                                 front_gap=front.x - ego.x if front else None, slow_front_predicate=slow,
                                 best_clear_lane=best, best_free_distance_advantage_m=advantage,
                                 observed_overtake_qualification=bool(slow and advantage is not None and advantage > 15),
                                 observed_best_lane_equals_submission=best == event["to_lane"]))
        previous, old_time = states, now
    write_csv(output / (folder.name + "_submission_predicates.csv"), rows)
    write_csv(output / (folder.name + "_lane_midpoint_counts.csv"), [dict(**ident, region=key[0], from_lane=key[1], to_lane=key[2], count=value) for key, value in sorted(spatial.items())])
    info = dict(**ident, source_sha256=sha(source), positions_sha256=seal["originals"]["positions.jsonl.gz"]["sha256"],
                exact_action_reasons=result["action_reasons"], exact_lane_transitions=dict(types), exact_execution=result["execution"],
                formation_state=result["formation_state"], completions=len(rows),
                limitations=["Normal_overtake action counts are original recorder counts; no reason log is rewritten or imputed.",
                             "Latest native submission can be an executing retry. Raw predicate qualification is not necessarily the first intention trigger.",
                             "Ending-to1-after640 is a spatial category; a held ordinary intent could have begun upstream of640."])
    (output / (folder.name + "_provenance.json")).write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(**ident, completions=len(rows), output=str(output))), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--expected-cases", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = read(args.batch / "manifest.json")
    assert len(records) == args.expected_cases
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "audit_nonformation_overtakes_source.py").write_bytes(Path(__file__).read_bytes())
    for record in records:
        analyze(Path(record["case_output"]), args.output)
