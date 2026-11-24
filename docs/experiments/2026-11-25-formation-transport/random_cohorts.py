"""Paired native SUMO tests on seeded random physical initial conditions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys

from run_study import OPTIONAL, REQUIRED


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ROADS = {"3to2": "formation_demo", "4to3": "four_to_three_demo"}
SPANS = {12: {"compact": 95., "long": 380.}, 24: {"compact": 185., "long": 580.}}


def write(path, data):
    path.write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def make_tape(seed, road, count, spacing):
    """Uniform lane choices subject to packing capacity; ordered hard-core longitudinal samples."""
    rng = random.Random(f"random-cohort-v1/{seed}/{road}/{count}/{spacing}")
    lanes, span = int(road[0]), SPANS[count][spacing]
    counts = [0]*lanes
    for _ in range(count):
        available = [i for i, n in enumerate(counts) if n < int(span//20)+1]
        counts[rng.choice(available)] += 1
    cars = []
    for lane, n in enumerate(counts):
        residual = span - 20*(n-1)
        sites = sorted(rng.uniform(0, residual) for _ in range(n))
        cars.extend(dict(lane=lane, x=s+20*i, speed=round(rng.uniform(26.5,30.), 3))
                    for i, s in enumerate(sites))
    cars.sort(key=lambda row: -row["x"])
    front, rear = cars[0]["x"], cars[-1]["x"]
    for car in cars:
        car["x"] = round(650.-span*(front-car["x"])/(front-rear), 4)
    return cars


def freeze(src, dest):
    dest.mkdir(parents=True)
    (dest/"tmp").mkdir()
    files = [*REQUIRED, *(name for name in OPTIONAL if (src/name).is_file())]
    for name in files:
        target = dest/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src/name, target)
    return {name: sha((dest/name).read_bytes()) for name in files}


def run_one(out, cell):
    model, road, count_text, spacing, seed_text = cell
    count, seed = int(count_text), int(seed_text)
    source = out/"frozen"/model
    sys.path.insert(0, str(source))
    from experiments import native_sumo as native
    from noa import native_rules
    if Path(native_rules.__file__).resolve() != source/"noa/native_rules.py" or native.ROOT != source:
        raise RuntimeError("Simulator and controller must both load from the requested frozen source")
    key = "_".join(cell[1:])
    tape_file = out/"tapes"/(key+".json")
    tape = json.loads(tape_file.read_bytes())
    case_dir = out/(model+"_"+key)
    folder = native.run_case(mode="transform", scenario=ROADS[road], seed=seed, flow=1750, duration=8.,
                             gui=False, output_base=case_dir, initial=tape)
    from experiments import complete_layers
    spec = importlib.util.spec_from_file_location("random_measure", out/"frozen/measure.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    report = audit.measure(folder, cohort=True)
    write(case_dir/"measure.json", report)
    result = json.loads((folder/"result.json").read_bytes())
    assert result["source_sha256"]["noa/native_rules.py"] == sha((source/"noa/native_rules.py").read_bytes())
    with gzip.open(folder/"positions.jsonl.gz", "rt") as stream:
        first = json.loads(next(stream))
    states = {key: s[:3] for key, s in first["states"].items()}
    errors = [(abs(states[f"initial_{i}"][0]-car["x"]),
               abs(states[f"initial_{i}"][1]-(.5+car["lane"])*3.3),
               abs(states[f"initial_{i}"][2]-car["speed"]))
              for i, car in enumerate(tape) if f"initial_{i}" in states]
    initial_ok = len(states)==count and all(max(e)<1e-5 for e in errors)
    row = dict(model=model, road=road, n=count, spacing=spacing, seed=seed, span_m=SPANS[count][spacing],
               entry_counts="/".join(str(sum(c["lane"]==i for c in tape)) for i in range(int(road[0]))),
               request_sha256=report["arrivals_sha256"], tape_sha256=sha(tape_file.read_bytes()),
               first_frame_s=first["time_s"], first_frame_n=len(states), initial_matches_request=initial_ok,
               first_frame_sha256=sha(json.dumps(states, sort_keys=True).encode()), run=folder.relative_to(out).as_posix())
    if errors:
        row.update(zip(("first_max_x_error_m", "first_max_y_error_m", "first_max_speed_error_m_s"),
                       (max(values) for values in zip(*errors))))
    for k in ("status", "completed", "collisions", "teleports", "lane_changes", "lane_change_completions"):
        row[k] = result[k]
    for region in ("upstream", "downstream"):
        for k in ("max_present", "all_present_total_s", "whole_hold_s", "peak_size"):
            row[region+"_"+k] = report[region][k]
    row["same_ids_peak"] = report["paired_peak"]["size"]
    row["whole_both"] = (row["same_ids_peak"]==count and
                         min(row["upstream_whole_hold_s"],row["downstream_whole_hold_s"])>0.)
    for stage in ("formation", "transform", "observed_population"):
        moves = report.get(stage+"_moves")
        fields = {"bound_total": "min_total_crossings", "bound_max": "min_max_crossings"}
        for label, key in fields.items():
            row[stage+"_"+label] = moves[key] if moves else None
        for key, label in (("midpoint","actual"), ("completed","settled")):
            row[stage+"_"+label+"_total"] = moves[key]["total"] if moves else None
            row[stage+"_"+label+"_max"] = moves[key]["max_per_car"] if moves else None
            row[stage+"_"+label+"_chain_ok"] = not moves[key]["mismatch_ids"] if moves else None
        valid = moves and not moves["midpoint"]["mismatch_ids"]
        row[stage+"_excess_total"] = moves["midpoint"]["total"]-moves["min_total_crossings"] if valid else None
        row[stage+"_excess_max"] = moves["midpoint"]["max_per_car"]-moves["min_max_crossings"] if valid else None
    write(case_dir/"row.json", row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-source", type=Path, default=ROOT/"tmp/nov25study/baseline_1124_demo/source")
    parser.add_argument("--candidate-source", type=Path, default=ROOT/"tmp/nov25study/kappa_robust/source")
    parser.add_argument("--evaluator", type=Path, default=HERE/"measure.py")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1511,1512,1513])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", nargs=5, help=argparse.SUPPRESS)
    args = parser.parse_args()
    out = args.output.resolve()
    if args.case:
        return run_one(out, args.case)
    out.mkdir(parents=True, exist_ok=False)
    frozen = out/"frozen"
    hashes = {name: freeze(path, frozen/name) for name,path in (
        ("base",args.base_source), ("candidate",args.candidate_source))}
    shutil.copyfile(args.evaluator, frozen/"measure.py")
    (out/"tapes").mkdir()
    cases = []
    for road,n,spacing,seed in itertools.product(ROADS, (12,24), ("compact","long"), args.seeds):
        case = [road,str(n),spacing,str(seed)]
        write(out/"tapes"/("_".join(case)+".json"), make_tape(seed,road,n,spacing))
        cases.extend([[model,*case] for model in hashes])
    write(out/"manifest.json", dict(seeds=args.seeds, sources=hashes,
          evaluator_sha256=sha((frozen/"measure.py").read_bytes()), generator_sha256=sha(Path(__file__).read_bytes())))
    def launch(cell):
        with (out/("_".join(cell)+".log")).open("wb") as log:
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--output", str(out), "--case", *cell],
                           check=True, stdout=log, stderr=subprocess.STDOUT)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(launch,cases))
    rows = [json.loads((out/"_".join(cell)/"row.json").read_bytes()) for cell in cases]
    for a,b in zip(rows[::2],rows[1::2]):
        matched = (a["request_sha256"]==b["request_sha256"] and a["first_frame_sha256"]==b["first_frame_sha256"]
                   and a["first_frame_s"]==b["first_frame_s"] and a["first_frame_n"]==a["n"])
        a["paired_full_first_frame"] = b["paired_full_first_frame"] = matched
    with (out/"summary.csv").open("w",newline="",encoding="utf-8") as stream:
        writer = csv.DictWriter(stream,fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader()
        writer.writerows(rows)


if __name__=="__main__":
    main()
