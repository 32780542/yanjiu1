"""Fixed chain24 approach-length experiment. Each controller runs in a fresh process."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ROADS = {"3to2": "formation_demo", "4to3": "four_to_three_demo",
         "3to4": "three_to_four_demo", "2to3": "two_to_three_demo"}


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def describe_frame(states, lane_count):
    columns = [sorted((s[0] for s in states.values() if round(s[1]/3.3-.5) == lane), reverse=True)
               for lane in range(lane_count)]
    xs = [s[0] for s in states.values()]
    speeds = [s[2] for s in states.values()]
    gap = 5.5 + .85 * sum(speeds)/len(speeds)
    best_spread = float("inf")
    for phase in (range(2) if lane_count == 2 else (0,)):
        origins = [x + (index + ((lane+phase) % 2)/2)*gap for lane, col in enumerate(columns)
                   for index, x in enumerate(col)]
        best_spread = min(best_spread, max(origins)-min(origins))
    return dict(counts="/".join(str(len(c)) for c in columns), front_m=round(max(xs), 2),
                span_m=round(max(xs)-min(xs), 2), balanced_target_span_m=round((len(xs)/lane_count-.5)*gap, 2),
                phase_spread_m=round(best_spread, 2), speed_spread_m_s=round(max(speeds)-min(speeds), 3))


def run_one(args):
    model, road, raw_length = args.case
    length = int(raw_length)
    source = (args.base if model == "11.24" else args.theta)/"source"
    sys.path.insert(0, str(source))
    from experiments import native_sumo as native
    from noa import native_rules
    if Path(native_rules.__file__).resolve() != source/"noa/native_rules.py" or native.ROOT != source:
        raise RuntimeError("Simulator and controller must both load from the requested frozen source")
    from experiments import complete_layers  # Bind the frozen assessor dependency in this process.
    spec = importlib.util.spec_from_file_location("length_measure", args.theta/"source/measure.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)

    tape = args.theta/f"{road}_chain24.json"
    scenario = ROADS[road]
    home = args.output/f"{model}_{road}_{length}"
    home.mkdir()
    original = args.theta/f"{road}_s20_q1750_chain24"
    if model != "11.24" and length == 1600 and (original/"measure.json").is_file():
        folder, = [p for p in original.iterdir() if (p/"positions.jsonl.gz").is_file()]
        report = json.loads((original/"measure.json").read_bytes())
    else:
        # run_case and build_network consult the same table. This is process-local.
        old_up, old_down, outgoing = native.ROAD_LAYOUT[scenario]
        assert (old_up, old_down) == (1600, 1000)
        native.ROAD_LAYOUT[scenario] = length, old_down, outgoing
        folder = native.run_case(mode="transform", scenario=scenario, seed=20, flow=1750., duration=8.,
                                 initial=json.loads(tape.read_bytes()), output_base=home, gui=False)
        report = audit.measure(folder, cohort=True)
        (home/"measure.json").write_text(json.dumps(report), encoding="utf-8")
    (incoming, actual_length), (outgoing, downstream) = audit.road_layout(folder)
    assert actual_length == length and downstream == 1000
    result = json.loads((folder/"result.json").read_bytes())
    loaded_rules_sha = sha(Path(native_rules.__file__))
    assert result["source_sha256"]["noa/native_rules.py"] == loaded_rules_sha == sha(source/"noa/native_rules.py")
    row = dict(controller=model, road=road, length_m=length, status=result["status"],
               completed=result["completed"], collisions=result["collisions"], teleports=result["teleports"],
               tape_sha256=sha(tape), arrivals_sha256=report["arrivals_sha256"],
               trajectory_sha256=sha(folder/"positions.jsonl.gz"), rules_sha256=loaded_rules_sha,
               frames_sha256=hashlib.sha256(gzip.decompress((folder/"positions.jsonl.gz").read_bytes())).hexdigest(),
               run=(folder.relative_to(ROOT) if folder.is_relative_to(ROOT) else folder).as_posix())
    last = {}
    with gzip.open(folder/"positions.jsonl.gz", "rt") as stream:
        for frame in map(json.loads, stream):
            states, t = frame["states"], frame["time_s"]
            if len(states) != 24:
                continue
            front, rear = max(s[0] for s in states.values()), min(s[0] for s in states.values())
            if "initial_front_m" not in row:
                row.update(initial_front_m=round(front, 2), initial_span_m=round(front-rear, 2))
            for region, inside in (("upstream", front < length-200.), ("downstream", rear >= length)):
                if inside:
                    last[region] = t, states
                if t == report[region]["first_whole_s"]:
                    row[region+"_first_front_m"] = round(front, 2)
                    row[region+"_front_travel_to_shape_m"] = round(front-row["initial_front_m"], 2)
                    if region == "downstream":
                        row["downstream_first_front_beyond_cut_m"] = round(front-length, 2)
    for region, count in (("upstream", incoming), ("downstream", outgoing)):
        for k in ("max_present", "all_present_total_s", "peak_size", "first_whole_s", "whole_hold_s", "whole_total_s"):
            row[region+"_"+k] = report[region][k]
        row[region+"_peak_counts"] = "/".join(map(str, report[region]["peak"]["counts"]))
        if region in last:
            t, states = last[region]
            row[region+"_last_full_t_s"] = t
            row.update({region+"_last_"+k: v for k, v in describe_frame(states, count).items()})
    row["paired_peak"] = report["paired_peak"]["size"]
    (home/"row.json").write_text(json.dumps(row, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theta", "--candidate-batch", type=Path, default=ROOT/"tmp/nov25study/theta_lattice")
    parser.add_argument("--base", type=Path, default=ROOT/"tmp/nov25study/baseline_1124_demo")
    parser.add_argument("--candidate-name", default="theta")
    parser.add_argument("--candidate-only", action="store_true")
    parser.add_argument("--lengths", type=int, nargs="+", default=[1600,2800,4000])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--case", nargs=3, help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.theta, args.base, args.output = (p.resolve() for p in (args.theta, args.base, args.output))
    if args.case:
        return run_one(args)
    args.output.mkdir(parents=True, exist_ok=False)
    models = [args.candidate_name] if args.candidate_only else [args.candidate_name, "11.24"]
    cells = [(m, r, str(n)) for m in models for r in ROADS
             if m != "11.24" or r in ("3to2", "4to3") for n in args.lengths]
    def launch(cell):
        with (args.output/("_".join(cell)+".log")).open("wb") as log:
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--theta", str(args.theta),
                            "--base", str(args.base), "--output", str(args.output), "--case", *cell],
                           check=True, stdout=log, stderr=subprocess.STDOUT)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(launch, cells))
    rows = [json.loads((args.output/("_".join(cell))/"row.json").read_bytes()) for cell in cells]
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (args.output/"summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
