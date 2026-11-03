"""Public-state D1/DR/DP fill-score queries, not private intention reconstruction."""
import argparse
import ast
from collections import defaultdict
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import sys
from audit_raw_midflow import read, sha, write_csv


def instrument(module):
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    original = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_fill")
    node = copy.deepcopy(original)
    assert isinstance(node.body[-3], ast.If) and isinstance(node.body[-1], ast.Return)
    node.name = "_fill_trace"
    node.body[-3].body = ast.parse("return dict(counts=tuple(counts), choices=choices, winner=None)").body
    node.body[-1] = ast.parse("return dict(counts=tuple(counts), choices=choices, winner=(car,lane))").body[0]
    transformed = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    namespace = dict(module.__dict__)
    exec(compile(transformed, "<read-only-fill-trace>", "exec"), namespace)
    decide = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_decide")
    definitions = {n.targets[0].id: n.value for n in decide.body if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)}
    call = next(n for n in ast.walk(decide) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_fill")
    context = [(k, compile(ast.Expression(definitions[k]), "<public-map-scope>", "eval")) for k in ("preparing", "receiving", "lanes")]
    arguments = [compile(ast.Expression(n), "<public-fill-argument>", "eval") for n in call.args[2:]]
    return namespace["_fill_trace"], context, arguments, ast.unparse(transformed)


def analyze(folder, output, window):
    record = read(folder / "case_record.json")
    assert record.get("seal_status") == "verified"
    run = Path(record["run_dir"])
    trips, result, seal = read(run / "trips.json"), read(run / "result.json"), read(folder / "evidence/seal.json")
    raw, source = run / "positions.jsonl.gz", run / "source/noa/native_rules.py"
    assert sha(raw) == seal["originals"][raw.name]["sha256"] and sha(source) == result["source_sha256"]["noa/native_rules.py"]
    spec = importlib.util.spec_from_file_location("frozen_real_gap_audit", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    traced, context, arguments, trace_source = instrument(module)
    ident = {k: record[k] for k in ("candidate", "flow", "seed", "scenario", "mode")}
    ids = {t["vehicle_id"]: i + 1 for i, t in enumerate(trips)}
    reverse = {value: key for key, value in ids.items()}
    lanes = {t["vehicle_id"]: t["lane"] for t in trips}
    transitions, requests = defaultdict(list), defaultdict(list)
    for t in trips:
        for event in t["lane_events"]:
            transitions[round(event["time_s"] * 10)].append((t["vehicle_id"], event["to_lane"]))
        for event in t["lane_completion_events"]:
            requests[round(event["requested_s"] * 10)].append(dict(vehicle_id=t["vehicle_id"], **event))
    statistics, sample_rows, event_rows = defaultdict(lambda: defaultdict(int)), [], []
    previous, old_time, checks, bindings = {}, None, 0, 0
    drop = 1000.0 if record["scenario"] == "lane_drop" else None
    for line in gzip.open(raw, "rt", encoding="utf-8"):
        frame = json.loads(line)
        now, states = frame["time_s"], frame["states"]
        tick = round(now * 10)
        for key, lane in transitions[tick]:
            lanes[key] = lane
        sample = tick % 10 == 0 and window[0] <= now < window[1]
        if sample or requests.get(tick):
            vehicles = {key: module.Vehicle(ids[key], s[0], s[1], s[2], lanes[key],
                         (s[1] - previous[key][1]) / (now - old_time) if key in previous else 0.0, s[3], now)
                        for key, s in states.items()}
            def query(key):
                nonlocal checks, bindings
                ego = vehicles[key]
                rows = tuple(sorted((c for c in vehicles.values() if c.track != ego.track and -100 <= c.x - ego.x <= 200), key=lambda c: (c.x, c.y, c.speed)))
                namespace = dict(module.__dict__, ego=ego, rows=rows, mode=record["mode"], drop_x=drop)
                for name, code in context:
                    namespace[name] = eval(code, namespace, namespace)
                fill_args = [eval(code, namespace, namespace) for code in arguments]
                trace = traced(ego, rows, *fill_args)
                reference = module._fill(ego, rows, *fill_args)
                winner = trace["winner"]
                own_lane = winner[1] if winner is not None and winner[0].track == ego.track else None
                assert own_lane == reference
                checks += 1
                counts = trace["counts"]
                info = dict(**ident, vehicle_id=key, time_s=now, x=ego.x, lane=ego.lane, receiving=namespace["receiving"],
                            fill_lanes=fill_args[0], future_argument=fill_args[1] if len(fill_args) > 1 else False,
                            counts_json=json.dumps(counts), choices_n=len(trace["choices"]), own_fresh_winner_lane=own_lane,
                            winner_vehicle=reverse[winner[0].track] if winner else None, winner_lane=winner[1] if winner else None)
                if winner:
                    car, lane = winner
                    best = min(trace["choices"], key=lambda item: item[0])
                    info.update(winner_cost=best[0][0], winner_score_json=json.dumps(best[0]),
                                winner_phi_delta=2 * (counts[lane] - counts[car.lane] + 1))
                    assert info["winner_phi_delta"] < 0
                if own_lane is not None:
                    priority = module._mandatory_priority(ego, rows, own_lane, drop)
                    info["blocked_by_mandatory_priority"] = priority
                    target, speed, gap = module._merge_target(ego, rows, own_lane)
                    info.update(scored_gap_front=reverse.get(gap[0]), scored_gap_rear=reverse.get(gap[1]), scored_target_x=target)
                    if not priority:
                        command, memory = module._decide(ego, rows, module.Memory(), record["mode"], drop)
                        assert command.reason == "fill_layer" and command.lane == own_lane and command.target_x == target and memory.gap == gap
                        info["same_frame_fresh_binding_verified"] = True
                        bindings += 1
                return info
            if sample:
                for key, ego in vehicles.items():
                    if abs(ego.vy) >= .1 or abs(ego.y - (ego.lane + .5) * 3.3) > .15:
                        continue
                    info = query(key)
                    region = "upstream" if ego.x < 640 else "preparation" if ego.x < 1000 else "downstream"
                    group = region, bool(info["future_argument"])
                    statistics[group]["sampled_resting_car_frames"] += 1
                    statistics[group]["any_candidate_frames"] += info["choices_n"] > 0
                    statistics[group]["own_fresh_winner_frames"] += info["own_fresh_winner_lane"] is not None
                    if info["own_fresh_winner_lane"] is not None:
                        sample_rows.append(info)
            for event in requests[tick]:
                key = event["vehicle_id"]
                info = query(key)
                counts = json.loads(info["counts_json"])
                a, b = event["from_lane"], event["to_lane"]
                info.update(from_lane=a, to_lane=b, requested_s=event["requested_s"],
                            latest_submission_matches_fresh_winner=info["own_fresh_winner_lane"] == b,
                            requested_phi_delta=2 * (counts[b] - counts[a] + 1) if max(a, b) < len(counts) else None,
                            ending_to1_after640=a == 2 and b == 1 and info["x"] >= 640)
                event_rows.append(info)
        previous, old_time = states, now
    write_csv(output / (folder.name + "_sampled_fresh_winners.csv"), sample_rows)
    write_csv(output / (folder.name + "_completed_submission_scores.csv"), event_rows)
    write_csv(output / (folder.name + "_sampled_scope_counts.csv"), [dict(**ident, region=k[0], future=k[1], **v) for k, v in statistics.items()])
    info = dict(**ident, source_sha256=sha(source), positions_sha256=seal["originals"][raw.name]["sha256"],
                window_s=window, sample_period_s=1.0, pure_winner_equivalence_checks=checks,
                same_frame_fresh_binding_checks=bindings, action_reasons=result["action_reasons"], execution=result["execution"],
                public_scope_expressions=[(name, ast.unparse(ast.parse(code.co_filename))) for name, code in []],
                limitations=["Sampled fresh-winner opportunities use fixed 1s snapshots and empty own Memory for interface verification; they are not imputed actual intentions.",
                             "All completed submissions use original latest-native timestamp. A held executing intention can differ from the current fresh winner without violating the rule.",
                             "Potential decreases are hypothetical single-car updates in one bounded local view, not a proof of globally monotone simultaneous behavior."])
    (output / (folder.name + "_provenance.json")).write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / (folder.name + "_instrumented_fill.py")).write_text(trace_source + "\n", encoding="utf-8")
    print(json.dumps(dict(**ident, checks=checks, bindings=bindings, output=str(output))), flush=True)


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
    (args.output / "audit_real_gap_scores_source.py").write_bytes(Path(__file__).read_bytes())
    for record in records:
        analyze(Path(record["case_output"]), args.output, (args.window_start, args.window_end))
